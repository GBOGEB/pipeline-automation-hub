"use strict";
/** Deterministic DMAIC temporal metrics. Incomparable series stay UNKNOWN. */
const SHA=/^[a-f0-9]{40}$/;
function verify(s){
 if(!Array.isArray(s)||!s.length)throw Error("missing cohort series");
 const key=s[0].cohort_key,instr=s[0].instrument_id,denom=s[0].denominator;
 if(!key||!instr||!Number.isInteger(denom)||denom<=0)throw Error("unbound measurement population");
 const ids=new Set(),ord=new Set();
 for(const r of s){
  if(r.cohort_key!==key||r.instrument_id!==instr||r.denominator!==denom)throw Error("unmatched cohort/instrument/denominator");
  if(!SHA.test(r.source_sha)||!Number.isInteger(r.n)||!Number.isInteger(r.numerator)||r.numerator<0||r.numerator>denom)throw Error("invalid source or numerator");
  if(ids.has(r.source_sha)||ord.has(r.n))throw Error("duplicate temporal observation");
  ids.add(r.source_sha);ord.add(r.n);
 }
 for(let i=1;i<s.length;i++)if(s[i].n<=s[i-1].n)throw Error("pulse order not increasing");
 return {cohort_key:key,instrument_id:instr,denominator:denom};
}
function coverage(s){
 const meta=verify(s);
 if(s.length<2)return {...meta,observations:s.length,baseline:{numerator:s[0].numerator,denominator:meta.denominator,source_sha:s[0].source_sha},
  current:null,numerator_delta:null,percentage_point_delta:null,convergence:"INSUFFICIENT_MATCHED_SERIES"};
 const first=s[0],last=s[s.length-1],delta=last.numerator-first.numerator;
 const diffs=s.slice(1).map((r,i)=>r.numerator-s[i].numerator);
 const trend=diffs.some(d=>d<0)?"NON_MONOTONIC":diffs.every(d=>d===0)?"NO_OBSERVED_CHANGE":"OBSERVED_UPLIFT";
 const convergence=s.length<6?"INSUFFICIENT_INDEPENDENT_PULSES":diffs.slice(-4).every(d=>d===0)?"OBSERVED_PLATEAU_NOT_SIX_SIGMA":"NOT_STABLE";
 return {...meta,observations:s.length,baseline:{numerator:first.numerator,denominator:meta.denominator,source_sha:first.source_sha},
  current:{numerator:last.numerator,denominator:meta.denominator,source_sha:last.source_sha},
  numerator_delta:delta,percentage_point_delta:Math.round(1000000*delta/meta.denominator)/10000,
  trend,convergence,qualified_for_statistical_stability:false,
  caution:"Coverage is an exact code-population ratio, not independent Bernoulli trials; Wilson CI and six-sigma acceptance are inapplicable."};
}
function queueP95(rows){
 if(!Array.isArray(rows))throw Error("job sample missing");
 const seen=new Set(),samples=[];
 for(const j of rows){
  if(!Number.isInteger(j.job_id)||seen.has(j.job_id))throw Error("duplicate/invalid job");
  seen.add(j.job_id);
  if(j.created_at==null||j.started_at==null)continue;
  const start=Date.parse(j.started_at),create=Date.parse(j.created_at);
  if(!Number.isFinite(start)||!Number.isFinite(create)||start<create)throw Error("invalid queue latency");
  samples.push((start-create)/60000);
 }
 samples.sort((a,b)=>a-b);
 return {observed_jobs:rows.length,valid_latency_samples:samples.length,queue_p95_minutes:
  samples.length>=20?samples[Math.ceil(.95*samples.length)-1]:null,
  qualification:samples.length>=20?"DESCRIPTIVE_COHORT_P95_NOT_CAUSAL":"INSUFFICIENT_VALID_JOB_TIMES_FOR_P95"};
}
function rootClosures(occurrences){
 if(!Array.isArray(occurrences))throw Error("missing roots");
 const unique=new Set(),verified=[];
 for(const r of occurrences){
  if(!r.signature||!r.source_sha||!SHA.test(r.source_sha))throw Error("unbound root signature");
  const key=r.source_repo+"|"+r.signature;
  if(unique.has(key))continue;unique.add(key);
  if(r.repair_verified===true&&r.exact_head_native_receipt&&r.owner_acceptance_ref&&r.same_population_control===true)verified.push(key);
 }
 return {distinct_root_candidates:unique.size,verified_closed_roots:verified.length,
  qualification:"ONLY_EXPLICIT_NATIVE_AND_OWNER_BOUND_CLOSURE","housekeeping_issue_closures_excluded":true};
}
module.exports={verify,coverage,queueP95,rootClosures};
