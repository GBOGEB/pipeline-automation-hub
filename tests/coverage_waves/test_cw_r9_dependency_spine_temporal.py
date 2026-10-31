"""Coverage wave r9: mission-control/gogreen/dependency_spine_temporal.py."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_PATH = REPO_ROOT / "mission-control" / "gogreen" / "dependency_spine_temporal.py"
_spec = importlib.util.spec_from_file_location("cw_r9_dependency_spine_temporal_mod", MOD_PATH)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

HEAD = "a" * 40
SOURCE = "b" * 40
REPO = "GBOGEB/CODEX"


def fixture(repo=REPO, sha=SOURCE):
    v = {"schema": "qps.dependency_spine.peer_census.v1", "repo": repo, "head_sha": sha,
         "exact_head_verified": True, "workflow_count": 2, "action_reference_count": 4,
         "dependabot_present": True,
         "runtime_proof": "NATIVE_SCAN_JOB_ONLY_NOT_DEPENDABOT_UPGRADE_PROOF",
         "governance": {"authority_transfer": False, "remote_dispatch_authorized": False,
                        "mutation_enabled": False, "formal_credit_delta": 0,
                        "merge_admission": "HOLD"}}
    return v, manifest_for(v, repo, sha)


def manifest_for(v, repo=REPO, sha=SOURCE):
    return {"schema": "qps.dependency_spine.peer_sha256.v1", "repo": repo, "head_sha": sha,
            "files": {"PEER_CENSUS.json": mod.digest(mod.canonical(v))}}


def stage(directory: Path, repo=REPO, sha=SOURCE) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    v, m = fixture(repo, sha)
    (directory / "PEER_CENSUS.json").write_bytes(mod.canonical(v))
    (directory / "PEER_SHA256.json").write_bytes(mod.canonical(m))
    return directory


def rehash(r):
    r["semantic_sha256"] = mod.digest(mod.canonical({k: v for k, v in r.items() if k != "semantic_sha256"}))
    return r


def empty_build(**kw):
    return mod.build(HEAD, mod.collect({}, {}), **kw)


# ---- primitives -----------------------------------------------------------

def test_constants_and_canonical():
    assert "GBOGEB/cryoplant-project" not in mod.PEERS
    assert len(mod.PEERS) == 4
    out = mod.canonical({"b": 1, "a": "é"})
    assert out.endswith(b"\n") and out.index(b'"a"') < out.index(b'"b"')
    assert b"\\u00e9" in out
    assert len(mod.digest(b"x")) == 64


def test_git_head_success_and_failure(monkeypatch, tmp_path):
    calls = []

    def ok(cmd, **kw):
        calls.append((cmd, kw["cwd"]))
        return SimpleNamespace(returncode=0, stdout=" " + HEAD + "\n")

    monkeypatch.setattr(mod.subprocess, "run", ok)
    assert mod.git_head(tmp_path) == HEAD
    assert calls[0][0][:2] == ["git", "rev-parse"] and calls[0][1] == tmp_path
    monkeypatch.setattr(mod.subprocess, "run",
                        lambda *a, **k: SimpleNamespace(returncode=128, stdout="junk"))
    assert mod.git_head(tmp_path) == ""


def make_owner_root(root: Path) -> Path:
    (root / "mission-control" / "gogreen").mkdir(parents=True)
    (root / "mission-control" / "golden-thread").mkdir(parents=True)
    (root / "mission-control" / "gogreen" / "sipoc_instances.py").write_text("", encoding="utf-8")
    (root / "mission-control" / "golden-thread" / "golden_thread.py").write_text("", encoding="utf-8")
    return root


def test_check_owner(tmp_path):
    with pytest.raises(ValueError, match="CANONICAL_OWNER_PLANNER_MISSING"):
        mod.check_owner(tmp_path)
    (tmp_path / "mission-control" / "gogreen").mkdir(parents=True)
    (tmp_path / "mission-control" / "gogreen" / "sipoc_instances.py").write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="CANONICAL_OWNER_PLANNER_MISSING"):
        mod.check_owner(tmp_path)
    (tmp_path / "mission-control" / "golden-thread").mkdir(parents=True)
    (tmp_path / "mission-control" / "golden-thread" / "golden_thread.py").write_text("", encoding="utf-8")
    assert mod.check_owner(tmp_path) is None


def test_check_owner_real_repo_structural():
    try:
        assert mod.check_owner(REPO_ROOT) is None
    except ValueError as e:
        assert str(e) == "CANONICAL_OWNER_PLANNER_MISSING"


# ---- validate_peer -------------------------------------------------------

def test_validate_peer_success_shape():
    v, m = fixture()
    out = mod.validate_peer(v, m, REPO, SOURCE)
    assert out["repo"] == REPO and out["head_sha"] == SOURCE
    assert out["workflow_count"] == 2 and out["action_reference_count"] == 4
    assert out["dependabot_present"] is True
    assert out["receipt_sha256"] == mod.digest(mod.canonical(v))
    assert out["origin"].startswith("LOCAL_BYTE_VERIFIED")


def test_validate_peer_bad_sha():
    with pytest.raises(ValueError, match="PEER_PIN_INVALID"):
        mod.validate_peer(*fixture(), REPO, "XYZ")


def test_validate_peer_schema():
    v, m = fixture()
    v["schema"] = "other"
    with pytest.raises(ValueError, match="PEER_SCHEMA"):
        mod.validate_peer(v, m, REPO, SOURCE)


@pytest.mark.parametrize("field,value", [("repo", "GBOGEB/ABACUS"), ("exact_head_verified", 1)])
def test_validate_peer_identity(field, value):
    v, m = fixture()
    v[field] = value
    with pytest.raises(ValueError, match="PEER_IDENTITY_DRIFT"):
        mod.validate_peer(v, m, REPO, SOURCE)


def test_validate_peer_manifest_schema_and_identity():
    v, m = fixture()
    m["schema"] = "x"
    with pytest.raises(ValueError, match="MANIFEST_SCHEMA"):
        mod.validate_peer(v, m, REPO, SOURCE)
    for field, value in (("repo", "GBOGEB/ABACUS"), ("head_sha", "c" * 40)):
        v, m = fixture()
        m[field] = value
        with pytest.raises(ValueError, match="MANIFEST_IDENTITY"):
            mod.validate_peer(v, m, REPO, SOURCE)


@pytest.mark.parametrize("key,value", [
    ("authority_transfer", True), ("mutation_enabled", None),
    ("formal_credit_delta", 1), ("merge_admission", "PASS"),
])
def test_validate_peer_governance(key, value):
    v, _ = fixture()
    v["governance"][key] = value
    with pytest.raises(ValueError, match="PEER_AUTHORITY_ESCALATION"):
        mod.validate_peer(v, manifest_for(v), REPO, SOURCE)


def test_validate_peer_missing_governance():
    v, _ = fixture()
    del v["governance"]
    with pytest.raises(ValueError, match="PEER_AUTHORITY_ESCALATION"):
        mod.validate_peer(v, manifest_for(v), REPO, SOURCE)


def test_validate_peer_runtime_proof():
    v, _ = fixture()
    v["runtime_proof"] = "DEPENDABOT_UPGRADE_PROOF"
    with pytest.raises(ValueError, match="PEER_FALSE_RUNTIME"):
        mod.validate_peer(v, manifest_for(v), REPO, SOURCE)


# ---- collect ---------------------------------------------------------------

def test_collect_pin_without_peer_rejected():
    with pytest.raises(ValueError, match="UNAUTHORIZED_PEER_SCOPE"):
        mod.collect({}, {REPO: SOURCE})


def test_collect_invalid_json(tmp_path):
    (tmp_path / "PEER_CENSUS.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "PEER_SHA256.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="PEER_STAGE_MISSING_OR_INVALID:" + REPO):
        mod.collect({REPO: tmp_path}, {REPO: SOURCE})


def test_collect_mixed_roster(tmp_path):
    d = stage(tmp_path / "codex")
    recs = mod.collect({REPO: d}, {REPO: SOURCE})
    assert set(recs) == set(mod.PEERS)
    assert recs[REPO]["status"] == "LOCALLY_VERIFIED_UNAUTHENTICATED"
    for repo in mod.PEERS:
        if repo != REPO:
            assert recs[repo] == {"repo": repo, "status": "NOT_STAGED", "head_sha": None}


@pytest.mark.xfail(strict=True, reason="production_defect: collect() raises bare KeyError (not a governed ValueError) when a peer dir is supplied without a matching --pin")
def test_collect_peer_without_pin_is_governed_error(tmp_path):
    d = stage(tmp_path / "codex")
    with pytest.raises(ValueError):
        mod.collect({REPO: d}, {})


# ---- build / verify --------------------------------------------------------

def test_build_rejects_bad_owner_and_roster():
    recs = mod.collect({}, {})
    with pytest.raises(ValueError, match="OWNER_HEAD_OR_ROSTER_INVALID"):
        mod.build("short", recs)
    partial = dict(recs)
    partial.pop(REPO)
    with pytest.raises(ValueError, match="OWNER_HEAD_OR_ROSTER_INVALID"):
        mod.build(HEAD, partial)


def test_build_staged_state_and_delta(tmp_path):
    recs = mod.collect({REPO: stage(tmp_path / "c")}, {REPO: SOURCE})
    r = mod.build(HEAD, recs, previous=empty_build())
    mod.verify(r)
    assert r["observation_state"] == "STAGE_ONLY_UNAUTHENTICATED"
    assert r["historical_n_minus_1"] == 0 and r["current_n"] == 1
    assert r["improvement_delta"] == 1
    assert r["metrics"]["peer_missing"] == 3
    assert len(r["sipoc"]) == 3


@pytest.mark.parametrize("key,value", [("schema", "other"), ("authority_transfer", True)])
def test_build_historical_source_rejected(key, value):
    prev = empty_build()
    prev[key] = value
    with pytest.raises(ValueError, match="HISTORICAL_SOURCE_NOT_ACCEPTED"):
        empty_build(previous=prev)


@pytest.mark.parametrize("val", ["1", -1, 5, None])
def test_build_historical_metric_invalid(val):
    prev = empty_build()
    prev["metrics"]["locally_staged_peers"] = val
    with pytest.raises(ValueError, match="HISTORICAL_METRIC_INVALID"):
        empty_build(previous=prev)


def test_build_historical_missing_metrics():
    prev = empty_build()
    del prev["metrics"]
    with pytest.raises(ValueError, match="HISTORICAL_METRIC_INVALID"):
        empty_build(previous=prev)


def test_verify_hash_drift():
    r = empty_build()
    r["current_n"] = 3
    with pytest.raises(ValueError, match="OBSERVATION_HASH_DRIFT"):
        mod.verify(r)


@pytest.mark.parametrize("key,value", [
    ("schema", "x"), ("authority_transfer", 0), ("formal_credit_delta", 1),
    ("mutation_enabled", True), ("dispatch_authorized", True), ("qps_disposition", "ACCEPT"),
])
def test_verify_false_accept(key, value):
    r = empty_build()
    r[key] = value
    with pytest.raises(ValueError, match="MISSIONCONTROL_FALSE_ACCEPT"):
        mod.verify(rehash(r))


def test_verify_false_accept_hops_and_missing_metrics():
    r = empty_build()
    r["metrics"]["native_cross_repo_hops_accepted"] = 1
    with pytest.raises(ValueError, match="MISSIONCONTROL_FALSE_ACCEPT"):
        mod.verify(rehash(r))
    r = empty_build()
    del r["metrics"]
    with pytest.raises(ValueError, match="MISSIONCONTROL_FALSE_ACCEPT"):
        mod.verify(rehash(r))


def test_verify_feedback_edge():
    r = empty_build()
    r["feedback"] = "SAME_PULSE"
    with pytest.raises(ValueError, match="INVALID_FEEDBACK_EDGE"):
        mod.verify(rehash(r))


# ---- main ------------------------------------------------------------------

def run_main(monkeypatch, argv, head=HEAD):
    monkeypatch.setattr(mod, "git_head", lambda root: head)
    monkeypatch.setattr(sys, "argv", ["dependency_spine_temporal.py", *argv])
    return mod.main()


def test_main_head_mismatch(monkeypatch, tmp_path):
    with pytest.raises(SystemExit, match="EXACT_HUB_SOURCE_HEAD_MISMATCH"):
        run_main(monkeypatch, ["--expected-head", HEAD, "--out", str(tmp_path / "o")], head="")


def test_main_happy_with_peer_and_previous(monkeypatch, tmp_path, capsys):
    root = make_owner_root(tmp_path / "root")
    peer = stage(tmp_path / "peer")
    prev_path = tmp_path / "prev.json"
    prev_path.write_bytes(mod.canonical(empty_build()))
    out = tmp_path / "out"
    rc = run_main(monkeypatch, ["--expected-head", HEAD, "--root", str(root),
                                "--peer", f"{REPO}={peer}", "--pin", f"{REPO}={SOURCE}",
                                "--previous", str(prev_path), "--out", str(out)])
    assert rc == 0
    written = json.loads((out / "MC_DEPENDENCY_SPINE_TEMPORAL.json").read_text(encoding="utf-8"))
    mod.verify(written)
    assert written["current_n"] == 1 and written["improvement_delta"] == 1
    printed = json.loads(capsys.readouterr().out.strip())
    assert printed == {"admission": "HOLD", "observed_staged": 1, "required_peers": 4,
                       "status": "STAGE_ONLY_UNAUTHENTICATED"}


def test_main_no_peers(monkeypatch, tmp_path, capsys):
    root = make_owner_root(tmp_path / "root")
    out = tmp_path / "out"
    assert run_main(monkeypatch, ["--expected-head", HEAD, "--root", str(root), "--out", str(out)]) == 0
    printed = json.loads(capsys.readouterr().out.strip())
    assert printed["status"] == "DEFER_NO_PEER_ARTIFACTS" and printed["observed_staged"] == 0


def test_main_owner_missing(monkeypatch, tmp_path):
    with pytest.raises(ValueError, match="CANONICAL_OWNER_PLANNER_MISSING"):
        run_main(monkeypatch, ["--expected-head", HEAD, "--root", str(tmp_path),
                               "--out", str(tmp_path / "o")])


@pytest.mark.parametrize("bad", ["noequals", "=x", REPO + "=", "DUP"])
def test_main_invalid_mapping(monkeypatch, tmp_path, bad):
    root = make_owner_root(tmp_path / "root")
    if bad == "DUP":
        args = ["--pin", f"{REPO}={SOURCE}", "--pin", f"{REPO}={SOURCE}"]
    else:
        args = ["--pin", bad]
    with pytest.raises(ValueError, match="INVALID_MAPPING"):
        run_main(monkeypatch, ["--expected-head", HEAD, "--root", str(root),
                               "--out", str(tmp_path / "o"), *args])
    assert not (tmp_path / "o").exists()


def test_dunder_main_entrypoint(monkeypatch, tmp_path):
    import runpy
    monkeypatch.setattr("subprocess.run",
                        lambda *a, **k: SimpleNamespace(returncode=1, stdout=""))
    monkeypatch.setattr(sys, "argv", ["x", "--expected-head", HEAD, "--out", str(tmp_path / "o")])
    with pytest.raises(SystemExit, match="EXACT_HUB_SOURCE_HEAD_MISMATCH"):
        runpy.run_path(str(MOD_PATH), run_name="__main__")
