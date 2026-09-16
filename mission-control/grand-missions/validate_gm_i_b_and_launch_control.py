#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise SystemExit(f"FAIL: {message}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    registry = load("GRAND_MISSION_REGISTRY.json")
    launch = load("GM_FLEET_IMMINENT_LAUNCH_CONTROL_v1.json")
    pulse = load("GM_IV_F05_F06_BOUNDED_PULSE_CONTRACT.json")

    missions = registry["grand_missions"]
    ids = [m["id"] for m in missions]
    require(ids == ["GM-I", "GM-II", "GM-III", "GM-IV", "GM-V"], f"canonical ids changed: {ids}")
    require([m["frontier_count"] for m in missions] == [1, 2, 4, 8, 16], "scaling sequence changed")
    gm = {m["id"]: m for m in missions}

    variants = {v["id"]: v for v in gm["GM-I"].get("variants", [])}
    require(set(variants) == {"GM-I-A", "GM-I-B"}, f"GM-I variants invalid: {sorted(variants)}")
    ib = variants["GM-I-B"]
    require(ib["repository"] == "GBOGEB/gg_MATH", "I-B provider repo drift")
    require(ib["state"] == "KEB_CLOSURE_IN_PROGRESS", "I-B must remain pending until KEB atom closes")
    require(ib["provider_merge_sha"] == "e9afd4131bde2071d184d0e3c5326b82f5756faa", "I-B merge SHA drift")
    require(ib["exact_federation_head_sha"] == "a5f32ef2b65caa9b49270d7fe8134acd6f1e71d8", "I-B exact federation head drift")
    require(ib["federation_run_id"] == 35139956561, "I-B run drift")
    require(ib["federation_artifact_digest"] == "sha256:2c7cbcddffc6c3830ab02a212563ef390e7fe189ce24214f4313e6e5bccd2921", "I-B federation digest drift")
    require(ib["original_provider_receipt_digest"] == "sha256:876c55c759de33392985f693f1735cdc0d38dda7d7b7a6c80ee80aee33fd8405", "I-B provider receipt digest drift")
    require(ib["authority_transfer"] is False and ib["formal_credit_delta"] == 0, "I-B authority guard failed")

    require(gm["GM-II"]["state"] == "CONTROL", "GM-II sentinel state drift")
    require(gm["GM-II"]["crew_posture"] == "SMALL_RECURRENCE_CELLS", "GM-II crew posture drift")
    require(gm["GM-III"]["state"] == "RECON_CONTROL", "GM-III state drift")
    require(gm["GM-III"]["crew_posture"] == "BROAD_CREW_RETURNED_SPECIALISTS_RESERVE", "GM-III crew posture drift")
    require(gm["GM-IV"]["state"] == "STAGED_ACTIVE_RECON_4_OF_8", "GM-IV promoted without Governor")
    require(gm["GM-IV"]["unfilled_frontier_slots"] == ["GM-IV-F05", "GM-IV-F06", "GM-IV-F07", "GM-IV-F08"], "GM-IV slots drift")
    require(gm["GM-V"]["state"] == "HELD" and gm["GM-V"]["children"] == [], "GM-V hold violated")

    require(pulse["canonical_state_must_remain"] == "STAGED_ACTIVE_RECON_4_OF_8", "F05/F06 pulse can promote")
    require(pulse["promotion_allowed_by_this_pulse"] is False, "F05/F06 promotion flag must be false")
    frontiers = {f["slot"]: f for f in pulse["frontiers"]}
    require(list(frontiers) == ["GM-IV-F05", "GM-IV-F06"], "pulse must contain exactly F05 and F06")
    require(frontiers["GM-IV-F05"]["repository"] == "GBOGEB/ABACUS", "F05 identity drift")
    require(frontiers["GM-IV-F06"]["repository"] == "GBOGEB/CODEX", "F06 identity drift")
    require(all(f["target_sha"] and len(f["target_sha"]) == 40 for f in frontiers.values()), "frontier SHA missing")
    require(all(f["return_path"] for f in frontiers.values()), "frontier return path missing")

    order = launch["launch_order"]
    require([x["order"] for x in order] == [1, 2, 3, 4, 5, 6], "launch ordering drift")
    require(order[0]["id"] == "GM-I-B-KEB-CLOSURE", "launch #1 drift")
    require(order[1]["id"] == "GM-I-B-FLEET-SYNC", "launch #2 drift")
    require(order[2]["id"] == "GM-I-B-CONTROL" and order[2]["state"] == "BLOCKED_BY_1_AND_2", "I-B CONTROL gate drift")
    require(order[3]["id"] == "GM-IV-F05-F06-PULSE" and order[3]["state"] == "STAGED_NO_PROMOTION", "GM-IV pulse drift")
    require(order[4]["policy"] == "continuous_control_presence_discontinuous_mission_execution", "sentinel policy drift")
    require(order[5]["state"] == "HELD", "GM-V launch order hold drift")

    checks = {
        "canonical_five_missions_preserved": True,
        "gm_i_b_registered_as_variant": True,
        "gm_ii_iii_sentinel_states_preserved": True,
        "gm_iv_canonical_4_of_8_preserved": True,
        "gm_iv_f05_f06_bounded_pulse_only": True,
        "gm_v_held": True,
        "authority_transfer": False,
        "formal_credit_delta": 0,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"result": "PASS_GM_I_B_AND_IMMINENT_LAUNCH_CONTROL", "checks": checks}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("PASS_GM_I_B_AND_IMMINENT_LAUNCH_CONTROL")


if __name__ == "__main__":
    main()
