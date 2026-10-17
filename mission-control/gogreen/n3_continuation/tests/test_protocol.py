"""3PSTAR / 3WSTAR governed continuation: native-positive and adversarial tests."""
from __future__ import annotations
import contextlib
import copy
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

HERE=Path(__file__).resolve().parents[1]
REPO=HERE.parents[2]
SOURCE=HERE/"protocol.py"
TEMPLATE=HERE/"N3_CHARTER_TEMPLATE.json"
SPEC=importlib.util.spec_from_file_location("n3_protocol_under_test",SOURCE)
p=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(p)
A="a"*40
B="b"*40
C="c"*40
D="d"*40
F="f"*40
G="e"*40

def sample():
    c=json.loads(TEMPLATE.read_text(encoding="utf-8"))
    c["execution_id"]="GOGREEN_20261017_NATIVE_N3_EXAMPLE"
    c["template_status"]="BOUNDED_SOURCE_TEST_FIXTURE_ONLY"
    c["baseline"]["source_sha"]=A
    c["baseline"]["observed_utc"]="2026-10-17T10:00:00Z"
    c["baseline"]["metric"].update(covered=6,eligible=10,production_blob=F)
    c["baseline"]["evidence_url"]="https://github.com/GBOGEB/cryoplant-project/actions/runs/100"
    return c

def observation(c,index,prior,source,covered=7,eligible=10,blob=F,
                outcome="SUCCESS",run=None):
    rid=run or (1000+index)
    return {
        "schema":p.OBS,"execution_id":c["execution_id"],
        "pulse_index":index,"phase":p.STEPS[index-1],
        "repository":c["repository"],"previous_source_sha":prior,
        "source_sha":source,"native_head_sha":source,
        "completed_utc":f"2026-10-17T{10+index:02d}:00:00Z",
        "run_status":"COMPLETED","conclusion":outcome,
        "run_id":rid,"attempt":1,"job_id":rid*10,
        "native_receipt_url":f"https://github.com/{c['repository']}/actions/runs/{rid}",
        "tests":{"executed":10,"passed":10 if outcome=="SUCCESS" else 9,
                 "failed":0 if outcome=="SUCCESS" else 1,"skipped":0},
        "metric":{"key":c["objective"]["metric_key"],"scope":c["baseline"]["metric"]["scope"],
                  "instrument":c["baseline"]["metric"]["instrument"],
                  "production_blob":blob,"covered":covered,"eligible":eligible},
        "first_red":None if outcome=="SUCCESS" else "native positive test first-red",
        "blockers":[],"completed_work":[],"root_closure_credit":0,
        "merge_authorized":False,"security_waiver_authorized":False
    }

