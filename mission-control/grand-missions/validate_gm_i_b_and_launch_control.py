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
    require(set(variants) == {"GM-I-A", "GM-I-B", "GM-I-C"}, f"GM-I variants invalid: {sorted(variants)}")
    ib = variants["GM-I-B"]
    require(ib["repository"] == "GBOGEB/gg_MATH", "I-B provider repo drift")
    require(ib["state"] == "CONTROL_SENTINEL_RECEIPT_REGRESSION", "I-B CONTROL posture drift")
    require(ib["provider_merge_sha"] == "e9afd4131bde2071d184d0e3c5326b82f5756faa", "I-B merge SHA drift")
    require(ib["exact_federation_head_sha"] == "a5f32ef2b65caa9b49270d7fe8134acd6f1e71d8", "I-B exact federation head drift")
    require(ib["original_provider_receipt_digest"] == "sha256:876c55c759de33392985f693f1735cdc0d38dda7d7b7a6c80ee80aee33fd8405", "I-B provider receipt digest drift")
    closure = ib.get("keb_closure", {})
    require(closure.get("abacus_pr") == 1252 and closure.get("abacus_exact_dow_run_id") == 35145377318, "I-B DOW closure drift")
    require(closure.get("codex_pr") == 750 and closure.get("codex_atom_id") == "KEB-ITEM-0002" and closure.get("codex_object_type") == "KEB_KNOWLEDGE_ATOM", "I-B KEB atom drift")
    require(closure.get("state") == "CLOSED_REAL_ATOM", "I-B KEB closure drift")
    require(ib["authority_transfer"] is False and ib["formal_credit_delta"] == 0, "I-B authority guard failed")

    ic = variants["GM-I-C"]
    require(ic.get("repository") == "GBOGEB/GEMINI", "I-C provider repo drift")
    require(ic.get("state") == "REGISTERED_BUILD_EXTERNAL_AUTH_PROOF_PENDING", "I-C pre-proof state drift")
    require(ic.get("authority_transfer") is False and ic.get("formal_credit_delta") == 0, "I-C authority guard failed")

    require(gm["GM-II"]["state"] == "CONTROL", "GM-II sentinel state drift")
    require(gm["GM-III"]["state"] == "RECON_CONTROL", "GM-III state drift")
    require("GBOGEB/GEMINI" in gm["GM-III"].get("children", []), "GM-III GEMINI frontier history was rewritten")

    gm4 = gm["GM-IV"]
    require(gm4["state"] == "ACTIVE_8_OF_8" and gm4["activation_stage"] == "ACTIVE_8_OF_8", "GM-IV ACTIVE8 state drift")
    require(gm4["candidate_frontiers"] == [f"GM-IV-F{i:02d}" for i in range(1, 9)], "GM-IV eight-frontier shape drift")
    require(gm4["unfilled_frontier_slots"] == [] and gm4["children"] == [], "GM-IV slot/child drift")
    require(gm4.get("active_8_of_8_evidence", {}).get("decision") == "READY_FOR_SEPARATE_ACTIVE_8_PROMOTION_PR", "GM-IV ACTIVE8 evidence drift")
    require(gm["GM-V"]["state"] == "HELD" and gm["GM-V"]["children"] == [], "GM-V hold violated")

    require(pulse["canonical_state_must_remain"] == "STAGED_ACTIVE_RECON_4_OF_8", "historical F05/F06 pulse contract drift")
    require(pulse["promotion_allowed_by_this_pulse"] is False, "historical F05/F06 pulse promotion flag drift")

    order = launch["launch_order"]
    require([x["order"] for x in order] == [1, 2, 3, 4, 5, 6, 7], "launch ordering drift")
    require(order[0]["state"] == "DONE_CONTROL" and order[1]["state"] == "DONE_CONTROL", "I-B closure/sync drift")
    require(order[2]["id"] == "GM-I-B-CONTROL" and order[2]["state"] == "ACTIVE_SENTINEL", "I-B sentinel drift")
    require(order[3]["id"] == "GM-IV-F05-F06-PULSE" and order[3]["state"] == "DONE_HISTORICAL_EVIDENCE", "GM-IV historical pulse drift")
    require(order[4]["id"] == "GM-IV-ACTIVE8-PROMOTION" and order[4]["state"] == "DONE_REPEAT_CONTROL_AND_RUNTIME_CAPABILITY_CAPACITY", "ACTIVE8 post-control state drift")
    post = order[4].get("post_promotion_dov", {})
    require(post.get("repeat_control", {}).get("result") == "PASS_POST_ACTIVE8_REPEAT_CONTROL", "ACTIVE8 repeat CONTROL evidence drift")
    require(post.get("runtime_capability_capacity", {}).get("result") == "PASS_RUNTIME_PROVEN_CAPABILITY_CAPACITY", "ACTIVE8 runtime capability capacity drift")
    require(post.get("runtime_capability_capacity", {}).get("scope") == "CAPABILITY_COVERAGE_NOT_CONCURRENCY_CAPACITY", "capacity scope drift")
    require(post.get("operational_availability") == "WITHHELD_EXTERNAL_NONCOMPENSATING_QPS_923", "operational availability gate drift")
    require(post.get("gm_v_launch_authorized") is False, "GM-V launch must remain unauthorized")
    require(order[5]["policy"] == "continuous_control_presence_discontinuous_mission_execution", "sentinel policy drift")
    require(order[6]["state"] == "HELD_EXTERNAL_OPERATIONAL_AVAILABILITY_GATE", "GM-V launch-order hold drift")
    require(order[6].get("current_first_red") == "GBOGEB/cryoplant-project#923_PRIVATE_REPO_ACTIONS_RUNNER_ADMISSION", "GM-V first red drift")

    checks = {
        "canonical_five_missions_preserved": True,
        "gm_i_b_control_sentinel_and_real_keb_atom": True,
        "gm_i_c_registered_without_i_b_mutation": True,
        "gm_iii_gemini_frontier_history_preserved": True,
        "gm_ii_iii_sentinels_preserved": True,
        "gm_iv_active8_exact_shape": True,
        "gm_iv_post_active8_repeat_control": True,
        "gm_iv_runtime_capability_capacity_8_of_8": True,
        "gm_v_external_operational_availability_withhold": True,
        "historical_f05_f06_evidence_retained": True,
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
