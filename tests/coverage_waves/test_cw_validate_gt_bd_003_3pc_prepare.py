"""Behavioural tests for mission-control/golden-thread/validate_gt_bd_003_3pc_prepare.py."""
import copy
import importlib.util
import json
import runpy
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_DIR = REPO_ROOT / "mission-control" / "golden-thread"
MOD_PATH = MOD_DIR / "validate_gt_bd_003_3pc_prepare.py"


def _load():
    spec = importlib.util.spec_from_file_location("cw_validate_gt_bd_003_3pc_prepare", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gt = _load()
REAL = json.loads((MOD_DIR / "GT_BD_003_3PC_PREPARE_W250_v1.json").read_text(encoding="utf-8"))


def _run(tmp_path, monkeypatch, data):
    p = tmp_path / "control.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(gt, "CONTROL", p)
    return gt.main()


def test_require():
    gt.require(True, "unused")
    with pytest.raises(SystemExit) as exc:
        gt.require(False, "msg")
    assert exc.value.code == "FAIL: msg"


def test_real_committed_control_passes(capsys):
    assert gt.main() == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {
        "status": "PASS_GT_BD_003_3PC_PREPARE_ONLY",
        "prepare": "PASS",
        "prove": "WITHHELD_CHILD_ZERO_STEP",
        "commit_or_hold": "HOLD",
        "child_pr": 1438,
        "child_head": "0c88a8efe09ccf7cb0b11ecc19632a1191621524",
        "child_disposition": "DEFER",
        "authority_transfer": False,
        "qps_credit_delta": 0,
    }


def _m(path, value):
    d = copy.deepcopy(REAL)
    node = d
    for k in path[:-1]:
        node = node[k]
    node[path[-1]] = value
    return d


@pytest.mark.parametrize("path,value,message", [
    (["bd_item"], "GT-BD-002", "wrong BD item"),
    (["method"], "3PR", "wrong method"),
    (["state"], "PROVE_PASS", "unexpected state"),
    (["authority_transfer"], True, "authority transfer must remain false"),
    (["formal_credit_delta"], 1, "formal credit must remain zero"),
    (["qps_credit_delta"], 1, "QPS credit must remain zero"),
    (["real_child_target", "repo"], "GBOGEB/x", "wrong child repository"),
    (["real_child_target", "pr"], 1, "wrong child PR"),
    (["real_child_target", "exact_head_sha"], "0" * 40, "child head drift"),
    (["real_child_target", "source_gate_document_id"], "X", "source gate mismatch"),
    (["real_child_target", "source_gate_blob_sha1"], "0", "source gate blob mismatch"),
    (["real_child_target", "child_disposition"], "ACCEPT", "child disposition promoted without proof"),
    (["real_child_target", "child_reset_authority"], "ANY", "child reset authority drift"),
    (["child_hosted_attempt", "run_id"], 1, "run id mismatch"),
    (["child_hosted_attempt", "job_id"], 1, "job id mismatch"),
    (["child_hosted_attempt", "steps"], [], "zero-step evidence was rewritten"),
    (["child_hosted_attempt", "classification"], "APP", "wrong failure class"),
    (["child_hosted_attempt", "application_defect_evidence"], True, "zero-step may not become application evidence"),
    (["child_hosted_attempt", "repair_authorized_from_attempt"], True, "repair must remain unauthorized"),
    (["three_pc", "Prepare", "status"], "FAIL", "Prepare must pass"),
    (["three_pc", "Prove", "status"], "PASS", "Prove must remain withheld"),
    (["three_pc", "Commit_or_HOLD", "status"], "COMMIT", "Commit must remain on hold"),
    (["three_pc", "Prove", "release_conditions"], ["QPS_PR_1438_HOSTED_RUN_STEPS_GT_0"],
     "3PC Prove release conditions incomplete"),
])
def test_fail_closed(tmp_path, monkeypatch, capsys, path, value, message):
    with pytest.raises(SystemExit) as exc:
        _run(tmp_path, monkeypatch, _m(path, value))
    assert exc.value.code == "FAIL: " + message
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("item", [
    "ZERO_STEP_NE_APPLICATION_FAIL",
    "PARENT_PASS_NE_CHILD_ACCEPT",
    "MISSIONCONTROL_PASS_NE_QPS_GT_BDQ_PASS",
    "QPS_GT_BDQ_0_UNCHANGED",
    "AUTHORITY_TRANSFER_FALSE",
])
def test_missing_non_compensation_control(tmp_path, monkeypatch, item):
    d = copy.deepcopy(REAL)
    d["non_compensation"] = [x for x in d["non_compensation"] if x != item]
    with pytest.raises(SystemExit) as exc:
        _run(tmp_path, monkeypatch, d)
    assert exc.value.code == "FAIL: missing non-compensation control: " + item


def test_main_guard_exit_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(MOD_PATH), run_name="__main__")
    assert exc.value.code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "PASS_GT_BD_003_3PC_PREPARE_ONLY"
