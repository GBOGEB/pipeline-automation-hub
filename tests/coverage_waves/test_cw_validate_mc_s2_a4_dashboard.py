"""Behavioural tests for mission-control/v2/adoption/validate_mc_s2_a4_dashboard.py."""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "mission-control" / "v2" / "adoption" / "validate_mc_s2_a4_dashboard.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("cw_validate_mc_s2_a4_dashboard_mod", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def mod():
    return _load_module()


SRC_BLOB = "1111111111111111111111111111111111111111"
STATUS_REL = "mission-control/v2/MC_MISSION_STATUS_CURRENT_v1.json"


class GitStub:
    def __init__(self, blob=SRC_BLOB):
        self.blob = blob
        self.calls = []

    def __call__(self, cmd, cwd=None, text=None):
        self.calls.append((list(cmd), cwd, text))
        return self.blob + "\n"


@pytest.fixture()
def git(mod, monkeypatch):
    stub = GitStub()
    monkeypatch.setattr(mod.subprocess, "check_output", stub)
    return stub


def _todo(tid, state):
    return {
        "todo_id": tid,
        "predicate": "PRED_" + tid,
        "state": state,
        "priority": "P1",
        "crew_owner": "C1",
        "runner_requirement": "NONE",
        "next_legal_transition": "CLOSE",
        "evidence_ref": "ref/" + tid,
    }


