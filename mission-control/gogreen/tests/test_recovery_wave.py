"""Regression/negative tests for source-bound CODE PURPLE N-wave evidence."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import recovery_wave as m

SAMPLE = ROOT / "samples" / "code_purple_recovery.json"


class RecoveryWaveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(SAMPLE.read_text())

    def record(self):
        return copy.deepcopy(self.data)

    def test_three_revision_terminal_census(self):
        result = m.rollup(self.record())
        self.assertEqual([(x["workflow_success"], x["workflow_denominator"])
                          for x in result["waves"]], [(28, 32), (30, 34), (35, 35)])
        self.assertEqual([x["root_unknown"] for x in result["waves"]], [1, 0, 0])
        self.assertIsNone(result["waves"][2]["comparable_workflow_pass_gain_pp"])

    def test_verified_first_red_transitions_not_global_root_closure(self):
        report = m.rollup(self.record())
        delta = report["last_comparison"]
        self.assertEqual(delta["root_predicates_comparable"], 2)
        self.assertEqual(delta["repaired_first_reds_on_pr_head"], 2)
        self.assertEqual(delta["reopened_first_reds_on_pr_head"], 0)
        self.assertTrue(all(x["verified_first_red_recovered_on_pr_head"]
                            for x in delta["transitions"]))
        self.assertTrue(all(x["global_causal_root_closed"] is None
                            for x in delta["transitions"]))

    def test_wider_fleet_and_admission_are_not_inferred(self):
        r = m.rollup(self.record())
        self.assertIsNone(r["coverage_gain_pp_fleetwide"])
        self.assertIsNone(r["scale"]["four_hop_evidence_completion"])
        self.assertFalse(r["merge_authorized"])
        self.assertFalse(r["effective_main_branch_protection"])
        self.assertEqual(r["qps_disposition"], "DEFER")
        self.assertFalse(r["methods"]["pca_eligible"])
        self.assertFalse(r["methods"]["bradley_terry_eligible"])

    def test_invalid_source_sha_rejected(self):
        d = self.record()
        d["observations"][2]["head_sha"] = "truncated"
        with self.assertRaisesRegex(ValueError, "source SHA"):
            m.rollup(d)

    def test_run_job_sha_mismatch_rejected(self):
        d = self.record()
        d["observations"][2]["root_observations"][d["fingerprints"][0]]["source_sha"] = "a" * 40
        with self.assertRaisesRegex(ValueError, "source SHA mismatch"):
            m.rollup(d)

    def test_root_predicate_drift_rejected(self):
        d = self.record()
        d["observations"][2]["root_observations"][d["fingerprints"][0]]["predicate"] = "Different gate"
        with self.assertRaisesRegex(ValueError, "predicate drift"):
            m.rollup(d)

    def test_root_population_drift_rejected(self):
        d = self.record()
        d["observations"][2]["root_observations"].pop(d["fingerprints"][1])
        with self.assertRaisesRegex(ValueError, "fixed root population"):
            m.rollup(d)

    def test_missing_earlier_root_is_null_not_zero(self):
        d = self.record()
        root = d["observations"][0]["root_observations"][d["fingerprints"][0]]
        self.assertEqual(root["state"], "UNKNOWN")
        self.assertIsNone(root["run_id"])
        root["run_id"] = 1
        with self.assertRaisesRegex(ValueError, "fabricated run"):
            m.rollup(d)

    def test_zero_run_id_cannot_count_as_native_receipt(self):
        d = self.record()
        d["observations"][1]["root_observations"][d["fingerprints"][0]]["run_id"] = 0
        with self.assertRaisesRegex(ValueError, "run ID"):
            m.rollup(d)

    def test_bad_run_attempt_rejected(self):
        d = self.record()
        d["observations"][2]["root_observations"][d["fingerprints"][1]]["run_attempt"] = None
        with self.assertRaisesRegex(ValueError, "run attempt"):
            m.rollup(d)

    def test_archive_metadata_cannot_claim_byte_proof(self):
        d = self.record()
        d["observations"][2]["root_observations"][d["fingerprints"][1]]["archive_bytes_verified"] = True
        with self.assertRaisesRegex(ValueError, "archive-byte"):
            m.rollup(d)

    def test_admission_and_qps_cannot_be_promoted(self):
        for key, val in (("admission", "PASS"), ("qps_disposition", "ACCEPT")):
            d = self.record()
            d[key] = val
            with self.assertRaisesRegex(ValueError, "automatic admission"):
                m.rollup(d)

    def test_revision_clock_cannot_reorder_history(self):
        d = self.record()
        d["observations"][1]["revision"] = 0
        with self.assertRaisesRegex(ValueError, "revision order"):
            m.rollup(d)

    def test_workflow_denominator_not_boolean(self):
        d = self.record()
        d["observations"][1]["workflow_counts"]["success"] = True
        with self.assertRaisesRegex(ValueError, "workflow count"):
            m.rollup(d)

    def test_deterministic_output_bytes(self):
        result = m.rollup(self.record())
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            sha1 = m.emit(result, out)
            first = (out / "recovery_wave.json").read_bytes()
            sha2 = m.emit(result, out)
            self.assertEqual(sha1, sha2)
            self.assertEqual(first, (out / "recovery_wave.json").read_bytes())
            self.assertEqual(64, len(sha1))
            self.assertIn("UNKNOWN", (out / "recovery_wave.md").read_text())

    def test_native_cli_produces_no_admission(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = subprocess.run([sys.executable, str(ROOT / "recovery_wave.py"),
                                "--input", str(SAMPLE), "--out", tmp],
                               text=True, capture_output=True, check=True, timeout=10)
            self.assertEqual(json.loads(p.stdout)["source_root_recoveries"], 2)
            result = json.loads((Path(tmp) / "recovery_wave.json").read_text())
            self.assertFalse(result["merge_authorized"])
            self.assertIsNone(result["methods"]["rolling_n_plus_2_forecast"])


if __name__ == "__main__":
    unittest.main()
