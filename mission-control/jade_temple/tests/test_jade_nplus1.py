"""Focused negative/positive controls; do not infer governance or release readiness."""
import copy, hashlib, importlib.util, json, re, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data';SITE=ROOT/'site'
spec=importlib.util.spec_from_file_location('jade_green',SITE/'build_green.py');jade=importlib.util.module_from_spec(spec);spec.loader.exec_module(jade)
class J1ContractTests(unittest.TestCase):
 def setup(self):pass
 def load(self,name):return json.loads((DATA/name).read_text())
 def test_population_and_exact_ids(self):
  d=self.load('REPO_READINESS_NPLUS1.json');r=d['rows'];self.assertEqual(len(r),21);self.assertEqual(len({x['repo'] for x in r}),21)
  self.assertTrue(all(re.fullmatch(r'[0-9a-f]{40}',x['head_readback']) for x in r))
 def test_census_not_live_coverage(self):
  m=self.load('GLOBAL_METRICS_NPLUS1.json');self.assertIsNone(m['kpis']['eligible_exact_head_release_ci']);self.assertIsNone(m['kpis']['governed_point_releases']);self.assertEqual(m['release_admission'],'HOLD')
 def test_no_fabricated_pages_qualifications(self):
  d=self.load('REPO_READINESS_NPLUS1.json');self.assertEqual(sum(x['site']['successful_dynamic_pages_workflow_observed'] for x in d['rows']),3)
  self.assertTrue(all(x['site']['served_http_url'] is None and x['site']['served_sha'] is None for x in d['rows']))
 def test_n11_and_green_not_conflated(self):
  cross=self.load('COHORT_CROSSWALK_NPLUS1.json');self.assertEqual((cross['intersection_count'],len(cross['n11_only']),len(cross['green_only'])),(13,8,8));self.assertIsNone(cross['owner_approved_single_cohort'])
 def test_current_telemetry_bounded(self):
  rs=self.load('REPO_READINESS_NPLUS1.json')['rows'];self.assertEqual(sum(x['recent_branch_query_returned_no_runs'] for x in rs),8)
  for r in rs:
   self.assertLessEqual(len(r['observed_recent_branch_runs']),2)
   self.assertEqual(r['readiness']['point_release'],'UNQUALIFIED')
 def test_foreign_run_must_not_equal_main(self):
  rs=self.load('REPO_READINESS_NPLUS1.json')['rows'];r=next(x for x in rs if x['repo'].endswith('/github_documentorganisatiesysteem_GBOGEB'))
  self.assertFalse(r['observed_recent_branch_runs'][0]['head_matches_default'])
 def test_priority_denominator(self):
  rs=self.load('REPO_READINESS_NPLUS1.json')['rows'];self.assertEqual([sum(x['priority']==p for x in rs) for p in ['P0','P1','P2']],[5,9,7])
 def test_static_urls_relative_and_https_only(self):
  t=(SITE/'green_template.html').read_text();self.assertNotIn('http://',t);self.assertIn('href="index.html"',t)
 def test_site_js_has_no_network_client(self):
  j=(SITE/'jade.js').read_text();self.assertNotRegex(j,r'(?<![A-Za-z])fetch\s*\(');self.assertNotRegex(j,r'XMLHttpRequest\s*\(')
 def test_static_build_byte_replay(self):
  for name,b in jade.build().items():self.assertEqual((SITE/name).read_bytes(),b,name)
 def test_public_hash_manifest_complete(self):
  m=json.loads((SITE/'site-manifest.json').read_text());self.assertEqual(m['publisher'],'EXISTING_METHOD_ATLAS_PAGES_ONLY')
  for path,h in m['public_files_sha256'].items():self.assertEqual(hashlib.sha256((SITE/path).read_bytes()).hexdigest(),h,path)
  for path,h in m['source_files_sha256'].items():self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),h,path)
 def test_authority_injection_rejected(self):
  origin=jade.read
  def patched(name):
   d=copy.deepcopy(origin(name))
   if name=='REPO_READINESS_NPLUS1.json':d['admission']='ADMITTED'
   return d
  jade.read=patched
  try:
   with self.assertRaises(AssertionError):jade.build()
  finally:jade.read=origin
 def test_cohort_population_tamper_rejected(self):
  origin=jade.read
  def patched(name):
   d=copy.deepcopy(origin(name))
   if name=='COHORT_CROSSWALK_NPLUS1.json':d['n11_only'].pop()
   return d
  jade.read=patched
  try:
   with self.assertRaises(AssertionError):jade.build()
  finally:jade.read=origin
 def test_hosted_proof_fabrication_rejected(self):
  origin=jade.read
  def patched(name):
   d=copy.deepcopy(origin(name))
   if name=='REPO_READINESS_NPLUS1.json':d['rows'][0]['site']['served_http_url']='https://invalid.example/'
   return d
  jade.read=patched
  try:
   with self.assertRaises(AssertionError):jade.build()
  finally:jade.read=origin
 def test_frozen_baseline_integrity(self):
  old=self.load('TOP21_PORTFOLIO.json');self.assertEqual(len(old['repositories']),21)
  self.assertEqual(sum(x['n11_historical']['root_review_candidates'] for x in old['repositories']),706)
  self.assertEqual(sum(x['n11_historical']['files'] for x in old['repositories']),26836)
 def test_output_does_not_weaken_green_census(self):
  m=self.load('GLOBAL_METRICS_NPLUS1.json')['kpis']['historical_gogreen_sample_prs'];self.assertEqual((m['sampled_prs'],m['check_ids'],m['failed_check_manifestations']),(41,509,33))
 def test_no_release_score_auto_100(self):
  text=(SITE/'green.html').read_text();self.assertIn('MERGE ADMISSION: HOLD',text);self.assertIn('UNKNOWN',text);self.assertNotIn('J5 · RELEASED · 21/21',text)
 def test_bootstrap_and_green_are_linked(self):
  self.assertIn('href="green.html"',(SITE/'index.html').read_text())
 def test_no_separate_pages_workflow_or_authority(self):
  m=self.load('REPO_READINESS_NPLUS1.json');self.assertFalse(m['authority_transfer'])
  self.assertTrue(all(x['merge_admission']=='HOLD' for x in m['rows']))
 def test_manifest_marks_local_only(self):
  m=json.loads((SITE/'site-manifest.json').read_text());self.assertEqual(m['evidence_level'],'LOCAL_REPRODUCIBILITY');self.assertIsNone(m['hosted_parity_receipt'])
if __name__=='__main__':unittest.main()