def _bundle(mod):
    t1, t2 = _todo("T1", "OPEN"), _todo("T2", "DONE")
    status = {
        "missions": [
            {
                "mission_id": "M-1",
                "mission_class": "LOCAL",
                "status": {"execution": "RUNNING"},
                "health": {"signal": "GREEN"},
                "coverage": {"maturity": "MCOV-2"},
                "progress": 0.5,
                "lifecycle": {"state": "ACTIVE"},
                "todo": {"state": "OPEN", "items": [t1, t2]},
                "metrics": {"evidence_state": "MEASURED", "core": {"work_total": None, "work_done": 3}, "custom": {}},
                "crew": {"state": "ASSIGNED", "members": [{"crew_id": "C1"}]},
                "runners": {"state": "IDLE", "items": [{"runner_id": "R1"}, {"runner_id": "R2"}]},
            },
            {"mission_id": "M-2", "mission_class": "GRAND", "metrics": {"custom": {"k": 1}}},
            {"mission_id": "M-3", "metrics": None, "crew": None, "runners": None},
        ]
    }
    unknown_proj = {
        "execution": "UNKNOWN",
        "health": "UNKNOWN",
        "progress": None,
        "mcov": "UNKNOWN",
        "lifecycle": "UNKNOWN",
        "todo_state": "UNKNOWN",
        "todo_count": 0,
        "authority_transfer": False,
        "crew": {"state": "UNKNOWN", "member_count": 0, "members": []},
        "runners": {"state": "UNKNOWN", "item_count": 0, "items": []},
    }
    summary = {
        "missions": 3,
        "by_execution": {"RUNNING": 1, "UNKNOWN": 2},
        "by_health": {"GREEN": 1, "UNKNOWN": 2},
        "by_mcov": {"MCOV-2": 1, "UNKNOWN": 2},
        "by_crew_state": {"ASSIGNED": 1, "UNKNOWN": 2},
        "by_runner_state": {"IDLE": 1, "UNKNOWN": 2},
        "crew_member_total": 1,
        "runner_item_total": 2,
        "by_metrics_evidence_state": {"MEASURED": 1, "UNKNOWN": 2},
        "metrics_custom_nonempty_mission_count": 1,
        "metrics_custom_nonempty_missions": ["M-2"],
        "metrics_core_non_null_value_count": 1,
        "todo_total": 2,
        "todo_by_state": {"OPEN": 1, "DONE": 1},
    }
    surface = {
        "schema": "missioncontrol.v2.adoption.dashboard_todo_surface.v1",
        "state": "ACTIVE_INITIAL_READ_ONLY_PROJECTION",
        "mode": "READ_ONLY_DERIVED_SURFACE",
        "authority_transfer": False,
        "formal_credit_delta": 0,
        "engineering_credit_delta": 0,
        "source": {"path": STATUS_REL, "blob": SRC_BLOB, "mission_rows": 3},
        "missions": [
            {
                "mission_id": "M-1",
                "mission_class": "LOCAL",
                "execution": "RUNNING",
                "health": "GREEN",
                "progress": 0.5,
                "mcov": "MCOV-2",
                "lifecycle": "ACTIVE",
                "todo_state": "OPEN",
                "todo_count": 2,
                "authority_transfer": False,
                "metrics": copy.deepcopy(status["missions"][0]["metrics"]),
                "crew": {"state": "ASSIGNED", "member_count": 1, "members": [{"crew_id": "C1"}]},
                "runners": {"state": "IDLE", "item_count": 2, "items": [{"runner_id": "R1"}, {"runner_id": "R2"}]},
            },
            dict(copy.deepcopy(unknown_proj), mission_id="M-2", mission_class="GRAND", metrics={"custom": {"k": 1}}),
            dict(copy.deepcopy(unknown_proj), mission_id="M-3", mission_class=None, metrics=None),
        ],
        "todos": [dict(copy.deepcopy(t1), mission_id="M-1"), dict(copy.deepcopy(t2), mission_id="M-1")],
        "summary": summary,
        "presentation_contract": {
            k: True
            for k in (
                "separate_status_progress_health_coverage",
                "mcov_not_code_coverage",
                "unknown_never_coerced_to_zero",
                "todo_predicates_preserved_verbatim",
                "dashboard_is_not_authority",
                "crew_envelope_preserved_verbatim",
                "runner_envelope_preserved_verbatim",
                "crew_member_count_derived_from_members",
                "runner_item_count_derived_from_items",
                "metrics_envelope_preserved_verbatim",
                "metrics_unknown_never_coerced_to_zero",
                "metrics_stats_are_derived_aggregates",
            )
        },
    }
    current = {
        "canonical": {
            "adoption_a3_trusted_control_disposition": mod.TRUSTED_REL,
            "adoption_a4_dashboard_todo_surface": mod.SURFACE_REL,
            "adoption_a4_dashboard_validator": mod.VALIDATOR_REL,
            "adoption_a4_dashboard_workflow": mod.WORKFLOW_REL,
            "adoption_a4_trusted_control_disposition": mod.A4_TRUSTED_REL,
            "adoption_a4_crew_runner_trusted_control": mod.CREW_TRUSTED_REL,
        },
        "adoption": {
            "active_wave": "MC-A4_DASHBOARD_AND_TODO_SURFACES",
            "next_wave": "MC-A4_DASHBOARD_AND_TODO_SURFACES",
            "a3_state": "CONTROLLED_COMPLETE_TRUSTED_CONTROL_REPAIRED",
            "a3_control_repair_state": "CONTROLLED_COMPLETE",
            "a4_state": "ACTIVE_INITIAL_READ_ONLY_PROJECTION",
            "a3_promotion_guard": "SATISFIED_BY_TRUSTED_FPC_36337930734",
            "a4_execution_allowed": True,
            "a4_trusted_control_state": "TRUSTED_CREW_RUNNER_SLICE",
            "a4_active_slice": "METRICS_STATS_VISIBILITY",
        },
    }
    base_inv = {
        "authority_transfer": False,
        "formal_credit_delta": 0,
        "engineering_credit_delta": 0,
        "historical_receipt_rewrite": False,
        "external_repository_mutation": False,
        "legacy_source_mutation": False,
    }
    trusted = {
        "schema": "missioncontrol.v2.adoption.a3_trusted_control_disposition.v1",
        "disposition": "CONTROLLED_COMPLETE_TRUSTED_CONTROL_REPAIRED",
        "exact_head": "ff94e5239e96ecede784b34bf22c4dfc14700157",
        "evidence": {
            "trusted_fpc_run": 36337930734,
            "trusted_fpc_status": "SUCCESS",
            "trusted_fpc_artifact_digest": "sha256:ef5829c105757e652afaf45928e2abe7e0b22e17c2aef338bbbd8b67d964df57",
        },
        "invariants": dict(base_inv, legacy_validator_mutation=False),
    }
    controlled = {"mission_rows": 3, "todo_rows": 2, "mode": "READ_ONLY_DERIVED_SURFACE", "source": STATUS_REL}
    a4_trusted = {
        "schema": "missioncontrol.v2.adoption.a4_trusted_control_disposition.v1",
        "disposition": "TRUSTED_INITIAL_SLICE",
        "exact_head": "b93be36c505a202bc2b1036deb328e997f62cedc",
        "merge": "0220d866e822452cf28f8b092335f64dcbd616e0",
        "evidence": {
            "a4_dashboard_run": 36383313818,
            "first_pass_closure_proof_run": 36383313909,
            "trusted_fpc_status_run": 36383416265,
            "trusted_fpc_status": "SUCCESS",
            "trusted_fpc_artifact_id": 10953123505,
            "trusted_fpc_artifact_digest": "sha256:6288f3cd40d67fb6cf450d3aa582dea280cee8c0789b02c4eca09b7a444fb020",
        },
        "controlled_surface": dict(controlled),
        "next_bounded_slice": "CREW_RUNNER_VISIBILITY",
        "invariants": dict(base_inv, dashboard_is_not_authority=True),
    }
    crew_trusted = {
        "schema": "missioncontrol.v2.adoption.a4_crew_runner_trusted_control_disposition.v1",
        "disposition": "TRUSTED_CREW_RUNNER_SLICE",
        "exact_head": "9be2701561d7d64b2e62628f6c5ebc66c91515ab",
        "merge": "4a3da830b9b299509e2f43fb52e86aa83460bdb0",
        "evidence": {
            "a3_enforcement_run": 36385095483,
            "a4_dashboard_run": 36385095455,
            "mc_v2_contract_run": 36385095397,
            "first_pass_closure_proof_run": 36385095423,
            "trusted_fpc_run": 36385164680,
            "trusted_fpc_status": "SUCCESS",
            "trusted_fpc_artifact_id": 10953679777,
            "trusted_fpc_artifact_digest": "sha256:881f9f78eabd2f3d8d777b945f8f244613eba2e7651dd23f05ce918b6bf536ed",
        },
        "controlled_surface": dict(
            controlled,
            by_crew_state={"ASSIGNED": 1, "UNKNOWN": 2},
            by_runner_state={"IDLE": 1, "UNKNOWN": 2},
            crew_member_total=1,
            runner_item_total=2,
        ),
        "next_bounded_slice": "METRICS_STATS_VISIBILITY",
        "invariants": dict(base_inv, dashboard_is_not_authority=True),
    }
    return {
        "surface": surface,
        "status": status,
        "current": current,
        "trusted": trusted,
        "a4_trusted": a4_trusted,
        "crew_trusted": crew_trusted,
    }


