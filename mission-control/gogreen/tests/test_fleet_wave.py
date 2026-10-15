"""G4 scoped fleet wave: source integrity, depth, scope delta and anti-fanout."""
import json,sys,unittest
from copy import deepcopy
from pathlib import Path
P=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(P))
from fleet_wave import rollup
CAT=json.loads((P/'samples'/'fleet_g0.json').read_text())

def scout():
    return {'schema':'gogreen.readonly-scout.v1','mode':'PASSIVE_GET_ONLY',
      'requested_runs_per_repo':2,'requested_jobs_per_run':3,'worker_dispatches':0,
      'external_authority_transfer':False,'security_waiver':False,'complete_fleet_census':False,
      'collection_errors':[],'unattributed_non_green':[],
      'repositories':[{'repository':r['repository'],'source_sha':r['head_sha'],
        'runs_considered':2,'successful_jobs_seen':0,'truncated':True,
        'fetch_state':'OBSERVED_PARTIAL_SAMPLE'} for r in CAT['repositories']]}

class G4Controls(unittest.TestCase):
    def test_breadth_and_depth_distinct(self):
        x=rollup(CAT,scout());m=x['metrics']
        self.assertEqual((6,42,1,0),(m['catalog_repos'],m['candidate_cells'],m['observed_cells'],m['verified_bytes_cells']))
        self.assertEqual(8,m['packets_staged']);self.assertEqual(0,m['packets_launched'])
        self.assertFalse(x['merge_authorized']);self.assertIsNone(m['real_worker_capacity'])
        self.assertEqual('DEFER',x['domains']['QPS_TRIAGE']['admission'])
        self.assertEqual(8,len(x['domains']))
    def test_source_sha_drift_rejected(self):
        s=scout();s['repositories'][0]['source_sha']='0'*40
        with self.assertRaises(ValueError):rollup(CAT,s)
    def test_unbounded_fanout_rejected(self):
        with self.assertRaises(ValueError):rollup(CAT,scout(),max_packets=20)
    def test_non_authorized_scout_rejected(self):
        for field,value in [('worker_dispatches',1),('security_waiver',True),('external_authority_transfer',True),('complete_fleet_census',True)]:
            s=scout();s[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):rollup(CAT,s)
    def test_invalid_run_job_cardinality_rejected(self):
        for field,n in [('runs_considered',9),('successful_jobs_seen',7)]:
            s=scout();s['repositories'][0][field]=n
            with self.subTest(field=field),self.assertRaises(ValueError):rollup(CAT,s)
    def test_missing_first_red_and_errors_rejected(self):
        s=scout();del s['unattributed_non_green']
        with self.assertRaises(ValueError):rollup(CAT,s)
    def test_unknown_not_imputed_to_zero(self):
        s=scout()
        for r in s['repositories']:r.update(fetch_state='UNKNOWN_ERROR',runs_considered=0,successful_jobs_seen=0,truncated=None)
        x=rollup(CAT,s)
        self.assertEqual(0,x['metrics']['reachable_repos'])
        self.assertIsNone(x['metrics']['root_closure'])
        self.assertEqual('UNKNOWN',x['domains']['LDAB_LLDB']['state'])
    def test_delta_matches_only_identical_catalog(self):
        x=rollup(CAT,scout());y=rollup(CAT,scout(),'G4-P1',x)
        self.assertEqual('MATCHED_CATALOG',y['delta']['scope'])
        self.assertEqual(0,y['delta']['observed_cells'])
        c=deepcopy(CAT);c['repositories'][0]['head_sha']='0'*40;c['observations']=[]
        s=scout();s['repositories'][0]['source_sha']='0'*40
        y=rollup(c,s,'G4-P1',x)
        self.assertIsNone(y['delta']['observed_cells'])
    def test_unauthorized_first_red_repo_rejected(self):
        s=scout();s['unattributed_non_green']=[{'repository':'outside/tenant'}]
        with self.assertRaises(ValueError):rollup(CAT,s)
    def test_disposition_does_not_claim_root(self):
        x=rollup(CAT,scout())
        self.assertTrue(all(p['state']=='STAGED_NOT_LAUNCHED' and p['root_id'] is None for p in x['packets']))
    def test_invalid_pulse_rejected(self):
        with self.assertRaises(ValueError):rollup(CAT,scout(),'invalid')
    def test_boolean_budget_rejected(self):
        s=scout();s['requested_jobs_per_run']=True
        with self.assertRaises(ValueError):rollup(CAT,s)

if __name__=='__main__':unittest.main()
