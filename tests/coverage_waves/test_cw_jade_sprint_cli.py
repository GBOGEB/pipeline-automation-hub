"""Behavioural coverage for mission-control/jade_temple/sprint/cli.py.

Targets what jade_temple/tests/test_jade_sprint_n3.py misses: git SHA guard,
fingerprint exclusions, optional jobs, cache receipt validation, lease/fail/
timeout paths, local_run, verify error paths and main() in every mode. All
subprocess use is faked on the loaded module; all outputs go to tmp_path.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SPRINT = REPO_ROOT / "mission-control" / "jade_temple" / "sprint"
DATA = REPO_ROOT / "mission-control" / "jade_temple" / "data" / "REPO_READINESS_NPLUS1.json"
HEAD = "0123456789abcdef0123456789abcdef01234567"


@pytest.fixture(scope="module")
def cli(tmp_path_factory):
    shadow_root = tmp_path_factory.mktemp("cw_sprint_shadow")
    if str(SPRINT) not in sys.path:
        sys.path.insert(0, str(SPRINT))
    # Bind cli's ``from model import ...`` to the sprint model regardless of
    # any other top-level ``model`` module cached by unrelated tests.
    mspec = importlib.util.spec_from_file_location("cw_sprint_model", SPRINT / "model.py")
    model = importlib.util.module_from_spec(mspec)
    mspec.loader.exec_module(model)
    saved = sys.modules.get("model")
    sys.modules["model"] = model
    try:
        spec = importlib.util.spec_from_file_location("cw_jade_sprint_cli", SPRINT / "cli.py")
        module = importlib.util.module_from_spec(spec)
        module.__file__ = str(shadow_root / "mission-control" / "jade_temple" / "sprint" / "cw_cli_shadow.py")
        spec.loader.exec_module(module)
    finally:
        if saved is None:
            sys.modules.pop("model", None)
        else:
            sys.modules["model"] = saved
    module._cw_shadow_root = shadow_root
    return module


class FakeProc:
    """Records argv; answers git rev-parse with HEAD and jobs per ``plan``."""

    def __init__(self, head=HEAD, git_code=0, plan=None):
        self.head = head
        self.git_code = git_code
        self.plan = plan or {}
        self.calls = []
        self.TimeoutExpired = subprocess.TimeoutExpired

    def run(self, argv, **kw):
        self.calls.append((list(argv), kw))
        if argv[:2] == ["git", "rev-parse"]:
            return subprocess.CompletedProcess(argv, self.git_code, self.head + "\n", "")
        key = next((Path(a).name for a in argv if a.endswith(".py")), argv[-1])
        outcome = self.plan.get(key, 0)
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(argv, kw.get("timeout"))
        return subprocess.CompletedProcess(argv, outcome, "out:" + argv[-1], "err")


@pytest.fixture
def fake_root(tmp_path):
    root = tmp_path / "repo"
    jade = root / "mission-control" / "jade_temple"
    (jade / "data").mkdir(parents=True)
    shutil.copyfile(DATA, jade / "data" / "REPO_READINESS_NPLUS1.json")
    (jade / "site").mkdir()
    (jade / "site" / "build_dashboard.py").write_text("x=1\n", encoding="utf-8")
    return root


def _job(jid="J", pool="LOCAL_PYTHON"):
    return {"id": jid, "pool": pool, "argv": ["py", "-c", jid], "timeout": 5}


# --- source_sha ---------------------------------------------------------------------

def test_source_sha_returns_stripped_head(cli, monkeypatch, tmp_path):
    fake = FakeProc()
    monkeypatch.setattr(cli, "subprocess", fake)
    assert cli.source_sha(tmp_path) == HEAD
    argv, kw = fake.calls[0]
    assert argv == ["git", "rev-parse", "HEAD"]
    assert kw["cwd"] == tmp_path and kw["timeout"] == 10


@pytest.mark.parametrize("head,code", [(HEAD, 128), (HEAD.upper(), 0), ("abc", 0)])
def test_source_sha_fails_closed(cli, monkeypatch, tmp_path, head, code):
    monkeypatch.setattr(cli, "subprocess", FakeProc(head=head, git_code=code))
    with pytest.raises(ValueError, match="^GIT_SOURCE_SHA_REQUIRED$"):
        cli.source_sha(tmp_path)


# --- input_fingerprint ------------------------------------------------------------

def test_fingerprint_excludes_generated_and_foreign_files(cli, fake_root):
    jade = fake_root / "mission-control" / "jade_temple"
    base, count = cli.input_fingerprint(fake_root, None)
    assert count == 2
    for rel in ("__pycache__/x.py", "qa/shot.json", "sprint/output/o.json",
                ".jade-cache/c.json", "site/image.png"):
        p = jade / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("noise", encoding="utf-8")
    assert cli.input_fingerprint(fake_root, None) == (base, 2)
    (jade / "site" / "new.md").write_text("doc", encoding="utf-8")
    changed, count = cli.input_fingerprint(fake_root, None)
    assert count == 3 and changed != base


def test_fingerprint_external_readback_is_included(cli, fake_root, tmp_path):
    base, count = cli.input_fingerprint(fake_root, None)
    ext = tmp_path / "n2.json"
    ext.write_text("{}", encoding="utf-8")
    digest, n = cli.input_fingerprint(fake_root, ext)
    assert n == count + 1 and digest != base
    internal = fake_root / "mission-control" / "jade_temple" / "data" / "REPO_READINESS_NPLUS1.json"
    assert cli.input_fingerprint(fake_root, internal) == (base, count)


def test_fingerprint_empty_source_fails(cli, tmp_path):
    (tmp_path / "mission-control" / "jade_temple").mkdir(parents=True)
    with pytest.raises(ValueError, match="^EMPTY_SOURCE_CONTENT_HASH$"):
        cli.input_fingerprint(tmp_path, None)


# --- jobs -------------------------------------------------------------------------------

def test_jobs_without_optional_scripts(cli, fake_root):
    ids = [j["id"] for j in cli.jobs(fake_root, "py", False)]
    assert ids == ["N1_CONTRACT_TESTS", "N1_GREEN_CHECK", "N1_SITE_CHECK"]


def test_jobs_with_burndown_and_browser(cli, fake_root):
    jade = fake_root / "mission-control" / "jade_temple"
    (jade / "site" / "build_burndown.py").write_text("", encoding="utf-8")
    (jade / "tools").mkdir()
    (jade / "tools" / "run_nplus1_browser_qa.py").write_text("", encoding="utf-8")
    work = cli.jobs(fake_root, "py", True)
    assert [j["id"] for j in work] == ["N1_CONTRACT_TESTS", "N1_GREEN_CHECK", "N1_SITE_CHECK",
                                       "N2_BURNDOWN_CHECK", "OPTIONAL_LOCAL_BROWSER"]
    browser = work[-1]
    assert browser["pool"] == "LOCAL_BROWSER" and browser["timeout"] == 420
    assert work[3]["argv"][-1] == "--check"


def test_jobs_browser_requires_script(cli, fake_root):
    with pytest.raises(ValueError, match="^BROWSER_SCRIPT_NOT_FOUND$"):
        cli.jobs(fake_root, "py", True)


# --- cache_valid ---------------------------------------------------------------------------

def _cache_doc(cli, job, inputs="b" * 64, **over):
    doc = {"schema": "jade.temple.local-cache.v1", "head": HEAD, "source_digest": inputs,
           "job": job["id"], "key": cli.cachekey(job, HEAD, inputs),
           "completed": datetime.now(timezone.utc).isoformat(),
           "state": "LOCAL_TEST_PASS", "authority": "LOCAL_ONLY"}
    doc.update(over)
    return doc


def test_cache_valid_accepts_fresh_receipt(cli, tmp_path):
    job = _job()
    path = tmp_path / "c.json"
    doc = _cache_doc(cli, job)
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert cli.cache_valid(path, HEAD, "b" * 64, job, 1) == doc


@pytest.mark.parametrize("over", [
    {"state": "LOCAL_TEST_FAIL"},
    {"authority": "NATIVE"},
    {"key": "0" * 64},
    {"completed": (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()},
    {"completed": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()},
    {"completed": "not-a-date"},
])
def test_cache_valid_rejects_bad_receipts(cli, tmp_path, over):
    job = _job()
    path = tmp_path / "c.json"
    path.write_text(json.dumps(_cache_doc(cli, job, **over)), encoding="utf-8")
    assert cli.cache_valid(path, HEAD, "b" * 64, job, 2) is None


def test_cache_valid_missing_or_corrupt(cli, tmp_path):
    assert cli.cache_valid(tmp_path / "nope.json", HEAD, "b", _job(), 1) is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert cli.cache_valid(bad, HEAD, "b", _job(), 1) is None
    missing_key = tmp_path / "mk.json"
    doc = _cache_doc(cli, _job(), inputs="b")
    del doc["completed"]
    missing_key.write_text(json.dumps(doc), encoding="utf-8")
    assert cli.cache_valid(missing_key, HEAD, "b", _job(), 1) is None


# --- run_one --------------------------------------------------------------------------------

def test_run_one_defers_when_lease_held(cli, monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "subprocess", FakeProc())
    job = _job()
    cache = tmp_path / "cache"
    cache.mkdir()
    key = cli.cachekey(job, HEAD, "i")
    (cache / (key + ".lease")).write_text("other", encoding="utf-8")
    r = cli.run_one(job, tmp_path, tmp_path, cache, HEAD, "i", 12, False, 0)
    assert r["status"] == "DEFER_LOCAL_LEASE"
    assert r["duration_seconds"] is None and r["release_credit"] == 0
    assert (cache / (key + ".lease")).read_text(encoding="utf-8") == "other"


def test_run_one_failure_writes_log_but_no_cache(cli, monkeypatch, tmp_path):
    fake = FakeProc(plan={"J": 3})
    monkeypatch.setattr(cli, "subprocess", fake)
    job = _job()
    cache = tmp_path / "cache"
    r = cli.run_one(job, tmp_path, tmp_path, cache, HEAD, "i", 12, False, 0)
    assert r["status"] == "LOCAL_TEST_FAIL" and r["exit_code"] == 3
    log = (tmp_path / "J.log").read_text(encoding="utf-8")
    assert log == "out:J\n--- STDERR ---\nerr"
    assert sorted(p.name for p in cache.iterdir()) == []
    assert fake.calls[0][1]["timeout"] == 5


def test_run_one_timeout(cli, monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "subprocess", FakeProc(plan={"J": "timeout"}))
    r = cli.run_one(_job(), tmp_path, tmp_path, tmp_path / "c", HEAD, "i", 12, False, 0)
    assert r["status"] == "LOCAL_TIMEOUT" and r["exit_code"] is None
    assert "timed out" in (tmp_path / "J.log").read_text(encoding="utf-8")


def test_run_one_no_cache_reruns_despite_valid_receipt(cli, monkeypatch, tmp_path):
    fake = FakeProc()
    monkeypatch.setattr(cli, "subprocess", fake)
    cache = tmp_path / "c"
    first = cli.run_one(_job(), tmp_path, tmp_path, cache, HEAD, "i", 12, False, 0)
    assert first["status"] == "LOCAL_TEST_PASS"
    hit = cli.run_one(_job(), tmp_path, tmp_path, cache, HEAD, "i", 12, False, 0)
    assert hit["status"] == "LOCAL_CACHE_HIT"
    again = cli.run_one(_job(), tmp_path, tmp_path, cache, HEAD, "i", 12, True, 0)
    assert again["status"] == "LOCAL_TEST_PASS"
    assert len(fake.calls) == 2


# --- local_run --------------------------------------------------------------------------------

def test_local_run_reports_counts_and_p95(cli, monkeypatch, fake_root, tmp_path):
    jade = fake_root / "mission-control" / "jade_temple"
    (jade / "tools").mkdir()
    (jade / "tools" / "run_nplus1_browser_qa.py").write_text("", encoding="utf-8")
    fake = FakeProc(plan={"build_green.py": 1, "run_nplus1_browser_qa.py": "timeout"})
    monkeypatch.setattr(cli, "subprocess", fake)
    out = tmp_path / "out"
    out.mkdir()
    rep = cli.local_run(fake_root, out, tmp_path / "cache", HEAD, "i", 1, 12, True, True)
    status = {r["id"]: r["status"] for r in rep["results"]}
    assert status == {"N1_CONTRACT_TESTS": "LOCAL_TEST_PASS", "N1_GREEN_CHECK": "LOCAL_TEST_FAIL",
                      "N1_SITE_CHECK": "LOCAL_TEST_PASS", "OPTIONAL_LOCAL_BROWSER": "LOCAL_TIMEOUT"}
    assert rep["jobs_attempted"] == 4
    assert (rep["local_pass"], rep["local_cache_hits"], rep["local_failures"]) == (2, 0, 2)
    assert isinstance(rep["local_queue_p95_seconds"], float)
    assert rep["release_admission"] == "HOLD" and rep["external_worker_dispatches"] == 0
    assert json.loads((out / "LOCAL_RUN.json").read_text(encoding="utf-8")) == rep


def test_local_run_all_deferred_has_no_p95(cli, monkeypatch, fake_root, tmp_path):
    monkeypatch.setattr(cli, "run_one", lambda job, *a: {"id": job["id"], "pool": job["pool"],
                                                         "status": "DEFER_LOCAL_LEASE",
                                                         "queue_wait_seconds": 0})
    out = tmp_path / "out"
    out.mkdir()
    rep = cli.local_run(fake_root, out, tmp_path / "c", HEAD, "i", 4, 12, False, False)
    assert rep["local_queue_p95_seconds"] is None
    assert rep["local_pass"] == 0 and rep["jobs_attempted"] == 3


@pytest.mark.parametrize("workers", [0, 5, 2.0])
def test_local_run_worker_bound(cli, tmp_path, workers):
    with pytest.raises(ValueError, match="^WORKER_BOUND_1_TO_4$"):
        cli.local_run(tmp_path, tmp_path, tmp_path, HEAD, "i", workers, 12, True, False)


# --- seal / verify ---------------------------------------------------------------------------

def _bundle(cli, monkeypatch, fake_root, out):
    monkeypatch.setattr(cli, "subprocess", FakeProc())
    return cli.write_bundle(fake_root, out)


def test_seal_includes_valid_local_run(cli, monkeypatch, fake_root, tmp_path):
    out = tmp_path / "out"
    head, inputs = _bundle(cli, monkeypatch, fake_root, out)
    assert head == HEAD
    (out / "LOCAL_RUN.json").write_bytes(cli.canonical({
        "head": head, "source_digest": inputs, "release_admission": "HOLD",
        "point_release": "TARGET_NOT_ACHIEVED", "external_worker_dispatches": 0}))
    receipt = cli.seal(out, head, inputs)
    assert "LOCAL_RUN.json" in receipt["files"]
    assert set(receipt["files"]) == set(cli.HASH_FILES) | {"LOCAL_RUN.json"}
    assert cli.verify(fake_root, out, head, inputs) == receipt
    (out / "LOCAL_RUN.json").unlink()
    with pytest.raises(ValueError, match="^INCOMPLETE_MANIFEST$"):
        cli.verify(fake_root, out, head, inputs)


def test_verify_error_paths(cli, monkeypatch, fake_root, tmp_path):
    out = tmp_path / "out"
    head, inputs = _bundle(cli, monkeypatch, fake_root, out)
    with pytest.raises(ValueError, match="^NO_SHA256_MANIFEST$"):
        cli.verify(fake_root, out, head, inputs)
    receipt = cli.seal(out, head, inputs)
    with pytest.raises(ValueError, match="^STALE_SOURCE_RECEIPT$"):
        cli.verify(fake_root, out, "f" * 40, inputs)
    with pytest.raises(ValueError, match="^STALE_SOURCE_RECEIPT$"):
        cli.verify(fake_root, out, head, "x")
    promoted = dict(receipt, admission="PASS")
    (out / "SHA256_MANIFEST.json").write_bytes(cli.canonical(promoted))
    with pytest.raises(ValueError, match="^RECEIPT_AUTHORITY$"):
        cli.verify(fake_root, out, head, inputs)
    (out / "SHA256_MANIFEST.json").write_bytes(cli.canonical(receipt))
    (out / "SPRINT_DAG.json").unlink()
    with pytest.raises(ValueError, match="^HASH_DRIFT:SPRINT_DAG.json$"):
        cli.verify(fake_root, out, head, inputs)


# --- main -------------------------------------------------------------------------------------

def _argv(fake_root, out, *extra):
    return ["--repo-root", str(fake_root), "--out", str(out), *extra]


def test_main_plan_mode(cli, monkeypatch, fake_root, tmp_path, capsys):
    fake = FakeProc()
    monkeypatch.setattr(cli, "subprocess", fake)
    out = tmp_path / "out"
    assert cli.main(_argv(fake_root, out, "--expected-head", HEAD)) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed == {"admission": "HOLD", "head": HEAD, "local": None, "mode": "plan",
                       "output": str(out.resolve()), "release": "TARGET_NOT_ACHIEVED"}
    assert not (out / "LOCAL_RUN.json").exists()
    assert all(c[0][0] == "git" for c in fake.calls)
    manifest = json.loads((out / "SHA256_MANIFEST.json").read_text(encoding="utf-8"))
    assert set(manifest["files"]) == set(cli.HASH_FILES)


def test_main_local_mode_with_failure_exits_one(cli, monkeypatch, fake_root, tmp_path, capsys):
    monkeypatch.setattr(cli, "subprocess", FakeProc(plan={"build_dashboard.py": 2}))
    out = tmp_path / "out"
    cache = tmp_path / "cachedir"
    rc = cli.main(_argv(fake_root, out, "--mode", "local", "--cache-dir", str(cache),
                        "--max-workers", "1"))
    assert rc == 1
    printed = json.loads(capsys.readouterr().out)
    assert printed["local"] == {"passed": 2, "cache_hits": 0, "failed": 1}
    assert len([p for p in cache.iterdir() if p.suffix == ".json"]) == 2
    manifest = json.loads((out / "SHA256_MANIFEST.json").read_text(encoding="utf-8"))
    assert "LOCAL_RUN.json" in manifest["files"]


def test_main_full_mode_uses_default_cache_and_hits_on_rerun(cli, monkeypatch, fake_root, tmp_path, capsys):
    monkeypatch.setattr(cli, "subprocess", FakeProc())
    out = tmp_path / "work" / "out"
    assert cli.main(_argv(fake_root, out, "--mode", "full")) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["local"] == {"passed": 3, "cache_hits": 0, "failed": 0}
    assert (tmp_path / "work" / ".jade-cache").is_dir()
    assert cli.main(_argv(fake_root, out, "--mode", "full")) == 0
    assert json.loads(capsys.readouterr().out)["local"] == {"passed": 0, "cache_hits": 3, "failed": 0}


def test_main_verify_mode_with_nplus2(cli, monkeypatch, fake_root, tmp_path, capsys):
    monkeypatch.setattr(cli, "subprocess", FakeProc())
    data = json.loads(DATA.read_text(encoding="utf-8"))
    n2 = {"schema": "jade.temple.fleet_readback.v2", "merge_admission": "HOLD",
          "authority_transfer": False,
          "rows": [{"repo": r["repo"], "current_head": r["head_readback"],
                    "owner_J5_point_release": None} for r in data["rows"]]}
    n2_path = tmp_path / "n2.json"
    n2_path.write_text(json.dumps(n2), encoding="utf-8")
    out = tmp_path / "out"
    assert cli.main(_argv(fake_root, out, "--nplus2", str(n2_path))) == 0
    capsys.readouterr()
    assert cli.main(_argv(fake_root, out, "--mode", "verify", "--nplus2", str(n2_path))) == 0
    assert json.loads(capsys.readouterr().out) == {"verified": True, "admission": "HOLD", "head": HEAD}
    # Without the readback the fingerprint differs, so the receipt is stale.
    with pytest.raises(ValueError, match="^STALE_SOURCE_RECEIPT$"):
        cli.main(_argv(fake_root, out, "--mode", "verify"))


@pytest.mark.parametrize("extra,msg", [
    (["--max-workers", "0"], "WORKER_BOUND_1_TO_4"),
    (["--max-workers", "5"], "WORKER_BOUND_1_TO_4"),
    (["--cache-ttl-hours", "0"], "CACHE_TTL_1_TO_72_HOURS"),
    (["--cache-ttl-hours", "73"], "CACHE_TTL_1_TO_72_HOURS"),
    (["--expected-head", "f" * 40], "EXPECTED_HEAD_MISMATCH"),
])
def test_main_argument_guards(cli, monkeypatch, fake_root, tmp_path, extra, msg):
    monkeypatch.setattr(cli, "subprocess", FakeProc())
    out = tmp_path / "out"
    with pytest.raises(ValueError, match="^" + msg + "$"):
        cli.main(_argv(fake_root, out, *extra))
    assert not out.exists()


def test_main_missing_nplus2(cli, monkeypatch, fake_root, tmp_path):
    monkeypatch.setattr(cli, "subprocess", FakeProc())
    with pytest.raises(ValueError, match="^N2_SOURCE_MISSING$"):
        cli.main(_argv(fake_root, tmp_path / "out", "--nplus2", str(tmp_path / "absent.json")))


def test_main_output_inside_sprint_source_rejected(cli, monkeypatch, fake_root):
    monkeypatch.setattr(cli, "subprocess", FakeProc())
    out = fake_root / "mission-control" / "jade_temple" / "sprint" / "output"
    with pytest.raises(ValueError, match="^OUTPUT_MUST_BE_OUTSIDE_SPRINT_SOURCE$"):
        cli.main(_argv(fake_root, out))
    assert not out.exists()


def test_main_default_repo_root_is_derived_from_module_file(cli, monkeypatch, tmp_path):
    shadow = cli._cw_shadow_root
    assert cli.ROOT == shadow
    monkeypatch.setattr(cli, "subprocess", FakeProc())
    with pytest.raises(ValueError, match="^OUTPUT_MUST_BE_OUTSIDE_SPRINT_SOURCE$"):
        cli.main(["--out", str(shadow / "mission-control" / "jade_temple" / "sprint" / "x")])


def test_main_via_sys_argv_rejects_unknown_mode(cli, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(sys, "argv", ["cli.py", "--out", str(tmp_path), "--mode", "release"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2
    assert "invalid choice: 'release'" in capsys.readouterr().err
