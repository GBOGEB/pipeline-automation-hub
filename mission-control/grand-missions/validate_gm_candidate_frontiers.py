#!/usr/bin/env python3
"""Validate GM-IV provisional candidates and GM-V reserve without promoting held missions."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def require(ok: bool, message: str) -> None:
    if not ok:
        raise SystemExit(f"FAIL: {message}")
    print(f"PASS: {message}")


def main() -> int:
    registry = load("GRAND_MISSION_REGISTRY.json")
    board = load("GM_IV_V_CANDIDATE_BOARD.json")
    scout = load("GM_IV_SCOUT_LEDGER.json")

    missions = {m["id"]: m for m in registry["grand_missions"]}
    gm4 = missions["GM-IV"]
    gm5 = missions["GM-V"]

    require(gm4["state"] == "HELD", "GM-IV remains HELD")
    require(gm4["children"] == [], "GM-IV canonical children remain empty")
    require(gm5["state"] == "HELD", "GM-V remains HELD")
    require(gm5["children"] == [], "GM-V canonical children remain empty")
    require(board["canonical_registry_unchanged"] is True, "candidate board declares no canonical mutation")

    candidates = board["gm_iv"]["frontiers"]
    reserves = board["gm_v_candidate_pool"]["ranked_reserve"]
    require(len(candidates) == 8, "GM-IV has exactly eight provisional scout slots")
    require(len(reserves) == 16, "GM-V has exactly sixteen ranked reserve slots")

    candidate_repos = [row["repo"] for row in candidates]
    reserve_repos = [row["repo"] for row in reserves]
    require(len(set(candidate_repos)) == 8, "GM-IV provisional repos are unique")
    require(len(set(reserve_repos)) == 16, "GM-V reserve repos are unique")
    require(set(candidate_repos).isdisjoint(reserve_repos), "GM-IV and GM-V pools do not overlap")

    excluded = set(board["hard_exclusions"]["already_assigned_grand_mission_repos"])
    excluded.update(board["hard_exclusions"]["horizontal_qps_triage_core"])
    require(set(candidate_repos).isdisjoint(excluded), "GM-IV candidates exclude prior grand-mission and horizontal-core repos")
    require(set(reserve_repos).isdisjoint(excluded), "GM-V reserve excludes prior grand-mission and horizontal-core repos")

    scout_rows = scout["frontiers"]
    require(len(scout_rows) == 8, "scout ledger covers all eight GM-IV provisional slots")
    require({r["repo"] for r in scout_rows} == set(candidate_repos), "scout ledger exactly matches provisional GM-IV pool")
    require(all(len(r["observed_head"]) == 40 for r in scout_rows), "all provisional scouts bind a 40-char observed head")
    require(scout["canonical_assignment_authorized"] is False, "scout ledger forbids premature canonical assignment")

    accepted_now = set(scout["acceptance_classes"]["ACCEPTED_NOW"])
    conditional = set(scout["acceptance_classes"]["ACCEPTED_CONDITIONAL_CURRENT_HEAD_REPEAT"])
    probe = set(scout["acceptance_classes"]["ACCEPTED_TO_BOUNDED_PROBE"])
    require(accepted_now | conditional | probe == set(candidate_repos), "every GM-IV slot has one controlled scout disposition")
    require(not (accepted_now & conditional or accepted_now & probe or conditional & probe), "scout acceptance classes are disjoint")

    print("RESULT: PASS_CANDIDATE_BOARD_HELD_CANONICAL")
    print(f"GM_IV_ACCEPTED_NOW={len(accepted_now)}")
    print(f"GM_IV_CONDITIONAL={len(conditional)}")
    print(f"GM_IV_PROBE_PENDING={len(probe)}")
    print("GM_V_RESERVE=16")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
