"""Behavioural tests for crew/measured/frontier/pc3/analyze_pc3_frontier.py."""
import importlib.util
import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MOD_PATH = (ROOT / 'mission-control' / 'qps-triage-ultra' / 'crew' / 'measured' / 'frontier'
            / 'pc3' / 'analyze_pc3_frontier.py')


def _load():
    spec = importlib.util.spec_from_file_location('cw_analyze_pc3_frontier_mod', MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pc = _load()

SCHEMA = 'missioncontrol.crew_frontier_pc3_runtime_receipt.v2'
HABITATS = ('linux', 'windows', 'macos')
LANES = ('baseline', 'held')
CELLS = [f'{h}-{l}' for h in HABITATS for l in LANES]
CLASSES = ['c0', 'c1', 'c2', 'c3', 'c4']
PRESSURE = {'admission_proxy_seconds', 'post_gate_admission_seconds',
            'human_dependency_wait_seconds', 'lane_held'}


def make_rows():
    rows = []
    i = 0
    for ci, (h, l) in enumerate((h, l) for h in HABITATS for l in LANES):
        for k in range(12):
            paired = k < 10
            pid = f'P{k // 2}' if paired else None
            variant = ('A' if k % 2 == 0 else 'B') if paired else None
            tclass = CLASSES[k // 2] if paired else 'solo'
            rows.append({
                'schema': SCHEMA,
                'mission_id': 'M-PC3',
                'source_sha': 'sha-1',
                'run_id': 'run-9',
                'habitat': {'id': h, 'lane': l},
                'task_id': f'{h}-{l}-{k}',
                'pair_id': pid,
                'variant': variant,
                'task_class': tclass,
                'semantic_digest': 'sd-' + str(pid),
                'resource_profile': 'rp-' + tclass,
                'workload': {'kind': 'w-' + tclass, 'iterations': 3, 'workers': 1 + k % 3},
                'workload_units': 10 * (k + 1),
                'disposition': 'ACCEPT',
                'allocation_strategy': ('alpha' if variant == 'A' else 'beta') if paired else 'gamma',
                'execute_seconds': 1.0 + 0.13 * ((i * 7) % 11),
                'predeclared_task_level': 1 + (k + ci) % 3,
                'rex_preflight': {'rex_ids_checked': ['R'] * (k % 4), 'checklist_version': 'CL-PC3'},
                'rex_postflight': {'rex_ids_observed': ['X'] if k == 0 else [],
                                   'recurrence_level': 'NONE',
                                   'preventive_action_effective': k == 1},
                'crew_combination': ['c'] * (1 + (k + ci) % 2),
                'measured_resource': {
                    'contention_processes': (k * 3 + ci) % 5,
                    'cache_reused': (k + ci) % 2 == 0,
                    'artifact_reused': k % 3 == 0,
                    'human_dependency_wait_seconds': float((k % 4) * (ci + 1)),
                },
            })
            i += 1
    return rows


def make_admission(none_cell='macos-held'):
    rows = []
    for ci, cell in enumerate(CELLS):
        rows.append({
            'cell_id': cell,
            'admission_proxy_seconds_from_run_creation': None if cell == none_cell else 10.0 * (ci + 1),
            'post_gate_admission_seconds': None if cell == none_cell else 2.0 * ci + 1.0,
        })
    return {'source_sha': 'sha-1', 'run_id': 'run-9', 'rows': rows}


def write_rows(root, rows):
    root.mkdir(parents=True, exist_ok=True)
    for i, r in enumerate(rows):
        (root / f'r{i:03d}__PC3-F{i}.json').write_text(json.dumps(r), encoding='utf-8')


def run_main(monkeypatch, tmp_path, rows, admission=None):
    write_rows(tmp_path / 'in', rows)
    apath = tmp_path / 'admission.json'
    apath.write_text(json.dumps(admission if admission is not None else make_admission()), encoding='utf-8')
    out = tmp_path / 'out.json'
    monkeypatch.setattr(sys, 'argv', ['analyze_pc3_frontier.py', '--input-root', str(tmp_path / 'in'),
                                      '--admission-telemetry', str(apath), '--out', str(out)])
    pc.main()
    return out


# ---------- helpers ----------

def test_mean_stdev_and_jacobi():
    assert pc.mean([2, 4]) == 3
    assert pc.stdev([1.0]) == 0.0
    assert pc.stdev([2.0, 4.0, 6.0]) == pytest.approx(2.0)
    vals, vecs = pc.jacobi_eigh([[2.0, 1.0], [1.0, 2.0]])
    assert vals == pytest.approx([3.0, 1.0])
    assert [abs(x) for x in vecs[1]] == pytest.approx([1 / math.sqrt(2)] * 2)
    assert pc.jacobi_eigh([[4.0]]) == ([4.0], [[1.0]])
    vals3, _ = pc.jacobi_eigh([[3.0, 0.5, 0.1], [0.5, 2.0, 0.3], [0.1, 0.3, 1.0]])
    assert sum(vals3) == pytest.approx(6.0)


def test_load_receipts_filters_pattern_and_schema(tmp_path):
    (tmp_path / 'd').mkdir()
    (tmp_path / 'd' / 'x__PC3-F1.json').write_text(json.dumps({'schema': SCHEMA, 'n': 1}), encoding='utf-8')
    (tmp_path / 'y__PC3-F2.json').write_text(json.dumps({'schema': 'v1'}), encoding='utf-8')
    (tmp_path / 'z__F3.json').write_text(json.dumps({'schema': SCHEMA, 'n': 3}), encoding='utf-8')
    assert pc.load_receipts(tmp_path) == [{'schema': SCHEMA, 'n': 1}]


# ---------- validate_cells ----------

def test_validate_cells_happy():
    grouped = pc.validate_cells(make_rows())
    assert sorted(grouped) == sorted(CELLS)
    assert all(len(v) == 12 for v in grouped.values())


def test_validate_cells_missing_cell():
    rows = [r for r in make_rows() if r['habitat']['id'] != 'macos']
    with pytest.raises(SystemExit, match='FAIL PC3 cells actual='):
        pc.validate_cells(rows)


def test_validate_cells_wrong_count():
    rows = make_rows()
    del rows[-1]
    with pytest.raises(SystemExit, match='FAIL macos-held receipt count 11'):
        pc.validate_cells(rows)


def test_validate_cells_rejected():
    rows = make_rows()
    rows[0]['disposition'] = 'REJECT'
    with pytest.raises(SystemExit, match='FAIL rejected task in linux-baseline'):
        pc.validate_cells(rows)


def test_validate_cells_pair_member_count():
    rows = make_rows()
    rows[0]['pair_id'] = None
    with pytest.raises(SystemExit, match='FAIL pair member count in linux-baseline'):
        pc.validate_cells(rows)


# ---------- validate_pairs ----------

def test_validate_pairs_happy():
    obs = pc.validate_pairs(make_rows())
    assert len(obs) == 30
    first = obs[0]
    assert first['observation_id'] == 'run-9:linux-baseline:P0'
    assert first['cell_id'] == 'linux-baseline' and first['lane'] == 'baseline'
    assert first['task_class'] == 'c0'
    for o in obs:
        assert o['winner'] in {'alpha', 'beta', 'TIE'}
        expected = abs(o['seconds_a'] - o['seconds_b']) / max(o['seconds_a'], o['seconds_b'])
        assert o['relative_gap'] == pytest.approx(expected)
        if o['relative_gap'] < 0.02:
            assert o['winner'] == 'TIE'
        elif o['seconds_a'] < o['seconds_b']:
            assert o['winner'] == 'alpha'
        else:
            assert o['winner'] == 'beta'


def test_validate_pairs_tie_branch():
    rows = make_rows()
    rows[0]['execute_seconds'] = 2.0
    rows[1]['execute_seconds'] = 2.01
    obs = pc.validate_pairs(rows)
    assert obs[0]['winner'] == 'TIE'


@pytest.mark.parametrize('mutator, pattern', [
    (lambda r: r.update(variant='A'), 'FAIL pair variants linux-baseline/P0'),
    (lambda r: r.update(source_sha='other'), 'FAIL provenance mismatch linux-baseline/P0'),
    (lambda r: r.update(run_id='other'), 'FAIL provenance mismatch linux-baseline/P0'),
    (lambda r: r.update(semantic_digest='other'), 'FAIL semantic mismatch linux-baseline/P0'),
    (lambda r: r.update(task_class='other'), 'FAIL task class mismatch linux-baseline/P0'),
    (lambda r: r['workload'].update(kind='other'), 'FAIL workload mismatch linux-baseline/P0'),
    (lambda r: r['workload'].update(iterations=42), 'FAIL workload mismatch linux-baseline/P0'),
    (lambda r: r.update(resource_profile='other'), 'FAIL resource-profile mismatch linux-baseline/P0'),
    (lambda r: r.update(disposition='REJECT'), 'FAIL rejected pair member linux-baseline/P0'),
])
def test_validate_pairs_contract_breaks(mutator, pattern):
    rows = make_rows()
    mutator(rows[1])
    with pytest.raises(SystemExit, match=pattern):
        pc.validate_pairs(rows)


def test_validate_pairs_incomplete_pair():
    rows = make_rows()
    del rows[1]
    with pytest.raises(SystemExit, match='FAIL pair linux-baseline/P0 count 1'):
        pc.validate_pairs(rows)


def test_validate_pairs_total_observation_count():
    rows = make_rows()[2:]
    with pytest.raises(SystemExit, match='FAIL expected 30 conditional observations, got 29'):
        pc.validate_pairs(rows)


# ---------- BT ----------

def _o(winner, cls='c0'):
    return {'strategy_a': 'alpha', 'strategy_b': 'beta', 'winner': winner, 'task_class': cls}


def test_bt_model_counts_and_centering():
    bt = pc.bt_model([_o('alpha'), _o('alpha'), _o('beta'), _o('TIE')])
    assert bt['status'] == 'READY_OBSERVED'
    assert bt['model'] == 'regularized_bradley_terry_log_odds'
    nodes = {n['strategy']: n for n in bt['nodes']}
    assert nodes['alpha']['wins'] == 2.5 and nodes['alpha']['losses'] == 1.5 and nodes['alpha']['ties'] == 1
    assert nodes['beta']['wins'] == 1.5 and nodes['beta']['losses'] == 2.5
    assert nodes['alpha']['bt_log_strength'] + nodes['beta']['bt_log_strength'] == pytest.approx(0.0)
    assert nodes['alpha']['bt_log_strength'] == pytest.approx(math.log(3.0 / 2.0))
    assert sum(n['normalized_strength'] for n in bt['nodes']) == pytest.approx(1.0)


def test_bt_model_empty_and_min_pairs():
    empty = pc.bt_model([])
    assert empty['status'] == 'DEFER_INSUFFICIENT_OBSERVED_PAIRS'
    assert empty['nodes'] == [] and empty['observed_pairs'] == 0
    assert pc.bt_model([_o('alpha')], min_pairs=1)['status'] == 'READY_OBSERVED'


def test_conditional_bt_ready_per_class():
    obs = [_o('alpha', c) for c in CLASSES for _ in range(6)]
    out = pc.conditional_bt(obs)
    assert sorted(out) == CLASSES
    for model in out.values():
        assert model['status'] == 'READY_CONDITIONAL_OBSERVED'
        assert model['observed_pairs'] == 6
        assert len(model['edges']) == 6


@pytest.mark.parametrize('obs', [
    [_o('alpha', c) for c in CLASSES[:4] for _ in range(6)],
    [_o('alpha', c) for c in CLASSES for _ in range(5)],
])
def test_conditional_bt_shape_failures(obs):
    with pytest.raises(SystemExit, match='five classes with six observed comparisons'):
        pc.conditional_bt(obs)


def test_conditional_bt_keeps_defer_status_internally(monkeypatch):
    # bt_model below min_pairs returns DEFER; conditional_bt must not upgrade it.
    calls = []
    real = pc.bt_model

    def spy(obs, min_pairs=3):
        res = real(obs, min_pairs=100)
        calls.append(res['status'])
        return res

    monkeypatch.setattr(pc, 'bt_model', spy)
    out = pc.conditional_bt([_o('alpha', c) for c in CLASSES for _ in range(6)])
    assert all(v['status'] == 'DEFER_INSUFFICIENT_OBSERVED_PAIRS' for v in out.values())
    assert calls == ['DEFER_INSUFFICIENT_OBSERVED_PAIRS'] * 5


# ---------- PCA ----------

def test_pca_model_real_decomposition():
    rows = make_rows()
    pca = pc.pca_model(rows, make_admission())
    assert pca['status'] == 'READY_MEASURED_PC3'
    assert pca['rows'] == 72
    assert pca['feature_count'] == len(pca['varying_features']) >= 6
    assert {'lane_held', 'runner_windows', 'runner_macos', 'admission_proxy_seconds'} <= set(pca['varying_features'])
    assert [c['component'] for c in pca['components']] == ['PC1', 'PC2', 'PC3', 'PC4', 'PC5']
    eig = [c['eigenvalue'] for c in pca['components']]
    assert eig == sorted(eig, reverse=True)
    assert 1 <= pca['pa95_component_count'] <= pca['feature_count']
    top = pca['components'][0]['top_absolute_loadings']
    assert len(top) == 6
    assert [abs(t['loading']) for t in top] == sorted((abs(t['loading']) for t in top), reverse=True)
    assert pca['pc3_pressure_hypothesis']['status'] in {'SUPPORTED', 'MIXED', 'NOT_SUPPORTED'}
    assert len(pca['scores']) == 72
    assert {'PC1', 'PC5', 'cell_id', 'task_class'} <= set(pca['scores'][0])


def test_pca_model_defers_below_twelve_rows():
    pca = pc.pca_model(make_rows()[:11], make_admission())
    assert pca['status'] == 'DEFER_INSUFFICIENT_MEASURED_VARIANCE'
    assert pca['rows'] == 11


def test_pca_model_defers_on_low_variance():
    rows = make_rows()[:12]
    for r in rows:
        r['execute_seconds'] = 1.0
        r['predeclared_task_level'] = 1
        r['rex_preflight']['rex_ids_checked'] = []
        r['crew_combination'] = ['c']
        r['workload']['workers'] = 1
        r['workload_units'] = 1
        r['measured_resource'] = {'contention_processes': 0, 'cache_reused': False,
                                  'artifact_reused': False, 'human_dependency_wait_seconds': 0.0}
    pca = pc.pca_model(rows, make_admission())
    assert pca == {'status': 'DEFER_INSUFFICIENT_MEASURED_VARIANCE', 'rows': 12, 'varying_features': []}


def _fake_eigh(varying, pc3_weights, n_components=None):
    """Return a jacobi_eigh replacement with a controlled PC3 loading vector."""
    p = len(varying)
    count = p if n_components is None else n_components

    def fake(cov):
        assert len(cov) == p
        vals = [float(p - i) for i in range(count)]
        vecs = []
        for i in range(count):
            if i == 2:
                vecs.append([pc3_weights.get(name, 0.0) for name in varying])
            else:
                vecs.append([1.0 if j == i else 0.0 for j in range(p)])
        return vals, vecs
    return fake


def _varying():
    return pc.pca_model(make_rows(), make_admission())['varying_features']


def test_pc3_hypothesis_supported(monkeypatch):
    varying = _varying()
    weights = {'admission_proxy_seconds': 0.9, 'human_dependency_wait_seconds': 0.8, 'log_execute_ms': 0.1}
    monkeypatch.setattr(pc, 'jacobi_eigh', _fake_eigh(varying, weights))
    hyp = pc.pca_model(make_rows(), make_admission())['pc3_pressure_hypothesis']
    assert hyp['status'] == 'SUPPORTED'
    assert hyp['candidate'] == 'QUEUE_ADMISSION_HUMAN_DEPENDENCY_PRESSURE'
    assert hyp['pressure_absolute_loading_share'] == pytest.approx(1.7 / 1.8)
    assert hyp['pressure_features_in_top5'] == ['admission_proxy_seconds', 'human_dependency_wait_seconds']


def test_pc3_hypothesis_mixed(monkeypatch):
    varying = _varying()
    non_pressure = [v for v in varying if v not in PRESSURE][:4]
    weights = {name: 1.0 for name in non_pressure}
    weights['lane_held'] = 0.1
    monkeypatch.setattr(pc, 'jacobi_eigh', _fake_eigh(varying, weights))
    hyp = pc.pca_model(make_rows(), make_admission())['pc3_pressure_hypothesis']
    assert hyp['status'] == 'MIXED'
    assert hyp['pressure_features_in_top5'] == ['lane_held']
    assert hyp['pressure_absolute_loading_share'] < 0.25


def test_pc3_hypothesis_not_supported(monkeypatch):
    varying = _varying()
    non_pressure = [v for v in varying if v not in PRESSURE]
    assert len(non_pressure) >= 5
    weights = {name: 1.0 for name in non_pressure}
    monkeypatch.setattr(pc, 'jacobi_eigh', _fake_eigh(varying, weights))
    hyp = pc.pca_model(make_rows(), make_admission())['pc3_pressure_hypothesis']
    assert hyp['status'] == 'NOT_SUPPORTED'
    assert hyp['pressure_features_in_top5'] == []
    assert hyp['pressure_absolute_loading_share'] == 0.0


def test_pca_without_pc3_component(monkeypatch):
    varying = _varying()
    monkeypatch.setattr(pc, 'jacobi_eigh', _fake_eigh(varying, {}, n_components=2))
    pca = pc.pca_model(make_rows(), make_admission())
    assert pca['status'] == 'DEFER_NO_PC3'
    assert pca['pc3_pressure_hypothesis'] == {'status': 'NOT_TESTED_NO_PC3'}
    assert len(pca['components']) == 2
    assert pca['pa95_component_count'] == 2


# ---------- main ----------

def test_main_writes_receipt(monkeypatch, tmp_path, capsys):
    out = run_main(monkeypatch, tmp_path, make_rows())
    doc = json.loads(out.read_text(encoding='utf-8'))
    assert doc['schema'] == 'missioncontrol.crew_frontier_pc3_analysis_receipt.v2'
    assert doc['mission_id'] == 'M-PC3'
    assert doc['cells'] == sorted(CELLS)
    assert doc['task_receipts'] == 72 and doc['rejected'] == 0
    assert doc['admission_telemetry'] == make_admission()
    assert doc['bt_global']['observed_pairs'] == 30 and len(doc['bt_global']['edges']) == 30
    assert sorted(doc['bt_conditional_by_task_class']) == CLASSES
    assert doc['rex'] == {'observed_event_count': 6, 'persistent_or_regression_count': 0,
                          'preventive_success_count': 6, 'checklist_version': 'CL-PC3'}
    assert doc['authority_transfer'] is False
    summary = json.loads(capsys.readouterr().out.strip())
    assert summary['status'] == 'PASS_CREW_FRONTIER_PC3_CONDITIONAL_BT'
    assert summary['cells'] == 6 and summary['conditional_bt_classes'] == 5
    assert summary['global_bt_pairs'] == 30
    assert summary['pc3_explained'] == doc['pca']['components'][2]['explained_variance_ratio']


def test_main_no_receipts(monkeypatch, tmp_path):
    with pytest.raises(SystemExit, match='FAIL no PC3 receipts'):
        run_main(monkeypatch, tmp_path, [])


@pytest.mark.parametrize('field', ['source_sha', 'run_id'])
def test_main_single_sha_and_run(monkeypatch, tmp_path, field):
    rows = make_rows()
    rows[5][field] = 'other'
    with pytest.raises(SystemExit, match='FAIL PC3 aggregate must contain one exact SHA and one run'):
        run_main(monkeypatch, tmp_path, rows)


def test_main_runs_cell_validation(monkeypatch, tmp_path):
    rows = make_rows()[:-1]
    with pytest.raises(SystemExit, match='receipt count 11'):
        run_main(monkeypatch, tmp_path, rows)


@pytest.mark.parametrize('field', ['source_sha', 'run_id'])
def test_main_admission_provenance(monkeypatch, tmp_path, field):
    adm = make_admission()
    adm[field] = 'stale'
    with pytest.raises(SystemExit, match='FAIL admission telemetry provenance mismatch'):
        run_main(monkeypatch, tmp_path, make_rows(), adm)


def test_main_rex_regression_veto(monkeypatch, tmp_path):
    rows = make_rows()
    rows[3]['rex_postflight']['recurrence_level'] = 'PERSISTENT'
    with pytest.raises(SystemExit, match='FAIL REX persistent/regression veto'):
        run_main(monkeypatch, tmp_path, rows)
    assert not (tmp_path / 'out.json').exists()


def test_main_pca_not_ready(monkeypatch, tmp_path):
    varying = _varying()
    monkeypatch.setattr(pc, 'jacobi_eigh', _fake_eigh(varying, {}, n_components=2))
    with pytest.raises(SystemExit, match='FAIL measured PC3 did not become ready'):
        run_main(monkeypatch, tmp_path, make_rows())

