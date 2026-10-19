"""Fail-closed N+i read-only scale-dock regression and negative controls."""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE=Path(__file__).resolve().parents[1]/'scale_dock.py'
spec=importlib.util.spec_from_file_location('scale_dock',MODULE)
dock=importlib.util.module_from_spec(spec);spec.loader.exec_module(dock)
A='a'*40; B='b'*40; M='c'*40

def fixture():
    rows=[]
    for i, (family,priority,mode,path,node,fp,root) in enumerate([
       ('GOVERNANCE','P0','SUPERVISED_REPAIR','ci/governance','GATE','same',None),
       ('SECURITY','P0','UNSUPERVISED_READONLY',None,'GATE','same',None),
       ('COMPATIBILITY','P1','SUPERVISED_REPAIR','src/compat.py','BUILD','python','root-hyp-a'),
       ('COVERAGE','P2','UNSUPERVISED_READONLY',None,'BUILD','zero',None),
       ('EVIDENCE','P1','UNSUPERVISED_READONLY',None,'ZIP','manifest','root-hyp-b'),
    ],1):
        rows.append({'id':f'F{i}','repo':'GBOGEB/ABACUS', 'source_sha':A,
            'run_id':100+i,'attempt':1,'job_id':200+i,'first_failed_step':'stage 1',
            'fingerprint':fp,'root_id':root,'owner_accepted':False,
            'family':family,'priority':priority,'state':'RED','dag_node':node,
            'mode':mode,'mutation_paths':[path] if path else []})
    base={'source_heads':{'GBOGEB/ABACUS':A,'GBOGEB/CODEX':B}, 'eligible':5,
        'findings':rows, 'queue':{'queued_run_ids':[],'queue_ages_seconds':[],
                                 'verified_runner_slots':None,'real_dispatches':0},
        'coverage':[{'repo':'GBOGEB/ABACUS','source_sha':A,'population':'same-cohort',
                     'tool':'coverage.py','selection':'same-test','scope':'src/compat.py',
                     'statements':{'covered':8,'eligible':10},
                     'branches':{'covered':4,'eligible':6}}]}
    p0=copy.deepcopy(base);p0.update(n=0,observed_at='2026-10-19T12:00:00Z')
    p1=copy.deepcopy(base);p1.update(n=1,observed_at='2026-10-19T12:10:00Z')
    p1['findings'][0]['state']='RECOVERED'
    p1['coverage'][0]['statements']['covered']=9
    p2=copy.deepcopy(p1);p2.update(n=2,observed_at='2026-10-19T12:20:00Z')
    return {'schema':dock.SCHEMA,'observation_class':'SYNTHETIC_REFERENCE',
        'cohort_id':'CP-TEST-SYNTHETIC','repos':['GBOGEB/ABACUS','GBOGEB/CODEX'],
        'controls':{'authority_transfer':False,'merge_admission':'HOLD',
          'dispatch_authorized':False,'security_waiver':False,
          'qps_engineering_acceptance':False},
        'dag':{'nodes':['GATE','BUILD','ZIP','CONSUMER'],
               'hard_edges':[['GATE','BUILD'],['BUILD','ZIP'],['ZIP','CONSUMER']]},
        'gg_math_provider_sha':M,'gg_math_decision':None,'pulses':[p0,p1,p2]}

