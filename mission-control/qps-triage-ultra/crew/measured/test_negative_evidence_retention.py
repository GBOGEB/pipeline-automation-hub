#!/usr/bin/env python3
import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CANONICAL = ROOT / "history"

accepted_names = [
    "RUN_RETURN_34767429274.json",
    "RUN_RETURN_34767461345.json",
]

rejected = json.loads(r'''[
  {
    "schema": "missioncontrol.measured_task_run_return.v1",
    "status": "REJECTED_EXACT_SHA_RUNTIME_RETURN",
    "authority_transfer": false,
    "mission_id": "MC-CREW-MEASURE-001",
    "run_id": "BD009-SYNTHETIC-REJECT-1",
    "job_id": "SYNTHETIC_FIXTURE",
    "source_sha": "1111111111111111111111111111111111111111",
    "head_branch": "SYNTHETIC_FIXTURE",
    "workflow_name": "MissionControl Measured Crew Allocation",
    "run_conclusion": "failure",
    "exact_sha_asserted": true,
    "rex_checklist_status": "PASS_REX_REUSE_CHECKLIST",
    "competency_promotions": 0,
    "rejection_reason": "SYNTHETIC_REGRESSION_FIXTURE_BD009_NOT_PROJECT_EVIDENCE",
    "artifact": {
      "id": 910000001,
      "name": "synthetic-bd009",
      "size_in_bytes": 1,
      "digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    },
    "source_evidence": {
      "return_basis": "SYNTHETIC_REGRESSION_FIXTURE_NOT_PROJECT_EVIDENCE"
    },
    "task_observations": [
      {
        "task_id": "T001-CREW-STRUCTURE-VERIFY",
        "assignment_id": "A001",
        "crew_id": "U06",
        "task_type": "VERIFY",
        "competency_dimension": "evidence_provenance",
        "predeclared_task_level": 4,
        "execute_seconds": 0.01,
        "disposition": "REJECT",
        "rex_ids_observed": [],
        "preventive_action_effective": false
      }
    ],
    "rex_postflight": {
      "recurring": [],
      "persistent": [],
      "regression": [],
      "note": "synthetic regression fixture"
    }
  },
  {
    "schema": "missioncontrol.measured_task_run_return.v1",
    "status": "REJECTED_EXACT_SHA_RUNTIME_RETURN",
    "authority_transfer": false,
    "mission_id": "MC-CREW-MEASURE-001",
    "run_id": "BD009-SYNTHETIC-REJECT-2",
    "job_id": "SYNTHETIC_FIXTURE",
    "source_sha": "2222222222222222222222222222222222222222",
    "head_branch": "SYNTHETIC_FIXTURE",
    "workflow_name": "MissionControl Measured Crew Allocation",
    "run_conclusion": "failure",
    "exact_sha_asserted": true,
    "rex_checklist_status": "PASS_REX_REUSE_CHECKLIST",
    "competency_promotions": 0,
    "rejection_reason": "SYNTHETIC_REGRESSION_FIXTURE_BD009_NOT_PROJECT_EVIDENCE",
    "artifact": {
      "id": 910000002,
      "name": "synthetic-bd009",
      "size_in_bytes": 1,
      "digest": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    },
    "source_evidence": {
      "return_basis": "SYNTHETIC_REGRESSION_FIXTURE_NOT_PROJECT_EVIDENCE"
    },
    "task_observations": [
      {
        "task_id": "T001-CREW-STRUCTURE-VERIFY",
        "assignment_id": "A001",
        "crew_id": "U06",
        "task_type": "VERIFY",
        "competency_dimension": "evidence_provenance",
        "predeclared_task_level": 4,
        "execute_seconds": 0.01,
        "disposition": "REJECT",
        "rex_ids_observed": [],
        "preventive_action_effective": false
      }
    ],
    "rex_postflight": {
      "recurring": [],
      "persistent": [],
      "regression": [],
      "note": "synthetic regression fixture"
    }
  }
]''')

with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    history = tmp / "history"
    live = tmp / "live"
    history.mkdir()
    live.mkdir()

    for name in accepted_names:
        (history / name).write_text((CANONICAL / name).read_text(encoding="utf-8"), encoding="utf-8")
    for i, doc in enumerate(rejected, start=1):
        (history / f"RUN_RETURN_BD009_SYNTHETIC_{i}.json").write_text(
            json.dumps(doc, indent=2) + "\n",
            encoding="utf-8",
        )

    env = os.environ.copy()
    env["MEASURED_EVIDENCE_HISTORY"] = str(history)
    env["MEASURED_LIVE_RECEIPTS_DIR"] = str(live)
    out = tmp / "allocation.json"
    env["MEASURED_ALLOCATION_OUT"] = str(out)

    subprocess.run(["python3", str(ROOT / "validate_evidence_returns.py")], check=True, env=env)
    subprocess.run(["python3", str(ROOT / "build_measured_allocation.py")], check=True, env=env)

    allocation = json.loads(out.read_text(encoding="utf-8"))
    row = next(
        r for r in allocation["rows"]
        if r["crew_id"] == "U06"
        and r["competency_dimension"] == "evidence_provenance"
    )
    assert row["accepted"] == 2
    assert row["rejected"] == 2
    assert row["allocation_eligible"] is False
    assert allocation["canonical_rejected_run_count"] == 2
    assert allocation["canonical_rejected_observation_count"] == 2
    assert allocation["negative_evidence_promotion_credit"] == 0
    assert allocation["negative_evidence_pca_bt_eligible"] is False

    print(json.dumps({
        "status": "PASS_HIST_BD_009_NEGATIVE_RETENTION",
        "crew_id": row["crew_id"],
        "accepted": row["accepted"],
        "rejected": row["rejected"],
        "allocation_eligible": row["allocation_eligible"],
        "synthetic_fixture_project_evidence": False,
    }, sort_keys=True))
