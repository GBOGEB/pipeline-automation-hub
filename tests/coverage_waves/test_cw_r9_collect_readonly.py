"""Coverage wave r9: mission-control/gogreen/collect_readonly.py (mocked network only)."""
import importlib.util
import io
import json
import runpy
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_DIR = REPO_ROOT / "mission-control" / "gogreen"
MOD_PATH = MOD_DIR / "collect_readonly.py"
if str(MOD_DIR) not in sys.path:
    sys.path.insert(0, str(MOD_DIR))
_spec = importlib.util.spec_from_file_location("cw_r9_collect_readonly_mod", MOD_PATH)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)
import spine  # noqa: E402

SHA = "a" * 40
REPO = "GBOGEB/ABACUS"


def fixture():
    return json.loads((MOD_DIR / "samples" / "fleet_g0.json").read_text(encoding="utf-8"))


def one_repo(families=("ci_contract", "security", "coverage")):
    return {"schema": fixture()["schema"],
            "repositories": [{"repository": REPO, "head_sha": SHA, "ref_kind": "MAIN",
                              "target_families": list(families), "authority_transfer": False}],
            "observations": []}


def ok_run(rid, name="Build", **kw):
    r = {"id": rid, "head_sha": SHA, "run_attempt": 1, "run_number": 3,
         "status": "completed", "conclusion": "success", "name": name}
    r.update(kw)
    return r


def ok_job(jid, **kw):
    j = {"id": jid, "status": "completed", "conclusion": "success", "name": "job%s" % jid}
    j.update(kw)
    return j


def make_fetch(runs, jobs_by_rid, total=None):
    calls = []

    def fetch(path):
        calls.append(path)
        if "/actions/runs?" in path:
            obj = {"workflow_runs": runs}
            if total is not None:
                obj["total_count"] = total
            return obj
        for rid, val in jobs_by_rid.items():
            if f"/actions/runs/{rid}/jobs" in path:
                if isinstance(val, Exception):
                    raise val
                return val
        raise AssertionError("unexpected path " + path)
    fetch.calls = calls
    return fetch


# ---------------- get_json ----------------

class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


@pytest.mark.parametrize("path", ["/users/x", "/repos/a/../b", "/repos//a"])
def test_get_json_rejects_paths(path, monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: pytest.fail("network"))
    with pytest.raises(ValueError):
        mod.get_json(path, "")


@pytest.mark.parametrize("token", ["", "tok123"])
def test_get_json_headers_and_parse(token, monkeypatch):
    seen = {}

    def fake(req, timeout):
        seen["req"], seen["timeout"] = req, timeout
        return _Resp(b'{"ok": 1}')
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    assert mod.get_json("/repos/a/b/actions/runs", token) == {"ok": 1}
    req = seen["req"]
    assert req.full_url == mod.API + "/repos/a/b/actions/runs"
    assert req.get_method() == "GET"
    assert seen["timeout"] == 12
    hdrs = {k.lower(): v for k, v in req.header_items()}
    assert hdrs["user-agent"] == "GOGREEN-G0-ReadOnly-Scout"
    if token:
        assert hdrs["authorization"] == "Bearer tok123"
    else:
        assert "authorization" not in hdrs


# ---------------- family_hint ----------------

ALL = ["security", "coverage", "runtime", "qps_triage", "math_model", "federation", "artifact", "ci_contract"]


@pytest.mark.parametrize("name,fam", [
    ("CodeQL", "security"), ("MIP B0 gate", "coverage"), ("Docker build", "runtime"),
    ("QPS Triage", "qps_triage"), ("Monte Carlo", "math_model"), ("Golden Thread", "federation"),
    ("Render PDF", "artifact"), ("Lint", "ci_contract"),
])
def test_family_hint_groups(name, fam):
    assert mod.family_hint(name, ALL) == fam


def test_family_hint_disallowed_falls_through():
    assert mod.family_hint("codeql coverage", ["coverage"]) == "coverage"
    assert mod.family_hint("codeql", ["ci_contract"]) == "ci_contract"


# ---------------- scan ----------------

