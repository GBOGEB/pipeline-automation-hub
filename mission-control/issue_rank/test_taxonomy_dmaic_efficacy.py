"""N7 DMAIC N+12 source-bound adaptive decision contracts."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
import taxonomy_dmaic_efficacy as d


def wave(n,covered=80,zero=2,failed=0,queue=3,lines=100,roster="f"*64):
    return {"wave":n,"cohort_id":"taxonomy-core-v1",
            "file_roster_sha256":roster,"head_sha":format(n+10,"040x"),
            "observed_at":f"2026-10-26T{n+1:02d}:00:00Z",
            "covered_lines":covered,"total_lines":lines,
            "zero_covered_files":zero,"tests_passed":20,
            "tests_failed":failed,"tests_skipped":1,
            "executed_jobs":2,"zero_step_jobs":0,"queue_depth":queue,
            "in_progress":2}


def input_of(*rows):
    return {"schema":d.INPUT,"cohort_id":"taxonomy-core-v1","waves":list(rows)}


class Decision(unittest.TestCase):
    def test_wilson_small_cohorts_not_confused_with_certainty(self):
        x=d.wilson(20,20)
        self.assertLess(x["lower"],1)
        self.assertGreater(x["lower"],0)
        self.assertEqual(x["denominator"],20)
        self.assertIsNone(d.wilson(0,0))

    def test_aggressive_n_plus_j_admissible_only_with_progress(self):
        r=d.assess(input_of(wave(0,70,5),wave(1,74,4),wave(2,82,2)))
        self.assertEqual(r["next_action"],"SCALE_BOUNDED")
        self.assertEqual(r["next_wave"],3)
        self.assertEqual(r["mip"]["progression"]["coverage_delta_pp"],12)
        self.assertEqual(r["mip"]["progression"]["zero_covered_files_reduction"],3)
        self.assertFalse(r["mip"]["progression"]["first_red_seen"])
        self.assertEqual(r["merge_admission"],"HOLD")

    def test_unmeasured_change_requires_smaller_slice(self):
        r=d.assess(input_of(wave(0),wave(1)))
        self.assertEqual(r["next_action"],"PROVE_NEXT_SMALL_SLICE")

    def test_queue_saturation_blocks_fanout_even_after_coverage_gain(self):
        r=d.assess(input_of(wave(0,70),wave(1,80,queue=30)))
        self.assertEqual(r["next_action"],"HOLD")
        self.assertIn("QUEUE_PRESSURE_EXCEEDS_20",r["stop_reasons"])

    def test_first_red_and_zero_step_are_noncompensating(self):
        r=d.assess(input_of(wave(0,70),wave(1,85,failed=1)))
        self.assertIn("FIRST_RED_EXISTS",r["stop_reasons"])
        a=wave(1,85)
        a["zero_step_jobs"]=1
        r=d.assess(input_of(wave(0,70),a))
        self.assertIn("ZERO_STEP_EVIDENCE",r["stop_reasons"])

    def test_stable_3_wave_stops_to_prevent_runner_churn(self):
        r=d.assess(input_of(wave(0,70,5),wave(1,80,2),wave(2,80,2),wave(3,80,2)))
        self.assertEqual(r["next_action"],"HOLD")
        self.assertIn("THREE_WAVES_STABLE_STOP_RULE",r["stop_reasons"])

    def test_max_n_plus_12_bounded_even_if_improving(self):
        waves=[wave(i,50+i,12-i) for i in range(13)]
        r=d.assess(input_of(*waves))
        self.assertEqual(r["latest_wave"],12)
        self.assertIn("MAX_12_WAVES",r["stop_reasons"])
        self.assertIsNone(r["next_wave"])

    def test_roster_change_denominator_and_bad_time_fail_closed(self):
        a=wave(0)
        b=wave(1,90,roster="e"*64)
        with self.assertRaisesRegex(ValueError,"FILE_ROSTER_CHANGED"):
            d.assess(input_of(a,b))
        b=wave(1,90,lines=110)
        r=d.assess(input_of(a,b))
        self.assertFalse(r["mip"]["progression"]["matched_denominator"])
        self.assertIn("UNMATCHED_COVERAGE_DENOMINATOR",r["stop_reasons"])
        b=wave(1,90)
        b["observed_at"]=a["observed_at"]
        with self.assertRaisesRegex(ValueError,"NON_MONOTONIC_TIME"):
            d.assess(input_of(a,b))

    def test_invalid_or_zero_native_jobs_not_accepted(self):
        a=wave(0)
        a["executed_jobs"]=0
        with self.assertRaisesRegex(ValueError,"UNEXECUTED_TEST_PROOF"):
            d.assess(input_of(a))
        a=wave(0)
        a["tests_passed"]=0
        with self.assertRaisesRegex(ValueError,"ZERO_TEST_JOBS"):
            d.assess(input_of(a))

    def test_idempotent_offline_receipt_and_cli(self):
        rows=input_of(wave(0),wave(1,82,1))
        r=d.assess(rows)
        self.assertEqual(r["receipt_sha256"],d.assess(copy.deepcopy(rows))["receipt_sha256"])
        with tempfile.TemporaryDirectory() as tmp:
            src,out=Path(tmp)/"in.json",Path(tmp)/"out.json"
            src.write_text(json.dumps(rows))
            self.assertEqual(d.main(["--in",str(src),"--out",str(out)]),0)
            self.assertEqual(json.loads(out.read_text())["formal_credit_delta"],0)


if __name__=="__main__":
    unittest.main()
