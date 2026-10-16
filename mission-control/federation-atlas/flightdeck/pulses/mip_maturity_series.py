"""Read-only MIP evidence series: descriptive, matched and forecast layers.

Consumes disposable Mission Control projections from the ABACUS #2033 producer.
Does not acquire native artifacts or certify independence, review, closure or QPS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

SCHEMA = "code-purple.mip.maturity-series-input.v1"
PROJECTION = "code-purple.mission-control.mip-consumer.v1"
OUT = "code-purple.mip.maturity-series.v1"
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
COHORT_KEYS = ("workflow_set_sha256", "test_selection_sha256",
               "runner_matrix_sha256")
MIN_QUEUE = 20


def require(predicate, reason):
    if not predicate:
        raise ValueError(reason)


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def utc(value):
    require(isinstance(value, str) and value.endswith("Z"),
            "UTC observation timestamp required")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid UTC observation timestamp") from exc
    require(stamp.utcoffset().total_seconds() == 0,
            "UTC timestamp required")
    return stamp


def cohort(value):
    require(isinstance(value, dict) and set(value) == set(COHORT_KEYS),
            "cohort must have workflow, tests and runner exact digests")
    require(all(isinstance(value[x], str) and HEX64.fullmatch(value[x])
                for x in COHORT_KEYS), "invalid cohort digest")
    return {x: value[x] for x in COHORT_KEYS}


def coverage(value, sha):
    if value is None:
        return None
    require(isinstance(value, dict) and value.get("source_sha") == sha,
            "coverage source SHA mismatch")
    for key in ("scope_sha256", "config_sha256", "artifact_sha256"):
        require(isinstance(value.get(key), str)
                and HEX64.fullmatch(value[key]),
                "missing coverage provenance: " + key)
    require(isinstance(value.get("tool_version"), str)
            and value["tool_version"].strip(), "coverage version absent")
    for part in ("lines", "branches"):
        valid, covered = value.get("eligible_" + part), value.get("covered_" + part)
        require(integer(valid) and integer(covered) and covered <= valid,
                "invalid coverage denominator: " + part)
    return value


def parse_row(raw):
    require(isinstance(raw, dict) and integer(raw.get("wave"), 1),
            "invalid ordered wave number")
    stamp = utc(raw.get("observed_at"))
    source = raw.get("projection")
    require(isinstance(source, dict) and source.get("schema") == PROJECTION
            and source.get("root_register_created") is False
            and source.get("html_truth_store_created") is False
            and source.get("merge_authorized") is False
            and source.get("authority_transfer") is False
            and source.get("admission") == "HOLD"
            and source.get("qps_engineering_acceptance") == "DEFER",
            "consumer source/authority invalid")
    identity = source.get("source")
    require(isinstance(identity, dict)
            and identity.get("repository") == "GBOGEB/ABACUS"
            and identity.get("original_binary_authenticated") is False
            and isinstance(identity.get("head_sha"), str)
            and HEX40.fullmatch(identity["head_sha"])
            and isinstance(identity.get("producer_sha256_claim"), str)
            and HEX64.fullmatch(identity["producer_sha256_claim"]),
            "unbound source identity")
    metrics = source.get("observed")
    require(isinstance(metrics, dict), "missing canonical metrics")
    total, terminal, success, pending = [
        metrics.get(x) for x in ("workflow_total_n", "workflow_terminal_n",
                                  "workflow_success_n", "workflow_pending_n")
    ]
    require(all(integer(x) for x in (total, terminal, success, pending))
            and total > 0 and terminal + pending == total
            and success <= terminal, "workflow denominator inconsistency")
    actual_rate = success / total if pending == 0 else None
    reported = metrics.get("workflow_success_fraction_descriptive")
    require((reported is None if pending else finite_number(reported)
             and abs(reported - actual_rate) <= 1e-8),
            "improper completed-workflow rate")
    trials = raw.get("run_attempts")
    require(isinstance(trials, list) and len(trials) == total
            and all(isinstance(x, list) and len(x) == 2
                    and all(integer(y, 1) for y in x) for x in trials)
            and len({tuple(x) for x in trials}) == len(trials),
            "run/attempt selection not uniquely bound")
    red = metrics.get("red_jobs_total")
    attributed = metrics.get("first_red_manifestations")
    missing = metrics.get("red_jobs_unattributed")
    require(all(integer(x) for x in (red, attributed, missing))
            and attributed + missing == red,
            "first-red denominator mismatch")
    queue_n = metrics.get("queue_samples")
    queue_native = metrics.get("queue_native_n")
    queue_fallback = metrics.get("queue_fallback_n")
    require(all(integer(x) for x in (queue_n, queue_native, queue_fallback))
            and queue_native + queue_fallback == queue_n,
            "queue basis denominator mismatch")
    p95 = metrics.get("queue_p95_seconds_source_reported")
    require((p95 is None if queue_n == 0
             else finite_number(p95) and p95 >= 0),
            "missing or invalid queue p95")
    cov = coverage(raw.get("coverage"), identity["head_sha"])
    return {
        "wave": raw["wave"], "observed_at": raw["observed_at"],
        "_clock": stamp, "source_sha": identity["head_sha"],
        "producer_digest_claim": identity["producer_sha256_claim"],
        "cohort": cohort(raw.get("cohort")),
        "run_attempts": [tuple(x) for x in trials],
        "workflow_total": total, "terminal": pending == 0,
        "success": success, "failure": metrics.get("workflow_failure_n"),
        "success_fraction": actual_rate,
        "red_jobs": red, "first_red_attributed": attributed,
        "first_red_fraction": attributed / red if red else None,
        "first_red_signatures": metrics.get("first_red_unique_signatures"),
        "queue_n": queue_n, "queue_native": queue_native,
        "queue_fallback": queue_fallback, "queue_p95": p95, "coverage": cov,
    }


def delta(before, after):
    cohort_match = before["cohort"] == after["cohort"]
    matched = (cohort_match and before["terminal"] and after["terminal"]
               and before["workflow_total"] == after["workflow_total"])
    queue_ok = (matched and min(before["queue_n"], after["queue_n"]) >= MIN_QUEUE
                and before["queue_fallback"] == after["queue_fallback"] == 0)
    c1, c2 = before["coverage"], after["coverage"]
    reasons = []
    if c1 is None or c2 is None:
        reasons.append("COVERAGE_MISSING")
    else:
        for key in ("scope_sha256", "config_sha256", "tool_version"):
            if c1[key] != c2[key]:
                reasons.append("COVERAGE_" + key.upper() + "_MISMATCH")
        for part in ("lines", "branches"):
            if c1["eligible_" + part] != c2["eligible_" + part]:
                reasons.append("COVERAGE_" + part.upper() + "_DENOMINATOR_CHANGED")
    comparable_coverage = matched and not reasons
    def covdelta(part):
        if not comparable_coverage:
            return None
        denom = c1["eligible_" + part]
        if not denom:
            return None
        return round(100 * (c2["covered_" + part] -
                            c1["covered_" + part]) / denom, 6)
    return {
        "from_wave": before["wave"], "to_wave": after["wave"],
        "cohort_matched": cohort_match,
        "terminal_denominator_matched": matched,
        "success_delta_pp_descriptive": (
            round(100 * (after["success_fraction"] -
                         before["success_fraction"]), 6) if matched else None),
        "queue_p95_delta_seconds_descriptive": (
            after["queue_p95"] - before["queue_p95"] if queue_ok else None),
        "queue_comparability": ("NATIVE_CLOCK_DESCRIPTIVE_ONLY" if queue_ok
                                 else "HOLD_MIXED_OR_UNQUALIFIED_CLOCK"),
        "coverage_comparability": ("DESCRIPTIVE_ONLY" if comparable_coverage
                                   else "HOLD_" + ",".join(reasons or ["COHORT"])),
        "line_coverage_delta_pp_candidate": covdelta("lines"),
        "branch_coverage_delta_pp_candidate": covdelta("branches"),
        "first_red_attribution_delta_pp": (
            round(100 * (after["first_red_fraction"] -
                         before["first_red_fraction"]), 6)
            if matched and before["first_red_fraction"] is not None
            and after["first_red_fraction"] is not None else None),
        "accepted_root_closures": None,
        "accepted_main_coverage": None,
        "causal_credit": None,
    }


def score_forecast(entry, by_wave):
    require(isinstance(entry, dict) and entry.get("method") == "persistence-v1"
            and entry.get("metric") == "workflow_success_fraction",
            "unsupported forecast method/metric")
    issue, target = entry.get("issued_wave"), entry.get("target_wave")
    require(integer(issue, 1) and integer(target, 1)
            and target in (issue + 1, issue + 2) and issue in by_wave,
            "forecast horizon or issuing wave invalid")
    observed = by_wave[issue]
    issued_at = utc(entry.get("issued_at"))
    require(issued_at > observed["_clock"]
            and entry.get("issued_sha") == observed["source_sha"]
            and observed["terminal"],
            "forecast issued without terminal source provenance")
    estimate = entry.get("prediction")
    require(finite_number(estimate) and 0 <= estimate <= 1
            and abs(estimate - observed["success_fraction"]) < 1e-9,
            "unqualified persistence prediction")
    actual = by_wave.get(target)
    if actual is not None:
        require(issued_at < actual["_clock"], "backdated forecast after actual")
        require(actual["terminal"] and actual["cohort"] == observed["cohort"]
                and actual["workflow_total"] == observed["workflow_total"],
                "forecast target unqualified or cohort changed")
    deviation = (actual["success_fraction"] - estimate if actual else None)
    return {"issued_wave": issue, "target_wave": target,
            "issued_sha": observed["source_sha"], "method": entry["method"],
            "issued_at": entry["issued_at"], "prediction": estimate,
            "actual": actual["success_fraction"] if actual else None,
            "signed_error": deviation,
            "absolute_error": abs(deviation) if deviation is not None else None,
            "squared_error": deviation ** 2 if deviation is not None else None,
            "kind": "FIXED_POINT_PREDICTION_NOT_BINOMIAL_CI",
            "immutable_provenance_authenticated": False}


def rollup(doc):
    require(isinstance(doc, dict) and doc.get("schema") == SCHEMA
            and doc.get("repository") == "GBOGEB/ABACUS"
            and doc.get("authority_transfer") is False,
            "series source schema or authority invalid")
    raw = doc.get("observations")
    require(isinstance(raw, list) and 1 <= len(raw) <= 200,
            "bounded source observations required")
    rows = [parse_row(x) for x in raw]
    used = set()
    for i, row in enumerate(rows):
        if i:
            require(row["wave"] == rows[i-1]["wave"] + 1
                    and row["_clock"] > rows[i-1]["_clock"],
                    "state clock must be strictly increasing")
        for identity in row["run_attempts"]:
            require(identity not in used,
                    "native run/attempt identity reused across waves")
            used.add(identity)
    forecasts = doc.get("forecasts", [])
    require(isinstance(forecasts, list), "forecasts list required")
    by_wave = {x["wave"]: x for x in rows}
    forecast_out = [score_forecast(x, by_wave) for x in forecasts]
    keyset = {(x["issued_wave"], x["target_wave"]) for x in forecast_out}
    require(len(keyset) == len(forecast_out), "duplicate immutable forecast key")
    scored = [x for x in forecast_out if x["absolute_error"] is not None]
    latest = rows[-1]
    proposals = []
    if latest["terminal"]:
        proposals = [{"issued_wave": latest["wave"],
                      "target_wave": latest["wave"] + lag,
                      "method": "persistence-v1",
                      "proposed_prediction": latest["success_fraction"],
                      "state": "UNISSUED"} for lag in (1, 2)]
    visible = [{key: val for key, val in x.items()
                if key not in ("_clock", "coverage", "run_attempts")}
               for x in rows]
    return {
        "schema": OUT, "repository": doc["repository"],
        "waves_observed": len(rows),
        "native_run_attempts_bound": len(used),
        "rows": visible,
        "comparisons": [delta(a, b) for a, b in zip(rows, rows[1:])],
        "forecasts": forecast_out, "forecast_n_scored": len(scored),
        "forecast_mae": (sum(x["absolute_error"] for x in scored) / len(scored)
                         if scored else None),
        "forecast_rmse": (math.sqrt(sum(x["squared_error"] for x in scored)
                                    / len(scored)) if scored else None),
        "proposed_n_plus_1_n_plus_2": proposals,
        "independent_observations_authenticated": None,
        "sampling_design_authenticated": None,
        "pca_qualified": False,
        "bt_qualified": False, "anova_qualified": False,
        "manova_qualified": False,
        "wilson_90_95_99_qualified": False,
        "provider": "GBOGEB/gg_MATH",
        "accepted_root_closures": None, "authority_transfer": False,
        "merge_authorized": False, "qps_acceptance": "DEFER",
        "admission": "HOLD",
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    require(args.input.is_file() and not args.input.is_symlink()
            and 0 < args.input.stat().st_size <= 5_000_000,
            "missing/linked/oversized input")
    require(args.input.resolve() != args.out.resolve()
            and not args.out.is_symlink(), "output aliases input")
    if args.out.exists():
        require(not os.path.samefile(args.input, args.out), "hardlink alias")
    raw = args.input.read_bytes()
    projection = rollup(json.loads(raw))
    projection["input_digest_sha256"] = hashlib.sha256(raw).hexdigest()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix="." + args.out.name + ".",
                                dir=args.out.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(projection, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temp, args.out)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
