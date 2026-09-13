#!/usr/bin/env python3
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path


def mean(xs):
    return sum(xs) / len(xs)


def stdev(xs):
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def jacobi_eigh(matrix, tol=1e-12, max_iter=10000):
    n = len(matrix)
    a = [row[:] for row in matrix]
    v = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for _ in range(max_iter):
        p, q, best = 0, 1 if n > 1 else 0, 0.0
        for i in range(n):
            for j in range(i + 1, n):
                val = abs(a[i][j])
                if val > best:
                    p, q, best = i, j, val
        if best < tol or n < 2:
            break
        app, aqq, apq = a[p][p], a[q][q], a[p][q]
        theta = 0.5 * math.atan2(2.0 * apq, aqq - app)
        c, s = math.cos(theta), math.sin(theta)
        for k in range(n):
            if k not in (p, q):
                aik, aqk = a[p][k], a[q][k]
                a[p][k] = a[k][p] = c * aik - s * aqk
                a[q][k] = a[k][q] = s * aik + c * aqk
        a[p][p] = c*c*app - 2*s*c*apq + s*s*aqq
        a[q][q] = s*s*app + 2*s*c*apq + c*c*aqq
        a[p][q] = a[q][p] = 0.0
        for k in range(n):
            vip, viq = v[k][p], v[k][q]
            v[k][p] = c * vip - s * viq
            v[k][q] = s * vip + c * viq
    vals = [a[i][i] for i in range(n)]
    vecs = [[v[r][c] for r in range(n)] for c in range(n)]
    order = sorted(range(n), key=lambda i: vals[i], reverse=True)
    return [vals[i] for i in order], [vecs[i] for i in order]


def load_receipts(root):
    rows = []
    for p in sorted(root.rglob('*__F*.json')):
        doc = json.loads(p.read_text(encoding='utf-8'))
        if doc.get('schema') == 'missioncontrol.crew_frontier_runtime_receipt.v1':
            rows.append(doc)
    return rows


def validate_pairs(rows):
    grouped = defaultdict(list)
    for r in rows:
        if r.get('pair_id'):
            grouped[(r['habitat']['id'], r['pair_id'])].append(r)
    observations = []
    for (habitat, pair_id), rs in sorted(grouped.items()):
        if len(rs) != 2:
            raise SystemExit(f'FAIL pair {habitat}/{pair_id} has {len(rs)} members')
        rs = sorted(rs, key=lambda x: x['variant'])
        a, b = rs
        if {a['variant'], b['variant']} != {'A', 'B'}:
            raise SystemExit(f'FAIL pair variants {habitat}/{pair_id}')
        if a['source_sha'] != b['source_sha'] or a['run_id'] != b['run_id']:
            raise SystemExit(f'FAIL pair provenance mismatch {habitat}/{pair_id}')
        if a['semantic_digest'] != b['semantic_digest']:
            raise SystemExit(f'FAIL semantic mismatch {habitat}/{pair_id}')
        if a['workload']['kind'] != b['workload']['kind'] or a['workload']['iterations'] != b['workload']['iterations']:
            raise SystemExit(f'FAIL workload equivalence {habitat}/{pair_id}')
        if a['disposition'] != 'ACCEPT' or b['disposition'] != 'ACCEPT':
            raise SystemExit(f'FAIL rejected pair member {habitat}/{pair_id}')
        ta, tb = a['execute_seconds'], b['execute_seconds']
        rel_gap = abs(ta - tb) / max(ta, tb, 1e-12)
        if rel_gap < 0.02:
            winner = 'TIE'
        else:
            winner = a['allocation_strategy'] if ta < tb else b['allocation_strategy']
        observations.append({
            'habitat': habitat,
            'pair_id': pair_id,
            'task_class': a['workload']['kind'],
            'source_sha': a['source_sha'],
            'run_id': a['run_id'],
            'strategy_a': a['allocation_strategy'],
            'strategy_b': b['allocation_strategy'],
            'seconds_a': ta,
            'seconds_b': tb,
            'relative_gap': rel_gap,
            'winner': winner,
            'semantic_digest': a['semantic_digest'],
            'comparable': True
        })
    return observations


def bt_model(observations):
    stats = defaultdict(lambda: {'wins': 0.0, 'losses': 0.0, 'ties': 0})
    edges = []
    for o in observations:
        a, b = o['strategy_a'], o['strategy_b']
        if o['winner'] == 'TIE':
            stats[a]['wins'] += 0.5; stats[a]['losses'] += 0.5; stats[a]['ties'] += 1
            stats[b]['wins'] += 0.5; stats[b]['losses'] += 0.5; stats[b]['ties'] += 1
        elif o['winner'] == a:
            stats[a]['wins'] += 1.0; stats[b]['losses'] += 1.0
        else:
            stats[b]['wins'] += 1.0; stats[a]['losses'] += 1.0
        edges.append(o)
    raw = {}
    for strategy, s in stats.items():
        raw[strategy] = math.log((s['wins'] + 0.5) / (s['losses'] + 0.5))
    center = mean(list(raw.values())) if raw else 0.0
    nodes = []
    denom = sum(math.exp(v - center) for v in raw.values()) or 1.0
    for strategy in sorted(raw):
        score = raw[strategy] - center
        nodes.append({
            'strategy': strategy,
            'bt_log_strength': score,
            'normalized_strength': math.exp(score) / denom,
            **stats[strategy]
        })
    return {
        'status': 'READY_OBSERVED' if len(observations) >= 3 else 'DEFER_INSUFFICIENT_OBSERVED_PAIRS',
        'model': 'regularized_bradley_terry_log_odds',
        'observed_pairs': len(observations),
        'nodes': nodes,
        'edges': edges
    }


