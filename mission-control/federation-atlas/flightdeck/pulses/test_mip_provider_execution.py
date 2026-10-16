"""Provider lineage, confidence ordering and multivariate negative tests."""
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path

from mip_provider_execution import evaluate, main

PROVIDER = Path(os.environ.get("MIP_PROVIDER_ROOT", "providers/gg_MATH"))
SHA = os.environ.get("MIP_PROVIDER_SHA", "8f8542494b36c1476127a02a280b279ec2cf02f9")


def fixture():
    n = 36
    rows = [[float(i) + (i % 4), float((i % 5) * 2) + i / 10,
             float((i % 7) * 3) - i / 12] for i in range(n)]
    paired = [["A", "B"], ["B", "A"], ["A", "C"], ["C", "A"],
              ["B", "C"], ["C", "B"]] * 2
    return {
        "schema": "code-purple.mip.provider-request.v1",
        "data_class": "SYNTHETIC_REFERENCE",
        "authority_transfer": False,
        "provider_sha": SHA,
        "design": {
            "schema": "code-purple.statistical-design.v1",
            "source_bound": True, "cohort_matched": True,
            "authority_transfer": False, "source_sha": "a" * 40,
            "independent_units": n, "feature_count": 3,
            "independence_verified": True, "same_scope": True,
            "same_units": True, "complete_terminal": True,
            "sampling_design_approved": True, "successes": 28,
            "eigenspace_diagnostics_pass": True, "covariance_rank": 3,
            "group_sizes": [12, 12, 12], "residual_diagnostics_pass": True,
            "pairwise_comparisons": len(paired),
            "comparison_graph_connected": True,
            "finite_bt_fit_conditions": True,
        },
        "reference_data": {
            "pca_rows": rows, "pca_reference_rows": rows,
            "anova_groups": [[j + 0.1 * k for j in range(i*12, i*12 + 12)]
                             for i in range(3) for k in ()],
            "winner_loser_pairs": paired,
        },
    }


def ready_fixture():
    data = fixture()
    data["reference_data"]["anova_groups"] = [
        [float(i * 2) + j * .5 + (j % 3) * .7 for j in range(12)]
        for i in range(3)
    ]
    return data


class MathReferenceTests(unittest.TestCase):
    def require_provider(self):
        if not (PROVIDER / "kernels" / "stats_core.py").is_file():
            self.skipTest("pinned gg_MATH provider not checked out locally")

    def test_unverified_native_stays_hold_even_with_claimed_design(self):
        data = ready_fixture()
        data["data_class"] = "NATIVE_UNVERIFIED"
        result = evaluate(data)
        self.assertFalse(result["provider_executed"])
        self.assertTrue(all(v["status"] ==
                            "HOLD_NATIVE_INDEPENDENCE_NOT_ATTESTED"
                            for v in result["methods"].values()))
        self.assertIsNone(result["source_trials_independently_authenticated"])

    def test_pinned_provider_reference_all_supported_methods(self):
        self.require_provider()
        r = evaluate(ready_fixture(), provider_root=PROVIDER)
        self.assertEqual(r["provider_sha"], SHA)
        self.assertTrue(r["provider_executed"])
        bands = r["methods"]["wilson"]["confidence_bands"]
        self.assertEqual(set(bands), {"90", "95", "99"})
        widths = [v["interval"][1] - v["interval"][0] for v
                  in (bands["90"], bands["95"], bands["99"])]
        self.assertLess(widths[0], widths[1])
        self.assertLess(widths[1], widths[2])
        self.assertAlmostEqual(sum(r["methods"]["pca"][
            "explained_variance_ratio"]), 1.0, places=7)
        self.assertGreaterEqual(r["methods"]["pca"]["eigengap_1_2"], 0)
        self.assertIsNotNone(r["methods"]["pca"]["temporal_alignment"])
        self.assertGreaterEqual(r["methods"]["anova"]["eta_squared"], 0)
        self.assertLessEqual(r["methods"]["anova"]["eta_squared"], 1)
        self.assertIsNone(r["methods"]["anova"]["p_value"])
        fit = r["methods"]["bradley_terry"]
        self.assertEqual(fit["status"], "SYNTHETIC_REFERENCE_ONLY")
        self.assertEqual(fit["comparison_n"], 12)
        self.assertGreaterEqual(len(fit["pairwise_probabilities"]), 3)
        pair = fit["pairwise_probabilities"][0]["intervals"]
        for level in ("90", "95", "99"):
            self.assertLessEqual(pair[level]["interval"][0],
                                 pair[level]["probability"])
            self.assertGreaterEqual(pair[level]["interval"][1],
                                    pair[level]["probability"])
        self.assertIn("HOLD_CANONICAL_PROVIDER", r["methods"]["manova"]["status"])
        self.assertFalse(r["numerical_reference_is_process_inference"])
        self.assertEqual(r["admission"], "HOLD")
        self.assertFalse(r["merge_authorized"])

    def test_provider_wrong_sha_rejected_without_fallback(self):
        self.require_provider()
        data = ready_fixture()
        data["provider_sha"] = "f" * 40
        with self.assertRaisesRegex(ValueError, "SHA mismatch"):
            evaluate(data, provider_root=PROVIDER)

    def test_unsupported_evidence_class_and_claimed_authority_rejected(self):
        for mutate in (
            lambda p: p.update(data_class="NATIVE_ACCEPTED"),
            lambda p: p.update(authority_transfer=True),
            lambda p: p["design"].update(authority_transfer=True),
        ):
            data = ready_fixture()
            mutate(data)
            with self.assertRaises(ValueError):
                evaluate(data, provider_root=PROVIDER)

    def test_pca_wrong_population_does_not_fit(self):
        self.require_provider()
        data = ready_fixture()
        data["reference_data"]["pca_rows"].pop()
        with self.assertRaisesRegex(ValueError, "PCA observations"):
            evaluate(data, provider_root=PROVIDER)

    def test_temporal_mismatch_rejected(self):
        self.require_provider()
        data = ready_fixture()
        data["reference_data"]["pca_reference_rows"][0].pop()
        with self.assertRaisesRegex(ValueError, "temporal PCA"):
            evaluate(data, provider_root=PROVIDER)

    def test_bt_unqualified_disconnected_design_does_not_fake_probability(self):
        self.require_provider()
        data = ready_fixture()
        pairs = [["A", "B"]] * 6 + [["C", "D"]] * 6
        data["reference_data"]["winner_loser_pairs"] = pairs
        report = evaluate(data, provider_root=PROVIDER)
        self.assertTrue(report["methods"]["bradley_terry"]["status"].startswith(
            "HOLD_"))
        self.assertIsNone(report["methods"]["bradley_terry"][
            "pairwise_probabilities"])

    def test_numeric_reference_bytes_reproducible(self):
        self.require_provider()
        req = ready_fixture()
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / "request.json"
            out = Path(t) / "receipt.json"
            src.write_text(json.dumps(req))
            self.assertEqual(main(["--input", str(src), "--provider-root",
                                   str(PROVIDER), "--out", str(out)]), 0)
            prior = out.read_bytes()
            self.assertEqual(main(["--input", str(src), "--provider-root",
                                   str(PROVIDER), "--out", str(out)]), 0)
            self.assertEqual(prior, out.read_bytes())
            self.assertEqual(json.loads(prior)["qps_acceptance"], "DEFER")


if __name__ == "__main__":
    unittest.main()
