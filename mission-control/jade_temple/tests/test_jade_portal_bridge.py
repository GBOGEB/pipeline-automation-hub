import copy,hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('jade_bridge',ROOT/'portal_bridge.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
HEAD='d3d450fbdbb34403e22589188a877560fb147b29'
class BridgeTest(unittest.TestCase):
 def test_stage_copy_and_manifest(self):
  with tempfile.TemporaryDirectory() as t:
   hashes={};p=mod.stage_jade(ROOT,t,hashes,HEAD)
   self.assertEqual(p['files_in_pages'],15);self.assertEqual(len(hashes),16)
   self.assertEqual(p['burndown_assets_in_pages'],7)
   self.assertEqual(hashes['jade/burndown.html'],mod.sha256(ROOT/'site/burndown.html'))
   self.assertEqual(hashes['jade/green.html'],mod.sha256(ROOT/'site/green.html'))
   self.assertFalse(p['hosted_http_verified'])
 def test_tampered_static_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   # Mirrors site bytes to a staging root then changes the advertised data JS;
   # negative test must reject before copying promoted output.
   proj=Path(t)/'proj';(proj/'site').mkdir(parents=True);(proj/'data').mkdir()
   import shutil
   for name in mod.STATIC_REQUIRED|{'jade.css','jade.js'}:shutil.copyfile(ROOT/'site'/name,proj/'site'/name)
   for name in ['REPO_READINESS_NPLUS1.json','COHORT_CROSSWALK_NPLUS1.json','GLOBAL_METRICS_NPLUS1.json']:shutil.copyfile(ROOT/'data'/name,proj/'data'/name)
   (proj/'site/jade_data.js').write_text('window.JADE_NPLUS1={};')
   with self.assertRaisesRegex(ValueError,'JADE_STATIC_SHA256_MISMATCH'):mod.stage_jade(proj,Path(t)/'out',{},HEAD)
 def test_no_false_admission(self):
  with self.assertRaisesRegex(ValueError,'SOURCE_SHA_INVALID'):mod.stage_jade(ROOT,Path('/tmp/jade-should-not-create'),{},'bad')
 def test_nonnative_stale_head_not_promoted(self):
  with tempfile.TemporaryDirectory() as t:
   p=mod.stage_jade(ROOT,t,{},HEAD)
   self.assertIsNone(p['native_release_admission'])
   self.assertEqual(p['presentation_head'],HEAD)
if __name__=='__main__':unittest.main()
