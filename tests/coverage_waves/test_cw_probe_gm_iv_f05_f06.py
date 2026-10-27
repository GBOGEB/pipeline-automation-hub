"""Behavioural tests for mission-control/grand-missions/probe_gm_iv_f05_f06.py."""
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MOD_PATH = REPO / 'mission-control' / 'grand-missions' / 'probe_gm_iv_f05_f06.py'


def _load():
    spec = importlib.util.spec_from_file_location('cw_probe_gm_iv_f05_f06_mod', MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


probe = _load()
STATE = probe.EXPECTED_CANONICAL_STATE


def _contract(**over):
    doc = {
        'canonical_state_must_remain': STATE,
        'promotion_allowed_by_this_pulse': False,
        'frontiers': [
            {'slot': 'GM-IV-F05', 'repository': 'org/f05', 'target_sha': 'a' * 40, 'return_path': 'ret/f05'},
            {'slot': 'GM-IV-F06', 'repository': 'org/f06', 'target_sha': 'b' * 40, 'return_path': 'ret/f06'},
        ],
    }
    doc.update(over)
    return doc


@pytest.fixture
def env(tmp_path, monkeypatch):
    root = tmp_path / 'repo' / 'mission-control' / 'grand-missions'
    root.mkdir(parents=True)
    contract = root / 'C.json'
    registry = root / 'R.json'
    contract.write_text(json.dumps(_contract()), encoding='utf-8')
    registry.write_text(json.dumps({'grand_missions': [{'id': 'GM-I', 'state': 'X'},
                                                       {'id': 'GM-IV', 'state': STATE}]}), encoding='utf-8')
    monkeypatch.setattr(probe, 'ROOT', root)
    monkeypatch.setattr(probe, 'CONTRACT', contract)
    monkeypatch.setattr(probe, 'REGISTRY', registry)
    f05 = tmp_path / 'f05'
    f06 = tmp_path / 'f06'
    for d in (f05, f06):
        (d / 'src').mkdir(parents=True)
        (d / 'src' / 'a.py').write_text('x', encoding='utf-8')
        (d / '.git').mkdir()
        (d / '.git' / 'HEAD').write_text('ref', encoding='utf-8')
    heads = {str(f05): 'a' * 40, str(f06): 'b' * 40}
    calls = []

    def fake_check_output(cmd, text=False):
        calls.append(cmd)
        return heads[cmd[2]] + '\n'

    monkeypatch.setattr(probe, 'subprocess', types.SimpleNamespace(check_output=fake_check_output))
    out = tmp_path / 'out' / 'deep' / 'receipt.json'
    argv = ['probe', '--f05', str(f05), '--f06', str(f06), '--source-sha', 'srcsha', '--out', str(out)]
    monkeypatch.setattr(sys, 'argv', argv)
    return types.SimpleNamespace(root=root, contract=contract, registry=registry, f05=f05, f06=f06,
                                 heads=heads, calls=calls, out=out)


def test_git_head_strips_and_uses_dash_c(env):
    assert probe.git_head(env.f05) == 'a' * 40
    assert env.calls[-1] == ['git', '-C', str(env.f05), 'rev-parse', 'HEAD']


def test_count_surface_excludes_git(tmp_path):
    (tmp_path / 'd1' / 'd2').mkdir(parents=True)
    (tmp_path / 'd1' / 'f.txt').write_text('1', encoding='utf-8')
    (tmp_path / 'top.txt').write_text('1', encoding='utf-8')
    (tmp_path / '.git' / 'objects').mkdir(parents=True)
    (tmp_path / '.git' / 'objects' / 'o').write_text('1', encoding='utf-8')
    assert probe.count_surface(tmp_path) == {'files': 2, 'directories': 2, 'entries': 4}


def test_count_surface_empty(tmp_path):
    assert probe.count_surface(tmp_path) == {'files': 0, 'directories': 0, 'entries': 0}


def test_canonical_state_reads_registry(env):
    assert probe.canonical_gm_iv_state() == STATE


def test_canonical_state_missing_gm_iv(env):
    env.registry.write_text(json.dumps({'grand_missions': [{'id': 'GM-I', 'state': 'X'}]}), encoding='utf-8')
    with pytest.raises(SystemExit, match='FAIL_GM_IV_MISSING_FROM_CANONICAL_REGISTRY'):
        probe.canonical_gm_iv_state()


def test_main_success_writes_receipt(env, capsys):
    assert probe.main() == 0
    assert capsys.readouterr().out.strip() == 'PASS_F05_F06_BOUNDED_RUNTIME_PROBE'
    raw = env.out.read_text(encoding='utf-8')
    assert raw.endswith('\n')
    receipt = json.loads(raw)
    assert receipt['source_control_sha'] == 'srcsha'
    assert receipt['canonical_state_before'] == receipt['canonical_state_after'] == STATE
    assert receipt['canonical_registry_path'].replace('\\', '/') == 'mission-control/grand-missions/R.json'
    assert receipt['promotion_allowed'] is False and receipt['formal_credit_delta'] == 0
    f05 = receipt['frontiers']['GM-IV-F05']
    assert f05['repository'] == 'org/f05'
    assert f05['observed_sha'] == f05['expected_sha'] == 'a' * 40
    assert f05['surface'] == {'files': 1, 'directories': 1, 'entries': 2}
    assert f05['return_path'] == 'ret/f05'
    assert receipt['frontiers']['GM-IV-F06']['observed_sha'] == 'b' * 40
    assert len(env.calls) == 2


def test_main_wrong_canonical_state(env):
    env.registry.write_text(json.dumps({'grand_missions': [{'id': 'GM-IV', 'state': 'ACTIVE_8_OF_8'}]}),
                            encoding='utf-8')
    with pytest.raises(SystemExit, match='FAIL_GM_IV_CANONICAL_STATE expected=.* actual=ACTIVE_8_OF_8'):
        probe.main()
    assert not env.out.exists()


def test_main_contract_registry_mismatch(env):
    env.contract.write_text(json.dumps(_contract(canonical_state_must_remain='OTHER')), encoding='utf-8')
    with pytest.raises(SystemExit, match='FAIL_GM_IV_CONTRACT_REGISTRY_STATE_MISMATCH'):
        probe.main()


@pytest.mark.parametrize('value', [True, None, 0])
def test_main_promotion_must_be_literal_false(env, value):
    env.contract.write_text(json.dumps(_contract(promotion_allowed_by_this_pulse=value)), encoding='utf-8')
    with pytest.raises(SystemExit, match='FAIL_GM_IV_PULSE_PROMOTION_MUST_BE_FALSE'):
        probe.main()


def test_main_sha_mismatch(env):
    env.heads[str(env.f06)] = 'c' * 40
    with pytest.raises(SystemExit, match='FAIL_GM-IV-F06_SHA expected=b+ actual=c+'):
        probe.main()
    assert not env.out.exists()


def test_main_zero_surface(env, tmp_path, monkeypatch):
    empty = tmp_path / 'empty'
    empty.mkdir()
    env.heads[str(empty)] = 'a' * 40
    argv = list(sys.argv)
    argv[2] = str(empty)
    monkeypatch.setattr(sys, 'argv', argv)
    with pytest.raises(SystemExit, match='FAIL_GM-IV-F05_ZERO_SURFACE'):
        probe.main()


def test_main_state_changed_during_probe(env, monkeypatch):
    states = iter([STATE, 'PROMOTED'])
    monkeypatch.setattr(probe, 'canonical_gm_iv_state', lambda: next(states))
    with pytest.raises(SystemExit, match='FAIL_GM_IV_CANONICAL_STATE_CHANGED before=.* after=PROMOTED'):
        probe.main()


def test_main_missing_required_args(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['probe', '--f05', 'x'])
    with pytest.raises(SystemExit) as exc:
        probe.main()
    assert exc.value.code == 2


def test_real_committed_contract_is_consistent():
    contract = json.loads(probe.CONTRACT.read_text(encoding='utf-8'))
    assert contract['canonical_state_must_remain'] == STATE
    assert contract['promotion_allowed_by_this_pulse'] is False
    assert {f['slot'] for f in contract['frontiers']} == {'GM-IV-F05', 'GM-IV-F06'}
    # The real registry is readable and GM-IV is present (its state may have moved on).
    assert isinstance(probe.canonical_gm_iv_state(), str)
