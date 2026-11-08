#!/usr/bin/env python3
"""Fail-closed validator for the GM-I-C R2 re-open overlay (two-way Drive bridge with broker).

The overlay may add waves, contracts, REX and runtime workers. It may not rewrite the v0.1
baseline: gate ids, crew, first red, authority and credit are checked against it.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
CONTROL = ROOT / "GM_I_C_R2_BIDIRECTIONAL_BRIDGE_CONTROL_v1.yaml"
BASELINE_CONTROL = ROOT / "GM-I-C_CROSS_AGENT_DRIVE_FEDERATION_CONTROL_v0.1.yaml"
BASELINE_CREW = ROOT / "GM-I-C_CREW_ALLOCATION_v0.1.yaml"

SHA40 = re.compile(r"^[0-9a-f]{40}$")
OPEN_STATES = {"PLANNED", "IN_PROGRESS", "BLOCKED_ON_OWNER"}
DONE_STATE = "PASS"
REQUIRED_NONCLAIMS = {
    "R2_REOPEN_NE_IC3_PASS",
    "R2_OFFLINE_CONTRACT_PASS_NE_HOSTED_DRIVE_PASS",
    "DRIVE_SNAPSHOT_NE_SOURCE_OF_TRUTH",
    "BROKER_DRAFT_PR_NE_REVIEW_OR_MERGE",
    "NO_GM_VI_NO_RENUMBERING",
}
BROKER_FUNCTIONS = {
    "HOLD", "READ", "PUBLISH", "REVIEW", "UPDATE", "FIX", "COMMIT", "DISJOINTED_COMMIT", "DISJOINTED_CENSUS",
}


class Fail(SystemExit):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Fail(f"FAIL: {message}")


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def validate(control: dict, baseline: dict, crew: dict, brief_text: str) -> dict:
    require(control.get("mission_id") == "GM-I-C", "overlay mission id must be GM-I-C")
    require(control.get("parent") == "GM-I", "overlay parent must remain GM-I")
    require(control.get("authority_transfer") is False, "authority transfer must remain false")
    require(control.get("formal_credit_delta") == 0, "formal credit delta must remain zero")
    require(control.get("reopen_kind") == "BRIEF_EXPANSION_OVERLAY", "re-open must be an overlay")

    base = control["baseline"]
    require(base["treatment"].startswith("OVERLAY_DO_NOT_REWRITE"), "baseline treatment must forbid rewrite")
    for key in ("historical_control", "historical_crew", "current_pointer"):
        require((REPO / base[key]).is_file(), f"baseline file missing: {base[key]}")
    for key in ("home_base_sha", "provider_main_sha_at_reopen"):
        require(bool(SHA40.match(str(base[key]))), f"{key} must be a full 40-hex SHA")

    first_red = control["first_red"]
    require(first_red["gate"] == baseline["first_red"]["gate"] == "IC3_AUTH", "first red must remain IC3_AUTH")
    require(first_red["owner"] == baseline["first_red"]["owner"], "first-red owner must match baseline")
    require(first_red["unchanged_from_baseline"] is True, "first red must be declared unchanged")

    gate_ids = [row["id"] for row in baseline["mission_gates"]]
    crew_ids = {row["crew_id"] for row in crew["active_crew"]} | {row["crew_id"] for row in crew["reserve_crew"]}
    active_ids = {row["crew_id"] for row in crew["active_crew"]}

    waves = control["waves"]
    wave_ids = [w["id"] for w in waves]
    require(wave_ids == [f"R2-W{i}" for i in range(len(waves))], f"wave ids must be R2-W0..R2-W{len(waves)-1} in order")
    ic3_pass = False
    states = {}
    for wave in waves:
        wid = wave["id"]
        for gate in wave["maps_to_gates"]:
            require(gate in gate_ids, f"{wid} maps to unknown gate {gate}")
        unknown = set(wave["crew"]) - crew_ids
        require(not unknown, f"{wid} assigns crew outside the v0.1 roster: {sorted(unknown)}")
        require(bool(wave.get("dod")), f"{wid} has no definition of done")
        state = wave["state"]
        states[wid] = state
        if state == DONE_STATE:
            ev = wave.get("evidence") or {}
            require(isinstance(ev.get("pr"), int), f"{wid} PASS without a PR number")
            require(bool(SHA40.match(str(ev.get("merge_sha", "")))), f"{wid} PASS without a full merge SHA")
            if "IC3_AUTH" in wave["maps_to_gates"]:
                ic3_pass = True
        elif state.startswith("BLOCKED_ON_R2-W"):
            blocker = state.removeprefix("BLOCKED_ON_")
            require(blocker in wave_ids and wave_ids.index(blocker) < wave_ids.index(wid), f"{wid} blocked on unknown or later wave {blocker}")
        else:
            require(state in OPEN_STATES, f"{wid} has unknown state {state}")
        reserve_used = set(wave["crew"]) - active_ids
        if reserve_used:
            require(wid in brief_text, f"{wid} wakes reserve crew {sorted(reserve_used)} but is not in the brief")

    for wave in waves:
        state = wave["state"]
        if state.startswith("BLOCKED_ON_R2-W"):
            continue
        if state == DONE_STATE:
            for earlier in waves[: wave_ids.index(wave["id"])]:
                if earlier["owner_action_required"] is False:
                    require(earlier["state"] == DONE_STATE, f"{wave['id']} PASS while earlier {earlier['id']} not PASS")
    if not ic3_pass:
        require(first_red["state"].startswith("WITHHELD"), "IC3 not passed: first red must stay WITHHELD")

    contracts = {c["id"]: c for c in control["contracts"]}
    require(len(contracts) == len(control["contracts"]), "duplicate contract ids")
    for cid, c in contracts.items():
        require(c["owner_repo"] == "GBOGEB/GEMINI", f"{cid} must be owned by the provider repo")
        require(c["wave"] in wave_ids, f"{cid} bound to unknown wave")
        if c["disposition"] != "NEW_NO_EXISTING_OWNER":
            require(bool(c.get("reuse_of")), f"{cid} reuses something but names no owner")
    require(contracts["gmi.proposal_profile.v1"]["disposition"] == "PROFILE_OF_EXISTING", "proposal must profile the GMI package contract")

    require(set(control["broker"]["functions"]) == BROKER_FUNCTIONS, "broker function set changed")
    require(control["broker"]["is_crew"] is False, "broker must not be crew")
    require("NEVER" in control["broker"]["functions"]["FIX"], "broker must never fix")
    require("NEVER_DEFAULT_BRANCH" in control["broker"]["functions"]["COMMIT"], "broker must never commit to default branch")

    for worker in control["runtime_workers_added"]:
        require(worker["is_crew"] is False, f"{worker['id']} must not be crew")
        require(worker["id"] not in crew_ids, f"{worker['id']} collides with a crew id")

    rex_ids = [r["id"] for r in control["rex_new"]]
    require(len(rex_ids) == len(set(rex_ids)), "duplicate REX ids")
    inherited = {r["id"] for r in baseline["inherited_rex"]}
    require(not (set(rex_ids) & inherited), "new REX ids collide with inherited REX")
    for rex in control["rex_new"]:
        require(all(rex.get(k) for k in ("learning", "evidence", "action")), f"{rex['id']} incomplete")

    missing_nonclaims = REQUIRED_NONCLAIMS - set(control["explicit_nonclaims"])
    require(not missing_nonclaims, f"missing non-claims: {sorted(missing_nonclaims)}")

    for token in wave_ids + rex_ids + list(contracts):
        require(token in brief_text, f"brief does not mention {token}")

    return {
        "result": "PASS_GM_I_C_R2_OVERLAY",
        "mission_id": "GM-I-C",
        "reopen_id": control["reopen_id"],
        "waves": states,
        "first_red": first_red["gate"],
        "first_red_state": first_red["state"],
        "contracts": sorted(contracts),
        "rex_new": rex_ids,
        "authority_transfer": False,
        "formal_credit_delta": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control", type=Path, default=CONTROL)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    control = load_yaml(args.control)
    brief_path = REPO / control["brief"]
    require(brief_path.is_file(), f"brief missing: {control['brief']}")
    result = validate(control, load_yaml(BASELINE_CONTROL), load_yaml(BASELINE_CREW), brief_path.read_text(encoding="utf-8"))
    text = json.dumps(result, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
