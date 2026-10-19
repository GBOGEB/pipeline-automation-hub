"use strict";
/** M3 scheduler feasibility only. Authenticated ABACUS dispatch requires separate CODEX #977 promotion. */
const crypto=require("node:crypto");
const SHA=/^[a-f0-9]{40}$/;
const GATEWAY_SOURCE="GBOGEB/CODEX:mission_control/mycelium/execution_gateway_contract.yaml";
function digest(v){return crypto.createHash("sha256").update(JSON.stringify(v)).digest("hex")}
function cleanPath(v){
 if(typeof v!=="string"||!v||v.startsWith("/")||v.includes("\\")||v.split("/").some(x=>!x||x==="."||x===".."))throw Error("unsafe source path");
 return v.replace(/\/$/,"");
}
function intersects(a,b){return a===b||a.startsWith(b+"/")||b.startsWith(a+"/")}
function stage(requests,context){
 if(!Array.isArray(requests)||!requests.length)throw Error("request population missing");
 if(!context||context.origin!=="NATIVE_GITHUB_ACTIONS"||!context.actor||!Number.isInteger(context.run_id)||context.run_id<=0||!Number.isInteger(context.attempt)||context.attempt<=0)throw Error("native principal and workflow provenance required");
 if(context.gateway_mutation_enabled!==false||context.dispatch_enabled!==false)throw Error("CODEX #977 unpromoted: mutation must remain disabled");
 const seen=new Set(),locks=[],rows=[];
 for(const r of requests){
  const id=r.id;
  if(typeof id!=="string"||!id||seen.has(id))throw Error("invalid/duplicate request id");
  seen.add(id);
  if(r.repo!=="GBOGEB/ABACUS"||r.action!=="STAGE_ONLY"||r.intent!=="SOURCE_OWNER_REPAIR_PROPOSAL")throw Error("ABACUS owner-only nonmutating stage");
  if(!SHA.test(r.head_sha)||r.head_sha!==context.observed_heads?.[r.repo+"#"+r.pr])throw Error("stale or unauthenticated head");
  if(!Array.isArray(r.paths)||!r.paths.length)throw Error("declared affected paths required");
  const paths=r.paths.map(cleanPath);
  if(paths.length!==new Set(paths).size)throw Error("duplicate changed-path scope");
  if(typeof r.idempotency_key!=="string"||r.idempotency_key!==digest({id:r.id,repo:r.repo,pr:r.pr,head_sha:r.head_sha,paths,action:r.action,intent:r.intent}))throw Error("idempotency key mismatch");
  if(context.completed_keys?.includes(r.idempotency_key))throw Error("replay forbidden");
  const collisions=locks.filter(x=>paths.some(p=>x.paths.some(prev=>intersects(p,prev))));
  rows.push({id,repo:r.repo,pr:r.pr,head_sha:r.head_sha,paths,owner:"ABACUS",gateway_source:GATEWAY_SOURCE,
   decision:collisions.length?"BLOCKED_PATH_LOCK":"STAGED_NOT_DISPATCHED",
   conflicts_with:collisions.map(x=>x.id),authenticated_runner_launch:null,repository_mutation:false,
   next_action:collisions.length?"OWNER_SPLIT_OR_SERIALIZE":"CODEX_977_OWNER_GATEWAY_PROMOTION"});
  if(!collisions.length)locks.push({id,paths});
 }
 return {schema:"missioncontrol.m3.disjoint_stage.v1",workflow_run_id:context.run_id,
  workflow_attempt:context.attempt,origin:context.origin,
  principal_recorded:"github:"+context.actor,
  principal_eligibility_verified:false,
  remote_gateway_promotion:"WITHHELD",
  remote_mutation_enabled:false,merge_admission:"HOLD",
  requests:rows,lock_population:locks.length,root_closure_credit:null,accepted_rex:null};
}
function key(r){return digest({id:r.id,repo:r.repo,pr:r.pr,head_sha:r.head_sha,paths:r.paths,action:r.action,intent:r.intent})}
module.exports={stage,key,intersects,cleanPath};
