#!/usr/bin/env python3
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def fail(msg):
    print(f"FAIL: {msg}")
    sys.exit(1)


def require_fields(record, required, context):
    missing = sorted(set(required) - set(record))
    if missing:
        fail(f"{context} missing required fields {missing}")


def main():
    registry = load("CREW_REGISTRY_v1.json")
    snapshot = load("CREW_SNAPSHOT_2026-09-13.json")
    policy = load("ROLE_GAP_POLICY_v1.json")
    signals = load("ROLE_GAP_SIGNALS_SEED_2026-09-13.json")
    trials = load("ROLE_TRIALS_v1.json")
    telemetry = load("CREW_TELEMETRY_SCHEMA_v1.json")

    crew = {c["crew_id"]: c for c in registry["crew"]}
    if len(crew) != len(registry["crew"]):
        fail("duplicate crew_id")

    counts = snapshot["fleet_population"]
    conceptual = [c for c in crew.values() if c.get("maturity") == "CONCEPTUAL"]
    partial_or_observed_specialists = [
        c for c in crew.values()
        if c["crew_id"].startswith("S") and c.get("maturity") in {"OBSERVED", "PARTIAL"}
    ]
    home = [c for c in crew.values() if c["crew_id"].startswith("U")]
    if len(home) != counts["permanent_home_seats"]:
        fail("HOME seat count mismatch")
    if len(partial_or_observed_specialists) != counts["observed_or_partial_specialists"]:
        fail("specialist count mismatch")
    if len(conceptual) != counts["conceptual_candidates"]:
        fail("conceptual count mismatch")
    if len(crew) != counts["total_registered_records"]:
        fail("total crew count mismatch")

    event_required = telemetry.get("event_required", [])
    if not event_required:
        fail("telemetry event_required contract must not be empty")
    for event in snapshot["live_observations"]:
        require_fields(event, event_required, f"telemetry event {event.get('event_id', '<missing>')}")
        if event["crew_id"] not in crew:
            fail(f"unknown telemetry crew {event['crew_id']}")
        if event["event_type"] not in telemetry["event_types"]:
            fail(f"unregistered event type {event['event_type']}")
        if event["state"] not in telemetry["states"]:
            fail(f"unregistered telemetry state {event['state']}")
        if event["evidence_class"] not in telemetry["evidence_classes"]:
            fail(f"unregistered evidence class {event['evidence_class']}")
        if event.get("steps_executed") == 0 and event["event_type"] in {"RUN_STEP", "RUN_END", "ACCEPT", "CONTROL_REPEAT"}:
            fail("zero-step runtime event cannot represent execution/accept/control")

    if snapshot["competency_promotion"]["promotions_this_snapshot"] != 0:
        fail("seed snapshot must not promote competence")

    if signals["evidence_class"] != "EXPERT_SEEDED_NOT_MEASURED":
        fail("seed signals must remain expert-seeded")

    candidates = {c["candidate_role_id"]: c for c in signals["candidates"]}
    for role_id in candidates:
        if role_id not in crew:
            fail(f"role-gap candidate {role_id} missing from registry")
        if crew[role_id].get("maturity") != "CONCEPTUAL":
            fail(f"role-gap candidate {role_id} must remain conceptual")

    trial_required = policy.get("trial_requirements", [])
    if not trial_required:
        fail("role-gap policy trial_requirements must not be empty")
    trial_ids = set()
    dimensions = set(load("COMPETENCY_MATRIX_v1.json")["dimensions"])
    for trial in trials["trials"]:
        if trial["trial_id"] in trial_ids:
            fail(f"duplicate trial id {trial['trial_id']}")
        trial_ids.add(trial["trial_id"])
        require_fields(trial, trial_required, f"trial {trial['trial_id']}")
        role_id = trial["candidate_role_id"]
        if role_id not in crew:
            fail(f"trial references unknown role {role_id}")
        if crew[role_id].get("maturity") != "CONCEPTUAL":
            fail(f"planned trial role {role_id} already promoted")
        if trial["state"] != "PLANNED_NOT_ACTIVATED":
            fail(f"seed trial {trial['trial_id']} must not auto-activate")
        if trial["promotion_after_success"] != "PARTIAL_ONLY":
            fail(f"trial {trial['trial_id']} cannot jump directly to observed/control")
        if not trial.get("mentor_or_challenger"):
            fail(f"trial {trial['trial_id']} missing mentor/challenger")
        if not trial.get("success_condition") or not trial.get("failure_condition"):
            fail(f"trial {trial['trial_id']} missing success/failure bounds")
        profile = trial.get("competency_target_profile", {})
        if set(profile) != dimensions:
            fail(f"trial {trial['trial_id']} competency_target_profile must exactly match registered dimensions")
        if any(not isinstance(value, int) or not 0 <= value <= 6 for value in profile.values()):
            fail(f"trial {trial['trial_id']} competency_target_profile values must be integers 0..6")

    if policy.get("authority_transfer") is not False or trials.get("authority_transfer") is not False:
        fail("authority transfer must remain false")

    print(json.dumps({
        "status": "PASS_CREW_TELEMETRY_STRUCTURE",
        "crew_records": len(crew),
        "live_events": len(snapshot["live_observations"]),
        "event_required_fields": len(event_required),
        "seed_role_gap_candidates": len(candidates),
        "planned_trials": len(trials["trials"]),
        "trial_required_fields": len(trial_required),
        "competency_promotions": 0,
        "authority_transfer": False
    }, sort_keys=True))


if __name__ == "__main__":
    main()
