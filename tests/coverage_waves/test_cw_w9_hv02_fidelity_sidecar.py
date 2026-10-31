"""Coverage wave w9: mission-control/v2/handoff/closeout/hv02_fidelity_sidecar.py (local bytes only)."""
import hashlib
import importlib.util
import json
import os
import runpy
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_PATH = REPO_ROOT / "mission-control" / "v2" / "handoff" / "closeout" / "hv02_fidelity_sidecar.py"
_spec = importlib.util.spec_from_file_location("cw_w9_hv02_fidelity_sidecar_mod", MOD_PATH)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

SRC = b"exported transcript bytes"
SRC_SHA = hashlib.sha256(SRC).hexdigest()
ART = b"artifact-bytes"
ART_SHA = hashlib.sha256(ART).hexdigest()


def base():
    return {
        "schema": mod.SCHEMA, "session_alias": "HV02-W9",
        "capture_utc": "UNKNOWN", "source_class": "GITHUB_OBSERVED",
        "source_locator": "UNKNOWN", "source_sha256": None,
        "source_state": "UNKNOWN", "scope": "CURRENT_VISIBLE",
        "completeness": "UNKNOWN", "message_count": None,
        "artifact_refs": [], "evidence": [],
        "merge_admission": "HOLD", "authority_transfer": False,
    }


def verified_export():
    obj = base()
    obj.update(source_class="AUTHORIZED_EXPORT", scope="AUTHORIZED_EXPORT", completeness="USER_DECLARED",
               source_state="VERIFIED", source_sha256=SRC_SHA, message_count=2, message_refs=["m1", "m2"],
               source_locator="https://github.com/GBOGEB/pipeline-automation-hub/pull/1",
               capture_utc="2026-10-20T10:00:00Z")
    return obj


def artifact(**kw):
    a = {"id": "art-1", "media_type": "text/plain", "bytes": len(ART), "sha256": ART_SHA,
         "custody": "LOCAL_PRIVATE", "access_class": "PRIVATE", "state": "VERIFIED"}
    a.update(kw)
    return a


# ------------------------------------------------------------------ helpers
@pytest.mark.parametrize("value,ok", [
    ("UNKNOWN", True), ("2026-10-20T10:00:00Z", True), ("2026-10-20T10:00:00+00:00", True),
    ("2026-10-20T10:00:00+02:00", False), ("2026-10-20T10:00:00", False), ("not a time", False), (17, False),
])
def test_check_utc(value, ok):
    assert mod.check_utc(value) is ok


@pytest.mark.parametrize("value,ok", [
    ("UNKNOWN", True), ("https://github.com/GBOGEB/x", True), (None, False),
    ("http://github.com/GBOGEB/x", False), ("https://gitlab.com/GBOGEB/x", False),
    ("https://github.com/other/x", False), ("https://u:p@github.com/GBOGEB/x", False),
    ("https://github.com/GBOGEB/x?a=1", False), ("https://github.com/GBOGEB/x#f", False),
])
def test_public_locator(value, ok):
    assert mod.public_locator(value) is ok


def test_is_sha_and_digest():
    assert mod.is_sha(SRC_SHA) and not mod.is_sha(SRC_SHA.upper()) and not mod.is_sha(5)
    assert mod.digest(b"") == hashlib.sha256(b"").hexdigest()


@pytest.mark.parametrize("tree,public,reason", [
    ({1: "x"}, True, "raw/private"),
    ({"Messages": []}, True, "raw/private"),
    ({"ok": ["ghp_" + "a" * 24]}, True, "credential"),
    ({"ok": "https://x/?token=1"}, False, "credential"),
    ({"ok": "C:\\Users\\me\\x"}, True, "private local storage"),
])
def test_validate_metadata_tree_rejects(tree, public, reason):
    with pytest.raises(ValueError, match=reason):
        mod.validate_metadata_tree(tree, public=public)


def test_validate_metadata_tree_private_allows_local_paths():
    mod.validate_metadata_tree({"a": ["/home/me/x", 3, None]}, public=False)


# ------------------------------------------------------------------ validate: success paths
def test_validate_minimal_receipt():
    r = mod.validate(base())
    assert r == {"schema": mod.SCHEMA, "source_state": "UNKNOWN", "completeness": "UNKNOWN",
                 "message_count": None, "artifacts_declared": 0, "artifacts_verified": 0,
                 "merge_admission": "HOLD", "verbatim_completeness_attested": False}


