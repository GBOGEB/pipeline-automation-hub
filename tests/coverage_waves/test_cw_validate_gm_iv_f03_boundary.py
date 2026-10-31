"""Behavioural tests for mission-control/grand-missions/validate_gm_iv_f03_boundary.py."""
import copy
import importlib.util
import json
import runpy
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_PATH = REPO_ROOT / "mission-control" / "grand-missions" / "validate_gm_iv_f03_boundary.py"


def _load():
    spec = importlib.util.spec_from_file_location("cw_validate_gm_iv_f03_boundary", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


f03 = _load()
_DROP = object()

GOOD = {
    "schema": "gbogeb-level1-ssot/v1",
    "repo": "GBOGEB/codespaces-jupyter",
    "role": "REPRODUCIBLE_NOTEBOOK_RUNTIME_PRODUCER",
    "authority_transfer": False,
    "authority": {"must_not": sorted(f03.EXPECTED_MUST_NOT) + ["extra boundary"]},
    "promotion_requires": "a notebook run that executes >0 cells twice with identical output",
}


def _mut(**changes):
    d = copy.deepcopy(GOOD)
    for k, v in changes.items():
        if v is _DROP:
            d.pop(k)
        else:
            d[k] = v
    return d


def _run(tmp_path, monkeypatch, data):
    p = tmp_path / "ssot.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["validate_gm_iv_f03_boundary.py", str(p)])
    f03.main()


def test_valid_ssot_prints_all_validations(tmp_path, monkeypatch, capsys):
    _run(tmp_path, monkeypatch, GOOD)
    assert capsys.readouterr().out.splitlines() == [
        "validated F03 Level-1 SSOT identity",
        "validated F03 runtime producer role",
        "validated F03 authority_transfer=false",
        "validated F03 must_not authority boundary",
        "F03 authority validation passed",
    ]


@pytest.mark.parametrize("data,message", [
    (_mut(schema="other/v1"), "schema must be gbogeb-level1-ssot/v1"),
    (_mut(repo="GBOGEB/other"), "repo must be GBOGEB/codespaces-jupyter"),
    (_mut(role="ENGINEERING_AUTHORITY"), "role must be REPRODUCIBLE_NOTEBOOK_RUNTIME_PRODUCER"),
    (_mut(authority_transfer=True), "authority_transfer must be false"),
    (_mut(authority_transfer=_DROP), "authority_transfer must be false"),
    (_mut(authority={"must_not": ["override child authority"]}),
     "missing must_not boundary: promote notebook execution to engineering authority, "
     "promote runtime PASS to domain validation"),
    (_mut(authority=_DROP),
     "missing must_not boundary: override child authority, promote notebook execution to "
     "engineering authority, promote runtime PASS to domain validation"),
    (_mut(promotion_requires="executes cells once"), "promotion_requires must require >0 cells twice"),
    (_mut(promotion_requires=_DROP), "promotion_requires must require >0 cells twice"),
])
def test_failures_have_exact_messages(tmp_path, monkeypatch, capsys, data, message):
    with pytest.raises(SystemExit) as exc:
        _run(tmp_path, monkeypatch, data)
    assert exc.value.code == 1
    assert capsys.readouterr().out == "F03 authority validation failed: " + message + "\n"


def test_fail_helper_exits_1(capsys):
    with pytest.raises(SystemExit) as exc:
        f03.fail("boom")
    assert exc.value.code == 1
    assert capsys.readouterr().out == "F03 authority validation failed: boom\n"


def test_main_guard_runs_validation(tmp_path, monkeypatch, capsys):
    p = tmp_path / "ssot.json"
    p.write_text(json.dumps(GOOD), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["x", str(p)])
    runpy.run_path(str(MOD_PATH), run_name="__main__")
    assert capsys.readouterr().out.endswith("F03 authority validation passed\n")
