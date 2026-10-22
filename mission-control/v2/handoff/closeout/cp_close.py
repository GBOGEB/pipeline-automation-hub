#!/usr/bin/env python3
"""CP.CLOSE: deterministic sanitized GitHub-first conversation handover."""
import argparse
import csv
import hashlib
import io
import json
import re
import statistics
import sys
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

SCHEMA = "missioncontrol.cp_close.intake.v1"
OWNER = "GBOGEB/pipeline-automation-hub"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
STATES = {"TODO","ACTIVE","IN_PR","HOLD","DEFER","DONE","CONTROL"}
RESULTS = ["START_HERE.md","LOSSLESS_HANDOVER.md","NEXT_CHAT_DROPIN.md",
           "STATE.json","CHAT_STATS.json","INTENT_ACTION_LEDGER.json",
           "BD_QUEUE_READONLY.json","TODO_BD_QUEUE.csv"]

def die(message):
    raise ValueError("CP_CLOSE_FAIL_CLOSED: "+message)

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def encode(obj):
    return (json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode("utf-8")

def owner_url(s):
    p=urlparse(s)
    return p.scheme=="https" and p.netloc=="github.com" and p.path.startswith("/GBOGEB/") and not p.username

def validate(i):
    if i.get("schema")!=SCHEMA or i.get("privacy")!="SANITIZED_SEMANTIC_ONLY":
        die("schema/privacy")
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9_.-]{2,80}",i.get("session_alias","")):
        die("session identity")
    src=i.get("source",{})
    if src.get("repository")!=OWNER or src.get("default_branch")!="master" or not HEX40.fullmatch(src.get("observed_main_sha","")):
        die("source identity must be existing master and full SHA")
    if i.get("merge_admission")!="HOLD" or i.get("security_waiver") is not False or i.get("authority_transfer") is not False:
        die("cannot transfer authority or admit merges")
    if i.get("complete_transcript_available") is not False or i.get("total_chat_user_prompts") is not None or i.get("total_chat_messages") is not None:
        die("unseen chat counts must remain UNKNOWN")
    if i.get("capture_granularity") not in {"DATE_ONLY","TIMESTAMP_OBSERVED"}:
        die("capture time precision")
    try:
        datetime.fromisoformat(i["capture_date"])
    except (ValueError,KeyError):
        die("capture date")
    for key in ("intents","actions","decisions","insights","pr_snapshot","external_issues","metric_observations","bd_focus"):
        if not isinstance(i.get(key),list):
            die("required array "+key)
    if {"raw_transcript","messages","password","api_key","private_reasoning"} & set(i):
        die("raw/private content may not be committed")
    action_ids=[a.get("id") for a in i["actions"]]
    if any(not isinstance(x,str) or not re.fullmatch(r"SC-A[0-9]{3}",x) for x in action_ids) or len(set(action_ids))!=len(action_ids):
        die("duplicate/invalid action identities")
    graph={}
    for a in i["actions"]:
        if a.get("state") not in STATES or a.get("priority") not in {"P0","P1","P2","P3"}:
            die("action state/priority")
        if not a.get("owner") or not a.get("summary") or not a.get("done_when"):
            die("action needs owner summary completion condition")
        if not isinstance(a.get("evidence_urls"),list) or not all(owner_url(x) for x in a["evidence_urls"]):
            die("action evidence links")
        deps=a.get("depends_on")
        if not isinstance(deps,list) or any(d not in action_ids for d in deps) or a["id"] in deps:
            die("orphan/self dependency")
        graph[a["id"]]=deps
    visited,active=set(),set()
    def visit(node):
        if node in active:
            die("action DAG cycle")
        if node not in visited:
            active.add(node)
            for parent in graph[node]:
                visit(parent)
            active.remove(node)
            visited.add(node)
    for node in graph:
        visit(node)
    intent_ids=[q.get("id") for q in i["intents"]]
    if len(set(intent_ids))!=len(intent_ids):
        die("duplicate intents")
    for q in i["intents"]:
        if not re.fullmatch(r"SC-I[0-9]{3}",q.get("id","")) or not q.get("summary"):
            die("invalid intent")
        if q.get("source_class") not in {"USER_VISIBLE_RECONSTRUCTED","SOURCE_BOUND_REFERENCE","USER_EXPLICIT_INTAKE"}:
            die("intent source not identified")
        if not isinstance(q.get("actions"),list) or any(n not in action_ids for n in q["actions"]):
            die("intent to action orphan")
        if q.get("original_chat_message_id") is not None or q.get("original_chat_timestamp") is not None:
            die("original user chat IDs/timestamps unproven")
    for q in i["decisions"]:
        if not q.get("name") or not q.get("rationale") or not owner_url(q.get("evidence_url","")):
            die("decision needs evidence/rationale")
    for q in i["insights"]:
        if not q.get("observation") or not q.get("implication") or not owner_url(q.get("evidence_url","")):
            die("insight needs evidence/implication")
    for p in i["pr_snapshot"]:
        if not isinstance(p.get("number"),int) or p.get("state") not in {"OPEN","MERGED","CLOSED_UNMERGED"}:
            die("PR type/state")
        if not owner_url(p.get("url","")) or not HEX40.fullmatch(str(p.get("head_sha",""))):
            die("PR head/link")
        if p["state"]=="MERGED" and not HEX40.fullmatch(str(p.get("merge_sha",""))):
            die("merged PR requires merge SHA")
    for issue in i["external_issues"]:
        if not owner_url(issue.get("url","")) or not issue.get("owner_lane"):
            die("owner-scoped issue")
    for q in i["metric_observations"]:
        if not q.get("metric") or not q.get("unit") or not q.get("population") or not owner_url(q.get("source","")):
            die("metric scope/evidence")
        a,b=q.get("numerator"),q.get("denominator")
        if (a is None)!=(b is None):
            die("metric numerator/denominator incomplete")
        if a is not None and (not isinstance(a,(int,float)) or not isinstance(b,(int,float)) or b<=0 or a<0 or a>b):
            die("invalid metric counts")
    if len(set(i["bd_focus"]))!=len(i["bd_focus"]) or not all(re.fullmatch(r"CPQ-\d{3}",x) for x in i["bd_focus"]):
        die("canonical BD keys only")

