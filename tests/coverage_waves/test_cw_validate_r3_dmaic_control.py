"""Behavioural tests for mission-control/grand-missions/validate_r3_dmaic_control.py."""
import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_DIR = REPO_ROOT / "mission-control" / "grand-missions"
MOD_PATH = MOD_DIR / "validate_r3_dmaic_control.py"
REAL = MOD_DIR / "R3_DMAIC_CONTROL_CURRENT_v1.json"


def _load():
    spec = importlib.util.spec_from_file_location("cw_validate_r3_dmaic_control", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = _load()


def _doc():
    return json.loads(REAL.read_text(encoding="utf-8"))


def test_fail_prefix():
    with pytest.raises(SystemExit) as exc:
        m.fail("x")
    assert str(exc.value) == "R3_DMAIC_CONTROL_FAIL: x"


def test_validate_real_committed_control_passes():
    checks = m.validate(_doc())
    assert set(checks) == {
        "schema", "authority", "three_pr_exact", "mip_m_exact", "ranked_defects", "historical_kpi",
        "prevention_kpi", "closure_kpi", "protected_surface_set", "r3_current", "three_pc",
        "tooling_3p3", "rules", "guards",
    }
    assert all(checks.values())


@pytest.mark.parametrize(
    "mutate, failed",
    [
        (lambda d: d.update(wave="W284"), "schema"),
        (lambda d: d.update(formal_credit_delta=1), "authority"),
        (lambda d: d["proofs"]["three_pr"].update(pr=261), "three_pr_exact"),
        (lambda d: d["proofs"]["mip_modernize_qps"].update(result="X"), "mip_m_exact"),
        (lambda d: d["ranked_defects"].update(total=6), "ranked_defects"),
        (lambda d: d["kpi"].update(historical_r3_median_merge_lead_seconds=170), "historical_kpi"),
        (lambda d: d["kpi"].update(false_accept_count=1), "prevention_kpi"),
        (lambda d: d["kpi"].update(qps_control_trigger_validation_coverage=0.5), "closure_kpi"),
        (lambda d: d["kpi"].update(protected_control_surfaces=[]), "protected_surface_set"),
        (lambda d: d["current_r3"].update(r4="NEXT"), "r3_current"),
        (lambda d: d["three_pc"].update(Commit="PASS"), "three_pc"),
        (lambda d: d["tooling_3p3"].update(r3_release_3p3_authorized=True), "tooling_3p3"),
        (lambda d: d["control_rules"].update(unknown_is_not_zero=False), "rules"),
        (lambda d: d["guards"].update(authority_transfer=True), "guards"),
    ],
)
def test_validate_reports_exact_failed_check(mutate, failed):
    d = _doc()
    mutate(d)
    with pytest.raises(SystemExit) as exc:
        m.validate(d)
    assert str(exc.value) == "R3_DMAIC_CONTROL_FAIL: " + json.dumps({failed: False})


def test_validate_missing_section_raises_keyerror():
    d = _doc()
    del d["kpi"]
    with pytest.raises(KeyError):
        m.validate(d)


def test_self_test_rejects_all_mutations_and_leaves_input():
    d = _doc()
    before = copy.deepcopy(d)
    assert m.self_test(d) is None
    assert d == before


def test_self_test_detects_permissive_validator(monkeypatch):
    monkeypatch.setattr(m, "validate", lambda d: {})
    with pytest.raises(SystemExit) as exc:
        m.self_test(_doc())
    assert str(exc.value) == "R3_DMAIC_CONTROL_FAIL: self-test accepted protected mutation"


def test_main_with_out_and_self_test(tmp_path, monkeypatch, capsys):
    out = tmp_path / "receipt.json"
    monkeypatch.setattr(sys, "argv", ["prog", "--control", str(REAL), "--out", str(out), "--self-test"])
    assert m.main() is None
    printed = capsys.readouterr().out
    assert out.read_text() == printed
    receipt = json.loads(printed)
    assert receipt["status"] == "PASS_W285_MIP_INNOVATE_PERPETUATE_3PC_PROVE"
    assert receipt["schema"] == "missioncontrol.hm01.r3.dmaic_control_receipt.v3"
    assert receipt["three_pc"]["Commit"] == "AUTHORIZED_ON_MERGE"
    assert all(receipt["checks"].values())


def test_main_without_out_skips_self_test(tmp_path, monkeypatch, capsys):
    called = []
    monkeypatch.setattr(m, "self_test", lambda d: called.append(d))
    monkeypatch.setattr(sys, "argv", ["prog", "--control", str(REAL)])
    m.main()
    assert called == []
    assert json.loads(capsys.readouterr().out)["formal_credit_delta"] == 0
    assert list(tmp_path.iterdir()) == []


def test_main_invalid_control_fails(tmp_path, monkeypatch):
    d = _doc()
    d["schema"] = "other"
    src = tmp_path / "c.json"
    src.write_text(json.dumps(d))
    out = tmp_path / "o.json"
    monkeypatch.setattr(sys, "argv", ["prog", "--control", str(src), "--out", str(out)])
    with pytest.raises(SystemExit) as exc:
        m.main()
    assert str(exc.value) == 'R3_DMAIC_CONTROL_FAIL: {"schema": false}'
    assert not out.exists()
