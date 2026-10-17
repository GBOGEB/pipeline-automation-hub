"""G3A N+10: adversarial CLI, native-boundary and unknown-data tests.

No live authentication or merge admission can be established by synthetic fixtures.
"""
from __future__ import annotations
import contextlib
import copy
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_n3_native_join import fixture
from n3_continuation import digest, validate
import n3_integrity
import n3_metrics
import n3_dashboard
import n3_native_join

LEDGER = HERE.parent / 'federation-atlas' / 'CBD_GOLDEN_GRAPH_N6_20261017.json'


def rechain(obj):
    for i in range(1, len(obj['receipts'])):
        obj['receipts'][i]['prev_receipt_digest'] = digest(obj['receipts'][i-1])
    validate(obj)
    return obj


class NegativeAndCLIExpansion(unittest.TestCase):
    def test_native_cli_output_file(self):
        with tempfile.TemporaryDirectory() as d:
            snapshot = Path(d) / 'source.json'
            target = Path(d) / 'native.json'
            snapshot.write_text(json.dumps(fixture()))
            with patch.object(sys, 'argv', ['n3_native_join.py', str(snapshot), '--out', str(target)]):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertIsNone(n3_native_join.main())
            result = json.loads(target.read_text())
            self.assertEqual(result['observed_jobs'], 1)
            self.assertFalse(result['native_exact_head_authenticated'])

    def test_native_cli_without_output_file(self):
        with tempfile.TemporaryDirectory() as d:
            snapshot = Path(d) / 'source.json'
            snapshot.write_text(json.dumps(fixture()))
            with patch.object(sys, 'argv', ['n3_native_join.py', str(snapshot)]):
                with contextlib.redirect_stdout(io.StringIO()) as out:
                    n3_native_join.main()
            self.assertEqual(json.loads(out.getvalue())['queued_runs'], 1)
            self.assertEqual(sorted(p.name for p in Path(d).iterdir()), ['source.json'])

    def test_native_invalid_calendar_timestamp(self):
        obj = fixture()
        obj['observed_at'] = 'not-an-iso-time'
        with self.assertRaisesRegex(ValueError, 'invalid timestamp'):
            n3_native_join.project(obj)

    def test_native_wrong_job_status(self):
        obj = fixture()
        obj['runs'][0]['jobs'][0]['status'] = 'unknown'
        with self.assertRaisesRegex(ValueError, 'bad native status'):
            n3_native_join.project(obj)

    def test_native_completed_run_without_started_timestamp(self):
        obj = fixture()
        obj['runs'][0]['run_started_at'] = None
        with self.assertRaisesRegex(ValueError, 'completed run without a start'):
            n3_native_join.project(obj)

    def test_native_declared_job_total_boolean_rejected(self):
        obj = fixture()
        obj['runs'][0]['job_total'] = True
        with self.assertRaisesRegex(ValueError, 'invalid job observation denominator'):
            n3_native_join.project(obj)

    def test_native_failed_step_missing_number_rejected(self):
        obj = fixture()
        obj['runs'][0]['jobs'][0]['failed_steps'] = [{'step_name':'pytest'}]
        with self.assertRaisesRegex(ValueError, 'invalid failed-step identity'):
            n3_native_join.project(obj)

    def test_native_failure_steps_only_on_failure(self):
        obj = fixture()
        obj['runs'][0]['jobs'][0]['status'] = 'in_progress'
        obj['runs'][0]['jobs'][0]['conclusion'] = None
        with self.assertRaisesRegex(ValueError, 'failed steps attached to nonfailed job'):
            n3_native_join.project(obj)

    def test_native_queue_job_cannot_pretend_completed(self):
        obj = fixture()
        obj['runs'][1]['jobs'].append(copy.deepcopy(obj['runs'][0]['jobs'][0]))
        obj['runs'][1]['job_total'] = 1
        with self.assertRaisesRegex(ValueError, 'duplicate/invalid native job ID'):
            n3_native_join.project(obj)

    def test_native_valid_timezone_offsets(self):
        obj = fixture()
        obj['observed_at'] = '2026-10-17T14:00:00+02:00'
        self.assertEqual(n3_native_join.project(obj)['observed_runs'], 2)

    def test_integrity_cli_without_out(self):
        with patch.object(sys,'argv',['n3_integrity.py',str(LEDGER)]):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(n3_integrity.main(),0)
        self.assertEqual(json.loads(out.getvalue())['structural_status'],'PASS_WITH_UNKNOWNS')

    def test_integrity_valid_native_shaped_proof_not_promoted(self):
        obj = json.loads(LEDGER.read_text())
        r = obj['receipts'][1]
        r['tests'] = {'kind':'NATIVE_EXACT_HEAD','passed':46,'failed':0,
                      'tested_sha':r['output_source_sha'],
                      'native_evidence':{'workflow_run_id':39029603161,'run_attempt':1,
                                         'artifact_sha256':'a'*64}}
        rechain(obj)
        audit=n3_integrity.inspect(obj)
        self.assertEqual(audit['issue_count'],0)
        self.assertFalse(audit['native_proof_promoted'])

    def test_planned_and_clock_fields_are_not_native_attestation(self):
        obj = json.loads(LEDGER.read_text())
        obj['receipts'][0]['planned']={'prediction':'local test count>=20'}
        obj['receipts'][0]['clock']={'kind':'UNVERIFIED'}
        rechain(obj)
        audit=n3_integrity.inspect(obj)
        self.assertEqual(audit['unknown_count'],4)
        self.assertFalse(audit['native_proof_promoted'])

    def test_metrics_cli_without_out(self):
        with patch.object(sys,'argv',['n3_metrics.py',str(LEDGER)]):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertIsNone(n3_metrics.main())
        self.assertEqual(json.loads(out.getvalue())['pulse_receipts'],3)

    def test_dashboard_cli_no_metrics_file(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'index.html'
            with patch.object(sys,'argv',['n3_dashboard.py',str(LEDGER),'--html',str(target)]):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertIsNone(n3_dashboard.main())
            self.assertIn('UNKNOWN',target.read_text())
            self.assertEqual(sorted(p.name for p in Path(d).iterdir()),['index.html'])

    def test_invalid_boolean_passed_count(self):
        obj=json.loads(LEDGER.read_text())
        obj['receipts'][0]['tests']['passed']=True
        with self.assertRaises(ValueError):
            validate(obj)


if __name__=='__main__':
    unittest.main()
