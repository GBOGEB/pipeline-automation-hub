import unittest

from temporal_effect_diagnostics import build_diagnostics
from temporal_pca_alignment import align_receipts


class TemporalEffectDiagnosticsTests(unittest.TestCase):
    def test_attenuation_without_reversal(self):
        receipt = {
            'source_sha': 'a' * 40,
            'mission_id': 'm',
            'competency_promotions': 0,
            'authority_transfer': False,
            'policies': {
                'short_compute': self.policy('short_compute', [0.60, 0.62, 0.64]),
                'long_compute_contended': self.policy('long_compute_contended', [0.20, 0.24, 0.32, 0.40]),
            },
        }
        cfg = {'control_policy_gate': {'min_pooled_winner_strength': 0.70}}
        row = build_diagnostics(receipt, cfg)['diagnostics']['long_compute_contended']
        self.assertEqual(row['effect_direction'], 'ALLOC_PAIRED_CELL')
        self.assertEqual(row['latest_cumulative_transition'], 'ATTENUATING_TOWARD_PARITY')
        self.assertFalse(row['aggregate_direction_reversed_since_previous_pulse'])
        self.assertLess(row['signed_pooled_effect'], 0.0)
        self.assertFalse(row['pca_policy_relation']['pca_polarity_enters_control_gate'])

    def test_reversal_detected(self):
        receipt = {
            'source_sha': 'a' * 40,
            'mission_id': 'm',
            'competency_promotions': 0,
            'authority_transfer': False,
            'policies': {
                'short_compute': self.policy('short_compute', [0.6, 0.65]),
                'long_compute_contended': self.policy('long_compute_contended', [0.4, 0.4, 0.9]),
            },
        }
        cfg = {'control_policy_gate': {'min_pooled_winner_strength': 0.70}}
        row = build_diagnostics(receipt, cfg)['diagnostics']['long_compute_contended']
        self.assertEqual(row['latest_cumulative_transition'], 'AGGREGATE_DIRECTION_REVERSAL')
        self.assertTrue(row['aggregate_direction_reversed_since_previous_pulse'])

    def test_authority_invariants_fail_closed(self):
        receipt = {'competency_promotions': 1, 'authority_transfer': False, 'policies': {}}
        cfg = {'control_policy_gate': {'min_pooled_winner_strength': 0.70}}
        with self.assertRaises(ValueError):
            build_diagnostics(receipt, cfg)

    @staticmethod
    def policy(name, strengths):
        records = []
        for i, strength in enumerate(strengths, 1):
            records.append({
                'window_id': str(i),
                'created_at': f'2026-09-{i:02d}T00:00:00Z',
                'single_normalized_strength': strength,
                'observed_pairs': 6,
            })
        pooled = sum(strengths) / len(strengths)
        return {
            'task_class': name,
            'window_evidence': records,
            'control_frontier': {
                'window_ids': [str(i) for i in range(1, len(strengths) + 1)],
                'independent_windows': len(strengths),
                'temporal_span_seconds': 86400.0 * max(0, len(strengths) - 1),
                'pooled_single_strength': pooled,
                'pooled_winner_strength': max(pooled, 1.0 - pooled),
            },
        }


class TemporalPCAAlignmentTests(unittest.TestCase):
    def test_global_sign_flip_is_orientation_only(self):
        ref = self.receipt([
            ('PC1', 3.0, {'a': 0.8, 'b': -0.6}),
            ('PC2', 1.0, {'a': 0.6, 'b': 0.8}),
        ])
        cand = self.receipt([
            ('PC1', 2.9, {'a': -0.8, 'b': 0.6}),
            ('PC2', 0.9, {'a': 0.6, 'b': 0.8}),
        ])
        pc1 = align_receipts(ref, cand, max_components=2)['component_alignment'][0]
        self.assertTrue(pc1['sign_flip_applied'])
        self.assertAlmostEqual(pc1['aligned_tucker_congruence'], 1.0, places=12)
        self.assertEqual(pc1['interpretation'], 'ORIENTATION_ONLY_SIGN_FLIP')

    def test_component_reordering_is_matched(self):
        ref = self.receipt([
            ('PC1', 4.0, {'a': 1.0, 'b': 0.0}),
            ('PC2', 2.0, {'a': 0.0, 'b': 1.0}),
        ])
        cand = self.receipt([
            ('PC1', 4.1, {'a': 0.0, 'b': 1.0}),
            ('PC2', 2.1, {'a': 1.0, 'b': 0.0}),
        ])
        first = align_receipts(ref, cand, max_components=2)['component_alignment'][0]
        self.assertEqual(first['candidate_component'], 'PC2')
        self.assertTrue(first['component_reordered'])
        self.assertAlmostEqual(abs(first['raw_tucker_congruence']), 1.0, places=12)

    def test_small_eigengap_flags_identity_ambiguity(self):
        ref = self.receipt([
            ('PC1', 2.00, {'a': 1.0, 'b': 0.0}),
            ('PC2', 1.98, {'a': 0.0, 'b': 1.0}),
        ])
        cand = self.receipt([
            ('PC1', 2.01, {'a': 1.0, 'b': 0.0}),
            ('PC2', 1.99, {'a': 0.0, 'b': 1.0}),
        ])
        first = align_receipts(ref, cand, max_components=2, min_relative_eigengap=0.05)['component_alignment'][0]
        self.assertEqual(first['eigengap_check'], 'AMBIGUOUS')
        self.assertFalse(first['component_identity_reliable'])

    @staticmethod
    def receipt(items):
        return {
            'source_sha': 'a' * 40,
            'components': [
                {'component': name, 'eigenvalue': eigenvalue, 'loadings': loadings}
                for name, eigenvalue, loadings in items
            ],
        }


if __name__ == '__main__':
    unittest.main()
