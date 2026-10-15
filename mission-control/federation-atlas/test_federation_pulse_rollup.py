"""Negative and longitudinal measurements for MissionControl federation overlay."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import federation_pulse_rollup as m

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "FEDERATION_OBSERVED_PULSES_v1.json"


def records():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class FederationMeasuredWaveTests(unittest.TestCase):
    def test_actual_observed_pulses_build(self):
        o = m.rollup(records())
        self.assertEqual({"observed": 2, "eligible": 5},
                         o["producer_breadth"])
        self.assertEqual({"observed": 1, "eligible": 5},
                         o["measured_coverage_breadth"])
        self.assertEqual(4, len(o["timeline"]))
        self.assertEqual("DEFER", o["qps_owner_decision"])
        self.assertIsNone(o["native_cross_repo_chain_verified"])

    def test_three_qps_pulses_have_real_numerators(self):
        steps = [x for x in m.rollup(records())["timeline"]
                 if x["repo"] == "GBOGEB/cryoplant-project"]
        self.assertEqual([0, 1, 2], [s["pulse"] for s in steps])
        self.assertEqual([93, 132, 135],
                         [s["line"]["covered"] for s in steps])
        self.assertEqual([36, 45, 48],
                         [s["branch"]["covered"] for s in steps])
        self.assertEqual([38, 48, 51], [s["tests_executed"] for s in steps])
        self.assertEqual([2, 2, 2],
                         [s["source_artifact_receipts"] for s in steps])

    def test_measured_gain_and_diminishing_return(self):
        steps = [x for x in m.rollup(records())["timeline"]
                 if x["repo"] == "GBOGEB/cryoplant-project"]
        a, b = steps[1]["delta"], steps[2]["delta"]
        self.assertEqual((39, 9, 10), (a["new_lines"], a["new_branches"],
                                        a["new_tests"]))
        self.assertEqual((3, 3, 3), (b["new_lines"], b["new_branches"],
                                       b["new_tests"]))
        self.assertAlmostEqual(3.9, a["covered_lines_per_added_test"])
        self.assertAlmostEqual(1.0, b["covered_lines_per_added_test"])
        self.assertEqual("EXPANDED_OR_CHANGED_TEST_SELECTION",
                         b["classification"])

    def test_abacus_queued_does_not_credit_missing(self):
        rows = m.rollup(records())["timeline"]
        p = next(x for x in rows if x["repo"] == "GBOGEB/ABACUS")
        self.assertEqual("QUEUED", p["status"])
        self.assertIsNone(p["line"])
        self.assertIsNone(p["branch"])
        self.assertEqual(0, p["source_artifact_receipts"])

    def test_pca_bt_need_actual_observations(self):
        readiness = m.rollup(records())["method_readiness"]
        self.assertEqual("UNKNOWN", readiness["PCA"]["state"])
        self.assertEqual("UNKNOWN", readiness["BT"]["state"])
        self.assertEqual(60, readiness["PCA"]["min_complete_rows"])
        self.assertIsNone(readiness["LDAB"])
        self.assertIsNone(readiness["LLDB"])

    def test_pca_bt_only_eligible_not_admission(self):
        d = records()
        d["method_receipts"]["pca_complete_rows"] = 60
        d["method_receipts"]["bt_terminal_pairs"] = 30
        d["method_receipts"]["bt_positive_outcomes"] = 5
        x = m.rollup(d)
        self.assertEqual("ELIGIBLE_TO_ANALYZE",
                         x["method_readiness"]["PCA"]["state"])
        self.assertEqual("ELIGIBLE_TO_ANALYZE",
                         x["method_readiness"]["BT"]["state"])
        self.assertIsNone(x["protected_main_admitted"])
        self.assertEqual("DEFER", x["qps_owner_decision"])

    def test_inadequate_pca_bt_is_hold(self):
        d = records()
        d["method_receipts"]["pca_complete_rows"] = 20
        d["method_receipts"]["bt_terminal_pairs"] = 25
        d["method_receipts"]["bt_positive_outcomes"] = 4
        x = m.rollup(d)
        self.assertEqual("HOLD_INSUFFICIENT_N",
                         x["method_readiness"]["PCA"]["state"])
        self.assertEqual("HOLD_INSUFFICIENT_N",
                         x["method_readiness"]["BT"]["state"])

    def test_python_scope_mismatch_rejected(self):
        d = records()
        d["observations"][1]["scope"][0]["sha256"] = "a" * 64
        with self.assertRaisesRegex(ValueError, "cross-Python"):
            m.rollup(d)

    def test_python_numerator_mismatch_rejected(self):
        d = records()
        d["observations"][1]["line"]["covered"] -= 1
        with self.assertRaisesRegex(ValueError, "cross-Python"):
            m.rollup(d)

    def test_missing_native_run_artifact_rejected(self):
        d = records()
        d["observations"][0]["artifact_id"] = None
        with self.assertRaisesRegex(ValueError, "artifact reference"):
            m.rollup(d)

    def test_pending_run_cannot_claim_coverage(self):
        d = records()
        d["observations"][-1]["line"] = {"covered": 0, "eligible": 1}
        with self.assertRaisesRegex(ValueError, "speculative"):
            m.rollup(d)

    def test_pending_run_cannot_forge_pass(self):
        d = records()
        d["observations"][-1]["status"] = "TERMINAL_PASS"
        with self.assertRaises(ValueError):
            m.rollup(d)

    def test_no_qps_accept_or_cross_repo_auth(self):
        d = records()
        d["observations"][0]["engineering_acceptance"] = True
        with self.assertRaisesRegex(ValueError, "unauthorized"):
            m.rollup(d)
        d = records()
        d["observations"][0]["native_replay_authenticated"] = True
        with self.assertRaisesRegex(ValueError, "unauthorized"):
            m.rollup(d)

    def test_duplicate_pulse_python_identity_rejected(self):
        d = records()
        d["observations"].append(copy.deepcopy(d["observations"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            m.rollup(d)

    def test_boolean_root_census_invalid(self):
        d = records()
        d["method_receipts"]["unique_confirmed_roots"] = False
        with self.assertRaisesRegex(ValueError, "method count"):
            m.rollup(d)

    def test_noncanonical_sha_rejected(self):
        d = records()
        d["observations"][0]["head_sha"] = "main"
        with self.assertRaisesRegex(ValueError, "immutable"):
            m.rollup(d)

    def test_unsupported_repo_not_silently_counted(self):
        d = records()
        d["observations"][0]["repo"] = "GBOGEB/other"
        with self.assertRaisesRegex(ValueError, "unrecognized"):
            m.rollup(d)

    def test_changed_source_denominator_prevents_claim(self):
        d = records()
        p = d["observations"][2]
        # Preserve cross-Python parity within pulse 1; change BOTH source hashes.
        for i in (2, 3):
            d["observations"][i]["scope"][0]["sha256"] = "f" * 64
        step = [x for x in m.rollup(d)["timeline"]
                if x["repo"] == "GBOGEB/cryoplant-project" and x["pulse"] == 1][0]
        self.assertEqual("DIFFERENT_SOURCE_OR_DENOMINATOR",
                         step["delta"]["classification"])
        self.assertIsNone(step["delta"]["line_pp"])

    def test_deterministic_second_pass(self):
        a = m.rollup(records())
        self.assertEqual(a, m.rollup(records()))
        self.assertEqual(a["receipt_sha256"],
                         m.hashlib.sha256(m.canonical({
                             k: v for k, v in a.items()
                             if k != "receipt_sha256"
                         }).encode()).hexdigest())

    def test_html_contains_links_and_unknown(self):
        page = m.render(m.rollup(records()))
        self.assertIn("38707522432", page)
        self.assertIn("UNKNOWN", page)
        self.assertIn("DEFER", page) if "DEFER" in page else self.assertIn("admission", page.lower())
        self.assertNotIn("<script>", page)

    def test_cli_writes_machine_and_human_receipts(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            with unittest.mock.patch.object(sys, "argv", [
                "rollup", "--input", str(FIXTURE), "--out", str(out)
            ]):
                self.assertEqual(0, m.main())
            row = json.loads((out / "federation-wave-metrics.json").read_text())
            self.assertEqual(1, row["measured_coverage_breadth"]["observed"])
            self.assertTrue((out / "federation-wave.html").stat().st_size > 200)
