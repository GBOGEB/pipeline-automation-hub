"""Coverage-wave tests for scripts/qps_satellite_adapter.py (loaded by path)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "qps_satellite_adapter.py"

_spec = importlib.util.spec_from_file_location("cw_r9_qps_satellite_adapter_mod", MODULE_PATH)
mod = importlib.util.module_from_spec(_spec)
sys.modules["cw_r9_qps_satellite_adapter_mod"] = mod
_spec.loader.exec_module(mod)

HASH_A = "a" * 64
HASH_B = "b" * 64


def _write(path: Path, obj) -> Path:
    path.write_text(json.dumps(obj), encoding="utf-8")
    return path


def _feedback(findings, **over):
    base = {
        "schema": mod.FEEDBACK_SCHEMA,
        "source": {"repository": mod.QPS_REPOSITORY},
        "target_repository": mod.SATELLITE_REPOSITORY,
        "correlation_id": "C-1",
        "findings": findings,
    }
    base.update(over)
    return base


# ---------- helpers ----------

def test_stable_id_and_hash_helpers():
    sid = mod._stable_id("x.txt", HASH_A)
    assert sid.startswith("SAT-") and len(sid) == 20
    assert sid == mod._stable_id("x.txt", HASH_A)
    assert sid != mod._stable_id("y.txt", HASH_A)
    assert mod._canonical_bytes({"b": 1, "a": "é"}) == '{"a":"é","b":1}'.encode("utf-8")
    assert len(mod._sha256_bytes(b"")) == 64


def test_normalize_cross_references_variants():
    assert mod._normalize_cross_references("nope") == []
    assert mod._normalize_cross_references(None) == []
    refs = mod._normalize_cross_references([
        "str-item",
        {"reference": "   "},
        {"reference": " z ", "context": " c ", "type": "  "},
        {"reference": "a"},
    ])
    assert refs == [
        {"reference": "a", "context": "", "type": "unknown"},
        {"reference": "z", "context": "c", "type": "unknown"},
    ]


# ---------- export ----------

def test_export_rejects_non_object(tmp_path):
    m = _write(tmp_path / "m.json", [1, 2])
    with pytest.raises(mod.AdapterError, match="JSON object"):
        mod.export_manifest(m, tmp_path / "o.json", "r", "s")


@pytest.mark.parametrize("manifest", [
    {},
    {"processing_summary": []},
    {"processing_summary": {"files_processed": {}}},
])
def test_export_rejects_bad_summary(tmp_path, manifest):
    m = _write(tmp_path / "m.json", manifest)
    with pytest.raises(mod.AdapterError, match="files_processed"):
        mod.export_manifest(m, tmp_path / "o.json", "r", "s")


def test_export_filters_and_sorts(tmp_path):
    manifest = {"processing_summary": {"files_processed": [
        "not-a-dict",
        {"metadata": "nope"},
        {"metadata": {"file_hash": HASH_A}},  # no path
        {"filename": "bad.txt", "metadata": {"file_hash": "xyz"}},  # bad hash
        {"filename": "Zeta.md", "metadata": {"file_hash": HASH_B.upper(), "file_type": "md"},
         "cross_references": [{"reference": "r1", "type": "doc"}], "processing_status": "OK"},
        {"filename": "ignored", "metadata": {"original_filename": "alpha.txt", "file_hash": HASH_A,
                                              "category": "C", "priority": "P1"}},
    ]}}
    m = _write(tmp_path / "m.json", manifest)
    out = tmp_path / "nested" / "out.json"
    payload = mod.export_manifest(m, out, "main", "abc")
    recs = payload["artifact_records"]
    assert [r["source_path"] for r in recs] == ["alpha.txt", "Zeta.md"]
    alpha, zeta = recs
    assert alpha["artifact_type"] == "UNKNOWN"
    assert alpha["category"] == "C" and alpha["priority"] == "P1"
    assert alpha["validation_status"] == "UNKNOWN"
    assert alpha["cross_references"] == []
    assert zeta["source_sha256"] == HASH_B
    assert zeta["artifact_type"] == "MD"
    assert zeta["validation_status"] == "OK"
    assert zeta["category"] == "UNKNOWN" and zeta["priority"] == "UNSET"
    assert zeta["cross_references"] == [{"reference": "r1", "context": "", "type": "doc"}]
    assert payload["source"]["ref"] == "main" and payload["source"]["sha"] == "abc"
    assert payload["source"]["manifest_path"] == "m.json"
    assert payload["governance"]["allowed_child_dispositions"] == ["ACCEPT", "DEFER", "REJECT"]
    on_disk = json.loads(out.read_text(encoding="utf-8"))
    assert on_disk == payload
    no_bridge = {k: v for k, v in payload.items() if k != "bridge_id"}
    assert payload["bridge_id"] == mod._sha256_bytes(mod._canonical_bytes(no_bridge))


# ---------- import_feedback ----------

@pytest.mark.parametrize("fb,msg", [
    ([], "feedback schema"),
    ({"schema": "other"}, "feedback schema"),
    ({"schema": mod.FEEDBACK_SCHEMA, "source": "x"}, "feedback source"),
    ({"schema": mod.FEEDBACK_SCHEMA, "source": {"repository": "other"}}, "feedback source"),
    (_feedback([], target_repository="other"), "target_repository"),
    (_feedback("notlist"), "findings must be an array"),
    (_feedback(["str"]), "each finding must be an object"),
    (_feedback([{"disposition": "MAYBE"}]), "invalid disposition"),
    (_feedback([{"disposition": "ACCEPT", "reusable_learning": True}]), "confidential=false"),
    (_feedback([{"disposition": "ACCEPT", "reusable_learning": True, "confidential": True}]),
     "confidential=false"),
])
def test_import_feedback_errors(tmp_path, fb, msg):
    f = _write(tmp_path / "f.json", fb)
    with pytest.raises(mod.AdapterError, match=msg):
        mod.import_feedback(f, tmp_path / "o.json")
    assert not (tmp_path / "o.json").exists()


def test_import_feedback_filters_and_sorts(tmp_path):
    findings = [
        {"disposition": "REJECT", "reusable_learning": True, "confidential": False, "finding_id": "R"},
        {"disposition": "DEFER", "finding_id": "D"},
        {"disposition": "ACCEPT", "reusable_learning": False, "finding_id": "NR"},
        {"disposition": "ACCEPT", "reusable_learning": "yes", "finding_id": "NR2"},
        {"disposition": "ACCEPT", "reusable_learning": True, "confidential": False, "finding_id": "F2",
         "learning_type": "PATTERN", "summary": "s", "source_reference": "ref"},
        {"disposition": "ACCEPT", "reusable_learning": True, "confidential": False, "finding_id": "F1"},
    ]
    f = _write(tmp_path / "f.json", _feedback(findings))
    out = tmp_path / "deep" / "o.json"
    res = mod.import_feedback(f, out)
    assert [item["finding_id"] for item in res["learnings"]] == ["F1", "F2"]
    f1, f2 = res["learnings"]
    assert f1["learning_type"] == "REGRESSION" and f1["summary"] == "" and f1["source_reference"] == ""
    assert f2["learning_type"] == "PATTERN" and f2["source_reference"] == "ref"
    assert all(item["authority"] == "REGRESSION_LEARNING_ONLY" and item["qps_disposition"] == "ACCEPT"
               for item in res["learnings"])
    assert res["correlation_id"] == "C-1"
    assert res["engineering_ssot_mutation_allowed"] is False
    assert json.loads(out.read_text(encoding="utf-8")) == res
    no_sha = {k: v for k, v in res.items() if k != "learning_sha256"}
    assert res["learning_sha256"] == mod._sha256_bytes(mod._canonical_bytes(no_sha))


def test_import_feedback_missing_correlation(tmp_path):
    fb = _feedback([])
    del fb["correlation_id"]
    res = mod.import_feedback(_write(tmp_path / "f.json", fb), tmp_path / "o.json")
    assert res["correlation_id"] == "" and res["learnings"] == []


# ---------- main ----------

def test_main_export(tmp_path, monkeypatch, capsys):
    m = _write(tmp_path / "m.json", {"processing_summary": {"files_processed": [
        {"filename": "a.txt", "metadata": {"file_hash": HASH_A}}]}})
    out = tmp_path / "o.json"
    monkeypatch.setattr(sys, "argv", ["prog", "export", "--manifest", str(m), "--output", str(out)])
    assert mod.main() == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["source"]["ref"] == "master" and printed["source"]["sha"] == "UNBOUND"
    assert printed == json.loads(out.read_text(encoding="utf-8"))


def test_main_import_feedback(tmp_path, monkeypatch, capsys):
    f = _write(tmp_path / "f.json", _feedback([]))
    out = tmp_path / "o.json"
    monkeypatch.setattr(sys, "argv", ["prog", "import-feedback", "--feedback", str(f), "--output", str(out)])
    assert mod.main() == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["schema"] == mod.LEARNING_SCHEMA
    assert out.exists()


def test_main_requires_command(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["prog"])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 2


def test_dunder_main_entrypoint(tmp_path, monkeypatch, capsys):
    import runpy

    f = _write(tmp_path / "f.json", _feedback([]))
    out = tmp_path / "o.json"
    monkeypatch.setattr(sys, "argv", ["prog", "import-feedback", "--feedback", str(f), "--output", str(out)])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(MODULE_PATH), run_name="__main__")
    assert exc.value.code == 0
    assert json.loads(capsys.readouterr().out)["schema"] == mod.LEARNING_SCHEMA
