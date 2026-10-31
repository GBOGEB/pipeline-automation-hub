"""Behavioural tests for mission-control/v2/adoption/validate_mc_s2_a3_projection.py."""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "mission-control" / "v2" / "adoption" / "validate_mc_s2_a3_projection.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("cw_validate_mc_s2_a3_projection_mod", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def mod():
    return _load_module()


def _blob(path):
    return "blob:" + path


class GitStub:
    """Deterministic stand-in for `git hash-object <path>`."""

    def __init__(self, overrides=None):
        self.overrides = dict(overrides or {})
        self.calls = []

    def __call__(self, cmd, cwd=None, text=None):
        self.calls.append((list(cmd), cwd, text))
        path = cmd[2]
        return self.overrides.get(path, _blob(path)) + "\n"


@pytest.fixture()
def git(mod, monkeypatch):
    stub = GitStub()
    monkeypatch.setattr(mod.subprocess, "check_output", stub)
    return stub


HEAD = "ff94e5239e96ecede784b34bf22c4dfc14700157"
DIGEST = "sha256:ef5829c105757e652afaf45928e2abe7e0b22e17c2aef338bbbd8b67d964df57"
A4 = "MC-A4_DASHBOARD_AND_TODO_SURFACES"
REPAIRED = "CONTROLLED_COMPLETE_TRUSTED_CONTROL_REPAIRED"
CANDIDATE = "CANDIDATE_DRAFT_WAIT_EXACT_HEAD_PROOF"


