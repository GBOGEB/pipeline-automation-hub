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

    def test_live_counts_drive_the_test_probes_when_present(self):
        # Archived zero-case files and modules stay counted but do not decide the live-code probes.
        live = {"files": 6, "cases": 40, "zero_case_files": 4, "py_modules": 30, "py_untested": 21,
                "live_zero_case_files": 0, "live_py_modules": 10, "live_py_untested": 1}
        states = L.probe_states(good_facts(tests=live))
        self.assertEqual((states["test.fail_closed"], states["test.controlled"]), (L.PASS, L.PASS))
        live.update(live_zero_case_files=1, live_py_untested=3)
        states = L.probe_states(good_facts(tests=live))
        self.assertEqual((states["test.fail_closed"], states["test.controlled"]), (L.FAIL, L.FAIL))


class Formalization(unittest.TestCase):
    def test_four_states(self):
        self.assertEqual(L.formalization([4, 1], True), "FORMALIZED")
        self.assertEqual(L.formalization([1], True), "PARTIAL")
        self.assertEqual(L.formalization([3, 0], False), "PARTIAL")
        self.assertEqual(L.formalization([2, 1], False), "INFORMAL")
        self.assertEqual(L.formalization([0, 0], False), "ABSENT")
        self.assertEqual(L.formalization([], False), "ABSENT")



class RFPulse(unittest.TestCase):
    SHA = "a" * 40

    def s(self, ident, **kw):
        item = {"id": ident, "cluster": "alpha", "phase": "P1_PILOT", "crew": "SCOUT",
                "state": "READY", "source_sha": self.SHA,
                "t0_ref": "actions_metrics@T0/run-100", "depends_on": []}
        item.update(kw)
        return item

    def plan(self, steps, **kw):
        return L.rf_pulse_plan(steps, source_sha=self.SHA, **kw)

    def test_decreasing_maturity_not_governance(self):
        self.assertEqual(list(L.RF_PHASE_MATURITY.values()), [5, 4, 3, 2, 1])
        p = self.plan([self.s("scout", phase="P4_SCOUT")])
        self.assertEqual(p["on"][0]["qualification_target"], 1)
        self.assertFalse(p["authority"]["merge_authorized"])
        self.assertFalse(p["authority"]["dispatch_performed"])

    def test_parallel_clusters_and_off_interval(self):
        p = self.plan([self.s("a"), self.s("b", cluster="beta"),
                       self.s("c", cluster="alpha")], per_cluster=1)
        self.assertEqual([s["id"] for s in p["on"]], ["a", "b"])
        self.assertEqual(p["held"], [{"id": "c", "reason": "CLUSTER_CAP"}])
        self.assertTrue(all(x["mode"] == "TAKE_STOCK_NEXT_PULSE" for x in p["off"]))

    def test_dependencies_done_only(self):
        p = self.plan([self.s("a"), self.s("b", depends_on=["a"])])
        self.assertIn({"id": "b", "reason": "DEPENDENCY_NOT_DONE"}, p["held"])
        p = self.plan([self.s("a", state="DONE"), self.s("b", depends_on=["a"])])
        self.assertEqual([s["id"] for s in p["on"]], ["b"])

    def test_unknown_dependency_and_cycle(self):
        with self.assertRaises(ValueError):
            self.plan([self.s("a", depends_on=["missing"])])
        with self.assertRaises(ValueError):
            self.plan([self.s("a", depends_on=["b"]), self.s("b", depends_on=["a"])])

    def test_stale_source_and_missing_t0_hold(self):
        p = self.plan([self.s("a", source_sha="b" * 40), self.s("b", t0_ref=None)])
        self.assertEqual([s["reason"] for s in p["held"]],
                         ["STALE_SOURCE_SHA", "MISSING_T0_RECEIPT"])

    def test_pr_cap_and_disjoint_write_paths(self):
        a = self.s("a", write_pr=True, touch_paths=["a.py"])
        b = self.s("b", cluster="beta", write_pr=True, touch_paths=["a.py"])
        self.assertEqual(self.plan([a, b], max_stack=2, open_stack=1)["held"],
                         [{"id": "b", "reason": "PR_STACK_CAP"}])
        self.assertEqual(self.plan([a, b])["held"],
                         [{"id": "b", "reason": "OVERLAPPING_PATHS"}])

    def test_failed_work_enters_off_repair(self):
        p = self.plan([self.s("red", state="FAILED"), self.s("ready")])
        self.assertEqual(next(x for x in p["off"] if x["id"] == "red")["mode"], "REPAIR_FIRST_RED")
        self.assertEqual([s["id"] for s in p["on"]], ["ready"])

    def test_capacity_and_invalid_inputs(self):
        p = self.plan([self.s("a"), self.s("b", cluster="beta")], max_parallel=1, per_cluster=1)
        self.assertEqual(p["held"], [{"id": "b", "reason": "PARALLEL_CAP"}])
        for kw in ({"max_parallel": 0}, {"open_stack": 6}, {"per_cluster": 0}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                self.plan([self.s("a")], **kw)
        for row in (self.s("a", crew="MAGIC"), self.s("a", write_pr=True),
                    self.s("a", touch_paths=["../x"])):
            with self.subTest(row=row), self.assertRaises(ValueError):
                self.plan([row])


    def test_unknown_duplicate_and_invalid_sha(self):
        with self.assertRaises(ValueError):
            self.plan([self.s("duplicate"), self.s("duplicate")])
        with self.assertRaises(ValueError):
            L.rf_pulse_plan([], source_sha="X" * 40)

    def test_nonready_candidate_never_dispatches(self):
        p = self.plan([self.s("hold", state="HOLD"), self.s("running", state="RUNNING")])
        self.assertEqual(p["on"], [])
        self.assertEqual([x["reason"] for x in p["held"]], ["NOT_READY", "NOT_READY"])

    def test_completed_ancestor_is_not_rescheduled(self):
        p = self.plan([self.s("complete", state="DONE"), self.s("child",
                       depends_on=["complete"])])
        self.assertEqual([x["id"] for x in p["on"]], ["child"])
        self.assertNotIn("complete", [x["id"] for x in p["off"]])

    def test_terminal_rows_are_source_bound(self):
        stale_done = self.s("a", state="DONE", source_sha="b" * 40)
        p = self.plan([stale_done, self.s("child", depends_on=["a"])])
        self.assertEqual(p["on"], [])
        self.assertEqual(p["held"], [{"id": "child", "reason": "DEPENDENCY_NOT_DONE"}])
        p = self.plan([self.s("red", state="FAILED", t0_ref=None),
                       self.s("old", state="FAILED", source_sha="b" * 40)])
        self.assertEqual(p["off"], [])
        self.assertEqual(sorted((x["id"], x["reason"]) for x in p["held"]),
                         [("old", "STALE_SOURCE_SHA"), ("red", "MISSING_T0_RECEIPT")])

    def test_aliased_write_paths_rejected(self):
        for path in ("./a.py", "a//b.py", "a/./b.py", "a\\b.py", "a/", "/a.py"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.plan([self.s("a", write_pr=True, touch_paths=[path])])

    def test_missing_t0_is_not_inferred_from_other_worker(self):
        p = self.plan([self.s("a", t0_ref="receipt"),
                       self.s("b", cluster="beta", t0_ref="")])
        self.assertEqual([x["id"] for x in p["on"]], ["a"])
        self.assertEqual(p["held"], [{"id": "b", "reason": "MISSING_T0_RECEIPT"}])

if __name__ == "__main__":
    unittest.main()
