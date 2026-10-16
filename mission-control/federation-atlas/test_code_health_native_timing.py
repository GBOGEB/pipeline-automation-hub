"""Native job time capsule: exact run identity, denominator and UTC proof."""

import copy
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from central import code_health  # noqa: E402


class NativeTimingTests(unittest.TestCase):
    def setUp(self):
        self.source = code_health.read_json(code_health.REGISTRY)
        self.cohort = self.source["runtime_cohorts"][0]

    def test_historical_exact_run_metadata_is_scoped(self):
        metrics = code_health.validate(self.source)
        self.assertEqual(metrics["historical_runtime_cohorts"], 1)
        self.assertEqual(metrics["historical_queue_job_samples"], 18)
        self.assertEqual(self.cohort["repository"], "GBOGEB/ABACUS")
        self.assertEqual(self.cohort["run_id"], 38869180768)
        self.assertEqual(self.cohort["run_attempt"], 1)
        self.assertEqual(len(self.cohort["jobs"]), 18)
        self.assertEqual(self.cohort["queue_p95_seconds"], 100)
        self.assertEqual(self.cohort["runtime_p95_seconds"], 182)
        self.assertEqual(self.cohort["observed_peak_parallel_jobs"], 11)
        self.assertEqual(self.cohort["runtime_sum_seconds"], 1386)
        self.assertEqual(self.cohort["admission"],
                         "PR_SIDE_CI_PASS_NOT_MAIN_ADMISSION")

    def test_available_slots_and_rex_remain_unknown(self):
        for key in ("runner_available_slots", "all_crew_launches_authenticated",
                    "accepted_rex"):
            self.assertIsNone(self.cohort[key])
        self.assertIsNone(self.source["runner_capacity"]["native_available_slots"])

    def test_shifted_queue_seconds_is_rejected(self):
        bad = copy.deepcopy(self.source)
        bad["runtime_cohorts"][0]["jobs"][0]["queue_seconds"] += 1
        with self.assertRaisesRegex(ValueError, "tampered native time"):
            code_health.validate(bad)

    def test_missing_job_is_not_a_full_population(self):
        bad = copy.deepcopy(self.source)
        bad["runtime_cohorts"][0]["jobs"].pop()
        with self.assertRaisesRegex(ValueError, "truncated native"):
            code_health.validate(bad)

    def test_duplicate_job_id_cannot_inflate_sample(self):
        bad = copy.deepcopy(self.source)
        bad["runtime_cohorts"][0]["jobs"][1]["job_id"] = (
            bad["runtime_cohorts"][0]["jobs"][0]["job_id"]
        )
        with self.assertRaisesRegex(ValueError, "duplicate native"):
            code_health.validate(bad)

    def test_fabricated_free_runner_capacity_rejected(self):
        bad = copy.deepcopy(self.source)
        bad["runtime_cohorts"][0]["runner_available_slots"] = 4
        with self.assertRaisesRegex(ValueError, "cannot authenticate"):
            code_health.validate(bad)

    def test_timing_aggregates_must_match_raw_native_population(self):
        bad = copy.deepcopy(self.source)
        bad["runtime_cohorts"][0]["queue_p95_seconds"] = 0
        with self.assertRaisesRegex(ValueError, "timing aggregates mismatch"):
            code_health.validate(bad)

    def test_terminal_workflow_does_not_mean_admitted_main(self):
        bad = copy.deepcopy(self.source)
        bad["runtime_cohorts"][0]["admission"] = "MAIN_ADMITTED"
        with self.assertRaisesRegex(ValueError, "repository admission"):
            code_health.validate(bad)

    def test_timing_panel_has_job_deeplinks_and_no_live_runner_claim(self):
        metrics = code_health.validate(self.source)
        page = code_health.render(
            self.source, metrics,
            code_health.route_work(
                self.source["work"], self.source["runner_capacity"]
            ),
            checkout_sha=self.source["authority"]["source_sha"],
        )
        self.assertIn("run #38869180768", page)
        self.assertIn("queue p95 100 s", page)
        self.assertIn("runtime p95 182 s", page)
        self.assertIn("available runner slots UNKNOWN", page)
        self.assertIn("/job/116868962792", page)


if __name__ == "__main__":
    unittest.main()