def _bundle(mod):
    tel_gm = {"mission_id": "GM-I-C", "authority_transfer": False, "todo": {"items": [{"predicate": "NORM_GM"}]}}
    tel_lm10 = {
        "mission_id": "LM-10",
        "authority_transfer": False,
        "lifecycle": {"state": "CLOSED"},
        "status": {"execution": "DONE"},
    }
    tel_lm11 = {
        "mission_id": "LM-11",
        "authority_transfer": False,
        "lifecycle": {"state": "ACTIVE"},
        "status": {"execution": "BLOCKED"},
        "metrics": {"custom": {"zero_step_reproduced": True}},
    }

    def binding(path):
        return {"path": path, "blob": _blob(path)}

    enforcement = {
        "schema": "missioncontrol.v2.adoption.validator_enforcement.v1",
        "mode": "ADDITIVE_FAIL_CLOSED_CROSS_CHECK",
        "authority_transfer": False,
        "formal_credit_delta": 0,
        "engineering_credit_delta": 0,
        "postmerge_trusted_control_repair": {
            "state": REPAIRED,
            "receipt": mod.POSTMERGE_REPAIR_REL,
            "disposition_receipt": mod.TRUSTED_DISPOSITION_REL,
            "authority_transfer": False,
            "formal_credit_delta": 0,
            "engineering_credit_delta": 0,
            "trusted_fpc": {
                "run_id": 36337930734,
                "status": "SUCCESS",
                "head_sha": HEAD,
                "artifact_id": 4242,
                "artifact_digest": DIGEST,
            },
        },
        "mutation_policy": {
            k: False
            for k in (
                "legacy_validator_edit",
                "legacy_source_edit",
                "historical_receipt_rewrite",
                "domain_authority_replacement",
                "external_repository_mutation",
            )
        },
        "legacy_validators": [
            {"id": vid, "mission_id": mid, "path": path, "blob": _blob(path), "immutable_in_mc_a3": True}
            for vid, (mid, path) in mod.REQUIRED_LEGACY_VALIDATORS.items()
        ],
        "projection_contract": {
            "required_projection_ids": ["P-GM", "P-LM10", "P-LM11"],
            "required_mission_ids": ["GM-I-C", "LM-10", "LM-11"],
        },
        "semantic_cross_checks": {
            "GM-I-C": {"source_first_red": "FR_GM", "normalized_v2_todo_predicate": "NORM_GM", "relation": "RELATED_NOT_IDENTICAL"},
            "LM-10": {
                "source_state": "CLOSED_SRC",
                "normalized_lifecycle": "CLOSED",
                "normalized_status": "DONE",
                "required_legacy_assertions": ["AS1", "AS2"],
            },
            "LM-11": {
                "source_state": "OPEN_SRC",
                "source_first_red": "FR_LM11",
                "normalized_lifecycle": "ACTIVE",
                "normalized_status": "BLOCKED",
                "zero_step_application_failure": False,
            },
        },
        "basis": {
            "a1": binding("x/a1.json"),
            "a2": binding("x/a2.json"),
            "telemetry": binding("x/status.json"),
            "official_register": binding("x/official.yaml"),
        },
        "source_controls": [binding("x/control.py")],
    }
    a1 = {"mode": "READ_ONLY_CENSUS", "authority_transfer": False, "mc_a2_candidates": ["C1", "C2"]}
    a2 = {
        "authority_transfer": False,
        "projection_policy": {
            "mode": "READ_ONLY_ADDITIVE",
            "legacy_identity_assertions_remain_authoritative": True,
            "historical_receipts_rewritten": False,
        },
        "a1_candidate_coverage": {"admitted_consumer_ids": ["C1", "C2"], "projected_consumer_ids": ["C2", "C1"], "parity": True},
        "projections": [
            {"projection_id": "P-GM", "mission_id": "GM-I-C", "current_telemetry": copy.deepcopy(tel_gm), "source_bindings": [binding("src/gm.json")]},
            {
                "projection_id": "P-LM10",
                "mission_id": "LM-10",
                "current_telemetry": copy.deepcopy(tel_lm10),
                "preserved_assertions": ["AS1", "AS2", "AS3"],
                "source_bindings": [binding("src/lm10.json"), binding("src/lm10b.json")],
            },
            {"projection_id": "P-LM11", "mission_id": "LM-11", "current_telemetry": copy.deepcopy(tel_lm11), "source_bindings": [binding("src/lm11.json")]},
        ],
    }
    status = {"missions": [tel_gm, tel_lm10, tel_lm11]}
    official = {
        "mission_control_operating_model": {
            "current": "mission-control/v2/MISSION_CONTROL_CURRENT_v2.json",
            "mission_telemetry": "mission-control/v2/MC_MISSION_STATUS_CURRENT_v1.json",
            "rule": "V2_GOVERNS_NEW_ORCHESTRATION_SEMANTICS_WITHOUT_REWRITING_HISTORICAL_MISSION_AUTHORITY",
        },
        "variants": [{"id": "GM-I-C", "first_red": "FR_GM"}],
        "local_missions": [{"id": "LM-10", "state": "CLOSED_SRC"}, {"id": "LM-11", "state": "OPEN_SRC", "first_red": "FR_LM11"}],
    }
    current = {
        "canonical": {
            "adoption_a3_postmerge_trusted_control": mod.POSTMERGE_REPAIR_REL,
            "adoption_a3_trusted_control_disposition": mod.TRUSTED_DISPOSITION_REL,
        },
        "adoption": {
            "completed_waves": ["MC-A1", "MC-A3_VALIDATOR_ENFORCEMENT"],
            "next_wave": A4,
            "authority_transfer": False,
            "formal_credit_delta": 0,
            "engineering_credit_delta": 0,
            "active_wave": A4,
            "a3_state": REPAIRED,
            "a3_control_repair_state": "CONTROLLED_COMPLETE",
            "a4_state": "ACTIVE_INITIAL_READ_ONLY_PROJECTION",
            "a4_execution_allowed": True,
            "a3_promotion_guard": "SATISFIED_BY_TRUSTED_FPC_36337930734",
        },
    }
    repair = {
        "schema": "missioncontrol.v2.adoption.a3_postmerge_trusted_control_repair.v1",
        "wave_id": "MC-A3_VALIDATOR_ENFORCEMENT",
        "reason": "PR457_MERGED_BEFORE_TRUSTED_FPC_COMPLETED",
        "control_repair_policy": {
            k: True
            for k in (
                "this_pr_is_draft_until_exact_head_candidate_proofs_complete",
                "this_pr_must_run_a3_enforcement",
                "this_pr_must_run_mc_v2_contract",
                "this_pr_must_run_first_pass_closure_proof",
                "this_pr_must_have_clean_exact_head_codex_review",
                "mark_ready_only_after_candidate_proofs_and_review",
                "trusted_fpc_success_required_after_ready",
                "merge_only_after_trusted_fpc_success",
                "a4_execution_forbidden_until_merge",
            )
        },
        "invariants": {"authority_transfer": False, "formal_credit_delta": 0, "engineering_credit_delta": 0},
        "intended_postmerge_state": {"a3_state": REPAIRED, "a4_state": "ADMITTED_PENDING_IMPLEMENTATION", "next_wave": A4},
    }
    trusted = {
        "schema": "missioncontrol.v2.adoption.a3_trusted_control_disposition.v1",
        "disposition": REPAIRED,
        "exact_head": HEAD,
        "next_wave": A4,
        "evidence": {
            "a3_enforcement_run": 36337747720,
            "fpc_proof_run": 36337747734,
            "trusted_fpc_run": 36337930734,
            "trusted_fpc_status": "SUCCESS",
            "trusted_fpc_artifact_id": 4242,
            "trusted_fpc_artifact_digest": DIGEST,
        },
        "invariants": {
            "authority_transfer": False,
            "formal_credit_delta": 0,
            "engineering_credit_delta": 0,
            "legacy_validator_mutation": False,
            "legacy_source_mutation": False,
            "historical_receipt_rewrite": False,
            "external_repository_mutation": False,
        },
    }
    return {
        "enforcement": enforcement,
        "a1": a1,
        "a2": a2,
        "status": status,
        "official": official,
        "current": current,
        "repair": repair,
        "trusted": trusted,
    }


