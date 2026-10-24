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
            self.assertEqual(data['action'],'REPAIR_FIRST_RED')
    def test_incomplete_gate_population_refused(self):
        g=dict(GATES);del g['matched_coverage']
        with self.assertRaisesRegex(ValueError,'incomplete or extra'):
            self.stop(gates=g)
    def test_release_cannot_be_qualified_by_json_mutation(self):
        d=json.loads((ROOT/'data/STOP_MODEL_NPLUS2.json').read_text(encoding='utf-8'))
        d["merge_admission"]="PASS"
        with self.assertRaisesRegex(ValueError,"unsafe authority"):
            mod.from_snapshot(d)
if __name__=="__main__":unittest.main()
