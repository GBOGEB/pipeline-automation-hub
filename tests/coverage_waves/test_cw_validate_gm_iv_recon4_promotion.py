"""Behavioural tests for mission-control/grand-missions/validate_gm_iv_recon4_promotion.py."""
import copy
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_DIR = REPO_ROOT / "mission-control" / "grand-missions"
MOD_PATH = MOD_DIR / "validate_gm_iv_recon4_promotion.py"


def _load():
    if str(MOD_DIR) not in sys.path:
        sys.path.insert(0, str(MOD_DIR))
    spec = importlib.util.spec_from_file_location("cw_validate_gm_iv_recon4_promotion", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = _load()

SHAPE = {
    "candidate_frontiers": ["GM-IV-F01", "GM-IV-F02", "GM-IV-F03", "GM-IV-F04"],
    "controlled_pilot_frontiers": ["GM-IV-F01", "GM-IV-F03"],
    "reference_frontiers": ["GM-IV-F02", "GM-IV-F04"],
    "unfilled_frontier_slots": ["GM-IV-F05", "GM-IV-F06", "GM-IV-F07", "GM-IV-F08"],
    "children": [],
}
ACCEPTED = {
    "source_sha": "4" * 40,
    "decision": "READY_FOR_SEPARATE_RECON_4_PROMOTION_PR",
    "post_merge_workflow_success_count": 14,
    "post_merge_workflow_total": 14,
}


class FakeFleet:
    """Deterministic stand-in for validate_gm_fleet with recording."""

    FORWARD_GM_IV_STATES_REQUIRING_GOVERNOR = {"ACTIVE_8_OF_8"}
    SUPPORTED_GM_IV_STATES = {"STAGED_ACTIVE_RECON_4_OF_8"}

    def __init__(self, evidence_ok=True):
        self.evidence_ok = evidence_ok

    def valid_recon4_evidence(self, item):
        return self.evidence_ok and item is not None

    def gm_iv_supported_shape(self, gm4):
        return gm4["state"] in self.SUPPORTED_GM_IV_STATES


def _docs():
    gm4 = {
        "id": "GM-IV",
        "state": "STAGED_ACTIVE_RECON_4_OF_8",
        "activation_stage": "RECON_4_OF_8",
        "frontier_count": 8,
        "candidate_frontiers": list(SHAPE["candidate_frontiers"]),
        "controlled_pilot_frontiers": list(SHAPE["controlled_pilot_frontiers"]),
        "reference_frontiers": list(SHAPE["reference_frontiers"]),
        "unfilled_frontier_slots": list(SHAPE["unfilled_frontier_slots"]),
        "children": [],
        "recon_4_of_8_evidence": dict(ACCEPTED),
        "pilot_2_of_8_evidence": {"F01": {"p": 1}, "F03": {"p": 3}},
    }
    return {
        "GM_IV_RECON4_PROMOTION_CONTRACT.json": {
            "wave": "W-RECON4",
            "mission_id": "GM-IV",
            "from_state": "STAGED_ACTIVE_PILOT_2_OF_8",
            "to_state": "STAGED_ACTIVE_RECON_4_OF_8",
            "to_activation_stage": "RECON_4_OF_8",
            "predecessor_governor_merge_sha": "4" * 40,
            "accepted_governor_evidence": dict(ACCEPTED),
            "required_shape": copy.deepcopy(SHAPE),
        },
        "GM_IV_RECON4_GOVERNOR_CONTRACT.json": {
            "accepted_gate_evidence": dict(ACCEPTED),
            "authority_transfer": False,
            "children_bound": False,
        },
        "GM_IV_PILOT2_GOVERNOR_CONTRACT.json": {
            "controlled_pilots": {"GM-IV-F01": {"p": 1}, "GM-IV-F03": {"p": 3}},
            "reference_frontiers": {
                "GM-IV-F02": {"disposition": "REFERENCE"},
                "GM-IV-F04": {"disposition": "REFERENCE"},
            },
        },
        "GRAND_MISSION_REGISTRY.json": {
            "authority_transfer": False,
            "grand_missions": [gm4, {"id": "GM-V", "state": "HELD", "children": []}],
        },
        "MISSION_CITY_GRAPH.json": {
            "mission_states": {"GM-IV": "STAGED_ACTIVE_RECON_4_OF_8"},
            "edges": [
                ["MISSION_CONTROL", "GM-IV", "RECON_4_OF_8_COMMAND"],
                ["FLEET_POOL", "GM-IV", "SCOUT_RECON_4_CONTROLLED"],
                ["GOVERNANCE_POOL", "GM-IV", "SECOND_GOVERNOR_STAGE_CONTROL"],
            ],
        },
        "GM_IV_EVIDENCE_ECONOMICS.json": {
            "authority_transfer": False,
            "fleet_invariant": {
                "mission_stage": "RECON_4_OF_8",
                "named_recon_frontiers": list(SHAPE["candidate_frontiers"]),
                "controlled_pilot_frontiers": list(SHAPE["controlled_pilot_frontiers"]),
                "reference_frontiers": list(SHAPE["reference_frontiers"]),
                "unfilled_frontier_slots": list(SHAPE["unfilled_frontier_slots"]),
            },
            "pca_gate": {"state": "DEFER"},
            "bt_gate": {"state": "DEFER"},
        },
    }


def _gm4(docs):
    return docs["GRAND_MISSION_REGISTRY.json"]["grand_missions"][0]


def _run(tmp_path, monkeypatch, docs, fleet=None):
    for name, doc in docs.items():
        (tmp_path / name).write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(m, "ROOT", tmp_path)
    monkeypatch.setattr(m, "fleet_validator", fleet or FakeFleet())
    out = tmp_path / "out" / "receipt.json"
    monkeypatch.setattr(sys, "argv", ["prog", "--source-sha", "abc", "--out", str(out)])
    rc = m.main()
    return rc, json.loads(out.read_text(encoding="utf-8"))


def test_digest_is_canonical():
    assert m.digest({"b": 1, "a": [1, 2]}) == m.digest({"a": [1, 2], "b": 1})
    assert m.digest({"a": 1}) != m.digest({"a": 2})


def test_load_uses_root(tmp_path, monkeypatch):
    (tmp_path / "x.json").write_text('{"k": true}', encoding="utf-8")
    monkeypatch.setattr(m, "ROOT", tmp_path)
    assert m.load("x.json") == {"k": True}


def test_main_pass(tmp_path, monkeypatch, capsys):
    docs = _docs()
    rc, receipt = _run(tmp_path, monkeypatch, docs)
    assert rc == 0
    assert receipt["result"] == "PASS_GM_IV_RECON4_PROMOTION"
    assert receipt["check_count"] == 15
    assert all(receipt["checks"].values())
    assert receipt["source_sha"] == "abc"
    assert receipt["wave"] == "W-RECON4"
    assert receipt["accepted_governor_evidence"] == ACCEPTED
    assert receipt["unfilled_frontier_slots"] == SHAPE["unfilled_frontier_slots"]
    expected_digest = m.digest({
        "contract": docs["GM_IV_RECON4_PROMOTION_CONTRACT.json"],
        "governor": docs["GM_IV_RECON4_GOVERNOR_CONTRACT.json"],
        "pilot2": docs["GM_IV_PILOT2_GOVERNOR_CONTRACT.json"],
        "registry": docs["GRAND_MISSION_REGISTRY.json"],
        "city": docs["MISSION_CITY_GRAPH.json"],
        "economics": docs["GM_IV_EVIDENCE_ECONOMICS.json"],
    })
    assert receipt["input_digest_sha256"] == expected_digest
    assert json.loads(capsys.readouterr().out)["result"] == "PASS_GM_IV_RECON4_PROMOTION"


def _set(path):
    def mutate(docs):
        target = docs
        for key in path[:-2]:
            target = target[key]
        target[path[-2]] = path[-1]
    return mutate


@pytest.mark.parametrize(
    "mutate, failed",
    [
        (_set(["GM_IV_RECON4_PROMOTION_CONTRACT.json", "from_state", "X"]), "01_contract_identity"),
        (_set(["GM_IV_RECON4_GOVERNOR_CONTRACT.json", "accepted_gate_evidence", {}]), "02_governor_evidence_contract_parity"),
        (lambda d: _gm4(d).update(frontier_count=4), "03_registry_recon4_state"),
        (lambda d: _gm4(d).update(unfilled_frontier_slots=[]), "04_exact_four_frontier_shape"),
        (lambda d: _gm4(d).update(recon_4_of_8_evidence={"x": 1}), "05_exact_recon4_evidence_bound"),
        (lambda d: _gm4(d)["pilot_2_of_8_evidence"].update(F01={}), "06_historical_f01_evidence_retained"),
        (lambda d: _gm4(d)["pilot_2_of_8_evidence"].update(F03={}), "07_historical_f03_evidence_retained"),
        (lambda d: d["GM_IV_PILOT2_GOVERNOR_CONTRACT.json"]["reference_frontiers"]["GM-IV-F04"].update(disposition="PILOT"),
         "08_reference_dispositions_retained"),
        (lambda d: d["MISSION_CITY_GRAPH.json"]["edges"].pop(), "09_mission_city_synchronized"),
        (lambda d: d["GM_IV_EVIDENCE_ECONOMICS.json"]["fleet_invariant"].update(mission_stage="ACTIVE_8_OF_8"),
         "12_evidence_economics_synchronized"),
        (lambda d: d["GM_IV_EVIDENCE_ECONOMICS.json"]["bt_gate"].update(state="PASS"), "13_local_models_still_fail_closed"),
        (_set(["GM_IV_RECON4_GOVERNOR_CONTRACT.json", "children_bound", True]), "14_no_authority_or_child_binding"),
        (lambda d: d["GRAND_MISSION_REGISTRY.json"]["grand_missions"][1].update(state="ACTIVE"), "15_gm_v_held"),
    ],
)
def test_main_single_check_failure(tmp_path, monkeypatch, mutate, failed):
    docs = _docs()
    mutate(docs)
    rc, receipt = _run(tmp_path, monkeypatch, docs)
    assert rc == 1
    assert receipt["result"] == "FAIL_GM_IV_RECON4_PROMOTION"
    assert [k for k, v in receipt["checks"].items() if not v] == [failed]


def test_fleet_validator_rejects_evidence(tmp_path, monkeypatch):
    rc, receipt = _run(tmp_path, monkeypatch, _docs(), FakeFleet(evidence_ok=False))
    assert rc == 1
    assert [k for k, v in receipt["checks"].items() if not v] == ["05_exact_recon4_evidence_bound"]


def test_fleet_validator_accepting_active8_breaks_fail_closed(tmp_path, monkeypatch):
    fleet = FakeFleet()
    fleet.SUPPORTED_GM_IV_STATES = {"STAGED_ACTIVE_RECON_4_OF_8", "ACTIVE_8_OF_8"}
    rc, receipt = _run(tmp_path, monkeypatch, _docs(), fleet)
    assert rc == 1
    assert receipt["checks"]["11_active8_remains_fail_closed"] is False
    assert receipt["checks"]["10_generic_fleet_accepts_exact_recon4"] is True


def test_active8_copy_does_not_mutate_registry(tmp_path, monkeypatch):
    seen = []
    fleet = FakeFleet()
    fleet.gm_iv_supported_shape = lambda gm4: seen.append(gm4["state"]) or gm4["state"] != "ACTIVE_8_OF_8"
    rc, receipt = _run(tmp_path, monkeypatch, _docs(), fleet)
    assert rc == 0
    assert seen == ["STAGED_ACTIVE_RECON_4_OF_8", "ACTIVE_8_OF_8"]
    assert receipt["current_state"] == "STAGED_ACTIVE_RECON_4_OF_8"


def test_real_committed_data_is_superseded(tmp_path, monkeypatch, capsys):
    # Uses the committed contracts and the real validate_gm_fleet. GM-IV has since been
    # promoted to ACTIVE_8_OF_8, so this historical RECON4 promotion gate now reports
    # FAIL on the stage-bound checks. That is expected supersession, not a defect.
    import validate_gm_fleet as real_fleet

    monkeypatch.setattr(m, "fleet_validator", real_fleet)
    out = tmp_path / "receipt.json"
    monkeypatch.setattr(sys, "argv", ["prog", "--source-sha", "real", "--out", str(out)])
    rc = m.main()
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert rc == 1
    assert receipt["result"] == "FAIL_GM_IV_RECON4_PROMOTION"
    assert receipt["current_state"] == "ACTIVE_8_OF_8"
    assert receipt["checks"]["01_contract_identity"] is True
    assert receipt["checks"]["03_registry_recon4_state"] is False
    assert receipt["checks"]["15_gm_v_held"] is True
