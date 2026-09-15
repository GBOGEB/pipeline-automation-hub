#!/usr/bin/env python3
from datetime import datetime, timedelta, timezone

from temporal_surveillance import attach_surveillance


def window(i, seconds, direction='ALLOC_PAIRED_CELL', strength=0.2, source_kind='HISTORICAL_ACTION_ARTIFACT'):
    return {
        'window_id': str(100 + i),
        'event': 'schedule',
        'workflow_path': '.github/workflows/crew-temporal-allocation-policy.yml',
        'source_kind': source_kind,
        'source_sha': f'{i + 1:040x}',
        'created_at': (datetime(2026, 9, 13, tzinfo=timezone.utc) + timedelta(seconds=seconds)).isoformat(),
        'hosted_runner_classes': ['linux', 'macos', 'windows'],
        'lanes': ['baseline', 'held'],
        'rex_veto': False,
        'task_classes': {
            'long_compute_contended': {
                'direction': direction,
                'single_normalized_strength': strength,
                'paired_normalized_strength': 1.0 - strength,
                'observed_pairs': 6,
            }
        },
    }


def test_surveillance_uses_only_genuine_scheduled_time():
    genuine = [window(i, i * 18000) for i in range(6)]
    synthetic = window(9, 300000, source_kind='SYNTHETIC_TEST')
    receipt = {
        'scheduled_control_frontier': {
            'eligibility_event': 'schedule',
            'eligibility_workflow_path': '.github/workflows/crew-temporal-allocation-policy.yml',
            'temporal_span_seconds': 90000,
        },
        'windows': genuine + [synthetic],
        'policies': {'long_compute_contended': {}},
    }
    out = attach_surveillance(receipt)['temporal_surveillance']
    row = out['classes']['long_compute_contended']
    assert out['genuine_scheduled_windows'] == 6
    assert out['synthetic_windows_counted'] == 0
    assert out['horizons']['H1_24H']['mature'] is True
    assert out['horizons']['H2_72H']['mature'] is False
    assert row['direction_flip_count'] == 0
    assert row['jackknife']['direction_preservation_fraction'] == 1.0
    assert row['early_vs_late_direction_agreement'] is True
    assert out['competency_promotions'] == 0
    assert out['authority_transfer'] is False


if __name__ == '__main__':
    test_surveillance_uses_only_genuine_scheduled_time()
    print('PASS_TEMPORAL_SURVEILLANCE_VNV')
