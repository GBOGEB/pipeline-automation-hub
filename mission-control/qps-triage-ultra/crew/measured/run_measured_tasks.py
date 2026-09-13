#!/usr/bin/env python3
import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CREW = ROOT.parent
OUT = ROOT / "receipts"
EXPOSURE_OUT = OUT / "exposure"
OUT.mkdir(parents=True, exist_ok=True)
EXPOSURE_OUT.mkdir(parents=True, exist_ok=True)

manifest = json.loads((ROOT / "MEASURED_TASK_MANIFEST_v1.json").read_text(encoding="utf-8"))
checklist = json.loads((ROOT / "REX_REUSE_CHECKLIST_v1.json").read_text(encoding="utf-8"))
registry = json.loads((CREW / "CREW_REGISTRY_v1.json").read_text(encoding="utf-8"))
competencies = json.loads((CREW / "COMPETENCY_MATRIX_v1.json").read_text(encoding="utf-8"))

crew_ids = {x["crew_id"] for x in registry["crew"]}
rex_ids = {x["rex_id"] for x in checklist["checklist"]}
dimensions = set(competencies["dimensions"])
source_sha = os.environ.get("MC_SOURCE_SHA", "")
checkout_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
run_id = os.environ.get("GITHUB_RUN_ID", "LOCAL_UNBOUND")
job_ref = os.environ.get("GITHUB_JOB", "LOCAL_UNBOUND")
runner_ref = os.environ.get("RUNNER_NAME", "LOCAL_UNBOUND")

if len(source_sha) != 40:
    raise SystemExit("FAIL: exact 40-char MC_SOURCE_SHA required")
if source_sha != checkout_sha:
    raise SystemExit(f"FAIL: receipt source SHA {source_sha} != checkout HEAD {checkout_sha}")

seen_assignments = set()
seen_tasks = set()
receipts = []
exposure_receipts = []

intervention_map = {
    "VERIFY": "VERIFY",
    "EXECUTE": "RUNTIME_OPERATOR",
    "MEASURE": "ANALYSIS",
    "REX": "GOVERNANCE",
}

