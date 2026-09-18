#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, json, re
from pathlib import Path

ACTIVE="1248290ca0a9d55ec83d0efa0235ed1a45a88eeb"
PREDECESSOR="70964e5f1577231512f4104b26f5f6649ad8cb39"
CANONICAL_SCHEMA="gmi.r3_successor.exact_env_capsule.v2"
FAULTS=[
 "DAG_DOV_NODE_IDENTITY","CAPSULE_SCHEMA_IDENTITY",
 "PRODUCER_AMBIENT_LD_LIBRARY_PATH","CONSUMER_AMBIENT_LD_LIBRARY_PATH",
 "PREDECESSOR_PROMOTED_AS_CURRENT",
]

def validate(doc):
    errs=[]; c=doc["canonical"]
    if c.get("active_source")!=ACTIVE or c.get("historical_predecessor")!=PREDECESSOR or c.get("active_source")==c.get("historical_predecessor"):
        errs.append("PREDECESSOR_PROMOTED_AS_CURRENT")
    if c["r3_dov_node"]["producer"]!=c["r3_dov_node"]["consumer"]:
        errs.append("DAG_DOV_NODE_IDENTITY")
    if set(c["capsule_schema"].values())!={CANONICAL_SCHEMA}:
        errs.append("CAPSULE_SCHEMA_IDENTITY")
    iso=c["clean_environment_isolation"]
    if not iso["producer_relocated_self_test_unsets_ld_library_path"] or not iso["standalone_validator_unsets_ld_library_path"]:
        errs.append("PRODUCER_AMBIENT_LD_LIBRARY_PATH")
    if not iso["qps_consumer_admission_unsets_ld_library_path"]:
        errs.append("CONSUMER_AMBIENT_LD_LIBRARY_PATH")
    src=c["source_authority"]
    if src["current_production_target"]!="ACTIVE_SOURCE_ONLY" or src["predecessor_role"]!="HISTORICAL_PROVENANCE_ONLY" or src["predecessor_relabel_allowed"]:
        if "PREDECESSOR_PROMOTED_AS_CURRENT" not in errs: errs.append("PREDECESSOR_PROMOTED_AS_CURRENT")
    if len(doc["fault_classes"])!=len(set(doc["fault_classes"])) or set(doc["fault_classes"])!=set(FAULTS):
        errs.append("FAULT_CLASS_SET_DRIFT")
    gates=c["gates"]
    if gates["r3_release_production_dov"]!="WITHHELD" or gates["r3_3p3_authorized"] is not False or gates["r4"]!="BLOCKED_NOT_NEXT":
        errs.append("GATE_OR_AUTHORITY_OVERCLAIM")
    if doc.get("authority_transfer") is not False or doc.get("formal_credit_delta")!=0:
        errs.append("AUTHORITY_OR_CREDIT_DRIFT")
    return errs

def latest_w275_receipt(root):
    base=root/"mission-control/qps-triage-ultra/missions/receipts"
    rows=[]; rx=re.compile(r"HM01_R3_W275_3PSTAR_MIP_FEDERATION_20260918_v(\d+)\.yaml$")
    for p in base.glob("HM01_R3_W275_3PSTAR_MIP_FEDERATION_20260918_v*.yaml"):
        m=rx.match(p.name)
        if m: rows.append((int(m.group(1)),p))
    if not rows: raise SystemExit("R3_DMAIC_PREMERGE_FAIL: no W275 federation receipt")
    return max(rows)[1]

def top_section(text,name):
    lines=text.splitlines(); target=name+":"
    for i,line in enumerate(lines):
        if line==target:
            out=[]
            for row in lines[i+1:]:
                if row and not row.startswith((" ","\t")): break
                out.append(row)
            return out
    return []

def section_has_scalar(lines,indent,key,value):
    prefix=" "*indent+key+":"
    return any(line.startswith(prefix) and line[len(prefix):].strip()==value for line in lines)

