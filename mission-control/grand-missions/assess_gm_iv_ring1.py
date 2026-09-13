#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REGISTRY = ROOT / "GRAND_MISSION_REGISTRY.json"
RING = ROOT / "GM_IV_RING1_RECON.json"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--f01-receipt", required=True)
    ap.add_argument("--f02-action", required=True)
    ap.add_argument("--f02-readme", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    registry = load(REGISTRY)
    ring = load(RING)
    f01 = load(args.f01_receipt)
    action_text = Path(args.f02_action).read_text(encoding="utf-8")
    readme_text = Path(args.f02_readme).read_text(encoding="utf-8")
    gm = {m["id"]: m for m in registry["grand_missions"]}
    targets = {f["slot"]: f for f in ring["frontiers"]}

    f01_sha = targets["GM-IV-F01"]["source_sha"]
    f02_sha = targets["GM-IV-F02"]["source_sha"]

    f01_pass = (
        f01.get("repo", {}).get("sha") == f01_sha
        and int(f01.get("census", {}).get("file_count", 0)) > 0
        and int(f01.get("repo", {}).get("dirty_file_count", -1)) == 0
    )
    f02_wrapper = (
        'using: "composite"' in action_text
        and "uses: actions/attest@" in action_text
        and "wrapper" in readme_text.lower()
        and "new implementations should use `actions/attest`" in readme_text
    )

    current_stage = gm["GM-IV"].get("state")
    allowed_forward_stages = {
        "STAGED_ACTIVE_RECON_2_OF_8",
        "STAGED_ACTIVE_PILOT_2_OF_8",
        "STAGED_ACTIVE_RECON_4_OF_8",
        "ACTIVE_8_OF_8",
    }
    checks = [
        ("01_gm_iv_stage_not_regressed", current_stage in allowed_forward_stages, current_stage),
        ("02_no_children_bound", gm["GM-IV"].get("children") == [], gm["GM-IV"].get("children")),
        ("03_gm_v_held", gm["GM-V"].get("state") == "HELD" and gm["GM-V"].get("children") == [], gm["GM-V"].get("state")),
        ("04_f01_exact_runtime_receipt", f01_pass, f01.get("repo", {})),
        ("05_f02_wrapper_contract", f02_wrapper, {"source_sha": f02_sha}),
        ("06_no_authority_transfer", ring.get("authority_transfer") is False and ring.get("children_bound") is False, False),
    ]
    failed = [c for c in checks if not c[1]]

    dispositions = {
        "GM-IV-F01": {
            "repository": targets["GM-IV-F01"]["repository"],
            "source_sha": f01_sha,
            "disposition": "PILOT" if f01_pass else "PARK",
            "reason": "independent executable self-index passed at exact SHA; suitable for bounded pilot without authority transfer" if f01_pass else "bounded executable proof failed",
            "next_crew": ["ENGINEER", "SMOKER", "QA"] if f01_pass else [],
        },
        "GM-IV-F02": {
            "repository": targets["GM-IV-F02"]["repository"],
            "source_sha": f02_sha,
            "disposition": "REFERENCE" if f02_wrapper else "PARK",
            "reason": "repository is a composite wrapper over pinned actions/attest and upstream README directs new implementations to actions/attest" if f02_wrapper else "wrapper boundary not proven",
            "next_crew": [],
        },
    }

    receipt = {
        "schema": "qps.gm_iv_ring1_recon_receipt.v1",
        "wave": "GM-FLEET-03-RING1",
        "repo": os.getenv("GITHUB_REPOSITORY", "LOCAL"),
        "source_sha": os.getenv("SOURCE_SHA", os.getenv("GITHUB_SHA", "UNKNOWN")),
        "run_id": os.getenv("GITHUB_RUN_ID", "LOCAL"),
        "authority_transfer": False,
        "children_bound": False,
        "historical_evidence_stage": "RECON_2_OF_8",
        "current_mission_state": current_stage,
        "checks": [{"check": n, "result": "PASS" if passed else "FAIL", "detail": d} for n, passed, d in checks],
        "result": "PASS" if not failed else "FAIL",
        "dispositions": dispositions,
        "pilot_gate": "READY_F01_ONLY" if not failed and dispositions["GM-IV-F01"]["disposition"] == "PILOT" else "WITHHELD",
        "gm_v_state": "HELD",
    }
    Path(args.out).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"result": receipt["result"], "pilot_gate": receipt["pilot_gate"], "current_mission_state": current_stage, "dispositions": {k: v["disposition"] for k, v in dispositions.items()}, "source_sha": receipt["source_sha"]}, sort_keys=True))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
