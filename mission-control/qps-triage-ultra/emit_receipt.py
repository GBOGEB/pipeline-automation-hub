#!/usr/bin/env python3
"""Emit the HOME node receipt using the common qps-fleet-receipt/v1 contract."""
from __future__ import annotations
import argparse, json, os
from datetime import datetime, timezone
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--source-sha", required=True)
ap.add_argument("--outcome", required=True)
ap.add_argument("--out", required=True)
a = ap.parse_args()
receipt = {
    "schema": "qps-fleet-receipt/v1",
    "mission_id": "ULTRA",
    "repo": "GBOGEB/pipeline-automation-hub",
    "source_sha": a.source_sha,
    "observed_at": datetime.now(timezone.utc).isoformat(),
    "execution": {
        "kernel": "mission-control/qps-triage-ultra/validate_w0.py+validate_federation.py",
        "outcome": a.outcome.upper(),
        "steps_gt0": True,
        "workflow_run_id": os.getenv("GITHUB_RUN_ID", "UNBOUND"),
        "workflow_run_attempt": os.getenv("GITHUB_RUN_ATTEMPT", "UNBOUND")
    },
    "evidence_class": "EXECUTED_CONTROL_PLANE",
    "authority_transfer": False,
    "engineering_acceptance": False
}
Path(a.out).parent.mkdir(parents=True, exist_ok=True)
Path(a.out).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(receipt, sort_keys=True))
