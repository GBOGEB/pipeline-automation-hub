"""Behavioural tests for crew/measured/frontier/pc3/collect_pc3_queue_telemetry.py."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET = (
    REPO_ROOT / "mission-control" / "qps-triage-ultra" / "crew" / "measured" / "frontier" / "pc3"
    / "collect_pc3_queue_telemetry.py"
)
HABITATS = ("linux", "windows", "macos")
LANES = ("baseline", "held")


@pytest.fixture
def mod():
    spec = importlib.util.spec_from_file_location("cw_collect_pc3_queue_telemetry", TARGET)
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


def _t(sec):
    return f"2026-01-01T00:{sec // 60:02d}:{sec % 60:02d}Z"


def _cells():
    jobs = []
    jid = 1
    for h in HABITATS:
        for lane in LANES:
            start = 20 if lane == "held" else 4
            jobs.append({"id": jid, "name": f"collect-{lane}-{h}", "status": "completed", "conclusion": "success",
                         "runner_name": f"r{jid}", "runner_group_name": "GitHub Actions",
                         "labels": [f"{h}-latest"], "started_at": _t(start), "completed_at": _t(start + 10)})
            jid += 1
    return jobs


@pytest.fixture
def harness(mod, monkeypatch, tmp_path):
    state = {"run": {"created_at": _t(0), "head_sha": "f" * 40}, "jobs": []}
    calls = []

    def fake_urlopen(req, timeout=None):
        calls.append({"url": req.full_url, "headers": dict(req.header_items()), "timeout": timeout})
        if req.full_url.endswith("/jobs?per_page=100"):
            return FakeResp(json.dumps({"jobs": state["jobs"]}).encode())
        return FakeResp(json.dumps(state["run"]).encode())

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("GITHUB_RUN_ID", "555")
    out = tmp_path / "telemetry.json"
    monkeypatch.setattr(sys, "argv", ["collect", "--out", str(out)])
    state["out"] = out
    state["calls"] = calls
    return state


def test_parse_ts(mod):
    assert mod.parse_ts(None) is None
    assert mod.parse_ts("") is None
    assert mod.parse_ts("2026-01-01T00:00:10Z").second == 10


@pytest.mark.parametrize("missing", ["GITHUB_TOKEN", "GITHUB_RUN_ID"])
def test_requires_environment(mod, harness, monkeypatch, missing):
    monkeypatch.delenv(missing)
    with pytest.raises(SystemExit, match="GITHUB_TOKEN/GITHUB_REPOSITORY/GITHUB_RUN_ID required"):
        mod.main()
    assert harness["calls"] == []


def test_requires_owner_slash_repo(mod, harness, monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "norepo")
    with pytest.raises(SystemExit):
        mod.main()


def test_full_matrix_with_gate(mod, harness, capsys):
    harness["jobs"] = _cells() + [
        {"id": 90, "name": "held-admission-gate", "started_at": _t(1), "completed_at": _t(12)},
        {"id": 91, "name": "summarize", "conclusion": "failure"},
        {"id": 92, "name": "collect-baseline-solaris", "conclusion": "failure"},
        {"id": 93, "name": "collect-other-linux", "conclusion": "failure"},
    ]
    mod.main()
    urls = [c["url"] for c in harness["calls"]]
    assert urls == ["https://api.github.com/repos/o/r/actions/runs/555",
                    "https://api.github.com/repos/o/r/actions/runs/555/jobs?per_page=100"]
    assert harness["calls"][0]["headers"]["Authorization"] == "Bearer test-token"
    doc = json.loads(harness["out"].read_text(encoding="utf-8"))
    assert doc["schema"] == "missioncontrol.crew_frontier_pc3_admission_telemetry.v2"
    assert doc["run_id"] == "555"
    assert doc["source_sha"] == "f" * 40
    assert doc["held_gate"] == {"job_id": 90, "started_at": _t(1), "completed_at": _t(12),
                                "designed_wait_seconds": 8.0}
    cells = {r["cell_id"]: r for r in doc["rows"]}
    assert sorted(cells) == sorted(f"{h}-{lane}" for h in HABITATS for lane in LANES)
    assert [r["cell_id"] for r in doc["rows"]] == sorted(cells)
    held = cells["linux-held"]
    assert held["admission_proxy_seconds_from_run_creation"] == 20.0
    assert held["post_gate_admission_seconds"] == 8.0
    assert held["job_execute_seconds"] == 10.0
    assert held["designed_gate_wait_seconds"] == 8.0
    base = cells["macos-baseline"]
    assert base["post_gate_admission_seconds"] is None
    assert base["designed_gate_wait_seconds"] == 0.0
    assert base["runner_labels"] == ["macos-latest"]
    summary = json.loads(capsys.readouterr().out)
    assert summary == {"status": "PASS_PC3_ADMISSION_TELEMETRY", "cells": 6, "source_sha": "f" * 40}


def test_without_gate_and_missing_timestamps(mod, harness):
    jobs = _cells()
    jobs[0]["started_at"] = None
    jobs[1]["completed_at"] = None
    jobs[2].pop("labels")
    harness["jobs"] = jobs
    harness["run"] = {"head_sha": None}  # created_at missing
    mod.main()
    doc = json.loads(harness["out"].read_text(encoding="utf-8"))
    assert doc["held_gate"]["job_id"] is None and doc["held_gate"]["completed_at"] is None
    for row in doc["rows"]:
        assert row["admission_proxy_seconds_from_run_creation"] is None
        assert row["post_gate_admission_seconds"] is None
    cells = {r["cell_id"]: r for r in doc["rows"]}
    assert cells["linux-baseline"]["job_execute_seconds"] is None
    assert cells["linux-held"]["job_execute_seconds"] is None
    assert cells["windows-baseline"]["runner_labels"] == []


def test_negative_delays_are_clamped(mod, harness):
    jobs = _cells()
    harness["run"]["created_at"] = _t(100)
    harness["jobs"] = jobs + [{"id": 90, "name": "held-admission-gate", "completed_at": _t(200)}]
    mod.main()
    doc = json.loads(harness["out"].read_text(encoding="utf-8"))
    for row in doc["rows"]:
        assert row["admission_proxy_seconds_from_run_creation"] == 0.0
    assert {r["cell_id"]: r["post_gate_admission_seconds"] for r in doc["rows"]}["windows-held"] == 0.0


def test_missing_cell_fails(mod, harness):
    harness["jobs"] = [j for j in _cells() if j["name"] != "collect-held-macos"]
    with pytest.raises(SystemExit, match=r"FAIL PC3 queue cells actual=.*expected=.*'macos-held'"):
        mod.main()
    assert not harness["out"].exists()


def test_unsuccessful_cell_fails(mod, harness):
    jobs = _cells()
    jobs[3]["conclusion"] = "cancelled"
    harness["jobs"] = jobs
    with pytest.raises(SystemExit, match="not successful"):
        mod.main()
    assert not harness["out"].exists()
