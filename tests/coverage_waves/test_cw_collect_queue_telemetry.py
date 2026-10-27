"""Behavioural tests for crew/measured/frontier/collect_queue_telemetry.py."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET = (
    REPO_ROOT / "mission-control" / "qps-triage-ultra" / "crew" / "measured" / "frontier"
    / "collect_queue_telemetry.py"
)


@pytest.fixture
def mod():
    spec = importlib.util.spec_from_file_location("cw_collect_queue_telemetry", TARGET)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResp:
    def __init__(self, body: bytes):
        self.body = body

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def harness(mod, monkeypatch, tmp_path):
    state = {"run": {"created_at": "2026-01-01T00:00:00Z", "head_sha": "e" * 40}, "jobs": [], "calls": []}

    def fake_urlopen(req, timeout=None):
        state["calls"].append({"url": req.full_url, "headers": dict(req.header_items()), "timeout": timeout})
        payload = {"jobs": state["jobs"]} if "/jobs" in req.full_url else state["run"]
        return FakeResp(json.dumps(payload).encode())

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("GITHUB_RUN_ID", "77")
    state["out"] = tmp_path / "q.json"
    monkeypatch.setattr(sys, "argv", ["collect", "--out", str(state["out"])])
    return state


def test_parse_ts(mod):
    assert mod.parse_ts("") is None
    assert mod.parse_ts("2026-01-01T00:00:05Z").second == 5


@pytest.mark.parametrize("var,value", [("GITHUB_TOKEN", ""), ("GITHUB_REPOSITORY", "bad"), ("GITHUB_RUN_ID", "")])
def test_requires_environment(mod, harness, monkeypatch, var, value):
    monkeypatch.setenv(var, value)
    with pytest.raises(SystemExit, match="FAIL: GITHUB_TOKEN/GITHUB_REPOSITORY/GITHUB_RUN_ID required"):
        mod.main()
    assert harness["calls"] == []


def test_collects_linux_and_windows_rows(mod, harness, capsys):
    harness["jobs"] = [
        {"id": 3, "name": "Probe (Windows)", "status": "completed", "conclusion": "success",
         "started_at": "2026-01-01T00:00:30Z", "completed_at": "2026-01-01T00:01:00Z"},
        {"id": 1, "name": "probe-linux", "status": "completed", "conclusion": "success",
         "started_at": "2026-01-01T00:00:10Z", "completed_at": "2026-01-01T00:00:15Z"},
        {"id": None, "name": "linux-pending", "status": "queued", "conclusion": None,
         "started_at": None, "completed_at": None},
        {"id": 9, "name": "macos-probe"},
        {"id": 10},
    ]
    mod.main()
    urls = [c["url"] for c in harness["calls"]]
    assert urls == ["https://api.github.com/repos/o/r/actions/runs/77",
                    "https://api.github.com/repos/o/r/actions/runs/77/jobs?per_page=100"]
    assert all(c["headers"]["Authorization"] == "Bearer test-token" for c in harness["calls"])
    assert harness["calls"][0]["timeout"] == 30
    doc = json.loads(harness["out"].read_text(encoding="utf-8"))
    assert doc["schema"] == "missioncontrol.crew_frontier_queue_telemetry.v1"
    assert doc["run_id"] == "77"
    assert doc["source_sha"] == "e" * 40
    assert [(r["habitat"], r["job_id"]) for r in doc["rows"]] == [("linux", None), ("linux", 1), ("windows", 3)]
    pending, linux, windows = doc["rows"]
    assert pending["queue_seconds_from_run_creation"] is None and pending["job_execute_seconds"] is None
    assert linux["queue_seconds_from_run_creation"] == 10.0 and linux["job_execute_seconds"] == 5.0
    assert windows["queue_seconds_from_run_creation"] == 30.0 and windows["job_execute_seconds"] == 30.0
    assert json.loads(capsys.readouterr().out) == {
        "status": "PASS_FRONTIER_QUEUE_TELEMETRY", "rows": 3, "source_sha": "e" * 40}


def test_missing_run_created_and_clamping(mod, harness):
    harness["jobs"] = [
        {"id": 1, "name": "linux", "started_at": "2026-01-01T00:00:10Z", "completed_at": "2026-01-01T00:00:05Z"},
    ]
    harness["run"] = {}
    mod.main()
    doc = json.loads(harness["out"].read_text(encoding="utf-8"))
    row = doc["rows"][0]
    assert row["queue_seconds_from_run_creation"] is None
    assert row["job_execute_seconds"] == 0.0  # completed before started is clamped to zero
    assert doc["source_sha"] is None


def test_no_jobs_key(mod, harness):
    harness["jobs"] = []
    mod.main()
    assert json.loads(harness["out"].read_text(encoding="utf-8"))["rows"] == []
