#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REGISTRY = ROOT / "GRAND_MISSION_REGISTRY.json"
CONTRACT = ROOT / "GM_IV_F01_PILOT_CONTRACT.json"
REX = ROOT / "GM_IV_RING1_REX.json"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runtime-receipt", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    registry = load(REGISTRY)
    contract = load(CONTRACT)
    rex = load(REX)
    runtime = load(args.runtime_receipt)
    gm = {m["id"]: m for m in registry["grand_missions"]}
    target = contract["target"]
    current_state = gm["GM-IV"].get("state")
    allowed_forward_states = {
        "STAGED_ACTIVE_RECON_2_OF_8",
        "STAGED_ACTIVE_PILOT_2_OF_8",
        "STAGED_ACTIVE_RECON_4_OF_8",
        "ACTIVE_8_OF_8",
    }

    checks = [
        ("01_exact_target_sha", runtime.get("target_sha") == target["source_sha"], runtime.get("target_sha")),
        ("02_positive_validator_pass", runtime.get("positive_exit_code") == 0 and runtime.get("positive_pass_marker") is True, runtime.get("positive_exit_code")),
        ("03_positive_surfaces", runtime.get("positive_validated_surface_count", 0) >= 4, runtime.get("positive_validated_surface_count")),
        ("04_negative_authority_probe_rejected", runtime.get("negative_exit_code", 0) != 0 and runtime.get("negative_rejection_marker") is True, runtime.get("negative_exit_code")),
        ("05_target_checkout_clean", runtime.get("target_dirty_file_count") == 0, runtime.get("target_dirty_file_count")),
        ("06_output_digest_bound", isinstance(runtime.get("positive_output_sha256"), str) and len(runtime["positive_output_sha256"]) == 64, runtime.get("positive_output_sha256")),
        ("07_historical_stage_preserved_current_stage_not_regressed", contract["mission_state_must_remain"] == "STAGED_ACTIVE_RECON_2_OF_8" and current_state in allowed_forward_states and gm["GM-IV"].get("children") == [], current_state),
        ("08_gm_v_held", gm["GM-V"].get("state") == "HELD" and gm["GM-V"].get("children") == [], gm["GM-V"].get("state")),
        ("09_f02_reference_only", contract.get("f02_state") == "REFERENCE", contract.get("f02_state")),
        ("10_no_authority_or_child_transfer", contract.get("authority_transfer") is False and contract.get("children_bound") is False, False),
        ("11_ring1_rex_assimilated", any(e.get("rex_id") == "REX-GMF-03-R1-001" for e in rex.get("events", [])), len(rex.get("events", []))),
    ]
    failed = [row for row in checks if not row[1]]

    receipt = {
        "schema": "qps.gm_iv_f01_pilot_receipt.v1",
        "wave": "GM-FLEET-03-F01-PILOT",
        "repo": os.getenv("GITHUB_REPOSITORY", "LOCAL"),
        "source_sha": os.getenv("SOURCE_SHA", os.getenv("GITHUB_SHA", "UNKNOWN")),
        "run_id": os.getenv("GITHUB_RUN_ID", "LOCAL"),
        "frontier": "GM-IV-F01",
        "target_repository": target["repository"],
        "target_sha": runtime.get("target_sha"),
        "authority_transfer": False,
        "children_bound": False,
        "historical_evidence_stage": "STAGED_ACTIVE_RECON_2_OF_8",
        "gm_iv_state": current_state,
        "gm_v_state": gm["GM-V"].get("state"),
        "checks": [{"check": n, "result": "PASS" if ok else "FAIL", "detail": detail} for n, ok, detail in checks],
        "result": "PASS" if not failed else "FAIL",
        "frontier_disposition": "PILOT_CONTROL_READY" if not failed else "PILOT_WITHHELD",
        "mission_promotion": "WITHHELD_FROM_F01_RECURRENCE__CURRENT_STAGE_MAY_HAVE_BEEN_PROMOTED_SEPARATELY",
        "next_frontier_action": "CONTROL_RECURRENCE_ONLY" if not failed else "ROUTE_FIRST_RED",
        "runtime": runtime,
    }
    Path(args.out).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "result": receipt["result"],
        "frontier_disposition": receipt["frontier_disposition"],
        "mission_promotion": receipt["mission_promotion"],
        "historical_evidence_stage": receipt["historical_evidence_stage"],
        "current_mission_state": receipt["gm_iv_state"],
        "source_sha": receipt["source_sha"],
        "target_sha": receipt["target_sha"],
    }, sort_keys=True))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
