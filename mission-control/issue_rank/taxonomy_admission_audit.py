#!/usr/bin/env python3
"""Read-only effective admission evidence audit. No GitHub mutations or waivers.

A RED-before-merge event proves a missing admission barrier only when the
specific context is *not* required. Never claim a configured required check
was bypassed from timing alone. A blocked-RED proof requires explicit
merge-API refusal under an effective rule and eligible principal.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

SCHEMA = "jade.admission-evidence-audit.v1"
HEX = re.compile(r"^[0-9a-f]{40}$", re.I)
REQUIRED_CONTEXT = "First-Pass Closure Gate / first-pass-closure"


def timestamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("MISSING_TIMESTAMP")
    try:
        v = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as e:
        raise ValueError("INVALID_TIMESTAMP") from e
    if v.tzinfo is None:
        raise ValueError("TIMESTAMP_MUST_HAVE_TIMEZONE")
    return v


def audit(snapshot: dict) -> dict:
    if not isinstance(snapshot, dict) or snapshot.get("schema") != "jade.admission-observation.v1":
        raise ValueError("OBSERVATION_SCHEMA_MISMATCH")
    ruleset, pull = snapshot.get("ruleset"), snapshot.get("pull_request")
    if not isinstance(ruleset, dict) or not isinstance(pull, dict):
        raise ValueError("EVIDENCE_ABSENT")
    head = pull.get("head_sha")
    if not isinstance(head, str) or not HEX.fullmatch(head):
        raise ValueError("PR_HEAD_NOT_EXACT")
    merge_time = timestamp(pull["merged_at"]) if pull.get("merged_at") else None
    if pull.get("merged") is True and not merge_time:
        raise ValueError("MERGED_TIME_ABSENT")
    if pull.get("merged") is False and merge_time:
        raise ValueError("UNMERGED_WITH_MERGE_TIMESTAMP")
    if ruleset.get("enforcement") != "active" or ruleset.get("target") != "branch":
        raise ValueError("EFFECTIVE_RULESET_NOT_ATTESTED")
    if not isinstance(ruleset.get("rules"), list):
        raise ValueError("RULES_NOT_RETURNED")
    policy = {x.get("type"): x.get("parameters") or {} for x in ruleset["rules"]
              if isinstance(x, dict)}
    checks = policy.get("required_status_checks", {}).get("required_status_checks")
    if checks is None:
        checks = []
    if not isinstance(checks, list):
        raise ValueError("REQUIRED_CHECKS_UNKNOWN")
    names = [c.get("context") for c in checks if isinstance(c, dict)]
    if len(names) != len(checks) or any(not isinstance(x, str) for x in names):
        raise ValueError("MALFORMED_CHECK_IDENTITY")
    pr = policy.get("pull_request") or {}
    expected = {
        "required_fpc_context": REQUIRED_CONTEXT in names,
        "strict_up_to_date": policy.get("required_status_checks", {}).get(
            "strict_required_status_checks_policy") is True,
        "independent_approval_required": int(pr.get("required_approving_review_count", 0)) >= 1,
        "dismiss_stale": pr.get("dismiss_stale_reviews_on_push") is True,
        "last_push_approval": pr.get("require_last_push_approval") is True,
        "resolved_threads": pr.get("required_review_thread_resolution") is True,
        "no_bypass_actors": isinstance(ruleset.get("bypass_actors"), list)
                           and len(ruleset["bypass_actors"]) == 0,
        "main_targeted": any(x in ("~DEFAULT_BRANCH", "refs/heads/master") for x
                             in ((ruleset.get("conditions") or {}).get("ref_name") or {}).get("include", [])),
    }
    runs = snapshot.get("workflow_runs")
    if not isinstance(runs, list):
        raise ValueError("RUNS_NOT_RETURNED")
    seen = set()
    reds = []
    for run in runs:
        if not isinstance(run, dict):
            raise ValueError("RUN_NOT_OBJECT")
        ident = run.get("id")
        if type(ident) is not int or ident <= 0 or ident in seen:
            raise ValueError("RUN_ID_DUPLICATE_OR_INVALID")
        seen.add(ident)
        if run.get("name") != REQUIRED_CONTEXT:
            continue
        if run.get("head_sha") != head:
            # Stale runs are not proof on the current PR head.
            continue
        if run.get("status") != "completed" or run.get("conclusion") != "failure":
            continue
        ended = timestamp(run.get("updated_at"))
        if merge_time and ended < merge_time:
            reds.append({"run_id": ident, "head_sha": head,
                         "observation": "RED_COMPLETED_BEFORE_MERGE",
                         "context_was_required": expected["required_fpc_context"]})
    reviews = snapshot.get("reviews")
    if not isinstance(reviews, list):
        raise ValueError("REVIEW_LIST_NOT_RETURNED")
    approval = any(
        isinstance(x, dict) and x.get("state") == "APPROVED"
        and x.get("commit_id") == head and isinstance(x.get("user"), str)
        and x["user"].casefold() != str(pull.get("author", "")).casefold()
        for x in reviews
    )
    gaps = sorted(k for k, ok in expected.items() if not ok)
    if pull.get("merged") and reds and not expected["required_fpc_context"]:
        observation = "MERGED_AFTER_UNREQUIRED_FPC_RED"
    elif pull.get("merged") and reds:
        observation = "POSSIBLE_ENFORCEMENT_FAILURE_REQUIRES_MERGE_API_AND_BYPASS_AUDIT"
    elif pull.get("merged"):
        observation = "MERGED_NO_QUALIFYING_RED_RECEIPT"
    else:
        observation = "NO_MERGE_OBSERVED"
    canary = snapshot.get("canary")
    blocked = (isinstance(canary, dict)
               and canary.get("head_sha") == head
               and canary.get("merge_api_rejected") is True
               and canary.get("required_check_failed") is True
               and expected["required_fpc_context"]
               and not gaps)
    return {
        "schema": SCHEMA, "repository": pull.get("repository"),
        "pr_number": pull.get("number"), "head_sha": head,
        "merged": pull.get("merged"), "merge_observation": observation,
        "red_before_merge": reds, "missing_controls": gaps,
        "eligible_approval_on_last_head_observed": approval,
        "blocked_red_canary_claim_consistent": bool(blocked),
        "blocked_red_canary_verified": False,
        "blocked_red_canary_evidence": "EXTERNAL_API_REFUSAL_AUTHENTICATION_REQUIRED",
        "governed_admission": "HOLD",
        "engineering_credit": 0, "formal_credit_delta": 0,
        "authority_transfer": False,
        "audit_limit": "REPO_RULESET_SNAPSHOT_NOT_FULL_ORG_EFFECTIVE_POLICY_PROOF",
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshot", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    result = audit(json.loads(args.snapshot.read_text(encoding="utf-8")))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(result["merge_observation"], "HOLD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
