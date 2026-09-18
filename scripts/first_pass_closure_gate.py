#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

MARKER_RE = re.compile(r"<!--\s*FPC_RECEIPT_V1\s*(\{.*?\})\s*-->", re.S)
CODEX_SUMMARY_MARKER = "<!-- codex-pull-request-review-summary -->"
CODEX_LOGIN = "chatgpt-codex-connector"
REQUIRED_PURPOSES = {"canonical_self_test", "mutation_test", "exact_head_ci"}

class GateError(RuntimeError):
    pass

@dataclass
class ApiClient:
    token: str
    api_root: str = "https://api.github.com"

    def get(self, path: str) -> Any:
        req = urllib.request.Request(
            self.api_root + path,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "gbo-first-pass-closure-gate/1",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise GateError(f"GitHub API {exc.code} for {path}: {body[:500]}") from exc

def parse_receipt(body: str | None) -> dict[str, Any]:
    m = MARKER_RE.search(body or "")
    if not m:
        raise GateError(
            "MISSING_RECEIPT: add <!-- FPC_RECEIPT_V1 {json} --> to the PR body after exact-head proofs and review complete"
        )
    try:
        receipt = json.loads(m.group(1))
    except json.JSONDecodeError as exc:
        raise GateError(f"INVALID_RECEIPT_JSON: {exc}") from exc
    if receipt.get("schema") != "first_pass_closure/v1":
        raise GateError("INVALID_RECEIPT_SCHEMA")
    if not isinstance(receipt.get("head_sha"), str) or len(receipt["head_sha"]) != 40:
        raise GateError("INVALID_RECEIPT_HEAD_SHA")
    runs = receipt.get("required_runs")
    if not isinstance(runs, list) or not runs:
        raise GateError("MISSING_REQUIRED_RUNS")
    return receipt

def review_is_completed_for_head(comments: list[dict[str, Any]], head_sha: str) -> tuple[bool, int | None]:
    prefix = head_sha[:7]
    summaries = [
        c for c in comments
        if CODEX_SUMMARY_MARKER in (c.get("body") or "")
    ]
    for c in reversed(summaries):
        body = c.get("body") or ""
        if f"`{prefix}`" in body and "**Completed**" in body:
            return True, c.get("id")
    return False, None

def codex_finding_reviews_for_head(reviews: list[dict[str, Any]], head_sha: str) -> list[dict[str, Any]]:
    prefixes = {head_sha[:7], head_sha[:10], head_sha[:12]}
    out = []
    for review in reviews:
        login = ((review.get("user") or review.get("author") or {}).get("login"))
        if login != CODEX_LOGIN:
            continue
        body = review.get("body") or ""
        if review.get("state") != "COMMENTED":
            continue
        if any(f"`{p}`" in body for p in prefixes):
            out.append(review)
    return out

def validate_run(client: ApiClient, spec: dict[str, Any], receipt_head: str) -> dict[str, Any]:
    repo = spec.get("repo")
    run_id = spec.get("run_id")
    purposes = spec.get("purposes")
    if not isinstance(repo, str) or repo.count("/") != 1:
        raise GateError("INVALID_RUN_REPO")
    if type(run_id) is not int or run_id <= 0:
        raise GateError("INVALID_RUN_ID")
    if not isinstance(purposes, list) or not purposes or not all(isinstance(p, str) for p in purposes):
        raise GateError("INVALID_RUN_PURPOSES")
    run = client.get(f"/repos/{repo}/actions/runs/{run_id}")
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        raise GateError(f"RUN_NOT_SUCCESS: {repo}#{run_id}")
    if run.get("head_sha") != receipt_head:
        raise GateError(
            f"RUN_HEAD_MISMATCH: {repo}#{run_id} has {run.get('head_sha')} expected {receipt_head}"
        )
    return {
        "repo": repo,
        "run_id": run_id,
        "purposes": purposes,
        "status": run.get("status"),
        "conclusion": run.get("conclusion"),
        "head_sha": run.get("head_sha"),
    }

def evaluate(client: ApiClient, repo: str, pr_number: int) -> dict[str, Any]:
    pr = client.get(f"/repos/{repo}/pulls/{pr_number}")
    head_sha = ((pr.get("head") or {}).get("sha"))
    if not isinstance(head_sha, str) or len(head_sha) != 40:
        raise GateError("PR_HEAD_UNAVAILABLE")

    receipt = parse_receipt(pr.get("body"))
    if receipt["head_sha"] != head_sha:
        raise GateError(f"STALE_HEAD: receipt={receipt['head_sha']} current={head_sha}")

    proven_purposes: set[str] = set()
    run_receipts = []
    for spec in receipt["required_runs"]:
        rr = validate_run(client, spec, head_sha)
        run_receipts.append(rr)
        proven_purposes.update(rr["purposes"])
    missing = sorted(REQUIRED_PURPOSES - proven_purposes)
    if missing:
        raise GateError("MISSING_REQUIRED_PROOF_PURPOSE: " + ",".join(missing))

    comments = client.get(f"/repos/{repo}/issues/{pr_number}/comments?per_page=100")
    completed, summary_id = review_is_completed_for_head(comments, head_sha)
    if not completed:
        raise GateError("CODEX_REVIEW_NOT_COMPLETED_ON_EXACT_HEAD")

    reviews = client.get(f"/repos/{repo}/pulls/{pr_number}/reviews?per_page=100")
    findings = codex_finding_reviews_for_head(reviews, head_sha)
    if findings:
        raise GateError(f"CODEX_MATERIAL_FINDINGS_ON_EXACT_HEAD: {len(findings)}")

    return {
        "schema": "first_pass_closure_gate_receipt/v1",
        "status": "PASS_FIRST_PASS_CLOSURE_GATE",
        "repository": repo,
        "pr_number": pr_number,
        "head_sha": head_sha,
        "codex_summary_comment_id": summary_id,
        "codex_material_finding_review_count": 0,
        "proven_purposes": sorted(proven_purposes),
        "required_runs": run_receipts,
        "merge_allowed": True,
        "authority_transfer": False,
        "formal_credit_delta": 0,
    }

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    ap.add_argument("--pr", type=int)
    ap.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"))
    ap.add_argument("--out")
    args = ap.parse_args()

    if not args.repo or not args.pr or not args.token:
        raise SystemExit("repo, pr and token are required")

    try:
        receipt = evaluate(ApiClient(args.token), args.repo, args.pr)
    except GateError as exc:
        print(json.dumps({
            "schema": "first_pass_closure_gate_receipt/v1",
            "status": "FAIL_FIRST_PASS_CLOSURE_GATE",
            "reason": str(exc),
            "merge_allowed": False,
            "authority_transfer": False,
            "formal_credit_delta": 0,
        }, sort_keys=True))
        return 2

    payload = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(payload)
    print(payload, end="")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
