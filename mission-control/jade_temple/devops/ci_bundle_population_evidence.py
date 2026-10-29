#!/usr/bin/env python3
"""Read-only unittest population observation for independent CI cohorts.

These are unauthenticated log observations, never gate or release credit.
"""
from __future__ import annotations

import re

SHA40 = re.compile(r"^[0-9a-f]{40}$")
RAN = re.compile(r"^Ran ([0-9]+) tests? in [0-9.]+s\r?$", re.M)
FOOTER = re.compile(
    r"^[ \t]*\r?\n(?:[ \t]*\r?\n)?[ \t]*(OK|FAILED)"
    r"(?: \(([^)\r\n]*)\))?[ \t]*(?:\r?\n|$)"
)
SKIP = re.compile(r"skipped=([0-9]+)")


def observe(log: str | None, source_sha: str, run_id: int, run_attempt: int = 1) -> dict:
    """Count one unittest step, not a concatenation of multiple test cohorts."""
    if (not isinstance(source_sha, str) or not SHA40.fullmatch(source_sha)
            or type(run_id) is not int or run_id <= 0
            or type(run_attempt) is not int or run_attempt <= 0):
        raise ValueError("INVALID_EVIDENCE_IDENTITY")
    result = {"source_sha": source_sha, "run_id": run_id, "run_attempt": run_attempt,
              "selected": None, "collected": None, "ran": None, "executed": None,
              "skipped": None, "state": "NOT_EXECUTED", "authority": "ADVISORY_ONLY"}
    if log is None:
        return result
    counts = list(RAN.finditer(log))
    if not counts:
        return dict(result, state="UNKNOWN_NO_SUMMARY")
    if len(counts) != 1:
        return dict(result, state="AMBIGUOUS_MULTIPLE_SUMMARIES")
    total = int(counts[0].group(1))
    footer = FOOTER.match(log[counts[0].end():])
    if not footer:
        return dict(result, ran=total, state="UNKNOWN_NO_OUTCOME")
    skip = SKIP.search(footer.group(2) or "")
    skipped = int(skip.group(1)) if skip else 0
    if skipped > total:
        return dict(result, ran=total, skipped=skipped, state="INVALID_SKIP_COUNT")
    return dict(result, ran=total, skipped=skipped, executed=total - skipped,
                state="LOG_PASS" if footer.group(1) == "OK" else "LOG_FAIL")


def reconcile(named: dict[str, dict], required=("devops", "actions_metrics")) -> dict:
    """Accept only the named and source/run/attempt-matched expected cohorts.

    The caller asserts identity and owns any authentication; this read-only
    adapter never infers an authenticated test population from raw log text.
    """
    if not isinstance(named, dict) or not named:
        raise ValueError("EMPTY_COHORTS")
    required = tuple(required)
    if not required or len(set(required)) != len(required) or any(not isinstance(k, str) or not k for k in required):
        raise ValueError("INVALID_REQUIRED_COHORTS")
    records = list(named.values())
    valid = all(
        isinstance(r, dict)
        and isinstance(r.get("source_sha"), str)
        and SHA40.fullmatch(r["source_sha"])
        and type(r.get("run_id")) is int and r["run_id"] > 0
        and type(r.get("run_attempt", 1)) is int and r.get("run_attempt", 1) > 0
        for r in records
    )
    matched = bool(valid and len({(r["source_sha"], r["run_id"], r.get("run_attempt", 1)) for r in records}) == 1)
    complete = set(required).issubset(named)
    scope_exact = set(named) == set(required)
    all_good = bool(valid and all(
        r.get("state") == "LOG_PASS" and r.get("skipped") == 0
        and type(r.get("ran")) is int
        and type(r.get("executed")) is int
        and 0 <= r["executed"] <= r["ran"]
        for r in records
    ))
    total = sum(named[k]["executed"] for k in required) if matched and complete and scope_exact and all_good else None
    return {"schema": "jade.devops.ci_population_observation.v1", "cohorts": named,
            "same_run_claim": matched, "all_logs_good": all_good,
            "complete_groups": complete, "scope_exact": scope_exact,
            "unexpected_groups": sorted(set(named) - set(required)),
            "observed_executed_total": total,
            "authority": "ADVISORY_ONLY", "merge_authorized": False}
