import copy,hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('jade_bridge',ROOT/'portal_bridge.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
HEAD='d3d450fbdbb34403e22589188a877560fb147b29'
class BridgeTest(unittest.TestCase):
 def test_stage_copy_and_manifest(self):
  with tempfile.TemporaryDirectory() as t:
   hashes={};p=mod.stage_jade(ROOT,t,hashes,HEAD)
   self.assertEqual(p['files_in_pages'],26);self.assertEqual(len(hashes),27)
   self.assertEqual(p['redtrace_assets_in_pages'],4)
   self.assertEqual(p['burndown_assets_in_pages'],7)
   self.assertEqual(p['eightpoint_assets_in_pages'],7)
   self.assertEqual(hashes['jade/eightpoint.html'],mod.sha256(ROOT/'site/eightpoint.html'))
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
   (proj/'site/jade_data.js').write_text('window.JADE_NPLUS1={};',encoding='utf-8')
   with self.assertRaisesRegex(ValueError,'JADE_STATIC_SHA256_MISMATCH'):mod.stage_jade(proj,Path(t)/'out',{},HEAD)
 def test_no_false_admission(self):
  with self.assertRaisesRegex(ValueError,'SOURCE_SHA_INVALID'):mod.stage_jade(ROOT,Path('/tmp/jade-should-not-create'),{},'bad')
 def test_nonnative_stale_head_not_promoted(self):
  with tempfile.TemporaryDirectory() as t:
   p=mod.stage_jade(ROOT,t,{},HEAD)
   self.assertIsNone(p['native_release_admission'])
   self.assertEqual(p['presentation_head'],HEAD)
 def test_all_portal_manifest_keys_are_posix(self):
  # Windows Path.__str__ uses backslashes; hosted-parity expects slash-delimited keys.
  from pathlib import PureWindowsPath
  self.assertEqual(PureWindowsPath('jade', 'green.html').as_posix(),'jade/green.html')
  with tempfile.TemporaryDirectory() as t:
   hashes={}
   mod.stage_jade(ROOT,t,hashes,HEAD)
   self.assertEqual(len(hashes),27)
   self.assertTrue(all(k.startswith('jade/') and '\\\\' not in k for k in hashes))
   self.assertEqual(hashes['jade/publisher-receipt.json'],mod.sha256(Path(t)/'jade/publisher-receipt.json'))
  source=(ROOT/'portal_bridge.py').read_text(encoding='utf-8')
  self.assertNotIn('str(dst.relative_to(output_root))',source)
  self.assertEqual(source.count('dst.relative_to(output_root).as_posix()'),5)
if __name__=='__main__':unittest.main()
