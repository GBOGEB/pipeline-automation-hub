"""Additional adversarial checks: reject nonfinite metrics and proof promotion."""
import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import n3_integrity as integ
from n3_continuation import digest

LEDGER = HERE.parent / 'federation-atlas' / 'CBD_GOLDEN_GRAPH_N3_20261017.json'


class IntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads(LEDGER.read_text(encoding='utf-8'))

    def setUp(self):
        self.ledger = copy.deepcopy(self.source)

    def audited(self):
        """Recompute downstream hashes to isolate each semantic negative test."""
        for index in range(1, len(self.ledger["receipts"])):
            self.ledger["receipts"][index]["prev_receipt_digest"] = digest(self.ledger["receipts"][index-1])
        return integ.inspect(self.ledger)

    def test_historical_is_safe_but_unverified(self):
        audit = self.audited()
        self.assertEqual(audit['issue_count'], 0)
        self.assertEqual(audit['pulse_count'], 3)
        self.assertGreater(audit['unknown_count'], 0)
        self.assertFalse(audit['native_proof_promoted'])

    def test_audit_is_deterministic(self):
        self.assertEqual(self.audited(), self.audited())

    def test_duplicate_path_rejected(self):
        paths = self.ledger['receipts'][0]['changed_paths']
        paths.append(paths[0])
        self.assertIn('PULSE-1:DUPLICATE_CHANGED_PATH', self.audited()['issues'])

    def test_nonfinite_delta_rejected(self):
        r = self.ledger['receipts'][0]
        r['coverage_delta'], r['coverage_matched'] = float('nan'), True
        self.assertIn('PULSE-1:INVALID_COVERAGE_DELTA', self.audited()['issues'])

    def test_infinite_delta_rejected(self):
        r = self.ledger['receipts'][0]
        r['coverage_delta'], r['coverage_matched'] = float('inf'), True
        self.assertEqual(self.audited()['issue_count'], 2)

    def test_extreme_coverage_rejected(self):
        r = self.ledger['receipts'][0]
        r['coverage_delta'], r['coverage_matched'] = 175, True
        self.assertIn('PULSE-1:INVALID_COVERAGE_DELTA', self.audited()['issues'])

    def test_matched_missing_denominators(self):
        r = self.ledger['receipts'][0]
        r['coverage_delta'], r['coverage_matched'] = 2, True
        self.assertIn('PULSE-1:COVERAGE_DENOMINATOR_UNBOUND', self.audited()['issues'])

    def test_non_native_evidence_not_proof(self):
        r = self.ledger['receipts'][1]
        r['tests']['kind'] = 'NATIVE_EXACT_HEAD'
        r['tests']['tested_sha'] = r['output_source_sha']
        self.assertIn('PULSE-2:UNBOUND_NATIVE_PROOF', self.audited()['issues'])

    def test_wrong_source_identity(self):
        r = self.ledger['receipts'][0]
        r['source_evidence'] = {'source_sha': 'f' * 40, 'class': 'GITHUB_COMMIT', 'locator': 'x'}
        self.assertIn('PULSE-1:CONTRADICTORY_SOURCE_PROOF', self.audited()['issues'])

    def test_source_claim_unverified_when_no_external_readback(self):
        audit = self.audited()
        self.assertTrue(any('SOURCE_AUTHENTICATION_UNBOUND' in item for item in audit['unknowns']))

    def test_optional_valid_source_evidence(self):
        r = self.ledger['receipts'][0]
        r['source_evidence'] = {'source_sha': r['output_source_sha'], 'class': 'GITHUB_COMMIT', 'locator': 'https://github.com/test'}
        self.assertNotIn('PULSE-1:CONTRADICTORY_SOURCE_PROOF', self.audited()['issues'])

    def test_v1_invalid_admission_still_rejected(self):
        self.ledger['receipts'][0]['merge_admission'] = 'PASS'
        with self.assertRaises(ValueError):
            self.audited()


if __name__ == '__main__':
    unittest.main()
