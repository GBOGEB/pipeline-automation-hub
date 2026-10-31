"""Behavioural tests for mission-control/runner-economics/validate_runner_fanout_mip.py.

Workflow files are synthesised under tmp_path (ROOT is monkeypatched); the committed
RUNNER_FANOUT_MIP_CONTROL_v1.json is used as the real control document.
"""
import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_PATH = REPO_ROOT / "mission-control" / "runner-economics" / "validate_runner_fanout_mip.py"


def _load():
    spec = importlib.util.spec_from_file_location("cw_validate_runner_fanout_mip", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fan = _load()
REAL_CONTROL = json.loads(fan.CONTROL.read_text(encoding="utf-8"))

EXCLUDE_OK = (
    "on:\n"
    "  pull_request:\n"
    "    paths:\n"
    "      - \"mission-control/grand-missions/**\"\n"
    "      - \"!mission-control/grand-missions/analytics/**\"\n"
    "  workflow_dispatch:\n"
    "jobs: {}\n"
)


def _specialist(paths):
    lines = "".join("      - \"" + p + "\"\n" for p in paths)
    return "on:\n  pull_request:\n    paths:\n" + lines + "  push:\n    branches: [master]\n"


FPC_GATE_OK = (
    "on:\n  pull_request_target:\n"
    "    types: [opened, synchronize, reopened, ready_for_review, edited]\n"
)
BROAD_OK = "on:\n  pull_request:\n    branches: [master]\npermissions:\n  contents: read\n"


def _tree(root, overrides=None):
    files = {p: EXCLUDE_OK for p in fan.EXCLUSION_FILES}
    for p, expected in fan.SPECIALIST_PATHS.items():
        files[p] = _specialist(expected)
    files[".github/workflows/first-pass-closure-gate.yml"] = FPC_GATE_OK
    files[".github/workflows/first-pass-closure-proof.yml"] = BROAD_OK
    files[".github/workflows/qps-triage-ultra-w0.yml"] = BROAD_OK
    files[".github/workflows/w3-16-m03-w0-recon.yml"] = BROAD_OK
    files.update(overrides or {})
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


def _run(tmp_path, monkeypatch, capsys, overrides=None, control=None):
    root = tmp_path / "repo"
    _tree(root, overrides)
    monkeypatch.setattr(fan, "ROOT", root)
    if control is not None:
        cp = tmp_path / "control.json"
        cp.write_text(json.dumps(control), encoding="utf-8")
        monkeypatch.setattr(fan, "CONTROL", cp)
    out = tmp_path / "receipt.json"
    monkeypatch.setattr(sys, "argv", ["v", "--source-sha", "cafe", "--out", str(out)])
    rc = fan.main()
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert json.loads(capsys.readouterr().out) == receipt
    return rc, receipt


def _failed(receipt):
    return [k for k, v in receipt["checks"].items() if not v]


def test_pull_request_block_absent():
    assert fan.pull_request_block("on:\n  push:\n") == ""


def test_pull_request_block_runs_to_end_without_terminator():
    content = "on:\n  pull_request:\n    paths: [a]\n"
    assert fan.pull_request_block(content) == "  pull_request:\n    paths: [a]\n"


def test_pull_request_block_stops_at_earliest_terminator():
    content = "on:\n  pull_request:\n    paths: [a]\n  push:\n  workflow_dispatch:\npermissions: {}\n"
    assert fan.pull_request_block(content) == "  pull_request:\n    paths: [a]\n"


def test_pull_request_block_ignores_pull_request_target():
    assert fan.pull_request_block(FPC_GATE_OK) == ""


def test_text_reads_relative_to_root(tmp_path, monkeypatch):
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    monkeypatch.setattr(fan, "ROOT", tmp_path)
    assert fan.text("a.txt") == "hello"


def test_real_control_with_conforming_workflows_passes(tmp_path, monkeypatch, capsys):
    rc, receipt = _run(tmp_path, monkeypatch, capsys)
    assert rc == 0
    assert receipt["result"] == "PASS_RUNNER_FANOUT_MIP_CONTROL"
    assert _failed(receipt) == []
    assert receipt["check_count"] == 1 + 10 + 4 + 4 + 2
    assert receipt["source_sha"] == "cafe"
    assert receipt["modeled_reduction_ratio"] == REAL_CONTROL["modeled_after_pure_gmia_analytics_change"][
        "modeled_reduction_ratio"]
    assert receipt["qps_923_compensation"] is False
    assert receipt["authority_transfer"] is False


@pytest.mark.parametrize("content", [
    "on:\n  pull_request:\n    paths:\n      - \"mission-control/grand-missions/**\"\n",
    "on:\n  pull_request:\n    paths:\n      - \"!mission-control/grand-missions/analytics/**\"\n",
    EXCLUDE_OK.replace("  workflow_dispatch:\n", "      - \"mission-control/grand-missions/analytics/x.json\"\n"),
    "on:\n  push:\n",
])
def test_exclusion_failures(tmp_path, monkeypatch, capsys, content):
    rc, receipt = _run(tmp_path, monkeypatch, capsys, overrides={fan.EXCLUSION_FILES[0]: content})
    assert rc == 1
    assert receipt["result"] == "FAIL_RUNNER_FANOUT_MIP_CONTROL"
    assert _failed(receipt) == ["exclude::gm-iv-pilot2-final-recensus.yml"]


def test_specialist_missing_path_fails(tmp_path, monkeypatch, capsys):
    path = ".github/workflows/w3-14-measured-pca.yml"
    partial = fan.SPECIALIST_PATHS[path][:1]
    rc, receipt = _run(tmp_path, monkeypatch, capsys, overrides={path: _specialist(partial)})
    assert rc == 1
    assert _failed(receipt) == ["scope::w3-14-measured-pca.yml"]


def test_specialist_without_paths_key_fails(tmp_path, monkeypatch, capsys):
    path = ".github/workflows/crew-telemetry-role-gap.yml"
    rc, receipt = _run(tmp_path, monkeypatch, capsys, overrides={path: BROAD_OK})
    assert _failed(receipt) == ["scope::crew-telemetry-role-gap.yml"]
    assert rc == 1


@pytest.mark.parametrize("path,content,check", [
    (".github/workflows/first-pass-closure-gate.yml", "on:\n  pull_request:\n", "preserve::first_pass_closure_global"),
    (".github/workflows/first-pass-closure-gate.yml", "on:\n  pull_request_target:\n    types: [opened]\n",
     "preserve::first_pass_closure_global"),
    (".github/workflows/first-pass-closure-proof.yml", _specialist(["x"]), "preserve::first_pass_closure_proof_broad"),
    (".github/workflows/first-pass-closure-proof.yml", "on:\n  push:\n", "preserve::first_pass_closure_proof_broad"),
    (".github/workflows/qps-triage-ultra-w0.yml", _specialist(["x"]), "preserve::qps_federation_broad"),
    (".github/workflows/w3-16-m03-w0-recon.yml", _specialist(["x"]), "preserve::w3_16_broad"),
])
def test_preserved_broad_controls(tmp_path, monkeypatch, capsys, path, content, check):
    rc, receipt = _run(tmp_path, monkeypatch, capsys, overrides={path: content})
    assert rc == 1
    assert _failed(receipt) == [check]


def _c(path, value):
    c = copy.deepcopy(REAL_CONTROL)
    node = c
    for k in path[:-1]:
        node = node[k]
    node[path[-1]] = value
    return c


@pytest.mark.parametrize("control,check", [
    (_c(["baseline", "pr"], 1), "01_baseline_bound"),
    (_c(["baseline", "head_sha"], "0"), "01_baseline_bound"),
    (_c(["baseline", "registered_workflow_count"], 18), "01_baseline_bound"),
    (_c(["baseline", "queue_exposure_ratio"], 0.5), "01_baseline_bound"),
    (_c(["modeled_after_pure_gmia_analytics_change", "expected_registered_workflows"], 7),
     "modeled_reduction_is_non_authoritative"),
    (_c(["modeled_after_pure_gmia_analytics_change", "modeled_reduction_count"], 12),
     "modeled_reduction_is_non_authoritative"),
    (_c(["modeled_after_pure_gmia_analytics_change", "classification"], "MEASURED"),
     "modeled_reduction_is_non_authoritative"),
    (_c(["mip", "Perpetuate", "postmerge_probe_required"], False), "modeled_reduction_is_non_authoritative"),
    (_c(["authority_transfer"], True), "non_compensation"),
    (_c(["formal_credit_delta"], 1), "non_compensation"),
    (_c(["engineering_credit_delta"], 1), "non_compensation"),
    (_c(["guards"], []), "non_compensation"),
])
def test_control_failures(tmp_path, monkeypatch, capsys, control, check):
    rc, receipt = _run(tmp_path, monkeypatch, capsys, control=control)
    assert rc == 1
    assert _failed(receipt) == [check]
    # Receipt constants are fixed regardless of the control content.
    assert receipt["baseline_registered_workflows"] == 19
    assert receipt["modeled_registered_workflows_after"] == 6


def test_missing_workflow_file_raises(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(fan, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["v", "--source-sha", "x", "--out", str(tmp_path / "r.json")])
    with pytest.raises(FileNotFoundError):
        fan.main()
    assert not (tmp_path / "r.json").exists()


def test_main_guard_exit_code(tmp_path, monkeypatch, capsys):
    # Execute the script body as __main__ with a synthetic ROOT by running the compiled
    # code in a namespace whose Path resolves ROOT under tmp_path.
    root = tmp_path / "a" / "b"
    _tree(root)
    script_dir = root / "mission-control" / "runner-economics"
    script_dir.mkdir(parents=True, exist_ok=True)
    (script_dir / "RUNNER_FANOUT_MIP_CONTROL_v1.json").write_text(json.dumps(REAL_CONTROL), encoding="utf-8")
    code = compile(MOD_PATH.read_text(encoding="utf-8"), str(MOD_PATH), "exec")
    ns = {"__name__": "__main__", "__file__": str(script_dir / "fanout_entry.py")}
    out = tmp_path / "r.json"
    monkeypatch.setattr(sys, "argv", ["v", "--source-sha", "s", "--out", str(out)])
    with pytest.raises(SystemExit) as exc:
        exec(code, ns)
    assert exc.value.code == 0
    assert json.loads(out.read_text(encoding="utf-8"))["result"] == "PASS_RUNNER_FANOUT_MIP_CONTROL"
