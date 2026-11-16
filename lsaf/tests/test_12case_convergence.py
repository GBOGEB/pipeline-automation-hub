import json
from pathlib import Path

from lsaf.compiler.dag import compile_dag
from lsaf.compiler.fingerprints import occurrence_ledger, semantic_fingerprint

CASES = (
    Path(__file__).parents[1]
    / "pilots"
    / "LSAF-P1-12CASE-CONVERGENCE"
    / "cases.json"
)


def _cases():
    return json.loads(CASES.read_text(encoding="utf-8"))["cases"]


def test_pilot_has_exactly_12_cases_with_4_4_4_split():
    cases = _cases()
    assert len(cases) == 12
    counts = {}
    for case in cases:
        counts[case["class"]] = counts.get(case["class"], 0) + 1
    assert counts == {
        "recurring_root": 4,
        "stale_or_admission": 4,
        "negative_control": 4,
    }


def test_recurring_root_cases_deduplicate_deterministically():
    for case in [x for x in _cases() if x["class"] == "recurring_root"]:
        ledger = occurrence_ledger(case["observations"])
        assert len(ledger) == 1, case["id"]
        assert ledger[0]["occurrence_count"] == case["expected_occurrence_count"]
        assert ledger[0]["maturity"] == "RECURRING"


def test_stale_and_admission_cases_never_false_ready():
    for case in [x for x in _cases() if x["class"] == "stale_or_admission"]:
        got = compile_dag(case["nodes"])
        assert got["ready"] == case["expected_ready"], case["id"]
        assert got["blocked"] == case["expected_blocked"], case["id"]


def test_negative_controls_remain_distinct_or_blocked():
    for case in [x for x in _cases() if x["class"] == "negative_control"]:
        if "left" in case:
            same = semantic_fingerprint(case["left"]) == semantic_fingerprint(case["right"])
            assert same is case["expected_same_fingerprint"], case["id"]
        else:
            got = compile_dag(case["nodes"])
            assert got["ready"] == case["expected_ready"], case["id"]
            assert got["blocked"] == case["expected_blocked"], case["id"]
            if "expected_cycle" in case:
                assert got["cycle"] == case["expected_cycle"], case["id"]
