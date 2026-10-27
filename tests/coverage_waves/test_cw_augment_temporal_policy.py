"""Behavioural tests for crew/measured/frontier/temporal/augment_temporal_policy.py."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MOD_PATH = (REPO / 'mission-control' / 'qps-triage-ultra' / 'crew' / 'measured' / 'frontier'
            / 'temporal' / 'augment_temporal_policy.py')


def _load():
    spec = importlib.util.spec_from_file_location('cw_augment_temporal_policy_mod', MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


atp = _load()


def _policy():
    return {
        'schema': 'old',
        'status': 'PASS_TEMPORAL',
        'independent_windows': 3,
        'distinct_source_shas': 2,
        'competency_promotions': 9,
        'authority_transfer': True,
        'policies': {
            'a': {'policy_status': 'CONTROL_POLICY'},
            'b': {'policy_status': 'RECOMMEND_REPEAT_STABLE'},
            'c': {'policy_status': 'RECOMMEND_REPEAT_STABLE'},
            'd': {'policy_status': 'OTHER'},
        },
    }


def _window(**over):
    doc = {
        'status': 'PASS_CONSTRAINED_HABITAT_WINDOW',
        'authority_transfer': False,
        'competency_promotions': 0,
        'runner': {'environment': 'self-hosted-constrained'},
        'conditional_pair_edges': 5,
        'task_receipts': 12,
    }
    doc.update(over)
    return doc


def _run(tmp_path, monkeypatch, discovery=None, window=None, window_arg=True):
    policy = tmp_path / 'policy.json'
    disc = tmp_path / 'disc.json'
    out = tmp_path / 'out.json'
    policy.write_text(json.dumps(_policy()), encoding='utf-8')
    disc.write_text(json.dumps(discovery if discovery is not None else
                               {'status': 'NO_CONSTRAINED_RUNNER', 'declared_labels': ['x'],
                                'matched_runner': None}), encoding='utf-8')
    argv = ['atp', '--policy', str(policy), '--discovery', str(disc), '--out', str(out)]
    win = tmp_path / 'window.json'
    if window is not None:
        win.write_text(json.dumps(window), encoding='utf-8')
    if window_arg:
        argv += ['--constrained-window', str(win)]
    monkeypatch.setattr(sys, 'argv', argv)
    atp.main()
    return json.loads(out.read_text(encoding='utf-8'))


def test_no_window_argument(tmp_path, monkeypatch, capsys):
    doc = _run(tmp_path, monkeypatch, window_arg=False)
    ext = doc['constrained_runner_extension']
    assert ext == {'status': 'NO_CONSTRAINED_RUNNER', 'declared_labels': ['x'], 'matched_runner': None,
                   'real_constrained_habitat_observed': False, 'window': None,
                   'policy_effect': 'NONE_UNTIL_REAL_ASSIGNMENT', 'authority_transfer': False}
    assert doc['schema'] == 'missioncontrol.temporal_allocation_policy_receipt.v1.1'
    assert doc['competency_promotions'] == 0 and doc['authority_transfer'] is False
    assert 'augmented_at' in doc
    printed = json.loads(capsys.readouterr().out)
    assert printed == {'status': 'PASS_TEMPORAL', 'windows': 3, 'distinct_shas': 2,
                       'constrained': 'NO_CONSTRAINED_RUNNER', 'control_policies': 1, 'repeat_stable': 2}


def test_discovery_defaults(tmp_path, monkeypatch):
    doc = _run(tmp_path, monkeypatch, discovery={}, window_arg=False)
    ext = doc['constrained_runner_extension']
    assert ext['status'] is None and ext['declared_labels'] == [] and ext['matched_runner'] is None


def test_window_path_missing_is_ignored(tmp_path, monkeypatch):
    doc = _run(tmp_path, monkeypatch, window=None, window_arg=True)
    assert doc['constrained_runner_extension']['real_constrained_habitat_observed'] is False


def test_valid_window_extends_policy(tmp_path, monkeypatch, capsys):
    win = _window()
    doc = _run(tmp_path, monkeypatch, window=win)
    ext = doc['constrained_runner_extension']
    assert ext['status'] == 'REAL_CONSTRAINED_HABITAT_OBSERVED'
    assert ext['real_constrained_habitat_observed'] is True
    assert ext['window'] == win
    assert ext['policy_effect'] == 'ROBUSTNESS_EXTENSION_ONLY'
    assert ext['declared_labels'] == ['x']
    assert json.loads(capsys.readouterr().out)['constrained'] == 'REAL_CONSTRAINED_HABITAT_OBSERVED'


@pytest.mark.parametrize('over,msg', [
    ({'status': 'FAIL'}, 'constrained window status'),
    ({'authority_transfer': True}, 'authority/promotion boundary'),
    ({'authority_transfer': None}, 'authority/promotion boundary'),
    ({'competency_promotions': 1}, 'authority/promotion boundary'),
    ({'runner': {'environment': 'github-hosted'}}, 'runner environment'),
    ({'runner': None}, None),
    ({'conditional_pair_edges': 4}, 'coverage'),
    ({'task_receipts': 11}, 'coverage'),
])
def test_invalid_window_rejected(tmp_path, monkeypatch, over, msg):
    win = _window(**over)
    if over.get('runner', 1) is None:
        del win['runner']
        msg = 'runner environment'
    with pytest.raises(SystemExit, match=msg):
        _run(tmp_path, monkeypatch, window=win)
    assert not (tmp_path / 'out.json').exists()
