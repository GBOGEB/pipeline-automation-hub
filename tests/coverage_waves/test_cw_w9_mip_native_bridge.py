"""Coverage wave 9: mission-control/federation-atlas/flightdeck/pulses/mip_native_bridge.py.

GitHub REST, the ABACUS checkout's ``git rev-parse`` and the downstream
consumer are faked; no network, git or real producer is used.
"""
from __future__ import annotations

import copy
import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PULSES = REPO_ROOT / "mission-control" / "federation-atlas" / "flightdeck" / "pulses"
MOD_PATH = PULSES / "mip_native_bridge.py"
if str(PULSES) not in sys.path:
    sys.path.insert(0, str(PULSES))
_spec = importlib.util.spec_from_file_location("cw_w9_mip_native_bridge_mod", MOD_PATH)
m = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = m
_spec.loader.exec_module(m)

SHA = "a" * 40
PIN = "2" * 40
PRODUCER = '''
def summarize(native):
    return {"runs": len(native["runs"]), "jobs": len(native["jobs"])}
'''


def run(identity, attempt=1):
    return {"id": identity, "run_attempt": attempt, "head_sha": SHA, "name": "CI",
            "path": ".github/workflows/ci.yml", "event": "pull_request",
            "html_url": "https://github.com/GBOGEB/ABACUS/actions/runs/%d" % identity,
            "status": "completed", "conclusion": "success", "created_at": "t"}


def job(identity, run_id, steps=True, runner=False):
    j = {"id": identity, "run_id": run_id, "run_attempt": 1, "head_sha": SHA, "name": "j",
         "status": "completed", "conclusion": "success", "created_at": "t",
         "started_at": "t", "completed_at": "t"}
    if steps:
        j["steps"] = [{"name": "s", "number": 1, "status": "completed", "conclusion": "success", "x": 1}]
    if runner:
        j["runner_id"] = 7
    return j


class Api:
    """Fake GitHub REST keyed by path; records requests."""

    def __init__(self, runs=None, jobs=None):
        self.runs = runs if runs is not None else {401: run(401)}
        self.jobs = jobs if jobs is not None else {401: [job(601, 401, runner=True), job(602, 401, steps=False)]}
        self.census = None
        self.paths = []

    def __call__(self, path, token=None):
        self.paths.append((path, token))
        if "event=pull_request" in path:
            if self.census is not None:
                return copy.deepcopy(self.census)
            runs = list(self.runs.values())
            return {"total_count": len(runs), "workflow_runs": copy.deepcopy(runs)}
        rid = int(path.split("/")[6].split("?")[0])
        if "/jobs?" in path:
            page = int(path.split("page=")[-1])
            js = self.jobs[rid]
            return {"total_count": len(js), "jobs": copy.deepcopy(js[(page - 1) * 100:page * 100])}
        return copy.deepcopy(self.runs[rid])


def manifest(selections=([401, 1],), head=SHA):
    sel = [list(x) for x in selections]
    return {"schema": "code-purple.mip.native-pr-census.v1", "repository": "GBOGEB/ABACUS",
            "event": "pull_request", "head_sha": head, "expected_total": len(sel), "run_attempts": sel}


# ------------------------------------------------------------------ helpers
def test_require_and_integer():
    m.require(True, "x")
    with pytest.raises(ValueError, match="boom"):
        m.require(False, "boom")
    assert m.integer(1) and not m.integer(0) and not m.integer(True) and not m.integer("1")


# ------------------------------------------------------------------ https_get
class _Resp:
    def __init__(self, status, body=b'{"id": 401}'):
        self.status = status
        self._b = io.BytesIO(body)

    def read(self, size=-1):
        return self._b.read(size)


def _conn_factory(status, log):
    class Conn:
        def __init__(self, host, timeout):
            self.host, self.timeout, self.closed = host, timeout, False
            log.append(self)

        def request(self, method, path, headers):
            self.method, self.path, self.headers = method, path, headers

        def getresponse(self):
            return _Resp(status)

        def close(self):
            self.closed = True
    return Conn