@pytest.mark.parametrize("k", [0, 9, True, "2"])
def test_invalid_max_jobs(k):
    with pytest.raises(ValueError, match="max_jobs"):
        mod.scan(one_repo(), lambda _: {}, max_jobs=k)


def test_runs_not_list_is_unknown_error():
    res, meta = mod.scan(one_repo(), lambda _: {"workflow_runs": None})
    row = meta["repositories"][0]
    assert row["fetch_state"] == "UNKNOWN_ERROR"
    assert meta["collection_errors"] == [{"repository": REPO, "kind": "RUN_FETCH_UNAVAILABLE",
                                          "error_type": "ValueError"}]
    assert res["observations"] == []


@pytest.mark.parametrize("exc", [
    urllib.error.URLError("down"),
    urllib.error.HTTPError("u", 404, "nf", None, None),
    KeyError("x"),
])
def test_run_fetch_network_errors(exc):
    def fetch(_):
        raise exc
    _, meta = mod.scan(one_repo(), fetch)
    assert meta["collection_errors"][0]["error_type"] == type(exc).__name__
    assert meta["repositories"][0]["fetch_state"] == "UNKNOWN_ERROR"


def test_total_not_int_truncated_none_and_query():
    fetch = make_fetch([], {}, total="many")
    _, meta = mod.scan(one_repo(), fetch, max_runs=5, max_jobs=4)
    row = meta["repositories"][0]
    assert row["truncated"] is None and row["runs_considered"] == 0
    assert row["fetch_state"] == "OBSERVED_PARTIAL_SAMPLE"
    assert fetch.calls == ["/repos/%s/actions/runs?head_sha=%s&per_page=5" % (REPO, SHA)]
    assert meta["requested_runs_per_repo"] == 5 and meta["requested_jobs_per_run"] == 4
    assert meta["worker_dispatches"] == 0 and meta["mode"] == "PASSIVE_GET_ONLY"


def test_total_int_not_truncated():
    _, meta = mod.scan(one_repo(), make_fetch([], {}, total=0))
    assert meta["repositories"][0]["truncated"] is False


@pytest.mark.parametrize("bad", [
    {"id": "1"}, {"id": 0}, {"run_attempt": 0}, {"run_attempt": "1"}, {"id": True},
])
def test_invalid_run_identity(bad):
    fetch = make_fetch([ok_run(5, **bad)], {})
    _, meta = mod.scan(one_repo(), fetch)
    assert meta["collection_errors"] == [{"repository": REPO, "kind": "INVALID_RUN_IDENTITY"}]
    assert len(fetch.calls) == 1


def test_non_green_run_recorded():
    _, meta = mod.scan(one_repo(), make_fetch([ok_run(5, status="in_progress", conclusion=None)], {}))
    red = meta["unattributed_non_green"][0]
    assert red["run_id"] == 5 and red["status"] == "in_progress" and red["root_id"] is None
    assert "job_id" not in red


@pytest.mark.parametrize("val,etype", [
    ({"jobs": "nope"}, "ValueError"),
    (urllib.error.URLError("x"), "URLError"),
    (KeyError("k"), "KeyError"),
])
def test_job_fetch_unavailable(val, etype):
    _, meta = mod.scan(one_repo(), make_fetch([ok_run(5)], {5: val}))
    assert meta["collection_errors"] == [{"repository": REPO, "run_id": 5,
                                          "kind": "JOB_FETCH_UNAVAILABLE", "error_type": etype}]
    assert meta["repositories"][0]["fetch_state"] == "OBSERVED_PARTIAL_SAMPLE"


