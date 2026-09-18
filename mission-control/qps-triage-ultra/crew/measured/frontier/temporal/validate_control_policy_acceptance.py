#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--receipt", required=True)
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    r = json.loads(Path(args.receipt).read_text(encoding="utf-8"))
    c = json.loads(Path(args.config).read_text(encoding="utf-8"))
    g = c["control_policy_gate"]
    f = r["basis"]["scheduled_control_frontier"]

    assert r["schema"] == "missioncontrol.temporal_control_policy_acceptance.v1"
    assert r["mission_id"] == c["mission_id"]
    assert r["authority_transfer"] is False
    assert r["competency_promotions"] == 0
    assert r["guards"]["synthetic_or_noop_clock_evidence_admitted"] is False
    assert r["guards"]["manual_window_credit"] is False
    assert r["guards"]["thresholds_changed"] is False
    assert r["guards"]["push_event_used_as_control_clock"] is False
    assert r["basis"]["workflow_event"] == c["window_contract"]["control_eligible_event"]
    assert f["rex_veto"] is False
    assert f["independent_windows"] >= g["min_independent_windows"]
    assert f["distinct_source_shas"] >= g["min_distinct_source_shas"]
    assert f["temporal_span_seconds"] >= g["min_temporal_span_seconds"]
    assert len(f["hosted_runner_classes"]) >= g["min_hosted_runner_classes"]
    assert {"baseline", "held"}.issubset(set(f["lanes"]))
    assert len(f["window_ids"]) == f["independent_windows"]

    assert r["surveillance"]["medium_72h_reached"] is True
    assert r["surveillance"]["observed_span_seconds"] >= r["surveillance"]["medium_72h_target_seconds"]
    assert r["surveillance"]["medium_7d_reached"] is False
    assert r["surveillance"]["observed_span_seconds"] < r["surveillance"]["medium_7d_target_seconds"]

    def failed_gates(p: dict) -> list[str]:
        failed = []
        if f["independent_windows"] < g["min_independent_windows"]:
            failed.append("independent_windows")
        if f["distinct_source_shas"] < g["min_distinct_source_shas"]:
            failed.append("distinct_source_shas")
        if f["temporal_span_seconds"] < g["min_temporal_span_seconds"]:
            failed.append("temporal_span_seconds")
        if p["directional_windows"] < g["min_directional_windows"]:
            failed.append("directional_windows")
        if p["direction_consistency"] < g["min_direction_consistency"]:
            failed.append("direction_consistency")
        if p["pooled_winner_strength"] < g["min_pooled_winner_strength"]:
            failed.append("pooled_winner_strength")
        if g["latest_two_directional_windows_must_agree"] and not p["latest_two_directional_windows_agree"]:
            failed.append("latest_two_directional_windows_agree")
        if len(f["hosted_runner_classes"]) < g["min_hosted_runner_classes"]:
            failed.append("hosted_runner_classes")
        if g["requires_baseline_and_held_lanes"] and not {"baseline", "held"}.issubset(set(f["lanes"])):
            failed.append("baseline_and_held_lanes")
        return failed

    control = {p["task_class"]: p for p in r["control_classes"]}
    noncontrol = {p["task_class"]: p for p in r["noncontrol_classes"]}
    assert set(control) == {"cache_artifact_reuse", "short_compute", "validation_bundle"}
    assert set(noncontrol) == {"human_dependency_wait_proxy", "long_compute_contended"}

    for p in control.values():
        assert p["policy_status"] == "CONTROL_POLICY"
        assert p["allocation_policy_promotion"] is True
        assert failed_gates(p) == []
        assert p["first_red_gate"] is None

    for p in noncontrol.values():
        failed = failed_gates(p)
        assert failed
        assert p["policy_status"] != "CONTROL_POLICY"
        assert p["allocation_policy_promotion"] is False
        assert p["failed_control_gates"] == failed
        assert p["first_red_gate"] == failed[0]

    assert control["short_compute"]["pooled_winner_strength"] >= g["min_pooled_winner_strength"]
    assert noncontrol["human_dependency_wait_proxy"]["first_red_gate"] == "direction_consistency"
    assert noncontrol["long_compute_contended"]["first_red_gate"] == "direction_consistency"
    assert r["full_control_policy"]["independently_satisfied"] is False
    assert r["full_control_policy"]["control_class_count"] == 3
    assert r["full_control_policy"]["task_class_count"] == 5
    assert r["full_control_policy"]["noncontrol_class_count"] == 2

    print(json.dumps({
        "status": "PASS_TEMPORAL_CONTROL_POLICY_ACCEPTANCE",
        "source_sha": r["basis"]["source_sha"],
        "workflow_run_id": r["basis"]["workflow_run_id"],
        "scheduled_windows": f["independent_windows"],
        "scheduled_span_seconds": f["temporal_span_seconds"],
        "control_classes": sorted(control),
        "noncontrol_first_red": {k: v["first_red_gate"] for k, v in sorted(noncontrol.items())},
        "medium_72h_reached": r["surveillance"]["medium_72h_reached"],
        "medium_7d_reached": r["surveillance"]["medium_7d_reached"],
        "competency_promotions": 0,
        "authority_transfer": False,
    }, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
