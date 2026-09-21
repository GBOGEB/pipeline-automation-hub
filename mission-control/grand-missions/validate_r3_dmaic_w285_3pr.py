#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

EXPECTED_REFRESH = {
    "pipeline_automation_hub": {
        "branch": "master",
        "head": "8d0e2ecba2c318527eb99c8b504994995deb660e",
    },
    "cryoplant_project": {
        "branch": "main",
        "head": "41998c71cf187e3640cf273f7be9b5b96539aab1",
    },
    "gemini": {
        "branch": "main",
        "head": "439838866e77784334ef76d231f9a9e0aa4f5e5c",
    },
}

EXPECTED_PROBE = {
    "r3_release_issue": "GBOGEB/cryoplant-project#1398",
    "environment_issue": "GBOGEB/cryoplant-project#1426",
    "dmaic_issue": "GBOGEB/pipeline-automation-hub#209",
    "active_successor": "1248290ca0a9d55ec83d0efa0235ed1a45a88eeb",
    "exact_capsule_schema_authoritative": "gmi.r3_successor.exact_env_capsule.v2",
    "producer_repo": "GBOGEB/GEMINI",
    "producer_state": "PASS_MERGED",
    "physical_bundle_state": "WAIT_RETURN",
    "first_red": "PHYSICAL_SUCCESSOR_GIT_BUNDLE_RETURN_1248290C",
    "r3_release_production_dov": "WITHHELD",
    "r4": "BLOCKED_NOT_NEXT",
}

EXPECTED_RANK = [
    {
        "order": 1,
        "id": "QPS_EXACT_ENV_VALIDATOR_SCHEMA_DRIFT",
        "severity": "P1",
        "action": "MIP_MODERNIZE_QPS_VALIDATOR_TO_AUTHORITATIVE_UNDERSCORE_SCHEMA",
    },
    {
        "order": 2,
        "id": "MC_PROTECTED_RECEIPT_SCHEMA_BINDING_DRIFT",
        "severity": "P1",
        "action": "MIP_INNOVATE_FEDERATION_V5_FROM_CANONICAL_QPS_AND_GEMINI_SCHEMA",
    },
    {
        "order": 3,
        "id": "MC_PRODUCER_READINESS_UNVALIDATED",
        "severity": "P2",
        "action": "MIP_INNOVATE_VALIDATE_SUCCESSOR_GIT_OBJECT_PRODUCER_STATE",
    },
    {
        "order": 4,
        "id": "MC_PHYSICAL_ABSENCE_UNVALIDATED",
        "severity": "P2",
        "action": "MIP_INNOVATE_VALIDATE_WAIT_RETURN_AND_QUALIFYING_BUNDLE_FALSE",
    },
    {
        "order": 5,
        "id": "QPS_DMAIC_CONSUMER_FAIL_OPEN",
        "severity": "P2",
        "action": "MIP_MODERNIZE_VALIDATE_ALL_PROPAGATED_KPI_AND_REMEASUREMENT_TRIGGERS",
    },
]

EXPECTED_GUARDS = {
    "issue_923": "RED_OWNER_ACTION",
    "gt_bdq_0": "RED_BLOCKED_ON_923_INFRA_PREEXECUTION",
    "runtime_gold": "WITHHELD",
    "canonical_gt_credit": "NONE",
    "r3_release_3p3_authorized": False,
}

EXPECTED_NEXT = "MIP_MODERNIZE_QPS_EXACT_ENV_AND_DMAIC_CONSUMER"


def fail(message: str) -> None:
    raise SystemExit("W285_3PR_FAIL: " + message)


def checks_for(doc: dict) -> dict[str, bool]:
    formal_credit = doc.get("formal_credit_delta")
    return {
        "schema": doc.get("schema") == "missioncontrol.hm01.r3.dmaic_w285_3pr_refresh.v1",
        "issue": doc.get("issue") == "GBOGEB/pipeline-automation-hub#209",
        "method": doc.get("method") == "3PR",
        "authority": doc.get("authority_transfer") is False,
        "formal_credit": (
            isinstance(formal_credit, int)
            and not isinstance(formal_credit, bool)
            and formal_credit == 0
        ),
        "refresh_exact": doc.get("refresh") == EXPECTED_REFRESH,
        "probe_exact": doc.get("probe") == EXPECTED_PROBE,
        "rank_exact": doc.get("rank") == EXPECTED_RANK,
        "guards_exact": doc.get("guards") == EXPECTED_GUARDS,
        "next_exact": doc.get("next") == EXPECTED_NEXT,
    }


def validate(doc: dict) -> dict[str, bool]:
    checks = checks_for(doc)
    if not all(checks.values()):
        fail(json.dumps({key: value for key, value in checks.items() if not value}, sort_keys=True))
    return checks


def self_test(doc: dict) -> None:
    mutations = []

    changed = copy.deepcopy(doc)
    changed["refresh"]["pipeline_automation_hub"]["head"] = "0" * 40
    mutations.append(changed)

    changed = copy.deepcopy(doc)
    changed["probe"]["active_successor"] = "0" * 40
    mutations.append(changed)

    changed = copy.deepcopy(doc)
    changed["rank"][0]["action"] = "ADVANCE_R4"
    mutations.append(changed)

    changed = copy.deepcopy(doc)
    changed["guards"]["r3_release_3p3_authorized"] = True
    mutations.append(changed)

    changed = copy.deepcopy(doc)
    changed["next"] = "ADVANCE_R4"
    mutations.append(changed)

    for candidate in mutations:
        try:
            validate(candidate)
        except SystemExit:
            continue
        fail("self-test accepted protected mutation")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--out")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    doc = json.loads(Path(args.receipt).read_text())
    checks = validate(doc)
    if args.self_test:
        self_test(doc)

    out = {
        "schema": "missioncontrol.hm01.r3.dmaic_w285_3pr_receipt.v2",
        "status": "PASS_3PR_REFRESH_PROBE_RANK",
        "checks": checks,
        "refresh": doc["refresh"],
        "probe": doc["probe"],
        "rank": doc["rank"],
        "guards": doc["guards"],
        "next": doc["next"],
        "authority_transfer": False,
        "formal_credit_delta": 0,
    }
    payload = json.dumps(out, indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(payload)
    print(payload, end="")


if __name__ == "__main__":
    main()
