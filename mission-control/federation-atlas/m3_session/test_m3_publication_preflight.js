"use strict";
const fs=require("node:fs"),os=require("node:os"),path=require("node:path"),assert=require("node:assert/strict");
const {build,REQUIRED}=require("./m3_publication_preflight");
const SHA=process.env.EXPECTED_SHA;
assert.match(SHA||"",/^[0-9a-f]{40}$/);
const root=path.resolve("out/m3/site"),ok=build(root,SHA);
assert.equal(ok.governance.publication_state,"WITHHELD_PENDING_OWNER");
assert.equal(ok.governance.hosted_publication_verified,false);
assert.equal(ok.governance.owner_approval,null);
assert.equal(ok.governance.hosted_content_sha256,null);
assert.equal(ok.governance.merge_admission,"HOLD");
assert.equal(Object.keys(ok.artifacts).length,REQUIRED.length);
assert.ok(ok.artifacts["docs/mission-control/m3/index.html"].sha256);
assert.throws(()=>build(root,"invalid"),/full exact checkout SHA/);
const tmp=fs.mkdtempSync(path.join(os.tmpdir(),"mc-m3-publication-"));
try{
 for(const file of REQUIRED){let p=path.join(tmp,file);fs.mkdirSync(path.dirname(p),{recursive:true});fs.copyFileSync(path.join(root,file),p)}
 fs.unlinkSync(path.join(tmp,"docs/mission-control/m2/federation.html"));
 assert.throws(()=>build(tmp,SHA),/missing required publication leaf/);
 fs.copyFileSync(path.join(root,"docs/mission-control/m2/federation.html"),path.join(tmp,"docs/mission-control/m2/federation.html"));
 let t=path.join(tmp,"docs/mission-control/m3/telemetry.json");const s=JSON.parse(fs.readFileSync(t));s.source_identity.m3_state_sha256="0".repeat(64);
 fs.writeFileSync(t,JSON.stringify(s));assert.throws(()=>build(tmp,SHA),/telemetry digest/);
}finally{fs.rmSync(tmp,{recursive:true,force:true})}
console.log("PASS M3 owner-gated candidate: seven present leaves, digests, navigation, withheld launch, two negative probes");
