#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GRAND = REPO / "mission-control" / "grand-missions"
EXPOSURE_DIR = REPO / "mission-control" / "qps-triage-ultra" / "crew" / "measured"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL: {message}")


def run_exposure_validator(receipt: dict) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "receipt.json"
        path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(EXPOSURE_DIR / "validate_crew_exposure.py"), str(path)],
            cwd=REPO,
            text=True,
            capture_output=True,
            check=False,
        )


def valid_measured_receipt() -> dict:
    return {
        "schema": "missioncontrol.crew_exposure_receipt.v1",
        "mission_id": "GM-IV",
        "task_id": "FORWARD_GATE_SAFETY_REGRESSION",
        "assignment_id": "TEST-001",
        "crew_id": "QA_1",
        "crew_role": "QA",
        "assignment_opened_at": "2026-09-14T00:00:00+00:00",
        "task_started_at": "2026-09-14T00:00:01+00:00",
        "task_ended_at": "2026-09-14T00:00:03+00:00",
        "assignment_released_at": "2026-09-14T00:00:04+00:00",
        "waiting_seconds": 1.0,
        "active_seconds": 2.0,
        "release_seconds": 1.0,
        "exposure_seconds": 4.0,
        "intervention_type": "VERIFY",
        "outcome": "CONTROL",
        "source_sha": "0" * 40,
        "receipt_evidence_class": "MEASURED_CREW_EXPOSURE",
        "attribution_basis": "PREDECLARED_ASSIGNMENT",
        "run_id": "123456789",
        "job_ref": "job://forward-gate-safety",
        "runner_ref": "runner://ubuntu-24.04",
        "authority_transfer": False,
        "child_binding": False,
        "frontier_binding": False,
        "mission_performance_eligible": True,
        "pca_eligible": False,
        "bt_eligible": False,
        "competency_promotion_eligible": False,
        "runtime_execute_seconds": 2.0,
    }


def main() -> int:
    fleet = load_module("gm_fleet_validator", GRAND / "validate_gm_fleet.py")
    exposure = load_module("crew_exposure_validator", EXPOSURE_DIR / "validate_crew_exposure.py")

    registry = json.loads((GRAND / "GRAND_MISSION_REGISTRY.json").read_text(encoding="utf-8"))
    contract = json.loads((GRAND / "GM_IV_RECON4_GOVERNOR_CONTRACT.json").read_text(encoding="utf-8"))
    gm_iv = next(item for item in registry["grand_missions"] if item["id"] == "GM-IV")

    require(
        gm_iv["state"] in {"STAGED_ACTIVE_PILOT_2_OF_8", "STAGED_ACTIVE_RECON_4_OF_8"},
        f"unexpected controlled baseline: {gm_iv['state']}",
    )
    require(fleet.gm_iv_supported_shape(gm_iv), "current governed GM-IV shape must be accepted")

    recon4 = copy.deepcopy(gm_iv)
    recon4.update(contract["proposed_shape"])
    recon4["frontier_count"] = 8
    if gm_iv["state"] == "STAGED_ACTIVE_RECON_4_OF_8":
        recon4["recon_4_of_8_evidence"] = contract["accepted_gate_evidence"]
        require(fleet.gm_iv_supported_shape(recon4), "governed RECON_4 shape must be accepted after promotion")
    else:
        recon4.pop("recon_4_of_8_evidence", None)
        require(
            not fleet.gm_iv_supported_shape(recon4),
            "RECON_4 must fail closed before separate promotion binds accepted evidence",
        )

    active8 = copy.deepcopy(recon4)
    active8["state"] = "ACTIVE_8_OF_8"
    active8["activation_stage"] = "ACTIVE_8_OF_8"
    require(
        not fleet.gm_iv_supported_shape(active8),
        "ACTIVE_8 must fail closed until its separate Governor defines the complete shape",
    )
    require(
        "ACTIVE_8_OF_8" in fleet.FORWARD_GM_IV_STATES_REQUIRING_GOVERNOR,
        "ACTIVE_8 must remain explicitly Governor-gated",
    )
    require(
        fleet.FORWARD_GM_IV_STATES_REQUIRING_GOVERNOR.isdisjoint(fleet.SUPPORTED_GM_IV_STATES),
        "unsupported forward stages must not leak into generic supported-state set",
    )

    for good in ("run-1", " job://1 ", "runner://1"):
        require(exposure.nonempty_string(good), f"valid provenance rejected: {good!r}")
    for bad in (None, "", "   ", 0, False, {}, []):
        require(not exposure.nonempty_string(bad), f"invalid provenance accepted: {bad!r}")

    valid = valid_measured_receipt()
    positive = run_exposure_validator(valid)
    require(positive.returncode == 0, f"positive measured receipt failed: {positive.stdout} {positive.stderr}")
    positive_data = json.loads(positive.stdout)
    require(positive_data["status"] == "PASS", "positive measured receipt did not PASS")

    for field in ("run_id", "job_ref", "runner_ref"):
        for invalid in (None, "", "   ", 0, False):
            candidate = copy.deepcopy(valid)
            candidate[field] = invalid
            result = run_exposure_validator(candidate)
            require(result.returncode != 0, f"{field}={invalid!r} unexpectedly passed")
            data = json.loads(result.stdout)
            require(data["status"] == "FAIL", f"{field}={invalid!r} did not emit FAIL")
            expected_check = {
                "run_id": "measured_run_bound",
                "job_ref": "measured_job_bound",
                "runner_ref": "measured_runner_bound",
            }[field]
            require(expected_check in data["failed"], f"{field} failure did not bind to {expected_check}")

    print(json.dumps({
        "result": "PASS_GM_IV_FORWARD_GATE_SAFETY",
        "current_state": gm_iv["state"],
        "recon_4_authorized": gm_iv["state"] == "STAGED_ACTIVE_RECON_4_OF_8",
        "active_8_authorized": False,
        "provenance_negative_controls": 15,
        "authority_transfer": False,
        "child_binding": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