def _proj(b, mission_id):
    return next(p for p in b["a2"]["projections"] if p["mission_id"] == mission_id)


# ---------------------------------------------------------------- git_blob


def test_git_blob_strips_output_and_runs_in_root(mod, git):
    assert mod.git_blob("a/b.json") == "blob:a/b.json"
    assert git.calls == [(["git", "hash-object", "a/b.json"], mod.ROOT, True)]


def test_root_resolves_to_repository(mod):
    assert mod.ROOT == REPO_ROOT
    assert mod.OFFICIAL == REPO_ROOT / "mission-control" / "OFFICIAL_MISSION_REGISTER_v1.yaml"


# ---------------------------------------------------------------- validate_documents


def test_valid_repaired_bundle_has_no_errors(mod):
    assert mod.validate_documents(**_bundle(mod)) == []


def test_candidate_lifecycle_branch_accepts_blocked_a4(mod):
    b = _bundle(mod)
    b["enforcement"]["postmerge_trusted_control_repair"]["state"] = CANDIDATE
    b["current"]["adoption"].update(
        active_wave="MC-A3_POSTMERGE_TRUSTED_CONTROL_REPAIR",
        a3_state="CONTROLLED_COMPLETE_PENDING_TRUSTED_CONTROL_REPAIR",
        a3_control_repair_state=CANDIDATE,
        a4_state="ADMITTED_BLOCKED_PENDING_A3_TRUSTED_CONTROL_REPAIR",
        a4_execution_allowed=False,
        a3_promotion_guard="POSTMERGE_TRUSTED_CONTROL_REPAIR_MUST_PASS_BEFORE_A4_EXECUTION",
    )
    # Trusted disposition is not consulted while the repair is still a candidate.
    b["trusted"] = {}
    assert mod.validate_documents(**b) == []


def test_candidate_lifecycle_rejects_unblocked_a4(mod):
    b = _bundle(mod)
    b["enforcement"]["postmerge_trusted_control_repair"]["state"] = CANDIDATE
    errors = mod.validate_documents(**b)
    assert "A4 execution must remain blocked until trusted-control repair completes" in errors
    assert "A3 trusted-control repair must remain active while A4 is blocked" in errors
    assert "A3 promotion guard drift" in errors


