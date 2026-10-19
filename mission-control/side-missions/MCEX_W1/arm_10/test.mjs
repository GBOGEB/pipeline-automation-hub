import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {validProfile,request,assess,suite,scenarios} from "./probe.mjs";
const profile=JSON.parse(readFileSync(new URL("./arm.json",import.meta.url),"utf8"));
test("profile remains nonmutating",()=>{
  assert.equal(validProfile(profile),true);
  assert.equal(profile.mutation_enabled,false);
  assert.equal(profile.remote_mutation_enabled,false);
  assert.deepEqual(profile.enabled_mutation_transports,[]);
});
test("all cases have identical expected decision population",()=>{
  const a=scenarios();assert.equal(a.length,22);
  assert.equal(a.filter(x=>x.expected==="LAB_ROUTE_PLAN_ONLY").length,2);
  assert.equal(new Set(a.map(x=>x.id)).size,22);
});
test("all twenty negative fixtures fail closed",()=>{
  const s=suite(profile);assert.equal(s.metrics.negative_cases,20);
  assert.equal(s.metrics.rejected_negatives,20);
  assert.equal(s.metrics.false_green,0);
});
test("gate conditions are independent and noncompensating",()=>{
  const keys=["ci","security","independent_review","owner"];
  for(const k of keys){
    const r=request("isolated-"+k);r.simulated_gates[k]="UNKNOWN";
    assert.equal(assess(r,profile).decision,"HOLD");
  }
});
test("A-B-A ancestry changes fail even when SHA returns to A",()=>{
  const r=request("aba");r.target.observed_epoch+=2;
  assert.equal(assess(r,profile).reason,"ABA_ANCESTRY_REJECTED");
});
test("completed idempotency key cannot be replayed in the same session",()=>{
  const r=request("replay"),seen=new Set();
  assert.equal(assess(r,profile,seen).decision,"LAB_ROUTE_PLAN_ONLY");
  assert.equal(assess(r,profile,seen).reason,"REPLAY_OF_COMPLETED_PLAN");
});
test("client forged identity cannot replace server binding",()=>{
  const r=request("bad-identity");r.principal.attested_by="CLIENT";
  assert.equal(assess(r,profile).reason,"CLIENT_ASSERTED_IDENTITY_REJECTED");
});
test("security and QPS credit cannot be forged",()=>{
  for(const key of ["security_waiver","claim_qps_engineering_acceptance","force_merge"]){
    const r=request("attempt-"+key);r[key]=true;
    assert.equal(assess(r,profile).decision,"HOLD");
  }
});
test("remote mutations and foreign owner applies never route",()=>{
  const r=request("remote-mut");r.remote_action="REMOTE_MUTATE";
  assert.equal(assess(r,profile).reason,"MUTATION_ACTION_DENIED");
  const wrong=request("wrong");wrong.target.repository="GBOGEB/ABACUS";
  assert.equal(assess(wrong,profile).reason,"REMOTE_TARGET_CANNOT_OWN_APPLY");
});
test("factorial action offers exactly follow arm, not authority",()=>{
  const s=suite(profile);
  assert.equal(s.metrics.positive_plans,2);
  assert.equal(s.metrics.local_shadow_plans,profile.local_shadow?2:0);
  assert.equal(s.metrics.remote_return_plans,profile.remote_readonly?2:0);
  assert.equal(s.boundary.remote_dispatch_executed,false);
});
test("not a GitHub write, actual CI, review or engineering acceptance",()=>{
  const s=suite(profile);
  assert.equal(s.metrics.git_writes,0);assert.equal(s.metrics.remote_writes,0);
  assert.equal(s.boundary.merge_admission,"HOLD");
  assert.equal(s.boundary.native_ci_proven,false);
  assert.equal(s.boundary.real_reviewer_proven,false);
  assert.equal(s.boundary.qps_acceptance,false);
});
test("reject hypothetical enabling of a production mutation transport",()=>{
  for(const update of [
    {mutation_enabled:true},{remote_mutation_enabled:true},
    {enabled_mutation_transports:["GITHUB_APP"]},{merge_admission:"GO"},
    {security_waiver:true}
  ]){
    assert.throws(()=>validProfile({...profile,...update}),/MCEX_FAIL_CLOSED_PROFILE/);
  }
});
test("shadow plan has no actual IO even when enabled",()=>{
  const r=assess(request("local"),profile);
  assert.equal(r.git_writes,0);assert.equal(r.remote_writes,0);
  assert.equal(r.local_shadow_modified,profile.local_shadow);
});
