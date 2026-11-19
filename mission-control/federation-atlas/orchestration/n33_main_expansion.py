#!/usr/bin/env python3
"""N3.3 source-bound Method Atlas *main.py* execution-path coverage.

Real production commands: plan, build (+ verification/rebuild), run-local with
1/2/4 workers on clean per-mode worktrees. Original N3.2 50-DAG pilot is
rerun on the *same* checkout/head/coverage version as the baseline.

Output artifacts are unmodified source-readonly; all generated files live
outside the source checkout. This is local CLI path coverage, not whole-repo
coverage, fleet capacity or permission to merge.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

SCHEMA="method-atlas.n33.main-execution-coverage.v1"
MAIN="mission-control/federation-atlas/orchestration/main.py"
N3="mission-control/federation-atlas/orchestration/warm_broker_pilot.py"
BASELINE_BLOB="41f04e8719981be6564cf6de33f365d83c7a2264"
BASELINE_BRANCHES=27
BASELINE_ELIGIBLE=276
# Source-pinned main.py entrypoint: import reaches the false guard arc;
# invoking the direct CLI reaches the true guard arc.
IMPORT_ONLY_MAIN_GUARD_ARC=(1262,-1)
CLI_MAIN_GUARD_ARC=(1262,1263)
SHA40=re.compile(r"^[a-f0-9]{40}$")
CHECKS=("stale_head","missing_source_input","malformed_snapshot",
        "tampered_bundle_member","dependency_cycle","source_drift_receipt")
MAX_SECONDS={"baseline":300,"plan":90,"build":300,"rebuild":300,
             "run1":540,"run2":540,"run4":540}
EXPECTED_TASKS={"validate","method","control","superstitch","convergence",
                "orchestration","assemble","portal"}


def demand(ok,code):
    if not ok:raise ValueError(code)


def canonical(obj):
    return (json.dumps(obj,sort_keys=True,indent=2,allow_nan=False)+"\n").encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(root,*args):
    r=subprocess.run(["git","-C",str(root),*args],text=True,capture_output=True,
                     timeout=30,check=False)
    demand(r.returncode==0,"GIT_IDENTITY_READBACK_FAILED")
    return r.stdout.strip()


def source_bytes_at_head(root, rel):
    """Raw committed bytes, independent of index flags and clean/smudge filters."""
    key=rel.as_posix() if isinstance(rel,Path) else rel
    demand(isinstance(key,str) and key and not key.startswith("/") and
           ".." not in Path(key).parts,"PINNED_SOURCE_PATH_INVALID")
    commit=subprocess.run(["git","-C",str(root),"rev-parse","HEAD:"+key],
                          capture_output=True,text=True,timeout=30,check=False)
    demand(commit.returncode==0 and bool(SHA40.fullmatch(commit.stdout.strip())),
           "PINNED_HEAD_BLOB_UNAVAILABLE")
    blob=subprocess.run(["git","-C",str(root),"cat-file","blob",commit.stdout.strip()],
                        capture_output=True,timeout=30,check=False)
    demand(blob.returncode==0,"PINNED_HEAD_BLOB_UNAVAILABLE")
    return blob.stdout


def verify_build_inputs_at_head(root):
    """Fail closed for all tracked orchestration inputs, including render.py.

    A hidden assume-unchanged/skip-worktree edit, local Git clean filter or
    symlink cannot substitute executable bytes while receipts claim HEAD.
    """
    subtree="mission-control/federation-atlas/orchestration"
    listing=subprocess.run(["git","-C",str(root),"ls-files","-z","--",subtree],
                           capture_output=True,timeout=30,check=False)
    demand(listing.returncode==0,"PINNED_SOURCE_LIST_UNAVAILABLE")
    names=[p.decode("utf-8") for p in listing.stdout.split(b"\0") if p]
    demand(MAIN in names and
           subtree+"/render.py" in names and
           subtree+"/n33_main_expansion.py" in names,
           "PINNED_BUILD_INPUT_SET_INCOMPLETE")
    for name in names:
        p=Path(root)/name
        demand(p.is_file() and not p.is_symlink(),"PINNED_SOURCE_NOT_REGULAR")
        demand(p.read_bytes()==source_bytes_at_head(root,name),
               "PINNED_SOURCE_BYTES_NOT_IN_HEAD")


def exact_root(root,head):
    demand(bool(SHA40.fullmatch(head or "")),"INVALID_EXACT_HEAD")
    demand(git(root,"rev-parse","HEAD")==head,"CHECKOUT_HEAD_DRIFT")
    demand(git(root,"hash-object",MAIN)==BASELINE_BLOB,
           "N33_MAIN_SOURCE_CHANGED_FROM_N32_27_ARC_BASELINE")
    demand(git(root,"status","--porcelain")=="","SOURCE_CHECKOUT_DIRTY")
    verify_build_inputs_at_head(root)


def producer(root,path,identity):
    spec=importlib.util.spec_from_file_location(identity,root/path)
    demand(spec is not None and spec.loader is not None,"SOURCE_MODULE_UNAVAILABLE")
    module=importlib.util.module_from_spec(spec)
    sys.modules[identity]=module
    spec.loader.exec_module(module)
    return module


def call(root,argv,output,timeout,env=None,expected=True):
    """Actual subprocess and log; no shell interpolation or hidden retries."""
    start=time.perf_counter()
    try:
        p=subprocess.run(argv,cwd=root,env={**os.environ,
                        "PYTHONDONTWRITEBYTECODE":"1",**(env or {})},
                        stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
                        timeout=timeout,check=False)
    except subprocess.TimeoutExpired:
        raise ValueError("N33_EXECUTION_TIMEOUT_"+output.stem) from None
    elapsed=time.perf_counter()-start
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(p.stdout+"\n----- STDERR -----\n"+p.stderr,encoding="utf-8")
    demand((p.returncode==0) is expected,
           ("UNEXPECTED_SUCCESS_" if not expected else "FIRST_RED_")+output.stem)
    return {"returncode":p.returncode,"wall_seconds":round(elapsed,6),
            "log_sha256":sha(output.read_bytes()),"log_path":output.name,
            "stderr":p.stderr}


def run_coverage(root,head,script,arguments,tag,directory,timeout):
    source=Path(root).resolve()
    base=Path(directory).resolve()
    cov=base/"instruments"/(tag+".coverage")
    log=base/"logs"/(tag+".log")
    raw=base/"coverage"/(tag+".json")
    cmd=[sys.executable,"-m","coverage","run","--branch",
         "--include=*/mission-control/federation-atlas/orchestration/main.py",
         str(source/script),*arguments]
    result=call(source,cmd,log,timeout,{"COVERAGE_FILE":str(cov)})
    call(source,[sys.executable,"-m","coverage","json","-q","-o",str(raw)],
         base/"logs"/(tag+"-coverage-export.log"),30,
         {"COVERAGE_FILE":str(cov)})
    return {**result,"coverage_path":str(raw),"coverage_sha256":sha(raw.read_bytes())}


def arcs(path):
    obj=json.loads(Path(path).read_bytes())
    demand(obj.get("meta",{}).get("branch_coverage") is True,
           "NOT_INSTRUMENTED_FOR_BRANCH_ARCS")
    matched=[(name,item) for name,item in obj.get("files",{}).items()
             if name.replace("\\","/")==MAIN or name.replace("\\","/").endswith("/"+MAIN)]
    demand(len(matched)==1,"MAIN_SOURCE_ARC_POPULATION_NOT_UNIQUE")
    name,item=matched[0]
    sm=item["summary"]
    denominator=sm["num_branches"]
    pairs=item.get("executed_branches")
    demand(isinstance(pairs,list) and
           all(isinstance(x,list) and len(x)==2 and
               all(type(y) is int for y in x) for x in pairs),
           "EXECUTED_ARC_IDENTITIES_MISSING")
    found={tuple(x) for x in pairs}
    demand(sm["covered_branches"]==len(found) and denominator>=len(found),
           "ARC_IDENTITY_DENOMINATOR_MISMATCH")
    demand(denominator==BASELINE_ELIGIBLE,
           "N33_MAIN_ELIGIBLE_DENOMINATOR_CHANGED")
    return {"file":name,"eligible":denominator,"covered":len(found),
            "statements":sm["num_statements"],
            "executed_arcs":sorted([list(x) for x in found])},found


def compare_coverage(base,observations):
    baseline,base_arcs=arcs(base)
    demand(baseline["covered"]==BASELINE_BRANCHES,
           "N32_BASELINE_27_ARCS_NOT_REPRODUCED")
    rows={}
    combined=set()
    for key,path in observations.items():
        measured,covered=arcs(path)
        combined.update(covered)
        rows[key]={"measured":measured["covered"],"eligible":measured["eligible"],
                   "new_vs_baseline":len(covered-base_arcs),
                   "source_file":measured["file"]}
    unpreserved=base_arcs-combined
    # The real N3.2 subprocess imports main.py (false __main__ branch).
    # The new real CLI cohorts execute main.py (true __main__ branch).
    # Preserve every other original branch, fail closed on any broader loss,
    # and bind the sole exception to the immutable main.py source blob.
    demand(not unpreserved or
           (unpreserved=={IMPORT_ONLY_MAIN_GUARD_ARC} and
            CLI_MAIN_GUARD_ARC in combined),
           "PREVIOUS_RUNTIME_ARCS_NOT_REACHED_BY_N33_COMMANDS")
    demand(len(combined)>len(base_arcs),"N33_NO_ACTUAL_MAIN_BRANCH_EXPANSION")
    return {
        "source_blob":BASELINE_BLOB,
        "baseline_head_population":"N3.2 actual 50-DAG warm broker; reproduced on candidate HEAD",
        "baseline":baseline,
        "baseline_covered_arcs":BASELINE_BRANCHES,
        "eligible_branch_arcs":BASELINE_ELIGIBLE,
        "positive_cohorts":rows,
        "union_executed_arcs":sorted([list(x) for x in combined]),
        "union_covered":len(combined),
        "newly_reached":len(combined-base_arcs),
        "previously_covered_preserved":len(base_arcs & combined),
        "baseline_only_import_guard_arcs":sorted([list(x) for x in unpreserved]),
        "source_union_including_real_baseline":len(base_arcs | combined),
        "regression_arcs":[],
        "coverage_target":60,
        "target_reached":len(combined)>=60,
        "whole_repository_coverage":None,
        "other_languages_covered":False,
        "instrumented_child_subprocess_branches":False,
    }


def plan_proof(path,head):
    path=Path(path)
    obj=json.loads(path.read_bytes())
    # Canonical broker.plan does not serialize the source SHA inside its
    # output. The caller's exact checkout + head must therefore be bound
    # in the enclosing receipt, NEVER invented inside broker-plan.json.
    demand(bool(SHA40.fullmatch(head or "")),"PLAN_HEAD_INVALID")
    demand(obj.get("schema")=="atlas.local-broker.plan.v1" and
           obj.get("dispatch_authorized") is False and
           obj.get("merge_authorized") is False,
           "PLAN_SCHEMA_OR_AUTHORITY_INVALID")
    demand(obj.get("time_basis")=="DETERMINISTIC_SOURCE_PLAN_NO_RUNTIME_OBSERVATION",
           "PLAN_NOT_DECLARED_AS_DETERMINISTIC_SOURCE")
    tasks=obj.get("tasks")
    demand(isinstance(tasks,list) and {x["id"] for x in tasks}==EXPECTED_TASKS,
           "PLAN_DAG_TASK_IDENTITY_MISMATCH")
    demand(all(isinstance(x.get("needs"),list) for x in tasks),
           "PLAN_DEPS_UNDECLARED")
    return {"sha256":sha(path.read_bytes()),"tasks":len(tasks),
            "declared_edges":sum(len(x["needs"]) for x in tasks)}


def build_proof(path,root,head,api):
    target=Path(path)
    manifest=api.verify_bundle(target,head,require_clean=True,source_root=root)
    demand(manifest["source_sha"]==head and
           manifest["remote_dispatch"] is False and
           manifest["merge_admission"]=="HOLD",
           "BUILD_AUTHORITY_OR_HEAD_MISMATCH")
    return {"manifest_sha256":sha((target/"manifest.json").read_bytes()),
            "members":len(manifest["files_sha256"]),
            "graph_members":sum(x.startswith("graphs/") for x in manifest["files_sha256"]),
            "verified_all_member_hashes":True}


def run_proof(out,source,head,workers,api):
    out=Path(out)
    obj=json.loads((out/"local-run.json").read_bytes())
    demand(obj.get("schema")=="atlas.local-broker.receipt.v1" and
           obj.get("success") is True and
           obj.get("source_changed_during_run") is False and
           obj.get("source_dirty") is False and
           obj.get("source_sha")==head and
           obj.get("outcome")=="LOCAL_GENERATORS_PASS",
           "ACTUAL_LOCAL_BROKER_RESULT_FIRST_RED")
    tasks=obj.get("tasks",{})
    demand(set(tasks)==EXPECTED_TASKS and all(x.get("state")=="succeeded"
           for x in tasks.values()),"LOCAL_DAG_INCOMPLETE_OR_RED")
    bounds=obj.get("bounds",{})
    metrics=obj.get("metrics",{})
    demand(bounds.get("workers")==workers and metrics.get("max_running",100)>0 and
           metrics["max_running"]<=workers and
           metrics.get("ready_wait_sample_count",0)>0,
           "ACTUAL_RUNNER_WORKERS_OR_QUEUE_INVALID")
    for name in sorted(EXPECTED_TASKS-{"validate"}):
        f=out/name
        actual=api.output_files(f)
        recorded=tasks[name]["result"]["output_files_sha256"]
        demand(actual==recorded and bool(recorded),
               "LOCAL_CHILD_PRODUCT_BYTES_UNVERIFIED_"+name)
    manifest=api.verify_bundle(out/"orchestration",head,require_clean=True,source_root=source)
    model=json.loads((out/"orchestration"/"atlas.json").read_bytes())
    api.validate_local_receipt(obj,model)
    demand(manifest["source_sha"]==head,"LOCAL_ORCHESTRATION_BUNDLE_DRIFT")
    return {"workers":workers,"source_head":head,
            "broker_tasks":len(tasks),
            "dependency_edges":sum(len(x["needs"]) for x in tasks.values()),
            "broker_elapsed_seconds":metrics["elapsed_seconds"],
            "max_running":metrics["max_running"],
            "ready_wait_sample_count":metrics["ready_wait_sample_count"],
            "ready_wait_p95_seconds":metrics.get("ready_wait_p95_seconds"),
            "verified_children":7,
            "verified_product_members":sum(len(tasks[x]["result"]["output_files_sha256"])
                                          for x in EXPECTED_TASKS-{"validate"}),
            "local_run_sha256":sha((out/"local-run.json").read_bytes()),
            "orchestration_manifest_sha256":sha(
                 (out/"orchestration"/"manifest.json").read_bytes()),
            "remote_dispatch":False,"merge_authorized":False}


def negative_controls(root,head,base,api,build_dir,plan,local_receipt):
    root,base=Path(root),Path(base)
    log=base/"logs"
    checks={}
    wrong=call(root,[sys.executable,str(root/MAIN),"plan","--root",str(root),
                     "--head","f"*40,"--out",str(base/"not-admitted")],
               log/"negative-head.log",30,expected=False)
    demand("checkout/head mismatch" in wrong["stderr"],
           "STALE_HEAD_REJECTED_FOR_UNRELATED_CAUSE")
    checks["stale_head"]="PASS_NATIVE_CLI"

    empty=base/"empty-source"
    empty.mkdir()
    missing=call(root,[sys.executable,str(root/MAIN),"check","--root",str(empty)],
                 log/"negative-missing.log",30,expected=False)
    demand("missing" in missing["stderr"].lower() or
           "no such file" in missing["stderr"].lower(),
           "MISSING_SOURCE_REJECTED_FOR_UNRELATED_CAUSE")
    checks["missing_source_input"]="PASS_NATIVE_CLI"

    malformed=base/"bad-snapshot.json"
    malformed.write_text("{broken-json",encoding="utf-8")
    bad=call(root,[sys.executable,str(root/MAIN),"plan","--root",str(root),
                   "--head",head,"--snapshot",str(malformed),
                   "--out",str(base/"badplan")],
             log/"negative-json.log",30,expected=False)
    demand("FAIL" in bad["stderr"],"MALFORMED_CONFIG_NOT_FAIL_CLOSED")
    checks["malformed_snapshot"]="PASS_NATIVE_CLI"

    # Tamper ONLY the emitted review bundle, never the checkout. Restore it
    # and prove the full unchanged manifest can again verify.
    member=Path(build_dir)/"style.css"
    original=member.read_bytes()
    member.write_bytes(original+b"\n/* intentional N3.3 tamper */\n")
    try:
        try:api.verify_bundle(build_dir,head)
        except ValueError as exc:
            demand("member hash mismatch" in str(exc),
                   "TAMPER_FAILURE_WRONG_CAUSAL_ORACLE")
        else:raise ValueError("TAMPERED_PRODUCT_FALSE_GREEN")
    finally:member.write_bytes(original)
    api.verify_bundle(build_dir,head,require_clean=True,source_root=root)
    checks["tampered_bundle_member"]="PASS_REAL_OUTPUT_VERIFIER"

    try:api.layers([{"id":"A"},{"id":"B"}],
                   [{"from":"A","to":"B"},{"from":"B","to":"A"}])
    except ValueError as exc:
        demand("cycle" in str(exc),"CYCLE_WRONG_CAUSAL_ORACLE")
    else:raise ValueError("DEPENDENCY_CYCLE_FALSE_GREEN")
    checks["dependency_cycle"]="PASS_REAL_KAHN_GUARD"

    bad_receipt=copy.deepcopy(local_receipt)
    bad_receipt["source_changed_during_run"]=True
    try:api.validate_local_receipt(bad_receipt,
                                  json.loads((Path(plan)/"atlas.json").read_bytes()))
    except ValueError as exc:
        demand("source drift" in str(exc),"SOURCE_DRIFT_WRONG_ORACLE")
    else:raise ValueError("SOURCE_DRIFT_FALSE_GREEN")
    checks["source_drift_receipt"]="PASS_REAL_RECEIPT_GUARD_NEGATIVE_FIXTURE"
    demand(set(checks)==set(CHECKS),"NEGATIVE_CONTROL_POPULATION_INCOMPLETE")
    return checks


def run(root,head,out):
    root,out=Path(root).resolve(),Path(out).resolve()
    demand(not out.is_relative_to(root) and not root.is_relative_to(out),
           "OUTPUT_OVERLAPS_CHECKOUT")
    demand(not out.exists() or not any(out.iterdir()),"OUTPUT_NOT_EMPTY")
    exact_root(root,head)
    api=producer(root,MAIN,"n33_main_owner")
    out.mkdir(parents=True,exist_ok=True)
    for d in ("coverage","logs","instruments","receipts"):
        (out/d).mkdir()
    initial=time.perf_counter()
    baseline_dir=out/"baseline-generated"
    baseline=run_coverage(root,head,N3,["--root",str(root),"--head",head,
                      "--pulses","4","--out",str(baseline_dir)],
                      "baseline",out,MAX_SECONDS["baseline"])
    baseline_raw=json.loads((baseline_dir/"n3_receipt.json").read_bytes())
    demand(len(baseline_raw.get("rows",[]))==50 and
           sum(x.get("accepted_fan_in") is True for x in baseline_raw["rows"])==24,
           "BASELINE_REAL_50_DAG_EXECUTION_INCOMPLETE")
    plan_dir=out/"plan"
    p=run_coverage(root,head,MAIN,["plan","--root",str(root),"--head",head,
                    "--out",str(plan_dir)],"plan",out,MAX_SECONDS["plan"])
    plan_a=plan_proof(plan_dir/"broker-plan.json",head)
    repeat_plan=out/"plan-repeat"
    call(root,[sys.executable,str(root/MAIN),"plan","--root",str(root),
               "--head",head,"--out",str(repeat_plan)],
         out/"logs"/"plan-repeat.log",MAX_SECONDS["plan"])
    demand(plan_a["sha256"]==sha((repeat_plan/"broker-plan.json").read_bytes()),
           "SOURCE_PLAN_NOT_DETERMINISTIC")
    bdir=out/"built"
    b=run_coverage(root,head,MAIN,["build","--root",str(root),"--head",head,
                    "--out",str(bdir)],"build",out,MAX_SECONDS["build"])
    build_a=build_proof(bdir,root,head,api)
    call(root,[sys.executable,str(root/MAIN),"check","--root",str(root),
               "--head",head,"--out",str(bdir)],
         out/"logs"/"check-built.log",90)
    # Do not redundantly rebuild the large artifact; require all members
    # under independent hash+size+source identity verification.
    cohorts={"plan":p,"build":b}
    runs={}
    observed=None
    for workers in (1,2,4):
        key="run"+str(workers)
        source=out/("source-worktree-"+str(workers))
        r=subprocess.run(["git","-C",str(root),"worktree","add","--detach",
                          str(source),head],capture_output=True,text=True,
                         timeout=180,check=False)
        demand(r.returncode==0,"ISOLATED_SOURCE_WORKTREE_CREATE_FAILED_"+key)
        try:
            demand(git(source,"status","--porcelain")=="",
                   "ISOLATED_SOURCE_NOT_CLEAN_"+key)
            actual=out/("runtime-"+str(workers))
            execution=run_coverage(source,head,MAIN,
                      ["run-local","--root",str(source),"--head",head,
                       "--workers",str(workers),"--out",str(actual)],
                       key,out,MAX_SECONDS[key])
            proof=run_proof(actual,source,head,workers,api)
            demand(git(source,"status","--porcelain")=="",
                   "GENERATORS_MODIFIED_SOURCE_WORKTREE_"+key)
            runs[key]={**proof,**{k:v for k,v in execution.items()
                         if k!="stderr"}}
            cohorts[key]=execution
            if observed is None:
                observed=(actual/"local-run.json",actual/"orchestration")
            shutil.copy2(actual/"local-run.json",out/"receipts"/(key+"-local-run.json"))
            shutil.copy2(actual/"orchestration"/"manifest.json",
                         out/"receipts"/(key+"-orchestration-manifest.json"))
        finally:
            subprocess.run(["git","-C",str(root),"worktree","remove","--force",
                            str(source)],capture_output=True,text=True,timeout=90,check=False)
    coverage=compare_coverage(cohorts_baseline(out),{
        key:value["coverage_path"] for key,value in cohorts.items()})
    demand(observed is not None,"NO_RUNTIME_TO_TEST_NEGATIVE_ORACLES")
    raw_run=json.loads(Path(observed[0]).read_bytes())
    controls=negative_controls(root,head,out,api,bdir,observed[1],raw_run)
    exact_root(root,head)
    # Only compact, independently reproducible receipts are exported.
    shutil.copy2(plan_dir/"broker-plan.json",out/"receipts"/"broker-plan.json")
    shutil.copy2(bdir/"manifest.json",out/"receipts"/"build-manifest.json")
    report={
      "schema":SCHEMA,"source":{"repository":"GBOGEB/pipeline-automation-hub",
        "head":head,"main_blob":BASELINE_BLOB},
      "baseline":{"source":"N3.2 real 50 DAGs on exact source",
        "head":head,"dags":50,"covered_arcs":BASELINE_BRANCHES,
        "eligible_arcs":BASELINE_ELIGIBLE,
        "runtime_log_sha256":baseline["log_sha256"]},
      "coverage":coverage,
      "observed":{"plan":plan_a,"build":build_a,"runtime_modes":runs,
                  "negative_controls":controls,
                  "negative_total":len(controls),
                  "total_verified_registered_generator_runs":24,
                  "coverage_cohort_independence":"SEPARATE_FILES_SAME_RUNNER"},
      "clock":{"wall_seconds":round(time.perf_counter()-initial,6),
               "setup_install_seconds":None,"billable_runner_minutes":None,
               "cache_hit":None,"independent_native_run_count":1},
      "governance":{"max_broker_workers_unchanged":4,"remote_dispatch":False,
                    "whole_repo_coverage":None,"fleet_capacity_proven":False,
                    "owner_approved":False,"merge_authorized":False,
                    "engineering_credit_delta":0},
    }
    (out/"n33_receipt.json").write_bytes(canonical(report))
    members=[Path("n33_receipt.json")]+sorted(
       [p.relative_to(out) for folder in ("coverage","receipts")
        for p in (out/folder).rglob("*") if p.is_file()])
    manifest={"schema":"method-atlas.n33.member-manifest.v1",
              "source_head":head,"source_blob":BASELINE_BLOB,
              "files_sha256":{x.as_posix():sha((out/x).read_bytes()) for x in members},
              "merge_authorized":False,"source_files_modified":False}
    (out/"n33_manifest.json").write_bytes(canonical(manifest))
    print(json.dumps({"status":"N33_EXECUTED_SOURCE_CLI_COVERAGE_PASS",
                      "head":head,"previous":BASELINE_BRANCHES,
                      "new":coverage["newly_reached"],
                      "union":coverage["union_covered"],
                      "eligible":BASELINE_ELIGIBLE,"target":coverage["target_reached"],
                      "all_modes":{k:round(v["broker_elapsed_seconds"],4)
                                   for k,v in runs.items()},
                      "negative_controls":len(controls),
                      "no_merger_authority":True},sort_keys=True))
    return report


def cohorts_baseline(out):
    return Path(out)/"coverage"/"baseline.json"


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--head",required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args(argv)
    run(args.root,args.head,args.out)


if __name__=="__main__":
    main()
