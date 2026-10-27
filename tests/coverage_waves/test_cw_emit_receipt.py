"""Behavioural tests for mission-control/qps-triage-ultra/emit_receipt.py (runs at import)."""
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MOD_PATH = REPO / 'mission-control' / 'qps-triage-ultra' / 'emit_receipt.py'


def _run(monkeypatch, argv):
    monkeypatch.setattr(sys, 'argv', ['emit_receipt'] + argv)
    spec = importlib.util.spec_from_file_location('cw_emit_receipt_mod', MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_emits_receipt_with_env(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('GITHUB_RUN_ID', '12345')
    monkeypatch.setenv('GITHUB_RUN_ATTEMPT', '2')
    out = tmp_path / 'nested' / 'dir' / 'r.json'
    mod = _run(monkeypatch, ['--source-sha', 'abc', '--outcome', 'success', '--out', str(out)])
    raw = out.read_text(encoding='utf-8')
    assert raw.endswith('\n')
    receipt = json.loads(raw)
    assert receipt == mod.receipt
    assert receipt['schema'] == 'qps-fleet-receipt/v1'
    assert receipt['mission_id'] == 'ULTRA'
    assert receipt['source_sha'] == 'abc'
    assert receipt['execution']['outcome'] == 'SUCCESS'
    assert receipt['execution']['workflow_run_id'] == '12345'
    assert receipt['execution']['workflow_run_attempt'] == '2'
    assert receipt['authority_transfer'] is False and receipt['engineering_acceptance'] is False
    assert datetime.fromisoformat(receipt['observed_at']).tzinfo is not None
    assert json.loads(capsys.readouterr().out) == receipt


def test_unbound_without_env(tmp_path, monkeypatch):
    monkeypatch.delenv('GITHUB_RUN_ID', raising=False)
    monkeypatch.delenv('GITHUB_RUN_ATTEMPT', raising=False)
    out = tmp_path / 'r.json'
    _run(monkeypatch, ['--source-sha', 's', '--outcome', 'Failure', '--out', str(out)])
    receipt = json.loads(out.read_text(encoding='utf-8'))
    assert receipt['execution']['workflow_run_id'] == 'UNBOUND'
    assert receipt['execution']['workflow_run_attempt'] == 'UNBOUND'
    assert receipt['execution']['outcome'] == 'FAILURE'


def test_missing_required_argument(tmp_path, monkeypatch):
    with pytest.raises(SystemExit) as exc:
        _run(monkeypatch, ['--source-sha', 's', '--out', str(tmp_path / 'r.json')])
    assert exc.value.code == 2
    assert not (tmp_path / 'r.json').exists()
