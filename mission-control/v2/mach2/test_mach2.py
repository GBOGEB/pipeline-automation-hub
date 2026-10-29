"""MACH-II mission/graph/cycle/statistical negative controls. No GitHub calls."""
import copy
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
from mach2 import (build, build_graph, defects_rate, load_manifest, run_event, schedule_sipoc,
                   trend, validate_missions, validate_mycelium, wilson)


def load_tests(loader, tests, pattern):
    # CI discovers only test_mach2.py; carry the GM-IV wave tests with it.
    import test_gm4_frontier
    tests.addTests(loader.loadTestsFromModule(test_gm4_frontier))
    return tests


class Mach2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m, cls.reg = load_manifest()

    def test_gm_ladder_and_protect_gmv(self):
        x=build()
        self.assertEqual([s["frontiers"] for s in x["mission_states"]],[1,2,4,8,16])
        self.assertEqual(x["mission_states"][-1]["state"],"HELD")
        self.assertFalse(x["dispatch_authorized"])

    def test_every_mission_has_mip(self):
        x=build()
        self.assertEqual(x["counts"]["MIP_axes"],15)
        self.assertTrue(all(set(z["MIP"])=={"modernise","innovate","perpetuate"} for z in x["mission_states"]))

    def test_gmv_no_executable_sipoc_nodes(self):
        x=build()
        self.assertTrue(all(not n["id"].startswith("sipoc:GM-V") for n in x["mycelium_graph"]["nodes"]))
        self.assertEqual(x["counts"]["SIPOC_steps"],20)

    def test_cyclic_learning_graph_and_acyclic_execution(self):
        g=build_graph(self.m,self.reg)
        self.assertTrue(any(e["kind"]=="REVERSE_PRESSURE" for e in g["edges"]))
        self.assertTrue(validate_mycelium(g)["executable_sipoc_acyclic"])

    def test_executable_cycle_fails_closed(self):
        g=build_graph(self.m,self.reg)
        g["edges"].append(dict(g["edges"][0], **{
            "from":"sipoc:GM-I:REX_RETURN","to":"sipoc:GM-I:SOURCE_READBACK",
            "kind":"SIPOC_DEPENDENCY","layer":"SIPOC"}))
        with self.assertRaisesRegex(ValueError,"cycle in executable"):
            validate_mycelium(g)

    def test_governed_acceptance_forgery_rejected(self):
        g=build_graph(self.m,self.reg)
        g["edges"][0]["binding"]="ACCEPTED"
        with self.assertRaisesRegex(ValueError,"unproven receipt"):
            validate_mycelium(g)

    def test_source_status_drift_rejected(self):
        m=copy.deepcopy(self.m)
        m["missions"][3]["source_disposition"]="GMV_LAUNCHED"
        with self.assertRaisesRegex(ValueError,"rewrite source disposition"):
            validate_missions(m,self.reg)

    def test_missing_mip_rejected(self):
        m=copy.deepcopy(self.m)
        del m["missions"][1]["mip"]["perpetuate"]
        with self.assertRaisesRegex(ValueError,"MIP incomplete"):
            validate_missions(m,self.reg)

    def test_wilson_requires_opportunity_denominator(self):
        self.assertIsNone(wilson(0,0))
        a=wilson(1,10)
        self.assertTrue(a["lower"]<.1<a["upper"])

    def test_six_sigma_no_claim_from_ten_green(self):
        x=defects_rate(0,10,independent=True,stable_control=True)
        self.assertEqual(x["state"],"DESCRIPTIVE_ONLY")
        self.assertIsNone(x["sigma_claim"])
        self.assertGreater(x["upper95_dpmo"],3.4)

    def test_many_zeros_are_candidate_only(self):
        x=defects_rate(0,1000000,independent=True,stable_control=True)
        self.assertEqual(x["state"],"SIX_SIGMA_STATISTICAL_UPPER_BOUND_CANDIDATE_NOT_CERTIFIED")
        self.assertLess(x["upper95_dpmo"],3.4)
        self.assertIsNone(x["sigma_claim"])

    def test_repeats_not_independent(self):
        x=defects_rate(0,1000000,independent=False,stable_control=True)
        self.assertEqual(x["state"],"DESCRIPTIVE_ONLY")
        self.assertIsNone(x["uncertainty"])
        self.assertIsNone(x["upper95_dpmo"])

    def test_n13_hierarchy_and_sipoc_wave_count(self):
        x=build()
        self.assertEqual(len(x["mycelium_graph"]["projection_receipt"]["waves"]),5)
        self.assertEqual(len(x["mission_states"]),5)

    def test_noncomparable_denominator_not_stability(self):
        rows=[{"pulse":i,"cohort_id":"GM-II","denominator":100+i,"residual_roots":8-i} for i in range(6)]
        self.assertEqual(trend(rows)["state"],"INCOMPARABLE_DENOMINATORS")

    def test_short_series_not_sigma_or_stable(self):
        rows=[{"pulse":i,"cohort_id":"GM-II","denominator":100,"residual_roots":8-i} for i in range(3)]
        self.assertEqual(trend(rows)["state"],"UNDERPOWERED_TREND_LT5")

    def test_five_descriptive_converging_not_certified(self):
        rows=[{"pulse":i,"cohort_id":"GM-II","denominator":100,"residual_roots":8-i} for i in range(5)]
        x=trend(rows)
        self.assertIn("CONVERGING_DESCRIPTIVE",x["state"])
        self.assertFalse(x["independent_stability_proven"])

    def test_event_clock_irregular_backward_dmaic_allowed(self):
        a={"sequence_e":1,"mission_id":"GM-II","action":"CONTROL","source_sha":"a"*40,
           "known_at":"2026-10-17T12:00Z","observed_at":"2026-10-17T11:00Z"}
        b=dict(a,sequence_e=3,action="ANALYSE")
        history=run_event(run_event([],a),b)
        self.assertEqual([x["action"] for x in history],["CONTROL","ANALYSE"])
        self.assertEqual(len(history),2)

    def test_clock_reuse_forbidden(self):
        a={"sequence_e":1,"mission_id":"GM-II","action":"CONTROL","source_sha":"a"*40,
           "known_at":"T1","observed_at":"T0"}
        with self.assertRaisesRegex(ValueError,"nonmonotone"):
            run_event([a],a)

    def test_semantic_generation_not_forged(self):
        a={"sequence_e":1,"mission_id":"GM-II","action":"CONTROL","source_sha":"a"*40,
           "known_at":"T1","observed_at":"T0","accepted_semantic_delta":True}
        with self.assertRaisesRegex(ValueError,"forged semantic"):
            run_event([],a)


if __name__=="__main__":
    unittest.main()