@pytest.mark.parametrize("state,present", [("SOMETHING_SECRET", True), (None, False)])
def test_unsupported_lifecycle_state_is_not_echoed(mod, state, present):
    b = _bundle(mod)
    if state is None:
        b["enforcement"]["postmerge_trusted_control_repair"].pop("state")
    else:
        b["enforcement"]["postmerge_trusted_control_repair"]["state"] = state
    errors = mod.validate_documents(**b)
    expected = "unsupported A3 repair lifecycle state (state_present=" + str(present) + ")"
    assert expected in errors
    assert not any("SOMETHING_SECRET" in e for e in errors)


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
    ("enforcement", ("schema",), "x", "A3 schema drift"),
    ("enforcement", ("mode",), "x", "A3 mode drift"),
    ("enforcement", ("authority_transfer",), True, "A3 authority transfer must remain false"),
    ("enforcement", ("engineering_credit_delta",), 1, "A3 engineering credit delta must remain zero"),
    ("current", ("canonical", "adoption_a3_postmerge_trusted_control"), "x", "A3 repair receipt pointer drift"),
    ("current", ("adoption", "completed_waves"), [], "A3 missing from completed waves"),
    ("current", ("adoption", "authority_transfer"), _DEL, "CURRENT adoption authority transfer weakened"),
    ("current", ("adoption", "a3_control_repair_state"), "x", "A3 control-repair completion drift"),
    ("current", ("adoption", "a4_state"), "x", "A4 active projection state drift"),
    ("repair", ("reason",), "x", "A3 repair reason drift"),
    ("repair", ("control_repair_policy", "merge_only_after_trusted_fpc_success"), False, "A3 repair policy weakened: merge_only_after_trusted_fpc_success"),
    ("repair", ("invariants", "formal_credit_delta"), 1, "A3 repair formal credit drift"),
    ("repair", ("intended_postmerge_state", "a4_state"), "x", "A4 intended postmerge state drift"),
    ("enforcement", ("postmerge_trusted_control_repair", "receipt"), "x", "A3 enforcement/repair receipt binding drift"),
    ("enforcement", ("postmerge_trusted_control_repair", "disposition_receipt"), "x", "A3 enforcement trusted disposition binding drift"),
    ("enforcement", ("postmerge_trusted_control_repair", "trusted_fpc", "head_sha"), "x", "A3 enforcement trusted FPC head drift"),
    ("enforcement", ("postmerge_trusted_control_repair", "trusted_fpc", "artifact_id"), 0, "A3 enforcement trusted FPC artifact ID drift"),
    ("trusted", ("evidence", "fpc_proof_run"), 0, "A3 trusted FPC proof run drift"),
    ("trusted", ("next_wave",), "x", "A3 trusted next-wave drift"),
    ("trusted", ("invariants", "external_repository_mutation"), True, "A3 trusted disposition external mutation drift"),
    ("enforcement", ("mutation_policy", "domain_authority_replacement"), True, "A3 mutation guard weakened: domain_authority_replacement"),
    ("enforcement", ("legacy_validators", 1, "path"), "x.py", "legacy validator path drift: LM11_QPS_WAVE_FEDERATION"),
    ("enforcement", ("legacy_validators", 2, "immutable_in_mc_a3"), False, "legacy validator immutability guard missing: GM_I_C_REGISTRATION"),
    ("a1", ("mode",), "x", "A1 is no longer read-only census"),
    ("a2", ("projection_policy", "historical_receipts_rewritten"), True, "A2 historical rewrite guard drift"),
    ("a2", ("a1_candidate_coverage", "parity"), False, "A2 parity flag drift"),
    ("a2", ("a1_candidate_coverage", "projected_consumer_ids"), ["C1"], "A2 admitted/projected consumer parity drift"),
    ("a1", ("mc_a2_candidates",), ["C1"], "A1 candidate/A2 admitted consumer parity drift"),
    ("official", ("mission_control_operating_model", "mission_telemetry"), "x", "Official Register telemetry bridge drift"),
    ("a2", ("projections", 0, "projection_id"), "P-X", "A2 projection ID set/order drift"),
    ("a2", ("projections", 2, "current_telemetry", "authority_transfer"), True, "LM-11 projection authority transfer drift"),
    ("official", ("variants", 0, "first_red"), "x", "GM-I-C source first-red drift"),
    ("enforcement", ("semantic_cross_checks", "GM-I-C", "relation"), "SAME", "GM-I-C semantic relation drift"),
    ("official", ("local_missions", 0, "state"), "x", "LM-10 source state drift"),
    ("a2", ("projections", 1, "preserved_assertions"), ["AS1"], "LM-10 preserved assertion missing: AS2"),
    ("official", ("local_missions", 1, "first_red"), "x", "LM-11 source first-red drift"),
    ("enforcement", ("semantic_cross_checks", "LM-11", "zero_step_application_failure"), True, "LM-11 zero-step/application-failure guard drift"),
]


