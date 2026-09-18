#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
import yaml

HERE = Path(__file__).resolve().parent
CONTROL = HERE / "GM_V_EXTERNAL_REENTRY_CONTROL_v1.yaml"
REGISTRY = HERE / "GRAND_MISSION_REGISTRY.json"

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-sha", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    c = yaml.safe_load(CONTROL.read_text(encoding="utf-8"))
    r = json.loads(REGISTRY.read_text(encoding="utf-8"))
    gm = {x["id"]: x for x in r["grand_missions"]}
    checks = {}

    checks["source_sha_exact"] = len(args.source_sha) == 40
    checks["refresh_pass"] = c["three_p_star"]["refresh"]["result"] == "PASS"
    checks["probe_block_confirmed"] = c["three_p_star"]["probe"]["result"] == "PASS_BLOCK_CONFIRMED"
    jobs = c["three_p_star"]["probe"]["release_runner_probe"]["jobs"]
    checks["release_probe_all_zero_step"] = len(jobs) == 3 and all(x["executed_steps"] == 0 for x in jobs)
    iv = c["three_p_star"]["probe"]["independent_validator"]
    checks["independent_validator_zero_step"] = iv["executed_steps"] == 0
    checks["rank_first_red_923"] = c["three_p_star"]["rank"]["first_red"] == "GBOGEB/cryoplant-project#923"
    checks["gm_iv_active8"] = gm["GM-IV"]["state"] == "ACTIVE_8_OF_8"
    checks["gm_v_held"] = gm["GM-V"]["state"] == "HELD" and gm["GM-V"]["children"] == []
    checks["no_authority_transfer"] = r["authority_transfer"] is False and c["authority_transfer"] is False
    checks["no_credit"] = c["formal_credit_delta"] == 0
    checks["mip_complete"] = all(c["mip"][k]["result"] == "PASS" for k in ("modernize","innovate","perpetuate"))
    pred = c["reentry_predicate"]["required_all"]
    checks["positive_witness_complete"] = set(pred) == {
        "owner_side_actions_admission_materially_changed",
        "unchanged_private_qps_release_runner_probe",
        "runner_id_nonzero",
        "executed_steps_gt_zero",
        "exact_current_qps_sha_bound",
    }
    checks["decision_withhold"] = c["decision"] == "WITHHOLD_GM_V_LAUNCH_EXTERNAL_OPERATIONAL_AVAILABILITY"

    failed = [k for k,v in checks.items() if not v]
    receipt = {
        "schema": "qps.gm_v_external_reentry_control_receipt.v1",
        "source_sha": args.source_sha,
        "result": "PASS" if not failed else "FAIL",
        "decision": c["decision"] if not failed else "FAIL_CLOSED",
        "first_red": c["three_p_star"]["rank"]["first_red"],
        "reentry_authorized_now": False,
        "gm_v_launch_authorized": False,
        "authority_transfer": False,
        "formal_credit_delta": 0,
        "checks": checks,
        "failed": failed,
    }
    Path(args.out).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
    return 1 if failed else 0

if __name__ == "__main__":
    raise SystemExit(main())
