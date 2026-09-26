import copy, json, unittest
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from gm_top7_depth3_metrics import compute, repo_metrics

CONTRACT=ROOT/"GM_TOP7_DEPTH3_MISSION_v1.json"

class TestGMTop7Depth3(unittest.TestCase):
    def setUp(self):
        self.doc=json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_baseline_contract(self):
        got=compute(self.doc)
        self.assertEqual(got["repo_count"],7)
        self.assertEqual(got["admitted_reds"],4)
        self.assertEqual(got["proven_green_reds"],0)
        self.assertEqual(got["fleet_blocker_checks"],1)
        self.assertEqual(got["fleet_pending_checks"],45)
        self.assertFalse(got["fleet_dov"])
        self.assertEqual(got["temporal"]["visible_failure_reduction_count"],3)
        self.assertAlmostEqual(got["temporal"]["visible_failure_reduction_fraction"],0.75)

    def test_zero_denominator_is_not_false_green_rate(self):
        row=copy.deepcopy(self.doc["repositories"][0])
        row["health"].update(successful_checks=0,failed_checks=0,action_required_checks=0,pending_checks=0,zero_step_unknown=0,exact_head_proven=False)
        got=repo_metrics(row)
        self.assertIsNone(got["failure_rate_nullable"])
        self.assertFalse(got["repo_dov"])

    def test_pending_blocks_dov(self):
        row=copy.deepcopy(self.doc["repositories"][3])
        row["health"]["pending_checks"]=1
        self.assertFalse(repo_metrics(row)["repo_dov"])

    def test_more_than_three_admitted_reds_fails(self):
        row=copy.deepcopy(self.doc["repositories"][1])
        row["red_slots"].append({"depth":4,"id":"SYNTHETIC","admitted":True,"status":"OPEN"})
        with self.assertRaises(SystemExit):
            repo_metrics(row)

if __name__=="__main__":
    unittest.main()
