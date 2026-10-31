"""Behavioural tests for mission-control/grand-missions/assess_gm_iv_ring2.py."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_DIR = REPO_ROOT / "mission-control" / "grand-missions"
MOD_PATH = MOD_DIR / "assess_gm_iv_ring2.py"


def _load():
    spec = importlib.util.spec_from_file_location("cw_assess_gm_iv_ring2", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = _load()

F03_SHA = "3" * 40
F04_SHA = "4" * 40


def _docs(state="STAGED_ACTIVE_RECON_2_OF_8"):
    contract = {
        "wave": "GM-FLEET-03-RING2",
        "mission_id": "GM-IV",
        "mission_state_required": "STAGED_ACTIVE_RECON_2_OF_8",
        "authority_transfer": False,
        "children_bound": False,
        "frontiers": {
            "GM-IV-F03": {"repository": "org/jupyter", "target_sha": F03_SHA},
            "GM-IV-F04": {"repository": "org/yaml", "target_sha": F04_SHA},
        },
        "promotion_invariants": ["GM_V_REMAINS_HELD", "OTHER"],
    }
    f03 = {
        "target_sha": F03_SHA,
        "executed_code_cells": 4,
        "error_count": 0,
        "run1_digest": "d" * 64,
        "run2_digest": "d" * 64,
        "mesh_role": "REPRODUCIBLE_NOTEBOOK_RUNTIME_PRODUCER",
        "must_not_override_child_authority": True,
        "source_dirty_count": 0,
    }
    f04 = {
        "target_sha": F04_SHA,
        "test_attempted": True,
        "test_exit_code": 2,
        "reference_parser_identity": True,
        "qps_authority_claim_detected": False,
        "source_dirty_count": 0,
    }
    registry = {
        "grand_missions": [
            {"id": "GM-IV", "state": state, "children": []},
            {"id": "GM-V", "state": "HELD", "children": []},
        ]
    }
    return {"contract": contract, "f03": f03, "f04": f04, "registry": registry}


def _run(tmp_path, monkeypatch, docs):
    paths = {}
    for name, doc in docs.items():
        p = tmp_path / (name + ".json")
        p.write_text(json.dumps(doc), encoding="utf-8")
        paths[name] = p
    monkeypatch.setattr(m, "REGISTRY", paths["registry"])
    out = tmp_path / "receipt.json"
    monkeypatch.setattr(sys, "argv", [
        "prog", "--contract", str(paths["contract"]), "--f03", str(paths["f03"]),
        "--f04", str(paths["f04"]), "--source-sha", "src", "--out", str(out),
    ])
    code = 0
    try:
        m.main()
    except SystemExit as exc:
        code = exc.code
    return code, json.loads(out.read_text(encoding="utf-8")), paths


def test_load_and_sha256_file(tmp_path):
    p = tmp_path / "a.json"
    data = b'{"x": [1, 2]}'
    p.write_bytes(data)
    assert m.load(p) == {"x": [1, 2]}
    assert m.sha256_file(p) == hashlib.sha256(data).hexdigest()
    big = tmp_path / "big.bin"
    blob = b"z" * (65536 * 2 + 7)
    big.write_bytes(blob)
    assert m.sha256_file(big) == hashlib.sha256(blob).hexdigest()


@pytest.mark.parametrize(
    "state",
    ["STAGED_ACTIVE_RECON_2_OF_8", "STAGED_ACTIVE_PILOT_2_OF_8", "STAGED_ACTIVE_RECON_4_OF_8", "ACTIVE_8_OF_8"],
)
def test_pass_for_all_allowed_forward_states(tmp_path, monkeypatch, capsys, state):
    code, receipt, paths = _run(tmp_path, monkeypatch, _docs(state))
    assert code == 0
    assert receipt["result"] == "PASS"
    assert len(receipt["checks"]) == 13 and all(receipt["checks"].values())
    assert receipt["mission_state"] == state
    assert receipt["dispositions"]["GM-IV-F03"] == {
        "repository": "org/jupyter",
        "disposition": "PILOT_READY",
        "reason": "repeated exact-SHA >0-cell deterministic runtime proof",
    }
    assert receipt["dispositions"]["GM-IV-F04"]["disposition"] == "REFERENCE"
    assert receipt["dispositions"]["GM-IV-F04"]["test_exit_code"] == 2
    assert receipt["pilot_gate"] == "SECOND_PILOT_CANDIDATE_READY_FOR_BOUNDED_CONTROL"
    assert receipt["input_digests"]["f03"] == m.sha256_file(paths["f03"])
    assert receipt["source_sha"] == "src"
    assert json.loads(capsys.readouterr().out)["result"] == "PASS"


def test_unknown_mission_state_fails_contract_check(tmp_path, monkeypatch):
    code, receipt, _ = _run(tmp_path, monkeypatch, _docs("RETIRED"))
    assert code == 1
    assert receipt["result"] == "FAIL"
    assert [k for k, v in receipt["checks"].items() if not v] == ["01_contract_mission_bounded"]
    # F03/F04 dispositions are independent of the mission-level check.
    assert receipt["dispositions"]["GM-IV-F03"]["disposition"] == "PILOT_READY"


@pytest.mark.parametrize(
    "doc, key, value, failed",
    [
        ("f03", "target_sha", "0" * 40, "02_f03_exact_sha"),
        ("f03", "executed_code_cells", 0, "03_f03_gt0_cells"),
        ("f03", "error_count", 1, "04_f03_no_errors"),
        ("f03", "run2_digest", "e" * 64, "05_f03_repeat_digest"),
        ("f03", "must_not_override_child_authority", "yes", "06_f03_mesh_boundary"),
        ("f03", "source_dirty_count", 2, "07_f03_clean_source"),
    ],
)
def test_f03_failures_defer_runtime(tmp_path, monkeypatch, doc, key, value, failed):
    docs = _docs()
    docs[doc][key] = value
    code, receipt, _ = _run(tmp_path, monkeypatch, docs)
    assert code == 1
    assert [k for k, v in receipt["checks"].items() if not v] == [failed]
    assert receipt["dispositions"]["GM-IV-F03"]["disposition"] == "DEFER_RUNTIME"
    assert receipt["dispositions"]["GM-IV-F03"]["reason"] == "runtime proof incomplete"
    assert receipt["pilot_gate"] == "SECOND_PILOT_NOT_READY"
    assert receipt["dispositions"]["GM-IV-F04"]["disposition"] == "REFERENCE"


def test_f03_empty_digests_fail_repeat(tmp_path, monkeypatch):
    docs = _docs()
    docs["f03"]["run1_digest"] = ""
    docs["f03"]["run2_digest"] = ""
    code, receipt, _ = _run(tmp_path, monkeypatch, docs)
    assert receipt["checks"]["05_f03_repeat_digest"] is False


def test_f03_missing_cells_defaults_to_zero(tmp_path, monkeypatch):
    docs = _docs()
    del docs["f03"]["executed_code_cells"]
    _, receipt, _ = _run(tmp_path, monkeypatch, docs)
    assert receipt["checks"]["03_f03_gt0_cells"] is False


@pytest.mark.parametrize(
    "key, value, failed",
    [
        ("target_sha", "0" * 40, "08_f04_exact_sha"),
        ("test_exit_code", "2", "09_f04_real_test_attempt"),
        ("test_attempted", False, "09_f04_real_test_attempt"),
        ("reference_parser_identity", False, "10_f04_reference_identity"),
        ("qps_authority_claim_detected", True, "11_f04_no_qps_authority"),
        ("source_dirty_count", None, "12_f04_clean_source"),
    ],
)
def test_f04_failures_defer_runtime(tmp_path, monkeypatch, key, value, failed):
    docs = _docs()
    docs["f04"][key] = value
    code, receipt, _ = _run(tmp_path, monkeypatch, docs)
    assert code == 1
    assert [k for k, v in receipt["checks"].items() if not v] == [failed]
    f04 = receipt["dispositions"]["GM-IV-F04"]
    assert f04["disposition"] == "DEFER_RUNTIME"
    assert f04["reason"] == "reference boundary incomplete"
    assert receipt["pilot_gate"] == "SECOND_PILOT_CANDIDATE_READY_FOR_BOUNDED_CONTROL"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["contract"].update(promotion_invariants=[]),
        lambda d: d["registry"]["grand_missions"][1].update(state="ACTIVE"),
        lambda d: d["registry"]["grand_missions"][1].update(children=["x"]),
    ],
)
def test_gm_v_hold_failures(tmp_path, monkeypatch, mutate):
    docs = _docs()
    mutate(docs)
    code, receipt, _ = _run(tmp_path, monkeypatch, docs)
    assert code == 1
    assert [k for k, v in receipt["checks"].items() if not v] == ["13_gm_v_held"]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["contract"].update(mission_id="GM-III"),
        lambda d: d["contract"].update(children_bound=True),
        lambda d: d["contract"].update(authority_transfer=0),
        lambda d: d["registry"]["grand_missions"][0].update(children=["c"]),
    ],
)
def test_contract_bound_failures(tmp_path, monkeypatch, mutate):
    docs = _docs()
    mutate(docs)
    code, receipt, _ = _run(tmp_path, monkeypatch, docs)
    assert code == 1
    assert receipt["checks"]["01_contract_mission_bounded"] is False


def test_real_committed_contract_and_registry(tmp_path, monkeypatch, capsys):
    # Committed ring2 contract + registry (offline); runtime receipts synthesised from
    # the contract's pinned SHAs. GM-IV has moved forward to ACTIVE_8_OF_8, which is an
    # allowed forward state, so the historical ring2 recurrence check still passes.
    contract_path = MOD_DIR / "GM_IV_RING2_RECON_CONTRACT.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    docs = _docs()
    docs["f03"]["target_sha"] = contract["frontiers"]["GM-IV-F03"]["target_sha"]
    docs["f04"]["target_sha"] = contract["frontiers"]["GM-IV-F04"]["target_sha"]
    f03 = tmp_path / "f03.json"
    f04 = tmp_path / "f04.json"
    f03.write_text(json.dumps(docs["f03"]), encoding="utf-8")
    f04.write_text(json.dumps(docs["f04"]), encoding="utf-8")
    out = tmp_path / "out.json"
    monkeypatch.setattr(sys, "argv", [
        "prog", "--contract", str(contract_path), "--f03", str(f03), "--f04", str(f04),
        "--source-sha", "real", "--out", str(out),
    ])
    m.main()
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["result"] == "PASS"
    assert receipt["mission_state"] == "ACTIVE_8_OF_8"
    assert receipt["gm_v_state"] == "HELD"
    assert receipt["wave"] == contract["wave"]