def test_validate_verified_export_with_artifacts_and_evidence():
    obj = verified_export()
    obj["artifact_refs"] = [artifact(),
                            artifact(id="art-2", state="PARTIAL", bytes=None, sha256=None),
                            artifact(id="art-3", state="PARTIAL")]
    obj["evidence"] = [{"state": "STALE", "run_sha": "a" * 40}, {"state": "PARTIAL", "run_sha": None},
                       {"state": "UNKNOWN"}]
    r = mod.validate(obj, source_bytes=SRC, artifact_bytes={"art-1": ART, "art-2": b"z", "art-3": ART})
    assert r["message_count"] == 2 and r["artifacts_declared"] == 3 and r["artifacts_verified"] == 1
    assert r["source_state"] == "VERIFIED"


def test_validate_private_mode_accepts_local_locator():
    obj = base()
    obj["source_locator"] = "local-vault-entry"
    assert mod.validate(obj, public=False)["merge_admission"] == "HOLD"


def test_validate_source_bytes_match_without_verified_state():
    obj = base()
    obj["source_sha256"] = SRC_SHA
    assert mod.validate(obj, source_bytes=SRC)["source_state"] == "UNKNOWN"


# ------------------------------------------------------------------ validate: fail-closed paths
def _mut(**kw):
    def f(o):
        o.update(kw)
    return f


def _del(key):
    def f(o):
        del o[key]
    return f


def _art(**kw):
    def f(o):
        o["artifact_refs"] = [artifact(**kw)]
    return f


CASES = [
    ("schema", lambda o: o.update(schema="x"), {}, "sidecar instance schema"),
    ("missing", _del("evidence"), {}, "required metadata absent"),
    ("alias_type", _mut(session_alias=5), {}, "session alias"),
    ("alias_short", _mut(session_alias="ab"), {}, "session alias"),
    ("utc", _mut(capture_utc="2026-10-20T10:00:00+01:00"), {}, "UTC timestamp"),
    ("source_class", _mut(source_class="NOPE"), {}, "source class/scope"),
    ("scope", _mut(scope="NOPE"), {}, "source class/scope"),
    ("completeness", _mut(completeness="NOPE"), {}, "fidelity/source state"),
    ("state", _mut(source_state="NOPE"), {}, "fidelity/source state"),
    ("admission", _mut(merge_admission="ADMIT"), {}, "cannot grant authority"),
    ("authority", _mut(authority_transfer=True), {}, "cannot grant authority"),
    ("public_locator", _mut(source_locator="https://example.com/x"), {}, "unapproved public locator"),
    ("empty_locator", _mut(source_locator=""), {"public": False}, "missing locator"),
    ("nonstr_locator", _mut(source_locator=7), {"public": False}, "missing locator"),
    ("bad_sha", _mut(source_sha256="abc"), {}, "invalid source digest"),
    ("verified_no_sha", _mut(source_state="VERIFIED"), {}, "not independently matched"),
    ("verified_no_bytes", _mut(source_state="VERIFIED", source_sha256=SRC_SHA), {}, "not independently matched"),
    ("verified_wrong", _mut(source_state="VERIFIED", source_sha256=SRC_SHA), {"source_bytes": b"x"},
     "not independently matched"),
    ("digest_mismatch", _mut(source_sha256=SRC_SHA), {"source_bytes": b"other"}, "source digest mismatch"),
    ("count_bool", _mut(message_count=True), {}, "invalid message count"),
    ("count_neg", _mut(message_count=-1), {}, "invalid message count"),
    ("count_str", _mut(message_count="2"), {}, "invalid message count"),
    ("count_unverified", _mut(message_count=0), {}, "unverified message population"),
    ("refs_without_count", _mut(message_refs=["m1"]), {}, "message refs without count"),
    ("artifact_list", _mut(artifact_refs={}), {}, "artifact/evidence list"),
    ("evidence_list", _mut(evidence="x"), {}, "artifact/evidence list"),
    ("art_shape_type", _mut(artifact_refs=["x"]), {}, "artifact record shape"),
    ("art_shape_keys", _mut(artifact_refs=[{"id": "a"}]), {}, "artifact record shape"),
    ("art_id_type", _art(id=5), {}, "unsafe/duplicate artifact id"),
    ("art_id_unsafe", _art(id="../x"), {}, "unsafe/duplicate artifact id"),
    ("art_dup", lambda o: o.update(artifact_refs=[artifact(state="PARTIAL"), artifact(state="PARTIAL")]), {},
     "unsafe/duplicate artifact id"),
    ("art_state", _art(state="NOPE"), {}, "artifact state/access"),
    ("art_access", _art(access_class="PUBLIC"), {}, "artifact state/access"),
    ("art_media_type", _art(media_type=3), {}, "artifact media type"),
    ("art_media_slash", _art(media_type="text"), {}, "artifact media type"),
    ("art_custody", _art(custody="CLOUD"), {}, "artifact custody"),
    ("art_bytes_bool", _art(bytes=True), {}, "artifact byte length"),
    ("art_bytes_neg", _art(bytes=-1), {}, "artifact byte length"),
    ("art_bytes_str", _art(bytes="1"), {}, "artifact byte length"),
    ("art_digest", _art(sha256="zz"), {}, "artifact digest"),
    ("art_verified_missing", _art(), {}, "artifact bytes not verified"),
    ("art_verified_len", _art(bytes=1), {"artifact_bytes": {"art-1": ART}}, "artifact bytes not verified"),
    ("art_verified_hash", _art(), {"artifact_bytes": {"art-1": b"x" * len(ART)}}, "artifact bytes not verified"),
    ("art_hash_mismatch", _art(state="PARTIAL"), {"artifact_bytes": {"art-1": b"other"}}, "artifact hash mismatch"),
    ("evidence_type", _mut(evidence=["x"]), {}, "evidence state"),
    ("evidence_state", _mut(evidence=[{"state": "NOPE"}]), {}, "evidence state"),
    ("run_sha_type", _mut(evidence=[{"state": "PARTIAL", "run_sha": 5}]), {}, "run source SHA"),
    ("run_sha_short", _mut(evidence=[{"state": "PARTIAL", "run_sha": "abc"}]), {}, "run source SHA"),
    ("evidence_verified", _mut(evidence=[{"state": "VERIFIED"}]), {}, "authenticated run evidence"),
]


