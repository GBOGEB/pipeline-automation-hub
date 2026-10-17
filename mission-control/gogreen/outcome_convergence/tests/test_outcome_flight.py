"""G9 complete-population native run convergence: positive and adversarial controls."""
from __future__ import annotations

import copy
import contextlib
import hashlib
import importlib.util
import io
import json
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"outcome_flight.py"
SAMPLE=ROOT/"samples/native_full_window_20261017.json"
spec=importlib.util.spec_from_file_location("outcome_flight",SOURCE)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
SHA="a"*40


class OutcomeConvergenceNative(unittest.TestCase):
    def setUp(self):
        self.x=json.loads(SAMPLE.read_text(encoding="utf-8"))

    def rejects(self):
        with self.assertRaises((ValueError,KeyError,TypeError)):
            m.validate(self.x)

    def first(self):
        return self.x["cohorts"][0]["runs"][0]

    def test_valid_population_57(self):
        self.assertEqual(len(m.validate(self.x)),57)

    def test_success_fail_cancelled_not_cherry_picked(self):
        x=m.summarize(self.x)
        self.assertEqual((x["total_native_runs"],x["native_terminal_success"],
                          x["native_terminal_failure"],x["native_terminal_cancelled"]),
                         (57,46,10,1))
        self.assertIsNone(x["independent_native_trials"])
        self.assertEqual(x["formal_admission"],"HOLD")

    def test_mixed_cohort_per_repo(self):
        rows=m.summarize(self.x)["per_repository"]
        self.assertEqual([(r["complete_observed_runs"],r["success"],r["failure"],
                           r["cancelled"]) for r in rows],[(27,26,0,1),(30,20,10,0)])

    def test_per_family_qps_canonicalization_not_green(self):
        families=m.summarize(self.x)["per_workflow"]
        q=next(f for f in families if f["workflow"]=="qps-canonicalization")
        self.assertEqual((q["observed_total"],q["completed_success"],
                          q["completed_failure"]),(8,2,6))
        self.assertIsNone(q["normalized_first_red_root"])
        self.assertIsNone(q["independent_trial_count"])

    def test_per_family_qps_native_debug_all_observed_green(self):
        families=m.summarize(self.x)["per_workflow"]
        q=next(f for f in families if f["workflow"]=="QPS TRIAGE Debug DAG Pilot")
        self.assertEqual((q["observed_total"],q["completed_success"]), (6,6))
        self.assertEqual(q["unobserved_ordinals_in_sample"],0)
        self.assertFalse(q["causality_attributed"])

    def test_temporal_proxies_never_claim_billing(self):
        rows=m.validate(self.x)
        self.assertTrue(all(r["queue_seconds_proxy"]>=0 for r in rows))
        self.assertTrue(all(r["execution_seconds_proxy"]>=0 for r in rows))
        s=m.summarize(self.x)
        self.assertTrue(s["queue_seconds_are_started_minus_created_proxy"])
        self.assertTrue(s["execution_seconds_are_updated_minus_started_proxy"])
        self.assertIsNone(s["actual_runner_capacity"])

    def test_distinct_run_attempt_and_source_join(self):
        rows=m.validate(self.x)
        self.assertEqual(len({(r["repository"],r["id"],r["attempt"]) for r in rows}),57)
        self.assertTrue(all(len(r["source_sha"])==40 for r in rows))

    def test_robust_odd_even_medians(self):
        self.assertEqual(m.median([1,2,10]),2)
        self.assertEqual(m.median([1,2,9,11]),5.5)

    def test_html_output_escapes_untrusted_workflow(self):
        summary=m.summarize(self.x)
        summary["per_workflow"][0]["workflow"]="<img onerror=alert(1)>"
        output=m.html_page(summary)
        self.assertIn("&lt;img",output)
        self.assertNotIn("<img onerror",output)

    def test_dag_typed_and_non_authorizing(self):
        d=m.sipoc(m.summarize(self.x))
        self.assertFalse(d["merge_authorized"])
        self.assertFalse(d["authority_transfer"])
        self.assertEqual(d["closed_roots"],0)
        self.assertTrue(any(e["evidence"]=="DECLARED" for e in d["edges"]))
        self.assertEqual(len({n["id"] for n in d["nodes"]}),len(d["nodes"]))

    def test_build_reproducible_sha256(self):
        with tempfile.TemporaryDirectory() as tmp:
            report,manifest=m.build(self.x,Path(tmp),SHA)
            self.assertEqual(report["total_native_runs"],57)
            for file,expected in manifest["files"].items():
                self.assertEqual(hashlib.sha256((Path(tmp)/file).read_bytes()).hexdigest(),expected)

    def test_real_cli_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=["outcome_flight.py","--input",str(SAMPLE),"--out",str(Path(tmp)/"out"),
                  "--source-sha",SHA]
            buf=io.StringIO()
            with patch.object(sys,"argv",args),contextlib.redirect_stdout(buf):
                runpy.run_path(str(SOURCE),run_name="__main__")
            self.assertEqual(json.loads(buf.getvalue())["native_runs"],57)
            self.assertTrue((Path(tmp)/"out"/"index.html").is_file())

    def test_wrong_source_sha_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                m.build(self.x,Path(tmp),"short")

    def test_bad_schema(self):
        self.x["schema"]="replacement"
        self.rejects()

    def test_forged_root_credit(self):
        self.x["formal_root_closures"]=1
        self.rejects()

    def test_remote_dispatch(self):
        self.x["dispatch_authorized"]=True
        self.rejects()

    def test_authority_claim(self):
        self.x["authority_transfer"]=True
        self.rejects()

    def test_merge_grant(self):
        self.x["merge_authorized"]=True
        self.rejects()

    def test_forged_atomic_read(self):
        self.x["collection_is_atomic"]=True
        self.rejects()

    def test_forged_source_endpoint(self):
        self.x["source"]="repository issues not actions"
        self.rejects()

    def test_wrong_observation_date(self):
        self.x["observed_date_utc"]="2026-10-18"
        self.rejects()

    def test_missing_cohort(self):
        self.x["cohorts"].pop()
        self.rejects()

    def test_duplicate_cohort(self):
        self.x["cohorts"][1]["repo"]="GBOGEB/gg_MATH"
        self.rejects()

    def test_unknown_scope_repo(self):
        self.x["cohorts"][1]["repo"]="GBOGEB/OTHER"
        self.rejects()

    def test_truncated_page(self):
        self.x["cohorts"][0]["runs"].pop()
        self.rejects()

    def test_page_size_exceeds_bounds(self):
        self.x["cohorts"][0]["api_total_count"]=101
        self.rejects()

    def test_missing_population_authority(self):
        self.x["cohorts"][0]["population_class"]="CURATED_GREENS"
        self.rejects()

    def test_mismatched_branch(self):
        self.x["cohorts"][0]["branch"]="release"
        self.rejects()

    def test_forged_green_conclusion(self):
        self.first()["conclusion"]="pending"
        self.rejects()

    def test_nonterminal_in_complete_census(self):
        self.first()["status"]="queued"
        self.rejects()

    def test_unsupported_run_event(self):
        self.first()["event"]="issue_comment"
        self.rejects()

    def test_duplicate_native_id(self):
        self.x["cohorts"][1]["runs"][0]["id"]=self.first()["id"]
        self.rejects()

    def test_duplicate_run_attempt(self):
        self.x["cohorts"][0]["runs"][1]["workflow"]=self.first()["workflow"]
        self.x["cohorts"][0]["runs"][1]["number"]=self.first()["number"]
        self.x["cohorts"][0]["runs"][1]["attempt"]=self.first()["attempt"]
        self.rejects()

    def test_zero_attempt(self):
        self.first()["attempt"]=0
        self.rejects()

    def test_boolean_attempt(self):
        self.first()["attempt"]=True
        self.rejects()

    def test_wrong_run_url(self):
        self.first()["run_url"]="https://github.com/GBOGEB/gg_MATH/actions/runs/1"
        self.rejects()

    def test_broken_sha(self):
        self.first()["sha"]="wrong"
        self.rejects()

    def test_run_clock_reversed(self):
        self.first()["updated_at"]="2026-10-16T00:00:00Z"
        self.rejects()

    def test_run_out_of_window(self):
        self.first()["created_at"]="2026-10-15T23:59:59Z"
        self.rejects()

    def test_malformed_timestamp(self):
        self.first()["created_at"]="2026-02-30T00:00:00Z"
        self.rejects()

    def test_future_run_within_wrong_date(self):
        self.first()["created_at"]="2026-10-18T00:00:01Z"
        self.rejects()

    def test_unbounded_update_age(self):
        self.first()["updated_at"]="2026-10-20T01:00:00Z"
        self.rejects()

    def test_empty_workflow(self):
        self.first()["workflow"]=""
        self.rejects()

    def test_empty_median_denominator(self):
        with self.assertRaises(ValueError):
            m.median([])

    def test_negative_median_inputs(self):
        with self.assertRaises(ValueError):
            m.median([-1])

    def test_bool_median_inputs(self):
        with self.assertRaises(ValueError):
            m.median([True])

    def test_extra_policy_claim_does_not_credit(self):
        self.x["independent_trials"]=999
        self.assertIsNone(m.summarize(self.x)["independent_native_trials"])

    def test_lineage_no_automatic_first_red(self):
        s=m.summarize(self.x)
        self.assertIsNone(s["first_red_root_population"])
        self.assertEqual(s["root_closure_credit"],0)

    def test_coverage_is_out_of_scope(self):
        s=m.summarize(self.x)
        self.assertEqual(s["sampled_job_run_join"],"REQUIRES_NATIVE_JOB_PAGINATION")
        self.assertIsNone(s["uncertainty_intervals"])


if __name__=="__main__":
    unittest.main()
