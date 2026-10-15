"""Focused positive and fail-closed process-lane projection controls."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lane_process


class LaneProcessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = lane_process.read_json(HERE / "PROCESS_LANES_v1.json")
        cls.registry = lane_process.read_json(HERE / "METHOD_OBSERVABILITY_v1.json")

    def contract_copy(self):
        return copy.deepcopy(self.contract)

    def test_full_contracted_stage_population(self):
        self.assertEqual(lane_process.verify(self.contract, self.registry), 39)
        self.assertEqual(len(self.contract["lanes"]), 10)

    def test_expected_historical_observability_breadth(self):
        m = lane_process.summary(self.contract)
        self.assertEqual(m["observability"]["before"], 1)
        self.assertEqual(m["observability"]["after"], 6)
        self.assertEqual(m["observability"]["eligible"], 42)
        self.assertEqual(m["observability"]["unobserved"], 36)
        self.assertEqual(m["observability"]["gain_pp"], 11.9)

    def test_same_source_depth_eligible_denominators(self):
        m = lane_process.summary(self.contract)
        self.assertEqual(m["focused_depth"]["statements"]["eligible"], 93)
        self.assertEqual(m["focused_depth"]["statements"]["delta_pp"], 16.129)
        self.assertEqual(m["focused_depth"]["branches"]["eligible"], 26)
        self.assertEqual(m["focused_depth"]["branches"]["delta_pp"], 11.5385)
        self.assertEqual(m["tests"]["passed_candidate"], 39)

    def test_mermaid_contains_all_lanes_and_next_pulse_feedback(self):
        source = lane_process.mermaid(self.contract)
        self.assertEqual(source.count("  subgraph "), 10)
        self.assertIn("3PC_COMMIT", source)
        self.assertIn("M2", source)
        self.assertIn("next pulse, never same-wave cycle", source)

    def test_output_links_to_existing_publisher_and_artifacts(self):
        with tempfile.TemporaryDirectory() as temp:
            metrics = lane_process.build(temp)
            path = Path(temp)
            self.assertEqual(metrics["node_count"], 39)
            self.assertTrue((path / "lane-process.mmd").exists())
            self.assertTrue((path / "lane-process.json").exists())
            markup = (path / "lane-process.html").read_text(encoding="utf-8")
            for target in ("index.html", "code-purple.html", "phase02-temporal.html",
                           "lane-process.mmd", "lane-process.json"):
                self.assertIn('href="' + target + '"', markup)
            for node in ("3PR_REFRESH", "PCA", "REX", "P9", "Unknown"):
                self.assertIn(node.casefold(), markup.casefold())

    def test_outputs_are_reproducible(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            lane_process.build(a)
            lane_process.build(b)
            for name in ("lane-process.html", "lane-process.mmd", "lane-process.json"):
                self.assertEqual((Path(a) / name).read_bytes(), (Path(b) / name).read_bytes())

    def test_observation_never_admits_or_attests(self):
        m = lane_process.summary(self.contract)
        self.assertEqual(m["merge_admission"], "HOLD")
        self.assertFalse(m["byte_verified"])
        self.assertIsNone(m["actual_worker_hours"])
        self.assertIsNone(m["runtime_sessions_verified"])
        self.assertEqual(m["root_closure_credited"], 0)
        self.assertEqual(m["pca"], "NOT_ASSESSABLE")

    def test_rejects_false_archive_proof(self):
        doc = self.contract_copy()
        doc["observation"]["archive_bytes_independently_verified"] = True
        with self.assertRaisesRegex(ValueError, "Unproven artifact"):
            lane_process.verify(doc, self.registry)

    def test_rejects_false_merge_and_closure(self):
        for key, val in (("merge_admission", "PASS"),
                         ("root_closure_credited", 1),
                         ("security_waiver", True),
                         ("authority_transfer", True)):
            with self.subTest(key=key):
                doc = self.contract_copy()
                doc["observation"][key] = val
                with self.assertRaises(ValueError):
                    lane_process.verify(doc, self.registry)

    def test_rejects_missing_lane(self):
        doc = self.contract_copy()
        doc["lanes"].pop()
        with self.assertRaisesRegex(ValueError, "lanes"):
            lane_process.verify(doc, self.registry)

    def test_rejects_duplicate_node(self):
        doc = self.contract_copy()
        doc["lanes"][3]["stages"][1][0] = "DEFINE"
        with self.assertRaisesRegex(ValueError, "Duplicate node"):
            lane_process.verify(doc, self.registry)

    def test_registry_drift_blocks_publication(self):
        doc = self.contract_copy()
        doc["lanes"][3]["stages"][0][0] = "DEFINE_RENAMED"
        with self.assertRaisesRegex(ValueError, "Registry stage mismatch"):
            lane_process.verify(doc, self.registry)

    def test_rex_census_never_become_canonical(self):
        doc = self.contract_copy()
        doc["lanes"][8]["kind"] = "canonical"
        with self.assertRaisesRegex(ValueError, "Projection promoted"):
            lane_process.verify(doc, self.registry)

    def test_coverage_population_cannot_be_exceeded(self):
        doc = self.contract_copy()
        doc["observation"]["branches"]["after"] = 27
        with self.assertRaisesRegex(ValueError, "numerator"):
            lane_process.verify(doc, self.registry)

    def test_unknowns_not_fabricated_zero(self):
        m = lane_process.summary(self.contract)
        self.assertIsNone(m["runtime_sessions_verified"])
        self.assertIsNone(m["actual_worker_hours"])
        self.assertEqual(m["m2_stability"], "HOLD")
        self.assertEqual(m["m3_capability"], "HOLD")

    def test_html_escapes_untrusted_lane_display(self):
        doc = self.contract_copy()
        doc["lanes"][0]["label"] = "<script>alert(1)</script>"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "contract.json"
            path.write_text(json.dumps(doc), encoding="utf-8")
            lane_process.build(temp, contract_path=path)
            markup = (Path(temp) / "lane-process.html").read_text()
            self.assertIn("&lt;script&gt;", markup)
            self.assertNotIn("<script>alert(1)</script>", markup)


    def test_test_population_rejects_negative_fractional_boolean_and_overflow(self):
        for key, value in (
            ("passed_candidate", -1),
            ("passed_candidate", 1.5),
            ("passed_candidate", True),
            ("candidate", 3.2),
            ("candidate", False),
            ("baseline", -1),
            ("baseline", True),
            ("baseline", 0),
            ("passed_candidate", 999),
        ):
            with self.subTest(field=key, value=value):
                doc = self.contract_copy()
                doc["observation"]["tests"][key] = value
                with self.assertRaisesRegex(ValueError, "Test counts|Invalid tests"):
                    lane_process.verify(doc, self.registry)

    def test_breadth_prose_derived_from_same_metrics_as_cards(self):
        doc = self.contract_copy()
        doc["observation"]["eligible_cells"] = 50
        doc["observation"]["g1_observed_cells"] = 7
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "contract.json"
            target.write_text(json.dumps(doc), encoding="utf-8")
            lane_process.build(temp, contract_path=target)
            markup = (Path(temp) / "lane-process.html").read_text(encoding="utf-8")
            self.assertIn("50 eligible repo-family cells", markup)
            self.assertIn("7 status/metadata observations", markup)
            self.assertIn("43 UNKNOWN", markup)
            self.assertNotIn("42 eligible repo-family cells, 6 status", markup)

if __name__ == "__main__":
    unittest.main()