def test_job_variants_and_observation_shape():
    jobs = {"jobs": [ok_job(0), ok_job("7"), ok_job(8, conclusion="failure"),
                     ok_job(9, name=None), ok_job(9), ok_job(10)]}
    fetch = make_fetch([ok_run(5, name="CodeQL scan"), ok_run(6, name=None)],
                       {5: jobs, 6: {"jobs": [ok_job(11)]}}, total=2)
    res, meta = mod.scan(one_repo(), fetch, max_jobs=8)
    assert "/repos/%s/actions/runs/5/jobs?per_page=8" % REPO in fetch.calls
    kinds = [e["kind"] for e in meta["collection_errors"]]
    assert kinds == ["INVALID_JOB_ID", "INVALID_JOB_ID"]
    reds = meta["unattributed_non_green"]
    assert len(reds) == 1 and reds[0]["job_id"] == 8 and reds[0]["conclusion"] == "failure"
    obs = res["observations"]
    assert [o["job_id"] for o in obs] == [9, 10, 11]  # duplicate job 9 skipped
    assert obs[0]["suite_id"] == "job:9"
    assert obs[0]["family"] == "security"
    assert obs[2]["family"] == "ci_contract" and obs[2]["workflow_name"] is None
    assert obs[0]["run_url"] == "https://github.com/%s/actions/runs/5" % REPO
    assert obs[0]["discovery_basis"] == "WORKFLOW_NAME_HEURISTIC_UNVERIFIED"
    assert meta["repositories"][0]["successful_jobs_seen"] == 3
    assert meta["repositories"][0]["truncated"] is False
    ev, _, _ = spine.build(res)
    assert ev["breadth"]["native_green_status_only_observations"] == 3


def test_seen_from_historical_observation_not_duplicated():
    f = fixture()
    old = f["observations"][0]
    sha, rid, jid = old["source_sha"], old["run_id"], old["job_id"]

    def fetch(path):
        if path.startswith("/repos/GBOGEB/ABACUS/actions/runs?"):
            return {"total_count": 1, "workflow_runs": [
                {"id": rid, "head_sha": sha, "run_attempt": 1, "run_number": 8,
                 "status": "completed", "conclusion": "success", "name": "x"}]}
        if "/jobs" in path:
            return {"jobs": [{"id": jid, "status": "completed", "conclusion": "success"}]}
        return {"workflow_runs": []}
    res, meta = mod.scan(f, fetch)
    assert len(res["observations"]) == 1
    assert res["observations"][0] == old
    abacus = [r for r in meta["repositories"] if r["repository"] == REPO][0]
    assert abacus["successful_jobs_seen"] == 0
    assert [r["repository"] for r in meta["repositories"]] == sorted(r["repository"] for r in f["repositories"])


# ---------------- main ----------------

def _setup_main(tmp_path, monkeypatch, token):
    cat = tmp_path / "cat.json"
    cat.write_text(json.dumps(one_repo()), encoding="utf-8")
    out = tmp_path / "out" / "nested"
    seen = []

    def fake_urlopen(req, timeout):
        seen.append(dict((k.lower(), v) for k, v in req.header_items()))
        if "/jobs" in req.full_url:
            return _Resp(json.dumps({"jobs": [ok_job(3)]}).encode())
        return _Resp(json.dumps({"total_count": 1, "workflow_runs": [ok_run(2)]}).encode())
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    if token:
        monkeypatch.setenv("GITHUB_TOKEN", token)
    else:
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(sys, "argv", ["collect_readonly.py", "--catalog", str(cat), "--out", str(out),
                                      "--max-runs", "3", "--max-jobs", "2"])
    return out, seen


def _check_out(out, capsys):
    printed = json.loads(capsys.readouterr().out.strip())
    assert printed == {"errors": 0, "unknown_failures": 0, "status_only_observations": 1}
    intake = json.loads((out / "live_intake.json").read_text(encoding="utf-8"))
    meta = json.loads((out / "live_scanner_metadata.json").read_text(encoding="utf-8"))
    assert len(intake["observations"]) == 1
    assert meta["requested_runs_per_repo"] == 3 and meta["requested_jobs_per_run"] == 2
    assert b"\r\n" not in (out / "live_intake.json").read_bytes()
    for name in ("evidence.json", "manifest.json", "summary.md"):
        assert (out / name).is_file()


def test_main_writes_outputs(tmp_path, monkeypatch, capsys):
    out, seen = _setup_main(tmp_path, monkeypatch, "tkn")
    mod.main()
    _check_out(out, capsys)
    assert seen and all(h["authorization"] == "Bearer tkn" for h in seen)


def test_main_as_script(tmp_path, monkeypatch, capsys):
    out, seen = _setup_main(tmp_path, monkeypatch, "")
    runpy.run_path(str(MOD_PATH), run_name="__main__")
    _check_out(out, capsys)
    assert seen and all("authorization" not in h for h in seen)
