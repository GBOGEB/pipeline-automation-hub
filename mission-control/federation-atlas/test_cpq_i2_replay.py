"""CPQ-010/013 independent historical identity and root-credit negative controls."""
from __future__ import annotations
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import cpq_i2_replay as x

RUNS=[
 (36249393504,'f8c3365feac6903152b7d42bdcc3cd992ff48414','pull_request','failure',108424874248,108424874250,'success','failure',9,11),
 (36336861952,'2d29cb81937b11dced88b128256ae138050b706b','push','success',108675180974,108675180909,'success','success',9,11),
 (36420226456,'d9b261f203eef96388db2523f2c78ee1f8cd38bd','schedule','success',108921685585,108921685543,'success','success',10,12),
]
def fixture():
 return {'schema':x.SCHEMA,'repository':'GBOGEB/ABACUS','authority_transfer':False,'formal_credit_delta':0,
         'source_class':'NATIVE_API_TRANSCRIPTION_NOT_ARTIFACT','runs':[
   {'run_id':a,'head_sha':b,'event':c,'conclusion':d,'attempt':1,'workflow':'DMAIC V3 Test Suite - Continuous Integration',
    'html_url':f'https://github.com/GBOGEB/ABACUS/actions/runs/{a}',
    'jobs':[{'name':'End-to-End Tests','job_id':e,'conclusion':g,'steps':j},
            {'name':'Quality Gates','job_id':f,'conclusion':h,'steps':k}]}
    for a,b,c,d,e,f,g,h,j,k in RUNS]}

class NativeI2Tests(unittest.TestCase):
 def test_positive_native_identity_breadth_not_formal_control(self):
  o=x.analyze(fixture());self.assertEqual(o['native_run_count'],3)
  self.assertEqual(o['paired_e2e_quality_success_runs'],2)
  self.assertEqual(o['distinct_heads'],3)
  self.assertEqual(o['paired_success_run_ids'],[36336861952,36420226456])
  self.assertIsNone(o['i2_canonical_control_handoff'])
  self.assertIsNone(o['cpq013_eligible_denominator'])
  self.assertIsNone(o['cpq013_max_unchanged_root_auto_repeat_after_control'])
  self.assertEqual(o['admission'],'HOLD')
 def test_schema_and_source_owner_required(self):
  for key,val in [('schema','fake'),('repository','OTHER/ABACUS'),('authority_transfer',True),('formal_credit_delta',1),('source_class','NATIVE_ARTIFACT_VERIFIED')]:
   with self.subTest(key=key):
    p=fixture();p[key]=val
    with self.assertRaises(ValueError):x.analyze(p)
 def test_duplicate_run_or_source_sha_refused(self):
  for key in ('run_id','head_sha'):
   p=fixture();p['runs'][2][key]=p['runs'][1][key]
   with self.subTest(key=key),self.assertRaises(ValueError):x.analyze(p)
 def test_zero_or_boolean_evidence_ids_rejected(self):
  for key,value in [('run_id',True),('attempt',0),('head_sha','a'*7),('head_sha','x'*40)]:
   p=fixture();p['runs'][0][key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):x.analyze(p)
 def test_job_id_and_steps_must_be_real_positive_integers(self):
  for key,value in [('job_id',0),('job_id',True),('steps',0),('steps',False)]:
   p=fixture();p['runs'][1]['jobs'][0][key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):x.analyze(p)
 def test_duplicate_job_class_and_forged_job_rejected(self):
  for key,value in [('name','Quality Gates'),('job_id',108675180909),('name','dummy job')]:
   p=fixture();p['runs'][1]['jobs'][0][key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):x.analyze(p)
 def test_missing_second_job_rejected(self):
  p=fixture();p['runs'][1]['jobs'].pop()
  with self.assertRaises(ValueError):x.analyze(p)
 def test_conclusion_cannot_claim_success_when_job_fails(self):
  p=fixture();p['runs'][1]['jobs'][0]['conclusion']='failure'
  with self.assertRaises(ValueError):x.analyze(p)
 def test_wrong_permalink_rejected(self):
  p=fixture();p['runs'][1]['html_url']='https://example.invalid/fake'
  with self.assertRaises(ValueError):x.analyze(p)
 def test_events_and_workflows_must_be_exact(self):
  for key,value in [('event','merge'),('workflow','Other Workflow'),('conclusion','green')]:
   p=fixture();p['runs'][0][key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):x.analyze(p)
 def test_old_or_reordered_run_cannot_imply_temporal_improvement(self):
  p=fixture();p['runs'].reverse()
  with self.assertRaises(ValueError):x.analyze(p)
 def test_no_unproven_root_credit_in_result(self):
  z=x.analyze(fixture())
  self.assertIsNone(z['accepted_causal_root_closures'])
  self.assertFalse(z['independent_stats_eligibility'])
  self.assertFalse(z['security_waiver'])
 def test_cli_exact_sha_and_hash_receipt(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td);f=d/'fixture.json';out=d/'result.json';f.write_text(json.dumps(fixture(),sort_keys=True))
   x.main(['--input',str(f),'--out',str(out),'--head','a'*40]);b=out.read_bytes()
   x.main(['--input',str(f),'--out',str(out),'--head','a'*40]);self.assertEqual(out.read_bytes(),b)
   self.assertEqual(len(json.loads(b)['input_sha256']),64)
   with self.assertRaises(ValueError):x.main(['--input',str(f),'--out',str(out),'--head','a'*7])
 def test_run_series_must_be_at_least_two(self):
  p=fixture();p['runs']=p['runs'][:1]
  with self.assertRaises(ValueError):x.analyze(p)
 def test_source_input_does_not_claim_native_artifact(self):
  self.assertEqual(fixture()['source_class'],'NATIVE_API_TRANSCRIPTION_NOT_ARTIFACT')

if __name__=='__main__':unittest.main()