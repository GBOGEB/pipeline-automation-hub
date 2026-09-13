#!/usr/bin/env python3
"""Validate GM-IV evidence economics without promoting reconnaissance into children."""

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
    gm = {row["id"]: row for row in registry["grand_missions"]}
    gm4 = gm["GM-IV"]
    gm5 = gm["GM-V"]

    ok("01_recon_2_of_8", inv["reconnaissance_observed"] == 2 and inv["reconnaissance_denominator"] == 8, "GM-IV recon must remain 2/8")
    ok("02_zero_children", inv["canonical_children_bound"] == 0 and gm4["children"] == [], "GM-IV canonical children remain empty")
    ok("03_no_f03_f04", inv["f03_bound"] is False and inv["f04_bound"] is False, "F03/F04 remain unbound")
    ok("04_gmv_held", inv["gm_v_state"] == "HELD" and gm5["state"] == "HELD" and gm5["children"] == [], "GM-V remains HELD")
    ok("05_registry_recon_state", gm4["state"] == "STAGED_ACTIVE_RECON_2_OF_8", "registry remains staged recon")

    rows = ledger["rows"]
    ok("06_three_measured_rows", len(rows) == 3 and all(r["evidence_class"] == "MEASURED" for r in rows), "three measured Ring2 economics rows")
    ok("07_no_fabricated_crew_time", all(r["crew_time_seconds"] is None and r["crew_time_status"] == "NOT_INSTRUMENTED" for r in rows), "crew time remains explicit telemetry gap")
    ok("08_no_slot_or_child_binding", all(r["slot_bound"] is False and r["child_bound"] is False for r in rows), "economics rows cannot bind frontier slots or children")
    ok("09_no_authority_transfer", ledger["authority_transfer"] is False and all(r["authority_transfer"] is False for r in rows), "authority remains external to economics")

    rates_ok = True
    for row in rows:
        expected = row["accepted_evidence_units"] / row["execute_seconds"] if row["execute_seconds"] else 0.0
        rates_ok = rates_ok and abs(expected - row["evidence_rate"]) < 1e-9
    ok("10_evidence_rate_math", rates_ok, "evidence_rate = accepted_evidence_units / execute_seconds")

    by_id = {r["row_id"]: r for r in rows}
    prov = by_id["GMIV_RING2_SCOUT_B_PROVENANCE_PASS"]
    full = by_id["GMIV_RING2_SCOUT_B_FULL_RUNTIME_PRUNED"]
    ratio = prov["evidence_rate"] / full["evidence_rate"]
    ok("11_provenance_efficiency_signal", ratio > 40 and full["payload_execute_seconds"] == 62, f"provenance/full-runtime evidence-rate ratio={ratio:.6f}")
    ok("12_pruned_runtime_disposition", full["disposition"] == "PRUNE_FULL_RUNTIME_KEEP_PROVENANCE_REFERENCE", "redundant runtime remains pruned")
    ok("13_pca_fail_closed", ledger["pca_gate"]["state"] == "DEFER", "PCA not promoted from one-mission three-row sample")
    ok("14_bt_fail_closed", ledger["bt_gate"]["state"] == "DEFER", "BT not promoted from one observed comparison")

    passed = sum(1 for c in checks if c["pass"])
    receipt = {
        "schema": "qps.gm_iv_evidence_economics_validation.v1",
        "status": "PASS" if passed == len(checks) else "FAIL",
        "passed": passed,
        "denominator": len(checks),
        "checks": checks,
        "fleet_invariant": "GM-IV recon=2/8; children=0/8; F03/F04 unbound; GM-V HELD",
        "authority_transfer": False,
    }
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
