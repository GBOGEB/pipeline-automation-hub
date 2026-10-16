"""Native cross-repository consumer tests: only pinned gg_MATH owns the math.

The fixture 5/10 is synthetic. No ABACUS workflow inference or QPS authority.
"""
from __future__ import annotations

import importlib.util
import subprocess
import unittest
from pathlib import Path

PROVIDER_SHA = "40ab86f2c821f50a85ace1556f656197b317e795"
PROVIDER = Path(__file__).resolve().parents[4] / "providers" / "gg_MATH"
SOURCE = PROVIDER / "kernels" / "stats_core.py"


class PinnedMathProviderContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SOURCE.is_file():
            raise RuntimeError("pinned canonical gg_MATH source checkout missing")
        spec = importlib.util.spec_from_file_location(
            "canonical_gg_math_stats_core", SOURCE
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load canonical mathematical source")
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def test_exact_provider_commit_and_binary_source(self):
        observed = subprocess.check_output(
            ["git", "-C", str(PROVIDER), "rev-parse", "HEAD"], text=True
        ).strip()
        self.assertEqual(observed, PROVIDER_SHA)
        self.assertEqual(self.module.__file__, str(SOURCE))

    def test_fixed_horizon_reference_bands_90_95_99(self):
        expected = {
            .90: (.269271, .730729),
            .95: (.236593, .763407),
            .99: (.184226, .815774),
        }
        bands = []
        for level, pair in expected.items():
            with self.subTest(level=level):
                result = self.module.wilson_proportion_interval(
                    5, 10, level=level
                )
                lo, hi = result["interval"]
                self.assertAlmostEqual(lo, pair[0], places=5)
                self.assertAlmostEqual(hi, pair[1], places=5)
                self.assertEqual(result["method"],
                                 "WILSON_SCORE_FIXED_HORIZON_TWO_SIDED")
                self.assertFalse(result["authority_transfer"])
                self.assertIsNone(result["independence_authenticated"])
                bands.append((lo, hi))
        self.assertLessEqual(bands[2][0], bands[1][0])
        self.assertLessEqual(bands[1][0], bands[0][0])
        self.assertLessEqual(bands[0][1], bands[1][1])
        self.assertLessEqual(bands[1][1], bands[2][1])

    def test_invalid_sampling_counts_rejected_at_provider(self):
        for k, n in ((True, 2), (3, 2), (1, 0)):
            with self.subTest(k=k, n=n):
                with self.assertRaises(ValueError):
                    self.module.wilson_proportion_interval(k, n)

    def test_reference_exposes_no_ci_or_engineering_admission(self):
        result = self.module.wilson_proportion_interval(5, 10)
        self.assertEqual(result["status"], "REFERENCE_ONLY_DESIGN_UNVERIFIED")
        self.assertNotIn("merge_authorized", result)
        self.assertNotIn("qps_accepted", result)
        self.assertIn("fixed horizon", result["assumptions"])


if __name__ == "__main__":
    unittest.main()
