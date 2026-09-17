#!/usr/bin/env python3
"""Static independent validation of the LM-11 MissionControl/QPS federation contract.

This validator intentionally does not reimplement the QPS graph extractor. It checks
MissionControl identity, authority boundaries, child receipts, launch-baseline integrity,
and the declared current first-red.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MISSIONS = ROOT / "mission-control" / "qps-triage-ultra" / "missions"
CURRENT = MISSIONS / "LM-11_MISSION_CONTROL_CURRENT_v2.yaml"
CONTRACT = MISSIONS / "LM-11_QPS_WAVE_GRAPH_CONTRACT_v2.json"
ATLAS = MISSIONS / "LM-11_QPS_WAVE_ATLAS_CURRENT_v2.md"
RECEIPT = MISSIONS / "receipts" / "LM11_QPS_WAVE_FEDERATION_20260917_v1.yaml"
REGISTER = ROOT / "mission-control" / "OFFICIAL_MISSION_REGISTER_v1.yaml"

EXPECTED_GAPS = {
    105, 113, 118, 141, 152, 156, 157, 193, 194, 195,
    207, 208, 209, 210, 211, 212, 213, 214, 215, 218,
    232, 233, 237, 241, 255,
}


def read(path: Path) -> str:
    if not path.exists():
        raise AssertionError(f"missing required surface: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def require(blob: str, needle: str, label: str) -> None:
    if needle not in blob:
        raise AssertionError(f"{label}: missing {needle!r}")


def extract_launch_gaps(receipt: str) -> set[int]:
    match = re.search(
        r"numeric_gaps:\n(?P<body>(?:\s+- W\d+\n)+)\s+guard:",
        receipt,
        flags=re.M,
    )
    if not match:
        raise AssertionError("receipt: numeric_gaps block not found")
    return {int(x) for x in re.findall(r"W(\d+)", match.group("body"))}


def main() -> None:
    current = read(CURRENT)
    atlas = read(ATLAS)
    receipt = read(RECEIPT)
    register = read(REGISTER)
    contract = json.loads(read(CONTRACT))

    # Contract / authority invariants.
    assert contract["mission_id"] == "LM-11"
    assert contract["authority_transfer"] is False
    assert contract["formal_credit_delta"] == 0
    assert contract["provider"]["implementation_pr"] == 1382
    assert contract["provider"]["runner_control_pr"] == 1385
    assert contract["projection_rules"]["destructive_delete"] is False
    assert contract["projection_rules"]["provenance_always_reachable"] is True
    assert contract["projection_rules"]["highest_wave_label_is_not_global_project_state"] is True
    assert contract["runtime_boundary"]["measured_graph_metrics_available"] is False
    assert contract["runtime_boundary"]["first_red"] == "LM11_FIRST_GREATER_THAN_ZERO_STEP_EXACT_HEAD_GRAPH_RUN"
    assert contract["bounded_dags"]["execution"]["acyclic_required"] is True
    assert contract["bounded_dags"]["supersession"]["acyclic_required"] is True
    assert contract["bounded_dags"]["global_recursive_graph"]["cycles_allowed"] is True

    # Current MissionControl is the governing mission surface; v1 remains provenance only.
    for needle in (
        "mission_id: LM-11",
        "supersedes: mission-control/qps-triage-ultra/missions/LM-11_MISSION_CONTROL_v1.yaml",
        "implementation_pr: 1382",
        "pr: 1385",
        "latest_observed_wave_label: W265",
        "current_global_qtg_wave: W248",
        "current_global_first_red: ISSUE_923",
        "P1_PROVENANCE_CENSUS:",
        "P2_LINEAGE_RESOLUTION:",
        "P3_DEPENDENCY_DAG:",
        "P4_ARTIFACT_RUNTIME:",
        "P5_NAVIGATION_HMI:",
        "P6_FEDERATION_SATELLITE:",
        "LM11_FIRST_GREATER_THAN_ZERO_STEP_EXACT_HEAD_GRAPH_RUN",
        "DO_NOT_SORT_WAVE_NUMBERS_AND_CALL_THAT_LINEAGE",
        "DO_NOT_FABRICATE_MEASURED_GRAPH_METRICS",
    ):
        require(current, needle, "current mission control")

    # Official registration must remain local and zero-credit.
    for needle in (
        "id: LM-11",
        "type: LOCAL_REPOSITORY_LINEAGE_AND_TRIAGE",
        "official_control: mission-control/qps-triage-ultra/missions/LM-11_MISSION_CONTROL_CURRENT_v2.yaml",
        "proof_state: INFRA_PREEXECUTION_ZERO_STEP_REPRODUCED",
        "LM_11_is_local_navigation_lineage_mission_not_global_QPS_wave",
        "LM_11_does_not_allocate_or_imply_GM_VI",
    ):
        require(register, needle, "official register")

    # Exact child evidence and zero-step semantics.
    for needle in (
        "observed_main: cbf09012b31c997cc0dcd245bb7f8c3e56bd601b",
        "pr: 1382",
        "merge: f6eb1f6344e9953c095cd4dfadcf89991499f791",
        "pr: 1385",
        "merge: cbf09012b31c997cc0dcd245bb7f8c3e56bd601b",
        "INFRA_PREEXECUTION_ZERO_STEP",
        "INFRA_PREEXECUTION_ZERO_STEP_REPRODUCED",
        "application_failure_claimed: false",
        "graph_execution_claimed: false",
        "measured_graph_metrics_claimed: false",
        "RESOLVED_BY_CURRENT_CANONICAL_RESOLVER_WITH_HISTORY_PRESERVED",
        "current_global_qtg_wave_reported_by_child: W248",
        "highest_later_wave_label_observed: W265",
        "LM11_FIRST_GREATER_THAN_ZERO_STEP_EXACT_HEAD_GRAPH_RUN",
    ):
        require(receipt, needle, "child federation receipt")

    gaps = extract_launch_gaps(receipt)
    if gaps != EXPECTED_GAPS:
        raise AssertionError(f"launch gap set drift: expected {sorted(EXPECTED_GAPS)}, got {sorted(gaps)}")
    require(receipt, "triage_wave_directory_count_W103_to_W264: 137", "launch projection")
    require(receipt, "numeric_gap_count_W103_to_W264: 25", "launch projection")
    require(receipt, "MISSING_DIRECTORY_NE_MISSING_WAVE_LINEAGE", "launch projection")

    # Atlas completeness is structural, not a runtime-success claim.
    for needle in (
        "## 5. Full pipeline wireframe",
        "## 6. Sectional DAG catalogue",
        "## 7. Entry and exit points",
        "## 8. Artifact and executable classes",
        "## 9. Satellite / federation node view",
        "## 10. HMI and navigation views",
        "V00 Restart Spine",
        "V12 Current Gate vs Highest Wave",
        "exact-head graph population: **NOT_EXECUTED**",
        "measured Wave↔PR coverage: **NOT_EXECUTED**",
    ):
        require(atlas, needle, "atlas")

    result = {
        "status": "PASS_LM11_MISSIONCONTROL_FEDERATION_STATIC",
        "mission": "LM-11",
        "qps_implementation_pr": 1382,
        "qps_runner_control_pr": 1385,
        "launch_wave_directory_projection": 137,
        "launch_numeric_gap_count": 25,
        "current_global_qtg_wave": "W248",
        "later_parallel_wave_label": "W265",
        "qps_runtime_proof": "WITHHELD_ZERO_STEP_REPRODUCED",
        "measured_graph_metrics_claimed": False,
        "authority_transfer": False,
        "formal_credit_delta": 0,
        "first_red": "LM11_FIRST_GREATER_THAN_ZERO_STEP_EXACT_HEAD_GRAPH_RUN",
    }
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
