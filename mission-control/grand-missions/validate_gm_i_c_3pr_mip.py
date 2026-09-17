#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
PACKET = ROOT / "GM_I_C_3PR_MIP_IC3_CONTROL_v1.json"
CURRENT = ROOT / "GM_I_C_CURRENT_v1.yaml"
EXPECTED_PARENT_MERGE = "3a65e884abe321347bd771b1b094d44e1e08cdd2"
EXPECTED_PARENT_HEAD = "fae367b78d9727e4b6cbc4aebdda129b17437b21"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL: {message}")


def main() -> int:
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    current = yaml.safe_load(CURRENT.read_text(encoding="utf-8"))

    require(packet["mission"] == "GM-I-C", "packet mission mismatch")
    require(packet["state"] == "3PR_MIP_COMPLETE_IC3_EXTERNAL_AUTH_STILL_RED", "unexpected packet state")
    require(packet["authority_transfer"] is False, "authority transfer must remain false")
    require(packet["formal_credit_delta"] == 0, "formal credit delta must remain zero")
    require(packet["hard_gate_compensation_allowed"] is False, "hard-gate compensation must remain forbidden")

    parent = packet["parent_method_control"]
    require(parent["method"] == "GLOBAL_3PR_MIP_M", "global method parent mismatch")
    require(parent["pr"] == 194, "global parent PR mismatch")
    require(parent["merge_sha"] == EXPECTED_PARENT_MERGE, "global parent merge mismatch")
    require(parent["exact_proven_head_sha"] == EXPECTED_PARENT_HEAD, "global parent head mismatch")
    require(parent["relationship"] == "LOCAL_SPECIALISATION_NO_DUPLICATE_AUTHORITY", "local/global authority relationship drift")
    require(packet["live_refresh"]["missioncontrol_sha"] == EXPECTED_PARENT_MERGE, "live MissionControl SHA is not the admitted parent")

    refresh = packet["three_pr"]["Refresh"]
    probe = packet["three_pr"]["Probe"]
    rank = packet["three_pr"]["Rank"]
    require(refresh["result"] == "PASS", "3PR Refresh not complete")
    require(probe["result"] == "PASS", "3PR Probe not complete")
    require(rank["result"] == "PASS", "3PR Rank not complete")
    require(rank["ranked_next_predicates"][0]["id"] == "IC3_EXTERNAL_IDENTITY_CONFIGURATION", "wrong ranked first predicate")
    require(rank["application_repair_rank"] == "NOT_SELECTED_NO_APPLICATION_DEFECT_EVIDENCE", "application repair was incorrectly selected")

    mip = packet["mip"]
    for phase in ("Modernize", "Innovate", "Perpetuate"):
        require(mip[phase]["result"] == "PASS_CONTROL_DESIGN", f"MIP {phase} not complete")

    layers = mip["Innovate"]["proof_layers"]
    require([row["layer"] for row in layers] == ["L0_CONFIG", "L1_IDENTITY", "L2_RESOURCE_AUTH", "L3_RESOURCE_IDENTITY", "L4_GT0_WORK", "L5_RECEIPT"], "proof-layer order drift")

    baseline = packet["kpi_baseline"]
    require(baseline["application_hardening_merged"] is True, "merged hardening baseline lost")
    require(baseline["manual_drive_root_positive_enumeration"] is True, "manual root observation lost")
    require(baseline["external_auth_issue_open"] is True, "external auth issue must remain open at this control point")
    require(baseline["hosted_ic3_pass_observed"] is False, "IC3 hosted PASS must remain withheld")
    require(baseline["ic3_credit"] == 0, "IC3 credit must remain zero")
    require(baseline["authority_inversion_count"] == 0, "authority inversion detected")
    require(baseline["duplicate_auth_implementation_count"] == 0, "duplicate auth implementation detected")

    withheld = set(packet["explicitly_not_executed"])
    require("3PC_EXTERNAL_AUTH_TRANSACTION" in withheld, "3PC must remain uncredited")
    require("3P3_CROSS_AGENT_PROPAGATION_PROOF" in withheld, "3P3 must remain uncredited")

    require(current["mission_id"] == "GM-I-C", "current pointer mission mismatch")
    require(current["authority_transfer"] is False, "current pointer authority transfer weakened")
    require(current["formal_credit_delta"] == 0, "current pointer formal credit weakened")
    current_parent = current["global_method_parent"]
    require(current_parent["pr"] == 194, "current pointer parent PR mismatch")
    require(current_parent["merge_sha"] == EXPECTED_PARENT_MERGE, "current pointer parent merge mismatch")
    require(current_parent["exact_proven_head_sha"] == EXPECTED_PARENT_HEAD, "current pointer parent head mismatch")
    require(current_parent["relationship"] == "LOCAL_SPECIALISATION_NO_DUPLICATE_AUTHORITY", "current pointer relationship drift")
    require(current["provider_current"]["sha"] == packet["live_refresh"]["provider_sha"], "provider SHA mismatch")
    require(current["provider_current"]["hardening_pr_state"] == "MERGED", "PR11 must be recorded merged")
    require(current["bridge_current"]["drive_root_id"] == packet["live_refresh"]["drive_root_id"], "Drive root mismatch")
    require(current["bridge_current"]["manual_connector_direct_children"] == 1, "manual Drive observation count drift")
    require(current["first_red"]["gate"] == "IC3_AUTH", "first red moved without proof")
    require("NO_3PC_CREDIT" in current["explicit_nonclaims"], "3PC nonclaim missing")
    require("NO_3P3_CREDIT" in current["explicit_nonclaims"], "3P3 nonclaim missing")

    receipt = {
        "result": "PASS_GM_I_C_3PR_MIP_CONTROL",
        "mission": "GM-I-C",
        "global_parent_pr": 194,
        "global_parent_merge_sha": EXPECTED_PARENT_MERGE,
        "three_pr": "PASS",
        "mip": "PASS_CONTROL_DESIGN",
        "ic3": "WITHHELD_EXTERNAL_AUTH_CONFIGURATION_AND_HOSTED_PROOF",
        "provider_sha": packet["live_refresh"]["provider_sha"],
        "drive_root_id": packet["live_refresh"]["drive_root_id"],
        "manual_drive_children": packet["live_refresh"]["drive_manual_connector_direct_children"],
        "next_predicate": rank["ranked_next_predicates"][0]["id"],
        "three_pc_credit": 0,
        "three_p3_credit": 0,
        "authority_transfer": False,
        "formal_credit_delta": 0
    }
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
