"""W5 stdlib tests: retained cohorts, nulls, disjoint budgets and next-epoch DAG.

All test receipts are synthetic LOCAL_TEST fixtures, not provider attestations.
Collected by the existing unittest-based native workflow, without dependencies.
"""
import contextlib
import copy
import io
import itertools
import json
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from metric_atlas import census as c
from test_census import H, good_receipt


class CensusW5Tests(unittest.TestCase):
    def test_deferred_known_heads_are_not_lost(self):
        r = c.rollup(c.request('W5', H, max_fanout=1), [])
        self.assertEqual((len(r['lanes']), r['eligible_repos']), (3, 3))

    def test_absent_evidence_is_unknown(self):
        r = c.rollup(c.request('W5', H), [])
        self.assertTrue(all(x.get('route_failure') is None for x in r['lanes']))

    def test_boolean_fanout_rejected(self):
        with self.assertRaises(c.CensusError):
            c.request('W5', H, max_fanout=True)

    def test_feedback_targets_next_epoch(self):
        self.assertNotIn('I --> A', c.dag_mermaid())
        self.assertIn('NEXT', c.dag_mermaid())
        self.assertIn('not dispatched', c.dag_mermaid())

    def test_nonobject_receipt_and_wrong_manifest(self):
        with self.assertRaises(c.CensusError):
            c.validate_receipt([], c.request('W5', H))
        with self.assertRaises(c.CensusError):
            c.rollup({'schema': 'wrong'}, [])

    def test_selector_restricts_route(self):
        m = c.request('W5', H, selector='native_checks')
        with self.assertRaises(c.CensusError):
            c.validate_receipt(good_receipt(m, route='coverage_catalog'), m)
        r = c.rollup(m, [good_receipt(m)])
        self.assertEqual(r['fully_observed_repos'], 1)
        self.assertIs(r['lanes'][0]['route_failure'], False)

    def test_deferred_route_still_required(self):
        m = c.request('W5', H, selector='coverage_catalog', max_fanout=1)
        r = c.rollup(m, [])
        self.assertEqual(r['lanes'][1]['routes_required'], ['coverage_catalog'])
        self.assertEqual(r['lanes'][1]['head_sha'], H['CODEX'])
        with self.assertRaises(c.CensusError):
            c.validate_receipt(good_receipt(c.request('W5', H), lane=1), m)

    def test_failure_keeps_other_lanes_unknown(self):
        m = c.request('W5', H)
        r = c.rollup(m, [dict(good_receipt(m), outcome='FAILURE')])
        self.assertIs(r['lanes'][0]['route_failure'], True)
        self.assertIsNone(r['lanes'][1]['route_failure'])
        self.assertEqual(r['fully_observed_repos'], 0)

    def test_native_counts_do_not_promote(self):
        m = c.request('W5', H)
        r = good_receipt(m)
        r.update(evidence_class='NATIVE_TEST_COUNTS_WITH_LOG_RECEIPT',
                 tests={'executed': 4, 'passed': 2, 'failed': 1, 'skipped': 1},
                 test_log_url='https://example.test/synthetic-only',
                 scope_fingerprint='FIXTURE',
                 coverage={'statements': 10, 'covered_statements': 6,
                           'branches': 4, 'covered_branches': 3,
                           'scope_fingerprint': 'FIXTURE', 'artifact_sha256': 'd'*64})
        c.validate_receipt(r, m)
        result = c.rollup(m, [r])
        self.assertIsNone(result['tests_executed'])
        self.assertIsNone(result['coverage_scope_matched_uplift'])
        self.assertIs(result['engineering_acceptance'], False)

    def test_statement_only_coverage(self):
        m = c.request('W5', H)
        r = good_receipt(m)
        r.update(evidence_class='NATIVE_TEST_COUNTS_WITH_LOG_RECEIPT',
                 coverage={'statements': 10, 'covered_statements': 6,
                           'scope_fingerprint': 'FIXTURE', 'artifact_sha256': 'd'*64})
        self.assertEqual(c.validate_receipt(r, m)['repo'], 'GBOGEB/ABACUS')
        self.assertIsNone(c.rollup(m, [r])['coverage_scope_matched_uplift'])

    def test_independent_attempts(self):
        m = c.request('W5', H)
        a = good_receipt(m)
        b = dict(a, run_attempt=2)
        r = c.rollup(m, [a, a, b, b])
        self.assertEqual((r['native_job_receipts'], r['run_attempts']), (2, 2))

    def test_cli_all_routes(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()) as stdout:
            p = Path(tmp)
            (p/'heads.json').write_text(json.dumps(H))
            m = p/'output/request.json'
            c.main(['request', '--wave', 'W5', '--heads', str(p/'heads.json'),
                    '--max-fanout', '1', '--output', str(m)])
            self.assertEqual(json.loads(m.read_text())['max_fanout'], 1)
            (p/'receipts.json').write_text('[]')
            r = p/'output/rollup.json'
            c.main(['rollup', '--manifest', str(m), '--receipts', str(p/'receipts.json'), '--output', str(r)])
            self.assertEqual(json.loads(r.read_text())['represented_repos'], 3)
            c.main(['diagrams', '--output', str(p/'graphs')])
            self.assertIn('NEXT', (p/'graphs/QPS_CENSUS_DAG.mmd').read_text())
            self.assertIn('Suppliers', (p/'graphs/QPS_CENSUS_SIPOC.mmd').read_text())
            self.assertIn('DIAGRAMS_WRITTEN', stdout.getvalue())

    def test_cli_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()) as stderr:
            with self.assertRaises(SystemExit) as e:
                c.main(['request', '--wave', 'W5', '--heads', str(Path(tmp)/'missing'), '--output', str(Path(tmp)/'out')])
            self.assertEqual(e.exception.code, 2)
            self.assertIn('CENSUS_HOLD', stderr.getvalue())

    def test_main_entrypoint(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            with patch.object(sys, 'argv', ['census', 'diagrams', '--output', tmp]):
                runpy.run_path(c.__file__, run_name='__main__')
            self.assertTrue((Path(tmp)/'QPS_CENSUS_DAG.mmd').is_file())


def availability_case(budget, available):
    def test(self):
        heads = {k: H[k] if yes else None for k, yes in zip(H, available)}
        r = c.rollup(c.request('W5-SCALE', heads, max_fanout=budget), [])
        self.assertEqual((len(r['lanes']), r['eligible_repos'], r['represented_repos']), (3, 3, 3))
        self.assertEqual(r['planned_repos'], min(sum(available), budget))
        self.assertEqual(r['deferred_repos'], max(0, sum(available)-budget))
        self.assertEqual(r['unknown_head_repos'], 3-sum(available))
        self.assertEqual(len({x['repo'] for x in r['lanes']}), 3)
        self.assertTrue(all(x['complete'] is False and x['route_failure'] is None for x in r['lanes']))
        self.assertEqual(r['observed_repos'], 0)
        self.assertIsNone(r['tests_executed'])
    return test


def request_error_case(kind, value):
    def test(self):
        args = {'wave': 'W5', 'heads': H, 'max_fanout': 3}
        args[kind] = value
        with self.assertRaises(c.CensusError):
            c.request(**args)
    return test


def receipt_error_case(mutation):
    def test(self):
        m = c.request('W5', H)
        r = good_receipt(m)
        r.update(copy.deepcopy(mutation))
        with self.assertRaises(c.CensusError):
            c.validate_receipt(r, m)
    return test


def cli_error_case(content):
    def test(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
            p = Path(tmp)
            (p/'heads.json').write_text(content)
            with self.assertRaises(SystemExit) as e:
                c.main(['request', '--wave', 'W5', '--heads', str(p/'heads.json'), '--output', str(p/'out')])
            self.assertEqual(e.exception.code, 2)
    return test


for _budget in (1, 2, 3):
    for _bits in itertools.product((False, True), repeat=3):
        _tag = ''.join(str(int(x)) for x in _bits)
        setattr(CensusW5Tests, 'test_scale_%s_%s' % (_budget, _tag), availability_case(_budget, _bits))
for _kind, _values in (
    ('wave', ['', '../other', None, 'x'*65, 99]),
    ('max_fanout', [False, True, 0, 4, 1.5, None, '2']),
    ('heads', [None, [], 'ABACUS', {}, dict(H, CODEX=False)]),
):
    for _i, _value in enumerate(_values):
        setattr(CensusW5Tests, 'test_reject_%s_%02d' % (_kind, _i), request_error_case(_kind, _value))
for _i, _mutation in enumerate([
    {'schema': 'wrong'}, {'request_id': 'bad'}, {'repo': 'GBOGEB/OTHER'},
    {'lane': 'BAD'}, {'route': 'shell'}, {'run_id': True}, {'run_attempt': 0},
    {'execution_sha': None}, {'execution_sha': 'short'}, {'authority_transfer': True},
    {'outcome': 'PENDING'}, {'tests': None}, {'coverage': []}, {'tests': {'executed': 1}},
    {'evidence_class': 'NATIVE_TEST_COUNTS_WITH_LOG_RECEIPT', 'tests': {'executed': 1}},
    {'evidence_class': 'NATIVE_TEST_COUNTS_WITH_LOG_RECEIPT', 'tests': {'executed': 2, 'passed': 1, 'failed': 0, 'skipped': 0}},
    {'evidence_class': 'NATIVE_TEST_COUNTS_WITH_LOG_RECEIPT', 'tests': {'executed': 1, 'passed': 1, 'failed': 0, 'skipped': 0}},
    {'coverage': {'statements': 10, 'covered_statements': 5}},
    {'evidence_class': 'NATIVE_TEST_COUNTS_WITH_LOG_RECEIPT', 'coverage': {'statements': 10, 'covered_statements': 5}},
    {'evidence_class': 'NATIVE_TEST_COUNTS_WITH_LOG_RECEIPT', 'coverage': {'statements': 10, 'covered_statements': 11, 'scope_fingerprint': 'FIXTURE', 'artifact_sha256': 'd'*64}},
]):
    setattr(CensusW5Tests, 'test_receipt_reject_%02d' % _i, receipt_error_case(_mutation))
for _i, _content in enumerate(['[]', '{"BAD":"short"}', '{broken']):
    setattr(CensusW5Tests, 'test_cli_reject_%02d' % _i, cli_error_case(_content))


if __name__ == '__main__':
    unittest.main()
