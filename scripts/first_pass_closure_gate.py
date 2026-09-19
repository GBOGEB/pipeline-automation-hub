#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

MARKER_RE = re.compile(r"<!--\s*FPC_RECEIPT_V1\s*(\{.*?\})\s*-->", re.S)
CODEX_SUMMARY_MARKER = "<!-- codex-pull-request-review-summary -->"
CODEX_LOGIN = "chatgpt-codex-connector"
REQUIRED_PURPOSES = {"canonical_self_test", "mutation_test", "exact_head_ci"}


class GateError(RuntimeError):
    pass


class ApiClient:
    def __init__(self, api_root: str = "https://api.github.com"):
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise GateError("GITHUB_TOKEN_UNAVAILABLE")
        self._auth_token = token
        self.api_root = api_root

    def get(self, path: str) -> Any:
        req = urllib.request.Request(
            self.api_root + path,
            headers={
                "Authorization": f"Bearer {self._auth_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "gbo-first-pass-closure-gate/2",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise GateError(f"GitHub API {exc.code} for {path}: {body[:500]}") from exc

    def get_all(self, path: str) -> list[Any]:
        rows: list[Any] = []
        page = 1
        while True:
            sep = "&" if "?" in path else "?"
            chunk = self.get(f"{path}{sep}per_page=100&page={page}")
            if not isinstance(chunk, list):
                raise GateError(f"EXPECTED_LIST: {path}")
            rows.extend(chunk)
            if len(chunk) < 100:
                return rows
            page += 1


def load_policy(path: str) -> dict[str, Any]:
    try:
        raw = Path(path).read_text(encoding="utf-8")
        policy = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError(f"POLICY_LOAD_FAILED: {type(exc).__name__}") from exc
    if not isinstance(policy, dict):
        raise GateError("POLICY_LOAD_FAILED: EXPECTED_OBJECT")
    return policy


def parse_receipt(body: str | None) -> dict[str, Any]:
    m = MARKER_RE.search(body or "")
    if not m:
        raise GateError("MISSING_RECEIPT")
    try:
        receipt = json.loads(m.group(1))
    except json.JSONDecodeError as exc:
        raise GateError(f"INVALID_RECEIPT_JSON: {exc}") from exc
    if set(receipt) != {"schema", "head_sha", "required_runs"}:
        raise GateError("INVALID_RECEIPT_FIELDS")
    if receipt.get("schema") != "first_pass_closure/v1":
        raise GateError("INVALID_RECEIPT_SCHEMA")
    if not isinstance(receipt.get("head_sha"), str) or len(receipt["head_sha"]) != 40:
        raise GateError("INVALID_RECEIPT_HEAD_SHA")
    runs = receipt.get("required_runs")
    if not isinstance(runs, list) or not runs:
        raise GateError("MISSING_REQUIRED_RUNS")
    return receipt


def review_is_completed_for_head(
    comments: list[dict[str, Any]], head_sha: str
) -> tuple[bool, int | None]:
    prefix = head_sha[:7]
    summaries = [c for c in comments if CODEX_SUMMARY_MARKER in (c.get("body") or "")]
    for c in reversed(summaries):
        body = c.get("body") or ""
        login = ((c.get("user") or c.get("author") or {}).get("login"))
        if login != CODEX_LOGIN:
            continue
        if f"`{prefix}`".replace("\\", "") in body and "**Completed**" in body:
            return True, c.get("id")
    return False, None


def codex_finding_reviews_for_head(
    reviews: list[dict[str, Any]], head_sha: str
) -> list[dict[str, Any]]:
    prefixes = {head_sha[:7], head_sha[:10], head_sha[:12]}
    out = []
    for review in reviews:
        login = ((review.get("user") or review.get("author") or {}).get("login"))
        if login != CODEX_LOGIN or review.get("state") != "COMMENTED":
            continue
        body = review.get("body") or ""
        if any((f"`{p}`".replace("\\", "")) in body for p in prefixes):
            out.append(review)
    return out


def _content_sha(client: Any, repo: str, path: str, ref: str) -> str:
    quoted_path = urllib.parse.quote(path, safe="/")
    quoted_ref = urllib.parse.quote(ref, safe="")
    row = client.get(f"/repos/{repo}/contents/{quoted_path}?ref={quoted_ref}")
    sha = row.get("sha") if isinstance(row, dict) else None
    if not isinstance(sha, str) or not sha:
        raise GateError(f"TRUSTED_SURFACE_IDENTITY_UNAVAILABLE: {path}@{ref}")
    return sha


def verify_trusted_surface(
    client: Any, repo: str, head_sha: str, policy: dict[str, Any]
) -> list[dict[str, str]]:
    cfg = policy.get("trusted_proof_surface")
    if not isinstance(cfg, dict):
        raise GateError("TRUSTED_PROOF_SURFACE_MISSING")
    reference_ref = cfg.get("reference_ref")
    paths = cfg.get("paths")
    if not isinstance(reference_ref, str) or not reference_ref:
        raise GateError("TRUSTED_PROOF_REFERENCE_MISSING")
    if not isinstance(paths, list) or not paths or not all(
        isinstance(p, str) and p for p in paths
    ):
        raise GateError("TRUSTED_PROOF_PATHS_INVALID")
    receipts: list[dict[str, str]] = []
    for path in paths:
        trusted_sha = _content_sha(client, repo, path, reference_ref)
        head_path_sha = _content_sha(client, repo, path, head_sha)
        if trusted_sha != head_path_sha:
            raise GateError(f"UNTRUSTED_PROOF_SURFACE_MUTATION: {path}")
        receipts.append(
            {"path": path, "trusted_sha": trusted_sha, "head_sha": head_path_sha}
        )
    return receipts


def allowed_purposes(policy: dict[str, Any], repo: str, run: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    allow = policy.get("proof_identity_allowlist") or {}
    for purpose, identities in allow.items():
        if purpose not in REQUIRED_PURPOSES or not isinstance(identities, list):
            continue
        for identity in identities:
            if not isinstance(identity, dict):
                continue
            if (
                identity.get("repo") == repo
                and identity.get("workflow_name") == run.get("name")
                and identity.get("workflow_path") == run.get("path")
            ):
                out.add(purpose)
                break
    return out


def validate_run(
    client: Any,
    spec: dict[str, Any],
    receipt_head: str,
    policy: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(spec, dict) or set(spec) != {"repo", "run_id"}:
        raise GateError("INVALID_RUN_FIELDS")
    repo = spec["repo"]
    run_id = spec["run_id"]
    if not isinstance(repo, str) or repo.count("/") != 1:
        raise GateError("INVALID_RUN_REPO")
    if type(run_id) is not int or run_id <= 0:
        raise GateError("INVALID_RUN_ID")
    run = client.get(f"/repos/{repo}/actions/runs/{run_id}")
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        raise GateError(f"RUN_NOT_SUCCESS: {repo}#{run_id}")
    if run.get("head_sha") != receipt_head:
        raise GateError(f"RUN_HEAD_MISMATCH: {repo}#{run_id}")
    purposes = sorted(allowed_purposes(policy, repo, run))
    if not purposes:
        raise GateError(f"UNTRUSTED_PROOF_WORKFLOW_IDENTITY: {repo}#{run_id}")
    return {
        "repo": repo,
        "run_id": run_id,
        "workflow_name": run.get("name"),
        "workflow_path": run.get("path"),
        "purposes": purposes,
        "status": run.get("status"),
        "conclusion": run.get("conclusion"),
        "head_sha": run.get("head_sha"),
    }


def evaluate(
    client: Any, repo: str, pr_number: int, policy: dict[str, Any]
) -> dict[str, Any]:
    pr = client.get(f"/repos/{repo}/pulls/{pr_number}")
    head_sha = ((pr.get("head") or {}).get("sha"))
    if not isinstance(head_sha, str) or len(head_sha) != 40:
        raise GateError("PR_HEAD_UNAVAILABLE")

    trusted_surface = verify_trusted_surface(client, repo, head_sha, policy)

    receipt = parse_receipt(pr.get("body"))
    if receipt["head_sha"] != head_sha:
        raise GateError(
            f"STALE_HEAD: receipt={receipt['head_sha']} current={head_sha}"
        )

    proven_purposes: set[str] = set()
    run_receipts = []
    for spec in receipt["required_runs"]:
        rr = validate_run(client, spec, head_sha, policy)
        run_receipts.append(rr)
        proven_purposes.update(rr["purposes"])
    missing = sorted(REQUIRED_PURPOSES - proven_purposes)
    if missing:
        raise GateError("MISSING_REQUIRED_PROOF_PURPOSE: " + ",".join(missing))

    comments = client.get_all(f"/repos/{repo}/issues/{pr_number}/comments")
    completed, summary_id = review_is_completed_for_head(comments, head_sha)
    if not completed:
        raise GateError("CODEX_REVIEW_NOT_COMPLETED_ON_EXACT_HEAD")

    reviews = client.get_all(f"/repos/{repo}/pulls/{pr_number}/reviews")
    findings = codex_finding_reviews_for_head(reviews, head_sha)
    if findings:
        raise GateError(
            f"CODEX_MATERIAL_FINDINGS_ON_EXACT_HEAD: {len(findings)}"
        )

    return {
        "schema": "first_pass_closure_gate_receipt/v1",
        "status": "PASS_FIRST_PASS_CLOSURE_GATE",
        "repository": repo,
        "pr_number": pr_number,
        "head_sha": head_sha,
        "trusted_proof_surface": trusted_surface,
        "codex_summary_comment_id": summary_id,
        "codex_material_finding_review_count": 0,
        "proven_purposes": sorted(proven_purposes),
        "required_runs": run_receipts,
        "merge_allowed": True,
        "authority_transfer": False,
        "formal_credit_delta": 0,
    }


def failure_receipt(reason: str) -> dict[str, Any]:
    return {
        "schema": "first_pass_closure_gate_receipt/v1",
        "status": "FAIL_FIRST_PASS_CLOSURE_GATE",
        "reason": reason,
        "merge_allowed": False,
        "authority_transfer": False,
        "formal_credit_delta": 0,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    ap.add_argument("--pr", type=int)
    ap.add_argument("--policy", required=True)
    ap.add_argument("--out")
    args = ap.parse_args()
    if not args.repo or not args.pr:
        raise SystemExit("repo and pr are required")

    try:
        policy = load_policy(args.policy)
        receipt = evaluate(ApiClient(), args.repo, args.pr, policy)
        code = 0
    except GateError as exc:
        receipt = failure_receipt(str(exc))
        code = 2

    payload = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
    print(payload, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
