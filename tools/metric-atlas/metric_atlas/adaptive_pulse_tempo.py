"""W381 read-only adaptive pulse *candidate* from canonical owner receipts.

Input is a frozen, homogeneous N-10..N pulse series. We do not fetch jobs, issue
CRON changes, authenticate receipts, or own the underlying queue/root metrics.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
from metric_atlas import topic_exchange as exchange

SCHEMA = "metric-atlas.adaptive-pulse-input.v1"
OUT = "metric-atlas.adaptive-pulse-candidate.v1"
LEVELS = (3, 6, 12)
OWNERS = ("actions_metrics", "everred", "topic_exchange")
METRICS = ("queue_p95_s", "queue_depth", "running_jobs", "unique_roots",
           "source_collisions", "controller_acks", "reused_packets", "source_reads")


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def valid_number(value, integer=False):
    return (type(value) is int if integer else type(value) in (int, float)
            and math.isfinite(value)) and value >= 0


def validate(doc):
    need(type(doc) is dict and set(doc) == {"schema", "mode", "current_budget",
         "limits", "pulses", "authority_transfer", "execution_authorized"},
         "INVALID_PULSE_INPUT")
    need(doc["schema"] == SCHEMA and doc["mode"] == "READ_ONLY_CANDIDATE"
         and doc["authority_transfer"] is False and doc["execution_authorized"] is False,
         "AUTHORITY_PROMOTION")
    need(type(doc["current_budget"]) is int and doc["current_budget"] in LEVELS,
         "BAD_TOPIC_BUDGET")
    limits = doc["limits"]
    need(type(limits) is dict and set(limits) ==
         {"max_queue_p95_s", "max_queue_depth", "max_running_jobs"}, "INVALID_LIMITS")
    for key, value in limits.items():
        need(valid_number(value) and value > 0, "INVALID_LIMIT_VALUE")
    pulses = doc["pulses"]
    need(type(pulses) is list and 1 <= len(pulses) <= 11, "BOUNDED_HISTORY_REQUIRED")
    previous = None
    bindings = set()
    for p in pulses:
        need(type(p) is dict and set(p) == {"n", "observed_at", "cohort_sha256",
             "method_version", "population_sha256", "provenance", "evidence_class",
             "metrics"}, "INVALID_PULSE_RECORD")
        need(type(p["n"]) is int and p["n"] >= 0, "BAD_PULSE_INDEX")
        at = exchange.timestamp(p["observed_at"])
        if previous is not None:
            need(p["n"] == previous["n"] + 1, "GAPPED_OR_REORDERED_HISTORY")
            need(at > previous["_time"], "NONMONOTONE_PULSE_TIME")
        previous = {"n": p["n"], "_time": at}
        need(all(exchange._sha(p[k], 64) for k in
                 ("cohort_sha256", "population_sha256")), "INVALID_COHORT_DIGEST")
        need(type(p["method_version"]) is str and bool(p["method_version"]),
             "MISSING_METHOD_VERSION")
        bindings.add((p["cohort_sha256"], p["method_version"], p["population_sha256"]))
        need(p["evidence_class"] in ("DECLARED_SCENARIO", "OWNER_RECEIPT_REFERENCED"),
             "UNSUPPORTED_EVIDENCE_CLASS")
        prov = p["provenance"]
        need(type(prov) is dict and set(prov) == set(OWNERS), "MISSING_METRIC_OWNER")
        for name in OWNERS:
            row = prov[name]
            need(type(row) is dict and set(row) == {"source_head", "receipt_sha256"}
                 and exchange._sha(row["source_head"], 40)
                 and exchange._sha(row["receipt_sha256"], 64), "INVALID_OWNER_BINDING")
        m = p["metrics"]
        need(type(m) is dict and set(m) == set(METRICS), "INVALID_METRIC_POPULATION")
        for k, v in m.items():
            need(v is None or valid_number(v, integer=k != "queue_p95_s"),
                 "INVALID_MEASUREMENT")
    need(len(bindings) == 1, "INCOMPARABLE_COHORT_OR_METHOD")
    return pulses


def propose(doc):
    pulses = validate(doc)
    current = pulses[-1]["metrics"]
    anchors = {"N-1": pulses[-2] if len(pulses) >= 2 else None,
               "N-5": pulses[-6] if len(pulses) >= 6 else None,
               "N-10": pulses[-11] if len(pulses) >= 11 else None}
    windows = {name: ({"n": row["n"], "queue_p95_s": row["metrics"]["queue_p95_s"],
                 "unique_roots": row["metrics"]["unique_roots"],
                 "source_reads": row["metrics"]["source_reads"]}
                 if row else None) for name, row in anchors.items()}
    required = ("queue_p95_s", "queue_depth", "running_jobs", "unique_roots",
                "source_collisions", "controller_acks", "reused_packets")
    missing = [key for key in required if current[key] is None]
    overloaded = (not missing and
                  (current["queue_p95_s"] > doc["limits"]["max_queue_p95_s"]
                   or current["queue_depth"] > doc["limits"]["max_queue_depth"]
                   or current["running_jobs"] >= doc["limits"]["max_running_jobs"]
                   or current["source_collisions"] > 0))
    complete = len(pulses) == 11 and all(
        anchors[k] is not None and anchors[k]["metrics"]["queue_p95_s"] is not None
        and anchors[k]["metrics"]["unique_roots"] is not None
        for k in anchors)
    nonregression = complete and not missing and all(
        current["queue_p95_s"] <= anchors[k]["metrics"]["queue_p95_s"]
        and current["unique_roots"] <= anchors[k]["metrics"]["unique_roots"]
        for k in anchors)
    recent_good = len(pulses) >= 2 and all(
        row["metrics"]["source_collisions"] == 0
        and row["metrics"]["controller_acks"] is not None
        and row["metrics"]["controller_acks"] >= 1
        and row["metrics"]["reused_packets"] is not None
        and row["metrics"]["reused_packets"] >= 1
        for row in pulses[-2:])
    level = doc["current_budget"]
    if missing:
        state, budget, multiplier = "HOLD_MISSING_TELEMETRY", level, 1
    elif overloaded:
        state, budget, multiplier = ("DECELERATE_CANDIDATE",
                                    LEVELS[max(0, LEVELS.index(level)-1)], 2)
    elif not complete:
        state, budget, multiplier = "HOLD_N10_INCOMPLETE", level, 1
    elif not nonregression or not recent_good:
        state, budget, multiplier = "STEADY_NO_SCALE_EVIDENCE", level, 1
    elif level == LEVELS[-1]:
        state, budget, multiplier = "STEADY_AT_CEILING", level, 1
    else:
        state, budget, multiplier = ("ACCELERATE_CANDIDATE",
                                    LEVELS[LEVELS.index(level)+1], 0.5)
    return {"schema": OUT, "source_input_sha256": exchange.digest(doc),
            "latest_n": pulses[-1]["n"], "window_references": windows,
            "cohort_comparable": True, "source_evidence_class":
                sorted({p["evidence_class"] for p in pulses}),
            "proposed_state": state, "topic_budget_now": level,
            "topic_budget_candidate": budget,
            "delta_probe_interval_multiplier_candidate": multiplier,
            "missing_metrics": missing,
            "verified_real_world_savings": None,
            "actual_queue_gain": None, "new_cron_jobs": 0,
            "native_workers_launched": 0, "authority_transfer": False,
            "execution_authorized": False, "merge_admission": "HOLD"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = propose(json.loads(args.input.read_text(encoding="utf-8")))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                        encoding="utf-8", newline="\n")
    print(json.dumps({"state": result["proposed_state"], "authorization": False}))


if __name__ == "__main__":
    main()
