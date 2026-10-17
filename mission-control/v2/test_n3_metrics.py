"""Telemetry test: never convert UNKNOWN into zero or invent an improvement."""
import copy
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from n3_continuation import digest
from n3_metrics import collect, ratio

LEDGER = HERE.parent / 'federation-atlas' / 'CBD_GOLDEN_GRAPH_N3_20261017.json'


class MetricsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = json.loads(LEDGER.read_text(encoding='utf-8'))

    def setUp(self):
        self.ledger = copy.deepcopy(self.original)

    def rechain(self):
        for i in range(1, len(self.ledger['receipts'])):
            self.ledger['receipts'][i]['prev_receipt_digest'] = digest(self.ledger['receipts'][i-1])

    def test_declared_test_denominators(self):
        m = collect(self.ledger)['metrics']
        self.assertEqual(m['pulse_receipts'], 3)
        self.assertEqual(m['local_test_receipts']['numerator'], 1)
        self.assertEqual(m['locally_reported_test_passes'], 24)
        self.assertEqual(m['measurement_completeness'], ratio(0, 9))
        self.assertEqual(m['declared_changed_paths_sum'], 5)

    def test_no_fabricated_admission(self):
        o = collect(self.ledger)
        self.assertEqual(o['merge_admission'], 'HOLD')
        self.assertEqual(o['metrics']['native_attested_receipts']['numerator'], 0)
        self.assertIsNone(o['metrics']['matched_code_coverage_improvement_pp'])
        self.assertIsNone(o['metrics']['time_saved_ms'])
        self.assertIsNone(o['metrics']['backlog_burndown'])

    def test_reproducible_and_immutable(self):
        before = copy.deepcopy(self.ledger)
        self.assertEqual(collect(self.ledger), collect(self.ledger))
        self.assertEqual(before, self.ledger)

    def test_empty_ledger_denominator(self):
        self.ledger['receipts'] = []
        m = collect(self.ledger)['metrics']
        self.assertEqual(m['measurement_completeness'], ratio(0, 0))
        self.assertIsNone(m['measurement_completeness']['fraction'])

    def test_invalid_coverage_fails(self):
        self.ledger['receipts'][2]['coverage_delta'] = float('inf')
        self.ledger['receipts'][2]['coverage_matched'] = True
        with self.assertRaises(ValueError):
            collect(self.ledger)

    def test_source_claims_are_not_authentication(self):
        m = collect(self.ledger)['metrics']
        self.assertEqual(m['source_sha_claims'], 3)
        self.assertEqual(m['authenticated_source_receipts']['numerator'], 0)

    def test_external_source_claim_not_auto_attested(self):
        r = self.ledger['receipts'][2]
        r['source_evidence'] = {'source_sha':r['output_source_sha'], 'class':'GITHUB_COMMIT',
                                'locator':'https://github.com/example'}
        self.rechain()
        self.assertEqual(collect(self.ledger)['metrics']['authenticated_source_receipts']['numerator'], 0)

    def test_ratio_guard(self):
        self.assertEqual(ratio(3, 6)['fraction'], 0.5)
        self.assertIsNone(ratio(0, 0)['fraction'])

    def test_no_stats_pseudoreplication(self):
        o = collect(self.ledger)
        self.assertIsNone(o['metrics']['independent_trials'])
        self.assertEqual(o['statistical_inference'], 'DEFER_NO_INDEPENDENT_COMPARABLE_TRIALS')

    def test_full_unknown_inventory(self):
        m = collect(self.ledger)['metrics']
        self.assertEqual(m['unknown_evidence_fields'], 9)


if __name__ == '__main__':
    unittest.main()
