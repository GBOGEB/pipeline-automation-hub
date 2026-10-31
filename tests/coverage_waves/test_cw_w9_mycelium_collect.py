"""Coverage wave w9: mission-control/gogreen/mycelium_history/collect.py (urllib and token faked)."""
import hashlib
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
MOD_PATH = REPO_ROOT / "mission-control" / "gogreen" / "mycelium_history" / "collect.py"
_spec = importlib.util.spec_from_file_location("cw_w9_mycelium_collect_mod", MOD_PATH)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

SHA_A = "a" * 40
SHA_B = "b" * 40
WF = 371030423
RUNS_BASE = "/repos/GBOGEB/CODEX/actions/workflows/missioncontrol-mycelium.yml/runs"


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def fake_urlopen(payload, seen):
    def urlopen(request, timeout=None):
        seen.append((request, timeout))
        return FakeResponse(payload)
    return urlopen


def raw_run(rid, conclusion="success", created="2026-10-01T00:00:00Z", attempt=1, status="completed"):
    return {"id": rid, "run_attempt": attempt, "head_sha": SHA_A, "workflow_id": WF,
            "status": status, "conclusion": conclusion if status == "completed" else None,
            "created_at": created, "name": "Mycelium"}


def run_row(rid, conclusion, created="2026-10-01T00:00:00Z"):
    return {"id": rid, "conclusion": conclusion, "created_at": created, "attempt": 1}


# ------------------------------------------------------------------ request_json / get_log_bytes
def test_request_json_with_token(monkeypatch):
    seen = []
    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen(b'{"ok": 1}', seen))
    assert mod.request_json("/repos/GBOGEB/CODEX/branches/main", token="test-token") == {"ok": 1}
    req, timeout = seen[0]
    assert req.full_url == "https://api.github.com/repos/GBOGEB/CODEX/branches/main"
    assert req.get_header("Authorization") == "Bearer test-token" and timeout == 35
    assert req.get_method() == "GET"


def test_request_json_without_token_list(monkeypatch):
    seen = []
    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen(b"[1, 2]", seen))
    assert mod.request_json("/repos/GBOGEB/CODEX/pulls") == [1, 2]
    assert seen[0][0].get_header("Authorization") is None


def test_request_json_rejects_scalar_document(monkeypatch):
    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen(b"3", []))
    with pytest.raises(ValueError, match="unexpected document type"):
        mod.request_json("/repos/GBOGEB/CODEX/x")


@pytest.mark.parametrize("path", ["/repos/GBOGEB/OTHER/x", "/repos/GBOGEB/CODEX//x",
                                  "/repos/GBOGEB/CODEX/https://evil"])
def test_request_json_rejects_unsafe_paths(path, monkeypatch):
    monkeypatch.setattr(mod.urllib.request, "urlopen", lambda *a, **k: pytest.fail("network"))
    with pytest.raises(ValueError, match="external or unsafe"):
        mod.request_json(path)


def test_get_log_bytes_token_and_no_token(monkeypatch):
    seen = []
    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen(b"log", seen))
    assert mod.get_log_bytes(5, token="test-token") == b"log"
    assert mod.get_log_bytes(6) == b"log"
    assert seen[0][0].get_header("Authorization") == "Bearer test-token" and seen[0][1] == 40
    assert seen[1][0].get_header("Authorization") is None
    assert seen[0][0].full_url.endswith("/repos/GBOGEB/CODEX/actions/jobs/5/logs")


def test_get_log_bytes_bounds(monkeypatch):
    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen(b"x" * 3_000_001, []))
    with pytest.raises(ValueError, match="bounded readable size"):
        mod.get_log_bytes(5)
    with pytest.raises(ValueError, match="log job ID"):
        mod.get_log_bytes(0)
    with pytest.raises(ValueError, match="log job ID"):
        mod.get_log_bytes("5")


