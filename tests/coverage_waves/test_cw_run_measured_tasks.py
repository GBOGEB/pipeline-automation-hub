"""Behavioural tests for crew/measured/run_measured_tasks.py.

The runner is a top-level script: all work happens at import time.  Each test
builds a synthetic crew tree in tmp_path, points the module's ``__file__`` at
it, swaps in fake ``subprocess``/``time`` modules for the duration of the
exec, and inspects the receipts written to the synthetic tree.
"""
import hashlib
import importlib.util
import itertools
import json
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MEASURED_DIR = REPO_ROOT / "mission-control" / "qps-triage-ultra" / "crew" / "measured"
MOD_PATH = MEASURED_DIR / "run_measured_tasks.py"

SHA = "a" * 40
CHECKLIST_SCHEMA = "missioncontrol.rex.reuse_checklist.v1"
_counter = itertools.count()


class FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _task(i, **over):
    task = {
        "assignment_id": f"A{i:03d}",
        "task_id": f"T{i:03d}",
        "crew_id": "U01",
        "crew_role_at_assignment": "VERIFIER",
        "task_type": "VERIFY",
        "competency_dimension": "evidence_provenance",
        "predeclared_task_level": 3,
        "command": ["python", "validate.py"],
        "applicable_rex_ids": ["REX-001", "REX-006"],
        "accept_condition": "exit_code == 0 and stdout contains PASS_OK",
        "promotion_allowed": False,
    }
    task.update(over)
    return task


def _build(tmp_path, tasks, history=None):
    crew = tmp_path / "crew"
    measured = crew / "measured"
    measured.mkdir(parents=True)
    (crew / "CREW_REGISTRY_v1.json").write_text(
        json.dumps({"crew": [{"crew_id": "U01"}, {"crew_id": "U02"}]}), encoding="utf-8")
    (crew / "COMPETENCY_MATRIX_v1.json").write_text(
        json.dumps({"dimensions": ["evidence_provenance", "runtime_execution"]}), encoding="utf-8")
    (measured / "REX_REUSE_CHECKLIST_v1.json").write_text(json.dumps({
        "schema": CHECKLIST_SCHEMA,
        "checklist": [{"rex_id": f"REX-00{i}"} for i in range(1, 8)],
    }), encoding="utf-8")
    (measured / "MEASURED_TASK_MANIFEST_v1.json").write_text(json.dumps({
        "mission_id": "MISSION-X", "tasks": tasks}), encoding="utf-8")
    if history is not None:
        (measured / "history").mkdir()
        (measured / "history" / "prior.json").write_text(json.dumps(history), encoding="utf-8")
    return measured


