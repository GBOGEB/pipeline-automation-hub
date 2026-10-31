"""Coverage wave w10: w2_live_bridge read-only GitHub client (faked urllib), make() and CLI."""
import copy
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
MOD_DIR = REPO_ROOT / "mission-control" / "federation-atlas" / "mission_rebuild"
MOD_PATH = MOD_DIR / "w2_live_bridge.py"
if str(MOD_DIR) not in sys.path:
    sys.path.insert(0, str(MOD_DIR))
_spec = importlib.util.spec_from_file_location("cw_w10_w2_live_bridge_mod", MOD_PATH)
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)

BRIDGE = json.loads(m.BRIDGE.read_text(encoding="utf-8"))
HEAD = "b" * 40
GG_SOURCES = (BRIDGE["provider"]["source_head_sha"], "d073992785c68820c3c9aa44260314fb82bd8f34")


def run(identity, head, status, conclusion=None, attempt=1):
    return {"id": identity, "head_sha": head, "status": status, "conclusion": conclusion,
            "run_attempt": attempt, "created_at": "2026-10-17T18:00:00Z",
            "updated_at": "2026-10-17T18:10:00Z"}


def jobs(run_id, ids, status="completed", conclusion="success"):
    return {"total_count": len(ids),
            "jobs": [{"id": x, "run_id": run_id, "status": status, "conclusion": conclusion,
                      "steps": [{"name": "s", "number": 1, "status": "completed",
                                 "conclusion": "success"}]} for x in ids]}


def fixture():
    w, gg, r = m.W1_REPO, m.GG_REPO, str(m.W1_RUN)
    rows = {
        w + "/actions/runs/" + r: run(m.W1_RUN, m.W1_HEAD, "completed", "success"),
        w + "/actions/runs/" + r + "/jobs?per_page=100": jobs(m.W1_RUN, [11, 12]),
        w + "/actions/runs/" + r + "/artifacts?per_page=100": {
            "total_count": 2, "artifacts": [{"id": 1, "name": "a", "size_in_bytes": 5,
                                             "digest": "sha256:" + "a" * 64}]},
        w + "/pulls/669/reviews?per_page=100": [
            {"state": "APPROVED", "user": {"login": "someone"}},
            {"state": "APPROVED", "user": {"login": "GBOGEB"}},
            {"state": "COMMENTED", "user": {"login": "x"}},
            {"state": "APPROVED"}],
        w + "/actions/runs?status=queued&per_page=1": {"total_count": 3},
        w + "/actions/runs?status=in_progress&per_page=1": {"total_count": -1},
    }
    for n, sha in zip(m.GG_RUNS, GG_SOURCES):
        rows[gg + "/actions/runs/" + str(n)] = run(n, sha, "in_progress")
        rows[gg + "/actions/runs/" + str(n) + "/jobs?per_page=100"] = jobs(n, [n % 1000 + 1])
        rows[gg + "/actions/runs/" + str(n) + "/artifacts?per_page=100"] = {"total_count": 0}
    return rows


def client_for(rows, missing=()):
    def read(repo, suffix):
        key = repo + suffix
        if key in missing:
            raise urllib.error.URLError("offline")
        return rows[key]
    return read


# ---- ReadOnlyGithub with faked urllib -----------------------------------

class FakeResponse:
    def __init__(self, body, status=200):
        self.status = status
        self._buf = io.BytesIO(body)

    def read(self, n=-1):
        return self._buf.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def urlopen(monkeypatch):
    calls = []
    state = {"body": b'{"ok": true}', "status": 200}

    def fake(req, timeout=None):
        calls.append((req, timeout))
        return FakeResponse(state["body"], state["status"])

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    return calls, state


def test_client_get_with_token(urlopen):
    calls, _ = urlopen
    out = m.ReadOnlyGithub("test-token")(m.W1_REPO, "/pulls/1")
    assert out == {"ok": True}
    req, timeout = calls[0]
    assert req.full_url == "https://api.github.com/repos/" + m.W1_REPO + "/pulls/1"
    assert req.get_method() == "GET"
    assert req.get_header("Authorization") == "Bearer test-token"
    assert timeout == 15


def test_client_without_token_sends_no_auth(urlopen):
    calls, _ = urlopen
    client = m.ReadOnlyGithub("")
    assert client.token is None
    client(m.GG_REPO, "/x")
    assert calls[0][0].get_header("Authorization") is None


@pytest.mark.parametrize("repo,suffix,msg", [
    ("evil/repo", "/x", "allowlist"),
    (m.W1_REPO, "x", "unsafe API path"),
    (m.W1_REPO, None, "unsafe API path"),
    (m.W1_REPO, "/a/../b", "unsafe API path"),
    (m.W1_REPO, "/http://x", "unsafe API path"),
])
def test_client_rejects_unsafe_requests(urlopen, repo, suffix, msg):
    calls, _ = urlopen
    with pytest.raises(ValueError, match=msg):
        m.ReadOnlyGithub("test-token")(repo, suffix)
    assert calls == []


