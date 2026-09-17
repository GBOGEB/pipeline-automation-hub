import unittest

from temporal_3pr_mip_control_surface import build_surface


class Temporal3PrMipControlSurfaceTests(unittest.TestCase):
    def config(self):
        return {
            'task_classes': [
                'short_compute',
                'long_compute_contended',
                'validation_bundle',
                'cache_artifact_reuse',
                'human_dependency_wait_proxy',
            ],
            'window_contract': {
                'control_eligible_event': 'schedule',
                'control_eligible_workflow_path': '.github/workflows/crew-temporal-allocation-policy.yml',
            },
            'control_policy_gate': {
                'min_independent_windows': 6,
                'min_distinct_source_shas': 3,
                'min_temporal_span_seconds': 86400,
                'min_directional_windows': 5,
                'min_direction_consistency': 0.8,
                'min_pooled_winner_strength': 0.7,
                'latest_two_directional_windows_must_agree': True,
                'min_hosted_runner_classes': 3,
                'requires_baseline_and_held_lanes': True,
            },
        }

    def policy(self, name, *, strength=0.75, consistency=0.9, latest=True):
        return {
            'task_class': name,
            'policy_status': 'CONTROL_POLICY',
            'allocation_recommendation': 'ALLOC_SINGLE_CELL',
            'control_frontier': {
                'independent_windows': 8,
                'distinct_source_shas': 4,
                'temporal_span_seconds': 90000.0,
                'directional_windows': 7,
                'direction_consistency': consistency,
                'pooled_winner_strength': strength,
                'latest_two_directional_windows_agree': latest,
                'hosted_runner_classes': ['linux', 'macos', 'windows'],
                'lanes': ['baseline', 'held'],
            },
        }

    def receipt(self):
        names = self.config()['task_classes']
        return {
            'mission_id': 'MC-CREW-FRONTIER-004',
            'competency_promotions': 0,
            'authority_transfer': False,
            'scheduled_control_frontier': {
                'eligibility_event': 'schedule',
                'eligibility_workflow_path': '.github/workflows/crew-temporal-allocation-policy.yml',
                'independent_windows': 8,
                'distinct_source_shas': 4,
                'temporal_span_seconds': 90000.0,
                'window_ids': [str(i) for i in range(8)],
            },
            'policies': {name: self.policy(name) for name in names},
        }

    def test_full_control_when_all_frozen_gates_pass(self):
        result = build_surface(self.receipt(), self.config())
        self.assertTrue(result['full_control_policy']['independently_satisfied'])
        self.assertEqual(result['full_control_policy']['control_class_count'], 5)
        self.assertEqual(result['competency_promotions'], 0)
        self.assertFalse(result['authority_transfer'])
        self.assertFalse(result['synthetic_or_noop_clock_evidence_admitted'])

    def test_first_red_is_frozen_strength_gate(self):
        receipt = self.receipt()
        receipt['policies']['short_compute'] = self.policy('short_compute', strength=0.699314)
        result = build_surface(receipt, self.config())
        row = result['focal_classes']['short_compute']
        self.assertFalse(row['recomputed_control_gate_pass'])
        self.assertEqual(row['first_red_gate'], 'pooled_winner_strength')
        self.assertIn('short_compute', result['full_control_policy']['noncontrol_classes'])

    def test_long_compute_can_have_multiple_reds_in_frozen_order(self):
        receipt = self.receipt()
        receipt['policies']['long_compute_contended'] = self.policy(
            'long_compute_contended', strength=0.626028, consistency=0.6923, latest=False
        )
        row = build_surface(receipt, self.config())['focal_classes']['long_compute_contended']
        self.assertEqual(row['first_red_gate'], 'direction_consistency')
        self.assertEqual(
            row['failed_gates'],
            ['direction_consistency', 'pooled_winner_strength', 'latest_two_directional_windows_agree'],
        )

    def test_authority_invariants_fail_closed(self):
        receipt = self.receipt()
        receipt['competency_promotions'] = 1
        with self.assertRaises(ValueError):
            build_surface(receipt, self.config())

    def test_non_schedule_frontier_fails_closed(self):
        receipt = self.receipt()
        receipt['scheduled_control_frontier']['eligibility_event'] = 'workflow_dispatch'
        with self.assertRaises(ValueError):
            build_surface(receipt, self.config())


if __name__ == '__main__':
    unittest.main()
