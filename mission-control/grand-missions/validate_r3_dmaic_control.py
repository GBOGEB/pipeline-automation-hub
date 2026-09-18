#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, json
from pathlib import Path

EXPECTED_PROOFS = {
  "W277": {"pr":210,"head":"984b53641c0f8e1e820ba5986a263265ea1fcd1a","merge":"177ad762acd4e4d2170841b217858f1ca4e41923","workflow_run":35340769134,"artifact_id":10545076561,"artifact_digest":"sha256:33449d0d8d6aa911c7822a662bf8696104c10d280dcc63c7db71b13bd978c189","result":"PASS_MEASURED_KPI_CONTRACT","treatment":"HISTORICAL_MEASUREMENT_BASELINE"},
  "W278": {"pr":211,"head":"e0946574d788769e0bce8e178d1a15934c6436b3","merge":"ccdb95047eb34a0f0d82a82618299274eb675be0","workflow_run":35340904915,"job":105586336403,"artifact_id":10545017109,"artifact_digest":"sha256:b064d1fe23f20cc67c8180bd4b6f0517d77eb52bcf13acf5f08fc905fc27767f","result":"PASS_PREMERGE_INVARIANT_PROOF","treatment":"HISTORICAL_PROVISIONAL_SELF_CONTAINED_PROOF_SUPERSEDED_BY_W280_R1"},
  "W280_first_red": {"pr":214,"head":"42279f4567fe11f99b8c5f16d616b52167408eb4","merge":"90ca031754955be82ebf1b9936f1807e970d9736","workflow_run":35341618617,"job":105588574924,"result":"FAIL_CAPSULE_SCHEMA_IDENTITY","classification":"APPLICATION_CONTROL_VALIDATOR_CANONICAL_SCHEMA_EXPECTATION_DRIFT","treatment":"IMMUTABLE_FAILED_MEASURE_ANALYSE_EVIDENCE"},
  "W280_R1": {"pr":215,"head":"b8723101c2bd0559a8ef8e21aa5209e9303f1582","merge":"bd05fd5f1cb472a8ea9175aa6bbeb474faa2057d","workflow_run":35341881590,"job":105589407653,"artifact_id":10544798850,"artifact_digest":"sha256:30ee06aa8134b78743f816e4d244d742d65595f745ded74194e198ca8f2a3eda","result":"PASS_PREMERGE_INVARIANT_AND_PROTECTED_CONTROL_PROOF","codex_review":"COMPLETED_NO_NEW_FINDINGS_OBSERVED","treatment":"CURRENT_PREVENTION_PROOF"}
}
EXPECTED_HIST={"pr_population":8,"mean_merge_lead_seconds":210,"median_merge_lead_seconds":169,"primary_pr_count":4,"primary_prs_requiring_recursive_repair":3,"first_pass_closure_rate":0.25,"defect_repair_closure_yield":1.0,"physical_r3_prerequisites_open":2,"exact_environment_capsule_admitted":0,"first_red_cardinality":2}
EXPECTED_OUTCOME={"physical_r3_prerequisites_open":1,"exact_environment_capsule_admitted":1,"first_red_cardinality":1,"original_recurrence_classes_encoded":5,"original_recurrence_synthetic_detection_rate":1.0,"false_accept_count":0,"protected_control_surfaces_validated":3,"protected_control_surfaces_total":3,"successor_git_object_producer_ready":1,"physical_successor_bundle_returned":0,"first_red_id":"PHYSICAL_SUCCESSOR_GIT_BUNDLE_RETURN_1248290C","protected_current_w275_federation_version":4}
EXPECTED_PROCESS={"pr_population_through_w280_r1":5,"proof_workflow_first_pass_pass_count":4,"proof_workflow_first_pass_yield":0.8,"review_evaluated_pr_count":5,"review_clean_pr_count":1,"review_clean_rate":0.2,"material_review_findings_observed_before_w281":10,"material_review_findings_closed_before_w281":6,"material_review_findings_target_after_w281":10,"review_finding_closure_yield_before_w281":0.6,"review_finding_closure_yield_target_after_w281":1.0,"qps_propagation_review_findings_open":2}
EXPECTED_LAGGING={"first_pass_closure_rate":{"current_historical":0.25,"status":"LEARNING_NOT_REWRITTEN","next_evaluation_after_new_primary_prs":4,"target":0.75},"mean_merge_lead_seconds":{"historical":210,"status":"BASELINE_NOT_YET_CONTROLLED","target_max":210},"median_merge_lead_seconds":{"historical":169,"status":"BASELINE_NOT_YET_CONTROLLED","target_max":169}}
EXPECTED_RULES={"immediate_red_if":["original_recurrence_synthetic_detection_rate < 1.0","false_accept_count > 0","protected_control_surfaces_validated != protected_control_surfaces_total","authority_transfer != false","formal_credit_delta != 0"],"lagging_remeasure_trigger":"AFTER_4_NEW_PRIMARY_CHANGE_PRS","qps_consumer_repair_required":True,"qps_consumer_repair_scope":"VALIDATE_ALL_PROPAGATED_KPIS_AND_ALL_REMEASUREMENT_TRIGGERS","no_probability_calibration_before_governed_model":True,"historical_predictions_immutable":True,"unknown_is_not_zero":True}
EXPECTED_TOOLING={"local_dov":"PASS_W280_R1_PROTECTED_CONTROL_PROOF","preserve":"PASS","propagate_target":"GBOGEB/cryoplant-project","propagate_required_receipt":"QPS_R3_DMAIC_CONTROL_CONSUMER_RECEIPT_v2.json","prove":"HOLD_WAIT_QPS_CONSUMER_FIX_FORWARD","r3_release_3p3_authorized":False}
EXPECTED_GUARDS={"r3_release_production_dov":"WITHHELD","r4":"BLOCKED_NOT_NEXT","issue_923":"RED_OWNER_ACTION","gt_bdq_0":"RED_BLOCKED_ON_923_INFRA_PREEXECUTION","canonical_gt_credit":"NONE"}

