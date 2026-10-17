#!/usr/bin/env python3
"""CODE PURPLE N3_CONTINUE: bounded, source-bound 3PSTAR pulse ledger.

This is a deterministic, fail-closed continuation controller. It does not
dispatch GitHub Actions, run in the background, merge PRs, grant authority or
invent native evidence. A mission worker supplies authenticated observations.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

CHARTER="codepurple.n3.charter.v1"
OBS="codepurple.n3.native-observation.v1"
LEDGER="codepurple.n3.ledger.v1"
RETURN="codepurple.n3.return-receipt.v1"
STEPS=("P1_RECONCILE_MEASURE","P2_ENHANCE_PROVE","P3_STABILIZE_RECHECK")
WAVES=("SERIAL","PARALLEL_DISJOINT","HYBRID_DEPENDENCY_BARRIER")
SHA=re.compile(r"[0-9a-f]{40}\Z")
REPO=re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
IDENT=re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,79}\Z")
MAJOR=frozenset(("SECURITY_P0_P1","FAILED_REQUIRED_GATE","OWNER_LEASE_CONFLICT",
 "MISSING_NATIVE_EXACT_HEAD","RULESET_CHANGE_REQUIRED","QPS_OWNER_ACCEPTANCE",
 "UNRECOVERABLE_SCOPE_DRIFT","UNAUTHORIZED_MERGE"))
DECISIONS=frozenset(("CONTINUE","REPAIR_NEXT_PULSE","HOLD_MAJOR"))
SHA256=re.compile(r"[0-9a-f]{64}\Z")

def require(value,reason):
    if not value:
        raise ValueError(reason)

def encoded(obj):
    return (json.dumps(obj,sort_keys=True,indent=2,ensure_ascii=True)+"\n").encode("ascii")

def digest(obj):
    return hashlib.sha256(encoded(obj)).hexdigest()

def sha(value,label="exact source SHA"):
    require(isinstance(value,str) and SHA.fullmatch(value) and value != "0"*40,
            label+" missing or malformed")
    return value

def timestamp(value):
    require(isinstance(value,str) and value.endswith("Z"),"UTC Z timestamp required")
    try:
        d=datetime.fromisoformat(value[:-1]+"+00:00")
    except ValueError as e:
        raise ValueError("invalid UTC timestamp") from e
    require(d.utcoffset().total_seconds()==0,"timestamp not UTC")
    return d

def metric(m):
    require(type(m) is dict,"metric object required")
    require(isinstance(m.get("key"),str) and IDENT.fullmatch(m["key"]),"metric key invalid")
    require(isinstance(m.get("scope"),str) and m["scope"].strip(),"metric scope required")
    require(isinstance(m.get("instrument"),str) and m["instrument"].strip(),"metric instrument required")
    sha(m.get("production_blob"),"metric production blob")
    c,e=m.get("covered"),m.get("eligible")
    require(type(c) is int and type(e) is int and 0<=c<=e and e>0,
            "positive measured denominator and valid numerator required")
    return m

def overlap(a,b):
    a=a.rstrip("/");b=b.rstrip("/")
    return a==b or a.startswith(b+"/") or b.startswith(a+"/")

def charter(c):
    require(type(c) is dict and c.get("schema")==CHARTER,"wrong charter schema")
    require(c.get("invocation")=="N3_CONTINUE" and c.get("method")=="3PSTAR",
            "3PSTAR is distinct from 3PR/3PC/3WSTAR")
    require(c.get("execution_mode")=="BOUNDED_IN_TURN","background execution not authorized")
    require(isinstance(c.get("execution_id"),str) and IDENT.fullmatch(c["execution_id"]),
            "qualified execution id required")
    require(isinstance(c.get("mission_id"),str) and IDENT.fullmatch(c["mission_id"]),
            "mission id required")
    repo=c.get("repository")
    require(isinstance(repo,str) and REPO.fullmatch(repo),"fully qualified owner/repo required")
    base=c.get("baseline")
    require(type(base) is dict,"baseline missing")
    sha(base.get("source_sha"))
    timestamp(base.get("observed_utc"))
    metric(base.get("metric"))
    require(type(c.get("objective")) is dict,"objective missing")
    require(base["metric"]["key"]==c["objective"].get("metric_key"),
            "objective and baseline metric differ")
    require(c["objective"].get("direction") in ("INCREASE","DECREASE","STABILIZE"),
            "unknown improvement direction")
    policy=c.get("policy")
    require(type(policy) is dict,"execution policy missing")
    require(policy.get("pulse_count")==3 and type(policy.get("pulse_count")) is int,
            "N3 requires exactly three pulses")
    require(policy.get("wave_strategy") in WAVES,"unrecognized wave strategy")
    workers=policy.get("max_disjoint_workers")
    require(type(workers) is int and 1<=workers<=4,"worker limit must be 1..4")
    retries=policy.get("max_attempts_per_pulse")
    require(type(retries) is int and 1<=retries<=3,"attempt limit must be 1..3")
    for field in ("merge_authorized","security_waiver_authorized",
                  "ruleset_change_authorized","background_execution_authorized",
                  "formal_root_closure_authorized"):
        require(policy.get(field) is False,"forbidden authority: "+field)
    require(policy.get("mutation_scope") in ("READ_ONLY","OWNED_BRANCH_ONLY"),
            "unbounded mutation authority")
    lanes=c.get("lanes")
    require(type(lanes) is list and 1<=len(lanes)<=12,"bounded typed lanes mandatory")
    identities=set();owned_paths=[]
    for lane in lanes:
        require(type(lane) is dict,"bad lane")
        ident=lane.get("id")
        require(isinstance(ident,str) and IDENT.fullmatch(ident) and ident not in identities,
                "duplicate/invalid lane id")
        identities.add(ident)
        require(lane.get("repository")==repo or (policy["mutation_scope"]=="READ_ONLY"),
                "external repo mutation not permitted")
        require(isinstance(lane.get("owner"),str) and lane["owner"].strip(),
                "lane lacks owner")
        paths=lane.get("paths")
        require(type(paths) is list and paths,"lane needs affected path families")
        for path in paths:
            require(isinstance(path,str) and bool(path) and not path.startswith("/")
                    and ".." not in path.split("/") and "\\" not in path and
                    path.strip()==path,"unsafe or non-normalized path")
            if lane.get("may_mutate"):
                require(policy["mutation_scope"]=="OWNED_BRANCH_ONLY" and
                        lane.get("lease_required") is True,"mutation requires path lease")
                owned_paths.append((ident,path))
    for i,(aid,ap) in enumerate(owned_paths):
        for bid,bp in owned_paths[i+1:]:
            require(aid==bid or not overlap(ap,bp),
                    "disjoint worker paths overlap: "+aid+" / "+bid)
    require(isinstance(c.get("required_evidence"),list) and
            {"NATIVE_RUN_ATTEMPT","EXACT_SOURCE_HEAD","SCOPE_DENOMINATOR","FIRST_RED_OR_PASS",
             "INDEPENDENT_ADMISSION_HOLD"}.issubset(set(c["required_evidence"])),
            "incomplete evidence charter")
    return c

def initial(c):
    charter(c)
    result={"schema":LEDGER,"execution_id":c["execution_id"],
            "mission_id":c["mission_id"],"repository":c["repository"],
            "baseline_source_sha":c["baseline"]["source_sha"],
            "charter_sha256":digest(c),"checkpoints":[],
            "stop_reason":None,"status":"N_BASELINE_READY","merge_authorized":False,
            "formal_root_closure_credit":0}
    return result

def validate_ledger(c,l):
    charter(c)
    require(type(l) is dict and l.get("schema")==LEDGER and
            l.get("execution_id")==c["execution_id"] and
            l.get("mission_id")==c["mission_id"] and
            l.get("repository")==c["repository"] and
            l.get("baseline_source_sha")==c["baseline"]["source_sha"] and
            l.get("charter_sha256")==digest(c),"ledger/charter identity mismatch")
    require(l.get("merge_authorized") is False and
            l.get("formal_root_closure_credit")==0,"ledger has forged authority")
    points=l.get("checkpoints")
    require(type(points) is list and len(points)<=3,"invalid checkpoint length")
    prior=c["baseline"]["source_sha"]
    chain=digest({"charter_sha256":l["charter_sha256"],"N":prior})
    runs=set()
    last_time=timestamp(c["baseline"]["observed_utc"])
    for i,r in enumerate(points):
        require(type(r) is dict and r.get("index")==i+1 and r.get("phase")==STEPS[i],
                "checkpoint sequence drift")
        require(r.get("previous_source_sha")==prior and r.get("previous_receipt_sha256")==chain,
                "broken N+ lineage chain")
        source=sha(r.get("source_sha"))
        require(type(r.get("run_key")) is list and len(r["run_key"])==2 and
                all(type(v) is int and v>0 for v in r["run_key"]) and
                tuple(r["run_key"]) not in runs,
                "duplicate/invalid native run attempt")
        runs.add(tuple(r["run_key"]))
        last=timestamp(r.get("completed_utc"))
        require(last>=last_time,"non-monotonic source time")
        require(r.get("native_outcome") in ("SUCCESS","FAILURE"),"nonterminal proof in ledger")
        require(r.get("major_blockers")==[] and
                r.get("root_closure_credit")==0 and r.get("merge_authorized") is False,
                "ledger checkpoint unqualified admission")
        metric(r["metric"])
        require(r["metric"]["key"]==c["objective"]["metric_key"],"checkpoint scope changed metric")
        require(r.get("receipt_sha256")==digest({k:v for k,v in r.items()
                                                  if k!="receipt_sha256"}),"checkpoint bytes altered")
        prior=source;chain=r["receipt_sha256"];last_time=last
    require(l.get("status") in ("N_BASELINE_READY","CONTINUE","REPAIR_NEXT_PULSE",
                                  "N3_MEASURED_COMPLETE","HOLD_MAJOR"),"bad execution state")
    if l["status"]!="HOLD_MAJOR":
        require((len(points)==0 and l["status"]=="N_BASELINE_READY") or
                (0<len(points)<3 and l["status"] in ("CONTINUE","REPAIR_NEXT_PULSE")) or
                (len(points)==3 and l["status"]=="N3_MEASURED_COMPLETE"),
                "ledger disposition does not match verified checkpoint count")
    require(l.get("stop_reason") is None or
            (l["status"]=="HOLD_MAJOR" and type(l["stop_reason"]) is dict),
            "unbound blocker")
    return l

def source_comparison(previous,current):
    matching=(previous["scope"]==current["scope"] and
              previous["instrument"]==current["instrument"] and
              previous["production_blob"]==current["production_blob"] and
              previous["eligible"]==current["eligible"])
    d=round(100*(current["covered"]-previous["covered"])/current["eligible"],4) if matching else None
    return "MATCHED_SOURCE_SCOPE" if matching else "UNMATCHED_SOURCE_SCOPE",d

def advance(c,l,o):
    validate_ledger(c,l)
    require(l["status"]!="HOLD_MAJOR" and len(l["checkpoints"])<3,
            "execution blocked or already completed")
    i=len(l["checkpoints"])+1
    require(type(o) is dict and o.get("schema")==OBS and
            o.get("execution_id")==c["execution_id"] and
            o.get("pulse_index")==i and type(o.get("pulse_index")) is int and
            o.get("phase")==STEPS[i-1] and o.get("repository")==c["repository"],
            "wrong native observation or pulse")
    previous=l["checkpoints"][-1] if l["checkpoints"] else None
    prev_sha=previous["source_sha"] if previous else c["baseline"]["source_sha"]
    require(o.get("previous_source_sha")==prev_sha,"stale head or incorrect N+i parent")
    sha(o.get("source_sha"))
    time=timestamp(o.get("completed_utc"))
    prevtime=timestamp(previous["completed_utc"] if previous else c["baseline"]["observed_utc"])
    require(time>=prevtime,"observation goes back in UTC")
    require(o.get("run_status")=="COMPLETED" and
            o.get("conclusion") in ("SUCCESS","FAILURE"),"queued/incomplete run cannot advance")
    rid,attempt=o.get("run_id"),o.get("attempt")
    require(type(rid) is int and rid>0 and type(attempt) is int and
            1<=attempt<=c["policy"]["max_attempts_per_pulse"],
            "native ID/attempt exceeds bounded policy")
    require(all([rid,attempt]!=r["run_key"] for r in l["checkpoints"]),
            "reused native attempt cannot give second pulse credit")
    require(o.get("native_head_sha")==o["source_sha"],
            "native head mismatch: exact-source run required")
    require(type(o.get("job_id")) is int and o["job_id"]>0,
            "native job proof required")
    require(o.get("native_receipt_url")==
            "https://github.com/"+c["repository"]+"/actions/runs/"+str(rid),
            "unbound native evidence URL")
    count=o.get("tests")
    require(type(count) is dict,"native test denominator required")
    if not all(type(count.get(k)) is int and count[k]>=0 for k in
               ("executed","passed","failed","skipped")):
        raise ValueError("invalid test outcomes")
    require(count["executed"]>=1 and count["passed"]+count["failed"]+count["skipped"]==count["executed"],
            "test denominator cannot be fabricated")
    if o["conclusion"]=="SUCCESS":
        require(count["failed"]==0,"green native run with failing native cases")
    else:
        require(isinstance(o.get("first_red"),str) and o["first_red"].strip(),
                "failed pulse requires attributable first-red")
    metric(o.get("metric"))
    require(o["metric"]["key"]==c["objective"]["metric_key"],"metric ID changed")
    require(o.get("root_closure_credit")==0 and o.get("merge_authorized") is False and
            o.get("security_waiver_authorized") is False,
            "observer cannot self-authorize merge/security/root closure")
    blockers=o.get("blockers")
    require(type(blockers) is list,"typed blockers required")
    for b in blockers:
        require(type(b) is dict and b.get("code") in MAJOR and
                b.get("severity")=="MAJOR" and
                isinstance(b.get("evidence_ref"),str) and b["evidence_ref"],
                "unknown or unproven major blocker")
    if blockers:
        out=dict(l)
        out["status"]="HOLD_MAJOR"
        out["stop_reason"]={"at":"N+"+str(i),"blockers":blockers,
                            "last_observed_native_run_id":rid,
                            "attempt":attempt,"source_sha":o["source_sha"]}
        validate_ledger(c,out)
        return out
    work=o.get("completed_work")
    require(type(work) is list,"work / no-work manifest required")
    lane_by_id={z["id"]:z for z in c["lanes"]}
    require(len({r.get("lane_id") for r in work if type(r) is dict})<=
            c["policy"]["max_disjoint_workers"],"worker limit exceeded")
    for row in work:
        require(type(row) is dict and row.get("lane_id") in lane_by_id and
                isinstance(row.get("disposition"),str) and row["disposition"] in
                ("READ_ONLY","OWNED_COMMIT","VERIFIED_NO_CHANGE"),
                "unowned work lane")
        if row["disposition"]=="OWNED_COMMIT":
            require(c["policy"]["mutation_scope"]=="OWNED_BRANCH_ONLY" and
                    lane_by_id[row["lane_id"]].get("may_mutate") is True and
                    row.get("owner_lease_valid") is True and
                    row.get("commit_sha")==o["source_sha"],
                    "unleased or stale source mutation")
    previous_metric=previous["metric"] if previous else c["baseline"]["metric"]
    comp,delta=source_comparison(previous_metric,o["metric"])
    verdict=("N3_MEASURED_COMPLETE" if i==3 else
             "REPAIR_NEXT_PULSE" if o["conclusion"]=="FAILURE" else "CONTINUE")
    chain=l["checkpoints"][-1]["receipt_sha256"] if previous else digest(
        {"charter_sha256":l["charter_sha256"],"N":l["baseline_source_sha"]})
    r={"index":i,"label":"N+"+str(i),"phase":STEPS[i-1],
       "previous_source_sha":prev_sha,"source_sha":o["source_sha"],
       "completed_utc":o["completed_utc"],"run_key":[rid,attempt],
       "job_id":o["job_id"],"native_receipt_url":o["native_receipt_url"],
       "native_outcome":o["conclusion"],"first_red":o.get("first_red"),
       "metric":o["metric"],"comparison":comp,"comparable_delta_pp":delta,
       "tests":count,"completed_work":work,
       "major_blockers":[],"previous_receipt_sha256":chain,
       "root_closure_credit":0,"merge_authorized":False}
    r["receipt_sha256"]=digest(r)
    out=dict(l)
    out["checkpoints"]=l["checkpoints"]+[r]
    out["status"]=verdict
    validate_ledger(c,out)
    return out

def plan(c,l):
    validate_ledger(c,l)
    i=len(l["checkpoints"])
    blocked=l["status"]=="HOLD_MAJOR"
    status="HOLD_MAJOR" if blocked else ("RETURN_N3" if i==3 else
       "REPAIR_SOURCE_FIRST_RED" if l["status"]=="REPAIR_NEXT_PULSE" else
       "EXECUTE_"+STEPS[i])
    return {"schema":"codepurple.n3.next-action.v1","execution_id":c["execution_id"],
            "confirmed_checkpoints":i,"target":"N+3","state":status,
            "phase":None if blocked or i==3 else STEPS[i],
            "source_sha":l["checkpoints"][-1]["source_sha"] if i else c["baseline"]["source_sha"],
            "worker_limit":c["policy"]["max_disjoint_workers"],
            "wave_strategy":c["policy"]["wave_strategy"],
            "commit_scope":c["policy"]["mutation_scope"],
            "requires_new_native_run_and_attempt":bool(i<3 and not blocked),
            "no_background_execution":True,"merge_authorized":False}

def return_receipt(c,l):
    validate_ledger(c,l)
    rs=l["checkpoints"]
    last=rs[-1]["metric"] if rs else c["baseline"]["metric"]
    comp,delta=source_comparison(c["baseline"]["metric"],last) if rs else ("NO_POST_BASELINE_EVIDENCE",None)
    return {"schema":RETURN,"execution_id":c["execution_id"],
            "moniker":"N3_CONTINUE/3PSTAR","baseline":"N",
            "last_verified_checkpoint":"N+"+str(len(rs)),
            "verified_checkpoint_count":len(rs),
            "three_pulses_complete":len(rs)==3,
            "native_terminal_successes":sum(x["native_outcome"]=="SUCCESS" for x in rs),
            "native_terminal_failures":sum(x["native_outcome"]=="FAILURE" for x in rs),
            "baseline_current_comparability":comp,"comparable_net_delta_pp":delta,
            "first_red_tasks":[x["first_red"] for x in rs if x["first_red"]],
            "stop_reason":l["stop_reason"],
            "next_action":plan(c,l)["state"],"head_sha":plan(c,l)["source_sha"],
            "native_input_authentication":"STRUCTURAL_ONLY_REQUIRES_INDEPENDENT_GITHUB_READBACK",
            "no_global_coverage_or_admission_inference":True,
            "independent_review":"UNVERIFIED","formal_root_closure_credit":0,
            "merge_authorized":False}

def sipoc(c,l):
    return {"schema":"codepurple.n3.sipoc-dag.v1",
        "nodes":[
         {"id":"S","role":"S","name":"Source owners + native GitHub","evidence":"SOURCE_BOUND"},
         {"id":"I","role":"I","name":"N charter, source scope, owner leases","evidence":"DECLARED"},
         {"id":"P1","role":"P","name":STEPS[0],"evidence":"RECORDED" if len(l["checkpoints"])>0 else "DECLARED"},
         {"id":"P2","role":"P","name":STEPS[1],"evidence":"RECORDED" if len(l["checkpoints"])>1 else "DECLARED"},
         {"id":"P3","role":"P","name":STEPS[2],"evidence":"RECORDED" if len(l["checkpoints"])>2 else "DECLARED"},
         {"id":"O","role":"O","name":"Append-only N3 receipt and metric/REX delta","evidence":"DERIVED"},
         {"id":"C","role":"C","name":"Independent admission/REX owner HOLD","evidence":"HOLD"}],
        "edges":[{"from":a,"to":b,"binding":"RECORDED" if i<len(l["checkpoints"])+1 else "DECLARED"}
                 for i,(a,b) in enumerate([("S","I"),("I","P1"),("P1","P2"),
                                            ("P2","P3"),("P3","O"),("O","C")])],
        "pulse_count":len(l["checkpoints"]),"wave_strategy":c["policy"]["wave_strategy"],
        "merge_authorized":False}

def html_page(receipt):
    e=lambda z:html.escape(str(z),quote=True)
    return ('<!doctype html><html lang="en"><meta charset="utf-8">'
      '<title>N3_CONTINUE governed return</title><style>'
      'body{font:16px system-ui;max-width:920px;margin:auto;padding:25px;background:#102338;color:#eef7ff}'
      'section{border:1px solid #657890;padding:16px;border-radius:10px;margin:15px 0}'
      'strong{color:#83dfb2}</style><body><h1>GoGREEN · N3_CONTINUE / 3PSTAR</h1>'
      '<section><p>Verified checkpoints: <strong>'+e(receipt["verified_checkpoint_count"])+
      '/3</strong> · '+e(receipt["last_verified_checkpoint"])+'</p><p>Next disposition: <strong>'+
      e(receipt["next_action"])+'</strong></p><p>Terminal native successes: '+
      e(receipt["native_terminal_successes"])+'; terminal reds: '+
      e(receipt["native_terminal_failures"])+'</p></section><section><p>Comparable net delta: '+
      e(receipt["comparable_net_delta_pp"] if receipt["comparable_net_delta_pp"] is not None else
      "UNKNOWN — changed source, tool, population or denominator")+
      '</p><p>Independent admission and REX root control: <strong>HOLD</strong>. '
      'This is an in-turn execution result, not an asynchronous service.</p></section></body></html>\n')

def produce(c,l,out):
    rec=return_receipt(c,l)
    files={"ledger.json":encoded(l),"return_receipt.json":encoded(rec),
           "next_action.json":encoded(plan(c,l)),
           "sipoc_dag.json":encoded(sipoc(c,l)),
           "index.html":html_page(rec).encode("utf-8")}
    require(not out.exists() or not any(out.iterdir()),
            "output directory not empty: append-only run snapshots cannot be overwritten")
    out.mkdir(parents=True,exist_ok=True)
    for name,raw in files.items():
        (out/name).write_bytes(raw)
    mf={"schema":"codepurple.n3.manifest.v1","charter_sha256":digest(c),
        "files_sha256":{name:hashlib.sha256(raw).hexdigest() for name,raw in files.items()},
        "authority_transfer":False,"merge_authorized":False}
    (out/"manifest.json").write_bytes(encoded(mf))
    return rec,mf

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--charter",type=Path,required=True)
    p.add_argument("--ledger",type=Path)
    p.add_argument("--observations",type=Path)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    c=json.loads(a.charter.read_text(encoding="utf-8"))
    l=json.loads(a.ledger.read_text(encoding="utf-8")) if a.ledger else initial(c)
    if a.observations:
        obs=json.loads(a.observations.read_text(encoding="utf-8"))
        require(type(obs) is list and len(obs)<=3,"at most three native observations per call")
        for item in obs:
            l=advance(c,l,item)
            if l["status"]=="HOLD_MAJOR":break
    rec,_=produce(c,l,a.out)
    print(json.dumps({"checkpoint":rec["last_verified_checkpoint"],
                      "complete":rec["three_pulses_complete"],
                      "next":rec["next_action"],"merge_authorized":False},sort_keys=True))

if __name__=="__main__":
    main()
