#!/usr/bin/env python3
"""Read-only historical PR->merge->parent run timeline for CODE PURPLE."""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

SCHEMA="code-purple.pr-merge-temporal.v1"
SHA=re.compile(r"^[0-9a-f]{40}$")
PRID=re.compile(r"^GBOGEB/[A-Za-z0-9_.-]+#[1-9][0-9]*$")
ALLOWED={"success","failure","cancelled","skipped",None}
PHASES={"PR_HEAD_ASSOCIATED","MERGE_COMMIT_ASSOCIATED"}

def require(condition,message):
    if not condition: raise ValueError(message)

def instant(s):
    require(isinstance(s,str) and s.endswith("Z"),"missing UTC timestamp")
    try: return datetime.fromisoformat(s.replace("Z","+00:00"))
    except ValueError as e: raise ValueError("invalid UTC timestamp") from e

def validate(d):
    require(isinstance(d,dict) and d.get("schema")==SCHEMA,"invalid schema")
    a=d.get("authority",{})
    require(a.get("merge_admission")=="HOLD" and
        a.get("authority_transfer") is False and
        a.get("security_waiver") is False and
        a.get("dispatch")=="STAGED_NOT_LAUNCHED" and
        a.get("accepted_rex") is None and
        a.get("accepted_root_closures") is None and
        a.get("current_main_coverage") is None,"authority inversion")
    require(d.get("recursive_contract",{}).get("cycle_behavior")=="VISITED_SET_SKIP" and
            type(d["recursive_contract"].get("max_depth")) is int and
            1<=d["recursive_contract"]["max_depth"]<=10,"unbounded recursion")
    prs=d.get("prs")
    require(isinstance(prs,list) and prs,"missing PR evidence")
    ids=set()
    for p in prs:
        repo,num=p.get("repository"),p.get("pr")
        require(isinstance(repo,str) and repo.startswith("GBOGEB/") and
                type(num) is int and num>0,"invalid PR")
        ref=f"{repo}#{num}"
        require(ref not in ids,"duplicate PR")
        ids.add(ref)
        for key in ("head_sha","merge_commit_sha"):
            require(isinstance(p.get(key),str) and SHA.fullmatch(p[key]),"invalid SHA")
        merge_time=instant(p.get("merged_at_utc"))
        require(p.get("admission") in
            ("MERGED_TO_DEFAULT_BRANCH_NO_QPS_CREDIT",
             "MERGED_TO_FEATURE_BRANCH_NOT_DEFAULT"),"invalid merge distinction")
        if p["admission"]=="MERGED_TO_DEFAULT_BRANCH_NO_QPS_CREDIT":
            require(p["base_branch"] in ("main","master") and
                    p.get("destination_pr") is None,"default branch claim invalid")
        else:
            require(p["base_branch"] not in ("main","master") and
                    type(p.get("destination_pr")) is int,"feature branch claim invalid")
        phases=p.get("phases",[])
        require(len(phases)==2 and {q.get("role") for q in phases}==PHASES,
                "incomplete phase pair")
        allruns={}
        for q in phases:
            expect=p["head_sha"] if q["role"]=="PR_HEAD_ASSOCIATED" else p["merge_commit_sha"]
            require(q.get("sha")==expect and
                    q.get("pagination")=="FIRST_PAGE_ONLY_PR_TRIGGERED_RUNS",
                    "phase lineage mismatch")
            for w in q.get("workflows",[]):
                rid=w.get("run_id")
                require(type(rid) is int and rid>0 and
                        type(w.get("workflow")) is str and w["workflow"] and
                        w.get("conclusion") in ALLOWED and
                        w.get("url")==f"https://github.com/{repo}/actions/runs/{rid}" and
                        w.get("attempt") is None and
                        all(w.get(k) is None for k in
                            ("created_at","started_at","completed_at")),
                        "workflow identity/timing proof invalid")
                require(rid not in allruns,"duplicate run identity across phases")
                allruns[rid]=q["role"]
        seen_clock=set()
        for c in p.get("job_log_clocks",[]):
            rid=c.get("run_id")
            require(rid in allruns and
                    type(c.get("job_id")) is int and c["job_id"]>0 and
                    (rid,c["job_id"]) not in seen_clock and
                    c.get("source")=="NATIVE_JOB_LOG_LINE_TIMESTAMPS",
                    "unbound job clock")
            seen_clock.add((rid,c["job_id"]))
            first,last=instant(c.get("first_utc")),instant(c.get("last_utc"))
            require(first<=last,"negative job time")
    edges=d.get("edges",[])
    destinations=set()
    for edge in edges:
        require(edge.get("from") in ids and
                isinstance(edge.get("to"),str) and
                (PRID.fullmatch(edge["to"]) or
                 edge["to"].endswith("@master") or edge["to"].endswith("@main")) and
                edge.get("kind") in ("MERGED_INTO_FEATURE_PR","MERGED_TO_DEFAULT") and
                edge.get("proof") in ("MERGE_COMMIT_IDENTICAL_TO_TARGET_HEAD",
                                      "MERGE_COMMIT_ANCESTOR_2_COMMITS_BEHIND",
                                      "EXACT_MERGE_EQUALS_DEFAULT_SHA"),
                "unsupported recursive edge")
        destinations.add(edge["to"])
    return d

