#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

EXPECTED_HOSTED_CELLS = {
    "linux-baseline", "linux-held", "macos-baseline", "macos-held",
    "windows-baseline", "windows-held",
}


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--acceptance", required=True)
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    a = load(args.acceptance)
    c = load(args.config)
    repeat = c["recommend_repeat_stable_gate"]
    control = c["control_policy_gate"]
    contract = c["window_contract"]

    assert a["schema"] == "missioncontrol.repeat_stable_acceptance.v1"
    assert a["authority_transfer"] is False
    assert a["competency_promotions"] == 0
    assert a["allocation_policy_promotion"] is False
    assert a["basis"]["rex_veto"] is False
    assert a["basis"]["historical_collection_errors"] == []
    assert set(a["basis"]["hosted_cells"]) == EXPECTED_HOSTED_CELLS

    frontier = a["scheduled_control_frontier"]
    assert frontier["eligibility_event"] == contract["control_eligible_event"]
    assert frontier["eligibility_workflow_path"] == contract["control_eligible_workflow_path"]
    assert frontier["independent_windows"] == len(frontier["window_ids"])
    assert frontier["distinct_source_shas"] >= 1
    assert frontier["temporal_span_seconds"] >= 0
    assert frontier["required_independent_windows"] == control["min_independent_windows"]
    assert frontier["required_distinct_source_shas"] == control["min_distinct_source_shas"]
    assert frontier["required_temporal_span_seconds"] == control["min_temporal_span_seconds"]
    assert frontier["clock_gate_met"] is (
        frontier["temporal_span_seconds"] >= control["min_temporal_span_seconds"]
    )

    configured = set(c["task_classes"])
    accepted = a["accepted_task_classes"]
    withheld = a["withheld_task_classes"]
    accepted_names = {x["task_class"] for x in accepted}
    withheld_names = {x["task_class"] for x in withheld}
    assert accepted_names.isdisjoint(withheld_names)
    assert accepted_names | withheld_names == configured

    for row in accepted:
        assert row["accepted"] is True
        assert row["policy_status"] == c["policy_outputs"]["repeat_stable"]
        assert row["allocation_recommendation"] in c["strategies"]
        assert row["independent_windows"] >= repeat["min_independent_windows"]
        assert row["distinct_source_shas"] >= repeat["min_distinct_source_shas"]
        assert row["temporal_span_seconds"] >= repeat["min_temporal_span_seconds"]
        assert row["directional_windows"] >= repeat["min_directional_windows"]
        assert row["direction_consistency"] >= repeat["min_direction_consistency"]
        assert row["pooled_winner_strength"] >= repeat["min_pooled_winner_strength"]
        assert row["latest_two_directional_windows_agree"] is repeat["latest_two_directional_windows_must_agree"]
        assert row["rex_veto"] is False
        assert row["competency_promotion"] is False
        assert row["authority_transfer"] is False

    for row in withheld:
        assert row["accepted"] is False
        assert row["allocation_recommendation"] == "NO_POLICY"
        assert row["policy_status"] != c["policy_outputs"]["repeat_stable"]

    cp = a["control_policy"]
    assert cp["status"] == "WITHHELD"
    assert cp["authority_transfer"] is False
    assert cp["competency_promotions"] == 0
    assert cp["required_independent_windows"] == control["min_independent_windows"]
    assert cp["required_distinct_source_shas"] == control["min_distinct_source_shas"]
    assert cp["required_temporal_span_seconds"] == control["min_temporal_span_seconds"]
    assert cp["observed_independent_windows"] == frontier["independent_windows"]
    assert cp["observed_distinct_source_shas"] == frontier["distinct_source_shas"]
    assert cp["observed_temporal_span_seconds"] == frontier["temporal_span_seconds"]

    control_still_blocked = (
        frontier["independent_windows"] < control["min_independent_windows"]
        or frontier["distinct_source_shas"] < control["min_distinct_source_shas"]
        or frontier["temporal_span_seconds"] < control["min_temporal_span_seconds"]
    )
    assert control_still_blocked

    print(json.dumps({
        "status": "PASS_REPEAT_STABLE_ACCEPTANCE",
        "accepted_task_classes": sorted(accepted_names),
        "withheld_task_classes": sorted(withheld_names),
        "scheduled_control_windows": frontier["independent_windows"],
        "scheduled_control_span_seconds": frontier["temporal_span_seconds"],
        "control_policy": "WITHHELD",
        "competency_promotions": 0,
        "authority_transfer": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
