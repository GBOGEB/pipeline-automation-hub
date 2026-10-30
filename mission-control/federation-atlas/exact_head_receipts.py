#!/usr/bin/env python3
"""Validate exact-head federation observations; never infer merge or QPS acceptance.

The input is an explicitly supplied GitHub readback, not a live lookup.
Run locally or in MissionControl after native collectors have emitted receipts.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

SCHEMA = "missioncontrol.federation.exact_head_receipts/v1"
OUTPUT_SCHEMA = "missioncontrol.federation.exact_head_rollup/v1"
REPOS = (
    "GBOGEB/gg_MATH",
    "GBOGEB/CODEX",
    "GBOGEB/ABACUS",
    "GBOGEB/cryoplant-project",
    "GBOGEB/pipeline-automation-hub",
)
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA64 = re.compile(r"[0-9a-f]{64}\Z")
STATUSES = {"SUCCESS", "FAILURE", "CANCELLED", "SKIPPED", "QUEUED", "IN_PROGRESS", "UNKNOWN"}
TERMINAL = {"SUCCESS", "FAILURE", "CANCELLED", "SKIPPED"}


def check(value, reason):
    if not value:
        raise ValueError(reason)


def strict_sha(value, pattern=SHA40):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def iso_utc(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def validate(data):
    check(isinstance(data, dict) and data.get("schema") == SCHEMA, "unknown schema")
    check(data.get("classification") == "OBSERVED_GITHUB_READBACK_NOT_OWNER_ACCEPTANCE",
          "false source classification")
    check(iso_utc(data.get("observed_at")), "missing UTC readback timestamp")
    rows = data.get("observations")
    check(isinstance(rows, list) and len(rows) == len(REPOS), "exactly five core repo rows required")
    seen = set()
    for row in rows:
        check(isinstance(row, dict), "invalid repo observation")
        repo = row.get("repository")
        check(repo in REPOS and repo not in seen, "unknown or repeated repository")
        seen.add(repo)
        head, source = row.get("head_sha"), row.get("source_sha")
        check(strict_sha(head) and source == head, "unmatched exact-head source SHA")
        check(row.get("conclusion") in STATUSES, "unknown run conclusion")
        check(row.get("security") in {"SUCCESS", "FAILURE", "UNKNOWN"}, "invalid security gate")
        check(row.get("independent_review") in {"VERIFIED", "NOT_VERIFIED"},
              "invalid review evidence")
        check(row.get("red_canary_blocked") in {True, False, None},
              "invalid RED canary proof")
        check(row.get("artifact_sha256") is None or strict_sha(row["artifact_sha256"], SHA64),
              "invalid artifact digest")
        status = row["conclusion"]
        run_id, attempt = row.get("run_id"), row.get("run_attempt")
        if status in TERMINAL:
            check(type(run_id) is int and run_id > 0, "terminal run requires native run id")
            check(type(attempt) is int and attempt > 0, "terminal run requires attempt")
        else:
            check(run_id is None or (type(run_id) is int and run_id > 0), "invalid run id")
            check(attempt is None or (type(attempt) is int and attempt > 0),
                  "invalid run attempt")
        # A positive conclusion never manufactures an artifact or independent review.
        check(row.get("owner_accepted") is False, "owner acceptance must stay external")
        check(row.get("override") is False, "no governance override admissible")
    check(seen == set(REPOS), "incomplete federation")
    counts = Counter(row["conclusion"] for row in rows)
    problems = []
    for row in rows:
        reason = []
        if row["conclusion"] != "SUCCESS":
            reason.append("RUN_" + row["conclusion"])
        if row["security"] != "SUCCESS":
            reason.append("SECURITY_" + row["security"])
        if row["independent_review"] != "VERIFIED":
            reason.append("REVIEW_NOT_VERIFIED")
        if row["red_canary_blocked"] is not True:
            reason.append("RED_CANARY_NOT_VERIFIED")
        if row["artifact_sha256"] is None:
            reason.append("ARTIFACT_HASH_MISSING")
        if reason:
            problems.append({"repository": row["repository"], "reasons": reason})
    # Never turn a self-declared snapshot into an approval, even when all green.
    return {
        "schema": OUTPUT_SCHEMA,
        "source_schema": SCHEMA,
        "observed_at": data["observed_at"],
        "repos_count": len(REPOS),
        "counts": {key: counts.get(key, 0) for key in sorted(STATUSES)},
        "terminal": sum(counts[key] for key in TERMINAL),
        "pending": sum(counts[key] for key in STATUSES - TERMINAL),
        "red": counts["FAILURE"] + counts["CANCELLED"],
        "blocked_repositories": problems,
        "source_match": True,
        "merge_admission": "HOLD" if problems else "CANDIDATE_FOR_INDEPENDENT_QUALIFICATION",
        "qps_engineering_acceptance": "UNKNOWN",
        "automatic_merge_authorized": False,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--output", type=Path)
    opts = ap.parse_args(argv)
    data = json.loads(opts.input.read_text(encoding="utf-8"))
    result = validate(data)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if opts.output is not None:
        opts.output.parent.mkdir(parents=True, exist_ok=True)
        opts.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
