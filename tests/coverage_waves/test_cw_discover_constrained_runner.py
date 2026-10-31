"""Behavioural tests for crew/measured/frontier/temporal/discover_constrained_runner.py."""
from __future__ import annotations

import importlib.util
import io
import json
import sys
import urllib.error
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET = (
    REPO_ROOT / "mission-control" / "qps-triage-ultra" / "crew" / "measured" / "frontier" / "temporal"
    / "discover_constrained_runner.py"
)


@pytest.fixture
def mod():
    spec = importlib.util.spec_from_file_location("cw_discover_constrained_runner", TARGET)
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
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.delenv("MC_CONSTRAINED_RUNNER_LABELS_JSON", raising=False)
    gh_out = tmp_path / "gh_output.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(gh_out))
    out = tmp_path / "receipt.json"
    monkeypatch.setattr(sys, "argv", ["discover", "--out", str(out)])
    return {"out": out, "gh_out": gh_out}


def _install_net(mod, monkeypatch, value):
    calls = []

    def fake_urlopen(req, timeout=None):
        calls.append({"url": req.full_url, "headers": dict(req.header_items()), "timeout": timeout})
        if isinstance(value, BaseException):
            raise value
        return FakeResp(json.dumps(value).encode("utf-8"))

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    return calls


def _runner(rid, name, os_name, labels, status="online", busy=False):
    return {"id": rid, "name": name, "os": os_name, "status": status, "busy": busy,
            "labels": [{"name": x} for x in labels] + [{"id": 0}]}


def _read(env):
    return json.loads(env["out"].read_text(encoding="utf-8"))


def _gh_output(env):
    lines = env["gh_out"].read_text(encoding="utf-8").splitlines()
    return dict(line.split("=", 1) for line in lines)


@pytest.mark.parametrize(
    "raw,expected",
    [("linux", "linux"), (" Linux ", "linux"), ("Windows", "windows"), ("macOS", "macos"),
     ("osx", "macos"), ("AIX", None), (None, None), ("", None)],
)
def test_normalize_habitat(mod, raw, expected):
    assert mod.normalize_habitat(raw) == expected


def test_write_output_noop_without_github_output(mod, monkeypatch, tmp_path):
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    mod.write_output(True, ["a"], "linux")  # no file, no error
    assert list(tmp_path.iterdir()) == []


def test_write_output_appends(mod, monkeypatch, tmp_path):
    target = tmp_path / "o.txt"
    target.write_text("prior=1\n", encoding="utf-8")
    monkeypatch.setenv("GITHUB_OUTPUT", str(target))
    mod.write_output(True, ["self-hosted", "gpu"], "macos")
    assert target.read_text(encoding="utf-8") == (
        'prior=1\nenabled=true\nlabels=["self-hosted","gpu"]\nhabitat=macos\n'
    )


def test_get_json_sends_auth_headers(mod, monkeypatch):
    calls = _install_net(mod, monkeypatch, {"runners": []})
    assert mod.get_json("https://api.github.com/x", "test-token") == {"runners": []}
    assert calls[0]["headers"]["Authorization"] == "Bearer test-token"
    assert calls[0]["headers"]["X-github-api-version"] == "2022-11-28"
    assert calls[0]["timeout"] == 30


def test_no_declared_labels_defers(mod, env, monkeypatch, capsys):
    calls = _install_net(mod, monkeypatch, AssertionError("no network expected"))
    mod.main()
    receipt = _read(env)
    assert receipt["status"] == "DEFERRED_NO_DECLARED_CONSTRAINED_RUNNER"
    assert receipt["enabled"] is False
    assert receipt["authority_transfer"] is False
    assert calls == []
    assert _gh_output(env) == {"enabled": "false", "labels": '["self-hosted"]', "habitat": "linux"}
    printed = json.loads(capsys.readouterr().out)
    assert printed == {"status": "DEFERRED_NO_DECLARED_CONSTRAINED_RUNNER", "enabled": False,
                       "declared_labels": [], "habitat": None}


@pytest.mark.parametrize(
    "raw,error",
    [
        ("not json", "Expecting value"),
        ('{"a": 1}', "labels must be non-empty string list"),
        ("[]", "labels must be non-empty string list"),
        ('["self-hosted", ""]', "labels must be non-empty string list"),
        ('["self-hosted", 3]', "labels must be non-empty string list"),
        ('["gpu"]', "self-hosted label required"),
    ],
)
def test_invalid_declared_labels(mod, env, monkeypatch, raw, error):
    monkeypatch.setenv("MC_CONSTRAINED_RUNNER_LABELS_JSON", raw)
    mod.main()
    receipt = _read(env)
    assert receipt["status"] == "DEFERRED_INVALID_DECLARED_RUNNER_LABELS"
    assert error in receipt["validation_error"]
    assert _gh_output(env)["labels"] == '["self-hosted"]'


