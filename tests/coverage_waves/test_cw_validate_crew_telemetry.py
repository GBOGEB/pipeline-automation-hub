"""Behavioural tests for mission-control/qps-triage-ultra/crew/validate_crew_telemetry.py."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "mission-control" / "qps-triage-ultra" / "crew" / "validate_crew_telemetry.py"


def _load():
    spec = importlib.util.spec_from_file_location("cw_validate_crew_telemetry_mod", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


vct = _load()


def _dataset():
    return {
        "CREW_REGISTRY_v1.json": {
            "crew": [
                {"crew_id": "U1", "maturity": "OBSERVED"},
                {"crew_id": "S1", "maturity": "PARTIAL"},
                {"crew_id": "C1", "maturity": "CONCEPTUAL"},
            ]
        },
        "CREW_SNAPSHOT_2026-09-13.json": {
            "fleet_population": {
                "permanent_home_seats": 1,
                "observed_or_partial_specialists": 1,
                "conceptual_candidates": 1,
                "total_registered_records": 3,
            },
            "live_observations": [
                {
                    "event_id": "E1",
                    "crew_id": "U1",
                    "event_type": "RUN_STEP",
                    "state": "OK",
                    "evidence_class": "MEASURED",
                    "steps_executed": 2,
                },
                {
                    "event_id": "E2",
                    "crew_id": "S1",
                    "event_type": "HEARTBEAT",
                    "state": "OK",
                    "evidence_class": "MEASURED",
                    "steps_executed": 0,
                },
            ],
            "competency_promotion": {"promotions_this_snapshot": 0},
        },
        "ROLE_GAP_POLICY_v1.json": {
            "trial_requirements": ["trial_id", "candidate_role_id", "state"],
            "authority_transfer": False,
        },
        "ROLE_GAP_SIGNALS_SEED_2026-09-13.json": {
            "evidence_class": "EXPERT_SEEDED_NOT_MEASURED",
            "candidates": [{"candidate_role_id": "C1"}],
        },
        "ROLE_TRIALS_v1.json": {
            "authority_transfer": False,
            "trials": [
                {
                    "trial_id": "T1",
                    "candidate_role_id": "C1",
                    "state": "PLANNED_NOT_ACTIVATED",
                    "promotion_after_success": "PARTIAL_ONLY",
                    "mentor_or_challenger": "U1",
                    "success_condition": "passes",
                    "failure_condition": "fails",
                    "competency_target_profile": {"d1": 3, "d2": 6},
                }
            ],
        },
        "CREW_TELEMETRY_SCHEMA_v1.json": {
            "event_required": ["event_id", "crew_id", "event_type", "state", "evidence_class"],
            "event_types": ["RUN_STEP", "HEARTBEAT"],
            "states": ["OK"],
            "evidence_classes": ["MEASURED"],
        },
        "COMPETENCY_MATRIX_v1.json": {"dimensions": ["d1", "d2"]},
    }


def _write(root: Path, data: dict) -> None:
    for name, payload in data.items():
        (root / name).write_text(json.dumps(payload), encoding="utf-8")


def _run(tmp_path, monkeypatch, data):
    _write(tmp_path, data)
    monkeypatch.setattr(vct, "ROOT", tmp_path)
    vct.main()


def test_load_reads_json_relative_to_root(tmp_path, monkeypatch):
    (tmp_path / "x.json").write_text('{"a": 1}', encoding="utf-8")
    monkeypatch.setattr(vct, "ROOT", tmp_path)
    assert vct.load("x.json") == {"a": 1}


def test_fail_prints_and_exits_1(capsys):
    with pytest.raises(SystemExit) as exc:
        vct.fail("boom")
    assert exc.value.code == 1
    assert capsys.readouterr().out.strip() == "FAIL: boom"


def test_require_fields_passes_and_reports_sorted_missing(capsys):
    vct.require_fields({"a": 1, "b": 2}, ["a", "b"], "ctx")
    with pytest.raises(SystemExit):
        vct.require_fields({"a": 1}, ["c", "b", "a"], "ctx")
    assert "ctx missing required fields ['b', 'c']" in capsys.readouterr().out


def test_valid_synthetic_dataset_passes(tmp_path, monkeypatch, capsys):
    _run(tmp_path, monkeypatch, _dataset())
    out = json.loads(capsys.readouterr().out)
    assert out == {
        "authority_transfer": False,
        "competency_promotions": 0,
        "crew_records": 3,
        "event_required_fields": 5,
        "live_events": 2,
        "planned_trials": 1,
        "seed_role_gap_candidates": 1,
        "status": "PASS_CREW_TELEMETRY_STRUCTURE",
        "trial_required_fields": 3,
    }


def test_real_committed_crew_data_passes(capsys):
    vct.main()
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "PASS_CREW_TELEMETRY_STRUCTURE"
    assert out["authority_transfer"] is False
    assert out["competency_promotions"] == 0


REG = "CREW_REGISTRY_v1.json"
SNAP = "CREW_SNAPSHOT_2026-09-13.json"
POL = "ROLE_GAP_POLICY_v1.json"
SIG = "ROLE_GAP_SIGNALS_SEED_2026-09-13.json"
TRI = "ROLE_TRIALS_v1.json"
TEL = "CREW_TELEMETRY_SCHEMA_v1.json"


def _dup_crew(d):
    d[REG]["crew"].append({"crew_id": "U1", "maturity": "OBSERVED"})


def _home(d):
    d[SNAP]["fleet_population"]["permanent_home_seats"] = 2


def _spec(d):
    d[SNAP]["fleet_population"]["observed_or_partial_specialists"] = 0


def _concept(d):
    d[SNAP]["fleet_population"]["conceptual_candidates"] = 5


def _total(d):
    d[SNAP]["fleet_population"]["total_registered_records"] = 9


def _no_event_required(d):
    del d[TEL]["event_required"]


def _event_missing_id(d):
    del d[SNAP]["live_observations"][0]["event_id"]


def _event_missing_state(d):
    del d[SNAP]["live_observations"][0]["state"]


def _unknown_crew(d):
    d[SNAP]["live_observations"][0]["crew_id"] = "ZZ"


def _bad_type(d):
    d[SNAP]["live_observations"][0]["event_type"] = "NOPE"


def _bad_state(d):
    d[SNAP]["live_observations"][0]["state"] = "WEIRD"


def _bad_evidence(d):
    d[SNAP]["live_observations"][0]["evidence_class"] = "GUESSED"


def _zero_step(d):
    d[SNAP]["live_observations"][0]["steps_executed"] = 0


def _promotion(d):
    d[SNAP]["competency_promotion"]["promotions_this_snapshot"] = 1


def _signals_measured(d):
    d[SIG]["evidence_class"] = "MEASURED"


def _candidate_missing(d):
    d[SIG]["candidates"].append({"candidate_role_id": "C9"})


def _candidate_promoted(d):
    d[SIG]["candidates"].append({"candidate_role_id": "S1"})


def _no_trial_req(d):
    d[POL]["trial_requirements"] = []


def _dup_trial(d):
    d[TRI]["trials"].append(dict(d[TRI]["trials"][0]))


def _trial_missing_field(d):
    d[POL]["trial_requirements"].append("budget")


def _trial_unknown_role(d):
    d[TRI]["trials"][0]["candidate_role_id"] = "C9"


def _trial_promoted_role(d):
    d[TRI]["trials"][0]["candidate_role_id"] = "S1"


def _trial_active(d):
    d[TRI]["trials"][0]["state"] = "ACTIVE"


def _trial_jump(d):
    d[TRI]["trials"][0]["promotion_after_success"] = "OBSERVED"


def _no_mentor(d):
    d[TRI]["trials"][0]["mentor_or_challenger"] = ""


def _no_success(d):
    del d[TRI]["trials"][0]["success_condition"]


def _no_failure(d):
    d[TRI]["trials"][0]["failure_condition"] = ""


def _profile_dims(d):
    d[TRI]["trials"][0]["competency_target_profile"] = {"d1": 3}


def _profile_range(d):
    d[TRI]["trials"][0]["competency_target_profile"]["d2"] = 7


def _profile_type(d):
    d[TRI]["trials"][0]["competency_target_profile"]["d1"] = 2.5


def _policy_authority(d):
    d[POL]["authority_transfer"] = True


def _trials_authority_missing(d):
    del d[TRI]["authority_transfer"]


@pytest.mark.parametrize(
    "mutate, message",
    [
        (_dup_crew, "duplicate crew_id"),
        (_home, "HOME seat count mismatch"),
        (_spec, "specialist count mismatch"),
        (_concept, "conceptual count mismatch"),
        (_total, "total crew count mismatch"),
        (_no_event_required, "telemetry event_required contract must not be empty"),
        (_event_missing_id, "telemetry event <missing> missing required fields ['event_id']"),
        (_event_missing_state, "telemetry event E1 missing required fields ['state']"),
        (_unknown_crew, "unknown telemetry crew ZZ"),
        (_bad_type, "unregistered event type NOPE"),
        (_bad_state, "unregistered telemetry state WEIRD"),
        (_bad_evidence, "unregistered evidence class GUESSED"),
        (_zero_step, "zero-step runtime event cannot represent execution/accept/control"),
        (_promotion, "seed snapshot must not promote competence"),
        (_signals_measured, "seed signals must remain expert-seeded"),
        (_candidate_missing, "role-gap candidate C9 missing from registry"),
        (_candidate_promoted, "role-gap candidate S1 must remain conceptual"),
        (_no_trial_req, "role-gap policy trial_requirements must not be empty"),
        (_dup_trial, "duplicate trial id T1"),
        (_trial_missing_field, "trial T1 missing required fields ['budget']"),
        (_trial_unknown_role, "trial references unknown role C9"),
        (_trial_promoted_role, "planned trial role S1 already promoted"),
        (_trial_active, "seed trial T1 must not auto-activate"),
        (_trial_jump, "trial T1 cannot jump directly to observed/control"),
        (_no_mentor, "trial T1 missing mentor/challenger"),
        (_no_success, "trial T1 missing success/failure bounds"),
        (_no_failure, "trial T1 missing success/failure bounds"),
        (_profile_dims, "competency_target_profile must exactly match registered dimensions"),
        (_profile_range, "competency_target_profile values must be integers 0..6"),
        (_profile_type, "competency_target_profile values must be integers 0..6"),
        (_policy_authority, "authority transfer must remain false"),
        (_trials_authority_missing, "authority transfer must remain false"),
    ],
)
def test_invalid_dataset_fails(tmp_path, monkeypatch, capsys, mutate, message):
    data = _dataset()
    mutate(data)
    with pytest.raises(SystemExit) as exc:
        _run(tmp_path, monkeypatch, data)
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert out.startswith("FAIL: ")
    assert message in out
