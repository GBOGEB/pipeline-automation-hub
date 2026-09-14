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


def bound_evidence(item: dict, disposition: str) -> bool:
    required = ["repository", "target_sha", "master_source_sha", "workflow_run_id", "artifact_id", "artifact_digest"]
    if any(not item.get(key) for key in required):
        return False
    return (
        isinstance(item["target_sha"], str)
        and len(item["target_sha"]) == 40
        and isinstance(item["master_source_sha"], str)
        and len(item["master_source_sha"]) == 40
        and isinstance(item["workflow_run_id"], int)
        and item["workflow_run_id"] > 0
        and isinstance(item["artifact_id"], int)
        and item["artifact_id"] > 0
        and isinstance(item["artifact_digest"], str)
        and item["artifact_digest"].startswith("sha256:")
        and len(item["artifact_digest"]) == 71
        and item.get("disposition") == disposition
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-sha", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    contract = load("GM_IV_RECON4_GOVERNOR_CONTRACT.json")
    pilot2 = load("GM_IV_PILOT2_GOVERNOR_CONTRACT.json")
    capacity = load("GM_FLEET_03_CAPACITY_CONTRACT.json")
    registry = load("GRAND_MISSION_REGISTRY.json")
    city = load("MISSION_CITY_GRAPH.json")

    missions = {item["id"]: item for item in registry["grand_missions"]}
    gm4 = missions["GM-IV"]
    gm5 = missions["GM-V"]
    proposed = dict(contract["proposed_shape"])
    proposed["frontier_count"] = gm4["frontier_count"]

    capacity_stage = next(
        item for item in capacity["stage_model"] if item["stage"] == "RECON_4_OF_8"
    )
    city_edges = {tuple(edge) for edge in city["edges"]}

    checks: dict[str, bool] = {}
    checks["01_contract_identity"] = (
        contract["mission_id"] == "GM-IV"
        and contract["from_state"] == "STAGED_ACTIVE_PILOT_2_OF_8"
        and contract["proposed_to_state"] == "STAGED_ACTIVE_RECON_4_OF_8"
        and contract["authority_transfer"] is False
        and contract["children_bound"] is False
    )
    checks["02_current_state_is_pilot2"] = (
        gm4["state"] == "STAGED_ACTIVE_PILOT_2_OF_8"
        and gm4["activation_stage"] == "PILOT_2_OF_8"
        and gm4["children"] == []
    )
    checks["03_current_four_frontier_identity"] = (
        gm4["candidate_frontiers"] == contract["frontier_policy"]["named_recon_frontiers"]
        and gm4["controlled_pilot_frontiers"] == contract["frontier_policy"]["controlled_pilots_retained"]
        and gm4["reference_frontiers"] == contract["frontier_policy"]["bounded_references_retained"]
        and gm4["unfilled_frontier_slots"] == contract["frontier_policy"]["unfilled_frontier_slots"]
    )

    registry_pilots = gm4["pilot_2_of_8_evidence"]
    pilot_contract = pilot2["controlled_pilots"]
    checks["04_f01_control_evidence_bound"] = (
        bound_evidence(pilot_contract["GM-IV-F01"], "PILOT_CONTROL_READY")
        and registry_pilots["F01"] == pilot_contract["GM-IV-F01"]
    )
    checks["05_f03_control_evidence_bound"] = (
        bound_evidence(pilot_contract["GM-IV-F03"], "PILOT_CONTROL_READY")
        and registry_pilots["F03"] == pilot_contract["GM-IV-F03"]
    )
    checks["06_f02_reference_evidence_bound"] = bound_evidence(
        pilot2["reference_frontiers"]["GM-IV-F02"], "REFERENCE"
    )
    checks["07_f04_reference_evidence_bound"] = bound_evidence(
        pilot2["reference_frontiers"]["GM-IV-F04"], "REFERENCE"
    )
    checks["08_pilot2_boundary_requires_separate_gate"] = (
        "DOES_NOT_AUTHORIZE_RECON_4_OF_8" in pilot2["next_stage_boundary"]
        and "SEPARATE_GOVERNOR_GATE_IS_REQUIRED" in pilot2["next_stage_boundary"]
    )
    checks["09_capacity_contract_authorizes_shape_class_only"] = (
        capacity_stage["maximum_bound_frontiers"] == 4
        and capacity_stage["authority_transfer"] is False
        and "four_named_frontiers" in capacity_stage["meaning"]
    )
    checks["10_mission_city_recon_reserve"] = (
        city["mission_states"]["GM-IV"] == gm4["state"]
        and ("FLEET_POOL", "GM-IV", "SCOUT_RESERVE_FOR_RECON_4") in city_edges
        and ("GOVERNANCE_POOL", "GM-IV", "SECOND_GOVERNOR_STAGE_CONTROL") in city_edges
    )
    checks["11_proposed_shape_complete"] = (
        proposed["state"] == "STAGED_ACTIVE_RECON_4_OF_8"
        and proposed["activation_stage"] == "RECON_4_OF_8"
        and proposed["candidate_frontiers"] == ["GM-IV-F01", "GM-IV-F02", "GM-IV-F03", "GM-IV-F04"]
        and proposed["controlled_pilot_frontiers"] == ["GM-IV-F01", "GM-IV-F03"]
        and proposed["reference_frontiers"] == ["GM-IV-F02", "GM-IV-F04"]
        and proposed["unfilled_frontier_slots"] == ["GM-IV-F05", "GM-IV-F06", "GM-IV-F07", "GM-IV-F08"]
        and proposed["children"] == []
    )
    checks["12_validator_still_fail_closed_before_promotion"] = not fleet_validator.gm_iv_supported_shape(proposed)
    checks["13_gm_v_held"] = (
        gm5["state"] == contract["gm_v_required_state"]
        and gm5["children"] == []
    )
    checks["14_no_registry_promotion_in_gate_lane"] = (
        gm4["state"] != contract["proposed_to_state"]
        and gm4["activation_stage"] != contract["proposed_activation_stage"]
    )

    ready = all(checks.values())
    decision = (
        contract["decision_semantics"]["READY"]
        if ready
        else contract["decision_semantics"]["WITHHOLD"]
    )

    receipt = {
        "schema": "qps.gm_iv_recon4_governor_readiness_receipt.v1",
        "wave": contract["wave"],
        "source_sha": args.source_sha,
        "predecessor_control_sha": contract["predecessor_control_sha"],
        "result": "PASS" if ready else "FAIL",
        "decision": decision,
        "checks": checks,
        "check_count": len(checks),
        "proposed_shape": contract["proposed_shape"],
        "proposed_shape_digest_sha256": digest(contract["proposed_shape"]),
        "current_state": gm4["state"],
        "registry_mutated": False,
        "mission_city_mutated": False,
        "children_bound": False,
        "authority_transfer": False,
        "gm_v_state": gm5["state"],
        "promotion_executed": False,
        "next_action": (
            "SEPARATE_RECON_4_PROMOTION_PR_WITH_EXACT_HEAD_CENSUS"
            if ready
            else "REPAIR_FIRST_RED_AND_REPEAT_GATE"
        ),
        "input_digest_sha256": digest({
            "contract": contract,
            "pilot2": pilot2,
            "capacity": capacity,
            "registry": registry,
            "city": city,
        }),
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
