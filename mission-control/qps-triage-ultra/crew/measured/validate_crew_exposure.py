#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

SCHEMA = Path(__file__).resolve().parent / "CREW_EXPOSURE_RECEIPT_SCHEMA_v1.json"


def ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("receipt")
    args = ap.parse_args()

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    receipt = json.loads(Path(args.receipt).read_text(encoding="utf-8"))
    errors: list[str] = []

    for field in schema["required_fields"]:
        if field not in receipt:
            errors.append(f"missing required field: {field}")

    if errors:
        print(json.dumps({"status": "FAIL", "errors": errors}, indent=2, sort_keys=True))
        return 1

    opened = ts(receipt["assignment_opened_at"])
    started = ts(receipt["task_started_at"])
    ended = ts(receipt["task_ended_at"])
    released = ts(receipt["assignment_released_at"])

    waiting = (started - opened).total_seconds()
    active = (ended - started).total_seconds()
    release = (released - ended).total_seconds()
    exposure = (released - opened).total_seconds()

    checks = {
        "ordered_timestamps": opened <= started <= ended <= released,
        "waiting_math": receipt["waiting_seconds"] == waiting,
        "active_math": receipt["active_seconds"] == active,
        "release_math": receipt["release_seconds"] == release,
        "exposure_math": receipt["exposure_seconds"] == exposure,
        "sum_identity": receipt["exposure_seconds"] == receipt["waiting_seconds"] + receipt["active_seconds"] + receipt["release_seconds"],
        "authority_transfer_false": receipt.get("authority_transfer") is False,
        "child_binding_false": receipt.get("child_binding") is False,
        "frontier_binding_false": receipt.get("frontier_binding") is False,
        "evidence_class_known": receipt["receipt_evidence_class"] in schema["receipt_evidence_classes"],
        "intervention_known": receipt["intervention_type"] in schema["intervention_types"],
        "outcome_known": receipt["outcome"] in schema["outcomes"],
    }

    evidence_class = receipt["receipt_evidence_class"]
    if evidence_class == "INSTRUMENTATION_CANARY_ONLY":
        checks.update({
            "canary_not_pca": receipt.get("pca_eligible") is False,
            "canary_not_bt": receipt.get("bt_eligible") is False,
            "canary_not_competency": receipt.get("competency_promotion_eligible") is False,
            "canary_not_mission_performance": receipt.get("mission_performance_eligible") is False,
        })
    elif evidence_class == "MEASURED_CREW_EXPOSURE":
        checks.update({
            "measured_predeclared_assignment": receipt.get("attribution_basis") == "PREDECLARED_ASSIGNMENT",
            "measured_exact_sha": isinstance(receipt.get("source_sha"), str) and len(receipt["source_sha"]) == 40,
            "measured_run_bound": bool(str(receipt.get("run_id", ""))),
            "measured_job_bound": bool(str(receipt.get("job_ref", ""))),
            "measured_runner_bound": bool(str(receipt.get("runner_ref", ""))),
            "measured_mission_performance": receipt.get("mission_performance_eligible") is True,
            "measured_not_pca_before_repeat": receipt.get("pca_eligible") is False,
            "measured_not_bt_before_repeat": receipt.get("bt_eligible") is False,
            "measured_not_competency_promotion": receipt.get("competency_promotion_eligible") is False,
            "measured_non_canary_crew": receipt.get("crew_id") != "CANARY_ONLY",
            "measured_non_canary_mission": receipt.get("mission_id") != "INSTRUMENTATION_CANARY",
        })

    failed = [name for name, passed in checks.items() if not passed]
    result = {
        "schema": "missioncontrol.crew_exposure_validation.v1",
        "status": "PASS" if not failed else "FAIL",
        "checks": checks,
        "failed": failed,
        "authority_transfer": False,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
