"""Behavioural tests for mission-control/grand-missions/validate_r3_dmaic_w285_3pr.py."""
import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_DIR = REPO_ROOT / "mission-control" / "grand-missions"
MOD_PATH = MOD_DIR / "validate_r3_dmaic_w285_3pr.py"
REAL = MOD_DIR / "R3_DMAIC_W285_3PR_REFRESH_v1.json"


def _load():
    spec = importlib.util.spec_from_file_location("cw_validate_r3_dmaic_w285_3pr", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = _load()


def _doc():
    return json.loads(REAL.read_text(encoding="utf-8"))


def _synthetic():
    return {
        "schema": "missioncontrol.hm01.r3.dmaic_w285_3pr_refresh.v1",
        "issue": "GBOGEB/pipeline-automation-hub#209",
        "method": "3PR",
        "authority_transfer": False,
        "formal_credit_delta": 0,
        "refresh": copy.deepcopy(m.EXPECTED_REFRESH),
        "probe": copy.deepcopy(m.EXPECTED_PROBE),
        "rank": copy.deepcopy(m.EXPECTED_RANK),
        "guards": copy.deepcopy(m.EXPECTED_GUARDS),
        "next": m.EXPECTED_NEXT,
    }


def test_fail_prefix():
    with pytest.raises(SystemExit) as exc:
        m.fail("boom")
    assert str(exc.value) == "W285_3PR_FAIL: boom"


def test_real_committed_receipt_validates():
    checks = m.validate(_doc())
    assert len(checks) == 10 and all(checks.values())


def test_synthetic_receipt_validates():
    assert all(m.checks_for(_synthetic()).values())


@pytest.mark.parametrize("value, ok", [(0, True), (False, False), (0.0, False), (1, False), (None, False), ("0", False)])
def test_formal_credit_must_be_int_zero_not_bool(value, ok):
    d = _synthetic()
    d["formal_credit_delta"] = value
    assert m.checks_for(d)["formal_credit"] is ok


@pytest.mark.parametrize(
    "key, value",
    [
        ("schema", "other"),
        ("issue", "x#1"),
        ("method", "2PR"),
        ("authority", None),
        ("refresh_exact", {}),
        ("probe_exact", {}),
        ("rank_exact", []),
        ("guards_exact", {}),
        ("next_exact", "ADVANCE_R4"),
    ],
)
def test_validate_reports_exact_failed_check(key, value):
    field = {
        "authority": "authority_transfer",
        "refresh_exact": "refresh",
        "probe_exact": "probe",
        "rank_exact": "rank",
        "guards_exact": "guards",
        "next_exact": "next",
    }.get(key, key)
    d = _synthetic()
    d[field] = value
    with pytest.raises(SystemExit) as exc:
        m.validate(d)
    assert str(exc.value) == "W285_3PR_FAIL: " + json.dumps({key: False})


def test_validate_empty_doc_lists_all_failures():
    with pytest.raises(SystemExit) as exc:
        m.validate({})
    failed = json.loads(str(exc.value).split(": ", 1)[1])
    assert len(failed) == 10 and not any(failed.values())


def test_self_test_rejects_mutations_without_mutating_input():
    d = _synthetic()
    before = copy.deepcopy(d)
    assert m.self_test(d) is None
    assert d == before


def test_self_test_detects_permissive_validator(monkeypatch):
    monkeypatch.setattr(m, "validate", lambda doc: {})
    with pytest.raises(SystemExit) as exc:
        m.self_test(_synthetic())
    assert str(exc.value) == "W285_3PR_FAIL: self-test accepted protected mutation"


def test_main_real_with_out_and_self_test(tmp_path, monkeypatch, capsys):
    out = tmp_path / "r.json"
    monkeypatch.setattr(sys, "argv", ["prog", "--receipt", str(REAL), "--out", str(out), "--self-test"])
    assert m.main() is None
    printed = capsys.readouterr().out
    assert out.read_text() == printed
    receipt = json.loads(printed)
    assert receipt["status"] == "PASS_3PR_REFRESH_PROBE_RANK"
    assert receipt["schema"] == "missioncontrol.hm01.r3.dmaic_w285_3pr_receipt.v2"
    assert receipt["next"] == m.EXPECTED_NEXT
    assert receipt["rank"] == m.EXPECTED_RANK


def test_main_without_out_or_self_test(tmp_path, monkeypatch, capsys):
    src = tmp_path / "in.json"
    src.write_text(json.dumps(_synthetic()))
    called = []
    monkeypatch.setattr(m, "self_test", lambda d: called.append(1))
    monkeypatch.setattr(sys, "argv", ["prog", "--receipt", str(src)])
    m.main()
    assert called == []
    assert json.loads(capsys.readouterr().out)["authority_transfer"] is False
    assert sorted(p.name for p in tmp_path.iterdir()) == ["in.json"]


def test_main_invalid_receipt(tmp_path, monkeypatch):
    d = _synthetic()
    d["next"] = "ADVANCE_R4"
    src = tmp_path / "in.json"
    src.write_text(json.dumps(d))
    monkeypatch.setattr(sys, "argv", ["prog", "--receipt", str(src)])
    with pytest.raises(SystemExit) as exc:
        m.main()
    assert str(exc.value) == 'W285_3PR_FAIL: {"next_exact": false}'
