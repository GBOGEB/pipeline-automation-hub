"""Adversarial tests for source-bound BD/CHAR read-only projection."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "BD_CHAR_SFED_20261016_P2.json"
SPEC = importlib.util.spec_from_file_location("bd_char_viewer", HERE / "bd_char_viewer.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PulseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads(DATA.read_text(encoding="utf-8"))

    def test_contract_and_exact_temporal_population(self):
        MODULE.validate(self.source)
        p = self.source["same_head_pulse"]
        self.assertEqual(8, len(p["run_ids"]))
        self.assertEqual(0, p["before"]["success"])
        self.assertEqual(8, p["after"]["success"])

    def test_projection_deterministic_and_sealed(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            receipt = MODULE.produce(DATA, out)
            before = (out / "index.html").read_bytes()
            again = MODULE.produce(DATA, out)
            self.assertEqual(receipt, again)
            self.assertEqual(before, (out / "index.html").read_bytes())
            self.assertIn(b'<title>CODE PURPLE', before)
            self.assertIn(b'Formal root open / closed', before)
            for n, digest in receipt["artifacts"].items():
                self.assertEqual(digest, hashlib.sha256((out / n).read_bytes()).hexdigest())

    def test_refuse_waiver_and_fake_main_acceptance(self):
        for name, value in (("security_waiver", True),
                            ("merge_admission", "PASS"),
                            ("accepted_root_closed", 8),
                            ("hosted_publication_verified", True),
                            ("accepted_rex", "fake")):
            with self.subTest(name=name):
                d = copy.deepcopy(self.source)
                d["authority"][name] = value
                with self.assertRaises(ValueError):
                    MODULE.validate(d)

    def test_refuse_changed_head_between_observations(self):
        d = copy.deepcopy(self.source)
        d["same_head_pulse"]["source_sha"] = "a" * 40
        with self.assertRaisesRegex(ValueError, "temporal SHA drift"):
            MODULE.validate(d)

    def test_refuse_duplicate_run_and_wrong_denominator(self):
        d = copy.deepcopy(self.source)
        d["same_head_pulse"]["run_ids"][1] = d["same_head_pulse"]["run_ids"][0]
        with self.assertRaises(ValueError):
            MODULE.validate(d)
        d = copy.deepcopy(self.source)
        d["same_head_pulse"]["before"]["nonterminal"] = 7
        with self.assertRaises(ValueError):
            MODULE.validate(d)

    def test_refuse_denominator_drift_and_false_root_close(self):
        d = copy.deepcopy(self.source)
        d["matched_historical_coverage"]["after"]["eligible"] += 1
        with self.assertRaisesRegex(ValueError, "coverage population drift"):
            MODULE.validate(d)
        d = copy.deepcopy(self.source)
        d["candidate_families"][0]["accepted_closure"] = True
        with self.assertRaisesRegex(ValueError, "invented causal closure"):
            MODULE.validate(d)

    def test_refuse_duplicate_pr_and_unsupported_provenance(self):
        d = copy.deepcopy(self.source)
        d["pr_rows"].append(copy.deepcopy(d["pr_rows"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate PR"):
            MODULE.validate(d)
        d = copy.deepcopy(self.source)
        d["pr_rows"][0]["scope"] = "QUALIFIED_EXACT_CHECKOUT"
        with self.assertRaisesRegex(ValueError, "invalid PR provenance"):
            MODULE.validate(d)

    def test_current_main_and_diff_are_unknown(self):
        c = self.source["matched_historical_coverage"]
        self.assertIsNone(c["current_main"])
        self.assertIsNone(c["current_pr_diff"])
        a = self.source["authority"]
        self.assertIsNone(a["accepted_root_open"])
        self.assertIsNone(a["accepted_root_reopened"])


if __name__ == "__main__":
    unittest.main()
