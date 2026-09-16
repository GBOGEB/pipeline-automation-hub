#!/usr/bin/env python3
import argparse
import copy
import json
from pathlib import Path

EXPECTED_SKILLS = {"math", "plots", "math-plots"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ledger", type=Path, required=True)
    p.add_argument("--receipts", type=Path, required=True)
    p.add_argument("--score-out", type=Path, required=True)
    p.add_argument("--rolled-ledger-out", type=Path, required=True)
    p.add_argument("--skills-ref", required=True)
    p.add_argument("--source-ref", required=True)
    ns = p.parse_args()

    ledger = json.loads(ns.ledger.read_text(encoding="utf-8"))
    receipts = []
    for path in sorted(ns.receipts.glob("*.json")):
        receipt = json.loads(path.read_text(encoding="utf-8"))
        receipts.append(receipt)

    skills = {r.get("skill") for r in receipts}
    if skills != EXPECTED_SKILLS or len(receipts) != 3:
        raise SystemExit(f"expected exactly three distinct skill receipts, got {sorted(skills)} / {len(receipts)}")
    for r in receipts:
        if r.get("status") != "PASS_SKILL_BUNDLE_RESOLUTION":
            raise SystemExit(f"non-pass receipt for {r.get('skill')}")
        if r.get("authority_transfer") is not False:
            raise SystemExit("authority transfer must remain false")
        if r.get("skills_ref") != ns.skills_ref:
            raise SystemExit(f"skills ref mismatch for {r.get('skill')}")
        if r.get("resolution_mode") != "hosted_pr_matrix":
            raise SystemExit(f"unexpected resolution mode for {r.get('skill')}")

    rolled = copy.deepcopy(ledger)
    due = None
    remaining = []
    for item in rolled.get("pending", []):
        if item.get("target_pulse") == "SKILL_P1" and item.get("metric") == "skill_bundles_resolvable":
            due = item
        else:
            remaining.append(item)
    if due is None:
        raise SystemExit("missing frozen SKILL_P1 prediction")

    prediction = due["prediction"]
    actual = len(receipts)
    abs_error = abs(actual - prediction)
    scored = copy.deepcopy(due)
    scored.update({
        "actual": actual,
        "absolute_error": abs_error,
        "observed_source_ref": ns.source_ref,
        "skills_ref": ns.skills_ref,
        "resolution_mode": "hosted_pr_matrix",
        "receipt_skills": sorted(skills),
        "status": "SCORED_EXACT_HIT" if abs_error == 0 else "SCORED_MISS"
    })
    rolled.setdefault("history", []).append(scored)

    if not any(x.get("target_pulse") == "SKILL_P3" for x in remaining):
        remaining.append({
            "issued_at_pulse": "SKILL_P1",
            "target_pulse": "SKILL_P3",
            "metric": "exact_pinned_consumer_receipts",
            "prediction": 3,
            "basis": "SKILL_P1 observed all three canonical bundles resolving at one exact skills SHA; next control forecasts three exact-pinned consumer receipts",
            "actual": None
        })
    rolled["pending"] = remaining
    calibration = rolled.setdefault("calibration", {})
    calibration["n_scored"] = int(calibration.get("n_scored", 0)) + 1
    calibration["state"] = "WARM_START_INSUFFICIENT_SCORED_HISTORY"
    calibration["last_absolute_error"] = abs_error
    calibration["probability_calibration_applied"] = False
    rolled["as_of"] = "2026-09-16T22:20:00+02:00"

    score = {
        "schema": "missioncontrol.crew.skill_resolution_pulse_score.v1",
        "pulse": "SKILL_P1",
        "global_alignment": "MP_P2_FIRST_FEDERATED_USE",
        "skills_ref": ns.skills_ref,
        "source_ref": ns.source_ref,
        "individual_receipts": sorted(skills),
        "prediction": prediction,
        "actual": actual,
        "absolute_error": abs_error,
        "forecast_status": scored["status"],
        "SKILL_P2_prediction_state": "FROZEN_PENDING_NOT_DUE",
        "SKILL_P3_issued": True,
        "calibration": rolled["calibration"],
        "authority_transfer": False,
        "formal_credit_delta": 0
    }

    ns.score_out.parent.mkdir(parents=True, exist_ok=True)
    ns.rolled_ledger_out.parent.mkdir(parents=True, exist_ok=True)
    ns.score_out.write_text(json.dumps(score, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ns.rolled_ledger_out.write_text(json.dumps(rolled, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(score, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
