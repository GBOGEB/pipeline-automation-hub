"""Table-driven geometry and negative-control tests; no fake inference."""
import copy
import unittest
from mip_statistical_qualification import METHODS, qualify


def baseline():
    return {
        "schema": "code-purple.statistical-design.v1",
        "authority_transfer": False, "source_bound": True,
        "cohort_matched": True, "independent_units": 0,
        "feature_count": 0, "independence_verified": False,
        "complete_terminal": False, "same_scope": False,
        "same_units": False, "sampling_design_approved": False,
        "successes": None, "group_sizes": [],
        "pairwise_comparisons": 0, "comparison_graph_connected": False,
        "finite_bt_fit_conditions": False, "covariance_rank": None,
        "residual_diagnostics_pass": False,
        "eigenspace_diagnostics_pass": False,
    }


class QualificationTests(unittest.TestCase):
    def test_realistic_correlated_ci_workflows_all_hold(self):
        r = qualify(baseline())
        self.assertTrue(all(x == "HOLD_DESIGN_NOT_QUALIFIED"
                            for x in r["method_status"].values()))
        self.assertEqual(set(r["numeric_intervals"]), {"90", "95", "99"})
        self.assertTrue(all(x is None for x in r["numeric_intervals"].values()))
        self.assertFalse(r["provider_execution_verified"])
        self.assertFalse(r["merge_authorized"])

    def test_eligible_design_is_not_a_computed_estimate(self):
        q = baseline()
        q.update(independent_units=36, feature_count=3,
                 independence_verified=True, complete_terminal=True,
                 same_scope=True, same_units=True,
                 sampling_design_approved=True, successes=28,
                 group_sizes=[12, 12, 12],
                 pairwise_comparisons=18, comparison_graph_connected=True,
                 finite_bt_fit_conditions=True, covariance_rank=3,
                 residual_diagnostics_pass=True,
                 eigenspace_diagnostics_pass=True)
        r = qualify(q)
        self.assertEqual(set(r["method_status"]), set(METHODS))
        self.assertTrue(all(v == "ELIGIBLE_FOR_PROVIDER_REVIEW"
                            for v in r["method_status"].values()))
        self.assertTrue(all(x is None for x in r["numeric_intervals"].values()))
        self.assertIsNone(r["pca_explained_variance"])
        self.assertEqual(r["qps_acceptance"], "DEFER")

    def test_methods_require_independence_even_at_large_n(self):
        q = baseline()
        q.update(independent_units=10000, feature_count=2,
                 successes=9999, complete_terminal=True,
                 same_scope=True, sampling_design_approved=True,
                 group_sizes=[5000, 5000], covariance_rank=2,
                 residual_diagnostics_pass=True, same_units=True,
                 eigenspace_diagnostics_pass=True)
        self.assertTrue(all(v.startswith("HOLD")
                            for v in qualify(q)["method_status"].values()))

    def test_pca_high_dimensional_and_low_rank_hold(self):
        for n, p, rank in ((12, 20, 12), (20, 5, 3), (4, 4, 4)):
            with self.subTest(n=n, p=p, rank=rank):
                q = baseline()
                q.update(independent_units=n, feature_count=p,
                         independence_verified=True, same_scope=True,
                         same_units=True, eigenspace_diagnostics_pass=True,
                         covariance_rank=rank)
                self.assertEqual(qualify(q)["method_status"]["pca"],
                                 "HOLD_DESIGN_NOT_QUALIFIED")

    def test_bt_disconnected_graph_does_not_earn_win_probability(self):
        q = baseline()
        q.update(independent_units=40, feature_count=2,
                 independence_verified=True, same_scope=True,
                 pairwise_comparisons=30, group_sizes=[20, 20],
                 finite_bt_fit_conditions=True)
        self.assertEqual(qualify(q)["method_status"]["bradley_terry"],
                         "HOLD_DESIGN_NOT_QUALIFIED")

    def test_manova_needs_covariance_rank_and_residual_design(self):
        q = baseline()
        q.update(independent_units=8, feature_count=5,
                 group_sizes=[4, 4], independence_verified=True,
                 same_scope=True, residual_diagnostics_pass=True,
                 covariance_rank=4)
        self.assertEqual(qualify(q)["method_status"]["anova"],
                         "ELIGIBLE_FOR_PROVIDER_REVIEW")
        self.assertEqual(qualify(q)["method_status"]["manova"],
                         "HOLD_DESIGN_NOT_QUALIFIED")

    def test_reject_false_counts_and_authority(self):
        for key, value in (("independent_units", True), ("feature_count", -1),
                           ("successes", 4), ("pairwise_comparisons", -1),
                           ("covariance_rank", False)):
            with self.subTest(key=key):
                q = baseline()
                q[key] = value
                if key == "successes":
                    q["independent_units"] = 2
                with self.assertRaises(ValueError):
                    qualify(q)
        q = baseline()
        q["authority_transfer"] = True
        with self.assertRaises(ValueError):
            qualify(q)

    def test_zero_independence_does_not_generate_p_over_n(self):
        result = qualify(baseline())
        self.assertIsNone(result["geometry"]["p_over_n"])

    def test_tested_methods_still_route_to_canonical_provider(self):
        result = qualify(baseline())
        self.assertEqual(result["provider"], "GBOGEB/gg_MATH")
        self.assertFalse(result["independent_engineering_acceptance"])


if __name__ == "__main__":
    unittest.main()
