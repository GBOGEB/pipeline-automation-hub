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

def docks():
    t='2026-10-19T12:00:00+00:00'
    return {
     'everred':{'schema':'everred.census/1.0','generated_at':t,
        'metrics':{'occurrences_total':40,'distinct_signatures':10,'unmatched_signatures':4,
          'roots_independent':3,'control_plane_red':1,'control_plane_probed':2,
          'root_closure_rate':.25,'recurrence_rate':0.0,'failure_amplification':1.5},
        'probes':{'R-P0':{'red':True},'R-P2':{'red':False}},
        'roots':[{'id':'R-P0','aliases':['root-hyp-a'],'state':'BLOCKED_AUTHORITY','severity':'P0'},
                 {'id':'R-P2','aliases':[],'state':'TRIAGED','severity':'P2'},
                 {'id':'R-DONE','aliases':[],'state':'VERIFIED_FIXED','severity':'P1'}]},
     'code_purple':{'schema':'code-purple.census/v2','generated_at':t,'incident':'CP-X','lifted':False,
        'repos':{'GBOGEB/ABACUS':{'open_prs':7}},
        'lift':[{'id':'L1','ok':True},{'id':'L2','ok':False}],
        'admission_audit':{'merged':10,'gate_green':2,'ungated':8,'with_red_checks':5},
        'follow_ups':[{'state':'open'},{'state':'closed'}]},
     'p_process':{'schema':'p-process.state/1.0','generated_at':t,'census_at':t,'everred_at':t,
        'incident':'CP-X','lifted':False,
        'repos':{'GBOGEB/ABACUS':{'mode':'CODE_PURPLE','open_roots':2,'worst':'P0','ruleset':'RED','reasons':['E1','E2']},
                 'GBOGEB/CODEX':{'mode':'EVERRED','open_roots':0,'worst':'NONE','ruleset':'GREEN','reasons':[]}}},
     'issue_bd':{'schema':'codepurple.bd-queue-wave.v1','scope':'LIVE_PUBLIC_THREE_REPO_PARTIAL_QPS_UNKNOWN',
        'open_prs':10,'open_issues':30,'open_items':40,'prs_with_failed_workflows':6,
        'prs_without_observed_failure':2,'prs_unknown':2,'manifestations':18,
        'family_groups':[{'family':'SECURITY','affected_prs':4,'failed_workflows':9,'candidate_owner':'ABACUS#1738'}],
        'issues':[{'repository':'GBOGEB/ABACUS','open_issues':30}],
        'queue_latency_workflow_level':{'n':3,'p50_seconds':12,'p95_seconds':90},
        'private_qps_open_issues':None,'independent_root_count':None,
        'authority_transfer':False,'dispatch_authorized':False,'merge_authorized':False},
     'crosswalk':{'schema':'codepurple.g5.discovery-gap-crosswalk.v1',
        'historical_g1':{'eligible_cells':4,'observed_cells':1,'missing_cells':3},
        'current_cohort':{'eligible_cells':4,'validated_observed_cells':None,'repos':[{},{}]},
        'gap_packets':[{'packet_id':'G1','family':'security','state':'UNKNOWN','dispatch_authorized':False,
                        'native_run_id':None,'run_attempt':None,'job_id':None,'root_id':None},
                       {'packet_id':'G2','family':'coverage','state':'OBSERVED','dispatch_authorized':False,
                        'native_run_id':9,'run_attempt':1,'job_id':3,'artifact_id':5,
                        'archive_bytes_verified':True,'root_id':'R-P2'}],
        'controls':{'merge_authorized':False,'security_waiver':False,'authority_transfer':False,
                    'qps_owner_acceptance':False}}}

def docked():
    x=fixture();x['docks']=docks();return x

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