def test_https_get_census_path_with_token(monkeypatch):
    log = []
    monkeypatch.setattr(m, "HTTPSConnection", _conn_factory(200, log))
    path = "/repos/GBOGEB/ABACUS/actions/runs?head_sha=" + SHA + "&event=pull_request&per_page=100"
    assert m.https_get(path, token="test-token") == {"id": 401}
    c = log[0]
    assert (c.host, c.timeout, c.method, c.path) == ("api.github.com", 25, "GET", path)
    assert c.headers["Authorization"] == "Bearer test-token" and c.closed


def test_https_get_jobs_path_without_token_and_non_200(monkeypatch):
    log = []
    monkeypatch.setattr(m, "HTTPSConnection", _conn_factory(404, log))
    path = "/repos/GBOGEB/ABACUS/actions/runs/401/attempts/1/jobs?per_page=100&page=2"
    with pytest.raises(ValueError, match="HTTP 404"):
        m.https_get(path)
    assert "Authorization" not in log[0].headers and log[0].closed


@pytest.mark.parametrize("path", ["/repos/GBOGEB/ABACUS/actions/runs/0",
                                  "/repos/GBOGEB/other/actions/runs/1",
                                  "/repos/GBOGEB/ABACUS/actions/runs?head_sha=" + SHA])
def test_https_get_rejects_inexact_paths(monkeypatch, path):
    monkeypatch.setattr(m, "HTTPSConnection", None)
    with pytest.raises(ValueError, match="exact native"):
        m.https_get(path)


# ------------------------------------------------------------------ validate_manifest
def test_validate_manifest_ok():
    api = Api()
    head, sel = m.validate_manifest(manifest(), getter=api)
    assert head == SHA and sel == [[401, 1]]
    assert api.paths[0][0].endswith("head_sha=" + SHA + "&event=pull_request&per_page=100")


@pytest.mark.parametrize("mutate, msg", [
    (lambda q: q.update(schema="x"), "schema/owner"),
    (lambda q: q.update(head_sha=None), "exact source SHA"),
    (lambda q: q.update(expected_total=0), "incomplete or duplicate"),
    (lambda q: q.update(run_attempts="x"), "incomplete or duplicate"),
    (lambda q: q.update(run_attempts=[[401, 1, 2]]), "incomplete or duplicate"),
    (lambda q: q.update(run_attempts=[[401, 0]]), "incomplete or duplicate"),
    (lambda q: q.update(run_attempts=[[401, 1], [401, 2]], expected_total=2), "incomplete or duplicate"),
])
def test_validate_manifest_rejects_bad_manifest(mutate, msg):
    q = manifest()
    mutate(q)
    with pytest.raises(ValueError, match=msg):
        m.validate_manifest(q, getter=Api())
    with pytest.raises(ValueError, match="schema/owner"):
        m.validate_manifest([], getter=Api())


@pytest.mark.parametrize("census", [
    [],
    {"total_count": 2, "workflow_runs": []},
    {"total_count": 1, "workflow_runs": "x"},
    {"total_count": 1, "workflow_runs": []},
])
def test_validate_manifest_population_changed(census):
    api = Api()
    api.census = census
    with pytest.raises(ValueError, match="population changed"):
        m.validate_manifest(manifest(), getter=api)


@pytest.mark.parametrize("item", [
    "x",
    dict(run(401), head_sha="b" * 40),
    dict(run(401), event="push"),
    dict(run(401), id=0),
    dict(run(401), run_attempt=None),
])
def test_validate_manifest_item_identity_mismatch(item):
    api = Api()
    api.census = {"total_count": 1, "workflow_runs": [item]}
    with pytest.raises(ValueError, match="identity/attempt mismatch"):
        m.validate_manifest(manifest(), getter=api)


