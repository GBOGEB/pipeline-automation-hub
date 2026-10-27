"""Behavioural tests for mission-control/grand-missions/validate_gm_v_3pstar_mip_control.py."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GM_DIR = REPO_ROOT / "mission-control" / "grand-missions"
MOD_PATH = GM_DIR / "validate_gm_v_3pstar_mip_control.py"
INPUTS = (
    "GM_V_3PSTAR_MIP_CONTROL_v1.json",
    "GM_V_CURRENT_v1.json",
    "GRAND_MISSION_REGISTRY.json",
    "GM_V_GOVERNOR_READINESS_CONTRACT.json",
)
EXPECTED_OUTPUTS = [
    "mission-control/grand-missions/GM_V_CURRENT_v1.json",
    "mission-control/grand-missions/GM_V_3PSTAR_MIP_CONTROL_v1.json",
    "mission-control/grand-missions/validate_gm_v_3pstar_mip_control.py",
    "mission-control/grand-missions/handover/SC_2026-09-18_GM_V_3PSTAR_MIP_LOSSLESS_HANDOVER_v1.md",
    "mission-control/grand-missions/handover/RESTART_DROPIN_2026-09-18_GM_V_v1.md",
    ".github/workflows/gm-v-3pstar-mip-control.yml",
    "mission-control/grand-missions/handover/SC_2026-09-18_GM_V_3PSTAR_MIP_LOSSLESS_HANDOVER_v2.md",
    "mission-control/grand-missions/handover/RESTART_DROPIN_2026-09-18_GM_V_v2.md",
]
QPS_MAIN = "eeac2b60fc16e5b2131d4054f95da0b0c663cc40"
CLASSIFICATION = "INFRA_PREEXECUTION_ZERO_STEP / RUNNER_ADMISSION"


def _load():
    spec = importlib.util.spec_from_file_location("cw_validate_gm_v_3pstar_mip_control", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def mod():
    return _load()


def _real_inputs():
    return {n: json.loads((GM_DIR / n).read_text(encoding="utf-8")) for n in INPUTS}


def _passing_inputs():
    """Real committed inputs repaired so every check of the stage holds."""
    data = _real_inputs()
    control = data["GM_V_3PSTAR_MIP_CONTROL_v1.json"]
    current = data["GM_V_CURRENT_v1.json"]
    control["mip"]["Modernize"]["result"] = "PASS"
    control["mip"]["Innovate"]["result"] = "PASS"
    control["mip"]["Perpetuate"]["result"] = "THIS_TRANSACTION"
    control["mip"]["Perpetuate"]["required_outputs"] = list(EXPECTED_OUTPUTS)
    control["latest_iteration"]["mip"]["Perpetuate"] = "PASS_HANDOVER_V2_ZERO_CHAT_ONLY_STATE"
    control["latest_iteration"]["qps_probe_was_retriggered"] = False
    control["latest_iteration"]["three_pr"]["Probe"] = "PASS_BLOCK_CONFIRMED_FROM_EXISTING_RUNS_NO_RERUN"
    control["source_authority"]["qps_main_at_refresh"] = QPS_MAIN
    gate = current["child_runtime_gate"]
    gate.update(issue=923, issue_state="OPEN", classification=CLASSIFICATION, refreshed_main=QPS_MAIN)
    control["lineage"]["latest_qps_runtime_observation"] = copy.deepcopy(gate["latest_observation"])
    current["progression"]["three_pc_prove"] = "WITHHELD_EXTERNAL"
    current["missioncontrol"]["handover"] = "handover/X_v2.md"
    current["missioncontrol"]["restart"] = "handover/Y_v2.md"
    return data


def _write_env(tmp_path, data, make_outputs=True):
    repo = tmp_path / "repo"
    root = repo / "mission-control" / "grand-missions"
    root.mkdir(parents=True)
    for name, obj in data.items():
        (root / name).write_text(json.dumps(obj), encoding="utf-8")
    if make_outputs:
        for rel in EXPECTED_OUTPUTS:
            p = repo / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            if not p.exists():
                p.write_text("x", encoding="utf-8")
    return root


def _run(mod, monkeypatch, root, out):
    monkeypatch.setattr(mod, "ROOT", root)
    monkeypatch.setattr(sys, "argv", ["prog", "--source-sha", "abc123", "--out", str(out)])
    return mod.main()


def test_canon_sha256_is_key_order_independent(mod):
    a = mod.canon_sha256({"b": 1, "a": [1, 2]})
    b = mod.canon_sha256({"a": [1, 2], "b": 1})
    assert a == b
    assert a == hashlib.sha256(b'{"a":[1,2],"b":1}').hexdigest()
    assert mod.canon_sha256({"a": 1}) != mod.canon_sha256({"a": 2})


def test_load_reads_json_relative_to_root(mod, monkeypatch, tmp_path):
    (tmp_path / "x.json").write_text('{"k": 5}', encoding="utf-8")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    assert mod.load("x.json") == {"k": 5}


def test_all_checks_pass_writes_receipt(mod, monkeypatch, tmp_path, capsys):
    data = _passing_inputs()
    root = _write_env(tmp_path, data)
    out = tmp_path / "receipt.json"
    assert _run(mod, monkeypatch, root, out) == 0
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["result"] == "PASS_GM_V_3PSTAR_MIP_CONTROL"
    assert receipt["check_count"] == 18
    assert all(receipt["checks"].values())
    assert receipt["source_sha"] == "abc123"
    assert receipt["latest_qps_probe_all_zero_step"] is True
    assert receipt["authority_transfer"] is False
    assert receipt["formal_credit_delta"] == 0
    assert receipt["input_digest_sha256"] == mod.canon_sha256({
        "control": data["GM_V_3PSTAR_MIP_CONTROL_v1.json"],
        "current": data["GM_V_CURRENT_v1.json"],
        "registry": data["GRAND_MISSION_REGISTRY.json"],
        "governor": data["GM_V_GOVERNOR_READINESS_CONTRACT.json"],
    })
    assert json.loads(capsys.readouterr().out) == receipt


def _mut_current(key_path, value):
    def apply(data):
        obj = data["GM_V_CURRENT_v1.json"]
        for k in key_path[:-1]:
            obj = obj[k]
        obj[key_path[-1]] = value
    return apply


def _mut_control(key_path, value):
    def apply(data):
        obj = data["GM_V_3PSTAR_MIP_CONTROL_v1.json"]
        for k in key_path[:-1]:
            obj = obj[k]
        obj[key_path[-1]] = value
    return apply


def _mut_gm(mid, key, value):
    def apply(data):
        for m in data["GRAND_MISSION_REGISTRY.json"]["grand_missions"]:
            if m["id"] == mid:
                m[key] = value
    return apply


def _mut_jobs_steps(data):
    data["GM_V_CURRENT_v1.json"]["child_runtime_gate"]["latest_observation"]["release_runner_probe"]["jobs"][0]["executed_steps"] = 3


def _mut_governor(data):
    data["GM_V_GOVERNOR_READINESS_CONTRACT.json"]["decision_semantics"]["WITHHOLD"] = "OTHER"


def _mut_registry_authority(data):
    data["GRAND_MISSION_REGISTRY.json"]["authority_transfer"] = True


@pytest.mark.parametrize(
    "mutate, failing",
    [
        (_mut_current(["canonical"], False), {"01_current_pointer_canonical"}),
        (_mut_gm("GM-IV", "children", ["c"]), {"02_gm_iv_active8"}),
        (_mut_gm("GM-V", "crew_posture", "ALLOCATED"), {"03_gm_v_held_unallocated"}),
        (_mut_current(["gm_iv", "concurrency_capacity_claimed"], True), {"04_runtime_capacity_boundary"}),
        (_mut_governor, {"05_governor_withhold_boundary"}),
        (_mut_control(["three_pr", "Rank", "result"], "FAIL"), {"06_three_pr_complete"}),
        (_mut_control(["mip", "Innovate", "result"], "FAIL"), {"07_mip_progression"}),
        (_mut_control(["three_pc", "Prove", "result"], "PASS"), {"08_three_pc_boundary"}),
        (_mut_control(["three_p3", "authorized"], True), {"09_three_p3_not_authorized"}),
        (_mut_control(["source_authority", "qps_main_at_refresh"], "0" * 40), {"10_qps_gate_bound"}),
        (_mut_control(["lineage", "gm_v_readiness", "postmerge_run_id"], 1), {"11_exact_receipt_lineage"}),
        (_mut_current(["chat_only_decision_count"], 1), {"12_no_chat_only_state"}),
        (_mut_registry_authority, {"13_no_authority_or_credit"}),
        (_mut_control(["three_pr", "Rank", "no_blind_rerun"], False), {"14_reentry_is_owner_change_first"}),
        (_mut_jobs_steps, {"16_latest_qps_observation_exact"}),
        (_mut_control(["latest_iteration", "qps_probe_was_retriggered"], True), {"17_w281_rebind_is_noncompensating"}),
        (_mut_current(["missioncontrol", "restart"], "restart_v1.md"), {"18_v2_restart_bound"}),
    ],
)
def test_single_check_failure_fails_receipt(mod, monkeypatch, tmp_path, mutate, failing):
    data = _passing_inputs()
    mutate(data)
    root = _write_env(tmp_path, data)
    out = tmp_path / "r.json"
    assert _run(mod, monkeypatch, root, out) == 1
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["result"] == "FAIL_GM_V_3PSTAR_MIP_CONTROL"
    assert {k for k, v in receipt["checks"].items() if not v} == failing


def test_missing_perpetuate_output_file_fails_check_15(mod, monkeypatch, tmp_path):
    root = _write_env(tmp_path, _passing_inputs(), make_outputs=False)
    out = tmp_path / "r.json"
    assert _run(mod, monkeypatch, root, out) == 1
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert [k for k, v in receipt["checks"].items() if not v] == ["15_perpetuate_outputs_exact_and_exist"]


def test_duplicate_required_output_fails_check_15(mod, monkeypatch, tmp_path):
    data = _passing_inputs()
    data["GM_V_3PSTAR_MIP_CONTROL_v1.json"]["mip"]["Perpetuate"]["required_outputs"].append(EXPECTED_OUTPUTS[0])
    root = _write_env(tmp_path, data)
    out = tmp_path / "r.json"
    assert _run(mod, monkeypatch, root, out) == 1
    assert json.loads(out.read_text(encoding="utf-8"))["checks"]["15_perpetuate_outputs_exact_and_exist"] is False


def test_real_committed_data_current_outcome(mod, monkeypatch, tmp_path):
    # The GM-V control stage has been superseded by later rebinds (the control now
    # records PASS_THIS_TRANSACTION and a newer QPS refresh), so the committed data
    # no longer satisfies this stage's exact checks. Assert the actual outcome.
    out = tmp_path / "real.json"
    monkeypatch.setattr(sys, "argv", ["prog", "--source-sha", "real", "--out", str(out)])
    assert mod.main() == 1
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["result"] == "FAIL_GM_V_3PSTAR_MIP_CONTROL"
    assert receipt["gm_v_state"] == "HELD"
    assert receipt["checks"]["07_mip_progression"] is False
    assert receipt["checks"]["01_current_pointer_canonical"] is True
