#!/usr/bin/env python3
from datetime import datetime, timedelta, timezone

import build_temporal_policy as policy


TASKS = policy.CONFIG["task_classes"]
TEMPORAL_PATH = policy.CONFIG["window_contract"]["control_eligible_workflow_path"]


def make_window(idx, seconds, event="schedule", path=TEMPORAL_PATH, single_strength=0.90):
    created = datetime(2026, 9, 13, tzinfo=timezone.utc) + timedelta(seconds=seconds)
    direction = "ALLOC_SINGLE_CELL" if single_strength >= 0.55 else "ALLOC_PAIRED_CELL"
    return {
        "window_id": str(1000 + idx),
        "run_attempt": 1,
        "workflow_name": "MissionControl Temporal Allocation Policy",
        "workflow_path": path,
        "event": event,
        "head_branch": "master",
        "source_sha": f"{idx + 1:040x}",
        "created_at": created.isoformat(),
        "source_kind": "SYNTHETIC_TEST",
        "analysis_digest_sha256": f"{idx + 101:064x}",
        "hosted_runner_classes": ["linux", "macos", "windows"],
        "lanes": ["baseline", "held"],
        "scarcity": {"status": "SCARCITY_UNPROVEN"},
        "rex_veto": False,
        "task_classes": {
            task: {
                "direction": direction,
                "single_normalized_strength": single_strength,
                "paired_normalized_strength": 1.0 - single_strength,
                "observed_pairs": 6,
            }
            for task in TASKS
        },
    }


def make_run(idx, seconds, event="pull_request", path=TEMPORAL_PATH):
    created = datetime(2026, 9, 13, tzinfo=timezone.utc) + timedelta(seconds=seconds)
    return {
        "id": 5000 + idx,
        "status": "completed",
        "conclusion": "success",
        "path": path,
        "event": event,
        "created_at": created.isoformat(),
    }


def test_non_scheduled_windows_cannot_satisfy_control_clock():
    windows = [
        make_window(0, 0, event="push"),
        make_window(1, 3600, event="push"),
        make_window(2, 7200, event="schedule"),
        make_window(3, 28800, event="schedule"),
        make_window(4, 50400, event="schedule"),
        make_window(5, 72000, event="schedule"),
        make_window(6, 90000, event="push"),
        make_window(7, 108000, event="workflow_dispatch"),
        make_window(8, 129600, event="pull_request"),
    ]
    receipt = policy.build_policy(windows)
    frontier = receipt["scheduled_control_frontier"]

    assert receipt["temporal_span_seconds"] >= 86400
    assert frontier["independent_windows"] == 4
    assert frontier["temporal_span_seconds"] < 86400
    assert all(p["policy_status"] != "CONTROL_POLICY" for p in receipt["policies"].values())
    assert all(p["allocation_policy_promotion"] is False for p in receipt["policies"].values())


def test_control_requires_six_genuine_scheduled_windows_and_full_span():
    windows = [make_window(i, i * 18000, event="schedule") for i in range(6)]
    receipt = policy.build_policy(windows)
    frontier = receipt["scheduled_control_frontier"]

    assert frontier["independent_windows"] == 6
    assert frontier["distinct_source_shas"] == 6
    assert frontier["temporal_span_seconds"] == 90000
    assert all(p["policy_status"] == "CONTROL_POLICY" for p in receipt["policies"].values())
    assert all(p["allocation_policy_promotion"] is True for p in receipt["policies"].values())
    assert all(p["control_frontier"]["independent_windows"] == 6 for p in receipt["policies"].values())


def test_scheduled_history_cannot_be_crowded_out_by_learning_traffic():
    scheduled = [make_run(i, i * 21600, event="schedule") for i in range(6)]
    recent = [make_run(100 + i, 200000 + i * 60, event="pull_request") for i in range(40)]

    selected = policy.select_historical_runs(recent, scheduled, current_run_id="999999")
    scheduled_selected = [
        row for row in selected
        if row["event"] == "schedule" and row["path"] == TEMPORAL_PATH
    ]

    assert len(recent) > policy.CONFIG["window_contract"]["historical_learning_window_limit"]
    assert len(scheduled_selected) == 6
    assert {row["id"] for row in scheduled_selected} == {row["id"] for row in scheduled}
    assert len(selected) == policy.CONFIG["window_contract"]["historical_learning_window_limit"] + 6


if __name__ == "__main__":
    test_non_scheduled_windows_cannot_satisfy_control_clock()
    test_control_requires_six_genuine_scheduled_windows_and_full_span()
    test_scheduled_history_cannot_be_crowded_out_by_learning_traffic()
    print("PASS_SCHEDULED_CONTROL_FRONTIER")