def pca_model(rows, queue_by_habitat):
    feature_names = [
        'log_execute_ms', 'task_level', 'rex_exposure_count', 'crew_size',
        'worker_count', 'log_workload_units', 'habitat_windows', 'queue_delay_seconds'
    ]
    matrix = []
    row_refs = []
    for r in rows:
        habitat = r['habitat']['id']
        vector = [
            math.log1p(r['execute_seconds'] * 1000.0),
            float(r['predeclared_task_level']),
            float(len(r['rex_preflight']['rex_ids_checked'])),
            float(len(r['crew_combination'])),
            float(r['workload']['workers']),
            math.log1p(float(r['workload_units'])),
            1.0 if habitat == 'windows' else 0.0,
            float(queue_by_habitat.get(habitat, 0.0))
        ]
        matrix.append(vector)
        row_refs.append({'habitat': habitat, 'task_id': r['task_id'], 'strategy': r['allocation_strategy']})
    varying = []
    standardized_cols = []
    for j, name in enumerate(feature_names):
        col = [row[j] for row in matrix]
        sd = stdev(col)
        if sd > 1e-12:
            m = mean(col)
            varying.append(name)
            standardized_cols.append([(x - m) / sd for x in col])
    if len(rows) < 3 or len(varying) < 2:
        return {'status': 'DEFER_INSUFFICIENT_MEASURED_VARIANCE', 'rows': len(rows), 'varying_features': varying}
    z = [[standardized_cols[j][i] for j in range(len(varying))] for i in range(len(rows))]
    n = len(z)
    p = len(varying)
    cov = [[sum(z[r][i] * z[r][j] for r in range(n)) / (n - 1) for j in range(p)] for i in range(p)]
    eigvals, eigvecs = jacobi_eigh(cov)
    eigvals = [max(0.0, x) for x in eigvals]
    total = sum(eigvals) or 1.0
    components = []
    for idx in range(min(2, len(eigvals))):
        loadings = {varying[j]: eigvecs[idx][j] for j in range(p)}
        components.append({
            'component': f'PC{idx+1}',
            'eigenvalue': eigvals[idx],
            'explained_variance_ratio': eigvals[idx] / total,
            'loadings': loadings
        })
    scores = []
    for ref, vec in zip(row_refs, z):
        item = dict(ref)
        for idx in range(len(components)):
            item[f'PC{idx+1}'] = sum(vec[j] * eigvecs[idx][j] for j in range(p))
        scores.append(item)
    return {
        'status': 'READY_MEASURED',
        'rows': len(rows),
        'feature_count': p,
        'varying_features': varying,
        'components': components,
        'scores': scores
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input-root', required=True)
    ap.add_argument('--queue-telemetry', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    root = Path(args.input_root)
    rows = load_receipts(root)
    if not rows:
        raise SystemExit('FAIL no frontier receipts')
    shas = {r['source_sha'] for r in rows}
    run_ids = {r['run_id'] for r in rows}
    if len(shas) != 1 or len(run_ids) != 1:
        raise SystemExit('FAIL aggregate must be one exact SHA and one run')
    if any(r['disposition'] != 'ACCEPT' for r in rows):
        raise SystemExit('FAIL rejected frontier task')
    queue = json.loads(Path(args.queue_telemetry).read_text(encoding='utf-8'))
    queue_by_habitat = {}
    for r in queue.get('rows', []):
        habitat = r.get('habitat')
        delay = r.get('queue_seconds_from_run_creation')
        if habitat and delay is not None:
            queue_by_habitat.setdefault(habitat, []).append(float(delay))
    queue_by_habitat = {k: mean(v) for k,v in queue_by_habitat.items()}
    pair_obs = validate_pairs(rows)
    pca = pca_model(rows, queue_by_habitat)
    bt = bt_model(pair_obs)
    rex = {
        'observed_event_count': sum(len(r['rex_postflight']['rex_ids_observed']) for r in rows),
        'persistent_or_regression_count': sum(1 for r in rows if r['rex_postflight'].get('recurrence_level') in {'PERSISTENT','REGRESSION'}),
        'preventive_success_count': sum(1 for r in rows if r['rex_postflight'].get('preventive_action_effective') is True),
        'checklist_version': rows[0]['rex_preflight']['checklist_version']
    }
    out = {
        'schema': 'missioncontrol.crew_frontier_analysis_receipt.v1',
        'mission_id': rows[0]['mission_id'],
        'source_sha': next(iter(shas)),
        'run_id': next(iter(run_ids)),
        'habitats': sorted({r['habitat']['id'] for r in rows}),
        'task_receipts': len(rows),
        'accepted': len(rows),
        'rejected': 0,
        'queue_telemetry': queue_by_habitat,
        'pca': pca,
        'bt': bt,
        'rex': rex,
        'competency_promotions': 0,
        'authority_transfer': False
    }
    if pca.get('status') != 'READY_MEASURED':
        raise SystemExit('FAIL PCA frontier did not reach measured readiness')
    if bt.get('status') != 'READY_OBSERVED':
        raise SystemExit('FAIL BT frontier did not reach observed readiness')
    Path(args.out).write_text(json.dumps(out, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({
        'status': 'PASS_CREW_FRONTIER_PCA_BT',
        'source_sha': out['source_sha'],
        'task_receipts': len(rows),
        'habitats': out['habitats'],
        'pca_status': pca['status'],
        'pca_features': pca['feature_count'],
        'bt_status': bt['status'],
        'observed_pairs': bt['observed_pairs'],
        'rex_events': rex['observed_event_count'],
        'competency_promotions': 0
    }, sort_keys=True))

if __name__ == '__main__':
    main()