ORDER = ("surface", "status", "current", "trusted", "a4_trusted", "crew_trusted")


def _run(mod, b):
    return mod.validate(*(b[k] for k in ORDER))


def test_valid_synthetic_bundle_passes_and_hashes_status_file(mod, git):
    assert _run(mod, _bundle(mod)) == []
    assert git.calls == [(["git", "hash-object", STATUS_REL], mod.ROOT, True)]


def test_root_resolves_to_repository(mod):
    assert mod.ROOT == REPO_ROOT
    assert mod.STATUS == REPO_ROOT / "mission-control" / "v2" / "MC_MISSION_STATUS_CURRENT_v1.json"


def _set(doc, path, value):
    *head, last = path
    for k in head:
        doc = doc[k]
    if value is _DEL:
        doc.pop(last)
    else:
        doc[last] = value


_DEL = object()

MUTATIONS = [
    ("surface", ("schema",), "x", "A4 schema drift"),
    ("surface", ("state",), "x", "A4 state drift"),
    ("surface", ("mode",), "x", "A4 mode drift"),
    ("surface", ("authority_transfer",), 0, "A4 authority transfer"),
    ("surface", ("formal_credit_delta",), 1, "A4 formal credit"),
    ("surface", ("engineering_credit_delta",), 1, "A4 engineering credit"),
    ("current", ("canonical", "adoption_a4_dashboard_workflow"), "x", "A4 canonical workflow pointer drift"),
    ("current", ("canonical", "adoption_a4_crew_runner_trusted_control"), "x", "A4 crew-runner trusted-control pointer drift"),
    ("current", ("adoption", "a4_execution_allowed"), 1, "A4 execution not governed-admitted"),
    ("current", ("adoption", "a4_trusted_control_state"), "x", "A4 trusted-control state drift"),
    ("trusted", ("exact_head",), "x", "A4 trusted exact-head drift"),
    ("trusted", ("evidence", "trusted_fpc_run"), 1, "A4 trusted gate run drift"),
    ("trusted", ("invariants", "legacy_validator_mutation"), True, "A4 trusted disposition legacy-validator mutation drift"),
    ("a4_trusted", ("merge",), "x", "A4 trusted-control merge drift"),
    ("a4_trusted", ("evidence", "trusted_fpc_artifact_id"), 1, "A4 trusted gate artifact ID drift"),
    ("a4_trusted", ("controlled_surface", "todo_rows"), 9, "A4 trusted controlled_surface todo_rows drift"),
    ("a4_trusted", ("controlled_surface", "source"), "x", "A4 trusted controlled_surface source drift"),
    ("a4_trusted", ("next_bounded_slice",), "x", "A4 trusted next slice drift"),
    ("a4_trusted", ("invariants", "dashboard_is_not_authority"), 1, "A4 trusted dashboard-authority guard drift"),
    ("crew_trusted", ("evidence", "mc_v2_contract_run"), 1, "A4 crew-runner MC v2 run drift"),
    ("crew_trusted", ("controlled_surface", "by_crew_state"), {}, "A4 crew-runner controlled crew-state drift"),
    ("crew_trusted", ("controlled_surface", "crew_member_total"), 0, "A4 crew-runner controlled crew total drift"),
    ("crew_trusted", ("invariants", "engineering_credit_delta"), 2, "A4 crew-runner engineering credit drift"),
    ("surface", ("source", "path"), "x", "A4 source path drift"),
    ("surface", ("source", "mission_rows"), 0, "A4 source mission_rows drift"),
    ("surface", ("missions", 0, "progress"), 0.9, "M-1 progress drift"),
    ("surface", ("missions", 0, "lifecycle"), "x", "M-1 lifecycle drift"),
    ("surface", ("missions", 0, "todo_count"), 0, "M-1 TODO count drift"),
    ("surface", ("missions", 1, "authority_transfer"), True, "M-2 authority transfer"),
    ("surface", ("missions", 1, "metrics"), {}, "M-2 metrics envelope drift"),
    ("surface", ("missions", 0, "crew", "member_count"), 7, "M-1 crew member_count drift"),
    ("surface", ("missions", 2, "runners", "items"), [{"runner_id": "X"}], "M-3 runner items drift"),
    ("surface", ("summary", "missions"), 2, "A4 mission summary drift"),
    ("surface", ("summary", "by_mcov"), {}, "A4 MCOV summary drift"),
    ("surface", ("summary", "metrics_custom_nonempty_mission_count"), 0, "A4 metrics custom mission-count drift"),
    ("surface", ("summary", "todo_total"), 3, "A4 TODO total drift"),
    ("surface", ("todos", 1, "evidence_ref"), "other", "A4 TODO field drift ('M-1', 'T2') evidence_ref"),
    ("surface", ("todos", 0, "priority"), _DEL, "A4 TODO field missing ('M-1', 'T1') priority"),
    ("surface", ("presentation_contract", "mcov_not_code_coverage"), _DEL, "A4 presentation contract weakened: mcov_not_code_coverage"),
]


