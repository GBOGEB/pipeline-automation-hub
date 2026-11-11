"""Read-scout 16/32 qualification requires matched native observations, not a load claim."""
from __future__ import annotations
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("scout_scale_advisory_under_test",HERE/"read_scout_scale.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
SHA="a"*40
HASH="b"*64


def row(pulse,workers):
    number=workers*100+pulse
    return {"pulse_id":pulse,"head_sha":SHA,"workload_sha256":HASH,
            "environment_sha256":"c"*64,
            "native":{"run_id":number,"job_id":number*10,"attempt":1,
                      "status":"completed","conclusion":"success","steps":8},
            "metrics":{"owner":m.METRIC_OWNER,
                       "accepted_outputs":10 if workers==16 else 12,
                       "wall_seconds":100 if workers==16 else 70,
                       "runner_seconds":1000 if workers==16 else 1080,
                       "queue_p95_seconds":90 if workers==16 else 70,
                       "cache_hit_ratio":0.5 if workers==16 else 0.75,
                       "first_red":0,"root_recurrences":0}}


def sample(include_optimized=False):
    cohorts={"scouts16":[row(i,16) for i in range(1,5)],
             "scouts32":[row(i,32) for i in range(1,5)]}
    if include_optimized:
        cohorts["optimized16"]=[row(i,16) for i in range(1,5)]
        for x in cohorts["optimized16"]:
            x["native"]["run_id"]+=10000
            x["native"]["job_id"]+=100000
            x["metrics"]["accepted_outputs"]=13
            x["metrics"]["wall_seconds"]=60
            x["metrics"]["runner_seconds"]=950
    return {"schema":m.SCHEMA,"repository":m.REPO,"metric_owner":m.METRIC_OWNER,
            "authority_transfer":False,"dispatch_authorized":False,
            "merge_authorized":False,"cohorts":cohorts}


class ScaleContract(unittest.TestCase):
    def test_no_data_is_hold_not_zero_or_approved(self):
        d=m.evaluate(None)
        self.assertEqual(d["classification"],"HOLD_NO_MATCHED_NATIVE_OBSERVATIONS")
        self.assertIsNone(d["relative_metrics"])
        self.assertFalse(d["dispatch_authorized"])

    def test_four_favorable_pairs_still_unverified_and_advisory(self):
        d=m.evaluate(sample())
        self.assertEqual(d["classification"],"ADVISORY_ONLY")
        self.assertEqual(d["cohorts"]["scouts16"]["pulses"],4)
        self.assertGreater(d["read_scout_32_to_16_throughput_ratio"],1)
        self.assertIn("NATIVE_RUN_JOB_STEP_READBACK_REQUIRED",d["reasons"])
        self.assertIn("PROCESS_OPTIMIZATION_COHORT_UNOBSERVED",d["reasons"])
        self.assertFalse(d["native_identity_authenticated"])
        self.assertFalse(d["scale_eligible_for_owner_decision"])
        self.assertFalse(d["mutator_workers_changed"])

    def test_process_optimization_does_not_create_new_dispatch_authority(self):
        d=m.evaluate(sample(include_optimized=True))
        self.assertEqual(d["classification"],"ADVISORY_ONLY")
        self.assertNotIn("PROCESS_OPTIMIZATION_COHORT_UNOBSERVED",d["reasons"])
        self.assertIn("optimized16",d["cohorts"])
        self.assertFalse(d["dispatch_authorized"])
        self.assertFalse(d["merge_authorized"])

    def test_duplicate_native_identity_rejected_even_across_peers(self):
        d=sample()
        d["cohorts"]["scouts32"][0]["native"]=copy.deepcopy(d["cohorts"]["scouts16"][0]["native"])
        with self.assertRaisesRegex(ValueError,"NATIVE_EXECUTION_REUSED"):
            m.evaluate(d)

    def test_out_of_order_or_missing_pulse_fails_closed(self):
        for bad in (0,7,3):
            d=sample();d["cohorts"]["scouts32"][1]["pulse_id"]=bad
            expected="INVALID_PULSE_ID" if bad==0 else "PULSES_NOT_CONSECUTIVE"
            with self.subTest(pulse=bad),self.assertRaisesRegex(ValueError,expected):
                m.evaluate(d)
        d=sample();d["cohorts"]["scouts32"].pop()
        with self.assertRaisesRegex(ValueError,"FOUR_PULSES_REQUIRED"):
            m.evaluate(d)

    def test_mixed_heads_workload_and_environment_are_not_comparable(self):
        for field,incorrect in (("head_sha","d"*40),("workload_sha256","d"*64),
                                ("environment_sha256","e"*64)):
            d=sample();d["cohorts"]["scouts32"][0][field]=incorrect
            with self.subTest(field=field):
                result=m.evaluate(d)
                self.assertEqual(result["classification"],"HOLD")
                self.assertIn("INCOMPARABLE_HEAD_WORKLOAD_OR_ENVIRONMENT",result["reasons"])

    def test_zero_step_is_not_an_executed_success(self):
        d=sample();d["cohorts"]["scouts32"][2]["native"]["steps"]=0
        result=m.evaluate(d)
        self.assertEqual(result["classification"],"HOLD")
        self.assertIn("ZERO_STEP_EXECUTION_SCOUTS32",result["reasons"])

    def test_queue_cost_and_root_recurrence_regressions_hold(self):
        changes=[("queue_p95_seconds",200,"PAIRWISE_QUEUE_P95_REGRESSION_SCOUTS32"),
                 ("runner_seconds",5000,"COST_PER_OUTPUT_REGRESSION"),
                 ("first_red",1,"RED_OR_RECURRENCE_SCOUTS32"),
                 ("root_recurrences",1,"RED_OR_RECURRENCE_SCOUTS32")]
        for key,value,reason in changes:
            d=sample();d["cohorts"]["scouts32"][1]["metrics"][key]=value
            with self.subTest(key=key):
                result=m.evaluate(d)
                self.assertEqual(result["classification"],"HOLD")
                self.assertIn(reason,result["reasons"])

    def test_red_and_cancelled_outcomes_cannot_be_silently_excluded(self):
        d=sample()
        d["cohorts"]["scouts16"][0]["native"]["conclusion"]="failure"
        d["cohorts"]["scouts32"][1]["native"]["conclusion"]="cancelled"
        result=m.evaluate(d)
        self.assertEqual(result["cohorts"]["scouts16"]["native_outcome_counts"]["failure"],1)
        self.assertEqual(result["cohorts"]["scouts32"]["native_outcome_counts"]["cancelled"],1)
        self.assertFalse(result["native_identity_authenticated"])

    def test_owner_or_authority_escalation_is_rejected(self):
        for field,val in (("metric_owner","scripts/made_up_metrics.py"),
                          ("repository","GBOGEB/cryoplant-project"),
                          ("dispatch_authorized",True),("merge_authorized",True)):
            d=sample();d[field]=val
            with self.subTest(field=field),self.assertRaises(ValueError):
                m.evaluate(d)

    def test_readonly_default_cli_emits_sealed_hold(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"report.json"
            code=m.main(["--out",str(path)])
            self.assertEqual(code,0)
            output=json.loads(path.read_text())
            self.assertEqual(output["classification"],"HOLD_NO_MATCHED_NATIVE_OBSERVATIONS")
            self.assertEqual(output["engineering_credit_delta"],0)


if __name__=="__main__":
    unittest.main()
