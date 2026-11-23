"""C-PATH (devops/cpath.py): CPM float over Kahn order, criticality, unlock, back-pressure, policies (offline)."""
import importlib.util
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
JADE = HERE.parent
QPS = HERE.parents[1] / "qps-triage-ultra"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


C = load("cpath", HERE / "cpath.py")
GATES = json.loads((JADE / "data" / "ROLLING5_POLICY.json").read_text(encoding="utf-8"))["gate_prerequisites"]
GN = sorted(GATES)
GE = [(p, g) for g, ps in GATES.items() for p in ps]

# Textbook CPM network (activity-on-node): A3 -> B2, A3 -> C4, B2 -> D1, C4 -> D1.
TN = ["A", "B", "C", "D"]
TE = [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")]
TD = {"A": 3, "B": 2, "C": 4, "D": 1}


class CpmTests(unittest.TestCase):
    def test_textbook_numbers(self):
        r = C.cpm(TN, TE, TD)
        self.assertEqual(r["makespan"], 8)
        n = r["nodes"]
        self.assertEqual((n["B"]["es"], n["B"]["ls"], n["B"]["total_float"]), (3, 5, 2))
        self.assertEqual(n["B"]["free_float"], 2)
        self.assertEqual(r["critical_path"], ["A", "C", "D"])
        self.assertEqual(r["critical_set"], ["A", "C", "D"])

    def test_done_work_moves_the_path(self):
        r = C.cpm(TN, TE, TD, done={"A", "C"})
        self.assertEqual(r["makespan"], 3)
        self.assertEqual(r["critical_path"], ["B", "D"])

    def test_unit_durations_match_owner_hop_count(self):
        dag = load("cicd_dag_for_cpath_test", JADE / "tools" / "cicd_dag.py")
        hop = dag.critical_path(GATES)
        r = C.cpm(GN, GE)
        self.assertEqual(r["makespan"], len(hop))
        self.assertEqual(r["critical_path"], hop)
        # CPM also exposes the tie the hop count hides.
        self.assertIn("H11", r["critical_set"])

    def test_remaining_gate_path_shifts_to_h08(self):
        done = {"H01", "H02", "H04", "H05", "H06"}
        full = C.cpm(GN, GE)
        self.assertEqual(full["nodes"]["H08"]["total_float"], 2)
        r = C.cpm(GN, GE, done=done)
        self.assertEqual(r["critical_path"], ["H08", "H09", "H12"])

    def test_cycle_is_condensed_and_reported(self):
        r = C.cpm(["X", "Y", "Z"], [("X", "Y"), ("Y", "X"), ("Y", "Z")])
        self.assertEqual(r["cycles"], [["X", "Y"]])
        self.assertEqual(r["nodes"]["X"]["component"], r["nodes"]["Y"]["component"])
        self.assertEqual(r["makespan"], 3)

    def test_unknown_endpoint_fails_closed(self):
        with self.assertRaises(ValueError):
            C.cpm(["A"], [("A", "Q")])

    def test_unknown_duration_is_not_zero(self):
        self.assertEqual(C.cpm(TN, TE)["makespan"], 3)


class UncertaintyTests(unittest.TestCase):
    def test_criticality_bounds_and_certain_nodes(self):
        r = C.criticality(TN, TE, spread={k: (v, v, v) for k, v in TD.items()}, samples=50)
        self.assertEqual(r["index"]["A"], 1.0)
        self.assertEqual(r["index"]["B"], 0.0)
        self.assertEqual(r["makespan"]["p50"], 8)

    def test_criticality_splits_a_tie(self):
        r = C.criticality(GN, GE, samples=200)
        self.assertGreater(r["index"]["H10"], 0.2)
        self.assertGreater(r["index"]["H11"], 0.2)
        self.assertEqual(r["index"]["H01"], 1.0)


class UnlockTests(unittest.TestCase):
    def test_frontier_releases_and_relief(self):
        u = C.unlock(GN, GE, done={"H01", "H02"})
        self.assertEqual(u["ready_now"], ["H03", "H04", "H08"])
        self.assertEqual(u["releases"]["H04"], ["H05", "H06", "H07"])
        self.assertEqual(u["releases"]["H08"], ["H09"])
        self.assertEqual(u["relief"]["H04"], 6)

    def test_relief_can_be_skipped(self):
        self.assertEqual(C.unlock(GN, GE, relief=False)["relief"], {})


class BackpressureTests(unittest.TestCase):
    Q = [{"id": "B1", "class": "REVIEW_WAIT", "priority_score": 1.0},
         {"id": "B2", "class": "OWNER_HOLD", "priority_score": 1.0}]
    CW = {"REVIEW_WAIT": "SEMANTIC_BOUNDARY_GUARD_REPAIR", "OWNER_HOLD": "UNREPAIRED_BASELINE"}

    @classmethod
    def setUpClass(cls):
        cls.pca = json.loads((QPS / "w3_measured_analytics_receipt.json").read_text(encoding="utf-8"))
        cls.bt = json.loads((QPS / "w3_observed_bt_receipt.json").read_text(encoding="utf-8"))

    def test_committed_evidence_is_too_thin_so_neutral(self):
        r = C.backpressure(self.Q, self.pca, self.bt, crosswalk=self.CW)
        self.assertEqual(r["status"], "NEUTRAL_HOLD")
        self.assertTrue(all(q["bp_weight"] == 1.0 for q in r["queue"]))
        self.assertEqual(r["wip_cap"], r["base_wip"])
        self.assertTrue(any(x.startswith("BT_HOLD") for x in r["reasons"]))
        self.assertTrue(any(x.startswith("PCA_HOLD") for x in r["reasons"]))

    def test_no_crosswalk_holds_bt_even_with_enough_pairs(self):
        r = C.backpressure(self.Q, self.pca, self.bt, min_bt_pairs=1)
        self.assertEqual(r["channels"]["bt"], "HOLD")
        self.assertIn("crosswalk", " ".join(r["reasons"]))

    def test_mechanism_when_gates_cleared(self):
        r = C.backpressure(self.Q, self.pca, self.bt, crosswalk=self.CW, min_bt_pairs=2, min_pca_rows=3)
        self.assertEqual(r["status"], "APPLIED")
        w = {q["id"]: q["bp_weight"] for q in r["queue"]}
        self.assertGreater(w["B1"], 1.0)
        self.assertLess(w["B2"], 1.0)
        self.assertEqual(r["queue"][0]["id"], "B1")
        self.assertLess(r["wip_cap"], r["base_wip"])
        self.assertGreaterEqual(r["wip_cap"], 1)

    def test_bt_not_pass_holds(self):
        bt = {"current_frontier": {"pair_count": 9, "result": {"status": "HOLD", "scores": {}}}}
        r = C.backpressure(self.Q, None, bt, crosswalk=self.CW, min_bt_pairs=1)
        self.assertEqual(r["status"], "NEUTRAL_HOLD")


class CrosswalkTests(unittest.TestCase):
    """The owner-approved BD -> BT crosswalk (decision 1 on #1276) is real data, not prose."""

    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads((JADE / "data" / "BD_BT_CROSSWALK.json").read_text(encoding="utf-8"))
        cls.bt = json.loads((QPS / "w3_observed_bt_receipt.json").read_text(encoding="utf-8"))
        cls.pca = json.loads((QPS / "w3_measured_analytics_receipt.json").read_text(encoding="utf-8"))
        bd = HERE.parents[1] / "v2/handoff/closeout/w11-gmic-r2-p0008/BD_B01_B46_READONLY.json"
        cls.bd = json.loads(bd.read_text(encoding="utf-8"))

    def test_approved_and_well_formed(self):
        self.assertEqual(self.doc["schema"], "jade.cpath.bd-bt-crosswalk.v1")
        self.assertEqual(self.doc["decision"], "OWNER_APPROVED")
        self.assertEqual(set(self.doc["map"]), {"REVIEW_WAIT", "ACTIONABLE", "OWNER_HOLD", "DEPENDENCY_HOLD"})

    def test_keys_are_bd_states_and_values_are_bt_interventions(self):
        states = {i["state"] for i in self.bd["items"]}
        scores = self.bt["current_frontier"]["result"]["scores"]
        for state, iv in self.doc["map"].items():
            self.assertIn(state, states, state)
            self.assertIn(iv, scores, iv)

    def test_approval_alone_does_not_switch_pressure_on(self):
        q = [{"id": i["id"], "class": i["state"], "priority_score": 1.0}
             for i in self.bd["items"] if i["state"] != "DONE"]
        r = C.backpressure(q, self.pca, self.bt, crosswalk=self.doc["map"])
        self.assertEqual(r["status"], "NEUTRAL_HOLD")
        self.assertFalse(any("crosswalk" in x for x in r["reasons"]))  # only evidence gates hold it now
        self.assertTrue(all(x["bp_weight"] == 1.0 for x in r["queue"]))


class PolicyTests(unittest.TestCase):
    def test_every_policy_respects_precedence_and_bounds(self):
        names, edges = C.random_dag(300, seed=3)
        for p in C.POLICIES:
            r = C.simulate(names, edges, workers=4, policy=p)
            self.assertGreaterEqual(r["makespan"] + 1e-9, r["lower_bound"])
            self.assertEqual(r["items"], 300)

    def test_cpath_first_reaches_lower_bound_when_capacity_balances_path(self):
        import random
        names, edges = C.random_dag(2000, seed=11)
        rng = random.Random(11)
        dur = {k: min(20.0, rng.lognormvariate(0.0, 0.8)) for k in names}
        order = names[:]
        rng.shuffle(order)
        age = {k: i for i, k in enumerate(order)}
        span = C.cpm(names, edges, dur)["makespan"]
        w = max(1, round(sum(dur.values()) / span))
        fifo = C.simulate(names, edges, dur, workers=w, policy="FIFO", age=age)
        cp = C.simulate(names, edges, dur, workers=w, policy="CPATH", age=age)
        self.assertLess(cp["makespan"], fifo["makespan"])
        self.assertLess(cp["makespan"], 1.02 * cp["lower_bound"])

    def test_wip_cap_limits_concurrency(self):
        names, edges = C.random_dag(200, seed=5)
        free = C.simulate(names, edges, workers=8, policy="CPATH")
        capped = C.simulate(names, edges, workers=8, policy="CPATH", wip_cap=2)
        self.assertEqual(capped["wip_cap"], 2)
        self.assertGreaterEqual(capped["makespan"], free["makespan"])

    def test_unknown_policy_rejected(self):
        with self.assertRaises(ValueError):
            C.simulate(TN, TE, policy="RANDOM")

    def test_synergy_arithmetic(self):
        res = {"FIFO": {"m": 100.0}, "CPATH": {"m": 80.0}, "UNLOCK": {"m": 90.0}, "COMBO": {"m": 72.0}}
        s = C.synergy(res, "m")
        self.assertAlmostEqual(s["multiplicative_prediction"], 0.28)
        self.assertEqual(s["verdict"], "MULTIPLICATIVE")
        res["COMBO"]["m"] = 80.0
        self.assertEqual(C.synergy(res, "m")["verdict"], "OVERLAP")


if __name__ == "__main__":
    unittest.main()
