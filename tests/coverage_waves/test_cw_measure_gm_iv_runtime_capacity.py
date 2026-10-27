"""Behavioural tests for mission-control/grand-missions/measure_gm_iv_runtime_capacity.py."""
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "mission-control" / "grand-missions" / "measure_gm_iv_runtime_capacity.py"
HEAD = "a" * 40
BASE = "b" * 40
CAPS = ("COMMAND", "TECHNICAL_BOUNDARY", "RECON", "ANALYSIS", "RUNTIME", "QA", "BUILD_REPAIR_RESERVE", "GOVERNANCE")


def _load_module():
    spec = importlib.util.spec_from_file_location("cw_measure_gm_iv_runtime_capacity", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def _manifest(mod):
    assignments = []
    for i, cap in enumerate(CAPS):
        assignments.append(
            {
                "capability": cap,
                "crew_id": f"U{i:02d}",
                "task_id": f"T{i:02d}",
                "task_type": "PROBE",
                "command": list(mod.CANONICAL_PROBES[cap]["command"]),
                "accept_marker": mod.CANONICAL_PROBES[cap]["accept_marker"],
            }
        )
    return {
        "wave": "W1",
        "measurement_scope": "CAPABILITY_COVERAGE_NOT_CONCURRENCY_CAPACITY",
        "concurrency_capacity_claimed": False,
        "authority_transfer": False,
        "formal_credit_delta": 0,
        "hard_gate_compensation_allowed": False,
        "assignments": assignments,
    }


class Fakes:
    def __init__(self, head=HEAD, ancestor_rc=0, failing_caps=(), cat_ok=True):
        self.head = head
        self.ancestor_rc = ancestor_rc
        self.failing_caps = set(failing_caps)
        self.cat_ok = cat_ok
        self.calls = []

    def check_output(self, cmd, text=None):
        self.calls.append(("check_output", cmd))
        return self.head + "\n"

    def check_call(self, cmd):
        self.calls.append(("check_call", cmd))
        if not self.cat_ok:
            raise subprocess.CalledProcessError(1, cmd)
        return 0

    def run(self, cmd, text=None, capture_output=None, env=None):
        self.calls.append(("run", cmd, env))
        if cmd[0] == "git":
            return subprocess.CompletedProcess(cmd, self.ancestor_rc)
        cap = cmd[-1]
        assert env["MC_SOURCE_SHA"] == HEAD and env["MC_BASE_SHA"] == BASE
        if cap in self.failing_caps:
            return subprocess.CompletedProcess(cmd, 1, None, None)
        return subprocess.CompletedProcess(cmd, 0, "PASS_GM_IV_RUNTIME_CAPABILITY_" + cap + "\n", "")


@pytest.fixture
def ctx(monkeypatch, tmp_path):
    mod = _load_module()
    root = tmp_path / "gm"
    cap_path = root / "capacity.json"
    reg_path = root / "registry.json"
    crew_path = tmp_path / "crew" / "CREW_REGISTRY_v1.json"
    man_path = root / "manifest.json"
    _write(cap_path, {"required_activation_capabilities": {c: [f"U{i:02d}", "UXX"] for i, c in enumerate(CAPS)}})
    _write(
        reg_path,
        {
            "grand_missions": [
                {"id": "GM-IV", "state": "ACTIVE_8_OF_8", "children": []},
                {"id": "GM-V", "state": "HELD", "children": []},
            ]
        },
    )
    _write(
        crew_path,
        {"crew": [{"crew_id": f"U{i:02d}", "name": f"n{i}", "maturity": "OBSERVED_RUNTIME", "current_load": "LOW"} for i in range(8)]},
    )
    _write(man_path, _manifest(mod))
    monkeypatch.setattr(mod, "CAPACITY_CONTRACT", cap_path)
    monkeypatch.setattr(mod, "REGISTRY", reg_path)
    monkeypatch.setattr(mod, "CREW_REGISTRY", crew_path)
    for k in ("GITHUB_RUN_ID", "GITHUB_JOB", "RUNNER_NAME"):
        monkeypatch.delenv(k, raising=False)
    fakes = Fakes()
    monkeypatch.setattr(mod.subprocess, "check_output", fakes.check_output)
    monkeypatch.setattr(mod.subprocess, "check_call", fakes.check_call)
    monkeypatch.setattr(mod.subprocess, "run", fakes.run)
    out = tmp_path / "out"
    monkeypatch.setattr(
        sys,
        "argv",
        ["m", "--manifest", str(man_path), "--out-dir", str(out), "--source-sha", HEAD, "--base-sha", BASE],
    )
    return {"mod": mod, "fakes": fakes, "out": out, "man": man_path, "cap": cap_path, "reg": reg_path, "crew": crew_path}


def _mutate(path, fn):
    data = json.loads(path.read_text(encoding="utf-8"))
    fn(data)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_canonical_probe_map(ctx):
    mod = ctx["mod"]
    assert set(mod.CANONICAL_PROBES) == set(CAPS)
    assert mod.CANONICAL_PROBES["QA"]["command"] == ["python", mod.PROBE_SCRIPT, "--capability", "QA"]


def test_helpers(ctx, tmp_path):
    mod = ctx["mod"]
    p = tmp_path / "h.bin"
    p.write_bytes(b"abc")
    assert mod.sha256_file(p) == hashlib.sha256(b"abc").hexdigest()
    mod.require(True, "x")
    with pytest.raises(SystemExit, match="FAIL: m"):
        mod.require(False, "m")
    assert mod.git("rev-parse", "HEAD") == HEAD
    assert ctx["fakes"].calls[-1] == ("check_output", ["git", "rev-parse", "HEAD"])


def test_main_full_pass(ctx, capsys, monkeypatch):
    monkeypatch.setenv("GITHUB_RUN_ID", "42")
    monkeypatch.setenv("GITHUB_JOB", "job")
    monkeypatch.setenv("RUNNER_NAME", "r1")
    ctx["mod"].main()
    out = capsys.readouterr().out
    assert "PASS_GM_IV_RUNTIME_CAPACITY_8_OF_8" in out
    assert "DEFER_GM_V_OPERATIONAL_AVAILABILITY_EXTERNAL_GATES" in out
    agg = json.loads((ctx["out"] / "GM_IV_RUNTIME_CAPACITY_MEASUREMENT_RECEIPT.json").read_text(encoding="utf-8"))
    assert agg["runtime_proven_capability_count"] == 8
    assert agg["runtime_proven_ratio"] == 1.0
    assert agg["capacity_class"] == "RUNTIME_PROVEN"
    assert agg["measured_capacity_result"] == "PASS_RUNTIME_PROVEN_CAPABILITY_CAPACITY"
    assert agg["run_id"] == "42" and agg["job_ref"] == "job" and agg["runner_ref"] == "r1"
    assert agg["wave"] == "W1"
    assert agg["input_digests"]["measurement_contract_sha256"] == hashlib.sha256(ctx["man"].read_bytes()).hexdigest()
    assert agg["input_digests"]["trusted_runner_sha256"] == hashlib.sha256(MODULE_PATH.read_bytes()).hexdigest()
    r = json.loads((ctx["out"] / "T00.json").read_text(encoding="utf-8"))
    assert r["capability"] == "COMMAND"
    assert r["disposition"] == "ACCEPT"
    assert r["crew_name"] == "n0"
    expected_cmd = json.dumps(["python", ctx["mod"].PROBE_SCRIPT, "--capability", "COMMAND"], separators=(",", ":"))
    assert r["command_sha256"] == hashlib.sha256(expected_cmd.encode()).hexdigest()
    calls = ctx["fakes"].calls
    assert ("check_call", ["git", "cat-file", "-e", BASE + "^{commit}"]) in calls
    probe_runs = [c for c in calls if c[0] == "run" and c[1][0] == "python"]
    assert len(probe_runs) == 8


def test_main_partial_failure(ctx, capsys):
    ctx["fakes"].failing_caps = {"QA"}
    with pytest.raises(SystemExit, match=r"FAIL_GM_IV_RUNTIME_CAPACITY failed=\['QA:U05'\]"):
        ctx["mod"].main()
    agg = json.loads((ctx["out"] / "GM_IV_RUNTIME_CAPACITY_MEASUREMENT_RECEIPT.json").read_text(encoding="utf-8"))
    assert agg["capacity_class"] == "NOT_PROVEN"
    assert agg["measured_capacity_result"] == "FAIL_RUNTIME_CAPABILITY_CAPACITY"
    assert agg["runtime_proven_capability_count"] == 7
    qa = json.loads((ctx["out"] / "T05.json").read_text(encoding="utf-8"))
    assert qa["disposition"] == "REJECT"
    assert qa["stdout_sha256"] == hashlib.sha256(b"").hexdigest()
    assert agg["run_id"] == "LOCAL_UNBOUND"


def test_marker_missing_rejects(ctx, monkeypatch):
    fakes = ctx["fakes"]

    def run(cmd, **kw):
        if cmd[0] == "git":
            return subprocess.CompletedProcess(cmd, 0)
        return subprocess.CompletedProcess(cmd, 0, "no marker", "")

    monkeypatch.setattr(ctx["mod"].subprocess, "run", run)
    with pytest.raises(SystemExit, match="FAIL_GM_IV_RUNTIME_CAPACITY"):
        ctx["mod"].main()
    assert fakes is not None


def test_short_source_sha(ctx, monkeypatch):
    argv = list(sys.argv)
    argv[argv.index("--source-sha") + 1] = "abc"
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit, match="source SHA must be 40"):
        ctx["mod"].main()


