"""Behavioural tests for crew/measured/frontier/analyze_frontier.py."""
import copy
import importlib.util
import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MOD_PATH = ROOT / 'mission-control' / 'qps-triage-ultra' / 'crew' / 'measured' / 'frontier' / 'analyze_frontier.py'


def _load():
    spec = importlib.util.spec_from_file_location('cw_analyze_frontier_mod', MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


af = _load()

SCHEMA = 'missioncontrol.crew_frontier_runtime_receipt.v1'
BASIS = 'SOURCE_SHA_PARITY_XOR_HABITAT'


def receipt(habitat, task_id, variant=None, pair_id=None, direction=None, position=None,
            secs=1.0, strategy='alpha', level=1, rex_checked=1, crew=1, workers=1, units=10):
    doc = {
        'schema': SCHEMA,
        'mission_id': 'M-1',
        'source_sha': 'abc123',
        'run_id': 'run-1',
        'habitat': {'id': habitat},
        'task_id': task_id,
        'pair_id': pair_id,
        'variant': variant,
        'semantic_digest': 'sd-' + str(pair_id),
        'workload': {'kind': 'k-' + str(pair_id), 'iterations': 5, 'workers': workers},
        'workload_units': units,
        'disposition': 'ACCEPT',
        'allocation_strategy': strategy,
        'execute_seconds': secs,
        'predeclared_task_level': level,
        'rex_preflight': {'rex_ids_checked': ['R'] * rex_checked, 'checklist_version': 'CL-7'},
        'rex_postflight': {'rex_ids_observed': ['R1'], 'recurrence_level': 'NONE',
                           'preventive_action_effective': True},
        'crew_combination': ['c'] * crew,
    }
    if direction is not None:
        doc['execution_order'] = {'pair_direction': direction, 'pair_position': position,
                                  'counterbalance_basis': BASIS}
    return doc


def pair(habitat, pair_id, direction, secs_a, secs_b, **kw):
    pos_a, pos_b = (1, 2) if direction == 'A_THEN_B' else (2, 1)
    return [
        receipt(habitat, f'{habitat}-{pair_id}-A', 'A', pair_id, direction, pos_a, secs_a, 'alpha', **kw),
        receipt(habitat, f'{habitat}-{pair_id}-B', 'B', pair_id, direction, pos_b, secs_b, 'beta', **kw),
    ]


def good_rows():
    rows = []
    rows += pair('linux', 'P1', 'A_THEN_B', 1.0, 2.0, level=1, crew=1)
    rows += pair('linux', 'P2', 'B_THEN_A', 3.0, 1.0, level=2, crew=2)
    rows += pair('windows', 'P1', 'B_THEN_A', 1.00, 1.01, level=3, crew=3)
    rows += pair('windows', 'P2', 'A_THEN_B', 0.5, 4.0, level=1, crew=2)
    rows.append(receipt('linux', 'solo', secs=2.5, level=4, rex_checked=3))
    return rows


def write_rows(root, rows):
    root.mkdir(parents=True, exist_ok=True)
    for i, r in enumerate(rows):
        (root / f'r{i:02d}__F{i}.json').write_text(json.dumps(r), encoding='utf-8')


def run_main(monkeypatch, tmp_path, rows, queue=None):
    write_rows(tmp_path / 'in', rows)
    qpath = tmp_path / 'queue.json'
    qpath.write_text(json.dumps(queue if queue is not None else {'rows': []}), encoding='utf-8')
    out = tmp_path / 'out.json'
    monkeypatch.setattr(sys, 'argv', ['analyze_frontier.py', '--input-root', str(tmp_path / 'in'),
                                      '--queue-telemetry', str(qpath), '--out', str(out)])
    af.main()
    return out


# ---------- numeric helpers ----------

def test_mean_and_stdev():
    assert af.mean([1, 2, 3]) == 2
    assert af.stdev([4.0]) == 0.0
    assert af.stdev([1.0, 2.0, 3.0]) == pytest.approx(1.0)


def test_jacobi_eigh_two_by_two_sorted_descending():
    vals, vecs = af.jacobi_eigh([[2.0, 1.0], [1.0, 2.0]])
    assert vals == pytest.approx([3.0, 1.0])
    assert [abs(x) for x in vecs[0]] == pytest.approx([1 / math.sqrt(2)] * 2)


def test_jacobi_eigh_diagonal_and_single():
    vals, vecs = af.jacobi_eigh([[1.0, 0.0, 0.0], [0.0, 5.0, 0.0], [0.0, 0.0, 3.0]])
    assert vals == [5.0, 3.0, 1.0]
    assert vecs[0] == [0.0, 1.0, 0.0]
    assert af.jacobi_eigh([[7.0]]) == ([7.0], [[1.0]])


def test_jacobi_eigh_three_by_three_reconstructs_trace():
    m = [[4.0, 1.0, 0.5], [1.0, 3.0, 0.2], [0.5, 0.2, 1.0]]
    vals, _ = af.jacobi_eigh(m)
    assert sum(vals) == pytest.approx(8.0)
    assert vals == sorted(vals, reverse=True)


# ---------- load_receipts ----------

def test_load_receipts_filters_by_name_and_schema(tmp_path):
    sub = tmp_path / 'nested'
    sub.mkdir()
    (sub / 'a__F1.json').write_text(json.dumps({'schema': SCHEMA, 'id': 1}), encoding='utf-8')
    (tmp_path / 'b__F2.json').write_text(json.dumps({'schema': 'other'}), encoding='utf-8')
    (tmp_path / 'c.json').write_text(json.dumps({'schema': SCHEMA, 'id': 3}), encoding='utf-8')
    rows = af.load_receipts(tmp_path)
    assert rows == [{'schema': SCHEMA, 'id': 1}]


# ---------- validate_pairs ----------

def test_validate_pairs_happy_path_winners_and_directions():
    obs, dirs = af.validate_pairs(good_rows())
    assert len(obs) == 4
    by_key = {(o['habitat'], o['pair_id']): o for o in obs}
    assert by_key[('linux', 'P1')]['winner'] == 'alpha'
    assert by_key[('linux', 'P2')]['winner'] == 'beta'
    assert by_key[('windows', 'P1')]['winner'] == 'TIE'
    assert by_key[('windows', 'P1')]['relative_gap'] == pytest.approx(0.01 / 1.01)
    assert by_key[('linux', 'P1')]['task_class'] == 'k-P1'
    assert all(o['comparable'] for o in obs)
    assert dirs == {'P1': ['A_THEN_B', 'B_THEN_A'], 'P2': ['A_THEN_B', 'B_THEN_A']}


def test_validate_pairs_single_habitat_does_not_require_counterbalance():
    rows = pair('linux', 'P1', 'A_THEN_B', 1.0, 2.0)
    obs, dirs = af.validate_pairs(rows)
    assert len(obs) == 1
    assert dirs == {'P1': ['A_THEN_B']}


def _mutate(rows, idx, fn):
    rows = copy.deepcopy(rows)
    fn(rows[idx])
    return rows


@pytest.mark.parametrize('mutator, pattern', [
    (lambda r: r.update(variant='A'), 'FAIL pair variants linux/P1'),
    (lambda r: r.update(source_sha='zzz'), 'FAIL pair provenance mismatch linux/P1'),
    (lambda r: r.update(run_id='run-2'), 'FAIL pair provenance mismatch linux/P1'),
    (lambda r: r.update(semantic_digest='x'), 'FAIL semantic mismatch linux/P1'),
    (lambda r: r['workload'].update(kind='other'), 'FAIL workload equivalence linux/P1'),
    (lambda r: r['workload'].update(iterations=99), 'FAIL workload equivalence linux/P1'),
    (lambda r: r.update(disposition='REJECT'), 'FAIL rejected pair member linux/P1'),
    (lambda r: r.pop('execution_order'), 'FAIL missing pair-order contract linux/P1'),
    (lambda r: r['execution_order'].update(pair_direction='B_THEN_A'), 'FAIL missing pair-order contract linux/P1'),
    (lambda r: r['execution_order'].update(pair_position=1), 'FAIL pair-order positions linux/P1'),
    (lambda r: r['execution_order'].update(counterbalance_basis='RANDOM'), 'FAIL counterbalance basis linux/P1'),
])
def test_validate_pairs_rejects_contract_breaks(mutator, pattern):
    # index 1 is the B member of linux/P1 (A_THEN_B)
    rows = _mutate(good_rows(), 1, mutator)
    with pytest.raises(SystemExit, match=pattern):
        af.validate_pairs(rows)


def test_validate_pairs_unknown_direction_on_a():
    rows = good_rows()
    rows[0]['execution_order']['pair_direction'] = 'SIDEWAYS'
    rows[1]['execution_order']['pair_direction'] = 'SIDEWAYS'
    with pytest.raises(SystemExit, match='FAIL missing pair-order contract linux/P1'):
        af.validate_pairs(rows)


def test_validate_pairs_incomplete_pair():
    rows = good_rows()
    del rows[1]
    with pytest.raises(SystemExit, match='FAIL pair linux/P1 has 1 members'):
        af.validate_pairs(rows)


def test_validate_pairs_a_then_b_wrong_positions():
    rows = good_rows()
    rows[0]['execution_order']['pair_position'] = 2
    rows[1]['execution_order']['pair_position'] = 1
    with pytest.raises(SystemExit, match='FAIL A_THEN_B positions linux/P1'):
        af.validate_pairs(rows)


def test_validate_pairs_b_then_a_wrong_positions():
    rows = good_rows()
    # rows[2:4] are linux/P2 with B_THEN_A
    rows[2]['execution_order']['pair_position'] = 1
    rows[3]['execution_order']['pair_position'] = 2
    with pytest.raises(SystemExit, match='FAIL B_THEN_A positions linux/P2'):
        af.validate_pairs(rows)


def test_validate_pairs_not_counterbalanced_across_habitats():
    rows = pair('linux', 'P1', 'A_THEN_B', 1.0, 2.0) + pair('windows', 'P1', 'A_THEN_B', 1.0, 2.0)
    with pytest.raises(SystemExit, match=r"not counterbalanced across habitats for P1: \['A_THEN_B'\]"):
        af.validate_pairs(rows)


# ---------- BT ----------

def _obs(winner, a='alpha', b='beta'):
    return {'strategy_a': a, 'strategy_b': b, 'winner': winner}


def test_two_node_bt_abilities_symmetric():
    fa, fb = af.two_node_bt_abilities(8.0, 4.0)
    assert fa == -fb
    assert fa - fb == pytest.approx(math.log(8.5 / 4.5))


def test_bt_model_counts_wins_losses_ties():
    obs = [_obs('alpha'), _obs('alpha'), _obs('beta'), _obs('TIE')]
    bt = af.bt_model(obs)
    assert bt['status'] == 'READY_OBSERVED'
    assert bt['model'] == 'TWO_NODE_BT_LOG_ODDS_V1'
    assert bt['analytic_scale_fixture'] == 'PASS'
    assert bt['observed_pairs'] == 4
    assert bt['edges'] == obs
    nodes = {n['strategy']: n for n in bt['nodes']}
    assert nodes['alpha']['wins'] == 2.5 and nodes['alpha']['losses'] == 1.5 and nodes['alpha']['ties'] == 1
    assert nodes['beta']['wins'] == 1.5 and nodes['beta']['losses'] == 2.5
    assert nodes['alpha']['bt_log_strength'] > nodes['beta']['bt_log_strength']
    assert nodes['alpha']['normalized_strength'] + nodes['beta']['normalized_strength'] == pytest.approx(1.0)
    gap = nodes['alpha']['bt_log_strength'] - nodes['beta']['bt_log_strength']
    assert gap == pytest.approx(math.log(3.0 / 2.0))


def test_bt_model_defers_below_three_pairs():
    assert af.bt_model([_obs('alpha'), _obs('beta')])['status'] == 'DEFER_INSUFFICIENT_OBSERVED_PAIRS'


@pytest.mark.parametrize('obs', [
    [_obs('alpha', 'alpha', 'alpha')],
    [_obs('alpha'), _obs('gamma', 'gamma', 'beta')],
])
def test_bt_model_requires_exactly_two_strategies(obs):
    with pytest.raises(SystemExit, match='requires exactly two strategies'):
        af.bt_model(obs)


def test_bt_model_analytic_fixture_guard(monkeypatch):
    real = af.two_node_bt_abilities

    def doubled(wa, wb):
        x, y = real(wa, wb)
        return 2 * x, 2 * y

    monkeypatch.setattr(af, 'two_node_bt_abilities', doubled)
    with pytest.raises(SystemExit, match='FAIL BT analytic scale fixture'):
        af.bt_model([_obs('alpha'), _obs('beta'), _obs('TIE')])


# ---------- PCA ----------

def test_pca_model_ready_with_queue_feature():
    rows = good_rows()
    pca = af.pca_model(rows, {'linux': 10.0, 'windows': 30.0})
    assert pca['status'] == 'READY_MEASURED'
    assert pca['rows'] == len(rows)
    assert 'queue_delay_seconds' in pca['varying_features']
    assert 'habitat_windows' in pca['varying_features']
    assert 'worker_count' not in pca['varying_features']
    assert pca['feature_count'] == len(pca['varying_features'])
    assert [c['component'] for c in pca['components']] == ['PC1', 'PC2']
    ratios = [c['explained_variance_ratio'] for c in pca['components']]
    assert ratios[0] >= ratios[1] >= 0
    assert sum(ratios) <= 1.0 + 1e-9
    assert len(pca['scores']) == len(rows)
    assert set(pca['scores'][0]) == {'habitat', 'task_id', 'strategy', 'PC1', 'PC2'}
    # standardized scores are centered
    assert sum(s['PC1'] for s in pca['scores']) == pytest.approx(0.0, abs=1e-9)


def test_pca_model_defers_on_too_few_rows():
    pca = af.pca_model(good_rows()[:2], {})
    assert pca['status'] == 'DEFER_INSUFFICIENT_MEASURED_VARIANCE'
    assert pca['rows'] == 2


def test_pca_model_defers_on_single_varying_feature():
    rows = [receipt('linux', f't{i}', secs=float(i + 1)) for i in range(4)]
    pca = af.pca_model(rows, {})
    assert pca == {'status': 'DEFER_INSUFFICIENT_MEASURED_VARIANCE', 'rows': 4,
                   'varying_features': ['log_execute_ms']}


# ---------- main ----------

def test_main_writes_analysis_receipt(monkeypatch, tmp_path, capsys):
    rows = good_rows()
    rows[0]['rex_postflight']['recurrence_level'] = 'REGRESSION'
    rows[1]['rex_postflight']['preventive_action_effective'] = False
    queue = {'rows': [
        {'habitat': 'linux', 'queue_seconds_from_run_creation': 10},
        {'habitat': 'linux', 'queue_seconds_from_run_creation': 20},
        {'habitat': 'windows', 'queue_seconds_from_run_creation': 5},
        {'habitat': 'windows', 'queue_seconds_from_run_creation': None},
        {'queue_seconds_from_run_creation': 99},
    ]}
    out = run_main(monkeypatch, tmp_path, rows, queue)
    doc = json.loads(out.read_text(encoding='utf-8'))
    assert doc['schema'] == 'missioncontrol.crew_frontier_analysis_receipt.v1'
    assert doc['mission_id'] == 'M-1'
    assert doc['source_sha'] == 'abc123' and doc['run_id'] == 'run-1'
    assert doc['habitats'] == ['linux', 'windows']
    assert doc['task_receipts'] == 9 and doc['accepted'] == 9 and doc['rejected'] == 0
    assert doc['queue_telemetry'] == {'linux': 15.0, 'windows': 5.0}
    assert doc['experimental_design']['pair_order_control'] == 'PASS_COUNTERBALANCED'
    assert doc['pca']['status'] == 'READY_MEASURED'
    assert doc['bt']['status'] == 'READY_OBSERVED' and doc['bt']['observed_pairs'] == 4
    assert doc['rex'] == {'observed_event_count': 9, 'persistent_or_regression_count': 1,
                          'preventive_success_count': 8, 'checklist_version': 'CL-7'}
    assert doc['authority_transfer'] is False and doc['competency_promotions'] == 0
    summary = json.loads(capsys.readouterr().out.strip())
    assert summary['status'] == 'PASS_CREW_FRONTIER_PCA_BT_COUNTERBALANCED'
    assert summary['observed_pairs'] == 4
    assert summary['rex_events'] == 9


def test_main_no_receipts(monkeypatch, tmp_path):
    with pytest.raises(SystemExit, match='FAIL no frontier receipts'):
        run_main(monkeypatch, tmp_path, [])


@pytest.mark.parametrize('field', ['source_sha', 'run_id'])
def test_main_requires_single_sha_and_run(monkeypatch, tmp_path, field):
    rows = good_rows()
    rows[-1][field] = 'different'
    with pytest.raises(SystemExit, match='FAIL aggregate must be one exact SHA and one run'):
        run_main(monkeypatch, tmp_path, rows)


def test_main_rejected_task(monkeypatch, tmp_path):
    rows = good_rows()
    rows[-1]['disposition'] = 'REJECT'
    with pytest.raises(SystemExit, match='FAIL rejected frontier task'):
        run_main(monkeypatch, tmp_path, rows)


def test_main_pca_not_ready(monkeypatch, tmp_path):
    rows = []
    for pid in ('P1', 'P2', 'P3'):
        rows += pair('linux', pid, 'A_THEN_B', 1.0, 1.0)
    for r in rows:
        r['workload']['kind'] = 'same'
    with pytest.raises(SystemExit, match='FAIL PCA frontier did not reach measured readiness'):
        run_main(monkeypatch, tmp_path, rows)
    assert not (tmp_path / 'out.json').exists()


def test_main_bt_not_ready(monkeypatch, tmp_path):
    rows = pair('linux', 'P1', 'A_THEN_B', 1.0, 2.0, level=1, crew=1)
    rows += pair('windows', 'P1', 'B_THEN_A', 3.0, 1.0, level=2, crew=3)
    with pytest.raises(SystemExit, match='FAIL BT frontier did not reach observed readiness'):
        run_main(monkeypatch, tmp_path, rows)
