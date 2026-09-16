#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REGISTRY = ROOT / "GRAND_MISSION_REGISTRY.json"
ACTIVE8 = ROOT / "GM_IV_ACTIVE8_GOVERNOR_CONTRACT.json"
CONTRACT = ROOT / "GM_IV_POST_ACTIVE8_REPEAT_CONTROL_CONTRACT.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL: {message}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-sha", required=True)
    ap.add_argument("--fleet-receipt", type=Path, required=True)
    ap.add_argument("--capacity-receipt", type=Path, required=True)
    ap.add_argument("--probe-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    registry = load(REGISTRY)
    active8 = load(ACTIVE8)
    contract = load(CONTRACT)
    fleet = load(args.fleet_receipt)
    capacity = load(args.capacity_receipt)
    gm = {m["id"]: m for m in registry["grand_missions"]}
    gm4, gm3, gm5 = gm["GM-IV"], gm["GM-III"], gm["GM-V"]

    checks: list[dict] = []

    def check(name: str, condition: bool, detail) -> None:
        require(condition, f"{name}: {detail}")
        checks.append({"check": name, "result": "PASS", "detail": detail})

    check("canonical_active8_state", gm4.get("state") == contract["required_state"], gm4.get("state"))
    check("canonical_active8_stage", gm4.get("activation_stage") == contract["required_activation_stage"], gm4.get("activation_stage"))
    check("gm_iv_zero_children", gm4.get("children") == [], gm4.get("children"))
    check("gm_iii_control_preserved", gm3.get("state") == "RECON_CONTROL", gm3.get("state"))
    check("gm_v_hard_hold", gm5.get("state") == "HELD" and gm5.get("children") == [], gm5.get("state"))
    check("fleet_authority_zero", registry.get("authority_transfer") is False and fleet.get("authority_transfer") is False, False)
    check("fleet_validator_repeat_pass", all(x.get("result") == "PASS" for x in fleet.get("validation_checks", [])), fleet.get("validation_check_count"))
    check("capacity_structural_gate", capacity.get("structural_gate") == "PASS", capacity.get("structural_gate"))
    check("capacity_current_active8", capacity.get("gm_iv_state") == "ACTIVE_8_OF_8", capacity.get("gm_iv_state"))
    check("capacity_gm_v_hold", capacity.get("gm_v_state") == "HELD", capacity.get("gm_v_state"))

    expected = active8["frontier_evidence"]
    observed = {}
    for i in range(1, 9):
        fid = f"GM-IV-F{i:02d}"
        spec = expected[fid]
        d = args.probe_root / fid
        observed_sha = (d / "HEAD_SHA").read_text(encoding="utf-8").strip()
        entry_count = int((d / "ENTRY_COUNT").read_text(encoding="utf-8").strip())
        check(f"{fid}_exact_sha", observed_sha == spec["target_sha"], observed_sha)
        check(f"{fid}_surface_gt0", entry_count > 0, entry_count)
        observed[fid] = {
            "repository": spec["repository"],
            "expected_sha": spec["target_sha"],
            "observed_sha": observed_sha,
            "entry_count": entry_count,
            "result": "PASS_EXACT_SHA_NONZERO_SURFACE",
        }

    receipt = {
        "schema": "qps.gm_iv_post_active8_repeat_control_receipt.v1",
        "mission_id": "GM-IV",
        "source_sha": args.source_sha,
        "promotion_merge_sha": contract["promotion_merge_sha"],
        "canonical_state": gm4["state"],
        "repeat_control_result": "PASS_POST_ACTIVE8_REPEAT_CONTROL",
        "repeat_control_check_count": len(checks),
        "repeat_control_checks": checks,
        "frontier_runtime_probe_coverage": {"passed": 8, "required": 8, "ratio": 1.0, "frontiers": observed},
        "structural_capacity_result": "PASS",
        "measured_capacity_result": "DEFER_RUNTIME_CAPABILITY_MEASUREMENT_REQUIRED",
        "measured_capacity_reason": "registered_or_structural_capability_coverage_is_not_runtime_proven_or_operationally_available_capacity",
        "gm_v_state": "HELD",
        "gm_v_launch_authorized": False,
        "children_bound": False,
        "authority_transfer": False,
        "formal_credit_delta": 0,
        "hard_gate_compensation_allowed": False,
        "next_action": contract["next_after_success"],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("PASS_GM_IV_POST_ACTIVE8_REPEAT_CONTROL")
    print("DEFER_GM_V_MEASURED_CAPACITY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
