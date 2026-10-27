"""Behavioural tests for mission-control/grand-missions/validate_gm_iv_active8_promotion.py."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GM_DIR = REPO_ROOT / "mission-control" / "grand-missions"
MOD_PATH = GM_DIR / "validate_gm_iv_active8_promotion.py"
CONTRACT = "GM_IV_ACTIVE8_PROMOTION_CONTRACT.json"
READINESS = "GM_IV_ACTIVE8_GOVERNOR_CONTRACT.json"
REG = "GRAND_MISSION_REGISTRY.json"
CITY = "MISSION_CITY_GRAPH.json"
ECON = "GM_IV_EVIDENCE_ECONOMICS.json"
NAMES = (CONTRACT, READINESS, REG, CITY, ECON)


def _load():
    if str(GM_DIR) not in sys.path:
        sys.path.insert(0, str(GM_DIR))
    spec = importlib.util.spec_from_file_location("cw_validate_gm_iv_active8_promotion", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def mod():
    return _load()


def _inputs():
    return {n: json.loads((GM_DIR / n).read_text(encoding="utf-8")) for n in NAMES}


def _run(mod, monkeypatch, tmp_path, data):
    root = tmp_path / "gm"
    root.mkdir()
    for n, obj in data.items():
        (root / n).write_text(json.dumps(obj), encoding="utf-8")
    monkeypatch.setattr(mod, "ROOT", root)
    out = tmp_path / "nested" / "dir" / "receipt.json"
    monkeypatch.setattr(sys, "argv", ["prog", "--source-sha", "sha-x", "--out", str(out)])
    rc = mod.main()
    return rc, json.loads(out.read_text(encoding="utf-8"))


def test_digest_is_canonical(mod):
    assert mod.digest({"b": 2, "a": 1}) == mod.digest({"a": 1, "b": 2})
    assert mod.digest([1]) == hashlib.sha256(b"[1]").hexdigest()


def test_pass_receipt_creates_parent_dirs(mod, monkeypatch, tmp_path, capsys):
    data = _inputs()
    rc, receipt = _run(mod, monkeypatch, tmp_path, data)
    assert rc == 0
    assert receipt["result"] == "PASS_GM_IV_ACTIVE8_PROMOTION"
    assert receipt["check_count"] == 13 and all(receipt["checks"].values())
    assert receipt["current_state"] == "ACTIVE_8_OF_8"
    assert receipt["wave"] == data[CONTRACT]["wave"]
    assert receipt["source_sha"] == "sha-x"
    assert receipt["accepted_readiness_evidence"] == data[CONTRACT]["accepted_readiness_evidence"]
    assert receipt["gm_v_launch_authorized"] is False
    assert receipt["input_digest_sha256"] == mod.digest({
        "contract": data[CONTRACT], "readiness": data[READINESS], "registry": data[REG],
        "city": data[CITY], "economics": data[ECON],
    })
    assert json.loads(capsys.readouterr().out) == receipt


def _set(name, path, value):
    def apply(data):
        obj = data[name]
        for k in path[:-1]:
            obj = obj[k]
        obj[path[-1]] = value
    return apply


def _gm(mid, key, value):
    def apply(data):
        for m in data[REG]["grand_missions"]:
            if m["id"] == mid:
                m[key] = value
    return apply


def _drop_edge(data):
    data[CITY]["edges"] = [e for e in data[CITY]["edges"] if tuple(e) != ("FLEET_POOL", "GM-IV", "SCOUT_ACTIVE_8_CONTROLLED")]


def _break_active8_evidence_both(data):
    # Changing the evidence in both the contract and the registry keeps them equal
    # but makes the generic fleet validator reject it.
    data[CONTRACT]["accepted_readiness_evidence"]["workflow_run_id"] = 1
    for m in data[REG]["grand_missions"]:
        if m["id"] == "GM-IV":
            m["active_8_of_8_evidence"]["workflow_run_id"] = 1


def _drop_recon4(data):
    for m in data[REG]["grand_missions"]:
        if m["id"] == "GM-IV":
            m.pop("recon_4_of_8_evidence", None)


@pytest.mark.parametrize(
    "mutate, failing",
    [
        (_set(CONTRACT, ["mission_id"], "GM-V"), {"01_contract_identity"}),
        (_set(READINESS, ["proposed_to_state"], "X"), {"02_readiness_evidence_exact"}),
        (_gm("GM-IV", "frontier_count", 7), {"03_registry_active8_state"}),
        (_set(CONTRACT, ["required_shape", "children"], ["c"]), {"04_exact_eight_frontier_shape"}),
        (_drop_recon4, {"06_recon4_evidence_retained", "09_generic_fleet_accepts_exact_active8"}),
        (_drop_edge, {"08_mission_city_synchronized"}),
        (_set(ECON, ["fleet_invariant", "canonical_children_bound"], 1), {"10_evidence_economics_synchronized"}),
        (_set(ECON, ["bt_gate", "state"], "FIT"), {"11_local_models_still_fail_closed"}),
        (_set(READINESS, ["children_bound"], True), {"12_no_authority_or_child_binding"}),
        (_gm("GM-V", "launch_gate", "NONE"), {"13_gm_v_held_separate_gate"}),
    ],
)
def test_single_check_failure(mod, monkeypatch, tmp_path, mutate, failing):
    data = _inputs()
    mutate(data)
    rc, receipt = _run(mod, monkeypatch, tmp_path, data)
    assert rc == 1
    assert receipt["result"] == "FAIL_GM_IV_ACTIVE8_PROMOTION"
    assert {k for k, v in receipt["checks"].items() if not v} == failing


def test_registry_evidence_mismatch_fails_check_05(mod, monkeypatch, tmp_path):
    data = _inputs()
    _gm("GM-IV", "active_8_of_8_evidence", {"source_sha": "other"})(data)
    rc, receipt = _run(mod, monkeypatch, tmp_path, data)
    assert rc == 1
    assert receipt["checks"]["05_exact_active8_evidence_bound"] is False


def test_evidence_rejected_by_fleet_validator(mod, monkeypatch, tmp_path):
    data = _inputs()
    _break_active8_evidence_both(data)
    rc, receipt = _run(mod, monkeypatch, tmp_path, data)
    assert rc == 1
    assert receipt["checks"]["02_readiness_evidence_exact"] is False
    assert receipt["checks"]["05_exact_active8_evidence_bound"] is False


def test_children_bound_fails_shape_and_generic_fleet(mod, monkeypatch, tmp_path):
    data = _inputs()
    _gm("GM-IV", "children", ["CHILD"])(data)
    rc, receipt = _run(mod, monkeypatch, tmp_path, data)
    assert rc == 1
    failing = {k for k, v in receipt["checks"].items() if not v}
    assert {"04_exact_eight_frontier_shape", "12_no_authority_or_child_binding"} <= failing


def test_real_committed_data_passes(mod, monkeypatch, tmp_path):
    out = tmp_path / "real.json"
    monkeypatch.setattr(sys, "argv", ["prog", "--source-sha", "real", "--out", str(out)])
    assert mod.main() == 0
    assert json.loads(out.read_text(encoding="utf-8"))["result"] == "PASS_GM_IV_ACTIVE8_PROMOTION"
