#!/usr/bin/env python3
import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTRACT = ROOT / "GM_IV_F05_F06_BOUNDED_PULSE_CONTRACT.json"


def git_head(path: Path) -> str:
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()


def count_surface(path: Path) -> dict:
    files = [p for p in path.rglob("*") if p.is_file() and ".git" not in p.parts]
    dirs = [p for p in path.rglob("*") if p.is_dir() and ".git" not in p.parts]
    return {"files": len(files), "directories": len(dirs), "entries": len(files) + len(dirs)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--f05", type=Path, required=True)
    ap.add_argument("--f06", type=Path, required=True)
    ap.add_argument("--source-sha", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    frontiers = {f["slot"]: f for f in contract["frontiers"]}
    observed = {}
    for slot, path in (("GM-IV-F05", args.f05), ("GM-IV-F06", args.f06)):
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

    receipt = {
        "schema": "qps.gm_iv_f05_f06_runtime_probe_receipt.v1",
        "mission_id": "GM-IV",
        "source_control_sha": args.source_sha,
        "canonical_state_before": "STAGED_ACTIVE_RECON_4_OF_8",
        "canonical_state_after": "STAGED_ACTIVE_RECON_4_OF_8",
        "promotion_requested": False,
        "promotion_allowed": False,
        "children_bound": False,
        "authority_transfer": False,
        "formal_credit_delta": 0,
        "frontiers": observed,
        "result": "PASS_F05_F06_BOUNDED_RUNTIME_PROBE",
        "next_action": "return_two_frontier_receipts_to_Governor_for_disposition_without_promoting_canonical_GM_IV",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(receipt["result"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
