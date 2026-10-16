import copy
import hashlib
import json
import sys
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'source'))
import live_census as c
import serve

SEED=json.loads((ROOT/'data/observed_fixture.json').read_text())
PRIOR=json.loads((ROOT/'data/prior_output/snapshot.json').read_text())

def sample():return copy.deepcopy(SEED)
class TestIdentity(unittest.TestCase):
 def test_valid_contract(self):self.assertEqual(c.build(sample())['authority']['admission'],'HOLD')
 def test_digest_stable_key_order(self):self.assertEqual(c.digest({'b':2,'a':1}),c.digest({'a':1,'b':2}))
 def test_invalid_sha_rejected(self):
  with self.assertRaisesRegex(ValueError,'SHA'):c.validate_sha('deadbeef')
 def test_repo_branch_rejected(self):
  s=sample();s['repositories'][0]['branch']='experimental'
  with self.assertRaisesRegex(ValueError,'repository'):c.build(s)
 def test_empty_census_rejected(self):
  s=sample();s['prs']=[]
  with self.assertRaisesRegex(ValueError,'empty'):c.build(s)
 def test_untrusted_source_origin_rejected(self):
  s=sample();s['mode']='TRUST_ME'
  with self.assertRaisesRegex(ValueError,'origin'):c.build(s)
 def test_duplicate_pr_rejected(self):
  s=sample();s['prs'].append(copy.deepcopy(s['prs'][0]))
  with self.assertRaisesRegex(ValueError,'duplicate'):c.build(s)
 def test_negative_ci_rejected(self):
  s=sample();s['prs'][0]['runs']={'success':-1}
  with self.assertRaisesRegex(ValueError,'negative'):c.build(s)
 def test_dangling_edge_rejected(self):
  s=c.build(sample());s['edges'].append({'from':'bad','to':'pr:ABACUS:2006','type':'CANDIDATE','admitted':False})
  with self.assertRaisesRegex(ValueError,'dangling'):c.data_identity(s)
 def test_closure_edge_rejected(self):
  s=c.build(sample());s['edges'][0]['type']='CLOSURE'
  with self.assertRaisesRegex(ValueError,'closure'):c.data_identity(s)
 def test_forced_root_closure_rejected(self):
  s=c.build(sample());s['authority']['root_closures_verified']=1
  with self.assertRaisesRegex(ValueError,'closure'):c.data_identity(s)
 def test_security_waiver_rejected(self):
  s=c.build(sample());s['authority']['security_waiver']=True
  with self.assertRaisesRegex(ValueError,'authority'):c.data_identity(s)
 def test_dispatch_promotion_rejected(self):
  s=c.build(sample());s['authority']['crew_dispatch']='RUNNING'
  with self.assertRaisesRegex(ValueError,'authority'):c.data_identity(s)
 def test_missing_native_counts_are_unknown(self):
  s=c.build(sample());p=next(p for p in s['prs'] if p['number']==2045)
  self.assertEqual(p['run_summary'],'UNKNOWN');self.assertGreater(s['metrics']['pr_status_unmeasured'],0)
 def test_historical_b9_not_promoted(self):
  m=c.build(sample())['metrics'];self.assertEqual(m['coverage_b9_historical']['covered'],253)
  self.assertIsNone(m['last_native_main_coverage'])
 def test_intermediate_merge_not_main(self):
  p=next(p for p in c.build(sample())['prs'] if p['number']==2060)
  self.assertEqual(p['disposition'],'MERGED_INTERMEDIATE_NOT_MAIN')
 def test_main_merge_not_accepted_automatically(self):
  s=sample();s['prs'][0]['merged']=True;s['prs'][0]['state']='closed';p=c.build(s)['prs'][0]
  self.assertEqual(p['disposition'],'MERGED_MAIN_UNVERIFIED')
 def test_event_head_invalidation(self):
  events=c.build(sample(),PRIOR)['events'];lookup={(x['kind'],x['id']) for x in events}
  self.assertIn(('PR_SOURCE_CHANGED',2033),lookup)
  self.assertIn(('REPO_HEAD_CHANGED','CODEX'),lookup)
 def test_intermediate_merge_transition(self):
  e=c.build(sample(),PRIOR)['events'];self.assertTrue(any(x['kind']=='PR_DISPOSITION_CHANGED' and x['id']==2060 for x in e))
 def test_no_new_event_same_data(self):
  same=c.build(sample());self.assertEqual(c.build(sample(),same)['events'],[])
 def test_root_candidate_not_closure(self):
  s=c.build(sample());self.assertEqual(s['metrics']['candidate_roots'],len(c.ROOTS));self.assertIsNone(s['metrics']['accepted_closed_roots'])
  self.assertTrue(all(not e['admitted'] for e in s['edges']))
 def test_associated_runs_not_exact_checkout(self):
  p=next(x for x in c.build(sample())['prs'] if x['number']==2059)
  self.assertEqual(p['evidence_level'],'PR_ASSOCIATED_NOT_CHECKOUT_ATTESTED')
 def test_status_negative_controls(self):
  self.assertEqual(c.status({'success':3,'failure':1}),'FAIL')
  self.assertEqual(c.status({'success':3,'queued':1}),'PENDING')
  self.assertEqual(c.status({'success':3}),'PARTIAL_SUCCESS')
  self.assertEqual(c.status({'cancelled':1}),'CANCELLED')
  self.assertEqual(c.status({}),'UNKNOWN')
 def test_github_path_restrictions(self):
  g=c.GitHubReadOnly(token='TEST')
  for bad in ('https://evil.local','/repos/GBOGEB/../secret','/repos/GBOGEB/ABACUS/../../secret'):
   with self.assertRaises(ValueError):g.get(bad)
 def test_missing_native_workflow_list_rejected(self):
  class Reader:
   def get(self,p):
    if '/commits/' in p:return {'sha':'a'*40}
    if '/pulls/' in p:return {'head':{'sha':'a'*40,'ref':'x'},'base':{'sha':'b'*40,'ref':'main'},'state':'open','merged':False}
    return {'workflow_runs':None}
  with self.assertRaisesRegex(ValueError,'runs missing'):c.acquire(Reader())
 def test_native_acquisition(self):
  class Reader:
   def get(self,p):
    if '/commits/' in p:return {'sha':'a'*40}
    if '/pulls/' in p:return {'head':{'sha':'a'*40,'ref':'feature'},'base':{'sha':'b'*40,'ref':'main'},'state':'open','merged':False}
    return {'workflow_runs':[{'id':5,'name':'Native B9','conclusion':'failure','head_sha':'a'*40}]}
  s=c.acquire(Reader());self.assertEqual(len(s['repositories']),5);self.assertEqual(len(s['prs']),len(c.WATCH))
  self.assertEqual(s['prs'][0]['runs']['failure'],1)
 def test_negative_run_id_rejected(self):
  s=sample();s['prs'][0]['native_runs']=[{'id':-1}]
  with self.assertRaisesRegex(ValueError,'run id'):c.build(s)