# ------------------------------------------------------------------ pure helpers
@pytest.mark.parametrize("line,expected", [
    ("##[error]Generated inventory drift found", "GENERATED_EXECUTABLE_INVENTORY_DRIFT"),
    ("##[error]inventory generated stale", "GENERATED_EXECUTABLE_INVENTORY_DRIFT"),
    ("##[error]untracked public file", "PUBLICATION_MANIFEST_DRIFT"),
    ("##[error]stale artifact present", "PUBLICATION_MANIFEST_DRIFT"),
    ("##[error]PR-007 violated", "GOVERNANCE_HEADER_FIRST_RED"),
    ("##[error]missing governance header", "GOVERNANCE_HEADER_FIRST_RED"),
    ("##[error]job timeout", "EXECUTION_TIMEOUT"),
    ("##[error]step timed out", "EXECUTION_TIMEOUT"),
    ("##[error]HTTP 401", "OWNER_AUTHORIZATION_GATE"),
    ("##[error]HTTP 403", "OWNER_AUTHORIZATION_GATE"),
    ("##[error]Permission denied", "OWNER_AUTHORIZATION_GATE"),
    ("##[error]test failed", "NATIVE_TEST_ASSERTION"),
    ("##[error]AssertionError", "NATIVE_TEST_ASSERTION"),
    ("##[error]inventory only", None),
])
def test_parse_error_classes(line, expected):
    got = mod.parse_error(("noise\necho ##[error]ignored test\n" + line + "\n").encode())
    if expected is None:
        clue = "inventory only"
        assert got == "UNCLASSIFIED_ERROR_" + hashlib.sha256(clue.encode()).hexdigest()[:12]
    else:
        assert got == expected


def test_parse_error_no_error_line():
    assert mod.parse_error(b"all good\n\xff\n") is None


def test_select_for_jobs_quota_and_fill():
    runs = [run_row(1, "failure", "2026-10-01"), run_row(2, "failure", "2026-10-02"),
            run_row(3, "timed_out", "2026-10-03"), run_row(4, "success", "2026-10-04"),
            run_row(5, "success", "2026-10-05"), run_row(6, "cancelled", "2026-10-06"),
            run_row(7, None, None)]
    picked = [r["id"] for r in mod.select_for_jobs(runs, 4)]
    # red quota = max(1, (20+7)//8) = 3, green quota = 1
    assert picked == [3, 2, 1, 5]
    assert [r["id"] for r in mod.select_for_jobs(runs, 7)] == [3, 2, 1, 5, 4, 6, 7]


def test_select_for_jobs_single_stratum_lends_capacity():
    greens = [run_row(i, "success", "2026-10-0" + str(i)) for i in range(1, 5)]
    assert [r["id"] for r in mod.select_for_jobs(greens, 2)] == [4, 3]
    reds = [run_row(i, "failure", "2026-10-0" + str(i)) for i in range(1, 4)]
    assert [r["id"] for r in mod.select_for_jobs(reds, 5)] == [3, 2, 1]


def test_select_for_jobs_skips_duplicate_ids_in_fill():
    runs = [run_row(5, "failure", "2026-10-09"), run_row(6, "failure", "2026-10-08"),
            run_row(7, "failure", "2026-10-07"), run_row(5, "failure", "2026-10-01")]
    assert [r["id"] for r in mod.select_for_jobs(runs, 4)] == [5, 6, 7]


def test_select_for_jobs_rejects_bad_size():
    with pytest.raises(ValueError, match="job selection size"):
        mod.select_for_jobs([], 0)
    with pytest.raises(ValueError, match="job selection size"):
        mod.select_for_jobs([], True)


def pr(number, merged=True, head=SHA_A, merge=SHA_B, base=True):
    d = {"number": number, "title": "t" * 300, "merged_at": "2026-10-01T00:00:00Z" if merged else None,
         "head": {"sha": head}, "merge_commit_sha": merge}
    if base:
        d["base"] = {"ref": "main"}
    return d