def test_short_base_sha(ctx, monkeypatch):
    argv = list(sys.argv)
    argv[argv.index("--base-sha") + 1] = "abc"
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit, match="base SHA must be 40"):
        ctx["mod"].main()


def test_head_mismatch(ctx):
    ctx["fakes"].head = "c" * 40
    with pytest.raises(SystemExit, match="source SHA mismatch"):
        ctx["mod"].main()


def test_base_commit_missing(ctx):
    ctx["fakes"].cat_ok = False
    with pytest.raises(subprocess.CalledProcessError):
        ctx["mod"].main()


def test_not_ancestor(ctx):
    ctx["fakes"].ancestor_rc = 1
    with pytest.raises(SystemExit, match="is not an ancestor"):
        ctx["mod"].main()


@pytest.mark.parametrize(
    "key,value,msg",
    [
        ("measurement_scope", "OTHER", "measurement scope"),
        ("concurrency_capacity_claimed", True, "concurrency capacity"),
        ("authority_transfer", True, "manifest authority_transfer"),
        ("formal_credit_delta", 1, "formal_credit_delta"),
        ("hard_gate_compensation_allowed", True, "hard-gate compensation"),
    ],
)
def test_manifest_flags(ctx, key, value, msg):
    _mutate(ctx["man"], lambda d: d.update({key: value}))
    with pytest.raises(SystemExit, match=msg):
        ctx["mod"].main()


