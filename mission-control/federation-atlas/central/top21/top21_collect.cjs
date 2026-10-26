#!/usr/bin/env node
'use strict';
/** Append-only public/authorized GitHub tree readback; never dispatch or mutate GitHub. */
const fs = require('node:fs');
const path = require('node:path');
const https = require('node:https');
const SHA = /^[0-9a-f]{40}$/;
const expectedKinds = /(^|\/)(requirements[^/]*\.txt|pyproject\.toml|package\.json|package-lock\.json|pnpm-lock\.yaml|yarn\.lock|go\.mod|Cargo\.toml|Pipfile|Dockerfile|Makefile|tsconfig(?:\..+)?\.json|.*\.csproj)$/i;
const rootAllowed = /^(README|LICENSE|COPYING|NOTICE|SECURITY|CONTRIBUTING|CHANGELOG|CODE_OF_CONDUCT|AGENTS|CLAUDE|AUTHORS|CITATION|CODEOWNERS|MANIFEST|LICENSE-MIT|LICENSE-APACHE)([._-]|$)/i;
const rootConfigs = /^(package(-lock)?\.json|pnpm-lock\.yaml|yarn\.lock|tsconfig(\..+)?\.json|pyproject\.toml|poetry\.lock|uv\.lock|Pipfile(\.lock)?|tox\.ini|pytest\.ini|setup\.py|setup\.cfg|requirements[^/]*\.txt|Dockerfile.*|Makefile|\.gitignore|\.gitattributes|\.editorconfig|\.pre-commit-config\.yaml|\.ruff\.toml|\.python-version|\.npmrc|\.nvmrc|\.eslintrc.*|eslint\.config\..+|jest\.config\..+|vite\.config\..+|webpack\.config\..+|Cargo\.toml|Cargo\.lock|go\.mod|go\.sum|Gemfile(\.lock)?|\.gitmodules)$/i;
function classify(pathname) {
 const file=pathname.split('/').pop();
 if (/^(Makefile|GNUmakefile|makefile)$/.test(file)) return 'Makefile';
 if (/^Dockerfile([._]|$)/.test(file)) return 'Dockerfile';
 if (/\.(psm1|psd1)$/i.test(file)) return 'PowerShell module';
 return (file.match(/(\.[^.]+)$/) || [,'[extensionless]'])[1].toLowerCase();
}
function rootReason(file) {
 if (/\.(pdf|docx?|pptx?|xlsx?|zip|7z|tar|gz|ipynb)$/i.test(file)) return 'ROOT_BINARY_OR_BUNDLE';
 if (/\.(md|markdown|rst|txt)$/i.test(file) && !rootAllowed.test(file)) return 'ROOT_NARRATIVE_JUSTIFICATION';
 if (/\.(csv|html)$/i.test(file)) return 'ROOT_DATA_OR_LAUNCH';
 if (/\.(json|yaml|yml)$/i.test(file) && !rootConfigs.test(file)) return 'ROOT_MANIFEST_REVIEW';
 if (/\.(py|js|ts|sh|ps1|bat|cmd)$/i.test(file) && !rootConfigs.test(file) && !/^manage\.py$|^build\.py$/i.test(file)) return 'ROOT_EXECUTABLE_REVIEW';
 return null;
}
function summarize(repo, branch, sha, tree) {
 if (!SHA.test(sha) || !tree || !SHA.test(tree.sha) || tree.truncated !== false || !Array.isArray(tree.tree)) throw Error('MISSING_OR_TRUNCATED_EXACT_GIT_TREE');
 const files=tree.tree.filter(x=>x.type==='blob'),dirs=tree.tree.filter(x=>x.type==='tree');
 const extensions={},tops={},depth2={},root_files=[],root_review=[],manifest_paths=[];
 for (const file of files) {
  const name=file.path,parts=name.split('/'),ext=classify(name);
  extensions[ext]=(extensions[ext]||0)+1;
  const top=parts.length===1?'[root]':parts[0];tops[top]=(tops[top]||0)+1;
  if(parts.length>=3){const sub=parts.slice(0,2).join('/');depth2[sub]=(depth2[sub]||0)+1;}
  if(parts.length===1){root_files.push(name);const reason=rootReason(name);if(reason)root_review.push({path:name,reason});}
  if(expectedKinds.test(name))manifest_paths.push(name);
 }
 const ranked=obj=>Object.entries(obj).sort((a,b)=>b[1]-a[1]).map(([name,files])=>({name,files}));
 return {repo,branch,sha,tree_sha:tree.sha,complete:true,tree_entries:tree.tree.length,files:files.length,directories:dirs.length,
 bytes:files.reduce((s,x)=>s+(x.size||0),0),extensions,top_level:ranked(tops),
 depth2:ranked(depth2).slice(0,45).map(({name,files})=>({path:name,files})),root_files,root_review,
 manifest_paths:manifest_paths.slice(0,140),manifest_total:manifest_paths.length,
 workflow_files:files.filter(x=>x.path.startsWith('.github/workflows/')&&/\.ya?ml$/.test(x.path)).length,
 tests_files:files.filter(x=>/(^|\/)(tests?|__tests__|spec)\//.test(x.path)||/test[_-].*\.py$|\.test\.[jt]sx?$/.test(x.path)).length};
}
async function getJSON(url, token) {
 for(let attempt=0;attempt<3;attempt++) {
  try {return await new Promise((resolve,reject)=>{
   const headers={'User-Agent':'mission-control-n11-readonly','Accept':'application/vnd.github+json'};
   if(token) headers.Authorization='Bearer '+token;
   const req=https.get(url,{headers,timeout:30000},res=>{
    const chunks=[];let total=0;
    res.on('data',c=>{total+=c.length;if(total>25000000){req.destroy(Error('RESPONSE_TOO_LARGE'));return;}chunks.push(c);});
    res.on('end',()=>{const body=Buffer.concat(chunks).toString('utf8');if(res.statusCode!==200){reject(Error('HTTP_'+res.statusCode+'_'+body.slice(0,120)));return;}try{resolve(JSON.parse(body));}catch(e){reject(e);}});
   });req.on('timeout',()=>req.destroy(Error('REQUEST_TIMEOUT')));req.on('error',reject);
  });}catch(err){if(attempt===2 || !/HTTP_5\d\d|HTTP_429|REQUEST_TIMEOUT/.test(String(err)))throw err;await new Promise(r=>setTimeout(r,500*(attempt+1)));}
 }
 throw Error('READBACK_RETRY_EXHAUSTED');
}
async function collectOne(repo,token) {
 if(!/^GBOGEB\/[\w.-]+$/.test(repo))throw Error('BAD_OWNER_OR_REPO');
 const root='https://api.github.com/repos/'+repo;
 const meta=await getJSON(root,token),branch=meta.default_branch;
 if(!branch || typeof branch!=='string')throw Error('MISSING_DEFAULT_BRANCH');
 const branchObj=await getJSON(root+'/branches/'+encodeURIComponent(branch),token),sha=branchObj.commit&&branchObj.commit.sha;
 if(!SHA.test(sha||''))throw Error('MISSING_EXACT_HEAD_SHA');
 const tree=await getJSON(root+'/git/trees/'+sha+'?recursive=1',token);
 return summarize(repo,branch,sha,tree);
}
async function main() {
 const rosterFile=process.argv[2],dest=process.argv[3],tag=process.argv[4]||'N_PLUS_1';
 if(!rosterFile||!dest)throw Error('Usage: node top21_collect.cjs <roster-json> <new-directory> <pulse-tag>');
 const roster=JSON.parse(fs.readFileSync(rosterFile,'utf8'));
 if(!Array.isArray(roster)||!roster.length||roster.length>100||new Set(roster).size!==roster.length)throw Error('INVALID_ROSTER');
 if(fs.existsSync(dest)&&fs.readdirSync(dest).length)throw Error('APPEND_ONLY_DEST_NOT_EMPTY');
 const records=[];const token=process.env.GITHUB_TOKEN||'';
 for(const repo of roster) {console.error('READ_ONLY_TREE '+repo);records.push(await collectOne(repo,token));}
 fs.mkdirSync(dest,{recursive:true});
 const size=6;for(let i=0;i<records.length;i+=size){const batch=Math.floor(i/size)+1,filename='CENSUS_'+tag+'_PART0'+batch+'.json';const payload={schema:'missioncontrol.top21.tree_census.part.v1',source:'GitHub Git Trees API recursive',frozen_at:new Date().toISOString(),batch,records:records.slice(i,i+size)};fs.writeFileSync(path.join(dest,filename),JSON.stringify(payload,null,2)+'\n',{flag:'wx'});}
 console.log(JSON.stringify({repos:records.length,files:records.reduce((s,x)=>s+x.files,0),snapshot_dir:dest,authority_transfer:false,dispatch:'NONE'}));
}
if(require.main===module)main().catch(err=>{console.error(String(err));process.exitCode=1;});
module.exports={classify,rootReason,summarize};
