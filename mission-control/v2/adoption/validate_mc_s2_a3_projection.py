#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
V2 = ROOT / "mission-control" / "v2"
ADOPTION = V2 / "adoption"

ENFORCEMENT = ADOPTION / "MC_S2_A3_VALIDATOR_ENFORCEMENT_20260927_v1.json"
A1 = ADOPTION / "MC_S2_A1_READ_ONLY_CONSUMER_CROSSWALK_20260927_v1.json"
A2 = ADOPTION / "MC_S2_A2_CURRENT_MISSION_PROJECTION_20260927_v1.json"
STATUS = V2 / "MC_MISSION_STATUS_CURRENT_v1.json"
OFFICIAL = ROOT / "mission-control" / "OFFICIAL_MISSION_REGISTER_v1.yaml"
CURRENT = V2 / "MISSION_CONTROL_CURRENT_v2.json"
POSTMERGE_REPAIR = ADOPTION / "MC_S2_A3_POSTMERGE_TRUSTED_CONTROL_20260927_v1.json"
POSTMERGE_REPAIR_REL = "mission-control/v2/adoption/MC_S2_A3_POSTMERGE_TRUSTED_CONTROL_20260927_v1.json"

REQUIRED_LEGACY_VALIDATORS = {
    "LM10_FLEET_OPEN_ISSUE_CONVERGENCE": (
        "LM-10",
        "mission-control/historian/validate_fleet_open_issue_convergence.py",
    ),
    "LM11_QPS_WAVE_FEDERATION": (
        "LM-11",
        "scripts/validate_lm11_qps_wave_federation.py",
    ),
    "GM_I_C_REGISTRATION": (
        "GM-I-C",
        "mission-control/grand-missions/validate_gm_i_c_registration.py",
    ),
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def git_blob(path: str) -> str:
    return subprocess.check_output(
        ["git", "hash-object", path],
        cwd=ROOT,
        text=True,
    ).strip()


def validate_documents(enforcement, a1, a2, status, official, current, repair):
    errors = []

    def req(ok, message):
        if not ok:
            errors.append(message)

    req(enforcement.get("schema") == "missioncontrol.v2.adoption.validator_enforcement.v1", "A3 schema drift")
    req(enforcement.get("mode") == "ADDITIVE_FAIL_CLOSED_CROSS_CHECK", "A3 mode drift")
    req(enforcement.get("authority_transfer") is False, "A3 authority transfer must remain false")
    req(enforcement.get("formal_credit_delta") == 0, "A3 formal credit delta must remain zero")
    req(enforcement.get("engineering_credit_delta") == 0, "A3 engineering credit delta must remain zero")


    # Post-merge trusted-control repair must be executable, not documentary.
    canonical = current.get("canonical", {})
    adoption = current.get("adoption", {})
    req(canonical.get("adoption_a3_postmerge_trusted_control") == POSTMERGE_REPAIR_REL, "A3 repair receipt pointer drift")
    req("MC-A3_VALIDATOR_ENFORCEMENT" in adoption.get("completed_waves", []), "A3 missing from completed waves during control repair")
    req(adoption.get("active_wave") == "MC-A3_POSTMERGE_TRUSTED_CONTROL_REPAIR", "A3 trusted-control repair must remain active while A4 is blocked")
    req(adoption.get("next_wave") == "MC-A4_DASHBOARD_AND_TODO_SURFACES", "A4 next-wave identity drift")
    req(adoption.get("a3_state") == "CONTROLLED_COMPLETE_PENDING_TRUSTED_CONTROL_REPAIR", "A3 pending trusted-control state drift")
    req(adoption.get("a3_control_repair_state") == "CANDIDATE_DRAFT_WAIT_EXACT_HEAD_PROOF", "A3 control-repair candidate state drift")
    req(adoption.get("a4_state") == "ADMITTED_BLOCKED_PENDING_A3_TRUSTED_CONTROL_REPAIR", "A4 blocked admission state drift")
    req(adoption.get("a4_execution_allowed") is False, "A4 execution must remain blocked until trusted-control repair merges")
    req(adoption.get("a3_promotion_guard") == "POSTMERGE_TRUSTED_CONTROL_REPAIR_MUST_PASS_BEFORE_A4_EXECUTION", "A3 promotion guard drift")
    req(adoption.get("authority_transfer") is False, "CURRENT adoption authority transfer weakened")
    req(adoption.get("formal_credit_delta") == 0, "CURRENT adoption formal credit drift")
    req(adoption.get("engineering_credit_delta") == 0, "CURRENT adoption engineering credit drift")

    req(repair.get("schema") == "missioncontrol.v2.adoption.a3_postmerge_trusted_control_repair.v1", "A3 repair receipt schema drift")
    req(repair.get("wave_id") == "MC-A3_VALIDATOR_ENFORCEMENT", "A3 repair receipt wave drift")
    req(repair.get("reason") == "PR457_MERGED_BEFORE_TRUSTED_FPC_COMPLETED", "A3 repair reason drift")
    policy = repair.get("control_repair_policy", {})
    for key in (
        "this_pr_is_draft_until_exact_head_candidate_proofs_complete",
        "this_pr_must_run_a3_enforcement",
        "this_pr_must_run_mc_v2_contract",
        "this_pr_must_run_first_pass_closure_proof",
        "this_pr_must_have_clean_exact_head_codex_review",
        "mark_ready_only_after_candidate_proofs_and_review",
        "trusted_fpc_success_required_after_ready",
        "merge_only_after_trusted_fpc_success",
        "a4_execution_forbidden_until_merge",
    ):
        req(policy.get(key) is True, f"A3 repair policy weakened: {key}")
    repair_inv = repair.get("invariants", {})
    req(repair_inv.get("authority_transfer") is False, "A3 repair authority transfer weakened")
    req(repair_inv.get("formal_credit_delta") == 0, "A3 repair formal credit drift")
    req(repair_inv.get("engineering_credit_delta") == 0, "A3 repair engineering credit drift")
    intended = repair.get("intended_postmerge_state", {})
    req(intended.get("a3_state") == "CONTROLLED_COMPLETE_TRUSTED_CONTROL_REPAIRED", "A3 intended postmerge state drift")
    req(intended.get("a4_state") == "ADMITTED_PENDING_IMPLEMENTATION", "A4 intended postmerge state drift")
    req(intended.get("next_wave") == "MC-A4_DASHBOARD_AND_TODO_SURFACES", "A4 intended next wave drift")

    repair_binding = enforcement.get("postmerge_trusted_control_repair", {})
    req(repair_binding.get("receipt") == POSTMERGE_REPAIR_REL, "A3 enforcement/repair receipt binding drift")
    req(repair_binding.get("state") == "CANDIDATE_DRAFT_WAIT_EXACT_HEAD_PROOF", "A3 enforcement repair-state drift")
    req(repair_binding.get("authority_transfer") is False, "A3 enforcement repair authority transfer weakened")
    req(repair_binding.get("formal_credit_delta") == 0, "A3 enforcement repair formal credit drift")
    req(repair_binding.get("engineering_credit_delta") == 0, "A3 enforcement repair engineering credit drift")

    mp = enforcement.get("mutation_policy", {})
    for key in (
        "legacy_validator_edit",
        "legacy_source_edit",
        "historical_receipt_rewrite",
        "domain_authority_replacement",
        "external_repository_mutation",
    ):
        req(mp.get(key) is False, f"A3 mutation guard weakened: {key}")

    legacy_rows = enforcement.get("legacy_validators", [])
    legacy_by_id = {row.get("id"): row for row in legacy_rows}
    req(len(legacy_rows) == len(REQUIRED_LEGACY_VALIDATORS), "legacy validator count drift")
    req(set(legacy_by_id) == set(REQUIRED_LEGACY_VALIDATORS), "legacy validator required ID set drift")
    for validator_id, (mission_id, path) in REQUIRED_LEGACY_VALIDATORS.items():
        row = legacy_by_id.get(validator_id, {})
        req(row.get("mission_id") == mission_id, f"legacy validator mission drift: {validator_id}")
        req(row.get("path") == path, f"legacy validator path drift: {validator_id}")
        req(row.get("immutable_in_mc_a3") is True, f"legacy validator immutability guard missing: {validator_id}")

    req(a1.get("mode") == "READ_ONLY_CENSUS", "A1 is no longer read-only census")
    req(a1.get("authority_transfer") is False, "A1 authority transfer drift")
    req(a2.get("projection_policy", {}).get("mode") == "READ_ONLY_ADDITIVE", "A2 projection mode drift")
    req(a2.get("projection_policy", {}).get("legacy_identity_assertions_remain_authoritative") is True, "A2 legacy authority guard drift")
    req(a2.get("projection_policy", {}).get("historical_receipts_rewritten") is False, "A2 historical rewrite guard drift")
    req(a2.get("authority_transfer") is False, "A2 authority transfer drift")

    bridge = official.get("mission_control_operating_model", {})
    req(bridge.get("current") == "mission-control/v2/MISSION_CONTROL_CURRENT_v2.json", "Official Register v2 current bridge drift")
    req(bridge.get("mission_telemetry") == "mission-control/v2/MC_MISSION_STATUS_CURRENT_v1.json", "Official Register telemetry bridge drift")
    req(bridge.get("rule") == "V2_GOVERNS_NEW_ORCHESTRATION_SEMANTICS_WITHOUT_REWRITING_HISTORICAL_MISSION_AUTHORITY", "Official Register authority bridge rule drift")

    expected_projection_ids = enforcement["projection_contract"]["required_projection_ids"]
    projections = a2.get("projections", [])
    req([p.get("projection_id") for p in projections] == expected_projection_ids, "A2 projection ID set/order drift")

    expected_missions = enforcement["projection_contract"]["required_mission_ids"]
    req([p.get("mission_id") for p in projections] == expected_missions, "A2 projected mission set/order drift")

    a1_candidates = set(a1.get("mc_a2_candidates", []))
    admitted = set(a2.get("a1_candidate_coverage", {}).get("admitted_consumer_ids", []))
    projected = set(a2.get("a1_candidate_coverage", {}).get("projected_consumer_ids", []))
    req(a1_candidates == admitted, "A1 candidate/A2 admitted consumer parity drift")
    req(admitted == projected, "A2 admitted/projected consumer parity drift")
    req(a2.get("a1_candidate_coverage", {}).get("parity") is True, "A2 parity flag drift")

    status_rows = {row["mission_id"]: row for row in status.get("missions", [])}
    proj_by_mission = {row["mission_id"]: row for row in projections}
    for mission_id in expected_missions:
        req(mission_id in status_rows, f"canonical telemetry missing {mission_id}")
        req(mission_id in proj_by_mission, f"A2 projection missing {mission_id}")
        if mission_id in status_rows and mission_id in proj_by_mission:
            req(
                proj_by_mission[mission_id].get("current_telemetry") == status_rows[mission_id],
                f"A2 projected telemetry drift for {mission_id}",
            )
            req(proj_by_mission[mission_id].get("current_telemetry", {}).get("authority_transfer") is False, f"{mission_id} projection authority transfer drift")

    variants = {row["id"]: row for row in official.get("variants", [])}
    gm = enforcement["semantic_cross_checks"]["GM-I-C"]
    gm_source = variants.get("GM-I-C", {})
    gm_proj = proj_by_mission.get("GM-I-C", {}).get("current_telemetry", {})
    gm_todos = gm_proj.get("todo", {}).get("items", [])
    req(gm_source.get("first_red") == gm["source_first_red"], "GM-I-C source first-red drift")
    req(len(gm_todos) == 1, "GM-I-C normalized TODO cardinality drift")
    if len(gm_todos) == 1:
        normalized = gm_todos[0].get("predicate")
        req(normalized == gm["normalized_v2_todo_predicate"], "GM-I-C normalized TODO predicate drift")
        req(normalized != gm_source.get("first_red"), "GM-I-C source first-red was collapsed into normalized TODO identifier")
    req(gm.get("relation") == "RELATED_NOT_IDENTICAL", "GM-I-C semantic relation drift")

    lm10 = enforcement["semantic_cross_checks"]["LM-10"]
    lm10_proj = proj_by_mission.get("LM-10", {}).get("current_telemetry", {})
    lm10_register = next((row for row in official.get("local_missions", []) if row.get("id") == "LM-10"), {})
    req(lm10_register.get("state") == lm10["source_state"], "LM-10 source state drift")
    req(lm10_proj.get("lifecycle", {}).get("state") == lm10["normalized_lifecycle"], "LM-10 lifecycle projection drift")
    req(lm10_proj.get("status", {}).get("execution") == lm10["normalized_status"], "LM-10 status projection drift")
    lm10_assertions = set(proj_by_mission.get("LM-10", {}).get("preserved_assertions", []))
    for assertion in lm10.get("required_legacy_assertions", []):
        req(assertion in lm10_assertions, f"LM-10 preserved assertion missing: {assertion}")

    lm11 = enforcement["semantic_cross_checks"]["LM-11"]
    lm11_proj = proj_by_mission.get("LM-11", {}).get("current_telemetry", {})
    lm11_register = next((row for row in official.get("local_missions", []) if row.get("id") == "LM-11"), {})
    req(lm11_register.get("state") == lm11["source_state"], "LM-11 source state drift")
    req(lm11_register.get("first_red") == lm11["source_first_red"], "LM-11 source first-red drift")
    req(lm11_proj.get("lifecycle", {}).get("state") == lm11["normalized_lifecycle"], "LM-11 lifecycle projection drift")
    req(lm11_proj.get("status", {}).get("execution") == lm11["normalized_status"], "LM-11 status projection drift")
    req(lm11_proj.get("metrics", {}).get("custom", {}).get("zero_step_reproduced") is True, "LM-11 zero-step evidence drift")
    req(lm11.get("zero_step_application_failure") is False, "LM-11 zero-step/application-failure guard drift")

    return errors


def validate_projection_source_bindings(a2):
    errors = []
    bound = []
    for projection in a2.get("projections", []):
        projection_id = projection.get("projection_id")
        rows = projection.get("source_bindings", [])
        if not rows:
            errors.append(f"A2 projection has no source bindings: {projection_id}")
            continue
        for row in rows:
            path = row.get("path")
            expected = row.get("blob")
            if not path or not expected:
                errors.append(f"A2 projection source binding incomplete: {projection_id}")
                continue
            actual = git_blob(path)
            bound.append({
                "kind": "A2_PROJECTION_SOURCE_BINDING",
                "projection_id": projection_id,
                "path": path,
                "expected": expected,
                "actual": actual,
            })
            if actual != expected:
                errors.append(f"A2 projection source blob drift: {projection_id}: {path}")
    return errors, bound


def validate_git_bindings(enforcement, a2):
    errors = []
    bound = []
    for group in ("basis",):
        for key in ("a1", "a2", "telemetry", "official_register"):
            row = enforcement[group][key]
            actual = git_blob(row["path"])
            bound.append({"path": row["path"], "expected": row["blob"], "actual": actual})
            if actual != row["blob"]:
                errors.append(f"blob drift: {row['path']}")
    legacy_rows = enforcement.get("legacy_validators", [])
    legacy_by_id = {row.get("id"): row for row in legacy_rows}
    if len(legacy_rows) != len(REQUIRED_LEGACY_VALIDATORS) or set(legacy_by_id) != set(REQUIRED_LEGACY_VALIDATORS):
        errors.append("legacy validator binding set incomplete")
    for validator_id, (mission_id, path) in REQUIRED_LEGACY_VALIDATORS.items():
        row = legacy_by_id.get(validator_id)
        if row is None:
            continue
        if row.get("mission_id") != mission_id or row.get("path") != path:
            errors.append(f"legacy validator identity drift: {validator_id}")
            continue
        actual = git_blob(row["path"])
        bound.append({"path": row["path"], "expected": row["blob"], "actual": actual})
        if actual != row["blob"]:
            errors.append(f"legacy validator blob drift: {row['path']}")
        if row.get("immutable_in_mc_a3") is not True:
            errors.append(f"legacy validator immutability guard missing: {row['path']}")
    for row in enforcement.get("source_controls", []):
        actual = git_blob(row["path"])
        bound.append({"path": row["path"], "expected": row["blob"], "actual": actual})
        if actual != row["blob"]:
            errors.append(f"source-control blob drift: {row['path']}")

    projection_errors, projection_bound = validate_projection_source_bindings(a2)
    errors.extend(projection_errors)
    bound.extend(projection_bound)
    return errors, bound


def self_test(bundle):
    base = bundle

    bad = copy.deepcopy(base)
    bad["enforcement"]["authority_transfer"] = True
    assert validate_documents(bad["enforcement"], bad["a1"], bad["a2"], bad["status"], bad["official"], bad["current"], bad["repair"])

    bad = copy.deepcopy(base)
    gm = next(p for p in bad["a2"]["projections"] if p["mission_id"] == "GM-I-C")
    gm["current_telemetry"]["todo"]["items"][0]["predicate"] = "IC3_AUTH_REAL_HOSTED_GT0_STEP_DRIVE_INGRESS_PASS"
    assert validate_documents(bad["enforcement"], bad["a1"], bad["a2"], bad["status"], bad["official"], bad["current"], bad["repair"])

    bad = copy.deepcopy(base)
    lm10 = next(p for p in bad["a2"]["projections"] if p["mission_id"] == "LM-10")
    lm10["current_telemetry"]["lifecycle"]["state"] = "ACTIVE"
    assert validate_documents(bad["enforcement"], bad["a1"], bad["a2"], bad["status"], bad["official"], bad["current"], bad["repair"])

    bad = copy.deepcopy(base)
    bad["a2"]["a1_candidate_coverage"]["projected_consumer_ids"] = []
    assert validate_documents(bad["enforcement"], bad["a1"], bad["a2"], bad["status"], bad["official"], bad["current"], bad["repair"])

    bad = copy.deepcopy(base)
    bad["a1"]["mc_a2_candidates"].append("MC-A1-C99")
    assert validate_documents(bad["enforcement"], bad["a1"], bad["a2"], bad["status"], bad["official"], bad["current"], bad["repair"])

    bad = copy.deepcopy(base)
    bad["enforcement"]["legacy_validators"] = bad["enforcement"]["legacy_validators"][:-1]
    assert validate_documents(bad["enforcement"], bad["a1"], bad["a2"], bad["status"], bad["official"], bad["current"], bad["repair"])

    bad = copy.deepcopy(base)
    bad["a2"]["projections"][0]["source_bindings"][0]["blob"] = "0" * 40
    projection_errors, _ = validate_projection_source_bindings(bad["a2"])
    assert projection_errors, "self-test failed to detect A2 embedded source-binding drift"

    bad = copy.deepcopy(base)
    bad["current"]["adoption"]["a4_execution_allowed"] = True
    assert validate_documents(bad["enforcement"], bad["a1"], bad["a2"], bad["status"], bad["official"], bad["current"], bad["repair"])

    bad = copy.deepcopy(base)
    bad["current"]["canonical"]["adoption_a3_postmerge_trusted_control"] = "mission-control/v2/adoption/WRONG.json"
    assert validate_documents(bad["enforcement"], bad["a1"], bad["a2"], bad["status"], bad["official"], bad["current"], bad["repair"])

    bad = copy.deepcopy(base)
    bad["repair"]["control_repair_policy"]["a4_execution_forbidden_until_merge"] = False
    assert validate_documents(bad["enforcement"], bad["a1"], bad["a2"], bad["status"], bad["official"], bad["current"], bad["repair"])

    bad = copy.deepcopy(base)
    bad["official"]["mission_control_operating_model"]["rule"] = "V2_REPLACES_SOURCE_AUTHORITY"
    assert validate_documents(bad["enforcement"], bad["a1"], bad["a2"], bad["status"], bad["official"], bad["current"], bad["repair"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--emit-receipt")
    args = ap.parse_args()

    bundle = {
        "enforcement": load_json(ENFORCEMENT),
        "a1": load_json(A1),
        "a2": load_json(A2),
        "status": load_json(STATUS),
        "official": load_yaml(OFFICIAL),
        "current": load_json(CURRENT),
        "repair": load_json(POSTMERGE_REPAIR),
    }

    errors = validate_documents(**bundle)
    blob_errors, bindings = validate_git_bindings(bundle["enforcement"], bundle["a2"])
    errors.extend(blob_errors)

    if args.self_test:
        self_test(bundle)

    receipt = {
        "schema": "missioncontrol.v2.adoption.validator_enforcement_receipt.v1",
        "source_sha": os.environ.get("MC_SOURCE_SHA") or os.environ.get("GITHUB_SHA"),
        "result": "PASS" if not errors else "FAIL",
        "checks": {
            "projection_parity": "PASS" if not any("projection" in e.lower() or "parity" in e.lower() for e in errors) else "FAIL",
            "source_bindings": "PASS" if not any("blob drift" in e.lower() for e in errors) else "FAIL",
            "official_register_bridge": "PASS" if not any("official register" in e.lower() for e in errors) else "FAIL",
            "gm_i_c_token_separation": "PASS" if not any("gm-i-c" in e.lower() for e in errors) else "FAIL",
            "lm10_projection": "PASS" if not any("lm-10" in e.lower() for e in errors) else "FAIL",
            "lm11_projection": "PASS" if not any("lm-11" in e.lower() for e in errors) else "FAIL",
            "no_authority_transfer": "PASS" if not any("authority transfer" in e.lower() for e in errors) else "FAIL",
            "a4_fail_closed_repair": "PASS" if not any("a4" in e.lower() or "repair" in e.lower() for e in errors) else "FAIL",
        },
        "projected_missions": ["GM-I-C", "LM-10", "LM-11"],
        "binding_count": len(bindings),
        "bindings": bindings,
        "errors": errors,
        "authority_transfer": False,
        "formal_credit_delta": 0,
        "engineering_credit_delta": 0,
    }

    print(json.dumps(receipt, indent=2, sort_keys=True))
    if args.emit_receipt:
        Path(args.emit_receipt).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    raise SystemExit(0 if not errors else 1)


if __name__ == "__main__":
    main()