def fail(msg): raise SystemExit("R3_DMAIC_CONTROL_FAIL: "+msg)

def validate(d: dict) -> dict:
    checks={
      "schema":d.get("schema")=="missioncontrol.hm01.r3.dmaic_control.v2" and d.get("wave")=="W281",
      "authority":d.get("authority_transfer") is False and d.get("formal_credit_delta")==0,
      "proof_identities":d.get("parent_proofs")==EXPECTED_PROOFS,
      "historical_frozen":d["kpi"].get("historical_r3_slice")==EXPECTED_HIST,
      "outcome_frozen":d["kpi"].get("current_outcome")==EXPECTED_OUTCOME,
      "process_frozen":d["kpi"].get("dmaic_process")==EXPECTED_PROCESS,
      "lagging_not_rewritten":d["kpi"].get("lagging_kpis")==EXPECTED_LAGGING,
      "control_rules":d.get("control_rules")==EXPECTED_RULES,
      "tooling_3p3":d.get("tooling_3p3")==EXPECTED_TOOLING,
      "guards":d.get("guards")==EXPECTED_GUARDS,
    }
    if not all(checks.values()): fail(json.dumps({k:v for k,v in checks.items() if not v},sort_keys=True))
    return checks

def self_test(d: dict):
    mutations=[]
    x=copy.deepcopy(d); x["parent_proofs"]["W280_R1"]["artifact_id"]=0; mutations.append(("proof identity",x))
    x=copy.deepcopy(d); x["kpi"]["historical_r3_slice"]["mean_merge_lead_seconds"]=209; mutations.append(("historical KPI",x))
    x=copy.deepcopy(d); x["tooling_3p3"]["propagate_target"]="OTHER"; mutations.append(("propagation target",x))
    x=copy.deepcopy(d); x["guards"]["canonical_gt_credit"]="PASS"; mutations.append(("guard",x))
    x=copy.deepcopy(d); x["control_rules"]["lagging_remeasure_trigger"]="NEVER"; mutations.append(("trigger",x))
    for label,x in mutations:
        try: validate(x)
        except SystemExit: continue
        fail("self-test accepted "+label+" mutation")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--control",required=True); ap.add_argument("--out"); ap.add_argument("--self-test",action="store_true"); a=ap.parse_args()
    d=json.loads(Path(a.control).read_text())
    checks=validate(d)
    if a.self_test: self_test(d)
    receipt={"schema":"missioncontrol.hm01.r3.dmaic_control_receipt.v2","status":"PASS_W281_REBASELINED_DMAIC_CONTROL","checks":checks,"kpi":d["kpi"],"tooling_3p3":d["tooling_3p3"],"guards":d["guards"],"authority_transfer":False,"formal_credit_delta":0,"next":"QPS_W282_CONSUMER_FIX_FORWARD"}
    payload=json.dumps(receipt,indent=2,sort_keys=True)+"\n"
    if a.out: Path(a.out).write_text(payload)
    print(payload,end="")

if __name__=="__main__": main()
