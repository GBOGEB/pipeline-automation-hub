#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def mission(doc, mission_id):
    return next(m for m in doc["grand_missions"] if m["id"] == mission_id)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--contract", required=True)
    p.add_argument("--pre-registry", required=True)
    p.add_argument("--pre-sha", required=True)
    p.add_argument("--post-registry", required=True)
    p.add_argument("--f01", required=True)
    p.add_argument("--f03", required=True)
    p.add_argument("--fleet", required=True)
    p.add_argument("--capacity", required=True)
    p.add_argument("--source-sha", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()

    c = load(a.contract)
    pre = load(a.pre_registry)
    post = load(a.post_registry)
    f01 = load(a.f01)
    f03 = load(a.f03)
    fleet = load(a.fleet)
    capacity = load(a.capacity)
    pre_iv = mission(pre, "GM-IV")
    post_iv = mission(post, "GM-IV")
    post_iii = mission(post, "GM-III")
    post_v = mission(post, "GM-V")
    pilots = c["controlled_pilots"]

    checks = {
        "01_contract_pre_master_exact": c["pre_promotion_master_sha"] == a.pre_sha,
        "02_pre_state_recon_2_of_8": pre_iv.get("state") == c["transition"]["from_state"] and pre_iv.get("activation_stage") == c["transition"]["from_stage"] and pre_iv.get("children") == [],
        "03_post_state_pilot_2_of_8": post_iv.get("state") == c["transition"]["to_state"] and post_iv.get("activation_stage") == c["transition"]["to_stage"],
        "04_post_two_controlled_pilots": post_iv.get("controlled_pilot_frontiers") == ["GM-IV-F01", "GM-IV-F03"] and post_iv.get("candidate_frontiers") == ["GM-IV-F01", "GM-IV-F03"],
        "05_reference_history_preserved": post_iv.get("reference_frontiers") == ["GM-IV-F02", "GM-IV-F04"],
        "06_only_four_slots_unfilled": post_iv.get("unfilled_frontier_slots") == ["GM-IV-F05", "GM-IV-F06", "GM-IV-F07", "GM-IV-F08"],
        "07_no_children_or_authority_transfer": post_iv.get("children") == [] and post.get("authority_transfer") is False and c.get("authority_transfer") is False and c.get("children_bound") is False,
        "08_f01_exact_positive_runtime": f01.get("target_sha") == pilots[0]["target_sha"] and f01.get("positive_exit_code") == 0 and f01.get("positive_pass_marker") is True and f01.get("positive_validated_surface_count", 0) >= 4,
        "09_f01_negative_authority_rejected": f01.get("negative_exit_code", 0) != 0 and f01.get("negative_rejection_marker") is True and f01.get("target_dirty_file_count") == 0,
        "10_f03_exact_positive_runtime": f03.get("target_sha") == pilots[1]["target_sha"] and f03.get("run1_code_cells", 0) > 0 and f03.get("run2_code_cells", 0) > 0 and f03.get("total_error_count") == 0,
        "11_f03_repeat_and_boundary": bool(f03.get("run1_digest")) and f03.get("run1_digest") == f03.get("run2_digest") and f03.get("positive_boundary_pass") is True and f03.get("negative_authority_rejected") is True and f03.get("target_dirty_count") == 0,
        "12_independent_repo_and_capability": pilots[0]["repository"] != pilots[1]["repository"] and pilots[0]["capability"] != pilots[1]["capability"],
        "13_prior_control_receipts_bound": all(x.get("master_run_id", 0) > 0 and x.get("master_artifact_id", 0) > 0 and str(x.get("master_artifact_digest", "")).startswith("sha256:") for x in pilots),
        "14_gm_iii_remains_control": post_iii.get("state") == "RECON_CONTROL",
        "15_gm_v_remains_held": post_v.get("state") == "HELD" and post_v.get("children") == [],
        "16_legacy_fleet_validator_pass": fleet.get("validation_check_count") == 16 and all(x.get("result") == "PASS" for x in fleet.get("validation_checks", [])),
        "17_capacity_validator_accepts_pilot_state": capacity.get("structural_gate") == "PASS" and capacity.get("activation_decision") == "PASS_STAGED_ACTIVE_PILOT_2_OF_8_CONTROL_SHAPE",
        "18_no_synthetic_pca_bt_credit": str(capacity.get("pca_gate", "")).startswith("DEFER_") and str(capacity.get("bt_gate", "")).startswith("DEFER_"),
        "19_return_triggers_bound": all(bool(x.get("return_trigger")) for x in pilots),
        "20_next_stage_not_auto_released": "does not authorize RECON_4_OF_8" in c.get("next_stage_boundary", ""),
    }
    result = "PASS" if all(checks.values()) else "FAIL"
    receipt = {
        "schema": "qps.gm_iv_pilot2_governor_receipt.v1",
        "wave": c["wave"],
        "source_sha": a.source_sha,
        "pre_promotion_master_sha": a.pre_sha,
        "result": result,
        "checks": checks,
        "governor_decision": "PROMOTE_PILOT_2_OF_8" if result == "PASS" else "WITHHOLD_PILOT_2_OF_8",
        "mission_state": post_iv.get("state"),
        "activation_stage": post_iv.get("activation_stage"),
        "controlled_pilots": post_iv.get("controlled_pilot_frontiers", []),
        "reference_frontiers": post_iv.get("reference_frontiers", []),
        "children_bound": False,
        "authority_transfer": False,
        "gm_v_state": post_v.get("state"),
        "next_stage": "RECON_4_OF_8_WITHHELD_SEPARATE_GATE",
        "input_digests": {
            "contract": digest(a.contract),
            "pre_registry": digest(a.pre_registry),
            "post_registry": digest(a.post_registry),
            "f01": digest(a.f01),
            "f03": digest(a.f03),
            "fleet": digest(a.fleet),
            "capacity": digest(a.capacity),
        },
    }
    Path(a.out).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    if result != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
