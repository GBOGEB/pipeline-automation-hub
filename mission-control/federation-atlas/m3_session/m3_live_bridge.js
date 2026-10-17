"use strict";
/** M3 read-only native telemetry join. Does not dispatch or grant authority. */
const fs=require("node:fs"),path=require("node:path"),crypto=require("node:crypto");
const ROOT=path.resolve(__dirname,"../../..");
const {queueP95}=require("./m3_metrics.js");
const SHA=/^[0-9a-f]{40}$/;
const TARGETS=[
 {repository:"GBOGEB/pipeline-automation-hub",pr:667,run:39059653346,source_sha:"93e3e977e0937624c342f1890578f8854c843c03"},
 {repository:"GBOGEB/ABACUS",pr:2162,run:39056877380,source_sha:"e053a4898fc74018b83092b0d2f8af2f4a909eb0"},
 {repository:"GBOGEB/ABACUS",pr:2161,run:39056628120,source_sha:"3d5554b7a62adc4b3df1760b7959fb390b7976c9"}
];
function assert(ok,message){if(!ok)throw new Error(message)}
function sha256(v){return crypto.createHash("sha256").update(v).digest("hex")}
function getJSON(rel){const b=fs.readFileSync(path.join(ROOT,rel));return {value:JSON.parse(b.toString("utf8")),sha256:sha256(b)}}
function validate(data){
 const {value:s,sha256:state_sha256}=getJSON("docs/mission-control/m3/state.json");
 const {value:c,sha256:census_sha256}=getJSON("docs/code-purple-live/snapshot.json");
 const gold=fs.readFileSync(path.join(ROOT,"mission-control/golden-thread/GOLDEN_THREAD_EVENT_SCHEMA_v1.json"));
 const atlas=fs.readFileSync(path.join(ROOT,"mission-control/federation-atlas/ATLAS_GRAPH_v1.yaml"));
 assert(s.schema==="missioncontrol.m3.readonly_projection.v1" && s.authority.merge_admission==="HOLD" && s.authority.remote_mutation_enabled===false,"M3 source authority");
 assert(c.schema==="codepurple.disjoint_live_census.v1" && c.authority.merge_authorized===false && c.authority.root_closures_verified===null,"live census authority");
 assert(c.authority.crew_dispatch==="STAGED_NOT_LAUNCHED" && c.authority.security_waiver===false,"live census non-authority");
 assert(c.repositories.every(r=>SHA.test(r.sha)) && s.repos.every(r=>SHA.test(r.sha)),"source SHA");
 assert(s.nodes.length===new Set(s.nodes.map(n=>n.id)).size,"duplicate M3 nodes");
 const set=new Set(s.nodes.map(n=>n.id));
 for(const e of s.edges)assert(set.has(e.from)&&set.has(e.to),"dangling M3 edge");
 assert(JSON.parse(gold).$id==="missioncontrol.golden_thread_ledger.v1","Golden Thread canonical source absent");
 assert(atlas.includes("missioncontrol.federation_atlas.graph.v1"),"Atlas source absent");
 return {m3:s,census:c,sources:{
  m3_state_sha256:state_sha256,live_census_sha256:census_sha256,
  golden_thread_event_schema_sha256:sha256(gold),
  federation_atlas_graph_sha256:sha256(atlas)
 }};
}
function bind(run,jobs,artifacts,target){
 assert(run&&run.id===target.run&&run.head_sha===target.source_sha,"run/source SHA mismatch");
 assert(SHA.test(run.head_sha)&&Number.isInteger(run.run_attempt)&&run.run_attempt>0,"run/attempt missing");
 assert(Array.isArray(jobs),"jobs population missing");
 assert(Array.isArray(artifacts),"artifacts population missing");
 const seen=new Set(),bound=[];
 for(const j of jobs){
  assert(Number.isInteger(j.id)&&j.id>0&&!seen.has(j.id),"invalid/duplicate job");
  seen.add(j.id);
  assert(j.run_id===undefined||j.run_id===run.id,"job/run mismatched");
  assert(j.run_attempt===undefined||j.run_attempt===run.run_attempt,"job attempt mismatched");
  bound.push({job_id:j.id,job_name:j.name||null,run_id:run.id,run_attempt:run.run_attempt,
   state:j.status||null,conclusion:j.conclusion??null,
   created_at:j.created_at||null,started_at:j.started_at||null,
   url:j.html_url||`https://github.com/${target.repository}/actions/runs/${run.id}/job/${j.id}`});
 }
 const distinctArtifacts=new Set(),boundArtifacts=[];
 for(const a of artifacts){
  assert(Number.isInteger(a.id)&&a.id>0&&!distinctArtifacts.has(a.id),"artifact identity");
  distinctArtifacts.add(a.id);
  assert(a.workflow_run?.id===undefined||a.workflow_run.id===run.id,"artifact/run mismatched");
  boundArtifacts.push({artifact_id:a.id,name:a.name||null,expired:a.expired??null,
   url:a.archive_download_url||`https://api.github.com/repos/${target.repository}/actions/artifacts/${a.id}/zip`,
   run_id:run.id,run_attempt:run.run_attempt});
 }
 return {repository:target.repository,pr:target.pr,source_sha:target.source_sha,run_id:run.id,run_attempt:run.run_attempt,
  run_state:run.status||null,conclusion:run.conclusion??null,
  updated_at:run.updated_at||null,url:run.html_url||`https://github.com/${target.repository}/actions/runs/${run.id}`,
  jobs:bound,artifacts:boundArtifacts,observed_jobs:bound.length,observed_artifacts:boundArtifacts.length,
  authenticated_native_run:true,authenticated_codex_to_abacus_crew_launch:null,merge_admission:"HOLD"};
}
function crosswalk(m3,census){
 const aliases={MC:"pipeline-automation-hub",CODEX:"CODEX",ABACUS:"ABACUS",QPS:"cryoplant-project",MATH:"gg_MATH"};
 return Object.entries(aliases).map(([m3_id,repo])=>{
  const source=census.repositories.find(r=>r.name===repo)||null;
  const current=m3.repos.find(r=>r.id===m3_id);
  return {m3_id,canonical_live_census_node_id:"repo:"+repo,
   source_snapshot_sha:source?.sha??null,display_snapshot_sha:current?.sha??null,
   source_heads_match:source?.sha===current?.sha?true:source?false:null,
   edge_binding:"IDENTITY_CROSSWALK_ONLY_NOT_FEDERATION_RECEIPT",
   golden_thread_subject_ref:"repo:GBOGEB/"+repo};
 });
}
function build(raw,mode,now){
 const {m3,census,sources}=validate();
 assert(mode==="FIXTURE"||mode==="NATIVE_GITHUB_READ","observation mode");
 const seen=new Set();
 const rows=TARGETS.map(target=>{
  const key=target.repository+"#"+target.pr;
  assert(!seen.has(key),"duplicate target");seen.add(key);
  const candidate=raw[key];
  assert(candidate&&candidate.run&&candidate.jobs&&candidate.artifacts,"missing run/job/artifact population: "+key);
  return bind(candidate.run,candidate.jobs,candidate.artifacts,target);
 });
 const censusTime=Date.parse(census.observed_at_utc);
 const observed=Date.parse(now);
 assert(Number.isFinite(censusTime)&&Number.isFinite(observed),"invalid observation clock");
 const ages={census_age_hours:Math.round((observed-censusTime)/360000)/10,
  census_stale_by_24h:observed-censusTime>86400000};
 return {schema:"missioncontrol.m3.telemetry_observation.v1",observed_at_utc:now,mode,
  source_identity:{...sources,m3_projection_source_sha:m3.source_sha,live_census_digest:census.source_digest||null},
  crosswalk:crosswalk(m3,census),freshness:ages,run_observations:rows,
  matched_main_coverage:null,matched_diff_coverage:null,canonical_root_open:null,canonical_root_closed:null,
  temporal_metrics:{matched_series_points:null,root_recurrence:null,queue_p95_minutes:null,
   per_run_queue_samples:rows.map(r=>({run_id:r.run_id,source_sha:r.source_sha,...queueP95(r.jobs)})),
   native_run_observation_count:rows.length,stable_or_six_sigma:null,
   qualification:"NO_MATCHED_TEMPORAL_SERIES_DO_NOT_FIT_PCA_BT_OR_CONVERGENCE"},
  authority:{merge_admission:"HOLD",correctly_governed_main_merge_verified:false,
   authenticated_remote_crew_launch:null,accepted_rex:null,root_closure_credit:null,
   security_waiver:false,remote_mutation:false,qps_decision:"DEFER"},
  notes:["Native run/job/artifact identities are associated to pinned run IDs; checkout attestation requires the native job receipt.",
   "Historical live-census source timestamps are not relabelled as refreshed observations.",
   "Golden Thread crosswalk carries identity references and hashes, never writes the canonical ledger.",
   "No cross-repo credential, worker dispatch, API mutation, or Pages publication."]};
}
async function get(url){
 const res=await fetch(url,{headers:{Accept:"application/vnd.github+json","User-Agent":"MissionControl-M3-readonly/1.0"},signal:AbortSignal.timeout(15000)});
 if(!res.ok)throw Error("GitHub GET "+res.status+" for "+url);
 return res.json();
}
async function live(){
 const records={};
 for(const t of TARGETS){
  const api=`https://api.github.com/repos/${t.repository}/actions/runs/${t.run}`;
  const run=await get(api);
  const jobs=await get(api+"/jobs?per_page=100");
  const artifacts=await get(api+"/artifacts?per_page=100");
  assert((jobs.total_count??jobs.jobs.length)===jobs.jobs.length,"jobs pagination incomplete");
  assert((artifacts.total_count??artifacts.artifacts.length)===artifacts.artifacts.length,"artifacts pagination incomplete");
  records[t.repository+"#"+t.pr]={run,jobs:jobs.jobs,artifacts:artifacts.artifacts};
 }
 return records;
}
async function main(){
 const mode=process.argv.includes("--live")?"NATIVE_GITHUB_READ":"FIXTURE";
 const arg=process.argv.indexOf("--out"),out=arg>=0?process.argv[arg+1]:null;
 assert(out,"--out path required");
 const fixture=process.argv.indexOf("--fixture");
 const raw=mode==="NATIVE_GITHUB_READ"?await live():JSON.parse(fs.readFileSync(process.argv[fixture+1],"utf8"));
 const now=mode==="NATIVE_GITHUB_READ"?new Date().toISOString(): "2026-10-17T18:48:12Z";
 const observation=build(raw,mode,now);
 fs.mkdirSync(path.dirname(out),{recursive:true});
 fs.writeFileSync(out,JSON.stringify(observation,null,2)+"\n");
 console.log(JSON.stringify({schema:observation.schema,rows:observation.run_observations.length,
  job_counts:observation.run_observations.map(x=>x.observed_jobs),
  census_stale:observation.freshness.census_stale_by_24h,mode}));
}
if(require.main===module)main().catch(e=>{console.error(e.message);process.exitCode=1});
module.exports={validate,bind,build,crosswalk,TARGETS};
