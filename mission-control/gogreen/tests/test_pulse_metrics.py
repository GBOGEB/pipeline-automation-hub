"""G3 fail-closed measured pulse and denominator comparability tests."""
import importlib.util,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('pulse_metrics',ROOT/'pulse_metrics.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
SHA='f'*40

def fixture():
    cov={'meta':{'branch_coverage':True,'version':'7.13.3'},
         'files':{'mission-control/gogreen/spine.py':{'summary':{
            'num_statements':10,'covered_lines':8,'num_branches':6,'covered_branches':4}},
         'mission-control/gogreen/tests/test_ignored.py':{'summary':{
            'num_statements':100,'covered_lines':100,'num_branches':2,'covered_branches':2}}}}
    return json.dumps(cov).encode(),b'Ran 12 tests in 0.01s\n\nOK\n'

def report(cov=None,log=None,comparison=None):
    c,l=fixture()
    return p.produce(cov if cov is not None else c,log if log is not None else l,
                     'GBOGEB/pipeline-automation-hub',SHA,SHA,'G2-P1',comparison)

class PulseReceiptTests(unittest.TestCase):
    def test_actual_production_denominator_and_no_admission(self):
        x=report()
        self.assertEqual({'executed':12,'passed':12,'failed':0,'skipped':0},x['tests'])
        self.assertEqual(12,x['coverage']['combined_covered'])
        self.assertEqual(16,x['coverage']['combined_eligible'])
        self.assertEqual(75.0,x['coverage']['combined_percent'])
        self.assertIsNone(x['real_child_capacity'])
        self.assertFalse(x['merge_authorized'])
        self.assertEqual('DEFER',x['child_acceptance'])

    def test_matched_baseline_delta(self):
        baseline=report()
        cov=json.loads(fixture()[0])
        cov['files']['mission-control/gogreen/spine.py']['summary']['covered_lines']=9
        cur=report(json.dumps(cov).encode(),comparison=baseline)
        self.assertEqual('MATCHED_SCOPE',cur['comparability'])
        self.assertEqual(6.25,cur['comparable_delta_pp'])

    def test_different_denominator_does_not_produce_fake_delta(self):
        baseline=report();cov=json.loads(fixture()[0])
        cov['files']['mission-control/gogreen/spine.py']['summary']['num_statements']=11
        x=report(json.dumps(cov).encode(),comparison=baseline)
        self.assertEqual('INCOMPARABLE_SCOPE_OR_TOOL',x['comparability'])
        self.assertIsNone(x['comparable_delta_pp'])

    def test_tool_version_change_not_comparable(self):
        baseline=report();cov=json.loads(fixture()[0]);cov['meta']['version']='7.12.0'
        x=report(json.dumps(cov).encode(),comparison=baseline)
        self.assertIsNone(x['comparable_delta_pp'])

    def test_missing_branch_mode(self):
        cov=json.loads(fixture()[0]);cov['meta']['branch_coverage']=False
        with self.assertRaisesRegex(ValueError,'branch mode'):report(json.dumps(cov).encode())

    def test_invalid_test_counts_or_missing_terminal_success(self):
        for log in [b'Ran 0 tests in 0.01s\nOK\n',
                    b'Ran 3 tests in 0.01s\nFAILED (failures=1)\n',
                    b'Ran 2 tests in 0.02s\nRan 2 tests in 0.02s\nOK\n',
                    b'Ran 2 tests in 0.02s\nOK (skipped=2)\n']:
            with self.subTest(log=log),self.assertRaises(ValueError):report(log=log)

    def test_skips_are_not_counted_as_passes(self):
        x=report(log=b'Ran 12 tests in 0.01s\nOK (skipped=2)\n')
        self.assertEqual(10,x['tests']['passed'])
        self.assertEqual(2,x['tests']['skipped'])

    def test_source_mismatch_and_boolean_denominator_rejected(self):
        c,l=fixture()
        with self.assertRaisesRegex(ValueError,'provenance'):
            p.produce(c,l,'GBOGEB/pipeline-automation-hub',SHA,'0'*40,'G2-P1')
        cov=json.loads(c)
        cov['files']['mission-control/gogreen/spine.py']['summary']['num_statements']=True
        with self.assertRaisesRegex(ValueError,'coverage count'):report(json.dumps(cov).encode())

    def test_no_production_source_is_error(self):
        cov=json.loads(fixture()[0]);cov['files']={'tests/test_only.py':{'summary':{}}}
        with self.assertRaisesRegex(ValueError,'no production files'):report(json.dumps(cov).encode())

    def test_zero_or_missing_eligible_counts_rejected(self):
        cov=json.loads(fixture()[0])
        cov['files']['mission-control/gogreen/spine.py']['summary']['num_statements']=0
        with self.assertRaisesRegex(ValueError,'incoherent'):report(json.dumps(cov).encode())

    def test_foreign_root_fragment_rejected(self):
        cov=json.loads(fixture()[0])
        rec=cov['files'].pop('mission-control/gogreen/spine.py')
        cov['files']['unrelated/mission-control/gogreen/spine.py']=rec
        with self.assertRaisesRegex(ValueError,'ambiguous coverage production path'):
            report(json.dumps(cov).encode())

    def test_parent_traversal_production_alias_rejected(self):
        cov=json.loads(fixture()[0])
        rec=cov['files'].pop('mission-control/gogreen/spine.py')
        cov['files']['mission-control/gogreen/../gogreen/spine.py']=rec
        with self.assertRaisesRegex(ValueError,'ambiguous coverage production path'):
            report(json.dumps(cov).encode())

    def test_valid_control_scope_still_matched(self):
        baseline=report()
        current=report(comparison=baseline)
        self.assertEqual('MATCHED_SCOPE',current['comparability'])
        self.assertEqual(0,current['comparable_delta_pp'])

    def test_forged_baseline_aggregate_rejected(self):
        baseline=report()
        baseline['coverage']['combined_covered']=16
        with self.assertRaisesRegex(ValueError,'baseline coverage integrity: aggregate mismatch'):
            report(comparison=baseline)

    def test_forged_baseline_percent_rejected(self):
        baseline=report()
        baseline['coverage']['combined_percent']=99.0
        with self.assertRaisesRegex(ValueError,'baseline coverage integrity: aggregate mismatch'):
            report(comparison=baseline)

    def test_baseline_authority_forgery_rejected(self):
        baseline=report()
        baseline['merge_authorized']=True
        with self.assertRaisesRegex(ValueError,'baseline coverage integrity: provenance or authority'):
            report(comparison=baseline)

    def test_baseline_negative_numerator_rejected(self):
        baseline=report()
        baseline['coverage']['production_modules']['mission-control/gogreen/spine.py']['covered_lines']=-1
        with self.assertRaisesRegex(ValueError,'baseline coverage integrity: invalid module count'):
            report(comparison=baseline)

    def test_changed_scope_remains_incomparable(self):
        baseline=report()
        cov=json.loads(fixture()[0])
        cov['files']['mission-control/gogreen/spine.py']['summary']['num_branches']=7
        receipt=report(json.dumps(cov).encode(),comparison=baseline)
        self.assertEqual('INCOMPARABLE_SCOPE_OR_TOOL',receipt['comparability'])
        self.assertIsNone(receipt['comparable_delta_pp'])


    def test_zero_statement_and_branch_debt_is_visible_without_waiver(self):
        cov=json.loads(fixture()[0])
        rec=cov['files']['mission-control/gogreen/spine.py']['summary']
        rec['covered_lines']=0
        rec['covered_branches']=0
        out=report(json.dumps(cov).encode())
        debt=out['coverage']
        self.assertEqual(['mission-control/gogreen/spine.py'],debt['zero_statement_modules'])
        self.assertEqual(['mission-control/gogreen/spine.py'],debt['zero_branch_modules'])
        self.assertEqual(0,debt['nonzero_statement_modules'])
        self.assertEqual('FAIL',debt['measured_zero_gate'])
        self.assertEqual('COVERAGE_JSON_REPORTED_ONLY',debt['inventory_scope'])
        self.assertFalse(out['merge_authorized'])

    def test_branchless_nonzero_statement_module_is_not_zero_branch_debt(self):
        cov=json.loads(fixture()[0])
        cov['files']['mission-control/gogreen/branchless.py']={'summary':{
            'num_statements':2,'covered_lines':1,
            'num_branches':0,'covered_branches':0}}
        out=report(json.dumps(cov).encode())
        self.assertEqual([],out['coverage']['zero_statement_modules'])
        self.assertEqual([],out['coverage']['zero_branch_modules'])
        self.assertEqual(2,out['coverage']['nonzero_statement_modules'])
        self.assertEqual('PASS_MEASURED_COHORT_ONLY',out['coverage']['measured_zero_gate'])

    def test_zero_debt_reduction_only_when_scope_matches(self):
        old=json.loads(fixture()[0])
        s=old['files']['mission-control/gogreen/spine.py']['summary']
        s['covered_lines']=s['covered_branches']=0
        baseline=report(json.dumps(old).encode())
        new=report(comparison=baseline)
        self.assertEqual('MATCHED_SCOPE',new['comparability'])
        self.assertEqual(-1,new['comparable_zero_statement_delta'])
        self.assertEqual(-1,new['comparable_zero_branch_delta'])
        self.assertEqual([],new['coverage']['zero_statement_modules'])

    def test_changed_denominator_never_claims_zero_debt_gain(self):
        old=json.loads(fixture()[0])
        s=old['files']['mission-control/gogreen/spine.py']['summary']
        s['covered_lines']=s['covered_branches']=0
        baseline=report(json.dumps(old).encode())
        now=json.loads(fixture()[0])
        now['files']['mission-control/gogreen/spine.py']['summary']['num_statements']=11
        new=report(json.dumps(now).encode(),comparison=baseline)
        self.assertEqual('INCOMPARABLE_SCOPE_OR_TOOL',new['comparability'])
        self.assertIsNone(new['comparable_zero_statement_delta'])
        self.assertIsNone(new['comparable_zero_branch_delta'])
