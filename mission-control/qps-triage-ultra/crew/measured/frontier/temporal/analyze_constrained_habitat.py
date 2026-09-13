#!/usr/bin/env python3
import argparse
import json
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

TASK_CLASSES = {
    'short_compute',
    'long_compute_contended',
    'validation_bundle',
    'cache_artifact_reuse',
    'human_dependency_wait_proxy'
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input-root', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    root = Path(args.input_root)
    source_sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    rows = [json.loads(p.read_text(encoding='utf-8')) for p in sorted(root.glob('*__PC3-F*.json'))]
    if len(rows) != 12:
        raise SystemExit(f'FAIL constrained receipts expected=12 actual={len(rows)}')
    if any(r.get('source_sha') != source_sha or r.get('disposition') != 'ACCEPT' for r in rows):
        raise SystemExit('FAIL constrained exact-SHA/acceptance')
    if any(r.get('habitat', {}).get('runner', {}).get('environment') != 'self-hosted-constrained' for r in rows):
        raise SystemExit('FAIL constrained runner environment is not self-hosted-constrained')
    pairs = defaultdict(list)
    for row in rows:
        if row.get('pair_id'):
            pairs[row['pair_id']].append(row)
    edges = []
    by_class = {}
    for pair_id, members in sorted(pairs.items()):
        if len(members) != 2:
            raise SystemExit(f'FAIL {pair_id} expected two members')
        members = sorted(members, key=lambda r: r['variant'])
        a, b = members
        if a['semantic_digest'] != b['semantic_digest']:
            raise SystemExit(f'FAIL semantic mismatch {pair_id}')
        if a['task_class'] != b['task_class'] or a['task_class'] not in TASK_CLASSES:
            raise SystemExit(f'FAIL task class {pair_id}')
        ta, tb = float(a['execute_seconds']), float(b['execute_seconds'])
        denom = max(ta, tb, 1e-12)
        gap = abs(ta - tb) / denom
        if gap < 0.02:
            winner = 'TIE'
        elif ta < tb:
            winner = a['allocation_strategy']
        else:
            winner = b['allocation_strategy']
        edge = {
            'pair_id': pair_id,
            'task_class': a['task_class'],
            'strategy_a': a['allocation_strategy'],
            'strategy_b': b['allocation_strategy'],
            'execute_seconds_a': ta,
            'execute_seconds_b': tb,
            'relative_gap': gap,
            'winner': winner,
            'semantic_digest': a['semantic_digest'],
            'comparable': True
        }
        edges.append(edge)
        by_class[a['task_class']] = {
            'winner': winner,
            'relative_gap': gap,
            'pair_id': pair_id
        }
    if set(by_class) != TASK_CLASSES:
        raise SystemExit(f'FAIL constrained classes actual={sorted(by_class)}')
    runner = rows[0]['habitat']['runner']
    out = {
        'schema': 'missioncontrol.constrained_habitat_window.v1',
        'status': 'PASS_CONSTRAINED_HABITAT_WINDOW',
        'captured_at': datetime.now(timezone.utc).isoformat(),
        'source_sha': source_sha,
        'run_id': rows[0].get('run_id'),
        'habitat_id': rows[0]['habitat']['id'],
        'lane': rows[0]['habitat']['lane'],
        'runner': runner,
        'task_receipts': 12,
        'accepted': 12,
        'conditional_pair_edges': 5,
        'by_task_class': by_class,
        'edges': edges,
        'eligible_for_temporal_policy_extension': True,
        'competency_promotions': 0,
        'authority_transfer': False
    }
    Path(args.out).write_text(json.dumps(out, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({'status': out['status'], 'source_sha': source_sha, 'pairs': len(edges), 'runner': runner.get('name')}, sort_keys=True))


if __name__ == '__main__':
    main()
