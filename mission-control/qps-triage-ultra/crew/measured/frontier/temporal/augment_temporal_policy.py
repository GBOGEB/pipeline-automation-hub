#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--policy', required=True)
    ap.add_argument('--discovery', required=True)
    ap.add_argument('--constrained-window')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    policy = json.loads(Path(args.policy).read_text(encoding='utf-8'))
    discovery = json.loads(Path(args.discovery).read_text(encoding='utf-8'))
    extension = {
        'status': discovery.get('status'),
        'declared_labels': discovery.get('declared_labels', []),
        'matched_runner': discovery.get('matched_runner'),
        'real_constrained_habitat_observed': False,
        'window': None,
        'policy_effect': 'NONE_UNTIL_REAL_ASSIGNMENT',
        'authority_transfer': False
    }

    if args.constrained_window:
        path = Path(args.constrained_window)
        if path.exists():
            window = json.loads(path.read_text(encoding='utf-8'))
            if window.get('status') != 'PASS_CONSTRAINED_HABITAT_WINDOW':
                raise SystemExit('FAIL constrained window status')
            if window.get('authority_transfer') is not False or window.get('competency_promotions') != 0:
                raise SystemExit('FAIL constrained window authority/promotion boundary')
            if window.get('runner', {}).get('environment') != 'self-hosted-constrained':
                raise SystemExit('FAIL constrained window runner environment')
            if window.get('conditional_pair_edges') != 5 or window.get('task_receipts') != 12:
                raise SystemExit('FAIL constrained window coverage')
            extension.update({
                'status': 'REAL_CONSTRAINED_HABITAT_OBSERVED',
                'real_constrained_habitat_observed': True,
                'window': window,
                'policy_effect': 'ROBUSTNESS_EXTENSION_ONLY'
            })

    policy['schema'] = 'missioncontrol.temporal_allocation_policy_receipt.v1.1'
    policy['augmented_at'] = datetime.now(timezone.utc).isoformat()
    policy['constrained_runner_extension'] = extension
    policy['competency_promotions'] = 0
    policy['authority_transfer'] = False
    Path(args.out).write_text(json.dumps(policy, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({
        'status': policy['status'],
        'windows': policy['independent_windows'],
        'distinct_shas': policy['distinct_source_shas'],
        'constrained': extension['status'],
        'control_policies': sum(v['policy_status'] == 'CONTROL_POLICY' for v in policy['policies'].values()),
        'repeat_stable': sum(v['policy_status'] == 'RECOMMEND_REPEAT_STABLE' for v in policy['policies'].values())
    }, sort_keys=True))


if __name__ == '__main__':
    main()
