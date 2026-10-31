"""Coverage wave 10: mission-control/jade_temple/devops/census.py.

Faked git / subprocess / HTTP only; every read and write of census data goes through tmp_path.
The module itself is JADE-pinned and is never written.
"""
import hashlib
import importlib.util
import json
import runpy
import subprocess
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("yaml")

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_PATH = REPO_ROOT / "mission-control" / "jade_temple" / "devops" / "census.py"
_spec = importlib.util.spec_from_file_location("cw_w10_jade_census_mod", MOD_PATH)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

HEAD = "a" * 40
BASE = "b" * 40


def blob_oid(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\x00" + data).hexdigest()


class Proc(SimpleNamespace):
    pass


def fake_run(returncode=0, stdout=b"", stderr=b""):
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        return Proc(returncode=returncode, stdout=stdout, stderr=stderr)
    run.calls = calls
    return run


# --------------------------------------------------------------------------- Git layer (subprocess faked)
def test_git_run_raises_on_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(mod.subprocess, "run", fake_run(returncode=1, stderr=b"  boom  "))
    with pytest.raises(RuntimeError, match="git status: boom"):
        mod.Git(tmp_path).run("status")


def test_git_cat_skips_missing_objects(tmp_path, monkeypatch):
    out = b"1111 missing\n2222 blob 3\nxyz\n"
    monkeypatch.setattr(mod.subprocess, "run", fake_run(stdout=out))
    assert mod.Git(tmp_path).cat(["1111", "2222"]) == {"2222": b"xyz"}


def test_git_first_parent_not_ancestor(tmp_path, monkeypatch):
    monkeypatch.setattr(mod.subprocess, "run", fake_run(returncode=1))
    assert mod.Git(tmp_path).first_parent(BASE, HEAD) is None


# --------------------------------------------------------------------------- fetch_repo (Git methods faked)
def _fake_git_methods(monkeypatch, rev_map):
    runs = []
    monkeypatch.setattr(mod.Git, "run", lambda self, *a, **k: runs.append(a) or b"")
    monkeypatch.setattr(mod.Git, "rev", lambda self, ref: rev_map.get(ref))
    monkeypatch.setattr(mod.Git, "ls_tree", lambda self, sha: [])
    monkeypatch.setattr(mod.Git, "missing", lambda self, sha: set())
    monkeypatch.setattr(mod, "refresh_tags", lambda d: True)
    return runs


def test_fetch_repo_existing_cache_without_baseline(tmp_path, monkeypatch):
    mod.cache_dir(tmp_path, "o/r").mkdir(parents=True)
    runs = _fake_git_methods(monkeypatch, {"refs/heads/main": HEAD})
    info = mod.fetch_repo(tmp_path, "o/r", "main", None)
    assert info == {"repo": "o/r", "ok": True, "head": HEAD, "baseline_fetched": False, "blobs_fetched": 0}
    assert runs[0][0] == "fetch"


def test_fetch_repo_unreachable_baseline_is_fetched_then_dropped(tmp_path, monkeypatch):
    mod.cache_dir(tmp_path, "o/r").mkdir(parents=True)
    runs = _fake_git_methods(monkeypatch, {"refs/heads/main": HEAD})
    info = mod.fetch_repo(tmp_path, "o/r", "main", BASE)
    assert info["ok"] is True and info["baseline_fetched"] is False
    assert any(BASE in a for a in runs)


# --------------------------------------------------------------------------- content analysis
def test_py_info_class_body_with_non_function_members():
    info = mod.py_info("class A:\n    x = 1\n    def test_m(self):\n        pass\n")
    assert info["methods"] == 1 and info["tests"] == 1 and info["symbols"] == ["A"]


class FakeGit:
    """In-memory git: one tree per commit, every blob present."""

    def __init__(self, trees, refs=None, dates=None):
        self.trees = trees  # sha -> {path: bytes}
        self.refs = refs or {}
        self.dates = dates or {}
        self.blobs = {blob_oid(v): v for t in trees.values() for v in t.values()}

    def rev(self, ref):
        if ref in self.refs:
            return self.refs[ref]
        return ref if ref in self.trees else None

    def commit_meta(self, sha):
        return {"sha": sha, "tree": "c" * 40, "date": self.dates.get(sha, "2026-10-20T00:00:00+00:00")}

    def ls_tree(self, sha):
        rows = [("100644", "blob", blob_oid(v), p) for p, v in sorted(self.trees[sha].items())]
        rows.append(("160000", "commit", "d" * 40, "vendored-sub"))
        rows.append(("040000", "tree", "e" * 40, "odd-tree-row"))
        return rows

    def missing(self, sha):
        return set()

    def cat(self, oids):
        return {o: self.blobs[o] for o in oids if o in self.blobs}

    def first_parent(self, base, head):
        return [(head, "fix: thing")]

    def diff_tree(self, base, head):
        return Counter({"M": 1})


WORKFLOW = b"""name: Admission gate
on:
  schedule:
    - cron: '0 0 * * *'
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pytest -q
"""

FILES = {
    "README.md": b"# demo\n",
    "pyproject.toml": b'[project]\nversion = "1.2.3"\n\n[tool.coverage.report]\nfail_under = 81.5\n',
    "setup.cfg": b"[metadata]\nname = demo\n",  # build manifest without a coverage floor
    "Dockerfile": b"FROM python:3.12\nHEALTHCHECK CMD true\n",
    "requirements.txt": b"# pinned\nrequests==2.0\n",
    "pkg/core.py": b"def add(a, b):\n    return a + b\n",
    "tests/test_core.py": b"from pkg.core import add\n\ndef test_add():\n    assert add(1, 2) == 3\n",
    ".github/workflows/gate.yml": WORKFLOW,
}


def test_scan_commit_manifest_signals_and_submodule():
    g = FakeGit({HEAD: FILES})
    sc = mod.scan_commit(g, "o/r", HEAD)
    assert sc["kinds"]["submodule"] == 1
    assert sc["coverage_config_floor"] == 81.5
    assert sc["healthcheck"] is True
    assert sc["pinned_requirements"] is True
    assert sc["declared_version"] is True
    assert sc["unread"] == 0


# --------------------------------------------------------------------------- wf_facts (synthetic records)
def _sig(**kw):
    s = {k: False for k in ("lint", "typecheck", "precommit", "build", "security", "provenance", "verify",
                            "alerting", "tests", "zero_test_guard", "implicit_zero_guard", "artifact_upload",
                            "digest", "coverage", "release", "deploy", "soft_fail_tests")}
    s.update(actions_total=1, actions_pinned=1, coverage_floor=None)
    s.update(kw)
    return s


def test_wf_facts_release_deploy_rollback_and_floors():
    dp_pass = {g: "PASS" for g in mod.W.DP_CORE + mod.W.DP_VERIFIED}
    wf = {"parse_error": False, "permissions": "default", "triggers": ["push", "workflow_dispatch"],
          "name": "deploy", "path": ".github/workflows/deploy.yml", "push_tags": True,
          "dispatch_inputs": ["ref"],
          "jobs": [{"id": "test", "permissions": "read-all", "def_sha256": "x", "needs": [], "oid": "j:test"},
                   {"id": "ship", "permissions": "read-all", "def_sha256": "y", "needs": ["test"],
                    "environment": "production", "dp": dp_pass, "oid": "j:ship"},
                   {"id": "nosig", "permissions": "read-all", "oid": "j:nosig"}],
          "sig": {"test": _sig(tests=True, coverage=True, coverage_floor=90.0),
                  "ship": _sig(build=True, provenance=True, deploy=True)}}
    broken = {"parse_error": True}
    out = mod.wf_facts([wf, broken], cov_cfg=80.0)
    assert out["parse_errors"] == 1 and out["workflows"] == 1
    assert out["release"] == 1 and out["release_gated"] == 1 and out["release_provenance"] == 1
    assert out["deploy"] == 1 and out["deploy_env"] == 1
    assert out["deploy_contract_core"] == 1 and out["deploy_verified"] == 1
    assert out["rollback"] == 1 and wf["sig"]["ship"]["rollback"] is True
    assert out["unguarded_test_jobs"] == 1
    assert out["coverage_floor_max"] == 90.0


# --------------------------------------------------------------------------- probes and indices
def test_probe_api_non_refusal_error_and_no_environments():
    replies = {"/branches/main": (404, b""), "/environments": (200, b'{"environments": []}')}

    def get(url):
        return replies[url.split("/repos/o/r", 1)[1]]
    budget = [10, 0, None]
    out = mod.probe_api("o/r", "main", budget, get)
    assert out["protected"] is None and out["environments"] == []
    assert out["protected_production"] is False and out["deployments"] is None
    assert budget == [8, 2, None]


def test_red_trace_index_without_recovered_windows():
    fed = {"repositories": [{"repository": "o/r", "counts": {}, "currently_red": 0, "currently_red_stale": 0,
                             "observed_at_utc": "2026-10-01T00:00:00Z",
                             "non_green": [{"class": "EVER_RED", "window": None, "current": "GREEN",
                                            "path": "p", "stale": False, "pinned": False}]}]}
    assert mod.red_trace_index(fed)["o/r"]["ci_mttr_hours_median"] is None


def test_evidence_for_gates_and_schedule():
    sc = {"name": "r", "evidence": {k: [] for k in mod.L.STAGE_KEYS}, "test_files": [],
          "workflows": [{"parse_error": False, "name": "Admission gate", "path": ".github/workflows/g.yml",
                         "triggers": ["schedule"], "jobs": [], "sig": {}, "oid": "jade:wf:r:g"},
                        {"parse_error": True, "oid": "jade:wf:r:bad"}]}
    assert mod.evidence_for("control.gates", sc) == ["jade:wf:r:g"]
    assert mod.evidence_for("monitor.schedule", sc) == ["jade:wf:r:g"]


def test_stage_contracts_with_hub_tree():
    hub = FakeGit({HEAD: {mod.CONTRACTS["S0_PLAN"][0]: b"x"}})
    out = mod.stage_contracts(hub, HEAD)
    assert out["S0_PLAN"][0]["present"] is True and out["S0_PLAN"][1]["present"] is False


# --------------------------------------------------------------------------- scan end to end on tmp data
def test_scan_hub_with_red_trace_and_no_baseline(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir()
    fed = {"digest_sha256": "f" * 64, "observed_at_utc": "2026-10-01T00:00:00Z",
           "repositories": [{"repository": mod.HUB, "counts": {"RED": 1}, "currently_red": 1,
                             "currently_red_stale": 0, "observed_at_utc": "2026-10-01T00:00:00Z",
                             "non_green": [{"class": "RED_TO_GREEN", "window": {"red_hours": 3}, "current": "GREEN",
                                            "path": "x", "stale": False, "pinned": False},
                                           {"class": "EVER_RED", "window": None, "current": "RED",
                                            "path": ".github/workflows/gate.yml", "stale": False,
                                            "pinned": False}]}]}
    (tmp_path / "data" / "RED_TRACE_FEDERATION_N8.json").write_text(json.dumps(fed), encoding="utf-8")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    roster = {"repositories": [{"rank": 1, "repo": mod.HUB, "branch": "master", "cohort_lane": "core",
                                "role": "hub"}]}
    roster_path = tmp_path / "roster.json"
    roster_path.write_text(json.dumps(roster), encoding="utf-8")
    cache = tmp_path / "cache"
    mod.cache_dir(cache, mod.HUB).mkdir(parents=True)
    hub_files = dict(FILES, **{mod.CONTRACTS["S0_PLAN"][0]: b"# spine\n"})
    fake = FakeGit({HEAD: hub_files}, refs={"refs/heads/master": HEAD})
    monkeypatch.setattr(mod, "Git", lambda d: fake)
    census, obj = mod.scan(cache, roster_path, "2026-10-31T00:00:00Z", probe_pages_on=False, probe_api_on=False)
    rec = census["repos"][0]
    assert rec["reachable"] is True and rec["head_sha"] == HEAD
    assert rec["delta"]["reachable"] is False and rec["delta"]["baseline_sha"] is None
    roots = rec["red_trace"]["first_red_roots"]
    assert roots[0]["blob_oid"] == blob_oid(WORKFLOW)
    contract = census["lifecycle"]["stages"][0]["contract"][0]
    assert contract["present"] is True
    assert obj["census_digest_sha256"] == census["digest_sha256"]


# --------------------------------------------------------------------------- CLI
def test_main_fetch_only_filter_and_runtime_error(tmp_path, monkeypatch, capsys):
    roster = {"repositories": [{"rank": 1, "repo": "o/a", "branch": "main"},
                               {"rank": 2, "repo": "o/b", "branch": "main"}]}
    roster_path = tmp_path / "roster.json"
    roster_path.write_text(json.dumps(roster), encoding="utf-8")
    seen = []

    def boom(cache, repo, branch, base):
        seen.append(repo)
        raise RuntimeError("git fetch: network down")
    monkeypatch.setattr(mod, "fetch_repo", boom)
    rc = mod.main(["fetch", "--cache", str(tmp_path / "cache"), "--roster", str(roster_path), "--only", "o/b"])
    assert rc == 0 and seen == ["o/b"]
    log = json.loads((tmp_path / "cache" / "fetch-log.json").read_text(encoding="utf-8"))
    assert log == {"o/b": {"repo": "o/b", "ok": False, "error": "git fetch: network down"}}
    assert "network down" in capsys.readouterr().out


def test_main_fetch_timeout_is_recorded(tmp_path, monkeypatch):
    roster_path = tmp_path / "roster.json"
    roster_path.write_text(json.dumps({"repositories": [{"rank": 1, "repo": "o/a", "branch": "main"}]}),
                           encoding="utf-8")

    def slow(*a):
        raise subprocess.TimeoutExpired("git clone", 1)
    monkeypatch.setattr(mod, "fetch_repo", slow)
    assert mod.main(["fetch", "--cache", str(tmp_path / "c"), "--roster", str(roster_path)]) == 0
    log = json.loads((tmp_path / "c" / "fetch-log.json").read_text(encoding="utf-8"))
    assert log["o/a"]["ok"] is False and "timed out" in log["o/a"]["error"]


def test_dunder_main_help_exits_zero(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["census.py", "--help"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(MOD_PATH), run_name="__main__")
    assert exc.value.code == 0
    assert "usage" in capsys.readouterr().out
