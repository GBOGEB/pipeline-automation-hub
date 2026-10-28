#!/usr/bin/env python3
"""Read-only unittest population observation for independent CI cohorts."""
from __future__ import annotations

import re

SHA40 = re.compile(r"^[0-9a-f]{40}$")
RAN = re.compile(r"^Ran ([0-9]+) tests? in [0-9.]+s$", re.M)
FINISH = re.compile(r"^(OK|FAILED)(?: \\(([^)]*)\\))?\\s*$", re.M)
SKIP = re.compile(r"skipped=([0-9]+)")


def observe(log: str | None, source_sha: str, run_id: int) -> dict:
    if not SHA40.fullmatch(source_sha) or run_id <= 0:
        raise ValueError("INVALID_EVIDENCE_IDENTITY")
    result = {"source_sha": source_sha, "run_id": run_id,
              "selected": None, "collected": None, "ran": None, "executed": None,
              "skipped": None, "state": "NOT_EXECUTED", "authority": "ADVISORY_ONLY"}
    if log is None:
        return result
    counts = list(RAN.finditer(log))
    if not counts:
        return dict(result, state="UNKNOWN_NO_SUMMARY")
    total = int(counts[-1].group(1))
    endings = [x for x in FINISH.finditer(log) if x.start() > counts[-1].end()]
    if not endings:
        return dict(result, ran=total, state="UNKNOWN_NO_OUTCOME")
    final = endings[-1]
    skip = SKIP.search(final.group(2) or "")
    skipped = int(skip.group(1)) if skip else 0
    if skipped > total:
        return dict(result, ran=total, skipped=skipped, state="INVALID_SKIP_COUNT")
    return dict(result, ran=total, skipped=skipped, executed=total - skipped,
                state="LOG_PASS" if final.group(1) == "OK" else "LOG_FAIL")


def reconcile(named: dict[str, dict]) -> dict:
    if not named:
        raise ValueError("EMPTY_COHORTS")
    records = list(named.values())
    matched = len({(r["source_sha"], r["run_id"]) for r in records}) == 1
    all_good = all(r["state"] == "LOG_PASS" and r["skipped"] == 0 for r in records)
    return {"schema": "jade.devops.ci_population_observation.v1", "cohorts": named,
            "same_run_claim": matched, "all_logs_good": all_good,
            "observed_executed_total": sum(r["executed"] for r in records) if matched and all_good else None,
            "authority": "ADVISORY_ONLY", "merge_authorized": False}
