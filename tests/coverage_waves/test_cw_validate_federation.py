"""Behavioural tests for mission-control/qps-triage-ultra/validate_federation.py."""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "mission-control" / "qps-triage-ultra" / "validate_federation.py"


def _load():
    spec = importlib.util.spec_from_file_location("cw_validate_federation_mod", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


vf = _load()
SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40


def _gate():
    return {
        "gate_id": "TEST-GATE",
        "mode": "ALL_REQUIRED",
        "authority_transfer": False,
        "required_nodes": {
            "ULTRA": {"repo": "o/ultra", "required_outcome": "SUCCESS"},
            "M02A": {"repo": "o/m02a", "target_head_sha": SHA_A, "required_outcome": "SUCCESS"},
            "M02B": {"repo": "o/m02b", "target_head_sha": SHA_B},
        },
    }


def _receipt(node, repo, sha, outcome="SUCCESS"):
    return {
        "schema": "qps-fleet-receipt/v1",
        "mission_id": node,
        "repo": repo,
        "source_sha": sha,
        "observed_at": "T",
        "execution": {
            "kernel": "k",
            "outcome": outcome,
            "steps_gt0": True,
            "workflow_run_id": "1",
            "workflow_run_attempt": "1",
        },
        "evidence_class": "SYNTHETIC",
        "authority_transfer": False,
        "engineering_acceptance": False,
    }


def _good(node):
    return {
        "ULTRA": _receipt("ULTRA", "o/ultra", SHA_C),
        "M02A": _receipt("M02A", "o/m02a", SHA_A),
        "M02B": _receipt("M02B", "o/m02b", SHA_B),
    }[node]


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setattr(vf, "GATE", _gate())
    monkeypatch.setattr(vf, "CONTRACT", copy.deepcopy(vf.CONTRACT))
    monkeypatch.setattr(vf, "ROOT", tmp_path)
    return tmp_path


def _run(monkeypatch, capsys, *args):
    monkeypatch.setattr(sys, "argv", ["validate_federation.py", *args])
    rc = vf.main()
    return rc, json.loads(capsys.readouterr().out)


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ---- committed repo data -------------------------------------------------

def test_committed_gate_and_contract_are_structurally_valid_and_self_test_passes():
    assert vf.structural_errors() == []
    assert vf.self_test() is True


# ---- structural_errors ---------------------------------------------------

def test_structural_errors_detects_each_violation(env, monkeypatch):
    monkeypatch.setitem(vf.CONTRACT, "receipt_schema", "other/v0")
    gate = {"mode": "ANY", "authority_transfer": True, "required_nodes": {"M02A": {}}}
    monkeypatch.setattr(vf, "GATE", gate)
    assert vf.structural_errors() == [
        "receipt_schema", "gate_mode", "authority_transfer",
        "missing_node:ULTRA", "missing_node:M02B",
    ]


def test_structural_errors_missing_authority_flag_is_error(env, monkeypatch):
    monkeypatch.setattr(vf, "GATE", {"mode": "ALL_REQUIRED"})
    errs = vf.structural_errors()
    assert "authority_transfer" in errs
    assert {"missing_node:ULTRA", "missing_node:M02A", "missing_node:M02B"} <= set(errs)


# ---- receipt_errors ------------------------------------------------------

def test_receipt_errors_clean_receipt(env):
    assert vf.receipt_errors(_good("M02A"), "M02A") == []
    # node without target_head_sha accepts any well-formed sha
    assert vf.receipt_errors(_good("ULTRA"), "ULTRA") == []


def test_receipt_errors_unknown_node(env):
    assert vf.receipt_errors(_good("M02A"), "NOPE") == ["unknown_node"]


def test_receipt_errors_empty_receipt_reports_everything(env):
    errs = vf.receipt_errors({}, "M02A")
    for key in vf.CONTRACT["required_top_level"]:
        assert "missing:" + key in errs
    for key in vf.CONTRACT["required_execution"]:
        assert "missing:execution." + key in errs
    for e in ("schema", "mission_id", "repo", "source_sha_format",
              "source_sha_target_mismatch", "authority_transfer",
              "engineering_acceptance", "steps_gt0", "outcome"):
        assert e in errs


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (lambda r: r.update(schema="x"), "schema"),
        (lambda r: r.update(mission_id="M02B"), "mission_id"),
        (lambda r: r.update(repo="o/other"), "repo"),
        (lambda r: r.update(source_sha="A" * 40), "source_sha_format"),
        (lambda r: r.update(source_sha="d" * 40), "source_sha_target_mismatch"),
        (lambda r: r.update(authority_transfer=True), "authority_transfer"),
        (lambda r: r.update(engineering_acceptance=None), "engineering_acceptance"),
        (lambda r: r["execution"].update(steps_gt0=1), "steps_gt0"),
        (lambda r: r["execution"].update(outcome="WEIRD"), "outcome"),
    ],
)
def test_receipt_errors_single_violation(env, mutate, expected):
    r = _good("M02A")
    mutate(r)
    errs = vf.receipt_errors(r, "M02A")
    if expected == "source_sha_format":
        # uppercase sha is malformed and therefore also differs from the target
        assert errs == ["source_sha_format", "source_sha_target_mismatch"]
    else:
        assert errs == [expected]


