"""JADE N+2 unit, source replay and adversarial publication proof."""
import copy,hashlib,importlib.util,json,re,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('builder',ROOT/'site/build_burndown.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
spec2=importlib.util.spec_from_file_location('bridge',ROOT/'portal_bridge.py')
bridge=importlib.util.module_from_spec(spec2);spec2.loader.exec_module(bridge)
class BurndownTests(unittest.TestCase):
 def test_deterministic_cli_check_and_rebuild(self):
  import sys
  from unittest.mock import patch
  with patch.object(sys,'argv',['build_burndown.py','--check']):mod.main()
  with patch.object(sys,'argv',['build_burndown.py']):mod.main()
  with patch.object(sys,'argv',['build_burndown.py','--check']):mod.main()
 def test_all_pinned_sources_validate(self):
  out=mod.builds()
  self.assertEqual(set(out),{'burndown.html','burndown.json','burndown-data.js','burndown.csv','burndown-manifest.json'})
  for k,b in out.items():self.assertEqual((ROOT/'site'/k).read_bytes(),b)
 def test_manifest_members_and_parent_sources(self):
  m=json.loads((ROOT/'site/burndown-manifest.json').read_text(encoding='utf-8'))
  self.assertEqual(m['static_population'],6)
  self.assertEqual(len(m['source_files_sha256']),4)
  for k,v in m['source_files_sha256'].items():self.assertEqual(hashlib.sha256((ROOT/k).read_bytes()).hexdigest(),v)
  for k,v in m['public_files_sha256'].items():self.assertEqual(hashlib.sha256((ROOT/'site'/k).read_bytes()).hexdigest(),v)
 def test_exact_roster_and_priority(self):
  d=json.loads((ROOT/'site/burndown.json').read_text(encoding='utf-8'))
  self.assertEqual(len(d['rows']),21)
  self.assertEqual((sum(r['priority']=='P0' for r in d['rows']),sum(r['priority']=='P1' for r in d['rows']),sum(r['priority']=='P2' for r in d['rows'])),(5,9,7))
  self.assertEqual(d['metrics']['heads_changed'],3)
 def test_no_false_closure_or_release(self):
  d=json.loads((ROOT/'site/burndown.json').read_text(encoding='utf-8'))
  self.assertEqual(d['merge_admission'],'HOLD')
  self.assertEqual(d['metrics']['owner_actions_closed'],0)
  self.assertIsNone(d['metrics']['hosted_jade_qualified'])
  self.assertIsNone(d['metrics']['global_matched_branch_coverage'])
 def test_main_checks_negative_and_green_population(self):
  d=json.loads((ROOT/'site/burndown.json').read_text(encoding='utf-8'))
  self.assertEqual(d['metrics']['main_check_runs'],{'success':23,'skipped':3,'failure':1,'total':27})
  self.assertEqual(d['controller']['action'],'REPAIR_FIRST_RED')
 def test_zero_mutation_guard(self):
  d=json.loads((ROOT/'data/STOP_MODEL_NPLUS2.json').read_text(encoding='utf-8'))
  self.assertIsNone(d['pulses'][0]['metrics']['comparable_new_branches_covered'])
  self.assertEqual(d['first_red_current_head'][0]['source_sha'],d['current_main_sha'])
 def test_hosted_claim_is_not_promoted_by_static_generator(self):
  m=json.loads((ROOT/'site/burndown-manifest.json').read_text(encoding='utf-8'))
  self.assertIsNone(m['hosted_sha'])
  self.assertEqual(m['publisher'],'EXISTING_METHOD_ATLAS_PAGES_ONLY')
  self.assertEqual(m['merge_admission'],'HOLD')
 def test_n2_portal_immutable_source_copy(self):
  with tempfile.TemporaryDirectory() as t:
   h={};r=bridge.stage_jade(ROOT,t,h,'a'*40)
   self.assertEqual(r['burndown_assets_in_pages'],7)
   self.assertEqual(len(h),27)
   self.assertEqual(h['jade/burndown-manifest.json'],bridge.sha256(ROOT/'site/burndown-manifest.json'))
 def test_n2_changed_source_rejected(self):
  import shutil
  with tempfile.TemporaryDirectory() as t:
   proj=Path(t)/'p';shutil.copytree(ROOT/'site',proj/'site')
   (proj/'data').mkdir()
   for k in ('REPO_READINESS_NPLUS1.json','COHORT_CROSSWALK_NPLUS1.json','GLOBAL_METRICS_NPLUS1.json','READBACK_NPLUS2.json','EVIDENCE_EVENTS_NPLUS2.json','STOP_MODEL_NPLUS2.json'):
    shutil.copyfile(ROOT/'data'/k,proj/'data'/k)
   (proj/'data/STOP_MODEL_NPLUS2.json').write_text('{}',encoding='utf-8',newline="\n")
   with self.assertRaisesRegex(ValueError,'JADE_N2_SOURCE_DIGEST_DRIFT'):
    bridge.stage_jade(proj,Path(t)/'out',{},'a'*40)
 def test_n2_static_not_partial(self):
  import shutil
  with tempfile.TemporaryDirectory() as t:
   proj=Path(t)/'p';shutil.copytree(ROOT/'site',proj/'site');(proj/'data').mkdir()
   for k in ('REPO_READINESS_NPLUS1.json','COHORT_CROSSWALK_NPLUS1.json','GLOBAL_METRICS_NPLUS1.json','READBACK_NPLUS2.json','EVIDENCE_EVENTS_NPLUS2.json','STOP_MODEL_NPLUS2.json'):
    shutil.copyfile(ROOT/'data'/k,proj/'data'/k)
   (proj/'site/burndown.js').unlink()
   with self.assertRaisesRegex(ValueError,'JADE_N2_PARTIAL_SITE'):
    bridge.stage_jade(proj,Path(t)/'out',{},'a'*40)
 def test_n2_false_authority_rejected(self):
  import shutil
  with tempfile.TemporaryDirectory() as t:
   proj=Path(t)/'p';shutil.copytree(ROOT/'site',proj/'site');(proj/'data').mkdir()
   for k in ('REPO_READINESS_NPLUS1.json','COHORT_CROSSWALK_NPLUS1.json','GLOBAL_METRICS_NPLUS1.json','READBACK_NPLUS2.json','EVIDENCE_EVENTS_NPLUS2.json','STOP_MODEL_NPLUS2.json'):
    shutil.copyfile(ROOT/'data'/k,proj/'data'/k)
   m=json.loads((proj/'site/burndown-manifest.json').read_text(encoding='utf-8'));m['merge_admission']='PASS'
   (proj/'site/burndown-manifest.json').write_text(json.dumps(m),encoding='utf-8',newline="\n")
   with self.assertRaisesRegex(ValueError,'JADE_N2_UNSAFE_MANIFEST'):
    bridge.stage_jade(proj,Path(t)/'out',{},'a'*40)
 def test_no_remote_js_client(self):
  t=(ROOT/'site/burndown.js').read_text(encoding='utf-8')
  for bad in ('fetch(', 'XMLHttpRequest', 'navigator.sendBeacon', 'WebSocket('):self.assertNotIn(bad,t)
 def test_all_relative_static_assets(self):
  html=(ROOT/'site/burndown.html').read_text(encoding='utf-8')
  self.assertIn('href="burndown.css"',html)
  self.assertIn('src="burndown-data.js"',html)
  self.assertIn('src="burndown.js"',html)
  self.assertIn("connect-src 'none'",html)
if __name__=='__main__':unittest.main()
