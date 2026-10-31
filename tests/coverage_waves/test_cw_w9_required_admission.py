"""Coverage wave w9: required_gate/admission.py runtime resolution, scope and CLI (offline)."""
import importlib.util
import json
import runpy
import subprocess
import sys
import types
from pathlib import Path

import pytest

pytest.importorskip("yaml")

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_DIR = REPO_ROOT / "mission-control" / "gogreen" / "required_gate"
MOD_PATH = MOD_DIR / "admission.py"
_spec = importlib.util.spec_from_file_location("cw_w9_required_admission_mod", MOD_PATH)
a = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(a)

REF = "actions/setup-node/sub@v4"


def fake_git(monkeypatch, tmp_path, fetch_rc=0, shows=None):
    """shows: {action file name: (returncode, stdout)}; unknown names -> rc 128."""
    calls = []
    shows = shows or {}

    def run(cmd, capture_output=True, text=True, timeout=None):
        calls.append(cmd)
        verb = cmd[3]
        if verb == "init":
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")
        if verb == "fetch":
            return types.SimpleNamespace(returncode=fetch_rc, stdout="", stderr="")
        name = cmd[4].rsplit("/", 1)[-1].split(":")[-1]
        rc, out = shows.get(name, (128, ""))
        return types.SimpleNamespace(returncode=rc, stdout=out, stderr="")
    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(a.tempfile, "tempdir", str(tmp_path))
    return calls


def test_resolve_runtime_rejects_bad_ref():
    assert a.resolve_runtime("not-a-ref") == "UNRESOLVED"
    assert a.resolve_runtime("o/r@../x") == "UNRESOLVED"


def test_resolve_runtime_fetch_failure(monkeypatch, tmp_path):
    calls = fake_git(monkeypatch, tmp_path, fetch_rc=1)
    assert a.resolve_runtime(REF) == "UNRESOLVED"
    assert [c[3] for c in calls] == ["init", "fetch"]
    assert "https://github.com/actions/setup-node" in calls[1]


def test_resolve_runtime_falls_back_to_action_yaml(monkeypatch, tmp_path):
    calls = fake_git(monkeypatch, tmp_path, shows={"action.yaml": (0, "runs:\n  using: 'node20'\n")})
    assert a.resolve_runtime(REF) == "node20"
    assert calls[2][4] == "FETCH_HEAD:sub/action.yml"
    assert calls[3][4] == "FETCH_HEAD:sub/action.yaml"


def test_resolve_runtime_root_action_without_using(monkeypatch, tmp_path):
    calls = fake_git(monkeypatch, tmp_path, shows={"action.yml": (0, "name: x\n")})
    assert a.resolve_runtime("actions/checkout@v4") == "UNRESOLVED"
    assert calls[2][4] == "FETCH_HEAD:action.yml"


def test_resolve_runtime_bad_yaml_and_missing(monkeypatch, tmp_path):
    fake_git(monkeypatch, tmp_path, shows={"action.yml": (0, "runs: [unclosed\n")})
    assert a.resolve_runtime(REF) == "UNRESOLVED"
    fake_git(monkeypatch, tmp_path, shows={})
    assert a.resolve_runtime(REF) == "UNRESOLVED"


def test_scope_unparseable(tmp_path):
    p = tmp_path / "w.yml"
    p.write_text("- a\n- b\n", encoding="utf-8", newline="\n")
    t = a.g.triggers(p)
    assert a.scope(t, ".github/workflows/w.yml", "- a\n") == ("UNPARSEABLE", [])


def mini(root):
    w = root / ".github" / "workflows"
    w.mkdir(parents=True)
    (w / "a.yml").write_text("name: A\non:\n  pull_request: {}\njobs:\n  j:\n    steps:\n      - uses: actions/checkout@v4\n",
                             encoding="utf-8", newline="\n")
    (w / "b.yaml").write_text("name: B\non:\n  pull_request: {}\njobs:\n  j:\n    steps:\n      - uses: o/r@v1\n",
                              encoding="utf-8", newline="\n")
    (w / "list.yml").write_text("- not\n- a mapping\n", encoding="utf-8", newline="\n")
    return root


def test_markdown_without_drift(tmp_path):
    doc = a.build(mini(tmp_path), None, None, None, {})
    md = a.markdown(doc, None)
    assert "Drift vs committed ledger" not in md
    assert "| EXCLUDED | UNPARSEABLE | 1 |" in md


def test_main_resolves_and_writes(tmp_path, monkeypatch, capsys):
    root = mini(tmp_path / "repo")
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps({"entries": [], "runtimes": {"actions/checkout@v4": "node24"}}),
                      encoding="utf-8", newline="\n")
    seen = []
    monkeypatch.setattr(a, "resolve_runtime", lambda ref: seen.append(ref) or "node20")
    out, summ = tmp_path / "out.json", tmp_path / "summary.md"
    doc = a.main(["--root", str(root), "--ledger", str(ledger), "--out", str(out), "--summary", str(summ),
                  "--resolve-runtimes"])
    assert seen == ["o/r@v1"]
    assert doc["runtimes"] == {"actions/checkout@v4": "node24", "o/r@v1": "node20"}
    assert json.loads(out.read_text(encoding="utf-8"))["schema"] == a.g.ADMISSION_SCHEMA
    assert "Drift vs committed ledger" in summ.read_text(encoding="utf-8")
    printed = json.loads(capsys.readouterr().out)
    assert printed["node20_workflows"] == 1
    assert set(printed["drift"]) == {"promoted", "demotion_candidates", "new_files", "removed_files"}


def test_main_without_previous_ledger(tmp_path, capsys):
    root = mini(tmp_path)
    doc = a.main(["--root", str(root)])
    assert doc["generated_from"]["previous_ledger_sha256"] is None
    assert json.loads(capsys.readouterr().out)["counts"]


def test_dunder_main(tmp_path, monkeypatch, capsys):
    root = mini(tmp_path)
    monkeypatch.setattr(sys, "argv", ["admission.py", "--root", str(root)])
    runpy.run_path(str(MOD_PATH), run_name="__main__")
    assert '"coverage"' in capsys.readouterr().out
