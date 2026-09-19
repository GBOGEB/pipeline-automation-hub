#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

MARKER_RE = re.compile(r"<!--\s*FPC_RECEIPT_V1\s*(\{.*?\})\s*-->", re.S)
CODEX_SUMMARY_MARKER = "<!-- codex-pull-request-review-summary -->"
CODEX_LOGIN = "chatgpt-codex-connector"
REQUIRED_PURPOSES = {"canonical_self_test", "mutation_test", "exact_head_ci"}


class GateError(RuntimeError):
    pass


class ApiClient:
    def __init__(self, token: str, api_root: str = "https://api.github.com"):
        self.token = token
        self.api_root = api_root

    def get(self, path: str) -> Any:
        req = urllib.request.Request(
            self.api_root + path,
            headers={
                "Authorization": f"Bearer {self.token}",
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
        with open(path, "r", encoding="utf-8") as handle:
            policy = json.load(handle)
    except FileNotFoundError as exc:
        raise GateError(f"POLICY_LOAD_FAILED:MISSING:{path}") from exc
    except PermissionError as exc:
        raise GateError(f"POLICY_LOAD_FAILED:PERMISSION:{path}") from exc
    except json.JSONDecodeError as exc:
        raise GateError(f"POLICY_LOAD_FAILED:INVALID_JSON:{exc.msg}") from exc
    except OSError as exc:
        raise GateError(f"POLICY_LOAD_FAILED:OSERROR:{type(exc).__name__}") from exc

    if not isinstance(policy, dict):
        raise GateError("POLICY_LOAD_FAILED:ROOT_NOT_OBJECT")
    if not isinstance(policy.get("proof_identity_allowlist"), dict):
        raise GateError("POLICY_LOAD_FAILED:PROOF_IDENTITY_ALLOWLIST_MISSING")
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
        if f"`{prefix}`" in body and "**Completed**" in body:
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
        if any(f"`{p}`" in body for p in prefixes):
            out.append(review)
    return out


def workflow_content_sha256(client: Any, repo: str, path: str, ref: str) -> str:
    payload = client.get(f"/repos/{repo}/contents/{path}?ref={ref}")
    if not isinstance(payload, dict):
        raise GateError(f"WORKFLOW_CONTENT_UNAVAILABLE: {repo}:{path}@{ref[:12]}")
    if payload.get("encoding") != "base64" or not isinstance(payload.get("content"), str):
        raise GateError(f"WORKFLOW_CONTENT_ENCODING_INVALID: {repo}:{path}@{ref[:12]}")
    try:
        raw = base64.b64decode(payload["content"], validate=False)
    except Exception as exc:
        raise GateError(f"WORKFLOW_CONTENT_DECODE_FAILED: {repo}:{path}@{ref[:12]}") from exc
    return hashlib.sha256(raw).hexdigest()


def allowed_purposes(
    client: Any,
    policy: dict[str, Any],
    subject_repo: str,
    base_sha: str,
    run: dict[str, Any],
) -> tuple[set[str], dict[str, Any]]:
    run_repo = ((run.get("repository") or {}).get("full_name")) or subject_repo
    run_name = run.get("name")
    run_path = run.get("path")
    run_head = run.get("head_sha")
    if not isinstance(run_path, str) or not isinstance(run_head, str):
        raise GateError("PROOF_WORKFLOW_IDENTITY_INCOMPLETE")

    matched_purposes: set[str] = set()
    allow = policy.get("proof_identity_allowlist") or {}
    for purpose, identities in allow.items():
        if purpose not in REQUIRED_PURPOSES or not isinstance(identities, list):
            continue
        for identity in identities:
            if not isinstance(identity, dict):
                continue
            if (
                identity.get("repo") == run_repo
                and identity.get("workflow_name") == run_name
                and identity.get("workflow_path") == run_path
            ):
                matched_purposes.add(purpose)
                break

    if not matched_purposes:
        raise GateError(
            f"UNTRUSTED_PROOF_WORKFLOW_IDENTITY: {run_repo}:{run_name}:{run_path}"
        )

    if run_repo != subject_repo:
        raise GateError(
            f"UNSUPPORTED_CROSS_REPO_PROOF_IDENTITY: {run_repo} subject={subject_repo}"
        )

    candidate_digest = workflow_content_sha256(client, run_repo, run_path, run_head)
    base_digest = workflow_content_sha256(client, subject_repo, run_path, base_sha)
    if candidate_digest != base_digest:
        raise GateError(
            "PROOF_WORKFLOW_MUTATED_FROM_TRUSTED_BASE: "
            f"{run_path} candidate={candidate_digest[:12]} base={base_digest[:12]}"
        )

    return matched_purposes, {
        "workflow_content_sha256": candidate_digest,
        "trusted_base_workflow_sha256": base_digest,
        "trusted_base_sha": base_sha,
    }


def validate_run(
    client: Any,
    spec: dict[str, Any],
    receipt_head: str,
    subject_repo: str,
    base_sha: str,
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

    run = {**run, "repository": {"full_name": repo}}
    purposes, trust = allowed_purposes(client, policy, subject_repo, base_sha, run)
    return {
        "repo": repo,
        "run_id": run_id,
        "workflow_name": run.get("name"),
        "workflow_path": run.get("path"),
        "purposes": sorted(purposes),
        "status": run.get("status"),
        "conclusion": run.get("conclusion"),
        "head_sha": run.get("head_sha"),
        **trust,
    }


def evaluate(
    client: Any, repo: str, pr_number: int, policy: dict[str, Any]
) -> dict[str, Any]:
    pr = client.get(f"/repos/{repo}/pulls/{pr_number}")
    head_sha = ((pr.get("head") or {}).get("sha"))
    base_sha = ((pr.get("base") or {}).get("sha"))
    if not isinstance(head_sha, str) or len(head_sha) != 40:
        raise GateError("PR_HEAD_UNAVAILABLE")
    if not isinstance(base_sha, str) or len(base_sha) != 40:
        raise GateError("PR_BASE_UNAVAILABLE")

    receipt = parse_receipt(pr.get("body"))
    if receipt["head_sha"] != head_sha:
        raise GateError(f"STALE_HEAD: receipt={receipt['head_sha']} current={head_sha}")

    proven_purposes: set[str] = set()
    run_receipts = []
    for spec in receipt["required_runs"]:
        rr = validate_run(client, spec, head_sha, repo, base_sha, policy)
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
        raise GateError(f"CODEX_MATERIAL_FINDINGS_ON_EXACT_HEAD: {len(findings)}")

    return {
        "schema": "first_pass_closure_gate_receipt/v2",
        "status": "PASS_FIRST_PASS_CLOSURE_GATE",
        "repository": repo,
        "pr_number": pr_number,
        "head_sha": head_sha,
        "base_sha": base_sha,
        "codex_summary_comment_id": summary_id,
        "codex_material_finding_review_count": 0,
        "proven_purposes": sorted(proven_purposes),
        "required_runs": run_receipts,
        "merge_allowed": True,
        "authority_transfer": False,
        "formal_credit_delta": 0,
    }


def fail_receipt(reason: str) -> dict[str, Any]:
    return {
        "schema": "first_pass_closure_gate_receipt/v2",
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
    ap.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"))
    ap.add_argument("--policy", required=True)
    ap.add_argument("--out")
    args = ap.parse_args()

    receipt: dict[str, Any]
    code: int
    try:
        if not args.repo or not args.pr or not args.token:
            raise GateError("ADMISSION_ARGUMENTS_MISSING: repo, pr and token are required")
        policy = load_policy(args.policy)
        receipt = evaluate(ApiClient(args.token), args.repo, args.pr, policy)
        code = 0
    except GateError as exc:
        receipt = fail_receipt(str(exc))
        code = 2
    except Exception as exc:
        receipt = fail_receipt(
            f"UNHANDLED_ADMISSION_FAILURE:{type(exc).__name__}:{str(exc)[:300]}"
        )
        code = 2

    payload = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.out:
        try:
            with open(args.out, "w", encoding="utf-8") as handle:
                handle.write(payload)
        except OSError:
            code = 2
    print(payload, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
