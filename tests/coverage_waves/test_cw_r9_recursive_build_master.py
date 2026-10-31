"""Coverage-wave tests for scripts/Recursive_Build_Master.py (loaded by path)."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import runpy
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "Recursive_Build_Master.py"
_SPEC = importlib.util.spec_from_file_location("cw_r9_recursive_build_master_mod", MODULE_PATH)
assert _SPEC and _SPEC.loader
MOD = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = MOD
_SPEC.loader.exec_module(MOD)

TS = "2026-09-18T15:00:00Z"


@pytest.fixture
def outputs(tmp_path):
    root = tmp_path / "outputs"
    (root / "metadata").mkdir(parents=True)
    (root / "cross_references").mkdir()
    return root


def _meta(root: Path, stem: str, payload: dict) -> Path:
    path = root / "metadata" / f"{stem}_metadata.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


# ---------------------------------------------------------------- helpers


def test_sha256_file_matches_hashlib(tmp_path):
    p = tmp_path / "f.bin"
    p.write_bytes(b"hello world")
    assert MOD.sha256_file(p) == hashlib.sha256(b"hello world").hexdigest()


def test_source_date_epoch_unset_and_empty(monkeypatch):
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
    assert MOD.source_date_epoch() is None
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "")
    assert MOD.source_date_epoch() is None


def test_source_date_epoch_valid(monkeypatch):
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "86400")
    assert MOD.source_date_epoch() == 86400


def test_source_date_epoch_invalid(monkeypatch):
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "not-a-number")
    with pytest.raises(ValueError, match="SOURCE_DATE_EPOCH must be an integer"):
        MOD.source_date_epoch()


def test_deterministic_timestamp_explicit_with_offset():
    assert MOD.deterministic_timestamp("2026-01-01T02:00:00+02:00") == "2026-01-01T00:00:00Z"
    assert MOD.deterministic_timestamp(TS) == TS


def test_deterministic_timestamp_from_epoch(monkeypatch):
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "0")
    assert MOD.deterministic_timestamp() == "1970-01-01T00:00:00Z"


def test_deterministic_timestamp_from_time(monkeypatch):
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
    monkeypatch.setattr(MOD.time, "time", lambda: 86400.7)
    assert MOD.deterministic_timestamp(None) == "1970-01-02T00:00:00Z"


def test_slug():
    assert MOD.slug("System Overview.PPTX") == "system_overview_pptx"
    assert MOD.slug("!!!") == "unknown"


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, "null"),
        (True, "true"),
        (False, "false"),
        (3, "3"),
        (0.5, "0.5"),
        ('a"b\\c', '"a\\"b\\\\c"'),
    ],
)
def test_yaml_scalar(value, expected):
    assert MOD.yaml_scalar(value) == expected


def test_write_simple_yaml_creates_parents(tmp_path):
    target = tmp_path / "a" / "b" / "x.yaml"
    MOD.write_simple_yaml(target, {"k": 1, "s": "v", "n": None})
    assert target.read_text(encoding="utf-8") == 'k: 1\ns: "v"\nn: null\n'


def test_artefact_record_as_dict_includes_authority():
    rec = MOD.ArtefactRecord("o", "n", "C", "HIGH", "t", "p", "s", "h", 2, 0.5, rank=3)
    d = rec.as_dict()
    assert d["authority"] == MOD.AUTHORITY
    assert d["rank"] == 3 and d["reference_count"] == 2


# ---------------------------------------------------------------- class


def test_init_clamps_top_n(outputs):
    b = MOD.RecursiveBuildMaster(outputs, TS, top_n=0)
    assert b.top_n == 1
    assert b.build_dir == outputs.resolve() / "recursive_build"
    assert b.generated_at == TS


def test_reference_count_variants(outputs):
    b = MOD.RecursiveBuildMaster(outputs, TS)
    assert b.reference_count({"cross_references": ["a", "b"]}) == 2
    assert b.reference_count({"normalized_name": "doc.pptx"}) == 0
    (outputs / "cross_references" / "doc_cross_refs.json").write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    assert b.reference_count({"normalized_name": "doc.pptx"}) == 3
    (outputs / "cross_references" / "orig_cross_refs.json").write_text(json.dumps({"a": 1}), encoding="utf-8")
    assert b.reference_count({"original_filename": "orig.docx"}) == 0
    assert b.reference_count({}) == 0


def test_score_components(outputs):
    b = MOD.RecursiveBuildMaster(outputs, TS)
    assert b.score({"priority": "critical", "file_hash": "x"}, 20) == 1.0
    assert b.score({}, 0) == 0.35
    assert b.score({"priority": "BOGUS"}, 5) == round(0.35 + 0.1, 6)


def test_make_records_defaults_and_ranking(outputs):
    _meta(outputs, "bare", {})
    _meta(outputs, "crit", {"original_filename": "Z.pptx", "priority": "critical", "file_hash": "h"})
    _meta(outputs, "crit2", {"original_filename": "a.pptx", "priority": "CRITICAL", "file_hash": "h"})
    recs = MOD.RecursiveBuildMaster(outputs, TS).make_records()
    assert [r.original_filename for r in recs] == ["a.pptx", "Z.pptx", "bare_metadata"]
    assert [r.rank for r in recs] == [1, 2, 3]
    bare = recs[2]
    assert bare.normalized_name == "bare_metadata"
    assert bare.category == "UNKNOWN" and bare.priority == "MEDIUM"
    assert bare.file_hash == "" and bare.processing_timestamp == ""
    assert bare.source_metadata_path == str(Path("metadata") / "bare_metadata.json")
    assert len(bare.source_metadata_sha256) == 64


def test_build_empty_input(outputs):
    receipt = MOD.RecursiveBuildMaster(outputs, TS, top_n=5).build()
    data = json.loads(receipt.read_text(encoding="utf-8"))
    assert data["status"] == "PASS_EMPTY_INPUT"
    assert data["record_count"] == 0 and data["top_n"] == 5
    assert set(data["outputs"]) == {
        str(Path("recursive_build") / n) for n in ("index.json", "index_top30.md", "master_index.md")
    }
    master = (outputs / "recursive_build" / "master_index.md").read_text(encoding="utf-8")
    assert "Total artefacts: 0" in master


def test_build_full_and_top_n_truncation(outputs):
    for i, (pri, cat) in enumerate([("HIGH", "B"), ("LOW", "A"), ("MEDIUM", "B")]):
        _meta(
            outputs,
            f"d{i}",
            {"original_filename": f"d{i}.pptx", "normalized_name": f"d{i}.pptx", "category": cat, "priority": pri},
        )
    b = MOD.RecursiveBuildMaster(outputs, TS, top_n=2)
    receipt = json.loads(b.build().read_text(encoding="utf-8"))
    assert receipt["status"] == "PASS" and receipt["record_count"] == 3
    for rel, digest in receipt["outputs"].items():
        assert MOD.sha256_file(outputs / rel) == digest
    top = (outputs / "recursive_build" / "index_top30.md").read_text(encoding="utf-8")
    assert "| 1 | " in top and "| 2 | " in top and "| 3 | " not in top
    master = (outputs / "recursive_build" / "master_index.md").read_text(encoding="utf-8")
    assert "- **A**: 1" in master and "- **B**: 2" in master
    assert master.index("- **A**") < master.index("- **B**")
    assert "[digital twin](../digital_twins/d0.md)" in master
    log = outputs / "recursive_build" / ".buildlog" / "d0_pptx" / "artefact_id.yaml"
    text = log.read_text(encoding="utf-8")
    assert 'priority: "HIGH"' in text and "rank: 1" in text
    index = json.loads((outputs / "recursive_build" / "index.json").read_text(encoding="utf-8"))
    assert index["total"] == 3 and index["records"][0]["original_filename"] == "d0.pptx"


# ---------------------------------------------------------------- CLI


def test_parse_args_defaults(monkeypatch):
    monkeypatch.delenv("PIPELINE_OUTPUT_DIR", raising=False)
    monkeypatch.setattr(sys, "argv", ["prog"])
    args = MOD.parse_args()
    assert Path(args.outputs_dir) == REPO_ROOT / "app" / "public" / "outputs"
    assert args.generated_at is None and args.top_n == 30


def test_parse_args_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("PIPELINE_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["prog", "--top-n", "4", "--generated-at", TS])
    args = MOD.parse_args()
    assert args.outputs_dir == str(tmp_path) and args.top_n == 4 and args.generated_at == TS


def test_main_prints_receipt(monkeypatch, outputs, capsys):
    monkeypatch.setattr(sys, "argv", ["prog", "--outputs-dir", str(outputs), "--generated-at", TS])
    assert MOD.main() == 0
    out = capsys.readouterr().out.strip()
    assert out.endswith("build_receipt.json")
    assert Path(out).exists()


def test_dunder_main_exits_zero(monkeypatch, outputs):
    monkeypatch.setattr(sys, "argv", ["prog", "--outputs-dir", str(outputs), "--generated-at", TS])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(MODULE_PATH), run_name="__main__")
    assert exc.value.code == 0
    assert (outputs / "recursive_build" / "build_receipt.json").exists()
