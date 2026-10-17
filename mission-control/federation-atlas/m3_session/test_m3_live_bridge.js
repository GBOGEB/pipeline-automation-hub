"use strict";
const assert=require("node:assert/strict");
const b=require("./m3_live_bridge.js");
const raw={};
for(const t of b.TARGETS){
 const k=t.repository+"#"+t.pr;
 raw[k]={run:{id:t.run,head_sha:t.source_sha,run_attempt:1,status:"completed",conclusion:t.pr===667?"success":"failure",updated_at:"2026-10-17T18:48:00Z"},
 jobs:[{id:t.run+90000000000,name:"native job",status:"completed",conclusion:t.pr===667?"success":"failure",run_id:t.run,run_attempt:1}],
 artifacts:[{id:t.run+80000000000,name:"native-artifact",workflow_run:{id:t.run},expired:false}]};
}
const o=b.build(raw,"FIXTURE","2026-10-17T18:48:12Z");
assert.equal(o.run_observations.length,3);
assert.equal(o.crosswalk.length,5);
assert.equal(o.run_observations.reduce((n,x)=>n+x.jobs.length,0),3);
assert.equal(o.authority.authenticated_remote_crew_launch,null);
assert.equal(o.authority.merge_admission,"HOLD");
assert.equal(o.matched_main_coverage,null);
assert.equal(o.matched_diff_coverage,null);
assert.equal(o.canonical_root_closed,null);
assert.equal(o.temporal_metrics.stable_or_six_sigma,null);
assert.ok(o.crosswalk.every(x=>x.edge_binding==="IDENTITY_CROSSWALK_ONLY_NOT_FEDERATION_RECEIPT"));
function reject(fn,msg){assert.throws(fn,undefined,msg)}
const clone=x=>JSON.parse(JSON.stringify(x));
let fake=clone(raw),key=b.TARGETS[1].repository+"#"+b.TARGETS[1].pr;
fake[key].run.head_sha="0000000000000000000000000000000000000000";
reject(()=>b.build(fake,"FIXTURE","2026-10-17T18:48:12Z"),"stale head");
fake=clone(raw);fake[key].jobs[0].run_id=123;
reject(()=>b.build(fake,"FIXTURE","2026-10-17T18:48:12Z"),"wrong run id");
fake=clone(raw);fake[key].jobs[0].run_attempt=2;
reject(()=>b.build(fake,"FIXTURE","2026-10-17T18:48:12Z"),"wrong attempt");
fake=clone(raw);delete fake[key].artifacts;
reject(()=>b.build(fake,"FIXTURE","2026-10-17T18:48:12Z"),"missing artifact population");
fake=clone(raw);fake[key].jobs.push(clone(fake[key].jobs[0]));
reject(()=>b.build(fake,"FIXTURE","2026-10-17T18:48:12Z"),"duplicate job");
fake=clone(raw);fake[key].artifacts[0].workflow_run.id=42;
reject(()=>b.build(fake,"FIXTURE","2026-10-17T18:48:12Z"),"wrong artifact run");
reject(()=>b.build(raw,"APPLY_MUTATION","2026-10-17T18:48:12Z"),"remote mutation forbidden");
reject(()=>b.build(raw,"FIXTURE","invalid"),"invalid observation time");
assert.ok(o.freshness.census_age_hours>=0);
console.log("PASS M3 typed 3-run / Golden Thread crosswalk / nine fail-closed assertions");