@pytest.mark.parametrize("name,mutate,kwargs,reason", CASES, ids=[c[0] for c in CASES])
def test_validate_fail_closed(name, mutate, kwargs, reason):
    obj = base()
    mutate(obj)
    with pytest.raises(ValueError, match=reason):
        mod.validate(obj, **kwargs)


def test_validate_rejects_non_dict():
    with pytest.raises(ValueError, match="sidecar instance schema"):
        mod.validate(["x"])


@pytest.mark.parametrize("change,kwargs,reason", [
    ({"source_class": "USER_SUPPLIED"}, {"source_bytes": SRC}, "unverified message population"),
    ({"scope": "SANITIZED_SUBSET"}, {"source_bytes": SRC}, "unverified message population"),
    ({"completeness": "PARTIAL"}, {"source_bytes": SRC}, "unverified message population"),
    ({"message_refs": ["m1"]}, {"source_bytes": SRC}, "message population references"),
    ({"message_refs": ["m1", "m1"]}, {"source_bytes": SRC}, "message population references"),
    ({"message_refs": None}, {"source_bytes": SRC}, "message population references"),
    ({"message_refs": ["m1", "../x"]}, {"source_bytes": SRC}, "unsafe message reference"),
    ({"message_refs": ["m1", 2]}, {"source_bytes": SRC}, "unsafe message reference"),
])
def test_validate_message_population(change, kwargs, reason):
    obj = verified_export()
    obj.update(change)
    with pytest.raises(ValueError, match=reason):
        mod.validate(obj, **kwargs)


# ------------------------------------------------------------------ CLI
def write(tmp_path, obj, name="sidecar.json"):
    p = tmp_path / name
    p.write_text(json.dumps(obj), encoding="utf-8")
    return p


def test_main_minimal(tmp_path, capsys):
    mod.main(["--sidecar", str(write(tmp_path, base()))])
    assert json.loads(capsys.readouterr().out)["merge_admission"] == "HOLD"


