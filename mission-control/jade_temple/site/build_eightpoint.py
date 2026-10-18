#!/usr/bin/env python3
"""Reproducible standalone N+3 eight-point HTML review projection.

This script reads governed/frozen source only. --check never rewrites files.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SITE=ROOT/'site'
SOURCE_FILES=(
 'data/EIGHT_POINT_AUDIT_NPLUS3.json',
 'data/HEAD_RECENSUS_NPLUS3.json',
 'data/CAPABILITY_LEDGER_NPLUS3.json',
 'data/COHORT_CROSSWALK_NPLUS1.json',
 'data/READBACK_NPLUS2.json',
)
STATIC_ASSETS=('eightpoint.css','eightpoint.js')

def digest(b):return hashlib.sha256(b).hexdigest()
def compact(z):
 return json.dumps(z,sort_keys=True,separators=(',',':'),ensure_ascii=True).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')

def builds():
 spec=importlib.util.spec_from_file_location('jade_eight_contract', ROOT/'tools/eight_point_contract.py')
 model=importlib.util.module_from_spec(spec);spec.loader.exec_module(model)
 d=model.projection()
 files={
  'eightpoint.html':(SITE/'eightpoint_template.html').read_bytes(),
  'eightpoint.json':(json.dumps(d,sort_keys=True,indent=2,ensure_ascii=True)+'\n').encode(),
  'eightpoint-data.js':('window.JADE_EIGHT='+compact(d)+';\n').encode(),
 }
 sio=io.StringIO()
 writer=csv.writer(sio,lineterminator='\n')
 writer.writerow(['rank','repo','priority','source_sha','head_changed','branch_protection_observed','owner_action','work_order','release'])
 for row in d['rows']:
  writer.writerow([row['rank'],row['repo'],row['priority'],row['observed_head'],row['head_changed'],
                   row['branch_protected_flag'],row['next_release_todo'],row['owner_work_order_state'],row['point_release']])
 files['eightpoint.csv']=sio.getvalue().encode()
 public={p:digest(b) for p,b in files.items()}
 for rel in STATIC_ASSETS:public[rel]=digest((SITE/rel).read_bytes())
 inputs={path:digest((ROOT/path).read_bytes()) for path in SOURCE_FILES}
 inputs['tools/eight_point_contract.py']=digest((ROOT/'tools/eight_point_contract.py').read_bytes())
 inputs['site/eightpoint_template.html']=digest((SITE/'eightpoint_template.html').read_bytes())
 semantic=digest(json.dumps({'inputs':inputs,'metrics':d['metrics'],'section_ids':[p['id'] for p in d['sections']]},sort_keys=True,separators=(',',':')).encode())
 manifest={'schema':'jade.temple.eightpoint_manifest.v3','publisher':'EXISTING_METHOD_ATLAS_PAGES_ONLY',
   'source_semantic_sha256':semantic,'parent_pr_733_head':d['source_sha'],
   'evidence_level':'LOCAL_REPRODUCIBILITY','merge_admission':'HOLD','security_waiver':False,
   'authority_transfer':False,'hosted_eightpoint_sha':None,
   'source_files_sha256':inputs,'public_files_sha256':public,'static_population':len(public),
   'cohort':'N11_MISSION_SELECTED_TOP21','controlled_ids':[p['id'] for p in d['sections']],
   'repo_count':len(d['rows']),'replay_command':'python mission-control/jade_temple/site/build_eightpoint.py --check'}
 files['eightpoint-manifest.json']=(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode()
 return files

def main():
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');args=p.parse_args()
 artifacts=builds()
 for name,blob in artifacts.items():
  target=SITE/name
  if args.check:
   if not target.is_file() or target.read_bytes()!=blob:
    raise SystemExit('JADE_EIGHT_FIRST_RED: REGEN_DRIFT '+name)
  else:target.write_bytes(blob)
 print(json.dumps({'status':'PASS' if args.check else 'BUILT','repo_count':21,'sections':8,
     'artifacts':len(artifacts),'semantic_sha256':json.loads(artifacts['eightpoint-manifest.json'])['source_semantic_sha256']}))
if __name__=='__main__':main()
