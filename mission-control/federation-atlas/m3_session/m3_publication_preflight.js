"use strict";
/** Review candidate only. No GitHub Pages API, access tokens, or deployments. */
const fs=require("node:fs"),path=require("node:path"),crypto=require("node:crypto");
const SHA=/^[0-9a-f]{40}$/;
const REQUIRED=[
 "docs/mission-control/m3/index.html",
 "docs/mission-control/m3/state.json",
 "docs/mission-control/m3/telemetry.json",
 "docs/mission-control/m2/index.html",
 "docs/mission-control/m2/pipeline.html",
 "docs/mission-control/m2/federation.html",
 "docs/code-purple-live/index.html"
];
const digest=(b)=>crypto.createHash("sha256").update(b).digest("hex");
function failUnless(v,m){if(!v)throw Error(m)}
function build(siteRoot,exactGitSHA){
 failUnless(SHA.test(exactGitSHA),"full exact checkout SHA required");
 const files={},root=path.resolve(siteRoot);
 for(const name of REQUIRED){
  const target=path.resolve(root,name);
  failUnless(target.startsWith(root+path.sep),"path escapes approved site root");
  failUnless(fs.existsSync(target)&&fs.statSync(target).isFile(),"missing required publication leaf: "+name);
  const b=fs.readFileSync(target);
  failUnless(b.length>0,"empty publication leaf: "+name);
  files[name]={sha256:digest(b),bytes:b.length};
 }
 const read=(name)=>fs.readFileSync(path.join(root,name),"utf8");
 const src=JSON.parse(read("docs/mission-control/m3/state.json"));
 const tel=JSON.parse(read("docs/mission-control/m3/telemetry.json"));
 const html=read("docs/mission-control/m3/index.html");
 failUnless(src.schema==="missioncontrol.m3.readonly_projection.v1"&&src.authority?.merge_admission==="HOLD"&&src.authority?.remote_mutation_enabled===false,"source authority invalid");
 failUnless(src.nodes.length===29&&src.edges.length===32&&src.repos.length===6,"source graph counts changed without owner crosswalk update");
 failUnless(tel.schema==="missioncontrol.m3.telemetry_observation.v1"&&tel.authority?.merge_admission==="HOLD"&&tel.authority.remote_mutation===false,"native telemetry required, static placeholder is not a promotion receipt");
 failUnless(tel.source_identity?.m3_state_sha256===files["docs/mission-control/m3/state.json"].sha256,"telemetry digest is not the bundled source");
 failUnless(html.includes("<h1>Federated execution flightdeck</h1>"),"source title missing");
 for(const route of ["../m2/index.html","../m2/pipeline.html","../m2/federation.html","../../code-purple-live/index.html"]){
  failUnless(html.includes('href="'+route+'"'),"missing navigation route "+route);
  const resolved=path.resolve(root,"docs/mission-control/m3",route);
  failUnless(resolved.startsWith(root+path.sep)&&fs.existsSync(resolved),"unserved route "+route);
 }
 failUnless(!html.includes("github_pat_"),"GitHub token leaked into site");
 const entrypoint="docs/mission-control/m3/index.html";
 return {
  schema:"missioncontrol.m3.owner_publication_preflight.v1",
  exact_checkout_sha:exactGitSHA,
  source_observed_date:src.observed_date_utc,
  source_snapshot_sha:src.source_sha,
  content_slug:src.content_slug,
  entrypoint,
  artifacts:files,
  total_bytes:Object.values(files).reduce((n,x)=>n+x.bytes,0),
  checks:{source_schema:"PASS",source_hierarchy:"PASS",cross_source_digest:"PASS",relative_navigation:"PASS",visible_authority:"PASS",exact_checkout:"PASS"},
  governance:{
    publication_state:"WITHHELD_PENDING_OWNER",
    approved_public_url:null,
    owner_approval:null,
    protected_environment_review:null,
    hosted_content_sha256:null,
    hosted_bytes_match:null,
    hosted_publication_verified:false,
    merge_admission:"HOLD",
    remote_mutation:false,
    security_waiver:false,
    qps_accepted:false
  },
  evidence_level:"EXACT_SHA_CANDIDATE_ONLY_NOT_PUBLISHED",
  next_action:"Owner independently reviews PR, enables/verifies an existing governed Pages publisher and authenticated hosted URL, then compares remote bytes on the exact released SHA."
 };
}
function main(){
 const argv=process.argv,root=argv[argv.indexOf("--site")+1],out=argv[argv.indexOf("--out")+1],sha=argv[argv.indexOf("--sha")+1];
 if(!root||!out||!sha||root.startsWith("--")||out.startsWith("--")||sha.startsWith("--"))throw Error("--site --out --sha required");
 const report=build(root,sha);
 fs.mkdirSync(path.dirname(out),{recursive:true});
 fs.writeFileSync(out,JSON.stringify(report,null,2)+"\n");
 process.stdout.write("M3 publication candidate validated; actual publication WITHHELD\n");
}
if(require.main===module){try{main()}catch(e){console.error(e.message);process.exitCode=1}}
module.exports={build,REQUIRED};
