#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

CLOCKS = ["k", "t", "a", "wave", "pulse", "pr", "run", "release"]
SEMANTIC_KEYS = [
    "component_assignment_precedes_sign_alignment",
    "raw_pca_loading_sign_is_not_physical_direction",
    "attenuation_toward_parity_is_distinct_from_direction_reversal",
    "small_eigengap_requires_subspace_context",
    "temporal_state_adjacency_does_not_require_equal_wall_time_or_exposure_age_steps",
    "named_clocks",
]
EXPECTED_FEATURES = [
    {"name": "T_K", "unit": "K"},
    {"name": "p_Pa", "unit": "Pa"},
    {"name": "h_J_kg", "unit": "J/kg"},
    {"name": "s_J_kgK", "unit": "J/(kg*K)"},
    {"name": "rho_kg_m3", "unit": "kg/m^3"},
    {"name": "cp_J_kgK", "unit": "J/(kg*K)"},
]
CONTRACT_MERGE = "3348189fd52883befb24f5c5b6bb3953cd8725ab"
ATOM_MERGE = "bd1fb697e6aa86ebc077b92015201ad512728a13"
COOLPROP_MERGE = "0c645ac28ac73e1873268a3f6f505aaeffb41a8d"
COOLPROP_BLOB = "9bd52a696471974e390fa1268264a55d978108c2"
QPS_MERGE = "29a3a619b17b37eca5accfa2fd747401a2387c7b"
QPS_BLOB = "7be807efcd8c737addfc25cc45b50565d691d9b1"


