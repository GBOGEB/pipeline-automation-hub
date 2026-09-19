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
from pathlib import Path
from typing import Any

MARKER_RE = re.compile(r"<!--\s*FPC_RECEIPT_V1\s*(\{.*?\})\s*-->", re.S)
CODEX_SUMMARY_MARKER = "<!-- codex-pull-request-review-summary -->"
DEFAULT_CODEX_LOGIN = "chatgpt-codex-connector"
REQUIRED_PURPOSES = {"canonical_self_test", "mutation_test", "exact_head_ci"}
PASS_STATUS = "PASS_FIRST_PASS_CLOSURE_GATE"
PASS_SCHEMA = "first_pass_closure_gate_receipt/v3"


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
                "User-Agent": "gbo-first-pass-closure-gate/3",
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
    protected = policy.get("protected_control_paths")
    if not isinstance(protected, list) or not protected or not all(
        isinstance(path, str) and path for path in protected
    ):
        raise GateError("POLICY_LOAD_FAILED:PROTECTED_CONTROL_PATHS_MISSING")
    return policy


def parse_receipt(body: str | None) -> dict[str, Any]:
    match = MARKER_RE.search(body or "")
    if not match:
        raise GateError("MISSING_RECEIPT")
    try:
        receipt = json.loads(match.group(1))
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


def login_matches(actual: str | None, expected: str) -> bool:
    return actual in {expected, f"{expected}[bot]"}


def codex_login(policy: dict[str, Any]) -> str:
    contract = policy.get("codex_contract") or {}
    value = contract.get("reviewer_login") or DEFAULT_CODEX_LOGIN
    return str(value)


def review_is_completed_for_head(
    comments: list[dict[str, Any]], head_sha: str, expected_login: str
) -> tuple[bool, int | None]:
    prefix = head_sha[:7]
    summaries = [c for c in comments if CODEX_SUMMARY_MARKER in (c.get("body") or "")]
    for comment in reversed(summaries):
        body = comment.get("body") or ""
        login = ((comment.get("user") or comment.get("author") or {}).get("login"))
        if not login_matches(login, expected_login):
            continue
        if f"`{prefix}`" in body and "**Completed**" in body:
            return True, comment.get("id")
    return False, None


def codex_finding_reviews_for_head(
    reviews: list[dict[str, Any]], head_sha: str, expected_login: str
) -> list[dict[str, Any]]:
    prefixes = {head_sha[:7], head_sha[:10], head_sha[:12]}
    out: list[dict[str, Any]] = []
    for review in reviews:
        login = ((review.get("user") or review.get("author") or {}).get("login"))
        if not login_matches(login, expected_login) or review.get("state") != "COMMENTED":
            continue
        body = review.get("body") or ""
        if any(f"`{prefix}`" in body for prefix in prefixes):
            out.append(review)
    return out


def protected_control_changes(
    client: Any, repo: str, pr_number: int, policy: dict[str, Any]
) -> list[str]:
    protected = set(policy.get("protected_control_paths") or [])
    files = client.get_all(f"/repos/{repo}/pulls/{pr_number}/files")
    changed: set[str] = set()
    for item in files:
        if not isinstance(item, dict):
            continue
        filename = item.get("filename")
        previous_filename = item.get("previous_filename")
        if isinstance(filename, str):
            changed.add(filename)
        if isinstance(previous_filename, str):
            changed.add(previous_filename)
    return sorted(protected & changed)


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

    protected = protected_control_changes(client, repo, pr_number, policy)
    if protected:
        raise GateError(
            "CONTROL_PLANE_CHANGE_REQUIRES_BOOTSTRAP: " + ",".join(protected)
        )

    receipt = parse_receipt(pr.get("body"))
    if receipt["head_sha"] != head_sha:
        raise GateError(f"STALE_HEAD: receipt={receipt['head_sha']} current={head_sha}")

    proven_purposes: set[str] = set()
    run_receipts: list[dict[str, Any]] = []
    for spec in receipt["required_runs"]:
        run_receipt = validate_run(client, spec, head_sha, repo, base_sha, policy)
        run_receipts.append(run_receipt)
        proven_purposes.update(run_receipt["purposes"])

    missing = sorted(REQUIRED_PURPOSES - proven_purposes)
    if missing:
        raise GateError("MISSING_REQUIRED_PROOF_PURPOSE: " + ",".join(missing))

    expected_login = codex_login(policy)
    comments = client.get_all(f"/repos/{repo}/issues/{pr_number}/comments")
    completed, summary_id = review_is_completed_for_head(
        comments, head_sha, expected_login
    )
    if not completed:
        raise GateError("CODEX_REVIEW_NOT_COMPLETED_ON_EXACT_HEAD")

    reviews = client.get_all(f"/repos/{repo}/pulls/{pr_number}/reviews")
    findings = codex_finding_reviews_for_head(reviews, head_sha, expected_login)
    if findings:
        raise GateError(f"CODEX_MATERIAL_FINDINGS_ON_EXACT_HEAD: {len(findings)}")

    return {
        "schema": PASS_SCHEMA,
        "status": PASS_STATUS,
        "repository": repo,
        "pr_number": pr_number,
        "head_sha": head_sha,
        "base_sha": base_sha,
        "trusted_controller_revision": base_sha,
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
        "schema": PASS_SCHEMA,
        "status": "FAIL_FIRST_PASS_CLOSURE_GATE",
        "reason": reason,
        "merge_allowed": False,
        "authority_transfer": False,
        "formal_credit_delta": 0,
    }


