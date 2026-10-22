import copy
import unittest
import ldab_guard as g

RUN_ID=301

def row(n=1,status='completed',conclusion='success',steps=True,run_id=RUN_ID):
    o={'id':n,'status':status,'conclusion':conclusion,'run_id':run_id}
    if steps:
        o['steps']=[{'name':'Set up job','number':1,'status':'completed','conclusion':'success'},
                    {'name':'Run unit tests','number':2,'status':'completed','conclusion':'success'}]
    return o

def jobs(rows,total=None):
    return {'total_count':len(rows) if total is None else total,'jobs':rows}

class GuardTests(unittest.TestCase):
    def assess(self, rows,total=None):return g.assess_jobs(jobs(rows,total),'W1',RUN_ID)
    def test_fully_executed_job(self):
        r=self.assess([row()]);self.assertTrue(r['terminal_success_with_steps']);self.assertEqual(r['passing'],1)
    def test_zero_jobs_does_not_turn_green(self):
        r=self.assess([]);self.assertTrue(r['complete']);self.assertFalse(r['nonempty']);self.assertFalse(r['terminal_success_with_steps'])
    def test_queued_job_does_not_turn_green(self):
        r=self.assess([row(status='queued',conclusion=None,steps=False)]);self.assertFalse(r['all_terminal']);self.assertFalse(r['terminal_success_with_steps'])
    def test_zero_steps_does_not_turn_green(self):
        r=self.assess([row(steps=False)]);self.assertFalse(r['executed_step_receipts'])
    def test_wrong_run_id_does_not_turn_green(self):
        r=self.assess([row(run_id=999)]);self.assertFalse(r['run_id_bound']);self.assertFalse(r['terminal_success_with_steps'])
    def test_missing_run_id_does_not_turn_green(self):
        j=row();del j['run_id'];self.assertFalse(self.assess([j])['terminal_success_with_steps'])
    def test_no_unbound_run_credit(self):
        r=g.assess_jobs(jobs([row()]),'W1');self.assertIsNone(r['run_id_bound']);self.assertFalse(r['terminal_success_with_steps'])
    def test_truncated_census_cannot_credit(self):
        r=self.assess([row()],2);self.assertFalse(r['complete']);self.assertIsNone(r['passing']);self.assertFalse(r['terminal_success_with_steps'])
    def test_duplicate_job_denied(self):
        with self.assertRaisesRegex(ValueError,'duplicate job'):self.assess([row(),row()])
    def test_invalid_conclusion_denied(self):
        with self.assertRaisesRegex(ValueError,'nonterminal job conclusion'):self.assess([row(status='queued')])
    def test_failed_step_not_causal_root(self):
        j=row(status='completed',conclusion='failure');j['steps'][1]['conclusion']='failure'
        r=self.assess([j]);self.assertEqual(len(r['ldab_step_manifestations']),1);self.assertIsNone(r['ldab_step_manifestations'][0]['root_id']);self.assertIsNone(r['distinct_causal_roots']);self.assertFalse(r['terminal_success_with_steps'])
    def test_fingerprint_is_deterministic(self):
        j=row(conclusion='failure');j['steps'][1]['conclusion']='failure'
        a=self.assess([j]);b=self.assess([copy.deepcopy(j)]);self.assertEqual(a['ldab_step_manifestations'],b['ldab_step_manifestations'])
    def test_bad_step_ordinal_denied(self):
        j=row();j['steps'][1]['number']=1
        with self.assertRaisesRegex(ValueError,'step ordinal'):self.assess([j])
    def test_malformed_roster_denied(self):
        with self.assertRaisesRegex(ValueError,'census count'):g.assess_jobs({'total_count':True,'jobs':[]},'W1',RUN_ID)
    def test_executed_job_not_test_or_lldb(self):
        r=self.assess([row()]);self.assertIsNone(r['native_tests_executed']);self.assertIsNone(r['lldb_native_debug_session']);self.assertFalse(r['native_artifact_bytes_verified'])
if __name__=='__main__':unittest.main()
