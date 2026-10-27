"""Unit and negative controls for the W3 measured-PCA and observed-BT engines.

Both engines were exercised only by the workflow's end-to-end asserts on the committed
inputs, so none of their DEFER / fail-closed branches had been shown to fire. Inputs are
copies of the committed documents mutated one rule at a time.
"""
import copy
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import w3_analytics as wa  # noqa: E402
import w3_bt_gate as wb  # noqa: E402

TELEMETRY = json.loads((HERE / "w3_fleet_telemetry.json").read_text(encoding="utf-8"))
OBSERVATIONS = json.loads((HERE / "w3_bt_observations.json").read_text(encoding="utf-8"))


class Eigen(unittest.TestCase):
    def test_jacobi_recovers_known_spectrum(self):
        vals, vecs = wa.jacobi_eigen_symmetric([[2.0, 1.0], [1.0, 2.0]])
        self.assertAlmostEqual(vals[0], 3.0, places=9)
        self.assertAlmostEqual(vals[1], 1.0, places=9)
        self.assertAlmostEqual(abs(vecs[0][0]), math.sqrt(0.5), places=9)
        self.assertEqual(wa.jacobi_eigen_symmetric([]), ([], []))

    def test_eigenvectors_orthonormal_on_3x3(self):
        m = [[4.0, 1.0, 0.5], [1.0, 3.0, 0.2], [0.5, 0.2, 1.0]]
        vals, vecs = wa.jacobi_eigen_symmetric(m)
        self.assertAlmostEqual(sum(vals), 8.0, places=9)  # trace preserved
        for i in range(3):
            for j in range(3):
                dot = sum(vecs[i][k] * vecs[j][k] for k in range(3))
                self.assertAlmostEqual(dot, 1.0 if i == j else 0.0, places=9)

    def test_canonical_sign_and_stats(self):
        self.assertEqual(wa.canonicalize([0.1, -0.9]), [-0.1, 0.9])
        self.assertEqual(wa.canonicalize([]), [])
        self.assertEqual(wa.sample_std([5.0]), 0.0)
        self.assertAlmostEqual(wa.sample_std([1.0, 3.0]), math.sqrt(2.0))


class MeasuredPCA(unittest.TestCase):
    def test_committed_telemetry_passes_and_is_variance_consistent(self):
        r = wa.analyze(copy.deepcopy(TELEMETRY))
        self.assertEqual(r["outcome"], "PASS_MEASURED_RUNTIME_FOOTPRINT_PCA")
        self.assertEqual((r["w3_13"], r["w3_14"]), ("PASS_THREE_COMPARABLE_MEASURED_FLEET_PULSES", "PASS_MEASURED_PCA"))
        self.assertAlmostEqual(sum(c["explained_variance_ratio"] for c in r["components"]), 1.0, places=9)
        self.assertLessEqual(len(r["components"]), r["row_count"] - 1)  # rank <= n-1
        self.assertFalse(r["authority_transfer"])

    def mutate(self, fn):
        d = copy.deepcopy(TELEMETRY)
        fn(d)
        return wa.analyze(d)

    def test_contract_failures_defer_with_reasons(self):
        f = self.required = TELEMETRY["comparability_contract"]["required_common_numeric_fields"][0]
        cases = {
            "EVIDENCE_CLASS_NOT_MEASURED_API_OBSERVATION": lambda d: d.update(evidence_class="SEEDED"),
            "INSUFFICIENT_ROWS": lambda d: d.update(rows=d["rows"][:1]),
            "INSUFFICIENT_DISTINCT_REPOS": lambda d: [r.update(repo="same/repo") for r in d["rows"]],
            "INSUFFICIENT_DISTINCT_MISSIONS": lambda d: [r.update(mission_id="M") for r in d["rows"]],
            f"ROW_0_NON_NUMERIC_{f}": lambda d: d["rows"][0].update({f: "12"}),
            "ROW_0_RUNNER_NOT_ASSIGNED": lambda d: d["rows"][0].update(runner_assigned=0),
            "ROW_0_NOT_SUCCESS": lambda d: d["rows"][0].update(terminal_success=0),
            "ROW_0_FAILED_STEPS_NONZERO": lambda d: d["rows"][0].update(failed_step_count=1),
        }
        for reason, fn in cases.items():
            with self.subTest(reason=reason):
                r = self.mutate(fn)
                self.assertEqual(r["outcome"], "DEFER_COMPARABILITY_CONTRACT_FAILED")
                self.assertIn(reason, r["failures"])
                self.assertEqual(r["w3_14"], "WITHHELD")

    def test_booleans_and_non_finite_are_not_numbers(self):
        f = TELEMETRY["comparability_contract"]["required_common_numeric_fields"][0]
        for bad in (True, float("nan"), float("inf")):
            with self.subTest(bad=bad):
                r = self.mutate(lambda d: d["rows"][0].update({f: bad}))
                self.assertIn(f"ROW_0_NON_NUMERIC_{f}", r["failures"])

    def test_constant_fields_withhold_pca_but_keep_pulse_gate(self):
        fields = TELEMETRY["comparability_contract"]["required_common_numeric_fields"]
        r = self.mutate(lambda d: [row.update({k: 7 for k in fields[1:]}) for row in d["rows"]])
        self.assertEqual(r["outcome"], "DEFER_INSUFFICIENT_VARIABLE_FIELDS")
        self.assertEqual((r["w3_13"], r["w3_14"]), ("PASS_THREE_COMPARABLE_MEASURED_FLEET_PULSES", "WITHHELD"))


