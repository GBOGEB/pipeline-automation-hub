"""Coverage-wave behavioural tests for mission-control/golden-thread/office_semantic_carrier.py.

Targets what test_office_semantic_carrier.py misses: package/XML validation
errors, relationship id collision handling, every extract() integrity check,
inject() guard rails and the CLI entry point. Packages are synthetic OPC ZIPs
built with the stdlib, so no python-docx/openpyxl/pptx is needed.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GT_DIR = REPO_ROOT / "mission-control" / "golden-thread"
if str(GT_DIR) not in sys.path:
    sys.path.insert(0, str(GT_DIR))

_spec = importlib.util.spec_from_file_location("cw_office_semantic_carrier", GT_DIR / "office_semantic_carrier.py")
osc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(osc)

CT_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Override PartName="/word/document.xml" ContentType="application/xml"/>'
    "</Types>"
)
RELS_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="x" Target="word/document.xml"/>'
    "</Relationships>"
)
TRUTH = {"schema": "cw.truth", "value": 1}


def make_pkg(path, parts=None, drop=()):
    base = {
        osc.CONTENT_TYPES: CT_XML,
        osc.ROOT_RELS: RELS_XML,
        "word/document.xml": "<document/>",
    }
    base.update(parts or {})
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in base.items():
            if name not in drop:
                zf.writestr(name, data)
    return path


def read_parts(path):
    with zipfile.ZipFile(path) as zf:
        return {n: zf.read(n) for n in zf.namelist()}


def carrier(tmp_path, truth=TRUTH, name="c.docx"):
    src = make_pkg(tmp_path / "src.docx")
    dst = tmp_path / name
    osc.inject(src, dst, truth)
    return dst


def rewrite(src, dst, **replacements):
    parts = read_parts(src)
    for key, value in replacements.items():
        name = {"truth": osc.TRUTH_PART, "manifest": osc.MANIFEST_PART}[key]
        parts[name] = value if isinstance(value, bytes) else json.dumps(value).encode()
    with zipfile.ZipFile(dst, "w") as zf:
        for n, d in parts.items():
            zf.writestr(n, d)
    return dst


# ------------------------------------------------------------------ primitives


def test_truth_bytes_requires_object_and_is_canonical():
    assert osc.truth_bytes({"b": 1, "a": "é"}) == '{"a":"é","b":1}'.encode("utf-8")
    with pytest.raises(osc.OfficeSemanticError, match="truth must be an object"):
        osc.truth_bytes([1])


def test_detect_format_case_insensitive_and_rejects_unknown():
    assert osc.detect_format(Path("A.PPTX")) == ("pptx", "ppt/presentation.xml")
    with pytest.raises(osc.OfficeSemanticError, match="supported Office formats are .docx, .xlsx and .pptx"):
        osc.detect_format(Path("a.odt"))


def test_read_package_rejects_non_zip_and_missing_parts(tmp_path):
    junk = tmp_path / "j.docx"
    junk.write_bytes(b"not a zip")
    with pytest.raises(osc.OfficeSemanticError, match="not an OOXML ZIP package"):
        osc._read_package(junk)
    for missing in (osc.CONTENT_TYPES, osc.ROOT_RELS, "word/document.xml"):
        p = make_pkg(tmp_path / "m.docx", drop=(missing,))
        with pytest.raises(osc.OfficeSemanticError, match=re.escape(f"docx: missing required package part {missing}")):
            osc._read_package(p)


def test_xml_root_parse_error_and_wrong_root():
    with pytest.raises(osc.OfficeSemanticError, match="invalid XML in package control part"):
        osc._xml_root(b"<broken", "Types")
    with pytest.raises(osc.OfficeSemanticError, match="unexpected XML root other"):
        osc._xml_root(b"<other/>", "Types")


def test_update_content_types_overwrites_existing_override():
    ns = osc.CONTENT_TYPES_NS
    data = (f'<Types xmlns="{ns}"><Override PartName="/{osc.TRUTH_PART}" ContentType="text/plain"/></Types>').encode()
    root = osc._xml_root(osc._update_content_types(data), "Types")
    overrides = {c.attrib["PartName"]: c.attrib["ContentType"] for c in root}
    assert overrides == {"/" + osc.TRUTH_PART: "application/json", "/" + osc.MANIFEST_PART: "application/json"}


def test_update_root_rels_replaces_old_carrier_rels_and_avoids_id_collisions():
    ns = osc.RELS_NS
    data = (
        f'<Relationships xmlns="{ns}">'
        '<Relationship Id="rIdGoldenThreadTruth" Type="x" Target="a"/>'
        '<Relationship Id="rIdGoldenThreadTruth2" Type="y" Target="b"/>'
        f'<Relationship Id="old" Type="{osc.REL_TYPE_MANIFEST}" Target="c"/>'
        "</Relationships>"
    ).encode()
    root = osc._xml_root(osc._update_root_rels(data), "Relationships")
    rels = [(r.attrib["Id"], r.attrib["Type"]) for r in root]
    assert rels == [
        ("rIdGoldenThreadTruth", "x"),
        ("rIdGoldenThreadTruth2", "y"),
        ("rIdGoldenThreadTruth3", osc.REL_TYPE_TRUTH),
        ("rIdGoldenThreadManifest", osc.REL_TYPE_MANIFEST),
    ]


def test_manifest_digest_and_optional_parent():
    m = osc._manifest(TRUTH, "docx", None)
    assert "parent_truth_digest" not in m
    body = {k: v for k, v in m.items() if k != "manifest_digest"}
    assert m["manifest_digest"] == osc.sha256_bytes(osc.canonical_json(body).encode())
    assert osc._manifest(TRUTH, "docx", "sha256:p")["parent_truth_digest"] == "sha256:p"


# ------------------------------------------------------------------ extract integrity


def test_extract_requires_carrier_parts(tmp_path):
    p = make_pkg(tmp_path / "plain.docx")
    with pytest.raises(osc.OfficeSemanticError, match="Golden Thread semantic carrier parts are missing"):
        osc.extract(p)


def test_extract_rejects_invalid_json_and_non_objects(tmp_path):
    good = carrier(tmp_path)
    bad = rewrite(good, tmp_path / "b1.docx", truth=b"\xff\xfe")
    with pytest.raises(osc.OfficeSemanticError, match="invalid Golden Thread JSON part"):
        osc.extract(bad)
    bad = rewrite(good, tmp_path / "b2.docx", manifest=b"{nope")
    with pytest.raises(osc.OfficeSemanticError, match="invalid Golden Thread JSON part"):
        osc.extract(bad)
    bad = rewrite(good, tmp_path / "b3.docx", truth=[1])
    with pytest.raises(osc.OfficeSemanticError, match="Golden Thread truth/manifest must be objects"):
        osc.extract(bad)


@pytest.mark.parametrize("field,value,message", [
    ("schema", "x", "semantic carrier schema mismatch"),
    ("format", "xlsx", "semantic carrier format mismatch"),
    ("authority_transfer", True, "semantic carrier authority_transfer must remain false"),
    ("visual_fidelity_credit", True, "semantic carrier may not grant visual fidelity credit"),
    ("truth_digest", "sha256:0", "truth digest mismatch"),
    ("manifest_digest", "sha256:0", "manifest digest mismatch"),
])
def test_extract_manifest_checks(tmp_path, field, value, message):
    good = carrier(tmp_path)
    manifest = json.loads(read_parts(good)[osc.MANIFEST_PART])
    manifest[field] = value
    bad = rewrite(good, tmp_path / "bad.docx", manifest=manifest)
    with pytest.raises(osc.OfficeSemanticError, match=message):
        osc.extract(bad)


# ------------------------------------------------------------------ inject guard rails


def test_inject_rejects_same_path_and_extension_mismatch(tmp_path):
    src = make_pkg(tmp_path / "s.docx")
    with pytest.raises(osc.OfficeSemanticError, match="source and destination must be different paths"):
        osc.inject(src, src, TRUTH)
    with pytest.raises(osc.OfficeSemanticError, match="destination extension must match source Office format"):
        osc.inject(src, tmp_path / "d.xlsx", TRUTH)


def test_reinject_new_truth_links_parent_and_preserves_other_parts(tmp_path):
    first = carrier(tmp_path, name="v1.docx")
    v1_digest = osc.truth_digest(TRUTH)
    out = tmp_path / "nested" / "v2.docx"
    new_truth = {"schema": "cw.truth", "value": 2}
    res = osc.inject(first, out, new_truth)
    assert res["status"] == "WRITTEN"
    assert res["parent_truth_digest"] == v1_digest
    parts = read_parts(out)
    assert parts["word/document.xml"] == b"<document/>"
    assert json.loads(parts[osc.MANIFEST_PART])["parent_truth_digest"] == v1_digest
    # Relationships are rewritten rather than duplicated on re-injection.
    rels = osc._xml_root(parts[osc.ROOT_RELS], "Relationships")
    assert sorted(r.attrib["Type"] for r in rels).count(osc.REL_TYPE_TRUTH) == 1


def test_inject_explicit_parent_digest_wins(tmp_path):
    first = carrier(tmp_path, name="v1.docx")
    res = osc.inject(first, tmp_path / "v2.docx", {"v": 3}, parent_truth_digest="sha256:explicit")
    assert res["parent_truth_digest"] == "sha256:explicit"


def test_inject_post_verification_failure(tmp_path, monkeypatch):
    src = make_pkg(tmp_path / "s.docx")
    real = osc.extract

    def tampered(path):
        out = real(path)
        out["truth"] = {"tampered": True}
        return out

    monkeypatch.setattr(osc, "extract", tampered)
    with pytest.raises(osc.OfficeSemanticError, match="post-injection semantic verification failed"):
        osc.inject(src, tmp_path / "d.docx", TRUTH)


# ------------------------------------------------------------------ CLI


def _truth_file(tmp_path, value, name="truth.json"):
    p = tmp_path / name
    p.write_text(json.dumps(value), encoding="utf-8")
    return p


def test_main_inject_extract_verify_roundtrip(tmp_path, capsys, monkeypatch):
    src = make_pkg(tmp_path / "s.docx")
    dst = tmp_path / "d.docx"
    tf = _truth_file(tmp_path, TRUTH)
    monkeypatch.setattr(sys, "argv", ["office_semantic_carrier.py", "inject", str(src), str(dst), str(tf),
                                      "--parent-truth-digest", "sha256:p"])
    assert osc.main() == 0
    injected = json.loads(capsys.readouterr().out)
    assert (injected["status"], injected["parent_truth_digest"]) == ("WRITTEN", "sha256:p")

    assert osc.main(["extract", str(dst)]) == 0
    assert json.loads(capsys.readouterr().out)["truth"] == TRUTH

    assert osc.main(["verify", str(dst), str(tf)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "PASS"


def test_main_failures_return_2(tmp_path, capsys):
    dst = carrier(tmp_path)
    other = _truth_file(tmp_path, {"other": 1}, "other.json")
    assert osc.main(["verify", str(dst), str(other)]) == 2
    assert capsys.readouterr().err == "FAIL: Office semantic delta detected\n"

    listy = _truth_file(tmp_path, [1], "list.json")
    assert osc.main(["verify", str(dst), str(listy)]) == 2
    assert capsys.readouterr().err == "FAIL: truth JSON must be an object\n"

    assert osc.main(["extract", str(tmp_path / "missing.docx")]) == 2
    assert capsys.readouterr().err.startswith("FAIL: ")
