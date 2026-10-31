"""Behavioural coverage for mission-control/v2/recursive-recovery/native_readback.py.

No network: urllib.request.urlopen and Reader are faked on the loaded module.
"""
import copy
import importlib.util
import io
import json
import sys
import urllib.error
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MOD_PATH = REPO / "mission-control" / "v2" / "recursive-recovery" / "native_readback.py"

S = "a" * 40
T = "b" * 40
RUN = 501
CONFIG = {"authority_transfer": False, "execution_mode": "GET_ONLY_NO_RERUN",
          "max_runs_per_pr": 2, "max_jobs_per_run": 50,
          "targets": [{"repo": "GBOGEB/demo", "branch": "main", "class": "CONTROL",
                       "issues": [], "prs": [7]}]}


@pytest.fixture
def nr():
    spec = importlib.util.spec_from_file_location("cw_native_readback", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def http_error(code):
    return urllib.error.HTTPError("https://api.github.com/x", code, "err", None, None)


class Routes:
    """Fake reader: route suffix/substring -> payload or exception."""

    def __init__(self, routes):
        self.routes = routes
        self.paths = []

    def get(self, path):
        self.paths.append(path)
        for key, value in self.routes.items():
            if key in path:
                if isinstance(value, BaseException):
                    raise value
                return copy.deepcopy(value)
        raise urllib.error.HTTPError(path, 404, "nf", None, None)


def base_routes(**over):
    routes = {
        "/branches/": {"commit": {"sha": S}},
        "/pulls/7": {"state": "open", "merged": False, "head": {"sha": S},
                     "base": {"sha": T, "ref": "main"}},
        "/check-runs?": {"total_count": 1, "check_runs": [{"status": None, "conclusion": None}]},
        "/jobs?per_page=": {"total_count": 2, "jobs": [
            {"id": 1, "conclusion": "success", "status": "completed"},
            {"id": 2, "conclusion": "failure", "status": "completed",
             "steps": [{"name": "a", "status": "completed", "conclusion": "success"}]}]},
        "/actions/runs?head_sha=": {"total_count": 1, "workflow_runs": [
            {"id": RUN, "head_sha": S, "run_attempt": 1, "created_at": "2026-01-01"}]},
    }
    routes.update(over)
    return routes


# ---------------------------------------------------------------- Reader.get

class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_reader_get_sends_authenticated_get(nr, monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout):
        seen["req"], seen["timeout"] = req, timeout
        return FakeResponse(b'{"ok": 1}')

    monkeypatch.setattr(nr.urllib.request, "urlopen", fake_urlopen)
    assert nr.Reader("tok").get("/repos/GBOGEB/x/branches/main") == {"ok": 1}
    req = seen["req"]
    assert req.full_url == "https://api.github.com/repos/GBOGEB/x/branches/main"
    assert req.get_method() == "GET"
    assert req.get_header("Authorization") == "Bearer tok"
    assert req.get_header("X-github-api-version") == "2022-11-28"
    assert seen["timeout"] == 14


def test_reader_without_token_sends_no_authorization(nr, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    seen = {}

    def fake_urlopen(req, timeout):
        seen["req"] = req
        return FakeResponse(b"[]")

    monkeypatch.setattr(nr.urllib.request, "urlopen", fake_urlopen)
    reader = nr.Reader()
    assert reader.token == ""
    assert reader.get("/repos/GBOGEB/x/issues/1") == []
    assert seen["req"].get_header("Authorization") is None


def test_reader_token_from_env(nr, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    assert nr.Reader().token == "test-token"


@pytest.mark.parametrize("endpoint", ["/repos/GBOGEB/../x", "/repos/GBOGEB/a\\b", "/repos/other/x"])
def test_reader_rejects_unapproved_endpoint(nr, endpoint):
    with pytest.raises(ValueError, match="^UNAPPROVED_GITHUB_ENDPOINT$"):
        nr.Reader("t").get(endpoint)


# ---------------------------------------------------------------- attempt_get

class Raiser:
    def __init__(self, exc):
        self.exc = exc

    def get(self, url):
        raise self.exc


@pytest.mark.parametrize("exc,expected", [
    (http_error(403), "INACCESSIBLE_OR_RATE_LIMITED_HTTP_403"),
    (http_error(429), "INACCESSIBLE_OR_RATE_LIMITED_HTTP_429"),
    (http_error(500), "GITHUB_HTTP_500"),
    (urllib.error.URLError("down"), "NETWORK_OR_RUNTIME_UNKNOWN_URLError"),
    (TimeoutError(), "NETWORK_OR_RUNTIME_UNKNOWN_TimeoutError"),
    (OSError(), "NETWORK_OR_RUNTIME_UNKNOWN_OSError"),
])
def test_attempt_get_maps_errors(nr, exc, expected):
    assert nr.attempt_get(Raiser(exc), "/x") == (None, expected)


# ---------------------------------------------------------------- trim / classify

def test_trim_checks_unknown_and_malformed(nr):
    assert nr.trim_checks(None) == {"quality": "UNKNOWN_UNAVAILABLE", "counts": None, "total_count": None}
    assert nr.trim_checks({"check_runs": "x", "total_count": 1})["quality"] == "UNKNOWN_MALFORMED"
    assert nr.trim_checks({"check_runs": [], "total_count": "1"})["quality"] == "UNKNOWN_MALFORMED"


def test_trim_checks_complete_counts(nr):
    out = nr.trim_checks({"total_count": 3, "check_runs": [
        {"status": "completed", "conclusion": "success"},
        {"status": "completed", "conclusion": "success"},
        {}]})
    assert out == {"quality": "COMPLETE_FIRST_PAGE", "total_count": 3, "checks_returned": 3,
                   "counts": {"completed/success": 2, "unknown/-": 1}}


def test_classify_failed_without_red_step(nr):
    job = {"conclusion": "failure", "steps": [{"name": "s", "status": "completed", "conclusion": "success"}]}
    assert nr.classify_job(job) == {"kind": "FAILED_UNKNOWN_STEP", "step": None}


# ---------------------------------------------------------------- sample_jobs

def test_sample_jobs_requires_int_id_and_attempt(nr):
    assert nr.sample_jobs(None, "GBOGEB/x", {"id": "1", "run_attempt": 1}, 5) == {
        "state": "UNKNOWN_RUN_ID_OR_ATTEMPT", "jobs": []}
    assert nr.sample_jobs(None, "GBOGEB/x", {"id": 1, "run_attempt": None}, 5)["state"] == \
        "UNKNOWN_RUN_ID_OR_ATTEMPT"


def test_sample_jobs_error_and_malformed(nr):
    r = nr.sample_jobs(Raiser(http_error(404)), "GBOGEB/x", {"id": 9, "run_attempt": 3}, 5)
    assert r == {"state": "INACCESSIBLE_OR_RATE_LIMITED_HTTP_404", "run": 9, "attempt": 3, "jobs": []}
    reader = Routes({"/jobs?": {"jobs": None, "total_count": 1}})
    r = nr.sample_jobs(reader, "GBOGEB/x", {"id": 9, "run_attempt": 3}, 5)
    assert r["state"] == "UNKNOWN_MALFORMED_JOB_PAGE" and r["jobs"] == []
    assert reader.paths == ["/repos/GBOGEB/x/actions/runs/9/jobs?per_page=5"]


def test_sample_jobs_truncated(nr):
    reader = Routes({"/jobs?": {"total_count": 5, "jobs": [{"id": 1, "conclusion": "success"}]}})
    r = nr.sample_jobs(reader, "GBOGEB/x", {"id": 9, "run_attempt": 1}, 1)
    assert r["state"] == "TRUNCATED_MORE_PAGES"
    assert r["total_jobs"] == 5
    assert r["jobs"][0]["first_red"]["kind"] == "NONFAILURE_OR_NONTERMINAL"


# ---------------------------------------------------------------- collect

@pytest.mark.parametrize("over", [{"authority_transfer": True}, {"execution_mode": "RERUN"},
                                  {"authority_transfer": None}])
def test_collect_rejects_unauthorized_config(nr, over):
    cfg = dict(CONFIG, **over)
    with pytest.raises(ValueError, match="^UNAUTHORIZED_COLLECTOR_CONFIG$"):
        nr.collect(Routes({}), cfg)


@pytest.mark.parametrize("repos", [["evil/x"], ["GBOGEB/a", "GBOGEB/a"]])
def test_collect_rejects_bad_or_duplicate_repo(nr, repos):
    cfg = dict(CONFIG, targets=[{"repo": r, "branch": "main", "class": "C"} for r in repos])
    with pytest.raises(ValueError, match="^INVALID_OR_DUPLICATE_REPOSITORY$"):
        nr.collect(Routes(base_routes()), cfg)


@pytest.mark.parametrize("key,bad,msg", [("issues", [0], "INVALID_ISSUE_ID"),
                                         ("issues", ["3"], "INVALID_ISSUE_ID"),
                                         ("prs", [-1], "INVALID_PR_ID")])
def test_collect_rejects_bad_ids(nr, key, bad, msg):
    target = {"repo": "GBOGEB/a", "branch": "main", "class": "C", key: bad}
    with pytest.raises(ValueError, match="^" + msg + "$"):
        nr.collect(Routes(base_routes()), dict(CONFIG, targets=[target]))


def test_collect_branch_sha_malformed_and_issue_error(nr):
    target = {"repo": "GBOGEB/a", "branch": "feat/x y", "class": "C", "issues": [3], "prs": []}
    reader = Routes({"/branches/": {"commit": {"sha": "short"}},
                     "/issues/3": http_error(403)})
    d = nr.collect(reader, dict(CONFIG, targets=[target]))
    row = d["targets"][0]
    assert row["source_quality"] == "UNKNOWN_BRANCH_SOURCE_IDENTITY"
    assert row["source_head_sha"] is None
    assert row["issues"] == [{"number": 3, "state": None, "observed": False,
                              "error": "INACCESSIBLE_OR_RATE_LIMITED_HTTP_403",
                              "evidence_class": "ISSUE_OBJECT_NOT_ROOT_CLOSURE"}]
    assert reader.paths[0] == "/repos/GBOGEB/a/branches/feat%2Fx%20y"
    assert d["sampling"]["source_accessible_repos"] == 0


def test_collect_branch_missing_commit_key(nr):
    reader = Routes(base_routes(**{"/branches/": {}}))
    d = nr.collect(reader, dict(CONFIG, targets=[dict(CONFIG["targets"][0], prs=[])]))
    assert d["targets"][0]["source_quality"] == "UNKNOWN_BRANCH_SOURCE_IDENTITY"


def test_collect_pr_malformed_sha(nr):
    reader = Routes(base_routes(**{"/pulls/7": {"head": {"sha": S}, "base": {}}}))
    d = nr.collect(reader, CONFIG)
    assert d["targets"][0]["prs"] == [{"number": 7, "state": "UNKNOWN",
                                       "error": "MALFORMED_PR_SHA", "head_sha": None}]


def test_collect_check_and_run_errors_recorded(nr):
    reader = Routes(base_routes(**{"/check-runs?": http_error(500),
                                   "/actions/runs?head_sha=": http_error(429)}))
    pr = nr.collect(reader, CONFIG)["targets"][0]["prs"][0]
    assert pr["check_runs"] == {"quality": "UNKNOWN_UNAVAILABLE", "counts": None,
                                "total_count": None, "error": "GITHUB_HTTP_500"}
    assert pr["run_access_error"] == "INACCESSIBLE_OR_RATE_LIMITED_HTTP_429"
    assert pr["runs"] == []
    assert "total_matching_runs_reported" not in pr


def test_collect_malformed_runs_list(nr):
    reader = Routes(base_routes(**{"/actions/runs?head_sha=": {"total_count": 0, "workflow_runs": "bad"}}))
    pr = nr.collect(reader, CONFIG)["targets"][0]["prs"][0]
    assert pr["run_access_error"] == "UNKNOWN_MALFORMED_RUNS"
    assert pr["runs"] == []
    assert pr["total_matching_runs_reported"] == 0
    assert pr["sample_limit_runs"] == 2


def test_collect_truncated_runs_filters_and_sorts(nr):
    runs = {"total_count": 9, "workflow_runs": [
        {"id": 1, "head_sha": S, "run_attempt": 1, "created_at": "2026-01-01"},
        {"id": 2, "head_sha": S, "run_attempt": 1, "created_at": "2026-03-01"},
        {"id": 3, "head_sha": S, "run_attempt": 2, "created_at": "2026-02-01"},
        {"id": 4, "head_sha": T, "run_attempt": 1, "created_at": "2026-09-01"},
        {"id": 5, "head_sha": S, "run_attempt": "1", "created_at": "2026-09-01"}]}
    reader = Routes(base_routes(**{"/actions/runs?head_sha=": runs}))
    d = nr.collect(reader, CONFIG)
    pr = d["targets"][0]["prs"][0]
    assert pr["run_access_error"] == "RUN_LIST_TRUNCATED"
    assert [r["id"] for r in pr["runs"]] == [2, 3]
    assert pr["total_matching_runs_reported"] == 9
    assert d["sampling"]["sampled_jobs"] == 4
    assert d["sampling"]["sampled_success_jobs"] == 2
    assert d["sampling"]["sampled_failed_jobs"] == 2
    assert pr["runs"][0]["job_receipt"]["jobs"][1]["first_red"]["kind"] == "FAILED_UNKNOWN_STEP"
    assert pr["check_runs"]["counts"] == {"unknown/-": 1}
    assert nr.verify(d) is True


def test_collect_semantic_hash_is_over_body(nr):
    import hashlib
    d = nr.collect(Routes(base_routes()), CONFIG)
    digest = d.pop("semantic_sha256")
    assert hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest() == digest


# ---------------------------------------------------------------- verify

@pytest.fixture
def good(nr):
    return nr.collect(Routes(base_routes()), CONFIG)


@pytest.mark.parametrize("mutate,msg", [
    (lambda d: d.update(schema="x"), "SCHEMA_OR_AUTHORITY"),
    (lambda d: d.update(authority_transfer=True), "SCHEMA_OR_AUTHORITY"),
    (lambda d: d.update(mutation_enabled=True), "ILLEGAL_ADMISSION_PROMOTION"),
    (lambda d: d.update(merge_admission="GO"), "ILLEGAL_ADMISSION_PROMOTION"),
    (lambda d: d.update(root_closure_credit=1), "FORGED_WORKER_OR_ROOT"),
    (lambda d: d["targets"][0].update(source_head_sha="bad"), "SOURCE_SHA_MISSING_OR_INVALID"),
    (lambda d: d["targets"][0]["prs"][0].update(head_sha="bad"), "SOURCE_SHA_MISSING_OR_INVALID"),
    (lambda d: d["targets"][0]["prs"][0]["runs"][0].update(head_sha=T), "STALE_RUN_OR_BAD_ATTEMPT"),
    (lambda d: d["targets"][0]["prs"][0]["runs"][0].update(attempt=0), "STALE_RUN_OR_BAD_ATTEMPT"),
    (lambda d: d["targets"][0]["prs"][0]["runs"][0]["job_receipt"]["jobs"][0].update(run=1),
     "JOB_RUN_ATTEMPT_MISMATCH"),
])
def test_verify_rejects_forgeries(nr, good, mutate, msg):
    mutate(good)
    with pytest.raises(ValueError, match="^" + msg + "$"):
        nr.verify(good)


def test_verify_accepts_null_shas_and_unknown_prs(nr, good):
    good["targets"][0]["source_head_sha"] = None
    good["targets"][0]["prs"].append({"number": 8, "state": "UNKNOWN", "head_sha": None})
    assert nr.verify(good) is True
    assert nr.verify({"schema": nr.SCHEMA, "authority_transfer": False, "mutation_enabled": False,
                      "merge_admission": "HOLD", "dispatch_count": 0, "root_closure_credit": None}) is True


# ---------------------------------------------------------------- main

def test_main_writes_observation_and_summary(nr, tmp_path, monkeypatch, capsys):
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps(CONFIG), encoding="utf-8")
    out = tmp_path / "deep" / "obs.json"
    monkeypatch.setattr(nr, "Reader", lambda: Routes(base_routes()))
    nr.main(["--config", str(cfg), "--out", str(out), "--require-controller"])
    raw = out.read_bytes()
    assert raw.endswith(b"}\n") and b"\r\n" not in raw
    obs = json.loads(raw)
    assert obs["targets"][0]["source_head_sha"] == S
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "PARTIAL_PROJECTION_NEVER_ADMISSION"
    assert summary["controller_bound"] is True
    assert summary["targets"] == 1
    assert summary["sampled_jobs"] == 2
    assert summary["file"] == str(out)


def test_main_require_controller_holds_without_source(nr, tmp_path, monkeypatch, capsys):
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps(CONFIG), encoding="utf-8")
    monkeypatch.setattr(nr, "Reader", lambda: Raiser(http_error(401)))
    with pytest.raises(SystemExit) as exc:
        nr.main(["--config", str(cfg), "--out", str(tmp_path / "o.json"), "--require-controller"])
    assert exc.value.code == "NO_CONTROLLER_SOURCE_IDENTITY: HOLD"
    assert json.loads(capsys.readouterr().out)["controller_bound"] is False
    obs = json.loads((tmp_path / "o.json").read_text(encoding="utf-8"))
    assert obs["targets"][0]["source_quality"] == "INACCESSIBLE_OR_RATE_LIMITED_HTTP_401"


def test_main_without_require_controller_does_not_exit(nr, tmp_path, monkeypatch, capsys):
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps(CONFIG), encoding="utf-8")
    monkeypatch.setattr(nr, "Reader", lambda: Raiser(urllib.error.URLError("x")))
    assert nr.main(["--config", str(cfg), "--out", str(tmp_path / "o.json")]) is None
    assert json.loads(capsys.readouterr().out)["controller_bound"] is False


def test_script_entrypoint_runs_main(tmp_path, monkeypatch, capsys):
    """Execute as __main__ with urlopen faked to fail closed (no network)."""
    import urllib.request
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps(dict(CONFIG, targets=[dict(CONFIG["targets"][0], prs=[])])), encoding="utf-8")

    def no_network(*a, **k):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(sys, "argv", ["native_readback", "--config", str(cfg), "--out", str(tmp_path / "o.json")])
    code = compile(MOD_PATH.read_text(encoding="utf-8"), str(MOD_PATH), "exec")
    exec(code, {"__name__": "__main__", "__file__": str(tmp_path / "cw_nr_main.py")})
    summary = json.loads(capsys.readouterr().out)
    assert summary["controller_bound"] is False
    obs = json.loads((tmp_path / "o.json").read_text(encoding="utf-8"))
    assert obs["targets"][0]["source_quality"] == "NETWORK_OR_RUNTIME_UNKNOWN_URLError"
