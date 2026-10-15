"use strict";
// Additive read-only continuation; no GitHub writes, raw chat ingestion or release authority.
const fs=require("fs"),path=require("path"),crypto=require("crypto");
const ROOT=path.resolve(__dirname,"../../../..");
const M2=path.resolve(__dirname,"../M2_STATE.json");
const OVERLAY=path.resolve(ROOT,"handover/session/CODE_PURPLE_M2_LIVE_RECONCILIATION_20261015.md");
const INPUT=path.join(__dirname,"M3_INPUT.json");
const validSha=x=>typeof x==="string" && /^[0-9a-f]{40}$/.test(x);
const digest=b=>crypto.createHash("sha256").update(b).digest("hex");
const blob=b=>crypto.createHash("sha1").update(Buffer.concat([Buffer.from("blob "+b.length+"\0"),b])).digest("hex");
const reject=m=>{throw Error("M3_FAIL_CLOSED: "+m);};
const htmlEscape=x=>String(x).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function load(){
 const raw={m2:fs.readFileSync(M2),overlay:fs.readFileSync(OVERLAY),input:fs.readFileSync(INPUT)};
 return {raw,m2:JSON.parse(raw.m2),input:JSON.parse(raw.input)};
}
function validate(x,m,raw){
 if(!x||!m||x.schema!=="missioncontrol.session_m3_continuation.v1"||
    m.schema!=="missioncontrol.session_m2_portal.v1")reject("schema");
 if(x.parent_milestone!=="M2"||x.parent_intent!=="CP-SESSION-20261015-002"||
    x.milestone!=="M3"||x.time_precision!=="DATE_ONLY")reject("lineage");
 if(x.original_chat_turn_ids_available!==false||x.raw_chat_transcript_available!==false||
    x.new_intent.original_chat_message_id!==null||x.new_intent.original_message_time!==null||
    x.new_intent.parent!=="CP-M2-I06")reject("fabricated ChatGPT origin");
 if(x.merge_authorized!==false||x.authority_transfer!==false||
    x.qps_engineering_acceptance!=="DEFER"||x.full_release!=="HOLD"||
    x.sources.no_competing_ssot!==true)reject("forbidden authority promotion");
 if(blob(raw.m2)!==x.sources.m2_json_git_blob||blob(raw.overlay)!==x.sources.m2_reconciliation_git_blob)
    reject("frozen ancestor blob drift");
 const d=x.frozen_denominators;
 if(m.intents.length!==15||m.actions.length!==20||m.repos.length!==6||
    m.release_gates.length!==9||d.original_intents!==15||d.original_actions!==20||
    d.prior_added_actions!==7||d.new_actions!==4||d.new_intents!==1||
    d.repo_profiles!==6||d.original_release_gates!==9||d.original_m2_html_pages!==12)
    reject("M2 cohort or denominator changed");
 if(!Array.isArray(x.m2_action_additions)||x.m2_action_additions.length!==7||
    !Array.isArray(x.m3_new_actions)||x.m3_new_actions.length!==4)reject("incomplete continuation");
 const original=m.actions.map(a=>a.id),added=x.m2_action_additions.map(a=>a.id),
       current=x.m3_new_actions.map(a=>a.id);
 const ids=original.concat(added,current),unique=new Set(ids);
 if(unique.size!==31)reject("duplicate action IDs");
 for(let k=1;k<=20;k++)if(!original.includes("M2-A"+String(k).padStart(2,"0")))reject("lost original action");
 for(let k=21;k<=27;k++)if(added[k-21]!=="M2-A"+k)reject("lost M2 overlay action");
 for(let k=1;k<=4;k++)if(current[k-1]!=="M3-A"+String(k).padStart(2,"0"))reject("lost M3 action");
 if(new Set(m.intents.map(i=>i.id)).size!==15||!m.intents.some(i=>i.id===x.new_intent.parent))
    reject("intent ancestry incomplete");
 for(const i of m.intents){
   if(i.original_chat_message_id!==null||i.original_chat_timestamp!==null||
      !i.actions.every(a=>unique.has(a)))reject("fabricated or orphan M2 intent");
 }
 for(const a of m.actions.concat(x.m2_action_additions,x.m3_new_actions)){
   if(!a.owner||!a.state||!a.priority||!a.evidence||!(a.summary||a.done_when)||
      !a.evidence.startsWith("https://github.com/GBOGEB/"))reject("action owner/evidence incomplete");
   if(["VERIFIED","RELEASED","MERGE_ADMITTED"].includes(a.state))reject("invented action closure");
 }
 if(m.merge_authorized!==false||m.qps_decision!=="DEFER"||m.full_release!=="HOLD"||
    m.release_gates.some(g=>!["HOLD","DEFER"].includes(g.status)))reject("M2 gate promoted");
 if(!Array.isArray(x.repos)||x.repos.length!==6||
    new Set(x.repos.map(r=>r.repo)).size!==6)reject("fleet scope");
 for(const r of x.repos)if(!m.repos.some(z=>z.name===r.repo)||
    !validSha(r.sha)||r.required_checks!=="OFF"||
    typeof r.protected_flag!=="boolean")reject("fleet head/required check snapshot");
 const forecast=x.forecast_pre_registered;
 if(forecast.actual!==null||forecast.score!=="PENDING_NATIVE"||
    forecast.total_joined_actions!==31||forecast.original_intents_preserved!==15)
    reject("forecast rewritten after observation");
 if(x.retained_historical_metrics.codex_1045.ruff_findings_nonblocking!==1221||
    x.retained_historical_metrics.g1.denominator!==66||
    x.retained_historical_metrics.g1.source_discovered!==13||
    x.retained_historical_metrics.g5.same_repo_replays!==1||
    x.retained_historical_metrics.g5.cross_repo_auth_links!==0||
    x.retained_historical_metrics.qps.physical_files_unverified!==8)
    reject("historical cohort redacted/promoted");
 return true;
}
function build(x,m,raw,head){
 if(!validSha(head))reject("exact Git head required");
 validate(x,m,raw);
 const items=m.actions.map(a=>Object.assign({origin:"M2_ORIGINAL"},a)).concat(
   x.m2_action_additions.map(a=>Object.assign({origin:"M2_ADDED"},a)),
   x.m3_new_actions.map(a=>Object.assign({origin:"M3_NEW"},a)));
 const stateCounts={};for(const a of items)stateCounts[a.state]=(stateCounts[a.state]||0)+1;
 return {schema:"missioncontrol.session_m3_projection.v1",
   source_sha:head,m2_blob:blob(raw.m2),m2_reconciliation_blob:blob(raw.overlay),
   intake_sha256:digest(raw.input),snapshot_date:x.capture_date_utc,
   data_class:"SANITIZED_SEMANTIC_LOSSLESS_NOT_RAW_TRANSCRIPT",
   intents:m.intents.concat([x.new_intent]),actions:items,release_gates:m.release_gates,
   repo_heads:x.repos,retained_metrics:x.retained_historical_metrics,
   forecast:x.forecast_pre_registered,pulse_contract:x.pulse_contract,
   action_counts:stateCounts,counts:{intents:16,actions:31,original_actions:20,
   m2_added:7,m3_new:4,repositories:6,release_gates:9},
   verified_chat_message_ids:0,live_worker_count:null,live_docker_ports:null,
   cross_repo_qps_acceptances:0,merge_authorized:false,qps:"DEFER",release:"HOLD",authority_transfer:false};
}
function fullMd(r){
 const l=["# CODE PURPLE — FULL M3 action and intent handover","",
 "**Class:** bounded source-backed semantic retention, NOT a complete ChatGPT transcript.",
 "**Source head:** "+r.source_sha+"; **M2 blob:** "+r.m2_blob+"; **overlay blob:** "+r.m2_reconciliation_blob,
 "**Release:** HOLD / QPS DEFER / reviewer and protection NOT established.","",
 "## All inherited intents (15) and current follow-up (1)",""];
 for(const i of r.intents)l.push("- "+i.id+"; parent "+i.parent+"; "+i.summary+
 (i.actions?"; mapped actions "+i.actions.join(", "):"; continuation intent")+
 "; original ChatGPT message ID/time UNKNOWN.");
 l.push("","## All actions (20 original + 7 M2 addenda + 4 M3)","","Every action remains traceable. Status is preserved, not automatically promoted.","");
 for(const a of r.actions)l.push("- [ ] "+a.id+" ["+a.priority+" / "+a.state+" / "+a.origin+"] "+
 a.owner+" — "+(a.summary||a.done_when)+". Exit: "+(a.done_when||a.summary)+
 ". [GitHub evidence/owner]("+a.evidence+").");
 l.push("","## Release predicates (noncompensating)","");
 for(const g of r.release_gates)l.push("- "+g.status+" — "+g.name+"; "+g.owner+"; proof: "+g.proof+".");
 l.push("","## Frozen fleet heads / NOT current without refresh","");
 for(const q of r.repo_heads)l.push("- "+q.repo+" "+q.branch+" "+q.sha+
 "; protected flag="+q.protected_flag+"; required checks="+q.required_checks+".");
 l.push("","## Root causes and comparability","");
 l.push("- CODEX #1043/#1044 historical CI failures survive their merges; #1045 targeted parity fixed on its own exact head.");
 l.push("- CODEX Ruff historical 1,221 findings are not unique resolved roots; current Ruff count requires fresh scan.");
 l.push("- G1 13/66 discovered, G5 1 same-repo authenticated replay, and 0 full QPS accepted hops have different populations.");
 l.push("- QPS 70/90 obligations, 36/45 breadth, 34/45 depth and eight original physical files are historical cohort controls.");
 l.push("- No invented Docker, port, LLDB, LDAB, MCP, crew, runner, calendar, original chat IDs or approval.");
 l.push("","## Next admissible stabilization pulse","");
 l.push("1. Re-census actual repo heads, effective checks/reviews and PR security before claiming integration.");
 l.push("2. Native exact-SHA handover generation, full negative controls, unchanged 12-page M2 portal and 19 Golden Thread tests.");
 l.push("3. Fix first attributable current CODEX/ABACUS first-red through existing disjoint owners; maintain security/A10.");
 l.push("4. Obtain exact-source KEB → DOW → QPS consumer receipts and QPS engineering decision.");
 l.push("5. Bind the eight genuine QPS controlled input bytes, #75/#943 decisions, render and qualify outward assets.");
 l.push("6. Admit only with independent review, effective required checks, exact-main CI and release-owner decision.");
 l.push("","## Lossless checkpoint stop rule","");
 l.push("After 3–5 material waves, source drift, conflict or overlong chat, publish next GitHub state, preserve every HOLD, provide concise drop-in and stop. The two-clock provenance is intent ordering versus Git exact-SHA/CI. Do not overwrite original M2 source.");
 return l.join("\n")+"\n";
}
function dropin(r){
 return [
 "# CODE PURPLE — M3 GitHub-only lossless drop-in","",
 "Continue MissionControl #153, following the current M3 native receipt. Read M2_STATE.json, original M2 lossless Markdown, M2 LIVE_RECONCILIATION, M3_INPUT.json, generated M3_FULL_HANDOVER.md and M3_MANIFEST.json. Verify current HEAD and exact native proof BEFORE execution.",
 "",
 "Preserve 15 original intents + M3 follow-up and ALL 20 original + 7 M2 added + 4 M3 actions (31), each with status/owner/proof. Original ChatGPT message IDs and timestamps UNKNOWN. Refresh 6 repository heads, CI, run/job/attempt, branch protection and eligible review.",
 "",
 "Current frozen MissionControl master "+r.repo_heads[0].sha+" is historical after handover. Required checks were OFF in all six latest inspected repos. Do not interpret past merged PRs as governed admission. CODEX 1221 Ruff findings are historical raw findings, ABACUS first-red pending, 8 physical QPS objects pending, full QPS ACCEPT 0. Exact-source KEB/DOW/QPS remains DEFER.",
 "",
 "First safe pulse: native handover/Golden Thread DoV, source-level red repair, owner-side protection/review, true cross-repo consumer replay, QPS safety/physical source, controlled binaries. No merges/waivers/release from this chat. Do not create ZIP/TAR handover, duplicate SSOT or make up worker/port counts.",
 "",
 "Keep main answer brief; when conversation grows long, checkpoint source JSON/Markdown/HTML in GitHub and stop.",
 ""].join("\n");
}
function dag(){
 return ['flowchart TD',
 ' U["New user intent"] --> S["Frozen M2 + additive M3"]',
 ' S --> V{"Source blob / privacy / 31 actions valid?"}',
 ' V -->|no| H["HOLD + owner repair"]',
 ' V -->|yes| P["Deterministic JSON / MD / HTML / DAG"]',
 ' P --> C["Native exact-head receipt + byte QA"]',
 ' C --> K["CODEX KEB challenge"]',
 ' K --> D["ABACUS DOW consumer"]',
 ' D --> Q{"QPS engineering disposition"}',
 ' Q -->|DEFER/REJECT| H',
 ' Q -->|ACCEPT| A{"Protection / eligible review?"}',
 ' A -->|no| H',
 ' A -->|yes| R["Governed release + exact-main REX"]',
 ' R -.->|"new logical N"| U',''].join("\n");
}
function html(r){
 const e=htmlEscape;
 const cards=[["Intents","16"],["Actions","31"],["Repositories","6"],["Enforced check sets","0/6"],["QPS accepted","0"],["Release gates","9 HOLD/DEFER"]].map(
   z=>'<section class="card"><small>'+e(z[0])+'</small><strong>'+e(z[1])+'</strong></section>').join("");
 const rows=r.actions.map(a=>'<tr data-search><td data-label="Action ID">'+e(a.id)+'</td><td data-label="Owner">'+e(a.owner)+'</td><td data-label="Disposition">'+e(a.state)+
 '</td><td data-label="Action / exit">'+e(a.summary||a.done_when)+'</td><td data-label="Evidence"><a href="'+e(a.evidence)+'">Owner</a></td></tr>').join("");
 const repos=r.repo_heads.map(x=>'<tr><td>'+e(x.repo)+'</td><td><code>'+e(x.sha)+'</code></td><td>'+e(x.required_checks)+'</td></tr>').join("");
 return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'+
 '<title>CODE PURPLE M3 — Lossless handover</title><style>:root{color-scheme:dark;--b:#101010;--f:#fafafa;--m:#bbb;--s:#222;--l:#444}*{box-sizing:border-box}body{margin:0;background:var(--b);color:var(--f);font:15px/1.5 system-ui,sans-serif}main{max-width:1140px;margin:auto;padding:24px 18px;overflow-wrap:anywhere}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(165px,1fr));gap:12px}.card{border:1px solid var(--l);padding:13px;border-radius:7px;background:var(--s)}small{color:var(--m)}strong{display:block;font-size:1.5rem}h1{font-size:1.6rem}h2{margin-top:30px;font-size:1.2rem}.scroller{overflow-x:auto}table{border-collapse:collapse;min-width:680px;width:100%}th,td{text-align:left;padding:10px;vertical-align:top;border-bottom:1px solid var(--l)}input{max-width:100%;padding:10px;background:var(--s);color:var(--f);border:1px solid var(--l);border-radius:7px}a{color:inherit}code{overflow-wrap:anywhere}@media(max-width:640px){.action-table{min-width:0}.action-table thead{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}.action-table tr[data-search]{display:block;margin:12px 0;padding:10px;border:1px solid var(--l);border-radius:8px;background:var(--s)}.action-table tr[data-search][hidden]{display:none}.action-table td{display:block;padding:6px 0;border:0;overflow-wrap:anywhere}.action-table td::before{content:attr(data-label);display:block;color:var(--m);font-size:.78rem;text-transform:uppercase}}@media(prefers-color-scheme:light){:root{color-scheme:light;--b:white;--f:#171717;--m:#555;--s:#fafafa;--l:#ddd}}</style></head><body><main>'+
 '<h1>CODE PURPLE — M3 lossless continuation</h1><p>Source-bound read-only snapshot, not a live GitHub or local agent console. All QPS release predicates remain HOLD/DEFER.</p>'+
 '<div class="grid">'+cards+'</div><h2>Action carryover — 20+7+4</h2><input type="search" id="search" aria-label="Filter action register" placeholder="Search action or owner">'+
 '<div class="scroller"><table class="action-table"><thead><tr><th>ID</th><th>Owner</th><th>Status</th><th>Action and exit</th><th>Evidence</th></tr></thead><tbody>'+rows+'</tbody></table></div>'+
 '<h2>Pinned repo heads — historical</h2><div class="scroller"><table><thead><tr><th>Repository</th><th>Exact SHA</th><th>Required checks</th></tr></thead><tbody>'+repos+'</tbody></table></div>'+
 '<p>Source SHA: <code>'+e(r.source_sha)+'</code> · M2 blob: <code>'+e(r.m2_blob)+'</code> · QPS DEFER; release HOLD; original chat message IDs UNKNOWN.</p>'+
 '<script>document.getElementById("search").addEventListener("input",function(){const s=this.value.toLowerCase();document.querySelectorAll("[data-search]").forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(s))})</script></main></body></html>';
}
function filesFor(x,m,raw,head){
 const report=build(x,m,raw,head);
 const files={"M3_INDEX.json":JSON.stringify(report,null,2)+"\n",
   "M3_FULL_HANDOVER.md":fullMd(report),"M3_DROPIN.md":dropin(report),
   "M3_DAG.mmd":dag(),"M3_DASHBOARD.html":html(report)};
 const manifest={schema:"missioncontrol.m3_manifest.v1",source_sha:head,m2_blob:report.m2_blob,
   overlay_blob:report.m2_reconciliation_blob,intake_sha256:report.intake_sha256,items:{},
   counts:report.counts,structural_qa:"PASS",browser_visual_qa:"DEFER",
   release:"HOLD",qps:"DEFER",merge_authorized:false};
 for(const key of Object.keys(files).sort())manifest.items[key]={sha256:digest(Buffer.from(files[key])),bytes:Buffer.byteLength(files[key])};
 files["M3_MANIFEST.json"]=JSON.stringify(manifest,null,2)+"\n";return files;
}
function main(){
 const args=process.argv.slice(2),o=args.indexOf("--out"),s=args.indexOf("--source-sha");
 const dest=o>=0?args[o+1]:null,head=s>=0?args[s+1]:null;
 if(!dest||!validSha(head))reject("expected --out DIR --source-sha SHA40");
 const {raw,m2,input}=load(),outputs=filesFor(input,m2,raw,head);
 const check=args.includes("--check");
 if(!check)fs.mkdirSync(dest,{recursive:true});
 for(const [key,value] of Object.entries(outputs)){
   const file=path.join(dest,key);
   if(check){if(!fs.existsSync(file)||fs.readFileSync(file,"utf8")!==value)reject("generated output drift "+key);}
   else fs.writeFileSync(file,value,"utf8");
 }
 console.log(JSON.stringify({schema:"missioncontrol.m3_native_producer.v1",
   source_sha:head,outputs:Object.keys(outputs).length,intents:16,actions:31,
   status:"PASS",release:"HOLD",merge_authorized:false}));
}
if(require.main===module){try{main();}catch(e){console.error(e.stack);process.exitCode=2;}}
module.exports={load,validate,build,filesFor,html,fullMd,dropin,dag,blob};
