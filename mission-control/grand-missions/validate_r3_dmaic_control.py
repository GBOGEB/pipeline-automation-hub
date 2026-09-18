#!/usr/bin/env python3
from __future__ import annotations
import argparse,copy,json
from pathlib import Path

EXPECTED_THREE_PR={
 "pr":260,"head":"04a78a9d5b81cbbf8b915810c7f2d9bd908ed7ad",
 "merge":"9bee27a1ef6a6fa9fed30c82d73fd931cf21b58b",
 "workflow_run":35359020674,"artifact_id":10553826137,
 "artifact_digest":"sha256:59345f42950a555754c3d47579fbff3b6f64f94586a47de632337e7da9a2582b",
 "result":"PASS_3PR_REFRESH_PROBE_RANK"
}
EXPECTED_MIP_M={
 "pr":1494,"head":"4cf5dd60980ff9eef45d542fb0a2f1afd25b1c20",
 "merge":"2571a520e2d765cf4089a8cd375ca3dd290def58",
 "consumer_receipt_blob":"ad02b2ac0dadf84c7ac4d44d55a64f77cefe00cb",
 "consumer_validator_blob":"79e82e4a5b3e5c176aa76998f681e9ccef5222d9",
 "exact_env_validator_blob":"a683201464240ec48d927225e6a52e284b7077cf",
 "private_runtime_proof":"WITHHELD_INFRA_PREEXECUTION_NONCOMPENSATING",
 "result":"PASS_MERGED_SOURCE_CONTROL_FIX"
}
EXPECTED_IDS=[
 "QPS_EXACT_ENV_VALIDATOR_SCHEMA_DRIFT","MC_PROTECTED_RECEIPT_SCHEMA_BINDING_DRIFT",
 "MC_PRODUCER_READINESS_UNVALIDATED","MC_PHYSICAL_ABSENCE_UNVALIDATED",
 "QPS_DMAIC_CONSUMER_FAIL_OPEN"
]
EXPECTED_GUARDS={"issue_923":"RED_OWNER_ACTION","gt_bdq_0":"RED_BLOCKED_ON_923_INFRA_PREEXECUTION","runtime_gold":"WITHHELD","canonical_gt_credit":"NONE","authority_transfer":False,"formal_credit_delta":0}
EXPECTED_RULES={"remeasure_first_pass_after_new_primary_prs":4,"immediate_red_if_preventive_coverage_below":1.0,"immediate_red_if_false_accepts_above":0,"historical_predictions_immutable":True,"unknown_is_not_zero":True}
def fail(m): raise SystemExit("R3_DMAIC_CONTROL_FAIL: "+m)
def validate(d):
  k=d["kpi"]; r=d["ranked_defects"]; c=d["current_r3"]; t=d["three_pc"]; p3=d["tooling_3p3"]
  checks={
   "schema":d.get("schema")=="missioncontrol.hm01.r3.dmaic_control.v3" and d.get("wave")=="W285",
   "authority":d.get("authority_transfer") is False and d.get("formal_credit_delta")==0,
   "three_pr_exact":d["proofs"]["three_pr"]==EXPECTED_THREE_PR,
   "mip_m_exact":d["proofs"]["mip_modernize_qps"]==EXPECTED_MIP_M,
   "ranked_defects":r=={"total":5,"qps_modernize_closed":2,"missioncontrol_innovate_perpetuate_closed":3,"open_after_exact_head_public_proof":0,"ids":EXPECTED_IDS},
   "historical_kpi":k["historical_r3_first_pass_closure_rate"]==0.25 and k["historical_r3_mean_merge_lead_seconds"]==210 and k["historical_r3_median_merge_lead_seconds"]==169,
   "prevention_kpi":k["preventive_defect_class_coverage"]==1.0 and k["synthetic_fault_detection_rate"]==1.0 and k["false_accept_count"]==0,
   "closure_kpi":k["ranked_defect_closure_target"]==1.0 and k["protected_control_surface_coverage"]==1.0 and k["qps_propagated_kpi_validation_coverage"]==1.0 and k["qps_control_trigger_validation_coverage"]==1.0,
   "protected_surface_set":k["protected_control_surfaces"]==["EXACT_ENVIRONMENT_SCHEMA","SUCCESSOR_GIT_OBJECT_PRODUCER_READINESS","PHYSICAL_BUNDLE_ABSENCE"],
   "r3_current":c=={"active_successor":"1248290ca0a9d55ec83d0efa0235ed1a45a88eeb","capsule_schema":"gmi.r3_successor.exact_env_capsule.v2","producer_ready":True,"physical_bundle_returned":False,"first_red":"PHYSICAL_SUCCESSOR_GIT_BUNDLE_RETURN_1248290C","r3_release_production_dov":"WITHHELD","r4":"BLOCKED_NOT_NEXT"},
   "three_pc":t=={"Prepare":"PASS_EXACT_INPUTS_BOUND","Prove":"THIS_PR_EXACT_HEAD_PUBLIC_PREMERGE_AND_CONTROL_WORKFLOWS","Commit":"HOLD_WAIT_PROVE","no_credit_from_prepare":True},
   "tooling_3p3":p3=={"authorized_after_commit":True,"target":"GBOGEB/cryoplant-project","required_return":"QPS_R3_DMAIC_3P3_RETURN_RECEIPT_v1.yaml","r3_release_3p3_authorized":False},
   "rules":d["control_rules"]==EXPECTED_RULES,
   "guards":d["guards"]==EXPECTED_GUARDS,
  }
  if not all(checks.values()): fail(json.dumps({k:v for k,v in checks.items() if not v},sort_keys=True))
  return checks
def self_test(d):
  tests=[]
  x=copy.deepcopy(d); x["proofs"]["mip_modernize_qps"]["consumer_receipt_blob"]="0"*40; tests.append(x)
  x=copy.deepcopy(d); x["ranked_defects"]["open_after_exact_head_public_proof"]=1; tests.append(x)
  x=copy.deepcopy(d); x["current_r3"]["physical_bundle_returned"]=True; tests.append(x)
  x=copy.deepcopy(d); x["control_rules"]["remeasure_first_pass_after_new_primary_prs"]=5; tests.append(x)
  x=copy.deepcopy(d); x["guards"]["canonical_gt_credit"]="PASS"; tests.append(x)
  for x in tests:
    try: validate(x)
    except SystemExit: continue
    fail("self-test accepted protected mutation")
def main():
  ap=argparse.ArgumentParser(); ap.add_argument("--control",required=True); ap.add_argument("--out"); ap.add_argument("--self-test",action="store_true"); a=ap.parse_args()
  d=json.loads(Path(a.control).read_text()); checks=validate(d)
  if a.self_test: self_test(d)
  out={"schema":"missioncontrol.hm01.r3.dmaic_control_receipt.v3","status":"PASS_W285_MIP_INNOVATE_PERPETUATE_3PC_PROVE","checks":checks,"three_pc":{"Prepare":"PASS","Prove":"PASS_EXACT_HEAD","Commit":"AUTHORIZED_ON_MERGE"},"tooling_3p3_next":"QPS_RETURN_AFTER_COMMIT","authority_transfer":False,"formal_credit_delta":0}
  payload=json.dumps(out,indent=2,sort_keys=True)+"\n"
  if a.out: Path(a.out).write_text(payload)
  print(payload,end="")
if __name__=="__main__": main()
