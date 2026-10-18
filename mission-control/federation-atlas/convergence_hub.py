#!/usr/bin/env python3
"""Read-only Global DoV hub inside the EXISTING Method Atlas / Pages publisher.

The source JSON is a bounded historical observation ledger, NOT an alternative
native producer, authenticated GitHub attestation, QPS owner gate, or dispatch.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHA40 = re.compile(r"[a-f0-9]{40}\Z")
SOURCE_NAME = "CONVERGENCE_HUB_SOURCES_W32.json"
SOURCE_SCHEMA = "codepurple.convergence_hub.sources.v1"
OUT_SCHEMA = "codepurple.convergence_hub.projection.v1"

PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer"><title>CODE PURPLE | Global DoV Convergence Hub</title>
<style>
:root{color-scheme:dark;--bg:#0b1221;--surface:#121e32;--raised:#192740;--ink:#eaf2fd;--sub:#9eafc7;--border:#32445d;--violet:#baabff;--teal:#68d6bd;--red:#ff8692;--amber:#f6c67d;--blue:#8dcfff}
*{box-sizing:border-box}body{margin:0;color:var(--ink);background:var(--bg);font:14px/1.5 system-ui,"Segoe UI",sans-serif}
main{max-width:1440px;margin:auto;padding:26px 20px 78px}h1,h2,h3,p{margin-top:0}h1{font-size:clamp(30px,4vw,51px);line-height:1.05;letter-spacing:-.04em;margin-bottom:12px}
h2{font-size:22px;letter-spacing:-.02em}h3{font-size:16px}a{color:var(--blue);overflow-wrap:anywhere}
.eyebrow{font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--teal);font-weight:750}.muted{color:var(--sub)}
.top{display:flex;justify-content:space-between;align-items:start;flex-wrap:wrap;gap:20px;border-bottom:1px solid var(--border);padding-bottom:22px}
.subnav{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0 26px}.subnav a{text-decoration:none;border:1px solid var(--border);border-radius:999px;padding:8px 12px;background:var(--surface)}
.gate{color:var(--amber);border:1px solid var(--amber);border-radius:999px;padding:7px 12px;font-size:12px;font-weight:700}
.cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.card,.panel{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:17px;min-width:0}
.value{font-size:clamp(24px,3vw,35px);font-weight:750;letter-spacing:-.04em;font-variant-numeric:tabular-nums;line-height:1.2}
.label{color:var(--sub);font-size:11px;text-transform:uppercase;letter-spacing:.07em;margin-bottom:6px}.note{font-size:12px;color:var(--sub);margin-top:9px;margin-bottom:0}
.progress{height:6px;background:#283a52;border-radius:20px;margin-top:11px;overflow:hidden}.fill{height:100%;background:var(--teal);border-radius:20px}
section{margin-top:32px;scroll-margin-top:18px}.sectionhead{display:flex;align-items:baseline;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:12px}
.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.panel h3{margin-bottom:5px}.tag{display:inline-block;font-size:10px;border-radius:6px;border:1px solid var(--border);padding:3px 6px;margin:4px 5px 4px 0}
.state-ok{color:var(--teal)}.state-unknown{color:var(--amber)}.state-red{color:var(--red)}
.toolbar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:12px 0}input,select,button{font:inherit;color:var(--ink);background:var(--raised);border:1px solid #61708a;border-radius:8px;padding:9px 11px}
input{min-width:200px;flex:1}button{cursor:pointer}button:hover{border-color:var(--teal)}button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible{outline:2px solid var(--teal);outline-offset:2px}
.tablewrap{overflow-x:auto;border:1px solid var(--border);border-radius:12px}table{width:100%;border-collapse:collapse;min-width:840px;background:var(--surface)}
th,td{padding:12px 11px;border-bottom:1px solid var(--border);text-align:left;vertical-align:top}th{color:var(--sub);text-transform:uppercase;letter-spacing:.07em;font-size:10px}td{font-size:12px}td code{font-size:11px;overflow-wrap:anywhere}
code,.mono{font:12px/1.5 ui-monospace,SFMono-Regular,Consolas,monospace}article code{overflow-wrap:anywhere}
.ledger-row:hover{background:#202e46}.stats{font-variant-numeric:tabular-nums}
.barrow{display:grid;grid-template-columns:180px 1fr 120px;gap:10px;align-items:center;margin:8px 0;font-size:12px}
.lineage{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.lineage .panel{border-top:3px solid var(--violet)}
.navcards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.navcards a{display:block;text-decoration:none;padding:12px 14px;background:var(--raised);border:1px solid var(--border);border-radius:9px}
.small{font-size:12px}.dim{color:var(--sub)}.wide{grid-column:1/-1}.nowrap{white-space:nowrap}
#live-state{min-height:24px}#live-results{display:grid;gap:8px;font-size:12px}.callout{border-left:3px solid var(--amber);padding:12px 15px;background:var(--raised);border-radius:5px}
@media(max-width:1080px){.cards{grid-template-columns:repeat(2,minmax(0,1fr))}.grid,.navcards{grid-template-columns:repeat(2,minmax(0,1fr))}.lineage{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:640px){main{padding:17px 12px 56px}.cards,.grid,.lineage,.navcards{grid-template-columns:1fr}.barrow{grid-template-columns:1fr;gap:3px}.top{display:block}h1{font-size:32px}.value{font-size:27px}.subnav a{font-size:12px}.toolbar>*{width:100%;min-width:0}}
</style></head>
<body><main>
<header class="top"><div><p class="eyebrow">MissionControl / CODE PURPLE / W32 / Global DoV</p><h1>One flight deck.<br>Many evidence fronts.</h1>
<p class="muted">A source-bound, sectional lens on local repair, regional coverage, six-repo federation, runner pressure, mathematical readiness and Golden Thread continuity.</p>
<p class="small dim">Frozen observation <strong id="snapshot-id"></strong> · Presentation head <code id="head-sha"></code></p></div>
<div><div class="gate">MERGE ADMISSION · HOLD</div><p class="small dim" style="margin-top:12px">Read-only · no credential storage · no dispatch</p></div></header>
<nav class="subnav" aria-label="Hub sections"><a href="#global">Global DoV</a><a href="#clusters">Family lens</a><a href="#evidence">Evidence ledger</a><a href="#coverage">Coverage</a><a href="#roots">Root pressure</a><a href="#expansion">N+ waves</a><a href="#golden">Golden Thread</a><a href="#dashboards">Dashboards</a><a href="#refresh">GitHub refresh</a></nav>
<section id="global"><div class="sectionhead"><h2>Global · measured with honest denominators</h2><span class="muted small">Never combine separate populations</span></div><div id="kpi-grid" class="cards"></div><p class="callout">Local or repository-native successes are not cross-repository engineering acceptance. Historical six-repo breadth, workflow run identity, code coverage, artifact CRC, and authentication are separate denominator families.</p></section>
<section id="clusters"><div class="sectionhead"><h2>Section / cluster / family DoV</h2><span class="muted small">Owner and gate follow the evidence source</span></div><div id="family-grid" class="grid"></div></section>
<section id="evidence"><div class="sectionhead"><h2>Native evidence · source and job lineage</h2><span class="muted small">Curated instances only, no total-fleet test claim</span></div>
<div class="toolbar"><label for="family-filter">Family</label><select id="family-filter"><option value="ALL">All families</option></select>
<label for="case-search">Find</label><input id="case-search" type="search" placeholder="PR, run, source, root, method..." aria-label="Filter evidence" autocomplete="off"><button id="clear-filters" type="button">Clear</button><span id="visible-count" class="small muted"></span></div>
<div class="tablewrap"><table><thead><tr><th>Evidence / family</th><th>Exact PR head and native identity</th><th>Executed / P / F / S</th><th>ZIP/member bytes</th><th>Qualification</th></tr></thead><tbody id="events-body"></tbody></table></div></section>
<section id="coverage"><div class="sectionhead"><h2>Coverage · scope is the denominator</h2><span class="muted small">Numerator/denominator preserved, cross-scope uplift withheld</span></div><div id="coverage-grid" class="grid"></div></section>
<section id="roots"><div class="sectionhead"><h2>First-red fingerprints, not causal-root closures</h2><span class="muted small">Nine manifestations / three signatures are not nine accepted roots</span></div><div id="root-grid" class="grid"></div></section>
<section id="expansion"><div class="sectionhead"><h2>N → N+1 → N+2 · bounded expansion options</h2><span class="muted small">Source-owned attacks; disjoint runners only after terminal preflight</span></div><div id="expansion-grid" class="grid"></div>
<p class="callout small">Scale guard: 3 consecutive matched flat deltas below target redirect the local slice. Cross-repo authenticated proof, capacity and governance cannot be compensated by unrelated green tests. PCA/BT must satisfy sample/graph identifiability.</p></section>
<section id="golden"><div class="sectionhead"><h2>Golden Thread · session continuity</h2><span class="muted small">CP.CLOSE → CP.HANDOFF → CP.RESUME; append only</span></div><div id="lineage-grid" class="lineage"></div>
<p class="small dim">Retain historical source SHA, PR/run/job/artifact identity, owner action and unknown fields; do not rewrite immutable predecessor receipts. <a href="lineage.mmd">Mermaid source</a> · <a href="ledger.json">Machine-readable hub ledger</a> · <a href="manifest.json">Byte manifest</a></p></section>
<section id="dashboards"><div class="sectionhead"><h2>Concentrated dashboard entry points</h2><span class="muted small">All existing native views preserved</span></div><div id="nav-grid" class="navcards"></div></section>
<section id="refresh"><div class="sectionhead"><h2>GitHub status reload · separate live overlay</h2><span class="muted small">Public REST GET only · no token · browser rate limits</span></div>
<div class="panel"><p class="small muted">Click to fetch the latest selected PR/run metadata. New observations are labelled LIVE UNVERIFIED; no archive bytes, tests, first-red attribution, merge approval, or QPS acceptance are inferred. Reload discards the browser overlay and returns to the immutable snapshot.</p>
<div class="toolbar"><button id="github-refresh" type="button">Refresh GitHub status</button><button id="reset-overlay" type="button">Reset overlay</button><button id="reload-page" type="button">Reload page</button></div><div id="live-state" role="status" aria-live="polite">Not checked · frozen source only</div><div id="live-results"></div></div></section>
<footer class="small dim" style="border-top:1px solid var(--border);padding-top:18px;margin-top:28px">DoV boundary: read-only projection, not an authoritative engineering or CI producer. Source: <a href="https://github.com/GBOGEB/pipeline-automation-hub">Mission Control</a>. Canonical #530 ZIP verification · #531 six-repo breadth · #533 lane viewer.</footer>
</main>
<script id="frozen-json" type="application/json">__SNAPSHOT_JSON__</script>
<script>
"use strict";
const pack=JSON.parse(document.getElementById("frozen-json").textContent);
const d=pack.sources, k=pack.kpis;
const el=id=>document.getElementById(id);
function elem(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=String(text);if(cls)n.className=cls;return n}
function append(parent,tag,text,cls){const x=elem(tag,text,cls);parent.appendChild(x);return x}
function safeExternal(url,label){const a=elem("a",label);a.href=url;a.rel="noopener noreferrer";a.target="_blank";return a}
function fmt(v){return v===null||v===undefined?"UNKNOWN":String(v)}
function pct(a,b){return b>0?(100*a/b).toFixed(1)+"%":"UNKNOWN"}
function card(label,value,note,ratio){const c=elem("article",undefined,"card");append(c,"div",label,"label");append(c,"div",value,"value");append(c,"p",note,"note");if(ratio!==undefined&&ratio!==null){const bar=append(c,"div",undefined,"progress");const f=append(bar,"div",undefined,"fill");f.style.width=Math.max(0,Math.min(100,ratio))+"%";bar.setAttribute("aria-label",label+" "+ratio.toFixed(1)+" percent")}return c}
function prUrl(e){return "https://github.com/"+e.repo+"/pull/"+e.pr}
function runUrl(e){return "https://github.com/"+e.repo+"/actions/runs/"+e.run}
function project(){
el("snapshot-id").textContent=d.snapshot_id;el("head-sha").textContent=pack.presentation_head;
const p=d.populations;const cg=el("kpi-grid");
const metrics=[
["Six-repo canonical breadth",p.canonical_federation.observed+"/"+p.canonical_federation.eligible,"Historical; 36 unobserved cells",100*p.canonical_federation.observed/p.canonical_federation.eligible],
["W31 native run identities",p.w31_run_identity.observed+"/"+p.w31_run_identity.reported,"Two repos, 33 unobserved-tail runs; NOT coverage",100*p.w31_run_identity.observed/p.w31_run_identity.reported],
["Authenticated W30 pair",p.native_federation_authenticated_edges.observed+"/"+p.native_federation_authenticated_edges.required,"CODEX to QPS still DEFER",0],
["Curated test executions",k.curated_executed,"Repeated test families and subtests overlap; not distinct cases",null],
["Root manifestations / signatures",k.root_manifestations+" / "+k.first_red_signatures,"Owner-accepted causal closures UNKNOWN",null],
["Worker capacity / hours","UNKNOWN","Never inferred from configured matrix parallelism",null],
["Method qualification","M1 PARTIAL","M2 HOLD · M3 HOLD · PCA/BT unqualified",null],
["Programme gate","HOLD","No waiver, acceptance or authority transfer",null]
];metrics.forEach(m=>cg.appendChild(card(...m)));
const fs=el("family-filter");
d.families.forEach(f=>{const o=elem("option",f.title);o.value=f.id;fs.appendChild(o)});
const fgrid=el("family-grid");
d.families.forEach(f=>{const a=elem("article",undefined,"panel");append(a,"div",f.id.toUpperCase(),"eyebrow");append(a,"h3",f.title);append(a,"p",f.purpose,"small muted");append(a,"p","Owner: "+f.owner,"small");append(a,"span",f.gate,"tag");const related=d.events.filter(e=>e.family===f.id);append(a,"p",related.length+" curated evidence records","small muted");fgrid.appendChild(a)});
const cg2=el("coverage-grid");
d.events.filter(e=>e.coverage).forEach(e=>{const a=elem("article",undefined,"panel");append(a,"h3",e.coverage.label);append(a,"p","Scope key: "+e.coverage.scope_key+" · exact PR head "+e.head.slice(0,12),"small muted");for(const [label,v] of [["Statements",e.coverage.statements],["Branches",e.coverage.branches]]){const row=append(a,"div",undefined,"barrow");append(row,"span",label);const bar=append(row,"div",undefined,"progress");const fill=append(bar,"div",undefined,"fill");fill.style.width=(100*v.covered/v.total).toFixed(2)+"%";append(row,"strong",v.covered+"/"+v.total+" · "+pct(v.covered,v.total),"stats")}const cmp=e.coverage.historical_comparison;
if(cmp){const gain=cmp.contemporary_covered-cmp.observed_covered;
append(a,"p","Historical B0 "+cmp.observed_covered+"/"+cmp.observed_total+" → focused native "+cmp.contemporary_covered+"/"+cmp.contemporary_total+"; Δ "+(gain>=0?"+":"")+gain+" opportunities","small");
append(a,"p","Descriptive same-file cohort; B0/source/config admission pairing still required","small state-unknown");
}else{append(a,"p","Different source/denominator: NO MATCHED DELTA","small state-unknown")}
cg2.appendChild(a)});
const rg=el("root-grid");d.roots.forEach(r=>{const a=elem("article",undefined,"panel");append(a,"h3",r.fingerprint);append(a,"div",r.job_manifestations+" manifestations","value");append(a,"p",r.distinct_run_attempts+" observed run attempt(s); root ID: "+fmt(r.root_id),"small muted");append(a,"p","Owner closure: UNKNOWN","state-unknown small");rg.appendChild(a)});
const wg=el("expansion-grid");d.avenues.forEach(o=>{const a=elem("article",undefined,"panel");append(a,"span",o.scope+" · "+o.id,"tag");append(a,"h3",o.name);append(a,"p","Opportunity: "+o.eligible,"small");append(a,"p","Next: "+o.next,"small muted");append(a,"p","Stop/retrigger: "+o.stop,"small state-unknown");wg.appendChild(a)});
const lg=el("lineage-grid");d.lineage.forEach(n=>{const a=elem("article",undefined,"panel");append(a,"span",n.id,"tag");append(a,"h3",n.state.replaceAll("_"," "));const url="https://github.com/GBOGEB/pipeline-automation-hub/blob/master/"+n.path;a.appendChild(safeExternal(url,"Open canonical source ↗"));append(a,"p","GitHub PR #"+n.pr,"small dim");lg.appendChild(a)});
const ng=el("nav-grid");d.navigation.forEach(n=>{const a=elem("a",n.label+" ↗");a.href=n.href;const s=append(a,"small"," · "+n.role,"dim");ng.appendChild(a)});
}
function renderEvents(){
const filter=el("family-filter").value, term=el("case-search").value.trim().toLowerCase();const body=el("events-body");body.replaceChildren();
let count=0;d.events.forEach(e=>{const hay=(e.id+" "+e.repo+" "+e.pr+" "+e.run+" "+e.first_red+" "+e.observations).toLowerCase();if(filter!=="ALL"&&e.family!==filter)return;if(term&&!hay.includes(term))return;count++;
const tr=elem("tr",undefined,"ledger-row");const c1=append(tr,"td");append(c1,"strong",e.id);append(c1,"div",e.family,"small dim");
const c2=append(tr,"td");c2.appendChild(safeExternal(prUrl(e),e.repo+" #"+e.pr+" ↗"));append(c2,"div",e.head,"mono dim");const a=safeExternal(runUrl(e),"Run "+e.run+" ↗");c2.appendChild(a);append(c2,"div","Attempt "+fmt(e.attempt)+" · jobs "+(e.jobs.length?e.jobs.join(", "):"UNKNOWN"),"small dim");
const c3=append(tr,"td");const t=e.tests;append(c3,"strong",[t.executed,t.passed,t.failed,t.skipped].map(fmt).join(" / "),"stats");
const c4=append(tr,"td");append(c4,"div",fmt(e.artifact.zip_bytes)+" ZIP / "+fmt(e.artifact.member_bytes)+" member bytes","small");append(c4,"div","CRC "+fmt(e.artifact.crc_members)+"/"+fmt(e.artifact.members),"small dim");append(c4,"div","Artifact "+fmt(e.artifact.id),"small dim");
const c5=append(tr,"td");append(c5,"div",e.status,e.status==="TERMINAL_SUCCESS"?"state-ok":e.status==="TERMINAL_FAILURE"?"state-red":"state-unknown");append(c5,"div",e.observations,"small");append(c5,"p",e.artifact.verification.replaceAll("_"," "),"note");body.appendChild(tr)});
el("visible-count").textContent=count+" / "+d.events.length+" cases visible";
}
function refresh(){
const btn=el("github-refresh");btn.disabled=true;el("live-state").textContent="Public GitHub readback running; no frozen data will be changed…";const area=el("live-results");area.replaceChildren();
const queries=[
{repo:"GBOGEB/gg_MATH",pr:69,run:39161390018},
{repo:"GBOGEB/CODEX",pr:1106,run:39161146097},
{repo:"GBOGEB/cryoplant-project",pr:1961,run:39158769270},
{repo:"GBOGEB/pipeline-automation-hub",pr:533,run:38719705691}
];
Promise.all(queries.map(async q=>{
const u="https://api.github.com/repos/"+q.repo;const urls=[u+"/pulls/"+q.pr,u+"/actions/runs/"+q.run];
let results=[];
for(const url of urls){try{const resp=await fetch(url,{method:"GET",headers:{"Accept":"application/vnd.github+json"},cache:"no-store"});if(!resp.ok)throw Error("HTTP "+resp.status);results.push(await resp.json())}catch(e){results.push({error:String(e)})}}
return {q,pr:results[0],run:results[1]};
})).then(rows=>{rows.forEach(x=>{const div=elem("div",undefined,"panel");append(div,"strong",x.q.repo+" #"+x.q.pr+" · run "+x.q.run);const pr=x.pr,run=x.run;
const prHead=pr.head&&pr.head.sha?pr.head.sha:"UNKNOWN";
append(div,"div","LIVE UNVERIFIED · PR head "+prHead+" · "+(pr.state||"UNKNOWN")+" · "+(pr.draft===true?"DRAFT":pr.draft===false?"NOT DRAFT":"UNKNOWN"),"small");
append(div,"div","Run "+(run.status||"UNKNOWN")+" / "+(run.conclusion||"UNKNOWN")+" · attempt "+fmt(run.run_attempt)+" · run source "+fmt(run.head_sha),"small");
if(pr.error||run.error)append(div,"div","GitHub unavailable or rate-limited: "+(pr.error||run.error),"state-unknown small");
if(prHead!=="UNKNOWN"&&run.head_sha&&run.head_sha!==prHead)append(div,"div","MISMATCH: source/run SHA differ; do not credit exact-head native proof","state-red small");
append(div,"div","Native job steps, ZIP and member hashes: NOT CHECKED BY BROWSER","small dim");
area.appendChild(div)});
el("live-state").textContent="Browser GET completed · "+new Date().toLocaleString()+" · UNVERIFIED metadata overlay, not native evidence or owner admission";
}).catch(e=>{el("live-state").textContent="GitHub status unavailable: "+String(e)}).finally(()=>{btn.disabled=false});
}
project();renderEvents();
el("family-filter").addEventListener("change",renderEvents);
el("case-search").addEventListener("input",renderEvents);
el("clear-filters").addEventListener("click",()=>{el("family-filter").value="ALL";el("case-search").value="";renderEvents()});
el("github-refresh").addEventListener("click",refresh);
el("reset-overlay").addEventListener("click",()=>{el("live-results").replaceChildren();el("live-state").textContent="Not checked · frozen source only"});
el("reload-page").addEventListener("click",()=>location.reload());
</script></body></html>
"""

