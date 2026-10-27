"""Behavioural tests for mission-control/grand-missions/assess_gm_iv_pilot2_governor.py."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GM_DIR = REPO_ROOT / "mission-control" / "grand-missions"
MOD_PATH = GM_DIR / "assess_gm_iv_pilot2_governor.py"
CONTRACT = "GM_IV_PILOT2_GOVERNOR_CONTRACT.json"
REG = "GRAND_MISSION_REGISTRY.json"
CITY = "MISSION_CITY_GRAPH.json"
ECON = "GM_IV_EVIDENCE_ECONOMICS.json"
NAMES = (CONTRACT, REG, CITY, ECON)


def _load():
    spec = importlib.util.spec_from_file_location("cw_assess_gm_iv_pilot2_governor", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def mod(monkeypatch):
    monkeypatch.delenv("SOURCE_SHA", raising=False)
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    return _load()


def _gm4(data):
    return next(m for m in data[REG]["grand_missions"] if m["id"] == "GM-IV")


def _pilot2_inputs():
    """Real inputs rewound to the PILOT_2_OF_8 stage this governor assessed."""
    data = {n: json.loads((GM_DIR / n).read_text(encoding="utf-8")) for n in NAMES}
    gm4 = _gm4(data)
    gm4.update(
        state=data[CONTRACT]["to_state"],
        activation_stage="PILOT_2_OF_8",
        controlled_pilot_frontiers=["GM-IV-F01", "GM-IV-F03"],
        reference_frontiers=["GM-IV-F02", "GM-IV-F04"],
        unfilled_frontier_slots=["GM-IV-F05", "GM-IV-F06", "GM-IV-F07", "GM-IV-F08"],
        children=[],
    )
    data[CITY]["mission_states"]["GM-IV"] = gm4["state"]
    data[ECON]["fleet_invariant"]["mission_stage"] = "PILOT_2_OF_8"
    data[ECON]["fleet_invariant"]["controlled_pilot_frontiers"] = ["GM-IV-F01", "GM-IV-F03"]
    return data


def _run(mod, monkeypatch, tmp_path, data):
    root = tmp_path / "gm"
    root.mkdir()
    for n, obj in data.items():
        (root / n).write_text(json.dumps(obj), encoding="utf-8")
    monkeypatch.setattr(mod, "HERE", root)
    out = tmp_path / "receipt.json"
    monkeypatch.setattr(sys, "argv", ["prog", "--out", str(out)])
    rc = mod.main()
    return rc, json.loads(out.read_text(encoding="utf-8"))


def test_digest_is_canonical(mod):
    assert mod.digest({"x": 1, "a": 2}) == mod.digest({"a": 2, "x": 1})
    assert len(mod.digest(None)) == 64


def test_pass_promotes_and_reports_local_sha(mod, monkeypatch, tmp_path, capsys):
    data = _pilot2_inputs()
    rc, receipt = _run(mod, monkeypatch, tmp_path, data)
    assert rc == 0
    assert receipt["result"] == "PASS"
    assert receipt["promotion_decision"] == "PROMOTE_PILOT_2_OF_8"
    assert receipt["source_sha"] == "LOCAL"
    assert len(receipt["checks"]) == 13
    assert all(c["result"] == "PASS" for c in receipt["checks"])
    assert receipt["mission_state"] == "STAGED_ACTIVE_PILOT_2_OF_8"
    assert receipt["controlled_pilot_frontiers"] == ["GM-IV-F01", "GM-IV-F03"]
    assert receipt["input_digest_sha256"] == mod.digest(
        {"contract": data[CONTRACT], "registry": data[REG], "city": data[CITY], "economics": data[ECON]}
    )
    summary = json.loads(capsys.readouterr().out)
    assert summary == {
        "result": "PASS",
        "promotion_decision": "PROMOTE_PILOT_2_OF_8",
        "source_sha": "LOCAL",
        "next_stage": "WITHHELD_PENDING_SEPARATE_RECON_4_OF_8_GOVERNOR_GATE",
    }


def test_source_sha_env_precedence(mod, monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_SHA", "gh-sha")
    (tmp_path / "a").mkdir()
    rc, receipt = _run(mod, monkeypatch, tmp_path / "a", _pilot2_inputs())
    assert rc == 0
    assert receipt["source_sha"] == "gh-sha"
    monkeypatch.setenv("SOURCE_SHA", "src-sha")
    (tmp_path / "b").mkdir()
    rc, receipt = _run(mod, monkeypatch, tmp_path / "b", _pilot2_inputs())
    assert receipt["source_sha"] == "src-sha"


def _set(name, path, value):
    def apply(data):
        obj = data[name]
        for k in path[:-1]:
            obj = obj[k]
        obj[path[-1]] = value
    return apply


def _gm4_set(key, value):
    def apply(data):
        _gm4(data)[key] = value
    return apply


def _gm5_state(data):
    next(m for m in data[REG]["grand_missions"] if m["id"] == "GM-V")["state"] = "ACTIVE"


def _pilot_disposition(data):
    data[CONTRACT]["controlled_pilots"]["GM-IV-F03"]["disposition"] = "RECON"


@pytest.mark.parametrize(
    "mutate, failing",
    [
        (_set(CONTRACT, ["from_state"], "X"), ["01_contract_transition"]),
        (_pilot_disposition, ["02_two_independent_controlled_pilots"]),
        (_set(CONTRACT, ["controlled_pilots", "GM-IV-F01", "workflow_run_id"], 1), ["03_f01_master_control_bound"]),
        (_set(CONTRACT, ["controlled_pilots", "GM-IV-F03", "artifact_digest"], "sha256:0"), ["04_f03_master_control_bound"]),
        (_set(CONTRACT, ["reference_frontiers", "GM-IV-F02", "disposition"], "PILOT"), ["05_reference_pair_bounded"]),
        (_gm4_set("activation_stage", "RECON_2_OF_8"), ["06_registry_pilot_shape"]),
        (_set(CONTRACT, ["children_bound"], True), ["07_zero_children"]),
        (_set(ECON, ["authority_transfer"], True), ["08_no_authority_transfer"]),
        (_set(CITY, ["mission_states", "GM-IV"], "OTHER"), ["09_mission_city_sync"]),
        (_set(ECON, ["fleet_invariant", "mission_stage"], "RECON_2_OF_8"), ["10_evidence_economics_sync"]),
        (_set(ECON, ["pca_gate", "state"], "FIT"), ["11_local_pca_bt_fail_closed"]),
        (_gm5_state, ["12_gm_v_held"]),
        (_set(CONTRACT, ["next_stage_boundary"], "AUTHORIZES_EVERYTHING"), ["13_next_stage_withheld"]),
    ],
)
def test_single_failed_check_withholds(mod, monkeypatch, tmp_path, mutate, failing):
    data = _pilot2_inputs()
    mutate(data)
    rc, receipt = _run(mod, monkeypatch, tmp_path, data)
    assert rc == 1
    assert receipt["result"] == "FAIL"
    assert receipt["promotion_decision"] == "WITHHOLD_PILOT_2_OF_8"
    assert [c["check"] for c in receipt["checks"] if c["result"] == "FAIL"] == failing


def test_real_committed_data_current_outcome(mod, monkeypatch, tmp_path):
    # GM-IV has since been promoted past PILOT_2_OF_8 (now ACTIVE_8_OF_8), so this
    # historical governor now withholds on the registry and economics shape checks.
    out = tmp_path / "real.json"
    monkeypatch.setattr(sys, "argv", ["prog", "--out", str(out)])
    assert mod.main() == 1
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["promotion_decision"] == "WITHHOLD_PILOT_2_OF_8"
    assert [c["check"] for c in receipt["checks"] if c["result"] == "FAIL"] == [
        "06_registry_pilot_shape",
        "10_evidence_economics_sync",
    ]
