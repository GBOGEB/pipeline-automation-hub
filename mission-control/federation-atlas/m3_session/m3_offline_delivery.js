"use strict";
/** M3 artifact adapter: makes a one-click, no-fetch offline HTML. No Pages permission. */
const fs=require("node:fs"),path=require("node:path"),crypto=require("node:crypto");
const sha=b=>crypto.createHash("sha256").update(b).digest("hex");
const ensure=(ok,msg)=>{if(!ok)throw Error("M3_OFFLINE_FAIL_CLOSED: "+msg)};
function make(site,checkoutSha){
 ensure(/^[0-9a-f]{40}$/.test(checkoutSha),"exact checkout SHA required");
 const folder=path.resolve(site,"docs/mission-control/m3");
 const stateBytes=fs.readFileSync(path.join(folder,"state.json"));
 const telemetryBytes=fs.readFileSync(path.join(folder,"telemetry.json"));
 const state=JSON.parse(stateBytes.toString()),telemetry=JSON.parse(telemetryBytes.toString());
 ensure(state.schema==="missioncontrol.m3.readonly_projection.v1"&&state.authority.merge_admission==="HOLD"&&state.authority.remote_mutation_enabled===false,"state authority");
 ensure(telemetry.schema==="missioncontrol.m3.telemetry_observation.v1"&&telemetry.authority.merge_admission==="HOLD"&&telemetry.authority.remote_mutation===false&&telemetry.authority.security_waiver===false,"telemetry authority");
 ensure(telemetry.source_identity?.m3_state_sha256===sha(stateBytes),"cross-source digest mismatch");
 ensure(state.nodes.length===29&&state.edges.length===32&&state.repos.length===6,"source counts changed");
 let html=fs.readFileSync(path.join(folder,"index.html"),"utf8");
 const assertOnce=(needle)=>ensure(html.split(needle).length===2,"unique HTML slot missing: "+needle.slice(0,50));
 const put=(a,b)=>{assertOnce(a);html=html.replace(a,b)};
 const embeddedState=stateBytes.toString("base64"),embeddedTelemetry=telemetryBytes.toString("base64");
 const renderOffline=[
 "function renderInline(){",
 ' try{',
 '  const data=JSON.parse(atob("'+embeddedState+'"));',
 '  const t=JSON.parse(atob("'+embeddedTelemetry+'"));',
 '  if(data.schema!=="missioncontrol.m3.readonly_projection.v1"||data.authority.merge_admission!=="HOLD"||data.authority.remote_mutation_enabled!==false||data.authority.security_waiver!==false)throw Error("State authority mismatch");',
 '  if(t.schema!=="missioncontrol.m3.telemetry_observation.v1"||t.authority.merge_admission!=="HOLD"||t.authority.remote_mutation!==false||t.authority.security_waiver!==false||t.source_identity.m3_state_sha256!=="'+sha(stateBytes)+'")throw Error("Telemetry digest mismatch");',
 '  $("err").hidden=true;render(data);',
 '  const out=$("liveTelemetry");clear(out);',
 '  put(out,cell("p","OFFLINE PINNED · "+t.observed_at_utc+" (NOT LIVE)"),',
 '    cell("p","SHA-256 state: "+t.source_identity.m3_state_sha256));',
 '  t.run_observations.forEach(r=>{let d=document.createElement("details");put(d,cell("summary",r.repository+" PR #"+r.pr+" · "+r.conclusion+" · "+r.observed_jobs+" jobs"),',
 '    cell("p","Source: "+r.source_sha+" · run "+r.run_id+" attempt "+r.run_attempt),anchor(r.url,"Source-bound native run"));out.append(d)});',
 '  put(out,cell("p","Remote Crew / accepted REX / matched coverage / verified engineering root closures remain UNKNOWN. P0 HOLD."));',
 ' }catch(e){$("err").hidden=false;$("err").textContent="Offline bundle rejected: "+e.message}',
 "}"
 ].join("\n");
 put("async function load()",renderOffline+"\nasync function load()");
 put('$("reload").addEventListener("click",load)','$("reload").addEventListener("click",renderInline)');
 put(');load();\n</script>',');renderInline();\n</script>');
 put('<title>Mission Control M3 — Federation Flightdeck</title>','<title>Mission Control M3 — OFFLINE Flightdeck</title>');
 put('<main><p id="err"','<main><p style="padding:9px 12px;border:1px solid #a47842;border-radius:8px">OFFLINE REVIEW · source-bound historical snapshot and native telemetry embedded. No hosted Pages, active refresh, dispatch, review or QPS admission is claimed.</p><p id="err"');
 const css='.shell{min-width:0;max-width:100%}.shell>.stack{min-width:0;max-width:100%}.panel{min-width:0;max-width:100%;overflow-wrap:anywhere}.scroll,.viewport{max-width:100%}@media(max-width:1050px){.shell{grid-template-columns:minmax(0,1fr)}}';
 put("</style></head><body>",css+"</style></head><body>");
 for(const p of ["index.html","pipeline.html","federation.html"]){
  put('href="../m2/'+p+'"','href="https://github.com/GBOGEB/pipeline-automation-hub/blob/'+checkoutSha+'/docs/mission-control/m2/'+p+'"');
 }
 put('href="../../code-purple-live/index.html"','href="https://github.com/GBOGEB/pipeline-automation-hub/blob/'+checkoutSha+'/docs/code-purple-live/index.html"');
 ensure(html.includes("renderInline();")&&!html.includes(");load();\n</script>"),"standalone auto-boot failed");
 ensure(!html.includes('github_pat_'),"credential string detected");
 return {html,receipt:{schema:"missioncontrol.m3.offline_delivery.v1",exact_checkout_sha:checkoutSha,source_state_sha256:sha(stateBytes),source_telemetry_sha256:sha(telemetryBytes),
  standalone_sha256:sha(Buffer.from(html,"utf8")),standalone_bytes:Buffer.byteLength(html,"utf8"),entrypoint:"M3_OPEN_ME_OFFLINE.html",
  evidence_level:"OFFLINE_PROJECTION_CANDIDATE",mode:"FULLY_INLINE_NO_FETCH",authority:"HOLD",hosted_pages_verified:null}};
}
if(require.main===module){
 try{const args=process.argv;const get=k=>args[args.indexOf(k)+1];ensure(["--site","--sha","--out"].every(k=>args.includes(k)),"usage --site --sha --out");
 const result=make(get("--site"),get("--sha"));const out=path.resolve(get("--out"));fs.mkdirSync(path.dirname(out),{recursive:true});fs.writeFileSync(out,result.html);
 fs.writeFileSync(path.join(path.dirname(out),"offline-delivery-receipt.json"),JSON.stringify(result.receipt,null,2)+"\n");console.log("M3 standalone generated "+result.receipt.standalone_sha256)}
 catch(e){console.error(e.message);process.exitCode=1}
}
module.exports={make};
