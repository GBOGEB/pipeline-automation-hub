"""Behavioural coverage for mission-control/federation-atlas/native_pulse_ingest.py.

Targets what test_native_pulse_ingest.py misses: the redirect handler, the
HTTP GET wrapper (faked opener), paginated live collection (faked get) and
main() in offline and live modes. Never touches the network.
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ATLAS = REPO_ROOT / "mission-control" / "federation-atlas"


def _load():
    if str(ATLAS) not in sys.path:
        sys.path.insert(0, str(ATLAS))
    spec = importlib.util.spec_from_file_location("cw_native_pulse_ingest",
                                                  ATLAS / "native_pulse_ingest.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


npi = _load()

SHA = "a" * 40
REPO = "GBOGEB/pipeline-automation-hub"


def fixture():
    run = {"id": 17, "repository": {"full_name": REPO}, "head_sha": SHA, "run_attempt": 2,
           "status": "completed", "conclusion": "success"}
    jobs = {"jobs": [{"id": 81, "run_id": 17, "run_attempt": 2,
                      "status": "completed", "conclusion": "success"}]}
    artifacts = {"artifacts": [{"id": 19, "name": "pulse-measurement", "expired": False}]}
    inner = {"schema": npi.INNER, "repository": REPO, "head_sha": SHA, "run_id": 17,
             "run_attempt": 2, "job_id": 81, "config_sha256": "b" * 64,
             "selection": "unit:fixed", "tool": {"name": "coverage.py", "version": "7"},
             "tests": {"passed": 3, "failed": 0, "skipped": 0},
             "source_scope": [{"path": "scripts/mod.py", "sha256": "c" * 64}],
             "line": {"covered": 1, "eligible": 4}, "branch": {"covered": 2, "eligible": 2}}
    return run, jobs, artifacts, inner


def zip_receipt(obj):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("pulse_measurement.json", json.dumps(obj))
    return buf.getvalue()


# --- TokenSafeRedirect ----------------------------------------------------------

def _req():
    return urllib.request.Request("https://api.github.com/repos/GBOGEB/x",
                                  headers={"Authorization": "Bearer test-token"})


def test_redirect_to_foreign_https_host_strips_authorization():
    handler = npi.TokenSafeRedirect()
    new = handler.redirect_request(_req(), None, 302, "Found", {},
                                   "https://objects.githubusercontent.com/blob")
    assert new.full_url == "https://objects.githubusercontent.com/blob"
    assert not new.has_header("Authorization")


def test_redirect_within_api_keeps_authorization():
    handler = npi.TokenSafeRedirect()
    new = handler.redirect_request(_req(), None, 301, "Moved", {},
                                   "https://api.github.com/repos/GBOGEB/y")
    assert new.get_header("Authorization") == "Bearer test-token"


def test_redirect_to_http_is_blocked():
    handler = npi.TokenSafeRedirect()
    with pytest.raises(ValueError, match="^insecure redirect blocked$"):
        handler.redirect_request(_req(), None, 302, "Found", {}, "http://example.com/x")


# --- get ----------------------------------------------------------------------------

class _Resp:
    def __init__(self, data):
        self.data = data
        self.asked = None

    def read(self, n):
        self.asked = n
        return self.data[:n]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _fake_opener(monkeypatch, payload):
    seen = {}

    class Opener:
        def open(self, req, timeout):
            seen["req"] = req
            seen["timeout"] = timeout
            seen["resp"] = _Resp(payload)
            return seen["resp"]

    def build_opener(*handlers):
        seen["handlers"] = handlers
        return Opener()

    monkeypatch.setattr(npi.urllib.request, "build_opener", build_opener)
    return seen


def test_get_json_with_token(monkeypatch):
    seen = _fake_opener(monkeypatch, b'{"ok": 1}')
    assert npi.get("/repos/GBOGEB/CODEX/actions/runs/1", "test-token") == {"ok": 1}
    req = seen["req"]
    assert req.full_url == "https://api.github.com/repos/GBOGEB/CODEX/actions/runs/1"
    assert req.get_method() == "GET"
    assert req.get_header("Authorization") == "Bearer test-token"
    assert req.get_header("User-agent") == "CODE-PURPLE-NativePulse-ReadOnly"
    assert seen["timeout"] == 20
    assert isinstance(seen["handlers"][0], npi.TokenSafeRedirect)
    assert seen["resp"].asked == 8_000_000


def test_get_binary_without_token(monkeypatch):
    seen = _fake_opener(monkeypatch, b"PK\x03\x04bytes")
    assert npi.get("/repos/GBOGEB/CODEX/actions/artifacts/3/zip", "", True) == b"PK\x03\x04bytes"
    assert not seen["req"].has_header("Authorization")
    assert seen["resp"].asked == npi.MAX_ARCHIVE + 1


def test_get_binary_over_budget(monkeypatch):
    monkeypatch.setattr(npi, "MAX_ARCHIVE", 4)
    _fake_opener(monkeypatch, b"123456")
    with pytest.raises(ValueError, match="^artifact download over budget$"):
        npi.get("/repos/GBOGEB/CODEX/actions/artifacts/3/zip", "", True)


@pytest.mark.parametrize("path", ["/repos/OTHER/x", "/repos/GBOGEB/../x",
                                  "/repos/GBOGEB//x", "https://evil/repos/GBOGEB/x"])
def test_get_rejects_disallowed_paths(monkeypatch, path):
    monkeypatch.setattr(npi.urllib.request, "build_opener",
                        lambda *a: pytest.fail("network"))
    with pytest.raises(ValueError, match="^disallowed API path$"):
        npi.get(path, "")


# --- collect -------------------------------------------------------------------------

def _router(run, job_pages, artifact_pages, archive=b"ZIP"):
    calls = []

    def fake_get(path, token, binary=False):
        calls.append((path, token, binary))
        base = "/repos/" + REPO + "/actions/runs/17"
        if path == base:
            return run
        if path.startswith(base + "/jobs?per_page=100&page="):
            return job_pages[int(path.rsplit("=", 1)[1]) - 1]
        if path.startswith(base + "/artifacts?per_page=100&page="):
            return artifact_pages[int(path.rsplit("=", 1)[1]) - 1]
        if path.endswith("/zip"):
            assert binary is True
            return archive
        raise AssertionError(path)

    fake_get.calls = calls
    return fake_get


def test_collect_metadata_only(monkeypatch):
    run, jobs, artifacts, _ = fixture()
    g = _router(run, [{"jobs": jobs["jobs"], "total_count": 1}],
                [{"artifacts": artifacts["artifacts"], "total_count": 1}])
    monkeypatch.setattr(npi, "get", g)
    r, j, a, raw = npi.collect(REPO, 17, token="test-token")
    assert r is run
    assert j == {"jobs": jobs["jobs"]}
    assert a == {"artifacts": artifacts["artifacts"]}
    assert raw is None
    assert all(t == "test-token" for _, t, _ in g.calls)
    assert len(g.calls) == 3


def test_collect_multi_page_and_artifact_download(monkeypatch):
    run, _, _, _ = fixture()
    page1 = [{"id": i, "run_id": 17} for i in range(1, 101)]
    page2 = [{"id": 101, "run_id": 17}]
    arts = [{"id": 19, "name": "pulse-measurement", "expired": False},
            {"id": 20, "name": "other", "expired": False}]
    g = _router(run, [{"jobs": page1, "total_count": 101}, {"jobs": page2, "total_count": 101}],
                [{"artifacts": arts, "total_count": 2}], archive=b"ARCHIVE")
    monkeypatch.setattr(npi, "get", g)
    _, jobs, _, raw = npi.collect(REPO, 17, "pulse-measurement")
    assert len(jobs["jobs"]) == 101
    assert raw == b"ARCHIVE"
    assert g.calls[-1] == ("/repos/" + REPO + "/actions/artifacts/19/zip", "", True)


@pytest.mark.parametrize("repo,run_id,msg", [
    ("GBOGEB/unknown", 17, "repository not in controlled cohort"),
    (REPO, 0, "invalid run ID"),
    (REPO, True, "invalid run ID"),
])
def test_collect_identity_guards(monkeypatch, repo, run_id, msg):
    monkeypatch.setattr(npi, "get", lambda *a, **k: pytest.fail("io"))
    with pytest.raises(ValueError, match="^" + msg + "$"):
        npi.collect(repo, run_id)


def _pages_error(monkeypatch, job_pages, msg):
    run, _, _, _ = fixture()
    monkeypatch.setattr(npi, "get", _router(run, job_pages, []))
    with pytest.raises(ValueError, match="^" + msg + "$"):
        npi.collect(REPO, 17)


def test_collect_invalid_list(monkeypatch):
    _pages_error(monkeypatch, [{"jobs": None, "total_count": 0}], "invalid GitHub jobs")


def test_collect_invalid_total_count(monkeypatch):
    _pages_error(monkeypatch, [{"jobs": [{}, {}], "total_count": 1}], "invalid total_count")


def test_collect_truncated_pagination(monkeypatch):
    _pages_error(monkeypatch, [{"jobs": [{}], "total_count": 5}], "truncated GitHub pagination")


def test_collect_pagination_limit(monkeypatch):
    pages = [{"jobs": [{}] * 100, "total_count": 5000} for _ in range(10)]
    _pages_error(monkeypatch, pages, "GitHub pagination limit exceeded")


@pytest.mark.parametrize("name,arts,msg", [
    ("bad name!", [], "invalid artifact name"),
    ("x", [{"id": 1, "name": "x"}, {"id": 2, "name": "x"}], "requested artifact not uniquely present"),
    ("x", [], "requested artifact not uniquely present"),
    ("x", [{"id": 1, "name": "x", "expired": True}], "artifact missing/expired"),
    ("x", [{"id": 0, "name": "x", "expired": False}], "artifact missing/expired"),
])
def test_collect_artifact_selection_errors(monkeypatch, name, arts, msg):
    run, jobs, _, _ = fixture()
    monkeypatch.setattr(npi, "get", _router(run, [{"jobs": jobs["jobs"], "total_count": 1}],
                                            [{"artifacts": arts, "total_count": len(arts)}]))
    with pytest.raises(ValueError, match="^" + msg + "$"):
        npi.collect(REPO, 17, name)


# --- validate branch not covered elsewhere -----------------------------------------

def test_validate_artifact_without_workflow_run_binding_is_accepted():
    run, jobs, artifacts, inner = fixture()
    report = npi.validate(REPO, 17, run, jobs, artifacts, artifact_name="pulse-measurement",
                          archive=zip_receipt(inner), metadata_origin="LIVE_GITHUB_API")
    assert report["evidence_depth"] == "RUN_BOUND_ARTIFACT_RECEIPT_INSPECTED"
    assert report["measurement"]["line"]["pct"] == 25.0
    assert report["measurement"]["branch"]["pct"] == 100.0
    assert report["artifact_id"] == 19
    assert report["metadata_origin"] == "LIVE_GITHUB_API"


# --- main ------------------------------------------------------------------------------

def _offline_files(tmp_path, with_archive):
    run, jobs, artifacts, inner = fixture()
    paths = {}
    for name, obj in (("run", run), ("jobs", jobs), ("artifacts", artifacts)):
        paths[name] = tmp_path / (name + ".json")
        paths[name].write_text(json.dumps(obj), encoding="utf-8")
    if with_archive:
        paths["archive"] = tmp_path / "a.zip"
        paths["archive"].write_bytes(zip_receipt(inner))
    return paths


def test_main_offline_with_archive(monkeypatch, tmp_path, capsys):
    f = _offline_files(tmp_path, True)
    out = tmp_path / "out"
    monkeypatch.setattr(npi, "collect", lambda *a, **k: pytest.fail("live"))
    monkeypatch.setattr(sys, "argv", ["npi", "--repo", REPO, "--run-id", "17",
                                      "--artifact-name", "pulse-measurement",
                                      "--expected-sha", SHA, "--out", str(out), "--offline",
                                      "--run-json", str(f["run"]), "--jobs-json", str(f["jobs"]),
                                      "--artifacts-json", str(f["artifacts"]),
                                      "--archive", str(f["archive"])])
    npi.main()
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "PASS"
    assert printed["evidence_depth"] == "RUN_BOUND_ARTIFACT_RECEIPT_INSPECTED"
    event = json.loads(Path(printed["path"]).read_text(encoding="utf-8"))
    assert event["metadata_origin"] == "CALLER_SUPPLIED_OFFLINE"
    assert event["event_sha256"] == printed["event_sha256"]
    ledger = json.loads((out / "native_pulse_ledger.json").read_text(encoding="utf-8"))
    assert ledger["archive_downloads_validated"] == 1
    assert "1/4 lines; 2/2 branches" in (out / "native_pulse_index.html").read_text(encoding="utf-8")


def test_main_offline_without_archive_is_metadata_only(monkeypatch, tmp_path, capsys):
    f = _offline_files(tmp_path, False)
    monkeypatch.setattr(sys, "argv", ["npi", "--repo", REPO, "--run-id", "17",
                                      "--out", str(tmp_path / "o"), "--offline",
                                      "--run-json", str(f["run"]), "--jobs-json", str(f["jobs"]),
                                      "--artifacts-json", str(f["artifacts"])])
    npi.main()
    printed = json.loads(capsys.readouterr().out)
    assert printed["evidence_depth"] == "RUN_METADATA_ONLY"


def test_main_offline_requires_triplet(monkeypatch, tmp_path):
    f = _offline_files(tmp_path, False)
    monkeypatch.setattr(sys, "argv", ["npi", "--repo", REPO, "--run-id", "17",
                                      "--out", str(tmp_path / "o"), "--offline",
                                      "--run-json", str(f["run"])])
    with pytest.raises(ValueError, match="^offline input triplet required$"):
        npi.main()
    assert not (tmp_path / "o").exists()


def test_main_live_rejects_offline_files(monkeypatch, tmp_path):
    f = _offline_files(tmp_path, False)
    monkeypatch.setattr(npi, "collect", lambda *a, **k: pytest.fail("live"))
    monkeypatch.setattr(sys, "argv", ["npi", "--repo", REPO, "--run-id", "17",
                                      "--out", str(tmp_path / "o"), "--jobs-json", str(f["jobs"])])
    with pytest.raises(ValueError, match="^offline files must not be passed as live evidence$"):
        npi.main()


def test_main_live_uses_collect_with_env_token(monkeypatch, tmp_path, capsys):
    run, jobs, artifacts, _ = fixture()
    seen = {}

    def fake_collect(repo, run_id, artifact_name=None, token=""):
        seen.update(repo=repo, run_id=run_id, artifact_name=artifact_name, token=token)
        return run, jobs, artifacts, None

    monkeypatch.setattr(npi, "collect", fake_collect)
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setattr(sys, "argv", ["npi", "--repo", REPO, "--run-id", "17",
                                      "--out", str(tmp_path / "o")])
    npi.main()
    assert seen == {"repo": REPO, "run_id": 17, "artifact_name": None, "token": "test-token"}
    printed = json.loads(capsys.readouterr().out)
    event = json.loads(Path(printed["path"]).read_text(encoding="utf-8"))
    assert event["metadata_origin"] == "LIVE_GITHUB_API"
    assert event["measurement"] is None


def test_main_live_without_token_passes_empty(monkeypatch, tmp_path, capsys):
    run, jobs, artifacts, _ = fixture()
    tokens = []
    monkeypatch.setattr(npi, "collect",
                        lambda repo, rid, name=None, token="": tokens.append(token) or
                        (run, jobs, artifacts, None))
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(sys, "argv", ["npi", "--repo", REPO, "--run-id", "17",
                                      "--out", str(tmp_path / "o")])
    npi.main()
    assert tokens == [""]
