/** MissionControl safety experiment, FIXTURES ONLY. No GitHub client, network, subprocess or repository mutation. */
import {createHash} from "node:crypto";
export const CODEx_SHA="493145eea784d39f57ea64a730af9f3e85586714";
export const HUB_BASE="0b6a6f1a062ecdcba4e532aa101735b54ab09911";
const ALLOWED_PATH="mission_control/mycelium/control_plane_projection.json";
const SHA=/^[a-f0-9]{40}$/;
const hash=value=>createHash("sha256").update(value).digest("hex");
const clone=v=>structuredClone(v);
export const digestRequest=r=>hash(JSON.stringify([r.target.repository,r.target.ref,r.target.expected_sha,r.target.request_epoch,r.path,r.nonce,r.action,r.remote_target]));
export function validProfile(p){
  if(p.schema!=="missioncontrol.mcex.arm.v1"||!["00","01","10","11"].includes(p.arm)
     ||p.controlled_main_sha!==HUB_BASE||p.codex_observed_main_sha!==CODEx_SHA
     ||p.simulation_only!==true||p.mutation_enabled!==false
     ||p.remote_mutation_enabled!==false||p.enabled_mutation_transports.length!==0
     ||p.merge_admission!=="HOLD"||p.security_waiver!==false
     ||typeof p.local_shadow!=="boolean"||typeof p.remote_readonly!=="boolean"
     ||p.arm!==(p.local_shadow?"1":"0")+(p.remote_readonly?"1":"0"))
      throw Error("MCEX_FAIL_CLOSED_PROFILE");
  return true;
}
export function request(nonce="case-positive-01",remote_target="GBOGEB/ABACUS"){
  const r={
    nonce, target:{repository:"GBOGEB/CODEX",ref:"main",expected_sha:CODEx_SHA,
      observed_sha:CODEx_SHA,request_epoch:7,observed_epoch:7},
    action:"STAGE_ONLY",path:ALLOWED_PATH,remote_target,remote_action:"READ_ONLY_RETURN_REQUEST",
    principal:{attested_by:"SERVER_FIXTURE_NOT_REAL_AUTH",server_bound:true},
    simulated_gates:{ci:"SIM_PASS",security:"SIM_PASS",independent_review:"SIM_PASS",owner:"SIM_PASS"},
    dry_run:{receipt_head:CODEx_SHA,after_sha:null,result:"SIMULATED_ONLY"},
    native_receipt_fixture:{sha:CODEx_SHA,run:400001,job:500001,attempt:1},
    security_waiver:false,claim_qps_engineering_acceptance:false,force_merge:false,
  };
  r.payload_sha256=digestRequest(r);
  r.idempotency_key="mcex:"+hash(r.nonce+"|"+r.target.expected_sha+"|"+r.payload_sha256);
  return r;
}
const deny=reason=>({decision:"HOLD",reason,offered_actions:[],local_shadow_modified:false,
    git_writes:0,remote_writes:0,real_ci_credited:false,real_owner_credited:false,
    merge_admission:"HOLD",security_waiver:false,qps_engineering_acceptance:false});
