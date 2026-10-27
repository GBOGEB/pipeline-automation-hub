"""Hostile offline verification of hosted proof: origin, bytes, repeat and SHA."""
import hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('hosted',ROOT/'tools/hosted_parity.py')
hosted=importlib.util.module_from_spec(spec);spec.loader.exec_module(hosted)
spec2=importlib.util.spec_from_file_location('bridge',ROOT/'portal_bridge.py')
bridge=importlib.util.module_from_spec(spec2);spec2.loader.exec_module(bridge)
SHA='a'*40
URL='https://gbogeb.github.io/pipeline-automation-hub/'
class HostedTests(unittest.TestCase):
 def fixture(self,t):
  out=Path(t);h={};bridge.stage_jade(ROOT,out,h,SHA)
  m={'schema':'codepurple.pages.readonly/v1','source_git_sha':SHA,'merge_authorized':False,
     'qps_owner_decision':'DEFER','public_files_sha256':h}
  (out/'site-manifest.json').write_text(json.dumps(m),encoding='utf-8',newline="\n")
  return out
 def test_actual_fetcher_has_correct_redirect_boundary(self):
  from unittest.mock import patch
  class Response:
   status=200
   def __init__(self,url,body):self.url=url;self.body=body
   def __enter__(self):return self
   def __exit__(self,*args):return False
   def geturl(self):return self.url
   def read(self,n):return self.body
  with patch.object(hosted.urllib.request,'urlopen',lambda req,timeout:Response(URL+'jade/burndown.html',b'valid')):
   self.assertEqual(hosted.fetch_hosted(URL,'jade/burndown.html'),b'valid')
  with patch.object(hosted.urllib.request,'urlopen',lambda req,timeout:Response('https://evil.test/steal',b'fake')):
   with self.assertRaisesRegex(ValueError,'JADE_BAD_HOSTED_STATUS_OR_REDIRECT'):
    hosted.fetch_hosted(URL,'jade/burndown.html')
  with patch.object(hosted.urllib.request,'urlopen',lambda req,timeout:Response(URL+'jade/burndown.html',b'z'*(hosted.MAX_BYTES+1))):
   with self.assertRaisesRegex(ValueError,'JADE_HOSTED_TOO_LARGE'):
    hosted.fetch_hosted(URL,'jade/burndown.html')
 def test_same_origin_redirect_to_wrong_page_is_rejected(self):
  from unittest.mock import patch
  class Response:
   status=200
   def __enter__(self):return self
   def __exit__(self,*args):return False
   def geturl(self):return URL+'jade/green.html'
   def read(self,n):return b'plausible-body'
  with patch.object(hosted.urllib.request,'urlopen',lambda req,timeout:Response()):
   with self.assertRaisesRegex(ValueError,'JADE_BAD_HOSTED_STATUS_OR_REDIRECT'):
    hosted.fetch_hosted(URL,'jade/burndown.html')
 def test_same_origin_redirect_with_query_is_rejected(self):
  from unittest.mock import patch
  class Response:
   status=200
   def __enter__(self):return self
   def __exit__(self,*args):return False
   def geturl(self):return URL+'jade/burndown.html?unexpected=1'
   def read(self,n):return b'plausible-body'
  with patch.object(hosted.urllib.request,'urlopen',lambda req,timeout:Response()):
   with self.assertRaisesRegex(ValueError,'JADE_BAD_HOSTED_STATUS_OR_REDIRECT'):
    hosted.fetch_hosted(URL,'jade/burndown.html')
 def test_unknown_asset_name_denied_before_get(self):
  with self.assertRaisesRegex(ValueError,'JADE_INVALID_RELATIVE_ASSET'):
   hosted.fetch_hosted(URL,'jade/../../secret')
 def test_transient_readback_cache_retry_is_bounded(self):
  with tempfile.TemporaryDirectory() as t:
   out=self.fixture(t);seen={}
   def fetch(url,rel):
    seen[rel]=seen.get(rel,0)+1
    if rel=='jade/burndown.html' and seen[rel]==1:return b'stale CDN asset'
    return (out/rel).read_bytes()
   r=hosted.verify(out,URL,SHA,repeat=2,attempts=2,wait=0,fetcher=fetch)
   self.assertEqual([o['attempt'] for o in r['observations']],[2,1])
 def test_hosted_cli_emits_readonly_receipt(self):
  import sys
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as t:
   out=self.fixture(t);target=Path(t)/'receipt.json'
   with patch.object(hosted,'verify',return_value={'schema':'jade.temple.hosted_parity.v2','head':SHA,'members_verified':23,'status':'PASS','observations':[{},{}]}),patch.object(sys,'argv',['hosted_parity.py','--expected-dir',str(out),'--base-url',URL,'--head',SHA,'--receipt',str(target)]):
    hosted.main()
   self.assertTrue(target.is_file())
 def test_missing_static_asset_denied_before_hosted_get(self):
  with tempfile.TemporaryDirectory() as t:
   out=self.fixture(t);(out/'jade/burndown.html').unlink()
   with self.assertRaisesRegex(ValueError,'JADE_PUBLISHER_LOCAL_DIGEST_DRIFT'):hosted.trusted_files(out,SHA)
 def test_independent_hosted_two_rounds(self):
  with tempfile.TemporaryDirectory() as t:
   out=self.fixture(t);calls=[]
   def fetch(url,rel):calls.append(rel);return (out/rel).read_bytes()
   r=hosted.verify(out,URL,SHA,repeat=2,attempts=1,wait=0,fetcher=fetch)
   self.assertEqual(r['members_verified'],27)
   self.assertEqual(len(r['observations']),2)
   self.assertEqual(len(calls),54)
   self.assertEqual(r['merge_admission'],'HOLD')
   self.assertIsNone(r['engineering_acceptance'])
 def test_mutated_hosted_asset_fails(self):
  with tempfile.TemporaryDirectory() as t:
   out=self.fixture(t)
   def fetch(url,rel):return b'poison' if rel=='jade/burndown.js' else (out/rel).read_bytes()
   with self.assertRaisesRegex(ValueError,'JADE_HOSTED_SHA_MISMATCH'):
    hosted.verify(out,URL,SHA,repeat=2,attempts=1,wait=0,fetcher=fetch)
 def test_missing_hosted_asset_fails(self):
  with tempfile.TemporaryDirectory() as t:
   out=self.fixture(t)
   def fetch(url,rel):return (out/rel).read_bytes() if rel!='jade/green.html' else Path('/__unreachable__').read_bytes()
   with self.assertRaisesRegex(ValueError,'JADE_HOSTED_SHA_MISMATCH'):
    hosted.verify(out,URL,SHA,repeat=2,attempts=1,wait=0,fetcher=fetch)
 def test_origin_must_be_correct(self):
  for url in ['http://gbogeb.github.io/pipeline-automation-hub/','https://evil.test/path/',
              'https://gbogeb.github.io.evil.test/pipeline-automation-hub/',
              'https://gbogeb.github.io/pipeline-automation-hub/../private',
              'https://gbogeb.github.io/pipeline-automation-hub/?token=abc']:
   with self.assertRaisesRegex(ValueError,'JADE_HOSTED_REFUSE_NONCANONICAL_ORIGIN'):
    hosted.base_url(url)
 def test_bad_source_sha_fails(self):
  with tempfile.TemporaryDirectory() as t:
   out=self.fixture(t)
   with self.assertRaisesRegex(ValueError,'JADE_BAD_SOURCE_SHA'):
    hosted.trusted_files(out,'bad')
 def test_changed_exact_main_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   out=self.fixture(t)
   with self.assertRaisesRegex(ValueError,'JADE_PUBLISHER_HEAD_OR_AUTHORITY'):
    hosted.trusted_files(out,'b'*40)
 def test_fake_waiver_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   out=self.fixture(t);p=out/'site-manifest.json';m=json.loads(p.read_text(encoding='utf-8'));m['merge_authorized']=True;p.write_text(json.dumps(m),encoding='utf-8',newline="\n")
   with self.assertRaisesRegex(ValueError,'JADE_PUBLISHER_HEAD_OR_AUTHORITY'):hosted.trusted_files(out,SHA)
 def test_untracked_asset_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   out=self.fixture(t);p=out/'site-manifest.json';m=json.loads(p.read_text(encoding='utf-8'));m['public_files_sha256']['jade/evil.js']='0'*64;p.write_text(json.dumps(m),encoding='utf-8',newline="\n")
   with self.assertRaisesRegex(ValueError,'JADE_PUBLISHER_POPULATION_DRIFT'):hosted.trusted_files(out,SHA)
 def test_bad_burndown_manifest_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   out=self.fixture(t);p=out/'jade/burndown-manifest.json';m=json.loads(p.read_text(encoding='utf-8'));m['hosted_sha']=SHA;p.write_text(json.dumps(m),encoding='utf-8',newline="\n")
   top=out/'site-manifest.json';d=json.loads(top.read_text(encoding='utf-8'));d['public_files_sha256']['jade/burndown-manifest.json']=hosted.digest(p.read_bytes());top.write_text(json.dumps(d),encoding='utf-8',newline="\n")
   with self.assertRaisesRegex(ValueError,'JADE_BURNDOWN_UNSAFE_CLAIM'):hosted.trusted_files(out,SHA)
 def test_eightpoint_fake_hosted_claim_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   out=self.fixture(t);p=out/'jade/eightpoint-manifest.json';m=json.loads(p.read_text(encoding='utf-8'));m['hosted_eightpoint_sha']=SHA;p.write_text(json.dumps(m),encoding='utf-8',newline="\n")
   top=out/'site-manifest.json';d=json.loads(top.read_text(encoding='utf-8'));d['public_files_sha256']['jade/eightpoint-manifest.json']=hosted.digest(p.read_bytes());top.write_text(json.dumps(d),encoding='utf-8',newline="\n")
   with self.assertRaisesRegex(ValueError,'JADE_EIGHT_UNSAFE_HOSTED_CLAIM'):hosted.trusted_files(out,SHA)
 def test_redtrace_authority_claim_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   out=self.fixture(t);p=out/'jade/redtrace-manifest.json';m=json.loads(p.read_text(encoding='utf-8'));m['merge_authorized']=True;p.write_text(json.dumps(m),encoding='utf-8',newline="\n")
   top=out/'site-manifest.json';d=json.loads(top.read_text(encoding='utf-8'));d['public_files_sha256']['jade/redtrace-manifest.json']=hosted.digest(p.read_bytes());top.write_text(json.dumps(d),encoding='utf-8',newline="\n")
   with self.assertRaisesRegex(ValueError,'JADE_N8_UNSAFE_HOSTED_CLAIM'):hosted.trusted_files(out,SHA)
 def test_redtrace_manifest_mismatch_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   out=self.fixture(t);p=out/'jade/redtrace-manifest.json';m=json.loads(p.read_text(encoding='utf-8'));m['public_files_sha256']['redtrace.html']='0'*64;p.write_text(json.dumps(m),encoding='utf-8',newline="\n")
   top=out/'site-manifest.json';d=json.loads(top.read_text(encoding='utf-8'));d['public_files_sha256']['jade/redtrace-manifest.json']=hosted.digest(p.read_bytes());top.write_text(json.dumps(d),encoding='utf-8',newline="\n")
   with self.assertRaisesRegex(ValueError,'JADE_N8_HOSTED_MANIFEST_MISMATCH'):hosted.trusted_files(out,SHA)
 def test_redtrace_pdf_served_bytes_must_match(self):
  with tempfile.TemporaryDirectory() as t:
   out=self.fixture(t)
   def served(url,rel):
    return b'%PDF-poison' if rel=='jade/redtrace-slides.pdf' else (out/rel).read_bytes()
   with self.assertRaisesRegex(ValueError,'JADE_HOSTED_SHA_MISMATCH'):
    hosted.verify(out,URL,SHA,repeat=2,attempts=1,wait=0,fetcher=served)
 def test_eightpoint_asset_corruption_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   out=self.fixture(t)
   def served(url,rel):
    return b'poison' if rel=='jade/eightpoint.js' else (out/rel).read_bytes()
   with self.assertRaisesRegex(ValueError,'JADE_HOSTED_SHA_MISMATCH'):
    hosted.verify(out,URL,SHA,repeat=2,attempts=1,wait=0,fetcher=served)
 def test_bounded_repeat_policy(self):
  with tempfile.TemporaryDirectory() as t:
   out=self.fixture(t)
   with self.assertRaisesRegex(ValueError,'JADE_BOUNDED_RETRY_CONTRACT'):
    hosted.verify(out,URL,SHA,repeat=1,attempts=1,fetcher=lambda u,p:(out/p).read_bytes())
if __name__=='__main__':unittest.main()
