"""Behavioural tests for mission-control/qps-triage-ultra/crew/score_skill_resolution_pulse.py."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "mission-control" / "qps-triage-ultra" / "crew" / "score_skill_resolution_pulse.py"
SKILLS_REF = "a" * 40
SOURCE_REF = "b" * 40


def _load_module():
    spec = importlib.util.spec_from_file_location("cw_score_skill_resolution_pulse", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mod():
    return _load_module()


def _receipt(skill, **over):
    r = {
        "skill": skill,
        "status": "PASS_SKILL_BUNDLE_RESOLUTION",
        "authority_transfer": False,
        "skills_ref": SKILLS_REF,
        "resolution_mode": "hosted_pr_matrix",
    }
    r.update(over)
    return r


def _ledger(prediction=3, extra_pending=None, calibration=None):
    pending = [
        {"target_pulse": "SKILL_P1", "metric": "skill_bundles_resolvable", "prediction": prediction, "actual": None},
        {"target_pulse": "SKILL_P2", "metric": "modes", "prediction": 2, "actual": None},
    ]
    pending.extend(extra_pending or [])
    doc = {"schema": "ledger", "pending": pending}
    if calibration is not None:
        doc["calibration"] = calibration
    return doc


def _setup(tmp_path, ledger, receipts):
    ledger_path = tmp_path / "ledger.json"
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    rdir = tmp_path / "receipts"
    rdir.mkdir()
    for i, r in enumerate(receipts):
        (rdir / "r{0}.json".format(i)).write_text(json.dumps(r), encoding="utf-8")
    (rdir / "ignored.txt").write_text("not json", encoding="utf-8")
    return ledger_path, rdir


def _run(mod, monkeypatch, tmp_path, ledger_path, rdir):
    score_out = tmp_path / "out" / "score.json"
    rolled_out = tmp_path / "out2" / "rolled.json"
    monkeypatch.setattr(sys, "argv", [
        "score",
        "--ledger", str(ledger_path),
        "--receipts", str(rdir),
        "--score-out", str(score_out),
        "--rolled-ledger-out", str(rolled_out),
        "--skills-ref", SKILLS_REF,
        "--source-ref", SOURCE_REF,
    ])
    mod.main()
    return (
        json.loads(score_out.read_text(encoding="utf-8")),
        json.loads(rolled_out.read_text(encoding="utf-8")),
    )


ALL = ["math", "plots", "math-plots"]


def test_exact_hit_rolls_ledger_and_issues_p3(mod, tmp_path, monkeypatch, capsys):
    ledger_path, rdir = _setup(tmp_path, _ledger(), [_receipt(s) for s in ALL])
    score, rolled = _run(mod, monkeypatch, tmp_path, ledger_path, rdir)
    assert score["forecast_status"] == "SCORED_EXACT_HIT"
    assert score["prediction"] == 3 and score["actual"] == 3 and score["absolute_error"] == 0
    assert score["individual_receipts"] == ["math", "math-plots", "plots"]
    assert score["skills_ref"] == SKILLS_REF and score["source_ref"] == SOURCE_REF
    assert score["calibration"]["n_scored"] == 1
    assert score["calibration"]["probability_calibration_applied"] is False
    hist = rolled["history"][-1]
    assert hist["status"] == "SCORED_EXACT_HIT"
    assert hist["observed_source_ref"] == SOURCE_REF
    targets = [p["target_pulse"] for p in rolled["pending"]]
    assert targets == ["SKILL_P2", "SKILL_P3"]
    assert rolled["pending"][1]["prediction"] == 3
    assert rolled["as_of"] == "2026-09-16T22:20:00+02:00"
    assert json.loads(capsys.readouterr().out) == score


def test_miss_and_existing_p3_and_calibration(mod, tmp_path, monkeypatch):
    p3 = {"target_pulse": "SKILL_P3", "metric": "x", "prediction": 9}
    ledger = _ledger(prediction=5, extra_pending=[p3], calibration={"n_scored": "2"})
    ledger["history"] = [{"old": True}]
    ledger_path, rdir = _setup(tmp_path, ledger, [_receipt(s) for s in ALL])
    score, rolled = _run(mod, monkeypatch, tmp_path, ledger_path, rdir)
    assert score["forecast_status"] == "SCORED_MISS"
    assert score["absolute_error"] == 2
    assert rolled["calibration"]["n_scored"] == 3
    assert rolled["calibration"]["last_absolute_error"] == 2
    assert len(rolled["history"]) == 2
    assert [p for p in rolled["pending"] if p["target_pulse"] == "SKILL_P3"] == [p3]


def test_input_ledger_not_mutated(mod, tmp_path, monkeypatch):
    ledger = _ledger()
    ledger_path, rdir = _setup(tmp_path, ledger, [_receipt(s) for s in ALL])
    before = ledger_path.read_text(encoding="utf-8")
    _run(mod, monkeypatch, tmp_path, ledger_path, rdir)
    assert ledger_path.read_text(encoding="utf-8") == before


@pytest.mark.parametrize(
    "receipts,match",
    [
        ([_receipt("math"), _receipt("plots")], "expected exactly three distinct skill receipts"),
        ([_receipt("math"), _receipt("plots"), _receipt("plots")], "expected exactly three"),
        ([_receipt("math"), _receipt("plots"), _receipt("math-plots"), _receipt("math")], "/ 4"),
        ([_receipt("math"), _receipt("plots"), _receipt("other")], "expected exactly three"),
        ([_receipt("math", status="FAIL"), _receipt("plots"), _receipt("math-plots")], "non-pass receipt for math"),
        ([_receipt("math", authority_transfer=None), _receipt("plots"), _receipt("math-plots")], "authority transfer must remain false"),
        ([_receipt("math", skills_ref="c"), _receipt("plots"), _receipt("math-plots")], "skills ref mismatch for math"),
        ([_receipt("math", resolution_mode="local"), _receipt("plots"), _receipt("math-plots")], "unexpected resolution mode for math"),
    ],
)
def test_receipt_validation_failures(mod, tmp_path, monkeypatch, receipts, match):
    ledger_path, rdir = _setup(tmp_path, _ledger(), receipts)
    with pytest.raises(SystemExit) as exc:
        _run(mod, monkeypatch, tmp_path, ledger_path, rdir)
    assert match in str(exc.value)
    assert not (tmp_path / "out" / "score.json").exists()


def test_missing_frozen_prediction(mod, tmp_path, monkeypatch):
    ledger = {"pending": [{"target_pulse": "SKILL_P1", "metric": "other", "prediction": 3}]}
    ledger_path, rdir = _setup(tmp_path, ledger, [_receipt(s) for s in ALL])
    with pytest.raises(SystemExit) as exc:
        _run(mod, monkeypatch, tmp_path, ledger_path, rdir)
    assert str(exc.value) == "missing frozen SKILL_P1 prediction"


def test_no_pending_key_is_missing_prediction(mod, tmp_path, monkeypatch):
    ledger_path, rdir = _setup(tmp_path, {}, [_receipt(s) for s in ALL])
    with pytest.raises(SystemExit) as exc:
        _run(mod, monkeypatch, tmp_path, ledger_path, rdir)
    assert "missing frozen" in str(exc.value)


def test_required_args(mod, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["score"])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 2