def test_client_rejects_non_200(urlopen):
    _, state = urlopen
    state["status"] = 204
    with pytest.raises(ValueError, match="unexpected GitHub status"):
        m.ReadOnlyGithub(None)(m.W1_REPO, "/x")


def test_client_bounds_response(urlopen):
    _, state = urlopen
    state["body"] = b" " * 2_500_001
    with pytest.raises(ValueError, match="bounded API response"):
        m.ReadOnlyGithub(None)(m.W1_REPO, "/x")


# ---- helpers ----------------------------------------------------------------

@pytest.mark.parametrize("exc", [
    urllib.error.URLError("down"), TimeoutError("slow"), OSError("io"), ValueError("v" * 300),
    KeyError("k"), json.JSONDecodeError("bad", "doc", 0),
])
def test_maybe_records_error(exc):
    def boom(repo, suffix):
        raise exc
    errors = {}
    assert m.maybe(boom, m.W1_REPO, "/x", errors, "key") is None
    assert errors["key"].startswith(type(exc).__name__ + ": ")
    assert len(errors["key"]) <= len(type(exc).__name__) + 2 + 120


def test_maybe_does_not_swallow_other_errors():
    def boom(repo, suffix):
        raise RuntimeError("x")
    with pytest.raises(RuntimeError):
        m.maybe(boom, m.W1_REPO, "/x", {}, "k")


@pytest.mark.parametrize("payload", [None, {"total_count": "1"}, {"total_count": 0, "artifacts": [{}]}])
def test_artifacts_fail_closed(payload):
    with pytest.raises(ValueError, match="MC_W2_FAIL_CLOSED"):
        m.artifacts(payload)


def test_run_status_urls_and_validation():
    s = m.run_status(run(m.W1_RUN, m.W1_HEAD, "completed", "success"), m.W1_HEAD, m.W1_RUN)
    assert s["url"].startswith("https://github.com/" + m.W1_REPO)
    g = m.run_status(run(m.GG_RUNS[0], "c" * 40, "queued"), "c" * 40, m.GG_RUNS[0])
    assert g["url"].startswith("https://github.com/" + m.GG_REPO)
    for bad in ({"run_attempt": 0}, {"run_attempt": True}, {"status": "weird"}):
        with pytest.raises(ValueError):
            m.run_status(dict(run(m.W1_RUN, m.W1_HEAD, "queued"), **bad), m.W1_HEAD, m.W1_RUN)
    with pytest.raises(ValueError, match="identity"):
        m.run_status([], m.W1_HEAD, m.W1_RUN)


# ---- make() -----------------------------------------------------------------

def test_make_full_success_population():
    s = m.make(client_for(fixture()), HEAD, copy.deepcopy(BRIDGE), "t")
    assert s["w1"]["native_success_with_known_job_population"] is True
    assert s["w1"]["artifacts"]["complete"] is False
    assert s["review"]["recorded_reviews"] == 4
    assert s["review"]["independent_approvals"] == 2
    assert s["unknown_burndown"]["reviews"]["status"] == "RECORDED_NOT_ACCEPTANCE"
    assert s["fleet"]["queued_run_count"] == 3
    assert s["fleet"]["in_progress_run_count"] is None
    assert s["gg_math"]["stale_bridge_classification"] == "NO_STALE_TERMINAL_PROOF"
    assert s["readback_errors"] == {}


def test_make_all_reads_fail():
    def down(repo, suffix):
        raise urllib.error.URLError("offline")
    s = m.make(down, HEAD, copy.deepcopy(BRIDGE), "t")
    assert s["w1"]["run"] is None and s["w1"]["jobs"] is None and s["w1"]["artifacts"] is None
    assert s["w1"]["attempt_2"] == "UNKNOWN"
    assert s["review"]["recorded_reviews"] is None
    assert s["review"]["independent_approvals"] is None
    assert s["unknown_burndown"]["reviews"]["status"] == "UNKNOWN"
    assert s["gg_math"]["stale_bridge_classification"] == "FRESHNESS_UNVERIFIED"
    assert all(p == {"run": None, "jobs": None, "artifacts": None} for p in s["gg_math"]["provider"])
    assert set(s["readback_errors"]) == {"w1_run", "reviews", "fleet_queued", "fleet_in_progress",
                                         "gg_run_" + str(m.GG_RUNS[0]), "gg_run_" + str(m.GG_RUNS[1])}


def test_make_partial_reads_and_large_review_page():
    rows = fixture()
    w, r = m.W1_REPO, str(m.W1_RUN)
    rows[w + "/pulls/669/reviews?per_page=100"] = [{"state": "APPROVED", "user": {"login": "z"}}] * 100
    missing = {w + "/actions/runs/" + r + "/jobs?per_page=100",
               w + "/actions/runs/" + r + "/artifacts?per_page=100",
               m.GG_REPO + "/actions/runs/" + str(m.GG_RUNS[1]) + "/jobs?per_page=100"}
    s = m.make(client_for(rows, missing), HEAD, copy.deepcopy(BRIDGE), "t")
    assert s["w1"]["jobs"] is None and s["w1"]["artifacts"] is None
    assert s["w1"]["native_success_with_known_job_population"] is False
    assert s["review"]["recorded_reviews"] is None
    assert s["gg_math"]["provider"][1]["jobs"] is None
    assert s["gg_math"]["provider"][1]["artifacts"] is not None


