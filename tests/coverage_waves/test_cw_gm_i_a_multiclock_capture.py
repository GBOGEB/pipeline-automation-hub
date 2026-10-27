"""Behavioural tests for mission-control/grand-missions/analytics/gm_i_a_multiclock_capture.py."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET = REPO_ROOT / "mission-control" / "grand-missions" / "analytics" / "gm_i_a_multiclock_capture.py"


@pytest.fixture
def mod():
    spec = importlib.util.spec_from_file_location("cw_gm_i_a_multiclock_capture", TARGET)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResp:
    def __init__(self, body: bytes):
        self.body = body

    def read(self, *args):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _install(mod, monkeypatch, route):
    calls = []

    def fake_urlopen(req, timeout=None):
        calls.append({"url": req.full_url, "headers": dict(req.header_items()), "timeout": timeout})
        return FakeResp(json.dumps(route(req.full_url)).encode("utf-8"))

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    return calls


def _job(jid, name, created, started, completed, steps=(), runner_id=7, **over):
    j = {"id": jid, "name": name, "status": "completed", "conclusion": "success", "runner_id": runner_id,
         "runner_name": f"runner-{jid}", "created_at": created, "started_at": started,
         "completed_at": completed, "steps": list(steps)}
    j.update(over)
    return j


def _step(name, started, completed, conclusion="success"):
    return {"name": name, "started_at": started, "completed_at": completed, "conclusion": conclusion}


def test_ts_and_seconds(mod):
    assert mod.seconds("2026-01-01T00:00:00Z", "2026-01-01T00:01:30Z") == 90
    assert mod.ts("2026-01-01T00:00:00+00:00") == mod.ts("2026-01-01T00:00:00Z")


def test_fetch_with_and_without_token(mod, monkeypatch):
    calls = _install(mod, monkeypatch, lambda url: {"ok": url})
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    assert mod.fetch("https://api.github.com/a") == {"ok": "https://api.github.com/a"}
    monkeypatch.delenv("GITHUB_TOKEN")
    mod.fetch("https://api.github.com/b")
    assert calls[0]["headers"]["Authorization"] == "Bearer test-token"
    assert calls[0]["headers"]["User-agent"] == "GBOGEB-MissionControl-MultiClock"
    assert calls[0]["timeout"] == 30
    assert "Authorization" not in calls[1]["headers"]


def test_run_artifacts_projection(mod, monkeypatch):
    calls = _install(mod, monkeypatch, lambda url: {"artifacts": [
        {"id": 1, "name": "a", "digest": "sha256:x", "expired": False, "size_in_bytes": 9},
        {"id": 2, "name": "b"},
    ]})
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert mod.run_artifacts("o/r", 5) == [
        {"id": 1, "name": "a", "digest": "sha256:x", "expired": False},
        {"id": 2, "name": "b", "digest": None, "expired": None},
    ]
    assert calls[0]["url"] == "https://api.github.com/repos/o/r/actions/runs/5/artifacts?per_page=100"


@pytest.mark.parametrize(
    "jobs,message",
    [
        ([], "expected one job J in o/r run 3, got 0"),
        ([{"name": "J"}, {"name": "J"}], "got 2"),
        ([{"name": "J", "status": "completed", "conclusion": "failure"}], "job not successful"),
        ([{"name": "J", "status": "in_progress", "conclusion": None}], "job not successful"),
        ([{"name": "J", "status": "completed", "conclusion": "success"}], "lacks runner identity"),
    ],
)
def test_job_rejects_bad_jobs(mod, monkeypatch, jobs, message):
    _install(mod, monkeypatch, lambda url: {"jobs": jobs})
    with pytest.raises(SystemExit, match=message):
        mod.job("o/r", 3, "J")


def test_job_returns_unique_successful_job(mod, monkeypatch):
    j = _job(1, "J", "t", "t", "t")
    _install(mod, monkeypatch, lambda url: {"jobs": [j, _job(2, "K", "t", "t", "t")]})
    assert mod.job("o/r", 3, "J") == j


def test_step_seconds(mod):
    j = {"steps": [_step("S", "2026-01-01T00:00:00Z", "2026-01-01T00:00:12Z"),
                   _step("F", "2026-01-01T00:00:00Z", "2026-01-01T00:00:12Z", conclusion="failure")]}
    assert mod.step_seconds(j, "S") == 12
    with pytest.raises(SystemExit, match="step not successful/unique: F"):
        mod.step_seconds(j, "F")
    with pytest.raises(SystemExit, match="step not successful/unique: M"):
        mod.step_seconds(j, "M")
    with pytest.raises(SystemExit):
        mod.step_seconds({}, "S")


def test_main_end_to_end(mod, monkeypatch, tmp_path, capsys):
    t = "2026-01-01T00:00:{:02d}Z".format
    heavy = _job(11, "HEAVY producer - exact-source wheel", t(0), t(5), t(50), steps=[
        _step("Checkout exact source head", t(5), t(8)),
        _step("Build exact-source wheel once", t(8), t(40)),
    ])
    fast = _job(12, "FAST consumer - artifact-only helium probe", t(1), t(10), t(30))
    dow = _job(21, "consume-provider-attestation", t(2), t(4), t(14))
    keb = _job(31, "consume-provider-attestation", t(3), t(9), t(29))
    runs = {
        "GBOGEB/CoolProp": ({"id": 100, "run_attempt": 2, "head_sha": "c" * 40}, [heavy, fast]),
        "GBOGEB/ABACUS": ({"id": 200, "head_sha": "a" * 40}, [dow]),
        "GBOGEB/CODEX": ({"id": 300, "head_sha": "d" * 40}, [keb]),
    }

    def route(url):
        for repo, (run, jobs) in runs.items():
            base = f"https://api.github.com/repos/{repo}/actions/runs/{run['id']}"
            if url == base:
                return run
            if url == base + "/jobs?per_page=100":
                return {"jobs": jobs}
            if url == base + "/artifacts?per_page=100":
                return {"artifacts": [{"id": run["id"] + 1, "name": f"art-{repo}"}]}
        raise AssertionError(url)

    calls = _install(mod, monkeypatch, route)
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    out = tmp_path / "row.json"
    monkeypatch.setattr(sys, "argv", ["cap", "--pulse-id", "P1", "--coolprop-run", "100", "--abacus-run", "200",
                                      "--codex-run", "300", "--out", str(out)])
    assert mod.main() == 0
    row = json.loads(out.read_text(encoding="utf-8"))
    assert row["pulse_id"] == "P1"
    assert row["provider_source_sha"] == "c" * 40
    assert row["evidence_class"] == "MEASURED"
    assert (row["heavy_queue_seconds"], row["heavy_checkout_seconds"], row["heavy_build_seconds"]) == (5, 3, 32)
    assert (row["fast_queue_seconds"], row["fast_execute_seconds"]) == (9, 20)
    assert (row["dow_queue_seconds"], row["dow_execute_seconds"]) == (2, 10)
    assert (row["keb_queue_seconds"], row["keb_execute_seconds"]) == (6, 20)
    ev = row["evidence"]
    assert ev["heavy"]["run_attempt"] == 2 and ev["dow"]["run_attempt"] is None
    assert ev["keb"]["repo"] == "GBOGEB/CODEX"
    assert ev["fast"]["artifacts"] == [{"id": 101, "name": "art-GBOGEB/CoolProp", "digest": None, "expired": None}]
    assert ev["heavy"]["runner_id"] == 7
    assert all(c["headers"]["Authorization"] == "Bearer test-token" for c in calls)
    assert json.loads(capsys.readouterr().out) == row
