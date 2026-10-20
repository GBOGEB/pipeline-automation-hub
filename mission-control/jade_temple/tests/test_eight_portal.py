"""Source-bound N+3 child of the ONE existing Mission Control Pages publisher."""
import importlib.util,json,shutil,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('jadebridge',ROOT/'portal_bridge.py')
bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
SHA='a'*40
class EightPortal(unittest.TestCase):
 def fixture(self,t):
  p=Path(t)/'proj'
  for name in bridge.EIGHT_REQUIRED:
   dst=p/'site'/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/'site'/name,dst)
  for name in bridge.EIGHT_SOURCES:
   dst=p/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dst)
  return p
 def test_seven_public_assets_staged(self):
  with tempfile.TemporaryDirectory() as temp:
   hash={};proof=bridge.stage_jade(ROOT,temp,hash,SHA)
   self.assertEqual(proof['eightpoint_assets_in_pages'],7)
   self.assertEqual(proof['files_in_pages'],26)
   self.assertEqual(len(hash),27)
   self.assertFalse(proof['hosted_http_verified'])
   self.assertEqual(hash['jade/eightpoint.html'],bridge.sha256(ROOT/'site/eightpoint.html'))
 def test_partial_page_population_fails(self):
  with tempfile.TemporaryDirectory() as temp:
   p=self.fixture(temp);(p/'site/eightpoint.css').unlink()
   with self.assertRaisesRegex(ValueError,'JADE_EIGHT_PARTIAL_SITE'):
    bridge.stage_eight_point(p,Path(temp)/'out',{})
 def test_poisoned_source_fails(self):
  with tempfile.TemporaryDirectory() as temp:
   p=self.fixture(temp);(p/'data/EIGHT_POINT_AUDIT_NPLUS3.json').write_text('{}')
   with self.assertRaisesRegex(ValueError,'JADE_EIGHT_SOURCE_DIGEST_DRIFT'):
    bridge.stage_eight_point(p,Path(temp)/'out',{})
 def test_poisoned_static_fails(self):
  with tempfile.TemporaryDirectory() as temp:
   p=self.fixture(temp);(p/'site/eightpoint.js').write_text('BAD')
   with self.assertRaisesRegex(ValueError,'JADE_EIGHT_STATIC_DIGEST_DRIFT'):
    bridge.stage_eight_point(p,Path(temp)/'out',{})
 def test_false_release_claim_fails(self):
  with tempfile.TemporaryDirectory() as temp:
   p=self.fixture(temp);f=p/'site/eightpoint.json';data=json.loads(f.read_text());data['merge_admission']='PASS';f.write_text(json.dumps(data))
   with self.assertRaisesRegex(ValueError,'JADE_EIGHT_UNSAFE_PROJECTION'):
    m=p/'site/eightpoint-manifest.json';x=json.loads(m.read_text());x['public_files_sha256']['eightpoint.json']=bridge.sha256(f);m.write_text(json.dumps(x))
    bridge.stage_eight_point(p,Path(temp)/'out',{})
 def test_legacy_n2_only_replay_supported(self):
  with tempfile.TemporaryDirectory() as temp:
   p=Path(temp)/'noeight';(p/'site').mkdir(parents=True)
   self.assertEqual(bridge.stage_eight_point(p,Path(temp)/'out',{}),0)
if __name__=='__main__':unittest.main()