class ObservedBT(unittest.TestCase):
    def test_bt_branches(self):
        self.assertEqual(wb.bt([])["status"], "DEFER_NO_USABLE_COMPARISONS")
        self.assertEqual(wb.bt([{"winner": "a", "loser": "a"}])["status"], "DEFER_NO_USABLE_COMPARISONS")
        d = wb.bt([{"winner": "a", "loser": "b"}, {"winner": "c", "loser": "d"}])
        self.assertEqual(d["status"], "DEFER_DISCONNECTED_COMPARISON_GRAPH")
        self.assertEqual(d["components"], [["a", "b"], ["c", "d"]])
        ok = wb.bt([{"winner": "a", "loser": "b"}, {"winner": "a", "loser": "c"}, {"winner": "b", "loser": "c"}])
        self.assertEqual(ok["status"], "PASS_OBSERVED_BT")
        self.assertEqual(list(ok["scores"]), ["a", "b", "c"])
        self.assertAlmostEqual(sum(ok["scores"].values()) / 3, 1.0, places=9)

    def test_committed_current_pairs_validate(self):
        self.assertEqual(wb.validate_current_pairs(OBSERVATIONS["current_frontier"]["pairs"], OBSERVATIONS["policy"]), [])

    def test_each_pair_rule_fires(self):
        base = OBSERVATIONS["current_frontier"]["pairs"][0]
        cases = {
            "MISSING_FIELDS": {"winner_exact_sha": ""},
            "NON_MEASURED_EVIDENCE_CLASS": {"evidence_class": "SEEDED"},
            "LOSER_NOT_MEASURED_FAIL": {"loser_outcome": "SUCCESS"},
            "WINNER_NOT_MEASURED_SUCCESS": {"winner_outcome": "FAIL"},
            "CONTROL_REPEAT_NOT_SUCCESS": {"control_repeat_outcome": "FAIL"},
            "RUN_ID_NOT_INTEGER": {"loser_run_id": "123"},
            "CONTROL_RUN_ID_NOT_INTEGER": {"control_repeat_run_id": 1.5},
        }
        for reason, change in cases.items():
            with self.subTest(reason=reason):
                got = wb.validate_current_pairs([dict(copy.deepcopy(base), **change)], OBSERVATIONS["policy"])
                self.assertIn(reason, [x["reason"] for x in got])

    def run_main(self, doc):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "obs.json"
            p.write_text(json.dumps(doc))
            out = Path(d) / "r.json"
            with mock.patch.object(sys, "argv", ["w3_bt_gate", "--input", str(p), "--out", str(out)]), \
                    mock.patch("builtins.print"):
                code = wb.main()
            return code, json.loads(out.read_text())

    def test_main_credits_only_valid_current_frontier(self):
        code, r = self.run_main(OBSERVATIONS)
        self.assertEqual((code, r["w3_15"]), (0, "PASS_OBSERVED_INTERVENTION_BT"))
        self.assertFalse(r["historical_control_rex"]["eligible_for_w3_15"])
        bad = copy.deepcopy(OBSERVATIONS)
        bad["current_frontier"]["pairs"][0]["control_repeat_outcome"] = "FAIL"
        code, r = self.run_main(bad)
        self.assertEqual(code, 2)
        self.assertEqual(r["current_frontier"]["result"]["status"], "DEFER_PAIR_EVIDENCE_VALIDATION_FAILED")
        short = copy.deepcopy(OBSERVATIONS)
        short["policy"]["minimum_current_frontier_pairs"] = 99
        self.assertEqual(self.run_main(short)[0], 2)