@pytest.mark.parametrize("doc,path,value,message", MUTATIONS, ids=[m[3] for m in MUTATIONS])
def test_single_drift_is_reported(mod, doc, path, value, message):
    b = _bundle(mod)
    _set(b[doc], path, value)
    assert message in mod.validate_documents(**b)


def test_projected_telemetry_must_equal_canonical_row(mod):
    b = _bundle(mod)
    _proj(b, "LM-11")["current_telemetry"]["status"]["execution"] = "DONE"
    errors = mod.validate_documents(**b)
    assert "A2 projected telemetry drift for LM-11" in errors
    assert "LM-11 status projection drift" in errors


def test_missing_mission_in_telemetry_and_projection(mod):
    b = _bundle(mod)
    b["status"]["missions"] = b["status"]["missions"][:2]
    b["a2"]["projections"] = b["a2"]["projections"][:2]
    errors = mod.validate_documents(**b)
    assert "canonical telemetry missing LM-11" in errors
    assert "A2 projection missing LM-11" in errors
    assert "A2 projected mission set/order drift" in errors
    assert not any(e.startswith("A2 projected telemetry drift") for e in errors)
    assert "LM-11 zero-step evidence drift" in errors


def test_gm_i_c_cardinality_and_token_collapse(mod):
    b = _bundle(mod)
    _proj(b, "GM-I-C")["current_telemetry"]["todo"]["items"] = []
    errors = mod.validate_documents(**b)
    assert "GM-I-C normalized TODO cardinality drift" in errors
    assert "GM-I-C normalized TODO predicate drift" not in errors

    b = _bundle(mod)
    # Collapsing the normalised predicate into the source first-red token is rejected.
    b["enforcement"]["semantic_cross_checks"]["GM-I-C"]["normalized_v2_todo_predicate"] = "FR_GM"
    _proj(b, "GM-I-C")["current_telemetry"]["todo"]["items"][0]["predicate"] = "FR_GM"
    b["status"]["missions"][0]["todo"]["items"][0]["predicate"] = "FR_GM"
    assert mod.validate_documents(**b) == [
        "GM-I-C source first-red was collapsed into normalized TODO identifier"
    ]


def test_legacy_validator_count_and_set_drift(mod):
    b = _bundle(mod)
    b["enforcement"]["legacy_validators"].pop()
    errors = mod.validate_documents(**b)
    assert "legacy validator count drift" in errors
    assert "legacy validator required ID set drift" in errors
    assert "legacy validator mission drift: GM_I_C_REGISTRATION" in errors


# ---------------------------------------------------------------- source bindings


def test_projection_source_bindings_match(mod, git):
    errors, bound = mod.validate_projection_source_bindings(_bundle(mod)["a2"])
    assert errors == []
    assert [r["path"] for r in bound] == ["src/gm.json", "src/lm10.json", "src/lm10b.json", "src/lm11.json"]
    assert bound[0] == {
        "kind": "A2_PROJECTION_SOURCE_BINDING",
        "projection_id": "P-GM",
        "path": "src/gm.json",
        "expected": "blob:src/gm.json",
        "actual": "blob:src/gm.json",
    }


