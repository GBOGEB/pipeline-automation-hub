"""Behavioural tests for mission-control/grand-missions/assess_gm_fleet_03.py."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "mission-control" / "grand-missions" / "assess_gm_fleet_03.py"
ENV_KEYS = ("GITHUB_REPOSITORY", "SOURCE_SHA", "GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_REF")


def _load_module():
    spec = importlib.util.spec_from_file_location("cw_assess_gm_fleet_03", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mod(monkeypatch):
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    return _load_module()


def _gm4(state="HELD", **extra):
    gm4 = {"id": "GM-IV", "state": state, "children": [], "candidate_frontiers": [], "unfilled_frontier_slots": []}
    gm4.update(extra)
    return gm4


def _docs(gm4=None):
    crew = {
        "crew": [
            {"crew_id": "U01", "maturity": "OBSERVED_RUNTIME", "current_load": "LOW"},
            {"crew_id": "U02", "maturity": "EXPERT_SEEDED", "current_load": "HIGH"},
            {"crew_id": "U03"},
        ]
    }
    snap = {
        "snapshot_class": "MIXED_OBSERVED_AND_EXPERT_SEEDED",
        "live_observations": [
            {"steps_executed": 0, "state": "BLOCKED"},
            {"steps_executed": None, "state": "BLOCKED"},
            {"steps_executed": 3, "state": "BLOCKED"},
            {"steps_executed": 0, "state": "PASS"},
        ],
    }
    registry = {
        "grand_missions": [
            {"id": "GM-III", "state": "RECON_CONTROL"},
            gm4 if gm4 is not None else _gm4(),
            {"id": "GM-V", "state": "HELD", "children": []},
        ]
    }
    contract = {
        "authority_transfer": False,
        "capacity_classes": {"REGISTERED": "counted_from_registry"},
        "required_activation_capabilities": {"COMMAND": ["U01", "U03"]},
    }
    candidates = {
        "authority_transfer": False,
        "candidate_ring": ["GM-IV-F01", "GM-IV-F02"],
        "unfilled_slots": ["F03", "F04", "F05", "F06", "F07", "F08"],
        "invariants": ["CANDIDATE_RECON_IS_NOT_A_GM_IV_CHILD_BINDING"],
    }
    return {"CREW": crew, "SNAPSHOT": snap, "REGISTRY": registry, "CONTRACT": contract, "CANDIDATES": candidates}


def _install(mod, monkeypatch, tmp_path, docs):
    for name, doc in docs.items():
        path = tmp_path / (name.lower() + ".json")
        path.write_text(json.dumps(doc), encoding="utf-8")
        monkeypatch.setattr(mod, name, path)


def _run(mod, monkeypatch, out):
    monkeypatch.setattr(sys, "argv", ["assess", "--out", str(out)])
    mod.main()
    return json.loads(out.read_text(encoding="utf-8"))


def _checks(receipt):
    return {c["check"]: c for c in receipt["structural_checks"]}


def test_load_reads_json(mod, tmp_path):
    p = tmp_path / "x.json"
    p.write_text('{"k": [1]}', encoding="utf-8")
    assert mod.load(p) == {"k": [1]}


def test_held_state_is_ready_for_recon(mod, tmp_path, monkeypatch, capsys):
    _install(mod, monkeypatch, tmp_path, _docs())
    out = tmp_path / "sub" / "receipt.json"
    receipt = _run(mod, monkeypatch, out)
    assert receipt["structural_gate"] == "PASS"
    assert receipt["activation_decision"] == "READY_FOR_RECON_2_OF_8_RUNTIME_PROOF"
    assert receipt["registered_crew_records"] == 3
    assert receipt["maturity_counts"] == {"EXPERT_SEEDED": 1, "OBSERVED_RUNTIME": 1, "UNKNOWN": 1}
    assert receipt["load_counts"] == {"HIGH": 1, "LOW": 1, "UNKNOWN": 1}
    assert receipt["retained_zero_step_observations"] == 2
    cov = receipt["capability_coverage"][0]
    assert cov["registered_hosts"] == ["U01", "U03"]
    assert cov["observed_hosts"] == ["U01"]
    assert cov["covered"] is True
    assert receipt["repo"] == "LOCAL" and receipt["source_sha"] == "UNKNOWN"
    assert receipt["run_id"] == "LOCAL" and receipt["ref"] == "LOCAL"
    summary = json.loads(capsys.readouterr().out)
    assert summary["result"] == "PASS_GM_FLEET_03_STRUCTURE"
    assert summary["baseline_candidate_frontiers"] == 2


def test_env_vars_flow_into_receipt(mod, tmp_path, monkeypatch):
    _install(mod, monkeypatch, tmp_path, _docs())
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("GITHUB_SHA", "abc")
    monkeypatch.setenv("GITHUB_RUN_ID", "7")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/x")
    receipt = _run(mod, monkeypatch, tmp_path / "r.json")
    assert receipt["repo"] == "o/r" and receipt["source_sha"] == "abc"
    monkeypatch.setenv("SOURCE_SHA", "def")
    receipt = _run(mod, monkeypatch, tmp_path / "r.json")
    assert receipt["source_sha"] == "def"
    assert receipt["run_id"] == "7" and receipt["ref"] == "refs/heads/x"


def test_recon_2_of_8_good_shape(mod, tmp_path, monkeypatch):
    gm4 = _gm4("STAGED_ACTIVE_RECON_2_OF_8", activation_stage="RECON_2_OF_8", candidate_frontiers=["GM-IV-F01", "GM-IV-F02"])
    _install(mod, monkeypatch, tmp_path, _docs(gm4))
    receipt = _run(mod, monkeypatch, tmp_path / "r.json")
    assert receipt["activation_decision"] == "PASS_STAGED_ACTIVE_RECON_2_OF_8_CONTROL_SHAPE"
    assert receipt["current_registry_frontiers"] == ["GM-IV-F01", "GM-IV-F02"]


def test_recon_2_of_8_bad_shape_fails(mod, tmp_path, monkeypatch, capsys):
    gm4 = _gm4("STAGED_ACTIVE_RECON_2_OF_8", activation_stage="RECON_2_OF_8", candidate_frontiers=["GM-IV-F01"])
    _install(mod, monkeypatch, tmp_path, _docs(gm4))
    out = tmp_path / "r.json"
    with pytest.raises(SystemExit) as exc:
        _run(mod, monkeypatch, out)
    assert exc.value.code == 1
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["structural_gate"] == "FAIL"
    assert receipt["activation_decision"] == "HELD_STRUCTURAL_GATE_RED"
    assert _checks(receipt)["11_current_stage_shape"]["result"] == "FAIL"
    assert json.loads(capsys.readouterr().out)["result"] == "FAIL_GM_FLEET_03_STRUCTURE"


def _pilot(**over):
    fields = dict(
        activation_stage="PILOT_2_OF_8",
        controlled_pilot_frontiers=["GM-IV-F01", "GM-IV-F03"],
        reference_frontiers=["GM-IV-F02", "GM-IV-F04"],
        unfilled_frontier_slots=["GM-IV-F05", "GM-IV-F06", "GM-IV-F07", "GM-IV-F08"],
    )
    fields.update(over)
    return _gm4("STAGED_ACTIVE_PILOT_2_OF_8", **fields)


def test_pilot_2_of_8_good_shape(mod, tmp_path, monkeypatch):
    _install(mod, monkeypatch, tmp_path, _docs(_pilot()))
    receipt = _run(mod, monkeypatch, tmp_path / "r.json")
    assert receipt["activation_decision"] == "PASS_STAGED_ACTIVE_PILOT_2_OF_8_CAPACITY_SHAPE"
    assert receipt["current_registry_unfilled_slots"] == ["GM-IV-F05", "GM-IV-F06", "GM-IV-F07", "GM-IV-F08"]


def test_pilot_2_of_8_bad_shape_fails(mod, tmp_path, monkeypatch):
    _install(mod, monkeypatch, tmp_path, _docs(_pilot(reference_frontiers=[])))
    with pytest.raises(SystemExit):
        _run(mod, monkeypatch, tmp_path / "r.json")


@pytest.mark.parametrize("state", ["STAGED_ACTIVE_RECON_4_OF_8", "ACTIVE_8_OF_8"])
def test_forward_stages(mod, tmp_path, monkeypatch, state):
    _install(mod, monkeypatch, tmp_path, _docs(_gm4(state)))
    receipt = _run(mod, monkeypatch, tmp_path / "r.json")
    assert receipt["activation_decision"] == "PASS_FORWARD_STAGE_CAPACITY_SHAPE"
    assert receipt["gm_iv_state"] == state


def test_unknown_gm_iv_state_fails(mod, tmp_path, monkeypatch):
    _install(mod, monkeypatch, tmp_path, _docs(_gm4("LAUNCHED")))
    out = tmp_path / "r.json"
    with pytest.raises(SystemExit):
        _run(mod, monkeypatch, out)
    checks = _checks(json.loads(out.read_text(encoding="utf-8")))
    assert checks["02_gm_iv_held_or_controlled_staged"]["result"] == "FAIL"
    assert checks["02_gm_iv_held_or_controlled_staged"]["detail"] == "LAUNCHED"


def test_uncovered_capability_fails(mod, tmp_path, monkeypatch):
    docs = _docs()
    docs["CONTRACT"]["required_activation_capabilities"]["BOUNDARY"] = ["U02", "ZZ9"]
    _install(mod, monkeypatch, tmp_path, docs)
    out = tmp_path / "r.json"
    with pytest.raises(SystemExit):
        _run(mod, monkeypatch, out)
    receipt = json.loads(out.read_text(encoding="utf-8"))
    rows = {r["capability"]: r for r in receipt["capability_coverage"]}
    assert rows["BOUNDARY"]["covered"] is False
    assert rows["BOUNDARY"]["registered_hosts"] == ["U02"]
    assert rows["COMMAND"]["covered"] is True
    assert _checks(receipt)["06_required_capability_host_coverage"]["result"] == "FAIL"


@pytest.mark.parametrize(
    "mutate,check",
    [
        (lambda d: d["REGISTRY"]["grand_missions"][0].update(state="ACTIVE"), "01_gm_iii_control"),
        (lambda d: d["REGISTRY"]["grand_missions"][2].update(children=["x"]), "03_gm_v_hard_held"),
        (lambda d: d["CANDIDATES"].update(candidate_ring=["a"]), "04_initial_candidate_ring_frozen"),
        (lambda d: d["CANDIDATES"].update(unfilled_slots=[]), "05_initial_unfilled_slots_frozen"),
        (lambda d: d["CONTRACT"].update(authority_transfer=True), "07_no_authority_transfer"),
        (lambda d: d["CONTRACT"]["capacity_classes"].update(REGISTERED="runtime"), "08_registered_capacity_not_claimed_runtime"),
        (lambda d: d["SNAPSHOT"].update(snapshot_class="MEASURED"), "09_snapshot_not_promoted_to_measured"),
        (lambda d: d["CANDIDATES"].update(invariants=[]), "10_candidate_recon_not_child_binding"),
    ],
)
def test_each_structural_check_can_fail(mod, tmp_path, monkeypatch, mutate, check):
    docs = _docs()
    mutate(docs)
    _install(mod, monkeypatch, tmp_path, docs)
    out = tmp_path / "r.json"
    with pytest.raises(SystemExit):
        _run(mod, monkeypatch, out)
    checks = _checks(json.loads(out.read_text(encoding="utf-8")))
    failed = sorted(name for name, c in checks.items() if c["result"] == "FAIL")
    assert failed == [check]


def test_missing_optional_sections_default(mod, tmp_path, monkeypatch):
    docs = _docs()
    docs["CREW"] = {}
    docs["SNAPSHOT"].pop("live_observations")
    docs["CONTRACT"]["required_activation_capabilities"] = {}
    _install(mod, monkeypatch, tmp_path, docs)
    receipt = _run(mod, monkeypatch, tmp_path / "r.json")
    assert receipt["registered_crew_records"] == 0
    assert receipt["retained_zero_step_observations"] == 0
    assert receipt["capability_coverage"] == []


def test_real_committed_data_passes(mod, tmp_path, monkeypatch):
    receipt = _run(mod, monkeypatch, tmp_path / "real.json")
    assert receipt["structural_gate"] == "PASS"
    assert receipt["schema"] == "qps.gm_fleet_03_capacity_receipt.v1"
    assert receipt["authority_transfer"] is False


def test_out_is_required(mod, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["assess"])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 2
