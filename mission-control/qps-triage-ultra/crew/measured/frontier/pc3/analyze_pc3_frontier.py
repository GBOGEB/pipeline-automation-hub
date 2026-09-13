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


def jacobi_eigh(matrix, tol=1e-12, max_iter=20000):
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
    for p in sorted(root.rglob('*__PC3-F*.json')):
        doc = json.loads(p.read_text(encoding='utf-8'))
        if doc.get('schema') == 'missioncontrol.crew_frontier_pc3_runtime_receipt.v2':
            rows.append(doc)
    return rows


def validate_cells(rows):
    expected_cells = {f'{h}-{l}' for h in ('linux', 'windows', 'macos') for l in ('baseline', 'held')}
    grouped = defaultdict(list)
    for r in rows:
        grouped[f"{r['habitat']['id']}-{r['habitat']['lane']}"].append(r)
    if set(grouped) != expected_cells:
        raise SystemExit(f'FAIL PC3 cells actual={sorted(grouped)} expected={sorted(expected_cells)}')
    for cell, rs in grouped.items():
        if len(rs) != 12:
            raise SystemExit(f'FAIL {cell} receipt count {len(rs)}')
        if any(r['disposition'] != 'ACCEPT' for r in rs):
            raise SystemExit(f'FAIL rejected task in {cell}')
        if sum(r.get('pair_id') is not None for r in rs) != 10:
            raise SystemExit(f'FAIL pair member count in {cell}')
    return grouped


