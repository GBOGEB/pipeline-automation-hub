"""Coverage arithmetic, evidence identity and immutable-event behavior."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('atlas_coverage_contract_tests', HERE / 'coverage_contract.py')
coverage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(coverage)
ROOT = HERE.parents[2]


class MetricTests(unittest.TestCase):
    def test_unknown_zero_and_branchless_are_distinct(self):
        self.assertEqual(coverage.metric({}, 'statements')['classification'], 'UNKNOWN')
        zero = coverage.metric({'covered': 0, 'eligible': 5}, 'statements')
        self.assertEqual(zero['classification'], 'ZERO_COVERED')
        self.assertEqual(zero['pct'], 0)
        branchless = coverage.metric({'covered': 0, 'eligible': 0}, 'branches')
        self.assertEqual(branchless['classification'], 'BRANCHLESS_NOT_APPLICABLE')
        self.assertIsNone(branchless['pct'])
        empty = coverage.metric({'covered': 0, 'eligible': 0}, 'statements')
        self.assertEqual(empty['classification'], 'NO_EXECUTABLE_ITEMS')
        self.assertIsNone(empty['pct'])

    def test_invalid_numerators_and_denominators_rejected(self):
        for value in ({'covered': 6, 'eligible': 5}, {'covered': -1, 'eligible': 5},
                      {'covered': True, 'eligible': 5}, {'covered': 1.5, 'eligible': 5},
                      {'covered': 1, 'eligible': None}, {'covered': 0, 'eligible': float('nan')},
                      {'covered': 0, 'eligible': -1}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                coverage.metric(value, 'statements')

    def test_percentage_and_remaining_are_derived_from_integer_counts(self):
        value = coverage.metric({'covered': 763, 'eligible': 852}, 'statements')
        self.assertAlmostEqual(value['pct'], 89.55399061032864)
        self.assertEqual(value['remaining'], 89)


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.source = json.loads((ROOT / coverage.SOURCE).read_bytes())

    def test_attachment_numbers_have_separate_populations_and_no_native_credit(self):
        model = coverage.build_model(ROOT)
        rows = {r['id']: r for r in model['rows']}
        self.assertEqual(rows['QPS_PR2016_10_MODULES']['statements']['covered'], 754)
        self.assertEqual(rows['QPS_PR2017_10_MODULES']['branches']['remaining'], 27)
        self.assertEqual(rows['QPS_PR2014_N6_12_MODULES']['eligible_modules'], 12)
        self.assertEqual(rows['ABACUS_HISTORICAL_BROAD_MAIN']['additional_statements_to_75pct'], 2043)
        self.assertEqual(rows['GG_MATH_W33_FOCUSED']['statements']['pct'], 100)
        self.assertTrue(all(r['comparison_key'] is None for r in rows.values()))
        self.assertTrue(all(not r['independently_verified'] for r in rows.values()))
        self.assertIsNone(model['portfolio']['statement_pct'])
        self.assertEqual(model['portfolio']['qualification'], 'NOT_QUALIFIED')

    def test_later_fifteen_module_inventory_is_not_ten_fifteenths_coverage(self):
        row = next(r for r in coverage.build_model(ROOT)['rows'] if r['id'] == 'QPS_LATER_MAIN_15_INVENTORY')
        self.assertEqual(row['eligible_modules'], 15)
        self.assertIsNone(row['instrumented_modules'])
        self.assertIsNone(row['statements']['covered'])
        self.assertIsNone(row['branches']['pct'])
        self.assertIsNone(row['zero_covered_modules'])
        self.assertFalse(row['inventory_completeness_qualified'])
        self.assertEqual(row['unknown_module_identity_count'], 8)
        self.assertTrue(all(m['statements']['pct'] is None for m in row['modules']))

    def test_reported_match_has_arithmetic_but_no_live_comparison_key(self):
        pair = coverage.build_model(ROOT)['comparisons'][0]
        self.assertEqual(pair['statements']['delta_covered'], 9)
        self.assertAlmostEqual(pair['statements']['delta_pp'], 100 * 9 / 852)
        self.assertEqual(pair['branches']['delta_covered'], 7)
        self.assertAlmostEqual(pair['branches']['delta_pp'], 100 * 7 / 304)
        self.assertFalse(pair['comparable_for_live_series'])
        self.assertFalse(pair['independently_verified'])
        self.assertIn('rounded', pair['rounding_note'])

    def test_breadth_is_not_code_coverage(self):
        row = next(r for r in coverage.build_model(ROOT)['rows'] if r['observation_kind'] == 'FEDERATION_BREADTH')
        self.assertEqual(row['breadth']['observed'], 6)
        self.assertEqual(row['breadth']['eligible'], 42)
        self.assertEqual(row['statements']['classification'], 'NOT_APPLICABLE_BREADTH')
        self.assertIsNone(row['statements']['pct'])
        self.assertEqual(coverage.gate_rows(row), [])

    def test_unknown_inventory_and_behavior_prevent_acceptance_at_full_coverage(self):
        model = coverage.build_model(ROOT)
        row = next(r for r in model['rows'] if r['id'] == 'GG_MATH_W33_FOCUSED')
        gates = coverage.gate_rows(row)
        self.assertTrue(all(g['noncompensating'] for g in gates))
        self.assertTrue(any(g['stage'] == 'INVENTORY' and g['status'] == 'UNKNOWN' for g in gates))
        self.assertTrue(any(g['stage'] == 'BEHAVIORAL_DEPTH' and g['status'] == 'UNKNOWN' for g in gates))
        self.assertEqual(model['merge_admission'], 'HOLD')

    def test_event_payload_changes_are_rejected(self):
        event = copy.deepcopy(self.source['events'][0])
        event['statements']['covered'] += 1
        with self.assertRaises(ValueError):
            coverage.validate_event(event)

    def test_recomputed_hash_cannot_reuse_old_content_bound_event_id(self):
        event = copy.deepcopy(self.source['events'][0])
        old_id = event['event_id']
        payload = {k:v for k,v in event.items() if k not in {'event_id','event_sha256'}}
        payload['statements']['covered'] += 1
        replacement = coverage.seal_event(payload)
        replacement['event_id'] = old_id
        with self.assertRaises(ValueError):
            coverage.validate_event(replacement)

    def test_malformed_test_counts_and_inventory_are_rejected(self):
        for change in ('tests', 'inventory', 'names'):
            with self.subTest(change=change):
                payload = coverage.validate_event(self.source['events'][0])
                if change == 'tests': payload['tests']['passed'] = -1
                elif change == 'inventory': payload['instrumented_modules'] = 11
                else: payload['known_module_names'] *= 2
                with self.assertRaises(ValueError):
                    coverage.validate_event(coverage.seal_event(payload))

    def test_duplicate_source_records_and_false_arithmetic_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for mutation in ('duplicate', 'arithmetic'):
                source = copy.deepcopy(self.source)
                if mutation == 'duplicate': source['events'].append(copy.deepcopy(source['events'][0]))
                else: source['reported_comparisons'][0]['reported_deltas']['statements'] = 10
                Path(tmp, 'source.json').write_text(json.dumps(source), encoding='utf-8')
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    coverage.build_model(Path(tmp), source_path='source.json')

    def test_ordered_history_cannot_remove_change_or_reorder_events(self):
        previous = self.source['events'][:2]
        self.assertEqual(coverage.validate_append_only(previous, self.source['events'])['appended'], 6)
        for current in (previous[:1], list(reversed(previous))):
            with self.subTest(current=current), self.assertRaises(ValueError):
                coverage.validate_append_only(previous, current)
        changed = copy.deepcopy(previous)
        payload = coverage.validate_event(changed[0])
        payload['statements']['covered'] += 1
        changed[0] = coverage.seal_event(payload)
        with self.assertRaises(ValueError):
            coverage.validate_append_only(previous, changed)

    def test_correction_can_append_as_new_event_retaining_original(self):
        old = self.source['events'][:1]
        correction = coverage.validate_event(copy.deepcopy(old[0]))
        correction['logical_id'] += '_CORRECTION'
        correction['supersedes_event_id'] = old[0]['event_id']
        correction['statements']['covered'] += 1
        current = old + [coverage.seal_event(correction)]
        self.assertEqual(coverage.validate_append_only(old, current)['appended'], 1)

    def test_generated_jsonl_is_deterministic_projection_not_persistent_history(self):
        model = coverage.build_model(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            first = coverage.write_outputs(model, tmp)
            before = Path(tmp, 'coverage_burndown.jsonl').read_bytes()
            second = coverage.write_outputs(model, tmp)
            self.assertEqual(first, second)
            self.assertEqual(before, Path(tmp, 'coverage_burndown.jsonl').read_bytes())
            rows = [json.loads(line) for line in before.splitlines()]
            self.assertEqual(len(rows), len(model['rows']))
            self.assertTrue(all('NOT_PERSISTENT_APPEND_LOG' in r['history_authority'] for r in rows))


class NativeComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.event = {'repository':'example/project','family':'core','cohort_id':'stable-population',
                      'eligible_modules':1,'independently_verified':True,'instrumentation_version':'coverage-test-v1',
                      'coverage_policy_id':'policy-v1','statements':{'covered':4,'eligible':5},
                      'branches':{'covered':2,'eligible':3},'changed_lines':{'covered':None,'eligible':None},
                      'native':{'repository':'example/project','head_sha':'a'*40,'run_id':1,'attempt':1,'job_id':2}, 'proof':{}}
        self.put('source_manifest', {'files':{'production.py':'d'*64}})
        self.put('coverage_config', {'policy':'policy-v1'})
        self.put('denominator_manifest', {'statements':5,'branches':3,'changed_lines':None})
        self.receipt()

    def put(self, key, value):
        raw = coverage.canonical(value)
        name = key+'.json'
        (self.root/name).write_bytes(raw)
        self.event['proof'][key] = {'path':name,'sha256':coverage.digest(raw)}

    def receipt(self):
        value = {**self.event['native'],'terminal':True,'executed_steps':3,
                 'coverage':{unit:self.event[unit] for unit in ('statements','branches','changed_lines')},
                 **{key+'_sha256':self.event['proof'][key]['sha256'] for key in ('source_manifest','coverage_config','denominator_manifest')}}
        self.put('native_receipt', value)

    def test_true_proof_bytes_qualify_identity_and_source_changes_split_series(self):
        first = coverage.comparison_key(self.event,self.root)
        self.assertIsNotNone(first)
        self.event['native'].update(head_sha='b'*40,run_id=3,job_id=4)
        self.receipt()
        self.assertEqual(coverage.comparison_key(self.event,self.root), first)
        self.put('source_manifest', {'files':{'production.py':'e'*64}})
        self.receipt()
        self.assertNotEqual(coverage.comparison_key(self.event,self.root), first)

    def test_unverified_flag_or_missing_identity_never_qualifies(self):
        for key in ('verification','native','proof'):
            with self.subTest(key=key):
                event = copy.deepcopy(self.event)
                if key=='verification': event['independently_verified']=False
                elif key=='native': event['native']['head_sha']=None
                else: event['proof'].pop('coverage_config')
                self.assertIsNone(coverage.comparison_key(event,self.root))

    def test_config_and_denominator_change_split_the_key(self):
        original = coverage.comparison_key(self.event,self.root)
        self.put('coverage_config',{'policy':'changed-exclusions'})
        self.receipt()
        changed = coverage.comparison_key(self.event,self.root)
        self.assertNotEqual(original,changed)
        self.event['statements']['eligible']=6
        self.put('denominator_manifest',{'statements':6,'branches':3,'changed_lines':None})
        self.receipt()
        self.assertNotEqual(changed,coverage.comparison_key(self.event,self.root))

    def test_receipt_numerator_cannot_be_substituted(self):
        self.event['statements']['covered']=5
        with self.assertRaises(ValueError): coverage.comparison_key(self.event,self.root)

    def test_tampered_bytes_and_mismatched_denominator_rejected(self):
        (self.root/'coverage_config.json').write_bytes(b'changed')
        with self.assertRaises(ValueError): coverage.comparison_key(self.event,self.root)
        self.put('coverage_config', {'policy':'restored'})
        self.put('denominator_manifest', {'statements':7,'branches':3,'changed_lines':None})
        self.receipt()
        with self.assertRaises(ValueError): coverage.comparison_key(self.event,self.root)

    def test_evidence_path_escape_rejected(self):
        self.event['proof']['source_manifest']['path']='../outside.json'
        with self.assertRaises(ValueError): coverage.comparison_key(self.event,self.root)


if __name__ == '__main__':
    unittest.main()
