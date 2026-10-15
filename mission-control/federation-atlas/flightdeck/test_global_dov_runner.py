"""Fail-closed global DoV contract regression suite."""
from __future__ import annotations
import copy
import json
import tempfile
import unittest
from pathlib import Path
from global_dov_runner import produce, validate

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "global_dov_owner_control_v1.json"


class GlobalDOVTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = json.loads(SOURCE.read_text(encoding="utf-8"))

    def test_source_valid(self):
        validate(self.original)

    def test_no_engineering_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = produce(SOURCE, Path(tmp))
            score = json.loads((Path(tmp) / "scorecard.json").read_text())
            self.assertEqual(0, result["engineering_credit"])
            self.assertEqual("DEFER", score["owner_acceptance"])
            self.assertEqual("HOLD", score["hard_gates"]["merge_admission"])
            self.assertEqual(8, len(score["actions"]))

    def test_reject_false_fleet_observation(self):
        doc = copy.deepcopy(self.original)
        next(x for x in doc["global_outcomes"] if x["id"] == "OBSERVABILITY")[
            "numerator"
        ] = 42
        with self.assertRaises(ValueError):
            validate(doc)

    def test_reject_changed_product_denominator(self):
        doc = copy.deepcopy(self.original)
        next(x for x in doc["global_outcomes"] if x["id"] == "PRODUCT")[
            "denominator"
        ] = 89
        with self.assertRaises(ValueError):
            validate(doc)

    def test_reject_changed_owner_gate(self):
        doc = copy.deepcopy(self.original)
        doc["hard_gates"]["qps_engineering_acceptance"] = "ACCEPT"
        with self.assertRaises(ValueError):
            validate(doc)

    def test_reject_hidden_source_conflict(self):
        doc = copy.deepcopy(self.original)
        doc["source_conflicts"][0]["disposition"] = "PASS"
        with self.assertRaises(ValueError):
            validate(doc)

    def test_reject_duplicate_actions(self):
        doc = copy.deepcopy(self.original)
        doc["decisions"][1]["id"] = doc["decisions"][0]["id"]
        with self.assertRaises(ValueError):
            validate(doc)

    def test_reject_missing_owner_proof(self):
        doc = copy.deepcopy(self.original)
        doc["decisions"][0]["proof"] = ""
        with self.assertRaises(ValueError):
            validate(doc)

    def test_reject_offsite_injected_action_link(self):
        doc = copy.deepcopy(self.original)
        doc["decisions"][0]["source"] = "https://example.invalid"
        with self.assertRaises(ValueError):
            validate(doc)

    def test_five_output_members_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            produce(SOURCE, Path(tmp))
            self.assertTrue((Path(tmp) / "index.html").exists())
            self.assertTrue((Path(tmp) / "owner_actions.csv").exists())
            manifest = json.loads((Path(tmp) / "manifest.json").read_text())
            self.assertEqual(3, len(manifest["files"]))


if __name__ == "__main__":
    unittest.main()