def test_main_with_source_and_artifact_root(tmp_path, capsys):
    root = tmp_path / "arts"
    root.mkdir()
    (root / "art-1").write_bytes(ART)
    obj = verified_export()
    obj["artifact_refs"] = [artifact(), artifact(id="art-2", state="PARTIAL", bytes=None, sha256=None)]
    src = tmp_path / "src.bin"
    src.write_bytes(SRC)
    mod.main(["--sidecar", str(write(tmp_path, obj)), "--source-file", str(src), "--artifact-root", str(root)])
    out = json.loads(capsys.readouterr().out)
    assert out["artifacts_verified"] == 1 and out["message_count"] == 2


def test_main_private_flag(tmp_path, capsys):
    obj = base()
    obj["source_locator"] = "local-only"
    mod.main(["--sidecar", str(write(tmp_path, obj)), "--private"])
    assert json.loads(capsys.readouterr().out)["source_state"] == "UNKNOWN"


def test_main_artifact_root_without_refs(tmp_path, capsys):
    obj = base()
    del obj["artifact_refs"]
    root = tmp_path / "arts"
    root.mkdir()
    with pytest.raises(ValueError, match="required metadata absent"):
        mod.main(["--sidecar", str(write(tmp_path, obj)), "--artifact-root", str(root)])


def test_main_unsafe_artifact_filename(tmp_path):
    root = tmp_path / "arts"
    root.mkdir()
    obj = base()
    obj["artifact_refs"] = [{"state": "VERIFIED", "id": "../escape"}]
    with pytest.raises(ValueError, match="artifact unsafe filename"):
        mod.main(["--sidecar", str(write(tmp_path, obj)), "--artifact-root", str(root)])
    obj["artifact_refs"] = [{"state": "VERIFIED"}]
    with pytest.raises(ValueError, match="artifact unsafe filename"):
        mod.main(["--sidecar", str(write(tmp_path, obj)), "--artifact-root", str(root)])


def test_main_artifact_path_escape(tmp_path, monkeypatch):
    root = tmp_path / "arts"
    root.mkdir()
    (root / "art-1").write_bytes(ART)
    obj = base()
    obj["artifact_refs"] = [artifact()]
    monkeypatch.setattr(Path, "is_symlink", lambda self: self.name == "art-1")
    with pytest.raises(ValueError, match="artifact path escape"):
        mod.main(["--sidecar", str(write(tmp_path, obj)), "--artifact-root", str(root)])


def test_main_artifact_resolves_outside_root(tmp_path, monkeypatch):
    root = tmp_path / "arts"
    root.mkdir()
    (root / "art-1").write_bytes(ART)
    obj = base()
    obj["artifact_refs"] = [artifact()]
    real_resolve = Path.resolve

    def resolve(self, *a, **kw):
        if self.name == "art-1":
            return real_resolve(tmp_path / "elsewhere")
        return real_resolve(self, *a, **kw)

    monkeypatch.setattr(Path, "resolve", resolve)
    with pytest.raises(ValueError, match="artifact path escape"):
        mod.main(["--sidecar", str(write(tmp_path, obj)), "--artifact-root", str(root)])


def test_dunder_main_success(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [str(MOD_PATH), "--sidecar", str(write(tmp_path, base()))])
    runpy.run_path(str(MOD_PATH), run_name="__main__")
    assert json.loads(capsys.readouterr().out)["merge_admission"] == "HOLD"


@pytest.mark.parametrize("content,needle", [
    (None, "schema"),
    ("{not json", "Expecting"),
])
def test_dunder_main_errors_become_systemexit(tmp_path, monkeypatch, content, needle):
    p = tmp_path / "s.json"
    if content is None:
        p.write_text(json.dumps({"schema": "wrong"}), encoding="utf-8")
    else:
        p.write_text(content, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [str(MOD_PATH), "--sidecar", str(p)])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(MOD_PATH), run_name="__main__")
    assert needle in str(exc.value.code)


def test_dunder_main_missing_file_oserror(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", [str(MOD_PATH), "--sidecar", os.fspath(tmp_path / "missing.json")])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(MOD_PATH), run_name="__main__")
    assert isinstance(exc.value.code, str) and exc.value.code