def fail_if(condition, error):
    if condition:
        raise ValueError(error)


def validate(d):
    fail_if(type(d) is not dict or d.get("schema") != SOURCE_SCHEMA, "SCHEMA_MISMATCH")
    a = d.get("authority", {})
    fail_if(not (a.get("publisher") == "EXISTING_METHOD_ATLAS_PAGES_ONLY"
                 and a.get("zip_verifier_pr") == 530
                 and a.get("six_repo_census_pr") == 531
                 and a.get("method_viewer_pr") == 533
                 and a.get("merge_admission") == "HOLD"
                 and a.get("authority_transfer") is False
                 and a.get("security_waiver") is False
                 and a.get("qps_owner_acceptance") is None
                 and a.get("formal_root_closures") is None), "AUTHORITY_PROMOTION")
    p = d["populations"]
    b = p["canonical_federation"]
    fail_if(b["observed"] + b["unobserved"] != b["eligible"] or b["eligible"] != 42
            or b["fresh_readback_qualified"] is not False, "FALSE_GLOBAL_CENSUS")
    w = p["w31_run_identity"]
    fail_if(w["observed"] + w["unknown_tail"] != w["reported"] or w["reported"] < 0,
            "FALSE_RUN_DENOMINATOR")
    hop = p["native_federation_authenticated_edges"]
    fail_if(hop["observed"] != 0 or hop["credit"] is not False, "FALSE_FEDERATION_PROOF")
    read = d["readiness"]
    fail_if((read["M1"], read["M2"], read["M3"]) != ("PARTIAL", "HOLD", "HOLD")
            or read["PCA"] != "NOT_FEDERATION_QUALIFIED"
            or read["BT"] != "NOT_FEDERATION_QUALIFIED"
            or read["worker_hours"] is not None or read["usable_worker_capacity"] is not None
            or read["source_bound_proof_coverage_global"] is not None, "FALSE_MIP_OR_CAPACITY")
    families = d["families"]
    fam_ids = [f["id"] for f in families]
    fail_if(len(fam_ids) != 6 or len(set(fam_ids)) != 6, "FAMILY_CENSUS")
    events = d["events"]
    fail_if(not events, "EMPTY_EVENTS")
    ids = set()
    job_ids = set()
    for e in events:
        fail_if(e["id"] in ids or e["family"] not in fam_ids, "DUPLICATE_OR_UNKNOWN_EVENT")
        ids.add(e["id"])
        fail_if(not SHA40.fullmatch(e["head"]) or not e["repo"].startswith("GBOGEB/")
                or type(e["pr"]) is not int or type(e["run"]) is not int, "BAD_SOURCE_IDENTITY")
        fail_if(e["status"] not in ("TERMINAL_SUCCESS", "TERMINAL_FAILURE", "NONTERMINAL"),
                "BAD_STATUS")
        t = e["tests"]
        if e["status"] == "NONTERMINAL":
            fail_if(any(t.get(f) is not None for f in ("executed", "passed", "failed", "skipped")),
                    "FAKE_NONTERMINAL_TESTS")
        else:
            fail_if(any(type(t.get(f)) is not int or t[f] < 0 for f in
                        ("executed", "passed", "failed", "skipped")), "BAD_TEST_COUNTS")
            fail_if(t["executed"] != t["passed"] + t["failed"] + t["skipped"],
                    "TEST_DENOMINATOR_DRIFT")
        if e["status"] == "TERMINAL_FAILURE":
            fail_if("first_red" not in e, "UNATTRIBUTED_FIRST_RED")
        for job in e["jobs"]:
            fail_if(type(job) is not int or job in job_ids, "DUPLICATE_JOB_ID")
            job_ids.add(job)
        cov = e.get("coverage")
        if cov:
            fail_if(not cov.get("scope_key"), "COVERAGE_SCOPE_UNDECLARED")
            for field in ("statements", "branches"):
                v = cov[field]
                fail_if(type(v["covered"]) is not int or type(v["total"]) is not int
                        or v["total"] < 1 or not 0 <= v["covered"] <= v["total"],
                        "COVERAGE_DENOMINATOR_INVALID")
            pair = cov.get("historical_comparison")
            if pair:
                summed = cov["statements"]["covered"] + cov["branches"]["covered"]
                denom = cov["statements"]["total"] + cov["branches"]["total"]
                fail_if(pair.get("admission_qualified") is not False
                        or pair.get("source_blobs_reported_unchanged") is not True
                        or pair.get("scope_paths_same") is not True
                        or pair.get("contemporary_covered") != summed
                        or pair.get("contemporary_total") != denom
                        or pair.get("observed_total") != denom
                        or not 0 <= pair.get("observed_covered",-1) <= denom,
                        "UNQUALIFIED_HISTORICAL_COMPARISON")
        z = e["artifact"]
        fail_if(z.get("verification") == "DOWNLOADED_VALIDATED" and
                (z.get("member_bytes") is None or z.get("crc_members") != z.get("members")),
                "FABRICATED_BYTE_VERIFICATION")
    roots = d["roots"]
    fail_if(sum(r["job_manifestations"] for r in roots) != 9 or len(roots) != 3,
            "ROOT_POPULATION_DRIFT")
    fail_if(any(r.get("root_id") is not None or r.get("owner_disposition") is not None for r in roots),
            "UNACCEPTED_ROOT_PROMOTION")
    for row in d["lineage"]:
        fail_if(not row["path"].startswith("mission-control/") or ".." in row["path"],
                "UNSAFE_GOLDEN_THREAD")
    return d