@pytest.mark.parametrize("doc,path,value,message", MUTATIONS, ids=[m[3] for m in MUTATIONS])
def test_single_drift_is_reported(mod, git, doc, path, value, message):
    b = _bundle(mod)
    _set(b[doc], path, value)
    errors = _run(mod, b)
    assert message in errors


def test_missing_sections_default_to_empty_and_fail_closed(mod, git):
    b = _bundle(mod)
    for k in ("trusted", "a4_trusted", "crew_trusted"):
        b[k] = {}
    b["current"] = {}
    errors = _run(mod, b)
    assert "A4 trusted disposition pointer drift" in errors
    assert "A4 not active" in errors
    assert "A4 trusted gate status drift" in errors
    assert "A4 crew-runner trusted artifact digest drift" in errors


def test_source_blob_mismatch_is_reported(mod, monkeypatch):
    monkeypatch.setattr(mod.subprocess, "check_output", GitStub("2" * 40))
    assert _run(mod, _bundle(mod)) == ["A4 source blob drift"]


def test_mission_set_and_duplicate_identity(mod, git):
    b = _bundle(mod)
    b["surface"]["missions"].append(copy.deepcopy(b["surface"]["missions"][0]))
    assert "A4 duplicate mission identity" in _run(mod, b)

    b = _bundle(mod)
    b["status"]["missions"].append(copy.deepcopy(b["status"]["missions"][2]))
    assert "canonical mission identity duplicate" in _run(mod, b)

    b = _bundle(mod)
    b["surface"]["missions"] = b["surface"]["missions"][:2]
    errors = _run(mod, b)
    assert "A4 mission-set drift" in errors
    # Missing projection is compared against an empty row.
    assert "M-3 authority transfer" in errors


