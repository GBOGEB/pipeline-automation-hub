"use strict";
const assert=require("node:assert/strict"),crypto=require("crypto");
const x=require("./m3_handover.js"),{raw,m2,input}=x.load();
const SHA="a".repeat(40),base=x.build(input,m2,raw,SHA);
let n=0;
function t(name,fn){fn();n++;console.log("PASS "+name);}
const clone=o=>structuredClone(o);
const reject=(i,m=m2,r=raw)=>assert.throws(()=>x.validate(i,m,r),/M3_FAIL_CLOSED/);
t("all 15 inherited M2 intents preserved",()=>assert.equal(base.intents.filter(i=>i.id.startsWith("CP-M2-")).length,15));
t("new user intent parent retained",()=>assert.equal(base.intents[15].parent,"CP-M2-I06"));
t("all 20 source actions retained",()=>assert.equal(base.actions.filter(a=>a.origin==="M2_ORIGINAL").length,20));
t("all seven M2 later actions retained",()=>assert.equal(base.actions.filter(a=>a.origin==="M2_ADDED").length,7));
t("four new execution items retained",()=>assert.equal(base.actions.filter(a=>a.origin==="M3_NEW").length,4));
t("31 distinct action identifiers",()=>assert.equal(new Set(base.actions.map(a=>a.id)).size,31));
t("9 independent release gates",()=>assert.equal(base.release_gates.length,9));
t("6 pinned repository heads",()=>assert.equal(base.repo_heads.length,6));
t("every required-check set remains OFF at snapshot",()=>assert(base.repo_heads.every(r=>r.required_checks==="OFF")));
t("hist Ruff remains 1221 raw findings",()=>assert.equal(base.retained_metrics.codex_1045.ruff_findings_nonblocking,1221));
t("fleet accepted hop remains zero",()=>assert.equal(base.cross_repo_qps_acceptances,0));
t("no original message ids asserted",()=>assert.equal(base.verified_chat_message_ids,0));
t("release and authority remain HOLD",()=>assert.equal(base.release,"HOLD"));
t("native intent provenance fabricated rejected",()=>{let q=clone(input);q.new_intent.original_chat_message_id="guessed";reject(q);});
t("false QPS acceptance rejected",()=>{let q=clone(input);q.qps_engineering_acceptance="ACCEPT";reject(q);});
t("false merge authorization rejected",()=>{let q=clone(input);q.merge_authorized=true;reject(q);});
t("M2 baseline loss rejected",()=>{let m=clone(m2);m.actions.pop();reject(input,m);});
t("M2 original first action lost rejected",()=>{let m=clone(m2);m.actions[0].id="M2-A99";reject(input,m);});
t("M2 added action loss rejected",()=>{let q=clone(input);q.m2_action_additions.pop();reject(q);});
t("later duplicate action rejected",()=>{let q=clone(input);q.m3_new_actions[0].id="M2-A21";reject(q);});
t("missing owner rejected",()=>{let q=clone(input);q.m3_new_actions[0].owner="";reject(q);});
t("untrusted external evidence link rejected",()=>{let q=clone(input);q.m2_action_additions[0].evidence="https://invalid.example";reject(q);});
t("current snapshot protection promoted rejected",()=>{let q=clone(input);q.repos[0].required_checks="ON";reject(q);});
t("stale M2 source blob rejected",()=>{let r=Object.assign({},raw,{m2:Buffer.concat([raw.m2,Buffer.from(" ")] )});reject(input,m2,r);});
t("stale M2 reconciliation blob rejected",()=>{let r=Object.assign({},raw,{overlay:Buffer.concat([raw.overlay,Buffer.from(" ")] )});reject(input,m2,r);});
t("preregistered forecast remains unscored",()=>{let q=clone(input);q.forecast_pre_registered.actual="PASS";reject(q);});
t("source root changed rejected",()=>{let q=clone(input);q.parent_intent="OTHER";reject(q);});
t("source output exact SHA must be 40-hex",()=>assert.throws(()=>x.build(input,m2,raw,"short"),/M3_FAIL_CLOSED/));
t("repeat builds deterministic on fixed head",()=>{
 const a=x.filesFor(input,m2,raw,SHA),b=x.filesFor(input,m2,raw,SHA);assert.deepEqual(a,b);
});
t("generated manifest hashes match bytes",()=>{
 const files=x.filesFor(input,m2,raw,SHA),manifest=JSON.parse(files["M3_MANIFEST.json"]);
 for(const [key,info] of Object.entries(manifest.items)){
  assert.equal(info.sha256,crypto.createHash("sha256").update(files[key]).digest("hex"));assert.equal(info.bytes,Buffer.byteLength(files[key]));
 }
});
t("HTML source gets escaped and search bound",()=>{
 const q=clone(input);q.m2_action_additions[0].done_when='<img onerror="alert(1)">';
 const r=x.build(q,m2,raw,SHA),h=x.html(r);
 assert(!h.includes('<img onerror="alert(1)">'));assert(h.includes("&lt;img"));
 assert(h.includes('id="search"'));assert(h.includes("viewport"));
});
t("Markdown contains every action and user intent",()=>{
 const md=x.fullMd(base);
 for(const a of base.actions)assert(md.includes(a.id));
 for(const i of base.intents)assert(md.includes(i.id));
});
t("DAG distinguishes release from producer",()=>{const md=x.dag();assert(md.includes("DEFER/REJECT"));assert(md.includes("Protection"));});
t("drop-in preserves all counts and requires refresh",()=>{
 const d=x.dropin(base);assert(d.includes("31"));assert(d.includes("15 original"));assert(d.includes("Refresh"));
});
console.log("Ran "+n+" M3 tests: PASS");
