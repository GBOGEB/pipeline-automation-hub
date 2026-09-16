#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CREW_ROOT = ROOT.parent / "qps-triage-ultra" / "crew"
DEFAULT_MANIFEST = ROOT / "GM_IV_RUNTIME_CAPACITY_MEASUREMENT_CONTRACT.json"
CAPACITY_CONTRACT = ROOT / "GM_FLEET_03_CAPACITY_CONTRACT.json"
REGISTRY = ROOT / "GRAND_MISSION_REGISTRY.json"
CREW_REGISTRY = CREW_ROOT / "CREW_REGISTRY_v1.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise SystemExit(f"FAIL: {message}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--source-sha", required=True)
    args = ap.parse_args()

    manifest = load(args.manifest)
    capacity = load(CAPACITY_CONTRACT)
    registry = load(REGISTRY)
    crew_registry = load(CREW_REGISTRY)

    actual_head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    require(len(args.source_sha) == 40, "source SHA must be 40 chars")
    require(actual_head == args.source_sha, f"source SHA mismatch expected={args.source_sha} actual={actual_head}")
    require(manifest.get("authority_transfer") is False, "manifest authority_transfer must be false")
    require(manifest.get("formal_credit_delta") == 0, "manifest formal_credit_delta must be zero")
    require(manifest.get("hard_gate_compensation_allowed") is False, "manifest hard-gate compensation must be false")

    missions = {m["id"]: m for m in registry["grand_missions"]}
    require(missions["GM-IV"]["state"] == "ACTIVE_8_OF_8", "GM-IV must remain ACTIVE_8_OF_8")
    require(missions["GM-IV"].get("children") == [], "GM-IV children must remain empty")
    require(missions["GM-V"]["state"] == "HELD", "GM-V must remain HELD")
    require(missions["GM-V"].get("children") == [], "GM-V children must remain empty")

    required = capacity["required_activation_capabilities"]
    assignments = manifest["assignments"]
    capabilities = [a["capability"] for a in assignments]
    crew_ids = [a["crew_id"] for a in assignments]
    task_ids = [a["task_id"] for a in assignments]
    require(set(capabilities) == set(required), f"capability set mismatch required={sorted(required)} actual={sorted(capabilities)}")
    require(len(capabilities) == len(set(capabilities)) == 8, "capabilities must be exactly 8 unique rows")
    require(len(crew_ids) == len(set(crew_ids)) == 8, "capacity measurement requires eight distinct predeclared hosts")
    require(len(task_ids) == len(set(task_ids)) == 8, "task IDs must be unique")

    crew_by_id = {r["crew_id"]: r for r in crew_registry["crew"]}
    args.out_dir.mkdir(parents=True, exist_ok=True)
    receipts = []
    run_id = str(os.environ.get("GITHUB_RUN_ID", "LOCAL_UNBOUND"))
    job_ref = str(os.environ.get("GITHUB_JOB", "LOCAL_UNBOUND"))
    runner_ref = str(os.environ.get("RUNNER_NAME", "LOCAL_UNBOUND"))

    for assignment in assignments:
        capability = assignment["capability"]
        crew_id = assignment["crew_id"]
        task_id = assignment["task_id"]
        require(crew_id in required[capability], f"{crew_id} is not an allowed host for {capability}")
        require(crew_id in crew_by_id, f"unknown crew host {crew_id}")
        crew = crew_by_id[crew_id]
        require(str(crew.get("maturity", "")).startswith("OBSERVED"), f"{crew_id} is not observed maturity")

        command = [str(x) for x in assignment["command"]]
        command_raw = json.dumps(command, separators=(",", ":"))
        env = os.environ.copy()
        env["MC_SOURCE_SHA"] = args.source_sha
        started = time.monotonic()
        proc = subprocess.run(command, text=True, capture_output=True, env=env)
        elapsed = round(time.monotonic() - started, 6)
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        accepted = proc.returncode == 0 and assignment["accept_marker"] in stdout
        disposition = "ACCEPT" if accepted else "REJECT"
        receipt = {
            "schema": "qps.gm_iv_runtime_capability_receipt.v1",
            "mission_id": "GM-IV",
            "capability": capability,
            "task_id": task_id,
            "task_type": assignment["task_type"],
            "crew_id": crew_id,
            "crew_name": crew.get("name"),
            "crew_maturity": crew.get("maturity"),
            "crew_current_load": crew.get("current_load"),
            "attribution_basis": "PREDECLARED_CAPABILITY_HOST",
            "receipt_evidence_class": "MEASURED_RUNTIME_CAPABILITY",
            "source_sha": args.source_sha,
            "run_id": run_id,
            "job_ref": job_ref,
            "runner_ref": runner_ref,
            "steps_executed": 1,
            "execute_seconds": elapsed,
            "exit_code": proc.returncode,
            "disposition": disposition,
            "capacity_class": "RUNTIME_PROVEN" if accepted else "NOT_PROVEN",
            "accept_marker": assignment["accept_marker"],
            "command_sha256": hashlib.sha256(command_raw.encode()).hexdigest(),
            "stdout_sha256": hashlib.sha256(stdout.encode()).hexdigest(),
            "stderr_sha256": hashlib.sha256(stderr.encode()).hexdigest(),
            "promotion_allowed": False,
            "competency_promotion_eligible": False,
            "authority_transfer": False,
            "formal_credit_delta": 0,
            "hard_gate_compensation_allowed": False
        }
        (args.out_dir / f"{task_id}.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        receipts.append(receipt)
        print(json.dumps({"capability": capability, "crew_id": crew_id, "disposition": disposition, "execute_seconds": elapsed}, sort_keys=True))

    accepted = [r for r in receipts if r["disposition"] == "ACCEPT"]
    aggregate = {
        "schema": "qps.gm_iv_runtime_capacity_measurement_receipt.v1",
        "wave": manifest["wave"],
        "mission_id": "GM-IV",
        "source_sha": args.source_sha,
        "run_id": run_id,
        "job_ref": job_ref,
        "runner_ref": runner_ref,
        "canonical_state": missions["GM-IV"]["state"],
        "gm_v_state": missions["GM-V"]["state"],
        "required_capability_count": len(required),
        "measured_capability_count": len(receipts),
        "runtime_proven_capability_count": len(accepted),
        "runtime_proven_ratio": len(accepted) / len(required),
        "distinct_predeclared_hosts": len(set(crew_ids)),
        "required_capabilities": sorted(required),
        "runtime_proven_capabilities": sorted(r["capability"] for r in accepted),
        "measured_capacity_result": "PASS_RUNTIME_PROVEN_CAPABILITY_CAPACITY" if len(accepted) == len(required) else "FAIL_RUNTIME_CAPABILITY_CAPACITY",
        "capacity_class": "RUNTIME_PROVEN" if len(accepted) == len(required) else "NOT_PROVEN",
        "operational_availability": "DEFER_EXTERNAL_NONCOMPENSATING_GATES_NOT_EVALUATED",
        "global_noncompensating_watch": "GBOGEB/cryoplant-project#923_LIVE_REFRESH_REQUIRED",
        "gm_v_launch_authorized": False,
        "competency_promotions": 0,
        "authority_transfer": False,
        "formal_credit_delta": 0,
        "hard_gate_compensation_allowed": False,
        "input_digests": {
            "measurement_contract_sha256": sha256_file(args.manifest),
            "capacity_contract_sha256": sha256_file(CAPACITY_CONTRACT),
            "crew_registry_sha256": sha256_file(CREW_REGISTRY),
            "grand_mission_registry_sha256": sha256_file(REGISTRY)
        },
        "capability_receipts": [
            {
                "capability": r["capability"],
                "crew_id": r["crew_id"],
                "task_id": r["task_id"],
                "capacity_class": r["capacity_class"],
                "steps_executed": r["steps_executed"],
                "disposition": r["disposition"]
            }
            for r in receipts
        ]
    }
    (args.out_dir / "GM_IV_RUNTIME_CAPACITY_MEASUREMENT_RECEIPT.json").write_text(
        json.dumps(aggregate, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(aggregate, sort_keys=True))

    if len(accepted) != len(required):
        failed = [f"{r['capability']}:{r['crew_id']}" for r in receipts if r["disposition"] != "ACCEPT"]
        raise SystemExit(f"FAIL_GM_IV_RUNTIME_CAPACITY failed={failed}")
    print("PASS_GM_IV_RUNTIME_CAPACITY_8_OF_8")
    print("DEFER_GM_V_OPERATIONAL_AVAILABILITY_EXTERNAL_GATES")


if __name__ == "__main__":
    main()