class TestFiles(unittest.TestCase):
 def test_roundtrip_hashes(self):
  with tempfile.TemporaryDirectory() as t:
   s=c.build(sample());m=c.write_outputs(s,Path(t));self.assertEqual(len(m['files_sha256']),5)
   for name,h in m['files_sha256'].items():self.assertEqual(hashlib.sha256((Path(t)/name).read_bytes()).hexdigest(),h)
 def test_tamper_detection(self):
  with tempfile.TemporaryDirectory() as t:
   c.write_outputs(c.build(sample()),Path(t));(Path(t)/'snapshot.json').write_text('tamper')
   with self.assertRaisesRegex(ValueError,'digest mismatch'):c.cli(['--verify',t])
 def test_input_seed_cli(self):
  with tempfile.TemporaryDirectory() as t:
   c.cli(['--seed',str(ROOT/'data/observed_fixture.json'),'--out',t])
   self.assertTrue((Path(t)/'nodes.json').is_file())
class TestServer(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.server=serve.Server(('127.0.0.1',0),serve.Handler,ROOT/'output',ROOT/'view')
  cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
 @classmethod
 def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join(timeout=3)
 def req(self,path):
  conn=HTTPConnection('127.0.0.1',self.server.server_port,timeout=4);conn.request('GET',path)
  r=conn.getresponse();ret=(r.status,dict(r.getheaders()),r.read());conn.close();return ret
 def test_healthz(self):
  code,h,b=self.req('/healthz');self.assertEqual(code,200);self.assertFalse(json.loads(b)['github_mutations_enabled'])
 def test_metrics_does_not_invent_root_zero(self):
  code,h,b=self.req('/metrics');self.assertEqual(code,200);self.assertIn(b'codepurple_census_nodes',b)
  self.assertNotIn(b'codepurple_roots_closed 0',b)
 def test_snapshot_endpoint(self):
  code,h,b=self.req('/api/v1/snapshot');self.assertEqual(code,200);self.assertEqual(json.loads(b)['authority']['admission'],'HOLD')
 def test_graph_endpoints(self):
  for path in ('/api/v1/nodes','/api/v1/edges','/api/v1/diagnostics','/api/v1/events'):
   code,h,b=self.req(path);self.assertEqual(code,200,path)
 def test_static_page_and_csp(self):
  code,h,b=self.req('/');self.assertEqual(code,200);self.assertIn(b'Disjoint Census &amp; Diagnostics',b)
  self.assertIn("default-src 'none'",h['Content-Security-Policy'])
 def test_static_js(self):
  code,h,b=self.req('/app.js');self.assertEqual(code,200);self.assertIn(b'root_closures_verified',b)
 def test_route_allowlist(self):
  for route in ('/does-not-exist','/../../etc/passwd','/api/v1/close-root'):
   code,h,b=self.req(route);self.assertEqual(code,404)
 def test_event_stream_has_no_authority(self):
  conn=HTTPConnection('127.0.0.1',self.server.server_port,timeout=4);conn.request('GET','/api/v1/stream')
  r=conn.getresponse();self.assertEqual(r.status,200);self.assertEqual(r.headers['Content-Type'],'text/event-stream')
  chunk=r.read(32);self.assertIn(b'event: census',chunk);conn.close()
if __name__=='__main__':unittest.main()
