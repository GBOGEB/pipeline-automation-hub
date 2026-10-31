"""Coverage wave 10: mission-control/v2/recursive-recovery/lineage.py (read-only repo data, tmp_path writes)."""
import copy
import importlib.util
import json
import runpy
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_PATH = REPO_ROOT / "mission-control" / "v2" / "recursive-recovery" / "lineage.py"
_spec = importlib.util.spec_from_file_location("cw_w10_lineage_mod", MOD_PATH)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


@pytest.fixture(scope="module")
def canon():
    return mod.load_canonical()


def fresh(canon):
    spec, data = canon
    return copy.deepcopy(spec), copy.deepcopy(data)


# --------------------------------------------------------------------------- validate_successor
def _mini_atlas(extra_internal=None):
    internal = [{"id": "breadth", "path": "b.json", "authority": "A", "blob_sha": "1" * 40},
                {"id": "other", "path": "o.json", "authority": "B", "blob_sha": "2" * 40}]
    frozen_raw = json.dumps({"internal": internal}).encode()
    spec = {"successor_of": {"file": "N12_SOURCE_ATLAS.json", "preserved_unchanged": True,
                             "blob_sha": mod.git_blob(frozen_raw)},
            "internal": [dict(internal[0], previous_frozen_blob_sha="1" * 40, blob_sha="3" * 40),
                         dict(internal[1])] + (extra_internal or []),
            "source_refresh_evidence": {"new_blob_sha": "3" * 40, "old_blob_sha": "1" * 40,
                                        "changed_internal_blobs": 1}}
    return spec, frozen_raw


def test_validate_successor_minimal_ok():
    spec, raw = _mini_atlas()
    assert mod.validate_successor(spec, raw) is None


def test_validate_successor_source_set_drift():
    spec, raw = _mini_atlas([{"id": "extra", "path": "e.json", "authority": "C", "blob_sha": "4" * 40}])
    with pytest.raises(ValueError, match="FROZEN_ATLAS_SOURCE_SET_DRIFT"):
        mod.validate_successor(spec, raw)


def test_validate_successor_denominator_drift():
    spec, raw = _mini_atlas()
    spec["source_refresh_evidence"]["changed_internal_blobs"] = 2
    with pytest.raises(ValueError, match="SOURCE_REFRESH_DENOMINATOR_DRIFT"):
        mod.validate_successor(spec, raw)


# --------------------------------------------------------------------------- load_canonical on tmp data
def _write_tmp_canon(tmp_path, monkeypatch, authority_transfer=False, bad_blob=False):
    payload = b'{"k": 1}\n'
    text_payload = "plain text\n".encode()
    blob = mod.git_blob(payload)
    internal = [{"id": "breadth", "path": "src/b.json", "authority": "A", "blob_sha": "0" * 40 if bad_blob else blob},
                {"id": "notes", "path": "src/n.md", "authority": "B", "blob_sha": mod.git_blob(text_payload)}]
    frozen_internal = [dict(internal[0], blob_sha="9" * 40), internal[1]]
    frozen_raw = json.dumps({"internal": frozen_internal}).encode()
    spec = {"successor_of": {"file": "N12_SOURCE_ATLAS.json", "preserved_unchanged": True,
                             "blob_sha": mod.git_blob(frozen_raw)},
            "internal": [dict(internal[0], previous_frozen_blob_sha="9" * 40), internal[1]],
            "source_refresh_evidence": {"new_blob_sha": internal[0]["blob_sha"], "old_blob_sha": "9" * 40,
                                        "changed_internal_blobs": 1},
            "controller": {"authority_transfer": authority_transfer}}
    here = tmp_path / "here"
    here.mkdir()
    (here / "N12_SOURCE_ATLAS.json").write_bytes(frozen_raw)
    (here / "N12_SOURCE_ATLAS_20261026.json").write_text(json.dumps(spec), encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "b.json").write_bytes(payload)
    (tmp_path / "src" / "n.md").write_bytes(text_payload)
    monkeypatch.setattr(mod, "HERE", here)
    monkeypatch.setattr(mod, "ROOT", tmp_path)


def test_load_canonical_tmp_ok_json_and_text(tmp_path, monkeypatch):
    _write_tmp_canon(tmp_path, monkeypatch)
    spec, content = mod.load_canonical()
    assert content == {"breadth": {"k": 1}, "notes": "plain text\n"}
    assert spec["controller"]["authority_transfer"] is False


def test_load_canonical_rejects_authority_transfer(tmp_path, monkeypatch):
    _write_tmp_canon(tmp_path, monkeypatch, authority_transfer=True)
    with pytest.raises(ValueError, match="authority may not transfer"):
        mod.load_canonical()


