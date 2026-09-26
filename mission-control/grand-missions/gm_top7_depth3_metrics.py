#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path

GREEN = "PROVEN_GREEN"

def fail(msg: str) -> None:
    raise SystemExit("GM_TOP7_D3_FAIL: " + msg)

def repo_metrics(row: dict) -> dict:
    slots = [s for s in row.get("red_slots", []) if s.get("admitted") is True]
    if len(slots) > 3:
        fail(f"{row['repo']}: more than 3 admitted red slots")
    health = row["health"]
    decisive = int(health["successful_checks"]) + int(health["failed_checks"]) + int(health["action_required_checks"])
    blockers = int(health["failed_checks"]) + int(health["action_required_checks"])
    failure_rate = None if decisive == 0 else blockers / decisive
    proven = sum(1 for s in slots if s.get("status") == GREEN)
    implemented = sum(1 for s in slots if s.get("status") in {
        GREEN, "REPAIRED_PENDING_PROOF", "SUPERSEDED_BY_CONCURRENT_GREEN"
    })
    admitted = len(slots)
    reduction = None if admitted == 0 else proven / admitted
    dov = (
        bool(health.get("exact_head_proven"))
        and blockers == 0
        and int(health["pending_checks"]) == 0
        and int(health["zero_step_unknown"]) == 0
        and proven == admitted
    )
    return {
        "repo": row["repo"],
        "admitted_reds": admitted,
        "implemented_or_superseded_reds": implemented,
        "proven_green_reds": proven,
        "open_reds": admitted - proven,
        "depth_reached": proven,
        "decisive_checks": decisive,
        "blocker_checks": blockers,
        "failure_rate_nullable": failure_rate,
        "pending_checks": int(health["pending_checks"]),
        "zero_step_unknown": int(health["zero_step_unknown"]),
        "repo_dov": dov,
    }

def compute(doc: dict) -> dict:
    if doc.get("authority_transfer") is not False:
        fail("authority_transfer must remain false")
    if doc.get("formal_credit_delta") != 0 or doc.get("engineering_credit_delta") != 0:
        fail("credit deltas must remain zero")
    repos = doc.get("repositories", [])
    if len(repos) != 7 or len({r["repo"] for r in repos}) != 7:
        fail("mission must contain exactly seven unique repositories")
    rows = [repo_metrics(r) for r in repos]
    admitted = sum(r["admitted_reds"] for r in rows)
    proven = sum(r["proven_green_reds"] for r in rows)
    blockers = sum(r["blocker_checks"] for r in rows)
    pending = sum(r["pending_checks"] for r in rows)
    zero = sum(r["zero_step_unknown"] for r in rows)
    dov = all(r["repo_dov"] for r in rows)
    obs = doc.get("temporal_observations", [])
    temporal = None
    if len(obs) >= 2:
        first, last = obs[0], obs[-1]
        b = int(first["completed_failure_families"])
        c = int(last["completed_failure_families"])
        temporal = {
            "baseline_completed_failure_families": b,
            "latest_completed_failure_families": c,
            "visible_failure_reduction_count": b - c,
            "visible_failure_reduction_fraction": None if b == 0 else (b-c)/b,
            "dov_credit_from_visible_reduction": False,
        }
    return {
        "mission_id": doc["mission_id"],
        "repo_count": len(rows),
        "admitted_reds": admitted,
        "proven_green_reds": proven,
        "open_or_unproven_reds": admitted - proven,
        "fleet_blocker_checks": blockers,
        "fleet_pending_checks": pending,
        "fleet_zero_step_unknown": zero,
        "fleet_dov": dov,
        "repos": rows,
        "temporal": temporal,
    }

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--contract", required=True)
    ap.add_argument("--out")
    a=ap.parse_args()
    doc=json.loads(Path(a.contract).read_text(encoding="utf-8"))
    result=compute(doc)
    payload=json.dumps(result,indent=2,sort_keys=True)+"\n"
    if a.out:
        Path(a.out).write_text(payload,encoding="utf-8")
    print(payload,end="")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