def test_validate_manifest_cohort_not_equal():
    with pytest.raises(ValueError, match="not equal to full"):
        m.validate_manifest(manifest([[401, 2]]), getter=Api())


# ------------------------------------------------------------------ collect
def test_collect_slims_runs_jobs_steps_and_runner():
    out = m.collect(SHA, [[401, 1]], Api())
    assert out["repository"] == "GBOGEB/ABACUS" and out["gate_bindings"] == {}
    assert set(out["runs"][0]) == {"id", "run_attempt", "head_sha", "name", "path", "html_url",
                                   "created_at", "status", "conclusion"}
    j1, j2 = out["jobs"]
    assert j1["runner_id"] == 7 and j1["steps"] == [{"name": "s", "number": 1, "status": "completed",
                                                     "conclusion": "success"}]
    assert "runner_id" not in j2 and "steps" not in j2


def test_collect_paginates_and_zero_jobs():
    api = Api(runs={401: run(401), 402: run(402)},
              jobs={401: [job(1000 + i, 401) for i in range(150)], 402: []})
    out = m.collect(SHA, [[401, 1], [402, 1]], api)
    assert len(out["jobs"]) == 150
    assert sum("/jobs?" in p for p, _ in api.paths) == 3


@pytest.mark.parametrize("sha, sel, msg", [
    ("bad", [[401, 1]], "exact source SHA"),
    (SHA, [], "bounded explicit"),
    (SHA, "x", "bounded explicit"),
    (SHA, [[401]], "exact native run/attempt"),
    (SHA, ["x"], "exact native run/attempt"),
    (SHA, [[401, 1], [401, 1]], "duplicate native run ID"),
])
def test_collect_rejects_selection(sha, sel, msg):
    with pytest.raises(ValueError, match=msg):
        m.collect(sha, sel, Api())


@pytest.mark.parametrize("mutate", [
    lambda r: r.update(id=999),
    lambda r: r.update(path=None),
    lambda r: r.update(path="scripts/x.yml"),
    lambda r: r.update(html_url="https://evil/401"),
])
def test_collect_rejects_run_identity(mutate):
    api = Api()
    mutate(api.runs[401])
    with pytest.raises(ValueError, match="workflow identity"):
        m.collect(SHA, [[401, 1]], api)


def test_collect_rejects_non_dict_run():
    with pytest.raises(ValueError, match="workflow identity"):
        m.collect(SHA, [[401, 1]], lambda p: [])


@pytest.mark.parametrize("page", [
    [],
    {"total_count": "1", "jobs": []},
    {"total_count": -1, "jobs": []},
    {"total_count": 1, "jobs": "x"},
])
def test_collect_rejects_invalid_jobs_page(page):
    api = Api()

    def get(path):
        return copy.deepcopy(page) if "/jobs?" in path else api(path)
    with pytest.raises(ValueError, match="invalid attempt-specific jobs page"):
        m.collect(SHA, [[401, 1]], get)


def test_collect_rejects_total_change_and_overflow():
    api = Api()
    totals = iter([150, 151])

    def changing(path):
        if "/jobs?" in path:
            t = next(totals)
            return {"total_count": t, "jobs": [job(5000 + i, 401) for i in range(100)]}
        return api(path)
    with pytest.raises(ValueError, match="pagination total changed"):
        m.collect(SHA, [[401, 1]], changing)

    def overflow(path):
        if "/jobs?" in path:
            return {"total_count": 1, "jobs": [job(1, 401), job(2, 401)]}
        return api(path)
    with pytest.raises(ValueError, match="pagination total changed"):
        m.collect(SHA, [[401, 1]], overflow)


