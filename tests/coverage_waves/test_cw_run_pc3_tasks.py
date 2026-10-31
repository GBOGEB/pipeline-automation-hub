"""Behavioural tests for crew/measured/frontier/pc3/run_pc3_tasks.py.

A synthetic repo tree is built in tmp_path and the module's ``__file__`` is
pointed at it before exec, so ROOT/FRONTIER/MEASURED/CREW/REPO all resolve
inside tmp_path.  ``subprocess`` (run/check_output/Popen) and ``time``
(perf_counter/sleep) are replaced on the loaded module with fakes, so no
contention burners, validators or sleeps really happen.
"""
import hashlib
import importlib.util
import itertools
import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MEASURED_DIR = REPO_ROOT / "mission-control" / "qps-triage-ultra" / "crew" / "measured"
MOD_PATH = MEASURED_DIR / "frontier" / "pc3" / "run_pc3_tasks.py"

SHA = "c" * 40
_counter = itertools.count()


class FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class FakeBurner:
    def __init__(self, argv, hang):
        self.argv = argv
        self.hang = hang
        self.killed = False
        self.waited = None

    def wait(self, timeout=None):
        self.waited = timeout
        if self.hang:
            raise subprocess.TimeoutExpired(self.argv, timeout)
        return 0

    def kill(self):
        self.killed = True


def _task(tid, kind="analytics_sweep", rp=None, pair_id=None, variant=None, **over):
    task = {
        "assignment_id": "A-" + tid,
        "task_id": tid,
        "pair_id": pair_id,
        "variant": variant,
        "task_class": "short_compute",
        "allocation_strategy": "ALLOC_SINGLE_CELL",
        "primary_crew_id": "U01",
        "crew_combination": ["U01"],
        "competency_dimension": "analysis",
        "predeclared_task_level": 3,
        "workload": {"kind": kind, "iterations": 3, "workers": 1},
        "resource_profile": rp if rp is not None else {
            "contention_processes": 0, "cache_reuse": False,
            "artifact_reuse": False, "human_dependency_wait_seconds": 0.0},
        "applicable_rex_ids": ["REX-005", "REX-006"],
    }
    task.update(over)
    return task


def _manifest(tasks, **over):
    m = {"mission_id": "PC3-X", "hypothesis": "h", "comparison_contract": {"x": 1},
         "promotion_allowed": False, "tasks": tasks}
    m.update(over)
    return m


