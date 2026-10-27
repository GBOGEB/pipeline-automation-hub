"""Behavioural tests for crew/measured/frontier/temporal/analyze_constrained_habitat.py."""
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MOD_PATH = (REPO / 'mission-control' / 'qps-triage-ultra' / 'crew' / 'measured' / 'frontier'
            / 'temporal' / 'analyze_constrained_habitat.py')


def _load():
    spec = importlib.util.spec_from_file_location('cw_analyze_constrained_habitat_mod', MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ach = _load()
SHA = 'f' * 40
CLASSES = sorted(ach.TASK_CLASSES)
# (seconds_a, seconds_b) per class: b-wins, a-wins, tie, a-wins, b-wins
TIMES = [(2.0, 1.0), (1.0, 2.0), (1.0, 1.01), (0.5, 3.0), (4.0, 2.0)]


def _row(i, pair_id=None, variant=None, task_class='short_compute', secs=1.0, strategy='s', digest='d'):
    return {
        'source_sha': SHA,
        'disposition': 'ACCEPT',
        'run_id': 'run-7',
        'habitat': {'id': 'hab-c', 'lane': 'lane-x',
                    'runner': {'environment': 'self-hosted-constrained', 'name': 'box-1'}},
        'pair_id': pair_id,
        'variant': variant,
        'task_class': task_class,
        'execute_seconds': secs,
        'allocation_strategy': strategy,
        'semantic_digest': digest,
        'idx': i,
    }


def _rows():
    rows = []
    for n, (cls, (ta, tb)) in enumerate(zip(CLASSES, TIMES)):
        pid = 'P%d' % n
        # write variant B first to prove sorting by variant
        rows.append(_row(len(rows), pid, 'B', cls, tb, 'strat_b', 'dg%d' % n))
        rows.append(_row(len(rows), pid, 'A', cls, ta, 'strat_a', 'dg%d' % n))
    rows.append(_row(len(rows)))
    rows.append(_row(len(rows), pair_id=''))
    return rows


def _write(root, rows):
    root.mkdir(parents=True, exist_ok=True)
    for i, r in enumerate(rows):
        (root / ('t%02d__PC3-F%02d.json' % (i, i))).write_text(json.dumps(r), encoding='utf-8')


@pytest.fixture
def env(tmp_path, monkeypatch):
    calls = []

    def fake_check_output(cmd, text=False):
        calls.append(cmd)
        return SHA + '\n'

    monkeypatch.setattr(ach, 'subprocess', types.SimpleNamespace(check_output=fake_check_output))
    root = tmp_path / 'in'
    out = tmp_path / 'out.json'
    monkeypatch.setattr(sys, 'argv', ['ach', '--input-root', str(root), '--out', str(out)])
    return types.SimpleNamespace(root=root, out=out, calls=calls)


def test_main_success(env, capsys):
    _write(env.root, _rows())
    (env.root / 'ignored.json').write_text('{}', encoding='utf-8')
    ach.main()
    assert env.calls == [['git', 'rev-parse', 'HEAD']]
    doc = json.loads(env.out.read_text(encoding='utf-8'))
    assert doc['status'] == 'PASS_CONSTRAINED_HABITAT_WINDOW'
    assert doc['source_sha'] == SHA
    assert doc['run_id'] == 'run-7' and doc['habitat_id'] == 'hab-c' and doc['lane'] == 'lane-x'
    assert doc['runner']['name'] == 'box-1'
    assert set(doc['by_task_class']) == ach.TASK_CLASSES
    assert len(doc['edges']) == 5
    winners = {e['task_class']: e['winner'] for e in doc['edges']}
    expected = {}
    for cls, (ta, tb) in zip(CLASSES, TIMES):
        if abs(ta - tb) / max(ta, tb) < 0.02:
            expected[cls] = 'TIE'
        else:
            expected[cls] = 'strat_a' if ta < tb else 'strat_b'
    assert winners == expected
    assert 'TIE' in winners.values()
    edge0 = doc['edges'][0]
    assert edge0['pair_id'] == 'P0' and edge0['strategy_a'] == 'strat_a'
    assert edge0['execute_seconds_a'] == TIMES[0][0]
    assert edge0['relative_gap'] == pytest.approx(0.5)
    assert doc['authority_transfer'] is False and doc['competency_promotions'] == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed == {'status': 'PASS_CONSTRAINED_HABITAT_WINDOW', 'source_sha': SHA,
                       'pairs': 5, 'runner': 'box-1'}


def test_zero_times_use_epsilon_and_tie(env):
    rows = _rows()
    rows[0]['execute_seconds'] = 0
    rows[1]['execute_seconds'] = 0
    _write(env.root, rows)
    ach.main()
    doc = json.loads(env.out.read_text(encoding='utf-8'))
    assert doc['edges'][0]['winner'] == 'TIE'
    assert doc['edges'][0]['relative_gap'] == 0


def test_wrong_receipt_count(env):
    _write(env.root, _rows()[:11])
    with pytest.raises(SystemExit, match='expected=12 actual=11'):
        ach.main()


@pytest.mark.parametrize('field,value', [('source_sha', 'other'), ('disposition', 'REJECT')])
def test_sha_or_disposition_mismatch(env, field, value):
    rows = _rows()
    rows[3][field] = value
    _write(env.root, rows)
    with pytest.raises(SystemExit, match='exact-SHA/acceptance'):
        ach.main()


def test_runner_environment_not_constrained(env):
    rows = _rows()
    rows[5]['habitat'] = {}
    _write(env.root, rows)
    with pytest.raises(SystemExit, match='not self-hosted-constrained'):
        ach.main()


def test_pair_with_wrong_member_count(env):
    rows = _rows()
    rows[-1]['pair_id'] = 'P0'
    _write(env.root, rows)
    with pytest.raises(SystemExit, match='FAIL P0 expected two members'):
        ach.main()


def test_semantic_mismatch(env):
    rows = _rows()
    rows[2]['semantic_digest'] = 'different'
    _write(env.root, rows)
    with pytest.raises(SystemExit, match='semantic mismatch P1'):
        ach.main()


def test_task_class_mismatch_between_members(env):
    rows = _rows()
    rows[0]['task_class'] = CLASSES[1]
    _write(env.root, rows)
    with pytest.raises(SystemExit, match='FAIL task class P0'):
        ach.main()


def test_unknown_task_class(env):
    rows = _rows()
    rows[0]['task_class'] = rows[1]['task_class'] = 'bogus'
    _write(env.root, rows)
    with pytest.raises(SystemExit, match='FAIL task class P0'):
        ach.main()


def test_missing_class_coverage(env):
    rows = _rows()
    # Pair P4 duplicates P0's class, so one class is uncovered
    rows[8]['task_class'] = rows[9]['task_class'] = CLASSES[0]
    _write(env.root, rows)
    with pytest.raises(SystemExit, match='FAIL constrained classes actual='):
        ach.main()
    assert not env.out.exists()