def test_collect_rejects_partial_empty_page_and_incomplete(monkeypatch):
    api = Api()

    def empty(path):
        if "/jobs?" in path:
            return {"total_count": 3, "jobs": []}
        return api(path)
    with pytest.raises(ValueError, match="partial empty jobs page"):
        m.collect(SHA, [[401, 1]], empty)
    monkeypatch.setattr(m, "MAX_PAGES", 1)

    def short(path):
        if "/jobs?" in path:
            return {"total_count": 2, "jobs": [job(1, 401)]}
        return api(path)
    with pytest.raises(ValueError, match="native job census incomplete"):
        m.collect(SHA, [[401, 1]], short)


@pytest.mark.parametrize("bad", ["x", dict(job(601, 401), id=True),
                                 dict(job(601, 401), run_id=402)])
def test_collect_rejects_job_identity(bad):
    api = Api(jobs={401: [bad]})
    with pytest.raises(ValueError, match="native job identity"):
        m.collect(SHA, [[401, 1]], api)


def test_collect_rejects_duplicate_job_and_bad_steps():
    api = Api(jobs={401: [job(601, 401), job(601, 401)]})
    with pytest.raises(ValueError, match="native job identity"):
        m.collect(SHA, [[401, 1]], api)
    api = Api(jobs={401: [dict(job(601, 401), steps={"a": 1})]})
    with pytest.raises(ValueError, match="invalid native step list"):
        m.collect(SHA, [[401, 1]], api)


# ------------------------------------------------------------------ canonical_producer
@pytest.fixture
def abacus(tmp_path, monkeypatch):
    root = tmp_path / "ABACUS"
    (root / "tools").mkdir(parents=True)
    (root / "tools" / "mip_ci_wave_telemetry.py").write_text(PRODUCER, encoding="utf-8")
    calls = []

    def check_output(cmd, text=False, timeout=None):
        calls.append(list(cmd))
        return PIN + "\n"
    monkeypatch.setattr(m.subprocess, "check_output", check_output)
    return root, calls


def test_canonical_producer_loads_module(abacus):
    root, calls = abacus
    mod = m.canonical_producer(root, PIN)
    assert mod.summarize({"runs": [1], "jobs": []}) == {"runs": 1, "jobs": 0}
    assert calls == [["git", "-C", str(root), "rev-parse", "HEAD"]]


def test_canonical_producer_rejections(abacus, tmp_path, monkeypatch):
    root, _ = abacus
    with pytest.raises(ValueError, match="exact commit required"):
        m.canonical_producer(root, "short")
    with pytest.raises(ValueError, match="missing ABACUS checkout"):
        m.canonical_producer(tmp_path / "nope", PIN)
    with pytest.raises(ValueError, match="source drift"):
        m.canonical_producer(root, "3" * 40)
    (root / "tools" / "mip_ci_wave_telemetry.py").unlink()
    with pytest.raises(ValueError, match="canonical producer module absent"):
        m.canonical_producer(root, PIN)


@pytest.mark.parametrize("exc", [OSError("no git"), subprocess.CalledProcessError(128, "git")])
def test_canonical_producer_git_missing(abacus, monkeypatch, exc):
    def boom(*a, **k):
        raise exc
    monkeypatch.setattr(m.subprocess, "check_output", boom)
    with pytest.raises(ValueError, match="git receipt missing"):
        m.canonical_producer(abacus[0], PIN)


def test_canonical_producer_loader_unavailable(abacus, monkeypatch):
    monkeypatch.setattr(m.importlib.util, "spec_from_file_location", lambda *a, **k: None)
    with pytest.raises(ValueError, match="loader unavailable"):
        m.canonical_producer(abacus[0], PIN)


# ------------------------------------------------------------------ project + main
def _fake_consume(calls, observed_extra=None):
    def consume(binding, metrics):
        calls.append((binding, metrics))
        observed = {"first_red_unique_signatures": 1, "first_red_manifestations": 2,
                    "red_jobs_total": 3, "first_red_attribution_fraction": 0.5}
        observed.update(observed_extra or {})
        return {"observed": observed, "confidence_intervals": {"95": {"estimate": None}}}
    return consume


