"""JADE N+9 lifecycle model: stage graph, SIPOC, ladder scoring and formalization (offline)."""
import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


L = load("lifecycle")


def good_facts(**over):
    wf = {k: 1 for k in ("lint", "typecheck", "precommit", "build", "artifact_digest", "tests_ci", "zero_test_guard",
                         "zero_test_guard_implicit", "security", "provenance", "release", "release_gated",
                         "release_provenance", "deploy", "deploy_env", "deploy_contract_core", "deploy_verified",
                         "verify", "rollback", "scheduled", "scheduled_verify", "alerting", "gates")}
    wf.update(actions_total=10, actions_pinned=10, workflows=3, permissions_declared=3, write_all=0,
              coverage_floor_max=90.0)
    f = {"has": lambda k: True, "wf": wf,
         "tests": {"files": 4, "cases": 40, "zero_case_files": 0, "py_modules": 10, "py_untested": 1},
         "tags": {"count": 3}, "pages": {"status": 200, "source_sha_match": True},
         "api": {"protected": True, "protected_production": True},
         "red_trace": {"counts": {"EVERRED": 0}, "currently_red": 0},
         "source_files": 12, "pinned_requirements": True, "declared_version": True}
    f.update(over)
    return f


class Graph(unittest.TestCase):
    def test_ten_stages_in_order_with_unique_keys(self):
        self.assertEqual(len(L.STAGE_KEYS), 10)
        self.assertEqual(L.STAGE_KEYS[0], "S0_PLAN")
        self.assertEqual(L.STAGE_KEYS[-1], "S9_CONTROL")
        self.assertEqual(len(set(L.STAGE_KEYS)), 10)

    def test_feedforward_is_acyclic_and_feedback_unrolls_to_next_pulse(self):
        layers = L.topo_layers(L.STAGE_KEYS, L.EDGES)
        self.assertEqual(layers[0], ["S0_PLAN"])
        self.assertEqual(sorted(sum(layers, [])), sorted(L.STAGE_KEYS))
        feedback = [e for e in L.EDGES if e[2].startswith("FEEDBACK")]
        self.assertEqual(feedback, [("S9_CONTROL", "S0_PLAN", "FEEDBACK_NEXT_PULSE")])

    def test_cycle_and_unknown_endpoint_are_refused(self):
        with self.assertRaises(ValueError):
            L.topo_layers(["a", "b"], [("a", "b", "FEEDFORWARD"), ("b", "a", "FEEDFORWARD")])
        with self.assertRaises(ValueError):
            L.topo_layers(["a"], [("a", "zz", "FEEDFORWARD")])

    def test_every_stage_has_complete_sipoc(self):
        for k in L.STAGE_KEYS:
            self.assertEqual(sorted(L.SIPOC[k]), ["C", "I", "O", "P", "S"], k)
            for part, items in L.SIPOC[k].items():
                self.assertTrue(items and all(isinstance(x, str) and x for x in items), (k, part))

    def test_every_stage_has_a_full_ladder_and_unique_probe_ids(self):
        self.assertEqual(len(L.PROBE_IDS), len(set(L.PROBE_IDS)))
        for k in L.STAGE_KEYS:
            levels = sorted(lv for _p, st, lv, _d in L.PROBES if st == k)
            self.assertEqual(levels, [1, 2, 3, 4, 5], k)

    def test_gate_crosswalk_present(self):
        gates = {k: g for k, _t, _q, g in L.STAGES}
        self.assertIn("H05", gates["S3_TEST"])
        self.assertIn("DP1-DP10", gates["S6_DEPLOY"])
        self.assertIn("P-loop", gates["S9_CONTROL"])


class Ladder(unittest.TestCase):
    def test_all_pass_is_controlled(self):
        states = L.probe_states(good_facts())
        self.assertEqual(set(states.values()), {L.PASS})
        for k, v in L.score(states).items():
            self.assertEqual((v["level"], v["label"], v["completion"], v["next_blocker"]), (5, "CONTROLLED", 1.0, None), k)

    def test_unknown_caps_level_and_is_not_pass(self):
        states = L.probe_states(good_facts(api={"protected": None, "protected_production": None}))
        self.assertEqual(states["plan.protection"], L.UNKNOWN)
        s = L.score(states)["S0_PLAN"]
        self.assertEqual((s["level"], s["unknown"], s["pass"]), (3, 1, 4))
        self.assertEqual(s["next_blocker"], {"probe": "plan.protection", "state": L.UNKNOWN})

    def test_ladder_is_cumulative_not_best_tier(self):
        states = {p: L.PASS for p in L.PROBE_IDS}
        states["test.files"] = L.FAIL
        s = L.score(states)["S3_TEST"]
        self.assertEqual(s["level"], 0)
        self.assertEqual(s["completion"], 0.8)
        self.assertEqual(s["fail"], 1)

    def test_empty_facts_fail_or_unknown_never_pass(self):
        wf = {k: 0 for k in good_facts()["wf"]}
        wf["coverage_floor_max"] = None
        f = good_facts(has=lambda k: False, wf=wf,
                       tests={"files": 0, "cases": 0, "zero_case_files": 0, "py_modules": 0, "py_untested": 0},
                       tags={"count": None}, pages=None, api=None, red_trace=None, source_files=0,
                       pinned_requirements=False, declared_version=False)
        states = L.probe_states(f)
        self.assertNotIn(L.PASS, states.values())
        self.assertEqual(states["release.tags"], L.UNKNOWN)
        self.assertEqual(states["control.red_trace"], L.UNKNOWN)
        self.assertEqual(states["build.pinned_actions"], L.UNKNOWN)

    def test_live_parity_tristate(self):
        cases = [({"status": None}, L.UNKNOWN), ({"status": 404}, L.FAIL),
                 ({"status": 200, "source_sha_match": None}, L.UNKNOWN),
                 ({"status": 200, "source_sha_match": False}, L.FAIL),
                 ({"status": 200, "source_sha_match": True}, L.PASS)]
        for pages, want in cases:
            with self.subTest(pages=pages):
                self.assertEqual(L.probe_states(good_facts(pages=pages))["monitor.live_parity"], want)

    def test_test_control_requires_floor_and_low_untested_share(self):
        f = good_facts(tests={"files": 4, "cases": 40, "zero_case_files": 0, "py_modules": 10, "py_untested": 3})
        self.assertEqual(L.probe_states(f)["test.controlled"], L.FAIL)
        f = good_facts(tests={"files": 4, "cases": 40, "zero_case_files": 1, "py_modules": 10, "py_untested": 0})
        self.assertEqual(L.probe_states(f)["test.fail_closed"], L.FAIL)


class Formalization(unittest.TestCase):
    def test_four_states(self):
        self.assertEqual(L.formalization([4, 1], True), "FORMALIZED")
        self.assertEqual(L.formalization([1], True), "PARTIAL")
        self.assertEqual(L.formalization([3, 0], False), "PARTIAL")
        self.assertEqual(L.formalization([2, 1], False), "INFORMAL")
        self.assertEqual(L.formalization([0, 0], False), "ABSENT")
        self.assertEqual(L.formalization([], False), "ABSENT")


if __name__ == "__main__":
    unittest.main()
