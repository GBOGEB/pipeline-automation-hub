#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path

def fail(msg): raise SystemExit("R3_DMAIC_CONTROL_FAIL: "+msg)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--control",required=True)
    ap.add_argument("--out")
    a=ap.parse_args()
    d=json.loads(Path(a.control).read_text())
    k=d["kpi"]; obs=k["observed_after_W278"]; hist=k["historical"]; delta=k["delta"]
    checks={
      "authority": d["authority_transfer"] is False and d["formal_credit_delta"]==0,
      "w277_bound": d["parent_proofs"]["W277"]["result"]=="PASS_MEASURED_KPI_CONTRACT",
      "w278_bound": d["parent_proofs"]["W278"]["result"]=="PASS_PREMERGE_INVARIANT_PROOF",
      "preventive_coverage": obs["preventive_defect_class_coverage"]==1.0,
      "synthetic_detection": obs["synthetic_fault_detection_rate"]==1.0,
      "false_accepts": obs["false_accept_count"]==0,
      "workflow_first_pass": obs["improvement_workflow_first_pass_yield"]==1.0 and obs["improvement_workflow_population"]==2,
      "physical_prereq_delta": hist["physical_r3_prerequisites_open"] + delta["physical_r3_prerequisites_open"] == obs["physical_r3_prerequisites_open"],
      "exact_env_delta": hist["exact_environment_capsule_admitted"] + delta["exact_environment_capsule_admitted"] == obs["exact_environment_capsule_admitted"],
      "first_red_delta": hist["first_red_cardinality"] + delta["first_red_cardinality"] == obs["first_red_cardinality"],
      "lagging_fpy_not_rewritten": k["lagging_kpis"]["first_pass_closure_rate"]["current_historical"]==0.25 and k["lagging_kpis"]["first_pass_closure_rate"]["status"]=="LEARNING_NOT_REWRITTEN",
      "r3_3p3_not_promoted": d["tooling_3p3"]["r3_release_3p3_authorized"] is False,
      "r3_gate_held": d["guards"]["r3_release_production_dov"]=="WITHHELD" and d["guards"]["r4"]=="BLOCKED_NOT_NEXT",
    }
    if not all(checks.values()):
        fail(json.dumps({k:v for k,v in checks.items() if not v},sort_keys=True))
    receipt={
      "schema":"missioncontrol.hm01.r3.dmaic_control_receipt.v1",
      "status":"PASS_DMAIC_TOOLING_CONTROL_READY_FOR_ONE_PROPAGATION",
      "checks":checks,
      "kpi":k,
      "tooling_3p3":d["tooling_3p3"],
      "guards":d["guards"],
      "authority_transfer":False,
      "formal_credit_delta":0,
      "next":"QPS_ONE_CONSUMER_PROPAGATION_PROOF"
    }
    payload=json.dumps(receipt,indent=2,sort_keys=True)+"\n"
    if a.out: Path(a.out).write_text(payload)
    print(payload,end="")

if __name__=="__main__": main()
