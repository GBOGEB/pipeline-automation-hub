#!/usr/bin/env python3
import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTRACT = ROOT / "GM_IV_F07_F08_BOUNDED_PULSE_CONTRACT.json"
REGISTRY = ROOT / "GRAND_MISSION_REGISTRY.json"
EXPECTED_CANONICAL_STATE = "STAGED_ACTIVE_RECON_4_OF_8"


def git_head(path: Path) -> str:
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()


def count_surface(path: Path) -> dict:
    files = [p for p in path.rglob("*") if p.is_file() and ".git" not in p.parts]
    dirs = [p for p in path.rglob("*") if p.is_dir() and ".git" not in p.parts]
    return {"files": len(files), "directories": len(dirs), "entries": len(files) + len(dirs)}


def canonical_registry() -> tuple[dict, dict]:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    missions = {m["id"]: m for m in registry["grand_missions"]}
    if "GM-IV" not in missions or "GM-V" not in missions:
        raise SystemExit("FAIL_REQUIRED_GRAND_MISSION_MISSING")
    return missions["GM-IV"], missions["GM-V"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--f07", type=Path, required=True)
    ap.add_argument("--f08", type=Path, required=True)
    ap.add_argument("--source-sha", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    gm4_before, gm5_before = canonical_registry()
    state_before = gm4_before["state"]
    if state_before != EXPECTED_CANONICAL_STATE:
        raise SystemExit(f"FAIL_GM_IV_CANONICAL_STATE expected={EXPECTED_CANONICAL_STATE} actual={state_before}")
    if gm5_before["state"] != "HELD":
        raise SystemExit(f"FAIL_GM_V_NOT_HELD actual={gm5_before['state']}")
    if contract["canonical_state_must_remain"] != state_before:
        raise SystemExit("FAIL_GM_IV_CONTRACT_REGISTRY_STATE_MISMATCH")
    if contract["promotion_allowed_by_this_pulse"] is not False:
        raise SystemExit("FAIL_GM_IV_PULSE_PROMOTION_MUST_BE_FALSE")

    readiness = gm4_before.get("active8_readiness", {})
    if readiness.get("result") != "PASS" or readiness.get("decision") != "READY_FOR_SEPARATE_ACTIVE_8_PROMOTION_PR":
        raise SystemExit("FAIL_ACTIVE8_READINESS_NOT_PASS")
    if readiness.get("canonical_state_after_gate") != EXPECTED_CANONICAL_STATE:
        raise SystemExit("FAIL_ACTIVE8_READINESS_CANONICAL_STATE_DRIFT")

    frontiers = {f["slot"]: f for f in contract["frontiers"]}
    observed = {}
    for slot, path in (("GM-IV-F07", args.f07), ("GM-IV-F08", args.f08)):
        spec = frontiers[slot]
        head = git_head(path)
        surface = count_surface(path)
        if head != spec["target_sha"]:
            raise SystemExit(f"FAIL_{slot}_SHA expected={spec['target_sha']} actual={head}")
        if surface["entries"] <= 0:
            raise SystemExit(f"FAIL_{slot}_ZERO_SURFACE")
        observed[slot] = {
            "repository": spec["repository"],
            "expected_sha": spec["target_sha"],
            "observed_sha": head,
            "surface": surface,
            "probe_result": "PASS_NONZERO_EXACT_SHA_SURFACE",
            "return_path": spec["return_path"],
            "authority_transfer": False,
            "formal_credit_delta": 0,
        }

    gm4_after, gm5_after = canonical_registry()
    if gm4_after["state"] != state_before:
        raise SystemExit(f"FAIL_GM_IV_CANONICAL_STATE_CHANGED before={state_before} after={gm4_after['state']}")
    if gm5_after["state"] != "HELD":
        raise SystemExit("FAIL_GM_V_CHANGED_DURING_PULSE")

    receipt = {
        "schema": "qps.gm_iv_f07_f08_runtime_probe_receipt.v1",
        "mission_id": "GM-IV",
        "source_control_sha": args.source_sha,
        "canonical_registry_path": str(REGISTRY.relative_to(ROOT.parent.parent)),
        "canonical_state_before": state_before,
        "canonical_state_after": gm4_after["state"],
        "active8_readiness_result": readiness["result"],
        "active8_readiness_decision": readiness["decision"],
        "promotion_requested": False,
        "promotion_allowed": False,
        "children_bound": False,
        "authority_transfer": False,
        "formal_credit_delta": 0,
        "gm_v_state_before": gm5_before["state"],
        "gm_v_state_after": gm5_after["state"],
        "frontiers": observed,
        "result": "PASS_F07_F08_BOUNDED_RUNTIME_PROBE",
        "next_action": "return_final_two_frontier_receipts_to_Governor_then_use_separate_ACTIVE8_promotion_transaction",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(receipt["result"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