@pytest.fixture
def env(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    crew = repo / "mission-control" / "qps-triage-ultra" / "crew"
    pc3 = crew / "measured" / "frontier" / "pc3"
    pc3.mkdir(parents=True)
    (crew / "CREW_REGISTRY_v1.json").write_text(
        json.dumps({"crew": [{"crew_id": "U01"}, {"crew_id": "U02"}]}), encoding="utf-8")
    (crew / "COMPETENCY_MATRIX_v1.json").write_text(
        json.dumps({"dimensions": ["analysis"]}), encoding="utf-8")
    (crew / "measured" / "REX_REUSE_CHECKLIST_v1.json").write_text(json.dumps({
        "schema": "missioncontrol.rex.reuse_checklist.v1",
        "checklist": [{"rex_id": f"REX-00{i}"} for i in range(1, 8)],
    }), encoding="utf-8")
    (crew / "notes.md").write_text("REX-001 REX-005 REX-005", encoding="utf-8")
    (crew / "blob.json").write_bytes(b"\xff\xfeREX")
    (pc3 / "FRONTIER_TASK_MANIFEST_v2.json").write_text(
        json.dumps(_manifest([_task("T1")])), encoding="utf-8")

    monkeypatch.setattr(sys, "path", [str(MEASURED_DIR)] + list(sys.path))
    spec = importlib.util.spec_from_file_location(f"cw_run_pc3_{next(_counter)}", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    mod.__file__ = str(pc3 / "pc3_runner_copy.py")
    spec.loader.exec_module(mod)

    state = types.SimpleNamespace(mod=mod, repo=repo, crew=crew, pc3=pc3, calls=[], procs={},
                                  popens=[], sleeps=[], checkout=SHA, hang=False)

    def run(cmd, cwd=None, text=None, capture_output=None):
        state.calls.append((tuple(cmd), cwd))
        return state.procs.get(Path(cmd[-1]).name, FakeProc(0, '{"status": "PASS"}\n'))

    def check_output(cmd, cwd=None, text=None):
        assert cmd == ["git", "rev-parse", "HEAD"]
        return state.checkout + "\n"

    def popen(argv, stdout=None, stderr=None):
        b = FakeBurner(argv, state.hang)
        state.popens.append(b)
        return b

    fake_sub = types.SimpleNamespace(run=run, check_output=check_output, Popen=popen,
                                     DEVNULL=subprocess.DEVNULL,
                                     TimeoutExpired=subprocess.TimeoutExpired)
    ticks = itertools.count()
    fake_time = types.SimpleNamespace(perf_counter=lambda: next(ticks) * 0.5,
                                      sleep=state.sleeps.append)
    monkeypatch.setattr(mod, "subprocess", fake_sub)
    monkeypatch.setattr(mod, "time", fake_time)
    for var in ("GITHUB_RUN_ID", "RUNNER_NAME", "RUNNER_OS", "RUNNER_ARCH",
                "RUNNER_ENVIRONMENT", "MC_REUSE_ARTIFACT"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path / "runner_temp"))
    monkeypatch.setenv("MC_SOURCE_SHA", SHA)
    return state


def _main(state, monkeypatch, tmp_path, habitat="linux", lane="baseline"):
    out = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", ["run", "--habitat", habitat, "--lane", lane, "--out", str(out)])
    code = None
    try:
        state.mod.main()
    except SystemExit as exc:
        code = exc.code
    return out, code


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


# --- path wiring --------------------------------------------------------------

def test_paths_resolve_inside_synthetic_tree(env):
    assert env.mod.REPO == env.repo.resolve()
    assert env.mod.CREW == env.crew.resolve()
    assert env.mod.DIMS == {"analysis"}


# --- workloads ----------------------------------------------------------------

def test_analytics_sweep_worker_invariant_and_clamps_workers(env):
    expected = hashlib.sha256(str(sum(((i * 2654435761) ^ (i >> 3)) % 1000003
                                      for i in range(50))).encode()).hexdigest()
    assert env.mod.analytics_sweep(50, 1) == (expected, 50)
    assert env.mod.analytics_sweep(50, 4) == (expected, 50)
    assert env.mod.analytics_sweep(50, 0) == (expected, 50)  # clamped to 1


def test_validation_bundle_markers_threads_and_failure(env):
    env.procs["validate_crew_telemetry.py"] = FakeProc(0, "  \n")
    env.procs["validate_rex_reuse.py"] = FakeProc(0, "PASS_REX\n")
    d1, u1 = env.mod.validation_bundle(1, 1)
    raw = "\n".join(sorted(["validate_crew_system.py|PASS", "validate_crew_telemetry.py|PASS_EMPTY",
                            "validate_rex_reuse.py|PASS_REX",
                            "validate_evidence_returns.py|PASS"])).encode()
    assert (d1, u1) == (hashlib.sha256(raw).hexdigest(), 4)
    assert env.mod.validation_bundle(2, 2) == (d1, 8)
    assert {cwd for _, cwd in env.calls} == {env.mod.REPO}
    env.procs["validate_evidence_returns.py"] = FakeProc(3, "o", "e")
    with pytest.raises(RuntimeError, match="validation failed"):
        env.mod.validation_bundle(1, 1)


def test_rex_surface_scan_counts(env):
    digest, units = env.mod.rex_surface_scan(2, 1)
    files = [p for p in (env.repo / "mission-control").rglob("*")
             if p.is_file() and p.suffix.lower() in {".json", ".yaml", ".yml", ".md", ".py"}]
    assert units == 2 * len(files)
    counts = {f"REX-{i:03d}": 0 for i in range(1, 7)}
    for p in files:
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for rid in counts:
            counts[rid] += text.count(rid)
    assert counts["REX-005"] >= 2
    assert digest == hashlib.sha256(
        json.dumps(counts, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def test_artifact_crosscheck_paths(env, tmp_path):
    a = tmp_path / "a.json"
    c = tmp_path / "c.json"
    with pytest.raises(RuntimeError, match="seed missing"):
        env.mod.artifact_crosscheck(1, 1, a, c)
    a.write_text("same", encoding="utf-8")
    c.write_text("diff", encoding="utf-8")
    with pytest.raises(RuntimeError, match="semantic mismatch"):
        env.mod.artifact_crosscheck(1, 1, a, c)
    c.write_text("same", encoding="utf-8")
    h = hashlib.sha256(b"same").hexdigest()
    expected = hashlib.sha256("\n".join([h, h, h]).encode()).hexdigest()
    assert env.mod.artifact_crosscheck(3, 1, a, c) == (expected, 6)
    assert env.mod.artifact_crosscheck(3, 2, a, c) == (expected, 6)


def test_artifact_crosscheck_detects_divergence_during_reuse(env, tmp_path, monkeypatch):
    a = tmp_path / "a.json"
    c = tmp_path / "c.json"
    a.write_text("same", encoding="utf-8")
    c.write_text("same", encoding="utf-8")
    real = env.mod.digest_bytes
    seen = itertools.count()
    monkeypatch.setattr(env.mod, "digest_bytes", lambda raw: real(raw + str(next(seen)).encode()))
    with pytest.raises(RuntimeError, match="reuse inputs diverged"):
        env.mod.artifact_crosscheck(1, 1, a, c)


def test_start_contention_spawns_requested_burners(env):
    burners = env.mod.start_contention(3, seconds=0.1)
    assert len(burners) == 3
    assert burners[0].argv[0] == sys.executable and burners[0].argv[-1] == "0.1"
    assert env.mod.start_contention(0) == []


def test_prepare_reuse_seed_default_and_env_artifact(env, tmp_path, monkeypatch):
    art, cache = env.mod.prepare_reuse_seed(SHA, "linux-held")
    assert art == env.mod.ROOT / "REUSE_ARTIFACT.json"
    assert _load(art)["source_sha"] == SHA
    assert cache == tmp_path / "runner_temp" / "mc-pc3-cache" / "linux-held-reuse-seed.json"
    assert cache.read_bytes() == art.read_bytes()
    # existing artifact is not overwritten
    art.write_text('{"keep": 1}\n', encoding="utf-8")
    env.mod.prepare_reuse_seed("d" * 40, "linux-held")
    assert _load(art) == {"keep": 1}
    # env-provided artifact path, created in a new directory
    custom = tmp_path / "nested" / "art.json"
    monkeypatch.setenv("MC_REUSE_ARTIFACT", str(custom))
    monkeypatch.delenv("RUNNER_TEMP")
    art2, cache2 = env.mod.prepare_reuse_seed(SHA, "macos-baseline")
    assert art2 == custom and custom.exists()
    assert cache2.parent == env.mod.ROOT / "mc-pc3-cache"


# --- main ---------------------------------------------------------------------

def test_main_accepts_all_kinds_with_resources(env, monkeypatch, tmp_path, capsys):
    rp_heavy = {"contention_processes": 2, "cache_reuse": True, "artifact_reuse": True,
                "human_dependency_wait_seconds": 1.5}
    tasks = [
        _task("S", "analytics_sweep", pair_id="P", variant="A"),
        _task("V", "validation_bundle", pair_id="P", variant="B", crew_combination=["U01", "U02"]),
        _task("X", "artifact_crosscheck", rp=rp_heavy, task_class="reuse"),
        _task("R", "rex_surface_scan", rp={}),
    ]
    monkeypatch.setattr(env.mod, "MANIFEST", _manifest(tasks))
    monkeypatch.setenv("GITHUB_RUN_ID", "42")
    monkeypatch.setenv("RUNNER_OS", "Linux")
    monkeypatch.setenv("MC_REUSE_ARTIFACT", str(tmp_path / "shared" / "art.json"))
    out, code = _main(env, monkeypatch, tmp_path, lane="held")
    assert code is None
    assert env.sleeps == [1.5]
    assert len(env.popens) == 2 and all(b.waited == 2 and not b.killed for b in env.popens)

    summary = _load(out / "linux-held__RUN_SUMMARY.json")
    assert summary["schema"] == "missioncontrol.crew_frontier_pc3_run_summary.v2"
    assert (summary["task_count"], summary["accepted"], summary["rejected"]) == (4, 4, 0)
    assert summary["pair_members"] == 2
    assert summary["artifact_reused"] is True and summary["cache_reused"] is True
    assert summary["cell_id"] == "linux-held" and summary["run_id"] == "42"

    x = _load(out / "linux-held__X.json")
    assert x["schema"] == "missioncontrol.crew_frontier_pc3_runtime_receipt.v2"
    assert x["measured_resource"] == {"contention_processes": 2, "cache_reused": True,
                                      "artifact_reused": True,
                                      "human_dependency_wait_seconds": 0.5}
    assert x["workload_units"] == 6
    assert x["execute_seconds"] == 0.5
    assert x["habitat"]["runner"] == {"name": "LOCAL_UNBOUND", "os": "Linux",
                                      "arch": "UNKNOWN", "environment": "github-hosted"}
    assert x["rex_postflight"]["preventive_action_effective"] is True
    s = _load(out / "linux-held__S.json")
    assert s["measured_resource"]["artifact_reused"] is False
    assert s["measured_resource"]["human_dependency_wait_seconds"] == 0.0
    printed = [json.loads(x) for x in capsys.readouterr().out.splitlines() if x.strip()]
    assert [p.get("task_id") for p in printed[:4]] == ["S", "V", "X", "R"]


def test_main_rejections_unknown_kind_failure_and_hung_burner(env, monkeypatch, tmp_path):
    env.hang = True
    rp = {"contention_processes": 1, "cache_reuse": True, "artifact_reuse": True}
    tasks = [
        _task("K", "mystery", rp=rp),
        _task("F", "validation_bundle"),
    ]
    env.procs["validate_crew_system.py"] = FakeProc(1)
    monkeypatch.setattr(env.mod, "MANIFEST", _manifest(tasks))
    out, code = _main(env, monkeypatch, tmp_path, habitat="macos")
    assert code == 1
    assert env.popens[0].killed is True
    k = _load(out / "macos-baseline__K.json")
    assert k["disposition"] == "REJECT"
    assert k["error"] == "RuntimeError('unknown workload mystery')"
    assert k["semantic_digest"] is None and k["workload_units"] == 0
    assert k["measured_resource"]["cache_reused"] is True
    assert k["measured_resource"]["artifact_reused"] is False  # no MC_REUSE_ARTIFACT
    assert k["rex_postflight"]["preventive_action_effective"] is None
    f = _load(out / "macos-baseline__F.json")
    assert "validation failed" in f["error"]
    summary = _load(out / "macos-baseline__RUN_SUMMARY.json")
    assert summary["rejected"] == 2 and summary["artifact_reused"] is False


def test_main_preflight_block_records_recurrence(env, monkeypatch, tmp_path):
    hist = env.crew / "measured" / "history"
    hist.mkdir()
    (hist / "h.json").write_text(json.dumps(
        {"rex_postflight": {"rex_ids_observed": ["REX-005"]}}), encoding="utf-8")
    rp = {"contention_processes": 3, "cache_reuse": True, "artifact_reuse": True,
          "human_dependency_wait_seconds": 2.0}
    monkeypatch.setattr(env.mod, "MANIFEST",
                        _manifest([_task("B1", rp=rp), _task("B2")], hypothesis=""))
    out, code = _main(env, monkeypatch, tmp_path, habitat="windows")
    assert code == 1
    assert env.popens == [] and env.sleeps == []
    b1 = _load(out / "windows-baseline__B1.json")
    assert b1["error"] == "REX_PREFLIGHT_BLOCKED:REX-005"
    assert b1["steps_executed"] == 0 and b1["execute_seconds"] == 0.0
    assert b1["measured_resource"] == {"contention_processes": 0, "cache_reused": False,
                                       "artifact_reused": False,
                                       "human_dependency_wait_seconds": 0.0}
    assert b1["rex_postflight"]["recurrence_level"] == "RECURRING"
    b2 = _load(out / "windows-baseline__B2.json")
    assert b2["rex_postflight"]["recurrence_level"] == "PERSISTENT"
    assert _load(out / "windows-baseline__RUN_SUMMARY.json")["preflight_blocked"] == 2


@pytest.mark.parametrize("source,checkout", [("", SHA), ("ab", "ab"), (SHA, "d" * 40)])
def test_main_sha_guard(env, monkeypatch, tmp_path, source, checkout):
    monkeypatch.setenv("MC_SOURCE_SHA", source)
    env.checkout = checkout
    _, code = _main(env, monkeypatch, tmp_path)
    assert code.startswith("FAIL exact SHA")


@pytest.mark.parametrize("task,msg", [
    (_task("C", primary_crew_id="U99"), "FAIL unknown crew in C"),
    (_task("C", crew_combination=["U99"]), "FAIL unknown crew in C"),
    (_task("C", competency_dimension="nope"), "FAIL unknown competency nope"),
    (_task("C", applicable_rex_ids=["REX-404"]), "FAIL unknown REX in C"),
])
def test_main_manifest_validation(env, monkeypatch, tmp_path, task, msg):
    monkeypatch.setattr(env.mod, "MANIFEST", _manifest([task]))
    _, code = _main(env, monkeypatch, tmp_path)
    assert code == msg


def test_main_rejects_bad_lane(env, monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["run", "--habitat", "linux", "--lane", "fast",
                                      "--out", str(tmp_path / "o")])
    with pytest.raises(SystemExit) as exc:
        env.mod.main()
    assert exc.value.code == 2
