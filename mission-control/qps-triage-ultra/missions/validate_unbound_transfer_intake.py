#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

EXPECTED_SOURCE_HEAD = "215e96f6bec22f7d4126322007029518a4f5ac23"
EXPECTED_ISSUE = "GBOGEB/pipeline-automation-hub#127"
EXPECTED_QPS_CONTROL = "GBOGEB/cryoplant-project#1258"
EXPECTED_DUP_SHA = "d7be6edd34c78574ae4bc4066a1531200d27e548d250319d43ca4c0551c34f44"
EXPECTED_REENTRY = {
    "trigger": "DISTINCT_MATERIALIZED_EXACT_BYTE_SOURCE_ARRIVES",
    "steps": [
        "PRESERVE_EXACT_SOURCE_BYTES",
        "BIND_SHA256",
        "RUN_EXISTING_QPS_UNBOUND_ROOT_READER",
        "REQUIRE_SAFE_SYNTAX_STATE",
        "RUN_EXISTING_QPS_STREAK_EVALUATOR",
        "REJECT_EXACT_SHA_DUPLICATES_WITHOUT_INCREMENT",
        "KEEP_AUTHORITY_TRANSFER_FALSE",
    ],
}

EXPECTED_INVARIANTS = {
    "RAW_SOURCE_CONTENT_IS_NOT_REPLICATED_IN_MISSIONCONTROL",
    "UNKNOWN_COUNTS_REMAIN_NULL_NOT_ZERO",
    "FORMAT_OR_LOCATION_DOES_NOT_CREATE_AUTHORITY",
    "EXACT_SHA_DEDUPE_PRECEDES_EVIDENCE_CREDIT",
    "SECRET_RISK_INPUT_IS_QUARANTINED",
    "CURATED_OUTPUT_ROUTES_TO_OWNING_REPOSITORY",
    "QPS_RETAINS_INTAKE_HASH_AND_ROUTING_AUTHORITY",
    "NO_COMPENSATION_OF_QPS_923_OR_OTHER_EXTERNAL_GATES",
}


def fail(message: str) -> None:
    raise SystemExit("UNBOUND_TRANSFER_INTAKE_FAIL: " + message)


