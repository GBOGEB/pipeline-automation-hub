#!/usr/bin/env python3
"""Validate GM-IV evidence economics without promoting pilot labels into children."""

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

    ok(
        "01_pilot_2_of_8",
        inv["mission_stage"] == "PILOT_2_OF_8"
        and gm4["state"] == "STAGED_ACTIVE_PILOT_2_OF_8"
        and gm4["activation_stage"] == "PILOT_2_OF_8",
        "GM-IV registry and economics agree on PILOT_2_OF_8",
    )
    ok(
        "02_zero_children",
        inv["canonical_children_bound"] == 0 and gm4["children"] == [],
        "GM-IV canonical children remain empty",
    )
    ok(
        "03_controlled_pilot_pair",
        inv["controlled_pilot_frontiers"] == ["GM-IV-F01", "GM-IV-F03"]
        and gm4.get("controlled_pilot_frontiers") == ["GM-IV-F01", "GM-IV-F03"],
        "F01 and F03 are the controlled pilot pair",
    )
    ok(
        "04_reference_frontiers",
        inv["reference_frontiers"] == ["GM-IV-F02", "GM-IV-F04"]
        and gm4.get("reference_frontiers") == ["GM-IV-F02", "GM-IV-F04"],
        "F02 and F04 remain references",
    )
    ok(
        "05_unfilled_f05_f08",
        inv["unfilled_frontier_slots"] == ["GM-IV-F05", "GM-IV-F06", "GM-IV-F07", "GM-IV-F08"]
        and gm4.get("unfilled_frontier_slots") == ["GM-IV-F05", "GM-IV-F06", "GM-IV-F07", "GM-IV-F08"],
        "only F05-F08 remain unfilled",
    )
    ok(
        "06_no_child_binding_or_authority_leakage",
        inv["f03_child_bound"] is False
        and inv["f04_child_bound"] is False
        and inv["pilot_frontier_labels_do_not_imply_children"] is True
        and ledger["authority_transfer"] is False
        and gm4["children"] == [],
        "pilot/reference frontier labels do not bind children or transfer authority",
    )
    ok(
        "07_gmv_held",
        inv["gm_v_state"] == "HELD"
        and gm5["state"] == "HELD"
        and gm5["children"] == [],
        "GM-V remains HELD",
    )

    rows = ledger["rows"]
    ok(
        "08_three_measured_rows",
        len(rows) == 3 and all(r["evidence_class"] == "MEASURED" for r in rows),
        "three measured Ring2 economics rows",
    )
    ok(
        "09_no_fabricated_crew_time",
        all(
            r["crew_time_seconds"] is None
            and r["crew_time_status"] == "NOT_INSTRUMENTED"
            for r in rows
        ),
        "crew time remains explicit telemetry gap",
    )
    ok(
        "10_no_slot_or_child_binding_from_economics",
        all(r["slot_bound"] is False and r["child_bound"] is False for r in rows),
        "economics rows cannot bind frontier slots or children",
    )
    ok(
        "11_no_authority_transfer",
        ledger["authority_transfer"] is False
        and all(r["authority_transfer"] is False for r in rows),
        "authority remains external to economics",
    )

    rates_ok = True
    for row in rows:
        expected = (
            row["accepted_evidence_units"] / row["execute_seconds"]
            if row["execute_seconds"]
            else 0.0
        )
        rates_ok = rates_ok and abs(expected - row["evidence_rate"]) < 1e-9
    ok(
        "12_evidence_rate_math",
        rates_ok,
        "evidence_rate = accepted_evidence_units / execute_seconds",
    )

    by_id = {r["row_id"]: r for r in rows}
    prov = by_id["GMIV_RING2_SCOUT_B_PROVENANCE_PASS"]
    full = by_id["GMIV_RING2_SCOUT_B_FULL_RUNTIME_PRUNED"]
    ratio = prov["evidence_rate"] / full["evidence_rate"]
    ok(
        "13_provenance_efficiency_signal",
        ratio > 40 and full["payload_execute_seconds"] == 62,
        f"provenance/full-runtime evidence-rate ratio={ratio:.6f}",
    )
    ok(
        "14_pruned_runtime_disposition",
        full["disposition"] == "PRUNE_FULL_RUNTIME_KEEP_PROVENANCE_REFERENCE",
        "redundant runtime remains pruned",
    )
    ok(
        "15_local_model_scope",
        scope["evidence_economics_models"] == "LOCAL_GMIV_RING2_ECONOMICS_ONLY"
        and "SEPARATE_MEASURED_CREW_PC3" in scope["global_model_context"],
        "local economics gate does not override separate global models",
    )
    ok(
        "16_pca_bt_fail_closed_locally",
        ledger["pca_gate"]["scope"] == "LOCAL_GMIV_RING2_EVIDENCE_ECONOMICS"
        and ledger["pca_gate"]["state"] == "DEFER"
        and ledger["bt_gate"]["scope"] == "LOCAL_GMIV_RING2_EVIDENCE_ECONOMICS"
        and ledger["bt_gate"]["state"] == "DEFER",
        "local economics PCA/BT remain fail-closed",
    )

    passed = sum(1 for c in checks if c["pass"])
    receipt = {
        "schema": "qps.gm_iv_evidence_economics_validation.v1",
        "status": "PASS" if passed == len(checks) else "FAIL",
        "passed": passed,
        "denominator": len(checks),
        "checks": checks,
        "fleet_invariant": "GM-IV PILOT_2_OF_8; controlled F01/F03; references F02/F04; children=0; F05-F08 unfilled; GM-V HELD",
        "model_scope": "LOCAL_GMIV_RING2_EVIDENCE_ECONOMICS",
        "authority_transfer": False,
    }
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
