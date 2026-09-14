#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
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

    contract = load("GM_IV_RECON4_PROMOTION_CONTRACT.json")
    governor = load("GM_IV_RECON4_GOVERNOR_CONTRACT.json")
    pilot2 = load("GM_IV_PILOT2_GOVERNOR_CONTRACT.json")
    registry = load("GRAND_MISSION_REGISTRY.json")
    city = load("MISSION_CITY_GRAPH.json")
    economics = load("GM_IV_EVIDENCE_ECONOMICS.json")

    missions = {m["id"]: m for m in registry["grand_missions"]}
    gm4 = missions["GM-IV"]
    gm5 = missions["GM-V"]
    shape = contract["required_shape"]
    edges = {tuple(edge) for edge in city["edges"]}
    accepted = contract["accepted_governor_evidence"]

    checks: dict[str, bool] = {}
    checks["01_contract_identity"] = (
        contract["mission_id"] == "GM-IV"
        and contract["from_state"] == "STAGED_ACTIVE_PILOT_2_OF_8"
        and contract["to_state"] == "STAGED_ACTIVE_RECON_4_OF_8"
        and contract["to_activation_stage"] == "RECON_4_OF_8"
    )
    checks["02_governor_evidence_contract_parity"] = (
        accepted == governor["accepted_gate_evidence"]
        and accepted["source_sha"] == contract["predecessor_governor_merge_sha"]
        and accepted["decision"] == "READY_FOR_SEPARATE_RECON_4_PROMOTION_PR"
        and accepted["post_merge_workflow_success_count"] == accepted["post_merge_workflow_total"] == 14
    )
    checks["03_registry_recon4_state"] = (
        gm4["state"] == contract["to_state"]
        and gm4["activation_stage"] == contract["to_activation_stage"]
        and gm4["frontier_count"] == 8
    )
    checks["04_exact_four_frontier_shape"] = (
        gm4["candidate_frontiers"] == shape["candidate_frontiers"]
        and gm4["controlled_pilot_frontiers"] == shape["controlled_pilot_frontiers"]
        and gm4["reference_frontiers"] == shape["reference_frontiers"]
        and gm4["unfilled_frontier_slots"] == shape["unfilled_frontier_slots"]
        and gm4["children"] == shape["children"] == []
    )
    checks["05_exact_recon4_evidence_bound"] = (
        gm4.get("recon_4_of_8_evidence") == accepted
        and fleet_validator.valid_recon4_evidence(gm4.get("recon_4_of_8_evidence"))
    )
    checks["06_historical_f01_evidence_retained"] = (
        gm4["pilot_2_of_8_evidence"]["F01"] == pilot2["controlled_pilots"]["GM-IV-F01"]
    )
    checks["07_historical_f03_evidence_retained"] = (
        gm4["pilot_2_of_8_evidence"]["F03"] == pilot2["controlled_pilots"]["GM-IV-F03"]
    )
    checks["08_reference_dispositions_retained"] = (
        pilot2["reference_frontiers"]["GM-IV-F02"]["disposition"] == "REFERENCE"
        and pilot2["reference_frontiers"]["GM-IV-F04"]["disposition"] == "REFERENCE"
        and gm4["reference_frontiers"] == ["GM-IV-F02", "GM-IV-F04"]
    )
    checks["09_mission_city_synchronized"] = (
        city["mission_states"]["GM-IV"] == gm4["state"]
        and ("MISSION_CONTROL", "GM-IV", "RECON_4_OF_8_COMMAND") in edges
        and ("FLEET_POOL", "GM-IV", "SCOUT_RECON_4_CONTROLLED") in edges
        and ("GOVERNANCE_POOL", "GM-IV", "SECOND_GOVERNOR_STAGE_CONTROL") in edges
    )
    checks["10_generic_fleet_accepts_exact_recon4"] = fleet_validator.gm_iv_supported_shape(gm4)

    active8 = copy.deepcopy(gm4)
    active8["state"] = "ACTIVE_8_OF_8"
    active8["activation_stage"] = "ACTIVE_8_OF_8"
    checks["11_active8_remains_fail_closed"] = (
        "ACTIVE_8_OF_8" in fleet_validator.FORWARD_GM_IV_STATES_REQUIRING_GOVERNOR
        and "ACTIVE_8_OF_8" not in fleet_validator.SUPPORTED_GM_IV_STATES
        and not fleet_validator.gm_iv_supported_shape(active8)
    )
    inv = economics["fleet_invariant"]
    checks["12_evidence_economics_synchronized"] = (
        inv["mission_stage"] == "RECON_4_OF_8"
        and inv["named_recon_frontiers"] == shape["candidate_frontiers"]
        and inv["controlled_pilot_frontiers"] == shape["controlled_pilot_frontiers"]
        and inv["reference_frontiers"] == shape["reference_frontiers"]
        and inv["unfilled_frontier_slots"] == shape["unfilled_frontier_slots"]
    )
    checks["13_local_models_still_fail_closed"] = (
        economics["pca_gate"]["state"] == "DEFER"
        and economics["bt_gate"]["state"] == "DEFER"
    )
    checks["14_no_authority_or_child_binding"] = (
        registry["authority_transfer"] is False
        and economics["authority_transfer"] is False
        and governor["authority_transfer"] is False
        and governor["children_bound"] is False
        and gm4["children"] == []
    )
    checks["15_gm_v_held"] = gm5["state"] == "HELD" and gm5["children"] == []

    passed = all(checks.values())
    receipt = {
        "schema": "qps.gm_iv_recon4_promotion_receipt.v1",
        "wave": contract["wave"],
        "source_sha": args.source_sha,
        "result": "PASS_GM_IV_RECON4_PROMOTION" if passed else "FAIL_GM_IV_RECON4_PROMOTION",
        "checks": checks,
        "check_count": len(checks),
        "current_state": gm4["state"],
        "activation_stage": gm4["activation_stage"],
        "named_recon_frontiers": gm4["candidate_frontiers"],
        "controlled_pilot_frontiers": gm4["controlled_pilot_frontiers"],
        "reference_frontiers": gm4["reference_frontiers"],
        "unfilled_frontier_slots": gm4["unfilled_frontier_slots"],
        "children_bound": False,
        "authority_transfer": False,
        "gm_v_state": gm5["state"],
        "active_8_authorized": False,
        "next_stage": "WITHHELD_PENDING_SEPARATE_ACTIVE_8_GOVERNOR_GATE",
        "accepted_governor_evidence": accepted,
        "input_digest_sha256": digest({
            "contract": contract,
            "governor": governor,
            "pilot2": pilot2,
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
