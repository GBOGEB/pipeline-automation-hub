#!/usr/bin/env python3
"""N+6 replay-safe first-RED occurrence/root ledger (PUBLIC Hub only).

A completed GREEN job is a diagnostic displacement, never automatic root
closure. Same-head reruns, A->B->A regressions, and zero-step queued jobs
must remain independently visible. No GitHub write or alert action.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

SCHEMA="jade.taxonomy-root-occurrence.v1"
INPUT="jade.first-red-occurrences.v1"
OWNER="GBOGEB/pipeline-automation-hub"
HEX=re.compile(r"^[a-f0-9]{40}$",re.I)
FINGERPRINT=re.compile(r"^[a-f0-9]{64}$",re.I)
STATUS={"RED","GREEN","SKIPPED","QUEUED"}


def instant(value):
    if not isinstance(value,str):
        raise ValueError("TIMESTAMP_MISSING")
    try:
        t=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:
        raise ValueError("TIMESTAMP_INVALID") from exc
    if t.tzinfo is None:
        raise ValueError("TIMESTAMP_UNZONED")
    return t


def calculate(payload: dict) -> dict:
    if not isinstance(payload,dict) or payload.get("schema")!=INPUT:
        raise ValueError("SCHEMA_MISMATCH")
    if payload.get("source_repository")!=OWNER:
        raise ValueError("PUBLIC_HUB_ONLY")
    e=payload.get("events")
    if not isinstance(e,list):
        raise ValueError("EVENTS_NOT_LIST")
    receipt_head=payload.get("source_head")
    if not isinstance(receipt_head,str) or not HEX.fullmatch(receipt_head):
        raise ValueError("SOURCE_HEAD_INVALID")
    ordered=[]
    seen={}
    occurrence_classes=Counter()
    for i,row in enumerate(e):
        if not isinstance(row,dict):
            raise ValueError("EVENT_NOT_OBJECT")
        head=row.get("head_sha")
        if not isinstance(head,str) or not HEX.fullmatch(head):
            raise ValueError("EVENT_HEAD_INVALID")
        fingerprint=row.get("root_fingerprint")
        if not isinstance(fingerprint,str) or not FINGERPRINT.fullmatch(fingerprint):
            raise ValueError("ROOT_UNBOUND")
        status=row.get("conclusion")
        if status not in STATUS:
            raise ValueError("STATUS_UNKNOWN")
        wave=row.get("wave")
        if type(wave) is not int or wave<0 or wave>64:
            raise ValueError("WAVE_INVALID")
        run=row.get("run_id")
        attempt=row.get("attempt")
        job=row.get("job_id")
        step=row.get("step_id")
        if any(type(n) is not int or n<1 for n in (run,attempt,job,step)):
            raise ValueError("RUN_JOB_STEP_IDENTITY_INVALID")
        steps=row.get("steps_executed")
        if type(steps) is not int or steps<0:
            raise ValueError("EXECUTION_COUNT_INVALID")
        if status in ("RED","GREEN") and steps==0:
            raise ValueError("ZERO_STEP_CANNOT_BE_TERMINAL_PROOF")
        if status=="QUEUED" and steps!=0:
            raise ValueError("QUEUED_WITH_EXECUTION_COUNT")
        when=instant(row.get("observed_at"))
        delivery=(run,attempt,job,step)
        semantic=(head,fingerprint,status,wave,steps,when.isoformat())
        if delivery in seen:
            if seen[delivery]!=semantic:
                raise ValueError("MUTATED_DELIVERY_IDENTITY")
            occurrence_classes["duplicate_delivery_ignored"]+=1
            continue
        seen[delivery]=semantic
        ordered.append((when,delivery,row))
    ordered.sort(key=lambda x:(x[0],x[1]))
    states=defaultdict(lambda:{"transitions":[],"heads":set(),"red":0,"green":0,"queued":0})
    unique_events=[]
    for when,delivery,row in ordered:
        root=row["root_fingerprint"]
        status=row["conclusion"]
        state=states[root]
        state["heads"].add(row["head_sha"])
        state["transitions"].append(status)
        state["red"]+=int(status=="RED")
        state["green"]+=int(status=="GREEN")
        state["queued"]+=int(status in ("QUEUED","SKIPPED"))
        occurrence_classes[status]+=1
        unique_events.append({
            "root":root,"wave":row["wave"],"head":row["head_sha"],
            "run_id":row["run_id"],"attempt":row["attempt"],"job_id":row["job_id"],
            "step_id":row["step_id"],"conclusion":status,
            "executed_steps":row["steps_executed"],
            "timestamp":when.isoformat()})
    summary=[]
    for fingerprint, r in sorted(states.items()):
        seq=r["transitions"]
        latest=seq[-1]
        transitions=sum(a!=b for a,b in zip(seq,seq[1:]))
        regression=any(a=="GREEN" and b=="RED" for a,b in zip(seq,seq[1:]))
        displaced=(r["red"]>0 and latest=="GREEN")
        summary.append({"root_fingerprint":fingerprint,
            "terminal_observation":latest,
            "diagnostic_red_displaced":displaced,
            "regression_after_green":regression,
            "status_flips":transitions,
            "head_count":len(r["heads"]),
            "red_occurrences":r["red"],"green_occurrences":r["green"],
            "nonterminal_occurrences":r["queued"],
            "verified_root_closed":False})
    out={
        "schema":SCHEMA,"source_repository":OWNER,"source_head":receipt_head,
        "raw_delivery_count":len(e),"deduplicated_occurrences":len(unique_events),
        "duplicate_deliveries":occurrence_classes["duplicate_delivery_ignored"],
        "unique_roots":len(summary),
        "currently_red_observed":sum(x["terminal_observation"]=="RED" for x in summary),
        "displaced_diagnostic_roots":sum(x["diagnostic_red_displaced"] for x in summary),
        "regression_roots":sum(x["regression_after_green"] for x in summary),
        "latest_wave":max((x["wave"] for x in unique_events),default=None),
        "root_closure_credit":0,"formal_credit_delta":0,"merge_admission":"HOLD",
        "absence_is_not_closure":True,
        "root_summary":summary,"events":unique_events,
        "source_grade":"OBSERVED_SYNTHETIC_OR_READBACK_NOT_OWNER_DISPOSITION",
        "authority_transfer":False}
    out["receipt_sha256"]=hashlib.sha256(json.dumps(
        out,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return out


def main(argv=None):
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--in",dest="source",required=True,type=Path)
    a.add_argument("--out",required=True,type=Path)
    opts=a.parse_args(argv)
    out=calculate(json.loads(opts.source.read_text(encoding="utf-8")))
    opts.out.parent.mkdir(parents=True,exist_ok=True)
    opts.out.write_text(json.dumps(out,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print("ROOT_OCCURRENCES",out["deduplicated_occurrences"],"ROOTS",out["unique_roots"])
    return 0


if __name__=="__main__":
    raise SystemExit(main())