class RedMetricTests(unittest.TestCase):
    def test_first_red_root_red_accounting(self):
        red=dock.evaluate(fixture())['red_metrics'];last=red['pulses'][-1]
        self.assertEqual((last['red'],last['root_linked_red'],last['unrooted_red']),(4,2,2))
        self.assertEqual(last['root_red'],['root-hyp-a','root-hyp-b'])
        self.assertEqual(red['transitions'][0]['recoveries'],['F1'])
        self.assertEqual(red['everred_in_window'],['F2','F3','F4','F5'])
        self.assertEqual((red['red_burndown'],red['recovery_rate'],red['regression_rate']),(1,.2,0.0))
        self.assertEqual(red['authority'],'MANIFESTATION_STATE_ONLY_NO_ROOT_CLOSURE_CREDIT')
    def test_regression_and_new_first_red(self):
        x=fixture();x['pulses'][2]['findings'][0]['state']='RED'
        x['pulses'][2]['findings'].append({**x['pulses'][2]['findings'][1],'id':'F6','run_id':999,'job_id':998})
        x['pulses'][2]['eligible']=6
        m=dock.evaluate(x)['red_metrics']['transitions'][-1]
        self.assertEqual((m['regressions'],m['new_first_reds']),(['F1'],['F6']))
        self.assertEqual(dock.evaluate(x)['red_metrics']['regression_rate'],1.0)
    def test_root_recovered_and_unknown_step_rate(self):
        x=fixture()
        for f in x['pulses'][2]['findings']:
            if f['root_id']=='root-hyp-a':f['state']='RECOVERED'
        x['pulses'][2]['findings'][1]['first_failed_step']=None
        last=dock.evaluate(x)['red_metrics']['pulses'][-1]
        self.assertEqual(last['root_recovered'],['root-hyp-a'])
        self.assertEqual(last['red_first_step_known_rate'],.6667)
    def test_fingerprint_root_conflict_flagged(self):
        x=fixture();x['pulses'][2]['findings'][4]['fingerprint']='python'
        self.assertEqual(dock.evaluate(x)['red_metrics']['pulses'][-1]['fingerprint_root_conflicts'],['python'])