def test_make_empty_reviews_known_zero():
    rows = fixture()
    rows[m.W1_REPO + "/pulls/669/reviews?per_page=100"] = []
    s = m.make(client_for(rows), HEAD, copy.deepcopy(BRIDGE), "t")
    assert s["unknown_burndown"]["reviews"]["status"] == "KNOWN_ZERO"
    assert s["review"]["independent_approvals"] == 0


def test_make_rejects_non_list_reviews():
    rows = fixture()
    rows[m.W1_REPO + "/pulls/669/reviews?per_page=100"] = {"x": 1}
    with pytest.raises(ValueError, match="review response type"):
        m.make(client_for(rows), HEAD, copy.deepcopy(BRIDGE), "t")


@pytest.mark.parametrize("head", [None, "B" * 40, "b" * 41])
def test_make_requires_exact_head(head):
    with pytest.raises(ValueError, match="consumer checkout identity"):
        m.make(client_for(fixture()), head, copy.deepcopy(BRIDGE), "t")


@pytest.mark.parametrize("mutate,msg", [
    (lambda b: b.__setitem__("schema", "x"), "custody"),
    (lambda b: b.__setitem__("snapshot_atomic", True), "custody"),
    (lambda b: b.pop("controls"), "custody"),
    (lambda b: b["controls"].__setitem__("authority_transfer", True), "custody"),
    (lambda b: b["provider"].__setitem__("source_head_sha", "0" * 40), "pinned gg_MATH producer head"),
    (lambda b: b["provider"].__setitem__("native_candidate_run", 1), "provider run identity"),
    (lambda b: b["method"].__setitem__("live_pulse_receipts_ingested", 1), "unacknowledged"),
])
def test_make_bridge_custody(mutate, msg):
    bridge = copy.deepcopy(BRIDGE)
    mutate(bridge)
    with pytest.raises(ValueError, match=msg):
        m.make(client_for(fixture()), HEAD, bridge, "t")


# ---- receipt + CLI ------------------------------------------------------------

def test_write_receipt_hash(tmp_path):
    out = tmp_path / "deep" / "r.json"
    digest = m.write_receipt({"b": 1, "a": "é"}, out)
    raw = out.read_bytes()
    import hashlib
    assert digest == hashlib.sha256(raw).hexdigest()
    assert raw.endswith(b"\n") and "é".encode("utf-8") in raw


def test_cli_fixture_mode(tmp_path, monkeypatch, capsys):
    fx = tmp_path / "fx.json"
    fx.write_text(json.dumps(fixture()), encoding="utf-8")
    out = tmp_path / "out" / "w2.json"
    monkeypatch.setattr(sys, "argv", [str(MOD_PATH), "--head", HEAD, "--out", str(out),
                                      "--fixture", str(fx)])
    runpy.run_path(str(MOD_PATH), run_name="__main__")
    line = json.loads(capsys.readouterr().out)
    assert line["W2_READ_ONLY_STATUS"] == "CAPTURED_WITH_HOLDS"
    assert line["w1_attempt"] == 1
    rec = json.loads(out.read_text(encoding="utf-8"))
    assert rec["evidence_class"] == "SYNTHETIC_TEST_FIXTURE_NOT_NATIVE"


def test_cli_fixture_missing_key_is_recorded(tmp_path, monkeypatch, capsys):
    fx = tmp_path / "fx.json"
    fx.write_text("{}", encoding="utf-8")
    out = tmp_path / "w2.json"
    monkeypatch.setattr(sys, "argv", [str(MOD_PATH), "--head", HEAD, "--out", str(out),
                                      "--fixture", str(fx)])
    runpy.run_path(str(MOD_PATH), run_name="__main__")
    rec = json.loads(out.read_text(encoding="utf-8"))
    assert "fixture missing" in rec["readback_errors"]["w1_run"]
    assert json.loads(capsys.readouterr().out)["w1_attempt"] is None


def test_cli_live_mode_uses_token_and_faked_network(tmp_path, monkeypatch, capsys):
    seen = []

    def offline(req, timeout=None):
        seen.append(req.get_header("Authorization"))
        raise urllib.error.URLError("no network in tests")

    monkeypatch.setattr(urllib.request, "urlopen", offline)
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    out = tmp_path / "w2.json"
    monkeypatch.setattr(sys, "argv", [str(MOD_PATH), "--head", HEAD, "--out", str(out)])
    runpy.run_path(str(MOD_PATH), run_name="__main__")
    rec = json.loads(out.read_text(encoding="utf-8"))
    assert rec["evidence_class"] == "GITHUB_API_METADATA_READ_ONLY"
    assert seen and set(seen) == {"Bearer test-token"}
    assert json.loads(capsys.readouterr().out)["gg_math_freshness"] == "FRESHNESS_UNVERIFIED"