def validate_pass_receipt(
    receipt: dict[str, Any], expected_head: str, expected_base: str
) -> None:
    if receipt.get("schema") != PASS_SCHEMA:
        raise GateError("FINAL_RECEIPT_SCHEMA_NOT_PASS_V3")
    if receipt.get("status") != PASS_STATUS:
        raise GateError("FINAL_RECEIPT_STATUS_NOT_PASS")
    if receipt.get("merge_allowed") is not True:
        raise GateError("FINAL_RECEIPT_MERGE_ALLOWED_NOT_TRUE")
    if receipt.get("head_sha") != expected_head:
        raise GateError("FINAL_RECEIPT_HEAD_MISMATCH")
    if receipt.get("base_sha") != expected_base:
        raise GateError("FINAL_RECEIPT_BASE_MISMATCH")
    if receipt.get("trusted_controller_revision") != expected_base:
        raise GateError("FINAL_RECEIPT_CONTROLLER_REVISION_MISMATCH")
    if receipt.get("codex_material_finding_review_count") != 0:
        raise GateError("FINAL_RECEIPT_CODEX_FINDINGS_NONZERO")
    if receipt.get("authority_transfer") is not False:
        raise GateError("FINAL_RECEIPT_AUTHORITY_TRANSFER_NOT_FALSE")
    if receipt.get("formal_credit_delta") != 0:
        raise GateError("FINAL_RECEIPT_FORMAL_CREDIT_NONZERO")


def validate_pass_receipt_file(path: str, expected_head: str, expected_base: str) -> None:
    try:
        receipt = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise GateError("FINAL_RECEIPT_MISSING") from exc
    except json.JSONDecodeError as exc:
        raise GateError("FINAL_RECEIPT_INVALID_JSON") from exc
    if not isinstance(receipt, dict):
        raise GateError("FINAL_RECEIPT_ROOT_NOT_OBJECT")
    validate_pass_receipt(receipt, expected_head, expected_base)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--pr", type=int)
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"))
    parser.add_argument("--policy")
    parser.add_argument("--out")
    parser.add_argument("--validate-receipt")
    parser.add_argument("--expected-head")
    parser.add_argument("--expected-base")
    args = parser.parse_args()

    if args.validate_receipt:
        try:
            if not args.expected_head or not args.expected_base:
                raise GateError("FINAL_RECEIPT_EXPECTED_IDENTITY_MISSING")
            validate_pass_receipt_file(
                args.validate_receipt, args.expected_head, args.expected_base
            )
            print("FPC_FINAL_RECEIPT_VALIDATION=PASS")
            return 0
        except GateError as exc:
            print(f"FPC_FINAL_RECEIPT_VALIDATION=FAIL:{exc}")
            return 2

    receipt: dict[str, Any]
    code: int
    try:
        if not args.repo or not args.pr or not args.token or not args.policy:
            raise GateError("ADMISSION_ARGUMENTS_MISSING: repo, pr, token and policy are required")
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
            Path(args.out).write_text(payload, encoding="utf-8")
        except OSError:
            code = 2
    print(payload, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
