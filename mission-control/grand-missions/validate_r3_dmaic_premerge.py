#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, json
from pathlib import Path

FAULTS = [
    "DAG_DOV_NODE_IDENTITY",
    "CAPSULE_SCHEMA_IDENTITY",
    "PRODUCER_AMBIENT_LD_LIBRARY_PATH",
    "CONSUMER_AMBIENT_LD_LIBRARY_PATH",
    "PREDECESSOR_PROMOTED_AS_CURRENT",
]

def validate(doc: dict) -> list[str]:
    errs=[]
    c=doc["canonical"]
    if c["r3_dov_node"]["producer"] != c["r3_dov_node"]["consumer"]:
        errs.append("DAG_DOV_NODE_IDENTITY")
    schemas=set(c["capsule_schema"].values())
    if schemas != {"gmi.r3_successor.exact_env_capsule.v2"}:
        errs.append("CAPSULE_SCHEMA_IDENTITY")
    iso=c["clean_environment_isolation"]
    if not iso["producer_relocated_self_test_unsets_ld_library_path"] or not iso["standalone_validator_unsets_ld_library_path"]:
        errs.append("PRODUCER_AMBIENT_LD_LIBRARY_PATH")
    if not iso["qps_consumer_admission_unsets_ld_library_path"]:
        errs.append("CONSUMER_AMBIENT_LD_LIBRARY_PATH")
    src=c["source_authority"]
    if src["current_production_target"] != "ACTIVE_SOURCE_ONLY" or src["predecessor_role"] != "HISTORICAL_PROVENANCE_ONLY" or src["predecessor_relabel_allowed"]:
        errs.append("PREDECESSOR_PROMOTED_AS_CURRENT")
    gates=c["gates"]
    if gates["r3_release_production_dov"]!="WITHHELD" or gates["r3_3p3_authorized"] is not False or gates["r4"]!="BLOCKED_NOT_NEXT":
        errs.append("GATE_OR_AUTHORITY_OVERCLAIM")
    if doc.get("authority_transfer") is not False or doc.get("formal_credit_delta") != 0:
        errs.append("AUTHORITY_OR_CREDIT_DRIFT")
    return errs

def inject(doc: dict, fault: str) -> dict:
    d=copy.deepcopy(doc); c=d["canonical"]
    if fault=="DAG_DOV_NODE_IDENTITY":
        c["r3_dov_node"]["producer"]="PASS_R3_RELEASE_PRODUCTION_DOV_EVALUATION"
    elif fault=="CAPSULE_SCHEMA_IDENTITY":
        c["capsule_schema"]["qps_consumer"]="gmi.r3.successor.exact_env_capsule.v2"
    elif fault=="PRODUCER_AMBIENT_LD_LIBRARY_PATH":
        c["clean_environment_isolation"]["standalone_validator_unsets_ld_library_path"]=False
    elif fault=="CONSUMER_AMBIENT_LD_LIBRARY_PATH":
        c["clean_environment_isolation"]["qps_consumer_admission_unsets_ld_library_path"]=False
    elif fault=="PREDECESSOR_PROMOTED_AS_CURRENT":
        c["source_authority"]["predecessor_relabel_allowed"]=True
    else:
        raise ValueError(fault)
    return d

def proof(doc: dict) -> dict:
    base_errors=validate(doc)
    if base_errors:
        raise SystemExit("R3_DMAIC_PREMERGE_FAIL: canonical contract invalid: "+",".join(base_errors))
    detected=[]
    false_accept=[]
    for fault in FAULTS:
        errs=validate(inject(doc,fault))
        if fault in errs:
            detected.append(fault)
        else:
            false_accept.append(fault)
    kpi={
        "observed_recurrence_classes":len(FAULTS),
        "preventive_classes_encoded":len(doc["fault_classes"]),
        "preventive_defect_class_coverage":len(doc["fault_classes"])/len(FAULTS),
        "synthetic_faults_injected":len(FAULTS),
        "synthetic_faults_detected":len(detected),
        "synthetic_fault_detection_rate":len(detected)/len(FAULTS),
        "false_accept_count":len(false_accept),
    }
    if kpi != doc["expected_kpis"]:
        raise SystemExit(f"R3_DMAIC_PREMERGE_FAIL: KPI mismatch expected={doc['expected_kpis']} got={kpi}")
    return {
        "schema":"missioncontrol.hm01.r3.premerge_invariant_receipt.v1",
        "status":"PASS_PREMERGE_INVARIANT_PROOF",
        "detected_fault_classes":detected,
        "false_accepts":false_accept,
        "kpi":kpi,
        "r3_release_authority_changed":False,
        "authority_transfer":False,
        "formal_credit_delta":0,
        "next":"W279_MIP_P_TOOLING_CONTROL_AND_ONE_QPS_PROPAGATION",
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--contract",required=True)
    ap.add_argument("--out")
    a=ap.parse_args()
    doc=json.loads(Path(a.contract).read_text())
    receipt=proof(doc)
    payload=json.dumps(receipt,indent=2,sort_keys=True)+"\n"
    if a.out: Path(a.out).write_text(payload)
    print(payload,end="")

if __name__=="__main__":
    main()
