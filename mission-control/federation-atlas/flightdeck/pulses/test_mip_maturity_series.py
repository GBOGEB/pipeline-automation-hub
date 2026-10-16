"""Matched and adversarial source-bound MIP time-series tests."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from mip_maturity_series import main, rollup

HASH = "a" * 64
SHA1 = "a" * 40
SHA2 = "b" * 40
SHA3 = "c" * 40


def wave(n, *, sha=None, success=8, pending=0, queue_fallback=0,
         scope=HASH, eligible_lines=100, lines=80, branches=20, p95=90):
    sha = sha or {1: SHA1, 2: SHA2, 3: SHA3}.get(n, SHA3)
    total = 10
    red = 4
    return {
        "wave": n, "observed_at": f"2026-10-{10+n:02d}T12:00:00Z",
        "cohort": {"workflow_set_sha256": HASH,
                   "test_selection_sha256": HASH,
                   "runner_matrix_sha256": HASH},
        "run_attempts": [[n * 1000 + k, 1] for k in range(total)],
        "projection": {
            "schema": "code-purple.mission-control.mip-consumer.v1",
            "source": {"repository": "GBOGEB/ABACUS", "head_sha": sha,
                       "producer_sha256_claim": HASH,
                       "original_binary_authenticated": False},
            "observed": {
                "workflow_total_n": total,
                "workflow_terminal_n": total - pending,
                "workflow_success_n": success,
                "workflow_pending_n": pending,
                "workflow_failure_n": total - pending - success,
                "workflow_success_fraction_descriptive": (
                    success / total if not pending else None),
                "first_red_manifestations": 3,
                "red_jobs_total": red, "red_jobs_unattributed": 1,
                "first_red_unique_signatures": 2,
                "queue_samples": 25,
                "queue_native_n": 25 - queue_fallback,
                "queue_fallback_n": queue_fallback,
                "queue_p95_seconds_source_reported": p95,
            },
            "root_register_created": False,
            "html_truth_store_created": False,
            "authority_transfer": False,
            "merge_authorized": False,
            "qps_engineering_acceptance": "DEFER",
            "admission": "HOLD",
        },
        "coverage": {
            "source_sha": sha, "scope_sha256": scope,
            "config_sha256": HASH, "artifact_sha256": HASH,
            "tool_version": "coverage.py 7.x",
            "eligible_lines": eligible_lines, "covered_lines": lines,
            "eligible_branches": 40, "covered_branches": branches,
        },
    }


def fixture():
    return {"schema": "code-purple.mip.maturity-series-input.v1",
            "repository": "GBOGEB/ABACUS", "authority_transfer": False,
            "observations": [wave(1), wave(2, success=9, lines=90,
                                    branches=24, p95=60)],
            "forecasts": []}


class MaturityTests(unittest.TestCase):
    def test_matched_descriptive_queue_and_coverage_deltas(self):
        result = rollup(fixture())
        self.assertEqual(result["waves_observed"], 2)
        self.assertEqual(result["native_run_attempts_bound"], 20)
        compare = result["comparisons"][0]
        self.assertTrue(compare["cohort_matched"])
        self.assertEqual(compare["success_delta_pp_descriptive"], 10.0)
        self.assertEqual(compare["queue_p95_delta_seconds_descriptive"], -30)
        self.assertEqual(compare["line_coverage_delta_pp_candidate"], 10.0)
        self.assertEqual(compare["branch_coverage_delta_pp_candidate"], 10.0)
        self.assertIsNone(compare["accepted_root_closures"])
        self.assertIsNone(result["independent_observations_authenticated"])
        self.assertEqual(result["admission"], "HOLD")

    def test_mixed_queue_timestamp_cannot_earn_latency_gain(self):
        doc = fixture()
        doc["observations"][1] = wave(2, success=9, queue_fallback=1, p95=12)
        result = rollup(doc)["comparisons"][0]
        self.assertIsNone(result["queue_p95_delta_seconds_descriptive"])
        self.assertIn("UNQUALIFIED_CLOCK", result["queue_comparability"])

    def test_coverage_scope_or_denominator_shift_unmatched(self):
        for changes in ({"scope": "b" * 64}, {"eligible_lines": 105}):
            with self.subTest(changes=changes):
                doc = fixture()
                doc["observations"][1] = wave(
                    2, success=9, **changes)
                comparison = rollup(doc)["comparisons"][0]
                self.assertIsNone(comparison["line_coverage_delta_pp_candidate"])

    def test_wrong_workflow_cohort_cannot_make_rate_trend(self):
        doc = fixture()
        doc["observations"][1]["cohort"]["runner_matrix_sha256"] = "b" * 64
        c = rollup(doc)["comparisons"][0]
        self.assertFalse(c["cohort_matched"])
        self.assertIsNone(c["success_delta_pp_descriptive"])

    def test_nonterminal_is_censored_not_success_or_fail(self):
        doc = fixture()
        doc["observations"][1] = wave(2, success=8, pending=1)
        c = rollup(doc)["comparisons"][0]
        self.assertIsNone(c["success_delta_pp_descriptive"])
        self.assertIsNone(c["queue_p95_delta_seconds_descriptive"])

    def test_explicit_n_plus_1_forecast_scored_without_retrofit(self):
        doc = fixture()
        doc["forecasts"] = [{
            "issued_wave": 1, "target_wave": 2,
            "issued_sha": SHA1, "issued_at": "2026-10-11T12:01:00Z",
            "method": "persistence-v1",
            "metric": "workflow_success_fraction", "prediction": 0.8,
        }]
        observed = rollup(doc)
        self.assertEqual(observed["forecast_n_scored"], 1)
        self.assertAlmostEqual(observed["forecast_mae"], 0.1)
        self.assertAlmostEqual(observed["forecast_rmse"], 0.1)
        self.assertEqual(observed["forecasts"][0]["actual"], 0.9)
        self.assertEqual([x["target_wave"] for x in
                          observed["proposed_n_plus_1_n_plus_2"]], [3, 4])
        self.assertFalse(observed["forecasts"][0][
            "immutable_provenance_authenticated"])

    def test_out_of_order_and_future_leakage_rejected(self):
        for mutated in (
            lambda d: d["observations"][1].update(wave=5),
            lambda d: d["observations"][1].update(
                observed_at="2026-10-11T11:00:00Z"),
            lambda d: d["observations"][1].update(run_attempts=
                d["observations"][0]["run_attempts"]),
        ):
            doc = fixture()
            mutated(doc)
            with self.assertRaises(ValueError):
                rollup(doc)
        doc = fixture()
        doc["forecasts"] = [{
            "issued_wave": 1, "target_wave": 2,
            "issued_sha": SHA1, "issued_at": "2026-10-12T13:00:00Z",
            "method": "persistence-v1",
            "metric": "workflow_success_fraction", "prediction": 0.8,
        }]
        with self.assertRaisesRegex(ValueError, "backdated"):
            rollup(doc)

    def test_reject_false_source_and_evidence_denominators(self):
        for change in (
            lambda d: d["observations"][0]["projection"].update(
                admission="PASS"),
            lambda d: d["observations"][0]["projection"]["observed"].update(
                first_red_manifestations=4),
            lambda d: d["observations"][0]["projection"]["observed"].update(
                queue_native_n=26),
            lambda d: d["observations"][0]["projection"]["source"].update(
                original_binary_authenticated=True),
            lambda d: d["observations"][0]["coverage"].update(
                covered_branches=True),
            lambda d: d["observations"][0]["run_attempts"].append([10, 1]),
        ):
            doc = fixture()
            change(doc)
            with self.assertRaises(ValueError):
                rollup(doc)

    def test_missing_coverage_never_means_zero_coverage(self):
        doc = fixture()
        doc["observations"][1]["coverage"] = None
        comparison = rollup(doc)["comparisons"][0]
        self.assertIsNone(comparison["branch_coverage_delta_pp_candidate"])
        self.assertIn("MISSING", comparison["coverage_comparability"])

    def test_unissued_n_plus_2_forecasts_remain_unscored(self):
        doc = fixture()
        doc["forecasts"] = [{
            "issued_wave": 2, "target_wave": 4,
            "issued_sha": SHA2, "issued_at": "2026-10-12T12:01:00Z",
            "method": "persistence-v1",
            "metric": "workflow_success_fraction", "prediction": 0.9,
        }]
        result = rollup(doc)
        self.assertEqual(result["forecast_n_scored"], 0)
        self.assertIsNone(result["forecasts"][0]["actual"])
        self.assertIsNone(result["forecast_mae"])

    def test_duplicate_forecast_key_is_rejected(self):
        doc = fixture()
        f = {"issued_wave": 1, "target_wave": 2,
             "issued_sha": SHA1, "issued_at": "2026-10-11T12:01:00Z",
             "method": "persistence-v1",
             "metric": "workflow_success_fraction", "prediction": 0.8}
        doc["forecasts"] = [f, copy.deepcopy(f)]
        with self.assertRaisesRegex(ValueError, "duplicate immutable"):
            rollup(doc)

    def test_cli_deterministic_atomic_and_rejects_input_alias(self):
        doc = fixture()
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            inp, out = p / "input.json", p / "output.json"
            inp.write_text(json.dumps(doc))
            self.assertEqual(main(["--input", str(inp), "--out", str(out)]), 0)
            data = out.read_bytes()
            self.assertEqual(main(["--input", str(inp), "--out", str(out)]), 0)
            self.assertEqual(out.read_bytes(), data)
            self.assertEqual(json.loads(data)["input_digest_sha256"],
                             hashlib.sha256(inp.read_bytes()).hexdigest())
            with self.assertRaisesRegex(ValueError, "aliases"):
                main(["--input", str(inp), "--out", str(inp)])


if __name__ == "__main__":
    unittest.main()
