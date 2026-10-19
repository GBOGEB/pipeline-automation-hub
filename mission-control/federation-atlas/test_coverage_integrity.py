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

    def test_cli_build_then_verify_exact_head(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(ci.main(['--source',str(ci.SOURCE),'--out',t,'--head',HEAD]),0)
            self.assertEqual(ci.main(['--source',str(ci.SOURCE),'--out',t,'--head',HEAD,'--verify-only']),0)

    def test_missing_output_requires_declared_local_path(self):
        with self.assertRaisesRegex(ValueError,'OUTPUT_REQUIRED'):
            ci.build(ci.SOURCE, None, HEAD)

    def test_bad_input_contract_families_are_independent(self):
        cases = [
            ('schema', 'SCHEMA_DRIFT', lambda d: d.__setitem__('schema','wrong')),
            ('head','INVALID_REPO_HEAD', lambda d: d['repo_heads'].__setitem__('GBOGEB/ABACUS','bad')),
            ('empty_events','NO_HISTORICAL_OBSERVATIONS',lambda d: d.__setitem__('observations',[])),
            ('dupe_event','DUPLICATE_OBSERVATION',lambda d: d['observations'].append(copy.deepcopy(d['observations'][0]))),
            ('event_sha','INVALID_MEASUREMENT_HEAD', lambda d: d['observations'][0].__setitem__('head_sha','bad')),
            ('event_class','UNSUPPORTED_MEASUREMENT_STATE',lambda d: d['observations'][0].__setitem__('cohort_type','LIVE')),
            ('unbound','UNBOUND_POPULATION',lambda d: d['observations'][0].__setitem__('population_key','')),
            ('missing_rows','MISSING_FILE_ROWS',lambda d: d['observations'][0].__setitem__('rows',[])),
            ('blob','MISSING_GIT_BLOB',lambda d: d['observations'][0]['rows'][0].__setitem__('source_blob','x')),
            ('job_id','MISSING_NATIVE_ID',lambda d: d['observations'][0]['lineage'].__setitem__('job_id',0)),
            ('inventory_head','INVENTORY_HEAD',lambda d: d['inventory_projections'][0].__setitem__('head_sha','bad')),
            ('inventory_dupe','INVALID_INVENTORY',lambda d: d['inventory_projections'][0]['candidate_source_paths'].append(d['inventory_projections'][0]['candidate_source_paths'][0])),
            ('other_shape','INVALID_OTHER_SCOPE',lambda d: d['other_scopes'][0].__setitem__('statement',[1])),
            ('other_counter','INVALID_OTHER_SCOPE_DENOMINATOR',lambda d: d['other_scopes'][0].__setitem__('statement',[100,5])),
            ('statement_over','COVERED_EXCEEDS_ELIGIBLE',lambda d: d['observations'][0]['rows'][0].__setitem__('statement',[100000,1])),
        ]
        for label, expected, modify in cases:
            with self.subTest(label=label):
                source = copy.deepcopy(self.doc)
                modify(source)
                with self.assertRaisesRegex(ValueError,expected):
                    ci.validate(source)

    def test_zero_eligible_population_is_not_100_percent(self):
        obs=copy.deepcopy(self.doc['observations'][0])
        for row in obs['rows']: row['statement']=[0,0]
        with self.assertRaisesRegex(ValueError,'NO_ELIGIBLE'):
            ci.measure(obs)
        self.assertIsNone(ci.ratio(0,0))

    def test_mismatched_test_runtime_and_source_sets_split_cohort(self):
        first,second=copy.deepcopy(self.doc['observations'])
        second['python']='3.12'
        self.assertEqual(ci.compare(first,second)['reason'],'COHORT_METADATA_DRIFT')
        second['python']=first['python']
        second['rows'].pop()
        self.assertEqual(ci.compare(first,second)['reason'],'SOURCE_FILE_SET_DRIFT')

    def test_expected_historical_pair_cannot_change_silently(self):
        payload=copy.deepcopy(self.doc)
        payload['observations'][1]['rows'][0]['source_blob']='a'*40
        with self.assertRaisesRegex(ValueError,'EXPECTED_HISTORICAL_PAIR'):
            ci.summarize(payload)

    def test_render_manifest_provenance_drift(self):
        with tempfile.TemporaryDirectory() as t:
            ci.build(ci.SOURCE,t,HEAD)
            path=Path(t,'manifest.json')
            m=json.loads(path.read_text())
            m['merge_admission']='PASS'
            path.write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,'MANIFEST_PROVENANCE'):
                ci.verify(t,HEAD)

    def test_forged_portfolio_coverage_rejected_even_with_resealed_member(self):
        import hashlib
        with tempfile.TemporaryDirectory() as t:
            ci.build(ci.SOURCE,t,HEAD)
            p=Path(t,'snapshot.json');doc=json.loads(p.read_text());doc['portfolio_total_coverage']=100
            raw=json.dumps(doc).encode();p.write_bytes(raw)
            mpath=Path(t,'manifest.json');m=json.loads(mpath.read_text())
            m['member_sha256']['snapshot.json']=hashlib.sha256(raw).hexdigest()
            m['member_bytes']['snapshot.json']=len(raw)
            mpath.write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,'PORTFOLIO_OR_AUTHORITY_PROMOTION'):
                ci.verify(t,HEAD)



    def test_historical_inventory_state_remains_noncurrent_and_nonqualified(self):
        d=copy.deepcopy(self.doc)
        d['inventory_projections'][0]['measurement_status']='HISTORICAL_INVENTORY_ONLY'
        ci.validate(d)
        result=ci.summarize(d)
        self.assertIsNone(result['current_inventory']['currently_measured_count'])
        self.assertIsNone(result['portfolio_total_coverage'])

    def test_direct_module_entrypoint_exits_after_writing_receipt(self):
        import contextlib
        import io
        import runpy
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as t:
            args=['coverage_integrity.py','--out',t,'--head',HEAD]
            with patch.object(sys,'argv',args), contextlib.redirect_stdout(io.StringIO()) as output:
                with self.assertRaises(SystemExit) as caught:
                    runpy.run_path(str(HERE/'coverage_integrity.py'),run_name='__main__')
            self.assertEqual(caught.exception.code,0)
            self.assertIn('SOURCE_BOUND_HISTORICAL_VIEW',output.getvalue())
            ci.verify(t,HEAD)


if __name__ == '__main__':
    unittest.main()