def traversal(start,edges,max_depth):
    """Breadth-first derived ancestry; cyclic/repeated links never loop."""
    adjacency={}
    for edge in edges: adjacency.setdefault(edge["from"],[]).append(edge["to"])
    discovered=[]
    seen={start}
    todo=[(start,0)]
    while todo:
        node,depth=todo.pop(0)
        discovered.append((node,depth))
        if depth>=max_depth: continue
        for nxt in sorted(adjacency.get(node,[])):
            if nxt not in seen:
                seen.add(nxt)
                todo.append((nxt,depth+1))
    return discovered

def classify(first,last,merge_at):
    a,b,m=instant(first),instant(last),instant(merge_at)
    if b<m:return "PRE_MERGE_JOB"
    if a>m:return "POST_MERGE_JOB"
    return "CROSSES_MERGE_BOUNDARY"

def summary(d):
    validate(d)
    counts={"success":0,"failure":0,"cancelled":0,"skipped":0,"nonterminal":0}
    for pr in d["prs"]:
        for phase in pr["phases"]:
            for run in phase["workflows"]:
                k=run["conclusion"] if run["conclusion"] in counts else "nonterminal"
                counts[k]+=1
    return counts

def esc(x): return html.escape(str(x),quote=True)

def render(d,sha256):
    validate(d)
    counts=summary(d)
    total=sum(counts.values())
    events=[]
    cards=[]
    rows=[]
    relations=[]
    for p in d["prs"]:
        reference=f"{p['repository']}#{p['pr']}"
        runs=sum(len(q["workflows"]) for q in p["phases"])
        ancestry=" → ".join(n for n,depth in traversal(reference,d["edges"],d["recursive_contract"]["max_depth"]))
        cards.append("<article><h3><a href='https://github.com/"+esc(p["repository"])+"/pull/"+str(p["pr"])+
          "' target='_blank' rel='noopener noreferrer'>"+esc(reference)+" ↗</a></h3><p>"+esc(p["admission"].replace("_"," "))+"</p>"+
          "<p class='mono'>head: "+esc(p["head_sha"][:16])+"…<br>merge: "+esc(p["merge_commit_sha"][:16])+"…</p>"+
          "<p>"+str(runs)+" PR-associated run observations</p><p>Parent chain: "+esc(ancestry)+"</p></article>")
        events.append((p["merged_at_utc"],reference,"MERGE",None,None,
            "Merged into "+p["base_branch"]))
        for q in p["phases"]:
            role=q["role"]
            for w in q["workflows"]:
                state=w["conclusion"] or w["status"] or "UNKNOWN"
                rows.append("<tr data-pr='"+str(p["pr"])+"' data-role='"+esc(role)+"' data-status='"+esc(state)+"'>"
                    "<td><a href='https://github.com/"+esc(p["repository"])+"/pull/"+str(p["pr"])+"'>#"+str(p["pr"])+"</a></td>"
                    "<td>"+esc(role.replace("_"," "))+"</td><td><a href='"+esc(w["url"])+
                    "' target='_blank' rel='noopener noreferrer'>"+str(w["run_id"])+"</a></td>"
                    "<td>"+esc(w["workflow"])+"</td><td>"+esc(state)+"</td><td>UNKNOWN</td></tr>")
        for c in p.get("job_log_clocks",[]):
            kind=classify(c["first_utc"],c["last_utc"],p["merged_at_utc"])
            events.append((c["first_utc"],reference,kind,c["run_id"],c["job_id"],
                "Job log first → last "+c["last_utc"]))
    events.sort(key=lambda x:(instant(x[0]),x[1],x[2]))
    timeline=""
    for utc,reference,kind,run,job,detail in events:
        link=(" · <a href='https://github.com/"+esc(reference.split("#")[0])+
             "/actions/runs/"+str(run)+"/job/"+str(job)+
             "' target='_blank' rel='noopener noreferrer'>Run "+str(run)+" / job "+str(job)+" ↗</a>") if run else ""
        timeline+="<li><time>"+esc(utc)+"</time><span><b>"+esc(reference)+
           "</b> <em>"+esc(kind.replace("_"," "))+"</em>"+link+
           "<p>"+esc(detail)+"</p></span></li>")
    for edge in d["edges"]:
        relations.append("<li>"+esc(edge["from"])+" → "+esc(edge["to"])+
                         " · "+esc(edge["kind"])+"</li>")
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="source-sha256" content="%s">
<meta name="referrer" content="no-referrer">
<title>CODE PURPLE · Merged PR temporal lineage</title>
<style>
:root{color-scheme:dark;--bg:#090f1d;--ink:#edf5ff;--panel:#172338;--line:#3a4963;--muted:#b8c7db;--mint:#85e1c2}
*{box-sizing:border-box}body{margin:0;color:var(--ink);background:var(--bg);font:14px/1.55 system-ui,sans-serif}main{max-width:1370px;margin:auto;padding:24px}
a{color:#a6cdff}h1{font-size:clamp(27px,4vw,42px);margin:5px 0}h2{font-size:20px}
header p{color:var(--muted)}.cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
article,section{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px;margin:12px 0;min-width:0}
article h3{font-size:16px;margin:0 0 8px}.mono{font:12px/1.6 ui-monospace,monospace;overflow-wrap:anywhere}
.num{font-size:25px;color:var(--mint);font-weight:750}strong{color:var(--mint)}.muted{color:var(--muted)}
ul.timeline{list-style:none;padding:0}ul.timeline li{display:grid;grid-template-columns:190px 1fr;gap:12px;border-left:3px solid #376379;border-bottom:1px solid var(--line);padding:12px}
time{font-family:ui-monospace,monospace;color:var(--mint);overflow-wrap:anywhere}em{font-size:12px;color:#f8d5a0}
table{border-collapse:collapse;width:100%;min-width:720px}td,th{text-align:left;padding:9px;border-bottom:1px solid var(--line);vertical-align:top}
td:nth-child(4){max-width:220px;overflow-wrap:anywhere}th{color:var(--muted)}.scroll{overflow-x:auto}
label{font-weight:650;margin-right:8px}select,input{font:inherit;color:var(--ink);background:#091222;border:1px solid var(--line);border-radius:8px;padding:8px}
nav{display:flex;flex-wrap:wrap;gap:15px;align-items:center;margin:12px 0}.hold{color:#f4c98a}
@media(max-width:900px){.cards{grid-template-columns:1fr}}@media(max-width:560px){main{padding:12px}ul.timeline li{grid-template-columns:1fr;gap:3px}td{padding:6px}}
</style></head><body><main>
<nav><a href="../index.html">← Mission Control</a><a href="../bd-char/index.html">BD / CHAR pulse P2</a><span class="hold">HOLD · read-only</span></nav>
<header><p>GBOGEB · Historical merged-PR recovery cohort · 16 October 2026</p>
<h1>Temporal / recursive PR and CI lineage</h1>
<p>Historical head runs → merge commit → feature/default branch → downstream runs. UTC event clock and bounded ancestry graph.</p>
<p class="hold">79 PR-triggered, first-page run observations; zero should be interpreted as no returned PR-triggered run, never no actual CI. Workflow timestamp and attempt are UNKNOWN when unavailable; job log timestamps are separately identified.</p></header>
<section><div class="cards">%s</div>
<p class="muted">%s successful · %s failures · %s cancelled · %s nonterminal · %s skipped / total %s source-associated run rows. Separate heads and populations; these are not reliability trials.</p></section>
<section><h2>Temporal evidence (UTC)</h2>
<ul class="timeline">%s</ul></section>
<section><h2>Verified recursive integration edges</h2>
<ul>%s</ul><p class="muted">Graph walk uses a visited-set and maximum depth of %s. No unverified or cyclic edge grants evidence transfer.</p></section>
<section><h2>Historical GitHub workflow run ledger</h2>
<nav><label for="filter">PR</label><select id="filter"><option value="">All</option><option>562</option><option>2060</option><option>2061</option></select>
<label for="phase">Phase</label><select id="phase"><option value="">All</option><option value="PR_HEAD_ASSOCIATED">PR head</option><option value="MERGE_COMMIT_ASSOCIATED">Merge commit</option></select>
<label for="search">Search</label><input id="search" type="search" placeholder="Workflow / run / status"><span id="count">%s</span></nav>
<div class="scroll"><table><thead><tr><th>PR</th><th>Source relationship</th><th>Native run</th><th>Workflow</th><th>Conclusion</th><th>Run clock / attempt</th></tr></thead><tbody id="rows">%s</tbody></table></div></section>
<section><h2>Provenance and limits</h2>
<p class="mono">Source SHA256: %s</p>
<p>PR-triggered first-page listing excludes other events, may omit pagination, and does not authenticate checkout identity. The merged timestamp is the PR event clock. Job log windows are individual job clocks. A passing historical job is not independent A10, Safety, REX or main admission.</p>
<p><a href="snapshot.json">Read-only snapshot JSON</a> · <a href="manifest.json">Generation hashes</a> · <a href="https://github.com/GBOGEB/ABACUS/issues/1929">Canonical BD/LDAB issue #1929</a></p></section>
<script>
'use strict';const rows=[...document.querySelectorAll('#rows tr')],pr=document.getElementById('filter'),phase=document.getElementById('phase'),search=document.getElementById('search');
function filter(){let n=0;for(const r of rows){let show=(!pr.value||r.dataset.pr===pr.value)&&(!phase.value||r.dataset.role===phase.value)&&r.textContent.toLowerCase().includes(search.value.trim().toLowerCase());r.hidden=!show;if(show)n++}document.getElementById('count').textContent=n+' / '+rows.length}
pr.addEventListener('change',filter);phase.addEventListener('change',filter);search.addEventListener('input',filter);
</script></main></body></html>""" % (sha256,"".join(cards),counts["success"],counts["failure"],counts["cancelled"],counts["nonterminal"],counts["skipped"],total,timeline,"".join(relations),d["recursive_contract"]["max_depth"],total,"".join(rows),sha256)

def produce(source,out):
    source,out=Path(source),Path(out)
    raw=source.read_bytes()
    d=validate(json.loads(raw))
    out.mkdir(parents=True,exist_ok=True)
    digest=hashlib.sha256(raw).hexdigest()
    (out/"index.html").write_text(render(d,digest),encoding="utf-8")
    (out/"snapshot.json").write_bytes(raw)
    manifest={"schema":"code-purple.pr-history.view-receipt.v1","source_sha256":digest,
              "artifact_sha256":{n:hashlib.sha256((out/n).read_bytes()).hexdigest()
                        for n in ("index.html","snapshot.json")},
              "grade":"EXACT_HEAD_PROJECTION_NOT_REMOTE_HISTORY_AUTHORITY",
              "merge_admission":"HOLD","authority_transfer":False}
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
    return manifest

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(produce(a.source,a.out),sort_keys=True))
if __name__=="__main__":main()
