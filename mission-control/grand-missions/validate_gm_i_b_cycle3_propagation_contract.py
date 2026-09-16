#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

EXPECTED_ATOM = {
    "keb_item_id": "KEB-ITEM-0002",
    "object_type": "KEB_KNOWLEDGE_ATOM",
    "source_digest": "sha256:876c55c759de33392985f693f1735cdc0d38dda7d7b7a6c80ee80aee33fd8405",
    "authority_cap": "A3_SYNTHETIC_ONLY",
}
EXPECTED_CLOCKS = ["k", "t", "a", "wave", "pulse", "pr", "run", "release"]
EXPECTED_FEATURES = [
    ("T_K", "K"),
    ("p_Pa", "Pa"),
    ("h_J_kg", "J/kg"),
    ("s_J_kgK", "J/(kg*K)"),
    ("rho_kg_m3", "kg/m^3"),
    ("cp_J_kgK", "J/(kg*K)"),
]


def sha256_json(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contract", type=Path, required=True)
    ap.add_argument("--atom", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    contract = json.loads(args.contract.read_text())
    atom = json.loads(args.atom.read_text())
    targets = {x["id"]: x for x in contract["propagation_targets"]}
    semantic = contract["semantic_invariants"]
    rules = contract["generalisation_rules"]
    kpi = contract["kpi_contract"]
    feature_pairs = [(x["name"], x["unit"]) for x in targets["T2_COOLPROP"]["required_feature_schema"]]

    checks = {
        "cycle3_identity": contract.get("mission") == "GM-I-B" and contract.get("cycle") == 3 and contract.get("cycle_ordinal") == "3P#3",
        "atom_identity": atom.get("keb_item_id") == EXPECTED_ATOM["keb_item_id"] and atom.get("object_type") == EXPECTED_ATOM["object_type"],
        "atom_source_digest": atom.get("source_digest") == EXPECTED_ATOM["source_digest"] == contract["source_atom"]["source_digest"],
        "atom_authority_cap": atom.get("authority_cap") == EXPECTED_ATOM["authority_cap"] == contract["source_atom"]["authority_cap"],
        "cycle2_receipt_bound": atom["independent_numeric_reproduction"]["receipt_sha256"] == contract["source_atom"]["cycle2_independent_receipt_sha256"],
        "cycle2_independent_pass": atom["independent_numeric_reproduction"]["result"] == "PASS_INDEPENDENT_C01_C07_7_OF_7",
        "semantic_count": len(semantic) == 6,
        "named_clocks_exact": semantic["named_clocks"] == EXPECTED_CLOCKS,
        "semantic_source_parity": atom["knowledge_claims"]["component_assignment_precedes_sign_alignment"] is True and atom["knowledge_claims"]["raw_pca_loading_sign_is_not_physical_direction"] is True and atom["knowledge_claims"]["attenuation_toward_parity_is_distinct_from_direction_reversal"] is True and atom["knowledge_claims"]["small_eigengap_requires_subspace_context"] is True and atom["knowledge_claims"]["temporal_state_adjacency_does_not_require_equal_wall_time_or_exposure_age_steps"] is True and atom["knowledge_claims"]["named_clocks_preserved"] == EXPECTED_CLOCKS,
        "three_targets_exact": set(targets) == {"T1_MISSIONCONTROL", "T2_COOLPROP", "T3_QPS_TRIAGE"},
        "coolprop_dimension_6": targets["T2_COOLPROP"]["required_feature_dimension"] == 6,
        "coolprop_schema_exact": feature_pairs == EXPECTED_FEATURES,
        "no_duplicate_math": all(x["new_independent_math_implementation_allowed"] is False for x in targets.values()),
        "generalisation_guards": rules["consumer_may_change_mathematical_semantics"] is False and rules["consumer_may_implement_duplicate_pca_kernel"] is False and rules["feature_dimension_is_not_display_dimension"] is True and rules["schema_mapping_alone_is_not_a_pca_result"] is True,
        "kpi_denominators_frozen": kpi["propagation_targets_total"] == 3 and kpi["semantic_invariants_total"] == 6 and kpi["child_targets_total"] == 2,
        "kpi_targets_frozen": kpi["propagation_coverage_target"] == 1.0 and kpi["semantic_parity_target"] == 1.0 and kpi["reuse_ratio_target"] == 1.0 and kpi["duplicate_implementation_count_target"] == 0 and kpi["child_disposition_coverage_target"] == 1.0 and kpi["authority_inversion_count_target"] == 0 and kpi["propagation_depth_target"] == 2,
        "authority_boundary": contract["authority_transfer"] is False and contract["formal_credit_delta"] == 0 and contract["hard_gate_compensation_allowed"] is False and atom["authority_guards"]["authority_transfer"] is False,
    }
    passed = all(checks.values())
    receipt = {
        "schema": "missioncontrol.gm_i_b.3p_ral_cycle3_contract_selfcheck_receipt.v1",
        "created_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "status": "PASS_CONTRACT_SELF_CHECK" if passed else "DEFER_CONTRACT_SELF_CHECK",
        "source_head": os.environ.get("GITHUB_SHA", "LOCAL_UNBOUND"),
        "source_atom": contract["source_atom"],
        "checks": checks,
        "kpi": {
            "propagation_targets_total": 3,
            "propagation_targets_reached": 1 if passed else 0,
            "propagation_coverage": (1 / 3) if passed else 0.0,
            "semantic_invariants_total": 6,
            "semantic_invariants_preserved_at_controller": 6 if passed else sum([checks["semantic_source_parity"]]) * 6,
            "semantic_parity": 1.0 if passed else 0.0,
            "reuse_ratio": 1.0 if passed else 0.0,
            "duplicate_implementation_count": 0,
            "child_disposition_coverage": 0.0,
            "propagation_depth": 0,
            "authority_inversion_count": 0 if checks["authority_boundary"] else 1
        },
        "next_action": "PROPAGATE_TO_T2_COOLPROP" if passed else "REPAIR_FIRST_RED",
        "authority_transfer": false if False else False,
        "formal_credit_delta": 0
    }
    receipt["contract_sha256"] = sha256_json(contract)
    receipt["atom_sha256"] = sha256_json(atom)
    receipt["receipt_sha256"] = sha256_json(receipt)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
