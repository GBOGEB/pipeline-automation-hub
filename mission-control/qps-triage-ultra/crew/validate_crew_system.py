#!/usr/bin/env python3
"""Dependency-free validator for the MissionControl crew capability system."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REGISTRY = HERE / "CREW_REGISTRY_v1.json"
MATRIX = HERE / "COMPETENCY_MATRIX_v1.json"
REX = HERE / "REX_LEARNING_LEDGER_v1.json"
POLICY = HERE / "ROLE_DEVELOPMENT_POLICY_v1.json"

DIMENSIONS = {
    "discovery",
    "deep_reading",
    "architecture",
    "planning",
    "build_repair",
    "runtime_execution",
    "evidence_provenance",
    "analysis_pca_bt",
    "operations_control",
    "rex_learning",
}


def load(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    registry = load(REGISTRY)
    matrix = load(MATRIX)
    rex = load(REX)
    policy = load(POLICY)

    require(registry.get("authority_transfer") is False, "authority_transfer must remain false", errors)
    crew = registry.get("crew", [])
    require(bool(crew), "crew registry must not be empty", errors)

    required_fields = set(registry.get("required_fields", []))
    ids: list[str] = []
    by_id: dict[str, dict] = {}

    for member in crew:
        crew_id = member.get("crew_id", "<missing>")
        ids.append(crew_id)
        by_id[crew_id] = member
        missing = sorted(required_fields - set(member))
        require(not missing, f"{crew_id}: missing required fields {missing}", errors)

        vector = member.get("competency_vector", {})
        require(DIMENSIONS <= set(vector), f"{crew_id}: competency vector missing dimensions", errors)
        for dim in DIMENSIONS:
            value = vector.get(dim)
            require(isinstance(value, int) and 0 <= value <= 6, f"{crew_id}: {dim} must be integer 0..6", errors)
        require(bool(vector.get("basis")), f"{crew_id}: competency basis required", errors)

        maturity = member.get("maturity")
        control = str(member.get("control_eligibility", ""))
        authority = member.get("authority", {})
        if maturity == "CONCEPTUAL":
            require(control == "NOT_ELIGIBLE", f"{crew_id}: conceptual role cannot be CONTROL eligible", errors)
            require(authority.get("promote") is False, f"{crew_id}: conceptual role cannot promote", errors)
            require(authority.get("control") is False, f"{crew_id}: conceptual role cannot hold CONTROL authority", errors)
            require(member.get("last_evidence_sha") is None, f"{crew_id}: conceptual role must not fabricate evidence SHA", errors)
        elif maturity in {"OBSERVED", "PARTIAL"}:
            require(bool(member.get("source_refs")), f"{crew_id}: observed/partial role needs source_refs", errors)
            require(bool(member.get("last_evidence_sha")), f"{crew_id}: observed/partial role needs evidence SHA", errors)
        else:
            errors.append(f"{crew_id}: unknown maturity {maturity!r}")

    require(len(ids) == len(set(ids)), "crew_id values must be unique", errors)

    require("S01" in by_id, "Ambassador S01 must exist", errors)
    if "S01" in by_id:
        require("AMBASSADOR" in by_id["S01"].get("roles", []), "S01 must carry AMBASSADOR role", errors)
        require(by_id["S01"].get("maturity") == "OBSERVED", "Ambassador must remain OBSERVED", errors)

    # Matrix integrity.
    require(set(matrix.get("dimensions", {})) == DIMENSIONS, "matrix dimensions must exactly match validator dimensions", errors)
    require("L6" in matrix.get("scale", {}), "competency scale must define L0..L6 through L6", errors)
    evidence_classes = set(matrix.get("evidence_classes", {}))
    for member in crew:
        basis = member.get("competency_vector", {}).get("basis")
        require(basis in evidence_classes, f"{member.get('crew_id')}: unknown competency evidence basis {basis!r}", errors)

    # REX references must resolve to real crew IDs.
    rex_ids: set[str] = set()
    for entry in rex.get("entries", []):
        rex_id = entry.get("rex_id")
        require(bool(rex_id), "REX entry missing rex_id", errors)
        require(rex_id not in rex_ids, f"duplicate REX id {rex_id}", errors)
        rex_ids.add(rex_id)
        for crew_id in entry.get("primary_roles", []):
            require(crew_id in by_id, f"{rex_id}: unknown crew reference {crew_id}", errors)
        for dim in entry.get("affected_competencies", []):
            require(dim in DIMENSIONS, f"{rex_id}: unknown competency {dim}", errors)

    declared_rex = {f"REX-{n:03d}" for n in range(1, 7)}
    require(declared_rex <= rex_ids, "REX-001 through REX-006 must be represented", errors)

    # Candidate role policy must bind only conceptual roles.
    candidate_ids = {item.get("crew_id") for item in policy.get("candidate_roles_seeded_now", [])}
    conceptual_ids = {member["crew_id"] for member in crew if member.get("maturity") == "CONCEPTUAL"}
    require(candidate_ids == conceptual_ids, "candidate role policy must exactly match conceptual registry members", errors)

    ambassador_rule = policy.get("ambassador_rule", {})
    require(ambassador_rule.get("crew_id") == "S01", "ambassador policy must bind S01", errors)

    states = [item.get("state") for item in policy.get("lifecycle", [])]
    required_states = ["NEED_SIGNAL", "CONCEPTUAL", "TRIAL", "PARTIAL", "OBSERVED", "CONTROL_ELIGIBLE", "MERGED_PRUNED_RETURNED"]
    require(states == required_states, "role lifecycle state machine order changed unexpectedly", errors)

    if errors:
        print(json.dumps({"status": "FAIL_CREW_SYSTEM", "error_count": len(errors), "errors": errors}, indent=2))
        return 1

    maturity_counts: dict[str, int] = {}
    for member in crew:
        maturity_counts[member["maturity"]] = maturity_counts.get(member["maturity"], 0) + 1

    print(
        json.dumps(
            {
                "status": "PASS_CREW_SYSTEM",
                "crew_count": len(crew),
                "maturity_counts": maturity_counts,
                "rex_count": len(rex_ids),
                "candidate_role_count": len(candidate_ids),
                "ambassador": "S01_OBSERVED",
                "authority_transfer": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
