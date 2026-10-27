"""Behavioural tests for mission-control/grand-missions/assess_gm_iv_f01_pilot.py."""
import copy
import importlib.util
import json
import runpy
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_DIR = REPO_ROOT / "mission-control" / "grand-missions"
MOD_PATH = MOD_DIR / "assess_gm_iv_f01_pilot.py"


def _load():
    spec = importlib.util.spec_from_file_location("cw_assess_gm_iv_f01_pilot", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pilot = _load()

TARGET_SHA = "d" * 40
ENV_KEYS = ("GITHUB_REPOSITORY", "SOURCE_SHA", "GITHUB_SHA", "GITHUB_RUN_ID")


def _registry(gm_iv_state="ACTIVE_8_OF_8", gm_iv_children=None, gm_v_state="HELD", gm_v_children=None):
    return {"grand_missions": [
        {"id": "GM-IV", "state": gm_iv_state, "children": [] if gm_iv_children is None else gm_iv_children},
        {"id": "GM-V", "state": gm_v_state, "children": [] if gm_v_children is None else gm_v_children},
    ]}


def _contract(**over):
    c = {
        "target": {"repository": "GBOGEB/target", "source_sha": TARGET_SHA},
        "mission_state_must_remain": "STAGED_ACTIVE_RECON_2_OF_8",
        "f02_state": "REFERENCE",
        "authority_transfer": False,
        "children_bound": False,
    }
    c.update(over)
    return c


def _rex(ids=("REX-GMF-03-R1-001",)):
    return {"events": [{"rex_id": i} for i in ids]}


def _runtime(**over):
    r = {
        "target_sha": TARGET_SHA,
        "positive_exit_code": 0,
        "positive_pass_marker": True,
        "positive_validated_surface_count": 4,
        "negative_exit_code": 1,
        "negative_rejection_marker": True,
        "target_dirty_file_count": 0,
        "positive_output_sha256": "a" * 64,
    }
    r.update(over)
    return r


def _write_runtime(tmp_path, runtime):
    rt_p = tmp_path / "runtime.json"
    rt_p.write_text(json.dumps(runtime), encoding="utf-8")
    out_p = tmp_path / "receipt.json"
    return ["assess_gm_iv_f01_pilot.py", "--runtime-receipt", str(rt_p), "--out", str(out_p)], out_p


def _run(tmp_path, monkeypatch, capsys, registry=None, contract=None, rex=None, runtime=None, env=None):
    paths = {}
    for name, data in (("REGISTRY", registry or _registry()), ("CONTRACT", contract or _contract()),
                       ("REX", rex if rex is not None else _rex())):
        p = tmp_path / (name.lower() + ".json")
        p.write_text(json.dumps(data), encoding="utf-8")
        monkeypatch.setattr(pilot, name, p)
        paths[name] = p
    for k in ENV_KEYS:
        monkeypatch.delenv(k, raising=False)
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)
    argv, out_p = _write_runtime(tmp_path, runtime if runtime is not None else _runtime())
    monkeypatch.setattr(sys, "argv", argv)
    code = None
    try:
        pilot.main()
    except SystemExit as exc:
        code = exc.code
    receipt = json.loads(out_p.read_text(encoding="utf-8"))
    summary = json.loads(capsys.readouterr().out)
    return code, receipt, summary


def _failed(receipt):
    return [c["check"] for c in receipt["checks"] if c["result"] == "FAIL"]


def test_load_reads_json(tmp_path):
    p = tmp_path / "x.json"
    p.write_text('{"k": 1}', encoding="utf-8")
    assert pilot.load(p) == {"k": 1}


def test_all_checks_pass(tmp_path, monkeypatch, capsys):
    code, receipt, summary = _run(tmp_path, monkeypatch, capsys)
    assert code is None
    assert receipt["result"] == "PASS"
    assert _failed(receipt) == []
    assert len(receipt["checks"]) == 11
    assert receipt["frontier_disposition"] == "PILOT_CONTROL_READY"
    assert receipt["next_frontier_action"] == "CONTROL_RECURRENCE_ONLY"
    assert receipt["target_repository"] == "GBOGEB/target"
    assert receipt["gm_iv_state"] == receipt["mission_state"] == "ACTIVE_8_OF_8"
    assert receipt["gm_v_state"] == "HELD"
    assert (receipt["repo"], receipt["source_sha"], receipt["run_id"]) == ("LOCAL", "UNKNOWN", "LOCAL")
    assert receipt["runtime"] == _runtime()
    assert summary == {
        "result": "PASS",
        "frontier_disposition": "PILOT_CONTROL_READY",
        "mission_promotion": "WITHHELD_FROM_F01_RECURRENCE__CURRENT_STAGE_MAY_HAVE_BEEN_PROMOTED_SEPARATELY",
        "historical_evidence_stage": "STAGED_ACTIVE_RECON_2_OF_8",
        "current_mission_state": "ACTIVE_8_OF_8",
        "source_sha": "UNKNOWN",
        "target_sha": TARGET_SHA,
    }