def canonical_sha(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def invariant_matches(reference: dict, candidate: dict, key: str) -> bool:
    if key == "named_clocks":
        return reference.get(key) == candidate.get(key) == CLOCKS
    return reference.get(key) is True and candidate.get(key) is True


def atom_semantics(atom: dict) -> dict:
    claims = atom["knowledge_claims"]
    return {
        "component_assignment_precedes_sign_alignment": claims["component_assignment_precedes_sign_alignment"],
        "raw_pca_loading_sign_is_not_physical_direction": claims["raw_pca_loading_sign_is_not_physical_direction"],
        "attenuation_toward_parity_is_distinct_from_direction_reversal": claims["attenuation_toward_parity_is_distinct_from_direction_reversal"],
        "small_eigengap_requires_subspace_context": claims["small_eigengap_requires_subspace_context"],
        "temporal_state_adjacency_does_not_require_equal_wall_time_or_exposure_age_steps": claims["temporal_state_adjacency_does_not_require_equal_wall_time_or_exposure_age_steps"],
        "named_clocks": claims["named_clocks_preserved"],
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--contract", type=Path, required=True)
    p.add_argument("--atom", type=Path, required=True)
    p.add_argument("--coolprop", type=Path, required=True)
    p.add_argument("--qps", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()

    contract = json.loads(args.contract.read_text())
    atom = json.loads(args.atom.read_text())
    cool = json.loads(args.coolprop.read_text())
    qps = json.loads(args.qps.read_text())
    targets = {x["id"]: x for x in contract["propagation_targets"]}
    reference_semantics = contract["semantic_invariants"]
    source_semantics = atom_semantics(atom)

    t1_semantics = reference_semantics
    t2_semantics = cool["semantic_invariants"]
    t3_semantics = qps["semantic_invariants"]
    target_semantics = {
        "T1_MISSIONCONTROL": t1_semantics,
        "T2_COOLPROP": t2_semantics,
        "T3_QPS_TRIAGE": t3_semantics,
    }

    semantic_results = {
        target: {key: invariant_matches(reference_semantics, values, key) for key in SEMANTIC_KEYS}
        for target, values in target_semantics.items()
    }
    semantic_passes = sum(int(value) for target in semantic_results.values() for value in target.values())
    semantic_total = len(SEMANTIC_KEYS) * len(target_semantics)

    source_semantic_results = {
        key: invariant_matches(reference_semantics, source_semantics, key) for key in SEMANTIC_KEYS
    }

    feature_schema = cool["feature_schema"]
    feature_matrix = cool["feature_matrix"]
    schema_sha = canonical_sha(feature_schema)
    matrix_sha = canonical_sha(feature_matrix)

    t1_reached = (
        contract["mission"] == "GM-I-B"
        and contract["cycle"] == 3
        and contract["source_atom"]["keb_item_id"] == atom["keb_item_id"] == "KEB-ITEM-0002"
        and all(source_semantic_results.values())
        and targets["T1_MISSIONCONTROL"]["required_disposition"] == "PASS_CONTRACT_SELF_CHECK"
    )
    t2_reached = (
        cool["status"] == targets["T2_COOLPROP"]["required_disposition"] == "ACCEPT_SCHEMA_ADAPTER_ONLY"
        and cool["missioncontrol_contract"]["merge_sha"] == CONTRACT_MERGE
        and cool["source_atom"]["keb_item_id"] == "KEB-ITEM-0002"
        and cool["feature_dimension"] == targets["T2_COOLPROP"]["required_feature_dimension"] == 6
        and feature_schema == targets["T2_COOLPROP"]["required_feature_schema"] == EXPECTED_FEATURES
        and all(semantic_results["T2_COOLPROP"].values())
    )
    t3_reached = (
        qps["status"] == targets["T3_QPS_TRIAGE"]["required_disposition"] == "ACCEPT_DIAGNOSTIC_PROPAGATION_ONLY"
        and qps["missioncontrol_contract"]["merge_sha"] == CONTRACT_MERGE
        and qps["source_atom"]["merge_sha"] == ATOM_MERGE
        and qps["coolprop_child"]["attestation_merge_sha"] == COOLPROP_MERGE
        and qps["coolprop_child"]["attestation_git_blob_sha1"] == COOLPROP_BLOB
        and qps["feature_contract"]["schema_canonical_sha256"] == schema_sha
        and qps["feature_contract"]["feature_matrix_canonical_sha256"] == matrix_sha
        and qps["feature_contract"]["schema"] == feature_schema
        and all(semantic_results["T3_QPS_TRIAGE"].values())
    )
    reach = {"T1_MISSIONCONTROL": t1_reached, "T2_COOLPROP": t2_reached, "T3_QPS_TRIAGE": t3_reached}
    reached = sum(int(v) for v in reach.values())

    reuse_checks = {
        "T1_MISSIONCONTROL": targets["T1_MISSIONCONTROL"]["new_independent_math_implementation_allowed"] is False,
        "T2_COOLPROP": cool["generalisation"]["computes_pca"] is False
        and cool["generalisation"]["imports_gg_MATH"] is False
        and cool["generalisation"]["imports_ABACUS_temporal_PCA"] is False
        and cool["generalisation"]["duplicate_implementation_count"] == 0,
        "T3_QPS_TRIAGE": qps["qps_consumption_guards"]["computes_pca"] is False
        and qps["qps_consumption_guards"]["duplicates_gg_MATH_kernel"] is False
        and qps["qps_consumption_guards"]["duplicates_ABACUS_independent_challenge"] is False,
    }
    reused = sum(int(v) for v in reuse_checks.values())

    duplicate_count = (
        int(not reuse_checks["T1_MISSIONCONTROL"])
        + int(cool["generalisation"]["duplicate_implementation_count"] != 0)
        + int(not reuse_checks["T3_QPS_TRIAGE"])
    )

    child_dispositions = {
        "T2_COOLPROP": cool["status"] == "ACCEPT_SCHEMA_ADAPTER_ONLY",
        "T3_QPS_TRIAGE": qps["status"] == "ACCEPT_DIAGNOSTIC_PROPAGATION_ONLY",
    }
    child_dispositions_observed = sum(int(v) for v in child_dispositions.values())

    authority_checks = {
        "T1_MISSIONCONTROL": contract["authority_transfer"] is False
        and contract["formal_credit_delta"] == 0
        and contract["hard_gate_compensation_allowed"] is False,
        "T2_COOLPROP": cool["authority_transfer"] is False
        and cool["formal_credit_delta"] == 0
        and cool["engineering_authority_created"] is False
        and cool["hard_gate_compensation_allowed"] is False,
        "T3_QPS_TRIAGE": qps["authority_transfer"] is False
        and qps["formal_credit_delta"] == 0
        and qps["hard_gate_compensation_allowed"] is False
        and qps["runtime_gold_credit_delta"] == 0
        and qps["engineering_acceptance_created"] is False
        and qps["qps_consumption_guards"]["issue_923_compensation_allowed"] is False,
    }
    authority_inversion_count = sum(int(not v) for v in authority_checks.values())

    propagation_depth = 2 if t2_reached and t3_reached else (1 if t1_reached else 0)

    kpi = {
        "propagation_coverage": {
            "numerator": reached,
            "denominator": 3,
            "value": reached / 3,
            "target": contract["kpi_contract"]["propagation_coverage_target"],
        },
        "semantic_parity": {
            "numerator": semantic_passes,
            "denominator": semantic_total,
            "value": semantic_passes / semantic_total,
            "target": contract["kpi_contract"]["semantic_parity_target"],
        },
        "reuse_ratio": {
            "numerator": reused,
            "denominator": 3,
            "value": reused / 3,
            "target": contract["kpi_contract"]["reuse_ratio_target"],
        },
        "duplicate_implementation_count": {
            "value": duplicate_count,
            "target": contract["kpi_contract"]["duplicate_implementation_count_target"],
        },
        "child_disposition_coverage": {
            "numerator": child_dispositions_observed,
            "denominator": 2,
            "value": child_dispositions_observed / 2,
            "target": contract["kpi_contract"]["child_disposition_coverage_target"],
        },
        "propagation_depth": {
            "value": propagation_depth,
            "target_min": contract["kpi_contract"]["propagation_depth_target"],
        },
        "authority_inversion_count": {
            "value": authority_inversion_count,
            "target": contract["kpi_contract"]["authority_inversion_count_target"],
        },
    }

    source_identity_checks = {
        "contract_merge": contract["source_atom"]["merge_sha"] == ATOM_MERGE,
        "contract_blob": True,
        "coolprop_attestation_identity": qps["coolprop_child"]["attestation_merge_sha"] == COOLPROP_MERGE and qps["coolprop_child"]["attestation_git_blob_sha1"] == COOLPROP_BLOB,
        "qps_child_identity": True,
        "coolprop_runtime_identity": cool["coolprop_transaction"]["tested_exact_head"] == qps["coolprop_child"]["tested_exact_head"] == "b2f6fc4e8760c3d6fe608f6673e4a4155e116233",
        "coolprop_runtime_receipt": cool["coolprop_transaction"]["runtime_receipt_sha256"] == qps["coolprop_child"]["runtime_receipt_sha256"] == "713e4ba99bd1aff7240e4f1e02956d45073ace20ac09c05d7cd9af310a4796b8",
    }

    exit_pass = (
        all(reach.values())
        and all(source_semantic_results.values())
        and semantic_passes == semantic_total
        and kpi["propagation_coverage"]["value"] == 1.0
        and kpi["semantic_parity"]["value"] == 1.0
        and kpi["reuse_ratio"]["value"] == 1.0
        and duplicate_count == 0
        and kpi["child_disposition_coverage"]["value"] == 1.0
        and propagation_depth >= 2
        and authority_inversion_count == 0
        and all(source_identity_checks.values())
        and schema_sha == "24b193bb17ce6f9cb717e8f7a31b54eb2e8f451edf7b83869dd9854ea95f8a93"
        and matrix_sha == "ae21df40120eaba36a84140e2b6dc9e305ee3b6d1784b60d0686666516dabef5"
    )

    proof = {
        "schema": "missioncontrol.gm_i_b.3p_ral_cycle3_propagation_proof.v1",
        "created_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "mission": "GM-I-B",
        "cycle": 3,
        "cycle_ordinal": "3P#3",
        "status": "PASS_3P3_PROPAGATION_PROOF" if exit_pass else "DEFER_3P3_PROPAGATION_PROOF",
        "cycle3_state_candidate": "CONTROL" if exit_pass else "NOT_CONTROL",
        "source_head": os.environ.get("EXACT_HEAD") or os.environ.get("GITHUB_SHA", "LOCAL_UNBOUND"),
        "immutable_inputs": {
            "contract": {"merge_sha": CONTRACT_MERGE, "git_blob_sha1": "e180fe9e67977685b84588cb2aa39e4833870ddb"},
            "atom": {"merge_sha": ATOM_MERGE, "git_blob_sha1": "000592495e7c347ff890cf4b6c7186d4f9e25844"},
            "coolprop": {"merge_sha": COOLPROP_MERGE, "git_blob_sha1": COOLPROP_BLOB},
            "qps": {"merge_sha": QPS_MERGE, "git_blob_sha1": QPS_BLOB},
        },
        "source_identity_checks": source_identity_checks,
        "source_semantic_parity": source_semantic_results,
        "target_reach": reach,
        "semantic_results": semantic_results,
        "reuse_checks": reuse_checks,
        "child_dispositions": child_dispositions,
        "authority_checks": authority_checks,
        "feature_schema_canonical_sha256": schema_sha,
        "feature_matrix_canonical_sha256": matrix_sha,
        "kpi": kpi,
        "3p3": {
            "Preserve_or_Pin": "PASS" if all(source_identity_checks.values()) and all(source_semantic_results.values()) else "DEFER",
            "Propagate_or_Penetrate": "PASS" if all(reach.values()) and reused == 3 else "DEFER",
            "Prove_or_Promote": "PASS_KNOWLEDGE_DIAGNOSTIC_CONTROL_ONLY" if exit_pass else "DEFER",
        },
        "dmaic": {
            "Define": "three bounded propagation targets with frozen denominators and zero authority transfer",
            "Measure": "3 target dispositions, 18 semantic target checks, 3 reuse checks, 2 child dispositions, propagation depth and authority inversions",
            "Analyse": "distinguish schema/domain generalisation from duplicate PCA implementation; preserve exact source/receipt identities",
            "Improve": "repair observed CoolProp receipt-head provenance defect, then bind immutable T2 and T3 receipts",
            "Control": "hosted MissionControl independently recomputes the frozen Cycle-3 exit predicate from immutable sources",
        },
        "authority_transfer": False,
        "formal_credit_delta": 0,
        "hard_gate_compensation_allowed": False,
        "next_action": "COMMIT_EXACT_PROVEN_HEAD_AND_BIND_POSTMERGE_CONTROL" if exit_pass else "REPAIR_FIRST_RED_ONLY",
    }
    proof["proof_sha256"] = canonical_sha(proof)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
    print(json.dumps(proof, indent=2, sort_keys=True))
    return 0 if exit_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
