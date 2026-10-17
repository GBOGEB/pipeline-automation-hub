"""G3A N+12: forecast/actual, scope parity, and safe SVG/HTML QA tests."""
import copy
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import n3_g3a_assessment as assessment
from test_n3_workflow_census import observation


def frozen():
    return {'schema':'missioncontrol.g3a.forecast_preaction.v1','source_start_head':'a'*40,
            'authority_transfer':False,'merge_admission':'HOLD','mission_id':'CBD-GOLDEN-GRAPH-604',
            'scope':{'baseline_statement_total':378,'baseline_branch_total':98,
                     'baseline_statement_covered':360,'baseline_branch_covered':84,'baseline_tests_passed_local':100},
            'predictions':[{'pulse':p,'expected_cumulative_local_tests_min':floor,'actual':None}
                           for p,floor in [(10,108),(11,115),(12,120)]]}


def obs():
    return {'schema':'missioncontrol.g3a.local_test_observations.v1','source_start_head':'a'*40,
            'provenance':'LOCAL_NOT_NATIVE_EXACT_HEAD',
            'pulses':[{'pulse':p,'tests_passed':n,'tests_failed':0,'source_checkpoint':chr(97+i)*40}
                      for i,(p,n) in enumerate([(10,116),(11,136),(12,148)])]}


def cov():
    # Deterministic reference scope; not the measured real repo coverage input.
    old=['n3_continuation.py','n3_integrity.py','n3_metrics.py','n3_dashboard.py',
         'n3_native_join.py','n3_wave_federation.py']
    statement_totals=[101,55,33,37,83,69]
    branch_totals=[20,28,8,10,14,18]
    statement_cov=[100,54,33,37,80,67]
    branch_cov=[20,26,8,10,12,17]
    files={f'mission-control/v2/{k}':{'summary':{'num_statements':t,'num_branches':b,
            'covered_lines':s,'covered_branches':c}} for k,t,b,s,c in zip(old,statement_totals,branch_totals,statement_cov,branch_cov)}
    # Adjust reference to historical exact six-module denominators 378/98.
    files['mission-control/v2/n3_workflow_census.py']={'summary':{'num_statements':110,'num_branches':22,'covered_lines':107,'covered_branches':19}}
    files['mission-control/v2/n3_g3a_assessment.py']={'summary':{'num_statements':90,'num_branches':18,'covered_lines':85,'covered_branches':15}}
    return {'files':files}


class G3AAssessmentTests(unittest.TestCase):
    def setUp(self):
        self.f=frozen();self.c=observation();self.v=cov();self.o=obs()
    def report(self):return assessment.assess(self.f,self.c,self.v,self.o)
    def reject(self,fn,fragment):
        fn()
        with self.assertRaisesRegex(ValueError,fragment):self.report()

    def test_good_local_results_with_no_native_promotion(self):
        p=self.report()
        self.assertEqual(p['local_test_growth'],48)
        self.assertEqual(p['native_proof_state'],'PENDING_OR_UNVERIFIED_NOT_PASS')
        self.assertIsNone(p['independent_trials'])
        self.assertEqual(p['merge_admission'],'HOLD')
        self.assertTrue(all(x['target_met'] for x in p['planned_vs_actual']))

    def test_forecast_frozen(self):
        self.reject(lambda:self.f['predictions'][0].__setitem__('actual',116),'forecast mutated')

    def test_pulse_ordinal_drift(self):
        self.reject(lambda:self.o['pulses'][0].__setitem__('pulse',9),'actual pulses incomplete')

    def test_invalid_test_count_bool(self):
        self.reject(lambda:self.o['pulses'][0].__setitem__('tests_passed',True),'invalid local test')

    def test_missing_coverage_scope(self):
        self.reject(lambda:self.v['files'].pop('mission-control/v2/n3_native_join.py'),'missing or colliding')

    def test_duplicate_source_basename_rejected(self):
        self.v['files']['other/copy/n3_metrics.py']=copy.deepcopy(self.v['files']['mission-control/v2/n3_metrics.py'])
        with self.assertRaisesRegex(ValueError,'colliding coverage source'):
            self.report()

    def test_cli_writes_consistent_machine_and_human(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d); paths={}
            for k, obj in [('forecast',self.f),('census',self.c),('coverage',self.v),('observations',self.o)]:
                p=base/(k+'.json');p.write_text(json.dumps(obj));paths[k]=p
            out=base/'artifacts'
            argv=['n3_g3a_assessment.py']
            for k,p in paths.items():argv += ['--'+k,str(p)]
            argv += ['--out-dir',str(out)]
            with patch.object(sys,'argv',argv):
                with contextlib.redirect_stdout(io.StringIO()):assessment.main()
            r=json.loads((out/'g3a-evaluation.json').read_text())
            h=(out/'g3a-evaluation.html').read_text()
            self.assertEqual(r['native_proof_state'],'PENDING_OR_UNVERIFIED_NOT_PASS')
            self.assertIn(r['forecast_digest'],h)
            self.assertEqual(r['merge_admission'],'HOLD')

    def test_mismatched_denominator(self):
        self.reject(lambda:self.v['files']['mission-control/v2/n3_continuation.py']['summary'].__setitem__('num_statements',102),'unmatched core')

    def test_head_mismatch(self):
        self.reject(lambda:self.f.__setitem__('source_start_head','b'*40),'forecast/census')

    def test_forged_provenance(self):
        self.reject(lambda:self.o.__setitem__('provenance','NATIVE_EXACT_HEAD'),'observation provenance')

    def test_unmet_forecast_reported_not_rejected(self):
        self.o['pulses'][1]['tests_passed']=110
        self.assertFalse(self.report()['planned_vs_actual'][1]['target_met'])

    def test_failed_tests_cannot_pass_forecast(self):
        self.o['pulses'][2]['tests_failed']=1
        self.assertFalse(self.report()['planned_vs_actual'][2]['target_met'])

    def test_authority_conflict_rejected(self):
        self.reject(lambda:self.f.__setitem__('authority_transfer',True),'authority conflict')

    def test_bad_coverage_counter(self):
        self.reject(lambda:self.v['files']['mission-control/v2/n3_dashboard.py']['summary'].__setitem__('covered_branches',False),'malformed coverage')

    def test_html_render_and_escaping(self):
        p=self.report()
        h=assessment.render(p)
        self.assertIn('svg',h)
        self.assertIn('HOLD',h)
        self.assertIn('&amp;',h)
        p['native_census_source_sha']='<script>alert(1)</script>'
        self.assertNotIn('<script>',assessment.render(p))
        self.assertIn('&lt;script&gt;',assessment.render(p))

    def test_unsafe_render_rejected(self):
        p=self.report();p['merge_admission']='PASS'
        with self.assertRaises(ValueError):assessment.render(p)

    def test_determinism_and_no_mutation(self):
        f=copy.deepcopy(self.f)
        self.assertEqual(self.report(),self.report())
        self.assertEqual(f,self.f)

    def test_actual_forecast_surplus(self):
        p=self.report()
        self.assertEqual([r['forecast_surplus'] for r in p['planned_vs_actual']],[8,21,28])


if __name__=='__main__':unittest.main()
