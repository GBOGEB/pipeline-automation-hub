#!/usr/bin/env python3
import argparse
import json
import os
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CREW = ROOT.parent / "qps-triage-ultra" / "crew" / "CREW_REGISTRY_v1.json"
SNAPSHOT = ROOT.parent / "qps-triage-ultra" / "crew" / "CREW_SNAPSHOT_2026-09-13.json"
REGISTRY = ROOT / "GRAND_MISSION_REGISTRY.json"
CONTRACT = ROOT / "GM_FLEET_03_CAPACITY_CONTRACT.json"
CANDIDATES = ROOT / "GM_IV_FRONTIER_CANDIDATES.json"


def load(path):
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    crew = load(CREW)
    snap = load(SNAPSHOT)
    gm = load(REGISTRY)
    contract = load(CONTRACT)
    candidates = load(CANDIDATES)

    by_id = {m["id"]: m for m in gm["grand_missions"]}
    records = crew.get("crew", [])
    maturity = Counter(str(r.get("maturity", "UNKNOWN")) for r in records)
    loads = Counter(str(r.get("current_load", "UNKNOWN")) for r in records)

    capability_rows = []
    all_capabilities_covered = True
    for capability, host_ids in contract["required_activation_capabilities"].items():
        present = [r for r in records if r.get("crew_id") in host_ids]
        observed = [r for r in present if str(r.get("maturity", "")).startswith("OBSERVED")]
        covered = bool(observed)
        all_capabilities_covered = all_capabilities_covered and covered
        capability_rows.append({
            "capability": capability,
            "declared_hosts": host_ids,
            "registered_hosts": [r.get("crew_id") for r in present],
            "observed_hosts": [r.get("crew_id") for r in observed],
            "covered": covered,
        })

    live_obs = snap.get("live_observations", [])
    zero_step_blocks = [
        o for o in live_obs
        if int(o.get("steps_executed", 0) or 0) == 0 and o.get("state") == "BLOCKED"
    ]

    gm4 = by_id["GM-IV"]
    gm_iv_state = gm4["state"]
    gm_iv_valid_state = gm_iv_state in [
        "HELD",
        "STAGED_ACTIVE_RECON_2_OF_8",
        "STAGED_ACTIVE_PILOT_2_OF_8",
        "STAGED_ACTIVE_RECON_4_OF_8",
        "ACTIVE_8_OF_8",
    ]
    staged_shape_ok = True
    if gm_iv_state == "STAGED_ACTIVE_RECON_2_OF_8":
        staged_shape_ok = (
            gm4.get("children") == []
            and gm4.get("activation_stage") == "RECON_2_OF_8"
            and gm4.get("candidate_frontiers") == ["GM-IV-F01", "GM-IV-F02"]
        )
    elif gm_iv_state == "STAGED_ACTIVE_PILOT_2_OF_8":
        staged_shape_ok = (
            gm4.get("children") == []
            and gm4.get("activation_stage") == "PILOT_2_OF_8"
            and gm4.get("controlled_pilot_frontiers") == ["GM-IV-F01", "GM-IV-F03"]
            and gm4.get("reference_frontiers") == ["GM-IV-F02", "GM-IV-F04"]
            and gm4.get("unfilled_frontier_slots") == [
                "GM-IV-F05", "GM-IV-F06", "GM-IV-F07", "GM-IV-F08"
            ]
        )

    checks = [
        ("01_gm_iii_control", by_id["GM-III"]["state"] == "RECON_CONTROL", by_id["GM-III"]["state"]),
        ("02_gm_iv_held_or_controlled_staged", gm_iv_valid_state, gm_iv_state),
        ("03_gm_v_hard_held", by_id["GM-V"]["state"] == "HELD" and by_id["GM-V"].get("children") == [], by_id["GM-V"]["state"]),
        ("04_initial_candidate_ring_frozen", len(candidates.get("candidate_ring", [])) == 2, len(candidates.get("candidate_ring", []))),
        ("05_initial_unfilled_slots_frozen", len(candidates.get("unfilled_slots", [])) == 6, len(candidates.get("unfilled_slots", []))),
        ("06_required_capability_host_coverage", all_capabilities_covered, capability_rows),
        ("07_no_authority_transfer", contract.get("authority_transfer") is False and candidates.get("authority_transfer") is False, False),
        ("08_registered_capacity_not_claimed_runtime", contract["capacity_classes"]["REGISTERED"].startswith("counted_from"), len(records)),
        ("09_snapshot_not_promoted_to_measured", snap.get("snapshot_class") == "MIXED_OBSERVED_AND_EXPERT_SEEDED", snap.get("snapshot_class")),
        ("10_candidate_recon_not_child_binding", "CANDIDATE_RECON_IS_NOT_A_GM_IV_CHILD_BINDING" in candidates.get("invariants", []), True),
        ("11_current_stage_shape", staged_shape_ok, gm_iv_state),
    ]

    failed = [c for c in checks if not c[1]]
    structural_release = not failed
    if not structural_release:
        decision = "HELD_STRUCTURAL_GATE_RED"
    elif gm_iv_state == "HELD":
        decision = "READY_FOR_RECON_2_OF_8_RUNTIME_PROOF"
    elif gm_iv_state == "STAGED_ACTIVE_RECON_2_OF_8":
        decision = "PASS_STAGED_ACTIVE_RECON_2_OF_8_CONTROL_SHAPE"
    elif gm_iv_state == "STAGED_ACTIVE_PILOT_2_OF_8":
        decision = "PASS_STAGED_ACTIVE_PILOT_2_OF_8_CAPACITY_SHAPE"
    else:
        decision = "PASS_FORWARD_STAGE_CAPACITY_SHAPE"

    receipt = {
        "schema": "qps.gm_fleet_03_capacity_receipt.v1",
        "wave": "GM-FLEET-03",
        "repo": os.getenv("GITHUB_REPOSITORY", "LOCAL"),
        "source_sha": os.getenv("SOURCE_SHA", os.getenv("GITHUB_SHA", "UNKNOWN")),
        "run_id": os.getenv("GITHUB_RUN_ID", "LOCAL"),
        "ref": os.getenv("GITHUB_REF", "LOCAL"),
        "authority_transfer": False,
        "registered_crew_records": len(records),
        "maturity_counts": dict(sorted(maturity.items())),
        "load_counts": dict(sorted(loads.items())),
        "capability_coverage": capability_rows,
        "activation_baseline_candidate_frontiers": candidates.get("candidate_ring", []),
        "activation_baseline_unfilled_slots": candidates.get("unfilled_slots", []),
        "current_registry_frontiers": gm4.get("candidate_frontiers", []),
        "current_registry_unfilled_slots": gm4.get("unfilled_frontier_slots", []),
        "retained_zero_step_observations": len(zero_step_blocks),
        "gm_iv_state": gm_iv_state,
        "structural_checks": [
            {"check": n, "result": "PASS" if passed else "FAIL", "detail": detail}
            for n, passed, detail in checks
        ],
        "structural_gate": "PASS" if structural_release else "FAIL",
        "runtime_gate": "PASS_GT0_ONLY_WHEN_EXECUTED_IN_WORKFLOW",
        "activation_decision": decision,
        "gm_v_state": "HELD",
        "pca_gate": "DEFER_NO_COMPARABLE_MEASURED_GM_I_TO_V_ROWS",
        "bt_gate": "DEFER_NO_CONNECTED_OBSERVED_GM_PAIRWISE_GRAPH",
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "result": "PASS_GM_FLEET_03_STRUCTURE" if structural_release else "FAIL_GM_FLEET_03_STRUCTURE",
        "registered_crew_records": len(records),
        "baseline_candidate_frontiers": len(candidates.get("candidate_ring", [])),
        "current_registry_frontiers": len(gm4.get("candidate_frontiers", [])),
        "gm_iv_state": gm_iv_state,
        "activation_decision": decision,
        "source_sha": receipt["source_sha"],
    }, sort_keys=True))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