@pytest.mark.parametrize(
    "idx,field,value,msg",
    [
        (0, "state", "X", "GM-IV must remain ACTIVE_8_OF_8"),
        (0, "children", ["c"], "GM-IV children"),
        (1, "state", "LIVE", "GM-V must remain HELD"),
        (1, "children", ["c"], "GM-V children"),
    ],
)
def test_registry_guards(ctx, idx, field, value, msg):
    _mutate(ctx["reg"], lambda d: d["grand_missions"][idx].update({field: value}))
    with pytest.raises(SystemExit, match=msg):
        ctx["mod"].main()


def test_capacity_contract_capability_set(ctx):
    _mutate(ctx["cap"], lambda d: d["required_activation_capabilities"].pop("QA"))
    with pytest.raises(SystemExit, match="identical capability sets"):
        ctx["mod"].main()


def test_manifest_capability_set_mismatch(ctx):
    _mutate(ctx["man"], lambda d: d["assignments"].pop())
    with pytest.raises(SystemExit, match="capability set mismatch"):
        ctx["mod"].main()


def test_duplicate_capability_rows(ctx):
    def fn(d):
        d["assignments"].append(dict(d["assignments"][0], crew_id="U99", task_id="T99"))

    _mutate(ctx["man"], fn)
    with pytest.raises(SystemExit, match="exactly 8 unique rows"):
        ctx["mod"].main()


def test_duplicate_crew(ctx):
    _mutate(ctx["man"], lambda d: d["assignments"][1].update(crew_id="U00"))
    with pytest.raises(SystemExit, match="eight distinct"):
        ctx["mod"].main()


def test_duplicate_task(ctx):
    _mutate(ctx["man"], lambda d: d["assignments"][1].update(task_id="T00"))
    with pytest.raises(SystemExit, match="task IDs must be unique"):
        ctx["mod"].main()


def test_command_divergence(ctx):
    _mutate(ctx["man"], lambda d: d["assignments"][2].update(command=["python", "evil.py"]))
    with pytest.raises(SystemExit, match="RECON: manifest command diverges"):
        ctx["mod"].main()


def test_marker_divergence(ctx):
    _mutate(ctx["man"], lambda d: d["assignments"][2].update(accept_marker="PASS"))
    with pytest.raises(SystemExit, match="RECON: manifest marker diverges"):
        ctx["mod"].main()


def test_host_not_allowed(ctx):
    _mutate(ctx["cap"], lambda d: d["required_activation_capabilities"].update(COMMAND=["U77"]))
    with pytest.raises(SystemExit, match="U00 is not an allowed host for COMMAND"):
        ctx["mod"].main()


def test_unknown_crew(ctx):
    _mutate(ctx["crew"], lambda d: d["crew"].pop(0))
    with pytest.raises(SystemExit, match="unknown crew host U00"):
        ctx["mod"].main()


def test_crew_not_observed(ctx):
    _mutate(ctx["crew"], lambda d: d["crew"][0].update(maturity="EXPERT_SEEDED"))
    with pytest.raises(SystemExit, match="U00 is not observed maturity"):
        ctx["mod"].main()
