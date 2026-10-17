"""N+7: exercise the real continuation CLI/negative branches without authority promotion."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import n3_continuation as continuation

LEDGER = HERE.parent / 'federation-atlas' / 'CBD_GOLDEN_GRAPH_N6_20261017.json'


class ContinuationCLIExtraTests(unittest.TestCase):
    def test_validate_historical_ledger_with_no_output(self):
        with patch.object(sys, 'argv', ['n3_continuation.py', str(LEDGER)]):
            self.assertEqual(continuation.main(), 0)

    def test_validate_and_copy_to_output(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'copy.json'
            with patch.object(sys, 'argv', ['n3_continuation.py', str(LEDGER), '--out', str(path)]):
                self.assertEqual(continuation.main(), 0)
            saved = json.loads(path.read_text())
            self.assertEqual(saved['receipts'][-1]['ordinal'], 6)
            self.assertEqual(saved['authority_transfer'], False)

    def test_record_requires_out(self):
        with tempfile.TemporaryDirectory() as d:
            rec = Path(d) / 'receipt.json'
            rec.write_text('{}')
            with patch.object(sys, 'argv', ['n3_continuation.py', str(LEDGER), '--record', str(rec)]):
                with self.assertRaisesRegex(ValueError, '--out required'):
                    continuation.main()

    def test_record_when_no_slots_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            rec = Path(d) / 'receipt.json'
            rec.write_text('{}')
            target = Path(d) / 'next.json'
            with patch.object(sys, 'argv', ['n3_continuation.py', str(LEDGER), '--record', str(rec), '--out', str(target)]):
                with self.assertRaisesRegex(ValueError, 'no legal next pulse'):
                    continuation.main()
            self.assertFalse(target.exists())

    def test_blocked_receipt_cli_returns_exit_two(self):
        with tempfile.TemporaryDirectory() as d:
            obj = json.loads(LEDGER.read_text())
            obj['receipts'] = obj['receipts'][:1]
            first = obj['receipts'][0]
            obj['receipts'].append({
                'ordinal': 5, 'pulse_id': 'GBOGEB/pipeline-automation-hub::CBD-GOLDEN-GRAPH-604::W-CBD-GRAPH-02::PULSE-5',
                'input_source_sha': first['output_source_sha'],
                'output_source_sha': first['output_source_sha'],
                'prev_receipt_digest': continuation.digest(first),
                'status': 'BLOCKED', 'major_blocker': 'DEPENDENCY_INCOMPLETE',
                'changed_paths': [], 'merge_admission': 'HOLD',
                'security_waiver': False, 'authority_transfer': False,
                'coverage_delta': None, 'tests': {'kind': 'NOT_RUN', 'passed': 0, 'failed': 0},
            })
            source = Path(d) / 'blocked.json'
            out = Path(d) / 'out.json'
            source.write_text(json.dumps(obj))
            with patch.object(sys, 'argv', ['n3_continuation.py', str(source), '--out', str(out)]):
                self.assertEqual(continuation.main(), 2)
            self.assertEqual(json.loads(out.read_text())['receipts'][-1]['status'], 'BLOCKED')

    def test_valid_path_requires_clean_segments(self):
        self.assertFalse(continuation.safe_path('../evil'))
        self.assertFalse(continuation.safe_path('a\\b'))
        self.assertFalse(continuation.safe_path('a//b'))
        self.assertTrue(continuation.safe_path('mission-control/v2/file.py'))

    def test_reject_unsafe_receipt_even_when_sha_matches(self):
        o = json.loads(LEDGER.read_text())
        o['receipts'][0]['security_waiver'] = True
        with self.assertRaisesRegex(ValueError, 'authority escalation'):
            continuation.validate(o)


if __name__ == '__main__':
    unittest.main()
