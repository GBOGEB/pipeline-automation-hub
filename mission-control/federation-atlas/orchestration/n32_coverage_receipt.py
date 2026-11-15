#!/usr/bin/env python3
"""N3.2 coverage: measured TEST versus ACTUAL_BROKER_EXECUTION populations.

An executed Python function is not an executed business outcome; this receipt
binds coverage.py's branch arcs to N3's independently verified actual DAG.
No inferred whole-repo denominator, no fabricated source/remote identity.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

HEAD = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SOURCE = ("broker.py", "main.py", "outcome_flight.py", "warm_broker_pilot.py")
SCHEMA = "method-atlas.n32.real-broker-coverage.v1"


def guard(ok, reason):
    if not ok:
        raise ValueError(reason)


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def hashbytes(raw):
    return hashlib.sha256(raw).hexdigest()


def exact_head(root, head):
    guard(bool(HEAD.fullmatch(head or "")), "EXACT_HEAD_REQUIRED")
    p=subprocess.run(["git","-C",str(root),"rev-parse","HEAD"],capture_output=True,
                     text=True,timeout=10,check=False)
    guard(p.returncode==0 and p.stdout.strip()==head, "CHECKOUT_HEAD_MISMATCH")


def load_coverage(path):
    raw=Path(path).read_bytes()
    obj=json.loads(raw)
    meta=obj.get("meta",{})
    guard(meta.get("branch_coverage") is True and meta.get("version"),
          "BRANCH_INSTRUMENTATION_MISSING")
    guard(isinstance(obj.get("files"),dict) and obj["files"],
          "MEASURED_SOURCE_FILES_MISSING")
    for path,entry in obj["files"].items():
        t=entry.get("summary",{})
        for key in ("num_statements","covered_lines","num_branches","covered_branches"):
            guard(type(t.get(key)) is int and t[key]>=0,"COVERAGE_NUMERIC_DENOMINATOR_INVALID")
        guard(t["covered_lines"]<=t["num_statements"] and
              t["covered_branches"]<=t["num_branches"],"COVERAGE_COUNT_EXCEEDS_DENOMINATOR")
    return obj,hashbytes(raw)


def select_files(data):
    found={}
    for path,entry in data["files"].items():
        matches=[name for name in SOURCE if Path(path).name==name]
        guard(len(matches)<=1,"AMBIGUOUS_SOURCE_PATH")
        if not matches:continue
        name=matches[0]
        guard(name not in found,"DUPLICATE_SOURCE_BASENAME")
        found[name]=entry["summary"]
    return found


def summarize_pop(data):
    files=select_files(data)
    missing=sorted(set(SOURCE)-set(files))
    rows={}
    for name in SOURCE:
        if name not in files:
            rows[name]={"status":"NOT_INSTRUMENTED_OR_NOT_EXECUTED",
                        "branches":None,"statements":None}
            continue
        v=files[name]
        eligible=v["num_branches"]
        rows[name]={
            "status":("BRANCHLESS_NOT_APPLICABLE" if eligible==0 else
                      "ZERO_INSTRUMENTED" if v["covered_branches"]==0 else
                      "MEASURED_PARTIAL_OR_FULL"),
            "branches":{"eligible":eligible,"covered":v["covered_branches"],
                        "pct":round(v["covered_branches"]*100/eligible,4) if eligible else None},
            "statements":{"eligible":v["num_statements"],"covered":v["covered_lines"],
                          "pct":round(v["covered_lines"]*100/v["num_statements"],4)
                          if v["num_statements"] else None},
        }
    return rows,missing


def compare(testpath,runtimepath,actualpath,head,root):
    root=Path(root).resolve()
    exact_head(root,head)
    tests,tests_hash=load_coverage(testpath)
    runtime,runtime_hash=load_coverage(runtimepath)
    guard(tests["meta"].get("version")==runtime["meta"].get("version"),
          "COVERAGE_TOOL_VERSION_DRIFT")
    t,tm=summarize_pop(tests)
    r,rm=summarize_pop(runtime)
    guard(not rm,"PRODUCTION_SOURCE_INSTRUMENTATION_INCOMPLETE")
    for name in SOURCE:
        location = ("mission-control/gogreen/outcome_convergence/" if name=="outcome_flight.py"
                    else "mission-control/federation-atlas/orchestration/") + name
        src=root/location
        guard(src.is_file(),"MISSING_TRACKED_SOURCE")
        guard(r[name]["statements"]["eligible"]>0 and
              r[name]["branches"]["eligible"]>0,
              "RUNTIME_NO_ELIGIBLE_ARCS_"+name)
        guard(r[name]["statements"]["covered"]>0 and
              r[name]["branches"]["covered"]>0,
              "RUNTIME_ZERO_HIT_ARCS_"+name)
    evidence=Path(actualpath)
    measured=json.loads(evidence.read_bytes())
    guard(measured.get("schema")=="method-atlas.warm-broker-pilot.v1" and
          measured.get("source",{}).get("head")==head,
          "ACTUAL_DAG_SOURCE_HEAD_DRIFT")
    expected=measured.get("plan",{})
    rows=measured.get("rows",[])
    guard(expected.get("positive_dag_count")==24 and
          expected.get("invalid_dag_count")==24 and
          expected.get("tamper_dag_count")==2 and len(rows)==50 and
          sum(x.get("accepted_fan_in") is True for x in rows)==24 and
          sum(x.get("accepted_fan_in") is False for x in rows)==26,
          "ACTUAL_DAG_OUTCOME_POPULATION_INCOMPLETE")
    return {
        "schema":SCHEMA,"head":head,
        "instrumentation":{"tool":"coverage.py","version":runtime["meta"]["version"],
                           "runtime_branch_coverage":True},
        "test_suite_population":{"definition":"UNIT_SUITE_INCLUDES_REAL_SMOKE",
             "coverage_json_sha256":tests_hash,"files":t,"missing":tm},
        "production_execution_population":{"definition":"ACTUAL_N3_50_BROKER_DAGS",
             "coverage_json_sha256":runtime_hash,"files":r,"missing":rm,
             "dag_receipt_sha256":hashbytes(evidence.read_bytes()),
             "verified_dags":50,"valid_joins":24,"negative_blocked_joins":26},
        "whole_repository_coverage":None,
        "cross_repository_coverage":None,
        "native_job_readback_authenticated":False,
        "branch_arcs_prove_product_acceptance":False,
        "merge_authorized":False,"remote_dispatch_authorized":False,
        "engineering_credit_delta":0,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--head",required=True)
    p.add_argument("--tests",type=Path,required=True)
    p.add_argument("--runtime",type=Path,required=True)
    p.add_argument("--actual",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args(argv)
    result=compare(args.tests,args.runtime,args.actual,args.head,args.root)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_bytes(canonical(result))
    print(json.dumps({"status":"MEASURED_ACTUAL_BROKER_BRANCH_COVERAGE",
                      "head":args.head,
                      "runtime_files":{k:v["branches"] for k,v in
                                       result["production_execution_population"]["files"].items()},
                      "native_fleet_qualified":False},sort_keys=True))


if __name__=="__main__":
    main()
