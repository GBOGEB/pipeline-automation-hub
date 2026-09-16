#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import validate_gm_fleet as fleet_validator

ROOT = Path(__file__).resolve().parent


def load(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def digest(obj: object) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-sha", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    contract = load("GM_IV_ACTIVE8_PROMOTION_CONTRACT.json")
    readiness = load("GM_IV_ACTIVE8_GOVERNOR_CONTRACT.json")
    registry = load("GRAND_MISSION_REGISTRY.json")
    city = load("MISSION_CITY_GRAPH.json")
    economics = load("GM_IV_EVIDENCE_ECONOMICS.json")

    missions = {m["id"]: m for m in registry["grand_missions"]}
    gm4 = missions["GM-IV"]
    gm5 = missions["GM-V"]
    shape = contract["required_shape"]
    accepted = contract["accepted_readiness_evidence"]
    edges = {tuple(edge) for edge in city["edges"]}

    checks: dict[str, bool] = {}
    checks["01_contract_identity"] = (
        contract["mission_id"] == "GM-IV"
        and contract["from_state"] == "STAGED_ACTIVE_RECON_4_OF_8"
        and contract["to_state"] == "ACTIVE_8_OF_8"
        and contract["to_activation_stage"] == "ACTIVE_8_OF_8"
    )
    checks["02_readiness_evidence_exact"] = (
        accepted["source_sha"] == contract["readiness_source_sha"] == "3943ae33eea2a4af6171b97517c19b79ed986fe8"
        and accepted["workflow_run_id"] == 35145656795
        and accepted["artifact_id"] == 10467671042
        and accepted["artifact_digest"] == "sha256:97d37b98334acbab0e1fec9bae56163e20fd5b9c2751be2495c52642bc6dd4cb"
        and accepted["decision"] == "READY_FOR_SEPARATE_ACTIVE_8_PROMOTION_PR"
        and accepted["result"] == "PASS"
        and readiness["from_state"] == "STAGED_ACTIVE_RECON_4_OF_8"
        and readiness["proposed_to_state"] == "ACTIVE_8_OF_8"
    )
    checks["03_registry_active8_state"] = (
        gm4["state"] == contract["to_state"]
        and gm4["activation_stage"] == contract["to_activation_stage"]
        and gm4["frontier_count"] == 8
    )
    checks["04_exact_eight_frontier_shape"] = (
        gm4["candidate_frontiers"] == shape["candidate_frontiers"]
        and gm4["controlled_pilot_frontiers"] == shape["controlled_pilot_frontiers"]
        and gm4["reference_frontiers"] == shape["reference_frontiers"]
        and gm4["new_candidate_recon_frontiers"] == shape["new_candidate_recon_frontiers"]
        and gm4["unfilled_frontier_slots"] == shape["unfilled_frontier_slots"] == []
        and gm4["children"] == shape["children"] == []
    )
    checks["05_exact_active8_evidence_bound"] = (
        gm4.get("active_8_of_8_evidence") == accepted
        and fleet_validator.valid_active8_evidence(gm4.get("active_8_of_8_evidence"))
    )
    checks["06_recon4_evidence_retained"] = fleet_validator.valid_recon4_evidence(gm4.get("recon_4_of_8_evidence"))
    checks["07_dispositions_retained"] = (
        gm4["controlled_pilot_frontiers"] == ["GM-IV-F01", "GM-IV-F03"]
        and gm4["reference_frontiers"] == ["GM-IV-F02", "GM-IV-F04"]
        and gm4["new_candidate_recon_frontiers"] == ["GM-IV-F05", "GM-IV-F06", "GM-IV-F07", "GM-IV-F08"]
    )
    checks["08_mission_city_synchronized"] = (
        city["mission_states"]["GM-IV"] == "ACTIVE_8_OF_8"
        and ("MISSION_CONTROL", "GM-IV", "ACTIVE_8_OF_8_COMMAND") in edges
        and ("FLEET_POOL", "GM-IV", "SCOUT_ACTIVE_8_CONTROLLED") in edges
        and ("GOVERNANCE_POOL", "GM-IV", "SECOND_GOVERNOR_ACTIVE8_CONTROL") in edges
    )
    checks["09_generic_fleet_accepts_exact_active8"] = fleet_validator.gm_iv_supported_shape(gm4)
    inv = economics["fleet_invariant"]
    checks["10_evidence_economics_synchronized"] = (
        inv["mission_stage"] == "ACTIVE_8_OF_8"
        and inv["named_recon_frontiers"] == shape["candidate_frontiers"]
        and inv["controlled_pilot_frontiers"] == shape["controlled_pilot_frontiers"]
        and inv["reference_frontiers"] == shape["reference_frontiers"]
        and inv["new_candidate_recon_frontiers"] == shape["new_candidate_recon_frontiers"]
        and inv["unfilled_frontier_slots"] == []
        and inv["canonical_children_bound"] == 0
    )
    checks["11_local_models_still_fail_closed"] = (
        economics["pca_gate"]["state"] == "DEFER"
        and economics["bt_gate"]["state"] == "DEFER"
    )
    checks["12_no_authority_or_child_binding"] = (
        registry["authority_transfer"] is False
        and economics["authority_transfer"] is False
        and readiness["authority_transfer"] is False
        and readiness["children_bound"] is False
        and gm4["children"] == []
    )
    checks["13_gm_v_held_separate_gate"] = (
        gm5["state"] == "HELD"
        and gm5["children"] == []
        and gm5["crew_posture"] == "UNALLOCATED"
        and "POST_ACTIVE8_REPEAT_CONTROL" in gm5["launch_gate"]
    )

    passed = all(checks.values())
    receipt = {
        "schema": "qps.gm_iv_active8_promotion_receipt.v1",
        "wave": contract["wave"],
        "source_sha": args.source_sha,
        "result": "PASS_GM_IV_ACTIVE8_PROMOTION" if passed else "FAIL_GM_IV_ACTIVE8_PROMOTION",
        "checks": checks,
        "check_count": len(checks),
        "current_state": gm4["state"],
        "activation_stage": gm4["activation_stage"],
        "candidate_frontiers": gm4["candidate_frontiers"],
        "children_bound": False,
        "authority_transfer": False,
        "gm_v_state": gm5["state"],
        "gm_v_launch_authorized": False,
        "next_stage": "POST_ACTIVE8_REPEAT_CONTROL_AND_MEASURED_CAPACITY_BEFORE_ANY_GM_V_LAUNCH",
        "accepted_readiness_evidence": accepted,
        "input_digest_sha256": digest({
            "contract": contract,
            "readiness": readiness,
            "registry": registry,
            "city": city,
            "economics": economics,
        }),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
