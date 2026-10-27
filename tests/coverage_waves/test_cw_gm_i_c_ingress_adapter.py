"""Behavioural tests for mission-control/grand-missions/gm_i_c_ingress_adapter.py."""
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "mission-control" / "grand-missions" / "gm_i_c_ingress_adapter.py"
SHA = "70964e5f1577231512f4104b26f5f6649ad8cb39"
OTHER = "1" * 40


def _load_module():
    spec = importlib.util.spec_from_file_location("cw_gm_i_c_ingress_adapter", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mod():
    return _load_module()


class FakeGit:
    """Deterministic stand-in for subprocess.run keyed by git subcommand."""

    def __init__(self, overrides=None):
        self.calls = []
        self.results = {
            "bundle verify": (0, "", ""),
            "bundle list-heads": (0, SHA + " refs/heads/main\n\n" + OTHER + " refs/heads/x\n", ""),
            "status": (0, "", ""),
            "fetch": (0, "", ""),
            "cat-file": (0, "", ""),
            "rev-parse": (0, SHA + "\n", ""),
            "bash": (0, "runner ok", ""),
        }
        self.results.update(overrides or {})

    def _key(self, cmd):
        if cmd[0] == "bash":
            return "bash"
        if cmd[1] == "bundle":
            return "bundle " + cmd[2]
        return cmd[1]

    def __call__(self, cmd, cwd=None, text=None, capture_output=None, check=None):
        self.calls.append({"cmd": list(cmd), "cwd": cwd, "check": check})
        rc, out, err = self.results[self._key(cmd)]
        if check and rc != 0:
            raise subprocess.CalledProcessError(rc, cmd, out, err)
        return subprocess.CompletedProcess(cmd, rc, out, err)


@pytest.fixture
def env(tmp_path):
    bundle = tmp_path / "src.bundle"
    bundle.write_bytes(b"bundle-bytes")
    ctl = tmp_path / "control"
    (ctl / ".git").mkdir(parents=True)
    receipt = tmp_path / "out" / "receipt.json"
    return {"bundle": bundle, "ctl": ctl, "receipt": receipt}


def _argv(monkeypatch, env, *extra):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "adapter",
            "--bundle",
            str(env["bundle"]),
            "--qps-control-checkout",
            str(env["ctl"]),
            "--receipt",
            str(env["receipt"]),
            *extra,
        ],
    )


def _receipt(env):
    return json.loads(env["receipt"].read_text(encoding="utf-8"))


def test_sha256_matches_hashlib(mod, tmp_path):
    p = tmp_path / "f.bin"
    p.write_bytes(b"x" * (1024 * 1024 + 7))
    assert mod.sha256(p) == hashlib.sha256(b"x" * (1024 * 1024 + 7)).hexdigest()


def test_run_delegates_to_subprocess(mod, monkeypatch):
    fake = FakeGit()
    monkeypatch.setattr(mod.subprocess, "run", fake)
    res = mod.run(["git", "status"], cwd=Path("."), check=False)
    assert res.returncode == 0
    assert fake.calls == [{"cmd": ["git", "status"], "cwd": Path("."), "check": False}]


def test_emit_creates_parents_and_sorted_json(mod, tmp_path):
    out = tmp_path / "a" / "b" / "r.json"
    mod.emit(out, {"b": 1, "a": 2})
    text = out.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert text.index('"a"') < text.index('"b"')


def test_fail_marks_defer(mod, tmp_path, capsys):
    out = tmp_path / "r.json"
    payload = {"authority_transfer": True}
    assert mod.fail(out, payload, "WHY", code=5) == 5
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data == {"state": "DEFER", "classification": "WHY", "authority_transfer": False, "formal_credit_delta": 0}
    assert "WHY" in capsys.readouterr().err


def test_bundle_missing(mod, monkeypatch, env):
    env["bundle"].unlink()
    fake = FakeGit()
    monkeypatch.setattr(mod.subprocess, "run", fake)
    _argv(monkeypatch, env)
    assert mod.main() == 2
    assert _receipt(env)["classification"] == "BUNDLE_NOT_FOUND"
    assert fake.calls == []


def test_control_not_git(mod, monkeypatch, env):
    (env["ctl"] / ".git").rmdir()
    monkeypatch.setattr(mod.subprocess, "run", FakeGit())
    _argv(monkeypatch, env)
    assert mod.main() == 2
    assert _receipt(env)["classification"] == "QPS_CONTROL_CHECKOUT_NOT_GIT_WORKTREE"


def test_bundle_verify_fail_tails_stderr(mod, monkeypatch, env):
    monkeypatch.setattr(mod.subprocess, "run", FakeGit({"bundle verify": (1, "", "e" * 5000)}))
    _argv(monkeypatch, env)
    assert mod.main() == 2
    r = _receipt(env)
    assert r["classification"] == "BUNDLE_VERIFY_FAIL"
    assert r["bundle_verify_rc"] == 1
    assert len(r["bundle_verify_stderr"]) == 4000
    assert r["bundle_sha256"] == hashlib.sha256(b"bundle-bytes").hexdigest()


def test_list_heads_fail(mod, monkeypatch, env):
    monkeypatch.setattr(mod.subprocess, "run", FakeGit({"bundle list-heads": (1, "", "x")}))
    _argv(monkeypatch, env)
    assert mod.main() == 2
    assert _receipt(env)["classification"] == "BUNDLE_LIST_HEADS_FAIL"


def test_expected_sha_not_advertised(mod, monkeypatch, env):
    monkeypatch.setattr(mod.subprocess, "run", FakeGit({"bundle list-heads": (0, OTHER + " refs/heads/x\n", "")}))
    _argv(monkeypatch, env)
    assert mod.main() == 2
    r = _receipt(env)
    assert r["classification"] == "EXPECTED_SHA_NOT_ADVERTISED_BY_BUNDLE"
    assert r["advertised_heads"] == [OTHER]


