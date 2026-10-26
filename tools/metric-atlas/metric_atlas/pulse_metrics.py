"""QPS TRIAGE N4: source-bound bounded-route pulse metrics.

Read-only projections over independently audited postflight receipts. A planned
request, fixture or nonterminal receiver SUCCESS cannot earn native/ZIP credit.
Missing capacity, branch coverage, security classification and elapsed time
remain None, never synthetic zero.
"""
from __future__ import annotations

import hashlib
import json
from statistics import median

SCHEMA = "qps-metric-postflight/v1"
ROUTES = frozenset(("native_checks", "coverage_catalog"))
PRODUCERS = frozenset(("GBOGEB/ABACUS", "GBOGEB/CODEX", "GBOGEB/cryoplant-project"))
TERMINAL = frozenset(("VERIFIED_LOCAL_ZIP_AND_NATIVE_JOB", "HOLD_ARTIFACT_BYTES_UNKNOWN",
                      "HOLD_ARTIFACT_BYTES_INVALID"))
BYTE_PROVED = "VERIFIED_LOCAL_ZIP_AND_NATIVE_JOB"


class PulseMetricError(ValueError):
    pass


def _fraction(numerator, denominator):
    return numerator / denominator if denominator else None


def _scope(rows):
    return tuple(sorted((x["repo"], x["route"]) for x in rows))


def summarize(postflight, *, pulse_index):
    if postflight.get("schema") != SCHEMA or type(pulse_index) is not int:
        raise PulseMetricError("invalid postflight schema or pulse index")
    rows = postflight.get("rows")
    if not isinstance(rows, list) or len(rows) > 6:
        raise PulseMetricError("invalid or unbounded route observations")
    pairs = _scope(rows)
    if len(set(pairs)) != len(pairs):
        raise PulseMetricError("duplicate source route")
    if any(repo not in PRODUCERS or route not in ROUTES for repo, route in pairs):
        raise PulseMetricError("unknown repository or DAG route")
    if (postflight.get("eligible_repos") != 3 or
            postflight.get("eligible_routes") != 6 or
            postflight.get("planned_routes") != len(rows) or
            postflight.get("planned_repos") != len(set(repo for repo, _ in pairs))):
        raise PulseMetricError("claimed denominators differ from observed population")
    native = 0
    bytes_valid = 0
    state_counts = {}
    for row in rows:
        status = row.get("status")
        if not isinstance(status, str):
            raise PulseMetricError("missing route disposition")
        state_counts[status] = state_counts.get(status, 0) + 1
        has_job = type(row.get("terminal_job_id")) is int and row["terminal_job_id"] > 0
        if (status in TERMINAL) != has_job:
            raise PulseMetricError("terminal job identity and disposition conflict")
        if status == BYTE_PROVED:
            a = row.get("artifact")
            if (not isinstance(a, dict) or a.get("byte_integrity") != "PASS" or
                    not isinstance(a.get("zip_bytes"), int) or a["zip_bytes"] <= 0 or
                    not isinstance(a.get("member_bytes"), int) or a["member_bytes"] <= 0 or
                    not isinstance(a.get("zip_sha256"), str) or len(a["zip_sha256"]) != 64 or
                    a.get("canonical_530_accepted") is not False):
                raise PulseMetricError("artifact proof incomplete or authority conflated")
            bytes_valid += 1
        native += has_job
    if (postflight.get("terminal_native_jobs_confirmed") != native or
            postflight.get("byte_verified_routes") != bytes_valid):
        raise PulseMetricError("claimed native/ZIP counts disagree with route evidence")
    eligible = len(rows)
    fingerprint = hashlib.sha256(json.dumps(pairs, separators=(",", ":")).encode()).hexdigest()
    return {
        "schema": "qps-metric-pulse/v1", "wave": postflight.get("wave"),
        "pulse_index": pulse_index, "scope_fingerprint": fingerprint,
        "source_routes": [dict(repo=a, route=b) for a, b in pairs],
        "eligible_repos": 3, "eligible_routes": 6,
        "planned_repos": postflight["planned_repos"], "planned_routes": eligible,
        "terminal_native_jobs": native, "verified_zip_routes": bytes_valid,
        "terminal_fraction": _fraction(native, eligible),
        "zip_fraction": _fraction(bytes_valid, eligible),
        "zip_given_terminal": _fraction(bytes_valid, native),
        "unverified_routes": eligible - bytes_valid,
        "status_counts": dict(sorted(state_counts.items())),
        "source_bound_test_count": None, "statement_coverage": None,
        "branch_coverage": None, "worker_hours": None, "latency_p95_seconds": None,
        "root_closures": None, "six_sigma_capability": None,
        "pca_readiness": None, "bt_readiness": None,
        "merge_admission": "HOLD", "qps_engineering_acceptance": False,
    }


def compare_pulses(history):
    if not history:
        return {"observations": 0, "status": "UNKNOWN", "delta_zip": None,
                "velocity_routes_per_pulse": None, "acceleration": None,
                "rolling_n20": None, "stability_mad": None, "winner": None}
    ordered = sorted(history, key=lambda x: x["pulse_index"])
    if len({x["pulse_index"] for x in ordered}) != len(ordered):
        raise PulseMetricError("duplicate temporal pulse index")
    if len({x["scope_fingerprint"] for x in ordered}) != 1:
        return {"observations": len(ordered), "status": "UNMATCHED_COHORT",
                "delta_zip": None, "velocity_routes_per_pulse": None,
                "acceleration": None, "rolling_n20": None,
                "stability_mad": None, "winner": None}
    valid = all(x.get("planned_routes") and x.get("verified_zip_routes") is not None
                for x in ordered)
    if not valid:
        raise PulseMetricError("incomplete pulse numerator or denominator")
    speeds = [(b["verified_zip_routes"] - a["verified_zip_routes"]) /
              (b["pulse_index"] - a["pulse_index"])
              for a, b in zip(ordered, ordered[1:])]
    delta = ordered[-1]["verified_zip_routes"] - ordered[0]["verified_zip_routes"]
    p = [x["zip_fraction"] for x in ordered]
    mad = median(abs(x - median(p[-5:])) for x in p[-5:]) if len(p) >= 5 else None
    return {"observations": len(ordered), "status": "COMPARABLE",
            "delta_zip": delta if len(ordered) >= 2 else None,
            "velocity_routes_per_pulse": speeds[-1] if speeds else None,
            "acceleration": speeds[-1] - speeds[-2] if len(speeds) >= 2 else None,
            "rolling_n20": sum(p[-20:]) / 20 if len(p) >= 20 else None,
            "stability_mad": mad,
            "six_sigma_capability": None, "winner": None}