def summary(d):
    native = [e for e in d["events"] if e["status"] != "NONTERMINAL"]
    measured = sum(e["tests"]["executed"] for e in native)
    return {"curated_executed": measured,
            "curated_successful_job_families": sum(e["status"] == "TERMINAL_SUCCESS" for e in native),
            "curated_terminal_job_families": len(native),
            "curated_scope": "OVERLAPPING_EXECUTION_INSTANCES_NOT_DISTINCT_TESTS",
            "root_manifestations": sum(r["job_manifestations"] for r in d["roots"]),
            "first_red_signatures": len(d["roots"]),
            "formal_causal_root_closures": None,
            "coverage_rollup_global": None,
            "actual_worker_hours": None}


def mermaid(d):
    rows = [
        "flowchart LR",
        "  A[ABACUS native coverage / roots] --> C[CODEX W31 Mycelium consumer]",
        "  M[gg_MATH statistical provider] --> C",
        "  C -.->|unauthenticated W30 edge| Q[QPS private owner HOLD]",
        "  A --> V[MC #530 archive verifier]",
        "  C --> B[MC #531 six-repo census]",
        "  V --> H[MC #533 Method Atlas and Hub]",
        "  B --> H",
        "  H --> G[Golden Thread CP.HANDOFF / CP.RESUME]",
        "  G -.->|NEXT PULSE feedback, not same-wave execution| A",
        "  classDef hold fill:#532a2b,stroke:#e8a9a9,color:#ffffff",
        "  class Q hold",
    ]
    return "\n".join(rows) + "\n"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def build(source, out, head):
    fail_if(not SHA40.fullmatch(head), "EXACT_PRESENTATION_HEAD_REQUIRED")
    source, out = Path(source), Path(out)
    raw = source.read_bytes()
    d = validate(json.loads(raw))
    out.mkdir(parents=True, exist_ok=True)
    ledger = {"schema": OUT_SCHEMA, "presentation_head": head,
              "source_file": source.name, "source_sha256": digest(raw),
              "frozen_snapshot_id": d["snapshot_id"],
              "authority": d["authority"],
              "populations": d["populations"],
              "readiness": d["readiness"],
              "kpis": summary(d),
              "events": d["events"], "roots": d["roots"],
              "lineage": d["lineage"], "avenues": d["avenues"],
              "browser_refresh_credit": False,
              "native_cross_repo_attestation": None}
    embedded = json.dumps({"presentation_head":head,"sources":d,"kpis":summary(d)},
                          sort_keys=True,ensure_ascii=True).replace("<",r"\u003c")
    page = PAGE.replace("__SNAPSHOT_JSON__", embedded)
    (out/"index.html").write_text(page,encoding="utf-8")
    (out/"ledger.json").write_text(json.dumps(ledger,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    (out/"lineage.mmd").write_text(mermaid(d),encoding="utf-8")
    m = {"schema":"codepurple.convergence_hub.manifest.v1",
         "presentation_head":head,"source_sha256":digest(raw),
         "publisher":"EXISTING_METHOD_ATLAS_PAGES_ONLY",
         "merge_admission":"HOLD","authority_transfer":False,
         "security_waiver":False,"qps_owner_acceptance":None,
         "member_sha256":{name:digest((out/name).read_bytes()) for name in
                           ("index.html","ledger.json","lineage.mmd")}}
    (out/"manifest.json").write_text(json.dumps(m,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    verify(out,head)
    return m


def verify(out,head):
    out=Path(out)
    m=json.loads((out/"manifest.json").read_text(encoding="utf-8"))
    fail_if(m.get("presentation_head")!=head or m.get("merge_admission")!="HOLD"
            or m.get("security_waiver") is not False or m.get("authority_transfer") is not False,
            "MANIFEST_GATE_PROMOTION")
    fail_if(set(m.get("member_sha256",{})) != {"index.html","ledger.json","lineage.mmd"},
            "MANIFEST_POPULATION")
    for name,sha in m["member_sha256"].items():
        fail_if(digest((out/name).read_bytes())!=sha,"MANIFEST_HASH_MISMATCH_"+name)
    d=json.loads((out/"ledger.json").read_text(encoding="utf-8"))
    fail_if(d.get("presentation_head")!=head or d.get("browser_refresh_credit") is not False
            or d.get("native_cross_repo_attestation") is not None or
            d.get("kpis",{}).get("coverage_rollup_global") is not None,
            "LEDGER_AUTHORITY_PROMOTION")
    return m


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",default=str(HERE/SOURCE_NAME))
    p.add_argument("--out",required=True)
    p.add_argument("--head",required=True)
    p.add_argument("--verify-only",action="store_true")
    a=p.parse_args()
    m=verify(a.out,a.head) if a.verify_only else build(a.source,a.out,a.head)
    print(json.dumps({"status":"SOURCE_BOUND_PROJECTION_ONLY",
                      "presentation_head":m["presentation_head"],
                      "files":m["member_sha256"]},sort_keys=True))


if __name__=="__main__":
    main()
