import copy
import unittest
from g3a_metric_consumer import consume, digest
H='a'*40; P='b'*40; M='c'*40
IDS=['QUEUE_P95','EXACT_HEAD_PROOF_YIELD','FIRST_RED_COUNT','ACCEPTED_RECEIPT_YIELD','PREDICTION_VS_ACTUAL','RUNNER_HEALTH']
def taxonomy(): return {'schema':'missioncontrol.phase02_kpi_taxonomy.v1','kpis':[{'id':v} for v in IDS]}
def sample():
    r={'schema':'gg_math.g3a_metric_bridge.v1',
       'source_repo':'GBOGEB/ABACUS','provider_repo':'GBOGEB/gg_MATH',
       'provider_sha':P,'source_head':H,'authority_transfer':False,
       'merge_admission':'HOLD','dispatch':'NOT_LAUNCHED',
       'qps_acceptance':False,'global_score':None,'federation_coverage':None,
       'coverage_n_series':[{'head_sha':M,'ratio':.79},{'head_sha':P,'ratio':.88}],
       'historical_coverage':.88,'current_coverage':None}
    r['receipt_sha256']=digest(r)
    return r
class Tests(unittest.TestCase):
    def test_basic_projection(self):
        self.assertEqual(consume(sample(),taxonomy(),consumer_sha=M)['merge_admission'],'HOLD')
    def test_read_only(self):
        self.assertTrue(consume(sample(),taxonomy(),consumer_sha=M)['read_only'])
    def test_no_new_kpis(self):
        self.assertFalse(consume(sample(),taxonomy(),consumer_sha=M)['new_kpi_registry_created'])
    def test_six_families(self):
        self.assertEqual(consume(sample(),taxonomy(),consumer_sha=M)['canonical_kpi_count'],6)
    def test_current_unknown(self):
        self.assertIsNone(consume(sample(),taxonomy(),consumer_sha=M)['current_coverage'])
    def test_source_bound(self):
        self.assertEqual(consume(sample(),taxonomy(),consumer_sha=M)['source_repo'],'GBOGEB/ABACUS')
    def test_bad_consumer_sha(self):
        with self.assertRaises(ValueError):consume(sample(),taxonomy(),consumer_sha='bad')
    def test_missing_canonical_family(self):
        t=taxonomy();t['kpis'].pop()
        with self.assertRaises(ValueError):consume(sample(),t,consumer_sha=M)
    def test_duplicate_canonical_family(self):
        t=taxonomy();t['kpis'].append(t['kpis'][0])
        with self.assertRaises(ValueError):consume(sample(),t,consumer_sha=M)
    def test_bad_taxonomy_schema(self):
        t=taxonomy();t['schema']='fake'
        with self.assertRaises(ValueError):consume(sample(),t,consumer_sha=M)
    def test_bad_receipt_schema(self):
        r=sample();r['schema']='bad'
        with self.assertRaises(ValueError):consume(r,taxonomy(),consumer_sha=M)
    def test_authority_transfer_blocked(self):
        r=sample();r['authority_transfer']=True
        with self.assertRaises(ValueError):consume(r,taxonomy(),consumer_sha=M)
    def test_go_claim_blocked(self):
        r=sample();r['merge_admission']='GO'
        with self.assertRaises(ValueError):consume(r,taxonomy(),consumer_sha=M)
    def test_dispatch_claim_blocked(self):
        r=sample();r['dispatch']='LAUNCHED'
        with self.assertRaises(ValueError):consume(r,taxonomy(),consumer_sha=M)
    def test_qps_claim_blocked(self):
        r=sample();r['qps_acceptance']=True
        with self.assertRaises(ValueError):consume(r,taxonomy(),consumer_sha=M)
    def test_global_score_rejected(self):
        r=sample();r['global_score']=1
        with self.assertRaises(ValueError):consume(r,taxonomy(),consumer_sha=M)
    def test_federation_coverage_rejected(self):
        r=sample();r['federation_coverage']=.88
        with self.assertRaises(ValueError):consume(r,taxonomy(),consumer_sha=M)
    def test_tampered_digest_rejected(self):
        r=sample();r['historical_coverage']=.95
        with self.assertRaises(ValueError):consume(r,taxonomy(),consumer_sha=M)
    def test_bad_source_repo(self):
        r=sample();r['source_repo']='bad'
        r['receipt_sha256']=digest({k:v for k,v in r.items() if k!='receipt_sha256'})
        with self.assertRaises(ValueError):consume(r,taxonomy(),consumer_sha=M)
    def test_stale_current_promoted(self):
        r=sample();r['current_coverage']=.88
        r['receipt_sha256']=digest({k:v for k,v in r.items() if k!='receipt_sha256'})
        with self.assertRaises(ValueError):consume(r,taxonomy(),consumer_sha=M)
    def test_empty_history_rejected(self):
        r=sample();r['coverage_n_series']=[]
        r['receipt_sha256']=digest({k:v for k,v in r.items() if k!='receipt_sha256'})
        with self.assertRaises(ValueError):consume(r,taxonomy(),consumer_sha=M)
    def test_repeat_digest(self):
        self.assertEqual(consume(sample(),taxonomy(),consumer_sha=M)['view_sha256'],
                         consume(sample(),taxonomy(),consumer_sha=M)['view_sha256'])
if __name__=='__main__':unittest.main()
