/* Read-only TOP21 merged PR evidence. Never auto-merges or infers causal roots. */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
const DIR='mission-control/gogreen/merged_outcome_census';
const BAD=new Set(['failure','timed_out','action_required']);
const TERMINAL=new Set(['success','failure','timed_out','action_required','cancelled','skipped','neutral','stale']);
const check=(x,msg)=>{if(!x)throw Error(msg)};
const hash=x=>crypto.createHash('sha256').update(x).digest('hex');
export function rosterNames(data){const c=data.cohorts;const n=[...c.top7,...c.top14_extension,...c.top21_extension];check(n.length===21&&new Set(n).size===21,'TOP21 roster drift');return n}
export function classifyPR(p,defaultBranch){
  check(p&&/^GBOGEB\/[-\w.]+$/.test(p.repository),'bad repository');
  check(Number.isInteger(p.pr)&&p.pr>0&&/^[a-f0-9]{40}$/.test(p.head_sha),'bad merged PR head');
  const merge=Date.parse(p.merged_at);check(Number.isFinite(merge),'missing merge UTC');
  check(Array.isArray(p.check_runs),'missing check evidence');
  const ids=new Set();let before=0,after=0,green=0,skipped=0,pending=0;const failures=[];
  for(const r of p.check_runs){
    check(Number.isSafeInteger(r.id)&&!ids.has(r.id),'duplicate check run');ids.add(r.id);
    check(typeof r.name==='string'&&r.name.length>0,'check name absent');
    check(['completed','queued','in_progress','waiting','requested','pending'].includes(r.status),'bad status');
    check(r.conclusion==null||TERMINAL.has(r.conclusion),'unsupported conclusion');
    const t=r.completed_at?Date.parse(r.completed_at):NaN;
    const chrono=Number.isFinite(t)?(t<=merge?'PREMERGE':'POSTMERGE'):'UNKNOWN_TIME';
    if(chrono==='PREMERGE')before++;else if(chrono==='POSTMERGE')after++;
    if(r.status!=='completed'||!r.conclusion)pending++;
    else if(r.conclusion==='success')green++;
    else if(['skipped','neutral'].includes(r.conclusion))skipped++;
    if(BAD.has(r.conclusion)){
      const link=(r.details_url??'').match(/^https:\/\/github\.com\/[^/]+\/[^/]+\/actions\/runs\/(\d+)\/job\/(\d+)/);
      failures.push({event_key:p.repository+'::'+p.pr+'::'+p.head_sha+'::'+r.id,repository:p.repository,pr:p.pr,head_sha:p.head_sha,
        check_name:r.name,check_run_id:r.id,conclusion:r.conclusion,completed_at:r.completed_at,chronology:chrono,
        run_id:link?Number(link[1]):null,job_id:link?Number(link[2]):null,details_url:r.details_url??null,
        first_red:'UNKNOWN_UNTIL_NATIVE_LOG',root_id:null,causal_status:'SYMPTOM_ONLY',owner:p.repository,merge_authorized:false});
    }
  }
  const complete=p.complete===true&&!p.error&&p.check_total===ids.size;
  const redBefore=failures.filter(x=>x.chronology==='PREMERGE').length;
  const redAfter=failures.filter(x=>x.chronology==='POSTMERGE').length;
  let state='UNKNOWN_INCOMPLETE';
  if(complete&&p.check_total===0)state='UNKNOWN_NO_CHECK_RUNS';
  else if(complete&&redBefore)state='MERGED_WITH_PREMERGE_RED';
  else if(complete&&redAfter)state='MERGED_WITH_POSTMERGE_RED';
  else if(complete&&pending)state='UNKNOWN_PENDING';
  else if(complete&&!green)state='UNKNOWN_NO_SUCCESS';
  else if(complete)state=after>0?'OBSERVED_GREEN_LAST_KNOWN':'OBSERVED_GREEN_AT_MERGE';
  return {repository:p.repository,pr:p.pr,head_sha:p.head_sha,merged_at:p.merged_at,base_branch:p.base_branch,
    mainline:defaultBranch?p.base_branch===defaultBranch:null,pr_url:p.pr_url,
    state,check_population_complete:complete,check_count:p.check_total,checks_retrieved:ids.size,
    green_checks:green,neutral_skipped:skipped,pending_checks:pending,
    premerge_red:redBefore,postmerge_red:redAfter,postmerge_observations:after,required_checks_verified:false,
    independent_review_verified:false,whole_repo_coverage:null,formal_root_closure_credit:0,
    failed_checks:failures,merge_authorized:false};
}
export function aggregate(roster,snapshots,branches={}){
  const names=rosterNames(roster),seen=new Set(),rows=[],source=[];
  for(const d of snapshots){
    check(d.schema==='gogreen.top21.merged-check-snapshot.v1'&&d.merge_authorized===false&&d.authority_transfer===false,'snapshot authority invalid');
    check(Array.isArray(d.prs),'snapshot PRs absent');
    source.push({cohort:d.cohort,roster_blob:d.roster_blob,observed_date:d.observed_date});
    for(const p of d.prs){
      check(names.includes(p.repository),'foreign repository in TOP21');
      const key=p.repository+'#'+p.pr;check(!seen.has(key),'duplicate PR observation');seen.add(key);
      rows.push(classifyPR(p,branches[p.repository]));
    }
  }
  const errors=rows.flatMap(x=>x.failed_checks);
  check(new Set(errors.map(x=>x.event_key)).size===errors.length,'duplicate failure credit');
  const byRepo=names.map(repo=>{const p=rows.filter(x=>x.repository===repo);
    return {repository:repo,pr_sample:p.length,observed_green:p.filter(x=>x.state.startsWith('OBSERVED_GREEN')).length,
      merged_with_pre_red:p.filter(x=>x.premerge_red>0).length,merged_with_post_red:p.filter(x=>x.postmerge_red>0).length,
      unknown:p.filter(x=>x.state.startsWith('UNKNOWN')).length,
      failed_check_observations:p.reduce((a,x)=>a+x.failed_checks.length,0),coverage_pct:null};
  });
  return {schema:'gogreen.top21.merged-rollup.v1',sources:source,roster_total:21,
    repos_seen:new Set(rows.map(x=>x.repository)).size,prs_sampled:rows.length,
    checks_observed:rows.reduce((a,x)=>a+x.checks_retrieved,0),failed_checks:errors.length,
    green_prs:rows.filter(x=>x.state.startsWith('OBSERVED_GREEN')).length,
    pre_red_prs:rows.filter(x=>x.premerge_red>0).length,post_red_prs:rows.filter(x=>x.postmerge_red>0).length,
    unknown_prs:rows.filter(x=>x.state.startsWith('UNKNOWN')).length,
    limitations:['Recent TWO merged among last 30 UPDATED closed PRs per repo, not full history',
      'Commit statuses not currently included','Pre/post timestamps are not independent approval proof',
      'No check runs is UNKNOWN, not green','Same named check does not establish same causal root'],
    by_repo:byRepo,prs:rows,everred:errors,whole_repo_coverage:null,formal_root_closure_credit:0,merge_authorized:false};
}
function csv(rows,keys){return keys.join(',')+'\n'+rows.map(r=>keys.map(k=>JSON.stringify(r[k]??'')).join(',')).join('\n')+'\n'}
export function createOutputs(result,out){
 fs.mkdirSync(out,{recursive:true});
 const f={
  'rollup.json':JSON.stringify({...result,prs:undefined,everred:undefined},null,2)+'\n',
  'merged_prs.json':JSON.stringify(result.prs.map(({failed_checks,...p})=>p),null,2)+'\n',
  'everred_handoff.json':JSON.stringify({schema:'codepurple.everred.merged-checks.v1',root_closure_credit:0,automatic_issue_creation:false,observations:result.everred},null,2)+'\n',
  'merged_prs.csv':csv(result.prs,['repository','pr','merged_at','mainline','state','checks_retrieved','green_checks','premerge_red','postmerge_red']),
  'everred_handoff.csv':csv(result.everred,['event_key','repository','pr','head_sha','chronology','check_name','conclusion','run_id','job_id','details_url']),
  'sipoc_dag.mmd':'flowchart LR\n S["TOP21 GitHub repos"] --> I["PR exact HEAD, merge UTC, check run/job"]\n I --> P["Read-only pagination, deduplication, chronology"]\n P --> G["GoGREEN observed working evidence"]\n P --> E["CODE PURPLE/EVERRED failed-check symptoms"]\n G -.-> C["Owner review, security, REX HOLD"]\n E -.-> C\n'
 };
 const hashes={};for(const [name,value] of Object.entries(f)){fs.writeFileSync(path.join(out,name),value);hashes[name]=hash(value);}
 const receipt={schema:'gogreen.top21.merged-release-receipt.v1',source_roster_blob:result.sources[0].roster_blob,files_sha256:hashes,
  native_ci_exact_head:null,artifact_qa_level:'SOURCE_BOUND_LOCAL_OR_RUNNER',formal_root_closure_credit:0,merge_authorized:false};
 fs.writeFileSync(path.join(out,'manifest.json'),JSON.stringify(receipt,null,2)+'\n');return receipt;
}
export function run(root=process.cwd(),out=null){
 const r=JSON.parse(fs.readFileSync(path.join(root,'mission-control/grand-missions/GM_DMAIC_EVOLUTION_T7_T14_T21_v1.json')));
 const dir=path.join(root,DIR,'snapshots');
 const d=['top7_20261017.json','top14_extension_20261017.json','top21_extension_20261017.json'].map(n=>JSON.parse(fs.readFileSync(path.join(dir,n))));
 const branchNames=Object.fromEntries(rosterNames(r).map(name=>[name,['GBOGEB/pipeline-automation-hub','GBOGEB/CoolProp','GBOGEB/telegraf','GBOGEB/github_Documents'].includes(name)?'master':'main']));
 const v=aggregate(r,d,branchNames);
 const m=createOutputs(v,out??path.join(root,DIR,'generated'));return {summary:{repos:v.repos_seen,prs:v.prs_sampled,checks:v.checks_observed,failed_check_observations:v.failed_checks,green:v.green_prs,premerge_red:v.pre_red_prs,postmerge_red:v.post_red_prs,unknown:v.unknown_prs},manifest:m};
}
if(process.argv[1]&&process.argv[1].endsWith('/analyze.mjs'))console.log(JSON.stringify(run(),null,2));
