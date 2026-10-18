"""N+3 eight-outline governance, source and action lineage negative controls."""
from __future__ import annotations
import copy
import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('jade8',ROOT/'tools/eight_point_contract.py')
engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
spec2=importlib.util.spec_from_file_location('jade8build',ROOT/'site/build_eightpoint.py')
builder=importlib.util.module_from_spec(spec2);spec2.loader.exec_module(builder)

def read(name):return json.loads((ROOT/'data'/name).read_text())
class EightPointMIP(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.a=read('EIGHT_POINT_AUDIT_NPLUS3.json');cls.h=read('HEAD_RECENSUS_NPLUS3.json')
  cls.l=read('CAPABILITY_LEDGER_NPLUS3.json');cls.x=read('COHORT_CROSSWALK_NPLUS1.json');cls.o=read('READBACK_NPLUS2.json')
 def bad(self,msg,component,mutation):
  a,h,l,x,o=[copy.deepcopy(t) for t in (self.a,self.h,self.l,self.x,self.o)]
  target={'a':a,'h':h,'l':l,'x':x,'o':o}[component]
  mutation(target)
  with self.assertRaisesRegex(ValueError,re.escape('JADE_EIGHT_FAIL_CLOSED: ')+msg):engine.validate(a,h,l,x,o)
 def test_complete_eight_point_mip(self):
  self.assertTrue(engine.validate(self.a,self.h,self.l,self.x,self.o))
  for section in self.a['eight_points']:
   with self.subTest(section=section['id']):
    self.assertTrue(section['MIP'] and section['current_gap'] and section['owner'])
    self.assertTrue(section['implementation'] and section['target_or_stop'])
    self.assertFalse(section['hard_gate_promoted'])
 def test_current_21_exact_shas(self):
  self.assertEqual(len(self.h['rows']),21)
  self.assertEqual(sum(r['head_changed'] for r in self.h['rows']),4)
  self.assertEqual(sum(r['branch_protected_flag'] for r in self.h['rows']),1)
  self.assertEqual([sum(r['priority']==x for r in self.h['rows']) for x in ('P0','P1','P2')],[5,9,7])
 def test_release_is_null_not_zero_or_success(self):
  z=engine.projection();self.assertEqual(z['merge_admission'],'HOLD')
  self.assertIsNone(z['formal_point_release']);self.assertIsNone(z['hosted_nplus3_verified'])
  self.assertIsNone(z['metrics']['fleet_coverage']);self.assertIsNone(z['metrics']['confirmed_defects'])
 def test_no_false_green_from_merged_cp_w10(self):
  z=engine.projection();self.assertEqual(z['metrics']['action_owner_closed'],0)
  self.assertTrue(all(not x['release_credit'] for x in z['capabilities']))
  self.assertEqual(self.a['cp_w10_pr_734_state'],'MERGED_WITHOUT_OBSERVED_HUMAN_REVIEW')
 def test_historical_first_red_unchanged(self):
  event=next(x for x in self.l['evidence'] if x['type']=='HISTORICAL_FIRST_RED')
  self.assertEqual(event['outcome'],'FAILURE');self.assertEqual(event['run'],39169421620)
 def test_no_invalid_html_authority(self):
  h=(ROOT/'site/eightpoint.html').read_text()
  self.assertIn('MERGE ADMISSION',h)
  self.assertIn('connect-src &#39;none&#39;',h.replace("'",'&#39;'))
  self.assertNotIn('http://',h)
 def test_csv_21_complete_noneditable(self):
  import csv
  with (ROOT/'site/eightpoint.csv').open(newline='') as f:rows=list(csv.DictReader(f))
  self.assertEqual(len(rows),21)
  self.assertTrue(all(r['release']=='UNQUALIFIED' for r in rows))
 def test_drift_tamper_rejected(self):
  self.bad('head drift mismatch','h',lambda x:x['rows'][0].__setitem__('head_changed',False))
 def test_fake_owner_close_rejected(self):
  self.bad('false owner closure','h',lambda x:x['rows'][0].__setitem__('owner_work_order_state','CLOSED'))
 def test_bad_cohort_intersection_rejected(self):
  self.bad('cohort falsification','x',lambda x:x.__setitem__('intersection_count',21))
 def test_false_merge_admission_rejected(self):
  self.bad('authority and HOLD','a',lambda x:x.__setitem__('merge_admission','PASS'))
 def test_false_owner_release_rejected(self):
  self.bad('fabricated release','a',lambda x:x.__setitem__('point_release_qualifications',21))
 def test_false_independent_review_rejected(self):
  self.bad('unauthorized green','a',lambda x:x['gate_states'].__setitem__('independent_review','PASS'))
 def test_swapped_cohort_order_rejected(self):
  self.bad('cohort order','h',lambda x:x['rows'].reverse())
 def test_empty_implementation_rejected(self):
  self.bad('J03 source changes','a',lambda x:x['eight_points'][2].__setitem__('implementation',[]))
 def test_mip_no_kpi_rejected(self):
  self.bad('J06 measurable KPI','a',lambda x:x['eight_points'][5].__setitem__('kpi',{}))
 def test_corrupt_section_order_rejected(self):
  self.bad('eight point identity/order','a',lambda x:x['eight_points'].reverse())
 def test_duplicate_capability_run_rejected(self):
  self.bad('duplicate capability ID','l',lambda x:x['evidence'].append(copy.deepcopy(x['evidence'][0])))
 def test_duplicate_run_different_id_rejected(self):
  def mutate(x):
   item=copy.deepcopy(x['evidence'][0]);item['id']='E-NEW';x['evidence'].append(item)
  self.bad('double-counted run','l',mutate)
 def test_green_event_changed_to_failure_rejected(self):
  self.bad('false positive','l',lambda x:x['evidence'][0].__setitem__('outcome','FAILURE'))
 def test_everred_failure_changed_to_green_rejected(self):
  self.bad('first red changed','l',lambda x:x['evidence'][1].__setitem__('outcome','SUCCESS'))
 def test_untrusted_receipt_denied(self):
  self.bad('untrusted native receipt','l',lambda x:x['evidence'][0].__setitem__('url','https://evil.invalid/'))
 def test_dependency_cycle_rejected(self):
  def mutate(x):x['dependencies'].append({'from':'J08','to':'J01','kind':'false convergence'})
  self.bad('DAG contains cycle','a',mutate)
 def test_unknown_dependency_rejected(self):
  self.bad('DAG invalid edge','a',lambda x:x['dependencies'][0].__setitem__('to','J99'))
 def test_out_of_order_wave_rejected(self):
  self.bad('wave dependency / admission','a',lambda x:x['wave_plan'][0].__setitem__('depends_on',['W4']))
 def test_one_only_pages_publisher(self):
  self.bad('competing publisher','a',lambda x:x.__setitem__('parent_publisher','JADE_SECOND_DEPLOYER'))
 def test_deterministic_source_and_public_hashes(self):
  build=builder.builds();manifest=json.loads(build['eightpoint-manifest.json'])
  self.assertEqual(manifest['static_population'],6);self.assertEqual(manifest['repo_count'],21)
  self.assertEqual(manifest['controlled_ids'],['J%02d'%i for i in range(1,9)])
  for name,body in build.items():self.assertEqual((ROOT/'site'/name).read_bytes(),body)
  for name,digest in manifest['public_files_sha256'].items():
   self.assertEqual(engine.sha(ROOT/'site'/name),digest)
 def test_builder_cli_generate_check_and_drift_rejection(self):
  import sys
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as temp:
   with patch.object(builder,'SITE',Path(temp)),patch.object(builder,'builds',return_value={'eightpoint.html':b'known\n','eightpoint-manifest.json':b'{"source_semantic_sha256":"sample"}'}):
    with patch.object(sys,'argv',['build_eightpoint.py']):builder.main()
    self.assertEqual((Path(temp)/'eightpoint.html').read_bytes(),b'known\n')
    with patch.object(sys,'argv',['build_eightpoint.py','--check']):builder.main()
    (Path(temp)/'eightpoint.html').write_bytes(b'tampered')
    with patch.object(sys,'argv',['build_eightpoint.py','--check']):
     with self.assertRaisesRegex(SystemExit,'JADE_EIGHT_FIRST_RED: REGEN_DRIFT'):builder.main()
 def test_builder_missing_static_rejected(self):
  import sys
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as temp:
   with patch.object(builder,'SITE',Path(temp)),patch.object(builder,'builds',return_value={'eightpoint.html':b'expected'}),patch.object(sys,'argv',['build_eightpoint.py','--check']):
    with self.assertRaisesRegex(SystemExit,'JADE_EIGHT_FIRST_RED: REGEN_DRIFT'):builder.main()
 def test_old_source_and_new_static_separate_hashes(self):
  m=read('EIGHT_POINT_AUDIT_NPLUS3.json')
  self.assertEqual(m['parent_pr_733_head'],engine.projection()['source_sha'])
  self.assertNotEqual(engine.sha(ROOT/'site/eightpoint.html'),engine.sha(ROOT/'data/EIGHT_POINT_AUDIT_NPLUS3.json'))
if __name__=='__main__':unittest.main()
