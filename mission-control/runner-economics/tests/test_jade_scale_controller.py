"""Negative and positive scaling decision tests, no network or fake workers."""
from pathlib import Path
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("controller", ROOT / "jade_scale_controller.py")
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)


def pulse(i, **updates):
    p = {"source_sha": "a" * 40, "instrumentor_sha": "b" * 40,
         "source_scope": "JADE_PR_NATIVE", "run_id": i,
         "queued": 2, "running": 3, "ready_disjoint": 22,
         "first_red": 0, "covered": 110, "denominator": 200,
         "zero_covered_files": 8, "native_green": True}
    p.update(updates)
    return p


class ScaleDMAIC(unittest.TestCase):
    def test_native_three_pulse_gain_may_propose_7_not_dispatch(self):
        r = C.decide([pulse(1, covered=100), pulse(2, covered=105),
                      pulse(3, covered=110)])
        self.assertEqual(r["proposed_parallel_ceiling"], 7)
        self.assertFalse(r["dispatch_authorized"])
        self.assertFalse(r["merge_authorized"])
        self.assertEqual(r["release_credit"], 0)
        self.assertIsNone(r["crew_workers_actually_launched"])

    def test_queue_pressure_contracts_from_15_to_7(self):
        r = C.decide([pulse(1), pulse(2), pulse(3, queued=60, running=2)],
                     current=15)
        self.assertEqual(r["proposed_parallel_ceiling"], 7)
        self.assertTrue(r["queue_backpressure"])

    def test_first_red_routes_doctor_before_parallelism(self):
        r = C.decide([pulse(1), pulse(2), pulse(3, first_red=1)])
        self.assertEqual(r["mode"], "FIRST_RED_ROUTE_DOCTOR")
        self.assertEqual(r["proposed_parallel_ceiling"], 3)

    def test_three_green_without_gain_holds(self):
        r = C.decide([pulse(1), pulse(2), pulse(3)])
        self.assertEqual(r["mode"], "NO_MEASURED_COVERAGE_OR_ZERO_GAP_GAIN")

    def test_zero_covered_reduction_counts_only_on_matched_scope(self):
        r = C.decide([pulse(1), pulse(2, zero_covered_files=7),
                      pulse(3, zero_covered_files=6)])
        self.assertTrue(r["measured_gain"])
        self.assertEqual(r["zero_covered_file_delta"], -2)

    def test_different_instrumentor_blocks_gain(self):
        r = C.decide([pulse(1), pulse(2, instrumentor_sha="c"*40),
                      pulse(3, covered=125)])
        self.assertIsNone(r["covered_lines_delta"])
        self.assertFalse(r["matched_instrumentor_scope_denominator"])

    def test_denominator_change_cannot_be_claimed_uplift(self):
        r = C.decide([pulse(1), pulse(2), pulse(3, denominator=300, covered=250)])
        self.assertFalse(r["measured_gain"])

    def test_duplicate_replay_does_not_establish_three_stable_pulses(self):
        r = C.decide([pulse(1), pulse(1), pulse(2, covered=130)])
        self.assertFalse(r["three_native_green"])
        self.assertEqual(r["proposed_parallel_ceiling"], 3)

    def test_zero_or_boolean_counts_rejected(self):
        for candidate in (pulse(1, denominator=0), pulse(1, queued=True),
                          pulse(1, first_red=-1), pulse(1, run_id=0)):
            with self.subTest(candidate=candidate):
                with self.assertRaises(ValueError):
                    C.decide([candidate])

    def test_insufficient_disjoint_work_holds_even_if_coverage_grows(self):
        r = C.decide([pulse(1, covered=100), pulse(2),
                      pulse(3, ready_disjoint=3)])
        self.assertEqual(r["mode"], "NO_DISJOINT_WORK_TO_MULTIPLY")

    def test_31_is_a_hard_ceiling_not_unbounded_multiplication(self):
        r = C.decide([pulse(1, covered=100), pulse(2),
                      pulse(3, ready_disjoint=99)], current=31)
        self.assertEqual(r["proposed_parallel_ceiling"], 31)


if __name__ == "__main__":
    unittest.main()


def test_zz_canary_g_pah():
    assert False, "red canary: proves CI collects this family"
