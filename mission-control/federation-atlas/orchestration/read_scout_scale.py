#!/usr/bin/env python3
"""PAH read-only scout scaling: existing metrics owner, no dispatch.

Compares complete matched 16 and 32 read-only scout observations. Never
measures queues itself, registers a watcher, raises mutator limits, or treats
self-reported native identities as authenticated. Missing input is HOLD.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path

SCHEMA="method-atlas.read-scout-scale-observation.v1"
OUTPUT="method-atlas.read-scout-scale-advisory.v1"
METRIC_OWNER="mission-control/jade_temple/devops/actions_metrics.py"
REPO="GBOGEB/pipeline-automation-hub"
SOURCE_HEAD_FIELD="head_sha"
HEX40=set("0123456789abcdef")
HEX64=HEX40
MODES={"scouts16":16,"scouts32":32,"optimized16":16}


def sha(s,size):
    return isinstance(s,str) and len(s)==size and all(c in HEX40 for c in s)


def integer(value,minimum=0):
    return type(value) is int and value>=minimum


def positive(value):
    return type(value) in (int,float) and math.isfinite(value) and value>0


def nonnegative(value):
    return type(value) in (int,float) and math.isfinite(value) and value>=0


def require(ok,code):
    if not ok:
        raise ValueError(code)


def observation_trial(row,mode,seen):
    require(isinstance(row,dict),"INVALID_TRIAL")
    p=row.get("pulse_id")
    require(integer(p,1),"INVALID_PULSE_ID")
    require(sha(row.get("head_sha"),40) and sha(row.get("workload_sha256"),64) and
            sha(row.get("environment_sha256"),64),"SOURCE_OR_WORKLOAD_UNBOUND")
    native=row.get("native")
    require(isinstance(native,dict),"NATIVE_IDENTITY_MISSING")
    identity=(native.get("run_id"),native.get("attempt"),native.get("job_id"))
    require(all(integer(x,1) for x in identity),"NATIVE_IDENTITY_INVALID")
    require(identity not in seen,"NATIVE_EXECUTION_REUSED")
    seen.add(identity)
    require(native.get("status")=="completed" and
            native.get("conclusion") in ("success","failure","cancelled"),
            "TERMINAL_OUTCOME_NOT_OBSERVED")
    require(integer(native.get("steps")),"NATIVE_STEPS_INVALID")
    metrics=row.get("metrics")
    require(isinstance(metrics,dict) and metrics.get("owner")==METRIC_OWNER,
            "CANONICAL_METRIC_OWNER_UNBOUND")
    require(integer(metrics.get("accepted_outputs")) and
            positive(metrics.get("wall_seconds")) and
            nonnegative(metrics.get("runner_seconds")) and
            nonnegative(metrics.get("queue_p95_seconds")) and
            integer(metrics.get("first_red")) and
            integer(metrics.get("root_recurrences")) and
            nonnegative(metrics.get("cache_hit_ratio")) and
            metrics["cache_hit_ratio"]<=1,
            "METRIC_POPULATION_INVALID")
    return {"pulse":p,"source":row["head_sha"],
            "workload":row["workload_sha256"],"environment":row["environment_sha256"],
            "native":identity,"conclusion":native["conclusion"],"steps":native["steps"],
            "metrics":metrics,"workers":MODES[mode]}


def evaluate(obs):
    if obs is None:
        return {"schema":OUTPUT,"classification":"HOLD_NO_MATCHED_NATIVE_OBSERVATIONS",
                "required_cohorts":["scouts16","scouts32"],"minimum_matched_pulses":4,
                "native_identity_authenticated":False,"dispatch_authorized":False,
                "merge_authorized":False,"mutator_workers_changed":False,
                "engineering_credit_delta":0,"relative_metrics":None}
    require(isinstance(obs,dict) and obs.get("schema")==SCHEMA,"BAD_OBSERVATION_SCHEMA")
    require(obs.get("repository")==REPO and obs.get("metric_owner")==METRIC_OWNER,
            "WRONG_SOURCE_METRIC_OWNER_OR_REPOSITORY")
    require(all(obs.get(k) is False for k in
                ("dispatch_authorized","merge_authorized","authority_transfer")),
            "AUTHORITY_ESCALATION")
    cohorts=obs.get("cohorts")
    require(isinstance(cohorts,dict) and
            {"scouts16","scouts32"}.issubset(cohorts) and
            set(cohorts).issubset(MODES),"INVALID_SCOUT_COHORTS")
    seen=set()
    population={}
    for mode,records in cohorts.items():
        require(isinstance(records,list) and len(records)==4,
                "FOUR_PULSES_REQUIRED")
        rows=[observation_trial(x,mode,seen) for x in records]
        pulses=[r["pulse"] for r in rows]
        require(pulses==list(range(pulses[0],pulses[0]+4)),
                "PULSES_NOT_CONSECUTIVE_OR_ORDERED")
        population[mode]=rows
    baseline=population["scouts16"]
    reasons=[]
    all_pulses=[x["pulse"] for x in baseline]
    for mode,records in population.items():
        if [x["pulse"] for x in records]!=all_pulses:
            reasons.append("PULSE_PAIRING_MISMATCH")
        for b,r in zip(baseline,records):
            if (r["source"],r["workload"],r["environment"])!=(
                    b["source"],b["workload"],b["environment"]):
                reasons.append("INCOMPARABLE_HEAD_WORKLOAD_OR_ENVIRONMENT")
    metrics={}
    for mode,records in population.items():
        eligible=sum(x["metrics"]["accepted_outputs"] for x in records)
        wall=sum(x["metrics"]["wall_seconds"] for x in records)
        spend=sum(x["metrics"]["runner_seconds"] for x in records)
        metrics[mode]={"workers":MODES[mode],"pulses":4,
                       "accepted_outputs":eligible,
                       "receipts_per_wall_second":round(eligible/wall,6),
                       "runner_seconds_per_accepted_output":round(spend/eligible,6) if eligible else None,
                       "queue_p95_values_seconds":[x["metrics"]["queue_p95_seconds"] for x in records],
                       "cache_hit_ratios":[x["metrics"]["cache_hit_ratio"] for x in records],
                       "first_red":sum(x["metrics"]["first_red"] for x in records),
                       "root_recurrences":sum(x["metrics"]["root_recurrences"] for x in records),
                       "executed_jobs":sum(x["steps"]>0 for x in records),
                       "native_outcome_counts":{state:sum(x["conclusion"]==state for x in records)
                                                for state in ("success","failure","cancelled")}}
        if eligible==0:
            reasons.append("ZERO_ACCEPTED_OUTPUTS_"+mode.upper())
        if any(x["steps"]==0 for x in records):
            reasons.append("ZERO_STEP_EXECUTION_"+mode.upper())
        if any(x["conclusion"]!="success" for x in records):
            reasons.append("NON_SUCCESS_NATIVE_OUTCOME_"+mode.upper())
        if metrics[mode]["first_red"] or metrics[mode]["root_recurrences"]:
            reasons.append("RED_OR_RECURRENCE_"+mode.upper())
    for mode,rows in population.items():
        if mode=="scouts16":
            continue
        for old,new in zip(baseline,rows):
            if new["metrics"]["queue_p95_seconds"]>old["metrics"]["queue_p95_seconds"]:
                reasons.append("PAIRWISE_QUEUE_P95_REGRESSION_"+mode.upper())
    ratio=None
    if metrics["scouts16"]["receipts_per_wall_second"]>0:
        ratio=round(metrics["scouts32"]["receipts_per_wall_second"]/
                    metrics["scouts16"]["receipts_per_wall_second"],4)
    if ratio is not None and ratio<=1.0:
        reasons.append("NO_OBSERVED_THROUGHPUT_GAIN")
    unit16=metrics["scouts16"]["runner_seconds_per_accepted_output"]
    unit32=metrics["scouts32"]["runner_seconds_per_accepted_output"]
    if unit16 is not None and unit32 is not None and unit32>unit16:
        reasons.append("COST_PER_OUTPUT_REGRESSION")
    if "optimized16" not in population:
        reasons.append("PROCESS_OPTIMIZATION_COHORT_UNOBSERVED")
    # No self-reported run ids are authenticated merely by source-controlled JSON.
    reasons.append("NATIVE_RUN_JOB_STEP_READBACK_REQUIRED")
    decision="HOLD" if any(x for x in reasons if x!="PROCESS_OPTIMIZATION_COHORT_UNOBSERVED" and
                        x!="NATIVE_RUN_JOB_STEP_READBACK_REQUIRED") else "ADVISORY_ONLY"
    return {"schema":OUTPUT,"classification":decision,
            "repository":REPO,"metric_owner":METRIC_OWNER,
            "cohorts":metrics,"read_scout_32_to_16_throughput_ratio":ratio,
            "reasons":sorted(set(reasons)),"native_identity_authenticated":False,
            "source_comparability_asserted_not_verified":True,
            "dispatch_authorized":False,"merge_authorized":False,
            "mutator_workers_changed":False,"engineering_credit_delta":0,
            "scale_eligible_for_owner_decision":False,
            "interpretation":"Native source owner must authenticate every reported job before any scale decision."}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input",type=Path)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args(argv)
    input_data=json.loads(args.input.read_text()) if args.input else None
    result=evaluate(input_data)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"status":result["classification"],
                      "native_authenticated":False,"output":str(args.out)},sort_keys=True))
    return 0 if result["classification"] in ("HOLD","HOLD_NO_MATCHED_NATIVE_OBSERVATIONS","ADVISORY_ONLY") else 2


if __name__=="__main__":
    raise SystemExit(main())
