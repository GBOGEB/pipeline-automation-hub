#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parent
REGISTRY = ROOT / "GRAND_MISSION_REGISTRY.json"
CAPACITY = ROOT / "GM_FLEET_03_CAPACITY_CONTRACT.json"
ECONOMICS = ROOT / "GM_IV_EVIDENCE_ECONOMICS.json"

def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def add(checks, name, passed, detail):
    checks.append({"check": name, "result": "PASS" if passed else "FAIL", "detail": detail})

def load_fleet():
    p=ROOT/"validate_gm_fleet.py"
    s=importlib.util.spec_from_file_location("fleet",p)
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
    return m

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--contract", required=True)
    ap.add_argument("--source-sha", required=True)
    ap.add_argument("--probe-root", required=True)
    ap.add_argument("--out", required=True)
    args=ap.parse_args()
    contract=load(args.contract); registry=load(REGISTRY); capacity=load(CAPACITY); economics=load(ECONOMICS)
    gm={m["id"]:m for m in registry["grand_missions"]}; gm4=gm["GM-IV"]; gm5=gm["GM-V"]
    fleet=load_fleet(); checks=[]
    mode="READINESS" if gm4.get("state")=="STAGED_ACTIVE_RECON_4_OF_8" else "CONTROL" if gm4.get("state")=="ACTIVE_8_OF_8" else "UNSUPPORTED"

    if mode=="READINESS":
        expected=contract["current_control_shape"]
        ok=(gm4.get("activation_stage")==expected["activation_stage"] and gm4.get("candidate_frontiers")==expected["candidate_frontiers"]
            and gm4.get("controlled_pilot_frontiers")==expected["controlled_pilot_frontiers"] and gm4.get("reference_frontiers")==expected["reference_frontiers"]
            and gm4.get("unfilled_frontier_slots")==expected["unfilled_frontier_slots"] and gm4.get("children")==[])
    elif mode=="CONTROL":
        expected=contract["proposed_eight_frontier_shape"]
        ok=(gm4.get("activation_stage")=="ACTIVE_8_OF_8" and gm4.get("candidate_frontiers")==expected["candidate_frontiers"]
            and gm4.get("controlled_pilot_frontiers")==expected["controlled_pilot_frontiers_retained"]
            and gm4.get("reference_frontiers")==expected["reference_frontiers_retained"]
            and gm4.get("new_candidate_recon_frontiers")==expected["new_candidate_recon_frontiers"]
            and gm4.get("unfilled_frontier_slots")==[] and gm4.get("children")==[])
    else: ok=False
    add(checks,"01_stage_aware_current_shape",ok,{"mode":mode,"state":gm4.get("state")})

    stage=next((x for x in capacity["stage_model"] if x["stage"]=="ACTIVE_8_OF_8"),None)
    add(checks,"02_capacity_contract_active8",bool(stage) and stage.get("maximum_bound_frontiers")==8 and stage.get("authority_transfer") is False,stage)

    evidence=contract["frontier_evidence"]; ids=list(evidence); repos=[evidence[x]["repository"] for x in ids]; shas=[evidence[x]["target_sha"] for x in ids]
    add(checks,"03_eight_unique_frontier_ids",ids==[f"GM-IV-F{i:02d}" for i in range(1,9)],ids)
    add(checks,"04_eight_unique_repositories",len(repos)==8 and len(set(repos))==8,repos)
    add(checks,"05_eight_target_shas",all(isinstance(x,str) and len(x)==40 for x in shas),shas)
    add(checks,"06_pilot_evidence_retained",gm4["pilot_2_of_8_evidence"]["F01"]["target_sha"]==evidence["GM-IV-F01"]["target_sha"] and gm4["pilot_2_of_8_evidence"]["F03"]["target_sha"]==evidence["GM-IV-F03"]["target_sha"],gm4["pilot_2_of_8_evidence"])
    add(checks,"07_recon4_evidence_retained",gm4.get("recon_4_of_8_evidence",{}).get("decision")=="READY_FOR_SEPARATE_RECON_4_PROMOTION_PR",gm4.get("recon_4_of_8_evidence"))

    probe_root=Path(args.probe_root); rows=[]; probe_ok=True
    for fid in ["GM-IV-F05","GM-IV-F06","GM-IV-F07","GM-IV-F08"]:
        p=probe_root/fid; observed=(p/"HEAD_SHA").read_text().strip() if (p/"HEAD_SHA").exists() else "MISSING"; count=int((p/"ENTRY_COUNT").read_text().strip()) if (p/"ENTRY_COUNT").exists() else 0
        row_ok=observed==evidence[fid]["target_sha"] and count>0; probe_ok &= row_ok
        rows.append({"frontier":fid,"observed_sha":observed,"entry_count":count,"result":"PASS" if row_ok else "FAIL"})
    add(checks,"08_f05_f08_exact_sha_gt0_probes",probe_ok,rows)

    econ_stage="RECON_4_OF_8" if mode=="READINESS" else "ACTIVE_8_OF_8"
    add(checks,"09_economics_stage_control",economics["fleet_invariant"]["mission_stage"]==econ_stage and economics["fleet_invariant"]["canonical_children_bound"]==0 and economics["pca_gate"]["state"]=="DEFER" and economics["bt_gate"]["state"]=="DEFER",{"expected_stage":econ_stage,"actual_stage":economics["fleet_invariant"]["mission_stage"]})
    add(checks,"10_no_authority_or_child_binding",contract["authority_transfer"] is False and contract["children_bound"] is False and gm4.get("children")==[],gm4.get("children"))
    add(checks,"11_gm_v_held",gm5.get("state")=="HELD" and gm5.get("children")==[],gm5.get("state"))

    if mode=="READINESS":
        probe=dict(gm4); probe["state"]="ACTIVE_8_OF_8"; probe["activation_stage"]="ACTIVE_8_OF_8"; probe["candidate_frontiers"]=[f"GM-IV-F{i:02d}" for i in range(1,9)]; probe["new_candidate_recon_frontiers"]=[f"GM-IV-F{i:02d}" for i in range(5,9)]; probe["unfilled_frontier_slots"]=[]
        validator_ok=not fleet.gm_iv_supported_shape(probe)
        add(checks,"12_readiness_fail_closed_before_promotion",validator_ok,"REJECTED" if validator_ok else "ACCEPTED")
    elif mode=="CONTROL":
        accepted=contract["accepted_readiness_evidence"]; actual=gm4.get("active_8_of_8_evidence",{})
        evidence_ok=all(actual.get(k)==v for k,v in accepted.items() if k!="evaluated_head_sha") and gm4.get("active8_readiness",{}).get("evaluated_head_sha")==accepted["evaluated_head_sha"]
        add(checks,"12_historical_readiness_exactly_retained",evidence_ok,actual)
        add(checks,"13_current_active8_validator_accepts",fleet.gm_iv_supported_shape(gm4),"ACCEPTED" if fleet.gm_iv_supported_shape(gm4) else "REJECTED")
    else:
        add(checks,"12_unsupported_stage",False,gm4.get("state"))

    passed=all(c["result"]=="PASS" for c in checks)
    if mode=="READINESS": decision=contract["decision_semantics"]["READY"] if passed else contract["decision_semantics"]["WITHHOLD"]
    elif mode=="CONTROL": decision=contract["decision_semantics"]["CONTROL"] if passed else contract["decision_semantics"]["WITHHOLD"]
    else: decision=contract["decision_semantics"]["WITHHOLD"]
    receipt={"schema":"qps.gm_iv_active8_governor_receipt.v2","wave":contract["wave"],"source_sha":args.source_sha,"mode":mode,"result":"PASS" if passed else "FAIL","decision":decision,"checks":checks,"children_bound":False,"authority_transfer":False,"canonical_state_after_gate":gm4.get("state"),"gm_v_state":gm5.get("state")}
    Path(args.out).write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(receipt,indent=2,sort_keys=True))
    if not passed: raise SystemExit(1)

if __name__=="__main__": main()
