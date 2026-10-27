"""Behavioural tests for mission-control/grand-missions/analytics/validate_gm_i_a_multiclock_3pstar_mip.py."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
AN_DIR = REPO_ROOT / "mission-control" / "grand-missions" / "analytics"
MOD_PATH = AN_DIR / "validate_gm_i_a_multiclock_3pstar_mip.py"
CONTROL = "GM_I_A_MULTI_CLOCK_3PSTAR_MIP_v1.json"
CURRENT = "GM_I_A_MULTI_CLOCK_CURRENT_v1.json"


def _load():
    spec = importlib.util.spec_from_file_location("cw_validate_gm_i_a_multiclock_3pstar_mip", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def mod():
    return _load()


def _control():
    return {
        "method": "3PSTAR_THEN_MIP_SEQUENTIAL",
        "authority_transfer": False,
        "formal_credit_delta": 0,
        "engineering_credit_delta": 0,
        "three_pstar": {"Refresh": {"result": "PASS"}, "Probe": {"result": "PASS_X"}, "Rank": {"result": "PASS_Y"}},
        "mip": {
            "Modernize": {"result": "PASS"},
            "Innovate": {"result": "PASS_BOUNDED"},
            "Perpetuate": {"result": "PASS_REPOSITORY_NATIVE"},
        },
        "next": {"state": "NEXT"},
    }


def _current(n=2):
    return {
        "measured_pulses": n,
        "pca": {"status": "WITHHELD_N%d_OF_27" % n},
        "bt": {"status": "WITHHELD_N%d_NO_STRONG_CONNECTIVITY" % n},
        "next_pulse": "GM-I-A-MCLOCK-P%03d" % (n + 1),
        "latest_metrics": {
            "pulse_id": "GM-I-A-MCLOCK-P%03d" % n,
            "queue_fraction": 0.5,
            "pressure_hhi": 0.3,
            "effective_clock_count": 3.3,
            "top4_fraction": 0.9,
        },
    }


def _readiness(current):
    n = current["measured_pulses"]
    latest = current["latest_metrics"]
    return {
        "schema": "missioncontrol.gm_i_a.multiclock_readiness.v2",
        "measured_pulses": n,
        "feature_count_p": 9,
        "pca": {
            "status": "DEFER_INSUFFICIENT_COMPARABLE_MEASURED_PULSES",
            "minimum_rows_required": 27,
            "rows_remaining_to_minimum": max(0, 27 - n),
            "covariance_rank_upper_bound": min(9, max(0, n - 1)),
        },
        "bt_reverse_pressure": {
            "status": "DEFER_NO_FINITE_MLE_REPEAT_STRUCTURE",
            "minimum_repeat_pulses": 3,
            "repeat_pulses_remaining": max(0, 3 - n),
            "directed_win_graph_strongly_connected": False,
            "bidirectional_pair_count": 0,
        },
        "latest_pulse_descriptive_pressure": dict(latest),
        "authority_transfer": False,
        "formal_credit_delta": 0,
    }


def _run(mod, monkeypatch, tmp_path, control, current, readiness, with_out=True):
    here = tmp_path / "an"
    here.mkdir()
    (here / CONTROL).write_text(json.dumps(control), encoding="utf-8")
    (here / CURRENT).write_text(json.dumps(current), encoding="utf-8")
    rp = tmp_path / "readiness.json"
    rp.write_text(json.dumps(readiness), encoding="utf-8")
    monkeypatch.setattr(mod, "HERE", here)
    out = tmp_path / "receipt.json"
    argv = ["prog", "--readiness", str(rp)]
    if with_out:
        argv += ["--out", str(out)]
    monkeypatch.setattr(sys, "argv", argv)
    return mod.main(), out


def test_require_passes_and_fails_with_prefixed_message(mod):
    assert mod.require(True, "ok") is None
    with pytest.raises(SystemExit) as exc:
        mod.require(False, "boom")
    assert exc.value.code == "FAIL boom"


def test_pass_writes_out_and_prints_same_text(mod, monkeypatch, tmp_path, capsys):
    cur = _current()
    rc, out = _run(mod, monkeypatch, tmp_path, _control(), cur, _readiness(cur))
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert capsys.readouterr().out == text
    receipt = json.loads(text)
    assert receipt["status"] == "PASS_3PSTAR_MIP_REPOSITORY_CONTROL"
    assert receipt["failed"] == []
    assert len(receipt["checks"]) == 12 and all(receipt["checks"].values())
    assert receipt["next"] == {"state": "NEXT"}
    assert receipt["authority_transfer"] is False and receipt["formal_credit_delta"] == 0


def test_without_out_only_prints(mod, monkeypatch, tmp_path, capsys):
    cur = _current()
    rc, out = _run(mod, monkeypatch, tmp_path, _control(), cur, _readiness(cur), with_out=False)
    assert rc == 0
    assert not out.exists()
    assert json.loads(capsys.readouterr().out)["status"] == "PASS_3PSTAR_MIP_REPOSITORY_CONTROL"


def test_gate_clamps_at_or_above_minimum(mod, monkeypatch, tmp_path):
    # With 30 pulses remaining counts clamp to 0 and the covariance rank caps at 9.
    cur = _current(30)
    r = _readiness(cur)
    assert r["pca"]["rows_remaining_to_minimum"] == 0
    assert r["pca"]["covariance_rank_upper_bound"] == 9
    rc, _ = _run(mod, monkeypatch, tmp_path, _control(), cur, r)
    assert rc == 0


def _c(path, value):
    def apply(control, current, readiness):
        obj = control
        for k in path[:-1]:
            obj = obj[k]
        obj[path[-1]] = value
    return apply


def _r(path, value):
    def apply(control, current, readiness):
        obj = readiness
        for k in path[:-1]:
            obj = obj[k]
        obj[path[-1]] = value
    return apply


def _cur(path, value):
    def apply(control, current, readiness):
        obj = current
        for k in path[:-1]:
            obj = obj[k]
        obj[path[-1]] = value
    return apply


@pytest.mark.parametrize(
    "mutate, failed",
    [
        (_c(["method"], "OTHER"), ["method"]),
        (_c(["formal_credit_delta"], 1), ["authority"]),
        (_c(["three_pstar", "Probe", "result"], "FAIL"), ["three_pstar"]),
        (_c(["mip", "Innovate", "result"], "PASS"), ["mip"]),
        (_r(["schema"], "v1"), ["readiness_schema"]),
        (_r(["feature_count_p"], 8), ["geometry"]),
        (_r(["pca", "covariance_rank_upper_bound"], 5), ["pca_gate"]),
        (_r(["bt_reverse_pressure", "directed_win_graph_strongly_connected"], True), ["bt_gate"]),
        (_r(["bt_reverse_pressure", "bidirectional_pair_count"], -1), ["bt_gate"]),
        (_r(["latest_pulse_descriptive_pressure", "queue_fraction"], 0.51), ["queue_separation"]),
        (_r(["latest_pulse_descriptive_pressure", "pulse_id"], "P999"), ["concentration"]),
        (_r(["latest_pulse_descriptive_pressure", "effective_clock_count"], 3.4), ["concentration"]),
        (_cur(["next_pulse"], "GM-I-A-MCLOCK-P002"), ["current_pointer"]),
        (_cur(["bt", "status"], "OPEN"), ["current_pointer"]),
        (_r(["authority_transfer"], True), ["no_promotion"]),
        (_c(["engineering_credit_delta"], 1), ["no_promotion"]),
    ],
)
def test_single_check_failure(mod, monkeypatch, tmp_path, capsys, mutate, failed):
    control, current = _control(), _current()
    readiness = _readiness(current)
    mutate(control, current, readiness)
    rc, out = _run(mod, monkeypatch, tmp_path, control, current, readiness)
    assert rc == 1
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["status"] == "FAIL_3PSTAR_MIP_REPOSITORY_CONTROL"
    assert receipt["failed"] == failed


def test_out_of_range_queue_fraction_fails_even_if_matching(mod, monkeypatch, tmp_path):
    current = _current()
    current["latest_metrics"]["queue_fraction"] = 1.5
    readiness = _readiness(current)
    rc, out = _run(mod, monkeypatch, tmp_path, _control(), current, readiness)
    assert rc == 1
    assert json.loads(out.read_text(encoding="utf-8"))["failed"] == ["queue_separation"]


def test_real_control_and_current_with_consistent_readiness(mod, monkeypatch, tmp_path):
    # Real committed control/current pointer; readiness is a CI artifact so it is
    # derived from the committed current pointer here.
    current = json.loads((AN_DIR / CURRENT).read_text(encoding="utf-8"))
    rp = tmp_path / "readiness.json"
    rp.write_text(json.dumps(_readiness(current)), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["prog", "--readiness", str(rp)])
    assert mod.main() == 0
