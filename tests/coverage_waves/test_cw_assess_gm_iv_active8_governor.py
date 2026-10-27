"""Behavioural tests for mission-control/grand-missions/assess_gm_iv_active8_governor.py."""
import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_DIR = REPO_ROOT / "mission-control" / "grand-missions"
MOD_PATH = MOD_DIR / "assess_gm_iv_active8_governor.py"


def _load():
    if str(MOD_DIR) not in sys.path:
        sys.path.insert(0, str(MOD_DIR))
    spec = importlib.util.spec_from_file_location("cw_assess_gm_iv_active8_governor", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gov = _load()

F = ["GM-IV-F%02d" % i for i in range(1, 9)]
SHA = {fid: (str(i) * 40)[:40] for i, fid in enumerate(F, start=1)}
ACTIVE8_EVIDENCE = {
    "source_sha": "3943ae33eea2a4af6171b97517c19b79ed986fe8",
    "workflow_run_id": 35145656795,
    "artifact_id": 10467671042,
    "artifact_digest": "sha256:97d37b98334acbab0e1fec9bae56163e20fd5b9c2751be2495c52642bc6dd4cb",
    "decision": "READY_FOR_SEPARATE_ACTIVE_8_PROMOTION_PR",
    "result": "PASS",
}
RECON4_EVIDENCE = {
    "source_sha": "a" * 40,
    "workflow_run_id": 11,
    "artifact_id": 22,
    "artifact_digest": "sha256:" + "b" * 64,
    "decision": "READY_FOR_SEPARATE_RECON_4_PROMOTION_PR",
    "post_merge_workflow_success_count": 3,
    "post_merge_workflow_total": 3,
}


def _contract():
    return {
        "wave": "W-TEST",
        "authority_transfer": False,
        "children_bound": False,
        "current_control_shape": {
            "activation_stage": "RECON_4_OF_8",
            "candidate_frontiers": F[:4],
            "controlled_pilot_frontiers": ["GM-IV-F01", "GM-IV-F03"],
            "reference_frontiers": ["GM-IV-F02", "GM-IV-F04"],
            "unfilled_frontier_slots": F[4:],
        },
        "proposed_eight_frontier_shape": {
            "candidate_frontiers": F,
            "controlled_pilot_frontiers_retained": ["GM-IV-F01", "GM-IV-F03"],
            "reference_frontiers_retained": ["GM-IV-F02", "GM-IV-F04"],
            "new_candidate_recon_frontiers": F[4:],
        },
        "frontier_evidence": {fid: {"repository": "org/repo%d" % i, "target_sha": SHA[fid]} for i, fid in enumerate(F)},
        "accepted_readiness_evidence": dict(ACTIVE8_EVIDENCE, evaluated_head_sha="c" * 40),
        "decision_semantics": {"READY": "D_READY", "WITHHOLD": "D_WITHHOLD", "CONTROL": "D_CONTROL"},
    }


def _gm4(mode):
    base = {
        "id": "GM-IV",
        "controlled_pilot_frontiers": ["GM-IV-F01", "GM-IV-F03"],
        "reference_frontiers": ["GM-IV-F02", "GM-IV-F04"],
        "children": [],
        "pilot_2_of_8_evidence": {"F01": {"target_sha": SHA["GM-IV-F01"]}, "F03": {"target_sha": SHA["GM-IV-F03"]}},
        "recon_4_of_8_evidence": dict(RECON4_EVIDENCE),
    }
    if mode == "READINESS":
        base.update(state="STAGED_ACTIVE_RECON_4_OF_8", activation_stage="RECON_4_OF_8",
                    candidate_frontiers=F[:4], unfilled_frontier_slots=F[4:])
    else:
        base.update(state="ACTIVE_8_OF_8", activation_stage="ACTIVE_8_OF_8", candidate_frontiers=F,
                    new_candidate_recon_frontiers=F[4:], unfilled_frontier_slots=[],
                    active_8_of_8_evidence=dict(ACTIVE8_EVIDENCE),
                    active8_readiness={"evaluated_head_sha": "c" * 40})
    return base


def _setup(tmp_path, monkeypatch, mode="READINESS", gm4=None, contract=None, capacity=None,
           economics=None, probes=True, argv_extra=()):
    gm4 = gm4 if gm4 is not None else _gm4(mode)
    registry = {"grand_missions": [gm4, {"id": "GM-V", "state": "HELD", "children": []}]}
    capacity = capacity if capacity is not None else {
        "stage_model": [{"stage": "RECON_4_OF_8", "maximum_bound_frontiers": 4},
                        {"stage": "ACTIVE_8_OF_8", "maximum_bound_frontiers": 8, "authority_transfer": False}]}
    econ_stage = "RECON_4_OF_8" if mode == "READINESS" else "ACTIVE_8_OF_8"
    economics = economics if economics is not None else {
        "fleet_invariant": {"mission_stage": econ_stage, "canonical_children_bound": 0},
        "pca_gate": {"state": "DEFER"}, "bt_gate": {"state": "DEFER"}}
    contract = contract if contract is not None else _contract()
    files = {"registry.json": registry, "capacity.json": capacity, "economics.json": economics,
             "contract.json": contract}
    for name, data in files.items():
        (tmp_path / name).write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(gov, "REGISTRY", tmp_path / "registry.json")
    monkeypatch.setattr(gov, "CAPACITY", tmp_path / "capacity.json")
    monkeypatch.setattr(gov, "ECONOMICS", tmp_path / "economics.json")
    probe_root = tmp_path / "probe"
    probe_root.mkdir()
    if probes:
        for fid in F[4:]:
            (probe_root / fid).mkdir()
            (probe_root / fid / "HEAD_SHA").write_text(SHA[fid] + "\n")
            (probe_root / fid / "ENTRY_COUNT").write_text("5\n")
    out = tmp_path / "receipt.json"
    monkeypatch.setattr(sys, "argv", ["prog", "--contract", str(tmp_path / "contract.json"), "--source-sha", "s" * 40,
                                      "--probe-root", str(probe_root), "--out", str(out), *argv_extra])
    return out, probe_root


def _checks(receipt):
    return {c["check"]: c["result"] for c in receipt["checks"]}


def test_load_and_add_helpers(tmp_path):
    p = tmp_path / "x.json"
    p.write_text('{"a": [1, 2]}', encoding="utf-8")
    assert gov.load(p) == {"a": [1, 2]}
    checks = []
    gov.add(checks, "n1", True, {"d": 1})
    gov.add(checks, "n2", 0, None)
    assert checks == [{"check": "n1", "result": "PASS", "detail": {"d": 1}},
                      {"check": "n2", "result": "FAIL", "detail": None}]


def test_load_fleet_returns_real_validator():
    fleet = gov.load_fleet()
    assert fleet.gm_iv_supported_shape({"state": "HELD"}) is True
    assert fleet.gm_iv_supported_shape({"state": "BOGUS"}) is False


def test_readiness_mode_passes_and_writes_ready_receipt(tmp_path, monkeypatch, capsys):
    out, _ = _setup(tmp_path, monkeypatch, "READINESS")
    gov.main()
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["mode"] == "READINESS"
    assert receipt["result"] == "PASS"
    assert receipt["decision"] == "D_READY"
    assert receipt["schema"] == "qps.gm_iv_active8_governor_receipt.v2"
    assert receipt["source_sha"] == "s" * 40
    assert receipt["canonical_state_after_gate"] == "STAGED_ACTIVE_RECON_4_OF_8"
    checks = _checks(receipt)
    assert len(checks) == 12
    assert checks["12_readiness_fail_closed_before_promotion"] == "PASS"
    assert all(v == "PASS" for v in checks.values())
    assert json.loads(capsys.readouterr().out) == receipt


def test_control_mode_passes_with_real_fleet_validator(tmp_path, monkeypatch):
    out, _ = _setup(tmp_path, monkeypatch, "CONTROL")
    gov.main()
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["mode"] == "CONTROL"
    assert receipt["decision"] == "D_CONTROL"
    checks = _checks(receipt)
    assert len(checks) == 13
    assert checks["13_current_active8_validator_accepts"] == "PASS"
    assert checks["12_historical_readiness_exactly_retained"] == "PASS"


def test_control_mode_withholds_when_readiness_evidence_drifts(tmp_path, monkeypatch):
    gm4 = _gm4("CONTROL")
    gm4["active8_readiness"]["evaluated_head_sha"] = "d" * 40
    out, _ = _setup(tmp_path, monkeypatch, "CONTROL", gm4=gm4)
    with pytest.raises(SystemExit) as exc:
        gov.main()
    assert exc.value.code == 1
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["result"] == "FAIL"
    assert receipt["decision"] == "D_WITHHOLD"
    assert _checks(receipt)["12_historical_readiness_exactly_retained"] == "FAIL"


def test_control_mode_rejected_by_validator_when_active8_evidence_wrong(tmp_path, monkeypatch):
    gm4 = _gm4("CONTROL")
    gm4["active_8_of_8_evidence"]["result"] = "FAIL"
    contract = _contract()
    contract["accepted_readiness_evidence"]["result"] = "FAIL"
    out, _ = _setup(tmp_path, monkeypatch, "CONTROL", gm4=gm4, contract=contract)
    with pytest.raises(SystemExit):
        gov.main()
    checks = _checks(json.loads(out.read_text(encoding="utf-8")))
    assert checks["12_historical_readiness_exactly_retained"] == "PASS"
    assert checks["13_current_active8_validator_accepts"] == "FAIL"


def test_unsupported_state_withholds(tmp_path, monkeypatch):
    gm4 = _gm4("READINESS")
    gm4["state"] = "HELD"
    out, _ = _setup(tmp_path, monkeypatch, "READINESS", gm4=gm4)
    with pytest.raises(SystemExit) as exc:
        gov.main()
    assert exc.value.code == 1
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["mode"] == "UNSUPPORTED"
    assert receipt["decision"] == "D_WITHHOLD"
    checks = _checks(receipt)
    assert checks["01_stage_aware_current_shape"] == "FAIL"
    assert checks["12_unsupported_stage"] == "FAIL"
    # economics stage expectation switches to ACTIVE_8_OF_8 outside READINESS
    assert checks["09_economics_stage_control"] == "FAIL"


def test_readiness_shape_mismatch_and_missing_probes(tmp_path, monkeypatch):
    gm4 = _gm4("READINESS")
    gm4["unfilled_frontier_slots"] = F[5:]
    out, probe_root = _setup(tmp_path, monkeypatch, "READINESS", gm4=gm4, probes=False)
    (probe_root / "GM-IV-F05").mkdir()
    (probe_root / "GM-IV-F05" / "HEAD_SHA").write_text(SHA["GM-IV-F05"])
    (probe_root / "GM-IV-F05" / "ENTRY_COUNT").write_text("0")
    with pytest.raises(SystemExit):
        gov.main()
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["decision"] == "D_WITHHOLD"
    checks = _checks(receipt)
    assert checks["01_stage_aware_current_shape"] == "FAIL"
    assert checks["08_f05_f08_exact_sha_gt0_probes"] == "FAIL"
    rows = [c for c in receipt["checks"] if c["check"].startswith("08_")][0]["detail"]
    assert rows[0] == {"frontier": "GM-IV-F05", "observed_sha": SHA["GM-IV-F05"], "entry_count": 0, "result": "FAIL"}
    assert rows[1]["observed_sha"] == "MISSING" and rows[1]["entry_count"] == 0


def test_probe_sha_mismatch_fails(tmp_path, monkeypatch):
    out, probe_root = _setup(tmp_path, monkeypatch, "READINESS")
    (probe_root / "GM-IV-F08" / "HEAD_SHA").write_text("f" * 40)
    with pytest.raises(SystemExit):
        gov.main()
    rows = [c for c in json.loads(out.read_text())["checks"] if c["check"].startswith("08_")][0]["detail"]
    assert [r["result"] for r in rows] == ["PASS", "PASS", "PASS", "FAIL"]


def test_capacity_without_active8_stage_and_bad_evidence_ids(tmp_path, monkeypatch):
    contract = _contract()
    ev = contract["frontier_evidence"]
    ev["GM-IV-F02"]["repository"] = ev["GM-IV-F01"]["repository"]
    ev["GM-IV-F07"]["target_sha"] = "short"
    capacity = {"stage_model": [{"stage": "RECON_4_OF_8", "maximum_bound_frontiers": 4}]}
    out, _ = _setup(tmp_path, monkeypatch, "READINESS", contract=contract, capacity=capacity)
    with pytest.raises(SystemExit):
        gov.main()
    receipt = json.loads(out.read_text())
    checks = _checks(receipt)
    assert checks["02_capacity_contract_active8"] == "FAIL"
    assert checks["03_eight_unique_frontier_ids"] == "PASS"
    assert checks["04_eight_unique_repositories"] == "FAIL"
    assert checks["05_eight_target_shas"] == "FAIL"
    detail02 = [c for c in receipt["checks"] if c["check"].startswith("02_")][0]["detail"]
    assert detail02 is None


def test_governance_guards_fail(tmp_path, monkeypatch):
    contract = _contract()
    contract["authority_transfer"] = True
    gm4 = _gm4("READINESS")
    gm4["recon_4_of_8_evidence"]["decision"] = "OTHER"
    gm4["pilot_2_of_8_evidence"]["F03"]["target_sha"] = "e" * 40
    out, _ = _setup(tmp_path, monkeypatch, "READINESS", gm4=gm4, contract=contract)
    reg = json.loads((tmp_path / "registry.json").read_text())
    reg["grand_missions"][1]["state"] = "ACTIVE"
    (tmp_path / "registry.json").write_text(json.dumps(reg))
    with pytest.raises(SystemExit):
        gov.main()
    checks = _checks(json.loads(out.read_text()))
    assert checks["06_pilot_evidence_retained"] == "FAIL"
    assert checks["07_recon4_evidence_retained"] == "FAIL"
    assert checks["10_no_authority_or_child_binding"] == "FAIL"
    assert checks["11_gm_v_held"] == "FAIL"


def test_readiness_fails_if_fleet_would_accept_promotion(tmp_path, monkeypatch):
    class LaxFleet:
        @staticmethod
        def gm_iv_supported_shape(_shape):
            return True

    monkeypatch.setattr(gov, "load_fleet", lambda: LaxFleet)
    out, _ = _setup(tmp_path, monkeypatch, "READINESS")
    with pytest.raises(SystemExit):
        gov.main()
    receipt = json.loads(out.read_text())
    detail = [c for c in receipt["checks"] if c["check"].startswith("12_")][0]
    assert detail["result"] == "FAIL" and detail["detail"] == "ACCEPTED"


def test_real_committed_contract_passes_with_matching_probes(tmp_path, monkeypatch):
    contract_path = MOD_DIR / "GM_IV_ACTIVE8_GOVERNOR_CONTRACT.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    probe_root = tmp_path / "probe"
    for fid in F[4:]:
        (probe_root / fid).mkdir(parents=True)
        (probe_root / fid / "HEAD_SHA").write_text(contract["frontier_evidence"][fid]["target_sha"])
        (probe_root / fid / "ENTRY_COUNT").write_text("3")
    out = tmp_path / "real.json"
    monkeypatch.setattr(sys, "argv", ["prog", "--contract", str(contract_path), "--source-sha", "r" * 40,
                                      "--probe-root", str(probe_root), "--out", str(out)])
    try:
        gov.main()
    except SystemExit:
        pass
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["mode"] in {"READINESS", "CONTROL"}
    assert _checks(receipt)["08_f05_f08_exact_sha_gt0_probes"] == "PASS"
    assert receipt["children_bound"] is False and receipt["authority_transfer"] is False
