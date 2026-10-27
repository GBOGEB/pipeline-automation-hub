"""Behavioural tests for mission-control/federation-atlas/superstitch/visual_pattern_scanner.py."""
import hashlib
import importlib.util
import json
import runpy
import sys
from pathlib import Path

import pytest

Image = pytest.importorskip('PIL.Image')
ImageDraw = pytest.importorskip('PIL.ImageDraw')

REPO = Path(__file__).resolve().parents[2]
MOD_PATH = REPO / 'mission-control' / 'federation-atlas' / 'superstitch' / 'visual_pattern_scanner.py'


def _load():
    spec = importlib.util.spec_from_file_location('cw_visual_pattern_scanner_mod', MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


vps = _load()


def _boxes(path, size=(400, 460)):
    img = Image.new('RGB', size, 'white')
    draw = ImageDraw.Draw(img)
    for y in range(20, size[1] - 60, 60):
        draw.rectangle([20, y, size[0] - 20, y + 40], outline='black', width=2)
    img.save(path)
    return path


def _blank(path, size=(400, 460)):
    # Uniform black: FIND_EDGES yields no response anywhere (white would light up the border).
    Image.new('RGB', size, 'black').save(path)
    return path


def _dot_lattice(path, size=(400, 460)):
    # Dark dot every 3px on white: ~89% of pixels see a strong positive edge response.
    img = Image.new('L', size, 255)
    px = img.load()
    for x in range(0, size[0], 3):
        for y in range(0, size[1], 3):
            px[x, y] = 0
    img.save(path)
    return path


def test_scan_pass_writes_report(tmp_path):
    img = _boxes(tmp_path / 'render.png')
    out = tmp_path / 'scan.json'
    report = vps.scan(str(img), str(out), expected_width=400)
    assert report['status'] == 'LOCAL_PIXEL_PATTERN_PASS'
    assert report['image'] == 'render.png'
    assert report['width'] == 400 and report['height'] == 460
    assert report['sha256'] == hashlib.sha256(img.read_bytes()).hexdigest()
    assert 0.005 <= report['edge_ratio'] <= 0.65
    assert report['edge_pixels'] > 0
    assert 0 < report['mean_luminance'] <= 255
    assert report['text_ocr_performed'] is False and report['engineering_credit'] is False
    assert json.loads(out.read_text()) == report


def test_scan_without_expected_width(tmp_path):
    img = _boxes(tmp_path / 'r.png', size=(500, 500))
    assert vps.scan(img, tmp_path / 'o.json')['width'] == 500


def test_width_mismatch(tmp_path):
    img = _boxes(tmp_path / 'r.png')
    with pytest.raises(ValueError, match='SCREENSHOT_WIDTH_MISMATCH'):
        vps.scan(img, tmp_path / 'o.json', expected_width=390)


@pytest.mark.parametrize('size', [(389, 460), (400, 449)])
def test_too_small(tmp_path, size):
    img = _boxes(tmp_path / 'r.png', size=size)
    with pytest.raises(ValueError, match='UNREADABLE_OR_TOO_SMALL_RENDER'):
        vps.scan(img, tmp_path / 'o.json')


def test_no_edges(tmp_path):
    img = _blank(tmp_path / 'r.png')
    with pytest.raises(ValueError, match='NO_STRUCTURAL_EDGES_DETECTED'):
        vps.scan(img, tmp_path / 'o.json')
    assert not (tmp_path / 'o.json').exists()


def test_overcomplex_noise(tmp_path):
    img = _dot_lattice(tmp_path / 'r.png')
    with pytest.raises(ValueError, match='OVERCOMPLEX_NOISE_LIKELY'):
        vps.scan(img, tmp_path / 'o.json')


def test_cli_entrypoint(tmp_path, monkeypatch, capsys):
    img = _boxes(tmp_path / 'r.png')
    out = tmp_path / 'o.json'
    monkeypatch.setattr(sys, 'argv', ['vps', '--image', str(img), '--out', str(out), '--width', '400'])
    runpy.run_path(str(MOD_PATH), run_name='__main__')
    printed = json.loads(capsys.readouterr().out)
    assert printed['status'] == 'LOCAL_PIXEL_PATTERN_PASS'
    assert out.exists()
