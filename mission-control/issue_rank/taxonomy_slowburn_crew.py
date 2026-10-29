#!/usr/bin/env python3
"""MissionControl/CREW branch-only N+1..N+12 slow-burn native proof runner.

Bounded repeat of DISJOINT test families on one exact PR SHA, reusing
the canonical REX ledger. The runner cannot merge, push, label, dispatch
new workflows, publish data, or certify root/engineering closure.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

SCHEMA="missioncontrol.crew.taxonomy-slowburn.v1"
SHA=re.compile(r"^[a-f0-9]{40}$",re.I)
MAX_WAVES=12
MAX_QUEUE=20
ROOT=Path(__file__).resolve().parents[2]
WD=ROOT/"mission-control"/"issue_rank"
REX=ROOT/"mission-control"/"qps-triage-ultra"/"crew"/"REX_LEARNING_LEDGER_v1.json"
LANES={
    "grammar":{"crew_role":"U02","command":["-m","unittest","-q","test_title_taxonomy"]},
    "rootrank":{"crew_role":"U07","command":["-m","unittest","-q","test_issue_rank"]},
    "privacy":{"crew_role":"S06","command":["-m","unittest","-q","test_taxonomy_pulse","test_taxonomy_explorer"]},
    "triway":{"crew_role":"S05","command":["-m","unittest","discover","-s","../qps-triage-ultra/issue-expedition",
        "-p","test_triway_burndown.py","-q"]},
}


def rex_preflight(path=REX):
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema")!="missioncontrol.crew.rex_learning_ledger.v1":
        raise ValueError("REX_SCHEMA_NOT_CURRENT")
    ids={x.get("rex_id") for x in data.get("entries",[]) if isinstance(x,dict)}
    needed={"REX-001","REX-002","REX-005","REX-006"}
    if not needed.issubset(ids):
        raise ValueError("REX_CONTROLS_MISSING")
    return sorted(needed)


def _native(cmd,wd,timeout):
    return subprocess.run(cmd,cwd=wd,text=True,capture_output=True,
                          timeout=timeout,check=False)


def run(*,lane,head,waves,queue_depth,budget_seconds=600,gap_seconds=5,
        runner=_native,sleep=time.sleep,clock=time.monotonic,rex_check=rex_preflight):
    if lane not in LANES:
        raise ValueError("CREW_LANE_UNKNOWN")
    if not isinstance(head,str) or not SHA.fullmatch(head):
        raise ValueError("EXACT_HEAD_MISSING")
    if type(waves) is not int or not 1<=waves<=MAX_WAVES:
        raise ValueError("WAVES_OUT_OF_BOUND")
    if type(queue_depth) is not int or queue_depth<0:
        raise ValueError("QUEUE_DEPTH_UNVERIFIED")
    if type(budget_seconds) is not int or not 1<=budget_seconds<=900:
        raise ValueError("BUDGET_OUT_OF_RANGE")
    if not isinstance(gap_seconds,(int,float)) or not 0<=gap_seconds<=30:
        raise ValueError("GAP_OUT_OF_RANGE")
    controls=rex_check()
    receipt={
        "schema":SCHEMA,"head_sha":head,"lane":lane,
        "crew_role":LANES[lane]["crew_role"],"rex_controls":controls,
        "waves_requested":waves,"waves_executed":0,
        "queue_depth_at_start":queue_depth,"queue_cap":MAX_QUEUE,
        "test_invocations":[],"status":None,"source_grade":"EXACT_HEAD_NATIVE_BRANCH_ONLY",
        "main_mutation":False,"merge_admission":"HOLD",
        "root_closure_credit":0,"formal_credit_delta":0,"authority_transfer":False}
    if queue_depth>MAX_QUEUE:
        receipt["status"]="BACKPRESSURE_HOLD_NO_TEST_PROOF"
    else:
        started=clock()
        for i in range(1,waves+1):
            elapsed=clock()-started
            remaining=budget_seconds-elapsed
            if remaining<30:
                receipt["status"]="BUDGET_EXHAUSTED_HOLD"
                break
            command=[sys.executable]+LANES[lane]["command"]
            t0=clock()
            try:
                p=runner(command,WD,max(1,min(remaining,90)))
                code=p.returncode
                out=(p.stdout or "")+"\n"+(p.stderr or "")
                output_sha=hashlib.sha256(out.encode("utf-8")).hexdigest()
            except subprocess.TimeoutExpired as exc:
                code=124
                output_sha=hashlib.sha256(str(exc).encode()).hexdigest()
            receipt["test_invocations"].append({
                "wave":i,"exit_code":code,
                "log_sha256":output_sha,"executed_steps":1,
                "elapsed_seconds":round(max(0,clock()-t0),3)})
            receipt["waves_executed"]+=1
            if code!=0:
                receipt["status"]="FIRST_RED_STOP"
                break
            if i<waves and gap_seconds:
                sleep(min(gap_seconds,max(0,budget_seconds-(clock()-started)-30)))
        if receipt["status"] is None:
            receipt["status"]="PASS_ALL_BOUNDED_WAVES"
    # A zero-wave backpressure receipt must never be mistaken for GREEN.
    receipt["terminal_native_proof"]=(receipt["status"]=="PASS_ALL_BOUNDED_WAVES"
                                     and receipt["waves_executed"]==waves
                                     and all(e["exit_code"]==0 and e["executed_steps"]>0
                                             for e in receipt["test_invocations"]))
    receipt["receipt_sha256"]=hashlib.sha256(json.dumps(
        receipt,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return receipt


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--lane",choices=sorted(LANES),required=True)
    p.add_argument("--head",required=True)
    p.add_argument("--waves",type=int,default=12)
    p.add_argument("--queue-depth",type=int,required=True)
    p.add_argument("--budget-seconds",type=int,default=600)
    p.add_argument("--gap-seconds",type=float,default=5)
    p.add_argument("--out",type=Path,required=True)
    opts=p.parse_args(argv)
    result=run(lane=opts.lane,head=opts.head,waves=opts.waves,
               queue_depth=opts.queue_depth,budget_seconds=opts.budget_seconds,
               gap_seconds=opts.gap_seconds)
    opts.out.parent.mkdir(parents=True,exist_ok=True)
    opts.out.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print("CREW_SLOWBURN",result["status"],"waves",result["waves_executed"],
          "receipt",result["receipt_sha256"])
    # A queued, budget-exhausted or RED run is NOT a successful CI proof.
    # Keep the receipt visible, but make the workflow terminal result non-green.
    return 0 if result["terminal_native_proof"] else 1


if __name__=="__main__":
    raise SystemExit(main())
