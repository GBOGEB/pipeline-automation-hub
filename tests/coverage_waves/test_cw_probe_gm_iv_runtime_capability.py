"""Behavioural tests for mission-control/grand-missions/probe_gm_iv_runtime_capability.py."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "mission-control" / "grand-missions" / "probe_gm_iv_runtime_capability.py"
HEAD = "a" * 40
BASE = "b" * 40


def _load_module():
    spec = importlib.util.spec_from_file_location("cw_probe_gm_iv_runtime_capability", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def _registry():
    return {
        "authority_transfer": False,
        "grand_missions": [
            {"id": "GM-IV", "state": "ACTIVE_8_OF_8", "children": [], "active_8_of_8_evidence": {"result": "PASS"}},
            {"id": "GM-V", "state": "HELD", "children": []},
        ],
    }


def _launch(gm_v_state="HELD_EXTERNAL_OPERATIONAL_AVAILABILITY_GATE"):
    return {
        "authority_transfer": False,
        "launch_order": [
            {"order": 1, "id": "GM-IV"},
            {"order": 2, "id": "GM-V-HOLD", "state": gm_v_state, "launch_gate": "SEPARATE_GOVERNOR_LAUNCH_REQUIRED"},
        ],
    }


def _governor():
    ev = {}
    for i in range(1, 9):
        ev[f"GM-IV-F{i:02d}"] = {"repository": f"GBOGEB/repo{i}", "target_sha": f"{i:x}" * 40, "class": "PILOT"}
    return {"frontier_evidence": ev}


@pytest.fixture
def root(tmp_path):
    root = tmp_path / "gm"
    _write(root / "GRAND_MISSION_REGISTRY.json", _registry())
    _write(root / "GM_FLEET_IMMINENT_LAUNCH_CONTROL_v1.json", _launch())
    _write(
        root / "GM_IV_ACTIVE8_PROMOTION_CONTRACT.json",
        {"forbidden_mutations": ["transfer engineering authority", "promote GM-V from HELD"]},
    )
    _write(root / "GM_IV_ACTIVE8_GOVERNOR_CONTRACT.json", _governor())
    _write(
        root / "GM_IV_POST_ACTIVE8_REPEAT_CONTROL_CONTRACT.json",
        {"success_semantics": {"repeat_control": "PASS_POST_ACTIVE8_REPEAT_CONTROL", "gm_v": "HELD"}},
    )
    _write(
        root / "GM_FLEET_03_CAPACITY_CONTRACT.json",
        {"authority_transfer": False, "release_invariants": ["NO_UNRESOLVED_NONCOMPENSATING_VETO"]},
    )
    return root


@pytest.fixture
def mod(monkeypatch, root, tmp_path):
    m = _load_module()
    monkeypatch.setattr(m, "ROOT", root)
    monkeypatch.setattr(m, "CREW", tmp_path / "crew")
    return m


def _mutate(root, name, fn):
    p = root / name
    data = json.loads(p.read_text(encoding="utf-8"))
    fn(data)
    p.write_text(json.dumps(data), encoding="utf-8")


def test_require_raises_systemexit(mod):
    mod.require(True, "ok")
    with pytest.raises(SystemExit, match="FAIL: nope"):
        mod.require(False, "nope")


def test_current_head_strips(mod, monkeypatch):
    calls = []

    def fake(cmd, text=None):
        calls.append(cmd)
        return HEAD + "\n"

    monkeypatch.setattr(mod.subprocess, "check_output", fake)
    assert mod.current_head() == HEAD
    assert calls == [["git", "rev-parse", "HEAD"]]


def test_run_python_success_and_failure(mod, monkeypatch, tmp_path):
    calls = []

    def ok(cmd, text=None, capture_output=None):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, " out \n", "")

    monkeypatch.setattr(mod.subprocess, "run", ok)
    assert mod.run_python(tmp_path / "x.py", "--a") == "out"
    assert calls == [["python", str(tmp_path / "x.py"), "--a"]]

    monkeypatch.setattr(mod.subprocess, "run", lambda cmd, **k: subprocess.CompletedProcess(cmd, 3, None, "bad"))
    with pytest.raises(SystemExit, match="x.py exit=3 stderr=bad"):
        mod.run_python(tmp_path / "x.py")


def test_run_python_none_stdout(mod, monkeypatch, tmp_path):
    monkeypatch.setattr(mod.subprocess, "run", lambda cmd, **k: subprocess.CompletedProcess(cmd, 0, None, ""))
    assert mod.run_python(tmp_path / "x.py") == ""


def test_probe_command_pass(mod):
    assert mod.probe_command() == {"launch_entries": 2, "gm_iv_state": "ACTIVE_8_OF_8", "gm_v_state": "HELD"}


def test_probe_command_non_monotonic(mod, root):
    _mutate(root, "GM_FLEET_IMMINENT_LAUNCH_CONTROL_v1.json", lambda d: d["launch_order"][0].update(order=2))
    with pytest.raises(SystemExit, match="unique and monotonic"):
        mod.probe_command()


def test_probe_command_gm_iv_state(mod, root):
    _mutate(root, "GRAND_MISSION_REGISTRY.json", lambda d: d["grand_missions"][0].update(state="X"))
    with pytest.raises(SystemExit, match="ACTIVE_8_OF_8"):
        mod.probe_command()


def test_probe_command_authority(mod, root):
    _mutate(root, "GM_FLEET_IMMINENT_LAUNCH_CONTROL_v1.json", lambda d: d.update(authority_transfer=True))
    with pytest.raises(SystemExit, match="authority transfer"):
        mod.probe_command()


def test_probe_technical_boundary_pass(mod):
    assert mod.probe_technical_boundary()["active8_evidence"] == "PASS"


@pytest.mark.parametrize(
    "fname,fn,msg",
    [
        ("GRAND_MISSION_REGISTRY.json", lambda d: d["grand_missions"][0].update(children=["c"]), "canonical children"),
        ("GRAND_MISSION_REGISTRY.json", lambda d: d["grand_missions"][0].pop("active_8_of_8_evidence"), "ACTIVE8 accepted"),
        ("GM_IV_ACTIVE8_PROMOTION_CONTRACT.json", lambda d: d.update(forbidden_mutations=["promote GM-V from HELD"]), "engineering authority"),
        ("GM_IV_ACTIVE8_PROMOTION_CONTRACT.json", lambda d: d.update(forbidden_mutations=["transfer engineering authority"]), "GM-V boundary"),
    ],
)
def test_probe_technical_boundary_failures(mod, root, fname, fn, msg):
    _mutate(root, fname, fn)
    with pytest.raises(SystemExit, match=msg):
        mod.probe_technical_boundary()


def test_probe_recon_pass(mod):
    assert mod.probe_recon() == {"frontiers": 8, "unique_repositories": 8, "unique_shas": 8}


def _gov_mut(fn):
    def inner(d):
        fn(d["frontier_evidence"])

    return inner


@pytest.mark.parametrize(
    "fn,msg",
    [
        (lambda ev: ev.pop("GM-IV-F08"), "keys mismatch"),
        (lambda ev: ev["GM-IV-F01"].update(repository="other/x"), "not governed"),
        (lambda ev: ev["GM-IV-F01"].update(target_sha="z" * 40), "invalid target SHA"),
        (lambda ev: ev["GM-IV-F01"].update(target_sha="a" * 39), "invalid target SHA"),
        (lambda ev: ev["GM-IV-F01"].pop("class"), "missing evidence class"),
        (lambda ev: ev["GM-IV-F02"].update(repository="GBOGEB/repo1"), "repositories must be unique"),
        (lambda ev: ev["GM-IV-F02"].update(target_sha="1" * 40), "SHAs must be unique"),
    ],
)
def test_probe_recon_failures(mod, root, fn, msg):
    _mutate(root, "GM_IV_ACTIVE8_GOVERNOR_CONTRACT.json", _gov_mut(fn))
    with pytest.raises(SystemExit, match=msg):
        mod.probe_recon()


def test_probe_analysis(mod, monkeypatch, root):
    seen = []
    monkeypatch.setattr(mod, "run_python", lambda p, *a: seen.append(p) or "x" * 300)
    res = mod.probe_analysis()
    assert res["stdout_tail"] == "x" * 240
    assert seen == [root / "validate_gm_iv_evidence_economics.py"]


@pytest.fixture
def git_ok(mod, monkeypatch):
    calls = []
    monkeypatch.setattr(mod.subprocess, "check_output", lambda cmd, text=None: HEAD + "\n")

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setenv("MC_SOURCE_SHA", HEAD)
    monkeypatch.setenv("MC_BASE_SHA", BASE)
    return calls


def test_probe_runtime_pass(mod, git_ok):
    assert mod.probe_runtime() == {"exact_source_sha": HEAD, "event_base_sha": BASE, "repeat_control_contract": "BOUND"}
    assert git_ok == [["git", "merge-base", "--is-ancestor", BASE, HEAD]]


def test_probe_runtime_missing_source(mod, git_ok, monkeypatch):
    monkeypatch.delenv("MC_SOURCE_SHA")
    with pytest.raises(SystemExit, match="MC_SOURCE_SHA"):
        mod.probe_runtime()


def test_probe_runtime_bad_base(mod, git_ok, monkeypatch):
    monkeypatch.setenv("MC_BASE_SHA", "short")
    with pytest.raises(SystemExit, match="MC_BASE_SHA"):
        mod.probe_runtime()


def test_probe_runtime_head_mismatch(mod, git_ok, monkeypatch):
    monkeypatch.setenv("MC_SOURCE_SHA", "c" * 40)
    with pytest.raises(SystemExit, match="head mismatch"):
        mod.probe_runtime()


def test_probe_runtime_not_ancestor(mod, git_ok, monkeypatch):
    monkeypatch.setattr(mod.subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1))
    with pytest.raises(SystemExit, match="ancestry mismatch"):
        mod.probe_runtime()


def test_probe_runtime_repeat_contract(mod, git_ok, root):
    _mutate(root, "GM_IV_POST_ACTIVE8_REPEAT_CONTROL_CONTRACT.json", lambda d: d["success_semantics"].update(repeat_control="X"))
    with pytest.raises(SystemExit, match="repeat CONTROL contract"):
        mod.probe_runtime()


def test_probe_runtime_gm_v(mod, git_ok, root):
    _mutate(root, "GM_IV_POST_ACTIVE8_REPEAT_CONTROL_CONTRACT.json", lambda d: d["success_semantics"].update(gm_v="LIVE"))
    with pytest.raises(SystemExit, match="preserve GM-V hold"):
        mod.probe_runtime()


def test_probe_qa(mod, monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(mod, "run_python", lambda p, *a: seen.append(p) or "... PASS_CREW_SYSTEM")
    assert mod.probe_qa()["marker"] == "PASS_CREW_SYSTEM"
    assert seen == [tmp_path / "crew" / "validate_crew_system.py"]
    monkeypatch.setattr(mod, "run_python", lambda p, *a: "nothing")
    with pytest.raises(SystemExit, match="marker missing"):
        mod.probe_qa()


def test_probe_build_repair_reserve(mod, root, monkeypatch):
    compiled = []
    monkeypatch.setattr(mod.py_compile, "compile", lambda path, doraise=False: compiled.append((path, doraise)))
    res = mod.probe_build_repair_reserve()
    assert res["count"] == 5
    assert "measure_gm_iv_runtime_capacity.py" in res["compiled_scripts"]
    assert all(d is True for _, d in compiled)
    assert compiled[0][0] == str(root / "validate_gm_fleet.py")


def test_probe_build_repair_reserve_real_compile_error(mod, root):
    (root / "validate_gm_fleet.py").write_text("def broken(:\n", encoding="utf-8")
    import py_compile

    with pytest.raises(py_compile.PyCompileError):
        mod.probe_build_repair_reserve()


@pytest.mark.parametrize("state", ["HELD", "HELD_EXTERNAL_OPERATIONAL_AVAILABILITY_GATE"])
def test_probe_governance_pass(mod, root, state):
    _write(root / "GM_FLEET_IMMINENT_LAUNCH_CONTROL_v1.json", _launch(state))
    assert mod.probe_governance()["separate_governor_launch"] is True


@pytest.mark.parametrize(
    "fname,fn,msg",
    [
        ("GRAND_MISSION_REGISTRY.json", lambda d: d.update(authority_transfer=True), "registry authority"),
        ("GM_FLEET_03_CAPACITY_CONTRACT.json", lambda d: d.update(authority_transfer=True), "capacity authority"),
        ("GM_FLEET_03_CAPACITY_CONTRACT.json", lambda d: d.update(release_invariants=[]), "noncompensating veto"),
        ("GRAND_MISSION_REGISTRY.json", lambda d: d["grand_missions"][1].update(children=["x"]), "governance hold broken"),
        ("GM_FLEET_IMMINENT_LAUNCH_CONTROL_v1.json", lambda d: d["launch_order"][1].update(state="LAUNCHED"), "hold broken: LAUNCHED"),
        ("GM_FLEET_IMMINENT_LAUNCH_CONTROL_v1.json", lambda d: d["launch_order"][1].update(launch_gate="NONE"), "Governor launch gate"),
    ],
)
def test_probe_governance_failures(mod, root, fname, fn, msg):
    _mutate(root, fname, fn)
    with pytest.raises(SystemExit, match=msg):
        mod.probe_governance()


def test_main_dispatches_and_prints_marker(mod, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["probe", "--capability", "COMMAND"])
    mod.main()
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[-1] == "PASS_GM_IV_RUNTIME_CAPABILITY_COMMAND"
    payload = json.loads(lines[0])
    assert payload["capability"] == "COMMAND"
    assert payload["detail"]["launch_entries"] == 2


def test_main_rejects_unknown_capability(mod, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["probe", "--capability", "NOPE"])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 2


def test_probe_map_complete(mod):
    assert sorted(mod.PROBES) == sorted(
        ["COMMAND", "TECHNICAL_BOUNDARY", "RECON", "ANALYSIS", "RUNTIME", "QA", "BUILD_REPAIR_RESERVE", "GOVERNANCE"]
    )
