"""Reproducible JADE point-release *preflight*, never a release CLI.

Default plan has zero workers launched. 'local' executes only allowlisted local
Python tests/build checkers; source-owned CI, security, Pages, tags and owners
are represented as deferred proof needs. Python standard library only.
"""
from __future__ import annotations
import argparse
import concurrent.futures as cf
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from model import build, canonical, digest, mermaid, render_html, demand

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
JADE=HERE.parent
SCHEMA="jade.temple.sprint.bundle.v1"
LOCAL_SCHEMA="jade.temple.sprint.local_execution.v1"
HASH_FILES=("SPRINT_DAG.json","SPRINT_SIPOC.json","SPRINT_METRICS.json",
            "SPRINT_SPINE.mmd","SPRINT_DASHBOARD.html","SPRINT_QUEUE.json")

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def source_sha(root):
    p=subprocess.run(["git","rev-parse","HEAD"],cwd=root,capture_output=True,text=True,
                     check=False,timeout=10)
    demand(p.returncode==0 and len(p.stdout.strip())==40 and
           all(c in "0123456789abcdef" for c in p.stdout.strip()),
           "GIT_SOURCE_SHA_REQUIRED")
    return p.stdout.strip()

def input_fingerprint(root, readback):
    # All JADE code/data under test, not just the entrypoint. Generated QA and
    # retained browser screenshots are deliberately excluded.
    root=root.resolve()
    prefix=root/"mission-control"/"jade_temple"
    paths=[]
    for p in prefix.rglob("*"):
        if not p.is_file() or p.is_symlink():
            continue
        rel=p.relative_to(root).as_posix()
        if any(x in p.parts for x in ("__pycache__",".venv",".git",".jade-cache")):
            continue
        if "/qa/" in rel or "/sprint/output/" in rel:
            continue
        if p.suffix.lower() not in (".py",".json",".yml",".yaml",".toml",
                                    ".html",".js",".css",".csv",".md",".ps1",".txt"):
            continue
        paths.append((rel,sha(p.read_bytes())))
    if readback is not None and not str(readback.resolve()).startswith(str(prefix)):
        paths.append(("EXTERNAL_READBACK:"+readback.name,sha(readback.read_bytes())))
    demand(bool(paths),"EMPTY_SOURCE_CONTENT_HASH")
    return sha(canonical(sorted(paths))),len(paths)

def jobs(root,python,with_browser):
    jade=root/"mission-control"/"jade_temple"
    results=[
        {"id":"N1_CONTRACT_TESTS","pool":"LOCAL_PYTHON","priority":0,
         "argv":[python,"-m","unittest","discover","-s",
                 str(jade/"tests"),"-p","test_*.py","-v"],"timeout":300},
        {"id":"N1_SITE_CHECK","pool":"LOCAL_PYTHON","priority":1,
         "argv":[python,str(jade/"site"/"build_dashboard.py"),"--check"],"timeout":120},
        {"id":"N1_GREEN_CHECK","pool":"LOCAL_PYTHON","priority":1,
         "argv":[python,str(jade/"site"/"build_green.py"),"--check"],"timeout":120},
    ]
    n2=jade/"site"/"build_burndown.py"
    if n2.is_file():
        results.append({"id":"N2_BURNDOWN_CHECK","pool":"LOCAL_PYTHON","priority":1,
                        "argv":[python,str(n2),"--check"],"timeout":120})
    if with_browser:
        browser=jade/"tools"/"run_nplus1_browser_qa.py"
        demand(browser.is_file(),"BROWSER_SCRIPT_NOT_FOUND")
        results.append({"id":"OPTIONAL_LOCAL_BROWSER","pool":"LOCAL_BROWSER","priority":2,
                        "argv":[python,str(browser)],"timeout":420})
    return sorted(results,key=lambda x:(x["priority"],x["id"]))

def cachekey(job,head,inputs):
    return sha(canonical({"schema":"jade.temple.cache-key.v1","head":head,
                         "source_inputs_sha256":inputs,
                         "job":job["id"],"argv":job["argv"],
                         "interpreter":sys.version,"platform":platform.system()}))

