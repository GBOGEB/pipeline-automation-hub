"""Behavioural tests for mission-control/grand-missions/validate_gm_iv_evidence_economics.py."""
import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_DIR = REPO_ROOT / "mission-control" / "grand-missions"
MOD_PATH = MOD_DIR / "validate_gm_iv_evidence_economics.py"


def _load():
    spec = importlib.util.spec_from_file_location("cw_validate_gm_iv_evidence_economics", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = _load()

ALL8 = ["GM-IV-F%02d" % i for i in range(1, 9)]
FIRST4 = ALL8[:4]
LAST4 = ALL8[4:]


def _row(row_id, units, seconds, **extra):
    row = {
        "row_id": row_id,
        "evidence_class": "MEASURED",
        "crew_time_seconds": None,
        "crew_time_status": "NOT_INSTRUMENTED",
        "slot_bound": False,
        "child_bound": False,
        "authority_transfer": False,
        "accepted_evidence_units": units,
        "execute_seconds": seconds,
        "evidence_rate": units / seconds if seconds else 0.0,
    }
    row.update(extra)
    return row


def _docs(active8=True):
    inv = {
        "mission_stage": "ACTIVE_8_OF_8" if active8 else "RECON_4_OF_8",
        "canonical_children_bound": 0,
        "named_recon_frontiers": ALL8 if active8 else FIRST4,
        "controlled_pilot_frontiers": ["GM-IV-F01", "GM-IV-F03"],
        "reference_frontiers": ["GM-IV-F02", "GM-IV-F04"],
        "unfilled_frontier_slots": [] if active8 else LAST4,
        "f03_child_bound": False,
        "f04_child_bound": False,
        "pilot_frontier_labels_do_not_imply_children": True,
        "gm_v_state": "HELD",
    }
    gm4 = {
        "id": "GM-IV",
        "state": "ACTIVE_8_OF_8" if active8 else "STAGED_ACTIVE_RECON_4_OF_8",
        "activation_stage": "ACTIVE_8_OF_8" if active8 else "RECON_4_OF_8",
        "children": [],
        "candidate_frontiers": ALL8 if active8 else FIRST4,
        "controlled_pilot_frontiers": ["GM-IV-F01", "GM-IV-F03"],
        "reference_frontiers": ["GM-IV-F02", "GM-IV-F04"],
        "unfilled_frontier_slots": [] if active8 else LAST4,
    }
    if active8:
        inv["new_candidate_recon_frontiers"] = LAST4
        gm4["new_candidate_recon_frontiers"] = LAST4
    ledger = {
        "authority_transfer": False,
        "model_scope": {
            "evidence_economics_models": "LOCAL_GMIV_RING2_ECONOMICS_ONLY",
            "global_model_context": "SEPARATE_MEASURED_CREW_PC3_AND_X",
        },
        "fleet_invariant": inv,
        "rows": [
            _row("GMIV_RING2_SCOUT_B_PROVENANCE_PASS", 5, 1),
            _row("GMIV_RING2_SCOUT_B_FULL_RUNTIME_PRUNED", 1, 10, payload_execute_seconds=62,
                 disposition="PRUNE_FULL_RUNTIME_KEEP_PROVENANCE_REFERENCE"),
            _row("ZERO_EXECUTE", 0, 0),
        ],
        "pca_gate": {"state": "DEFER"},
        "bt_gate": {"state": "DEFER"},
    }
    registry = {"grand_missions": [gm4, {"id": "GM-V", "state": "HELD", "children": []}]}
    return ledger, registry


def _run(tmp_path, monkeypatch, ledger, registry, capsys):
    lp = tmp_path / "ledger.json"
    rp = tmp_path / "registry.json"
    lp.write_text(json.dumps(ledger), encoding="utf-8")
    rp.write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setattr(m, "LEDGER", lp)
    monkeypatch.setattr(m, "REGISTRY", rp)
    rc = m.main()
    return rc, json.loads(capsys.readouterr().out)


def _failed(receipt):
    return [c["name"] for c in receipt["checks"] if not c["pass"]]


def test_active8_pass(tmp_path, monkeypatch, capsys):
    ledger, registry = _docs(active8=True)
    rc, receipt = _run(tmp_path, monkeypatch, ledger, registry, capsys)
    assert rc == 0
    assert receipt["status"] == "PASS"
    assert receipt["passed"] == receipt["denominator"] == 18
    assert receipt["fleet_invariant"] == "GM-IV ACTIVE_8_OF_8; children=0; GM-V HELD"
    names = [c["name"] for c in receipt["checks"]]
    assert "06b_active8_new_candidates" in names
    ratio_check = next(c for c in receipt["checks"] if c["name"] == "14_provenance_efficiency_signal")
    assert ratio_check["detail"] == "ratio=50.000000"


def test_recon4_pass_has_no_06b(tmp_path, monkeypatch, capsys):
    ledger, registry = _docs(active8=False)
    rc, receipt = _run(tmp_path, monkeypatch, ledger, registry, capsys)
    assert rc == 0
    assert receipt["denominator"] == 17
    assert receipt["fleet_invariant"] == "GM-IV RECON_4_OF_8; children=0; GM-V HELD"
    names = [c["name"] for c in receipt["checks"]]
    assert "06b_active8_new_candidates" not in names
    unfilled = next(c for c in receipt["checks"] if c["name"] == "06_frontier_slot_state")
    assert unfilled["detail"] == "unfilled=" + str(LAST4)


def test_recon4_ledger_against_active8_registry_fails_stage(tmp_path, monkeypatch, capsys):
    ledger, _ = _docs(active8=False)
    _, registry = _docs(active8=True)
    rc, receipt = _run(tmp_path, monkeypatch, ledger, registry, capsys)
    assert rc == 1
    assert receipt["status"] == "FAIL"
    assert _failed(receipt) == [
        "01_stage_sync", "03_named_frontiers", "06_frontier_slot_state", "06b_active8_new_candidates",
    ]


def _rows(ledger):
    return ledger["rows"]


@pytest.mark.parametrize(
    "mutate, failed",
    [
        (lambda l, r: l["fleet_invariant"].update(canonical_children_bound=1), ["02_zero_children"]),
        (lambda l, r: r["grand_missions"][0].update(controlled_pilot_frontiers=["GM-IV-F01"]), ["04_controlled_pilot_pair"]),
        (lambda l, r: l["fleet_invariant"].update(reference_frontiers=[]), ["05_reference_frontiers"]),
        (lambda l, r: l["fleet_invariant"].update(f04_child_bound=True), ["07_no_child_binding_or_authority_leakage"]),
        (lambda l, r: r["grand_missions"][1].update(children=["x"]), ["08_gmv_held"]),
        (lambda l, r: _rows(l)[2].update(evidence_class="ESTIMATED"), ["09_three_measured_rows"]),
        (lambda l, r: _rows(l)[0].update(crew_time_seconds=5), ["10_no_fabricated_crew_time"]),
        (lambda l, r: _rows(l)[1].update(slot_bound=True), ["11_no_slot_or_child_binding_from_economics"]),
        (lambda l, r: _rows(l)[2].update(authority_transfer=True), ["12_no_authority_transfer"]),
        (lambda l, r: _rows(l)[2].update(evidence_rate=0.5), ["13_evidence_rate_math"]),
        (lambda l, r: _rows(l)[1].update(payload_execute_seconds=61), ["14_provenance_efficiency_signal"]),
        (lambda l, r: _rows(l)[1].update(disposition="KEEP"), ["15_pruned_runtime_disposition"]),
        (lambda l, r: l["model_scope"].update(global_model_context="NONE"), ["16_local_model_scope"]),
        (lambda l, r: l["pca_gate"].update(state="PASS"), ["17_pca_bt_fail_closed_locally"]),
        (lambda l, r: l.update(authority_transfer=True),
         ["07_no_child_binding_or_authority_leakage", "12_no_authority_transfer"]),
        (lambda l, r: r["grand_missions"][0].update(children=["c"]),
         ["02_zero_children", "07_no_child_binding_or_authority_leakage"]),
    ],
)
def test_single_mutation_failures(tmp_path, monkeypatch, capsys, mutate, failed):
    ledger, registry = _docs(active8=True)
    mutate(ledger, registry)
    rc, receipt = _run(tmp_path, monkeypatch, ledger, registry, capsys)
    assert rc == 1
    assert _failed(receipt) == failed
    assert receipt["passed"] == receipt["denominator"] - len(failed)


def test_low_efficiency_ratio_fails(tmp_path, monkeypatch, capsys):
    ledger, registry = _docs(active8=True)
    _rows(ledger)[0].update(accepted_evidence_units=4, execute_seconds=1, evidence_rate=4.0)
    rc, receipt = _run(tmp_path, monkeypatch, ledger, registry, capsys)
    assert rc == 1
    assert _failed(receipt) == ["14_provenance_efficiency_signal"]


def test_missing_named_row_raises(tmp_path, monkeypatch, capsys):
    ledger, registry = _docs(active8=True)
    _rows(ledger)[0]["row_id"] = "OTHER"
    with pytest.raises(KeyError):
        _run(tmp_path, monkeypatch, ledger, registry, capsys)


def test_real_committed_ledger_passes(capsys):
    # Offline check against the committed ledger and registry (no path patching).
    rc = m.main()
    receipt = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert receipt["status"] == "PASS"
    assert receipt["authority_transfer"] is False
