#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REGISTRY = ROOT / "GRAND_MISSION_REGISTRY.json"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--contract", required=True)
    p.add_argument("--runtime", required=True)
    p.add_argument("--boundary", required=True)
    p.add_argument("--source-sha", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()

    contract = load(a.contract)
    runtime = load(a.runtime)
    boundary = load(a.boundary)
    registry = load(REGISTRY)
    gm = {m["id"]: m for m in registry["grand_missions"]}
    gm4 = gm["GM-IV"]
    gm5 = gm["GM-V"]
    target = contract["target"]
    current_state = gm4.get("state")
    allowed_forward_states = {
        "STAGED_ACTIVE_RECON_2_OF_8",
        "STAGED_ACTIVE_PILOT_2_OF_8",
        "STAGED_ACTIVE_RECON_4_OF_8",
        "ACTIVE_8_OF_8",
    }

    checks = {
        "01_exact_target_sha": runtime.get("target_sha") == target["source_sha"],
        "02_positive_boundary_pass": boundary.get("positive_exit_code") == 0,
        "03_positive_boundary_markers": boundary.get("positive_marker_count", 0) >= 5,
        "04_gt0_cells_run1": runtime.get("run1_code_cells", 0) > 0,
        "05_gt0_cells_run2": runtime.get("run2_code_cells", 0) > 0,
        "06_zero_errors": runtime.get("total_error_count") == 0,
        "07_repeat_digest_equal": bool(runtime.get("run1_digest")) and runtime.get("run1_digest") == runtime.get("run2_digest"),
        "08_negative_authority_rejected": boundary.get("negative_exit_code", 0) != 0 and boundary.get("negative_rejection_observed") is True,
        "09_target_unmodified": runtime.get("target_dirty_count") == 0 and boundary.get("target_repository_modified") is False,
        "10_no_authority_transfer": contract.get("authority_transfer") is False and contract.get("children_bound") is False,
        "11_historical_stage_preserved_current_stage_not_regressed": contract.get("mission_state_must_remain") == "STAGED_ACTIVE_RECON_2_OF_8" and current_state in allowed_forward_states and gm4.get("children") == [],
        "12_f01_independent_control_exists": contract.get("existing_controlled_pilot") == "GM-IV-F01",
        "13_f04_reference": contract.get("f04_state") == "REFERENCE",
        "14_gm_v_held": runtime.get("gm_v_state") == "HELD" and gm5.get("state") == "HELD" and gm5.get("children") == [],
    }
    result = "PASS" if all(checks.values()) else "FAIL"
    receipt = {
        "schema": "qps.gm_iv_f03_pilot_receipt.v1",
        "wave": contract["wave"],
        "source_sha": a.source_sha,
        "target_sha": target["source_sha"],
        "result": result,
        "checks": checks,
        "frontier_disposition": "PILOT_CONTROL_READY" if result == "PASS" else "PILOT_NOT_READY",
        "controlled_pilot_pair_if_master_repeats": ["GM-IV-F01", "GM-IV-F03"],
        "mission_promotion": "WITHHELD_FROM_F03_RECURRENCE__CURRENT_STAGE_MAY_HAVE_BEEN_PROMOTED_SEPARATELY",
        "historical_evidence_stage": "STAGED_ACTIVE_RECON_2_OF_8",
        "mission_state": current_state,
        "children_bound": False,
        "authority_transfer": False,
        "gm_v_state": gm5.get("state"),
        "input_digests": {
            "contract": sha256_file(a.contract),
            "runtime": sha256_file(a.runtime),
            "boundary": sha256_file(a.boundary),
        },
    }
    Path(a.out).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    if result != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
