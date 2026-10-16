"""Paired wave geometry: matched source names but no fabricated independence."""
import copy
import unittest
from abacus_mip_transition import compare
S0='a'*40
S1='b'*40
D='c'*64

def fixture(sha, outcomes):
    return {'repository':'GBOGEB/ABACUS','source_sha':sha,
            'acquisition':'github-actions-rest-exact-pull-request-cohort',
            'census_complete':True,'run_attempts_observed':len(outcomes),
            'runs':[{'id':100+i,'run_attempt':1,'head_sha':sha,'name':name,
                     'status':'completed','conclusion':conclusion}
                    for i,(name,conclusion) in enumerate(outcomes.items())]}

def docs():
    a=fixture(S0,{'CI':'failure','Lint':'success','Security':'failure','A10':'cancelled'})
    b=fixture(S1,{'CI':'success','Lint':'success','Security':'success','A10':'cancelled'})
    return a,b

class TransitionTests(unittest.TestCase):
    def test_two_realistic_gains_and_no_false_statistics(self):
        a,b=docs()
        r=compare(a,b,before_digest=D,after_digest=D)
        self.assertEqual(r['success_before'],1)
        self.assertEqual(r['success_after'],3)
        self.assertEqual(r['workflow_gains'],2)
        self.assertEqual(r['workflow_losses'],0)
        self.assertEqual(r['success_delta_pp'],50)
        self.assertIsNone(r['inferential']['pca_pc1_variance_pct'])
        self.assertIsNone(r['inferential']['bradley_terry_win_probability_pct'])
        self.assertIsNone(r['inferential']['confidence_intervals_90_95_99']['99'])
        self.assertEqual(r['merge_admission'],'HOLD')

    def test_order_invariance_for_native_run_list(self):
        a,b=docs();b["runs"].reverse()
        r=compare(a,b,before_digest=D,after_digest=D)
        self.assertEqual(r["workflow_gains"],2)
        self.assertEqual(r["workflow_losses"],0)

    def test_missing_workflow_denominator_rejected(self):
        a,b=docs();b['runs'].pop();b['run_attempts_observed']-=1
        with self.assertRaisesRegex(ValueError,'unmatched workflow'):
            compare(a,b,before_digest=D,after_digest=D)

    def test_duplicate_names_and_duplicate_run_rejected(self):
        for key in ('name','id'):
            a,b=docs();b['runs'][1][key]=b['runs'][0][key]
            with self.subTest(key=key),self.assertRaises(ValueError):
                compare(a,b,before_digest=D,after_digest=D)

    def test_same_sha_and_stale_run_identity_rejected(self):
        a,b=docs();b['source_sha']=S0
        with self.assertRaises(ValueError):
            compare(a,b,before_digest=D,after_digest=D)
        a,b=docs();b['runs'][0]['head_sha']=S0
        with self.assertRaisesRegex(ValueError,'nonterminal or mismatched'):
            compare(a,b,before_digest=D,after_digest=D)

    def test_pending_or_forged_complete_rejected(self):
        a,b=docs();b['runs'][0]['status']='in_progress'
        with self.assertRaises(ValueError):
            compare(a,b,before_digest=D,after_digest=D)
        a,b=docs();a['census_complete']=False
        with self.assertRaises(ValueError):
            compare(a,b,before_digest=D,after_digest=D)

if __name__=='__main__':
    unittest.main()
