#!/usr/bin/env python3
"""Read-only owner rule-suite join; never grants merge or closure authority.

This adds a bypass-provenance join downstream of taxonomy_admission_audit.py.
It does NOT reinterpret FPC statuses, approve a bypass, mutate GitHub or
promote a green result. Input rule-suite data must be owner-exported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

REPO = "GBOGEB/pipeline-automation-hub"
REF = "refs/heads/master"
SOFT_RULESET = 26995106
FPC_CONTEXT = "First-Pass Closure Gate / first-pass-closure"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
ROOT = "GBOGEB/pipeline-automation-hub#336"
EVENT_SCHEMA = "fpc.merge-cohort.v1"
SOURCE_SCHEMA = "fpc.rule-suite-export.v1"
RESULT_SCHEMA = "fpc.rule-suite-join.v1"


def instant(value):
    if not isinstance(value, str):
        raise ValueError("UTC_TIMESTAMP_REQUIRED")
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("BAD_TIMESTAMP") from exc
    if d.tzinfo is None:
        raise ValueError("TIMEZONE_REQUIRED")
    return d.astimezone(timezone.utc)


def sha(value, field):
    if not isinstance(value, str) or not SHA40.fullmatch(value):
        raise ValueError(field + "_NOT_EXACT_SHA")
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def validate_cohort(data):
    if not isinstance(data, dict) or data.get("schema") != EVENT_SCHEMA:
        raise ValueError("EVENT_SCHEMA")
    if data.get("repository") != REPO or data.get("ref") != REF:
        raise ValueError("EVENT_SCOPE")
    events = data.get("events")
    if not isinstance(events, list) or not events:
        raise ValueError("NO_EVENTS")
    seen = set()
    for e in events:
        if not isinstance(e, dict) or type(e.get("pr")) is not int or e["pr"] < 1:
            raise ValueError("INVALID_PR")
        sha(e.get("head_sha"), "HEAD")
        sha(e.get("merge_commit_sha"), "MERGE")
        instant(e.get("merged_at"))
        key = (e["pr"], e["head_sha"], e["merged_at"])
        if key in seen:
            raise ValueError("DUPLICATE_MERGE_EVENT")
        seen.add(key)
        fpc = e.get("fpc")
        if not isinstance(fpc, dict) or fpc.get("state") not in ("FAILURE", "SUCCESS", "ABSENT"):
            raise ValueError("FPC_OBSERVATION_INVALID")
        if fpc["state"] == "ABSENT":
            if fpc.get("status_id") is not None or fpc.get("run_url") is not None:
                raise ValueError("ABSENT_WITH_RECEIPT")
        elif (type(fpc.get("status_id")) is not int or fpc["status_id"] < 1 or
              not isinstance(fpc.get("run_url"), str) or
              not fpc["run_url"].startswith("https://github.com/" + REPO + "/actions/runs/")):
            raise ValueError("FPC_STATUS_RECEIPT_INCOMPLETE")
        if e.get("cohort") not in ("historical_27", "later_positive_control"):
            raise ValueError("COHORT_UNKNOWN")
    return sorted(events, key=lambda e: (instant(e["merged_at"]), e["pr"]))


def source_state(source, events):
    if not isinstance(source, dict) or source.get("schema") != SOURCE_SCHEMA:
        raise ValueError("SOURCE_SCHEMA")
    if source.get("repository") != REPO or source.get("ref") != REF:
        raise ValueError("SOURCE_SCOPE")
    state = source.get("state")
    if state == "FORBIDDEN":
        if source.get("http_status") != 403 or source.get("suites") not in (None, []):
            raise ValueError("FORBIDDEN_SOURCE_CONTRADICTION")
        return "FORBIDDEN", []
    if state not in ("COMPLETE", "INCOMPLETE"):
        raise ValueError("SOURCE_STATE_UNKNOWN")
    suites = source.get("suites")
    if not isinstance(suites, list):
        raise ValueError("SOURCE_SUITES_ABSENT")
    ids = []
    for s in suites:
        if not isinstance(s, dict) or type(s.get("id")) is not int:
            raise ValueError("INVALID_SUITE_ID")
        ids.append(s["id"])
    if len(set(ids)) != len(ids):
        raise ValueError("DUPLICATE_RULE_SUITE_ID")
    if (state != "COMPLETE" or source.get("pagination_complete") is not True or
        source.get("details_complete") is not True or source.get("metadata_truncated") is True):
        return "INCOMPLETE", suites
    lo, hi = instant(source.get("window_start")), instant(source.get("window_end"))
    if lo > min(instant(e["merged_at"]) for e in events) or hi < max(instant(e["merged_at"]) for e in events):
        return "INCOMPLETE", suites
    if source.get("filter") not in ("all", "bypass"):
        return "INCOMPLETE", suites
    return "COMPLETE", suites


def scoped_suite(suite, event):
    if suite.get("after_sha") != event["merge_commit_sha"] or suite.get("ref") != REF:
        return False
    try:
        pushed = instant(suite.get("pushed_at"))
    except ValueError:
        return False
    return abs((pushed - instant(event["merged_at"])).total_seconds()) <= 900


def classify_match(suite):
    result = suite.get("result")
    if result != "bypass":
        return "RULE_SUITE_" + result.upper() + "_OBSERVED_NO_ADMISSION_PROOF" if result in ("pass", "fail") else "RULE_SUITE_OUTCOME_UNKNOWN"
    evaluations = suite.get("rule_evaluations")
    if not isinstance(evaluations, list):
        return "BYPASS_OBSERVED_RULE_EVALUATIONS_MISSING"
    for rule in evaluations:
        if not isinstance(rule, dict):
            continue
        source = rule.get("rule_source") or {}
        details = rule.get("details")
        if (isinstance(source, dict) and source.get("type") == "ruleset" and
            source.get("id") == SOFT_RULESET and rule.get("enforcement") == "active" and
            rule.get("rule_type") == "required_status_checks" and rule.get("result") == "fail" and
            isinstance(details, str) and FPC_CONTEXT.casefold() in details.casefold()):
            return "FPC_BYPASS_OBSERVED_OWNER_DECISION_REQUIRED"
    return "BYPASS_OBSERVED_FPC_SCOPE_UNPROVEN"


def replay(cohort, source):
    events = validate_cohort(cohort)
    state, suites = source_state(source, events)
    rows = []
    for e in events:
        matching = sorted((s for s in suites if scoped_suite(s, e)), key=lambda s: s["id"]) if state == "COMPLETE" else []
        if state == "FORBIDDEN":
            verdict = "ADMIN_READ_403_UNRESOLVED"
        elif state == "INCOMPLETE":
            verdict = "SOURCE_INCOMPLETE_UNRESOLVED"
        elif not matching:
            verdict = "NO_MATCHING_RULE_SUITE_OBSERVED_UNRESOLVED"
        elif len(matching) > 1:
            verdict = "MULTIPLE_MATCHING_RULE_SUITES_UNRESOLVED"
        else:
            verdict = classify_match(matching[0])
        rows.append({"pr": e["pr"], "head_sha": e["head_sha"],
                     "merge_commit_sha": e["merge_commit_sha"], "merged_at": e["merged_at"],
                     "cohort": e["cohort"], "fpc_observed": e["fpc"]["state"],
                     "fpc_status_id": e["fpc"].get("status_id"),
                     "rule_suite_ids": [s["id"] for s in matching], "rule_suite_verdict": verdict,
                     "owner_admission": "HOLD", "authorized_bypass": False,
                     "root_owner": ROOT, "formal_root_closure_credit": 0})
    counts = {key: sum(r["fpc_observed"] == key for r in rows) for key in ("FAILURE", "ABSENT", "SUCCESS")}
    digest = hashlib.sha256(canonical({"events": events, "source": source}).encode()).hexdigest()
    return {"schema": RESULT_SCHEMA, "repository": REPO, "ref": REF,
            "observed_events": len(rows), "historical_events": sum(r["cohort"] == "historical_27" for r in rows),
            "positive_controls": sum(r["cohort"] == "later_positive_control" for r in rows),
            "fpc_observations": counts, "rule_suite_source_state": state,
            "fpc_bypass_observed": sum(r["rule_suite_verdict"] == "FPC_BYPASS_OBSERVED_OWNER_DECISION_REQUIRED" for r in rows),
            "authorized_bypasses": 0, "new_semantic_roots": 0, "formal_root_closures": 0,
            "root_ownership": [ROOT], "merge_admission": "HOLD", "authority_transfer": False,
            "digest_sha256": digest, "events": rows}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--events", required=True, type=Path)
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()
    result = replay(json.loads(args.events.read_text(encoding="utf-8")),
                    json.loads(args.source.read_text(encoding="utf-8")))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "events"}, sort_keys=True))


if __name__ == "__main__":
    main()
