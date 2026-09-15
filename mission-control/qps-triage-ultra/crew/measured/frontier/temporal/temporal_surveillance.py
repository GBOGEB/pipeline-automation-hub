#!/usr/bin/env python3
"""Non-promotional temporal surveillance metrics for MissionControl CONTROL evidence.

This module never creates CONTROL windows and never changes the CONTROL entry gate.
It derives robustness observations from genuine scheduled windows already present in
the temporal policy receipt. Synthetic fixtures are excluded from operational time.
"""
from collections import Counter
from datetime import datetime


def _genuine_scheduled_windows(receipt):
    frontier = receipt.get('scheduled_control_frontier', {})
    event = frontier.get('eligibility_event', 'schedule')
    path = frontier.get('eligibility_workflow_path')
    rows = []
    for w in receipt.get('windows', []):
        if w.get('event') != event or (path and w.get('workflow_path') != path):
            continue
        if w.get('source_kind') == 'SYNTHETIC_TEST':
            continue
        rows.append(w)
    return sorted(rows, key=lambda w: (w.get('created_at', ''), int(w.get('window_id', 0))))


def _genuine_span_seconds(windows):
    if len(windows) < 2:
        return 0.0
    first = datetime.fromisoformat(windows[0]['created_at'].replace('Z', '+00:00'))
    last = datetime.fromisoformat(windows[-1]['created_at'].replace('Z', '+00:00'))
    return max(0.0, (last - first).total_seconds())


def _class_stats(windows, task_class):
    records = []
    for w in windows:
        row = w['task_classes'][task_class]
        records.append({
            'window_id': w['window_id'],
            'source_sha': w['source_sha'],
            'created_at': w['created_at'],
            'direction': row['direction'],
            'single_normalized_strength': float(row['single_normalized_strength']),
            'observed_pairs': int(row['observed_pairs']),
        })
    directional = [r for r in records if r['direction'] != 'INDETERMINATE']
    counts = Counter(r['direction'] for r in directional)
    dominant = counts.most_common(1)[0][0] if counts else 'INDETERMINATE'
    flips = sum(a['direction'] != b['direction'] for a, b in zip(directional, directional[1:]))
    total_pairs = sum(r['observed_pairs'] for r in records)
    pooled_single = (
        sum(r['single_normalized_strength'] * r['observed_pairs'] for r in records) / total_pairs
        if total_pairs else 0.5
    )
    return records, directional, dominant, pooled_single, flips


def _jackknife(records, reference_direction):
    if len(records) < 2:
        return {'samples': 0, 'min_pooled_winner_strength': None, 'direction_preservation_fraction': None}
    strengths = []
    preserved = 0
    for idx in range(len(records)):
        sample = records[:idx] + records[idx + 1:]
        pairs = sum(r['observed_pairs'] for r in sample)
        single = sum(r['single_normalized_strength'] * r['observed_pairs'] for r in sample) / pairs if pairs else 0.5
        winner = max(single, 1.0 - single)
        direction = 'ALLOC_SINGLE_CELL' if single > 0.5 else 'ALLOC_PAIRED_CELL' if single < 0.5 else 'INDETERMINATE'
        strengths.append(winner)
        preserved += direction == reference_direction
    return {
        'samples': len(records),
        'min_pooled_winner_strength': min(strengths),
        'direction_preservation_fraction': preserved / len(records),
    }


def _half_direction(records):
    if not records:
        return 'INDETERMINATE'
    pairs = sum(r['observed_pairs'] for r in records)
    single = sum(r['single_normalized_strength'] * r['observed_pairs'] for r in records) / pairs if pairs else 0.5
    if single >= 0.55:
        return 'ALLOC_SINGLE_CELL'
    if single <= 0.45:
        return 'ALLOC_PAIRED_CELL'
    return 'INDETERMINATE'


def _concentration(windows):
    n = len(windows)
    if not n:
        return {'source_sha_max_window_fraction': None, 'runner_class_max_presence_fraction': None, 'lane_max_presence_fraction': None}
    sha = Counter(w['source_sha'] for w in windows)
    runners = Counter(h for w in windows for h in set(w.get('hosted_runner_classes', [])))
    lanes = Counter(l for w in windows for l in set(w.get('lanes', [])))
    return {
        'source_sha_max_window_fraction': max(sha.values()) / n,
        'runner_class_max_presence_fraction': max(runners.values(), default=0) / n,
        'lane_max_presence_fraction': max(lanes.values(), default=0) / n,
    }


def attach_surveillance(receipt):
    windows = _genuine_scheduled_windows(receipt)
    span = _genuine_span_seconds(windows)
    horizons = {'H1_24H': 86400, 'H2_72H': 259200, 'H3_7D': 604800, 'H4_30D': 2592000}
    classes = {}
    for task_class in receipt.get('policies', {}):
        records, directional, dominant, pooled_single, flips = _class_stats(windows, task_class)
        mid = len(records) // 2
        early = _half_direction(records[:mid])
        late = _half_direction(records[mid:])
        jackknife = _jackknife(records, dominant)
        classes[task_class] = {
            'genuine_scheduled_windows': len(records),
            'directional_windows': len(directional),
            'direction_flip_count': flips,
            'indeterminate_window_fraction': ((len(records) - len(directional)) / len(records)) if records else None,
            'rolling_pooled_winner_strength': max(pooled_single, 1.0 - pooled_single),
            'dominant_direction': dominant,
            'jackknife': jackknife,
            'early_direction': early,
            'late_direction': late,
            'early_vs_late_direction_agreement': early == late and early != 'INDETERMINATE',
            'rex_veto_count': sum(bool(w.get('rex_veto')) for w in windows),
            'evidence_concentration': _concentration(windows),
        }
    receipt['temporal_surveillance'] = {
        'schema': 'missioncontrol.temporal_surveillance.v1',
        'role': 'NON_PROMOTIONAL_ROBUSTNESS_AND_PERSISTENCE_OBSERVATION',
        'genuine_scheduled_windows': len(windows),
        'genuine_temporal_span_seconds': span,
        'horizons': {name: {'target_span_seconds': target, 'mature': span >= target} for name, target in horizons.items()},
        'classes': classes,
        'synthetic_windows_counted': 0,
        'changes_control_entry_gate': False,
        'competency_promotions': 0,
        'authority_transfer': False,
    }
    return receipt
