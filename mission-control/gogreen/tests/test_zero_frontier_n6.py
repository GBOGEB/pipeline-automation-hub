"""GOGREEN coverage ZERO frontier: exact-head positive/negative matched denominator tests."""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "pulse_metrics.py"
SPEC = importlib.util.spec_from_file_location("gogreen_pulse_zero_frontier", SOURCE)
pulse = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pulse)
SHA = "a" * 40
MODULE = "mission-control/gogreen/scale_dock.py"
LOG = b"Ran 4 tests in 0.002s\n\nOK\n"


def payload(covered_lines=0, covered_branches=0, path=MODULE):
    return json.dumps({
        "meta": {"branch_coverage": True, "version": "7.10.7"},
        "files": {path: {"summary": {
            "num_statements": 4, "covered_lines": covered_lines,
            "num_branches": 2, "covered_branches": covered_branches,
        }}},
    }).encode("utf-8")


def result(raw, compare=None):
    return pulse.produce(raw, LOG, "GBOGEB/pipeline-automation-hub",
                         SHA, SHA, "G7-P1", comparison=compare)


class ZeroFrontierTest(unittest.TestCase):
    def test_zero_coverage_is_failed_not_unknown(self):
        result0 = result(payload())
        cov = result0["coverage"]
        self.assertEqual(cov["zero_statement_modules"], [MODULE])
        self.assertEqual(cov["zero_branch_modules"], [MODULE])
        self.assertEqual(cov["measured_zero_gate"], "FAIL")

    def test_true_nonzero_population_clears_measured_zero_only(self):
        current = result(payload(4, 2))
        self.assertEqual(current["coverage"]["measured_zero_gate"], "PASS_MEASURED_COHORT_ONLY")
        self.assertEqual(current["coverage"]["combined_percent"], 100)
        self.assertFalse(current["merge_authorized"])

    def test_matched_zero_burndown_counts_independently(self):
        baseline = result(payload())
        current = result(payload(4, 2), baseline)
        self.assertEqual(current["comparability"], "MATCHED_SCOPE")
        self.assertEqual(current["comparable_zero_statement_delta"], -1)
        self.assertEqual(current["comparable_zero_branch_delta"], -1)
        self.assertEqual(current["comparable_delta_pp"], 100)

    def test_changed_denominator_disallows_synthetic_gain(self):
        old = result(payload())
        new = json.loads(payload(4, 2))
        new["files"][MODULE]["summary"]["num_statements"] = 5
        current = result(json.dumps(new).encode(), old)
        self.assertEqual(current["comparability"], "INCOMPARABLE_SCOPE_OR_TOOL")
        self.assertIsNone(current["comparable_delta_pp"])

    def test_forged_baseline_aggregate_rejected(self):
        baseline = result(payload())
        baseline["coverage"]["combined_eligible"] = 99
        with self.assertRaisesRegex(ValueError, "aggregate mismatch"):
            result(payload(2, 1), baseline)

    def test_boolean_denominator_rejected(self):
        bad = json.loads(payload())
        bad["files"][MODULE]["summary"]["num_branches"] = True
        with self.assertRaisesRegex(ValueError, "invalid coverage count"):
            result(json.dumps(bad).encode())

    def test_parent_path_alias_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "ambiguous coverage production path"):
            result(payload(path="mission-control/gogreen/../gogreen/scale_dock.py"))

    def test_missing_exact_head_rejected(self):
        with self.assertRaisesRegex(ValueError, "exact checkout"):
            pulse.produce(payload(), LOG, "GBOGEB/pipeline-automation-hub", SHA, "b"*40, "G7-P1")


if __name__ == "__main__":
    unittest.main()
