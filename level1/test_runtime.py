"""Unit controls for the Level-1 MIP runtime (previously exercised only by CLI smoke steps).

Covers the analytic engines' PASS and DEFER branches, input validation, the census gate
arithmetic and the CLI exit-code contract. Fixtures prove the engine only; they are not
project evidence.
"""
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import runtime as rt  # noqa: E402


class PCA(unittest.TestCase):
    def test_correlated_rows_load_on_one_component(self):
        r = rt.pca([[1, 1], [2, 2.2], [3, 2.9], [4, 4.1]])
        self.assertEqual(r["status"], "PASS_TESTABLE_ENGINE")
        self.assertGreater(r["explained_variance_ratio"], 0.99)
        self.assertAlmostEqual(abs(r["component"][0]), abs(r["component"][1]), places=1)

    def test_orthogonal_seed_does_not_trap_power_iteration(self):
        r = rt.pca([[1, -1], [2, -2], [3, -3]])
        self.assertEqual(r["status"], "PASS_TESTABLE_ENGINE")
        self.assertAlmostEqual(r["explained_variance_ratio"], 1.0, places=6)
        self.assertLess(r["component"][0] * r["component"][1], 0)

    def test_defers_instead_of_inventing_a_component(self):
        self.assertEqual(rt.pca([[1, 2], [3, 4]])["status"], "DEFER_INSUFFICIENT_OBSERVATIONS")
        self.assertEqual(rt.pca([[1], [2], [3]])["status"], "DEFER_INSUFFICIENT_OBSERVATIONS")
        self.assertEqual(rt.pca([[1, 1], [1, 1], [1, 1]])["status"], "DEFER_ZERO_VARIANCE")

    def test_ragged_rows_rejected(self):
        with self.assertRaises(ValueError):
            rt.pca([[1, 2], [3, 4], [5]])

    def test_power_iteration_degenerate_seed(self):
        self.assertIsNone(rt._power([[0.0, 0.0], [0.0, 0.0]], [1.0, 0.0]))
        self.assertIsNone(rt._power([[1.0, 0.0], [0.0, 1.0]], [0.0, 0.0]))


class BradleyTerry(unittest.TestCase):
    def test_connected_graph_ranks_the_consistent_winner_first(self):
        r = rt.bt([["repair", "docs"], ["repair", "style"], ["runtime", "docs"], ["repair", "runtime"]])
        self.assertEqual(r["status"], "PASS_TESTABLE_ENGINE")
        self.assertEqual(next(iter(r["scores"])), "repair")
        self.assertAlmostEqual(sum(r["scores"].values()) / len(r["scores"]), 1.0, places=6)

    def test_disconnected_and_self_only_defer(self):
        d = rt.bt([["A", "B"], ["C", "D"]])
        self.assertEqual(d["status"], "DEFER_DISCONNECTED_COMPARISON_GRAPH")
        self.assertEqual(d["components"], [["A", "B"], ["C", "D"]])
        self.assertEqual(rt.bt([["x", "x"]])["status"], "DEFER_NO_USABLE_COMPARISONS")
        self.assertEqual(rt.bt([])["scores"], {})

    def test_components(self):
        self.assertEqual(rt._components(["a", "b", "c"], [("a", "b")]), [["a", "b"], ["c"]])


class Census(unittest.TestCase):
    def test_repository_census_reaches_level_1_0(self):
        c = rt.census()
        self.assertEqual(c["schema"], "gbogeb-level1-census/v2")
        self.assertEqual(c["passed"], c["total"])
        self.assertTrue(c["level_1_0"])
        self.assertEqual(c["level"], 1.0)

    def test_missing_control_section_lowers_level_and_mip_reports_it(self):
        with tempfile.TemporaryDirectory() as d:
            ctl = Path(d) / "LEVEL1.md"
            ctl.write_text("## Index\n## AOD\n## DMAIC\n## PCA\n")  # no BT section
            with mock.patch.object(rt, "CONTROL", ctl):
                c = rt.census()
                self.assertFalse(c["gates"]["bt"])
                self.assertFalse(c["level_1_0"])
                self.assertIn("bt", rt.mip()["modernize"]["missing_or_stale"])
                self.assertEqual(rt.selftest()["status"], "FAIL")

    def test_broken_native_runtime_reference_blocks_level_1_0(self):
        with tempfile.TemporaryDirectory() as d:
            ssot = Path(d) / "ssot.json"
            ssot.write_text(json.dumps({"repo": "x", "existing_runtime_refs": ["does/not/exist.py"]}))
            with mock.patch.object(rt, "SSOT", ssot):
                c = rt.census()
                self.assertTrue(c["control_level_1_0"])
                self.assertFalse(c["native_runtime_refs_ok"])
                self.assertFalse(c["level_1_0"])
                self.assertIn("native_runtime_refs", rt.mip()["modernize"]["missing_or_stale"])

    def test_digest_and_missing_files(self):
        self.assertIsNone(rt.digest(Path("/nonexistent/x")))
        self.assertEqual(rt.text(Path("/nonexistent/x")), "")
        self.assertEqual(rt.obj(Path("/nonexistent/x")), {})


class Receipts(unittest.TestCase):
    def test_selftest_passes_and_marks_fixtures_as_non_evidence(self):
        r = rt.selftest()
        self.assertEqual(r["status"], "PASS")
        self.assertFalse(r["fixture_is_project_evidence"])
        self.assertEqual(len(r["manifest_sha256"]), 64)

    def test_orchestrate_never_transfers_authority(self):
        o = rt.orchestrate()
        self.assertEqual(o["status"], "READY")
        self.assertEqual(o["sequence"][0], "census")
        self.assertFalse(o["mip"]["innovate"]["authority_transfer"])


class CLI(unittest.TestCase):
    def run_main(self, *argv):
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", ["runtime.py", *argv]), redirect_stdout(buf):
            code = rt.main()
        return code, json.loads(buf.getvalue())

    def test_analytics_defer_without_measured_input(self):
        for cmd in ("pca", "bt"):
            code, out = self.run_main(cmd)
            self.assertEqual((code, out["status"]), (0, "DEFER_NO_MEASURED_INPUT"))

    def test_analytics_read_measured_input(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "pairs.json"
            p.write_text(json.dumps([["a", "b"], ["a", "c"], ["b", "c"]]))
            code, out = self.run_main("bt", "--input", str(p))
            self.assertEqual((code, out["status"]), (0, "PASS_TESTABLE_ENGINE"))
            p.write_text(json.dumps([[1, 2], [2, 4.1], [3, 5.9]]))
            code, out = self.run_main("pca", "--input", str(p))
            self.assertEqual(out["status"], "PASS_TESTABLE_ENGINE")

    def test_failing_selftest_exits_nonzero(self):
        with mock.patch.object(rt, "selftest", return_value={"status": "FAIL"}):
            code, out = self.run_main("self-test")
        self.assertEqual(code, 1)

    def test_subprocess_contract(self):
        r = subprocess.run([sys.executable, str(HERE / "runtime.py"), "census"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertIn("gbogeb-level1-census/v2", r.stdout)


if __name__ == "__main__":
    unittest.main()
