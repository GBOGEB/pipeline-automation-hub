"""W378-P1: two bounded topic pilot waves, independent source/read-only fan-in.

Pure consumer of topic_wave/W377; not a runner launcher, scheduler, or issue
controller. No authoritative BD, CI or source-coverage metric is generated.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from metric_atlas import topic_wave

SCHEMA = 'qps.topic-wave-scale.plan.v1'
OUTPUT = 'qps.topic-wave-scale.receipt.v1'
REPO = re.compile(r'GBOGEB/[A-Za-z0-9_.-]+\Z')
SHA40 = re.compile(r'[0-9a-f]{40}\Z')
WORKFLOW = re.compile(r'\.github/workflows/[A-Za-z0-9_.-]+\.yml\Z')


def need(ok,msg):
    if not ok:raise ValueError(msg)


def validate(doc):
    need(isinstance(doc,dict) and doc.get('schema')==SCHEMA,'INVALID_SCALE_SCHEMA')
    need(doc.get('mode')=='TWO_WAVE_DECLARED_READ_ONLY' and doc.get('authority_transfer') is False
         and doc.get('merge_admission')=='HOLD','UNAUTHORISED_SCALE')
    need(doc.get('native_runners_launched')==0 and doc.get('source_writers')==0,'FORGED_EXECUTION')
    need(type(doc.get('max_parallel_readers')) is int and 1<=doc['max_parallel_readers']<=2,'CAPACITY_UNKNOWN_NO_SCALE')
    waves=doc.get('waves')
    need(isinstance(waves,list) and len(waves)==2,'REQUIRE_TWO_BOUNDED_WAVES')
    results=[]; all_topics=set(); all_producers=set()
    graphs=[]
    for idx,pulse in enumerate(waves,1):
        need(pulse.get('max_readers')<=doc['max_parallel_readers'],'WAVE_OVER_CAPACITY')
        result=topic_wave.pilot(pulse)
        need(len(result['topics'])==3,'THREE_TOPICS_PER_WAVE')
        for item in result['topics']:
            need(item['topic'] not in all_topics,'OVERLAPPING_TOPIC_LEASE')
            all_topics.add(item['topic']);all_producers.add(item['producer_repo'])
        graphs.append(topic_wave.digest({'nodes':result['graph']['nodes'],'edges':result['graph']['edges']}))
        results.append(result)
    need(len(all_producers)<=3,'THREE_PHYSICAL_REPOSITORY_CAP')
    need(len(set(graphs))==1,'INCONSISTENT_GRAPH_SOURCE_ACROSS_WAVES')
    # topic_wave.compare() treats method drift as incomparable; never aggregate across it.
    need(len({r['method_version'] for r in results})==1,'METHOD_DRIFT_ACROSS_WAVES')
    targets=doc.get('bd_targets')
    need(isinstance(targets,list) and len(targets)<=12,'UNBOUNDED_TARGETS')
    seen=set()
    for t in targets:
        need(isinstance(t,dict) and set(t)=={'kind','repo','number','head_sha','topic','evidence'},'BAD_TARGET_SHAPE')
        need(t['kind'] in ('PR','ISSUE') and isinstance(t['repo'],str) and REPO.fullmatch(t['repo']), 'BAD_TARGET_REPO')
        need(type(t['number']) is int and t['number']>0,'BAD_TARGET_NUMBER')
        need(t['head_sha'] is None or isinstance(t['head_sha'],str) and SHA40.fullmatch(t['head_sha']),'BAD_TARGET_HEAD')
        need(t['evidence']=='DECLARED_SCENARIO_NOT_NATIVE' and t['topic'] in all_topics,'FALSE_BD_SOURCE_PROOF')
        key=(t['kind'],t['repo'],t['number']);need(key not in seen,'DUPLICATE_BD_TARGET');seen.add(key)
    jobs=doc.get('existing_cron')
    need(isinstance(jobs,list) and len(jobs)<=8,'CRON_CAP')
    names=set()
    for entry in jobs:
        need(isinstance(entry,dict) and set(entry)=={'path','expression','observed_repo','evidence'},'BAD_CRON_SHAPE')
        need(isinstance(entry['path'],str) and WORKFLOW.fullmatch(entry['path']) and entry['path'] not in names,'BAD_CRON_ID')
        names.add(entry['path']);need(entry['evidence']=='READ_ONLY_METADATA' and entry['observed_repo']=='GBOGEB/pipeline-automation-hub','CRON_AUTHORITY_FORGED')
        need(isinstance(entry['expression'],str) and len(entry['expression'].split())==5,'BAD_CRON_EXPRESSION')
    return results, sorted(all_producers)


def plan(doc):
    waves, producers=validate(doc)
    steps=[]; prior=None
    for i,result in enumerate(waves,1):
        member={'wave':i,'pulse_sha256':result['source_pulse_sha256'],
                'topic_count':len(result['topics']),
                'topic_ids':[x['topic'] for x in result['topics']],
                'producer_recensus_scenarios':result['metrics']['source_recensus_requested'],
                'recipient_pull_scenarios':result['metrics']['recipient_pulls_requested'],
                'parent_receipt_sha256':prior, 'state':'LOCAL_DECLARED_PLAN_NOT_EXECUTED'}
        member['receipt_sha256']=topic_wave.digest(member)
        steps.append(member);prior=member['receipt_sha256']
    return {'schema':OUTPUT,'plan_sha256':topic_wave.digest(doc),
            'source_graph_sha256':topic_wave.digest({'nodes':waves[0]['graph']['nodes'],'edges':waves[0]['graph']['edges']}),
            'method_version':waves[0]['method_version'],
            'producer_repos':producers,'planned_topic_count':sum(x['topic_count'] for x in steps),
            'wave_count':len(steps),'waves':steps,
            'bd_targets_count':len(doc['bd_targets']),
            'existing_cron_reused_count':len(doc['existing_cron']),
            'new_cron_jobs_created':0,
            'metrics':{'source_recensus_scenarios':sum(x['producer_recensus_scenarios'] for x in steps),
                       'recipient_pull_scenarios':sum(x['recipient_pull_scenarios'] for x in steps),
                       'queue_depth_planned_waves':len(steps),
                       'verified_external_acks':0,'native_worker_minutes':None,'queue_p95_seconds':None,
                       'saved_scan_minutes':None,'matched_bd_net_burn':None,'root_closures':None,
                       'formal_credit_delta':0,'source_writers':0,'native_runners_launched':0},
            'authority_transfer':False,'merge_admission':'HOLD'}


def emit(doc,out):
    result=plan(doc);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    blob=json.dumps(result,indent=2,sort_keys=True)+'\n'
    (out/'fan-in.json').write_text(blob,encoding='utf-8',newline='\n')
    m={'schema':'qps.topic-wave-scale.manifest.v1','input_sha256':topic_wave.digest(doc),
       'fan_in_sha256':hashlib.sha256(blob.encode()).hexdigest(),'merge_admission':'HOLD','authority_transfer':False}
    (out/'manifest.json').write_text(json.dumps(m,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();r=emit(json.loads(a.input.read_text(encoding='utf-8')),a.out)
    print(json.dumps({'planned_topics':r['planned_topic_count'],'waves':r['wave_count'],
        'native_runners':r['metrics']['native_runners_launched'],'authority':'HOLD'},sort_keys=True))

if __name__=='__main__':main()
