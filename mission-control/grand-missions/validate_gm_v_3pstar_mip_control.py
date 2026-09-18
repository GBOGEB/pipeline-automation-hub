#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def load(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))

def canon_sha256(obj: object) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-sha", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    control = load("GM_V_3PSTAR_MIP_CONTROL_v1.json")
    current = load("GM_V_CURRENT_v1.json")
    registry = load("GRAND_MISSION_REGISTRY.json")
    governor = load("GM_V_GOVERNOR_READINESS_CONTRACT.json")
    missions = {m["id"]: m for m in registry["grand_missions"]}
    gm4 = missions["GM-IV"]
    gm5 = missions["GM-V"]
    obs = current["child_runtime_gate"]["latest_observation"]
    cobs = control["lineage"]["latest_qps_runtime_observation"]

    checks: dict[str, bool] = {}
    checks["01_current_pointer_canonical"] = current["canonical"] is True
    checks["02_gm_iv_active8"] = (
        gm4["state"] == "ACTIVE_8_OF_8"
        and gm4["activation_stage"] == "ACTIVE_8_OF_8"
        and gm4["children"] == []
    )
    checks["03_gm_v_held_unallocated"] = (
        gm5["state"] == "HELD"
        and gm5["children"] == []
        and gm5["crew_posture"] == "UNALLOCATED"
        and current["gm_v"]["launch_authorized"] is False
    )
    checks["04_runtime_capacity_boundary"] = (
        current["gm_iv"]["runtime_capacity_class"] == "RUNTIME_PROVEN"
        and current["gm_iv"]["capability_coverage"] == "8_OF_8"
        and current["gm_iv"]["concurrency_capacity_claimed"] is False
        and control["lineage"]["runtime_capability_capacity"]["measurement_scope"]
            == "CAPABILITY_COVERAGE_NOT_CONCURRENCY_CAPACITY"
    )
    checks["05_governor_withhold_boundary"] = (
        current["gm_v"]["latest_governor_decision"]
            == "WITHHOLD_GM_V_LAUNCH_EXTERNAL_OPERATIONAL_AVAILABILITY"
        and governor["decision_semantics"]["WITHHOLD"]
            == "WITHHOLD_GM_V_LAUNCH_EXTERNAL_OPERATIONAL_AVAILABILITY"
        and current["child_runtime_gate"]["compensation_allowed"] is False
    )
    checks["06_three_pr_complete"] = all(
        control["three_pr"][k]["result"] == "PASS"
        for k in ("Refresh", "Probe", "Rank")
    )
    checks["07_mip_progression"] = (
        control["mip"]["Modernize"]["result"] == "PASS"
        and control["mip"]["Innovate"]["result"] == "PASS"
        and control["mip"]["Perpetuate"]["result"] == "THIS_TRANSACTION"
        and control["latest_iteration"]["mip"]["Perpetuate"]
            == "PASS_HANDOVER_V2_ZERO_CHAT_ONLY_STATE"
    )
    checks["08_three_pc_boundary"] = (
        control["three_pc"]["Prepare"]["result"] == "PASS_CONTROL_PREPARED"
        and control["three_pc"]["Prove"]["result"] == "WITHHELD_EXTERNAL"
        and control["three_pc"]["Commit"]["result"] == "HOLD_WAIT_PROVE"
    )
    checks["09_three_p3_not_authorized"] = control["three_p3"]["authorized"] is False
    checks["10_qps_gate_bound"] = (
        current["child_runtime_gate"]["issue"] == 923
        and current["child_runtime_gate"]["issue_state"] == "OPEN"
        and current["child_runtime_gate"]["classification"]
            == "INFRA_PREEXECUTION_ZERO_STEP / RUNNER_ADMISSION"
        and current["child_runtime_gate"]["refreshed_main"]
            == "eeac2b60fc16e5b2131d4054f95da0b0c663cc40"
        and control["source_authority"]["qps_main_at_refresh"]
            == current["child_runtime_gate"]["refreshed_main"]
    )
    checks["11_exact_receipt_lineage"] = (
        control["lineage"]["runtime_capability_capacity"]["run_id"] == 35171901674
        and control["lineage"]["runtime_capability_capacity"]["artifact_id"] == 10476967287
        and control["lineage"]["gm_v_readiness"]["postmerge_run_id"] == 35343419829
        and control["lineage"]["gm_v_readiness"]["postmerge_artifact_id"] == 10546460986
        and control["lineage"]["historical_control_fixforward"]["merge_sha"]
            == "3df37a0485874f968f0dffa02bc474c5f4645fba"
    )
    checks["12_no_chat_only_state"] = (
        current["chat_only_todo_count"] == 0
        and current["chat_only_decision_count"] == 0
    )
    checks["13_no_authority_or_credit"] = (
        current["authority_transfer"] is False
        and current["formal_credit_delta"] == 0
        and control["authority_transfer"] is False
        and control["formal_credit_delta"] == 0
        and control["engineering_credit_delta"] == 0
        and registry["authority_transfer"] is False
    )
    checks["14_reentry_is_owner_change_first"] = (
        current["next_order"][0] == "REFRESH_MISSIONCONTROL_MASTER_AND_QPS_MAIN"
        and "OWNER_SIDE_ACTIONS_ADMISSION_CHANGE" in control["three_pc"]["Prepare"]["required_inputs"]
        and control["three_pr"]["Rank"]["no_blind_rerun"] is True
    )
    jobs = obs["release_runner_probe"]["jobs"]
    checks["15_latest_qps_observation_exact"] = (
        obs == cobs
        and obs["qps_pr"] == 1476
        and obs["qps_head_sha"] == "458dae93993a970d94c5a8c85c2d04e40390e454"
        and obs["qps_merge_sha"] == "eeac2b60fc16e5b2131d4054f95da0b0c663cc40"
        and obs["release_runner_probe"]["run_id"] == 35350233629
        and len(jobs) == 3
        and all(j["executed_steps"] == 0 for j in jobs)
        and obs["independent_validator"]["run_id"] == 35350233647
        and obs["independent_validator"]["job_id"] == 105616351882
        and obs["independent_validator"]["executed_steps"] == 0
        and obs["classification"] == "INFRA_PREEXECUTION_ZERO_STEP / RUNNER_ADMISSION"
    )
    checks["16_w281_rebind_is_noncompensating"] = (
        control["latest_iteration"]["qps_probe_was_retriggered"] is False
        and control["latest_iteration"]["three_pr"]["Probe"]
            == "PASS_BLOCK_CONFIRMED_FROM_EXISTING_RUNS_NO_RERUN"
        and current["progression"]["three_pc_prove"] == "WITHHELD_EXTERNAL"
        and current["gm_v"]["launch_authorized"] is False
    )
    checks["17_v2_restart_bound"] = (
        current["missioncontrol"]["handover"].endswith("_v2.md")
        and current["missioncontrol"]["restart"].endswith("_v2.md")
    )

    passed = all(checks.values())
    receipt = {
        "schema": "missioncontrol.gm_v.3pstar_mip_validation_receipt.v1",
        "source_sha": args.source_sha,
        "result": "PASS_GM_V_3PSTAR_MIP_CONTROL" if passed else "FAIL_GM_V_3PSTAR_MIP_CONTROL",
        "check_count": len(checks),
        "checks": checks,
        "gm_iv_state": gm4["state"],
        "gm_v_state": gm5["state"],
        "gm_v_launch_authorized": False,
        "three_pc_prove": control["three_pc"]["Prove"]["result"],
        "three_p3_authorized": control["three_p3"]["authorized"],
        "qps_runtime_gate": current["child_runtime_gate"]["classification"],
        "latest_qps_probe_run": obs["release_runner_probe"]["run_id"],
        "latest_qps_probe_all_zero_step": all(j["executed_steps"] == 0 for j in jobs),
        "input_digest_sha256": canon_sha256({
            "control": control,
            "current": current,
            "registry": registry,
            "governor": governor,
        }),
        "authority_transfer": False,
        "formal_credit_delta": 0,
    }
    Path(args.out).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if passed else 1

if __name__ == "__main__":
    raise SystemExit(main())
