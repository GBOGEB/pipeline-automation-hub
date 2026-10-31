"""Behavioural tests for scripts/ppt_processor.py."""
import hashlib
import importlib.util
import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MOD_PATH = ROOT / 'scripts' / 'ppt_processor.py'


def _load():
    spec = importlib.util.spec_from_file_location('cw_ppt_processor_mod', MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pp = _load()

EPOCH = '1700000000'
EPOCH_ISO = '2023-11-14T22:13:20+00:00'


@pytest.fixture(autouse=True)
def _fixed_env(monkeypatch):
    monkeypatch.setenv('SOURCE_DATE_EPOCH', EPOCH)
    monkeypatch.delenv('PIPELINE_INPUT_DIR', raising=False)
    monkeypatch.delenv('PIPELINE_OUTPUT_DIR', raising=False)


def make_pptx(path, members=('[Content_Types].xml', 'ppt/presentation.xml')):
    with zipfile.ZipFile(path, 'w') as z:
        for m in members:
            z.writestr(m, '<x/>')
    return path


@pytest.fixture
def proc(tmp_path):
    inp = tmp_path / 'in'
    inp.mkdir()
    return pp.PPTProcessor(str(inp), str(tmp_path / 'out'))


# ---------------------------------------------------------------- _timestamp_now

def test_timestamp_uses_source_date_epoch():
    assert pp._timestamp_now() == EPOCH_ISO


def test_timestamp_rejects_non_integer_epoch(monkeypatch):
    monkeypatch.setenv('SOURCE_DATE_EPOCH', 'yesterday')
    with pytest.raises(ValueError, match='SOURCE_DATE_EPOCH must be an integer'):
        pp._timestamp_now()


def test_timestamp_falls_back_to_now(monkeypatch):
    monkeypatch.delenv('SOURCE_DATE_EPOCH')
    ts = pp._timestamp_now()
    assert ts.endswith('+00:00')
    assert ts != EPOCH_ISO


def test_default_dirs_relative_to_repo_root():
    assert pp.REPO_ROOT == ROOT
    assert pp.DEFAULT_INPUT_DIR == ROOT / 'app' / 'public' / 'master_input'
    assert pp.DEFAULT_OUTPUT_DIR == ROOT / 'app' / 'public' / 'outputs'


# ---------------------------------------------------------------- init / validation

def test_init_creates_output_subdirs(proc, tmp_path):
    for sub in ('metadata', 'digital_twins', 'cross_references'):
        assert (tmp_path / 'out' / sub).is_dir()


def test_validate_rejects_wrong_suffix(proc, tmp_path):
    with pytest.raises(ValueError, match='not a .pptx file: deck.ppt'):
        proc.validate_pptx_package(tmp_path / 'deck.ppt')


def test_validate_rejects_missing_file(proc, tmp_path):
    with pytest.raises(FileNotFoundError):
        proc.validate_pptx_package(tmp_path / 'missing.pptx')


def test_validate_rejects_non_zip(proc, tmp_path):
    f = tmp_path / 'fake.PPTX'
    f.write_bytes(b'not a zip at all')
    with pytest.raises(ValueError, match='not ZIP/OpenXML'):
        proc.validate_pptx_package(f)


def test_validate_rejects_zip_missing_members(proc, tmp_path):
    f = make_pptx(tmp_path / 'partial.pptx', members=('[Content_Types].xml',))
    with pytest.raises(ValueError, match=r"missing required OpenXML members: \['ppt/presentation.xml'\]"):
        proc.validate_pptx_package(f)


def test_validate_accepts_minimal_package(proc, tmp_path):
    assert proc.validate_pptx_package(make_pptx(tmp_path / 'ok.pptx')) is None


def test_validate_accepts_real_python_pptx_file(proc, tmp_path):
    pptx = pytest.importorskip('pptx')
    f = tmp_path / 'real.pptx'
    pptx.Presentation().save(str(f))
    proc.validate_pptx_package(f)


# ---------------------------------------------------------------- metadata heuristics

@pytest.mark.parametrize('name,category,priority,sub', [
    ('MINERVA_overview.pptx', 'SYSTEM_ARCHITECTURE', 'HIGH', 'CORE_SYSTEMS'),
    ('Our Values.pptx', 'VALUES_POLICY', 'HIGH', 'GOVERNANCE'),
    ('granting.pptx', 'PROJECT_STATUS', 'MEDIUM', 'PROGRESS_TRACKING'),
    ('naming_rules.pptx', 'STANDARDS', 'HIGH', 'DOCUMENTATION'),
    ('ped.pptx', 'COMPLIANCE', 'CRITICAL', 'REGULATORY'),
    ('buildings.pptx', 'INFRASTRUCTURE', 'MEDIUM', 'FACILITIES'),
    ('pressure.pptx', 'SYSTEMS', 'HIGH', 'OPERATIONS'),
    ('xyz.pptx', 'GENERAL', 'MEDIUM', 'MISC'),
])
def test_extract_filename_metadata_categories(proc, name, category, priority, sub):
    md = proc.extract_filename_metadata(name, 'T0')
    assert (md['category'], md['priority'], md['sub_category']) == (category, priority, sub)
    assert md['processing_timestamp'] == 'T0'
    assert md['content_parsed'] is False
    assert md['file_hash'] is None
    assert md['authority'] == 'METADATA_ONLY_NOT_DOCUMENT_TRUTH'


def test_extract_filename_metadata_normalizes_and_defaults_timestamp(proc):
    md = proc.extract_filename_metadata('a b&c (1).pptx')
    assert md['normalized_name'] == 'a_b_c__1_.pptx'
    assert md['processing_timestamp'] == EPOCH_ISO


def test_extract_cross_references(proc):
    refs = proc.extract_cross_references('minerva_values_qplant_naming_ped.pptx')
    assert [r['reference'] for r in refs] == [
        'SCK CEN/0245', 'SCK CEN/0156', 'SCK CEN/0789', 'SCK CEN/0334', 'SCK CEN/0567']
    assert all(r['authority'] == 'UNVERIFIED_CANDIDATE' and r['evidence_basis'] == 'filename_only'
               for r in refs)
    assert proc.extract_cross_references('xyz.pptx') == []


def test_generate_file_hash_matches_sha256(proc, tmp_path):
    f = tmp_path / 'blob.bin'
    payload = b'abc' * 5000
    f.write_bytes(payload)
    assert proc.generate_file_hash(f) == hashlib.sha256(payload).hexdigest()


def test_digital_twin_content(proc):
    md = proc.extract_filename_metadata('status.pptx', 'T1')
    refs = proc.extract_cross_references('status.pptx')
    twin = proc.create_digital_twin('status.pptx', md, refs)
    assert twin.startswith('# status\n')
    assert '**Category**: PROJECT_STATUS' in twin
    assert '- **SCK CEN/0789**: QPLANT Status' in twin
    assert '"keb_id": "status.pptx"' in twin
    assert '- **Created**: T1' in twin


def test_digital_twin_defaults_and_no_refs(proc):
    twin = proc.create_digital_twin('x.pptx', {'processing_timestamp': 'T'}, [])
    assert '**Category**: UNKNOWN' in twin
    assert '**Sub-category**: GENERAL' in twin
    assert '- No filename-derived candidate references' in twin
    assert '"keb_id": "x.pptx"' in twin


# ---------------------------------------------------------------- process_file / process_all_files

def test_process_file_writes_all_outputs(proc, tmp_path):
    f = make_pptx(tmp_path / 'in' / 'PED compliance.pptx')
    res = proc.process_file(f.name)
    assert res['processing_status'] == 'METADATA_ONLY_COMPLETED'
    assert res['content_parsed'] is False
    md = res['metadata']
    assert md['file_hash'] == hashlib.sha256(f.read_bytes()).hexdigest()
    assert md['file_size'] == f.stat().st_size
    assert md['pptx_package_validated'] is True
    out = tmp_path / 'out'
    saved = json.loads((out / 'metadata' / 'PED compliance_metadata.json').read_text(encoding='utf-8'))
    assert saved == md
    refs = json.loads((out / 'cross_references' / 'PED compliance_cross_refs.json').read_text(encoding='utf-8'))
    assert refs == res['cross_references'] and refs[0]['reference'] == 'SCK CEN/0567'
    twin = (out / 'digital_twins' / 'PED_compliance.md').read_text(encoding='utf-8')
    assert md['file_hash'] in twin


def test_process_file_rejects_invalid(proc, tmp_path):
    (tmp_path / 'in' / 'bad.pptx').write_bytes(b'nope')
    with pytest.raises(ValueError):
        proc.process_file('bad.pptx')
    assert not any((tmp_path / 'out' / 'metadata').iterdir())


def test_process_all_files_mixed(proc, tmp_path):
    inp = tmp_path / 'in'
    make_pptx(inp / 'minerva.pptx')
    make_pptx(inp / 'architecture2.pptx')
    make_pptx(inp / 'plain.pptx')
    (inp / 'broken.pptx').write_bytes(b'garbage')
    (inp / 'ignored.txt').write_text('x')
    res = proc.process_all_files()
    assert res['total_files'] == 4
    assert res['successful'] == 3
    assert res['failed'] == 1
    assert res['categories_summary'] == {'SYSTEM_ARCHITECTURE': 2, 'GENERAL': 1}
    assert res['cross_references_global'] == ['SCK CEN/0245']
    assert res['processing_started'] == EPOCH_ISO == res['processing_completed']
    bad = [r for r in res['files_processed'] if r['filename'] == 'broken.pptx'][0]
    assert bad['processing_status'] == 'REJECTED_OR_FAILED'
    assert 'not ZIP' in bad['error']
    summary = json.loads((tmp_path / 'out' / 'processing_summary.json').read_text(encoding='utf-8'))
    assert summary == res


def test_process_all_files_empty(proc, tmp_path):
    res = proc.process_all_files()
    assert (res['total_files'], res['successful'], res['failed']) == (0, 0, 0)
    assert res['categories_summary'] == {} and res['cross_references_global'] == []


# ---------------------------------------------------------------- CLI

def test_main_success_with_args(tmp_path, monkeypatch, capsys):
    inp = tmp_path / 'i'
    inp.mkdir()
    make_pptx(inp / 'naming.pptx')
    out = tmp_path / 'o'
    monkeypatch.setattr(sys, 'argv', ['ppt_processor', '--input-dir', str(inp), '--output-dir', str(out)])
    assert pp.main() == 0
    text = capsys.readouterr().out
    assert text.startswith('Starting legacy metadata-only PPTX processor...')
    payload = json.loads(text.split('\n', 1)[1])
    assert payload == {'scope': 'LEGACY_METADATA_ONLY', 'total_files': 1, 'successful': 1,
                       'failed': 0, 'output_dir': str(out.resolve())}


def test_main_env_dirs_and_failure_exit_code(tmp_path, monkeypatch, capsys):
    inp = tmp_path / 'ei'
    inp.mkdir()
    (inp / 'bad.pptx').write_bytes(b'x')
    out = tmp_path / 'eo'
    monkeypatch.setenv('PIPELINE_INPUT_DIR', str(inp))
    monkeypatch.setenv('PIPELINE_OUTPUT_DIR', str(out))
    monkeypatch.setattr(sys, 'argv', ['ppt_processor'])
    assert pp.main() == 2
    assert (out / 'processing_summary.json').exists()
    assert '"failed": 1' in capsys.readouterr().out


def test_parse_args_defaults_to_repo_paths(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['ppt_processor'])
    ns = pp._parse_args()
    assert ns.input_dir == str(pp.DEFAULT_INPUT_DIR)
    assert ns.output_dir == str(pp.DEFAULT_OUTPUT_DIR)