def prompt_stats(messages_path):
    result={"source":"NOT_SUPPLIED","full_chat_total_prompts":None,"full_chat_total_messages":None,
            "sample_user_prompts":None,"sample_assistant_messages":None,"sample_tool_messages":None,
            "sample_total_messages":None,"sample_user_words":None,"sample_user_characters":None,
            "sample_user_words_median":None,"sample_user_words_p95":None,
            "timestamp_coverage":None,"duration_hours":None,"model_tokens":None,
            "latency_ms_p95":None,"completeness":"UNAVAILABLE","provider_verified":False}
    if messages_path is None:
        return result
    data=json.loads(messages_path.read_text("utf-8"))
    if data.get("schema")!="missioncontrol.user_supplied_messages.v1" or not isinstance(data.get("messages"),list) or not data["messages"]:
        die("optional transcript shape invalid")
    counts=Counter()
    lengths=[]
    timestamps=[]
    totalchars=0
    for m in data["messages"]:
        if m.get("role") not in {"user","assistant","system","tool","developer"} or not isinstance(m.get("text"),str):
            die("bad supplied role/text")
        counts[m["role"]]+=1
        if m["role"]=="user":
            lengths.append(len(m["text"].split()))
            totalchars+=len(m["text"])
        if m.get("created_at"):
            try:
                t=datetime.fromisoformat(m["created_at"].replace("Z","+00:00"))
            except ValueError:
                die("bad time")
            if t.tzinfo is None:
                die("time requires timezone")
            timestamps.append(t)
    lengths.sort()
    coverage=len(timestamps)==len(data["messages"])
    result.update({"source":"USER_SUPPLIED_LOCAL_COUNT_ONLY",
                   "sample_user_prompts":counts["user"],"sample_assistant_messages":counts["assistant"],
                   "sample_tool_messages":counts["tool"],"sample_total_messages":len(data["messages"]),
                   "sample_user_words":sum(lengths),"sample_user_characters":totalchars,
                   "sample_user_words_median":statistics.median(lengths) if lengths else None,
                   "sample_user_words_p95":lengths[min(len(lengths)-1,(95*len(lengths)+99)//100-1)] if len(lengths)>=20 else None,
                   "timestamp_coverage":coverage,
                   "duration_hours":round((max(timestamps)-min(timestamps)).total_seconds()/3600,3) if coverage else None,
                   "completeness":"SUPPLIED_DECLARED_COMPLETE_NOT_PROVIDER_VERIFIED" if data.get("declared_complete") else "SUPPLIED_SUBSET_ONLY"})
    return result

def bd_snapshot(path,keys):
    raw=path.read_bytes()
    d=json.loads(raw)
    if d.get("schema")!="missioncontrol.code_purple.bd_queue.v1" or d.get("authority_transfer") is not False:
        die("canonical BD input not valid")
    idx={q["id"]:q for q in d["items"]}
    if len(idx)!=len(d["items"]) or any(k not in idx for k in keys):
        die("invalid canonical BD focus")
    focus=[]
    for k in keys:
        q=idx[k]
        history=q.get("history") or []
        if not history:
            die("no BD source history")
        last=history[-1]
        focus.append({"id":k,"title":q["title"],"severity":q["severity"],
                      "state":last["state"],"flow":last["flow"],"at":last["at"],
                      "done_when":q["done_when"],"control_when":q["control_when"],
                      "links":q["links"],"source_evidence":last["evidence"]})
    return {"schema":"missioncontrol.cp_close.bd_projection.v1",
            "owner":"CANONICAL_CODE_PURPLE_BD_QUEUE_ONLY",
            "source_path":"mission-control/federation-atlas/CODE_PURPLE_BD_QUEUE_v1.json",
            "source_sha256":sha(raw),"global_item_count":len(idx),
            "global_lifecycle_counts":dict(sorted(Counter(q["history"][-1]["state"] for q in d["items"]).items())),
            "focus":focus,"read_only_historical":True,"new_canonical_bd_items":0,"authority_transfer":False}

def render(i,bd,stats):
    acts=i["actions"]
    states=dict(sorted(Counter(a["state"] for a in acts).items()))
    state={"schema":"missioncontrol.cp_close.state.v1","moniker":"CP.CLOSE",
           "session_alias":i["session_alias"],"capture_date":i["capture_date"],
           "source":i["source"],"capture_scope":i["capture_scope"],
           "intent_count_reconstructed":len(i["intents"]),"action_count_reconstructed":len(acts),
           "session_action_states":states,"bd_focus_count":len(bd["focus"]),
           "full_chat_prompt_count":None,"full_chat_message_count":None,
           "release_gate":"INDEPENDENT_PR_AND_MAIN_ADMISSION",
           "semantic_handover_state":"SOURCE_BOUND_REVIEWABLE",
           "authority_transfer":False,"security_waiver":False}
    ledger={"schema":"missioncontrol.cp_close.semantic_ledger.v1","intents":i["intents"],
            "actions":acts,"decisions":i["decisions"],"insights":i["insights"],
            "metrics":i["metric_observations"],"prs":i["pr_snapshot"],
            "issues":i["external_issues"]}
    narrative=["# CODE PURPLE — CP.CLOSE lossless semantic session handover","",
        "Session: "+i["session_alias"]+" | Capture: "+i["capture_date"]+" ("+i["capture_granularity"]+")",
        "Historical master head: "+i["source"]["observed_main_sha"],
        "Class: SANITIZED SEMANTIC-LOSSLESS RECONSTRUCTION, NOT VERBATIM TRANSCRIPT.",
        "Complete message IDs, timestamps, token counts and hidden reasoning unavailable.","",
        "## Narrative and traced intents"]
    for q in i["intents"]:
        narrative.append("- "+q["id"]+" ["+q["source_class"]+"] "+q["summary"]+"; actions: "+(", ".join(q["actions"]) or "NONE"))
    narrative.extend(["","## Decisions / insights"])
    for q in i["decisions"]:
        narrative.append("- "+q["name"]+": "+q["rationale"]+"; "+q["disposition"]+"; "+q["evidence_url"])
    for q in i["insights"]:
        narrative.append("- "+q["observation"]+"; implication: "+q["implication"]+"; "+q["evidence_url"])
    narrative.extend(["","## GitHub PRs (status at observation only)"])
    for q in i["pr_snapshot"]:
        narrative.append("- PR #"+str(q["number"])+" "+q["state"]+" HEAD "+q["head_sha"]+" MERGE "+str(q.get("merge_sha"))+"; "+q["url"])
    narrative.extend(["","## Owned TODO, BD work, completion requirements"])
    for a in acts:
        narrative.append("- "+a["id"]+" "+a["priority"]+" "+a["state"]+" / "+a["owner"]+": "+a["summary"]+"; DOD: "+a["done_when"]+"; depends: "+str(a["depends_on"])+"; "+(", ".join(a["evidence_urls"]) or "NO_EVIDENCE"))
    for q in bd["focus"]:
        narrative.append("- "+q["id"]+" "+q["state"]+"/"+q["flow"]+": "+q["title"]+"; "+q["done_when"])
    narrative.extend(["","## Matched metrics (no global denominator promotion)"])
    for q in i["metric_observations"]:
        display=(str(q["numerator"])+"/"+str(q["denominator"])) if q["numerator"] is not None else "UNKNOWN"
        narrative.append("- "+q["metric"]+" "+display+" "+q["unit"]+"; cohort "+q["population"]+"; class "+q["evidence_class"]+"; "+q["source"])
    narrative.extend(["","## Chat statistics and data gaps",
        "- Full chat user prompt count: UNKNOWN, not zero. Complete original transcript was not supplied.",
        "- Reconstructed intent count: "+str(len(i["intents"]))+"; source-grounded actions: "+str(len(acts))+"; NOT prompt counts.",
        "- Optional supplied sample user prompts: "+str(stats["sample_user_prompts"])+". Provider-verified completeness: NO.",
        "- Actual ChatGPT tokens, wall clock, hidden turn IDs, original timestamps: UNKNOWN.",
        "","## On restart",
        "Verify hashes and refresh master/PR SHA, native workflows, run/job/attempt receipts, effective branch protection and eligible review.",
        "Do not convert a successful local test, merged PR, GitHub Pages render, screenshot or chat summary into formal engineering credit.",
        "Carry every HOLD and open owner issue to the next governed G3P pulse.",""])
    todo=io.StringIO()
    c=csv.writer(todo,lineterminator="\n")
    c.writerow(["id","priority","state","owner","done_when","depends_on","github_evidence"])
    for a in acts:
        if a["state"] not in {"DONE","CONTROL"}:
            c.writerow([a["id"],a["priority"],a["state"],a["owner"],a["done_when"],
                        "|".join(a["depends_on"]),"|".join(a["evidence_urls"])])
    start=["# START HERE — CP.CLOSE GitHub checkpoint","",
        "Status: sanitized semantic source snapshot, not full raw conversation.",
        "Read: MANIFEST.json, STATE.json, LOSSLESS_HANDOVER.md, INTENT_ACTION_LEDGER.json, BD_QUEUE_READONLY.json, CHAT_STATS.json, TODO_BD_QUEUE.csv, NEXT_CHAT_DROPIN.md.",
        "Then fresh-fetch repository heads/PRs/CI and compare the historical exact SHA. No auto-merge or security waiver.",
        "Canonical BD queue and Golden Thread remain authoritative. This package contains a read-only subset only.",""]
    drop=["# CP.RESUME drop-in for a new chat","",
        "Continue Mission Control "+i["session_alias"]+" using the verified GitHub CP.CLOSE packet.",
        "Repository: "+OWNER+". Read closeout/records/"+i["session_alias"]+"/START_HERE.md; check MANIFEST SHA256.",
        "Refresh live main/PR heads and native run-job-attempt logs; compare with the frozen historical SHA "+i["source"]["observed_main_sha"]+".",
        "Restore every intent, decision, action, evidence link and BD queue HOLD without mutating canonical records.",
        "Original full prompt and message counts remain UNKNOWN without an authorized export.",
        "Choose next source-owner priority, freeze forecast, and execute at most one governed G3P three-pulse envelope if authorized.",
        "No unapproved protected merge, safety/security waiver, QPS acceptance, fake worker or background promise.",""]
    return {"START_HERE.md":("\n".join(start)).encode(),
            "LOSSLESS_HANDOVER.md":("\n".join(narrative)).encode(),
            "NEXT_CHAT_DROPIN.md":("\n".join(drop)).encode(),
            "STATE.json":encode(state),"CHAT_STATS.json":encode(stats),
            "INTENT_ACTION_LEDGER.json":encode(ledger),"BD_QUEUE_READONLY.json":encode(bd),
            "TODO_BD_QUEUE.csv":todo.getvalue().encode()}

def build(intake_path,queue_path,out,messages=None,check=False,archive=None):
    raw=intake_path.read_bytes()
    i=json.loads(raw)
    validate(i)
    bd=bd_snapshot(queue_path,i["bd_focus"])
    stats=prompt_stats(messages)
    files=render(i,bd,stats)
    manifest={"schema":"missioncontrol.cp_close.manifest.v1",
              "session_alias":i["session_alias"],"intake_sha256":sha(raw),
              "canonical_bd_sha256":bd["source_sha256"],
              "observed_main_sha":i["source"]["observed_main_sha"],
              "member_sha256":{k:sha(v) for k,v in sorted(files.items())},
              "verbatim_transcript_claim":False,"authority_transfer":False,
              "main_merge_admission":"INDEPENDENT_REVIEW_REQUIRED"}
    files["MANIFEST.json"]=encode(manifest)
    if check:
        if not out.is_dir():
            die("generated record directory missing")
        for name,data in files.items():
            if not (out/name).is_file() or (out/name).read_bytes()!=data:
                die("generated record drift "+name)
    else:
        out.mkdir(parents=True,exist_ok=True)
        for name,data in files.items():
            (out/name).write_bytes(data)
    if archive:
        archive.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED) as z:
            for name,data in sorted(files.items()):
                info=zipfile.ZipInfo(name,(2026,10,17,0,0,0))
                info.compress_type=zipfile.ZIP_DEFLATED
                z.writestr(info,data)
        with zipfile.ZipFile(archive) as z:
            if z.testzip() or set(z.namelist())!=set(files):
                die("archive CRC or paths")
    return {"session_alias":i["session_alias"],"intents":len(i["intents"]),
            "actions":len(i["actions"]),"prompt_count":stats["sample_user_prompts"],
            "bd_focus":len(bd["focus"]),"artifact_count":len(files),
            "manifest_sha256":sha(files["MANIFEST.json"]),
            "status":"REVIEWABLE_NOT_MAIN_ADMITTED"}

def main(argv=None):
    ap=argparse.ArgumentParser(description="CP.CLOSE read-only session closeout")
    ap.add_argument("--intake",type=Path,required=True)
    ap.add_argument("--bd",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--messages",type=Path)
    ap.add_argument("--check",action="store_true")
    ap.add_argument("--zip",dest="archive",type=Path)
    p=ap.parse_args(argv)
    print(json.dumps(build(p.intake,p.bd,p.out,p.messages,p.check,p.archive),sort_keys=True))

if __name__=="__main__":
    try:
        main()
    except (ValueError,KeyError,FileNotFoundError,json.JSONDecodeError) as exc:
        print(str(exc),file=sys.stderr)
        raise SystemExit(2)
