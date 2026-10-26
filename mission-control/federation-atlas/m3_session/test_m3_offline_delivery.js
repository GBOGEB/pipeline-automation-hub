"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path"),os=require("node:os");
const {make}=require("./m3_offline_delivery");
const root=path.resolve("out/m3/site"),sha=process.env.EXPECTED_SHA;
assert.match(sha||"",/^[0-9a-f]{40}$/);
const result=make(root,sha);
assert.equal(result.receipt.authority,"HOLD");
assert.equal(result.receipt.hosted_pages_verified,null);
assert.equal(result.receipt.mode,"FULLY_INLINE_NO_FETCH");
assert.equal(result.receipt.exact_checkout_sha,sha);
assert.ok(result.html.includes("function renderInline(){"));
assert.ok(result.html.includes(');renderInline();\n</script>'));
assert.ok(!result.html.includes(');load();\n</script>'));
assert.ok(!result.html.includes('addEventListener("click",load)'));
assert.ok(!result.html.includes("github_pat_"));
const tmp=fs.mkdtempSync(path.join(os.tmpdir(),"m3-offline-qa-"));
try{
 const folder=path.join(tmp,"docs/mission-control/m3");
 fs.mkdirSync(folder,{recursive:true});
 for(const k of ["index.html","state.json","telemetry.json"]){
  fs.copyFileSync(path.join(root,"docs/mission-control/m3",k),path.join(folder,k));
 }
 const tel=path.join(folder,"telemetry.json"),valid=JSON.parse(fs.readFileSync(tel,"utf8"));
 valid.source_identity.m3_state_sha256="0".repeat(64);
 fs.writeFileSync(tel,JSON.stringify(valid));
 assert.throws(()=>make(tmp,sha),/cross-source digest mismatch/);
 fs.copyFileSync(path.join(root,"docs/mission-control/m3/telemetry.json"),tel);
 fs.rmSync(path.join(folder,"state.json"));
 assert.throws(()=>make(tmp,sha),/ENOENT/);
 assert.throws(()=>make(root,"not-a-sha"),/exact checkout SHA/);
}finally{fs.rmSync(tmp,{recursive:true,force:true})}
console.log("PASS M3 offline download/open adapter: source hash, no-fetch, full SHA, negative forged/missing and authority");
