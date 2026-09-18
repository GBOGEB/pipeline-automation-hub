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
    )
    checks["08_three_pc_boundary"] = (
        control["three_pc"]["Prepare"]["result"] == "PASS_CONTROL_PREPARED"
        and control["three_pc"]["Prove"]["result"] == "WITHHELD_EXTERNAL"
        and control["three_pc"]["Commit"]["result"] == "HOLD_WAIT_PROVE"
        and control["three_pc"]["Commit"]["gm_v_launch_authorized"] is False
    )
    checks["09_three_p3_not_authorized"] = control["three_p3"]["authorized"] is False
    checks["10_qps_gate_bound"] = (
        current["child_runtime_gate"]["issue"] == 923
        and current["child_runtime_gate"]["issue_state"] == "OPEN"
        and current["child_runtime_gate"]["classification"]
            == "INFRA_PREEXECUTION_ZERO_STEP / RUNNER_ADMISSION"
        and len(current["child_runtime_gate"]["refreshed_main"]) == 40
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
    repo_root = ROOT.parent.parent
    required_outputs = control["mip"]["Perpetuate"]["required_outputs"]
    checks["15_perpetuate_outputs_exist"] = (
        len(required_outputs) == 6
        and len(set(required_outputs)) == 6
        and all((repo_root / p).is_file() for p in required_outputs)
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
        "gm_v_launch_authorized": control["three_pc"]["Commit"]["gm_v_launch_authorized"],
        "three_pc_prove": control["three_pc"]["Prove"]["result"],
        "three_p3_authorized": control["three_p3"]["authorized"],
        "qps_runtime_gate": current["child_runtime_gate"]["classification"],
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
