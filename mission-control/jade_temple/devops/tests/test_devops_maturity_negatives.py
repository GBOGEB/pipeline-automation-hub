"""JADE maturity and temporal-DAG negative controls.

Adds actual source-bound exercised cases rather than downgrading the existing
native >=89 executed-test requirement. Tests canonical lifecycle.py only.
"""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("jade_devops_lifecycle_negatives", ROOT / "lifecycle.py")
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)


class MaturityNonCompensation(unittest.TestCase):
    def states(self):
        return {pid: L.PASS for pid in L.PROBE_IDS}

    def test_no_stage_can_skip_failed_first_level(self):
        for stage in L.STAGE_KEYS:
            with self.subTest(stage=stage):
                first = next(pid for pid, s, lv, _ in L.PROBES if s == stage and lv == 1)
                states = self.states()
                states[first] = L.FAIL
                result = L.stage_score(states, stage)
                self.assertEqual((result["level"], result["pass"], result["fail"]), (0, 4, 1))

    def test_unknown_at_first_level_is_not_implicit_success(self):
        for stage in L.STAGE_KEYS:
            with self.subTest(stage=stage):
                first = next(pid for pid, s, lv, _ in L.PROBES if s == stage and lv == 1)
                states = self.states()
                states[first] = L.UNKNOWN
                result = L.stage_score(states, stage)
                self.assertEqual((result["level"], result["unknown"]), (0, 1))

    def test_second_level_failure_caps_stage_at_one(self):
        for stage in L.STAGE_KEYS:
            with self.subTest(stage=stage):
                second = next(pid for pid, s, lv, _ in L.PROBES if s == stage and lv == 2)
                states = self.states()
                states[second] = L.FAIL
                self.assertEqual(L.stage_score(states, stage)["level"], 1)

    def test_fifth_level_unknown_caps_stage_at_four(self):
        for stage in L.STAGE_KEYS:
            with self.subTest(stage=stage):
                last = next(pid for pid, s, lv, _ in L.PROBES if s == stage and lv == 5)
                states = self.states()
                states[last] = L.UNKNOWN
                self.assertEqual(L.stage_score(states, stage)["level"], 4)

    def test_completion_fraction_never_promotes_a_failed_stage(self):
        states = self.states()
        states["test.files"] = L.FAIL
        report = L.stage_score(states, "S3_TEST")
        self.assertEqual(report["completion"], 0.8)
        self.assertEqual(report["level"], 0)
        self.assertEqual(report["next_blocker"]["probe"], "test.files")

    def test_mixed_fail_and_unknown_not_compensated_by_other_probes(self):
        states = self.states()
        states["secure.policy"] = L.FAIL
        states["secure.depbot"] = L.UNKNOWN
        report = L.stage_score(states, "S4_SECURE")
        self.assertEqual((report["pass"], report["fail"], report["unknown"]), (3, 1, 1))
        self.assertEqual(report["level"], 0)

    def test_missing_evidence_never_becomes_a_zero_or_pass(self):
        states = self.states()
        states.pop("build.lock")
        with self.assertRaises(KeyError):
            L.stage_score(states, "S2_BUILD")

    def test_one_stage_cannot_compensate_another_stage_red(self):
        states = self.states()
        states["control.no_red"] = L.FAIL
        scored = L.score(states)
        self.assertEqual(scored["S9_CONTROL"]["level"], 4)
        self.assertEqual(scored["S0_PLAN"]["level"], 5)
        self.assertEqual(len(scored), 10)

    def test_unrelated_unknown_cannot_affect_another_stage(self):
        states = self.states()
        states["deploy.contract"] = L.UNKNOWN
        scored = L.score(states)
        self.assertEqual(scored["S3_TEST"]["level"], 5)
        self.assertEqual(scored["S6_DEPLOY"]["level"], 3)


class TemporalGraphNonCompensation(unittest.TestCase):
    def test_feedback_only_edges_do_not_create_same_pulse_dependencies(self):
        layers = L.topo_layers(["a", "b"], [("b", "a", "FEEDBACK_NEXT_PULSE")])
        self.assertEqual(layers, [["a", "b"]])

    def test_temporal_feedback_source_still_requires_known_identity(self):
        with self.assertRaises(ValueError):
            L.topo_layers(["a"], [("ghost", "a", "FEEDBACK_NEXT_PULSE")])

    def test_a_feedforward_cycle_cannot_be_hidden_by_feedback(self):
        edges = [("a", "b", "FEEDFORWARD"), ("b", "a", "FEEDFORWARD"),
                 ("a", "b", "FEEDBACK_NEXT_PULSE")]
        with self.assertRaisesRegex(ValueError, "cycle"):
            L.topo_layers(["a", "b"], edges)

    def test_partial_maturity_without_written_contract_is_not_formalized(self):
        self.assertEqual(L.formalization([5, 4], False), "PARTIAL")
        self.assertEqual(L.formalization([0, 0], True), "PARTIAL")
        self.assertEqual(L.formalization([4, 0], True), "FORMALIZED")

    def test_missing_ratio_and_boolean_evidence_remains_unknown(self):
        self.assertIsNone(L._ratio_ok(9, 0, 0.9))
        self.assertEqual(L._b(None), L.UNKNOWN)
        self.assertEqual(L._b(False), L.FAIL)
        self.assertEqual(L._b(True), L.PASS)



    def test_no_stage_can_be_promoted_by_five_explicit_failures(self):
        states = {pid: L.FAIL for pid in L.PROBE_IDS}
        for stage in L.STAGE_KEYS:
            with self.subTest(stage=stage):
                score = L.stage_score(states, stage)
                self.assertEqual(score["level"], 0)
                self.assertEqual((score["pass"], score["fail"], score["unknown"]), (0, 5, 0))

    def test_all_unknown_probes_are_not_five_successes(self):
        states = {pid: L.UNKNOWN for pid in L.PROBE_IDS}
        for stage in L.STAGE_KEYS:
            with self.subTest(stage=stage):
                score = L.stage_score(states, stage)
                self.assertEqual(score["level"], 0)
                self.assertEqual((score["pass"], score["fail"], score["unknown"]), (0, 0, 5))

    def test_disjoint_parallel_inputs_join_only_after_both_sources(self):
        layers = L.topo_layers(
            ["source-a", "source-b", "join"],
            [("source-a", "join", "FEEDFORWARD"),
             ("source-b", "join", "FEEDFORWARD")],
        )
        self.assertEqual(layers, [["source-a", "source-b"], ["join"]])


if __name__ == "__main__":
    unittest.main()
