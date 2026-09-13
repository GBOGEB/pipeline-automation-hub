#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REGISTRY = ROOT / "GRAND_MISSION_REGISTRY.json"


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--contract", required=True)
    p.add_argument("--f03", required=True)
    p.add_argument("--f04", required=True)
    p.add_argument("--source-sha", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()

    contract = load(a.contract)
    f03 = load(a.f03)
    f04 = load(a.f04)
    registry = load(REGISTRY)
    gm = {m["id"]: m for m in registry["grand_missions"]}
    gm4 = gm["GM-IV"]
    gm5 = gm["GM-V"]
    current_state = gm4.get("state")
    allowed_forward_states = {
        "STAGED_ACTIVE_RECON_2_OF_8",
        "STAGED_ACTIVE_PILOT_2_OF_8",
        "STAGED_ACTIVE_RECON_4_OF_8",
        "ACTIVE_8_OF_8",
    }

    checks = {}
    checks["01_contract_mission_bounded"] = (
        contract["mission_id"] == "GM-IV"
        and contract["mission_state_required"] == "STAGED_ACTIVE_RECON_2_OF_8"
        and current_state in allowed_forward_states
        and gm4.get("children") == []
        and contract["authority_transfer"] is False
        and contract["children_bound"] is False
    )
    checks["02_f03_exact_sha"] = f03.get("target_sha") == contract["frontiers"]["GM-IV-F03"]["target_sha"]
    checks["03_f03_gt0_cells"] = f03.get("executed_code_cells", 0) > 0
    checks["04_f03_no_errors"] = f03.get("error_count") == 0
    checks["05_f03_repeat_digest"] = (
        bool(f03.get("run1_digest")) and f03.get("run1_digest") == f03.get("run2_digest")
    )
    checks["06_f03_mesh_boundary"] = (
        f03.get("mesh_role") == "REPRODUCIBLE_NOTEBOOK_RUNTIME_PRODUCER"
        and f03.get("must_not_override_child_authority") is True
    )
    checks["07_f03_clean_source"] = f03.get("source_dirty_count") == 0

    checks["08_f04_exact_sha"] = f04.get("target_sha") == contract["frontiers"]["GM-IV-F04"]["target_sha"]
    checks["09_f04_real_test_attempt"] = f04.get("test_attempted") is True and isinstance(f04.get("test_exit_code"), int)
    checks["10_f04_reference_identity"] = f04.get("reference_parser_identity") is True
    checks["11_f04_no_qps_authority"] = f04.get("qps_authority_claim_detected") is False
    checks["12_f04_clean_source"] = f04.get("source_dirty_count") == 0
    checks["13_gm_v_held"] = (
        "GM_V_REMAINS_HELD" in contract["promotion_invariants"]
        and gm5.get("state") == "HELD"
        and gm5.get("children") == []
    )

    f03_ready = all(checks[k] for k in [
        "02_f03_exact_sha", "03_f03_gt0_cells", "04_f03_no_errors",
        "05_f03_repeat_digest", "06_f03_mesh_boundary", "07_f03_clean_source"
    ])
    f04_reference = all(checks[k] for k in [
        "08_f04_exact_sha", "09_f04_real_test_attempt", "10_f04_reference_identity",
        "11_f04_no_qps_authority", "12_f04_clean_source"
    ])

    result = "PASS" if all(checks.values()) else "FAIL"
    receipt = {
        "schema": "qps.gm_iv_ring2_recon_receipt.v1",
        "wave": contract["wave"],
        "source_sha": a.source_sha,
        "result": result,
        "checks": checks,
        "dispositions": {
            "GM-IV-F03": {
                "repository": contract["frontiers"]["GM-IV-F03"]["repository"],
                "disposition": "PILOT_READY" if f03_ready else "DEFER_RUNTIME",
                "reason": "repeated exact-SHA >0-cell deterministic runtime proof" if f03_ready else "runtime proof incomplete"
            },
            "GM-IV-F04": {
                "repository": contract["frontiers"]["GM-IV-F04"]["repository"],
                "disposition": "REFERENCE" if f04_reference else "DEFER_RUNTIME",
                "reason": "upstream reference parser with real bounded test attempt and no QPS authority claim" if f04_reference else "reference boundary incomplete",
                "test_exit_code": f04.get("test_exit_code")
            }
        },
        "pilot_gate": "SECOND_PILOT_CANDIDATE_READY_FOR_BOUNDED_CONTROL" if f03_ready else "SECOND_PILOT_NOT_READY",
        "mission_promotion": "WITHHELD_FROM_RING2_RECURRENCE__CURRENT_STAGE_MAY_HAVE_BEEN_PROMOTED_SEPARATELY",
        "historical_evidence_stage": "STAGED_ACTIVE_RECON_2_OF_8",
        "mission_state": current_state,
        "children_bound": False,
        "authority_transfer": False,
        "gm_v_state": gm5.get("state"),
        "input_digests": {
            "contract": sha256_file(a.contract),
            "f03": sha256_file(a.f03),
            "f04": sha256_file(a.f04)
        }
    }
    Path(a.out).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    if result != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
