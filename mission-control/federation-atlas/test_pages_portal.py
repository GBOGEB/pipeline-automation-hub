import tempfile,unittest,json
from pathlib import Path
import pages_portal
class TestPages(unittest.TestCase):
 def test_generate_sanitized(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);src=p/"atlas";src.mkdir();(src/"index.html").write_text("<html>Atlas</html>")
   (src/"lane-process.mmd").write_text("flowchart LR\n A-->B")
   (src/"secret.txt").write_text("SECRET")
   m=pages_portal.build(src,p/"out","a"*40)
   self.assertEqual(m["qps_owner_decision"],"DEFER")
   self.assertNotIn("secret.txt",str(m))
   self.assertTrue((p/"out"/"index.html").is_file())
   self.assertTrue((p/"out"/"atlas"/"lane-process.mmd").is_file())
 def test_missioncontrol_launch_is_in_existing_publisher(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);src=p/"atlas";src.mkdir()
   (src/"index.html").write_text("<title>source atlas</title>")
   m=pages_portal.build(src,p/"published","a"*40)
   dst=p/"published"/"missioncontrol"
   self.assertTrue((dst/"index.html").is_file())
   self.assertTrue((dst/"federation.mmd").is_file())
   self.assertTrue((dst/"SIPOC.md").is_file())
   self.assertTrue((dst/"snapshot.json").is_file())
   self.assertTrue((dst/"manifest.json").is_file())
   nav=json.loads((dst/"manifest.json").read_text())
   self.assertEqual(nav["publisher"],"EXISTING_ATLAS_PAGES_ONLY")
   self.assertEqual(nav["merge_admission"],"HOLD")
   self.assertIsNone(nav["native_qa"])
   self.assertFalse(nav["hosted_http_verified"])
   self.assertEqual(nav["source_head_sha"],"a"*40)
   for name,expected in nav["files_sha256"].items():
    import hashlib
    self.assertEqual(hashlib.sha256((dst/name).read_bytes()).hexdigest(),expected)
    self.assertEqual(m["public_files_sha256"]["missioncontrol/"+name],expected)
   home=(p/"published"/"index.html").read_text()
   self.assertIn('href="missioncontrol/index.html"',home)
   self.assertIn("six-panel federation navigator",home)
   atom=json.loads((dst/"GRAPH_ATOMS_W1_v1.json").read_text())
   self.assertEqual(atom["metrics"]["all_atoms"],32)
   self.assertEqual((atom["metrics"]["node_atoms"],atom["metrics"]["relation_atoms"]),(13,19))
   self.assertIsNone(atom["metrics"]["eligible_causal_roots"])
   self.assertEqual(len(atom["atoms"]),32)
   self.assertIn("missioncontrol/GRAPH_ATOMS_W1_v1.json",m["public_files_sha256"])
   self.assertFalse(m["merge_authorized"])
 def test_bad_sha(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);p.joinpath("index.html").write_text("x")
   with self.assertRaises(ValueError):pages_portal.build(p,p/"out","BAD")
 def test_gg_math_provider_not_fake_hosted(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);src=p/"atlas";src.mkdir();(src/"index.html").write_text("<title>Test Atlas</title>")
   m=pages_portal.build(src,p/"out","a"*40)
   body=(p/"out"/"index.html").read_text()
   self.assertIn("gg_MATH · Convergence Plotly source",body)
   self.assertIn("native/Pages verification pending",body)
   self.assertIn("https://github.com/GBOGEB/gg_MATH/blob/",body)
   self.assertFalse((p/"out"/"gg-math"/"index.html").exists())
   self.assertFalse(m["merge_authorized"])
if __name__=="__main__":unittest.main()
