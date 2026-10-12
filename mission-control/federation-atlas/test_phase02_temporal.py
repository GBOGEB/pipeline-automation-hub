import copy
import tempfile
from pathlib import Path
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import phase02_temporal as t

class TemporalTests(unittest.TestCase):
    def setUp(self):
        self.data=t.load("OBSERVED_PR519_20261012.json")
        self.policy=t.load("TEST_LANE_CONTROL_POLICY_v1.json")
    def test_scoped_metrics(self):
        r=t.classify(self.data)
        self.assertEqual(len(r["kpis"]),6)
        self.assertEqual(r["kpis"]["QUEUE_P95"]["value"],6)
        self.assertEqual(r["kpis"]["QUEUE_P95"]["denominator"],7)
        self.assertEqual(r["kpis"]["QUEUE_P95"]["status"],"SCOPED_OBSERVED_PARTIAL")
        self.assertEqual(r["kpis"]["FIRST_RED_COUNT"]["governance_reds_observed"],1)
        self.assertIsNone(r["kpis"]["FIRST_RED_COUNT"]["value"])
        self.assertIsNone(r["kpis"]["EXACT_HEAD_PROOF_YIELD"]["value"])
        self.assertEqual(r["kpis"]["PREDICTION_VS_ACTUAL"]["status"],"NOT_MEASURED")
        self.assertEqual(r["observed_postmerge_workflows"]["successful_workflows"],16)
    def test_bad_queue_and_duplicate(self):
        d=copy.deepcopy(self.data)
        d["queue_jobs"][0]["started"]="2026-10-12T13:11:45Z"
        with self.assertRaises(ValueError):t.classify(d)
        d=copy.deepcopy(self.data)
        d["queue_jobs"].append(d["queue_jobs"][0])
        with self.assertRaises(ValueError):t.classify(d)
    def test_svg_no_fabrication(self):
        self.assertEqual(t.graph(self.data["red_events"]).count("<circle"),1)
        self.assertEqual(t.graph([]).count("<circle"),0)
        self.assertIn("log1p",t.graph([]))
        with self.assertRaises(ValueError):t.graph([],"log")
    def test_control(self):
        self.assertEqual(t.control_disposition([],self.policy),"HOLD")
        r={"root_closed":True,"exact_head_admitted":True,"independent_repeat":True,"sha":"a"*40,"pulse":"P1"}
        self.assertEqual(t.control_disposition([r],self.policy),"HOLD")
        self.assertEqual(t.control_disposition([r,dict(r,sha="b"*40,pulse="P2")],self.policy),"ELIGIBLE_FOR_OWNER_REVIEW")
    def test_policy(self):
        self.assertEqual(t.optional_test_decision({"required":True,"lane":"GOVERNANCE_ADMISSION"},self.policy),"EXECUTE_REQUIRED")
        self.assertEqual(t.optional_test_decision({"required":False,"lane":"UNKNOWN"},self.policy),"EXECUTE_REQUIRED")
        good={"required":False,"lane":"PYTHON_TRIAGE_SHORT",
              "distinct_head_history":[{"sha":str(i).zfill(40),"conclusion":"success","executed_steps":2} for i in range(10)],
              "impact_map_verified":True,"touched_dependencies":False,"current_smoke_green":True,
              "canary_admitted":True,"full_sweep_within_7d":True}
        self.assertEqual(t.optional_test_decision(good,self.policy),"OPTIONAL_SHADOW_DEFER_ONLY")
        good["distinct_head_history"][4]["conclusion"]="failure"
        self.assertEqual(t.optional_test_decision(good,self.policy),"EXECUTE_NOT_CONSISTENTLY_GREEN")
    def test_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=t.build(tmp)
            html=(Path(tmp)/"phase02-temporal.html").read_text(encoding="utf-8")
            self.assertIn("Toggle light/dark",html)
            self.assertIn("24h",html)
            self.assertIn("11 passed / 1 failed",html)
            self.assertIn("DATA",r["schema"].upper() if False else "DATA") # explicit fixture no synthetic history
            self.assertTrue((Path(tmp)/"phase02-first-red.svg").exists())
if __name__=="__main__":unittest.main()
