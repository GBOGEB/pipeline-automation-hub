import unittest,copy,tempfile,json,hashlib
from pathlib import Path
import regime_controller as m
S='a'*40

def obs(t,q,ids=None,**kwargs):
    x={'schema':'gogreen.queue-wave.v1','repo':'GBOGEB/ABACUS','sha':S,'observed_at':t,'queued':q,'queued_run_ids':ids,'new_run_ids':None,'exited_run_ids':None,'queue_age_seconds':None,'terminal':{'pass':None,'fail':None,'cancelled':None},'coverage':None,'worker_cost_minutes':None,'verified_closed_root_ids':None}
    x.update(kwargs);return x
A=obs('2026-10-15T08:00:00Z',3,[1,2,3]);B=obs('2026-10-15T08:10:00Z',2,[2,4])
class Tests(unittest.TestCase):
    def test_queue_delta_is_not_closure(self):
        x=m.wave(A,B);self.assertEqual(x['queued_delta'],-1);self.assertIsNone(x['independently_verified_root_closures']);self.assertFalse(x['merge_authorized'])
    def test_identity_join(self):
        x=m.wave(A,B);self.assertEqual(x['new_run_ids'],[4]);self.assertEqual(x['exited_run_ids'],[1,3])
    def test_missing_ids_unknown(self):
        x=m.wave(obs(A['observed_at'],3),obs(B['observed_at'],2));self.assertIsNone(x['exited_run_ids'])
    def test_promotion_requires_all(self):
        self.assertEqual(m.wave(A,B,True,True,True)['regime'],'RECOVERING')
        for bits in [(False,True,True),(True,False,True),(True,True,False)]:self.assertEqual(m.wave(A,B,*bits)['regime'],'CONGESTED')
    def test_requested_stable_requires_proof(self):
        self.assertEqual(m.wave(A,B,True,True,True,'STABLE')['regime'],'STABLE')
        self.assertEqual(m.wave(A,B,True,False,True,'STABLE')['regime'],'CONGESTED')
    def test_refuse_cross_sha(self):
        b=copy.deepcopy(B);b['sha']='b'*40
        with self.assertRaises(ValueError):m.wave(A,b)
    def test_nonmonotone_time(self):
        with self.assertRaises(ValueError):m.wave(B,A)
    def test_incomplete_queue_ids(self):
        b=copy.deepcopy(B);b['queued']=3
        with self.assertRaises(ValueError):m.wave(A,b)
    def test_bad_arrival_claim(self):
        b=copy.deepcopy(B);b['new_run_ids']=[9]
        with self.assertRaises(ValueError):m.wave(A,b)
    def test_quantiles(self):
        b=copy.deepcopy(B);b['queue_age_seconds']=[10,20,30,40]
        z=m.wave(A,b);self.assertEqual(z['queue_age_p50_seconds'],20);self.assertEqual(z['queue_age_p95_seconds'],40)
    def test_coverage_matched(self):
        a=copy.deepcopy(A);b=copy.deepcopy(B)
        cov={'covered':8,'eligible':10,'scope':'sc','tool':'coverage.py 7','selection':'test','sha':S}
        a['coverage']=cov;b['coverage']={**cov,'covered':9}
        self.assertEqual(m.wave(a,b)['coverage_delta_pp'],10)
        b['coverage']['eligible']=11;self.assertIsNone(m.wave(a,b)['coverage_delta_pp'])
    def test_bad_coverage_denominator(self):
        b=copy.deepcopy(B);b['coverage']={'covered':11,'eligible':10,'scope':'sc','tool':'t','selection':'s','sha':S}
        with self.assertRaises(ValueError):m.wave(A,b)
    def test_closure_needs_ids(self):
        b=copy.deepcopy(B);b['verified_closed_root_ids']=['root-a'];self.assertEqual(m.wave(A,b)['independently_verified_root_closures'],1)
    def test_terminal_unknown_not_zero(self):
        self.assertIsNone(m.wave(A,B)['terminal']['pass'])
    def test_reject_wrong_timezone(self):
        b=copy.deepcopy(B);b['observed_at']='2026-10-15T10:10:00+02:00'
        with self.assertRaises(ValueError):m.wave(A,b)
    def test_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            digest=m.emit(m.wave(A,B),d);self.assertEqual(digest,hashlib.sha256((Path(d)/'regime_receipt.json').read_bytes()).hexdigest())
if __name__=='__main__':unittest.main()
