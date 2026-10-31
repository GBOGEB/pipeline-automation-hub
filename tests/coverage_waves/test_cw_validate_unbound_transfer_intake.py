"""Behavioural tests for mission-control/qps-triage-ultra/missions/validate_unbound_transfer_intake.py."""
import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MISSIONS_DIR = REPO_ROOT / "mission-control" / "qps-triage-ultra" / "missions"
MODULE_PATH = MISSIONS_DIR / "validate_unbound_transfer_intake.py"
CONTROL = MISSIONS_DIR / "UNBOUND_TRANSFER_INTAKE_CURRENT_v1.json"


def _load_module():
    spec = importlib.util.spec_from_file_location("cw_validate_unbound_transfer_intake", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mod():
    return _load_module()


@pytest.fixture
def doc():
    return json.loads(CONTROL.read_text(encoding="utf-8"))


def test_fail_prefix(mod):
    with pytest.raises(SystemExit) as exc:
        mod.fail("x")
    assert str(exc.value) == "UNBOUND_TRANSFER_INTAKE_FAIL: x"


def test_real_control_validates(mod, doc):
    checks = mod.validate(doc)
    assert set(checks) >= {"schema", "issue", "authority", "invariants", "disposition"}
    assert all(checks.values())


def test_self_test_passes_on_real_control(mod, doc):
    snapshot = copy.deepcopy(doc)
    assert mod.self_test(doc) is None
    assert doc == snapshot


def _set(path, value):
    def fn(d):
        node = d
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value
    return fn


def _leg(leg, key, value):
    return _set(["scout_reader_census", leg, key], value)


CASES = [
    (_set(["schema"], "v2"), "schema"),
    (_set(["mission_control_issue"], "x#1"), "issue"),
    (_set(["authority_transfer"], None), "authority"),
    (_set(["formal_credit_delta", "release"], 1), "credit_zero"),
    (_set(["source_authority", "exact_head"], "0" * 40), "source_head"),
    (_set(["source_authority", "control_issue"], "x#2"), "source_control"),
    (_leg("leg5_txt_log", "open_routes", 3), "leg5_state"),
    (_leg("leg5_txt_log", "exact_sha_family_count", 0), "unknown_counts_null"),
    (_set(["scout_reader_census", "leg5_txt_log", "known_duplicate_family_example", "aliases"], ["one"]), "known_duplicate_bound"),
    (_leg("leg6_markdown", "authority_created", True), "leg6_control"),
    (_leg("leg9_yml", "streak", "2_OF_5"), "structured_wait"),
    (_set(["queue", 0, "state"], "9_OF_9_CLOSED"), "queue_exact"),
    (_set(["reentry_contract", "trigger"], "ANY"), "reentry_contract"),
    (_set(["invariants"], []), "invariants"),
    (_set(["disposition", "residual_local_coding_pressure"], 1), "disposition"),
]


@pytest.mark.parametrize("mutation,check", CASES)
def test_each_check_rejects_drift(mod, doc, mutation, check):
    mutation(doc)
    with pytest.raises(SystemExit) as exc:
        mod.validate(doc)
    msg = str(exc.value)
    assert msg.startswith("UNBOUND_TRANSFER_INTAKE_FAIL: ")
    failed = json.loads(msg.split(": ", 1)[1])
    assert failed == {check: False}


def test_empty_document_fails_every_check(mod):
    with pytest.raises(SystemExit) as exc:
        mod.validate({})
    failed = json.loads(str(exc.value).split(": ", 1)[1])
    assert "schema" in failed and "queue_exact" in failed
    assert "structured_wait" in failed


def test_self_test_detects_validator_that_accepts_mutation(mod, doc, monkeypatch):
    monkeypatch.setattr(mod, "validate", lambda d: {})
    with pytest.raises(SystemExit) as exc:
        mod.self_test(doc)
    assert str(exc.value) == "UNBOUND_TRANSFER_INTAKE_FAIL: self-test accepted protected mutation"


def test_main_with_out_and_self_test(mod, tmp_path, monkeypatch, capsys):
    out = tmp_path / "receipt.json"
    monkeypatch.setattr(sys, "argv", ["v", "--control", str(CONTROL), "--out", str(out), "--self-test"])
    mod.main()
    receipt = json.loads(out.read_text())
    assert receipt == json.loads(capsys.readouterr().out)
    assert receipt["status"] == "PASS_UNBOUND_TRANSFER_RECEIVER"
    assert receipt["source_head"] == mod.EXPECTED_SOURCE_HEAD
    assert receipt["authority_transfer"] is False
    assert all(receipt["checks"].values())


def test_main_stdout_only_and_invalid_control(mod, tmp_path, monkeypatch, capsys, doc):
    monkeypatch.setattr(sys, "argv", ["v", "--control", str(CONTROL)])
    mod.main()
    assert json.loads(capsys.readouterr().out)["formal_credit_delta"] == 0

    doc["authority_transfer"] = True
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(doc), encoding="utf-8")
    out = tmp_path / "never.json"
    monkeypatch.setattr(sys, "argv", ["v", "--control", str(bad), "--out", str(out)])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert "authority" in str(exc.value)
    assert not out.exists()
