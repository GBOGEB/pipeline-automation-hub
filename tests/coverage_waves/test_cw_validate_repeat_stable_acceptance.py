"""Behavioural tests for temporal/validate_repeat_stable_acceptance.py."""
import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_DIR = REPO_ROOT / "mission-control" / "qps-triage-ultra" / "crew" / "measured" / "frontier" / "temporal"
MOD_PATH = MOD_DIR / "validate_repeat_stable_acceptance.py"


def _load():
    spec = importlib.util.spec_from_file_location("cw_validate_repeat_stable_acceptance", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


val = _load()

CONFIG = {
    "task_classes": ["alpha", "beta"],
    "strategies": ["S1", "S2"],
    "policy_outputs": {"repeat_stable": "REPEAT_STABLE"},
    "window_contract": {"control_eligible_event": "schedule",
                        "control_eligible_workflow_path": ".github/workflows/t.yml"},
    "recommend_repeat_stable_gate": {
        "min_independent_windows": 2, "min_distinct_source_shas": 1, "min_temporal_span_seconds": 10,
        "min_directional_windows": 2, "min_direction_consistency": 0.7, "min_pooled_winner_strength": 0.5,
        "latest_two_directional_windows_must_agree": True,
    },
    "control_policy_gate": {"min_independent_windows": 5, "min_distinct_source_shas": 3,
                            "min_temporal_span_seconds": 1000},
}

ACCEPTED_ROW = {
    "task_class": "alpha", "accepted": True, "policy_status": "REPEAT_STABLE", "allocation_recommendation": "S1",
    "independent_windows": 2, "distinct_source_shas": 1, "temporal_span_seconds": 50, "directional_windows": 2,
    "direction_consistency": 0.9, "pooled_winner_strength": 0.6, "latest_two_directional_windows_agree": True,
    "rex_veto": False, "competency_promotion": False, "authority_transfer": False,
}

ACCEPTANCE = {
    "schema": "missioncontrol.repeat_stable_acceptance.v1",
    "authority_transfer": False,
    "competency_promotions": 0,
    "allocation_policy_promotion": False,
    "basis": {"rex_veto": False, "historical_collection_errors": [],
              "hosted_cells": sorted(val.EXPECTED_HOSTED_CELLS)},
    "scheduled_control_frontier": {
        "eligibility_event": "schedule", "eligibility_workflow_path": ".github/workflows/t.yml",
        "independent_windows": 2, "window_ids": ["w1", "w2"], "distinct_source_shas": 1,
        "temporal_span_seconds": 50, "required_independent_windows": 5, "required_distinct_source_shas": 3,
        "required_temporal_span_seconds": 1000, "clock_gate_met": False,
    },
    "accepted_task_classes": [ACCEPTED_ROW],
    "withheld_task_classes": [{"task_class": "beta", "accepted": False, "allocation_recommendation": "NO_POLICY",
                               "policy_status": "WITHHELD"}],
    "control_policy": {
        "status": "WITHHELD", "authority_transfer": False, "competency_promotions": 0,
        "required_independent_windows": 5, "required_distinct_source_shas": 3,
        "required_temporal_span_seconds": 1000, "observed_independent_windows": 2,
        "observed_distinct_source_shas": 1, "observed_temporal_span_seconds": 50,
    },
}


def _run(tmp_path, monkeypatch, acceptance=None, config=None):
    ap = tmp_path / "acceptance.json"
    cp = tmp_path / "config.json"
    ap.write_text(json.dumps(acceptance if acceptance is not None else ACCEPTANCE), encoding="utf-8")
    cp.write_text(json.dumps(config if config is not None else CONFIG), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["prog", "--acceptance", str(ap), "--config", str(cp)])
    return val.main()


def test_load_reads_json(tmp_path):
    p = tmp_path / "x.json"
    p.write_text('[1, "two"]', encoding="utf-8")
    assert val.load(p) == [1, "two"]
    assert val.load(str(p)) == [1, "two"]


def test_valid_acceptance_passes(tmp_path, monkeypatch, capsys):
    assert _run(tmp_path, monkeypatch) is None
    out = json.loads(capsys.readouterr().out)
    assert out == {
        "status": "PASS_REPEAT_STABLE_ACCEPTANCE",
        "accepted_task_classes": ["alpha"],
        "withheld_task_classes": ["beta"],
        "scheduled_control_windows": 2,
        "scheduled_control_span_seconds": 50,
        "control_policy": "WITHHELD",
        "competency_promotions": 0,
        "authority_transfer": False,
    }


@pytest.mark.parametrize("frontier_update", [
    # Only the third control requirement is unmet: exercises the full or-chain.
    {"independent_windows": 5, "window_ids": ["w%d" % i for i in range(5)], "distinct_source_shas": 3},
    # Only distinct SHAs unmet.
    {"independent_windows": 5, "window_ids": ["w%d" % i for i in range(5)], "distinct_source_shas": 1,
     "temporal_span_seconds": 2000, "clock_gate_met": True},
])
def test_control_still_blocked_by_any_single_requirement(tmp_path, monkeypatch, frontier_update):
    a = copy.deepcopy(ACCEPTANCE)
    a["scheduled_control_frontier"].update(frontier_update)
    f = a["scheduled_control_frontier"]
    a["control_policy"].update(observed_independent_windows=f["independent_windows"],
                               observed_distinct_source_shas=f["distinct_source_shas"],
                               observed_temporal_span_seconds=f["temporal_span_seconds"])
    assert _run(tmp_path, monkeypatch, acceptance=a) is None


def test_control_gate_fully_met_is_rejected(tmp_path, monkeypatch):
    a = copy.deepcopy(ACCEPTANCE)
    a["scheduled_control_frontier"].update(independent_windows=5, window_ids=["w%d" % i for i in range(5)],
                                           distinct_source_shas=3, temporal_span_seconds=1000, clock_gate_met=True)
    a["control_policy"].update(observed_independent_windows=5, observed_distinct_source_shas=3,
                               observed_temporal_span_seconds=1000)
    with pytest.raises(AssertionError):
        _run(tmp_path, monkeypatch, acceptance=a)


def _set(path, value):
    def mutate(a):
        node = a
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value
    return mutate


@pytest.mark.parametrize("mutate", [
    _set(["schema"], "wrong"),
    _set(["authority_transfer"], True),
    _set(["competency_promotions"], 2),
    _set(["allocation_policy_promotion"], True),
    _set(["basis", "rex_veto"], True),
    _set(["basis", "historical_collection_errors"], ["boom"]),
    _set(["basis", "hosted_cells"], ["linux-baseline"]),
    _set(["scheduled_control_frontier", "eligibility_event"], "push"),
    _set(["scheduled_control_frontier", "eligibility_workflow_path"], "other.yml"),
    _set(["scheduled_control_frontier", "window_ids"], ["w1"]),
    _set(["scheduled_control_frontier", "distinct_source_shas"], 0),
    _set(["scheduled_control_frontier", "temporal_span_seconds"], -1),
    _set(["scheduled_control_frontier", "required_independent_windows"], 4),
    _set(["scheduled_control_frontier", "required_distinct_source_shas"], 4),
    _set(["scheduled_control_frontier", "required_temporal_span_seconds"], 4),
    _set(["scheduled_control_frontier", "clock_gate_met"], True),
    _set(["withheld_task_classes", 0, "task_class"], "alpha"),
    _set(["withheld_task_classes", 0, "task_class"], "gamma"),
    _set(["accepted_task_classes", 0, "accepted"], False),
    _set(["accepted_task_classes", 0, "policy_status"], "OTHER"),
    _set(["accepted_task_classes", 0, "allocation_recommendation"], "S9"),
    _set(["accepted_task_classes", 0, "independent_windows"], 1),
    _set(["accepted_task_classes", 0, "distinct_source_shas"], 0),
    _set(["accepted_task_classes", 0, "temporal_span_seconds"], 5),
    _set(["accepted_task_classes", 0, "directional_windows"], 1),
    _set(["accepted_task_classes", 0, "direction_consistency"], 0.5),
    _set(["accepted_task_classes", 0, "pooled_winner_strength"], 0.1),
    _set(["accepted_task_classes", 0, "latest_two_directional_windows_agree"], False),
    _set(["accepted_task_classes", 0, "rex_veto"], True),
    _set(["accepted_task_classes", 0, "competency_promotion"], True),
    _set(["accepted_task_classes", 0, "authority_transfer"], True),
    _set(["withheld_task_classes", 0, "accepted"], True),
    _set(["withheld_task_classes", 0, "allocation_recommendation"], "S1"),
    _set(["withheld_task_classes", 0, "policy_status"], "REPEAT_STABLE"),
    _set(["control_policy", "status"], "CONTROL"),
    _set(["control_policy", "authority_transfer"], True),
    _set(["control_policy", "competency_promotions"], 1),
    _set(["control_policy", "required_independent_windows"], 1),
    _set(["control_policy", "required_distinct_source_shas"], 1),
    _set(["control_policy", "required_temporal_span_seconds"], 1),
    _set(["control_policy", "observed_independent_windows"], 9),
    _set(["control_policy", "observed_distinct_source_shas"], 9),
    _set(["control_policy", "observed_temporal_span_seconds"], 9),
], ids=lambda f: "mutation")
def test_acceptance_violations_are_rejected(tmp_path, monkeypatch, mutate):
    a = copy.deepcopy(ACCEPTANCE)
    mutate(a)
    with pytest.raises(AssertionError):
        _run(tmp_path, monkeypatch, acceptance=a)


def test_real_committed_acceptance_passes(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["prog", "--acceptance", str(MOD_DIR / "REPEAT_STABLE_ACCEPTANCE_v1.json"),
                                      "--config", str(MOD_DIR / "TEMPORAL_POLICY_CONFIG_v1.json")])
    assert val.main() is None
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "PASS_REPEAT_STABLE_ACCEPTANCE"
    assert out["control_policy"] == "WITHHELD"
