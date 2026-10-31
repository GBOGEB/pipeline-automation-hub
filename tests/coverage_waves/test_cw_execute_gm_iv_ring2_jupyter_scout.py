"""Behavioural tests for mission-control/grand-missions/execute_gm_iv_ring2_jupyter_scout.py.

No Jupyter kernel is started: ExecutePreprocessor and subprocess are replaced
with deterministic fakes on the loaded module.
"""
import hashlib
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

nbformat = pytest.importorskip("nbformat")
pytest.importorskip("nbconvert")

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_DIR = REPO_ROOT / "mission-control" / "grand-missions"
MOD_PATH = MOD_DIR / "execute_gm_iv_ring2_jupyter_scout.py"


def _load():
    spec = importlib.util.spec_from_file_location("cw_execute_gm_iv_ring2_jupyter_scout", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = _load()

MC_SHA = "c" * 40
HEAD = "d" * 40


def test_canonical_outputs_normalises_output_types():
    nb = {
        "cells": [
            {"cell_type": "markdown", "source": "# title"},
            {
                "cell_type": "code",
                "execution_count": 1,
                "source": "print(1)",
                "outputs": [
                    {"output_type": "stream", "name": "stdout", "text": "1\n", "extra": "dropped"},
                    {"output_type": "execute_result", "data": {"text/plain": "2"}, "execution_count": 1},
                    {"output_type": "display_data"},
                    {"output_type": "error", "ename": "E", "evalue": "v", "traceback": ["tb"]},
                    {"output_type": "unknown_kind", "foo": 1},
                ],
            },
            {"cell_type": "code", "execution_count": None, "source": "x"},
        ]
    }
    out = m.canonical_outputs(nb)
    assert out["executed_code_cells"] == 1
    assert [c["index"] for c in out["cells"]] == [1, 2]
    outputs = out["cells"][0]["outputs"]
    assert outputs[0] == {"output_type": "stream", "name": "stdout", "text": "1\n"}
    assert outputs[1] == {"output_type": "execute_result", "data": {"text/plain": "2"}}
    assert outputs[2] == {"output_type": "display_data", "data": {}}
    assert outputs[3] == {"output_type": "error", "ename": "E", "evalue": "v", "traceback": ["tb"]}
    assert outputs[4] == {"output_type": "unknown_kind"}
    assert out["cells"][1] == {"index": 2, "source": "x", "outputs": []}
    payload = {"executed_code_cells": 1, "cells": out["cells"]}
    expected = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    assert out["digest_sha256"] == expected


def test_canonical_outputs_empty_notebook():
    out = m.canonical_outputs({})
    assert out["executed_code_cells"] == 0
    assert out["cells"] == []
    assert len(out["digest_sha256"]) == 64


class FakeEP:
    calls = []

    def __init__(self, timeout, kernel_name, allow_errors):
        FakeEP.calls.append({"timeout": timeout, "kernel_name": kernel_name, "allow_errors": allow_errors})

    def preprocess(self, nb, resources):
        FakeEP.calls[-1]["resources"] = resources
        for i, cell in enumerate(nb.cells):
            if cell.cell_type == "code":
                cell.execution_count = i + 1
                cell.outputs = [nbformat.v4.new_output("stream", name="stdout", text="ok\n")]
        return nb, resources


def _write_nb(path):
    nb = nbformat.v4.new_notebook()
    nb.cells = [nbformat.v4.new_markdown_cell("hi"), nbformat.v4.new_code_cell("print('ok')")]
    path.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(nb, str(path))
    return path


def test_execute_uses_notebook_directory(tmp_path, monkeypatch):
    FakeEP.calls = []
    monkeypatch.setattr(m, "ExecutePreprocessor", FakeEP)
    nb_path = _write_nb(tmp_path / "notebooks" / "a.ipynb")
    out = m.execute(nb_path)
    assert out["executed_code_cells"] == 1
    assert out["cells"][0]["outputs"] == [{"output_type": "stream", "name": "stdout", "text": "ok\n"}]
    call = FakeEP.calls[0]
    assert call["timeout"] == 240 and call["kernel_name"] == "python3" and call["allow_errors"] is False
    assert call["resources"] == {"metadata": {"path": str(nb_path.parent)}}


def test_version_installed_and_missing():
    assert m.version("nbformat") == nbformat.__version__
    assert m.version("cw-definitely-not-installed-pkg-xyz") == "NOT_INSTALLED"


def _fake_git(head=HEAD, statuses=("", "")):
    seq = list(statuses)
    calls = []

    def check_output(cmd, text=True):
        calls.append(cmd)
        if cmd[-2:] == ["rev-parse", "HEAD"]:
            return head + "\n"
        if cmd[-1] == "--porcelain":
            return seq.pop(0)
        raise AssertionError(cmd)

    return types.SimpleNamespace(check_output=check_output), calls


def _setup(tmp_path, monkeypatch, head=HEAD, statuses=("", ""), runs=None, mc_sha=MC_SHA):
    repo = tmp_path / "repo"
    _write_nb(repo / "notebooks" / "a.ipynb")
    out = tmp_path / "out" / "receipt.json"
    fake, calls = _fake_git(head, statuses)
    monkeypatch.setattr(m, "subprocess", fake)
    if mc_sha is None:
        monkeypatch.delenv("MISSIONCONTROL_SHA", raising=False)
    else:
        monkeypatch.setenv("MISSIONCONTROL_SHA", mc_sha)
    if runs is None:
        runs = [{"executed_code_cells": 2, "digest_sha256": "x" * 64, "cells": []}] * 2
    queue = list(runs)
    monkeypatch.setattr(m, "execute", lambda source: queue.pop(0))
    monkeypatch.setattr(sys, "argv", [
        "prog", "--repo", str(repo), "--notebook", "notebooks/a.ipynb",
        "--expected-sha", HEAD, "--out", str(out),
    ])
    return repo, out, calls


def test_main_pass_writes_receipt(tmp_path, monkeypatch, capsys):
    repo, out, calls = _setup(tmp_path, monkeypatch)
    assert m.main() == 0
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["missioncontrol_source_sha"] == MC_SHA
    assert receipt["candidate_sha"] == HEAD
    assert receipt["notebook_working_directory"] == "notebooks"
    nb_bytes = (repo / "notebooks" / "a.ipynb").read_bytes()
    assert receipt["source_file_sha256"] == hashlib.sha256(nb_bytes).hexdigest()
    assert receipt["run_2_digest_sha256"] == "x" * 64
    assert receipt["disposition"] == "SCOUT_RUNTIME_PASS_CANDIDATE_ONLY"
    assert receipt["environment"]["ipykernel"]
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "PASS_GM_IV_RING2_SCOUT_A"
    assert printed["executed_code_cells"] == 2
    assert calls[0] == ["git", "-C", str(repo.resolve()), "rev-parse", "HEAD"]
    assert len(calls) == 3


@pytest.mark.parametrize("sha", [None, "", "abc"])
def test_main_requires_40_char_missioncontrol_sha(tmp_path, monkeypatch, sha):
    _setup(tmp_path, monkeypatch, mc_sha=sha)
    with pytest.raises(SystemExit) as exc:
        m.main()
    assert str(exc.value) == "FAIL: exact 40-char MISSIONCONTROL_SHA required"


def test_main_head_mismatch(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, head="e" * 40)
    with pytest.raises(AssertionError) as exc:
        m.main()
    assert exc.value.args[0] == ("e" * 40, HEAD)


def test_main_missing_notebook(tmp_path, monkeypatch):
    repo, _, _ = _setup(tmp_path, monkeypatch)
    (repo / "notebooks" / "a.ipynb").unlink()
    with pytest.raises(AssertionError):
        m.main()


def test_main_dirty_before(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, statuses=(" M x\n", ""))
    with pytest.raises(AssertionError, match="candidate checkout must start clean"):
        m.main()


def test_main_dirty_after(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, statuses=("", "?? new\n"))
    with pytest.raises(AssertionError, match="candidate checkout must remain clean"):
        m.main()


def test_main_zero_cells(tmp_path, monkeypatch):
    runs = [{"executed_code_cells": 0, "digest_sha256": "x"}] * 2
    _setup(tmp_path, monkeypatch, runs=runs)
    with pytest.raises(AssertionError, match="scout requires >0 executed notebook cells"):
        m.main()


def test_main_cell_count_drift(tmp_path, monkeypatch):
    runs = [{"executed_code_cells": 2, "digest_sha256": "x"}, {"executed_code_cells": 3, "digest_sha256": "x"}]
    _setup(tmp_path, monkeypatch, runs=runs)
    with pytest.raises(AssertionError):
        m.main()


def test_main_digest_drift(tmp_path, monkeypatch):
    runs = [{"executed_code_cells": 2, "digest_sha256": "x"}, {"executed_code_cells": 2, "digest_sha256": "y"}]
    _, out, _ = _setup(tmp_path, monkeypatch, runs=runs)
    with pytest.raises(AssertionError, match="notebook output digest must repeat"):
        m.main()
    assert not out.exists()
