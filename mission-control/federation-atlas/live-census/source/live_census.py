#!/usr/bin/env python3
"""CODE PURPLE: source-typed, read-only disjoint GitHub census.

A census is a measurement projection, not a root closure or merge decision.
No GitHub mutation endpoint is called. No token is stored in outputs.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import statistics
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from source_access import SourceAccessError, read_json, write_diagnostic

SCHEMA = 'codepurple.disjoint_live_census.v1'
REPOS = {'ABACUS':'main', 'CODEX':'main', 'pipeline-automation-hub':'master',
         'cryoplant-project':'main', 'gg_MATH':'main'}
WATCH = {2006:'HANDOVER_V2_B9',2059:'HANDOVER_V2_SYMLINK',2046:'DMAIC_C2_W72',
         2041:'GOV_WORKFLOW',2033:'CI_WORKER_TELEMETRY',2052:'SECURITY_REVIEW',
         2058:'LOSSLESS_BINDER',2045:'PYTHON_COMPAT',2029:'PYTHON_COMPAT',
         2051:'DMAIC_C3',2054:'DMAIC_C4',2057:'DMAIC_C5',2060:'DMAIC_FANIN',
         1995:'GOV_WORKFLOW'}
ROOTS = {
 'GOV_WORKFLOW':{'owner':'ABACUS #2041 / #1995','scope':'Workflow inventory','prs':[1995,2041]},
 'PYTHON_COMPAT':{'owner':'ABACUS #2029 / #2045','scope':'Dependency resolution','prs':[2029,2045,2059,2033]},
 'B9_CHANGED_LINE':{'owner':'ABACUS #2006','scope':'80% changed-line admission','prs':[2006]},
 'HANDOVER_SYMLINK':{'owner':'ABACUS #2059','scope':'Archive path boundary','prs':[2059]},
 'W72_RECEIPT_SHA':{'owner':'ABACUS #2046 / #2033','scope':'Checkout/event SHA lineage','prs':[2046,2033]},
 'SECURITY_SEPARATE':{'owner':'ABACUS #2027 / #2052','scope':'Bandit and Safety distinct','prs':[2052]},
 'CREW_REX_AUTHORITY':{'owner':'CODEX #977','scope':'Dispatch remains staged','prs':[]},
}
SHA = re.compile(r'^[a-f0-9]{40}$')

def digest(data:Any)->str:
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def validate_sha(s:Any)->str:
    if not isinstance(s,str) or not SHA.fullmatch(s):
        raise ValueError('invalid source SHA')
    return s

def utcnow()->str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')

class GitHubReadOnly:
    def __init__(self, token:str|None=None):
        self.token=(os.environ.get('CROSS_REPO_READ_TOKEN') or os.environ.get('GITHUB_TOKEN','')) if token is None else token
    def get(self, resource:str):
        if not resource.startswith('/repos/GBOGEB/') or any(x in resource for x in ('..','\\','%','\n','\r')):
            raise ValueError('unapproved read-only GitHub path')
        req=urllib.request.Request('https://api.github.com'+resource,headers={
            'Accept':'application/vnd.github+json','User-Agent':'code-purple-readonly-census/1.0',
            **({'Authorization':'Bearer '+self.token} if self.token else {})})
        return read_json(req, resource, timeout=12)

def status(counts:dict)->str:
    if counts.get('failure',0)>0 or counts.get('timed_out',0)>0: return 'FAIL'
    if any(counts.get(x,0)>0 for x in ('queued','waiting','in_progress','pending')):return 'PENDING'
    if counts.get('cancelled',0)>0:return 'CANCELLED'
    if counts.get('success',0)>0:return 'PARTIAL_SUCCESS'  # no job checkout provenance
    return 'UNKNOWN'

def data_identity(data:dict):
    if data.get('schema')!=SCHEMA or data.get('authority',{}).get('merge_authorized') is not False or data.get('authority',{}).get('security_waiver') is not False:raise ValueError('authority mismatch')
    if data.get('authority',{}).get('root_closures_verified') is not None:raise ValueError('root closure forged')
    if data.get('authority',{}).get('crew_dispatch')!='STAGED_NOT_LAUNCHED':raise ValueError('crew authority forged')
    nodes=data.get('nodes');edges=data.get('edges')
    if not isinstance(nodes,list) or not isinstance(edges,list):raise ValueError('missing graph')
    ids=[n['id'] for n in nodes]
    if len(set(ids))!=len(ids):raise ValueError('duplicate graph node')
    idset=set(ids)
    for e in edges:
        if e.get('from') not in idset or e.get('to') not in idset:raise ValueError('dangling edge')
        if e.get('type')=='CLOSURE' or e.get('admitted') is True:raise ValueError('unverified closure edge')
    for r in data.get('repositories',[]):validate_sha(r['sha'])
    for p in data.get('prs',[]):validate_sha(p['head_sha']);validate_sha(p['base_sha'])
    return data

def build(observation:dict, predecessor:dict|None=None)->dict:
    """Normalize public API observations; fail closed on missing data/authority."""
    if observation.get('mode') not in ('CONNECTOR_READBACK','NATIVE_GITHUB_READ','OFFLINE_FIXTURE'):raise ValueError('invalid observation origin')
    repos=observation.get('repositories',[]);prs=observation.get('prs',[])
    if not repos or not prs:raise ValueError('empty census')
    nodes=[];edges=[];seen=set()
    def node(id,**kw):
        if id in seen:raise ValueError('duplicate id: '+id)
        seen.add(id);nodes.append({'id':id,**kw})
    def edge(src,dst,kind,proof='DECLARED_NOT_ACCEPTED'):
        edges.append({'from':src,'to':dst,'type':kind,'proof':proof,'admitted':False})
    row_repos=[];row_pr=[];workflow_counter={};missing_checks=0;leaf_count=0
    for r in repos:
        name=r['name'];sha=validate_sha(r['sha']);branch=r['branch']
        if name not in REPOS or branch!=REPOS[name]:raise ValueError('unknown repository or branch')
        uid='repo:'+name;node(uid,kind='REPOSITORY',sha=sha,label=name,url='https://github.com/GBOGEB/'+name)
        row_repos.append({'name':name,'branch':branch,'sha':sha,'url':'https://github.com/GBOGEB/'+name})
    for issue_repo,number,description in [('ABACUS',1860,'Main admission'),('ABACUS',1929,'Root and evidence spine'),('CODEX',977,'Crew dispatch permission')]:
        node(f'issue:{issue_repo}:{number}',kind='GOVERNANCE_ISSUE',label=description,
             url=f'https://github.com/GBOGEB/{issue_repo}/issues/{number}',disposition='OPEN_NOT_CLOSURE')
        edge('repo:'+issue_repo,f'issue:{issue_repo}:{number}','OWNS_ISSUE')
    for rid,info in ROOTS.items():
        node('root:'+rid,kind='ROOT_CANDIDATE',label=rid,owner=info['owner'],disposition='UNKNOWN')
        edge('issue:CODEX:977' if rid=='CREW_REX_AUTHORITY' else 'issue:ABACUS:1929',
             'root:'+rid,'TRACKS_CANDIDATE')
    branches={p.get('head'):p['number'] for p in prs}
    for p in prs:
        n=p['number'];h=validate_sha(p['head_sha']);b=validate_sha(p['base_sha'])
        if not isinstance(n,int) or n<=0:raise ValueError('invalid PR number')
        branch=p.get('base','main');merged=p.get('merged',False);state=p.get('state','unknown')
        if merged and branch!='main':disposition='MERGED_INTERMEDIATE_NOT_MAIN'
        elif merged:disposition='MERGED_MAIN_UNVERIFIED'
        elif state=='open':disposition='OPEN'
        else:disposition='CLOSED_UNMERGED_OR_UNKNOWN'
        pid=f'pr:ABACUS:{n}';node(pid,kind='PULL_REQUEST',label=f'ABACUS #{n}',sha=h,disposition=disposition,url=f'https://github.com/GBOGEB/ABACUS/pull/{n}')
        edge('repo:ABACUS',pid,'CONTAINS_PR')
        if p.get('head') in branches and p.get('head')!=branch and branch in branches:
            edge(f'pr:ABACUS:{branches[branch]}',pid,'STACKED_PARENT')
        elif branch in branches and branches[branch]!=n:
            edge(f'pr:ABACUS:{branches[branch]}',pid,'STACKED_PARENT')
        counts={k:int(v) for k,v in p.get('runs',{}).items() if k in ('success','failure','queued','waiting','in_progress','pending','cancelled','timed_out')}
        if any(v<0 for v in counts.values()):raise ValueError('negative CI counts')
        if not counts:missing_checks+=1
        for key,value in counts.items():workflow_counter[key]=workflow_counter.get(key,0)+value
        row_pr.append({'number':n,'head_sha':h,'base_sha':b,'head':p.get('head',''),'base':branch,'state':state,
                       'merged':bool(merged),'disposition':disposition,'title':p.get('title',f'PR #{n}'),
                       'domain':WATCH.get(n,'UNCLASSIFIED'),'runs':counts,'run_summary':status(counts),
                       'evidence_level':'PR_ASSOCIATED_NOT_CHECKOUT_ATTESTED',
                       'url':f'https://github.com/GBOGEB/ABACUS/pull/{n}'})
        for root in ROOTS:
            if n in ROOTS[root]['prs']:edge('root:'+root,pid,'CANDIDATE_MANIFESTATION')
        for run in p.get('native_runs',[]):
            runid=run.get('id')
            if not isinstance(runid,int) or runid<=0:raise ValueError('invalid run id')
            ri=f'run:ABACUS:{runid}';node(ri,kind='WORKFLOW_RUN',label=run.get('name','Workflow run'),sha=h,
                 conclusion=run.get('conclusion'),url=f'https://github.com/GBOGEB/ABACUS/actions/runs/{runid}')
            edge(pid,ri,'RUN_ASSOCIATED');leaf_count+=1
    prior_heads={q['name']:q['sha'] for q in (predecessor or {}).get('repositories',[])}
    prior_pr={q['number']:q for q in (predecessor or {}).get('prs',[])}
    transitions=[]
    for r in row_repos:
        old=prior_heads.get(r['name'])
        if old and old!=r['sha']:
            transitions.append({'kind':'REPO_HEAD_CHANGED','id':r['name'],'before':old,'after':r['sha'],'invalidation':'REVERIFY_DEPENDENTS'})
    for p in row_pr:
        old=prior_pr.get(p['number'])
        if old and (old['head_sha']!=p['head_sha'] or old['base_sha']!=p['base_sha']):
            transitions.append({'kind':'PR_SOURCE_CHANGED','id':p['number'],'before':old['head_sha'],'after':p['head_sha'],
                                'invalidation':'PRIOR_GREENS_STALE'})
        if old and old['disposition']!=p['disposition']:
            transitions.append({'kind':'PR_DISPOSITION_CHANGED','id':p['number'],'before':old['disposition'],'after':p['disposition'],
                                'invalidation':'NO_ROOT_CLOSURE_INFERRED'})
    src={'repositories':row_repos,'prs':row_pr,'watch':sorted(WATCH)}
    snapshot={'schema':SCHEMA,'observed_at_utc':observation['observed_at_utc'],'origin':observation['mode'],
              'observation_quality':('NATIVE_READ_ONLY_NOT_ARTIFACT_VERIFIED' if observation['mode']=='NATIVE_GITHUB_READ' else 'CONNECTOR_READBACK_NOT_ARTIFACT_VERIFIED' if observation['mode']=='CONNECTOR_READBACK' else 'OFFLINE_FIXTURE_NOT_LIVE'),
              'authority':{'merge_authorized':False,'security_waiver':False,'root_closures_verified':None,'crew_dispatch':'STAGED_NOT_LAUNCHED','qps_decision':'DEFER','admission':'HOLD'},
              'repositories':row_repos,'prs':row_pr,'nodes':nodes,'edges':edges,'events':transitions,
              'metrics':{'repos_observed':len(row_repos),'pr_observed':len(row_pr),'native_run_leaves':leaf_count,
                         'pr_status_unmeasured':missing_checks,'run_associations_by_status':workflow_counter,
                         'candidate_roots':len(ROOTS),'accepted_closed_roots':None,'queue_p50_seconds':None,'queue_p95_seconds':None,
                         'pca_eligible':False,'bt_eligible':False,'last_native_main_coverage':None,
                         'coverage_b9_historical':{'covered':253,'eligible':625,'threshold_percent':80,'evidence_level':'HISTORICAL_DIFFERENT_CHECKOUT'}},
              'source_digest':digest(src),'predecessor_digest':digest(predecessor) if predecessor else None}
    return data_identity(snapshot)

def acquire(reader:GitHubReadOnly):
    """GET only; incomplete result fails, never silently becomes zero."""
    observed={'mode':'NATIVE_GITHUB_READ','observed_at_utc':utcnow(),'repositories':[],'prs':[]}
    for name,branch in REPOS.items():
        q=reader.get('/repos/GBOGEB/'+name+'/commits/'+branch)
        observed['repositories'].append({'name':name,'branch':branch,'sha':validate_sha(q['sha'])})
    for n in WATCH:
        p=reader.get(f'/repos/GBOGEB/ABACUS/pulls/{n}')
        r=reader.get(f'/repos/GBOGEB/ABACUS/actions/runs?head_sha={p["head"]["sha"]}&per_page=100')
        runs=r.get('workflow_runs')
        if not isinstance(runs,list):raise ValueError('native workflow runs missing')
        counts={};small=[]
        for run in runs:
            # GitHub association is NOT an attested checkout. Preserve attempt identities.
            c=run.get('conclusion') or run.get('status') or 'pending'
            counts[c]=counts.get(c,0)+1
            small.append({'id':run['id'],'name':run.get('name'),'conclusion':c,'attempt':run.get('run_attempt'),
                          'head_sha_claim':run.get('head_sha')})
        observed['prs'].append({'number':n,'title':p.get('title'),'head_sha':p['head']['sha'],
            'base_sha':p['base']['sha'],'head':p['head']['ref'],'base':p['base']['ref'],'state':p['state'],
            'merged':p['merged'],'runs':counts,'native_runs':small[:30]})
    return observed

def write_outputs(snapshot:dict,out:Path):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    files={'snapshot.json':snapshot,'nodes.json':snapshot['nodes'],'edges.json':snapshot['edges'],
           'diagnostics.json':{'schema':'codepurple.live.diagnostics.v1','metrics':snapshot['metrics'],
                               'authority':snapshot['authority'],'observed_at_utc':snapshot['observed_at_utc']}}
    hashes={}
    for name,data in files.items():
        content=json.dumps(data,indent=2,sort_keys=True,ensure_ascii=False)+'\n'
        tmp=out/(name+'.tmp');tmp.write_text(content,encoding='utf-8');tmp.replace(out/name)
        hashes[name]=hashlib.sha256((out/name).read_bytes()).hexdigest()
    (out/'events.ndjson').write_text(''.join(json.dumps(e,sort_keys=True)+'\n' for e in snapshot['events']),encoding='utf-8')
    hashes['events.ndjson']=hashlib.sha256((out/'events.ndjson').read_bytes()).hexdigest()
    manifest={'schema':'codepurple.live.bundle.v1','source_digest':snapshot['source_digest'],
              'observed_at_utc':snapshot['observed_at_utc'],'files_sha256':hashes,
              'evidence_level':'LOCAL_REPRODUCIBILITY','release_authorized':False}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return manifest

def cli(argv=None):
    parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--seed');group.add_argument('--refresh',action='store_true');group.add_argument('--verify')
    parser.add_argument('--previous');parser.add_argument('--out',default='output')
    a=parser.parse_args(argv)
    if a.verify:
        root=Path(a.verify);m=json.loads((root/'manifest.json').read_text())
        for name,sha in m['files_sha256'].items():
            if hashlib.sha256((root/name).read_bytes()).hexdigest()!=sha:raise ValueError('digest mismatch: '+name)
        data_identity(json.loads((root/'snapshot.json').read_text()));print('PASS',len(m['files_sha256']));return
    if a.refresh:
        try:
            obs=acquire(GitHubReadOnly())
        except SourceAccessError as error:
            diagnostic=write_diagnostic(error,Path(a.out))
            print(json.dumps({'status':'SOURCE_ACCESS_UNKNOWN_FAIL_CLOSED',
                              'repository':error.repository,'http_status':error.http_status,
                              'diagnostic':str(diagnostic)},sort_keys=True))
            raise SystemExit(2)
    else:
        obs=json.loads(Path(a.seed).read_text())
    prev=json.loads(Path(a.previous).read_text()) if a.previous else None
    m=write_outputs(build(obs,prev),Path(a.out));print(json.dumps({'status':'LOCAL_REPRODUCIBILITY','files':len(m['files_sha256']),'source_digest':m['source_digest']}))
if __name__=='__main__':cli()
