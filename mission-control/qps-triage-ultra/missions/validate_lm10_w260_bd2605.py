#!/usr/bin/env python3
from __future__ import annotations
import json
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
INPUT=ROOT/"mission-control/qps-triage-ultra/missions/LM-10_W260_BD260_5_PROVIDER_RECEIPT_PROJECTION_v1.json"
OUT=ROOT/"mission-control/qps-triage-ultra/missions/LM-10_W260_BD260_5_TRIAGE_RECEIPT_v1.json"

EXPECTED_SOURCE="2b27f4a6d70a11324d9a7c81d9c88995888b3d74"
EXPECTED_ARTIFACT_DIGEST="sha256:603da43f85e9709f0372b3f487e5c15c78e628adc4f6ae19232b8108af233a15"
EXPECTED_FIXTURE="9bdb111b1365583ba4d615176d93c7a0650dc85bcd958db8567cba48214586f5"
EXPECTED_CONTRACT="95b8a1c7b886026d491bbf880f3a6d9ab17c4b4cdac36687593a97f130f8fd63"
ALLOWED_THRESHOLD_CLASSES={"STATISTICAL","PROJECT_GOVERNED","GOVERNANCE_IDENTITY","NONE"}

def main():
    d=json.loads(INPUT.read_text())
    p=d["provider"]; r=d["receipt"]
    assert p["source_sha"]==EXPECTED_SOURCE
    assert r["source_sha"]==EXPECTED_SOURCE
    assert p["workflow_run"]==35592153194
    assert p["job"]==106308723087
    assert p["artifact_id"]==10634743904
    assert p["artifact_digest"]==EXPECTED_ARTIFACT_DIGEST
    assert r["fixture_sha256"]==EXPECTED_FIXTURE
    assert r["contract_sha256"]==EXPECTED_CONTRACT
    assert r["status"]=="PASS_COMMON_FIXTURE_CHALLENGE"
    assert r["card_count"]==5
    assert r["authority_transfer"] is False
    assert r["formal_credit_delta"]==0
    assert r["engineering_acceptance"] is False
    assert r["qps_threshold_authority"] is False
    assert d["authority_transfer"] is False
    assert d["formal_credit_delta"]==0

    required=set(r["required_card_keys"])
    assert required=={"math","assumptions","value","threshold_kind","measured_result","uncertainty","first_red","validity_domain","dmaic_kpi","disposition"}
    first_reds=[]
    statistical=0
    governed=0
    none=0
    for card in r["cards"]:
        assert card["keys_exact"] is True
        assert card["threshold_class"] in ALLOWED_THRESHOLD_CLASSES
        if card["threshold_class"]=="STATISTICAL":
            statistical+=1
            assert card["threshold_kind"] in {"DISTRIBUTION_DERIVED_AND_DATA_CALIBRATED","DATA_CALIBRATED"}
        elif card["threshold_class"]=="PROJECT_GOVERNED":
            governed+=1
            assert card["threshold_kind"].startswith("PROJECT_GOVERNED")
        elif card["threshold_class"]=="GOVERNANCE_IDENTITY":
            assert card["threshold_kind"]=="EXACT_IDENTITY"
        else:
            none+=1
            assert card["threshold_kind"]=="NO_UNIVERSAL_THRESHOLD"
        if card["first_red"] is not None:
            first_reds.append(card["first_red"])

    assert statistical==2
    assert governed==0
    assert none==2
    assert "MANOVA_RUNTIME_NOT_PROMOTED_IN_THIS_SLICE" in first_reds
    assert "DEFER_NO_FINITE_MLE" in first_reds
    assert r["explicit_defer"]["confidence_sequence"]=="RESEARCH_TODO"
    assert r["explicit_defer"]["hierarchical_bayesian_bt"]=="RESEARCH_TODO"
    assert r["explicit_defer"]["grassmann_state_space"]=="RESEARCH_TODO"
    assert r["explicit_defer"]["manova"]=="NOT_PROMOTED_IN_THIS_SLICE"

    out={
      "schema":"qps.lm10.w260.bd2605.triage_receipt.v1",
      "mission_id":"LM-10","wave":"W260","bd_id":"BD-260.5",
      "source_sha":os.environ.get("SOURCE_SHA","LOCAL_UNBOUND"),
      "provider_source_sha":EXPECTED_SOURCE,
      "provider_run":35592153194,
      "provider_job":106308723087,
      "provider_artifact_id":10634743904,
      "provider_artifact_digest":EXPECTED_ARTIFACT_DIGEST,
      "fixture_sha256":EXPECTED_FIXTURE,
      "contract_sha256":EXPECTED_CONTRACT,
      "card_count":5,
      "threshold_class_counts":{"STATISTICAL":statistical,"PROJECT_GOVERNED":governed,"NONE":none,"GOVERNANCE_IDENTITY":1},
      "retained_first_reds":first_reds,
      "disposition":"ACCEPT_BOUNDED_PROJECT_MATH_WITH_EXPLICIT_DEFER",
      "next":"BD-260.6_OPTIONAL_FEDERATION_DISPOSITION",
      "authority_transfer":False,
      "formal_credit_delta":0,
      "engineering_acceptance":False,
      "qps_threshold_authority":False,
      "status":"PASS_TRIAGE_VERIFICATION"
    }
    OUT.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print("PASS_LM10_W260_BD260_5_TRIAGE")

if __name__=="__main__":
    main()
