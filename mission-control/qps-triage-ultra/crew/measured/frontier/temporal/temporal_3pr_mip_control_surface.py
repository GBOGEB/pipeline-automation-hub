#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


GATE_ORDER = (
    'independent_windows',
    'distinct_source_shas',
    'temporal_span_seconds',
    'directional_windows',
    'direction_consistency',
    'pooled_winner_strength',
    'latest_two_directional_windows_agree',
    'hosted_runner_classes',
    'baseline_and_held_lanes',
)


def _gate_rows(control: dict, gate: dict) -> list[dict]:
    lanes = set(control.get('lanes', []))
    rows = [
        {
            'gate': 'independent_windows',
            'actual': int(control.get('independent_windows', 0)),
            'required': int(gate['min_independent_windows']),
            'pass': int(control.get('independent_windows', 0)) >= int(gate['min_independent_windows']),
        },
        {
            'gate': 'distinct_source_shas',
            'actual': int(control.get('distinct_source_shas', 0)),
            'required': int(gate['min_distinct_source_shas']),
            'pass': int(control.get('distinct_source_shas', 0)) >= int(gate['min_distinct_source_shas']),
        },
        {
            'gate': 'temporal_span_seconds',
            'actual': float(control.get('temporal_span_seconds', 0.0)),
            'required': float(gate['min_temporal_span_seconds']),
            'pass': float(control.get('temporal_span_seconds', 0.0)) >= float(gate['min_temporal_span_seconds']),
        },
        {
            'gate': 'directional_windows',
            'actual': int(control.get('directional_windows', 0)),
            'required': int(gate['min_directional_windows']),
            'pass': int(control.get('directional_windows', 0)) >= int(gate['min_directional_windows']),
        },
        {
            'gate': 'direction_consistency',
            'actual': float(control.get('direction_consistency', 0.0)),
            'required': float(gate['min_direction_consistency']),
            'pass': float(control.get('direction_consistency', 0.0)) >= float(gate['min_direction_consistency']),
        },
        {
            'gate': 'pooled_winner_strength',
            'actual': float(control.get('pooled_winner_strength', 0.0)),
            'required': float(gate['min_pooled_winner_strength']),
            'pass': float(control.get('pooled_winner_strength', 0.0)) >= float(gate['min_pooled_winner_strength']),
        },
        {
            'gate': 'latest_two_directional_windows_agree',
            'actual': bool(control.get('latest_two_directional_windows_agree', False)),
            'required': bool(gate.get('latest_two_directional_windows_must_agree', False)),
            'pass': (
                not gate.get('latest_two_directional_windows_must_agree', False)
                or bool(control.get('latest_two_directional_windows_agree', False))
            ),
        },
        {
            'gate': 'hosted_runner_classes',
            'actual': len(control.get('hosted_runner_classes', [])),
            'required': int(gate.get('min_hosted_runner_classes', 0)),
            'pass': len(control.get('hosted_runner_classes', [])) >= int(gate.get('min_hosted_runner_classes', 0)),
        },
        {
            'gate': 'baseline_and_held_lanes',
            'actual': sorted(lanes),
            'required': ['baseline', 'held'] if gate.get('requires_baseline_and_held_lanes') else [],
            'pass': (
                not gate.get('requires_baseline_and_held_lanes')
                or {'baseline', 'held'}.issubset(lanes)
            ),
        },
    ]
    assert tuple(row['gate'] for row in rows) == GATE_ORDER
    return rows


def _class_receipt(policy: dict, gate: dict) -> dict:
    control = policy['control_frontier']
    rows = _gate_rows(control, gate)
    failed = [row['gate'] for row in rows if not row['pass']]
    recomputed_pass = not failed
    return {
        'task_class': policy['task_class'],
        'policy_status_from_source': policy.get('policy_status'),
        'allocation_recommendation_from_source': policy.get('allocation_recommendation'),
        'recomputed_control_gate_pass': recomputed_pass,
        'first_red_gate': failed[0] if failed else None,
        'failed_gates': failed,
        'gate_rows': rows,
    }


def build_surface(receipt: dict, config: dict) -> dict:
    if receipt.get('competency_promotions') != 0:
        raise ValueError('competency_promotions must remain zero')
    if receipt.get('authority_transfer') is not False:
        raise ValueError('authority_transfer must remain false')

    contract = config['window_contract']
    frontier = receipt.get('scheduled_control_frontier', {})
    if frontier.get('eligibility_event') != contract['control_eligible_event']:
        raise ValueError('scheduled CONTROL frontier event contract mismatch')
    if frontier.get('eligibility_workflow_path') != contract['control_eligible_workflow_path']:
        raise ValueError('scheduled CONTROL frontier workflow contract mismatch')

    gate = config['control_policy_gate']
    class_rows = {
        name: _class_receipt(receipt['policies'][name], gate)
        for name in config['task_classes']
    }
    control_classes = sorted(name for name, row in class_rows.items() if row['recomputed_control_gate_pass'])
    noncontrol_classes = sorted(name for name, row in class_rows.items() if not row['recomputed_control_gate_pass'])

    focal = {
        name: class_rows[name]
        for name in ('short_compute', 'long_compute_contended')
    }
    return {
        'schema': 'missioncontrol.temporal_3pr_mip_control_surface.v1',
        'mission_id': receipt.get('mission_id'),
        'operator_stack': {
            '3PR': ['Refresh', 'Probe', 'Rank'],
            'MIP': ['Modernize', 'Innovate', 'Perpetuate'],
        },
        'governed_clock_source': 'GENUINE_SCHEDULED_CONTROL_FRONTIER_ONLY',
        'source_frontier': {
            'eligibility_event': frontier.get('eligibility_event'),
            'eligibility_workflow_path': frontier.get('eligibility_workflow_path'),
            'independent_windows': frontier.get('independent_windows'),
            'distinct_source_shas': frontier.get('distinct_source_shas'),
            'temporal_span_seconds': frontier.get('temporal_span_seconds'),
            'window_ids': frontier.get('window_ids', []),
        },
        'control_policy_thresholds_unchanged': True,
        'synthetic_or_noop_clock_evidence_admitted': False,
        'competency_promotions': 0,
        'authority_transfer': False,
        'focal_classes': focal,
        'all_classes': class_rows,
        'full_control_policy': {
            'control_class_count': len(control_classes),
            'task_class_count': len(class_rows),
            'control_classes': control_classes,
            'noncontrol_classes': noncontrol_classes,
            'independently_satisfied': len(control_classes) == len(class_rows),
        },
        'mip_disposition': {
            'Modernize': 'Expose every frozen CONTROL AND-gate as an auditable row.',
            'Innovate': 'Emit deterministic first-red and full-set CONTROL summaries without changing thresholds.',
            'Perpetuate': 'Bind the receipt to genuine scheduled CONTROL provenance for repeat surveillance.',
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--policy', required=True)
    ap.add_argument('--config', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    receipt = json.loads(Path(args.policy).read_text(encoding='utf-8'))
    config = json.loads(Path(args.config).read_text(encoding='utf-8'))
    result = build_surface(receipt, config)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