def validate_pairs(rows):
    grouped = defaultdict(list)
    for r in rows:
        if r.get('pair_id'):
            cell = f"{r['habitat']['id']}-{r['habitat']['lane']}"
            grouped[(cell, r['pair_id'])].append(r)
    observations = []
    for (cell, pair_id), rs in sorted(grouped.items()):
        if len(rs) != 2:
            raise SystemExit(f'FAIL pair {cell}/{pair_id} count {len(rs)}')
        rs = sorted(rs, key=lambda x: x['variant'])
        a, b = rs
        if {a['variant'], b['variant']} != {'A', 'B'}:
            raise SystemExit(f'FAIL pair variants {cell}/{pair_id}')
        if a['source_sha'] != b['source_sha'] or a['run_id'] != b['run_id']:
            raise SystemExit(f'FAIL provenance mismatch {cell}/{pair_id}')
        if a['semantic_digest'] != b['semantic_digest']:
            raise SystemExit(f'FAIL semantic mismatch {cell}/{pair_id}')
        if a['task_class'] != b['task_class']:
            raise SystemExit(f'FAIL task class mismatch {cell}/{pair_id}')
        if a['workload']['kind'] != b['workload']['kind'] or a['workload']['iterations'] != b['workload']['iterations']:
            raise SystemExit(f'FAIL workload mismatch {cell}/{pair_id}')
        if a['resource_profile'] != b['resource_profile']:
            raise SystemExit(f'FAIL resource-profile mismatch {cell}/{pair_id}')
        if a['disposition'] != 'ACCEPT' or b['disposition'] != 'ACCEPT':
            raise SystemExit(f'FAIL rejected pair member {cell}/{pair_id}')
        ta, tb = float(a['execute_seconds']), float(b['execute_seconds'])
        rel_gap = abs(ta - tb) / max(ta, tb, 1e-12)
        winner = 'TIE' if rel_gap < 0.02 else (a['allocation_strategy'] if ta < tb else b['allocation_strategy'])
        observations.append({
            'observation_id': f"{a['run_id']}:{cell}:{pair_id}",
            'cell_id': cell,
            'habitat': a['habitat']['id'],
            'lane': a['habitat']['lane'],
            'pair_id': pair_id,
            'task_class': a['task_class'],
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
    if len(observations) != 30:
        raise SystemExit(f'FAIL expected 30 conditional observations, got {len(observations)}')
    return observations


def bt_model(observations, min_pairs=3):
    stats = defaultdict(lambda: {'wins': 0.0, 'losses': 0.0, 'ties': 0})
    for o in observations:
        a, b = o['strategy_a'], o['strategy_b']
        if o['winner'] == 'TIE':
            stats[a]['wins'] += 0.5; stats[a]['losses'] += 0.5; stats[a]['ties'] += 1
            stats[b]['wins'] += 0.5; stats[b]['losses'] += 0.5; stats[b]['ties'] += 1
        elif o['winner'] == a:
            stats[a]['wins'] += 1.0; stats[b]['losses'] += 1.0
        else:
            stats[b]['wins'] += 1.0; stats[a]['losses'] += 1.0
    raw = {k: math.log((v['wins'] + 0.5) / (v['losses'] + 0.5)) for k, v in stats.items()}
    center = mean(list(raw.values())) if raw else 0.0
    denom = sum(math.exp(v - center) for v in raw.values()) or 1.0
    nodes = []
    for strategy in sorted(raw):
        score = raw[strategy] - center
        nodes.append({
            'strategy': strategy,
            'bt_log_strength': score,
            'normalized_strength': math.exp(score) / denom,
            **stats[strategy]
        })
    return {
        'status': 'READY_OBSERVED' if len(observations) >= min_pairs else 'DEFER_INSUFFICIENT_OBSERVED_PAIRS',
        'model': 'regularized_bradley_terry_log_odds',
        'observed_pairs': len(observations),
        'nodes': nodes
    }


def conditional_bt(observations):
    by_class = defaultdict(list)
    for o in observations:
        by_class[o['task_class']].append(o)
    out = {}
    for task_class, obs in sorted(by_class.items()):
        model = bt_model(obs, min_pairs=3)
        model['status'] = 'READY_CONDITIONAL_OBSERVED' if model['status'] == 'READY_OBSERVED' else model['status']
        model['edges'] = obs
        out[task_class] = model
    if len(out) != 5 or any(v['observed_pairs'] != 6 for v in out.values()):
        raise SystemExit('FAIL conditional BT requires five classes with six observed comparisons each')
    return out


def pca_model(rows, admission):
    by_cell = {r['cell_id']: r for r in admission['rows']}
    feature_names = [
        'log_execute_ms', 'task_level', 'rex_exposure_count', 'crew_size', 'worker_count',
        'log_workload_units', 'runner_windows', 'runner_macos', 'lane_held',
        'admission_proxy_seconds', 'post_gate_admission_seconds', 'contention_processes',
        'cache_reused', 'artifact_reused', 'human_dependency_wait_seconds'
    ]
    matrix, refs = [], []
    for r in rows:
        habitat = r['habitat']['id']
        lane = r['habitat']['lane']
        cell = f'{habitat}-{lane}'
        q = by_cell[cell]
        mr = r['measured_resource']
        vector = [
            math.log1p(float(r['execute_seconds']) * 1000.0),
            float(r['predeclared_task_level']),
            float(len(r['rex_preflight']['rex_ids_checked'])),
            float(len(r['crew_combination'])),
            float(r['workload']['workers']),
            math.log1p(float(r['workload_units'])),
            1.0 if habitat == 'windows' else 0.0,
            1.0 if habitat == 'macos' else 0.0,
            1.0 if lane == 'held' else 0.0,
            float(q['admission_proxy_seconds_from_run_creation'] or 0.0),
            float(q['post_gate_admission_seconds'] or 0.0),
            float(mr['contention_processes']),
            1.0 if mr['cache_reused'] else 0.0,
            1.0 if mr['artifact_reused'] else 0.0,
            float(mr['human_dependency_wait_seconds'])
        ]
        matrix.append(vector)
        refs.append({'cell_id': cell, 'task_id': r['task_id'], 'task_class': r['task_class'], 'strategy': r['allocation_strategy']})

    varying, cols = [], []
    for j, name in enumerate(feature_names):
        col = [row[j] for row in matrix]
        sd = stdev(col)
        if sd > 1e-12:
            m = mean(col)
            varying.append(name)
            cols.append([(x - m) / sd for x in col])
    if len(rows) < 12 or len(varying) < 6:
        return {'status': 'DEFER_INSUFFICIENT_MEASURED_VARIANCE', 'rows': len(rows), 'varying_features': varying}
    z = [[cols[j][i] for j in range(len(varying))] for i in range(len(rows))]
    n, p = len(z), len(varying)
    cov = [[sum(z[r][i] * z[r][j] for r in range(n)) / (n - 1) for j in range(p)] for i in range(p)]
    eigvals, eigvecs = jacobi_eigh(cov)
    eigvals = [max(0.0, x) for x in eigvals]
    total = sum(eigvals) or 1.0
    components = []
    for idx in range(min(5, len(eigvals))):
        loadings = {varying[j]: eigvecs[idx][j] for j in range(p)}
        ranked = sorted(loadings.items(), key=lambda kv: abs(kv[1]), reverse=True)
        components.append({
            'component': f'PC{idx+1}',
            'eigenvalue': eigvals[idx],
            'explained_variance_ratio': eigvals[idx] / total,
            'loadings': loadings,
            'top_absolute_loadings': [{'feature': k, 'loading': v} for k, v in ranked[:6]]
        })
    scores = []
    for ref, vec in zip(refs, z):
        item = dict(ref)
        for idx in range(len(components)):
            item[f'PC{idx+1}'] = sum(vec[j] * eigvecs[idx][j] for j in range(p))
        scores.append(item)

    cumulative = 0.0
    pa95 = len(eigvals)
    for idx, eig in enumerate(eigvals):
        cumulative += eig / total
        if cumulative >= 0.95:
            pa95 = idx + 1
            break

    pc3 = components[2] if len(components) >= 3 else None
    hypothesis = {'status': 'NOT_TESTED_NO_PC3'}
    if pc3:
        pressure = {'admission_proxy_seconds', 'post_gate_admission_seconds', 'human_dependency_wait_seconds', 'lane_held'}
        abs_load = {k: abs(v) for k, v in pc3['loadings'].items()}
        total_abs = sum(abs_load.values()) or 1.0
        pressure_share = sum(abs_load.get(k, 0.0) for k in pressure) / total_abs
        top5 = [x['feature'] for x in pc3['top_absolute_loadings'][:5]]
        top_pressure = [x for x in top5 if x in pressure]
        if pressure_share >= 0.40 and len(top_pressure) >= 2:
            status = 'SUPPORTED'
        elif pressure_share >= 0.25 or len(top_pressure) >= 1:
            status = 'MIXED'
        else:
            status = 'NOT_SUPPORTED'
        hypothesis = {
            'status': status,
            'candidate': 'QUEUE_ADMISSION_HUMAN_DEPENDENCY_PRESSURE',
            'pressure_absolute_loading_share': pressure_share,
            'pressure_features_in_top5': top_pressure,
            'rule': 'SUPPORTED requires >=40% of absolute PC3 loading mass on predeclared pressure features and >=2 pressure features in PC3 top-5; MIXED is weaker evidence; otherwise NOT_SUPPORTED.',
            'sign_note': 'Principal-component signs are arbitrary; interpretation uses absolute loading magnitude.'
        }

    return {
        'status': 'READY_MEASURED_PC3' if len(components) >= 3 else 'DEFER_NO_PC3',
        'rows': len(rows),
        'feature_count': p,
        'varying_features': varying,
        'components': components,
        'pa95_component_count': pa95,
        'pc3_pressure_hypothesis': hypothesis,
        'scores': scores
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input-root', required=True)
    ap.add_argument('--admission-telemetry', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    rows = load_receipts(Path(args.input_root))
    if not rows:
        raise SystemExit('FAIL no PC3 receipts')
    shas = {r['source_sha'] for r in rows}
    runs = {r['run_id'] for r in rows}
    if len(shas) != 1 or len(runs) != 1:
        raise SystemExit('FAIL PC3 aggregate must contain one exact SHA and one run')
    validate_cells(rows)
    admission = json.loads(Path(args.admission_telemetry).read_text(encoding='utf-8'))
    if admission.get('source_sha') != next(iter(shas)) or admission.get('run_id') != next(iter(runs)):
        raise SystemExit('FAIL admission telemetry provenance mismatch')

    observations = validate_pairs(rows)
    global_bt = bt_model(observations)
    per_class = conditional_bt(observations)
    pca = pca_model(rows, admission)
    rex = {
        'observed_event_count': sum(len(r['rex_postflight']['rex_ids_observed']) for r in rows),
        'persistent_or_regression_count': sum(1 for r in rows if r['rex_postflight'].get('recurrence_level') in {'PERSISTENT', 'REGRESSION'}),
        'preventive_success_count': sum(1 for r in rows if r['rex_postflight'].get('preventive_action_effective') is True),
        'checklist_version': rows[0]['rex_preflight']['checklist_version']
    }
    out = {
        'schema': 'missioncontrol.crew_frontier_pc3_analysis_receipt.v2',
        'mission_id': rows[0]['mission_id'],
        'source_sha': next(iter(shas)),
        'run_id': next(iter(runs)),
        'cells': sorted({f"{r['habitat']['id']}-{r['habitat']['lane']}" for r in rows}),
        'task_receipts': len(rows),
        'accepted': len(rows),
        'rejected': 0,
        'admission_telemetry': admission,
        'pca': pca,
        'bt_global': {**global_bt, 'edges': observations},
        'bt_conditional_by_task_class': per_class,
        'rex': rex,
        'competency_promotions': 0,
        'authority_transfer': False
    }
    if len(rows) != 72:
        raise SystemExit(f'FAIL expected 72 task receipts, got {len(rows)}')
    if pca.get('status') != 'READY_MEASURED_PC3':
        raise SystemExit('FAIL measured PC3 did not become ready')
    if len(pca.get('components', [])) < 3:
        raise SystemExit('FAIL PC3 component absent')
    if global_bt.get('status') != 'READY_OBSERVED' or global_bt.get('observed_pairs') != 30:
        raise SystemExit('FAIL global BT not ready at 30 observations')
    if any(v.get('status') != 'READY_CONDITIONAL_OBSERVED' for v in per_class.values()):
        raise SystemExit('FAIL conditional BT class not ready')
    if rex['persistent_or_regression_count']:
        raise SystemExit('FAIL REX persistent/regression veto')
    Path(args.out).write_text(json.dumps(out, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    pc3 = pca['components'][2]
    print(json.dumps({
        'status': 'PASS_CREW_FRONTIER_PC3_CONDITIONAL_BT',
        'source_sha': out['source_sha'],
        'task_receipts': len(rows),
        'cells': len(out['cells']),
        'pca_status': pca['status'],
        'pca_features': pca['feature_count'],
        'pc1_explained': pca['components'][0]['explained_variance_ratio'],
        'pc2_explained': pca['components'][1]['explained_variance_ratio'],
        'pc3_explained': pc3['explained_variance_ratio'],
        'pc3_hypothesis': pca['pc3_pressure_hypothesis']['status'],
        'global_bt_pairs': global_bt['observed_pairs'],
        'conditional_bt_classes': len(per_class),
        'competency_promotions': 0
    }, sort_keys=True))

if __name__ == '__main__':
    main()
