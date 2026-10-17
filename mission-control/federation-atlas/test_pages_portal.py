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