def test_status_fail(mod, monkeypatch, env):
    monkeypatch.setattr(mod.subprocess, "run", FakeGit({"status": (128, "", "")}))
    _argv(monkeypatch, env)
    assert mod.main() == 2
    assert _receipt(env)["classification"] == "QPS_CONTROL_STATUS_FAIL"


def test_control_dirty(mod, monkeypatch, env):
    monkeypatch.setattr(mod.subprocess, "run", FakeGit({"status": (0, " M a.py\n?? b\n", "")}))
    _argv(monkeypatch, env)
    assert mod.main() == 2
    r = _receipt(env)
    assert r["classification"] == "QPS_CONTROL_CHECKOUT_DIRTY"
    assert r["control_dirty_paths"] == [" M a.py", "?? b"]


def test_fetch_fail(mod, monkeypatch, env):
    fake = FakeGit({"fetch": (1, "", "boom")})
    monkeypatch.setattr(mod.subprocess, "run", fake)
    _argv(monkeypatch, env)
    assert mod.main() == 2
    r = _receipt(env)
    assert r["classification"] == "BUNDLE_IMPORT_FAIL"
    assert r["bundle_fetch_stderr"] == "boom"
    fetch = [c for c in fake.calls if c["cmd"][1] == "fetch"][0]
    assert fetch["cmd"][-1] == SHA + ":refs/gm-i-c/" + SHA
    assert fetch["cwd"] == env["ctl"]


def test_commit_absent_after_import(mod, monkeypatch, env):
    monkeypatch.setattr(mod.subprocess, "run", FakeGit({"cat-file": (1, "", "")}))
    _argv(monkeypatch, env)
    assert mod.main() == 2
    assert _receipt(env)["classification"] == "EXPECTED_COMMIT_NOT_PRESENT_AFTER_IMPORT"


def test_resolved_mismatch(mod, monkeypatch, env):
    monkeypatch.setattr(mod.subprocess, "run", FakeGit({"rev-parse": (0, OTHER + "\n", "")}))
    _argv(monkeypatch, env)
    assert mod.main() == 2
    r = _receipt(env)
    assert r["classification"] == "SOURCE_SHA_MISMATCH"
    assert r["resolved_source_sha"] == OTHER


def test_rev_parse_failure_raises(mod, monkeypatch, env):
    monkeypatch.setattr(mod.subprocess, "run", FakeGit({"rev-parse": (128, "", "bad")}))
    _argv(monkeypatch, env)
    with pytest.raises(subprocess.CalledProcessError):
        mod.main()


def test_ingress_pass_without_r3(mod, monkeypatch, env, capsys):
    fake = FakeGit()
    monkeypatch.setattr(mod.subprocess, "run", fake)
    _argv(monkeypatch, env)
    assert mod.main() == 0
    r = _receipt(env)
    assert r["state"] == "INGRESS_VERIFIED"
    assert r["classification"] == "REAL_GIT_OBJECT_INGRESS_PASS"
    assert r["r3_dispatched"] is False
    assert r["authority_transfer"] is False
    assert r["advertised_heads"] == [SHA, OTHER]
    assert not any(c["cmd"][0] == "bash" for c in fake.calls)
    assert json.loads(capsys.readouterr().out)["state"] == "INGRESS_VERIFIED"


def test_custom_expected_sha(mod, monkeypatch, env):
    monkeypatch.setattr(
        mod.subprocess,
        "run",
        FakeGit({"rev-parse": (0, OTHER, "")}),
    )
    _argv(monkeypatch, env, "--expected-sha", OTHER)
    assert mod.main() == 0
    assert _receipt(env)["expected_source_sha"] == OTHER


def test_execute_r3_runner_missing(mod, monkeypatch, env):
    monkeypatch.setattr(mod.subprocess, "run", FakeGit())
    _argv(monkeypatch, env, "--execute-r3")
    assert mod.main() == 2
    assert _receipt(env)["classification"] == "GOVERNED_R3_RUNNER_MISSING"


def _make_runner(env):
    runner = env["ctl"] / "scripts" / "run_r3_final_local_exact_worktree_v2.sh"
    runner.parent.mkdir(parents=True)
    runner.write_text("#!/bin/sh\n", encoding="utf-8")
    return runner


def test_execute_r3_pass(mod, monkeypatch, env):
    runner = _make_runner(env)
    fake = FakeGit()
    monkeypatch.setattr(mod.subprocess, "run", fake)
    _argv(monkeypatch, env, "--execute-r3")
    assert mod.main() == 0
    r = _receipt(env)
    assert r["state"] == "R3_DISPATCH_COMPLETED"
    assert r["classification"] == "REAL_GIT_OBJECT_INGRESS_AND_R3_DISPATCH_PASS"
    assert r["r3_dispatched"] is True
    assert r["r3_returncode"] == 0
    assert r["r3_stdout_tail"] == "runner ok"
    assert fake.calls[-1]["cmd"] == ["bash", str(runner)]


def test_execute_r3_nonzero(mod, monkeypatch, env):
    _make_runner(env)
    monkeypatch.setattr(mod.subprocess, "run", FakeGit({"bash": (7, "o" * 9000, "err")}))
    _argv(monkeypatch, env, "--execute-r3")
    assert mod.main() == 7
    r = _receipt(env)
    assert r["state"] == "DEFER"
    assert r["classification"] == "R3_EXECUTOR_RETURNED_NONZERO"
    assert len(r["r3_stdout_tail"]) == 8000
    assert r["r3_stderr_tail"] == "err"