class ReceiptSync(unittest.TestCase):
    """The committed receipts must equal engine output on the committed inputs (N+12 root)."""

    def setUp(self):
        import w3_receipt_sync as sync
        self.sync = sync
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for name in ("w3_fleet_telemetry.json", "w3_bt_observations.json",
                     "w3_measured_analytics_receipt.json", "w3_observed_bt_receipt.json"):
            (self.root / name).write_text((HERE / name).read_text(encoding="utf-8"), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_committed_receipts_are_current(self):
        rep = self.sync.check(HERE)
        self.assertEqual({k: v["state"] for k, v in rep.items()},
                         {k: "CURRENT" for k in self.sync.PAIRS}, rep)

    def test_input_change_without_regeneration_is_stale(self):
        tel = json.loads((self.root / "w3_fleet_telemetry.json").read_text())
        tel["rows"] = tel["rows"][:3]  # exactly the 2026-09-12 shape
        (self.root / "w3_fleet_telemetry.json").write_text(json.dumps(tel))
        rep = self.sync.check(self.root)
        self.assertEqual(rep["w3_measured_analytics_receipt.json"]["state"], "STALE")
        self.assertIn("$.row_count: committed=5 engine=3", rep["w3_measured_analytics_receipt.json"]["diff"])
        self.assertEqual(self.sync.main(["--root", str(self.root), "--check"]), 1)

    def test_write_restores_and_keeps_provenance(self):
        obs = json.loads((self.root / "w3_bt_observations.json").read_text())
        obs["current_frontier"]["pairs"] = []
        (self.root / "w3_bt_observations.json").write_text(json.dumps(obs))
        self.assertEqual(self.sync.check(self.root)["w3_observed_bt_receipt.json"]["state"], "STALE")
        self.sync.write(self.root, None)
        self.assertEqual(self.sync.main(["--root", str(self.root), "--check"]), 0)
        r = json.loads((self.root / "w3_observed_bt_receipt.json").read_text())
        self.assertEqual(r["ci_proof"]["run_id"], 39984340926)  # provenance kept, not engine output
        self.assertEqual(r["w3_15"], "WITHHELD_NO_VALID_CURRENT_FRONTIER_PAIRWISE_OUTCOMES")

    def test_float_canon_tolerates_last_ulp_only(self):
        self.assertEqual(self.sync.canon(0.1 + 0.2), self.sync.canon(0.3))
        self.assertNotEqual(self.sync.canon(0.7597), self.sync.canon(0.8584))


if __name__ == "__main__":
    unittest.main()