def _run(tmp_path, monkeypatch, tasks, *, procs=None, checkout=SHA, source=SHA,
         history=None, env=None):
    """Exec the runner against a synthetic tree; return (measured_dir, exit, calls)."""
    measured = _build(tmp_path, tasks, history)
    if source is None:
        monkeypatch.delenv("MC_SOURCE_SHA", raising=False)
    else:
        monkeypatch.setenv("MC_SOURCE_SHA", source)
    for var in ("GITHUB_RUN_ID", "GITHUB_JOB", "RUNNER_NAME"):
        monkeypatch.delenv(var, raising=False)
    for key, value in (env or {}).items():
        monkeypatch.setenv(key, value)
    calls = []
    procs = dict(procs or {})

    def run(cmd, text=None, capture_output=None):
        calls.append(list(cmd))
        return procs.get(tuple(cmd), FakeProc(0, "PASS_OK\n", ""))

    def check_output(cmd, text=None):
        assert cmd == ["git", "rev-parse", "HEAD"]
        return checkout + "\n"

    ticks = itertools.count()
    fake_sub = types.SimpleNamespace(run=run, check_output=check_output)
    fake_time = types.SimpleNamespace(monotonic=lambda: next(ticks) * 0.25)

    spec = importlib.util.spec_from_file_location(
        f"cw_run_measured_tasks_{next(_counter)}", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    mod.__file__ = str(measured / "measured_runner_copy.py")
    monkeypatch.setattr(sys, "path", [str(MEASURED_DIR)] + list(sys.path))
    saved = {k: sys.modules.get(k) for k in ("subprocess", "time")}
    sys.modules["subprocess"] = fake_sub
    sys.modules["time"] = fake_time
    code = None
    try:
        spec.loader.exec_module(mod)
    except SystemExit as exc:
        code = exc.code
    finally:
        for k, v in saved.items():
            sys.modules[k] = v
    return measured, code, calls


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_all_tasks_accepted_writes_receipts_exposure_and_summary(tmp_path, monkeypatch, capsys):
    tasks = [_task(1), _task(2, task_type="EXECUTE", crew_id="U02",
                             competency_dimension="runtime_execution")]
    measured, code, calls = _run(tmp_path, monkeypatch, tasks)
    assert code is None
    assert calls == [["python", "validate.py"], ["python", "validate.py"]]
    out = measured / "receipts"
    r1 = _load(out / "T001.json")
    assert r1["schema"] == "missioncontrol.mission_crew_task_runtime_receipt.v1"
    assert r1["disposition"] == "ACCEPT"
    assert r1["receipt_evidence_class"] == "MEASURED_RUNTIME_ACCEPTED"
    assert r1["exit_code"] == 0
    assert r1["steps_executed"] == 1
    assert r1["execute_seconds"] == 0.25
    assert r1["run_id"] == "LOCAL_UNBOUND" and r1["job_ref"] == "LOCAL_UNBOUND"
    assert r1["source_sha"] == SHA
    assert r1["rex_preflight"]["payload_allowed"] is True
    assert r1["rex_postflight"]["preventive_action_effective"] is True
    assert r1["rex_postflight"]["new_rex_signal"] is None
    assert r1["rex_postflight"]["recurrence_level"] is None
    assert r1["rex_postflight"]["ledger_update_required"] is False
    assert r1["command_sha256"] == hashlib.sha256(
        json.dumps(["python", "validate.py"], separators=(",", ":")).encode()).hexdigest()
    assert r1["stdout_sha256"] == hashlib.sha256(b"PASS_OK\n").hexdigest()
    assert r1["stderr_sha256"] == hashlib.sha256(b"").hexdigest()

    e2 = _load(out / "exposure" / "T002__EXPOSURE.json")
    assert e2["schema"] == "missioncontrol.crew_exposure_receipt.v1"
    assert e2["intervention_type"] == "RUNTIME_OPERATOR"
    assert e2["outcome"] == "ACCEPT"
    assert e2["crew_id"] == "U02"
    assert e2["runtime_execute_seconds"] == 0.25
    assert e2["pca_eligible"] is False and e2["mission_performance_eligible"] is True
    assert e2["exposure_seconds"] >= e2["active_seconds"] >= 0

    summary = _load(out / "RUN_SUMMARY.json")
    assert summary["task_count"] == 2
    assert summary["accepted"] == 2 and summary["rejected"] == 0
    assert summary["preflight_blocked"] == 0
    assert summary["crew_exposure_receipts"] == 2
    assert summary["crew_runtime_execute_seconds_total"] == 0.5
    assert summary["checkout_sha"] == SHA
    printed = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert printed[0]["task_id"] == "T001" and printed[0]["disposition"] == "ACCEPT"
    assert printed[-1]["schema"] == "missioncontrol.measured_task_run_summary.v1"


def test_env_bindings_are_recorded(tmp_path, monkeypatch):
    env = {"GITHUB_RUN_ID": "999", "GITHUB_JOB": "job-1", "RUNNER_NAME": "runner-7"}
    measured, code, _ = _run(tmp_path, monkeypatch, [_task(1, task_type="REX")], env=env)
    assert code is None
    r = _load(measured / "receipts" / "T001.json")
    assert (r["run_id"], r["job_ref"], r["runner_ref"]) == ("999", "job-1", "runner-7")
    e = _load(measured / "receipts" / "exposure" / "T001__EXPOSURE.json")
    assert e["intervention_type"] == "GOVERNANCE"
    assert e["run_id"] == "999"


@pytest.mark.parametrize("proc,expected_exit", [
    (FakeProc(1, "PASS_OK", "boom"), 1),
    (FakeProc(0, "something else", ""), 0),
    (FakeProc(0, None, None), 0),
])
def test_failed_or_unmatched_command_is_rejected_and_exits_1(tmp_path, monkeypatch, proc, expected_exit):
    task = _task(1, task_type="MEASURE")
    measured, code, _ = _run(tmp_path, monkeypatch, [task],
                             procs={("python", "validate.py"): proc})
    assert code == 1
    r = _load(measured / "receipts" / "T001.json")
    assert r["disposition"] == "REJECT"
    assert r["receipt_evidence_class"] == "MEASURED_RUNTIME_REJECTED"
    assert r["exit_code"] == expected_exit
    assert r["rex_postflight"]["preventive_action_effective"] is None
    e = _load(measured / "receipts" / "exposure" / "T001__EXPOSURE.json")
    assert e["intervention_type"] == "ANALYSIS" and e["outcome"] == "REJECT"
    summary = _load(measured / "receipts" / "RUN_SUMMARY.json")
    assert summary["rejected"] == 1 and summary["accepted"] == 0


def test_yaml_mutation_blocks_preflight_without_running(tmp_path, monkeypatch):
    tasks = [
        _task(1, command=["python", "fix.py", "config.YAML"], applicable_rex_ids=["REX-003"]),
        _task(2, command=["python", "fix.py", "other.yml"], applicable_rex_ids=["REX-003"]),
    ]
    measured, code, calls = _run(tmp_path, monkeypatch, tasks)
    assert code == 1
    assert calls == []
    r1 = _load(measured / "receipts" / "T001.json")
    assert r1["steps_executed"] == 0 and r1["exit_code"] is None
    assert r1["execute_seconds"] == 0.0
    assert r1["rex_preflight"]["blocking_rex_ids"] == ["REX-003"]
    assert r1["rex_postflight"]["new_rex_signal"] == ["REX-003"]
    assert r1["rex_postflight"]["recurrence_level"] == "NEW"
    assert r1["rex_postflight"]["ledger_update_required"] is True
    # The second task sees the in-memory history updated by the first.
    r2 = _load(measured / "receipts" / "T002.json")
    assert r2["rex_postflight"]["recurrence_level"] == "RECURRING"
    assert r2["rex_postflight"]["new_rex_signal"] is None
    summary = _load(measured / "receipts" / "RUN_SUMMARY.json")
    assert summary["preflight_blocked"] == 2


def test_unregistered_rex_evaluator_with_prior_history_is_persistent(tmp_path, monkeypatch):
    history = {"rex_postflight": {"rex_ids_observed": ["REX-007", "REX-007"]}}
    measured, code, _ = _run(tmp_path, monkeypatch,
                             [_task(1, applicable_rex_ids=["REX-007"])], history=history)
    assert code == 1
    r = _load(measured / "receipts" / "T001.json")
    assert r["rex_postflight"]["recurrence_level"] == "PERSISTENT"


def test_missing_accept_prefix_uses_whole_condition(tmp_path, monkeypatch):
    task = _task(1, accept_condition="MARKER", applicable_rex_ids=[])
    measured, code, _ = _run(tmp_path, monkeypatch, [task],
                             procs={("python", "validate.py"): FakeProc(0, "has MARKER", "")})
    assert code is None
    r = _load(measured / "receipts" / "T001.json")
    assert r["disposition"] == "ACCEPT"
    assert r["rex_postflight"]["preventive_action_effective"] is None


@pytest.mark.parametrize("source,checkout,msg", [
    (None, SHA, "exact 40-char MC_SOURCE_SHA required"),
    ("abc", SHA, "exact 40-char MC_SOURCE_SHA required"),
    (SHA, "b" * 40, "!= checkout HEAD"),
])
def test_sha_guards(tmp_path, monkeypatch, source, checkout, msg):
    measured, code, calls = _run(tmp_path, monkeypatch, [_task(1)], source=source, checkout=checkout)
    assert msg in str(code)
    assert calls == []
    assert not (measured / "receipts" / "RUN_SUMMARY.json").exists()


@pytest.mark.parametrize("tasks,msg", [
    ([_task(1), _task(2, assignment_id="A001")], "duplicate assignment_id/task_id"),
    ([_task(1), _task(2, task_id="T001")], "duplicate assignment_id/task_id"),
    ([_task(1, crew_id="U99")], "unknown crew U99"),
    ([_task(1, competency_dimension="nope")], "unknown competency nope"),
    ([_task(1, applicable_rex_ids=["REX-999"])], "unknown REX ids ['REX-999']"),
    ([_task(1, promotion_allowed=True)], "may not promote competence"),
    ([{k: v for k, v in _task(1).items() if k != "promotion_allowed"}], "may not promote competence"),
    ([_task(1, task_type="DANCE")], "no exposure intervention mapping for DANCE"),
])
def test_manifest_validation_errors(tmp_path, monkeypatch, tasks, msg):
    _, code, _ = _run(tmp_path, monkeypatch, tasks)
    assert isinstance(code, str) and msg in code


def test_preflight_requires_accept_condition_binding(tmp_path, monkeypatch):
    task = _task(1, applicable_rex_ids=["REX-005"], accept_condition="")
    measured, code, calls = _run(tmp_path, monkeypatch, [task])
    assert code == 1 and calls == []
    r = _load(measured / "receipts" / "T001.json")
    assert r["rex_preflight"]["blocking_rex_ids"] == ["REX-005"]
