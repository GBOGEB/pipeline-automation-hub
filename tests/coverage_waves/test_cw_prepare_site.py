"""Behavioural tests for mission-control/qps-triage-ultra/site/scripts/prepare_site.py."""
import importlib.util
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MOD_PATH = REPO / 'mission-control' / 'qps-triage-ultra' / 'site' / 'scripts' / 'prepare_site.py'


def _load():
    spec = importlib.util.spec_from_file_location('cw_prepare_site_mod', MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ps = _load()

ENV_VARS = ('GITHUB_SHA', 'QPS_SOURCE_SHA', 'QPS_RELEASE_ID', 'QPS_EVIDENCE_STATE')


@pytest.fixture
def env(tmp_path, monkeypatch):
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    out = tmp_path / '_data' / 'qps_build.yml'
    out.parent.mkdir()
    monkeypatch.setattr(ps, 'OUT', out)
    calls = []
    state = {'result': 'deadbeefcafe0123456789\n', 'raise': None}

    def fake_check_output(cmd, text=False):
        calls.append(cmd)
        if state['raise']:
            raise state['raise']
        return state['result']

    monkeypatch.setattr(ps, 'subprocess', types.SimpleNamespace(check_output=fake_check_output))
    return types.SimpleNamespace(out=out, calls=calls, state=state, mp=monkeypatch)


def _yaml(path):
    lines = path.read_text(encoding='utf-8').split('\n')
    assert lines[-1] == ''
    return dict(line.split(': ', 1) for line in lines[:-1])


def test_root_points_at_site_dir():
    assert ps.ROOT.name == 'site'
    assert ps.OUT == ps.ROOT / '_data' / 'qps_build.yml'


def test_git_sha_prefers_github_sha(env):
    env.mp.setenv('GITHUB_SHA', '  ghsha  ')
    env.mp.setenv('QPS_SOURCE_SHA', 'qps')
    assert ps.git_sha() == 'ghsha'
    assert env.calls == []


def test_git_sha_falls_back_to_qps_source_sha(env):
    env.mp.setenv('QPS_SOURCE_SHA', 'qpssha')
    assert ps.git_sha() == 'qpssha'


def test_git_sha_from_git(env):
    assert ps.git_sha() == 'deadbeefcafe0123456789'
    assert env.calls == [['git', 'rev-parse', 'HEAD']]


def test_git_sha_unbound_on_error(env):
    env.state['raise'] = OSError('no git')
    assert ps.git_sha() == 'UNBOUND'


def test_main_bound_defaults(env, capsys):
    assert ps.main() == 0
    data = _yaml(env.out)
    assert data == {'release_id': 'qps-web-deadbeefcafe', 'source_sha': 'deadbeefcafe0123456789',
                    'schema_version': 'qps.web.publication.v1', 'evidence_state': 'OBSERVED'}
    out = capsys.readouterr().out
    assert 'release_id=qps-web-deadbeefcafe' in out and 'source_sha=deadbeefcafe0123456789' in out


def test_main_unbound(env):
    env.state['raise'] = RuntimeError('boom')
    assert ps.main() == 2
    data = _yaml(env.out)
    assert data['release_id'] == 'qps-web-unbound'
    assert data['source_sha'] == 'UNBOUND'
    assert data['evidence_state'] == 'DRAFT'


def test_main_env_overrides(env):
    env.mp.setenv('GITHUB_SHA', 'abc')
    env.mp.setenv('QPS_RELEASE_ID', 'rel-7')
    env.mp.setenv('QPS_EVIDENCE_STATE', 'VERIFIED')
    assert ps.main() == 0
    data = _yaml(env.out)
    assert data['release_id'] == 'rel-7'
    assert data['evidence_state'] == 'VERIFIED'
    assert data['source_sha'] == 'abc'
