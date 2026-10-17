"""N13 native source-access negative controls; offline."""
import io,json,sys,tempfile,unittest,urllib.error,urllib.request
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'source'))
from source_access import SourceAccessError,read_json,write_diagnostic
R='/repos/GBOGEB/cryoplant-project/commits/main'
class SourceAccessTests(unittest.TestCase):
 def test_success(self):
  v=read_json(urllib.request.Request('https://api.github.com'+R),R,opener=lambda *_a,**_k:io.BytesIO(b'{"sha":"'+b'a'*40+b'"}'))
  self.assertEqual(v['sha'],'a'*40)
 def test_visibility_unknown(self):
  for code in (401,403,404):
   with self.subTest(code=code):
    def fail(*_a,**_k):raise urllib.error.HTTPError('https://api.github.com',code,'Not Found',None,None)
    with self.assertRaises(SourceAccessError) as caught:
     read_json(urllib.request.Request('https://api.github.com'+R),R,opener=fail)
    d=caught.exception.diagnostic()
    self.assertIsNone(d['source_present'])
    self.assertIsNone(d['source_access_authorized'])
    self.assertFalse(d['fresh_census_generated'])
 def test_rate_limit(self):
  self.assertEqual(SourceAccessError(R,429).diagnostic()['classification'],'SOURCE_RATE_LIMIT_UNKNOWN')
 def test_transport_unknown(self):
  def fail(*_a,**_k):raise urllib.error.URLError('offline')
  with self.assertRaises(SourceAccessError):read_json(urllib.request.Request('https://api.github.com'+R),R,opener=fail)
 def test_no_secret_leak_and_durable_receipt(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);(root/'snapshot.json').write_text('historical')
   p=write_diagnostic(SourceAccessError(R,404),root)
   self.assertEqual((root/'snapshot.json').read_text(),'historical')
   d=json.loads(p.read_text())
   self.assertEqual(d['repository'],'cryoplant-project')
   self.assertFalse(d['merge_authorized'])
   self.assertIsNone(d['accepted_causal_root_closures'])
   self.assertNotIn('Authorization',p.read_text())
if __name__=='__main__':unittest.main()
