"""Behavioural tests for mission-control/federation-atlas/flightdeck/office_export.py."""
import copy
import importlib.util
import json
import sys
import types
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MOD_DIR = ROOT / 'mission-control' / 'federation-atlas' / 'flightdeck'
MOD_PATH = MOD_DIR / 'office_export.py'


def _load():
    if str(MOD_DIR) not in sys.path:
        sys.path.insert(0, str(MOD_DIR))
    spec = importlib.util.spec_from_file_location('cw_office_export_mod', MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


oe = _load()

SHA = 'a' * 64


def make_census(unknown=36, matched=2, stale=3):
    repos = [
        {'name': 'repo%d' % i, 'short': 'R%d' % i, 'role': 'role %d' % i,
         'inputs': 'in%d' % i, 'outputs': 'out%d' % i, 'boundaries': 'b%d' % i}
        for i in range(6)
    ]
    cells = []
    for i in range(42):
        status = 'UNKNOWN_NOT_OBSERVED' if i < unknown else 'OBSERVED_STATUS_ONLY'
        cells.append({
            'id': 'BD-%02d' % i, 'repository': 'repo%d' % (i % 6), 'family': 'fam%d' % (i % 7),
            'family_label': 'Family %d' % (i % 7), 'status': status, 'source_sha': 'sha%d' % i,
            'run_id': str(1000 + i), 'job_id': str(2000 + i), 'owner_role': 'owner',
            'next_action': 'act', 'victory_predicate': 'pred',
            'repo_url': 'https://github.com/x/repo%d' % (i % 6),
            'bd_authority': 'https://github.com/x/bd/%d' % i,
        })
    anchors = []
    for i in range(5):
        status = 'MATCHES_SNAPSHOT' if i < matched else ('STALE_ANCHOR' if i < matched + stale else 'OTHER')
        anchors.append({
            'repository': 'repo%d' % i, 'source_anchor': 's%d' % i, 'observed_main_sha': 'm%d' % i,
            'status': status, 'protected_on_snapshot': True, 'next_action': 'refresh',
            'repo_branch_url': 'https://github.com/x/repo%d/tree/main' % i,
        })
    pipeline = [
        {'id': 'P%d' % i, 'group': 'g', 'name': 'stage %d' % i, 'trigger': 't', 'command': 'python x.py',
         'inputs': 'i', 'outputs': 'o', 'gate': 'gate'}
        for i in range(3)
    ]
    controls = [{'id': 'C%d' % i, 'name': 'ctrl %d' % i, 'threshold': 'thr <%d>' % i, 'response': 'resp'}
                for i in range(2)]
    return {
        'schema': 'missioncontrol.flightdeck.census.v1',
        'cells': cells, 'anchors': anchors, 'pipeline': pipeline, 'controls': controls,
        'repositories': repos,
        'metrics': {'unobserved_cells': unknown},
        'engineering_accepted': False,
        'source_semantic_sha256': SHA,
        'exact_checkout_sha': None,
        'snapshot_observed_at_utc': '2026-10-01T00:00:00',
    }


def write_census(tmp_path, data, name='census.json'):
    p = tmp_path / name
    p.write_text(json.dumps(data), encoding='utf-8')
    return p


# ---------------------------------------------------------------- load()

def test_load_accepts_qualified_census(tmp_path):
    data = make_census()
    got = oe.load(write_census(tmp_path, data))
    assert got == data


@pytest.mark.parametrize('mutate', [
    lambda d: d.__setitem__('schema', 'other.v1'),
    lambda d: d['cells'].pop(),
    lambda d: d['anchors'].pop(),
    lambda d: d['metrics'].__setitem__('unobserved_cells', 35),
    lambda d: d.pop('metrics'),
    lambda d: d.__setitem__('engineering_accepted', True),
    lambda d: d.pop('engineering_accepted'),
    lambda d: d.__setitem__('engineering_accepted', 0),
])
def test_load_rejects_unqualified_census(tmp_path, mutate):
    data = make_census()
    mutate(data)
    with pytest.raises(ValueError, match='Unqualified binary input census'):
        oe.load(write_census(tmp_path, data))


def test_load_rejects_missing_cells_and_anchors(tmp_path):
    data = make_census()
    del data['cells']
    with pytest.raises(ValueError):
        oe.load(write_census(tmp_path, data))


# ---------------------------------------------------------------- xlsx()

def test_xlsx_writes_sheets_formulas_and_seeded_caches(tmp_path):
    openpyxl = pytest.importorskip('openpyxl')
    data = make_census(unknown=30, matched=1, stale=2)
    out = tmp_path / 'reg.xlsx'
    oe.xlsx(data, out)
    assert out.exists()
    assert not (tmp_path / 'reg.cached-tmp.xlsx').exists()

    wb = openpyxl.load_workbook(out)
    assert wb.sheetnames == ['Overview', 'Evidence 42', 'Anchors 5', 'Pipeline', 'Doc Control', 'Sources']
    ov = wb['Overview']
    assert ov['B2'].value == SHA
    assert ov['B3'].value == 'LOCAL_UNBOUND'
    assert ov['B6'].value.startswith('=COUNTA(')
    assert ov.freeze_panes == 'B6'
    ev = wb['Evidence 42']
    assert ev.max_row == 43
    assert ev['A2'].value == 'BD-00'
    assert ev.freeze_panes == 'A2'
    assert ev.auto_filter.ref == 'A1:L43'
    assert ev['K2'].hyperlink is not None
    assert wb['Doc Control'].auto_filter.ref is None
    assert wb['Anchors 5'].max_row == 6
    assert wb['Pipeline'].max_row == 4

    cached = openpyxl.load_workbook(out, data_only=True)['Overview']
    assert [cached['B%d' % r].value for r in range(6, 11)] == [42, 12, 30, 1, 2]
    with zipfile.ZipFile(out) as z:
        assert b'fullCalcOnLoad="1"' in z.read('xl/workbook.xml')


def test_xlsx_uses_exact_checkout_sha_when_present(tmp_path):
    openpyxl = pytest.importorskip('openpyxl')
    data = make_census()
    data['exact_checkout_sha'] = 'deadbeef'
    out = tmp_path / 'x.xlsx'
    oe.xlsx(data, out)
    assert openpyxl.load_workbook(out)['Overview']['B3'].value == 'deadbeef'


def test_xlsx_raises_when_formula_cache_not_found(tmp_path, monkeypatch):
    pytest.importorskip('openpyxl')
    import re as real_re
    fake_re = types.ModuleType('re')
    fake_re.subn = lambda *a, **k: (a[2], 0)
    monkeypatch.setitem(sys.modules, 're', fake_re)
    with pytest.raises(ValueError, match='Formula cache not uniquely found: B6'):
        oe.xlsx(make_census(), tmp_path / 'bad.xlsx')
    monkeypatch.setitem(sys.modules, 're', real_re)


# ---------------------------------------------------------------- docx()

def test_docx_contains_repositories_pipeline_and_controls(tmp_path):
    docx_mod = pytest.importorskip('docx')
    data = make_census()
    out = tmp_path / 'r.docx'
    oe.docx(data, out)
    d = docx_mod.Document(str(out))
    text = '\n'.join(p.text for p in d.paragraphs)
    assert 'Federation Flight Deck' in text
    for r in data['repositories']:
        assert r['short'] in text
        assert 'Boundary: ' + r['boundaries'] in text
    assert 'P0 · stage 0' in text
    assert 'C1  ctrl 1' in text
    assert 'Source semantic SHA-256: ' + SHA in text
    assert d.tables[0].rows[1].cells[1].text == SHA
    assert 'Not an approved engineering document' in d.sections[0].footer.paragraphs[0].text


# ---------------------------------------------------------------- pdf()

def test_pdf_builds_document(tmp_path):
    pytest.importorskip('reportlab')
    data = make_census()
    out = tmp_path / 'b.pdf'
    oe.pdf(data, out)
    raw = out.read_bytes()
    assert raw.startswith(b'%PDF')
    assert raw.rstrip().endswith(b'%%EOF')
    assert b'/Count ' in raw


# ---------------------------------------------------------------- main()

class FakeCompleted:
    def __init__(self, returncode, stderr=''):
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = ''


def _stub_writers(monkeypatch, calls):
    for name in ('xlsx', 'docx', 'pdf'):
        monkeypatch.setattr(oe, name, lambda data, path, _n=name: calls.append((_n, Path(path).name)))


def test_main_success_invokes_all_producers(tmp_path, monkeypatch, capsys):
    calls = []
    _stub_writers(monkeypatch, calls)
    seen = {}

    def fake_run(cmd, capture_output, text):
        seen['cmd'] = cmd
        return FakeCompleted(0)

    monkeypatch.setattr(oe.subprocess, 'run', fake_run)
    src = write_census(tmp_path, make_census())
    out = tmp_path / 'out' / 'nested'
    rc = oe.main(['--input', str(src), '--out', str(out)])
    assert rc == 0
    assert out.is_dir()
    assert calls == [('xlsx', 'evidence_register.xlsx'), ('docx', 'federation_report.docx'),
                     ('pdf', 'linked_evidence_book.pdf')]
    assert seen['cmd'][0] == 'node'
    assert seen['cmd'][1].endswith('slides.js')
    assert seen['cmd'][3] == str(out / 'mission_brief.pptx')
    payload = json.loads(capsys.readouterr().out)
    assert payload['status'] == 'PASS'
    assert payload['source_semantic_sha256'] == SHA
    assert 'mission_brief.pptx' in payload['files']


def test_main_raises_when_pptx_producer_fails(tmp_path, monkeypatch):
    _stub_writers(monkeypatch, [])
    monkeypatch.setattr(oe.subprocess, 'run', lambda *a, **k: FakeCompleted(1, 'x' * 2000 + 'BOOM'))
    src = write_census(tmp_path, make_census())
    with pytest.raises(RuntimeError, match='PPTX producer failed: x+BOOM') as ei:
        oe.main(['--input', str(src), '--out', str(tmp_path / 'o')])
    assert len(str(ei.value)) == len('PPTX producer failed: ') + 1800


def test_main_rejects_bad_census_before_writing(tmp_path, monkeypatch):
    calls = []
    _stub_writers(monkeypatch, calls)
    monkeypatch.setattr(oe.subprocess, 'run', lambda *a, **k: pytest.fail('should not run'))
    data = make_census()
    data['engineering_accepted'] = True
    with pytest.raises(ValueError):
        oe.main(['--input', str(write_census(tmp_path, data)), '--out', str(tmp_path / 'o')])
    assert calls == []
    assert not (tmp_path / 'o').exists()


def test_main_requires_arguments(monkeypatch):
    with pytest.raises(SystemExit) as ei:
        oe.main([])
    assert ei.value.code == 2


def test_main_end_to_end_real_writers(tmp_path, monkeypatch):
    pytest.importorskip('openpyxl')
    pytest.importorskip('docx')
    pytest.importorskip('reportlab')
    monkeypatch.setattr(oe.subprocess, 'run', lambda *a, **k: FakeCompleted(0))
    src = write_census(tmp_path, copy.deepcopy(make_census()))
    out = tmp_path / 'deliver'
    assert oe.main(['--input', str(src), '--out', str(out)]) == 0
    assert sorted(p.name for p in out.iterdir()) == [
        'evidence_register.xlsx', 'federation_report.docx', 'linked_evidence_book.pdf']
