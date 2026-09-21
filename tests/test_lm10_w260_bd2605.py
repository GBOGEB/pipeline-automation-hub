#!/usr/bin/env python3
import copy
import importlib.util
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "mission-control/qps-triage-ultra/missions/validate_lm10_w260_bd2605.py"
INPUT = ROOT / "mission-control/qps-triage-ultra/missions/LM-10_W260_BD260_5_PROVIDER_RECEIPT_PROJECTION_v1.json"
OUT = ROOT / "mission-control/qps-triage-ultra/missions/LM-10_W260_BD260_5_TRIAGE_RECEIPT_v1.json"

spec = importlib.util.spec_from_file_location("bd2605_validator", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def expect_reject(mutator):
    d = json.loads(INPUT.read_text())
    mutator(d)
    try:
        module.validate_projection(d)
    except AssertionError:
        return
    raise AssertionError("mutated provider projection must fail closed")


def test_validator():
    cp = subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "PASS_LM10_W260_BD260_5_TRIAGE" in cp.stdout
    d = json.loads(OUT.read_text())
    assert d["status"] == "PASS_TRIAGE_VERIFICATION"
    assert d["disposition"] == "ACCEPT_BOUNDED_PROJECT_MATH_WITH_EXPLICIT_DEFER"
    assert d["authority_transfer"] is False
    assert d["formal_credit_delta"] == 0
    assert d["threshold_class_counts"] == {
        "GOVERNANCE_IDENTITY": 1,
        "NONE": 2,
        "PROJECT_GOVERNED": 0,
        "STATISTICAL": 2,
    }
    assert d["retained_first_reds"] == [
        "MANOVA_RUNTIME_NOT_PROMOTED_IN_THIS_SLICE",
        "DEFER_NO_FINITE_MLE",
    ]


def test_missing_governance_identity_card_fails():
    def mutate(d):
        d["receipt"]["cards"] = d["receipt"]["cards"][:-1]
    expect_reject(mutate)


def test_card_count_mismatch_fails():
    def mutate(d):
        d["receipt"]["card_count"] = 4
    expect_reject(mutate)


def test_disposition_identity_mismatch_fails():
    def mutate(d):
        d["receipt"]["cards"][3]["disposition"] = "REJECT"
    expect_reject(mutate)


def test_first_red_reassignment_fails():
    def mutate(d):
        d["receipt"]["cards"][2]["first_red"] = "DEFER_NO_FINITE_MLE"
        d["receipt"]["cards"][3]["first_red"] = "MANOVA_RUNTIME_NOT_PROMOTED_IN_THIS_SLICE"
    expect_reject(mutate)


if __name__ == "__main__":
    test_validator()
    test_missing_governance_identity_card_fails()
    test_card_count_mismatch_fails()
    test_disposition_identity_mismatch_fails()
    test_first_red_reassignment_fails()
    print("PASS_LM10_W260_BD260_5_TEST")