export function assess(r,p,used=new Set()){
  validProfile(p);
  if(r.action!=="STAGE_ONLY"||r.remote_action!=="READ_ONLY_RETURN_REQUEST")
    return deny("MUTATION_ACTION_DENIED");
  if(r.security_waiver!==false||r.claim_qps_engineering_acceptance!==false||r.force_merge!==false)
    return deny("UNAUTHORIZED_WAIVER_OR_CREDIT");
  if(r.target?.repository!=="GBOGEB/CODEX"||r.target.ref!=="main")
    return deny("REMOTE_TARGET_CANNOT_OWN_APPLY");
  const t=r.target;
  if(!SHA.test(t.expected_sha)||!SHA.test(t.observed_sha))return deny("INVALID_SOURCE_SHA");
  if(t.expected_sha!==t.observed_sha)return deny("STALE_HEAD");
  if(t.request_epoch!==t.observed_epoch)return deny("ABA_ANCESTRY_REJECTED");
  if(r.path!==ALLOWED_PATH)return deny("DISJOINT_PATH_LEASE_DENIED");
  if(r.principal?.attested_by!=="SERVER_FIXTURE_NOT_REAL_AUTH")
    return deny("CLIENT_ASSERTED_IDENTITY_REJECTED");
  if(r.principal?.server_bound!==true)return deny("PRINCIPAL_NOT_BOUND");
  for(const [key,reason] of [
    ["ci","MISSING_INDEPENDENT_CI"],["security","MISSING_SECURITY_GATE"],
    ["independent_review","MISSING_INDEPENDENT_REVIEW"],["owner","MISSING_OWNER_APPROVAL"]
  ])if(r.simulated_gates?.[key]!=="SIM_PASS")return deny(reason);
  if(r.dry_run?.receipt_head!==t.expected_sha||r.dry_run?.after_sha!==null
     ||r.dry_run?.result!=="SIMULATED_ONLY")return deny("DRY_RUN_NOT_EXACT_OR_MUTATED");
  if(r.native_receipt_fixture?.sha!==t.expected_sha
     ||!Number.isSafeInteger(r.native_receipt_fixture?.run)||r.native_receipt_fixture.run<=0
     ||!Number.isSafeInteger(r.native_receipt_fixture?.job)||r.native_receipt_fixture.job<=0
     ||!Number.isSafeInteger(r.native_receipt_fixture?.attempt)||r.native_receipt_fixture.attempt<=0)
    return deny("RUN_JOB_ATTEMPT_NOT_BOUND");
  if(r.payload_sha256!==digestRequest(r)||
     r.idempotency_key!=="mcex:"+hash(r.nonce+"|"+t.expected_sha+"|"+r.payload_sha256))
    return deny("DIGEST_BINDING_MISMATCH");
  if(used.has(r.idempotency_key))return deny("REPLAY_OF_COMPLETED_PLAN");
  if(!["GBOGEB/ABACUS","GBOGEB/cryoplant-project"].includes(r.remote_target))
    return deny("REMOTE_RETURN_TARGET_NOT_ALLOWLISTED");
  used.add(r.idempotency_key);
  // The only 'write' below is to a cloned in-memory object. No repo is changed.
  const before=Object.freeze({view:"CONTROL_PLANE",state:"FROZEN"});
  const after=p.local_shadow?{...before,state:"SHADOW_EMULATION_ONLY"}:{...before};
  const actions=["STAGE_PROPOSAL_ONLY"];
  if(p.local_shadow)actions.push("EMULATE_CODEX_WRITE_IN_MEMORY");
  if(p.remote_readonly)actions.push("PREPARE_REMOTE_READONLY_RETURN_ONLY");
  return {decision:"LAB_ROUTE_PLAN_ONLY",reason:null,offered_actions:actions,
    local_shadow_modified:after.state!==before.state,git_writes:0,remote_writes:0,
    real_ci_credited:false,real_owner_credited:false,
    merge_admission:"HOLD",security_waiver:false,qps_engineering_acceptance:false};
}
export function scenarios(){
  const cases=[];
  function add(id,expected,mutate,precompleted=false,remote_target="GBOGEB/ABACUS"){
    const r=request(id,remote_target);if(mutate)mutate(r);
    if(id!=="digest-tampered"&&id!=="idempotency-forged"){
      r.payload_sha256=digestRequest(r);
      r.idempotency_key="mcex:"+hash(r.nonce+"|"+r.target.expected_sha+"|"+r.payload_sha256);
    }
    cases.push({id,expected,r,precompleted});
  }
  add("nominal-abacus","LAB_ROUTE_PLAN_ONLY");
  add("nominal-qps","LAB_ROUTE_PLAN_ONLY",null,false,"GBOGEB/cryoplant-project");
  add("missing-ci","MISSING_INDEPENDENT_CI",r=>r.simulated_gates.ci="UNKNOWN");
  add("missing-review","MISSING_INDEPENDENT_REVIEW",r=>r.simulated_gates.independent_review="UNKNOWN");
  add("missing-security","MISSING_SECURITY_GATE",r=>r.simulated_gates.security="UNKNOWN");
  add("missing-owner","MISSING_OWNER_APPROVAL",r=>r.simulated_gates.owner="UNKNOWN");
  add("stale-head","STALE_HEAD",r=>r.target.observed_sha="b".repeat(40));
  add("aba-same-sha","ABA_ANCESTRY_REJECTED",r=>r.target.observed_epoch=9);
  add("outside-path","DISJOINT_PATH_LEASE_DENIED",r=>r.path=".github/workflows/untrusted.yml");
  add("wrong-repo","REMOTE_TARGET_CANNOT_OWN_APPLY",r=>r.target.repository="GBOGEB/ABACUS");
  add("client-identity","CLIENT_ASSERTED_IDENTITY_REJECTED",r=>r.principal.attested_by="CLIENT_CLAIMED_ADMIN");
  add("unbound-principal","PRINCIPAL_NOT_BOUND",r=>r.principal.server_bound=false);
  add("no-dry-run","DRY_RUN_NOT_EXACT_OR_MUTATED",r=>r.dry_run=null);
  add("dryrun-mutated","DRY_RUN_NOT_EXACT_OR_MUTATED",r=>r.dry_run.after_sha="f".repeat(40));
  add("wrong-run-sha","RUN_JOB_ATTEMPT_NOT_BOUND",r=>r.native_receipt_fixture.sha="a".repeat(40));
  add("missing-job","RUN_JOB_ATTEMPT_NOT_BOUND",r=>r.native_receipt_fixture.job=null);
  add("digest-tampered","DIGEST_BINDING_MISMATCH",r=>r.payload_sha256="0".repeat(64));
  add("completed-replay","REPLAY_OF_COMPLETED_PLAN",null,true);
  add("remote-mutate-action","MUTATION_ACTION_DENIED",r=>r.remote_action="REMOTE_MUTATE");
  add("waiver-attempt","UNAUTHORIZED_WAIVER_OR_CREDIT",r=>r.security_waiver=true);
  add("fake-qps-acceptance","UNAUTHORIZED_WAIVER_OR_CREDIT",r=>r.claim_qps_engineering_acceptance=true);
  add("uncertain-ci","MISSING_INDEPENDENT_CI",r=>r.simulated_gates.ci=null);
  return cases;
}
export function suite(profile){
  validProfile(profile);
  const rows=scenarios().map(s=>{
    const seen=new Set(s.precompleted?[s.r.idempotency_key]:[]);
    const result=assess(s.r,profile,seen);
    return {id:s.id,expected:s.expected,actual:result.decision==="HOLD"?result.reason:result.decision,
      correct:(result.decision==="HOLD"?result.reason:result.decision)===s.expected,
      ...result};
  });
  const positive=rows.filter(x=>x.decision==="LAB_ROUTE_PLAN_ONLY");
  return {schema:"missioncontrol.mcex.comparison_receipt.v1",arm:profile.arm,source_main_sha:HUB_BASE,
    codex_pin_sha:CODEx_SHA,simulation_only:true,
    conditions:{local_shadow:profile.local_shadow,remote_readonly:profile.remote_readonly},
    metrics:{cases:rows.length,negative_cases:rows.length-positive.length,
      rejected_negatives:rows.filter(x=>x.expected!=="LAB_ROUTE_PLAN_ONLY"&&x.decision==="HOLD").length,
      positive_plans:positive.length,false_green:rows.filter(x=>!x.correct).length,
      local_shadow_plans:positive.filter(x=>x.local_shadow_modified).length,
      remote_return_plans:positive.filter(x=>x.offered_actions.includes("PREPARE_REMOTE_READONLY_RETURN_ONLY")).length,
      git_writes:rows.reduce((a,x)=>a+x.git_writes,0),
      remote_writes:rows.reduce((a,x)=>a+x.remote_writes,0)},
    boundary:{native_ci_proven:false,real_security_proven:false,real_reviewer_proven:false,
      real_owner_authorization_proven:false,remote_dispatch_executed:false,
      persisted_replay_ledger_proven:false,qps_acceptance:false,merge_admission:"HOLD"},
    cases:rows.map(x=>({id:x.id,expected:x.expected,actual:x.actual,correct:x.correct,
      offered_actions:x.offered_actions}))};
}
