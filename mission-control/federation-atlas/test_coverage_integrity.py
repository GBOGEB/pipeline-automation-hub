"""Adversarial tests for CODE PURPLE scope-bound historical coverage viewer."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import coverage_integrity as ci

HEAD = '9b9a556b4287889c44cd0d5d3c2ac16b33baea4e'


class CoverageIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads(ci.SOURCE.read_text(encoding='utf-8'))

    def test_exact_source_matched_improvement(self):
        result = ci.summarize(self.doc)
        self.assertEqual(result['comparison']['source_files'], 10)
        self.assertEqual(result['comparison']['statement_delta'], 9)
        self.assertEqual(result['comparison']['branch_delta'], 7)
        self.assertEqual(result['comparison']['state'], 'SOURCE_MATCHED_DIFFERENT_TEST_EXECUTION')
        self.assertEqual(result['comparison']['accepted_gain'], None)
        self.assertEqual(result['observations'][1]['covered_statements'], [763,852])
        self.assertEqual(result['observations'][1]['covered_branches'], [277,304])
        self.assertEqual(result['observations'][1]['zero_statement_files'], [])
        self.assertEqual(result['observations'][1]['minimum_statement_pct'], 70.0)
        self.assertEqual(result['observations'][1]['minimum_branch_pct'], 50.0)

    def test_compensating_regression_is_not_hidden(self):
        changes = {x['file'].split('/')[-1]: x for x in ci.summarize(self.doc)['comparison']['per_file']}
        self.assertEqual((changes['build_dashboard.py']['statement_delta'],changes['build_dashboard.py']['branch_delta']),(-9,-2))
        self.assertEqual((changes['support_bridge.py']['statement_delta'],changes['support_bridge.py']['branch_delta']),(18,9))

    def test_inventory_added_not_falsely_zero(self):
        state = ci.summarize(self.doc)['current_inventory']
        self.assertEqual(state['candidate_file_count'], 15)
        self.assertEqual(state['introduced_count'], 5)
        self.assertIsNone(state['currently_measured_count'])
        self.assertIsNone(state['zero_coverage_count'])
        self.assertIsNone(state['current_main_statement'])

    def test_abacus_fixed_denominator_goal_is_2043_not_3818(self):
        groups = ci.summarize(self.doc)['other_scopes']
        abacus = next(x for x in groups if x['id'] == 'abacus-main-historical')
        self.assertEqual(abacus['same_denominator_remaining_to_75pct'], 2043)

    def test_federation_is_never_summed_as_code_coverage(self):
        result = ci.summarize(self.doc)
        self.assertEqual(result['federation_breadth']['observed_historical'], 6)
        self.assertIsNone(result['federation_breadth']['authenticated_fresh'])
        self.assertIsNone(result['portfolio_total_coverage'])

    def test_missing_file_makes_pair_incomparable(self):
        a,b = copy.deepcopy(self.doc['observations'])
        b['rows'].pop()
        self.assertEqual(ci.compare(a,b)['reason'], 'SOURCE_FILE_SET_DRIFT')

    def test_source_blob_mismatch_blocks_uplift(self):
        a,b = copy.deepcopy(self.doc['observations'])
        b['rows'][0]['source_blob'] = 'b'*40
        self.assertEqual(ci.compare(a,b)['reason'], 'BLOB_OR_ELIGIBLE_DENOMINATOR_DRIFT')

    def test_counter_denominator_drift_blocks_uplift(self):
        a,b = copy.deepcopy(self.doc['observations'])
        b['rows'][0]['statement'][1] += 1
        self.assertEqual(ci.compare(a,b)['state'], 'INCOMPARABLE')

    def test_well_tested_module_cannot_compensate_zero(self):
        a=copy.deepcopy(self.doc['observations'][0])
        a['rows'][0]['statement'][0] = 0
        m=ci.measure(a)
        self.assertEqual(m['measured_zero_gate'],'FAIL')
        self.assertEqual(len(m['zero_statement_files']),1)

    def test_eligible_branch_zero_is_independent_gate(self):
        a=copy.deepcopy(self.doc['observations'][0])
        a['rows'][0]['branch'][0] = 0
        self.assertEqual(ci.measure(a)['measured_zero_gate'],'FAIL')

    def test_empty_branch_denominator_is_na(self):
        a=copy.deepcopy(self.doc['observations'][0])
        for row in a['rows']: row['branch']=[0,0]
        m=ci.measure(a)
        self.assertIsNone(m['minimum_branch_pct'])
        self.assertEqual(m['zero_branch_files'],[])

    def test_bad_boolean_numerator_rejected(self):
        d=copy.deepcopy(self.doc)
        d['observations'][0]['rows'][0]['statement'][0] = True
        with self.assertRaisesRegex(ValueError,'INVALID_COUNTER'):
            ci.validate(d)

    def test_missing_crc_or_fake_artifact_rejected(self):
        d=copy.deepcopy(self.doc)
        d['observations'][0]['lineage']['zip_crc_verified']=False
        with self.assertRaisesRegex(ValueError,'HISTORICAL_ZIP'):
            ci.validate(d)

    def test_fake_canonical_breadth_blocked(self):
        d=copy.deepcopy(self.doc)
        d['federation_breadth']['authenticated_fresh'] = 42
        with self.assertRaisesRegex(ValueError,'FAKE_FEDERATION'):
            ci.validate(d)

    def test_authority_bypass_blocked(self):
        d=copy.deepcopy(self.doc)
        d['authority']['merge_admission']='PASS'
        with self.assertRaisesRegex(ValueError,'FALSE_AUTHORITY'):
            ci.validate(d)

    def test_empty_source_path_and_duplicate_rejected(self):
        d=copy.deepcopy(self.doc)
        d['observations'][0]['rows'][0]['path']='../private.py'
        with self.assertRaisesRegex(ValueError,'UNSAFE_OR_DUPLICATE'):
            ci.validate(d)

    def test_current_main_measurement_cannot_be_invented(self):
        d=copy.deepcopy(self.doc)
        d['inventory_projections'][0]['measured_source_paths'] = ['foo.py']
        with self.assertRaisesRegex(ValueError,'INVENTED_CURRENT'):
            ci.validate(d)

    def test_run_id_and_steps_fail_closed(self):
        d=copy.deepcopy(self.doc)
        d['observations'][0]['lineage']['job_executed_steps']=0
        with self.assertRaisesRegex(ValueError,'HISTORICAL_ZIP'):
            ci.validate(d)

    def test_build_themes_verify_and_tamper(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            manifest=ci.build(ci.SOURCE,root,HEAD)
            self.assertEqual(len(manifest['member_sha256']),7)
            self.assertNotEqual((root/'graph-light.svg').read_bytes(),(root/'graph-dark.svg').read_bytes())
            self.assertEqual((root/'graph-light.svg').read_text().count('data-node='),len(ci.NODES))
            self.assertEqual((root/'graph-dark.svg').read_text().count('data-edge='),len(ci.EDGES))
            html=(root/'index.html').read_text()
            self.assertIn('Appearance',html)
            self.assertIn('Current QPS inventory candidates',html)
            self.assertIn('not current-main coverage',html)
            ci.verify(root,HEAD)
            (root/'graph-dark.svg').write_text('<svg>tampered</svg>')
            with self.assertRaisesRegex(ValueError,'TAMPERED_COVERAGE'):
                ci.verify(root,HEAD)

    def test_bad_publisher_head_fails_closed(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaisesRegex(ValueError,'PUBLISHER_EXACT'):
                ci.build(ci.SOURCE,Path(t),'fake-head')


if __name__ == '__main__':
    unittest.main()
