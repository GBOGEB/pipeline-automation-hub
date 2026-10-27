#!/usr/bin/env python3
"""Eight independent JADE N+3 MIP work packages, immutable evidence gates.

No GitHub mutation, CI dispatch, false success or bypass is possible here.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
_pb=importlib.util.spec_from_file_location('jade_private_boundary',ROOT/'tools/private_boundary.py');PB=importlib.util.module_from_spec(_pb);_pb.loader.exec_module(PB)
SHA40=re.compile(r'^(?:[0-9a-f]{40}|'+PB.MARK+')$')  # a private repo's head is PB.MARK (counts only)
GATES=('source_integrity','native_tests','matched_coverage','security','independent_review',
       'required_checks','blocked_red_canary','hosted_parity','owner_release')
POINTS=tuple('J%02d'%i for i in range(1,9))
CAP_TYPES=('NATIVE_POSITIVE','HISTORICAL_FIRST_RED','OWNER_CONFIRMED_CLOSURE')
PRIORITIES={'P0':5,'P1':9,'P2':7}

def refuse(ok,msg):
 if not ok:raise ValueError('JADE_EIGHT_FAIL_CLOSED: '+msg)

def load(name):
 return json.loads((ROOT/'data'/name).read_text(encoding='utf-8'))

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def validate(audit,heads,ledger,crosswalk,old):
 refuse(audit.get('schema')=='jade.temple.eightpoint_audit.v3','audit schema')
 refuse(heads.get('schema')=='jade.temple.eightpoint_heads.v3','heads schema')
 refuse(ledger.get('schema')=='jade.temple.capability_ledger.v3','ledger schema')
 for x in (audit,heads,ledger):
  refuse(x.get('merge_admission')=='HOLD' and x.get('authority_transfer') is False,'authority and HOLD')
 refuse(audit.get('security_waiver') is False and heads.get('security_waiver') is False,'waiver')
 refuse(audit.get('parent_publisher')=='EXISTING_METHOD_ATLAS_PAGES_ONLY','competing publisher')
 refuse(audit.get('owner_review_disposition') is None and audit.get('hosted_eightpoint_exact_parity') is None,'false acceptance')
 refuse(audit.get('point_release_qualifications') is None,'fabricated release')
 refuse(bool(SHA40.fullmatch(audit.get('parent_pr_733_head',''))) and bool(SHA40.fullmatch(audit.get('cp_w10_pr_734_head',''))),'source identities')
 gate=audit.get('gate_states',{})
 refuse(set(gate)==set(GATES),'nine independent gate population')
 refuse(all(v in ('PASS','FAIL','UNKNOWN','PENDING','MISSING') for v in gate.values()),'invalid gate status')
 refuse(gate['independent_review']!='PASS' and gate['required_checks']!='PASS' and gate['owner_release']!='PASS','unauthorized green')
 eight=audit.get('eight_points',[])
 refuse(len(eight)==8 and tuple(p['id'] for p in eight)==POINTS,'eight point identity/order')
 for point in eight:
  refuse(set(['id','outline','scope','baseline','current_gap','MIP','implementation','kpi','target_or_stop','owner','admission_blocker','stop_rule','evidence_urls']).issubset(point),'section contract keys')
  for k in ('outline','scope','baseline','current_gap','MIP','target_or_stop','owner','admission_blocker','stop_rule'):
   refuse(bool(str(point[k]).strip()),point['id']+' missing '+k)
  refuse(bool(point['implementation']) and all(isinstance(z,str) and z for z in point['implementation']),point['id']+' source changes')
  refuse(bool(point['kpi']) and all(v is None or isinstance(v,(int,float,str)) for v in point['kpi'].values()),point['id']+' measurable KPI')
  refuse(point.get('source_qualified') is False and point.get('owner_qualified') is False and point.get('hard_gate_promoted') is False,point['id']+' false closure')
  refuse(point['evidence_urls'] and all(z.startswith('https://github.com/') for z in point['evidence_urls']),point['id']+' source URLs')
 rows=heads.get('rows',[])
 refuse(len(rows)==len(old.get('rows',[]))==21,'N11 population')
 refuse([z['repo'] for z in rows]==[z['repo'] for z in old['rows']],'cohort order')
 refuse(len({z['repo'] for z in rows})==21,'duplicate repo')
 refuse(heads.get('cohort')=='N11_MISSION_SELECTED_TOP21' and heads.get('observation_kind')=='NON_ATOMIC_21_GITHUB_BRANCH_READBACK','observation provenance')
 refuse(all(bool(SHA40.fullmatch(x['observed_head'])) and bool(SHA40.fullmatch(x['prior_nplus2_sha'])) for x in rows),'invalid SHA')
 refuse(all(x['prior_nplus2_sha']==old['rows'][i]['current_head'] for i,x in enumerate(rows)),'previous SHA lineage')
 refuse(all(x['head_changed']==(x['observed_head']!=x['prior_nplus2_sha']) for x in rows),'head drift mismatch')
 changes=[x['repo'] for x in rows if x['head_changed']]
 refuse(heads['head_drift_count']==len(changes) and heads['changed_repos']==changes,'drift denominator')
 refuse(all(x.get('owner_work_order_state')=='OPEN_UNQUALIFIED' and x.get('point_release')=='UNQUALIFIED' for x in rows),'false owner closure')
 refuse({p:sum(x['priority']==p for x in rows) for p in PRIORITIES}==PRIORITIES,'priority population')
 refuse(sum(x['branch_protected_flag'] for x in rows)==1,'branch protected flag census')
 refuse(crosswalk['n11_count']==crosswalk['green_count']==21 and crosswalk['intersection_count']==13
        and len(crosswalk['n11_only'])==len(crosswalk['green_only'])==8
        and crosswalk.get('owner_approved_single_cohort') is None,'cohort falsification')
 events=ledger.get('evidence',[])
 refuse(len(events)==len({x['id'] for x in events}),'duplicate capability ID')
 refuse(len({(x['sha'],x['run']) for x in events})==len(events),'double-counted run')
 for event in events:
  refuse(event['type'] in CAP_TYPES and event['outcome'] in ('SUCCESS','FAILURE'), 'event state')
  refuse(bool(SHA40.fullmatch(event['sha'])) and isinstance(event['run'],int) and event['run']>0, 'event source')
  refuse(event.get('release_credit') is False,'capability is not release proof')
  refuse(event['url'].startswith('https://github.com/GBOGEB/'),'untrusted native receipt')
  if event['type']=='NATIVE_POSITIVE':refuse(event['outcome']=='SUCCESS','false positive')
  if event['type']=='HISTORICAL_FIRST_RED':refuse(event['outcome']=='FAILURE','first red changed')
 refuse(not ledger.get('owner_release_receipts') and ledger.get('postmerge_main_audit_receipt') is None,'unverified main promoted')
 deps=audit.get('dependencies',[])
 refuse(len(deps)>=7 and all(d['from'] in POINTS and d['to'] in POINTS and d['from']!=d['to'] for d in deps),'DAG invalid edge')
 adjacency={k:[] for k in POINTS}
 for d in deps:adjacency[d['from']].append(d['to'])
 def visit(k,stack,done):
  refuse(k not in stack,'DAG contains cycle')
  if k in done:return
  for child in adjacency[k]:visit(child,stack|{k},done)
  done.add(k)
 done=set()
 for k in POINTS:visit(k,set(),done)
 waves=audit.get('wave_plan',[])
 refuse(len(waves)==5 and len({w['id'] for w in waves})==5,'five bounded wave identities')
 known=set()
 for w in waves:
  refuse(set(w['depends_on']).issubset(known) and w.get('admission')=='HOLD','wave dependency / admission')
  known.add(w['id'])
 return True

def projection():
 a=load('EIGHT_POINT_AUDIT_NPLUS3.json');h=load('HEAD_RECENSUS_NPLUS3.json');l=load('CAPABILITY_LEDGER_NPLUS3.json')
 x=load('COHORT_CROSSWALK_NPLUS1.json');o=load('READBACK_NPLUS2.json')
 validate(a,h,l,x,o)
 open_work=sum(r['owner_work_order_state']=='OPEN_UNQUALIFIED' for r in h['rows'])
 positive=sum(e['type']=='NATIVE_POSITIVE' for e in l['evidence'])
 red=sum(e['type']=='HISTORICAL_FIRST_RED' for e in l['evidence'])
 assert open_work==21
 stat={'repos':21,'drift':h['head_drift_count'],'flag_protected':sum(r['branch_protected_flag'] for r in h['rows']),
       'action_open':open_work,'action_owner_closed':0,'priority':PRIORITIES,
       'intersection':x['intersection_count'],'n11_only':8,'green_only':8,
       'native_positive_events':positive,'historical_first_red_events':red,
       'release_qualified':None,'fleet_coverage':None,'n2_focused_statements':[279,291],
       'n2_focused_branches':[113,130],'original_root_candidates':706,
       'high_yield_root_candidates':627,'confirmed_defects':None,
       'eight_sections':len(a['eight_points']),
       'governance_gate_pass':sum(v=='PASS' for v in a['gate_states'].values()),
       'governance_gate_total':len(GATES)}
 return {'schema':'jade.temple.eightpoint_projection.v3','source_observed_at':h['observed_at_utc'],
         'source_readback_non_atomic':True,'source_sha':a['parent_pr_733_head'],
         'stacked_parent_pr':733,'merged_cp_w10_pr':734,
         'cohort':'N11_MISSION_SELECTED_TOP21','publisher':'EXISTING_METHOD_ATLAS_PAGES_ONLY',
         'merge_admission':'HOLD','security_waiver':False,'authority_transfer':False,
         'hosted_nplus3_verified':None,'formal_point_release':None,
         'metrics':stat,'gates':a['gate_states'],'sections':a['eight_points'],
         'rows':h['rows'],'capabilities':l['evidence'],'dag':a['dependencies'],
         'waves':a['wave_plan'],
         'stop_decision':'OWNER_BLOCKED','stop_reason':'Mandatory independent human review, required checks and release owner proof unqualified',
         'limitations':a['limitations']}

if __name__=='__main__':
 r=projection();print(json.dumps({'status':'PASS','sections':len(r['sections']),'rows':len(r['rows']),
                                  'head_drift':r['metrics']['drift'],'open':r['metrics']['action_open'],
                                  'stop':r['stop_decision']},sort_keys=True))
