"""Read-only MIP/DMAIC scaling decision from matched native pulse receipts.

Does not start GitHub jobs, create workers, merge PRs, waive reviews or
promote H01-H12 status. The 3->7->15->31 ladder is a proposal, not capacity.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

LADDER = (3, 7, 15, 31)
SHA = re.compile(r"^[0-9a-f]{40}$")


def validate(pulse):
    required = ("source_sha", "instrumentor_sha", "source_scope", "run_id",
                "queued", "running", "ready_disjoint", "first_red",
                "covered", "denominator", "zero_covered_files", "native_green")
    if not isinstance(pulse, dict) or any(k not in pulse for k in required):
        raise ValueError("incomplete pulse population")
    if not all(isinstance(pulse[k], str) and SHA.fullmatch(pulse[k])
               for k in ("source_sha", "instrumentor_sha")):
        raise ValueError("invalid exact identity")
    if not isinstance(pulse["source_scope"], str) or not pulse["source_scope"]:
        raise ValueError("unbound source population")
    for k in ("run_id", "queued", "running", "ready_disjoint",
              "first_red", "covered", "denominator", "zero_covered_files"):
        if type(pulse[k]) is not int or pulse[k] < 0:
            raise ValueError("invalid metric: " + k)
    if pulse["run_id"] == 0 or pulse["denominator"] == 0:
        raise ValueError("zero run or denominator")
    if pulse["covered"] > pulse["denominator"]:
        raise ValueError("covered exceeds denominator")
    if type(pulse["native_green"]) is not bool:
        raise ValueError("native_green must be boolean")
    return pulse


def decide(pulses, current=3):
    if current not in LADDER:
        raise ValueError("invalid capacity ladder position")
    if not isinstance(pulses, list) or not pulses:
        raise ValueError("no native pulses")
    for p in pulses:
        validate(p)
    recent = pulses[-3:]
    latest = recent[-1]
    identity = {(p["instrumentor_sha"], p["source_scope"], p["denominator"]) for p in recent}
    matched = len(recent) == 3 and len(identity) == 1
    distinct_runs = len({p["run_id"] for p in recent}) == len(recent)
    stable = len(recent) == 3 and distinct_runs and all(
        p["native_green"] and p["first_red"] == 0 for p in recent
    )
    queue_pressure = latest["queued"] > max(8, 2 * max(1, latest["running"]))
    delta_lines = recent[-1]["covered"] - recent[0]["covered"] if matched else None
    delta_zero = recent[-1]["zero_covered_files"] - recent[0]["zero_covered_files"] if matched else None
    measured_gain = matched and (delta_lines > 0 or delta_zero < 0)
    reason = "NO_PROMOTION"
    target = current
    if latest["first_red"] > 0 or not latest["native_green"]:
        reason = "FIRST_RED_ROUTE_DOCTOR"
    elif queue_pressure:
        target = LADDER[max(0, LADDER.index(current) - 1)]
        reason = "QUEUE_BACKPRESSURE_CONTRACT_OR_HOLD"
    elif not stable or not matched:
        reason = "NEED_THREE_DISTINCT_MATCHED_NATIVE_PULSES"
    elif not measured_gain:
        reason = "NO_MEASURED_COVERAGE_OR_ZERO_GAP_GAIN"
    elif latest["ready_disjoint"] <= current:
        reason = "NO_DISJOINT_WORK_TO_MULTIPLY"
    else:
        target = LADDER[min(len(LADDER) - 1, LADDER.index(current) + 1)]
        reason = "PROPOSE_EXPAND_AFTER_INDEPENDENT_GOVERNOR_CHECK"
    return {
        "schema": "missioncontrol.jade-scale.v1",
        "mode": reason,
        "proposed_parallel_ceiling": target,
        "current_parallel_ceiling": current,
        "observed_pulses": len(recent),
        "distinct_run_ids": distinct_runs,
        "matched_instrumentor_scope_denominator": matched,
        "three_native_green": stable,
        "queue_backpressure": queue_pressure,
        "covered_lines_delta": delta_lines,
        "zero_covered_file_delta": delta_zero,
        "measured_gain": bool(measured_gain),
        "source_sha": latest["source_sha"],
        "native_last_run_id": latest["run_id"],
        "crew_workers_actually_launched": None,
        "dispatch_authorized": False,
        "independent_review": False,
        "merge_authorized": False,
        "release_credit": 0,
        "authority_transfer": False,
        "dmaic": {
            "Define": "disjoint READY packets with exact SHA",
            "Measure": "native runs + queue + matched denominator + zero-covered files",
            "Analyze": reason,
            "Improve": "prefer reuse, split, route and first-red repair before scale",
            "Control": "non-compensating H08/H09/H12 HOLD",
        },
    }


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--pulses", type=Path, required=True)
    p.add_argument("--current", type=int, choices=LADDER, default=3)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    receipt = decide(json.loads(args.pulses.read_text(encoding="utf-8")), args.current)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8", newline="\n")
    print(json.dumps({"mode": receipt["mode"],
                      "proposed": receipt["proposed_parallel_ceiling"],
                      "dispatch_authorized": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
