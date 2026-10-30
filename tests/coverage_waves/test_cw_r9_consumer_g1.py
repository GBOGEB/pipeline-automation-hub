"""Coverage wave r9: branch coverage for mission-control/gogreen/g5/consumer_g1.py."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_PATH = REPO_ROOT / "mission-control" / "gogreen" / "g5" / "consumer_g1.py"
_spec = importlib.util.spec_from_file_location("cw_r9_consumer_g1_mod", MOD_PATH)
m = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = m
_spec.loader.exec_module(m)

SOURCE = "a" * 40
RUN = 12345
JOB = 67890


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def members(report_over=None, manifest_over=None, html=None, logs=None):
    report = {"schema": "gogreen.federation.rollup.v1",
              "breadth_depth": {"repositories": 6, "target_repo_surface_cells": 66,
                                "source_discovered_cells": 13, "native_status_verified_cells": 0,
                                "artifact_bytes_verified_cells": 0, "unknown_cells": 53},
              "authority_transfer": False, "merge_authorized": False}
    report.update(report_over or {})
    mem = {"rollup.json": json.dumps(report).encode(),
           "rollup.html": html if html is not None else
           ("<html>" + SOURCE + " 13/66 DEFER</html>").encode(),
           "source_tests.log": b"Ran 1\n\nOK\n", "html_tests.log": b"Ran 1\n\nOK\n"}
    mem.update(logs or {})
    manifest = {"schema": "gogreen.federation.rollup.manifest.v1",
                "producer_source_sha": SOURCE, "native_run_id": RUN, "native_attempt": 1,
                "evidence_class": "PRODUCER_NATIVE_NOT_CONSUMER_ACCEPTED",
                "authority_transfer": False, "merge_authorized": False,
                "independent_downloaded_bytes_verified": False,
                "sha256": {x: _sha(mem[x]) for x in ("rollup.json", "rollup.html")}}
    manifest.update(manifest_over or {})
    mem["manifest.json"] = json.dumps(manifest).encode()
    return mem


def pack(mem, compression=zipfile.ZIP_DEFLATED, tweak=None, extra=()):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=compression) as z:
        for name, value in sorted(mem.items()):
            info = zipfile.ZipInfo(name)
            info.compress_type = compression
            if tweak and name in tweak:
                tweak[name](info)
            z.writestr(info, value)
        for name, value in extra:
            z.writestr(name, value)
    return buf.getvalue()


def check(raw, **kw):
    args = dict(expected_archive_sha256=_sha(raw), expected_source_sha=SOURCE,
                expected_run_id=RUN, expected_job_id=JOB)
    args.update(kw)
    return m.validate_archive(raw, **args)


def test_valid_archive_result_shape():
    raw = pack(members())
    out = check(raw)
    assert out["schema"] == m.SCHEMA
    p = out["producer"]
    assert p["head_sha"] == SOURCE and p["run_id"] == RUN and p["job_id"] == JOB
    assert p["archive_sha256"] == _sha(raw)
    assert p["rollup_sha256"] == _sha(members()["rollup.json"])
    assert out["merge_authorized"] is False and out["qps_disposition"] == "DEFER"
    assert out["consumer"]["status"] == "VERIFIED_DOWNLOADED_BYTES"


@pytest.mark.parametrize("raw", [bytearray(b"x"), b"x" * (m.MAX_ARCHIVE + 1)], ids=["bytearray", "oversize"])
def test_byte_budget(raw):
    with pytest.raises(ValueError, match="byte budget"):
        m.validate_archive(raw, expected_archive_sha256="0" * 64, expected_source_sha=SOURCE,
                           expected_run_id=RUN, expected_job_id=JOB)


def test_bad_hex_and_digest_mismatch():
    raw = pack(members())
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        check(raw, expected_archive_sha256="XYZ")
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        check(raw, expected_archive_sha256="0" * 64)


def test_invalid_source_sha():
    with pytest.raises(ValueError, match="pinned producer SHA"):
        check(pack(members()), expected_source_sha="A" * 40)


@pytest.mark.parametrize("run,job", [(True, JOB), (0, JOB), (RUN, "5"), (RUN, -1)])
def test_bad_run_job_ids(run, job):
    with pytest.raises(ValueError, match="run/job ID"):
        check(pack(members()), expected_run_id=run, expected_job_id=job)


def test_duplicate_member_rejected():
    with pytest.warns(UserWarning):
        raw = pack(members(), extra=[("rollup.json", b"{}")])
    with pytest.raises(ValueError, match="members changed"):
        check(raw)


def test_oversize_member_rejected():
    mem = members(logs={"source_tests.log": b"\nOK" + b"0" * m.MAX_MEMBER})
    raw = pack(mem)
    assert len(raw) < m.MAX_ARCHIVE
    with pytest.raises(ValueError, match="size/encryption"):
        check(raw)


def test_encrypted_flag_rejected():
    # zipfile resets flag_bits on write, so set the encryption bit in the central directory.
    raw = bytearray(pack(members(), compression=zipfile.ZIP_STORED))
    name = b"html_tests.log"
    pos = 0
    while True:
        pos = raw.index(b"PK", pos)
        if raw[pos + 46:pos + 46 + len(name)] == name:
            break
        pos += 4
    raw[pos + 8] |= 1
    raw = bytes(raw)
    with pytest.raises(ValueError, match="size/encryption"):
        check(raw)


def test_symlink_rejected():
    def link(info):
        info.external_attr = (0o120777 << 16)
    raw = pack(members(), tweak={"rollup.html": link})
    with pytest.raises(ValueError, match="symlink"):
        check(raw)


def test_crc_failure_rejected():
    mem = members()
    raw = bytearray(pack(mem, compression=zipfile.ZIP_STORED))
    needle = b"Ran 1\n\nOK\n"
    idx = raw.find(needle)
    raw[idx] = ord("X")
    raw = bytes(raw)
    with pytest.raises(ValueError, match="CRC/integrity"):
        check(raw)


def test_not_a_zip():
    with pytest.raises(ValueError, match="invalid ZIP encoding"):
        check(b"definitely not a zip")


@pytest.mark.parametrize("over,msg", [
    ({"schema": "x"}, "manifest schema"),
    ({"producer_source_sha": "b" * 40}, "provenance"),
    ({"native_run_id": RUN + 1}, "provenance"),
    ({"native_attempt": 2}, "run attempt"),
    ({"evidence_class": "ACCEPTED"}, "evidence class"),
    ({"merge_authorized": True}, "unauthorized approval"),
    ({"independent_downloaded_bytes_verified": None}, "unauthorized approval"),
    ({"sha256": {}}, "digest mismatch: rollup.json"),
])
def test_manifest_rejections(over, msg):
    with pytest.raises(ValueError, match=msg):
        check(pack(members(manifest_over=over)))


def test_html_digest_mismatch():
    mem = members()
    man = json.loads(mem["manifest.json"])
    man["sha256"]["rollup.html"] = "0" * 64
    mem["manifest.json"] = json.dumps(man).encode()
    with pytest.raises(ValueError, match="digest mismatch: rollup.html"):
        check(pack(mem))


def test_missing_sha256_map_rejected():
    mem = members()
    man = json.loads(mem["manifest.json"])
    del man["sha256"]
    mem["manifest.json"] = json.dumps(man).encode()
    with pytest.raises(ValueError, match="digest mismatch"):
        check(pack(mem))


@pytest.mark.parametrize("over,msg", [
    ({"schema": "other"}, "report source schema"),
    ({"breadth_depth": {"repositories": 6}}, "denominator"),
    ({"authority_transfer": True}, "owner authority"),
    ({"merge_authorized": None}, "owner authority"),
])
def test_report_rejections(over, msg):
    with pytest.raises(ValueError, match=msg):
        check(pack(members(report_over=over)))


def test_report_without_breadth_depth():
    mem = members()
    rep = json.loads(mem["rollup.json"])
    del rep["breadth_depth"]
    mem = members()
    raw_rep = json.dumps(rep).encode()
    mem["rollup.json"] = raw_rep
    man = json.loads(mem["manifest.json"])
    man["sha256"]["rollup.json"] = _sha(raw_rep)
    mem["manifest.json"] = json.dumps(man).encode()
    with pytest.raises(ValueError, match="denominator"):
        check(pack(mem))


@pytest.mark.parametrize("html", [
    b"<html>13/66 DEFER</html>",
    ("<html>" + SOURCE + " DEFER</html>").encode(),
    ("<html>" + SOURCE + " 13/66</html>").encode(),
])
def test_html_parity(html):
    with pytest.raises(ValueError, match="parity"):
        check(pack(members(html=html)))


@pytest.mark.parametrize("name", ["source_tests.log", "html_tests.log"])
def test_log_not_ok(name):
    with pytest.raises(ValueError, match="unittest log"):
        check(pack(members(logs={name: b"FAILED (errors=1)\n"})))


def test_emit_writes_all_files(tmp_path):
    out = check(pack(members()))
    d = tmp_path / "a" / "b"
    digest = m.emit(out, d)
    data = (d / "g1_consumer_receipt.json").read_bytes()
    assert _sha(data) == digest
    assert json.loads(data) == out
    assert (d / "g1_consumer_receipt.sha256").read_text(encoding="ascii") == digest + "\n"
    md = (d / "g1_consumer_receipt.md").read_text(encoding="utf-8")
    assert digest in md and "HOLD" in md
    page = (d / "g1_consumer_receipt.html").read_text(encoding="utf-8")
    assert SOURCE in page and str(RUN) in page and str(JOB) in page and digest in page
    assert m.emit(out, d) == digest  # idempotent, exist_ok


def test_main_cli(tmp_path, monkeypatch, capsys):
    raw = pack(members())
    zp = tmp_path / "a.zip"
    zp.write_bytes(raw)
    out = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", ["consumer_g1", "--zip", str(zp), "--archive-sha256", _sha(raw),
                                      "--source-sha", SOURCE, "--run-id", str(RUN),
                                      "--job-id", str(JOB), "--out", str(out)])
    m.main()
    res = json.loads(capsys.readouterr().out)
    assert res["consumer_proof"] == "PASS" and res["merge_authorized"] is False
    assert res["sha256"] == (out / "g1_consumer_receipt.sha256").read_text().strip()


def test_main_cli_rejects(tmp_path, monkeypatch):
    zp = tmp_path / "a.zip"
    zp.write_bytes(b"junk")
    monkeypatch.setattr(sys, "argv", ["consumer_g1", "--zip", str(zp), "--archive-sha256", _sha(b"junk"),
                                      "--source-sha", SOURCE, "--run-id", "1",
                                      "--job-id", "1", "--out", str(tmp_path / "o")])
    with pytest.raises(ValueError, match="invalid ZIP"):
        m.main()
    assert not (tmp_path / "o").exists()


def test_dunder_main_guard(tmp_path, monkeypatch, capsys):
    import runpy
    raw = pack(members())
    zp = tmp_path / "a.zip"
    zp.write_bytes(raw)
    monkeypatch.setattr(sys, "argv", ["consumer_g1", "--zip", str(zp), "--archive-sha256", _sha(raw),
                                      "--source-sha", SOURCE, "--run-id", str(RUN),
                                      "--job-id", str(JOB), "--out", str(tmp_path / "o")])
    runpy.run_path(str(MOD_PATH), run_name="__main__")
    assert json.loads(capsys.readouterr().out)["consumer_proof"] == "PASS"
    assert (tmp_path / "o" / "g1_consumer_receipt.html").is_file()
