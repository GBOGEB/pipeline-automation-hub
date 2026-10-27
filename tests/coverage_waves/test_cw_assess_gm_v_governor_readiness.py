"""Behavioural tests for mission-control/grand-missions/assess_gm_v_governor_readiness.py."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GM_DIR = REPO_ROOT / "mission-control" / "grand-missions"
MOD_PATH = GM_DIR / "assess_gm_v_governor_readiness.py"
CONTRACT = "GM_V_GOVERNOR_READINESS_CONTRACT.json"
REG = "GRAND_MISSION_REGISTRY.json"


def _load():
    spec = importlib.util.spec_from_file_location("cw_assess_gm_v_governor_readiness", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def mod():
    return _load()


def _inputs():
    return {n: json.loads((GM_DIR / n).read_text(encoding="utf-8")) for n in (CONTRACT, REG)}


def _write(tmp_path, data):
    root = tmp_path / "gm"
    root.mkdir()
    for n, obj in data.items():
        (root / n).write_text(json.dumps(obj), encoding="utf-8")
    return root


def _run(mod, monkeypatch, tmp_path, data):
    monkeypatch.setattr(mod, "ROOT", _write(tmp_path, data))
    out = tmp_path / "receipt.json"
    monkeypatch.setattr(sys, "argv", ["prog", "--source-sha", "s9", "--out", str(out)])
    return out


def _failing(receipt):
    return [c["check"] for c in receipt["checks"] if c["result"] == "FAIL"]


def test_add_appends_pass_and_fail(mod):
    checks = []
    mod.add(checks, "a", True, 1)
    mod.add(checks, "b", False, {"x": 2})
    assert checks == [
        {"check": "a", "result": "PASS", "detail": 1},
        {"check": "b", "result": "FAIL", "detail": {"x": 2}},
    ]


def test_structural_pass_external_hold_withholds(mod, monkeypatch, tmp_path, capsys):
    data = _inputs()
    out = _run(mod, monkeypatch, tmp_path, data)
    assert mod.main() is None
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["result"] == "WITHHOLD"
    assert receipt["decision"] == data[CONTRACT]["decision_semantics"]["WITHHOLD"]
    assert receipt["gm_v_launch_authorized"] is False
    assert _failing(receipt) == []
    assert len(receipt["checks"]) == 7
    assert receipt["source_sha"] == "s9"
    op = data[CONTRACT]["prerequisites"]["operational_availability"]
    assert receipt["operational_availability"] == op["current_result"]
    assert receipt["reentry_trigger"] == op["reentry_trigger"]
    assert receipt["boundary"] == data[CONTRACT]["readiness_boundary"]
    assert json.loads(capsys.readouterr().out) == receipt


def test_operational_availability_met_is_ready(mod, monkeypatch, tmp_path):
    data = _inputs()
    op = data[CONTRACT]["prerequisites"]["operational_availability"]
    op["required_result"] = op["current_result"]
    out = _run(mod, monkeypatch, tmp_path, data)
    mod.main()
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["result"] == "READY"
    assert receipt["decision"] == data[CONTRACT]["decision_semantics"]["READY"]
    assert receipt["gm_v_launch_authorized"] is True


def _gm(mid, key, value):
    def apply(data):
        for m in data[REG]["grand_missions"]:
            if m["id"] == mid:
                m[key] = value
    return apply


def _pre(section, key, value):
    def apply(data):
        data[CONTRACT]["prerequisites"][section][key] = value
    return apply


def _probe_steps(data):
    obs = data[CONTRACT]["prerequisites"]["operational_availability"]["latest_exact_head_observation"]
    obs["release_runner_probe_jobs"][0]["steps_executed"] = 4


def _evidence(data):
    for m in data[REG]["grand_missions"]:
        if m["id"] == "GM-IV":
            m["active_8_of_8_evidence"]["artifact_id"] = 1


def _no_evidence(data):
    for m in data[REG]["grand_missions"]:
        if m["id"] == "GM-IV":
            m.pop("active_8_of_8_evidence")


@pytest.mark.parametrize(
    "mutate, failing",
    [
        (_gm("GM-IV", "children", ["c"]), ["01_gm_iv_active8_control"]),
        (_evidence, ["02_active8_readiness_evidence_retained"]),
        (_no_evidence, ["02_active8_readiness_evidence_retained"]),
        (_pre("post_active8_repeat_control", "artifact_digest", "md5:0"), ["03_repeat_control_bound"]),
        (_pre("runtime_capability_capacity", "concurrency_capacity_claimed", True), ["04_runtime_capability_capacity_exact"]),
        (_probe_steps, ["05_external_operational_availability_observation_bound"]),
        (_gm("GM-V", "crew_posture", "ALLOCATED"), ["06_gm_v_still_held"]),
        (lambda d: d[REG].__setitem__("authority_transfer", True), ["07_no_authority_or_child_binding"]),
    ],
)
def test_structural_failure_exits_nonzero(mod, monkeypatch, tmp_path, mutate, failing):
    data = _inputs()
    mutate(data)
    out = _run(mod, monkeypatch, tmp_path, data)
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 1
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["result"] == "FAIL"
    assert receipt["decision"] == data[CONTRACT]["decision_semantics"]["WITHHOLD"]
    assert receipt["gm_v_launch_authorized"] is False
    assert _failing(receipt) == failing


def test_structural_failure_overrides_operational_ready(mod, monkeypatch, tmp_path):
    data = _inputs()
    op = data[CONTRACT]["prerequisites"]["operational_availability"]
    op["required_result"] = op["current_result"]
    _gm("GM-V", "state", "LAUNCHED")(data)
    out = _run(mod, monkeypatch, tmp_path, data)
    with pytest.raises(SystemExit):
        mod.main()
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["result"] == "FAIL" and receipt["gm_v_launch_authorized"] is False


def test_real_committed_data_withholds(mod, monkeypatch, tmp_path):
    out = tmp_path / "real.json"
    monkeypatch.setattr(sys, "argv", ["prog", "--source-sha", "real", "--out", str(out)])
    mod.main()
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["result"] == "WITHHOLD"
    assert receipt["gm_v_state"] == "HELD"
