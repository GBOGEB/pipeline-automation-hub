#!/usr/bin/env python3
"""Read-only CPQ-010/013 native-job lineage inspector; NOT a CONTROL promotion.

Input receipts are connector-transcribed GitHub run/job metadata. This checker does
not attest their authenticity; only native artifact bytes and a source-owner
CONTROL disposition could qualify them for causal closure.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

SHA=re.compile(r'[0-9a-f]{40}\Z')
SCHEMA='missioncontrol.code_purple.cpq_i2_native_evidence.v1'
RESULT='missioncontrol.code_purple.cpq_i2_replay.v1'
REQUIRED={'End-to-End Tests','Quality Gates'}


def require(ok, message):
    if not ok:raise ValueError(message)


def analyze(source):
    require(isinstance(source,dict) and source.get('schema')==SCHEMA,'unsupported schema')
    require(source.get('repository')=='GBOGEB/ABACUS','source owner mismatch')
    require(source.get('authority_transfer') is False,'authority escalation')
    require(source.get('source_class')=='NATIVE_API_TRANSCRIPTION_NOT_ARTIFACT','invalid source proof class')
    require(source.get('formal_credit_delta')==0,'unapproved formal credit')
    runs=source.get('runs')
    require(isinstance(runs,list) and len(runs)>=2,'native replay requires >=2 runs')
    ids=set();sha_set=set();observed=[]
    for r in runs:
        run=r.get('run_id');sha=r.get('head_sha');attempt=r.get('attempt');jobs=r.get('jobs')
        require(type(run) is int and run>0 and run not in ids,'invalid or duplicate run ID')
        require(isinstance(sha,str) and SHA.fullmatch(sha),'unbound SHA')
        require(type(attempt) is int and attempt>0,'run attempt invalid')
        require(r.get('workflow')=='DMAIC V3 Test Suite - Continuous Integration','workflow provenance mismatch')
        require(r.get('conclusion') in ('success','failure','cancelled'),'unbound run conclusion')
        require(r.get('event') in ('push','schedule','pull_request'),'invalid native run event')
        require(isinstance(jobs,list) and len(jobs)>=2,'missing native jobs')
        seen_names=set();seen_ids=set();job_state={}
        for j in jobs:
            name=j.get('name');j_id=j.get('job_id');steps=j.get('steps');status=j.get('conclusion')
            require(name in REQUIRED,'unexpected/ambiguous job class')
            require(name not in seen_names and type(j_id) is int and j_id>0 and j_id not in seen_ids,'duplicate/missing job ID')
            require(type(steps) is int and steps>0,'no executed native steps')
            require(status in ('success','failure','cancelled'),'unknown native job state')
            seen_names.add(name);seen_ids.add(j_id);job_state[name]=status
        require(seen_names==REQUIRED,'both distinct E2E/Quality jobs required')
        require(r.get('html_url')==f'https://github.com/GBOGEB/ABACUS/actions/runs/{run}','wrong run permalink')
        require(r.get('head_sha') not in sha_set,'distinct-source repeat is required')
        require((r['conclusion']!='success') or all(v=='success' for v in job_state.values()),'false-green job summary')
        ids.add(run);sha_set.add(sha)
        observed.append({'run_id':run,'head_sha':sha,'attempt':attempt,'event':r['event'],
                         'run_conclusion':r['conclusion'],'jobs':job_state,'native_steps':{j['name']:j['steps'] for j in jobs},
                         'observed_pair_success':all(v=='success' for v in job_state.values())})
    success=[x for x in observed if x['observed_pair_success']]
    require(all(x['run_id']<y['run_id'] for x,y in zip(observed,observed[1:])), 'unordered native run series')
    # The historical repo contract records I2 control_job=null, and does not
    # bind a qualifying CONTROL handoff; leave all causal-rate fields null.
    return {'schema':RESULT,'source_class':source['source_class'],'repository':source['repository'],
            'native_run_count':len(observed),'distinct_heads':len(sha_set),
            'paired_e2e_quality_success_runs':len(success),
            'paired_success_run_ids':[x['run_id'] for x in success],
            'records':observed,
            'i2_canonical_control_handoff':None,'cpq010_status':'OWNER_CONTROL_REQUIRED',
            'cpq013_max_unchanged_root_auto_repeat_after_control':None,
            'cpq013_eligible_denominator':None,
            'accepted_causal_root_closures':None,'independent_stats_eligibility':False,
            'authority_transfer':False,'security_waiver':False,'dispatch_authorized':False,
            'formal_credit_delta':0,'admission':'HOLD'}


def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--input',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path);p.add_argument('--head',required=True)
    a=p.parse_args(argv)
    require(bool(SHA.fullmatch(a.head)),'invalid consumer exact SHA')
    raw=a.input.read_bytes();source=json.loads(raw)
    out=analyze(source)
    out['input_sha256']=hashlib.sha256(raw).hexdigest()
    out['consumer_source_sha']=a.head
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print('CPQ_N6_I2=HISTORICAL_JOB_REPLAY_PASS; CONTROL=HOLD; ROOT_CLOSURES=UNKNOWN')

if __name__=='__main__':main()