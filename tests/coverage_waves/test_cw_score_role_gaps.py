"""Behavioural tests for mission-control/qps-triage-ultra/crew/score_role_gaps.py."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CREW_DIR = REPO_ROOT / "mission-control" / "qps-triage-ultra" / "crew"
MODULE_PATH = CREW_DIR / "score_role_gaps.py"

POLICY = {
    "signals": {"a": {"weight": 0.5}, "b": {"weight": 0.5}},
    "penalties": {"p": {"weight": 0.4}},
}


def _load_module():
    spec = importlib.util.spec_from_file_location("cw_score_role_gaps", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mod():
    return _load_module()


def _cand(a=1.0, b=1.0, p=0.0, **extra):
    c = {"candidate_role_id": "R1", "name": "Role", "signals": {"a": a, "b": b}, "penalties": {"p": p}}
    c.update(extra)
    return c


def test_load_json(mod, tmp_path):
    f = tmp_path / "x.json"
    f.write_text('{"x": 2}', encoding="utf-8")
    assert mod.load_json(str(f)) == {"x": 2}


@pytest.mark.parametrize(
    "score,cand,expected",
    [
        (0.7, {"independent_need_signals": [1, 2], "trial_ready": True}, "TRIAL_CANDIDATE"),
        (0.65, {"independent_need_signals": [1, 2], "trial_ready": True}, "TRIAL_CANDIDATE"),
        (0.7, {"independent_need_signals": [1], "trial_ready": True}, "WATCH_OR_SECOND"),
        (0.7, {"independent_need_signals": [1, 2], "trial_ready": False}, "WATCH_OR_SECOND"),
        (0.7, {"independent_need_signals": [1, 2], "trial_ready": True, "authority_collision": True}, "WATCH_OR_SECOND"),
        (0.45, {}, "WATCH_OR_SECOND"),
        (0.4499, {"independent_need_signals": [1, 2], "trial_ready": True}, "REUSE_TRAIN_TOOL_OR_PRUNE"),
    ],
)
def test_decision_for_thresholds(mod, score, cand, expected):
    assert mod.decision_for(score, cand) == expected


def test_score_candidate_weights_and_fields(mod):
    c = _cand(a=1.0, b=0.5, p=0.5, independent_need_signals=["x", "y"], trial_ready=True,
              evidence_class="SEEDED", warning="w")
    r = mod.score_candidate(POLICY, c)
    assert r["positive"] == 0.75
    assert r["penalty"] == 0.2
    assert r["score"] == 0.55
    assert r["decision"] == "WATCH_OR_SECOND"
    assert r["independent_need_signal_count"] == 2
    assert r["trial_ready"] is True and r["authority_collision"] is False
    assert r["evidence_class"] == "SEEDED" and r["warning"] == "w" and r["name"] == "Role"


def test_score_clamped_to_zero_and_one(mod):
    low = mod.score_candidate(POLICY, _cand(a=0.0, b=0.0, p=1.0))
    assert low["score"] == 0.0 and low["penalty"] == 0.4
    policy = {"signals": {"a": {"weight": 2.0}}, "penalties": {}}
    high = mod.score_candidate(policy, {"candidate_role_id": "R", "signals": {"a": 1.0}})
    assert high["score"] == 1.0 and high["positive"] == 2.0


@pytest.mark.parametrize("kw,match", [({"a": 1.5}, "R1 a outside 0..1"), ({"p": -0.1}, "R1 p outside 0..1")])
def test_out_of_range_values_rejected(mod, kw, match):
    with pytest.raises(ValueError, match=match):
        mod.score_candidate(POLICY, _cand(**kw))


def test_missing_signals_and_penalties_reported_together(mod):
    c = {"candidate_role_id": "R9", "signals": {"a": 0.1}, "penalties": {}}
    with pytest.raises(ValueError) as exc:
        mod.score_candidate(POLICY, c)
    assert str(exc.value) == "R9 missing signal:b, penalty:p"


def _write(tmp_path, signals_doc):
    pol = tmp_path / "policy.json"
    sig = tmp_path / "signals.json"
    pol.write_text(json.dumps(POLICY), encoding="utf-8")
    sig.write_text(json.dumps(signals_doc), encoding="utf-8")
    return pol, sig


def test_main_writes_out_and_stdout(mod, tmp_path, monkeypatch, capsys):
    doc = {"evidence_class": "MEASURED", "candidates": [_cand(independent_need_signals=[1, 2], trial_ready=True, evidence_class="IGNORED")]}
    pol, sig = _write(tmp_path, doc)
    out = tmp_path / "deep" / "receipt.json"
    monkeypatch.setattr(sys, "argv", ["s", "--policy", str(pol), "--signals", str(sig), "--out", str(out)])
    mod.main()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload == json.loads(capsys.readouterr().out)
    assert payload["permanent_role_promotion_allowed"] is True
    assert payload["source_evidence_class"] == "MEASURED"
    assert payload["results"][0]["evidence_class"] == "MEASURED"
    assert payload["results"][0]["decision"] == "TRIAL_CANDIDATE"
    assert payload["authority_transfer"] is False


def test_main_without_out_defaults_unproven(mod, tmp_path, monkeypatch, capsys):
    pol, sig = _write(tmp_path, {})
    monkeypatch.setattr(sys, "argv", ["s", "--policy", str(pol), "--signals", str(sig)])
    mod.main()
    payload = json.loads(capsys.readouterr().out)
    assert payload["source_evidence_class"] == "UNPROVEN"
    assert payload["permanent_role_promotion_allowed"] is False
    assert payload["results"] == []
    assert sorted(p.name for p in tmp_path.iterdir()) == ["policy.json", "signals.json"]


def test_real_committed_seed(mod, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [
        "s",
        "--policy", str(CREW_DIR / "ROLE_GAP_POLICY_v1.json"),
        "--signals", str(CREW_DIR / "ROLE_GAP_SIGNALS_SEED_2026-09-13.json"),
    ])
    mod.main()
    payload = json.loads(capsys.readouterr().out)
    assert payload["source_evidence_class"] == "EXPERT_SEEDED_NOT_MEASURED"
    assert payload["permanent_role_promotion_allowed"] is False
    assert payload["results"]
    for row in payload["results"]:
        assert 0.0 <= row["score"] <= 1.0
        assert row["decision"] in {"TRIAL_CANDIDATE", "WATCH_OR_SECOND", "REUSE_TRAIN_TOOL_OR_PRUNE"}
