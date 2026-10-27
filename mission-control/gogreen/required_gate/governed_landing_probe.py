#!/usr/bin/env python3
"""Read-only, fail-closed cross-check of *effective* GitHub PR admission evidence.

This supplements (never replaces) required_gate/gate.py and First-Pass Closure.
It neither promotes engineering acceptance nor merges/dispatches/modifies rules.
For safety it NEVER emits merge_allowed=True, even with complete observations.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

SCHEMA = "codepurple.governed_landing.readback.v1"
REPO = "GBOGEB/pipeline-automation-hub"
RULESET_ID = 25789280
HEX40 = re.compile(r"[a-f0-9]{40}\Z")
REQUIRED_NAMES = ("validate-ultra-control", "canonical-self-test-and-mutation",
                  "GOGREEN required gate")


def hold(condition, name):
    return {"gate": name, "state": "PASS" if condition else "HOLD"}


def _rules(ruleset):
    return {r.get("type"): r for r in ruleset.get("rules", [])
            if isinstance(r, dict) and isinstance(r.get("type"), str)}


def _head(pr):
    head = (pr.get("head") or {}).get("sha")
    base = (pr.get("base") or {}).get("sha")
    return head, base


def classify(pr, ruleset, reviews, check_runs, checks_complete=False,
             threads_complete=False, blocked_red_receipt=None, read_error=None,
             second_head=None):
    """HOLD-first projection from sampled native GitHub objects.

    ruleset/review/check data may be partial; absent is never a satisfied gate.
    This classifier is *not* an attestation that the caller authenticated GitHub.
    """
    if not isinstance(pr, dict):
        raise ValueError("ADMISSION_HOLD: PR must be a mapping")
    head, base = _head(pr)
    stable = (isinstance(head, str) and bool(HEX40.fullmatch(head))
              and isinstance(base, str) and bool(HEX40.fullmatch(base))
              and second_head == head)
    author = ((pr.get("user") or {}).get("login"))
    candidate_open = (pr.get("state") == "open" and pr.get("draft") is False
                      and pr.get("merged_at") is None)
    r = ruleset if isinstance(ruleset, dict) else {}
    types = _rules(r)
    p = (types.get("pull_request") or {}).get("parameters") or {}
    s = (types.get("required_status_checks") or {}).get("parameters") or {}
    includes = ((r.get("conditions") or {}).get("ref_name") or {}).get("include") or []
    excludes = ((r.get("conditions") or {}).get("ref_name") or {}).get("exclude") or []
    protected_ref = "~DEFAULT_BRANCH" in includes or "refs/heads/master" in includes
    protected_ref = protected_ref and "refs/heads/master" not in excludes
    active = (r.get("id") == RULESET_ID and r.get("enforcement") == "active"
              and r.get("target") == "branch" and protected_ref
              and isinstance(r.get("bypass_actors"), list)
              and len(r["bypass_actors"]) == 0)
    review_count = p.get("required_approving_review_count")
    enforced_human = type(review_count) is int and review_count >= 1
    required_status = s.get("required_status_checks") or []
    required_contexts = {
        c.get("context") for c in required_status
        if isinstance(c, dict) and isinstance(c.get("context"), str)
    }
    status_policy = all(x in required_contexts for x in REQUIRED_NAMES)
    status_policy = status_policy and bool(s.get("strict_required_status_checks_policy"))
    # GitHub checks returned on exact head; samples/pagination MUST be complete.
    completed = {}
    if isinstance(check_runs, list):
        for run in check_runs:
            if not isinstance(run, dict) or run.get("head_sha") != head:
                continue
            name = run.get("name")
            if name not in REQUIRED_NAMES:
                continue
            # Many attempts may exist. Never let an older success conceal red.
            t = (run.get("completed_at") or "", run.get("id") or 0)
            if name not in completed or t > completed[name][0]:
                completed[name] = (t, run.get("status") == "completed"
                                    and run.get("conclusion") == "success")
    checks_ok = bool(checks_complete) and all(
        name in completed and completed[name][1] for name in REQUIRED_NAMES)
    # Last eligible human review per reviewer wins. Bot COMMENTED is not approval.
    latest = {}
    if isinstance(reviews, list):
        for review in reviews:
            if not isinstance(review, dict):
                continue
            user = review.get("user") or {}
            login = user.get("login")
            if (not isinstance(login, str) or login == author
                    or user.get("type") != "User"):
                continue
            ident = (review.get("submitted_at") or "", review.get("id") or 0)
            if login not in latest or ident > latest[login][0]:
                latest[login] = (ident, review)
    approvers = sum(
        v[1].get("state") == "APPROVED" and v[1].get("commit_id") == head
        for v in latest.values()
    )
    req = [
        hold(stable, "same_exact_pr_head_twice"),
        hold(candidate_open, "candidate_open_non_draft"),
        hold(active, "effective_ruleset_applies_no_bypass"),
        hold(enforced_human, "at_least_one_required_human_approval"),
        hold(bool(p.get("require_last_push_approval")), "last_push_approval_enforced"),
        hold(bool(p.get("dismiss_stale_reviews_on_push")), "dismiss_stale_reviews"),
        hold(bool(p.get("required_review_thread_resolution")) and threads_complete,
             "all_review_threads_verified_resolved"),
        hold(bool(s.get("strict_required_status_checks_policy")), "up_to_date_before_merge"),
        hold("non_fast_forward" in types and "deletion" in types,
             "non_fast_forward_and_deletion_denied"),
        hold(status_policy, "mandatory_exact_head_check_contexts"),
        hold(checks_ok, "latest_exact_head_native_required_checks"),
        hold(approvers >= 1, "eligible_independent_exact_head_human_review"),
        hold(blocked_red_receipt is not None
             and blocked_red_receipt.get("proof_class") == "GITHUB_REJECTED_RED_MERGE"
             and blocked_red_receipt.get("head_sha") == head
             and blocked_red_receipt.get("rule_id") == RULESET_ID
             and bool(blocked_red_receipt.get("external_rejection_receipt_digest")),
             "blocked_red_canary_platform_rejection"),
        hold(read_error is None, "authenticated_complete_readback"),
    ]
    return {
        "schema": SCHEMA, "repository": REPO,
        "pr_number": pr.get("number"),
        "head_sha": head if isinstance(head, str) and HEX40.fullmatch(head) else None,
        "base_sha": base if isinstance(base, str) and HEX40.fullmatch(base) else None,
        "ruleset_id": RULESET_ID, "gates": req,
        "pass_count": sum(x["state"] == "PASS" for x in req),
        "hold_count": sum(x["state"] == "HOLD" for x in req),
        "observed_eligible_human_approvals": approvers,
        "checks_sample_complete": bool(checks_complete),
        "review_threads_sample_complete": bool(threads_complete),
        "red_canary_source": "NONE" if blocked_red_receipt is None else "CALLER_SUPPLIED_UNVERIFIED",
        "read_error": read_error,
        "readiness": "CANDIDATE_REQUIRES_HUMAN_ADMISSION"
                     if all(x["state"] == "PASS" for x in req) else "HOLD",
        "merge_allowed": False, "authority_transfer": False,
        "formal_engineering_credit_delta": 0,
        "qps_owner_acceptance": "NOT_ESTABLISHED",
    }


class Reader:
    """Allowlisted GET only; never serialize bearer token in receipts."""
    def __init__(self, token=None):
        self.token = token if token is not None else os.getenv("GITHUB_TOKEN", "")
        if not self.token:
            raise ValueError("ADMISSION_HOLD:GITHUB_TOKEN unavailable")

    def get(self, suffix):
        if not suffix.startswith("/repos/" + REPO + "/"):
            raise ValueError("ADMISSION_HOLD:non-allowlisted endpoint")
        if ".." in suffix or "\\" in suffix:
            raise ValueError("ADMISSION_HOLD:unsafe endpoint")
        request = urllib.request.Request(
            "https://api.github.com" + suffix, method="GET",
            headers={"Authorization": "Bearer " + self.token,
                     "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28",
                     "User-Agent": "codepurple-governed-landing-readonly/1"})
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.load(response)

    def list(self, path, member=None, maximum=500):
        rows = []
        for page in range(1, 7):
            separator = "&" if "?" in path else "?"
            result = self.get(path + separator + "per_page=100&page=" + str(page))
            batch = result.get(member) if member else result
            if not isinstance(batch, list):
                raise ValueError("ADMISSION_HOLD:page not list")
            rows += batch
            if len(rows) > maximum:
                raise ValueError("ADMISSION_HOLD:exceeded readback bound")
            total = result.get("total_count") if member else None
            if len(batch) < 100 or isinstance(total, int) and len(rows) >= total:
                return rows, total is None or len(rows) == total
        return rows, False


def collect(reader, number, rule_id=RULESET_ID):
    """Small bounded metadata census, not a review-thread/canary authority.

    GraphQL thread resolution and *actual blocked RED* receipts require a
    distinct authenticated controller; until then they stay UNKNOWN/HOLD.
    """
    if type(number) is not int or not 1 <= number <= 1_000_000:
        raise ValueError("ADMISSION_HOLD:invalid PR number")
    prefix = "/repos/" + REPO
    pr = reader.get(f"{prefix}/pulls/{number}")
    reviews, reviews_complete = reader.list(f"{prefix}/pulls/{number}/reviews")
    head, _ = _head(pr)
    if not isinstance(head, str) or not HEX40.fullmatch(head):
        raise ValueError("ADMISSION_HOLD:invalid PR head")
    checks, checks_complete = reader.list(f"{prefix}/commits/{head}/check-runs",
                                          member="check_runs")
    ruleset = reader.get(f"{prefix}/rulesets/{int(rule_id)}")
    pr_again = reader.get(f"{prefix}/pulls/{number}")
    result = classify(pr, ruleset, reviews if reviews_complete else [], checks,
                      checks_complete=checks_complete, threads_complete=False,
                      blocked_red_receipt=None, second_head=_head(pr_again)[0])
    result["source_quality"] = "AUTHENTICATED_GITHUB_GET_PARTIAL_THREAD_AND_CANARY"
    result["review_api_complete"] = reviews_complete
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only governed landing audit; never merge")
    parser.add_argument("--pr", required=True, type=int)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = collect(Reader(), args.pr)
    except (ValueError, urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        # Diagnostic failure is HOLD, never PASS/zero; no credentials exposed.
        result = {"schema": SCHEMA, "repository": REPO, "pr_number": args.pr,
                  "readiness": "HOLD", "merge_allowed": False,
                  "source_quality": "UNKNOWN_ACCESS_OR_RUNTIME",
                  "reason_class": type(exc).__name__,
                  "authority_transfer": False, "formal_engineering_credit_delta": 0}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"schema": SCHEMA, "pr": args.pr, "readiness": "HOLD",
                      "merge_allowed": False, "evidence_path": str(args.out)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