def test_merged_pr_sample_pages_and_filters():
    page1 = [pr(i) for i in range(1, 100)] + [pr(100, merged=False)]
    page2 = [pr(200, merge="nope", base=False)]
    pages = {1: page1, 2: page2}
    calls = []

    def fetch(path):
        calls.append(path)
        return pages[int(path.rsplit("=", 1)[1])]
    found = mod.merged_pr_sample(fetch)
    assert len(calls) == 2 and len(found) == 100
    assert found[0]["title"] == "t" * 250 and found[0]["merge_sha"] == SHA_B and found[0]["base"] == "main"
    assert found[-1]["merge_sha"] is None and found[-1]["base"] is None
    assert found[-1]["url"] == "https://github.com/GBOGEB/CODEX/pull/200"


def test_merged_pr_sample_exhausts_max_pages():
    full = [pr(i) for i in range(100)]
    calls = []

    def fetch(path):
        calls.append(path)
        return full
    assert len(mod.merged_pr_sample(fetch, max_pages=2)) == 200 and len(calls) == 2


def test_merged_pr_sample_rejects_bad_pages():
    with pytest.raises(ValueError, match="merged PR page invalid"):
        mod.merged_pr_sample(lambda p: {"x": 1})
    with pytest.raises(ValueError, match="PR head missing"):
        mod.merged_pr_sample(lambda p: [{"number": 1, "merged_at": "x", "head": None}])


def test_read_run_pages_empty_population():
    out = mod.read_run_pages(lambda p: {"total_count": 0, "workflow_runs": []})
    assert out["runs"] == [] and out["workflow_id"] is None and out["run_inventory_complete"] is True
    assert out["page_count"] == 1


# ------------------------------------------------------------------ collect()
def job(jid, steps=None, conclusion="success"):
    return {"id": jid, "name": "j%s" % jid, "status": "completed", "conclusion": conclusion,
            "steps": steps or []}


FAIL_STEPS = [{"number": 1, "name": "setup", "status": "completed", "conclusion": "success"},
              {"number": 2, "name": "build", "status": "completed", "conclusion": "failure"},
              {"number": 3, "name": "post", "status": "completed", "conclusion": "skipped"}]


class World:
    def __init__(self, sha_after=SHA_A):
        self.sha_after = sha_after
        self.branch_calls = 0
        self.runs = [raw_run(10, "failure", "2026-10-10"), raw_run(11, "failure", "2026-10-11"),
                     raw_run(12, "success", "2026-10-12"), raw_run(13, "timed_out", "2026-10-13"),
                     raw_run(14, "failure", "2026-10-14")]
        self.jobs = {
            10: [job(100, FAIL_STEPS, "failure"), job(101, FAIL_STEPS, "failure"), job(102, FAIL_STEPS, "failure")],
            11: [job(110, FAIL_STEPS, "failure")],
            12: [job(120)],
            14: [job(140, FAIL_STEPS, "failure")],
        }

    def fetch(self, path):
        if path.endswith("/branches/main"):
            self.branch_calls += 1
            return {"commit": {"sha": SHA_A if self.branch_calls == 1 else self.sha_after}}
        if path.startswith(RUNS_BASE):
            return {"total_count": len(self.runs), "workflow_runs": self.runs}
        if "/actions/runs/" in path and "/jobs" in path:
            rid = int(path.split("/actions/runs/")[1].split("/")[0])
            if rid == 13:
                raise urllib.error.URLError("offline")
            return {"total_count": len(self.jobs[rid]), "jobs": self.jobs[rid]}
        if "/pulls?" in path:
            return [pr(1)]
        raise AssertionError(path)


def get_logs(job_id):
    if job_id == 101:
        raise urllib.error.HTTPError("u", 410, "gone", {}, None)
    if job_id == 102:
        raise ValueError("MYCELIUM_CAPTURE_HOLD: too big")
    return b"##[error]job timeout\n"


