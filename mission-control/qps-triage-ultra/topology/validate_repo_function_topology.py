#!/usr/bin/env python3
"""Fail-closed validation for the QPS TRIAGE repository-function topology."""

from __future__ import annotations

from pathlib import Path
import sys

import yaml


HERE = Path(__file__).resolve().parent
TOPOLOGY = HERE / "QPS_REPO_FUNCTION_TOPOLOGY_v1.yaml"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    data = yaml.safe_load(TOPOLOGY.read_text(encoding="utf-8"))

    require(data["schema"] == "qps-triage-ultra/repo-function-topology/1.0", "unexpected schema")
    require(data["mission"] == "H4_QPS_TRIAGE", "wrong mission owner")
    require(data["authority_transfer"] is False, "authority transfer must remain false")

    credit = data["formal_credit_delta"]
    require(all(value == 0 for value in credit.values()), "topology routing must create zero formal credit")

    repos = data["repositories"]
    names = [entry["repo"] for entry in repos]
    require(len(names) == len(set(names)), "repository entries must be unique")

    by_name = {entry["repo"]: entry for entry in repos}

    required = {
        "GBOGEB/cryoplant-project": ("ACTIVE_USED", "QPS_CHILD_AUTHORITY"),
        "GBOGEB/pipeline-automation-hub": ("ACTIVE_USED", "MISSION_CONTROL_ORCHESTRATION"),
        "GBOGEB/CODEX": ("ACTIVE_USED", "KEB_SEMANTIC_PROVENANCE"),
        "GBOGEB/ABACUS": ("ACTIVE_USED", "DOW_RUNTIME_METRICS_PROJECTION"),
        "GBOGEB/DOCX_RTM_Automation": ("ACTIVE_USED", "SOURCE_EXTRACTION_RTM_RECONCILIATION"),
        "GBOGEB/Q_engineering_tools": ("EXECUTION_SATELLITE", "EXACT_PAYLOAD_RUNTIME_CARRIER"),
        "GBOGEB/gg_MATH": ("CONTROL_RESERVE", "GENERIC_MATH_PROVIDER"),
        "GBOGEB/stale": ("MAINTENANCE_ONLY", "NONE"),
    }
    for repo, (state, function) in required.items():
        require(repo in by_name, f"missing required topology repo: {repo}")
        require(by_name[repo]["state"] == state, f"unexpected state for {repo}")
        require(by_name[repo]["function"] == function, f"unexpected function for {repo}")

    child_authorities = [entry["repo"] for entry in repos if entry["function"] == "QPS_CHILD_AUTHORITY"]
    require(child_authorities == ["GBOGEB/cryoplant-project"], "exactly one QPS child authority is allowed")

    qtools_prohibitions = set(by_name["GBOGEB/Q_engineering_tools"]["prohibitions"])
    require("cannot_compensate_cryoplant_issue_923" in qtools_prohibitions, "execution carrier must not compensate #923")
    require("cannot_promote_QPS_source_authority" in qtools_prohibitions, "execution carrier must not promote source authority")

    for entry in repos:
        if entry["state"] in {"CONDITIONAL_RESERVE", "DORMANT_CANDIDATE"}:
            require(entry.get("activation_trigger"), f"{entry['repo']} needs an explicit activation trigger")
        if entry["state"] == "MAINTENANCE_ONLY":
            require(not entry.get("exploit_next"), f"maintenance-only repo {entry['repo']} must have no exploit allocation")

    routing = data["routing_selector"]
    require(routing["engineering_source_disposition"] == "GBOGEB/cryoplant-project", "engineering route drift")
    require(routing["semantics_provenance"] == "GBOGEB/CODEX", "semantic route drift")
    require(routing["independent_measurement_runtime_QA"] == "GBOGEB/ABACUS", "measurement route drift")
    require(routing["exact_payload_execution_when_authority_repo_runtime_blocked"] == "GBOGEB/Q_engineering_tools", "runtime-carrier route drift")
    require(routing["generic_math_provider"] == "GBOGEB/gg_MATH", "math-provider route drift")
    require(routing["orchestration_triage_topology"] == "GBOGEB/pipeline-automation-hub", "orchestration route drift")

    gate = data["current_gate"]
    require(gate["h4_w2_3pc_mip_i"] == "HOLD_QPS_REPO_LOCAL_RUNNER_923", "H4 W2 must remain fail-closed")
    require(gate["h4_w3_3p3_mip_p"] == "GATED_BY_W2_LOCAL_DOV", "H4 W3 must remain gated by W2")
    require(gate["independent_non_h4_progress"]["m08_mip2_seed"] == "PASS_FEDERATED_EXACT_RUNTIME", "M08 seed state drift")
    require(gate["post_mip2d_once_only"]["chain"] == ["GBOGEB/CODEX", "GBOGEB/ABACUS", "GBOGEB/cryoplant-project"], "3P3 chain drift")
    require(gate["post_mip2d_once_only"]["terminal_rule"] == "STOP_OR_CONTROL", "3P3 must terminate in STOP/CONTROL")

    print(f"PASS repo-function topology: {len(repos)} repositories; authority_transfer=false; H4 W2 HOLD preserved")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, KeyError, TypeError, ValueError) as exc:
        print(f"FAIL repo-function topology: {exc}", file=sys.stderr)
        raise SystemExit(1)
