#!/usr/bin/env python3
"""Stable CLI facade for the temporal policy engine.

The engine keeps aggregate learning evidence and scheduled-only CONTROL evidence
separate. This facade makes CONTROL rows self-consistent for downstream
enforcement and attaches non-promotional H1-H4 surveillance observations.
"""

import temporal_policy_engine as engine
from temporal_policy_engine import *  # noqa: F401,F403
from temporal_surveillance import attach_surveillance

_ENGINE_BUILD_POLICY = engine.build_policy


def build_policy(windows):
    receipt = _ENGINE_BUILD_POLICY(windows)
    for row in receipt['policies'].values():
        learning_evidence = list(row.get('window_evidence', []))
        row['learning_frontier'] = {
            'independent_windows': row['independent_windows'],
            'directional_windows': row['directional_windows'],
            'distinct_source_shas': row['distinct_source_shas'],
            'temporal_span_seconds': row['temporal_span_seconds'],
            'direction_counts': row['direction_counts'],
            'dominant_direction': row['dominant_direction'],
            'direction_consistency': row['direction_consistency'],
            'latest_two_directional_windows_agree': row['latest_two_directional_windows_agree'],
            'pooled_single_strength': row['pooled_single_strength'],
            'pooled_winner_strength': row['pooled_winner_strength'],
            'observed_pairs_total': row['observed_pairs_total'],
            'window_evidence': learning_evidence,
        }

        if row['policy_status'] != CONFIG['policy_outputs']['control']:
            continue

        control = row['control_frontier']
        row['independent_windows'] = control['independent_windows']
        row['directional_windows'] = control['directional_windows']
        row['distinct_source_shas'] = control['distinct_source_shas']
        row['temporal_span_seconds'] = control['temporal_span_seconds']
        row['direction_counts'] = control['direction_counts']
        row['dominant_direction'] = control['dominant_direction']
        row['direction_consistency'] = control['direction_consistency']
        row['latest_two_directional_windows_agree'] = control['latest_two_directional_windows_agree']
        row['pooled_single_strength'] = control['pooled_single_strength']
        row['pooled_winner_strength'] = control['pooled_winner_strength']
        row['observed_pairs_total'] = control['observed_pairs_total']
        control_ids = set(control['window_ids'])
        row['window_evidence'] = [r for r in learning_evidence if r['window_id'] in control_ids]
        assert row['dominant_direction'] == row['allocation_recommendation']

    return attach_surveillance(receipt)


engine.build_policy = build_policy


if __name__ == '__main__':
    engine.main()