def test_collect_full_flow():
    w = World()
    out = mod.collect(w.fetch, get_logs, max_failure_logs=5)
    assert out["source_main_before"] == SHA_A and out["source_main_stable_during_scan"] is True
    assert out["observed_run_count"] == 5 and out["run_inventory_complete"] is True
    assert out["job_detail_error_count"] == 1
    assert out["job_detail_errors"] == [{"run_id": 13, "kind": "URLError"}]
    assert out["selected_job_run_count"] == 4
    assert out["log_read_attempts"] == 5 and out["failure_log_reads"] == 3
    assert out["unreadable_log_attempts"] == 2
    statuses = {j["id"]: j["log_read_status"] for d in out["selected_job_details"].values() for j in d["jobs"]}
    assert statuses[101] == "HTTPERROR" and statuses[102] == "VALUEERROR"
    assert statuses[120] == "NOT_REQUESTED"
    read = [j for d in out["selected_job_details"].values() for j in d["jobs"] if j["log_read_status"] == "READ_BOUNDED"]
    assert all(j["log_first_error"] == "EXECUTION_TIMEOUT" and len(j["log_bytes_sha256"]) == 64 for j in read)
    assert list(statuses.values()).count("NOT_REQUESTED") == 1
    assert out["older_attempts_collected"] is True and out["merged_pr_sample_is_complete"] is False
    assert out["merge_admission"] == "HOLD" and out["capture_at"].endswith("Z")


def test_collect_main_moved_during_scan():
    out = mod.collect(World(sha_after=SHA_B).fetch, get_logs, max_failure_logs=0)
    assert out["source_main_after"] == SHA_B and out["source_main_stable_during_scan"] is False
    assert out["log_read_attempts"] == 0


def test_collect_bad_branch_shas():
    with pytest.raises(ValueError, match="CODEX main SHA"):
        mod.collect(lambda p: {"commit": None}, get_logs)
    with pytest.raises(ValueError, match="CODEX current SHA"):
        mod.collect(World(sha_after="nope").fetch, get_logs)


# ------------------------------------------------------------------ main()
def test_main_writes_output(tmp_path, monkeypatch, capsys):
    w = World()
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    tokens = []

    def request_json(path, *, token=None):
        tokens.append(token)
        return w.fetch(path)

    def logs(job_id, *, token=None):
        tokens.append(token)
        return get_logs(job_id)

    monkeypatch.setattr(mod, "request_json", request_json)
    monkeypatch.setattr(mod, "get_log_bytes", logs)
    out = tmp_path / "deep" / "capture.json"
    monkeypatch.setattr(sys, "argv", ["collect.py", "--output", str(out), "--max-runs", "50",
                                      "--job-detail-limit", "5", "--failure-log-limit", "2"])
    mod.main()
    summary = json.loads(capsys.readouterr().out)
    assert summary == {"observed": 5, "api_total": 5, "complete": True, "detail_jobs": 4, "errors": 1,
                       "merge_admission": "HOLD"}
    assert set(tokens) == {"test-token"}
    data = out.read_bytes()
    assert b"\r\n" not in data and json.loads(data)["log_read_attempts"] == 2


@pytest.mark.parametrize("args", [
    ["--max-runs", "0"], ["--max-runs", "1201"], ["--job-detail-limit", "0"],
    ["--max-runs", "5", "--job-detail-limit", "6"], ["--failure-log-limit", "-1"],
    ["--failure-log-limit", "41"],
])
def test_main_rejects_bounds(tmp_path, monkeypatch, args):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setattr(sys, "argv", ["collect.py", "--output", str(tmp_path / "o.json")] + args)
    with pytest.raises(ValueError, match="bounds"):
        mod.main()


def test_main_requires_token(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(sys, "argv", ["collect.py", "--output", str(tmp_path / "o.json")])
    with pytest.raises(ValueError, match="token required"):
        mod.main()


def test_dunder_main_without_token(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: pytest.fail("network"))
    monkeypatch.setattr(sys, "argv", [str(MOD_PATH), "--output", str(tmp_path / "o.json")])
    with pytest.raises(ValueError, match="token required"):
        runpy.run_path(str(MOD_PATH), run_name="__main__")
    assert not (tmp_path / "o.json").exists()