def cache_valid(path,head,inputs,job,ttl_hours):
    if not path.is_file() or path.is_symlink():
        return None
    try:
        doc=json.loads(path.read_text(encoding="utf-8"))
        demand(doc.get("schema")=="jade.temple.local-cache.v1" and
               doc.get("head")==head and doc.get("source_digest")==inputs and
               doc.get("job")==job["id"] and doc.get("key")==cachekey(job,head,inputs)
               and doc.get("state")=="LOCAL_TEST_PASS" and doc.get("authority")=="LOCAL_ONLY",
               "INVALID_CACHE_RECEIPT")
        completed=datetime.fromisoformat(doc["completed"].replace("Z","+00:00"))
        age=(datetime.now(timezone.utc)-completed).total_seconds()
        demand(0<=age<=ttl_hours*3600,"EXPIRED_CACHE_RECEIPT")
        return doc
    except (OSError,ValueError,TypeError,KeyError):
        return None

def run_one(job,root,out,cache,head,inputs,ttl_hours,no_cache,started_plan):
    key=cachekey(job,head,inputs)
    record=cache/(key+".json")
    queued_for=round(max(0.0,time.monotonic()-started_plan),3)
    if not no_cache:
        previous=cache_valid(record,head,inputs,job,ttl_hours)
        if previous is not None:
            return {"id":job["id"],"pool":job["pool"],"status":"LOCAL_CACHE_HIT",
                    "queue_wait_seconds":queued_for,"duration_seconds":0,
                    "cache_key":key,"native_proof":None,"release_credit":0,
                    "previous_local_receipt_digest":sha(record.read_bytes())}
    # Atomic lease: a duplicate local launcher must not run the same step
    # concurrently; it may instead choose other admissible work.
    cache.mkdir(parents=True,exist_ok=True)
    lease=cache/(key+".lease")
    try:
        fd=os.open(str(lease),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError:
        return {"id":job["id"],"pool":job["pool"],"status":"DEFER_LOCAL_LEASE",
                "queue_wait_seconds":queued_for,"duration_seconds":None,
                "cache_key":key,"native_proof":None,"release_credit":0}
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as handle:
            handle.write(head+"\n")
        start=time.monotonic()
        try:
            p=subprocess.run(job["argv"],cwd=root,capture_output=True,text=True,
                             errors="replace",check=False,timeout=job["timeout"])
            log=p.stdout+"\n--- STDERR ---\n"+p.stderr
            status="LOCAL_TEST_PASS" if p.returncode==0 else "LOCAL_TEST_FAIL"
            code=p.returncode
        except subprocess.TimeoutExpired as ex:
            log=str(ex)
            status="LOCAL_TIMEOUT"
            code=None
        dur=round(time.monotonic()-start,3)
        logfile=out/(job["id"]+".log")
        logfile.write_text(log[-200000:],encoding="utf-8",newline="\n")
        result={"id":job["id"],"pool":job["pool"],"status":status,
                "exit_code":code,"queue_wait_seconds":queued_for,
                "duration_seconds":dur,"log_sha256":sha(logfile.read_bytes()),
                "cache_key":key,"native_proof":None,"release_credit":0}
        if status=="LOCAL_TEST_PASS":
            cache_doc={"schema":"jade.temple.local-cache.v1",
                       "head":head,"source_digest":inputs,
                       "job":job["id"],"key":key,
                       "completed":datetime.now(timezone.utc).isoformat(),
                       "state":"LOCAL_TEST_PASS","authority":"LOCAL_ONLY",
                       "log_sha256":result["log_sha256"]}
            temporary=cache/(key+".tmp."+str(os.getpid()))
            temporary.write_bytes(canonical(cache_doc))
            os.replace(temporary,record)
        return result
    finally:
        lease.unlink(missing_ok=True)

def local_run(root,out,cache,head,inputs,max_workers,ttl,no_cache,with_browser):
    demand(type(max_workers) is int and 1<=max_workers<=4,"WORKER_BOUND_1_TO_4")
    work=jobs(root,sys.executable,with_browser)
    start=time.monotonic()
    results=[]
    # Work is disjoint by local action; long external dependencies are never
    # submitted. Browser isolation prevents Playwright from consuming Python slots.
    with cf.ThreadPoolExecutor(max_workers=max_workers) as p:
        with cf.ThreadPoolExecutor(max_workers=1) as b:
            fs=[]
            for task in work:
                pool=b if task["pool"]=="LOCAL_BROWSER" else p
                fs.append(pool.submit(run_one,task,root,out,cache,head,inputs,ttl,no_cache,start))
            for future in cf.as_completed(fs):
                results.append(future.result())
    results.sort(key=lambda x:x["id"])
    durations=[x["queue_wait_seconds"] for x in results if x["status"]!="DEFER_LOCAL_LEASE"]
    report={"schema":LOCAL_SCHEMA,"head":head,"source_digest":inputs,
            "configured_local_python_slots":max_workers,
            "actual_native_runner_slots":None,
            "jobs_attempted":len(results),
            "local_pass":sum(x["status"]=="LOCAL_TEST_PASS" for x in results),
            "local_cache_hits":sum(x["status"]=="LOCAL_CACHE_HIT" for x in results),
            "local_failures":sum(x["status"] in ("LOCAL_TEST_FAIL","LOCAL_TIMEOUT") for x in results),
            "local_queue_p95_seconds":(round(sorted(durations)[math.ceil(.95*len(durations))-1],3)
                                        if durations else None),
            "native_queue_p95_seconds":None,
            "deferred_long_external":["NATIVE_GITHUB_CI","J2_HTTPS_PAGES",
                "J3_EFFECTIVE_PROTECTION","ELIGIBLE_HUMAN_REVIEW",
                "J4_RELEASE_CANDIDATE","J5_POINT_RELEASE"],
            "external_worker_dispatches":0,"release_admission":"HOLD",
            "point_release":"TARGET_NOT_ACHIEVED","results":results}
    (out/"LOCAL_RUN.json").write_bytes(canonical(report))
    return report

def write_bundle(root,out,readback=None):
    source=json.loads((root/"mission-control"/"jade_temple"/"data"/
                       "REPO_READINESS_NPLUS1.json").read_text(encoding="utf-8"))
    n2=json.loads(readback.read_text(encoding="utf-8")) if readback else None
    projection=build(source,n2)
    graph=projection.pop("graph")
    sipoc=projection.pop("sipoc")
    queued=projection.pop("work_orders")
    queue={"schema":"jade.temple.sprint.queue.v1",
           "authority":"STAGE_ONLY_NOT_DISPATCHED","items":queued,
           "configured_local_capacity":2,
           "measured_runner_capacity":None,
           "native_job_population":None,
           "known_long_wait_policy":"DEFER_AND_EXECUTE_INDEPENDENT_SLICE",
           "risk":"P0_APPROVAL_PAGES_NATIVE_SOURCE_BLOCKED"}
    inputs,cnt=input_fingerprint(root,readback)
    head=source_sha(root)
    metrics={**projection,"exact_local_checkout_head":head,
             "input_contents_sha256":inputs,"fingerprinted_files":cnt,
             "local_pipeline_qualified":None}
    blobs={
      "SPRINT_DAG.json":canonical(graph),
      "SPRINT_SIPOC.json":canonical(sipoc),
      "SPRINT_METRICS.json":canonical(metrics),
      "SPRINT_QUEUE.json":canonical(queue),
      "SPRINT_SPINE.mmd":mermaid(metrics).encode("utf-8"),
      "SPRINT_DASHBOARD.html":render_html({**metrics,"graph":graph,"sipoc":sipoc,"work_orders":queued}).encode("utf-8")
    }
    out.mkdir(parents=True,exist_ok=True)
    for name,content in blobs.items():
        (out/name).write_bytes(content)
    return head,inputs

def seal(out,head,inputs):
    names=list(HASH_FILES)
    if (out/"LOCAL_RUN.json").is_file():
        local=json.loads((out/"LOCAL_RUN.json").read_text(encoding="utf-8"))
        demand(local.get("head")==head and local.get("source_digest")==inputs and
               local.get("release_admission")=="HOLD" and
               local.get("point_release")=="TARGET_NOT_ACHIEVED" and
               local.get("external_worker_dispatches")==0, "STALE_OR_PROMOTED_LOCAL_RESULT")
        names.append("LOCAL_RUN.json")
    receipt={"schema":SCHEMA,"source_head":head,
             "source_contents_sha256":inputs,
             "admission":"HOLD","point_release":"TARGET_NOT_ACHIEVED",
             "native_test_admission":None,"remote_dispatches":0,
             "files":{name:sha((out/name).read_bytes()) for name in sorted(names)}}
    (out/"SHA256_MANIFEST.json").write_bytes(canonical(receipt))
    return receipt

def verify(root,out,head,inputs):
    path=out/"SHA256_MANIFEST.json"
    demand(path.is_file(),"NO_SHA256_MANIFEST")
    data=json.loads(path.read_text(encoding="utf-8"))
    demand(data.get("schema")==SCHEMA and data.get("admission")=="HOLD" and
           data.get("point_release")=="TARGET_NOT_ACHIEVED" and
           data.get("remote_dispatches")==0,"RECEIPT_AUTHORITY")
    demand(data.get("source_head")==head and
           data.get("source_contents_sha256")==inputs,"STALE_SOURCE_RECEIPT")
    expected=set(HASH_FILES)
    if (out/"LOCAL_RUN.json").is_file():expected.add("LOCAL_RUN.json")
    demand(set(data.get("files",{}))==expected,"INCOMPLETE_MANIFEST")
    for name,want in data["files"].items():
        demand((out/name).is_file() and sha((out/name).read_bytes())==want,
               "HASH_DRIFT:"+name)
    return data

def main(argv=None):
    p=argparse.ArgumentParser(description="JADE point-release readiness only; NEVER publishes.")
    p.add_argument("--mode",choices=("plan","local","verify","full"),default="plan")
    p.add_argument("--repo-root",type=Path,default=ROOT)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--cache-dir",type=Path)
    p.add_argument("--max-workers",type=int,default=2)
    p.add_argument("--cache-ttl-hours",type=int,default=12)
    p.add_argument("--no-cache",action="store_true")
    p.add_argument("--with-browser",action="store_true")
    p.add_argument("--nplus2",type=Path)
    p.add_argument("--expected-head")
    a=p.parse_args(argv)
    root=a.repo_root.resolve()
    out=a.out.resolve()
    cache=(a.cache_dir or out.parent/".jade-cache").resolve()
    demand(1<=a.max_workers<=4,"WORKER_BOUND_1_TO_4")
    demand(1<=a.cache_ttl_hours<=72,"CACHE_TTL_1_TO_72_HOURS")
    demand(not str(out).startswith(str(root/"mission-control"/"jade_temple"/"sprint")),
           "OUTPUT_MUST_BE_OUTSIDE_SPRINT_SOURCE")
    head=source_sha(root)
    if a.expected_head:
        demand(a.expected_head==head,"EXPECTED_HEAD_MISMATCH")
    n2=a.nplus2.resolve() if a.nplus2 else None
    if n2 is not None:
        demand(n2.is_file(),"N2_SOURCE_MISSING")
    if a.mode=="verify":
        inputs,_=input_fingerprint(root,n2)
        verify(root,out,head,inputs)
        print(json.dumps({"verified":True,"admission":"HOLD","head":head}))
        return 0
    h,inputs=write_bundle(root,out,n2)
    if a.mode in ("local","full"):
        result=local_run(root,out,cache,h,inputs,a.max_workers,
                         a.cache_ttl_hours,a.no_cache,a.with_browser)
    else:
        result=None
    seal(out,h,inputs)
    verify(root,out,h,inputs)
    print(json.dumps({"mode":a.mode,"head":h,"output":str(out),
                      "local":None if result is None else
                      {"passed":result["local_pass"],
                       "cache_hits":result["local_cache_hits"],
                       "failed":result["local_failures"]},
                      "release":"TARGET_NOT_ACHIEVED","admission":"HOLD"},sort_keys=True))
    return 1 if result and result["local_failures"] else 0

if __name__=="__main__":
    raise SystemExit(main())
