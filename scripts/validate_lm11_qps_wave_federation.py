#!/usr/bin/env python3
"""Validate LM-11 MissionControl/QPS federation bindings without duplicating QPS graph logic."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MISSIONS = ROOT / "mission-control" / "qps-triage-ultra" / "missions"
CONTROL = MISSIONS / "LM-11_MISSION_CONTROL_v1.yaml"
CONTRACT = MISSIONS / "LM-11_QPS_WAVE_GRAPH_CONTRACT_v1.json"
ATLAS = MISSIONS / "LM-11_QPS_WAVE_ATLAS_v1.md"
RECEIPT = MISSIONS / "LM-11_REFRESH_AND_CHILD_RECEIPT_2026-09-17_v1.yaml"
REGISTER = ROOT / "mission-control" / "OFFICIAL_MISSION_REGISTER_v1.yaml"


def text(path: Path) -> str:
    if not path.exists():
        raise AssertionError(f"missing required LM-11 surface: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def require(haystack: str, needle: str, label: str) -> None:
    if needle not in haystack:
        raise AssertionError(f"{label}: missing {needle!r}")


def main() -> None:
    control = text(CONTROL)
    atlas = text(ATLAS)
    receipt = text(RECEIPT)
    register = text(REGISTER)
    contract = json.loads(text(CONTRACT))

    assert contract["mission_id"] == "LM-11"
    assert contract["authority_transfer"] is False
    assert contract["formal_credit_delta"] == 0
    assert contract["projection_rules"]["destructive_delete"] is False
    assert contract["projection_rules"]["provenance_always_reachable"] is True
    assert "SUPERSEDES" in contract["edge_schema"]["edge_types"]
    assert "PARALLEL_NONCOMPENSATING" in contract["edge_schema"]["edge_types"]

    for needle in (
        "mission_id: LM-11",
        "authority_transfer: false",
        "formal_credit_delta: 0",
        "chronological_predecessor_NE_causal_parent_NE_semantic_predecessor_NE_prior_current",
        "absence_of_triage_wNNN_directory_does_not_prove_absence_of_wave_history",
    ):
        require(control, needle, "mission control")

    for needle in (
        "LM-11",
        "QPS_WAVE_LINEAGE_DEPENDENCY_CARTOGRAPHY",
        "implementation_pr: 1382",
        "implementation_merge_sha: f6eb1f6344e9953c095cd4dfadcf89991499f791",
        "current_first_red: LM11_FIRST_GREATER_THAN_ZERO_STEP_EXACT_HEAD_GRAPH_RUN",
        "LM_11_navigation_does_not_mutate_QPS_child_authority_or_compensate_runtime_GOLD",
    ):
        require(register, needle, "official mission register")

    for needle in (
        "qps_child:",
        "observed_main: cbf09012b31c997cc0dcd245bb7f8c3e56bd601b",
        "implementation_pr: 1382",
        "implementation_merge: f6eb1f6344e9953c095cd4dfadcf89991499f791",
        "INFRA_PREEXECUTION_ZERO_STEP",
        "INFRA_PREEXECUTION_ZERO_STEP_REPRODUCED",
        "application_failure_claimed: false",
        "graph_runtime_claimed: false",
        "disposition: RESOLVED_BY_CURRENT_RESOLVER_PRECEDENCE_WITH_HISTORY_PRESERVED",
        "historical_pr_110_reachable: true",
        "current_pr_111: true",
        "issue_923_compensation: FORBIDDEN",
        "LM11_FIRST_GREATER_THAN_ZERO_STEP_EXACT_HEAD_GRAPH_RUN",
    ):
        require(receipt, needle, "refresh/child receipt")

    for needle in (
        "Global recursion may cycle across transactions.",
        "Each bounded execution DAG and each lineage DAG must remain acyclic.",
        "Human-facing generated output",
        "Hybrid control",
        "Machine state",
        "Code core",
        "Wave Timeline",
        "Dependency DAG",
        "Satellite Round-trip",
    ):
        require(atlas, needle, "atlas")

    result = {
        "status": "PASS_LM11_MISSIONCONTROL_FEDERATION_STATIC",
        "mission": "LM-11",
        "qps_implementation_pr": 1382,
        "qps_implementation_merge": "f6eb1f6344e9953c095cd4dfadcf89991499f791",
        "qps_hosted_runtime_proof": "DEFER_INFRA_PREEXECUTION",
        "runtime_metrics_claimed": False,
        "authority_transfer": False,
        "formal_credit_delta": 0,
        "first_red": "LM11_FIRST_GREATER_THAN_ZERO_STEP_EXACT_HEAD_GRAPH_RUN",
    }
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