def test_env_identity(tmp_path, monkeypatch, capsys):
    _, receipt, _ = _run(tmp_path, monkeypatch, capsys, env={
        "GITHUB_REPOSITORY": "o/r", "GITHUB_SHA": "g", "SOURCE_SHA": "s", "GITHUB_RUN_ID": "9"})
    assert (receipt["repo"], receipt["source_sha"], receipt["run_id"]) == ("o/r", "s", "9")


@pytest.mark.parametrize("runtime,check", [
    (_runtime(target_sha="e" * 40), "01_exact_target_sha"),
    (_runtime(positive_exit_code=2), "02_positive_validator_pass"),
    (_runtime(positive_pass_marker=False), "02_positive_validator_pass"),
    (_runtime(positive_validated_surface_count=3), "03_positive_surfaces"),
    (_runtime(negative_exit_code=0), "04_negative_authority_probe_rejected"),
    (_runtime(negative_rejection_marker=False), "04_negative_authority_probe_rejected"),
    (_runtime(target_dirty_file_count=1), "05_target_checkout_clean"),
    (_runtime(positive_output_sha256="abc"), "06_output_digest_bound"),
    (_runtime(positive_output_sha256=None), "06_output_digest_bound"),
])
def test_runtime_failures(tmp_path, monkeypatch, capsys, runtime, check):
    code, receipt, summary = _run(tmp_path, monkeypatch, capsys, runtime=runtime)
    assert code == 1
    assert _failed(receipt) == [check]
    assert receipt["frontier_disposition"] == "PILOT_WITHHELD"
    assert receipt["next_frontier_action"] == "ROUTE_FIRST_RED"
    assert summary["result"] == "FAIL"


def test_missing_runtime_fields_use_defaults(tmp_path, monkeypatch, capsys):
    code, receipt, _ = _run(tmp_path, monkeypatch, capsys, runtime={"target_sha": TARGET_SHA})
    assert code == 1
    assert _failed(receipt) == [
        "02_positive_validator_pass", "03_positive_surfaces", "04_negative_authority_probe_rejected",
        "05_target_checkout_clean", "06_output_digest_bound"]


@pytest.mark.parametrize("kwargs,check", [
    ({"registry": _registry(gm_iv_state="DORMANT")}, "07_historical_stage_preserved_current_stage_not_regressed"),
    ({"registry": _registry(gm_iv_children=["c"])}, "07_historical_stage_preserved_current_stage_not_regressed"),
    ({"contract": _contract(mission_state_must_remain="ACTIVE_8_OF_8")},
     "07_historical_stage_preserved_current_stage_not_regressed"),
    ({"registry": _registry(gm_v_state="ACTIVE")}, "08_gm_v_held"),
    ({"registry": _registry(gm_v_children=["c"])}, "08_gm_v_held"),
    ({"contract": _contract(f02_state="PILOT")}, "09_f02_reference_only"),
    ({"contract": _contract(authority_transfer=True)}, "10_no_authority_or_child_transfer"),
    ({"contract": _contract(children_bound=True)}, "10_no_authority_or_child_transfer"),
    ({"rex": _rex(ids=("REX-OTHER",))}, "11_ring1_rex_assimilated"),
    ({"rex": {}}, "11_ring1_rex_assimilated"),
])
def test_governance_failures(tmp_path, monkeypatch, capsys, kwargs, check):
    code, receipt, _ = _run(tmp_path, monkeypatch, capsys, **kwargs)
    assert code == 1
    assert _failed(receipt) == [check]


@pytest.mark.parametrize("state", [
    "STAGED_ACTIVE_RECON_2_OF_8", "STAGED_ACTIVE_PILOT_2_OF_8", "STAGED_ACTIVE_RECON_4_OF_8"])
def test_forward_states_allowed(tmp_path, monkeypatch, capsys, state):
    code, receipt, _ = _run(tmp_path, monkeypatch, capsys, registry=_registry(gm_iv_state=state))
    assert code is None
    assert receipt["gm_iv_state"] == state


def test_real_committed_contract_registry_rex_via_main_guard(tmp_path, monkeypatch, capsys):
    """Offline entry-point run against committed registry, F01 contract and ring-1 REX."""
    contract = json.loads((MOD_DIR / "GM_IV_F01_PILOT_CONTRACT.json").read_text(encoding="utf-8"))
    for k in ENV_KEYS:
        monkeypatch.delenv(k, raising=False)
    argv, out_p = _write_runtime(tmp_path, _runtime(target_sha=contract["target"]["source_sha"]))
    monkeypatch.setattr(sys, "argv", argv)
    runpy.run_path(str(MOD_PATH), run_name="__main__")
    receipt = json.loads(out_p.read_text(encoding="utf-8"))
    assert receipt["result"] == "PASS"
    assert receipt["target_repository"] == contract["target"]["repository"]
    assert receipt["gm_v_state"] == "HELD"
