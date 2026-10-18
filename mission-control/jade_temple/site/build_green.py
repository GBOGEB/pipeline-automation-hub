#!/usr/bin/env python3
"""Deterministic, offline JADE GoGREEN projection. Never fetch live GitHub here."""
import csv, hashlib, io, json, re, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
SITE=ROOT/'site'
def read(name):return json.loads((DATA/name).read_text('utf-8'))
def compact(obj):return json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=True).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
def build():
 d,c,m=read('REPO_READINESS_NPLUS1.json'),read('COHORT_CROSSWALK_NPLUS1.json'),read('GLOBAL_METRICS_NPLUS1.json')
 rows=d['rows'];assert d['schema']=='jade.temple.repo_readiness.v1' and c['schema']=='jade.temple.cohort_crosswalk.v1' and m['schema']=='jade.temple.global_kpi.v1'
 assert d['admission']==m['release_admission']=='HOLD' and not d['authority_transfer'] and not m['authority_transfer']
 assert len(rows)==21 and len({r['repo'] for r in rows})==21 and set(r['repo'].split('/')[1] for r in rows)==(set(c['intersection'])|set(c['n11_only']))
 assert (c['n11_count'],c['green_count'],c['intersection_count'],len(c['n11_only']),len(c['green_only']))==(21,21,13,8,8)
 assert sum(r['historical_n11_root_candidates'] for r in rows)==706
 assert sum(not r['observed_recent_branch_runs'] for r in rows)==8
 assert sum(r['site']['successful_dynamic_pages_workflow_observed'] for r in rows)==3
 assert all(re.fullmatch('[0-9a-f]{40}',r['head_readback']) and r['readiness']['point_release']=='UNQUALIFIED' and not r['authority_transfer'] and r['merge_admission']=='HOLD' for r in rows)
 assert all(r['site']['served_http_url'] is None and r['site']['served_sha'] is None for r in rows)
 assert {r['historical_gogreen']['status'] for r in rows}=={'COHORT_NOT_SAMPLED','HISTORICAL_RED_OBSERVED','POSITIVE_OBSERVED_HISTORICAL','NO_NATIVE_CHECK_EVIDENCE'}
 g=m['kpis'];assert g['n11_green_sample_overlap']['numerator']==13 and g['positive_historical_sample_n11_overlap']['numerator']==9
 assert g['historical_gogreen_sample_prs']=={'sampled_prs':41,'check_ids':509,'failed_check_manifestations':33,'cohort':'OTHER_TOP21_COHORT'}
 z={'schema':'jade.temple.presentation.v1','admission':'HOLD','authority_transfer':False,'source_observed_window':d['observed_window'],'crosswalk':c,'metrics':m,'rows':rows,'evidence_promoted':False,'security_waiver':False}
 out={}
 out['green.html']=(SITE/'green_template.html').read_bytes()
 out['jade_data.js']=('window.JADE_NPLUS1='+compact(z)+';\n').encode('utf-8')
 out['snapshot.json']=(json.dumps(z,sort_keys=True,indent=2,ensure_ascii=True)+'\n').encode('utf-8')
 s=io.StringIO();w=csv.writer(s);w.writerow(['rank','repository','priority','head_sha','technical_need','next_point_release_todo','gogreen_observation','latest_sample_run','hosting','admission'])
 for r in rows:w.writerow([r['rank'],r['repo'],r['priority'],r['head_readback'],r['technical_need'],r['next_point_release_todo'],r['historical_gogreen']['status'],r['observed_recent_branch_runs'][0]['run_id'] if r['observed_recent_branch_runs'] else 'UNKNOWN','UNKNOWN','HOLD'])
 out['top21_bd_queue.csv']=s.getvalue().encode('utf-8')
 # The standalone bundle does not contain an executable GitHub publisher.
 sourcefiles=['data/REPO_READINESS_NPLUS1.json','data/COHORT_CROSSWALK_NPLUS1.json','data/GLOBAL_METRICS_NPLUS1.json']
 sourcehash={x:hashlib.sha256((ROOT/x).read_bytes()).hexdigest() for x in sourcefiles}
 filehash={p:hashlib.sha256(b).hexdigest() for p,b in out.items()}
 for p in ['jade.css','jade.js','index.html']:filehash[p]=hashlib.sha256((SITE/p).read_bytes()).hexdigest()
 manifest={'schema':'jade.temple.static_manifest.v1','publisher':'EXISTING_METHOD_ATLAS_PAGES_ONLY','merge_admission':'HOLD','security_waiver':False,'authority_transfer':False,'public_files_sha256':filehash,'source_files_sha256':sourcehash,'source_git_sha':None,'evidence_level':'LOCAL_REPRODUCIBILITY','hosted_parity_receipt':None,'served_http_sha':None,'no_second_publisher':True}
 out['site-manifest.json']=(json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode('utf-8')
 return out
if __name__=='__main__':
 out=build();check='--check' in sys.argv
 for path,data in out.items():
  target=SITE/path
  if check:
   if not target.is_file() or target.read_bytes()!=data:raise SystemExit('FAIL: stale '+path)
  else:target.write_bytes(data)
 print(('PASS' if check else 'BUILT'),len(out),'site files SHA256',hashlib.sha256(out['green.html']).hexdigest())