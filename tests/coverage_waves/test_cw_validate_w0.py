"""Behavioural tests for mission-control/qps-triage-ultra/validate_w0.py."""
import hashlib
import importlib.util
import json
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MOD_PATH = REPO / 'mission-control' / 'qps-triage-ultra' / 'validate_w0.py'


def _load():
    spec = importlib.util.spec_from_file_location('cw_validate_w0_mod', MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


vw = _load()

GOOD = {
    'README.md': '# W0\nauthority_transfer: false\n',
    'architecture.yaml': 'coverage_floor: 0.8\n',
    'mission_registry.yaml': 'M01:\nM02A:\nM02B:\n',
    'resource_policy.yaml': 'x: 1\n',
    'metric_registry.yaml': 'pca: MEASURED_NUMERIC_ONLY\nbt: EXPLICIT_PAIRWISE_OUTCOMES_ONLY\n',
    'pulse_ledger.yaml': 'p: 1\n',
}


@pytest.fixture
def base(tmp_path, monkeypatch):
    for name, text in GOOD.items():
        (tmp_path / name).write_text(text, encoding='utf-8')
    monkeypatch.setattr(vw, 'BASE', tmp_path)
    calls = []

    def fake_check_output(cmd, text=False):
        calls.append(cmd)
        return 'headsha\n'

    monkeypatch.setattr(vw, 'subprocess', types.SimpleNamespace(check_output=fake_check_output))
    base_ns = types.SimpleNamespace(path=tmp_path, calls=calls)
    return base_ns


def test_module_paths_resolve_to_repo():
    assert vw.ROOT == REPO
    assert vw.BASE == REPO / 'mission-control' / 'qps-triage-ultra'
    assert len(vw.REQUIRED) == 6


def test_sha256(tmp_path):
    p = tmp_path / 'f'
    p.write_bytes(b'abc')
    assert vw.sha256(p) == hashlib.sha256(b'abc').hexdigest()


def test_head_uses_git(base):
    assert vw.head() == 'headsha'
    assert base.calls == [['git', 'rev-parse', 'HEAD']]


def test_main_pass(base, capsys):
    assert vw.main() == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt['status'] == 'PASS'
    assert receipt['head_sha'] == 'headsha'
    assert receipt['missing'] == []
    assert all(receipt['invariants'].values())
    assert receipt['digests']['README.md'] == vw.sha256(base.path / 'README.md')
    assert len(receipt['digests']) == 6
    assert receipt['authority_transfer'] is False


def test_alternate_authority_spelling(base, capsys):
    (base.path / 'README.md').write_text('authority_transfer=false\n', encoding='utf-8')
    assert vw.main() == 0


def test_main_missing_file(base, capsys):
    (base.path / 'pulse_ledger.yaml').unlink()
    assert vw.main() == 1
    receipt = json.loads(capsys.readouterr().out)
    assert receipt['status'] == 'FAIL'
    assert receipt['missing'] == ['pulse_ledger.yaml']
    assert 'pulse_ledger.yaml' not in receipt['digests']


@pytest.mark.parametrize('name,key', [
    ('README.md', 'authority_transfer_false'),
    ('architecture.yaml', 'coverage_floor_present'),
    ('mission_registry.yaml', 'active_M01'),
])
def test_main_invariant_failure(base, capsys, name, key):
    (base.path / name).write_text('nothing\n', encoding='utf-8')
    assert vw.main() == 1
    receipt = json.loads(capsys.readouterr().out)
    assert receipt['status'] == 'FAIL'
    assert receipt['invariants'][key] is False
    assert receipt['missing'] == []
