"""Behavioural tests for temporal/validate_control_policy_acceptance.py."""
import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_DIR = REPO_ROOT / "mission-control" / "qps-triage-ultra" / "crew" / "measured" / "frontier" / "temporal"
MOD_PATH = MOD_DIR / "validate_control_policy_acceptance.py"


def _load():
    spec = importlib.util.spec_from_file_location("cw_validate_control_policy_acceptance", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


val = _load()

CONFIG = {
    "mission_id": "M-TEMP",
    "window_contract": {"control_eligible_event": "schedule"},
    "control_policy_gate": {
        "min_independent_windows": 3,
        "min_distinct_source_shas": 2,
        "min_temporal_span_seconds": 100,
        "min_directional_windows": 2,
        "min_direction_consistency": 0.8,
        "min_pooled_winner_strength": 0.5,
        "latest_two_directional_windows_must_agree": True,
        "min_hosted_runner_classes": 2,
        "requires_baseline_and_held_lanes": True,
    },
}


def _good(name):
    return {"task_class": name, "directional_windows": 3, "direction_consistency": 1.0,
            "pooled_winner_strength": 0.9, "latest_two_directional_windows_agree": True,
            "policy_status": "CONTROL_POLICY", "allocation_policy_promotion": True, "first_red_gate": None}


def _bad(name):
    return {"task_class": name, "directional_windows": 3, "direction_consistency": 0.4,
            "pooled_winner_strength": 0.9, "latest_two_directional_windows_agree": True,
            "policy_status": "RECOMMEND_ONLY", "allocation_policy_promotion": False,
            "failed_control_gates": ["direction_consistency"], "first_red_gate": "direction_consistency"}


RECEIPT = {
    "schema": "missioncontrol.temporal_control_policy_acceptance.v1",
    "mission_id": "M-TEMP",
    "authority_transfer": False,
    "competency_promotions": 0,
    "guards": {"synthetic_or_noop_clock_evidence_admitted": False, "manual_window_credit": False,
               "thresholds_changed": False, "push_event_used_as_control_clock": False},
    "basis": {
        "workflow_event": "schedule",
        "source_sha": "s" * 40,
        "workflow_run_id": "42",
        "scheduled_control_frontier": {
            "rex_veto": False, "independent_windows": 3, "distinct_source_shas": 2,
            "temporal_span_seconds": 150, "hosted_runner_classes": ["linux", "windows"],
            "lanes": ["baseline", "held", "extra"], "window_ids": ["w1", "w2", "w3"],
        },
    },
    "surveillance": {"medium_72h_reached": True, "observed_span_seconds": 300, "medium_72h_target_seconds": 200,
                     "medium_7d_reached": False, "medium_7d_target_seconds": 1000},
    "control_classes": [_good("cache_artifact_reuse"), _good("short_compute"), _good("validation_bundle")],
    "noncontrol_classes": [_bad("human_dependency_wait_proxy"), _bad("long_compute_contended")],
    "full_control_policy": {"independently_satisfied": False, "control_class_count": 3,
                            "task_class_count": 5, "noncontrol_class_count": 2},
}


def _run(tmp_path, monkeypatch, receipt=None, config=None):
    rp = tmp_path / "receipt.json"
    cp = tmp_path / "config.json"
    rp.write_text(json.dumps(receipt if receipt is not None else RECEIPT), encoding="utf-8")
    cp.write_text(json.dumps(config if config is not None else CONFIG), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["prog", "--receipt", str(rp), "--config", str(cp)])
    return val.main()


def test_valid_receipt_passes_and_summarises(tmp_path, monkeypatch, capsys):
    assert _run(tmp_path, monkeypatch) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "PASS_TEMPORAL_CONTROL_POLICY_ACCEPTANCE"
    assert out["source_sha"] == "s" * 40
    assert out["workflow_run_id"] == "42"
    assert out["scheduled_windows"] == 3 and out["scheduled_span_seconds"] == 150
    assert out["control_classes"] == ["cache_artifact_reuse", "short_compute", "validation_bundle"]
    assert out["noncontrol_first_red"] == {"human_dependency_wait_proxy": "direction_consistency",
                                           "long_compute_contended": "direction_consistency"}
    assert out["authority_transfer"] is False and out["competency_promotions"] == 0


def test_gate_flags_disabled_still_passes(tmp_path, monkeypatch):
    cfg = copy.deepcopy(CONFIG)
    cfg["control_policy_gate"]["latest_two_directional_windows_must_agree"] = False
    cfg["control_policy_gate"]["requires_baseline_and_held_lanes"] = False
    r = copy.deepcopy(RECEIPT)
    for p in r["control_classes"]:
        p["latest_two_directional_windows_agree"] = False
    assert _run(tmp_path, monkeypatch, receipt=r, config=cfg) == 0


def _set(path, value):
    def mutate(r):
        node = r
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value
    return mutate


@pytest.mark.parametrize("mutate", [
    _set(["schema"], "wrong.v1"),
    _set(["mission_id"], "OTHER"),
    _set(["authority_transfer"], True),
    _set(["competency_promotions"], 1),
    _set(["guards", "synthetic_or_noop_clock_evidence_admitted"], True),
    _set(["guards", "manual_window_credit"], True),
    _set(["guards", "thresholds_changed"], True),
    _set(["guards", "push_event_used_as_control_clock"], True),
    _set(["basis", "workflow_event"], "push"),
    _set(["basis", "scheduled_control_frontier", "rex_veto"], True),
    _set(["basis", "scheduled_control_frontier", "independent_windows"], 2),
    _set(["basis", "scheduled_control_frontier", "distinct_source_shas"], 1),
    _set(["basis", "scheduled_control_frontier", "temporal_span_seconds"], 99),
    _set(["basis", "scheduled_control_frontier", "hosted_runner_classes"], ["linux"]),
    _set(["basis", "scheduled_control_frontier", "lanes"], ["baseline"]),
    _set(["basis", "scheduled_control_frontier", "window_ids"], ["w1", "w2", "w3", "w4"]),
    _set(["surveillance", "medium_72h_reached"], False),
    _set(["surveillance", "observed_span_seconds"], 150),
    _set(["surveillance", "medium_7d_reached"], True),
    _set(["surveillance", "medium_7d_target_seconds"], 250),
    _set(["full_control_policy", "independently_satisfied"], True),
    _set(["full_control_policy", "control_class_count"], 2),
    _set(["full_control_policy", "task_class_count"], 4),
    _set(["full_control_policy", "noncontrol_class_count"], 3),
], ids=lambda f: "mutation")
def test_receipt_violations_are_rejected(tmp_path, monkeypatch, mutate):
    r = copy.deepcopy(RECEIPT)
    mutate(r)
    with pytest.raises(AssertionError):
        _run(tmp_path, monkeypatch, receipt=r)


def test_wrong_class_sets_rejected(tmp_path, monkeypatch):
    r = copy.deepcopy(RECEIPT)
    r["control_classes"] = r["control_classes"][:2]
    with pytest.raises(AssertionError):
        _run(tmp_path, monkeypatch, receipt=r)
    r = copy.deepcopy(RECEIPT)
    r["noncontrol_classes"][0]["task_class"] = "other"
    with pytest.raises(AssertionError):
        _run(tmp_path, monkeypatch, receipt=r)


@pytest.mark.parametrize("field,value", [
    ("policy_status", "RECOMMEND_ONLY"),
    ("allocation_policy_promotion", False),
    ("direction_consistency", 0.1),
    ("first_red_gate", "x"),
])
def test_control_class_defects_rejected(tmp_path, monkeypatch, field, value):
    r = copy.deepcopy(RECEIPT)
    r["control_classes"][1][field] = value
    with pytest.raises(AssertionError):
        _run(tmp_path, monkeypatch, receipt=r)


@pytest.mark.parametrize("field,value", [
    ("direction_consistency", 0.95),
    ("policy_status", "CONTROL_POLICY"),
    ("allocation_policy_promotion", True),
    ("failed_control_gates", ["pooled_winner_strength"]),
    ("first_red_gate", "pooled_winner_strength"),
])
def test_noncontrol_class_defects_rejected(tmp_path, monkeypatch, field, value):
    r = copy.deepcopy(RECEIPT)
    r["noncontrol_classes"][0][field] = value
    with pytest.raises(AssertionError):
        _run(tmp_path, monkeypatch, receipt=r)


def test_noncontrol_gate_order_determines_first_red(tmp_path, monkeypatch):
    # Every per-class gate red: failed list is ordered, so first_red becomes
    # directional_windows and the explicit direction_consistency pin rejects it.
    r = copy.deepcopy(RECEIPT)
    p = r["noncontrol_classes"][0]
    p.update(directional_windows=1, direction_consistency=0.1, pooled_winner_strength=0.1,
             latest_two_directional_windows_agree=False,
             failed_control_gates=["directional_windows", "direction_consistency",
                                   "pooled_winner_strength", "latest_two_directional_windows_agree"],
             first_red_gate="directional_windows")
    with pytest.raises(AssertionError):
        _run(tmp_path, monkeypatch, receipt=r)
    # Same failures except directional_windows: classification is consistent and passes.
    r2 = copy.deepcopy(RECEIPT)
    p2 = r2["noncontrol_classes"][1]
    p2.update(pooled_winner_strength=0.1, latest_two_directional_windows_agree=False,
              failed_control_gates=["direction_consistency", "pooled_winner_strength",
                                    "latest_two_directional_windows_agree"])
    assert _run(tmp_path, monkeypatch, receipt=r2) == 0


def test_real_committed_receipt_passes(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["prog", "--receipt", str(MOD_DIR / "CONTROL_POLICY_ACCEPTANCE_v1.json"),
                                      "--config", str(MOD_DIR / "TEMPORAL_POLICY_CONFIG_v1.json")])
    assert val.main() == 0
    assert json.loads(capsys.readouterr().out)["status"] == "PASS_TEMPORAL_CONTROL_POLICY_ACCEPTANCE"
