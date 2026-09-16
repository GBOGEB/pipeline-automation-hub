#!/usr/bin/env python3
"""Validate GM-IV evidence economics across RECON4 and post-ACTIVE8 control."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEDGER = HERE / "GM_IV_EVIDENCE_ECONOMICS.json"
REGISTRY = HERE / "GRAND_MISSION_REGISTRY.json"


def main() -> int:
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    checks = []

    def ok(name: str, condition: bool, detail: str) -> None:
        checks.append({"name": name, "pass": bool(condition), "detail": detail})

    inv = ledger["fleet_invariant"]
    scope = ledger["model_scope"]
    gm = {row["id"]: row for row in registry["grand_missions"]}
    gm4 = gm["GM-IV"]
    gm5 = gm["GM-V"]
    active8 = gm4["state"] == "ACTIVE_8_OF_8"
    expected_frontiers = [f"GM-IV-F{i:02d}" for i in range(1, 9)] if active8 else [f"GM-IV-F{i:02d}" for i in range(1, 5)]
    expected_unfilled = [] if active8 else [f"GM-IV-F{i:02d}" for i in range(5, 9)]
    expected_stage = "ACTIVE_8_OF_8" if active8 else "RECON_4_OF_8"
    expected_registry_state = "ACTIVE_8_OF_8" if active8 else "STAGED_ACTIVE_RECON_4_OF_8"

    ok("01_stage_sync", inv["mission_stage"] == expected_stage and gm4["state"] == expected_registry_state and gm4["activation_stage"] == expected_stage, f"stage={expected_stage}")
    ok("02_zero_children", inv["canonical_children_bound"] == 0 and gm4["children"] == [], "GM-IV canonical children remain empty")
    ok("03_named_frontiers", inv["named_recon_frontiers"] == expected_frontiers and gm4.get("candidate_frontiers") == expected_frontiers, f"named={expected_frontiers}")
    ok("04_controlled_pilot_pair", inv["controlled_pilot_frontiers"] == ["GM-IV-F01", "GM-IV-F03"] and gm4.get("controlled_pilot_frontiers") == ["GM-IV-F01", "GM-IV-F03"], "F01/F03 retained")
    ok("05_reference_frontiers", inv["reference_frontiers"] == ["GM-IV-F02", "GM-IV-F04"] and gm4.get("reference_frontiers") == ["GM-IV-F02", "GM-IV-F04"], "F02/F04 retained")
    ok("06_frontier_slot_state", inv["unfilled_frontier_slots"] == expected_unfilled and gm4.get("unfilled_frontier_slots") == expected_unfilled, f"unfilled={expected_unfilled}")
    if active8:
        expected_new = ["GM-IV-F05", "GM-IV-F06", "GM-IV-F07", "GM-IV-F08"]
        ok("06b_active8_new_candidates", inv.get("new_candidate_recon_frontiers") == expected_new and gm4.get("new_candidate_recon_frontiers") == expected_new, "F05-F08 candidate-recon retained")
    ok("07_no_child_binding_or_authority_leakage", inv["f03_child_bound"] is False and inv["f04_child_bound"] is False and inv["pilot_frontier_labels_do_not_imply_children"] is True and ledger["authority_transfer"] is False and gm4["children"] == [], "no child/authority leakage")
    ok("08_gmv_held", inv["gm_v_state"] == "HELD" and gm5["state"] == "HELD" and gm5["children"] == [], "GM-V HELD")

    rows = ledger["rows"]
    ok("09_three_measured_rows", len(rows) == 3 and all(r["evidence_class"] == "MEASURED" for r in rows), "three measured Ring2 economics rows retained")
    ok("10_no_fabricated_crew_time", all(r["crew_time_seconds"] is None and r["crew_time_status"] == "NOT_INSTRUMENTED" for r in rows), "crew time remains uninstrumented")
    ok("11_no_slot_or_child_binding_from_economics", all(r["slot_bound"] is False and r["child_bound"] is False for r in rows), "economics cannot bind slots/children")
    ok("12_no_authority_transfer", ledger["authority_transfer"] is False and all(r["authority_transfer"] is False for r in rows), "authority external to economics")

    rates_ok = True
    for row in rows:
        expected = row["accepted_evidence_units"] / row["execute_seconds"] if row["execute_seconds"] else 0.0
        rates_ok = rates_ok and abs(expected - row["evidence_rate"]) < 1e-9
    ok("13_evidence_rate_math", rates_ok, "evidence-rate arithmetic retained")
    by_id = {r["row_id"]: r for r in rows}
    prov = by_id["GMIV_RING2_SCOUT_B_PROVENANCE_PASS"]
    full = by_id["GMIV_RING2_SCOUT_B_FULL_RUNTIME_PRUNED"]
    ratio = prov["evidence_rate"] / full["evidence_rate"]
    ok("14_provenance_efficiency_signal", ratio > 40 and full["payload_execute_seconds"] == 62, f"ratio={ratio:.6f}")
    ok("15_pruned_runtime_disposition", full["disposition"] == "PRUNE_FULL_RUNTIME_KEEP_PROVENANCE_REFERENCE", "redundant runtime remains pruned")
    ok("16_local_model_scope", scope["evidence_economics_models"] == "LOCAL_GMIV_RING2_ECONOMICS_ONLY" and "SEPARATE_MEASURED_CREW_PC3" in scope["global_model_context"], "local model scope retained")
    ok("17_pca_bt_fail_closed_locally", ledger["pca_gate"]["state"] == "DEFER" and ledger["bt_gate"]["state"] == "DEFER", "local PCA/BT stay DEFER")

    passed = sum(1 for c in checks if c["pass"])
    receipt = {
        "schema": "qps.gm_iv_evidence_economics_validation.v1",
        "status": "PASS" if passed == len(checks) else "FAIL",
        "passed": passed,
        "denominator": len(checks),
        "checks": checks,
        "fleet_invariant": f"GM-IV {expected_stage}; children=0; GM-V HELD",
        "model_scope": "LOCAL_GMIV_RING2_EVIDENCE_ECONOMICS",
        "authority_transfer": False,
    }
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