def validate(doc: dict) -> dict[str, bool]:
    credit = doc.get("formal_credit_delta", {})
    census = doc.get("scout_reader_census", {})
    leg5 = census.get("leg5_txt_log", {})
    leg6 = census.get("leg6_markdown", {})
    leg7 = census.get("leg7_json", {})
    leg8 = census.get("leg8_yaml", {})
    leg9 = census.get("leg9_yml", {})
    source = doc.get("source_authority", {})
    disposition = doc.get("disposition", {})
    queue = doc.get("queue", [])

    checks = {
        "schema": doc.get("schema") == "missioncontrol.unbound_transfer_intake_current.v1",
        "issue": doc.get("mission_control_issue") == EXPECTED_ISSUE,
        "authority": doc.get("authority_transfer") is False,
        "credit_zero": credit == {
            "engineering": 0,
            "compliance": 0,
            "negotiation": 0,
            "acceptance": 0,
            "release": 0,
            "runtime_gold": 0,
        },
        "source_head": source.get("exact_head") == EXPECTED_SOURCE_HEAD,
        "source_control": source.get("control_issue") == EXPECTED_QPS_CONTROL,
        "leg5_state": (
            leg5.get("state") == "CONTROL_5_OF_5_REAL_PROCESS_ONLY"
            and leg5.get("accessible_txt_census_observed") == 214
            and leg5.get("unique_reader_objects_observed") == 30
            and leg5.get("tracked_owner_routes") == 9
            and leg5.get("closed_routes") == 7
            and leg5.get("open_routes") == 2
        ),
        "unknown_counts_null": (
            leg5.get("exact_sha_family_count") is None
            and leg5.get("duplicate_alias_count") is None
            and leg5.get("quarantined_secret_risk_source_count") is None
        ),
        "known_duplicate_bound": (
            leg5.get("known_duplicate_family_example", {}).get("sha256") == EXPECTED_DUP_SHA
            and leg5.get("known_duplicate_family_example", {}).get("credit_delta") == 0
            and len(leg5.get("known_duplicate_family_example", {}).get("aliases", [])) == 2
        ),
        "leg6_control": (
            leg6.get("state") == "CONTROL_5_OF_5_PROCESS_ONLY"
            and leg6.get("authority_created") is False
            and leg6.get("next") == "CLOSED_UNLESS_REGRESSION"
        ),
        "structured_wait": all(
            row.get("state") == "IMPROVE_WAIT_EXACT_BYTES"
            and row.get("streak") == "1_OF_5"
            and row.get("increment_this_refresh") == 0
            and row.get("runnable_now") is False
            for row in (leg7, leg8, leg9)
        ),
        "queue_exact": (
            len(queue) == 2
            and queue[0].get("item") == "LEG5_DOWNSTREAM_OWNER_ROUTE_CLOSURE"
            and queue[0].get("state") == "7_OF_9_CLOSED"
            and queue[0].get("local_missioncontrol_code_action") is False
            and queue[1].get("item") == "ROOT_JSON_YAML_YML_INTAKE"
            and queue[1].get("class") == "EXTERNAL_RETURN"
            and queue[1].get("state") == "WAIT_EXACT_BYTE_MATERIALIZATION"
            and queue[1].get("local_missioncontrol_code_action") is False
        ),
        "reentry_contract": doc.get("reentry_contract") == EXPECTED_REENTRY,
        "invariants": set(doc.get("invariants", [])) == EXPECTED_INVARIANTS,
        "disposition": disposition == {
            "mission_control_acceptance": "PASS_RECEIVER_CONTRACT_MATERIALIZED",
            "issue_127_after_receiver_proof": "CLOSE_COMPLETED",
            "residual_input_pressure": "EXTERNAL_RETURN_ONLY",
            "residual_local_coding_pressure": 0,
        },
    }
    if not all(checks.values()):
        fail(json.dumps({k: v for k, v in checks.items() if not v}, sort_keys=True))
    return checks


def self_test(doc: dict) -> None:
    mutations = []

    candidate = copy.deepcopy(doc)
    candidate["authority_transfer"] = True
    mutations.append(candidate)

    candidate = copy.deepcopy(doc)
    candidate["source_authority"]["exact_head"] = "0" * 40
    mutations.append(candidate)

    candidate = copy.deepcopy(doc)
    candidate["scout_reader_census"]["leg5_txt_log"]["duplicate_alias_count"] = 0
    mutations.append(candidate)

    candidate = copy.deepcopy(doc)
    candidate["scout_reader_census"]["leg7_json"]["runnable_now"] = True
    mutations.append(candidate)

    candidate = copy.deepcopy(doc)
    candidate["queue"][1]["class"] = "RUNNABLE_INTERNAL"
    mutations.append(candidate)

    candidate = copy.deepcopy(doc)
    candidate["reentry_contract"]["steps"].remove("BIND_SHA256")
    mutations.append(candidate)

    candidate = copy.deepcopy(doc)
    candidate["reentry_contract"]["trigger"] = "ANY_REFERENCE_SEEN"
    mutations.append(candidate)

    for candidate in mutations:
        try:
            validate(candidate)
        except SystemExit:
            continue
        fail("self-test accepted protected mutation")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control", required=True)
    parser.add_argument("--out")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    doc = json.loads(Path(args.control).read_text())
    checks = validate(doc)
    if args.self_test:
        self_test(doc)

    receipt = {
        "schema": "missioncontrol.unbound_transfer_intake_receipt.v1",
        "status": "PASS_UNBOUND_TRANSFER_RECEIVER",
        "source_head": EXPECTED_SOURCE_HEAD,
        "mission_control_issue": EXPECTED_ISSUE,
        "checks": checks,
        "next": "WAIT_EXTERNAL_EXACT_BYTES_OR_OWNER_ROUTE_RUNTIME_RETURN",
        "authority_transfer": False,
        "formal_credit_delta": 0,
    }
    payload = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(payload)
    print(payload, end="")


if __name__ == "__main__":
    main()