def test_todo_identity_duplicates_and_set_drift(mod, git):
    b = _bundle(mod)
    b["surface"]["todos"].append(copy.deepcopy(b["surface"]["todos"][0]))
    assert "A4 duplicate TODO identity" in _run(mod, b)

    b = _bundle(mod)
    b["status"]["missions"][0]["todo"]["items"][1]["todo_id"] = "T1"
    errors = _run(mod, b)
    assert "canonical TODO identity duplicate" in errors
    assert "A4 TODO identity-set drift" in errors

    b = _bundle(mod)
    b["surface"]["todos"].pop()
    errors = _run(mod, b)
    assert "A4 TODO identity-set drift" in errors
    assert any(e.startswith("A4 TODO field missing ('M-1', 'T2')") for e in errors)


def test_metrics_aggregates_count_only_non_null_core_and_nonempty_custom(mod, git):
    b = _bundle(mod)
    m = b["status"]["missions"][0]["metrics"]
    m["core"]["work_total"] = 0  # 0 is a value, not unknown
    b["surface"]["missions"][0]["metrics"] = copy.deepcopy(m)
    errors = _run(mod, b)
    assert errors == ["A4 metrics core non-null count drift"]
    b["surface"]["summary"]["metrics_core_non_null_value_count"] = 2
    assert _run(mod, b) == []


def test_self_test_accepts_valid_bundle(mod, git):
    b = _bundle(mod)
    snapshot = copy.deepcopy(b)
    mod.self_test(*(b[k] for k in ORDER))
    assert b == snapshot  # mutations are on deep copies only


def test_self_test_fails_when_validator_is_blind(mod, monkeypatch):
    monkeypatch.setattr(mod, "validate", lambda *a: [])
    with pytest.raises(AssertionError):
        mod.self_test(*(_bundle(mod)[k] for k in ORDER))


def _write_bundle(mod, monkeypatch, tmp_path, b):
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    for name, key in (
        ("SURFACE", "surface"),
        ("STATUS", "status"),
        ("CURRENT", "current"),
        ("TRUSTED", "trusted"),
        ("A4_TRUSTED", "a4_trusted"),
        ("CREW_TRUSTED", "crew_trusted"),
    ):
        p = tmp_path / (key + ".json")
        p.write_text(json.dumps(b[key]), encoding="utf-8")
        monkeypatch.setattr(mod, name, p)


def test_main_pass_receipt(mod, git, monkeypatch, tmp_path, capsys):
    _write_bundle(mod, monkeypatch, tmp_path, _bundle(mod))
    monkeypatch.setattr(sys, "argv", ["validate_mc_s2_a4_dashboard.py"])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["result"] == "PASS"
    assert receipt["schema"] == "missioncontrol.v2.adoption.a4_dashboard_validation_receipt.v1"
    assert (receipt["mission_rows"], receipt["todo_rows"]) == (3, 2)
    assert receipt["errors"] == []
    assert receipt["authority_transfer"] is False
    assert git.calls[0][0] == ["git", "hash-object", "status.json"]
    assert git.calls[0][1] == tmp_path


def test_main_fail_receipt(mod, git, monkeypatch, tmp_path, capsys):
    b = _bundle(mod)
    b["surface"]["state"] = "RETIRED"
    _write_bundle(mod, monkeypatch, tmp_path, b)
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 1
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["result"] == "FAIL"
    assert receipt["errors"] == ["A4 state drift"]


def test_load_reads_utf8_json(mod, tmp_path):
    p = tmp_path / "doc.json"
    p.write_text(json.dumps({"name": "été"}), encoding="utf-8")
    assert mod.load(p) == {"name": "été"}


def test_committed_surface_validates_offline(mod, monkeypatch):
    surface = mod.load(mod.SURFACE)
    docs = [surface, mod.load(mod.STATUS), mod.load(mod.CURRENT), mod.load(mod.TRUSTED), mod.load(mod.A4_TRUSTED), mod.load(mod.CREW_TRUSTED)]
    monkeypatch.setattr(mod.subprocess, "check_output", GitStub(surface["source"]["blob"]))
    assert mod.validate(*docs) == []