for task in manifest["tasks"]:
    assignment_opened_iso = datetime.now(timezone.utc).isoformat()
    assignment_opened_mono = time.monotonic()

    aid = task["assignment_id"]
    tid = task["task_id"]
    if aid in seen_assignments or tid in seen_tasks:
        raise SystemExit("FAIL: duplicate assignment_id/task_id")
    seen_assignments.add(aid)
    seen_tasks.add(tid)
    if task["crew_id"] not in crew_ids:
        raise SystemExit(f"FAIL: unknown crew {task['crew_id']}")
    if task["competency_dimension"] not in dimensions:
        raise SystemExit(f"FAIL: unknown competency {task['competency_dimension']}")
    applicable = task.get("applicable_rex_ids", [])
    unknown_rex = sorted(set(applicable) - rex_ids)
    if unknown_rex:
        raise SystemExit(f"FAIL: unknown REX ids {unknown_rex}")
    if task.get("promotion_allowed") is not False:
        raise SystemExit(f"FAIL: pilot task {tid} may not promote competence")
    if task["task_type"] not in intervention_map:
        raise SystemExit(f"FAIL: no exposure intervention mapping for {task['task_type']}")

    command = task["command"]
    command_text = json.dumps(command, separators=(",", ":"))
    command_sha = hashlib.sha256(command_text.encode()).hexdigest()
    start_iso = datetime.now(timezone.utc).isoformat()
    start = time.monotonic()
    proc = subprocess.run(command, text=True, capture_output=True)
    elapsed = round(time.monotonic() - start, 6)
    end_mono = time.monotonic()
    end_iso = datetime.now(timezone.utc).isoformat()
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""

    expected = task["accept_condition"].split("stdout contains ", 1)[-1]
    accepted = proc.returncode == 0 and expected in stdout
    disposition = "ACCEPT" if accepted else "REJECT"

    rex_triggered = []
    if proc.returncode != 0 and "REX-006" in applicable:
        rex_triggered.append("REX-006")
    if not task.get("accept_condition") and "REX-005" in applicable:
        rex_triggered.append("REX-005")

    receipt = {
        "schema": "missioncontrol.mission_crew_task_runtime_receipt.v1",
        "mission_id": manifest["mission_id"],
        "task_id": tid,
        "assignment_id": aid,
        "crew_id": task["crew_id"],
        "crew_role_at_assignment": task["crew_role_at_assignment"],
        "attribution_basis": "PREDECLARED_ASSIGNMENT",
        "task_type": task["task_type"],
        "competency_dimension": task["competency_dimension"],
        "predeclared_task_level": task["predeclared_task_level"],
        "source_sha": source_sha,
        "run_id": str(run_id),
        "job_ref": job_ref,
        "runner_ref": runner_ref,
        "started_at": start_iso,
        "ended_at": end_iso,
        "execute_seconds": elapsed,
        "steps_executed": 1,
        "exit_code": proc.returncode,
        "disposition": disposition,
        "stdout_sha256": hashlib.sha256(stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr.encode()).hexdigest(),
        "command_sha256": command_sha,
        "receipt_evidence_class": "MEASURED_RUNTIME_ACCEPTED" if accepted else "MEASURED_RUNTIME_REJECTED",
        "promotion_allowed": False,
        "rex_preflight": {
            "checklist_version": checklist["schema"],
            "rex_ids_checked": applicable,
            "automated_checks": ["registered_rex_ids", "predeclared_assignment", "named_accept_condition", "exact_source_sha"],
            "manual_checklist_items": "NOT_ASSESSED_BY_RUNTIME_WRAPPER",
            "blocking_rex_ids": []
        },
        "rex_postflight": {
            "rex_ids_observed": rex_triggered,
            "new_rex_signal": None,
            "recurrence_level": "NEW" if rex_triggered else None,
            "preventive_action_effective": True if "REX-006" in applicable and proc.returncode == 0 else None,
            "ledger_update_required": bool(rex_triggered)
        }
    }
    path = OUT / f"{tid}.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipts.append(receipt)

    released_mono = time.monotonic()
    released_iso = datetime.now(timezone.utc).isoformat()
    waiting_seconds = round(start - assignment_opened_mono, 6)
    release_seconds = round(released_mono - end_mono, 6)
    exposure_seconds = round(released_mono - assignment_opened_mono, 6)

    exposure_receipt = {
        "schema": "missioncontrol.crew_exposure_receipt.v1",
        "mission_id": manifest["mission_id"],
        "task_id": tid,
        "assignment_id": aid,
        "crew_id": task["crew_id"],
        "crew_role": task["crew_role_at_assignment"],
        "assignment_opened_at": assignment_opened_iso,
        "task_started_at": start_iso,
        "task_ended_at": end_iso,
        "assignment_released_at": released_iso,
        "waiting_seconds": waiting_seconds,
        "active_seconds": elapsed,
        "release_seconds": release_seconds,
        "exposure_seconds": exposure_seconds,
        "intervention_type": intervention_map[task["task_type"]],
        "outcome": disposition,
        "source_sha": source_sha,
        "run_id": str(run_id),
        "job_ref": job_ref,
        "runner_ref": runner_ref,
        "attribution_basis": "PREDECLARED_ASSIGNMENT",
        "receipt_evidence_class": "MEASURED_CREW_EXPOSURE",
        "mission_performance_eligible": True,
        "pca_eligible": False,
        "bt_eligible": False,
        "competency_promotion_eligible": False,
        "authority_transfer": False,
        "child_binding": False,
        "frontier_binding": False
    }
    exposure_path = EXPOSURE_OUT / f"{tid}__EXPOSURE.json"
    exposure_path.write_text(
        json.dumps(exposure_receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    exposure_receipts.append(exposure_receipt)
    print(json.dumps({
        "task_id": tid,
        "crew_id": task["crew_id"],
        "disposition": disposition,
        "execute_seconds": elapsed,
        "waiting_seconds": waiting_seconds,
        "release_seconds": release_seconds,
        "exposure_seconds": exposure_seconds,
    }, sort_keys=True))

summary = {
    "schema": "missioncontrol.measured_task_run_summary.v1",
    "mission_id": manifest["mission_id"],
    "source_sha": source_sha,
    "checkout_sha": checkout_sha,
    "run_id": str(run_id),
    "task_count": len(receipts),
    "accepted": sum(r["disposition"] == "ACCEPT" for r in receipts),
    "rejected": sum(r["disposition"] == "REJECT" for r in receipts),
    "crew_exposure_receipts": len(exposure_receipts),
    "crew_exposure_seconds_total": round(sum(r["exposure_seconds"] for r in exposure_receipts), 6),
    "crew_waiting_seconds_total": round(sum(r["waiting_seconds"] for r in exposure_receipts), 6),
    "crew_active_seconds_total": round(sum(r["active_seconds"] for r in exposure_receipts), 6),
    "crew_release_seconds_total": round(sum(r["release_seconds"] for r in exposure_receipts), 6),
    "crew_exposure_pca_eligible": False,
    "crew_exposure_bt_eligible": False,
    "competency_promotions": 0,
    "authority_transfer": False
}
(OUT / "RUN_SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(summary, sort_keys=True))
if summary["rejected"]:
    raise SystemExit(1)
