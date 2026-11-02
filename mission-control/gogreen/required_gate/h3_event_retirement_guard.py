"""H3 preflight: no enforced gate may lose its only recheck event path.

Read-only, zero GitHub mutations; imports the existing required_gate owner.
This controls proposed listener-set migration, NOT the actual event producer
or the canonical Actions Metrics denominator.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OWNER = Path(__file__).with_name("gate.py")


def _owner():
    spec = importlib.util.spec_from_file_location("gogreen_h3_owner", OWNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def assess(required: list[str], live: list[str], proposed: list[str]) -> dict:
    """Missing or replaced upstream sources require owner-authorized native proof.

    No external proposal may itself certify an alternative event source;
    every removed enforced listener stays HOLD until an independent
    owner-controlled acceptance mechanism is implemented and proven.
    """
    all_lists = (required, live, proposed)
    valid = all(isinstance(xs, list) and all(isinstance(x, str) and x for x in xs)
                and len(xs) == len(set(xs)) for xs in all_lists)
    if not valid:
        return {"schema": "gogreen.h3.trigger-retirement-preflight.v1",
                "state": "HOLD", "reason": "invalid or duplicate workflow identities",
                "merge_authorized": False, "production_event_reduction": False}
    required_set, live_set, proposed_set = map(set, all_lists)
    missing_live = sorted(required_set - live_set)
    unknown_live = sorted(live_set - required_set)
    proposed_missing = sorted(required_set - proposed_set)
    proposed_extra = sorted(proposed_set - required_set)
    change = sorted(live_set ^ proposed_set)
    sound = not missing_live and not unknown_live
    # This deliberately cannot authorize removal. A future successor must
    # first have independent replay and owner-approved provenance evidence.
    state = "BASELINE_PRESERVED" if sound and not change else "HOLD"
    return {"schema": "gogreen.h3.trigger-retirement-preflight.v1",
            "state": state, "required_count": len(required),
            "live_listener_count": len(live), "candidate_listener_count": len(proposed),
            "missing_live_enforced": missing_live, "unlisted_live": unknown_live,
            "candidate_missing_enforced": proposed_missing, "candidate_extra": proposed_extra,
            "changed_listener_names": change,
            "verified_successor_count": 0,
            "approval_note": "No replacement source receipts or independent recovery DoV were supplied",
            "production_event_reduction": False, "merge_authorized": False}


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--proposed", type=Path, help="JSON list of proposed workflow_run listener names")
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        gate = _owner()
        ledger = gate.load_policy(None, None, a.root, "head")
        required = gate.recheck_names(a.root, ledger)
        live = gate.declared_recheck_names((a.root / gate.RECHECK).read_text(encoding="utf-8"))
        proposed = json.loads(a.proposed.read_text(encoding="utf-8")) if a.proposed else live
        result = assess(required, live, proposed)
    except (OSError, ValueError, KeyError, TypeError, ImportError) as exc:
        result = {"schema": "gogreen.h3.trigger-retirement-preflight.v1",
                  "state": "HOLD", "reason": type(exc).__name__,
                  "production_event_reduction": False, "merge_authorized": False}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["state"] == "BASELINE_PRESERVED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
