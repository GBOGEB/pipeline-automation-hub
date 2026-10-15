"""GOGREEN controlled probe does not stress real services or transfer authority."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gogreen_probe", ROOT / "synthetic_probe.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class SyntheticQueueTests(unittest.TestCase):
    def test_positive_control_and_bounded_queue(self):
        result = probe.run(total=18, queue_depth=3, workers=2, cycles=2)
        self.assertEqual(result["outcome"], "LOCAL_PROBE_PASS")
        self.assertTrue(result["synthetic"])
        self.assertFalse(result["child_stress_admitted"])
        self.assertFalse(result["merge_authorized"])
        self.assertIsNone(result["independent_trials"])
        self.assertEqual(2, len(result["iterations"]))
        self.assertTrue(all(x["processed"] == 18 and x["faults"] == 0 and x["max_queue"] <= 3 and x["peak_in_flight"] <= 2 for x in result["iterations"]))

    def test_negative_control_detects_injected_fault(self):
        result = probe.run(total=7, queue_depth=2, workers=2, cycles=3, inject_failure=2)
        self.assertEqual(result["outcome"], "EXPECTED_FAULT_OBSERVED")
        self.assertEqual(sum(x["faults"] for x in result["iterations"]), 3)
        self.assertFalse(result["child_stress_admitted"])

    def test_limits_reject_unbounded_scale(self):
        for kwargs in ({"total": 65}, {"queue_depth": 9}, {"workers": 5}, {"cycles": 4},
                       {"workers": True}, {"total": 0}, {"inject_failure": 99}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                probe.run(**kwargs)


if __name__ == "__main__":
    unittest.main()
