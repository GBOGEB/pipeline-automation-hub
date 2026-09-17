#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONTROL = HERE / "GT_BD_003_3PC_PREPARE_W250_v1.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL: {message}")


def main() -> int:
    c = json.loads(CONTROL.read_text(encoding="utf-8"))
    require(c["bd_item"] == "GT-BD-003", "wrong BD item")
    require(c["method"] == "3PC", "wrong method")
    require(c["state"] == "PREPARE_PASS_PROVE_HELD_CHILD_HOSTED_ZERO_STEP", "unexpected state")
    require(c["authority_transfer"] is False, "authority transfer must remain false")
    require(c["formal_credit_delta"] == 0, "formal credit must remain zero")
    require(c["qps_credit_delta"] == 0, "QPS credit must remain zero")

    child = c["real_child_target"]
    require(child["repo"] == "GBOGEB/cryoplant-project", "wrong child repository")
    require(child["pr"] == 1438, "wrong child PR")
    require(child["exact_head_sha"] == "0c88a8efe09ccf7cb0b11ecc19632a1191621524", "child head drift")
    require(child["source_gate_document_id"] == "W93_R5_PVPS_TERMINAL_CHILD_GATE", "source gate mismatch")
    require(child["source_gate_blob_sha1"] == "d3584cd900c583d918683eb2b02c94a08c66e84c", "source gate blob mismatch")
    require(child["child_disposition"] == "DEFER", "child disposition promoted without proof")
    require(child["child_reset_authority"] == "QPS_CHILD_ONLY", "child reset authority drift")

    attempt = c["child_hosted_attempt"]
    require(attempt["run_id"] == 35244036243, "run id mismatch")
    require(attempt["job_id"] == 105279499163, "job id mismatch")
    require(attempt["steps"] is None, "zero-step evidence was rewritten")
    require(attempt["classification"] == "INFRA_PREEXECUTION_ZERO_STEP", "wrong failure class")
    require(attempt["application_defect_evidence"] is False, "zero-step may not become application evidence")
    require(attempt["repair_authorized_from_attempt"] is False, "repair must remain unauthorized")

    three_pc = c["three_pc"]
    require(three_pc["Prepare"]["status"] == "PASS", "Prepare must pass")
    require(three_pc["Prove"]["status"] == "WITHHELD", "Prove must remain withheld")
    require(three_pc["Commit_or_HOLD"]["status"] == "HOLD", "Commit must remain on hold")

    release = set(three_pc["Prove"]["release_conditions"])
    required = {
        "QPS_PR_1438_HOSTED_RUN_STEPS_GT_0",
        "CHILD_AUTHORITY_VALIDATOR_PASS",
        "MISSIONCONTROL_GENERIC_GATE_PROOF_EXECUTED",
        "PERMISSIVE_CANNOT_COMPENSATE_LATCHED_INHIBIT",
        "UNAUTHORIZED_RESET_REJECTED",
        "AUTHORIZED_REASONED_RESET_CLEARS_LATCH_AND_PERMISSIVES",
        "CURRENT_SOURCE_INHIBIT_REASSERTS_AFTER_REPROPAGATION",
        "FINAL_CHILD_DISPOSITION_REMAINS_DEFER",
    }
    require(required.issubset(release), "3PC Prove release conditions incomplete")

    noncomp = set(c["non_compensation"])
    for item in (
        "ZERO_STEP_NE_APPLICATION_FAIL",
        "PARENT_PASS_NE_CHILD_ACCEPT",
        "MISSIONCONTROL_PASS_NE_QPS_GT_BDQ_PASS",
        "QPS_GT_BDQ_0_UNCHANGED",
        "AUTHORITY_TRANSFER_FALSE",
    ):
        require(item in noncomp, f"missing non-compensation control: {item}")

    print(json.dumps({
        "status": "PASS_GT_BD_003_3PC_PREPARE_ONLY",
        "prepare": "PASS",
        "prove": "WITHHELD_CHILD_ZERO_STEP",
        "commit_or_hold": "HOLD",
        "child_pr": child["pr"],
        "child_head": child["exact_head_sha"],
        "child_disposition": child["child_disposition"],
        "authority_transfer": False,
        "qps_credit_delta": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
