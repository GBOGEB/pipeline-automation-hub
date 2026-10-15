"""Append-only wave histories: source scope, trend comparisons, and safe presentation."""
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
import wave_timeline as m

SAMPLE = ROOT / "samples" / "wave_timeline.json"
CURRENT = "c" * 40


class EvolutionaryTimelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads(SAMPLE.read_text())

    def data(self):
        return copy.deepcopy(self.source)

    def test_native_g0_g1_g2_report_and_deltas(self):
        r = m.build(self.data(), source_sha=CURRENT)
        self.assertEqual([w["observed_cells"] for w in r["waves"]], [1, 6, 6])
        self.assertEqual([w["regression_tests_pass"] for w in r["waves"]], [None, 39, 55])
        self.assertEqual(r["waves"][1]["delta"]["observed_cells"], 5)
        self.assertEqual(r["waves"][2]["delta"]["observed_cells"], 0)
        self.assertEqual(r["waves"][2]["delta"]["native_tests"], 16)
        self.assertEqual(r["waves"][1]["delta"]["native_tests"], None)
        self.assertEqual(r["waves"][2]["delta"]["focused_statement_coverage_pp"], 0)
        self.assertEqual(r["waves"][2]["delta"]["focused_branch_coverage_pp"], 0)
        self.assertEqual(r["waves"][2]["recovered_first_red_fingerprints"], 2)
        self.assertIsNone(r["waves"][2]["delta"]["recovered_roots"])

    def test_future_wave_absent_not_zero(self):
        r = m.build(self.data(), source_sha=CURRENT)
        self.assertEqual(r["future"]["next_wave"], "G3")
        self.assertEqual(r["future"]["status"], "WAIT_FOR_NATIVE_EVIDENCE")
        self.assertIsNone(r["improvement_claims"]["global_root_closures"])
        self.assertIsNone(r["improvement_claims"]["real_worker_launches"])

    def test_fixed_catalog_denominator_tamper(self):
        d = self.data()
        d["catalog"][0]["target_family_cells"] = 12
        with self.assertRaisesRegex(ValueError, "denominator drift"):
            m.validate(d)

    def test_duplicate_repository_rejected(self):
        d = self.data()
        d["catalog"][1]["repository"] = d["catalog"][0]["repository"]
        with self.assertRaisesRegex(ValueError, "duplicate catalog"):
            m.validate(d)

    def test_wave_drop_reindex_rejected(self):
        d = self.data()
        d["waves"].pop(1)
        with self.assertRaisesRegex(ValueError, "wave ordering"):
            m.validate(d)

    def test_unknown_not_transmuted_into_zero(self):
        d = self.data()
        d["waves"][0]["tests"]["executed"] = 0
        with self.assertRaisesRegex(ValueError, "unknown counts"):
            m.validate(d)

    def test_fake_archive_byte_proof_rejected(self):
        d = self.data()
        d["waves"][2]["archive_bytes_independently_verified"] = True
        with self.assertRaisesRegex(ValueError, "independent archive byte proof"):
            m.validate(d)

    def test_failed_native_run_rejected(self):
        d = self.data()
        d["waves"][2]["run_conclusion"] = "failure"
        with self.assertRaisesRegex(ValueError, "native terminal PASS"):
            m.validate(d)

    def test_run_url_id_mismatch_rejected(self):
        d = self.data()
        d["waves"][1]["workflow_url"] = "https://github.com/other/repo/actions/runs/99"
        with self.assertRaisesRegex(ValueError, "URL provenance"):
            m.validate(d)

    def test_negative_measured_cell_regression_rejected(self):
        d = self.data()
        d["waves"][2]["fleet"]["observed_cells"] = 5
        with self.assertRaisesRegex(ValueError, "observation regression"):
            m.validate(d)

    def test_coverage_denominator_drift_is_unknown_delta(self):
        d = self.data()
        d["waves"][2]["focused"]["statements"]["eligible"] += 1
        r = m.build(d, source_sha=CURRENT)
        self.assertIsNone(r["waves"][2]["delta"]["focused_statement_coverage_pp"])

    def test_coverage_source_digest_drift_is_unknown_delta(self):
        d = self.data()
        d["waves"][2]["focused"]["source_file_sha256"] = "d" * 64
        r = m.build(d, source_sha=CURRENT)
        self.assertIsNone(r["waves"][2]["delta"]["focused_statement_coverage_pp"])
        self.assertIsNone(r["waves"][2]["delta"]["focused_branch_coverage_pp"])

    def test_append_only_prior_prefix_preserved(self):
        d = self.data()
        previous = self.data()
        previous["waves"] = previous["waves"][:2]
        self.assertTrue(m.validate(d, previous=previous))
        bad = self.data()
        bad["waves"][0]["fleet"]["observed_cells"] = 2
        with self.assertRaisesRegex(ValueError, "historical.*tampered"):
            m.validate(bad, previous=previous)

    def test_history_without_appended_wave_rejected(self):
        d = self.data()
        with self.assertRaisesRegex(ValueError, "append-only"):
            m.validate(d, previous=copy.deepcopy(d))

    def test_next_wave_extensible_without_fake_measurement(self):
        d = self.data()
        future = copy.deepcopy(d["waves"][-1])
        future["wave"] = "G3"
        future["ordinal"] = 3
        future["observed_at_utc"] = "2026-10-15T09:06:08Z"
        future["source_sha"] = "d" * 40
        future["run_id"] = 40000000000
        future["job_id"] = 110000000000
        future["workflow_url"] = (
            "https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/40000000000"
        )
        future["archive_artifact_id"] = 12000000000
        future["root_predicates_recovered"] = None
        d["waves"].append(future)
        r = m.build(d, source_sha=CURRENT)
        self.assertEqual(r["future"]["next_wave"], "G4")
        self.assertEqual(r["waves"][-1]["delta"]["native_tests"], 0)

    def test_wave_chronology_reversed_is_rejected(self):
        d = self.data()
        d["waves"][2]["observed_at_utc"] = "2026-10-15T08:00:00Z"
        with self.assertRaisesRegex(ValueError, "chronology reversed"):
            m.validate(d)

    def test_html_escapes_untrusted_scope_notes(self):
        d = self.data()
        d["waves"][-1]["scope_notes"] = '<img src=x onerror="alert(1)">'
        r = m.build(d, source_sha=CURRENT)
        markup = m.render_html(r)
        self.assertNotIn('<img src=x onerror="alert(1)">', markup)
        self.assertIn("&lt;img src=x onerror=", markup)
        self.assertIn("wave scorecard", markup)

    def test_markdown_links_native_runs_and_notes_unknown(self):
        text = m.render_markdown(m.build(self.data(), source_sha=CURRENT))
        self.assertIn("38709078403", text)
        self.assertIn("UNKNOWN", text)
        self.assertIn("G2", text)

    def test_deterministic_four_outputs(self):
        r = m.build(self.data(), source_sha=CURRENT)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            a = m.emit(r, out)
            first = (out / "wave_timeline.json").read_bytes()
            b = m.emit(r, out)
            self.assertEqual(a, b)
            self.assertEqual(len(a), 64)
            self.assertEqual(first, (out / "wave_timeline.json").read_bytes())
            self.assertIn("G2", (out / "wave_timeline.html").read_text())

    def test_native_cli_fail_closed_admission(self):
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run(
                [sys.executable, str(ROOT / "wave_timeline.py"),
                 "--input", str(SAMPLE), "--out", temp,
                 "--source-sha", CURRENT], capture_output=True, text=True,
                check=True, timeout=10,
            )
            payload = json.loads(result.stdout)
            self.assertEqual(payload["latest"], "G2")
            self.assertEqual(payload["next"], "G3")
            self.assertFalse(payload["merge_authorized"])
            stored = json.loads((Path(temp) / "wave_timeline.json").read_text())
            self.assertEqual(stored["admission"], "HOLD")


if __name__ == "__main__":
    unittest.main()
