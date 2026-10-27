"""Behavioural tests for scripts/validate_lm11_qps_wave_federation.py."""
from __future__ import annotations

import importlib.util
import json
import runpy
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "validate_lm11_qps_wave_federation.py"


def _load():
    spec = importlib.util.spec_from_file_location("cw_validate_lm11_qps_wave_federation", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = _load()
SURFACES = ("CURRENT", "CONTRACT", "ATLAS", "RECEIPT", "REGISTER")


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Copy the committed surfaces into tmp_path and repoint the module there."""
    paths = {}
    for name in SURFACES:
        src = getattr(m, name)
        dst = tmp_path / name.lower() / src.name
        dst.parent.mkdir()
        dst.write_bytes(src.read_bytes())
        paths[name] = dst
        monkeypatch.setattr(m, name, dst)
    monkeypatch.setattr(m, "ROOT", tmp_path)
    return paths


def _replace(path, old, new):
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")


def test_read_missing_surface_reports_relative_path(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "ROOT", tmp_path)
    with pytest.raises(AssertionError, match="missing required surface: nope.yaml"):
        m.read(tmp_path / "nope.yaml")
    f = tmp_path / "ok.txt"
    f.write_text("hi", encoding="utf-8")
    assert m.read(f) == "hi"


def test_require():
    m.require("abc", "b", "lbl")
    with pytest.raises(AssertionError, match="lbl: missing 'z'"):
        m.require("abc", "z", "lbl")


def test_extract_launch_gaps():
    receipt = "x:\n  numeric_gaps:\n    - W105\n    - W113\n  guard: G\n"
    assert m.extract_launch_gaps(receipt) == {105, 113}
    with pytest.raises(AssertionError, match="numeric_gaps block not found"):
        m.extract_launch_gaps("numeric_gaps: []\n")


def test_main_passes_on_committed_copy(env, capsys):
    m.main()
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "PASS_LM11_MISSIONCONTROL_FEDERATION_STATIC"
    assert out["launch_numeric_gap_count"] == 25
    assert out["first_red"] == "LM11_FIRST_GREATER_THAN_ZERO_STEP_EXACT_HEAD_GRAPH_RUN"


def test_main_missing_surface(env):
    env["ATLAS"].unlink()
    with pytest.raises(AssertionError, match="missing required surface"):
        m.main()


@pytest.mark.parametrize(
    "key,path",
    [
        ("authority_transfer", None),
        ("formal_credit_delta", None),
        ("destructive_delete", "projection_rules"),
        ("measured_graph_metrics_available", "runtime_boundary"),
    ],
)
def test_main_rejects_contract_drift(env, key, path):
    c = env["CONTRACT"]
    d = json.loads(c.read_text(encoding="utf-8"))
    target = d if path is None else d[path]
    target[key] = 1 if key == "formal_credit_delta" else True
    c.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(AssertionError):
        m.main()


@pytest.mark.parametrize(
    "surface,needle,label",
    [
        ("CURRENT", "mission_id: LM-11", "current mission control"),
        ("REGISTER", "missioncontrol_checks: PASS_6_OF_6", "official register"),
        ("RECEIPT", "graph_execution_claimed: false", "child federation receipt"),
        ("RECEIPT", "triage_wave_directory_count_W103_to_W264: 137", "launch projection"),
        ("ATLAS", "## 9. Satellite / federation node view", "atlas"),
    ],
)
def test_main_rejects_missing_needle(env, surface, needle, label):
    _replace(env[surface], needle, "REDACTED_NEEDLE")
    with pytest.raises(AssertionError, match=label):
        m.main()


def test_main_rejects_gap_set_drift(env):
    _replace(env["RECEIPT"], "W105", "W106")
    with pytest.raises(AssertionError, match="launch gap set drift"):
        m.main()


def test_real_committed_data_via_cli(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [str(MODULE_PATH)])
    runpy.run_path(str(MODULE_PATH), run_name="__main__")
    assert "PASS_LM11_MISSIONCONTROL_FEDERATION_STATIC" in capsys.readouterr().out