def test_projection_source_binding_failures(mod, monkeypatch):
    monkeypatch.setattr(mod.subprocess, "check_output", GitStub({"src/lm11.json": "drifted"}))
    a2 = _bundle(mod)["a2"]
    a2["projections"][0]["source_bindings"] = []
    a2["projections"][1]["source_bindings"][0]["blob"] = ""
    errors, bound = mod.validate_projection_source_bindings(a2)
    assert errors == [
        "A2 projection has no source bindings: P-GM",
        "A2 projection source binding incomplete: P-LM10",
        "A2 projection source blob drift: P-LM11: src/lm11.json",
    ]
    assert [(r["path"], r["actual"]) for r in bound] == [("src/lm10b.json", "blob:src/lm10b.json"), ("src/lm11.json", "drifted")]


def test_git_bindings_all_match(mod, git):
    b = _bundle(mod)
    errors, bound = mod.validate_git_bindings(b["enforcement"], b["a2"])
    assert errors == []
    # 4 basis + 3 legacy + 1 source control + 4 projection bindings
    assert len(bound) == 12
    assert all(r["expected"] == r["actual"] for r in bound)


def test_git_bindings_detect_every_drift_kind(mod, monkeypatch):
    legacy_paths = [p for _, p in mod.REQUIRED_LEGACY_VALIDATORS.values()]
    monkeypatch.setattr(
        mod.subprocess,
        "check_output",
        GitStub({"x/a2.json": "d1", legacy_paths[0]: "d2", "x/control.py": "d3", "src/gm.json": "d4"}),
    )
    b = _bundle(mod)
    b["enforcement"]["legacy_validators"][2]["immutable_in_mc_a3"] = False
    errors, _ = mod.validate_git_bindings(b["enforcement"], b["a2"])
    assert errors == [
        "blob drift: x/a2.json",
        "legacy validator blob drift: " + legacy_paths[0],
        "legacy validator immutability guard missing: " + legacy_paths[2],
        "source-control blob drift: x/control.py",
        "A2 projection source blob drift: P-GM: src/gm.json",
    ]


def test_git_bindings_incomplete_and_identity_drift(mod, git):
    b = _bundle(mod)
    rows = b["enforcement"]["legacy_validators"]
    rows.pop()  # GM_I_C_REGISTRATION missing
    rows[1]["mission_id"] = "LM-99"
    errors, bound = mod.validate_git_bindings(b["enforcement"], b["a2"])
    assert errors == [
        "legacy validator binding set incomplete",
        "legacy validator identity drift: LM11_QPS_WAVE_FEDERATION",
    ]
    hashed = [c[0][2] for c in git.calls]
    assert rows[0]["path"] in hashed
    assert rows[1]["path"] not in hashed


# ---------------------------------------------------------------- self_test


def test_self_test_passes_on_valid_bundle(mod, git):
    b = _bundle(mod)
    snapshot = copy.deepcopy(b)
    mod.self_test(b)
    assert b == snapshot


def test_self_test_fails_when_validator_is_blind(mod, git, monkeypatch):
    monkeypatch.setattr(mod, "validate_documents", lambda *a, **k: [])
    with pytest.raises(AssertionError):
        mod.self_test(_bundle(mod))


# ---------------------------------------------------------------- main


def _write_bundle(mod, monkeypatch, tmp_path, b):
    names = {
        "ENFORCEMENT": "enforcement",
        "A1": "a1",
        "A2": "a2",
        "STATUS": "status",
        "CURRENT": "current",
        "POSTMERGE_REPAIR": "repair",
        "TRUSTED_DISPOSITION": "trusted",
    }
    for const, key in names.items():
        p = tmp_path / (key + ".json")
        p.write_text(json.dumps(b[key]), encoding="utf-8")
        monkeypatch.setattr(mod, const, p)
    off = tmp_path / "official.yaml"
    off.write_text(yaml.safe_dump(b["official"]), encoding="utf-8")
    monkeypatch.setattr(mod, "OFFICIAL", off)