class N3Contract(unittest.TestCase):
    def setUp(self):
        self.c=sample()
        self.l=p.initial(self.c)
        self.o=observation(self.c,1,A,B)

    def badcharter(self):
        with self.assertRaises((ValueError,TypeError,KeyError)):
            p.charter(self.c)

    def badobservation(self):
        with self.assertRaises((ValueError,TypeError,KeyError)):
            p.advance(self.c,self.l,self.o)

    def test_00_template_refuses_to_fake_live_head(self):
        with self.assertRaises(ValueError):
            p.charter(json.loads(TEMPLATE.read_text()))

    def test_charter_good_and_baseline(self):
        self.assertEqual(p.charter(self.c)["method"],"3PSTAR")
        self.assertEqual(self.l["status"],"N_BASELINE_READY")
        self.assertEqual(p.plan(self.c,self.l)["phase"],"P1_RECONCILE_MEASURE")

    def test_three_pulses_complete_exactly_N3(self):
        one=p.advance(self.c,self.l,self.o)
        two=p.advance(self.c,one,observation(self.c,2,B,C,covered=8))
        three=p.advance(self.c,two,observation(self.c,3,C,D,covered=9))
        r=p.return_receipt(self.c,three)
        self.assertEqual(r["last_verified_checkpoint"],"N+3")
        self.assertEqual(r["verified_checkpoint_count"],3)
        self.assertTrue(r["three_pulses_complete"])
        self.assertEqual(r["native_terminal_successes"],3)
        self.assertEqual(p.plan(self.c,three)["state"],"RETURN_N3")
        self.assertFalse(r["merge_authorized"])

    def test_one_pulse_changes_N_to_N1_not_three_waves(self):
        l=p.advance(self.c,self.l,self.o)
        self.assertEqual((len(l["checkpoints"]),l["status"]),(1,"CONTINUE"))
        self.assertEqual(l["checkpoints"][0]["label"],"N+1")
        self.assertEqual(l["checkpoints"][0]["comparable_delta_pp"],10.0)

    def test_three_wave_strategies_do_not_change_pulse_count(self):
        for strategy in p.WAVES:
            self.c["policy"]["wave_strategy"]=strategy
            self.assertEqual(p.initial(self.c)["checkpoints"],[])

    def test_recorded_failed_pulse_is_not_a_green_run(self):
        self.o=observation(self.c,1,A,B,outcome="FAILURE")
        l=p.advance(self.c,self.l,self.o)
        self.assertEqual(l["status"],"REPAIR_NEXT_PULSE")
        self.assertEqual(p.plan(self.c,l)["state"],"REPAIR_SOURCE_FIRST_RED")
        self.assertEqual(p.return_receipt(self.c,l)["native_terminal_failures"],1)

    def test_major_blocker_return_partial_not_N1(self):
        self.o["blockers"]=[{"code":"SECURITY_P0_P1","severity":"MAJOR",
                             "evidence_ref":"https://github.com/GBOGEB/cryoplant-project/issues/7"}]
        l=p.advance(self.c,self.l,self.o)
        self.assertEqual(len(l["checkpoints"]),0)
        self.assertEqual(l["status"],"HOLD_MAJOR")
        self.assertEqual(p.plan(self.c,l)["state"],"HOLD_MAJOR")
        self.assertFalse(p.return_receipt(self.c,l)["three_pulses_complete"])

    def test_major_blocker_rejects_next_pulse(self):
        self.o["blockers"]=[{"code":"OWNER_LEASE_CONFLICT","severity":"MAJOR",
                             "evidence_ref":"https://example.com/lease"}]
        held=p.advance(self.c,self.l,self.o)
        with self.assertRaises(ValueError):
            p.advance(self.c,held,self.o)

    def test_all_success_still_no_merge_or_root_credit(self):
        one=p.advance(self.c,self.l,self.o)
        self.assertFalse(one["merge_authorized"])
        self.assertEqual(one["formal_root_closure_credit"],0)
        self.assertEqual(p.return_receipt(self.c,one)["independent_review"],"UNVERIFIED")

    def test_coverage_delta_not_comparable_after_blob_change(self):
        self.o["metric"]["production_blob"]=G
        x=p.advance(self.c,self.l,self.o)["checkpoints"][0]
        self.assertIsNone(x["comparable_delta_pp"])
        self.assertEqual(x["comparison"],"UNMATCHED_SOURCE_SCOPE")

    def test_coverage_delta_not_comparable_after_denominator_change(self):
        self.o["metric"]["eligible"]=12
        x=p.advance(self.c,self.l,self.o)["checkpoints"][0]
        self.assertIsNone(x["comparable_delta_pp"])

    def test_coverage_delta_not_comparable_after_instrument_change(self):
        self.o["metric"]["instrument"]="different"
        x=p.advance(self.c,self.l,self.o)["checkpoints"][0]
        self.assertIsNone(x["comparable_delta_pp"])

    def test_no_zero_delta_without_postbaseline(self):
        x=p.return_receipt(self.c,self.l)
        self.assertIsNone(x["comparable_net_delta_pp"])
        self.assertEqual(x["baseline_current_comparability"],"NO_POST_BASELINE_EVIDENCE")

    def test_outcomes_append_only_receipt_sha(self):
        x=p.advance(self.c,self.l,self.o)
        self.assertEqual(len(x["checkpoints"][0]["receipt_sha256"]),64)
        p.validate_ledger(self.c,x)
        x["checkpoints"][0]["metric"]["covered"]=8
        with self.assertRaises(ValueError):
            p.validate_ledger(self.c,x)

    def test_sha256_artifacts_reproducible_and_no_overwrite(self):
        x=p.advance(self.c,self.l,self.o)
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)/"first"
            rec,m=p.produce(self.c,x,d)
            for k,v in m["files_sha256"].items():
                self.assertEqual(hashlib.sha256((d/k).read_bytes()).hexdigest(),v)
            self.assertIn("SIPOC", (d/"sipoc_dag.json").read_text().upper() or "SIPOC")
            with self.assertRaises(ValueError):
                p.produce(self.c,x,d)

    def test_cli_initial_creates_partial_return_without_fake_pulses(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);inp=d/"charter.json";inp.write_bytes(p.encoded(self.c))
            out=d/"output";buf=io.StringIO()
            argv=["protocol.py","--charter",str(inp),"--out",str(out)]
            with patch.object(sys,"argv",argv),contextlib.redirect_stdout(buf):
                runpy.run_path(str(SOURCE),run_name="__main__")
            self.assertEqual(json.loads(buf.getvalue())["checkpoint"],"N+0")
            self.assertEqual(json.loads((out/"ledger.json").read_text())["checkpoints"],[])

    def test_cli_three_observations_in_one_bounded_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);cp=d/"c.json";cp.write_bytes(p.encoded(self.c))
            obs=[self.o,observation(self.c,2,B,C,covered=8),observation(self.c,3,C,D,covered=9)]
            op=d/"obs.json";op.write_bytes(p.encoded(obs))
            out=d/"final";buf=io.StringIO()
            argv=["protocol.py","--charter",str(cp),"--observations",str(op),
                  "--out",str(out)]
            with patch.object(sys,"argv",argv),contextlib.redirect_stdout(buf):
                runpy.run_path(str(SOURCE),run_name="__main__")
            self.assertTrue(json.loads(buf.getvalue())["complete"])
            self.assertEqual(len(json.loads((out/"ledger.json").read_text())["checkpoints"]),3)

    def test_sipoc_source_to_customer_dag(self):
        d=p.sipoc(self.c,self.l)
        self.assertEqual(len(d["nodes"]),7)
        self.assertEqual(len(d["edges"]),6)
        self.assertFalse(d["merge_authorized"])

    def test_html_escapes_dynamic_source(self):
        rec=p.return_receipt(self.c,self.l)
        rec["next_action"]="<script>alert(1)</script>"
        src=p.html_page(rec)
        self.assertIn("&lt;script&gt;",src)
        self.assertNotIn("<script>alert",src)

    def test_source_time_monotonicity(self):
        self.o["completed_utc"]="2026-10-16T10:00:00Z"
        self.badobservation()

    def test_missing_utc_timezone(self):
        self.o["completed_utc"]="2026-10-17T11:00:00+01:00"
        self.badobservation()

    def test_utc_invalid_day(self):
        self.o["completed_utc"]="2026-02-30T00:00:00Z"
        self.badobservation()

    def test_nonterminal_queue_not_a_pulse(self):
        self.o["run_status"]="QUEUED"
        self.badobservation()

    def test_cancelled_not_silent_green(self):
        self.o["conclusion"]="CANCELLED"
        self.badobservation()

    def test_wrong_phase_sequence(self):
        self.o["phase"]="P2_ENHANCE_PROVE"
        self.badobservation()

    def test_wrong_pulse_index(self):
        self.o["pulse_index"]=3
        self.badobservation()

    def test_duplicate_native_run_id_and_attempt(self):
        l=p.advance(self.c,self.l,self.o)
        self.l=l
        self.o=observation(self.c,2,B,C,run=1001)
        self.badobservation()

    def test_source_sha_not_matching_native_head(self):
        self.o["native_head_sha"]=D
        self.badobservation()

    def test_stale_parent_head(self):
        self.o["previous_source_sha"]=D
        self.badobservation()

    def test_missing_job_receipt(self):
        self.o["job_id"]=None
        self.badobservation()

    def test_source_run_url_not_exact(self):
        self.o["native_receipt_url"]="https://github.com/GBOGEB/cryoplant-project/actions/runs/1001junk"
        self.badobservation()

    def test_forged_native_bool_run_id(self):
        self.o["run_id"]=True
        self.badobservation()

    def test_invalid_attempt_zero(self):
        self.o["attempt"]=0
        self.badobservation()

    def test_skipped_tests_do_not_falsely_pass_denominator(self):
        self.o["tests"]["skipped"]=1
        self.badobservation()

    def test_zero_native_tests_cannot_pass(self):
        self.o["tests"]={"executed":0,"passed":0,"failed":0,"skipped":0}
        self.badobservation()

    def test_false_green_with_failed_tests(self):
        self.o["tests"]={"executed":10,"passed":9,"failed":1,"skipped":0}
        self.badobservation()

    def test_failed_run_requires_first_red(self):
        self.o=observation(self.c,1,A,B,outcome="FAILURE")
        self.o["first_red"]=None
        self.badobservation()

    def test_forged_merge_admission(self):
        self.o["merge_authorized"]=True
        self.badobservation()

    def test_forged_root_closure(self):
        self.o["root_closure_credit"]=1
        self.badobservation()

    def test_forged_security_waiver(self):
        self.o["security_waiver_authorized"]=True
        self.badobservation()

    def test_major_blocker_wrong_class_rejected(self):
        self.o["blockers"]=[{"code":"UNKNOWN_MAGIC","severity":"MAJOR","evidence_ref":"x"}]
        self.badobservation()

    def test_major_blocker_without_source_rejected(self):
        self.o["blockers"]=[{"code":"SECURITY_P0_P1","severity":"MAJOR","evidence_ref":""}]
        self.badobservation()

    def test_owner_lease_required_for_commit(self):
        self.o["completed_work"]=[{"lane_id":"DEPENDENCY_CI","disposition":"OWNED_COMMIT",
                                    "owner_lease_valid":False,"commit_sha":B}]
        self.badobservation()

    def test_authorized_owned_source_commit(self):
        self.o["completed_work"]=[{"lane_id":"DEPENDENCY_CI","disposition":"OWNED_COMMIT",
                                    "owner_lease_valid":True,"commit_sha":B}]
        x=p.advance(self.c,self.l,self.o)
        self.assertEqual(x["checkpoints"][0]["completed_work"][0]["lane_id"],"DEPENDENCY_CI")

    def test_other_repo_commit_disallowed(self):
        self.c["lanes"][1]["repository"]="GBOGEB/ABACUS"
        self.badcharter()

    def test_path_overlap_disallowed_even_nested(self):
        self.c["lanes"][1]["paths"]=["tests"]
        self.c["lanes"][2]["paths"]=["tests/test_qps_w163_hx_chart_namespace.py"]
        self.badcharter()

    def test_parent_traversal_forbidden(self):
        self.c["lanes"][1]["paths"]=["../secrets/"]
        self.badcharter()

    def test_no_mutation_in_readonly_charter(self):
        self.c["policy"]["mutation_scope"]="READ_ONLY"
        self.badcharter()

    def test_unsupported_wave_strategy_rejected(self):
        self.c["policy"]["wave_strategy"]="THREE_PULSES_AS_THREE_JOBS"
        self.badcharter()

    def test_method_three_pr_not_three_pulses(self):
        self.c["method"]="3PR"
        self.badcharter()

    def test_three_wave_token_not_three_pulse(self):
        self.c["method"]="3WSTAR"
        self.badcharter()

    def test_no_four_pulses(self):
        self.c["policy"]["pulse_count"]=4
        self.badcharter()

    def test_invalid_workers_five(self):
        self.c["policy"]["max_disjoint_workers"]=5
        self.badcharter()

    def test_invalid_attempts_four(self):
        self.c["policy"]["max_attempts_per_pulse"]=4
        self.badcharter()

    def test_authority_transfer_forbidden_by_policy(self):
        self.c["policy"]["merge_authorized"]=True
        self.badcharter()

    def test_security_waiver_policy_forbidden(self):
        self.c["policy"]["security_waiver_authorized"]=True
        self.badcharter()

    def test_background_promise_forbidden(self):
        self.c["execution_mode"]="AUTONOMOUS_ALWAYS_RUNNING"
        self.badcharter()

    def test_no_exact_baseline(self):
        self.c["baseline"]["source_sha"]=None
        self.badcharter()

    def test_missing_baseline_eligible_denominator(self):
        self.c["baseline"]["metric"]["eligible"]=0
        self.badcharter()

    def test_metric_negative_coverage_forbidden(self):
        self.c["baseline"]["metric"]["covered"]=-1
        self.badcharter()

    def test_metric_covered_cannot_exceed_eligible(self):
        self.o["metric"]["covered"]=15
        self.badobservation()

    def test_missing_source_scope(self):
        self.c["baseline"]["metric"]["scope"]=""
        self.badcharter()

    def test_missing_required_evidence(self):
        self.c["required_evidence"].remove("FIRST_RED_OR_PASS")
        self.badcharter()

    def test_duplicate_lane(self):
        self.c["lanes"][2]["id"]="DEPENDENCY_CI"
        self.badcharter()

    def test_stale_charter_sha_in_ledger(self):
        self.l["charter_sha256"]="0"*64
        self.badobservation()

    def test_ledger_cannot_claim_merge(self):
        self.l["merge_authorized"]=True
        self.badobservation()

    def test_after_three_native_events_fourth_prohibited(self):
        a=p.advance(self.c,self.l,self.o)
        b=p.advance(self.c,a,observation(self.c,2,B,C))
        d=p.advance(self.c,b,observation(self.c,3,C,D))
        with self.assertRaises(ValueError):
            p.advance(self.c,d,observation(self.c,3,D,G,run=2000))

    def test_forged_completion_without_N3_rejected(self):
        self.l["status"]="N3_MEASURED_COMPLETE"
        self.badobservation()

    def test_bounded_run_attempt_cannot_exceed_policy(self):
        self.o["attempt"]=self.c["policy"]["max_attempts_per_pulse"]+1
        self.badobservation()

    def test_read_only_lane_cannot_claim_owner_commit(self):
        self.o["completed_work"]=[{"lane_id":"ROOT_CENSUS",
                                    "disposition":"OWNED_COMMIT",
                                    "owner_lease_valid":True,"commit_sha":B}]
        self.badobservation()

    def test_worker_count_fanout_cap_fail_closed(self):
        self.c["policy"]["max_disjoint_workers"]=1
        self.l=p.initial(self.c)
        self.o["completed_work"]=[
           {"lane_id":"ROOT_CENSUS","disposition":"READ_ONLY"},
           {"lane_id":"DEPENDENCY_CI","disposition":"VERIFIED_NO_CHANGE"}]
        self.badobservation()

    def test_invalid_native_test_outcome_type_rejected(self):
        # True is an int subclass; numbers must be exact native integer counts.
        self.o["tests"]["passed"]=True
        self.badobservation()

    def test_nonmutating_work_item_is_accepted(self):
        # Exercise a non-empty, legitimate no-commit work lane.
        self.o["completed_work"]=[{"lane_id":"ROOT_CENSUS",
                                   "disposition":"VERIFIED_NO_CHANGE"}]
        new=p.advance(self.c,self.l,self.o)
        self.assertEqual(new["checkpoints"][0]["completed_work"][0]["disposition"],
                         "VERIFIED_NO_CHANGE")
        self.assertFalse(new["merge_authorized"])

    def test_cli_major_blocker_stops_before_following_pulse(self):
        import contextlib
        import io
        import runpy
        import sys
        from unittest.mock import patch
        # An authoritative blocker must stop iteration, not silently execute P2.
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            c=d/"charter.json"
            c.write_bytes(p.encoded(self.c))
            blocked=copy.deepcopy(self.o)
            blocked["blockers"]=[{
                "code":"OWNER_LEASE_CONFLICT",
                "severity":"MAJOR",
                "evidence_ref":"https://github.com/GBOGEB/cryoplant-project/issues/7"
            }]
            subsequent=observation(self.c,2,B,C,run=987654)
            obs=d/"observations.json"
            obs.write_bytes(p.encoded([blocked,subsequent]))
            target=d/"receipt"
            out=io.StringIO()
            argv=["protocol.py","--charter",str(c),
                  "--observations",str(obs),"--out",str(target)]
            with patch.object(sys,"argv",argv),contextlib.redirect_stdout(out):
                runpy.run_path(str(SOURCE),run_name="__main__")
            receipt=json.loads((target/"return_receipt.json").read_text())
            self.assertFalse(receipt["three_pulses_complete"])
            self.assertEqual(receipt["verified_checkpoint_count"],0)
            self.assertEqual(receipt["next_action"],"HOLD_MAJOR")
            self.assertEqual(receipt["stop_reason"]["at"],"N+1")
            self.assertEqual(len(json.loads((target/"ledger.json").read_text())["checkpoints"]),0)
            self.assertFalse(json.loads(out.getvalue())["complete"])

    def test_immutable_historical_root_baseline(self):
        tax=json.loads((REPO/"mission-control/v2/MC_GLOSSARY_TAXONOMY_v2.json").read_text())
        self.assertEqual(tax["as_of"],"2026-09-27")
        self.assertEqual(tax["reservations"]["3PR"]["canonical_meaning"],
                         "THREE_P_REFRESH_PROBE_RANK")
        self.assertEqual(tax["reservations"]["3PC"]["canonical_meaning"],
                         "THREE_P_PREPARE_PROVE_COMMIT")
        self.assertEqual(tax["reservations"]["3PSTAR"]["canonical_invocation"],"N3_CONTINUE")
        self.assertEqual(tax["n3_continuation_extension"]["maximum_pulses_per_call"],3)

if __name__=="__main__":
    unittest.main()
