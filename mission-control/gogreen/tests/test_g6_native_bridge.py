"""Fail-closed G6 intake: cross-repo head drift, nonterminal and fake bytes."""
from __future__ import annotations
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from g6_native_bridge import bridge


class G6NativeBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.crosswalk = json.loads(
            (ROOT / "g5_gap_crosswalk_20261015.json").read_text(encoding="utf-8"))
        cls.heads = {
            r["repository"]: r["source_sha"]
            for r in cls.crosswalk["current_cohort"]["repos"]
        }

    def test_empty_fresh_cohort_not_historical_six(self):
        out = bridge(self.crosswalk, self.heads, [])
        self.assertEqual(42, out["evidence"]["breadth"]["catalog_repo_family_cells"])
        self.assertEqual(0, out["evidence"]["breadth"]["observed_cells"])
        self.assertEqual(42, out["evidence"]["breadth"]["not_observed_cells"])
        self.assertFalse(out["merge_authorized"])
        self.assertIsNone(out["verified_zip_members"])
        self.assertIsNone(out["accepted_root_closures"])

    def test_head_drift_is_rejected(self):
        heads = dict(self.heads)
        heads["GBOGEB/ABACUS"] = "f" * 40
        with self.assertRaisesRegex(ValueError, "head drift"):
            bridge(self.crosswalk, heads, [])

    def test_synthetic_untrusted_native_row_rejected(self):
        row = {
            "repository": "GBOGEB/ABACUS", "family": "ci_contract",
            "source_sha": self.heads["GBOGEB/ABACUS"],
            "suite_id": "untrusted", "run_id": 1, "run_number": 1,
            "run_attempt": 1, "job_id": 1,
            "workflow_status": "completed", "workflow_conclusion": "success",
            "job_status": "completed", "job_conclusion": "success",
            "config_identity": "UNKNOWN",
            "run_url": "https://github.com/GBOGEB/ABACUS/actions/runs/1",
            "evidence_class": "SYNTHETIC_NOT_NATIVE"
        }
        with self.assertRaises(ValueError):
            bridge(self.crosswalk, self.heads, [row])

    def test_nonterminal_rejected(self):
        with self.assertRaisesRegex(ValueError, "nonterminal"):
            bridge(self.crosswalk, self.heads, [
                {"workflow_status": "queued", "job_status": "queued"}
            ])

    def test_self_asserted_bytes_rejected(self):
        with self.assertRaisesRegex(ValueError, "ZIP/member"):
            bridge(self.crosswalk, self.heads, [
                {"workflow_status": "completed", "job_status": "completed",
                 "artifact": {"bytes_verified": True}}
            ])

    def test_duplicate_repo_or_denominator_rejected(self):
        bad = copy.deepcopy(self.crosswalk)
        bad["current_cohort"]["repos"][1]["repository"] = "GBOGEB/ABACUS"
        with self.assertRaisesRegex(ValueError, "six exact"):
            bridge(bad, self.heads, [])
        bad = copy.deepcopy(self.crosswalk)
        bad["current_cohort"]["repos"][0]["families"].append("ci_contract")
        with self.assertRaises(ValueError):
            bridge(bad, self.heads, [])


if __name__ == "__main__":
    unittest.main()
