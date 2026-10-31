"""Behavioural tests for mission-control/grand-missions/assess_gm_iv_f03_pilot.py."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GM_DIR = REPO_ROOT / "mission-control" / "grand-missions"
MOD_PATH = GM_DIR / "assess_gm_iv_f03_pilot.py"
TARGET = "1eba2240a86d1fd2bd6375e2fac481caf645cdde"


def _load():
    spec = importlib.util.spec_from_file_location("cw_assess_gm_iv_f03_pilot", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def mod():
    return _load()


def _contract():
    return {
        "wave": "W",
        "target": {"source_sha": TARGET},
        "authority_transfer": False,
        "children_bound": False,
        "mission_state_must_remain": "STAGED_ACTIVE_RECON_2_OF_8",
        "existing_controlled_pilot": "GM-IV-F01",
        "f04_state": "REFERENCE",
    }


def _runtime():
    return {
        "target_sha": TARGET,
        "run1_code_cells": 3,
        "run2_code_cells": 3,
        "total_error_count": 0,
        "run1_digest": "d1",
        "run2_digest": "d1",
        "target_dirty_count": 0,
        "gm_v_state": "HELD",
    }


def _boundary():
    return {
        "positive_exit_code": 0,
        "positive_marker_count": 5,
        "negative_exit_code": 1,
        "negative_rejection_observed": True,
        "target_repository_modified": False,
    }


def _registry(gm4_state="STAGED_ACTIVE_RECON_2_OF_8", gm4_children=None, gm5_state="HELD"):
    return {"grand_missions": [
        {"id": "GM-IV", "state": gm4_state, "children": [] if gm4_children is None else gm4_children},
        {"id": "GM-V", "state": gm5_state, "children": []},
    ]}


def _run(mod, monkeypatch, tmp_path, contract, runtime, boundary, registry=None, contract_path=None):
    paths = {}
    for name, obj in (("contract", contract), ("runtime", runtime), ("boundary", boundary)):
        p = tmp_path / (name + ".json")
        p.write_text(json.dumps(obj), encoding="utf-8")
        paths[name] = p
    if contract_path is not None:
        paths["contract"] = contract_path
    if registry is not None:
        reg = tmp_path / "registry.json"
        reg.write_text(json.dumps(registry), encoding="utf-8")
        monkeypatch.setattr(mod, "REGISTRY", reg)
    out = tmp_path / "receipt.json"
    monkeypatch.setattr(sys, "argv", [
        "prog", "--contract", str(paths["contract"]), "--runtime", str(paths["runtime"]),
        "--boundary", str(paths["boundary"]), "--source-sha", "src", "--out", str(out),
    ])
    return paths, out


def test_sha256_file_matches_hashlib(mod, tmp_path):
    p = tmp_path / "blob.bin"
    payload = b"a" * 70000 + b"tail"
    p.write_bytes(payload)
    assert mod.sha256_file(p) == hashlib.sha256(payload).hexdigest()


def test_load_accepts_path_and_str(mod, tmp_path):
    p = tmp_path / "x.json"
    p.write_text('{"a": 1}', encoding="utf-8")
    assert mod.load(p) == mod.load(str(p)) == {"a": 1}


@pytest.mark.parametrize("state", [
    "STAGED_ACTIVE_RECON_2_OF_8", "STAGED_ACTIVE_PILOT_2_OF_8", "STAGED_ACTIVE_RECON_4_OF_8", "ACTIVE_8_OF_8",
])
def test_pass_for_every_allowed_forward_state(mod, monkeypatch, tmp_path, capsys, state):
    paths, out = _run(mod, monkeypatch, tmp_path, _contract(), _runtime(), _boundary(), _registry(state))
    assert mod.main() is None
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["result"] == "PASS"
    assert receipt["frontier_disposition"] == "PILOT_CONTROL_READY"
    assert all(receipt["checks"].values()) and len(receipt["checks"]) == 14
    assert receipt["mission_state"] == state
    assert receipt["target_sha"] == TARGET and receipt["source_sha"] == "src"
    assert receipt["wave"] == "W"
    assert receipt["input_digests"] == {k: mod.sha256_file(v) for k, v in paths.items()}
    assert json.loads(capsys.readouterr().out) == receipt


def _fail(mod, monkeypatch, tmp_path, contract, runtime, boundary, registry):
    _, out = _run(mod, monkeypatch, tmp_path, contract, runtime, boundary, registry)
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 1
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["result"] == "FAIL"
    assert receipt["frontier_disposition"] == "PILOT_NOT_READY"
    return sorted(k for k, v in receipt["checks"].items() if not v)


@pytest.mark.parametrize(
    "which, key, value, failing",
    [
        ("runtime", "target_sha", "other", ["01_exact_target_sha"]),
        ("boundary", "positive_exit_code", 2, ["02_positive_boundary_pass"]),
        ("boundary", "positive_marker_count", 4, ["03_positive_boundary_markers"]),
        ("runtime", "run1_code_cells", 0, ["04_gt0_cells_run1"]),
        ("runtime", "run2_code_cells", 0, ["05_gt0_cells_run2"]),
        ("runtime", "total_error_count", 1, ["06_zero_errors"]),
        ("runtime", "run2_digest", "d2", ["07_repeat_digest_equal"]),
        ("boundary", "negative_rejection_observed", False, ["08_negative_authority_rejected"]),
        ("boundary", "negative_exit_code", 0, ["08_negative_authority_rejected"]),
        ("boundary", "target_repository_modified", True, ["09_target_unmodified"]),
        ("contract", "children_bound", True, ["10_no_authority_transfer"]),
        ("contract", "mission_state_must_remain", "ACTIVE_8_OF_8",
         ["11_historical_stage_preserved_current_stage_not_regressed"]),
        ("contract", "existing_controlled_pilot", "GM-IV-F02", ["12_f01_independent_control_exists"]),
        ("contract", "f04_state", "PILOT", ["13_f04_reference"]),
        ("runtime", "gm_v_state", "ACTIVE", ["14_gm_v_held"]),
    ],
)
def test_single_check_failure(mod, monkeypatch, tmp_path, which, key, value, failing):
    objs = {"contract": _contract(), "runtime": _runtime(), "boundary": _boundary()}
    objs[which][key] = value
    got = _fail(mod, monkeypatch, tmp_path, objs["contract"], objs["runtime"], objs["boundary"], _registry())
    assert got == failing


def test_regressed_or_unknown_state_fails_check_11(mod, monkeypatch, tmp_path):
    got = _fail(mod, monkeypatch, tmp_path, _contract(), _runtime(), _boundary(), _registry("HELD"))
    assert got == ["11_historical_stage_preserved_current_stage_not_regressed"]


def test_children_bound_fails_check_11(mod, monkeypatch, tmp_path):
    got = _fail(mod, monkeypatch, tmp_path, _contract(), _runtime(), _boundary(), _registry(gm4_children=["c"]))
    assert got == ["11_historical_stage_preserved_current_stage_not_regressed"]


def test_registry_gm_v_not_held_fails_check_14(mod, monkeypatch, tmp_path):
    got = _fail(mod, monkeypatch, tmp_path, _contract(), _runtime(), _boundary(), _registry(gm5_state="ACTIVE"))
    assert got == ["14_gm_v_held"]


def test_empty_runtime_and_boundary_use_fail_closed_defaults(mod, monkeypatch, tmp_path):
    got = _fail(mod, monkeypatch, tmp_path, _contract(), {}, {}, _registry())
    assert got == sorted([
        "01_exact_target_sha", "02_positive_boundary_pass", "03_positive_boundary_markers",
        "04_gt0_cells_run1", "05_gt0_cells_run2", "06_zero_errors", "07_repeat_digest_equal",
        "08_negative_authority_rejected", "09_target_unmodified", "14_gm_v_held",
    ])


def test_empty_digests_do_not_count_as_repeat(mod, monkeypatch, tmp_path):
    rt = _runtime()
    rt["run1_digest"] = rt["run2_digest"] = ""
    got = _fail(mod, monkeypatch, tmp_path, _contract(), rt, _boundary(), _registry())
    assert got == ["07_repeat_digest_equal"]


def test_real_contract_and_registry_pass_with_synthetic_runtime(mod, monkeypatch, tmp_path):
    # Real committed F03 contract + real registry (GM-IV now ACTIVE_8_OF_8, an allowed
    # forward state); runtime/boundary receipts are synthetic as they are CI artifacts.
    real_contract = GM_DIR / "GM_IV_F03_PILOT_CONTRACT.json"
    _, out = _run(mod, monkeypatch, tmp_path, {}, _runtime(), _boundary(), contract_path=real_contract)
    mod.main()
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["result"] == "PASS"
    assert receipt["wave"] == "GM-FLEET-03-F03-PILOT"