class DockTests(unittest.TestCase):
    def bad(self, fn):
        x=docked();fn(x['docks'])
        with self.assertRaises(ValueError):dock.evaluate(x)
    def test_undocked_sources_are_unknown_not_zero(self):
        r=dock.evaluate(fixture())
        self.assertEqual({v['status'] for v in r['docks'].values()},{'NOT_DOCKED'})
        self.assertEqual(r['dock_consistency']['state'],'NOT_COMPARABLE')
        self.assertIn('never zero',dock.render_html(r))
    def test_everred_metrics_and_root_crosswalk(self):
        e=dock.evaluate(docked())['docks']['everred']
        m=e['metrics']
        self.assertEqual((m['roots_open'],m['signature_match_rate'],m['control_plane_red_rate']),(2,.6,.5))
        self.assertEqual(m['e1_red_p0_probes'],['R-P0'])
        self.assertEqual(m['scale_dock_roots_matched'],{'root-hyp-a':'R-P0'})
        self.assertEqual(m['scale_dock_roots_unmatched'],['root-hyp-b'])
        self.assertEqual(e['age_hours_at_latest_pulse'],.33)
        self.assertFalse(e['stale'])
    def test_code_purple_p_process_bd_crosswalk_metrics(self):
        d=dock.evaluate(docked())['docks']
        cp,pp,bd,xw=(d[k]['metrics'] for k in ('code_purple','p_process','issue_bd','crosswalk'))
        self.assertEqual((cp['lift_unmet'],cp['gate_green_rate'],cp['red_merge_rate'],cp['follow_ups_open']),(['L2'],.2,.5,1))
        self.assertEqual((pp['code_purple_repos'],pp['open_roots'],pp['worst_priority'],pp['ruleset_red_rate']),(['GBOGEB/ABACUS'],2,'P0',.5))
        self.assertEqual((bd['red_pr_rate'],bd['unknown_pr_rate'],bd['manifestations_per_red_pr']),(.75,.2,3.0))
        self.assertFalse(bd['full_census'])
        self.assertIsNone(bd['private_qps_open_issues'])
        self.assertEqual((xw['historical_breadth'],xw['native_identity_rate'],xw['archive_bytes_verified'],xw['root_bound']),(.25,.5,1,1))
        self.assertIsNone(xw['current_breadth'])
    def test_consistency_agrees(self):
        r=dock.evaluate(docked())
        self.assertEqual(r['dock_consistency']['state'],'CONSISTENT_WHERE_OBSERVED')
        self.assertEqual(r['stop_decision'],'STOP_SCALING_DIAGNOSE_RESIDUAL')
    def test_consistency_disagreement_holds(self):
        x=docked();x['docks']['p_process']['repos']['GBOGEB/ABACUS']['mode']='EVERRED'
        x['docks']['p_process']['incident']='CP-Y'
        c=dock.evaluate(x)['dock_consistency']
        self.assertEqual(c['state'],'HOLD_SOURCE_DISAGREEMENT')
        self.assertEqual({k['check'].split(':')[0] for k in c['checks'] if k['state']=='DISAGREE'},{'incident','E1','E2'})
    def test_stale_dock_flagged(self):
        x=docked();x['docks']['everred']['generated_at']='2026-10-10T00:00:00Z'
        self.assertTrue(dock.evaluate(x)['docks']['everred']['stale'])
    def test_dock_html_and_mermaid(self):
        r=dock.evaluate(docked())
        with tempfile.TemporaryDirectory() as a:
            dock.emit(r,Path(a),A)
            page=(Path(a)/'scale-dock.html').read_text();graph=(Path(a)/'scale-dock.mmd').read_text()
        self.assertIn('Docked metrics',page);self.assertIn('75.0%',page)
        self.assertIn('EVERRED root census - DOCKED_READ_ONLY_PROJECTION',graph)
        self.assertIn('N+1 = N?',graph)
    def test_dock_input_digest_bound(self):
        a=dock.evaluate(docked())['docks']['everred']['input_sha256']
        x=docked();x['docks']['everred']['metrics']['occurrences_total']=41
        self.assertNotEqual(a,dock.evaluate(x)['docks']['everred']['input_sha256'])
    def test_unknown_dock(self):self.bad(lambda d:d.update(mystery={}))
    def test_dock_schema(self):self.bad(lambda d:d['everred'].update(schema='everred.census/0.9'))
    def test_dock_local_offset(self):self.bad(lambda d:d['everred'].update(generated_at='2026-10-19T14:00:00+02:00'))
    def test_everred_numerator(self):self.bad(lambda d:d['everred']['metrics'].update(unmatched_signatures=11))
    def test_everred_rate_bounds(self):self.bad(lambda d:d['everred']['metrics'].update(root_closure_rate=1.5))
    def test_everred_alias_collision(self):self.bad(lambda d:d['everred']['roots'][1]['aliases'].append('root-hyp-a'))
    def test_lifted_with_unmet_criteria(self):self.bad(lambda d:d['code_purple'].update(lifted=True))
    def test_audit_numerator(self):self.bad(lambda d:d['code_purple']['admission_audit'].update(gate_green=11))
    def test_p_mode(self):self.bad(lambda d:d['p_process']['repos']['GBOGEB/CODEX'].update(mode='GREEN'))
    def test_bd_partition(self):self.bad(lambda d:d['issue_bd'].update(prs_unknown=3))
    def test_bd_item_parity(self):self.bad(lambda d:d['issue_bd'].update(open_items=41))
    def test_bd_authority(self):self.bad(lambda d:d['issue_bd'].update(merge_authorized=True))
    def test_crosswalk_dispatch(self):self.bad(lambda d:d['crosswalk']['gap_packets'][0].update(dispatch_authorized=True))
    def test_crosswalk_partial_identity(self):self.bad(lambda d:d['crosswalk']['gap_packets'][0].update(native_run_id=4))
    def test_crosswalk_partition(self):self.bad(lambda d:d['crosswalk']['historical_g1'].update(missing_cells=2))
    def test_crosswalk_authority(self):self.bad(lambda d:d['crosswalk']['controls'].update(merge_authorized=True))

if __name__=='__main__':unittest.main()
