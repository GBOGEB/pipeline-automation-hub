#!/usr/bin/env python3
"""Read-only task planner / capability inventory. No executors or network writes."""
import argparse
import datetime as dt
import json
import os
from collections import Counter
from pathlib import Path
import re
import shutil
import sys
try:
    import tomllib
except ImportError:
    import tomli as tomllib

SHA = re.compile(r"^[a-f0-9]{40}$")
ORDER = {"P0":0,"P1":1,"P2":2,"P3":3}
SKIP={".git",".venv","venv","node_modules","__pycache__",".tox","dist","build"}

def check(cond,msg):
    if not cond:
        raise ValueError(msg)

def load_config(c,p):
    with Path(c).open('rb') as f: cfg=tomllib.load(f)
    data=json.loads(Path(p).read_text(encoding='utf-8'))
    check(cfg.get('code_purple',{}).get('mutation_enabled') is False and cfg['code_purple'].get('allow_remote_dispatch') is False,'local mutation/dispatch forbidden')
    return cfg,validate_plan(data)

def validate_plan(p):
    a=p.get('authority',{})
    check(p.get('schema')=='code-purple.worker-proposal.v1','unknown worker schema')
    check(a.get('mutation_enabled') is False and a.get('security_waiver') is False and a.get('authority_transfer') is False and a.get('merge_admission')=='HOLD' and a.get('dispatch')=='STAGED_NOT_LAUNCHED','authority inversion')
    check(type(p.get('limits',{}).get('initial_concurrency')) is int and 1<=p['limits']['initial_concurrency']<=2,'initial concurrency must be bounded to 2')
    check(p['limits'].get('actual_live_workers') is None,'inferred worker dispatch')
    types=p.get('worker_types',{})
    check(types and all(isinstance(v.get('skills'),list) and v['skills'] and v.get('exec_mode') for v in types.values()),'invalid worker types')
    ids=set(); tasks=p.get('tasks',[])
    check(isinstance(tasks,list) and tasks,'empty workers')
    for t in tasks:
        k=t.get('id')
        check(isinstance(k,str) and k and k not in ids,'duplicate worker task'); ids.add(k)
        check(t.get('type') in types and t.get('priority') in ORDER and type(t.get('read_only')) is bool,'invalid task type')
        check(isinstance(t.get('source_sha'),str) and SHA.fullmatch(t['source_sha']),'source SHA missing')
        check(t.get('repo','').startswith('GBOGEB/') and isinstance(t.get('proof'),str),'source identity')
        leases=t.get('path_leases',[])
        check(isinstance(leases,list) and leases and len(leases)==len(set(leases)),'path lease missing or duplicated')
        check(all(isinstance(x,str) and x and not x.startswith('/') and '..' not in Path(x).parts and '\\' not in x and not x.startswith('.git/') for x in leases),'invalid path lease')
    for t in tasks:
        deps=t.get('depends_on',[])
        check(isinstance(deps,list) and len(deps)==len(set(deps)) and t['id'] not in deps and all(k in ids for k in deps),'unknown dependency')
    done=set()
    while len(done)<len(tasks):
        ready={t['id'] for t in tasks if t['id'] not in done and set(t['depends_on'])<=done}
        check(bool(ready),'cyclic dependency graph');done.update(ready)
    return p

def overlaps(a,b):
    return a==b or a.startswith(b.rstrip('/')+'/') or b.startswith(a.rstrip('/')+'/')

def plan_waves(p,limit=None):
    validate_plan(p)
    tasks={t['id']:t for t in p['tasks']}
    capacity=limit or p['limits']['initial_concurrency']
    check(type(capacity) is int and 1<=capacity<=4,'unapproved concurrency')
    complete=set(); waves=[]
    while len(complete)<len(tasks):
        choices=sorted((t for t in tasks.values() if t['id'] not in complete and set(t['depends_on'])<=complete),key=lambda t:(ORDER[t['priority']],t['id']))
        batch=[]
        for t in choices:
            if len(batch)>=capacity:break
            clash=any(t['repo']==b['repo'] and (not t['read_only'] or not b['read_only']) and any(overlaps(x,y) for x in t['path_leases'] for y in b['path_leases']) for b in batch)
            if not clash:batch.append(t)
        check(batch,'no feasible disjoint path schedule')
        waves.append({'wave':len(waves)+1,'tasks':[{'task_id':t['id'],'worker_type':t['type'],'skills':p['worker_types'][t['type']]['skills'],'lease':t['path_leases'],'status':'READ_ONLY_CANDIDATE' if t['read_only'] else 'STAGED_APPROVAL_NOT_EXECUTED'} for t in batch],'actual_run_ids':None,'simulation_only':True})
        complete.update(t['id'] for t in batch)
    return {'schema':'code-purple.local-disjoint-schedule.v1','waves':waves,'execution':'NOT_LAUNCHED','actual_concurrency':None,'simulation_only':True,'merge_admission':'HOLD'}

def inspect_environment(repo,cfg):
    repo=Path(repo)
    cli={name:{'installed_on_path':shutil.which(name) is not None,'authenticated':None,'authorized_to_dispatch':None} for name in cfg['detect']['cli_candidates']}
    tools={name:shutil.which(name) is not None for name in ('git','python','pwsh','bash','code','pycharm')}
    c=Counter();files=[]
    if repo.is_dir():
        for directory,dirs,names in os.walk(repo,followlinks=False):
            dirs[:]=[d for d in dirs if d not in SKIP and not Path(directory,d).is_symlink()]
            for n in names:
                suffix=Path(n).suffix.lower() or ('Dockerfile' if n=='Dockerfile' else '[none]')
                if suffix in cfg['detect']['file_extensions'] or suffix=='Dockerfile':c[suffix]+=1
                if n in ('AGENTS.md','README.md','CODEOWNERS','pyproject.toml','SKILL.md','requirements.txt') and len(files)<80:
                    files.append(str(Path(directory,n).relative_to(repo)).replace('\\','/'))
    return {'schema':'code-purple.local-capability-census.v1','python':sys.version.split()[0], 'os_family':os.name,'repo_git_head':None,'repo_head_qualification':'LOCAL_ONLY_NOT_NATIVE_CI','tools':tools,'agent_cli':cli,'agent_authorization':'UNKNOWN','scout_files':sorted(files),'extension_counts':dict(sorted(c.items())),'secrets_read':False,'agents_executed':False,'scope':'READ_ONLY_REPO_SCAN_EXCLUDES_SECRETS_AND_GIT_METADATA'}

def build_receipt(repo,cfg,p):
    return {'schema':'code-purple.local-devkit-receipt.v1','date_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'environment':inspect_environment(repo,cfg),'plan':plan_waves(p),'authority':{'security_waiver':False,'authority_transfer':False,'dispatch':'STAGED_NOT_LAUNCHED','admission':'HOLD'}}

def main():
    a=argparse.ArgumentParser();root=Path(__file__).resolve().parent
    a.add_argument('--config',type=Path,default=root/'runner.toml');a.add_argument('--plan',type=Path,default=root/'worker_plan.json');a.add_argument('--repo',type=Path,default=Path.cwd());a.add_argument('--out',type=Path)
    opts=a.parse_args();cfg,plan=load_config(opts.config,opts.plan);value=json.dumps(build_receipt(opts.repo,cfg,plan),indent=2,sort_keys=True)+'\n'
    if opts.out:
        check(not opts.out.is_symlink(),'unsafe output symlink');opts.out.parent.mkdir(parents=True,exist_ok=True);opts.out.write_text(value,encoding='utf-8')
    print(value,end='')

if __name__=='__main__':main()
