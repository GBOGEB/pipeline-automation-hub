#!/usr/bin/env python3
"""JADE N+2 deterministic read-only renderer and tamper-evident multi-source manifest."""
from __future__ import annotations
import argparse,csv,hashlib,importlib.util,io,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SITE=ROOT/'site';DATA=ROOT/'data'
_pb=importlib.util.spec_from_file_location('jade_private_boundary',ROOT/'tools/private_boundary.py');PB=importlib.util.module_from_spec(_pb);_pb.loader.exec_module(PB)
SOURCES=("data/READBACK_NPLUS2.json","data/EVIDENCE_EVENTS_NPLUS2.json","data/STOP_MODEL_NPLUS2.json","data/REPO_READINESS_NPLUS1.json")

def load(rel): return json.loads((ROOT/rel).read_text(encoding='utf-8'))
def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def compact(d): return json.dumps(d,sort_keys=True,separators=(',',':'),ensure_ascii=True).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
def builds():
    r,e,m=(load(x) for x in SOURCES[:3]);prior=load(SOURCES[3])
    assert r['schema']=='jade.temple.fleet_readback.v2' and e['schema']=='jade.temple.evidence_events.v2' and m['schema']=='jade.temple.stopping_model.v2'
    assert r['merge_admission']==e['merge_admission']==m['merge_admission']=='HOLD'
    assert r['authority_transfer'] is e['authority_transfer'] is m['authority_transfer'] is False
    assert r['security_waiver'] is m['security_waiver'] is False
    assert len(r['rows'])==len(prior['rows'])==21 and len({x['repo'] for x in r['rows']})==21
    assert [x['repo'] for x in r['rows']]==[x['repo'] for x in prior['rows']]
    assert sum(x['head_changed'] for x in r['rows'])==3
    assert sum(x['priority']=='P0' for x in r['rows'])==5 and sum(x['priority']=='P1' for x in r['rows'])==9
    assert all(bool(re.fullmatch('[0-9a-f]{40}',x['current_head'])) or x['current_head']==PB.MARK for x in r['rows'])
    assert all(x['owner_final_action_closed'] is False and x['owner_J5_point_release'] is None for x in r['rows'])
    check=e['summary']['main_exact_head_check_runs'];assert check=={'success':23,'skipped':3,'failure':1,'total':27}
    assert e['summary']['owner_root_closures_credited']==0 and m['current_owner_actions']['closed_qualified']==0
    assert m['current_main_sha']==next(x['current_head'] for x in r['rows'] if x['repo']=='GBOGEB/pipeline-automation-hub')
    spec=importlib.util.spec_from_file_location('jade_stop',ROOT/'tools/stop_rules.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    controller=mod.from_snapshot(m)
    assert controller['action']=='REPAIR_FIRST_RED' and controller['merge_admission']=='HOLD'
    z={'schema':'jade.temple.burndown_projection.v2','cohort':'N11_MISSION_SELECTED_TOP21','source_observed_date':'2026-10-19',
      'source_main_head':m['current_main_sha'],'authority_transfer':False,'security_waiver':False,'merge_admission':'HOLD',
      'evidence_level':'FROZEN_NONATOMIC_REPO_READBACK_PLUS_NATIVE_LINKS',
      'rows':r['rows'],'gates':m['gates'],'controller':controller,
      'metrics':{'heads_observed':21,'heads_changed':3,'owner_actions_open':21,'owner_actions_closed':0,
       'owner_causal_roots_qualified':0,'root_review_candidates_historical':706,
       'historical_cohort_overlap':13,'historical_green_positive_in_overlap':9,
       'current_head_GOGREEN_preservation_scope':'MISSION_CONTROL_JADE_ONLY',
       'main_check_runs':check,'source_bound_native_jade_tests':44,'source_bound_native_jade_viewports':3,
       'hosted_jade_qualified':None,'global_matched_statement_coverage':None,
       'global_matched_branch_coverage':None},
      'pulses':m['pulses'],'first_red_current_head':m['first_red_current_head'],
      'governance_no_review_pr':732,'source_links':[ev['url'] for ev in e['events'] if 'url' in ev],
      'stop_policy':m['stop_rules']}
    z=PB.project(z);r=dict(r,rows=z['rows'])
    files={}
    files['burndown.html']=(SITE/'burndown_template.html').read_bytes()
    files['burndown.json']=(json.dumps(z,sort_keys=True,indent=2,ensure_ascii=True)+'\n').encode('utf-8')
    files['burndown-data.js']=('window.JADE_NPLUS2='+compact(z)+';\n').encode('utf-8')
    c=io.StringIO();wr=csv.writer(c,lineterminator='\n')
    wr.writerow(['rank','repo','priority','old_head','current_head','head_drift','first_two_run_ids','owner_next_release_todo','owner_action_closed','governed_release'])
    for x in r['rows']:
        wr.writerow([x['rank'],x['repo'],x['priority'],x['nplus1_sha'],x['current_head'],x['head_changed'],
                     '|'.join(str(y['id']) for y in x['latest_two_branch_runs']),x['next_release_todo'],False,'UNQUALIFIED'])
    files['burndown.csv']=c.getvalue().encode('utf-8')
    pubfiles={k:sha(v) for k,v in files.items()}
    for asset in ('burndown.css','burndown.js'):pubfiles[asset]=sha((SITE/asset).read_bytes())
    model={'schema':'jade.temple.burndown_manifest.v2','publisher':'EXISTING_METHOD_ATLAS_PAGES_ONLY',
        'evidence_level':'LOCAL_REPRODUCIBILITY','merge_admission':'HOLD','authority_transfer':False,
        'security_waiver':False,'hosted_sha':None,
        'static_population':len(pubfiles),'readback_group':'N11_MISSION_SELECTED_TOP21',
        'public_files_sha256':pubfiles,'source_files_sha256':{rel:sha((ROOT/rel).read_bytes()) for rel in SOURCES},
        'replay_command':'python mission-control/jade_temple/site/build_burndown.py --check'}
    files['burndown-manifest.json']=(json.dumps(model,sort_keys=True,indent=2)+'\n').encode('utf-8')
    return files

def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    files=builds()
    for rel,b in files.items():
        file=SITE/rel
        if a.check:
            if not file.is_file() or file.read_bytes()!=b:
                raise SystemExit('JADE_BURNDOWN_FIRST_RED: STALE_SOURCE '+rel)
        else:file.write_bytes(b)
    print(('PASS' if a.check else 'BUILT')+' JADE N+2 files='+str(len(files))+' sha256='+sha(files['burndown.json']))
if __name__=='__main__':main()