class _Producer:
    @staticmethod
    def summarize(native):
        return {"jobs": len(native["jobs"])}


def test_project_binds_digest_and_holds(monkeypatch):
    calls = []
    monkeypatch.setattr(m, "consume", _fake_consume(calls))
    out = m.project(SHA, [[401, 1]], _Producer, getter=Api(), verified_pr_event_cohort=True)
    binding, metrics = calls[0]
    assert metrics == {"jobs": 2}
    assert binding["producer_sha256"] == out["canonical_producer_digest_sha256"]
    assert len(binding["producer_sha256"]) == 64 and binding["authority_transfer"] is False
    assert out["first_red"] == {"unique_signatures": 1, "manifestations": 2,
                                "red_job_denominator": 3, "attribution_fraction": 0.5}
    assert out["selected_workflow_count"] == 1 and out["selected_job_count"] == 2
    assert out["pull_request_event_head_cohort_verified"] is True
    assert out["admission"] == "HOLD" and out["merge_authorized"] is False


@pytest.fixture
def cli(tmp_path, abacus, monkeypatch):
    api = Api()
    monkeypatch.setattr(m, "https_get", api)
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    calls = []
    monkeypatch.setattr(m, "consume", _fake_consume(calls))
    base = ["--sha", SHA, "--abacus-checkout", str(abacus[0]), "--producer-sha", PIN]
    return api, base, tmp_path


def test_main_run_selector_writes_atomically(cli):
    api, base, tmp = cli
    out = tmp / "o" / "native.json"
    assert m.main(base + ["--run", "401:1", "--out", str(out)]) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["run_attempts"] == [[401, 1]]
    assert doc["pull_request_event_head_cohort_verified"] is False
    assert all(tok == "test-token" for _, tok in api.paths)
    assert [p.name for p in out.parent.iterdir()] == ["native.json"]


def test_main_manifest_verified(cli):
    api, base, tmp = cli
    mf = tmp / "manifest.json"
    mf.write_text(json.dumps(manifest()), encoding="utf-8")
    out = tmp / "native.json"
    assert m.main(base + ["--manifest", str(mf), "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["pull_request_event_head_cohort_verified"] is True
    assert api.paths[0][1] == "test-token" and "event=pull_request" in api.paths[0][0]
    with pytest.raises(ValueError, match="CLI source head"):
        m.main(["--sha", "b" * 40] + base[2:] + ["--manifest", str(mf), "--out", str(out)])


def test_main_selector_rules(cli):
    _, base, tmp = cli
    out = str(tmp / "o.json")
    with pytest.raises(ValueError, match="use exact"):
        m.main(base + ["--out", out])
    mf = tmp / "m.json"
    with pytest.raises(ValueError, match="use exact"):
        m.main(base + ["--run", "401:1", "--manifest", str(mf), "--out", out])
    with pytest.raises(ValueError, match="plain manifest required"):
        m.main(base + ["--manifest", str(mf), "--out", out])
    for raw in ("401", "401:1:2", "401:x"):
        with pytest.raises(ValueError, match="ID:ATTEMPT"):
            m.main(base + ["--run", raw, "--out", out])


def test_main_rejects_symlink_out(cli):
    _, base, tmp = cli
    target = tmp / "target.json"
    target.write_text("{}", encoding="utf-8")
    link = tmp / "link.json"
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this host")
    with pytest.raises(ValueError, match="symlink not permitted"):
        m.main(base + ["--run", "401:1", "--out", str(link)])


def test_main_cleans_temp_on_serialisation_failure(cli, monkeypatch):
    _, base, tmp = cli
    monkeypatch.setattr(m, "consume", _fake_consume([], {"bad": object()}))
    out = tmp / "fail" / "native.json"
    with pytest.raises(TypeError):
        m.main(base + ["--run", "401:1", "--out", str(out)])
    assert list(out.parent.iterdir()) == []
