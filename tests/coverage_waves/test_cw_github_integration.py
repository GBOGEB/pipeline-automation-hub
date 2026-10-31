"""Behavioural tests for scripts/github_integration.py (subprocess fully faked; no git/gh)."""
from __future__ import annotations

import builtins
import functools
import importlib.util
import json
import subprocess
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "github_integration.py"


def _load():
    spec = importlib.util.spec_from_file_location("cw_github_integration", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = _load()


class FakeGit:
    """Records calls; returns scripted results; raises CalledProcessError for failing commands."""

    def __init__(self, status_rc=0, fail_on=(), outputs=None):
        self.calls = []
        self.status_rc = status_rc
        self.fail_on = set(fail_on)
        self.outputs = outputs or {}

    def run(self, cmd, **kwargs):
        self.calls.append((tuple(cmd), kwargs))
        sub = cmd[1]
        if sub in self.fail_on and kwargs.get("check"):
            raise subprocess.CalledProcessError(128, cmd)
        rc = self.status_rc if sub == "status" else 0
        return types.SimpleNamespace(returncode=rc, stdout=self.outputs.get(sub, ""), stderr="")

    def subs(self):
        return [c[0][1] for c in self.calls]


@pytest.fixture
def utf8_open(monkeypatch):
    # The module opens files without an explicit encoding; pin UTF-8 so emoji content
    # writes identically on every platform (see report: Windows cp1252 default).
    monkeypatch.setattr(m, "open", functools.partial(builtins.open, encoding="utf-8"), raising=False)


def _install(monkeypatch, fake):
    monkeypatch.setattr(m, "subprocess", types.SimpleNamespace(run=fake.run, CalledProcessError=subprocess.CalledProcessError))


def test_init_sets_paths_and_structure(tmp_path):
    gi = m.GitHubIntegrator(str(tmp_path))
    assert gi.project_root == tmp_path
    assert gi.outputs_dir == tmp_path / "app" / "public" / "outputs"
    assert set(gi.repo_structure) == {"master_input", "digital_twins", "metadata", "cross_references", "processing_logs"}


def test_initialize_existing_repo_does_not_init(tmp_path, monkeypatch, capsys):
    fake = FakeGit(status_rc=0)
    _install(monkeypatch, fake)
    assert m.GitHubIntegrator(str(tmp_path)).initialize_git_repo() is True
    assert fake.subs() == ["status"]
    assert fake.calls[0][1]["cwd"] == tmp_path
    assert "already exists" in capsys.readouterr().out


def test_initialize_new_repo_runs_init_and_config(tmp_path, monkeypatch):
    fake = FakeGit(status_rc=128)
    _install(monkeypatch, fake)
    assert m.GitHubIntegrator(str(tmp_path)).initialize_git_repo() is True
    assert fake.subs() == ["status", "init", "config", "config"]
    assert fake.calls[2][0][2:] == ("user.name", "Pipeline Automation Hub")


def test_initialize_failure_returns_false(tmp_path, monkeypatch, capsys):
    fake = FakeGit(status_rc=128, fail_on={"init"})
    _install(monkeypatch, fake)
    assert m.GitHubIntegrator(str(tmp_path)).initialize_git_repo() is False
    assert "Failed to initialize" in capsys.readouterr().out


def test_gitignore_and_readme_written(tmp_path, utf8_open):
    gi = m.GitHubIntegrator(str(tmp_path))
    gi.create_gitignore()
    gi.create_readme()
    ignore = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert "node_modules/" in ignore and "!app/public/outputs/metadata/" in ignore
    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert readme.startswith("# Pipeline Automation Hub")
    assert "## 📝 Change Log" in readme


def test_setup_directory_structure_is_idempotent(tmp_path):
    gi = m.GitHubIntegrator(str(tmp_path))
    gi.setup_directory_structure()
    gi.setup_directory_structure()
    for d in ("app/public/master_input", "app/public/outputs/processing_logs", "scripts"):
        assert (tmp_path / d).is_dir()


def test_manifest_skipped_without_summary(tmp_path, capsys):
    m.GitHubIntegrator(str(tmp_path)).create_processing_manifest()
    assert not (tmp_path / "PROCESSING_MANIFEST.json").exists()
    assert "Processing summary not found" in capsys.readouterr().out


def test_manifest_written_from_summary(tmp_path, utf8_open):
    gi = m.GitHubIntegrator(str(tmp_path))
    gi.outputs_dir.mkdir(parents=True)
    (gi.outputs_dir / "processing_summary.json").write_text('{"files": 3}', encoding="utf-8")
    gi.create_processing_manifest()
    manifest = json.loads((tmp_path / "PROCESSING_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["processing_summary"] == {"files": 3}
    assert manifest["pipeline_version"] == "1.0.0"
    assert manifest["repository_structure"] == gi.repo_structure
    assert manifest["git_integration"]["tracking_enabled"] is True


def test_manifest_bad_summary_is_reported_not_raised(tmp_path, capsys):
    gi = m.GitHubIntegrator(str(tmp_path))
    gi.outputs_dir.mkdir(parents=True)
    (gi.outputs_dir / "processing_summary.json").write_text("{not json", encoding="utf-8")
    gi.create_processing_manifest()
    assert "Failed to create manifest" in capsys.readouterr().out
    assert not (tmp_path / "PROCESSING_MANIFEST.json").exists()


def test_stage_and_commit_success(tmp_path, monkeypatch):
    fake = FakeGit()
    _install(monkeypatch, fake)
    assert m.GitHubIntegrator(str(tmp_path)).stage_and_commit_changes() is True
    assert fake.subs() == ["add", "commit"]
    commit_cmd = fake.calls[1][0]
    assert commit_cmd[2] == "-m"
    assert commit_cmd[3].startswith("Document Processing Pipeline - Complete Integration")


def test_stage_and_commit_failure(tmp_path, monkeypatch, capsys):
    fake = FakeGit(fail_on={"commit"})
    _install(monkeypatch, fake)
    assert m.GitHubIntegrator(str(tmp_path)).stage_and_commit_changes() is False
    assert "Failed to commit" in capsys.readouterr().out


def test_display_status_prints_git_facts(tmp_path, monkeypatch, capsys):
    fake = FakeGit(outputs={
        "branch": "main\n",
        "rev-list": "42\n",
        "log": "abc123 msg\n",
        "count-objects": "count: 1\n\nsize: 2 KiB\nin-pack: 9\n",
    })
    _install(monkeypatch, fake)
    m.GitHubIntegrator(str(tmp_path)).display_integration_status()
    out = capsys.readouterr().out
    assert "Current Branch: main" in out
    assert "Total Commits: 42" in out
    assert "Last Commit: abc123 msg" in out
    assert "   count: 1" in out
    assert "in-pack" not in out  # only the first three lines are considered; blank one skipped


def test_display_status_handles_git_failure(tmp_path, monkeypatch, capsys):
    _install(monkeypatch, FakeGit(fail_on={"rev-list"}))
    m.GitHubIntegrator(str(tmp_path)).display_integration_status()
    assert "Could not retrieve Git status" in capsys.readouterr().out


def test_integrate_success_end_to_end(tmp_path, monkeypatch, capsys, utf8_open):
    fake = FakeGit(status_rc=0)
    _install(monkeypatch, fake)
    assert m.GitHubIntegrator(str(tmp_path)).integrate() is True
    assert fake.subs() == ["status", "add", "commit", "branch", "rev-list", "log", "count-objects"]
    assert (tmp_path / "README.md").exists() and (tmp_path / ".gitignore").exists()
    assert "Completed Successfully" in capsys.readouterr().out


def test_integrate_init_failure_skips_commit(tmp_path, monkeypatch, capsys, utf8_open):
    fake = FakeGit(status_rc=1, fail_on={"init"})
    _install(monkeypatch, fake)
    assert m.GitHubIntegrator(str(tmp_path)).integrate() is False
    assert "commit" not in fake.subs() and "add" not in fake.subs()
    assert "encountered issues" in capsys.readouterr().out


def test_integrate_commit_failure(tmp_path, monkeypatch, capsys, utf8_open):
    fake = FakeGit(fail_on={"commit"})
    _install(monkeypatch, fake)
    assert m.GitHubIntegrator(str(tmp_path)).integrate() is False
    assert "branch" not in fake.subs()
    assert "encountered issues" in capsys.readouterr().out


def test_main_block_uses_hardcoded_root(monkeypatch):
    seen = []

    class Stub:
        def __init__(self, root):
            seen.append(root)

        def integrate(self):
            seen.append("integrate")
            return True

    # Run the module source as __main__, swapping in a stub class before the
    # entry-point block executes so nothing touches /home/ubuntu or git.
    src = MODULE_PATH.read_text(encoding="utf-8")
    head, tail = src.split('if __name__ == "__main__":', 1)
    ns = {"__name__": "__main__", "__file__": "unused_main_stub.py"}
    exec(compile(head, str(MODULE_PATH), "exec"), ns)
    ns["GitHubIntegrator"] = Stub
    pad = "\n" * head.count("\n")  # keep original line numbers for tracing
    exec(compile(pad + 'if __name__ == "__main__":' + tail, str(MODULE_PATH), "exec"), ns)
    assert seen == ["/home/ubuntu/pipeline_automation_app", "integrate"]


@pytest.mark.xfail(
    condition=__import__("locale").getpreferredencoding(False).lower().replace("-", "") != "utf8",
    strict=True,
    raises=UnicodeEncodeError,
    reason="production_defect: github_integration.py opens README/.gitignore/manifest with open(..., 'w') "
    "and no encoding; the emoji README content raises UnicodeEncodeError under a non-UTF-8 locale (Windows cp1252)",
)
def test_create_readme_writes_emoji_with_platform_default_encoding(tmp_path):
    # No utf8_open fixture here: this exercises the module's real open() call.
    gi = m.GitHubIntegrator(str(tmp_path))
    gi.create_readme()
    text = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "\U0001f91d Contributing" in text
