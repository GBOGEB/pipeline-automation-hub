"""Behavioural tests for crew/measured/frontier/run_frontier_tasks.py.

A synthetic repo tree is built in tmp_path and the module's ``__file__`` is
pointed at it before exec, so every path constant (ROOT/REPO/CREW) resolves
inside tmp_path.  ``subprocess`` and ``time`` are replaced on the loaded module
with deterministic fakes.
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
MOD_PATH = MEASURED_DIR / "frontier" / "run_frontier_tasks.py"

SHA_EVEN = "a" * 39 + "2"   # source parity 0
SHA_ODD = "a" * 39 + "3"    # source parity 1
_counter = itertools.count()


class FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _task(tid, kind="analytics_sweep", pair_id=None, variant=None, **over):
    task = {
        "assignment_id": "A-" + tid,
        "task_id": tid,
        "pair_id": pair_id,
        "variant": variant,
        "allocation_strategy": "ALLOC_SINGLE_CELL",
        "crew_combination": ["U01"],
        "primary_crew_id": "U01",
        "competency_dimension": "runtime_execution",
        "predeclared_task_level": 3,
        "workload": {"kind": kind, "iterations": 2, "workers": 1},
        "applicable_rex_ids": ["REX-002", "REX-005", "REX-006"],
    }
    task.update(over)
    return task


def _manifest(tasks, **over):
    m = {"mission_id": "FRONTIER-X", "objective": "o", "comparison_rule": "c",
         "promotion_allowed": False, "tasks": tasks}
    m.update(over)
    return m


@pytest.fixture
def env(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    crew = repo / "mission-control" / "qps-triage-ultra" / "crew"
    frontier = crew / "measured" / "frontier"
    frontier.mkdir(parents=True)
    (repo / "mission-control" / "qps-triage-ultra" / "architecture.yaml").write_text(
        "name: x\nrex: REX-001\n", encoding="utf-8")
    (crew / "CREW_REGISTRY_v1.json").write_text(
        json.dumps({"crew": [{"crew_id": "U01"}, {"crew_id": "U02"}]}), encoding="utf-8")
    (crew / "COMPETENCY_MATRIX_v1.json").write_text(
        json.dumps({"dimensions": ["runtime_execution"]}), encoding="utf-8")
    (crew / "ROLE_DEVELOPMENT_POLICY_v1.json").write_text(json.dumps({"p": 1}), encoding="utf-8")
    (crew / "receipts").mkdir()
    (crew / "receipts" / "skip.json").write_text("not json", encoding="utf-8")
    (crew / "measured" / "REX_REUSE_CHECKLIST_v1.json").write_text(json.dumps({
        "schema": "missioncontrol.rex.reuse_checklist.v1",
        "checklist": [{"rex_id": f"REX-00{i}"} for i in range(1, 8)],
    }), encoding="utf-8")
    (crew / "measured" / "notes.md").write_bytes(b"REX-002 REX-002 REX-006")
    (crew / "measured" / "bin.py").write_bytes(b"\xff\xfe\x00bad")
    (frontier / "FRONTIER_TASK_MANIFEST_v1.json").write_text(
        json.dumps(_manifest([_task("T1")])), encoding="utf-8")

    monkeypatch.setattr(sys, "path", [str(MEASURED_DIR)] + list(sys.path))
    spec = importlib.util.spec_from_file_location(f"cw_run_frontier_{next(_counter)}", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    mod.__file__ = str(frontier / "frontier_runner_copy.py")
    spec.loader.exec_module(mod)

    state = types.SimpleNamespace(mod=mod, repo=repo, crew=crew, frontier=frontier,
                                  calls=[], procs={}, checkout=SHA_EVEN)

    def run(cmd, cwd=None, text=None, capture_output=None):
        state.calls.append((tuple(cmd), cwd))
        return state.procs.get(Path(cmd[-1]).name, FakeProc(0, '{"status": "PASS"}\n'))

    def check_output(cmd, cwd=None, text=None):
        assert cmd == ["git", "rev-parse", "HEAD"]
        return state.checkout + "\n"

    ticks = itertools.count()
    monkeypatch.setattr(mod, "subprocess", types.SimpleNamespace(run=run, check_output=check_output))
    monkeypatch.setattr(mod, "time", types.SimpleNamespace(perf_counter=lambda: next(ticks) * 0.5))
    for var in ("GITHUB_RUN_ID", "RUNNER_NAME", "RUNNER_OS", "RUNNER_ARCH"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("MC_SOURCE_SHA", SHA_EVEN)
    return state


def _main(state, monkeypatch, tmp_path, habitat="linux"):
    out = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", ["run", "--habitat", habitat, "--out", str(out)])
    code = None
    try:
        state.mod.main()
    except SystemExit as exc:
        code = exc.code
    return out, code


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


# --- module-level path wiring -------------------------------------------------

def test_paths_resolve_inside_synthetic_tree(env):
    assert env.mod.REPO == env.repo.resolve()
    assert env.mod.CREW == env.crew.resolve()
    assert env.mod.CREW_IDS == {"U01", "U02"}
    assert "REX-007" in env.mod.REX_IDS


# --- workloads ------------------------------------------------------------------

def test_json_census_skips_receipts_and_is_worker_invariant(env):
    files = env.mod.json_files()
    assert all("receipts" not in p.parts for p in files)
    assert len(files) == 5
    d1, u1 = env.mod.json_census(2, 1)
    d2, u2 = env.mod.json_census(1, 3)
    assert d1 == d2 and len(d1) == 64
    assert (u1, u2) == (10, 5)


def test_validation_bundle_markers_and_threads(env):
    env.procs["validate_crew_telemetry.py"] = FakeProc(0, "")
    env.procs["validate_rex_reuse.py"] = FakeProc(0, "line\nPASS_REX\n")
    d1, u1 = env.mod.validation_bundle(1, 1)
    expected = "\n".join(sorted([
        "validate_crew_system.py|PASS", "validate_crew_telemetry.py|PASS_EMPTY",
        "validate_rex_reuse.py|PASS_REX", "validate_evidence_returns.py|PASS"])).encode()
    assert d1 == hashlib.sha256(expected).hexdigest()
    assert u1 == 4
    assert all(cwd == env.mod.REPO for _, cwd in env.calls)
    d2, u2 = env.mod.validation_bundle(2, 4)
    assert d2 == d1 and u2 == 8


def test_validation_bundle_failure_raises(env):
    env.procs["validate_crew_system.py"] = FakeProc(2, "out", "err")
    with pytest.raises(RuntimeError, match="validation failed"):
        env.mod.validation_bundle(1, 1)


def test_analytics_sweep_is_worker_invariant(env):
    expected = sum(((i * 2654435761) ^ (i >> 3)) % 1000003 for i in range(100))
    d1, u1 = env.mod.analytics_sweep(100, 1)
    d3, u3 = env.mod.analytics_sweep(100, 3)
    assert d1 == d3 == hashlib.sha256(str(expected).encode()).hexdigest()
    assert u1 == u3 == 100


def test_rex_surface_scan_counts_and_skips_undecodable(env):
    digest, units = env.mod.rex_surface_scan(2, 1)
    files = [p for p in (env.repo / "mission-control").rglob("*")
             if p.is_file() and p.suffix.lower() in {".json", ".yaml", ".yml", ".md", ".py"}]
    assert units == len(files) * 2
    counts = {f"REX-{i:03d}": 0 for i in range(1, 7)}
    for p in files:
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for rid in counts:
            counts[rid] += text.count(rid)
    assert counts["REX-002"] >= 2
    assert digest == hashlib.sha256(
        json.dumps(counts, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def test_topology_crosswalk(env):
    digest, units = env.mod.topology_crosswalk(3, 1)
    assert units == 12 and len(digest) == 64


def test_topology_crosswalk_missing_target(env):
    (env.crew / "ROLE_DEVELOPMENT_POLICY_v1.json").unlink()
    with pytest.raises(FileNotFoundError):
        env.mod.topology_crosswalk(1, 1)


# --- counterbalancing -----------------------------------------------------------

@pytest.mark.parametrize("sha,habitat,phase,direction", [
    (SHA_EVEN, "linux", 0, "A_THEN_B"),
    (SHA_EVEN, "windows", 1, "B_THEN_A"),
    (SHA_ODD, "linux", 1, "B_THEN_A"),
    (SHA_ODD, "windows", 0, "A_THEN_B"),
])
def test_counterbalanced_tasks_phase(env, sha, habitat, phase, direction):
    tasks = [_task("U1"), _task("PA", pair_id="P", variant="A"), _task("PB", pair_id="P", variant="B")]
    ordered, meta, got_phase = env.mod.counterbalanced_tasks(tasks, habitat, sha)
    assert got_phase == phase
    assert ordered[-1]["task_id"] == "U1"
    assert [t["task_id"] for t in ordered[:2]] == (["PA", "PB"] if direction == "A_THEN_B" else ["PB", "PA"])
    assert meta[ordered[0]["task_id"]]["pair_position"] == 1
    assert meta[ordered[1]["task_id"]]["pair_direction"] == direction
    assert meta["U1"] == {"pair_position": None, "pair_direction": None,
                          "counterbalance_phase": phase,
                          "counterbalance_basis": "SOURCE_SHA_PARITY_XOR_HABITAT"}


@pytest.mark.parametrize("members", [
    [("X", "A")],
    [("X", "A"), ("Y", "A")],
    [("X", "A"), ("Y", "B"), ("Z", "B")],
])
def test_counterbalanced_tasks_requires_ab_pair(env, members):
    tasks = [_task(tid, pair_id="P", variant=v) for tid, v in members]
    with pytest.raises(SystemExit, match="requires A/B pair: P"):
        env.mod.counterbalanced_tasks(tasks, "linux", SHA_EVEN)


# --- main -----------------------------------------------------------------------

def test_main_accepts_all_workloads_and_writes_receipts(env, monkeypatch, tmp_path, capsys):
    tasks = [
        _task("F1", "json_census", pair_id="P", variant="A"),
        _task("F2", "json_census", pair_id="P", variant="B", crew_combination=["U01", "U02"]),
        _task("F3", "validation_bundle"),
        _task("F4", "rex_surface_scan"),
        _task("F5", "topology_crosswalk"),
    ]
    monkeypatch.setattr(env.mod, "MANIFEST", _manifest(tasks))
    monkeypatch.setenv("GITHUB_RUN_ID", "77")
    monkeypatch.setenv("RUNNER_ARCH", "X64")
    out, code = _main(env, monkeypatch, tmp_path, habitat="windows")
    assert code is None
    summary = _load(out / "windows__RUN_SUMMARY.json")
    assert summary["schema"] == "missioncontrol.crew_frontier_run_summary.v1"
    assert summary["task_count"] == 5 and summary["accepted"] == 5 and summary["rejected"] == 0
    assert summary["pair_members"] == 2
    assert summary["counterbalance_phase"] == 1
    assert summary["run_id"] == "77"
    r2 = _load(out / "windows__F2.json")
    assert r2["execution_order"]["index"] == 1  # B runs first in phase 1
    assert r2["execution_order"]["pair_direction"] == "B_THEN_A"
    assert r2["habitat"] == {"id": "windows", "runner_os": "windows",
                             "runner_arch": "X64", "runner_name": "LOCAL_UNBOUND"}
    assert r2["execute_seconds"] == 0.5
    assert r2["steps_executed"] == 1
    assert r2["semantic_digest"] and r2["workload_units"] > 0
    assert r2["rex_postflight"]["preventive_action_effective"] is True
    r5 = _load(out / "windows__F5.json")
    assert r5["workload_units"] == 8 and r5["error"] is None
    lines = [json.loads(x) for x in capsys.readouterr().out.splitlines() if x.strip()]
    assert [x.get("task_id") for x in lines[:5]] == ["F2", "F1", "F3", "F4", "F5"]


def test_main_workload_exception_and_preflight_block_reject(env, monkeypatch, tmp_path):
    tasks = [
        _task("BAD", "validation_bundle"),
        _task("UNK", "nonexistent_kind"),
        _task("UNK2", "nonexistent_kind"),
    ]
    env.procs["validate_crew_system.py"] = FakeProc(1, "", "nope")
    monkeypatch.setattr(env.mod, "MANIFEST", _manifest(tasks))
    out, code = _main(env, monkeypatch, tmp_path)
    assert code == 1
    bad = _load(out / "linux__BAD.json")
    assert bad["disposition"] == "REJECT"
    assert "validation failed" in bad["error"]
    assert bad["semantic_digest"] is None and bad["workload_units"] == 0
    assert bad["steps_executed"] == 1
    assert bad["rex_postflight"]["preventive_action_effective"] is None
    unk = _load(out / "linux__UNK.json")
    assert unk["error"] == "REX_PREFLIGHT_BLOCKED:REX-002"
    assert unk["steps_executed"] == 0 and unk["execute_seconds"] == 0.0
    assert unk["rex_postflight"]["recurrence_level"] == "NEW"
    unk2 = _load(out / "linux__UNK2.json")
    assert unk2["rex_postflight"]["recurrence_level"] == "RECURRING"
    summary = _load(out / "linux__RUN_SUMMARY.json")
    assert summary["rejected"] == 3 and summary["preflight_blocked"] == 2


def test_main_proof_gate_unbound_blocks(env, monkeypatch, tmp_path):
    monkeypatch.setattr(env.mod, "MANIFEST", _manifest([_task("T1")], promotion_allowed=True))
    out, code = _main(env, monkeypatch, tmp_path)
    assert code == 1
    r = _load(out / "linux__T1.json")
    assert r["rex_preflight"]["blocking_rex_ids"] == ["REX-005"]


def test_main_history_marks_regression_after_preventive_control(env, monkeypatch, tmp_path):
    hist = env.crew / "measured" / "history"
    hist.mkdir()
    (hist / "h.json").write_text(json.dumps({"rex_postflight": {
        "rex_ids_observed": ["REX-002"], "preventive_action_effective": True}}), encoding="utf-8")
    monkeypatch.setattr(env.mod, "MANIFEST", _manifest([_task("T1", "bogus")]))
    out, code = _main(env, monkeypatch, tmp_path)
    assert code == 1
    assert _load(out / "linux__T1.json")["rex_postflight"]["recurrence_level"] == "REGRESSION"


@pytest.mark.parametrize("source,checkout", [
    ("", SHA_EVEN), ("abc", "abc"), (SHA_EVEN, SHA_ODD),
])
def test_main_sha_guard(env, monkeypatch, tmp_path, source, checkout):
    monkeypatch.setenv("MC_SOURCE_SHA", source)
    env.checkout = checkout
    out, code = _main(env, monkeypatch, tmp_path)
    assert "FAIL exact SHA" in code
    assert not (out / "linux__RUN_SUMMARY.json").exists()


@pytest.mark.parametrize("tasks,msg", [
    ([_task("D"), _task("D")], "FAIL duplicate task"),
    ([_task("C", primary_crew_id="U99")], "FAIL unknown crew in C"),
    ([_task("C", crew_combination=["U01", "U99"])], "FAIL unknown crew in C"),
    ([_task("C", competency_dimension="zzz")], "FAIL unknown competency zzz"),
    ([_task("C", applicable_rex_ids=["REX-404"])], "FAIL unknown REX in C"),
])
def test_main_manifest_validation(env, monkeypatch, tmp_path, tasks, msg):
    monkeypatch.setattr(env.mod, "MANIFEST", _manifest(tasks))
    _, code = _main(env, monkeypatch, tmp_path)
    assert code == msg


def test_main_rejects_unknown_habitat(env, monkeypatch, tmp_path):
    with pytest.raises(SystemExit) as exc:
        monkeypatch.setattr(sys, "argv", ["run", "--habitat", "macos", "--out", str(tmp_path / "o")])
        env.mod.main()
    assert exc.value.code == 2

