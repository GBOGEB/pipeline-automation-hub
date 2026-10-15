"""G2 local bounded queue scaling; synthetic observations never child-capacity credit."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from synthetic_probe import run

PROFILES = (
    ("small", 8, 2, 1, 1, None),
    ("medium", 32, 4, 2, 2, None),
    ("ceiling", 64, 8, 4, 3, None),
    ("negative", 8, 2, 2, 2, 3),
)

def matrix(profiles=PROFILES):
    if type(profiles) not in (list, tuple) or not 1 <= len(profiles) <= len(PROFILES):
        raise ValueError("profile count exceeds bounded offline testflight")
    names, entries = set(), []
    for name, total, depth, workers, cycles, fault in profiles:
        if not isinstance(name, str) or not name or name in names:
            raise ValueError("duplicate/invalid profile identity")
        names.add(name)
        result = run(total, depth, workers, cycles, fault)
        entries.append({"profile": name, "probe": result,
                        "cycle_count": cycles, "task_observations": total * cycles,
                        "fault_count": sum(x["faults"] for x in result["iterations"]),
                        "observed_max_queue": max(x["max_queue"] for x in result["iterations"]),
                        "observed_peak_workers": max(x["peak_in_flight"] for x in result["iterations"]),
                        "queue_wait_p95_ns_max": max(x["queue_wait_p95_ns"] for x in result["iterations"]),
                        "synthetic_throughput_per_cycle": [x["synthetic_throughput_tasks_per_s"] for x in result["iterations"]]})
    return {"schema": "gogreen.synthetic-scaling-matrix.v1", "state": "OFFLINE_ONLY",
            "profiles": entries, "profile_count": len(entries),
            "total_task_observations": sum(x["task_observations"] for x in entries),
            "independent_native_runs": None, "real_child_capacity": None,
            "statistical_stability": "NOT_ESTABLISHED", "remote_mutations": 0,
            "child_acceptance": "DEFER", "merge_authorized": False}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args=parser.parse_args()
    result=matrix()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"profile_count":result["profile_count"],
                      "total_task_observations":result["total_task_observations"],
                      "real_child_capacity":None},sort_keys=True))

if __name__ == "__main__":
    main()