class ScaleDockTests(unittest.TestCase):
    def bad(self, fn):
        x=fixture();fn(x)
        with self.assertRaises(ValueError):dock.evaluate(x)
    def test_three_pulse_stop_is_diagnose_not_admission(self):
        r=dock.evaluate(fixture())
        self.assertEqual(r['stop_decision'],'STOP_SCALING_DIAGNOSE_RESIDUAL')
        self.assertEqual(len(r['pulses']),3)
        self.assertEqual(r['latest_unresolved_manifestations'],4)
        self.assertFalse(r['dispatch_authorized'])
        self.assertEqual(r['merge_admission'],'HOLD')
    def test_distinct_populations(self):
        r=dock.evaluate(fixture());p=r['pulses'][-1]
        self.assertEqual((p['observed'],p['eligible'],p['fingerprints']), (5,5,4))
        self.assertEqual(p['repeated_fingerprint_occurrences'],1)
        self.assertEqual(len(p['candidate_root_ids']),2)
        self.assertEqual(p['accepted_root_ids'],[])
    def test_matched_coverage_delta(self):
        r=dock.evaluate(fixture())
        self.assertEqual(r['comparisons'][0]['matched_coverage'][0]['statement_delta_pp'],10.0)
        self.assertEqual(r['comparisons'][0]['matched_coverage'][0]['branch_delta_pp'],0.0)
    def test_changed_denominator_no_coverage_credit(self):
        x=fixture();x['pulses'][1]['coverage'][0]['statements']['eligible']=11
        out=dock.evaluate(x)['comparisons'][0]['matched_coverage'][0]
        self.assertFalse(out['matched_denominators'])
        self.assertIsNone(out['statement_delta_pp'])
    def test_hard_dag_fanout_and_priority(self):
        r=dock.evaluate(fixture())
        self.assertEqual(r['dag']['downstream_declared']['GATE'],3)
        self.assertEqual(r['ranked'][0]['priority'],'P0')
        self.assertIsNone(r['dag']['runtime_verified_edges'])
    def test_two_disjoint_write_proposals_zero_dispatch(self):
        r=dock.evaluate(fixture());p=r['shadow_proposals']
        self.assertEqual(p['supervised_source_writers'],['F3'])
        self.assertEqual(p['real_dispatches'],0)
        self.assertEqual(p['real_writer_leases'],0)
        self.assertIsNone(r['worker_hours'])
    def test_overlap_writer_paths_one_proposal(self):
        x=fixture();x['pulses'][-1]['findings'][2]['mutation_paths']=['ci/governance/policy.yaml']
        r=dock.evaluate(x)
        self.assertEqual(r['shadow_proposals']['supervised_source_writers'],['F3'])
    def test_adaptive_regime_unknown_holds(self):
        x=fixture();x['pulses'][-1]['queue']['queued_run_ids']=None
        x['pulses'][-1]['queue']['queue_ages_seconds']=None
        r=dock.evaluate(x)['shadow_proposals']
        self.assertEqual(r['regime'],'UNKNOWN_HOLD')
        self.assertEqual(r['proposal_caps'],{'readers':0,'writers':0})
    def test_queue_congested_p95_throttles(self):
        x=fixture();x['pulses'][-1]['queue'].update(queued_run_ids=[44],queue_ages_seconds=[800])
        r=dock.evaluate(x)['shadow_proposals']
        self.assertEqual(r['regime'],'CONGESTED_HOLD')
        self.assertEqual(r['read_only'],[])
    def test_queue_recovering_caps(self):
        x=fixture();x['pulses'][-1]['queue'].update(queued_run_ids=[44],queue_ages_seconds=[30])
        r=dock.evaluate(x)['shadow_proposals']
        self.assertEqual(r['regime'],'RECOVERING')
        self.assertEqual(r['proposal_caps'],{'readers':2,'writers':1})
    def test_reads_are_unsupervised_only(self):
        self.assertEqual(len(dock.evaluate(fixture())['shadow_proposals']['read_only']),3)
    def test_queue_unknown_no_plateau(self):
        x=fixture();x['pulses'][-1]['queue']['queued_run_ids']=None
        x['pulses'][-1]['queue']['queue_ages_seconds']=None
        self.assertEqual(dock.evaluate(x)['stop_decision'],'CONTINUE_BOUNDED_OBSERVATION')
    def test_changed_coverage_numerator_not_fixed_point(self):
        x=fixture();x['pulses'][-1]['coverage'][0]['statements']['covered']=10
        self.assertEqual(dock.evaluate(x)['stop_decision'],'CONTINUE_BOUNDED_OBSERVATION')
    def test_queue_identity_change_not_fixed_point(self):
        x=fixture();x['pulses'][-2]['queue'].update(queued_run_ids=[1],queue_ages_seconds=[10])
        x['pulses'][-1]['queue'].update(queued_run_ids=[2],queue_ages_seconds=[10])
        self.assertEqual(dock.evaluate(x)['comparisons'][-1]['queue_run_exits'],[1])
        self.assertEqual(dock.evaluate(x)['stop_decision'],'CONTINUE_BOUNDED_OBSERVATION')
    def test_source_head_drift_no_false_fixed_point(self):
        x=fixture();x['pulses'][-1]['source_heads']['GBOGEB/CODEX']='d'*40
        self.assertEqual(dock.evaluate(x)['stop_decision'],'CONTINUE_BOUNDED_OBSERVATION')
    def test_missing_observation_population_no_fixed_point(self):
        x=fixture();x['pulses'][-1]['eligible']=6
        self.assertEqual(dock.evaluate(x)['stop_decision'],'HOLD_INCOMPARABLE_OR_NEW_STATE')
    def test_full_recovered_still_hold(self):
        x=fixture()
        for p in x['pulses'][-2:]:
            for f in p['findings']:f['state']='RECOVERED'
        r=dock.evaluate(x)
        self.assertEqual(r['stop_decision'],'CANDIDATE_FIXED_POINT_ADMISSION_HOLD')
        self.assertFalse(r['qps_engineering_acceptance'])
    def test_missing_source_sha(self):
        self.bad(lambda x:x['pulses'][1]['source_heads'].update({'GBOGEB/ABACUS':'bad'}))
    def test_mismatched_job_source(self):
        self.bad(lambda x:x['pulses'][1]['findings'][0].update(source_sha=B))
    def test_duplicate_id(self):
        self.bad(lambda x:x['pulses'][1]['findings'][1].update(id='F1'))
    def test_duplicate_native_job_identity(self):
        self.bad(lambda x:x['pulses'][1]['findings'][1].update(run_id=101,job_id=201))
    def test_partial_native_tuple(self):
        self.bad(lambda x:x['pulses'][1]['findings'][0].update(attempt=None))
    def test_missing_first_red_step_typed_unknown(self):
        x=fixture();x['pulses'][1]['findings'][0]['first_failed_step']=None
        r=dock.evaluate(x)
        self.assertEqual(r['pulses'][1]['first_red_steps_known'],4)
    def test_fabricated_source_owner(self):
        self.bad(lambda x:x['pulses'][1]['findings'][0].update(owner_accepted=True))
    def test_invalid_severity(self):
        self.bad(lambda x:x['pulses'][0]['findings'][0].update(priority='P-1'))
    def test_unrecognized_family(self):
        self.bad(lambda x:x['pulses'][0]['findings'][0].update(family='MYSTERY'))
    def test_invalid_lease_parent(self):
        self.bad(lambda x:x['pulses'][0]['findings'][0].update(mutation_paths=['../unsafe']))
    def test_missing_repair_lease(self):
        self.bad(lambda x:x['pulses'][0]['findings'][0].update(mutation_paths=[]))
    def test_unrecognized_dag_node(self):
        self.bad(lambda x:x['pulses'][0]['findings'][0].update(dag_node='alien'))
    def test_hard_cycle(self):
        self.bad(lambda x:x['dag']['hard_edges'].append(['CONSUMER','GATE']))
    def test_dag_duplicate_arc(self):
        self.bad(lambda x:x['dag']['hard_edges'].append(['GATE','BUILD']))
    def test_queue_ages_cardinality(self):
        self.bad(lambda x:x['pulses'][1]['queue'].update(queue_ages_seconds=[1]))
    def test_negative_queue_age(self):
        self.bad(lambda x:x['pulses'][1]['queue'].update(queued_run_ids=[42],queue_ages_seconds=[-1]))
    def test_no_remote_dispatch_credit(self):
        self.bad(lambda x:x['pulses'][1]['queue'].update(real_dispatches=1))
    def test_no_false_authority_promotion(self):
        self.bad(lambda x:x['controls'].update(merge_admission='PASS'))
    def test_utc_not_local(self):
        self.bad(lambda x:x['pulses'][1].update(observed_at='2026-10-19T14:10:00+02:00'))
    def test_monotonic_n(self):
        self.bad(lambda x:x['pulses'][2].update(n=1))
    def test_strict_gg_math_contract(self):
        x=fixture();payload={'schema':'gg_math.g3a_pulse_decision.v1',
        'provider_sha':M,'merge_admission':'HOLD','authority_transfer':False,
        'qps_acceptance':False,'six_sigma_verified':False,'root_closure_credit':None,
        'pca_readiness':'DEFER_UNMATCHED_JOINT_ROWS',
        'bt_readiness':'DEFER_NO_OBSERVED_PAIRWISE_COMPARISONS','forecast_mae':.01}
        payload['receipt_sha256']=hashlib.sha256(json.dumps(payload,sort_keys=True,
                  separators=(',',':')).encode()).hexdigest()
        x['gg_math_decision']=payload
        self.assertEqual(dock.evaluate(x)['gg_math_dock']['forecast_mae'],.01)
        payload['forecast_mae']=0
        with self.assertRaisesRegex(ValueError,'math receipt digest'):dock.evaluate(x)
    def test_math_maturity_cannot_self_pass(self):
        x=fixture();x['gg_math_decision']={'schema':'gg_math.g3a_pulse_decision.v1',
          'provider_sha':M,'merge_admission':'PASS'}
        with self.assertRaises(ValueError):dock.evaluate(x)
    def test_deterministic_byte_manifests_and_html(self):
        r=dock.evaluate(fixture())
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
            ma=dock.emit(r,Path(a),A); mb=dock.emit(r,Path(b),A)
            self.assertEqual(ma,mb)
            for name, row in ma['members'].items():
                raw=(Path(a)/name).read_bytes()
                self.assertEqual(row['bytes'],len(raw))
                self.assertEqual(row['sha256'],hashlib.sha256(raw).hexdigest())
            self.assertIn('N+1 = N?', (Path(a)/'scale-dock.mmd').read_text())
            self.assertIn('<table>', (Path(a)/'scale-dock.html').read_text())
    def test_html_escapes_ids(self):
        x=fixture()
        for p in x['pulses']:p['findings'][0]['id']='<script>attack()</script>'
        page=dock.render_html(dock.evaluate(x))
        self.assertNotIn('<script>',page)
        self.assertIn('&lt;script&gt;',page)
    def test_stress_260_fingerprints_not_260_roots(self):
        x=fixture()
        for p in x['pulses']:
            t=p['findings'][0]
            p['findings']=[{**t, 'id':f'R{i}', 'run_id':i+300, 'job_id':i+1000,
                            'mode':'UNSUPERVISED_READONLY', 'mutation_paths':[],
                            'fingerprint':f'F{i//20}', 'root_id':None,'state':'RED'} for i in range(260)]
            p['eligible']=260
        r=dock.evaluate(x)
        p=r['pulses'][-1]
        self.assertEqual((p['observed'],p['fingerprints'],p['repeated_fingerprint_occurrences']),
                         (260,13,247))
        self.assertEqual(p['candidate_root_ids'],[])
        self.assertEqual(len(r['shadow_proposals']['read_only']),4)

if __name__=='__main__':unittest.main()