@pytest.mark.parametrize("token,repo", [("", "o/r"), ("test-token", "norepo")])
def test_missing_discovery_context(mod, env, monkeypatch, token, repo):
    monkeypatch.setenv("MC_CONSTRAINED_RUNNER_LABELS_JSON", '["self-hosted","gpu"]')
    monkeypatch.setenv("GITHUB_TOKEN", token)
    monkeypatch.setenv("GITHUB_REPOSITORY", repo)
    mod.main()
    receipt = _read(env)
    assert receipt["status"] == "DEFERRED_RUNNER_DISCOVERY_CONTEXT_UNAVAILABLE"
    assert receipt["declared_labels"] == ["self-hosted", "gpu"]
    assert _gh_output(env)["labels"] == '["self-hosted","gpu"]'


def test_ready_prefers_idle_runner(mod, env, monkeypatch):
    monkeypatch.setenv("MC_CONSTRAINED_RUNNER_LABELS_JSON", '["self-hosted","gpu"]')
    calls = _install_net(mod, monkeypatch, {"runners": [
        _runner(1, "a-busy", "Windows", ["self-hosted", "gpu"], busy=True),
        _runner(2, "z-idle", "Windows", ["self-hosted", "gpu", "x64"]),
        _runner(3, "b-off", "Linux", ["self-hosted", "gpu"], status="offline"),
        _runner(4, "c-nolabel", "Linux", ["self-hosted"]),
    ]})
    mod.main()
    assert calls[0]["url"] == "https://api.github.com/repos/o/r/actions/runners?per_page=100"
    receipt = _read(env)
    assert receipt["status"] == "READY_DECLARED_CONSTRAINED_RUNNER"
    assert receipt["enabled"] is True
    assert receipt["habitat"] == "windows"
    assert receipt["matched_runner"] == {"id": 2, "name": "z-idle", "os": "Windows", "status": "online",
                                         "busy": False, "labels": ["gpu", "self-hosted", "x64"]}
    assert _gh_output(env) == {"enabled": "true", "labels": '["self-hosted","gpu"]', "habitat": "windows"}


def test_unsupported_runner_os(mod, env, monkeypatch):
    monkeypatch.setenv("MC_CONSTRAINED_RUNNER_LABELS_JSON", '["self-hosted"]')
    _install_net(mod, monkeypatch, {"runners": [_runner(9, "aix", "AIX", ["self-hosted"])]})
    mod.main()
    receipt = _read(env)
    assert receipt["status"] == "DEFERRED_UNSUPPORTED_RUNNER_OS"
    assert receipt["enabled"] is False
    assert receipt["habitat"] is None
    assert receipt["matched_runner"]["name"] == "aix"
    assert _gh_output(env)["habitat"] == "linux"


def test_no_online_runner(mod, env, monkeypatch):
    monkeypatch.setenv("MC_CONSTRAINED_RUNNER_LABELS_JSON", '["self-hosted"]')
    _install_net(mod, monkeypatch, {})
    mod.main()
    assert _read(env)["status"] == "DEFERRED_DECLARED_RUNNER_NOT_ONLINE"


def test_http_error_status(mod, env, monkeypatch):
    monkeypatch.setenv("MC_CONSTRAINED_RUNNER_LABELS_JSON", '["self-hosted"]')
    err = urllib.error.HTTPError("https://api.github.com/x", 403, "Forbidden", hdrs=None, fp=io.BytesIO(b""))
    _install_net(mod, monkeypatch, err)
    mod.main()
    assert _read(env)["status"] == "DEFERRED_RUNNER_DISCOVERY_HTTP_403"


def test_network_error_status(mod, env, monkeypatch):
    monkeypatch.setenv("MC_CONSTRAINED_RUNNER_LABELS_JSON", '["self-hosted"]')
    _install_net(mod, monkeypatch, urllib.error.URLError("down"))
    mod.main()
    receipt = _read(env)
    assert receipt["status"] == "DEFERRED_RUNNER_DISCOVERY_NETWORK"
    assert receipt["enabled"] is False
