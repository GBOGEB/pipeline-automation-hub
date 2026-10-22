/* Bounded GitHub API read-only collector: never posts issues, reruns CI or merges PRs. */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {rosterNames} from './analyze.mjs';
const stop=(x,m)=>{if(!x)throw Error(m)};
const args=process.argv.slice(2);
const get=(key,def)=>{const i=args.indexOf('--'+key);return i<0?def:args[i+1]};
const MAX_PR=Math.min(5,Math.max(1,Number(get('per-repo','2'))));
const MAX_CLOSED=Math.min(50,Math.max(20,Number(get('closed-page','30'))));
const MAX_PAGES=Math.min(5,Math.max(1,Number(get('check-pages','4'))));
const token=process.env.GH_TOP21_READ_TOKEN||process.env.GH_TOKEN||process.env.GITHUB_TOKEN;
const output=path.resolve(get('out','./top21_live_receipts'));
stop(token,'Explicit read-only cross-repo GitHub token is required');
stop(Number.isSafeInteger(MAX_PR)&&Number.isSafeInteger(MAX_CLOSED)&&Number.isSafeInteger(MAX_PAGES),'invalid request caps');
const root=process.cwd(),rosterPath=path.join(root,'mission-control/grand-missions/GM_DMAIC_EVOLUTION_T7_T14_T21_v1.json');
const rosterText=fs.readFileSync(rosterPath,'utf8');
const roster=JSON.parse(rosterText),names=rosterNames(roster);
const semanticSha=crypto.createHash('sha256').update(rosterText).digest('hex');
async function GET(url){
 const result=await fetch(url,{method:'GET',redirect:'error',headers:{
 'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','Authorization':'Bearer '+token}});
 if(!result.ok)throw Error('HTTP '+result.status+' '+url+' (source access/rate-limit not verified)');
 return result.json();
}
async function one(name){
 let pulls=[],error=null;
 const repo='GBOGEB/'+name;
 try{
  const closed=await GET('https://api.github.com/repos/'+repo+'/pulls?state=closed&sort=updated&direction=desc&per_page='+MAX_CLOSED);
  stop(Array.isArray(closed),'invalid GitHub PR collection');
  pulls=closed.filter(x=>x.merged_at).sort((a,b)=>b.merged_at.localeCompare(a.merged_at)).slice(0,MAX_PR);
 }catch(e){return {repo,prs:[],error:'DISCOVERY: '+String(e)};}
 const prs=[];
 for(const p of pulls){
  let runs=[],checkTotal=null,why=null;
  for(let page=1;page<=MAX_PAGES;page++){
   try{
    const z=await GET('https://api.github.com/repos/'+repo+'/commits/'+p.head.sha+'/check-runs?per_page=30&page='+page);
    stop(Number.isInteger(z.total_count)&&Array.isArray(z.check_runs),'invalid check-count contract');
    checkTotal=z.total_count;
    runs.push(...z.check_runs.map(x=>({id:x.id,name:x.name,status:x.status,conclusion:x.conclusion,
     started_at:x.started_at,completed_at:x.completed_at,details_url:x.details_url})));
    if(runs.length>=checkTotal)break;
   }catch(e){why='CHECK_RUN_READ: '+String(e);break;}
  }
  prs.push({repository:repo,pr:p.number,head_sha:p.head.sha,merged_at:p.merged_at,
   base_branch:p.base.ref,pr_url:p.html_url,check_total:checkTotal,check_runs:runs,
   complete:why===null&&checkTotal===runs.length,error:why,
   selection:'RECENT_MERGED_FROM_UPDATED_CLOSED_PAGE_NOT_LIFETIME'});
 }
 return {repo,prs,error};
}
const groups=[
 {cohort:'TOP7',members:roster.cohorts.top7},
 {cohort:'TOP14_EXTENSION',members:roster.cohorts.top14_extension},
 {cohort:'TOP21_EXTENSION',members:roster.cohorts.top21_extension}
];
fs.mkdirSync(output,{recursive:true});
const report=[];
for(const group of groups){
 const results=[];
 // Small disjoint fan-out (3) limits load and makes denied repos visible, never silent.
 for(let i=0;i<group.members.length;i+=3)results.push(...await Promise.all(group.members.slice(i,i+3).map(x=>one(x.split('/')[1]))));
 const doc={schema:'gogreen.top21.merged-check-snapshot.v1',cohort:group.cohort,
  roster_path:'mission-control/grand-missions/GM_DMAIC_EVOLUTION_T7_T14_T21_v1.json',
  roster_semantic_sha256:semanticSha,roster_blob:'LIVE_CHECKOUT_SHA_REQUIRES_GIT_READBACK',
  observed_date:new Date().toISOString(),sampling:{max_per_repo:MAX_PR,closed_page:MAX_CLOSED,check_pages:MAX_PAGES},
  repo_denials:results.filter(x=>x.error).map(x=>({repository:x.repo,error:x.error})),
  source_access_denominator:results.length,authority_transfer:false,merge_authorized:false,root_closure_credit:0,
  prs:results.flatMap(x=>x.prs)};
 const fname=group.cohort.toLowerCase()+'_live.json';
 fs.writeFileSync(path.join(output,fname),JSON.stringify(doc,null,2)+'\n');
 report.push({cohort:group.cohort,repo_eligible:results.length,repo_denied:doc.repo_denials.length,
  prs:doc.prs.length,checks:doc.prs.reduce((n,x)=>n+x.check_runs.length,0),file:fname});
}
fs.writeFileSync(path.join(output,'LIVE_READ_RECEIPT.json'),JSON.stringify({schema:'gogreen.top21.live-read-only.v1',
 cohorts:report,planned_repo_coverage:names.length,source_roster_semantic_sha256:semanticSha,
 remote_mutation:false,independent_approval:false,root_closure_credit:0,merge_authorized:false},null,2)+'\n');
console.log(JSON.stringify({cohorts:report,status:'READ_ONLY_CENSUS_GENERATED_REQUIRES_CLASSIFIER_AND_OWNER_QA',merge_authorized:false},null,2));