def test_load_canonical_rejects_blob_drift(tmp_path, monkeypatch):
    _write_tmp_canon(tmp_path, monkeypatch, bad_blob=True)
    with pytest.raises(ValueError, match="FROZEN_SOURCE_BLOB_DRIFT: breadth"):
        mod.load_canonical()


# --------------------------------------------------------------------------- yaml_mission
def test_yaml_mission_missing_category_and_id():
    text = "local_missions:\n  - id: LM-1\n    name: 'One'\n"
    with pytest.raises(ValueError, match="namespace missing: horizontal_missions"):
        mod.yaml_mission(text, "horizontal_missions", "HM-01")
    with pytest.raises(ValueError, match="mission ID missing: LM-2"):
        mod.yaml_mission(text, "local_missions", "LM-2")
    row = mod.yaml_mission(text, "local_missions", "LM-1")
    assert row["name"] == "One" and row["type"] is None and row["authority_transfer"] is False


# --------------------------------------------------------------------------- build guards
def _expect(canon, mutate, pattern):
    spec, data = fresh(canon)
    mutate(spec, data)
    with pytest.raises(ValueError, match=pattern):
        mod.build(spec, data)


def test_build_valid_structure(canon):
    spec, data = fresh(canon)
    out = mod.build(spec, data)
    assert out["schema"] == mod.SCHEMA
    assert out["authority_transfer"] is False
    assert len(out["semantic_sha256"]) == 64


def test_build_rejects_identity_change(canon):
    _expect(canon, lambda s, d: d["gm_registry"]["grand_missions"].reverse(), "identity changed")


def test_build_rejects_authority_transfer(canon):
    def m(s, d):
        d["crew_roster"]["authority_transfer"] = True
    _expect(canon, m, "canonical authority transfer")


def test_build_rejects_duplicate_crew(canon):
    def m(s, d):
        d["crew_roster"]["crew"].append(copy.deepcopy(d["crew_roster"]["crew"][0]))
    _expect(canon, m, "duplicate crew ID")


def test_build_rejects_duplicate_rex_event(canon):
    def m(s, d):
        d["rex_ledger"]["events"].append(copy.deepcopy(d["rex_ledger"]["events"][0]))
    _expect(canon, m, "duplicate REX event")


def test_build_rejects_corrupted_top7(canon):
    def m(s, d):
        d["top7"]["selection"]["repositories"] = d["top7"]["selection"]["repositories"][:6]
    _expect(canon, m, "Top7 scope corrupted")


def test_build_rejects_rex_unknown_mission(canon):
    def m(s, d):
        d["rex_ledger"]["events"][0]["mission_id"] = "GM-NOPE"
    _expect(canon, m, "REX refers to unknown mission: GM-NOPE")


def test_build_duplicate_edges_variant_without_repo_and_unknown_role(canon):
    spec, data = fresh(canon)
    gm1 = data["gm_registry"]["grand_missions"][0]
    gm1["children"] = ["GBOGEB/dup", "GBOGEB/dup"]  # second child edge is deduplicated
    gm1["variants"] = list(gm1.get("variants", [])) + [{"id": "GM-I-VX", "name": "variant"}]
    data["rex_ledger"]["events"][0]["crew_role"] = "ROLE_NOT_REGISTERED"
    out = mod.build(spec, data)
    pairs = [(e["from"], e["to"], e["kind"]) for e in out["graph"]["edges"]]
    assert pairs.count(("mission:GM-I", "repo:GBOGEB/dup", "HISTORICAL_FRONTIER")) == 1
    assert any(r["id"] == "GM-I-VX" and r["repository"] is None for r in out["missions"])
    rex0 = "rex:" + data["rex_ledger"]["events"][0]["event_id"]
    assert not any(e["to"] == rex0 and e["kind"] == "REX_ROLE_REPORT" for e in out["graph"]["edges"])


# --------------------------------------------------------------------------- CLI
def test_main_writes_projection(tmp_path, capsys):
    out = tmp_path / "deep" / "projection.json"
    mod.main(["--out", str(out)])
    summary = json.loads(capsys.readouterr().out)
    written = json.loads(out.read_text(encoding="utf-8"))
    assert summary["sha256"] == written["semantic_sha256"]
    assert summary["admission"] == "HOLD"
    assert out.read_bytes().endswith(b"}\n") and b"\r\n" not in out.read_bytes()


def test_dunder_main(tmp_path, monkeypatch, capsys):
    out = tmp_path / "p.json"
    monkeypatch.setattr(sys, "argv", ["lineage.py", "--out", str(out)])
    runpy.run_path(str(MOD_PATH), run_name="__main__")
    assert out.is_file()
    assert json.loads(capsys.readouterr().out)["schema"] == mod.SCHEMA