def test_receipt_errors_malformed_sha_on_untargeted_node(env):
    r = _good("ULTRA")
    r["source_sha"] = "short"
    assert vf.receipt_errors(r, "ULTRA") == ["source_sha_format"]


# ---- self_test -----------------------------------------------------------

def test_self_test_fails_when_good_fixture_rejected(env, monkeypatch):
    monkeypatch.setitem(vf.CONTRACT, "allowed_outcomes", ["FAILURE"])
    assert vf.self_test() is False


# ---- load_inbox ----------------------------------------------------------

def test_load_inbox_absent_dir_is_noop(env):
    supplied = {}
    vf.load_inbox(supplied)
    assert supplied == {}


def test_load_inbox_does_not_override_and_skips_missing_mission(env):
    inbox = env / "receipts" / "inbox"
    _write(inbox / "a.json", _good("M02A"))
    first_b = _good("M02B")
    first_b["observed_at"] = "first"
    _write(inbox / "b1.json", first_b)
    _write(inbox / "b2.json", _good("M02B"))
    _write(inbox / "c.json", {"no": "mission"})
    (inbox / "ignored.txt").write_text("{}", encoding="utf-8")
    preset = {"M02A": {"preset": True}}
    vf.load_inbox(preset)
    assert preset["M02A"] == {"preset": True}
    assert preset["M02B"]["observed_at"] == "first"
    assert set(preset) == {"M02A", "M02B"}


# ---- main ----------------------------------------------------------------

def test_main_fail_structure(env, monkeypatch, capsys):
    monkeypatch.setitem(vf.GATE, "mode", "ANY")
    rc, out = _run(monkeypatch, capsys)
    assert rc == 1
    assert out == {"status": "FAIL_STRUCTURE", "errors": ["gate_mode"]}


def test_main_structure_only(env, monkeypatch, capsys):
    rc, out = _run(monkeypatch, capsys, "--structure-only")
    assert rc == 0
    assert out == {"status": "PASS_STRUCTURE_ONLY", "gate": "TEST-GATE", "is_project_dov": False}


def test_main_self_test_pass(env, monkeypatch, capsys):
    rc, out = _run(monkeypatch, capsys, "--self-test")
    assert rc == 0
    assert out["status"] == "PASS_TESTABLE_ENGINE"
    assert out["fixture_is_project_evidence"] is False


def test_main_self_test_fail(env, monkeypatch, capsys):
    monkeypatch.setattr(vf, "self_test", lambda: False)
    rc, out = _run(monkeypatch, capsys, "--self-test")
    assert rc == 1
    assert out["status"] == "FAIL_SELF_TEST"


