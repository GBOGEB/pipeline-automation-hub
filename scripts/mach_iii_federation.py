"""Read-only MACH-III federation evaluator: no network or merge actions."""
import json
import sys
from pathlib import Path


def evaluate(policy, observations):
    seen = set()
    category_prs = {}
    root_prs = {}
    unknown = set()
    for item in observations:
        pr = item["pr"]
        identity = (pr, item.get("head_sha"), item.get("run_id"), item.get("job_id"))
        if identity in seen:
            continue
        seen.add(identity)
        if item.get("status") != "failure":
            continue
        category_prs.setdefault(item.get("job", "UNKNOWN"), set()).add(pr)
        if all(item.get(k) for k in ("head_sha", "first_red_signature", "root_id", "root_evidence")):
            root_prs.setdefault(item["root_id"], set()).add(pr)
        else:
            unknown.add(pr)
    return {"active": bool(policy.get("active", False)), "admission": "HOLD",
            "observed_records": len(seen),
            "observed_prs": len({i["pr"] for i in observations}),
            "job_label_overlap": {k: len(v) for k, v in sorted(category_prs.items())},
            "proven_root_leverage": {k: len(v) for k, v in sorted(root_prs.items())},
            "unknown_root_prs": sorted(unknown),
            "actual_merges": None, "effective_ruleset_verified": False}


if __name__ == "__main__":
    policy = json.loads(Path(sys.argv[1]).read_text())
    observations = json.loads(Path(sys.argv[2]).read_text())["observations"] if len(sys.argv) > 2 else []
    print(json.dumps(evaluate(policy, observations), indent=2))