def test_main_pass_with_self_test_and_receipt(mod, git, monkeypatch, tmp_path, capsys):
    _write_bundle(mod, monkeypatch, tmp_path, _bundle(mod))
    out = tmp_path / "receipt.json"
    monkeypatch.setenv("MC_SOURCE_SHA", "abc123")
    monkeypatch.setenv("GITHUB_SHA", "ignored")
    monkeypatch.setattr(sys, "argv", ["validate", "--self-test", "--emit-receipt", str(out)])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 0
    printed = json.loads(capsys.readouterr().out)
    written = json.loads(out.read_text(encoding="utf-8"))
    assert printed == written
    assert written["result"] == "PASS"
    assert written["source_sha"] == "abc123"
    assert set(written["checks"].values()) == {"PASS"}
    assert written["binding_count"] == 12 == len(written["bindings"])
    assert written["projected_missions"] == ["GM-I-C", "LM-10", "LM-11"]


def test_main_fail_flags_matching_checks(mod, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(mod.subprocess, "check_output", GitStub({"x/a1.json": "drift"}))
    b = _bundle(mod)
    b["official"]["mission_control_operating_model"]["rule"] = "V2_REPLACES_SOURCE_AUTHORITY"
    b["a2"]["authority_transfer"] = True
    _write_bundle(mod, monkeypatch, tmp_path, b)
    monkeypatch.delenv("MC_SOURCE_SHA", raising=False)
    monkeypatch.setenv("GITHUB_SHA", "gh-sha")
    monkeypatch.setattr(sys, "argv", ["validate"])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 1
    r = json.loads(capsys.readouterr().out)
    assert r["result"] == "FAIL"
    assert r["source_sha"] == "gh-sha"
    assert r["checks"]["official_register_bridge"] == "FAIL"
    assert r["checks"]["source_bindings"] == "FAIL"
    assert r["checks"]["no_authority_transfer"] == "FAIL"
    assert r["checks"]["lm10_projection"] == "PASS"
    assert r["checks"]["gm_i_c_token_separation"] == "PASS"
    assert not (tmp_path / "receipt.json").exists()


def test_main_without_sha_env_reports_none(mod, git, monkeypatch, tmp_path, capsys):
    b = _bundle(mod)
    _proj(b, "LM-10")["current_telemetry"]["lifecycle"]["state"] = "ACTIVE"
    _write_bundle(mod, monkeypatch, tmp_path, b)
    monkeypatch.delenv("MC_SOURCE_SHA", raising=False)
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    monkeypatch.setattr(sys, "argv", ["validate"])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 1
    r = json.loads(capsys.readouterr().out)
    assert r["source_sha"] is None
    assert r["checks"]["lm10_projection"] == "FAIL"
    assert r["checks"]["projection_parity"] == "FAIL"


def test_loaders_read_utf8(mod, tmp_path):
    j = tmp_path / "d.json"
    j.write_text(json.dumps({"a": "é"}), encoding="utf-8")
    y = tmp_path / "d.yaml"
    y.write_text("a: é\nb: [1, 2]\n", encoding="utf-8")
    assert mod.load_json(j) == {"a": "é"}
    assert mod.load_yaml(y) == {"a": "é", "b": [1, 2]}


def test_committed_documents_validate_offline(mod):
    bundle = {
        "enforcement": mod.load_json(mod.ENFORCEMENT),
        "a1": mod.load_json(mod.A1),
        "a2": mod.load_json(mod.A2),
        "status": mod.load_json(mod.STATUS),
        "official": mod.load_yaml(mod.OFFICIAL),
        "current": mod.load_json(mod.CURRENT),
        "repair": mod.load_json(mod.POSTMERGE_REPAIR),
        "trusted": mod.load_json(mod.TRUSTED_DISPOSITION),
    }
    assert mod.validate_documents(**bundle) == []
