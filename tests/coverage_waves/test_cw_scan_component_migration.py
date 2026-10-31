"""Behavioural tests for crew/measured/frontier/pc3/scan_component_migration.py."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MOD_PATH = (REPO / 'mission-control' / 'qps-triage-ultra' / 'crew' / 'measured' / 'frontier'
            / 'pc3' / 'scan_component_migration.py')


def _load():
    spec = importlib.util.spec_from_file_location('cw_scan_component_migration_mod', MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


scm = _load()


def _component(name, loadings, evr=0.1):
    top = sorted(loadings.items(), key=lambda kv: abs(kv[1]), reverse=True)
    return {'component': name, 'explained_variance_ratio': evr, 'loadings': loadings,
            'top_absolute_loadings': [{'feature': k, 'loading': v} for k, v in top]}


def _components(pressure_pc='PC3', pressure_strength=1.0):
    comps = []
    for i in range(1, 6):
        name = 'PC%d' % i
        loadings = {'noise_a': 0.3, 'noise_b': -0.3}
        if name == 'PC1':
            loadings.update({'log_execute_ms': 0.9, 'cache_reused': -0.8})
        if name == 'PC2':
            loadings.update({'worker_count': 0.9, 'crew_size': 0.9})
        if name == 'PC4':
            loadings.update({'rex_exposure_count': -0.9, 'task_level': 0.7})
        if name == pressure_pc:
            loadings.update({'admission_proxy_seconds': pressure_strength, 'lane_held': -pressure_strength})
        comps.append(_component(name, loadings, evr=0.5 / i))
    return comps


def _run(tmp_path, monkeypatch, components, source_extra=None):
    src = {'source_sha': 'abc', 'run_id': 'r1',
           'pca': {'components': components, 'pc3_pressure_hypothesis': 'H'}}
    src.update(source_extra or {})
    analysis = tmp_path / 'a.json'
    out = tmp_path / 'o.json'
    analysis.write_text(json.dumps(src), encoding='utf-8')
    monkeypatch.setattr(sys, 'argv', ['scm', '--analysis', str(analysis), '--out', str(out)])
    scm.main()
    return json.loads(out.read_text(encoding='utf-8'))


def test_component_share_basic():
    comp = {'loadings': {'a': 1.0, 'b': -3.0, 'c': '0'}}
    assert scm.component_share(comp, {'b'}) == pytest.approx(0.75)
    assert scm.component_share(comp, {'missing'}) == 0.0


def test_component_share_all_zero_uses_unit_total():
    assert scm.component_share({'loadings': {'a': 0.0}}, {'a'}) == 0.0
    assert scm.component_share({'loadings': {}}, {'a'}) == 0.0


def test_pressure_detected_on_pc3(tmp_path, monkeypatch, capsys):
    doc = _run(tmp_path, monkeypatch, _components('PC3'))
    assert doc['pressure_disposition'] == 'DETECTED_PC3'
    axes = doc['axes']
    assert axes['admission_human_dependency_pressure']['detected_component'] == 'PC3'
    assert axes['execution_reuse_pressure']['detected_component'] == 'PC1'
    assert axes['execution_reuse_pressure']['status'] == 'DETECTED'
    assert axes['parallelism_crew_scale']['detected_component'] == 'PC2'
    assert axes['rex_difficulty_workload']['detected_component'] == 'PC4'
    pressure = axes['admission_human_dependency_pressure']
    assert sorted(pressure['features_in_top5']) == ['admission_proxy_seconds', 'lane_held']
    assert pressure['threshold'] == 0.40
    scan = pressure['component_scan']
    assert len(scan) == 5
    shares = [r['absolute_loading_share'] for r in scan]
    assert shares == sorted(shares, reverse=True)
    assert doc['pc3_pressure_hypothesis'] == 'H'
    assert doc['source_sha'] == 'abc' and doc['run_id'] == 'r1'
    assert doc['authority_transfer'] is False
    printed = json.loads(capsys.readouterr().out)
    assert printed['status'] == 'PASS_COMPONENT_MIGRATION_SCAN'
    assert printed['pressure_component'] == 'PC3'
    assert printed['parallelism_component'] == 'PC2'


def test_pressure_detected_elsewhere(tmp_path, monkeypatch):
    doc = _run(tmp_path, monkeypatch, _components('PC5'))
    assert doc['pressure_disposition'] == 'DETECTED_PC5_NOT_PC3'


def test_pressure_diffuse(tmp_path, monkeypatch):
    doc = _run(tmp_path, monkeypatch, _components('PC3', pressure_strength=0.1))
    assert doc['axes']['admission_human_dependency_pressure']['status'] == 'DIFFUSE'
    assert doc['pressure_disposition'] == 'NO_DOMINANT_PRESSURE_COMPONENT_PC1_PC5'


def test_requires_five_components(tmp_path, monkeypatch):
    with pytest.raises(SystemExit, match='requires PC1-PC5'):
        _run(tmp_path, monkeypatch, _components()[:4])
    assert not (tmp_path / 'o.json').exists()