def test_main_bad_receipt_argument(env, monkeypatch, capsys):
    rc, out = _run(monkeypatch, capsys, "--receipt", "M02A-no-equals")
    assert rc == 1
    assert out == {"status": "FAIL_ARGUMENT", "item": "M02A-no-equals"}


def test_main_no_receipts_defers_all(env, monkeypatch, capsys):
    rc, out = _run(monkeypatch, capsys)
    assert rc == 0
    assert out["status"] == "DEFER_MISSING_RECEIPTS"
    assert out["missing"] == ["M02A", "M02B", "ULTRA"]
    assert out["validated_nodes"] == []


def test_main_partial_receipts_defer(env, monkeypatch, capsys):
    p = _write(env / "a.json", _good("M02A"))
    rc, out = _run(monkeypatch, capsys, "--receipt", "M02A=" + str(p))
    assert rc == 0
    assert out["status"] == "DEFER_MISSING_RECEIPTS"
    assert out["validated_outcomes"] == {"M02A": "SUCCESS"}
    assert out["missing"] == ["M02B", "ULTRA"]
    assert out["is_project_dov"] is False


def test_main_required_outcome_not_met_fails_gate(env, monkeypatch, capsys):
    # FAILURE is an allowed outcome, so the only error is the required outcome
    p = _write(env / "u.json", _receipt("ULTRA", "o/ultra", SHA_C, outcome="FAILURE"))
    rc, out = _run(monkeypatch, capsys, "--receipt", "ULTRA=" + str(p))
    assert rc == 1
    assert out["status"] == "FAIL_FEDERATION_GATE"
    assert out["errors"] == {"ULTRA": ["required_outcome_not_met"]}


def test_main_node_without_required_outcome_accepts_failure(env, monkeypatch, capsys):
    p = _write(env / "b.json", _receipt("M02B", "o/m02b", SHA_B, outcome="FAILURE"))
    rc, out = _run(monkeypatch, capsys, "--receipt", "M02B=" + str(p))
    assert rc == 0
    assert out["status"] == "DEFER_MISSING_RECEIPTS"
    assert out["validated_outcomes"] == {"M02B": "FAILURE"}


def test_main_unknown_node_fails_gate(env, monkeypatch, capsys):
    p = _write(env / "x.json", {"execution": {}})
    rc, out = _run(monkeypatch, capsys, "--receipt", "ZZZ=" + str(p))
    assert rc == 1
    assert out["errors"] == {"ZZZ": ["unknown_node"]}
    assert out["validated_nodes"] == ["ZZZ"]
    assert out["is_project_dov"] is False


def test_main_full_pass_via_args_and_inbox(env, monkeypatch, capsys):
    pa = _write(env / "a.json", _good("M02A"))
    inbox = env / "receipts" / "inbox"
    _write(inbox / "b.json", _good("M02B"))
    _write(inbox / "u.json", _good("ULTRA"))
    bad_a = _good("M02A")
    bad_a["authority_transfer"] = True
    _write(inbox / "a.json", bad_a)  # must not override explicit --receipt
    rc, out = _run(monkeypatch, capsys, "--receipt", "M02A=" + str(pa), "--inbox")
    assert rc == 0
    assert out == {
        "status": "PASS_FEDERATION_GATE",
        "gate": "TEST-GATE",
        "validated_nodes": ["M02A", "M02B", "ULTRA"],
        "validated_outcomes": {"M02A": "SUCCESS", "M02B": "SUCCESS", "ULTRA": "SUCCESS"},
        "is_project_dov": True,
    }


def test_main_inbox_flag_off_ignores_inbox(env, monkeypatch, capsys):
    _write(env / "receipts" / "inbox" / "u.json", _good("ULTRA"))
    rc, out = _run(monkeypatch, capsys)
    assert rc == 0
    assert out["validated_nodes"] == []
