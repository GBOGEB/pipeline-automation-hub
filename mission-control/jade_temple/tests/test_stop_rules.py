"""No fake convergence, no implicit zero, no owner authority from green CI."""
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("stop",ROOT/"tools"/"stop_rules.py")
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
SHA="a"*40
GATES={k:"PASS" for k in mod.REQUIRED_GATES}
def pulse(n, sha=SHA, metrics=None, native="TERMINAL", pending=0, scope="21-cohort"):
    return {"id":n,"cohort_sha":"b"*40,"eligible_denominator":21,"instrumentor":"v1",
            "scope":scope,"heads":{"repo":sha},"native_state":native,"pending_roots":pending,
            "metrics": metrics if metrics is not None else dict.fromkeys(mod.REQUIRED_METRICS, 0)}
class StopTests(unittest.TestCase):
    def stop(self,gates=None,pulses=None,reds=None,pending=False,repeat=None):
        return mod.evaluate(gates or dict(GATES), pulses or [], reds or [], pending, SHA, repeat or [])
    def test_three_same_matched_pulses_stops_recensus_not_release(self):
        a=self.stop(pulses=[pulse(1),pulse(2),pulse(3)])
        self.assertEqual(a["action"],"PIVOT_DISJOINT_OWNER")
        self.assertEqual(a["merge_admission"],"HOLD")
        self.assertFalse(a["formal_release_credit"])
    def test_only_two_pulses_cannot_claim_plateau(self):
        self.assertFalse(mod.plateau([pulse(1),pulse(2)]))
    def test_head_drift_invalidates_plateau(self):
        self.assertFalse(mod.plateau([pulse(1),pulse(2,sha="c"*40),pulse(3)]))
    def test_denominator_drift_invalidates_plateau(self):
        a=[pulse(1),pulse(2),pulse(3)];a[1]["eligible_denominator"]=20
        self.assertFalse(mod.plateau(a))
    def test_instrumentor_drift_invalidates_plateau(self):
        a=[pulse(1),pulse(2),pulse(3)];a[2]["instrumentor"]="v2"
        self.assertFalse(mod.plateau(a))
    def test_unknown_branch_delta_cannot_be_zero_gain(self):
        a=[pulse(1),pulse(2),pulse(3)];a[2]["metrics"]["comparable_new_branches_covered"]=None
        self.assertFalse(mod.plateau(a))
    def test_pending_native_halts_duplicate_runners(self):
        self.assertEqual(self.stop(pending=True)["action"],"WAIT_NATIVE")
    def test_first_red_supersedes_green_and_plateau(self):
        reds=[{"source_sha":SHA,"owner":"MissionControl","url":"https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/1"}]
        a=self.stop(pulses=[pulse(1),pulse(2),pulse(3)],reds=reds)
        self.assertEqual(a["action"],"REPAIR_FIRST_RED")
    def test_untrusted_first_red_refused(self):
        with self.assertRaisesRegex(ValueError,"untrusted first red"):
            self.stop(reds=[{"source_sha":"d"*40,"owner":"X","url":"https://github.com/a"}])
    def test_required_security_is_noncompensating(self):
        g=dict(GATES);g["security"]="FAIL"
        replay=[{"source_sha":SHA,"run_id":1,"conclusion":"success"},{"source_sha":SHA,"run_id":2,"conclusion":"success"}]
        self.assertEqual(self.stop(gates=g,repeat=replay)["action"],"OWNER_BLOCKED")
    def test_missing_review_blocks_even_two_green_replays(self):
        g=dict(GATES);g["independent_review"]="MISSING"
        replay=[{"source_sha":SHA,"run_id":1,"conclusion":"success"},{"source_sha":SHA,"run_id":2,"conclusion":"success"}]
        self.assertEqual(self.stop(gates=g,repeat=replay)["action"],"OWNER_BLOCKED")
    def test_duplicated_run_not_independent(self):
        replay=[{"source_sha":SHA,"run_id":1,"conclusion":"success"}]*2
        self.assertNotEqual(self.stop(repeat=replay)["action"],"TARGET_MET_STOP_ENGINEERING")
    def test_two_successes_different_source_identity_replay_accepted_for_controller_only(self):
        replay=[{"source_sha":SHA,"run_id":1,"conclusion":"success"},{"source_sha":SHA,"run_id":2,"conclusion":"success"}]
        a=self.stop(repeat=replay)
        self.assertEqual(a["action"],"TARGET_MET_STOP_ENGINEERING")
        self.assertEqual(a["merge_admission"],"HOLD")
    def test_stale_or_unsafe_evidence_rejected(self):
        with self.assertRaisesRegex(ValueError,"invalid gate state"):
            self.stop(gates={**GATES,"security":"WAIVED"})
        with self.assertRaisesRegex(ValueError,"untrusted repeat"):
            self.stop(repeat=[{"source_sha":SHA,"run_id":"1","conclusion":"success"}])
    def test_pending_unknown_is_not_false(self):
        with self.assertRaisesRegex(ValueError,"pending must be boolean"):
            mod.evaluate(GATES,[],[],None,SHA,[])
    def test_frozen_actual_stop_is_first_red_hold(self):
        d=json.loads((ROOT/'data/STOP_MODEL_NPLUS2.json').read_text(encoding='utf-8'))
        x=mod.from_snapshot(d)
        self.assertEqual(x["action"],"REPAIR_FIRST_RED")
        self.assertEqual(x["merge_admission"],"HOLD")
    def test_stop_controller_cli_receipt_output(self):
        import sys
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as t:
            out=Path(t)/'receipt.json'
            with patch.object(sys,'argv',['stop_rules.py','--receipt',str(out)]):
                mod.main()
            data=json.loads(out.read_text(encoding='utf-8'))
            # The default model is the current pulse, so a bare run replays the committed N+10 receipt.
            self.assertEqual(data,json.loads((ROOT/'data/STOP_RECEIPT_N10.json').read_text(encoding='utf-8')))
            self.assertEqual(data['action'],'OWNER_BLOCKED')
    def test_frozen_nplus2_replays_with_explicit_model(self):
        import sys
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as t:
            out=Path(t)/'receipt.json'
            with patch.object(sys,'argv',['stop_rules.py','--model',str(ROOT/'data/STOP_MODEL_NPLUS2.json'),'--receipt',str(out)]):
                mod.main()
            self.assertEqual(json.loads(out.read_text(encoding='utf-8'))['action'],'REPAIR_FIRST_RED')
    def test_incomplete_gate_population_refused(self):
        g=dict(GATES);del g['matched_coverage']
        with self.assertRaisesRegex(ValueError,'incomplete or extra'):
            self.stop(gates=g)
    # MACH-II: the solo owner's review waiver counts only when the platform enforces required
    # checks and an automated review exists on the exact head.
    REPLAY=[{"source_sha":SHA,"run_id":1,"conclusion":"success"},{"source_sha":SHA,"run_id":2,"conclusion":"success"}]
    def waiver(self,**review):
        r={"kind":"copilot_review","head_sha":SHA,"url":"https://github.com/GBOGEB/pipeline-automation-hub/pull/1#pullrequestreview-1",**review}
        return {"level":"MACH-II","policy":"https://github.com/GBOGEB/ABACUS/blob/main/docs/governance/CODE_PURPLE_MACH_LADDER.md","automated_review":r}
    def waived(self,waiver,**gates):
        g={**GATES,"independent_review":mod.REVIEW_WAIVER,**gates}
        return mod.evaluate(g,[],[],False,SHA,self.REPLAY,waiver)
    def test_qualified_mach2_waiver_meets_target_and_is_labelled(self):
        a=self.waived(self.waiver())
        self.assertEqual(a["action"],"TARGET_MET_STOP_ENGINEERING")
        self.assertEqual(a["review_basis"],"WAIVED_MACH_II")
        self.assertEqual(a["merge_admission"],"HOLD")
        self.assertFalse(a["formal_release_credit"])
    def test_codeql_counts_as_automated_review(self):
        self.assertEqual(self.waived(self.waiver(kind="codeql"))["action"],"TARGET_MET_STOP_ENGINEERING")
    def test_waiver_without_enforced_required_checks_is_owner_blocked(self):
        for state in ("UNKNOWN","FAIL","MISSING","PENDING"):
            a=self.waived(self.waiver(),required_checks=state)
            self.assertEqual(a["action"],"OWNER_BLOCKED",state)
            self.assertEqual(a["review_basis"],"WAIVER_UNQUALIFIED")
    def test_automated_review_on_another_head_does_not_qualify(self):
        a=self.waived(self.waiver(head_sha="c"*40))
        self.assertEqual(a["action"],"OWNER_BLOCKED")
        self.assertEqual(a["review_basis"],"WAIVER_UNQUALIFIED")
    def test_unknown_review_kind_or_untrusted_links_do_not_qualify(self):
        for w in (self.waiver(kind="human_self_approval"),self.waiver(url="http://example.com/r"),
                  {**self.waiver(),"policy":"local-note.md"},{**self.waiver(),"level":"MACH-I"},
                  {**self.waiver(),"automated_review":None}):
            self.assertEqual(self.waived(w)["action"],"OWNER_BLOCKED",w)
    def test_waiver_replaces_review_only(self):
        for gate in ("security","required_checks","blocked_red_canary","owner_release"):
            with self.assertRaisesRegex(ValueError,"invalid gate state"):
                self.waived(self.waiver(),**{gate:mod.REVIEW_WAIVER})
    def test_waiver_flag_and_record_must_agree(self):
        with self.assertRaisesRegex(ValueError,"waiver state and waiver record disagree"):
            mod.evaluate({**GATES,"independent_review":mod.REVIEW_WAIVER},[],[],False,SHA,self.REPLAY)
        with self.assertRaisesRegex(ValueError,"waiver state and waiver record disagree"):
            mod.evaluate(dict(GATES),[],[],False,SHA,self.REPLAY,self.waiver())
    def test_waiver_does_not_override_first_red(self):
        reds=[{"source_sha":SHA,"owner":"MissionControl","url":"https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/1"}]
        g={**GATES,"independent_review":mod.REVIEW_WAIVER}
        self.assertEqual(mod.evaluate(g,[],reds,False,SHA,self.REPLAY,self.waiver())["action"],"REPAIR_FIRST_RED")
    def test_snapshot_without_waiver_keeps_receipt_shape(self):
        d=json.loads((ROOT/'data/STOP_MODEL_NPLUS2.json').read_text(encoding='utf-8'))
        self.assertNotIn("review_waiver",d)
        self.assertNotIn("review_basis",mod.from_snapshot(d))
    def test_snapshot_carries_waiver_record(self):
        d=json.loads((ROOT/'data/STOP_MODEL_NPLUS2.json').read_text(encoding='utf-8'))
        d["gates"]["independent_review"]=mod.REVIEW_WAIVER
        d["review_waiver"]=self.waiver(head_sha=d["current_main_sha"])
        x=mod.from_snapshot(d)
        self.assertEqual(x["action"],"REPAIR_FIRST_RED")
        self.assertEqual(x["review_basis"],"WAIVER_UNQUALIFIED")
    # N+10: the first pulse bound to exact-head native receipts after the hub ruleset was enforced.
    def n10(self):
        return json.loads((ROOT/'data/STOP_MODEL_N10.json').read_text(encoding='utf-8'))
    def test_n10_replays_owner_blocked_on_security_with_qualified_waiver(self):
        d=self.n10();x=mod.from_snapshot(d)
        self.assertEqual(x["action"],"OWNER_BLOCKED")
        self.assertEqual(x["review_basis"],"WAIVED_MACH_II")
        self.assertEqual(d["gates"]["security"],"FAIL")
        self.assertEqual(x["merge_admission"],"HOLD")
    def test_n10_committed_receipt_matches_replay(self):
        d=self.n10()
        r=json.loads((ROOT/'data/STOP_RECEIPT_N10.json').read_text(encoding='utf-8'))
        self.assertEqual(r,{"schema":"jade.temple.stop_receipt.v2","source_sha":d["current_main_sha"],
                            "proof_level":"SOURCE_MODEL_REPLAY_ONLY",**mod.from_snapshot(d)})
    def test_n10_every_gate_has_a_bound_receipt(self):
        d=self.n10();head=d["current_main_sha"]
        self.assertEqual(set(d["gate_receipts"]),set(mod.REQUIRED_GATES))
        for gate,rec in d["gate_receipts"].items():
            self.assertEqual(rec["state"],d["gates"][gate],gate)
            if rec["state"]=="UNKNOWN":
                self.assertEqual(rec["evidence"],[],gate)
                continue
            self.assertTrue(rec["evidence"],gate)
            for e in rec["evidence"]:
                self.assertTrue(e["url"].startswith("https://github.com/"),gate)
                if gate!="required_checks":
                    self.assertRegex(e["source_sha"],r"^[0-9a-f]{40}$",gate)
                if gate not in ("blocked_red_canary","required_checks"):
                    self.assertEqual(e["source_sha"],head,gate)
    def test_n10_security_alerts_are_what_holds_the_gate(self):
        d=self.n10();alerts=[e for e in d["gate_receipts"]["security"]["evidence"] if e["kind"]=="open_code_scanning_alert"]
        self.assertTrue(alerts)
        self.assertTrue(all(a["path"].startswith("mission-control/jade_temple/") for a in alerts))
    def test_n10_gate_flip_without_matching_receipt_is_rejected(self):
        # Flipping gate states while the receipts still say FAIL / UNKNOWN must never reach target-met.
        d=self.n10();d["gates"]["security"]="PASS";d["gates"]["owner_release"]="PASS"
        with self.assertRaisesRegex(ValueError,"gate receipt disagrees with gate state: (security|owner_release)"):
            mod.from_snapshot(d)
        d=self.n10();d["gates"]["owner_release"]="PASS"
        with self.assertRaisesRegex(ValueError,"disagrees with gate state: owner_release"):
            mod.from_snapshot(d)
    def test_n10_flipped_receipt_without_bound_evidence_is_rejected(self):
        d=self.n10();d["gates"]["owner_release"]="PASS";d["gate_receipts"]["owner_release"]["state"]="PASS"
        with self.assertRaisesRegex(ValueError,"positive gate without receipt evidence: owner_release"):
            mod.from_snapshot(d)
        d["gate_receipts"]["owner_release"]["evidence"]=[{"source_sha":"c"*40,"url":"https://github.com/GBOGEB/pipeline-automation-hub/pull/1"}]
        with self.assertRaisesRegex(ValueError,"not bound to the current head: owner_release"):
            mod.from_snapshot(d)
        d["gate_receipts"]["owner_release"]["evidence"]=[{"source_sha":d["current_main_sha"],"url":"http://example.com/x"}]
        with self.assertRaisesRegex(ValueError,"untrusted gate receipt: owner_release"):
            mod.from_snapshot(d)
    def test_n10_receipts_must_cover_every_gate_and_succeed(self):
        d=self.n10();del d["gate_receipts"]["hosted_parity"]
        with self.assertRaisesRegex(ValueError,"do not cover the gates"):
            mod.from_snapshot(d)
        d=self.n10();d["gate_receipts"]["native_tests"]["evidence"][0]["conclusion"]="failure"
        with self.assertRaisesRegex(ValueError,"unsuccessful receipt: native_tests"):
            mod.from_snapshot(d)
    def test_snapshot_without_receipts_cannot_meet_target(self):
        d=self.n10();del d["gate_receipts"];d["gates"]["security"]="PASS";d["gates"]["owner_release"]="PASS"
        self.assertNotEqual(mod.from_snapshot(d)["action"],"TARGET_MET_STOP_ENGINEERING")
    def test_n10_only_security_and_owner_release_remain(self):
        # The same flips with receipts that agree and are bound to the head are the only way to target-met.
        d=self.n10();head=d["current_main_sha"]
        def grant(gate):
            d["gates"][gate]="PASS"
            d["gate_receipts"][gate]={"state":"PASS","evidence":[{"kind":"test_fixture","source_sha":head,
                "url":"https://github.com/GBOGEB/pipeline-automation-hub/pull/1"}]}
        grant("security")
        self.assertEqual(mod.from_snapshot(d)["action"],"CONTINUE_DISJOINT_MEASUREMENT")
        grant("owner_release")
        self.assertEqual(mod.from_snapshot(d)["action"],"TARGET_MET_STOP_ENGINEERING")
    def test_n10_pulse_reads_the_same_cohort_without_inventing_metrics(self):
        d=self.n10();p=d["pulses"][-1];prev=d["pulses"][-2]
        self.assertEqual(p["id"],"N+10_READBACK")
        self.assertEqual((p["cohort_sha"],p["scope"],p["eligible_denominator"]),(prev["cohort_sha"],prev["scope"],21))
        self.assertEqual(sorted(p["heads"]),sorted(prev["heads"]))
        self.assertTrue(all(v is None for v in p["metrics"].values()))
        self.assertIsNone(d["current_owner_actions"])
    def test_release_cannot_be_qualified_by_json_mutation(self):
        d=json.loads((ROOT/'data/STOP_MODEL_NPLUS2.json').read_text(encoding='utf-8'))
        d["merge_admission"]="PASS"
        with self.assertRaisesRegex(ValueError,"unsafe authority"):
            mod.from_snapshot(d)
if __name__=="__main__":unittest.main()
