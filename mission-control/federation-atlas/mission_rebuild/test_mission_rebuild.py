import copy, hashlib, tempfile, unittest
from pathlib import Path
import build
class Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  a=build.ATLAS
  cls.l,_=build.read(a/"PROCESS_LANES_v1.json")
  cls.b,_=build.read(a/"CODE_PURPLE_BEAMS_DAG_v1.json")
  cls.w,_=build.read(a.parent/"gogreen/samples/sipoc_instance_wave_20261016.json")
 def model(self,l=None,b=None,w=None,sha="a"*40):
  return build.project(l if l is not None else self.l,b if b is not None else self.b,w if w is not None else self.w,sha,{})
 def test_counts_and_holds(self):
  m=self.model()
  self.assertEqual((m["population"]["repositories"],m["population"]["lanes"],m["population"]["process_atoms"]),(5,10,39))
  self.assertEqual(len(m["nodes"]),m["population"]["nodes"])
  self.assertTrue(all(e["temporal"]=="NEXT_PULSE" for e in m["edges"] if e["kind"]=="FEEDBACK"))
  self.assertFalse(m["scheduler"]["dispatch_authorized"])
  self.assertIsNone(m["scheduler"]["actual_worker_capacity"])
  self.assertIsNone(m["gate"]["qps_acceptance"])
 def test_reproducible_manifest(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);w=build.ATLAS.parent/"gogreen/samples/sipoc_instance_wave_20261016.json"
   x=build.build(build.ATLAS,p,"a"*40,w);y=build.build(build.ATLAS,p,"a"*40,w)
   self.assertEqual(x,y)
   for n,h in x["files_sha256"].items():self.assertEqual(hashlib.sha256((p/n).read_bytes()).hexdigest(),h)
   self.assertNotIn("__GRAPH_DATA__",(p/"index.html").read_text())
 def test_bad_sha(self):
  with self.assertRaisesRegex(ValueError,"exact checkout"):self.model(sha="fake")
 def test_authority_forgery(self):
  w=copy.deepcopy(self.w);w["dispatch_authorized"]=True
  with self.assertRaisesRegex(ValueError,"planner control"):self.model(w=w)
 def test_bad_edge(self):
  b=copy.deepcopy(self.b);b["edges"].append({"from":"B999","to":"B1","type":"FEEDFORWARD"})
  with self.assertRaisesRegex(ValueError,"beam dependency"):self.model(b=b)
 def test_cycle(self):
  b=copy.deepcopy(self.b);b["edges"].append({"from":"B1","to":"B1","type":"FEEDFORWARD"})
  with self.assertRaisesRegex(ValueError,"same-pulse beam cycle"):self.model(b=b)
 def test_stage_drift(self):
  l=copy.deepcopy(self.l);l["lanes"][0]["stages"].pop()
  with self.assertRaisesRegex(ValueError,"population drift"):self.model(l=l)
 def test_sipoc_drift(self):
  l=copy.deepcopy(self.l);l["sipoc"][0]["key"]="X"
  with self.assertRaisesRegex(ValueError,"SIPOC source"):self.model(l=l)
if __name__=="__main__":unittest.main()
