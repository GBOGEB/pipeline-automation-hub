"""H3 negative controls: no candidate can silently delete enforced recovery listeners."""
import unittest
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("mip_h3_guard", HERE / "h3_event_retirement_guard.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class EventRetirementSafetyTests(unittest.TestCase):
    def test_existing_exact_population_is_preserved_not_reduced(self):
        expected = ["A", "B", "C"]
        out = M.assess(expected, expected, expected)
        self.assertEqual(out["state"], "BASELINE_PRESERVED")
        self.assertFalse(out["production_event_reduction"])
        self.assertFalse(out["merge_authorized"])

    def test_retiring_one_enforced_gate_is_hold(self):
        out = M.assess(["A", "B"], ["A", "B"], ["A"])
        self.assertEqual(out["state"], "HOLD")
        self.assertEqual(out["candidate_missing_enforced"], ["B"])

    def test_fake_replacement_labels_do_not_authorize_retirement(self):
        out = M.assess(["A"], ["A"], ["replacement-A"])
        self.assertEqual(out["state"], "HOLD")
        self.assertEqual(out["candidate_missing_enforced"], ["A"])

    def test_current_population_drift_is_hold(self):
        for live in (["A"], ["A", "B", "unexpected"]):
            out = M.assess(["A", "B"], live, live)
            self.assertEqual(out["state"], "HOLD")

    def test_duplicate_names_are_hold(self):
        out = M.assess(["A"], ["A", "A"], ["A"])
        self.assertEqual(out["state"], "HOLD")

    def test_non_list_or_non_text_is_hold(self):
        for proposed in ("A", ["A", None], {"name": "A"}):
            self.assertEqual(M.assess(["A"], ["A"], proposed)["state"], "HOLD")


if __name__ == "__main__":
    unittest.main()
