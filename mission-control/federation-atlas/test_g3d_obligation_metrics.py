"""G3D telemetry contracts: negative controls must reject misleading credit."""
import copy
import json
import unittest
from pathlib import Path
import g3d_obligation_metrics as g3d

DATA = Path(__file__).with_name("G3D_OBLIGATION_SNAPSHOT_v1.json")


class G3DMetricsTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(DATA.read_text(encoding="utf-8"))

    def test_five_fixed_parents_no_closure(self):
        out = g3d.summarize(self.data)
        self.assertEqual(out["parents_total"], 5)
        self.assertEqual(out["parents_verified_closed"], 0)
        self.assertEqual(out["merge_admission"], "HOLD")

    def test_matched_integer_denominator(self):
        out = g3d.summarize(self.data)
        self.assertEqual([x["classified"] for x in out["workflow_source_history"]],
                         [164, 172, 188])
        self.assertEqual([x["remaining"] for x in out["workflow_source_history"]],
                         [24, 16, 0])
        self.assertEqual([x["classified_gain"] for x in
                          out["source_progress_velocity"]], [8, 16])

    def test_mismatched_denominator_is_rejected(self):
        self.data["history"][2]["workflow_denominator"] = 187
        with self.assertRaisesRegex(ValueError, "non-matched"):
            g3d.summarize(self.data)

    def test_nonmonotone_pulse_clock_is_rejected(self):
        self.data["history"][1]["n"] = 0
        with self.assertRaisesRegex(ValueError, "monotone"):
            g3d.summarize(self.data)

    def test_zero_work_hours_must_not_replace_unknown(self):
        self.data["human_worker_hours"] = 0
        with self.assertRaisesRegex(ValueError, "unknown"):
            g3d.summarize(self.data)

    def test_reported_fingerprint_not_promoted_to_causal_root(self):
        self.data["fingerprints"][0]["accepted_root_id"] = "R123"
        with self.assertRaisesRegex(ValueError, "root"):
            g3d.summarize(self.data)

    def test_successful_component_run_does_not_mean_admission(self):
        self.data["terminal"][0]["conclusion"] = "success"
        out = g3d.summarize(self.data)
        self.assertFalse(out["terminal_receipts"][0]["qualifies_for_admission"])

    def test_historical_coverage_never_relabels_as_current(self):
        out = g3d.summarize(self.data)
        self.assertAlmostEqual(
            out["historical_coverage"]["statements"]["change_percentage_points"],
            16.129, places=2)
        self.assertEqual(out["fresh_census_breadth"], None)

    def test_coverage_mismatched_scope_is_rejected(self):
        self.data["coverage"]["branches"]["scope"] = "OTHER_REPOSITORY"
        with self.assertRaisesRegex(ValueError, "scope"):
            g3d.summarize(self.data)

    def test_forecasts_not_retroactively_rewritten(self):
        self.data["forecasts"][0]["outcome"] = "PASS"
        with self.assertRaisesRegex(ValueError, "frozen"):
            g3d.summarize(self.data)

    def test_future_prediction_cannot_have_fabricated_probability(self):
        self.data["forecasts"][1]["probability"] = 0.98
        with self.assertRaisesRegex(ValueError, "frozen"):
            g3d.summarize(self.data)

    def test_terminal_exact_sha_and_job_are_required(self):
        self.data["terminal"][0]["source_sha"] = "HEAD"
        with self.assertRaisesRegex(ValueError, "source binding"):
            g3d.summarize(self.data)

    def test_g3f_latest_epoch_separates_cohort_and_live(self):
        x = g3d.summarize(self.data)
        self.assertEqual(x["source_current_unclassified_scope"],
                         "HISTORICAL_FIXED_188_NOT_LIVE")
        r = x["latest_source_epoch"]
        self.assertEqual((r["new_arrivals"], r["retirements"]), (21, 0))
        self.assertEqual(r["pre_repair"]["unclassified"], 8)
        self.assertEqual(r["repair_head"]["unclassified"], 0)
        self.assertEqual(r["repair_head"]["unit_tests_passed"], 324)
        self.assertEqual(r["main_source"]["native_main_gate"],
                         "UNKNOWN_NOT_CREDITED")
        self.assertFalse(r["effective_independent_admission"])
        self.assertEqual(x["parents_verified_closed"], 0)

    def test_g3f_population_conservation_rejects_fabricated_arrival(self):
        self.data["live_epoch"]["arrivals_since_fixed"].pop()
        with self.assertRaisesRegex(ValueError, "conservation"):
            g3d.summarize(self.data)

    def test_g3f_mismatched_live_denominator_rejected(self):
        self.data["live_epoch"]["pre_repair"]["workflow_total"] = 208
        with self.assertRaisesRegex(ValueError, "matched 209"):
            g3d.summarize(self.data)

    def test_g3f_mismatched_native_test_population_rejected(self):
        self.data["live_epoch"]["repair_head"]["native_governance"][
            "unit_tests_passed"] = 323
        with self.assertRaisesRegex(ValueError, "native test"):
            g3d.summarize(self.data)

    def test_g3f_root_closure_or_admission_forgery_rejected(self):
        self.data["live_epoch"]["accepted_root_closures"] = 1
        with self.assertRaisesRegex(ValueError, "authority"):
            g3d.summarize(self.data)

    def test_g3f_missing_receipt_is_not_main_success(self):
        self.data["live_epoch"]["main_source_at_observation"][
            "native_main_run_id"] = 39230923051
        with self.assertRaisesRegex(ValueError, "main CI"):
            g3d.summarize(self.data)

    def test_historical_federation_denominators_stable(self):
        out = g3d.summarize(self.data)
        self.assertEqual((out["historical_census_observed"],
                          out["historical_census_eligible"]), (6, 42))
        self.assertEqual(out["maturity"]["M3"], "HOLD")
        self.assertEqual(out["PCA_federation_readiness"], "NOT_QUALIFIED")


if __name__ == "__main__":
    unittest.main()
