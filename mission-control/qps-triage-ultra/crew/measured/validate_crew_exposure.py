#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

SCHEMA = Path(__file__).resolve().parent / "CREW_EXPOSURE_RECEIPT_SCHEMA_v1.json"
MICROS = 1_000_000


def ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def us(seconds: float) -> int:
    return int(round(float(seconds) * MICROS))


def delta_us(a: datetime, b: datetime) -> int:
    delta = b - a
    return ((delta.days * 86400 + delta.seconds) * MICROS) + delta.microseconds


def nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


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

    waiting_us = delta_us(opened, started)
    active_us = delta_us(started, ended)
    release_us = delta_us(ended, released)
    exposure_us = delta_us(opened, released)

    receipt_waiting_us = us(receipt["waiting_seconds"])
    receipt_active_us = us(receipt["active_seconds"])
    receipt_release_us = us(receipt["release_seconds"])
    receipt_exposure_us = us(receipt["exposure_seconds"])

    checks = {
        "ordered_timestamps": opened <= started <= ended <= released,
        "waiting_math": receipt_waiting_us == waiting_us,
        "active_math": receipt_active_us == active_us,
        "release_math": receipt_release_us == release_us,
        "exposure_math": receipt_exposure_us == exposure_us,
        "sum_identity": receipt_exposure_us == receipt_waiting_us + receipt_active_us + receipt_release_us,
        "timestamp_sum_identity": exposure_us == waiting_us + active_us + release_us,
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
            "measured_run_bound": nonempty_string(receipt.get("run_id")),
            "measured_job_bound": nonempty_string(receipt.get("job_ref")),
            "measured_runner_bound": nonempty_string(receipt.get("runner_ref")),
            "measured_mission_performance": receipt.get("mission_performance_eligible") is True,
            "measured_not_pca_before_repeat": receipt.get("pca_eligible") is False,
            "measured_not_bt_before_repeat": receipt.get("bt_eligible") is False,
            "measured_not_competency_promotion": receipt.get("competency_promotion_eligible") is False,
            "measured_non_canary_crew": receipt.get("crew_id") != "CANARY_ONLY",
            "measured_non_canary_mission": receipt.get("mission_id") != "INSTRUMENTATION_CANARY",
            "runtime_separate_if_present": (
                "runtime_execute_seconds" not in receipt
                or us(receipt["runtime_execute_seconds"]) >= 0
            ),
        })

    failed = [name for name, passed in checks.items() if not passed]
    result = {
        "schema": "missioncontrol.crew_exposure_validation.v1",
        "status": "PASS" if not failed else "FAIL",
        "checks": checks,
        "failed": failed,
        "time_resolution": "MICROSECOND_INTEGER",
        "authority_transfer": False,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
