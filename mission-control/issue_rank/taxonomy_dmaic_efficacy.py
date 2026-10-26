#!/usr/bin/env python3
"""N+7-12 MIP/DMAIC measured scaling controller: advisory, no runner dispatch.

Gate increases in coverage against a MATCHED source cohort and tests with
actual executed steps. Do not promote a positive numerator with changed
denominator, stale head, queue saturation or any real first-red.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path

INPUT="jade.dmaic-measured-waves.v1"
SCHEMA="jade.dmaic-decision.v1"
SHA=re.compile(r"^[0-9a-f]{40}$",re.I)
MAX_WAVES=12
MAX_QUEUED=20


def parse_time(s):
    if not isinstance(s,str):
        raise ValueError("TIME_MISSING")
    try:
        t=datetime.fromisoformat(s.replace("Z","+00:00"))
    except ValueError as exc:
        raise ValueError("TIME_INVALID") from exc
    if t.tzinfo is None:
        raise ValueError("TIMEZONE_MISSING")
    return t


def wilson(good:int,total:int,z:float=1.96):
    if total==0:
        return None
    p=good/total
    denom=1+z*z/total
    centre=(p+z*z/(2*total))/denom
    spread=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/denom
    return {"estimate":round(p,6),"lower":round(max(0,centre-spread),6),
            "upper":round(min(1,centre+spread),6),"denominator":total}


def assess(source:dict) -> dict:
    if not isinstance(source,dict) or source.get("schema")!=INPUT:
        raise ValueError("UNKNOWN_SCHEMA")
    waves=source.get("waves")
    if not isinstance(waves,list) or not waves or len(waves)>MAX_WAVES+1:
        raise ValueError("INVALID_WAVE_POPULATION")
    cohort=source.get("cohort_id")
    if not isinstance(cohort,str) or not re.fullmatch(r"[a-z0-9][a-z0-9._:-]{2,79}",cohort):
        raise ValueError("COHORT_UNBOUND")
    previous=None
    parsed=[]
    for i,w in enumerate(waves):
        if not isinstance(w,dict) or type(w.get("wave")) is not int or w["wave"]!=i:
            raise ValueError("UNMATCHED_WAVE_INDEX")
        if w.get("cohort_id")!=cohort:
            raise ValueError("COHORT_CHANGED")
        if not isinstance(w.get("file_roster_sha256"),str) or not re.fullmatch(r"[a-f0-9]{64}",w["file_roster_sha256"],re.I):
            raise ValueError("FILE_ROSTER_NOT_PINNED")
        if i>0 and w["file_roster_sha256"]!=waves[0]["file_roster_sha256"]:
            raise ValueError("FILE_ROSTER_CHANGED")
        if not isinstance(w.get("head_sha"),str) or not SHA.fullmatch(w["head_sha"]):
            raise ValueError("HEAD_NOT_PINNED")
        now=parse_time(w.get("observed_at"))
        if previous and now<=previous:
            raise ValueError("NON_MONOTONIC_TIME")
        previous=now
        required=("covered_lines","total_lines","zero_covered_files",
                  "tests_passed","tests_failed","tests_skipped",
                  "executed_jobs","zero_step_jobs","queue_depth","in_progress")
        if any(type(w.get(k)) is not int or w[k]<0 for k in required):
            raise ValueError("INVALID_MEASURED_COUNTERS")
        if not 0<w["total_lines"] or w["covered_lines"]>w["total_lines"]:
            raise ValueError("COVERAGE_DENOMINATOR_INVALID")
        if w["tests_passed"]+w["tests_failed"]==0 and w["executed_jobs"]>0:
            raise ValueError("ZERO_TEST_JOBS_NOT_CREDITABLE")
        if w["executed_jobs"]==0 and (w["tests_passed"]>0 or w["tests_failed"]>0):
            raise ValueError("UNEXECUTED_TEST_PROOF")
        if w["zero_step_jobs"]>w["executed_jobs"]:
            raise ValueError("ZERO_STEP_GT_JOBS")
        parsed.append({"wave":i,"head_sha":w["head_sha"],
                       "file_roster_sha256":w["file_roster_sha256"],
                       "covered_lines":w["covered_lines"],
                       "total_lines":w["total_lines"],
                       "coverage":round(w["covered_lines"]/w["total_lines"],6),
                       "zero_covered_files":w["zero_covered_files"],
                       "tests_passed":w["tests_passed"],
                       "tests_failed":w["tests_failed"],
                       "tests_skipped":w["tests_skipped"],
                       "executed_jobs":w["executed_jobs"],
                       "zero_step_jobs":w["zero_step_jobs"],
                       "queue_depth":w["queue_depth"],
                       "in_progress":w["in_progress"]})
    first,last=parsed[0],parsed[-1]
    comparable=(first["total_lines"]==last["total_lines"] and
                all(p["total_lines"]==first["total_lines"] for p in parsed))
    any_red=any(p["tests_failed"]>0 for p in parsed)
    congested=last["queue_depth"]>MAX_QUEUED
    # Three consecutive *observed* waves with identical coverage AND
    # zero-file count mean two consecutive N+1=N transitions.
    stable=(len(parsed)>=3 and all(
        parsed[i]["covered_lines"]==parsed[i-1]["covered_lines"] and
        parsed[i]["zero_covered_files"]==parsed[i-1]["zero_covered_files"]
        for i in (-1,-2)))
    changes={
        "matched_denominator":comparable,
        "coverage_delta_pp":round((last["coverage"]-first["coverage"])*100,4)
          if comparable else None,
        "zero_covered_files_reduction":first["zero_covered_files"]-last["zero_covered_files"]
          if comparable else None,
        "queue_depth_delta":last["queue_depth"]-first["queue_depth"],
        "latest_test_yield_95pct_wilson":wilson(last["tests_passed"],
             last["tests_passed"]+last["tests_failed"]),
        "first_red_seen":any_red,
        "zero_step_jobs_total":sum(x["zero_step_jobs"] for x in parsed),
        "root_burndown_verified":None,
    }
    reasons=[]
    if not comparable: reasons.append("UNMATCHED_COVERAGE_DENOMINATOR")
    if any_red: reasons.append("FIRST_RED_EXISTS")
    if congested: reasons.append("QUEUE_PRESSURE_EXCEEDS_20")
    if any(p["zero_step_jobs"]>0 for p in parsed): reasons.append("ZERO_STEP_EVIDENCE")
    if stable: reasons.append("THREE_WAVES_STABLE_STOP_RULE")
    if last["wave"]>=MAX_WAVES: reasons.append("MAX_12_WAVES")
    positive=(comparable and changes["coverage_delta_pp"] is not None and
              (changes["coverage_delta_pp"]>0 or changes["zero_covered_files_reduction"]>0))
    action=("HOLD" if reasons else "SCALE_BOUNDED" if positive else "PROVE_NEXT_SMALL_SLICE")
    report={
        "schema":SCHEMA,"cohort_id":cohort,"waves_observed":len(parsed),
        "latest_wave":last["wave"],"max_wave":MAX_WAVES,
        "dmaic":{"define":"SAME_COHORT_COVERAGE_AND_FIRST_RED",
                 "measure":"EXACT_HEAD_TERMINAL_NATIVE_ONLY",
                 "analyse":"NO_CAUSAL_ATTRIBUTION_FROM_COUNT_DELTAS",
                 "improve":"BOUNDED_NON_COMPENSATING_RETEST",
                 "control":"NO_AUTOMERGE_NO_ADMISSION"},
        "mip":{"progression":changes,"interventions_not_yet_causally_validated":True},
        "next_action":action,"next_wave":last["wave"]+1 if action!="HOLD" else None,
        "stop_reasons":reasons,
        "merge_admission":"HOLD","root_closure_credit":0,"formal_credit_delta":0,
        "authority_transfer":False}
    report["receipt_sha256"]=hashlib.sha256(json.dumps(
        report,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return report


def main(argv=None):
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--in",dest="input",type=Path,required=True)
    a.add_argument("--out",type=Path,required=True)
    args=a.parse_args(argv)
    report=assess(json.loads(args.input.read_text(encoding="utf-8")))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("DMAIC",report["next_action"],report["stop_reasons"])
    return 0


if __name__=="__main__":
    raise SystemExit(main())
