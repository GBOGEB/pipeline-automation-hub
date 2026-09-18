#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def load(name):
    return json.loads((ROOT/name).read_text(encoding="utf-8"))

def add(checks,name,passed,detail):
    checks.append({"check":name,"result":"PASS" if passed else "FAIL","detail":detail})

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source-sha",required=True)
    ap.add_argument("--out",required=True)
    args=ap.parse_args()

    c=load("GM_V_GOVERNOR_READINESS_CONTRACT.json")
    r=load("GRAND_MISSION_REGISTRY.json")
    gm={m["id"]:m for m in r["grand_missions"]}
    gm4=gm["GM-IV"]; gm5=gm["GM-V"]; checks=[]

    active=c["prerequisites"]["gm_iv_active8"]
    add(checks,"01_gm_iv_active8_control",
        gm4.get("state")=="ACTIVE_8_OF_8" and gm4.get("activation_stage")=="ACTIVE_8_OF_8" and gm4.get("children")==[],
        {"state":gm4.get("state"),"stage":gm4.get("activation_stage"),"children":gm4.get("children")})
    ev=gm4.get("active_8_of_8_evidence",{})
    add(checks,"02_active8_readiness_evidence_retained",
        ev.get("source_sha")==active["readiness_head_sha"] and ev.get("workflow_run_id")==active["readiness_run_id"]
        and ev.get("artifact_id")==active["readiness_artifact_id"] and ev.get("artifact_digest")==active["readiness_artifact_digest"],
        ev)

    repeat=c["prerequisites"]["post_active8_repeat_control"]
    add(checks,"03_repeat_control_bound",
        repeat["result"]=="PASS_POST_ACTIVE8_REPEAT_CONTROL" and len(repeat["merge_sha"])==40 and len(repeat["exact_head_sha"])==40
        and repeat["run_id"]>0 and repeat["artifact_id"]>0 and repeat["artifact_digest"].startswith("sha256:"),
        repeat)

    cap=c["prerequisites"]["runtime_capability_capacity"]
    cap_ok=(
        cap["result"]=="PASS_RUNTIME_PROVEN_CAPABILITY_CAPACITY"
        and cap["required_capability_count"]==8 and cap["runtime_proven_capability_count"]==8
        and cap["runtime_proven_ratio"]==1.0 and cap["distinct_predeclared_hosts"]==8
        and cap["measurement_scope"]=="CAPABILITY_COVERAGE_NOT_CONCURRENCY_CAPACITY"
        and cap["concurrency_capacity_claimed"] is False
    )
    add(checks,"04_runtime_capability_capacity_exact",cap_ok,cap)

    op=c["prerequisites"]["operational_availability"]
    external_hold=(
        op["current_result"]=="WITHHOLD_EXTERNAL_NONCOMPENSATING_RUNNER_ADMISSION"
        and op["blocking_surface"]=="GBOGEB/cryoplant-project#923"
        and op["compensation_allowed"] is False
        and op["latest_exact_head_observation"]["validator_steps_executed"]==0
        and all(x["steps_executed"]==0 for x in op["latest_exact_head_observation"]["release_runner_probe_jobs"])
    )
    add(checks,"05_external_operational_availability_observation_bound",external_hold,op)

    add(checks,"06_gm_v_still_held",
        gm5.get("state")=="HELD" and gm5.get("children")==[] and gm5.get("crew_posture")=="UNALLOCATED",
        {"state":gm5.get("state"),"children":gm5.get("children"),"crew_posture":gm5.get("crew_posture")})
    add(checks,"07_no_authority_or_child_binding",
        c["authority_transfer"] is False and c["children_bound"] is False and r.get("authority_transfer") is False,
        {"contract_authority_transfer":c["authority_transfer"],"fleet_authority_transfer":r.get("authority_transfer")})

    structural_pass=all(x["result"]=="PASS" for x in checks)
    operational_ready=(op["current_result"]==op["required_result"])
    decision=c["decision_semantics"]["READY"] if structural_pass and operational_ready else c["decision_semantics"]["WITHHOLD"]
    result="READY" if structural_pass and operational_ready else "WITHHOLD" if structural_pass else "FAIL"
    receipt={
      "schema":"qps.gm_v_governor_readiness_receipt.v1",
      "wave":c["wave"],
      "source_sha":args.source_sha,
      "result":result,
      "decision":decision,
      "checks":checks,
      "gm_iv_state":gm4.get("state"),
      "gm_v_state":gm5.get("state"),
      "gm_v_launch_authorized":bool(structural_pass and operational_ready),
      "children_bound":False,
      "authority_transfer":False,
      "runtime_capacity_class":"RUNTIME_PROVEN",
      "operational_availability":op["current_result"],
      "reentry_trigger":op["reentry_trigger"],
      "boundary":c["readiness_boundary"]
    }
    Path(args.out).write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(receipt,indent=2,sort_keys=True))
    if not structural_pass:
        raise SystemExit(1)

if __name__=="__main__":
    main()