def validate_actual_controls(root):
    errs=[]
    control=(root/"mission-control/grand-missions/GM_I_C_R3_SUCCESSOR_3PSTAR_MIP_CONTROL_v1.yaml").read_text()
    ingress=(root/"mission-control/grand-missions/GM_I_C_R3_SUCCESSOR_INGRESS_MANIFEST_v2.yaml").read_text()
    receipt_path=latest_w275_receipt(root); receipt=receipt_path.read_text()
    required_control=[
      f"active_r3_production_source: {ACTIVE}",f"predecessor_source: {PREDECESSOR}",
      "R3_SUCCESSOR_EXACT_ENVIRONMENT_REPROOF -> PASS_R3_RELEASE_PRODUCTION_DOV",
      "PASS_R3_RELEASE_PRODUCTION_DOV -> R4_FRESH_CLONE_COLD_START_REGENERATION_AND_PARITY",
    ]
    if any(x not in control for x in required_control) or "PASS_R3_RELEASE_PRODUCTION_DOV_EVALUATION" in control:
        errs.append("DAG_DOV_NODE_IDENTITY")
    three_p3=top_section(control,"three_p3")
    if not section_has_scalar(three_p3,2,"authorized","false"): errs.append("GATE_OR_AUTHORITY_OVERCLAIM")
    required_ingress=[
      f"historical_predecessor: {PREDECESSOR}",f"active_production_successor: {ACTIVE}",
      "preferred_filename: QPS_R3_1248290c.bundle",f"must_contain_commit: {ACTIVE}",
    ]
    if any(x not in ingress for x in required_ingress): errs.append("PREDECESSOR_PROMOTED_AS_CURRENT")

    current=top_section(receipt,"current_qps_restart")
    exact_env=top_section(receipt,"exact_environment")
    producer=top_section(receipt,"successor_git_object_producer")
    physical=top_section(receipt,"physical_return")
    pstar=top_section(receipt,"three_pstar")
    if receipt_path.name!="HM01_R3_W275_3PSTAR_MIP_FEDERATION_20260918_v5.yaml":
        errs.append("PROTECTED_CURRENT_W275_VERSION_DRIFT")
    if not section_has_scalar(current,2,"active_successor",ACTIVE) or not section_has_scalar(current,2,"first_red","PHYSICAL_SUCCESSOR_GIT_BUNDLE_RETURN_1248290C"):
        errs.append("PROTECTED_CONTROL_DERIVATION_DRIFT")
    if not section_has_scalar(exact_env,2,"manifest",CANONICAL_SCHEMA):
        errs.append("CAPSULE_SCHEMA_IDENTITY")
    if not section_has_scalar(producer,2,"state","PASS_MERGED"):
        errs.append("PRODUCER_READINESS_DRIFT")
    if not section_has_scalar(physical,2,"state","WAIT_RETURN") or not section_has_scalar(physical,2,"first_red","PHYSICAL_SUCCESSOR_GIT_BUNDLE_RETURN_1248290C") or not section_has_scalar(physical,4,"qualifying_bundle_found","false"):
        errs.append("PHYSICAL_RETURN_STATE_DRIFT")
    if not section_has_scalar(pstar,2,"three_p3_authorized","false") or not section_has_scalar(pstar,2,"r4","BLOCKED_NOT_NEXT"):
        errs.append("GATE_OR_AUTHORITY_OVERCLAIM")
    return sorted(set(errs))

def inject(doc,fault):
    d=copy.deepcopy(doc); c=d["canonical"]
    if fault=="DAG_DOV_NODE_IDENTITY": c["r3_dov_node"]["producer"]="PASS_R3_RELEASE_PRODUCTION_DOV_EVALUATION"
    elif fault=="CAPSULE_SCHEMA_IDENTITY": c["capsule_schema"]["qps_consumer"]="gmi.r3.successor.exact_env_capsule.v2"
    elif fault=="PRODUCER_AMBIENT_LD_LIBRARY_PATH": c["clean_environment_isolation"]["standalone_validator_unsets_ld_library_path"]=False
    elif fault=="CONSUMER_AMBIENT_LD_LIBRARY_PATH": c["clean_environment_isolation"]["qps_consumer_admission_unsets_ld_library_path"]=False
    elif fault=="PREDECESSOR_PROMOTED_AS_CURRENT": c["active_source"]=PREDECESSOR
    else: raise ValueError(fault)
    return d

def proof(doc,root):
    base_errors=validate(doc)+validate_actual_controls(root)
    if base_errors: raise SystemExit("R3_DMAIC_PREMERGE_FAIL: canonical/protected contract invalid: "+",".join(sorted(set(base_errors))))
    detected=[]; false_accept=[]
    for fault in FAULTS:
        errs=validate(inject(doc,fault))
        (detected if fault in errs else false_accept).append(fault)
    kpi={"observed_recurrence_classes":len(FAULTS),"preventive_classes_encoded":len(set(doc["fault_classes"])),"preventive_defect_class_coverage":len(set(doc["fault_classes"]))/len(FAULTS),"synthetic_faults_injected":len(FAULTS),"synthetic_faults_detected":len(detected),"synthetic_fault_detection_rate":len(detected)/len(FAULTS),"false_accept_count":len(false_accept)}
    if kpi!=doc["expected_kpis"]: raise SystemExit(f"R3_DMAIC_PREMERGE_FAIL: KPI mismatch expected={doc['expected_kpis']} got={kpi}")
    return {"schema":"missioncontrol.hm01.r3.premerge_invariant_receipt.v3","status":"PASS_W285_PREMERGE_AND_PROTECTED_CONTROL_PROOF","detected_fault_classes":detected,"false_accepts":false_accept,"protected_control_validation":"PASS_V5","kpi":kpi,"r3_release_authority_changed":False,"authority_transfer":False,"formal_credit_delta":0,"next":"W285_3PC_COMMIT_THEN_TOOLING_3P3_RETURN"}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--contract",required=True); ap.add_argument("--repo-root",default="."); ap.add_argument("--out"); a=ap.parse_args()
    doc=json.loads(Path(a.contract).read_text()); receipt=proof(doc,Path(a.repo_root).resolve())
    payload=json.dumps(receipt,indent=2,sort_keys=True)+"\n"
    if a.out: Path(a.out).write_text(payload)
    print(payload,end="")
if __name__=="__main__": main()
