"""Behavioural tests for mission-control/grand-missions/assess_gm_iv_recon4_governor.py."""
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_DIR = REPO_ROOT / "mission-control" / "grand-missions"
MOD_PATH = MOD_DIR / "assess_gm_iv_recon4_governor.py"


def _load():
    if str(MOD_DIR) not in sys.path:
        sys.path.insert(0, str(MOD_DIR))
    spec = importlib.util.spec_from_file_location("cw_assess_gm_iv_recon4_governor", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gov = _load()

F = ["GM-IV-F%02d" % i for i in range(1, 9)]


def _evidence(disposition, seed="1"):
    return {
        "repository": "org/repo" + seed,
        "target_sha": seed * 40,
        "master_source_sha": "m" * 40,
        "workflow_run_id": 101,
        "artifact_id": 202,
        "artifact_digest": "sha256:" + "a" * 64,
        "disposition": disposition,
    }


GATE_EVIDENCE = {"source_sha": "g" * 40, "decision": "READY_FOR_SEPARATE_RECON_4_PROMOTION_PR"}

PROPOSED = {
    "state": "STAGED_ACTIVE_RECON_4_OF_8",
    "activation_stage": "RECON_4_OF_8",
    "candidate_frontiers": F[:4],
    "controlled_pilot_frontiers": ["GM-IV-F01", "GM-IV-F03"],
    "reference_frontiers": ["GM-IV-F02", "GM-IV-F04"],
    "unfilled_frontier_slots": F[4:],
    "children": [],
}


def _docs(mode="READINESS"):
    pilots = {"GM-IV-F01": _evidence("PILOT_CONTROL_READY", "1"), "GM-IV-F03": _evidence("PILOT_CONTROL_READY", "3")}
    contract = {
        "mission_id": "GM-IV",
        "from_state": "STAGED_ACTIVE_PILOT_2_OF_8",
        "proposed_to_state": "STAGED_ACTIVE_RECON_4_OF_8",
        "authority_transfer": False,
        "children_bound": False,
        "wave": "W-R4",
        "predecessor_control_sha": "p" * 40,
        "proposed_shape": dict(PROPOSED),
        "frontier_policy": {
            "named_recon_frontiers": F[:4],
            "controlled_pilots_retained": ["GM-IV-F01", "GM-IV-F03"],
            "bounded_references_retained": ["GM-IV-F02", "GM-IV-F04"],
            "unfilled_frontier_slots": F[4:],
        },
        "accepted_gate_evidence": dict(GATE_EVIDENCE),
        "gm_v_required_state": "HELD",
        "decision_semantics": {"READY": "D_READY", "WITHHOLD": "D_WITHHOLD", "CONTROL": "D_CONTROL"},
    }
    pilot2 = {
        "controlled_pilots": pilots,
        "reference_frontiers": {"GM-IV-F02": _evidence("REFERENCE", "2"), "GM-IV-F04": _evidence("REFERENCE", "4")},
    }
    capacity = {"stage_model": [
        {"stage": "PILOT_2_OF_8", "maximum_bound_frontiers": 2},
        {"stage": "RECON_4_OF_8", "maximum_bound_frontiers": 4, "authority_transfer": False,
         "meaning": "four_named_frontiers_bounded"},
    ]}
    gm4 = {
        "id": "GM-IV",
        "frontier_count": 8,
        "candidate_frontiers": F[:4],
        "controlled_pilot_frontiers": ["GM-IV-F01", "GM-IV-F03"],
        "reference_frontiers": ["GM-IV-F02", "GM-IV-F04"],
        "unfilled_frontier_slots": F[4:],
        "children": [],
        "pilot_2_of_8_evidence": {"F01": dict(pilots["GM-IV-F01"]), "F03": dict(pilots["GM-IV-F03"])},
    }
    if mode == "READINESS":
        gm4.update(state="STAGED_ACTIVE_PILOT_2_OF_8", activation_stage="PILOT_2_OF_8")
        edges = [["FLEET_POOL", "GM-IV", "SCOUT_RESERVE_FOR_RECON_4"],
                 ["GOVERNANCE_POOL", "GM-IV", "SECOND_GOVERNOR_STAGE_CONTROL"]]
    else:
        gm4.update(state="STAGED_ACTIVE_RECON_4_OF_8", activation_stage="RECON_4_OF_8",
                   recon_4_of_8_evidence=dict(GATE_EVIDENCE))
        edges = [["MISSION_CONTROL", "GM-IV", "RECON_4_OF_8_COMMAND"],
                 ["FLEET_POOL", "GM-IV", "SCOUT_RECON_4_CONTROLLED"],
                 ["GOVERNANCE_POOL", "GM-IV", "SECOND_GOVERNOR_STAGE_CONTROL"]]
    registry = {"authority_transfer": False,
                "grand_missions": [gm4, {"id": "GM-V", "state": "HELD", "children": []}]}
    city = {"edges": edges, "mission_states": {"GM-IV": gm4["state"]}}
    return {"contract": contract, "pilot2": pilot2, "capacity": capacity, "registry": registry, "city": city}


NAMES = {
    "contract": "GM_IV_RECON4_GOVERNOR_CONTRACT.json",
    "pilot2": "GM_IV_PILOT2_GOVERNOR_CONTRACT.json",
    "capacity": "GM_FLEET_03_CAPACITY_CONTRACT.json",
    "registry": "GRAND_MISSION_REGISTRY.json",
    "city": "MISSION_CITY_GRAPH.json",
}

STUB_FLEET = SimpleNamespace(
    gm_iv_supported_shape=lambda shape: bool(shape.get("recon_4_of_8_evidence")),
    valid_recon4_evidence=lambda item: bool(item) and item.get("decision") == "READY_FOR_SEPARATE_RECON_4_PROMOTION_PR",
    FORWARD_GM_IV_STATES_REQUIRING_GOVERNOR={"ACTIVE_8_OF_8"},
)


def _run(tmp_path, monkeypatch, docs, fleet=STUB_FLEET):
    for key, name in NAMES.items():
        (tmp_path / name).write_text(json.dumps(docs[key]), encoding="utf-8")
    monkeypatch.setattr(gov, "ROOT", tmp_path)
    monkeypatch.setattr(gov, "fleet_validator", fleet)
    out = tmp_path / "nested" / "receipt.json"
    monkeypatch.setattr(sys, "argv", ["prog", "--source-sha", "s" * 40, "--out", str(out)])
    rc = gov.main()
    return rc, json.loads(out.read_text(encoding="utf-8"))


def test_digest_is_canonical_and_order_independent():
    a = gov.digest({"b": 1, "a": [1, 2]})
    assert a == gov.digest({"a": [1, 2], "b": 1})
    assert len(a) == 64 and a != gov.digest({"a": [2, 1], "b": 1})


def test_load_reads_relative_to_root(tmp_path, monkeypatch):
    (tmp_path / "x.json").write_text('{"k": true}', encoding="utf-8")
    monkeypatch.setattr(gov, "ROOT", tmp_path)
    assert gov.load("x.json") == {"k": True}


def test_bound_evidence_accepts_complete_item():
    assert gov.bound_evidence(_evidence("REFERENCE"), "REFERENCE") is True


@pytest.mark.parametrize("mutate", [
    lambda e: e.pop("artifact_id"),
    lambda e: e.update(target_sha="short"),
    lambda e: e.update(master_source_sha=1234),
    lambda e: e.update(workflow_run_id="101"),
    lambda e: e.update(workflow_run_id=-5),
    lambda e: e.update(artifact_id=1.5),
    lambda e: e.update(artifact_digest="md5:" + "a" * 67),
    lambda e: e.update(artifact_digest="sha256:abc"),
    lambda e: e.update(disposition="OTHER"),
])
def test_bound_evidence_rejects_defects(mutate):
    item = _evidence("REFERENCE")
    mutate(item)
    assert gov.bound_evidence(item, "REFERENCE") is False


def test_readiness_mode_ready(tmp_path, monkeypatch, capsys):
    docs = _docs("READINESS")
    rc, receipt = _run(tmp_path, monkeypatch, docs)
    assert rc == 0
    assert receipt["mode"] == "READINESS"
    assert receipt["result"] == "PASS"
    assert receipt["decision"] == "D_READY"
    assert receipt["next_action"] == "SEPARATE_RECON_4_PROMOTION_PR_WITH_EXACT_HEAD_CENSUS"
    assert receipt["check_count"] == 14 and all(receipt["checks"].values())
    assert receipt["registry_mutated"] is False and receipt["promotion_executed"] is False
    assert receipt["proposed_shape_digest_sha256"] == gov.digest(docs["contract"]["proposed_shape"])
    assert receipt["input_digest_sha256"] == gov.digest(docs)
    assert json.loads(capsys.readouterr().out) == receipt


def test_control_mode_ready(tmp_path, monkeypatch):
    rc, receipt = _run(tmp_path, monkeypatch, _docs("CONTROL"))
    assert rc == 0
    assert receipt["mode"] == "CONTROL"
    assert receipt["decision"] == "D_CONTROL"
    assert receipt["next_action"] == "SEPARATE_ACTIVE_8_GOVERNOR_REQUIRED"
    assert receipt["registry_mutated"] is True and receipt["mission_city_mutated"] is True
    assert receipt["active_8_authorized"] is False


def test_control_mode_gate_evidence_mismatch_withholds(tmp_path, monkeypatch):
    docs = _docs("CONTROL")
    docs["contract"]["accepted_gate_evidence"]["source_sha"] = "h" * 40
    rc, receipt = _run(tmp_path, monkeypatch, docs)
    assert rc == 1
    assert receipt["checks"]["11_exact_gate_evidence_binding"] is False
    assert receipt["decision"] == "D_WITHHOLD"
    assert receipt["next_action"] == "REPAIR_FIRST_RED_AND_REPEAT_GATE"


def test_invalid_mode_withholds(tmp_path, monkeypatch):
    docs = _docs("CONTROL")
    gm4 = docs["registry"]["grand_missions"][0]
    gm4["state"] = "ACTIVE_8_OF_8"
    rc, receipt = _run(tmp_path, monkeypatch, docs)
    assert rc == 1
    assert receipt["mode"] == "INVALID"
    assert receipt["checks"]["02_mode_is_governed"] is False
    assert receipt["checks"]["10_stage_specific_governor_boundary"] is False
    assert receipt["current_state"] == "ACTIVE_8_OF_8"


def test_readiness_missing_city_edge_and_bad_evidence(tmp_path, monkeypatch):
    docs = _docs("READINESS")
    docs["city"]["edges"] = docs["city"]["edges"][1:]
    docs["registry"]["grand_missions"][0]["pilot_2_of_8_evidence"]["F03"]["artifact_id"] = 999
    docs["pilot2"]["reference_frontiers"]["GM-IV-F04"]["disposition"] = "PILOT_CONTROL_READY"
    docs["capacity"]["stage_model"][1]["maximum_bound_frontiers"] = 8
    docs["registry"]["grand_missions"][1]["state"] = "ACTIVE"
    rc, receipt = _run(tmp_path, monkeypatch, docs)
    assert rc == 1
    c = receipt["checks"]
    assert c["10_stage_specific_governor_boundary"] is False
    assert c["11_exact_gate_evidence_binding"] is True
    assert c["04_f01_control_evidence_bound"] is True
    assert c["05_f03_control_evidence_bound"] is False
    assert c["06_f02_reference_evidence_bound"] is True
    assert c["07_f04_reference_evidence_bound"] is False
    assert c["08_capacity_contract_recon4_bounded"] is False
    assert c["14_gm_v_held"] is False


def test_contract_identity_and_shape_drift(tmp_path, monkeypatch):
    docs = _docs("READINESS")
    docs["contract"]["authority_transfer"] = True
    docs["contract"]["proposed_shape"]["children"] = ["child"]
    docs["registry"]["grand_missions"][0]["candidate_frontiers"] = F[:3]
    rc, receipt = _run(tmp_path, monkeypatch, docs)
    assert rc == 1
    c = receipt["checks"]
    assert c["01_contract_identity"] is False
    assert c["03_current_or_proposed_four_frontier_identity"] is False
    assert c["09_proposed_shape_complete"] is False
    assert c["13_no_authority_or_child_binding"] is False


def test_active8_must_remain_fail_closed(tmp_path, monkeypatch):
    lax = SimpleNamespace(
        gm_iv_supported_shape=lambda shape: shape.get("state") != "STAGED_ACTIVE_RECON_4_OF_8",
        valid_recon4_evidence=lambda item: True,
        FORWARD_GM_IV_STATES_REQUIRING_GOVERNOR={"ACTIVE_8_OF_8"},
    )
    rc, receipt = _run(tmp_path, monkeypatch, _docs("READINESS"), fleet=lax)
    assert rc == 1
    assert receipt["checks"]["12_active8_still_fail_closed"] is False


def test_real_fleet_validator_no_longer_lists_active8_as_forward(tmp_path, monkeypatch):
    real_fleet = gov.fleet_validator
    rc, receipt = _run(tmp_path, monkeypatch, _docs("READINESS"), fleet=real_fleet)
    expected = "ACTIVE_8_OF_8" in real_fleet.FORWARD_GM_IV_STATES_REQUIRING_GOVERNOR
    assert receipt["checks"]["12_active8_still_fail_closed"] is expected
    assert rc == (0 if expected else 1)


def test_real_committed_data_is_deterministic(tmp_path, monkeypatch):
    def run(name):
        out = tmp_path / name
        monkeypatch.setattr(sys, "argv", ["prog", "--source-sha", "x" * 40, "--out", str(out)])
        rc = gov.main()
        return rc, json.loads(out.read_text(encoding="utf-8"))

    rc1, r1 = run("a.json")
    rc2, r2 = run("b.json")
    assert rc1 == rc2 and r1 == r2
    assert r1["schema"] == "qps.gm_iv_recon4_governor_receipt.v2"
    assert r1["check_count"] == 14
    assert r1["mode"] in {"READINESS", "CONTROL", "INVALID"}
    assert rc1 == (0 if r1["result"] == "PASS" else 1)
