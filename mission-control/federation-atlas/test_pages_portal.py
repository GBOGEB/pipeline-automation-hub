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
 def test_mission_rebuild_partial_output_fails_closed(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);src=p/"atlas";src.mkdir();(src/"index.html").write_text("valid Atlas")
   target=src/"mission-rebuild";target.mkdir();(target/"index.html").write_text("<title>incomplete</title>")
   with self.assertRaisesRegex(ValueError,"partial Mission rebuild"):
    pages_portal.build(src,p/"out","a"*40)
 def test_mission_rebuild_forged_digest_fails_closed(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);src=p/"atlas";src.mkdir();(src/"index.html").write_text("valid Atlas")
   target=src/"mission-rebuild";target.mkdir()
   (target/"index.html").write_text("<title>fake</title>")
   (target/"graph.json").write_text(json.dumps({"source_sha":"a"*40,"gate":{"merge_admission":"HOLD"},"scheduler":{"dispatch_authorized":False}}))
   (target/"graph.mmd").write_text("flowchart LR\\n")
   (target/"manifest.json").write_text(json.dumps({"schema":"missioncontrol.makeover.manifest.v1","source_sha":"a"*40,"published_by":"EXISTING_METHOD_ATLAS_PAGES_ONLY","merge_admission":"HOLD","security_waiver":False,"authority_transfer":False,"files_sha256":{"index.html":"0"*64,"graph.json":"0"*64,"graph.mmd":"0"*64}}))
   with self.assertRaisesRegex(ValueError,"Mission rebuild hash mismatch"):
    pages_portal.build(src,p/"out","a"*40)
 def test_w2_requires_complete_native_plotly_pair(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);src=p/"atlas";src.mkdir();(src/"index.html").write_text("Atlas")
   w=src/"mission-rebuild";w.mkdir();(w/"evidence.json").write_text("{}")
   with self.assertRaisesRegex(ValueError,"partial W2 MissionControl evidence"):
    pages_portal.build(src,p/"out","a"*40)
 def test_w2_rejects_forged_member_hash(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);src=p/"atlas";src.mkdir();(src/"index.html").write_text("Atlas")
   w=src/"mission-rebuild";w.mkdir()
   state={"schema":"missioncontrol.makeover.w2_native_observation.v1",
          "source_head_sha":"a"*40,"governance":{"merge_admission":"HOLD"},
          "gg_math":{"native_live_pulse_receipts_ingested":0},
          "fleet":{"capacity_slots":None},
          "unknown_burndown":{"coverage":{"covered_statements":None}}}
   receipt={"schema":"missioncontrol.makeover.w2_plotly_manifest.v1",
            "source_sha":"a"*40,"publisher":"EXISTING_METHOD_ATLAS_PAGES_ONLY",
            "merge_admission":"HOLD","security_waiver":False,
            "authority_transfer":False,"gg_math_kernel_duplicated":False,
            "member_sha256":{"evidence.json":"0"*64,"evidence.html":"0"*64}}
   (w/"evidence.json").write_text(json.dumps(state))
   (w/"evidence.html").write_text("<title>forged</title>")
   (w/"evidence-manifest.json").write_text(json.dumps(receipt))
   with self.assertRaisesRegex(ValueError,"W2 evidence source hash mismatch"):
    pages_portal.build(src,p/"out","a"*40)
 def test_n3_partial_input_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);src=p/"atlas";src.mkdir();(src/"index.html").write_text("Atlas")
   n=src/"mission-rebuild";n.mkdir();(n/"n3-metrics.html").write_text("partial")
   with self.assertRaisesRegex(ValueError,"partial N3 source-bound KPI output"):
    pages_portal.build(src,p/"out","a"*40)
 def test_n3_manifest_digest_forgery_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);src=p/"atlas";src.mkdir();(src/"index.html").write_text("Atlas")
   n=src/"mission-rebuild";n.mkdir()
   state={"schema":"missioncontrol.n3.scoped_native_kpi.v1",
          "presentation_sha":"a"*40,"producer_sha":"b"*40,
          "source_repo":"GBOGEB/pipeline-automation-hub",
          "fleet_runner_capacity":None,
          "owner_required_status_gate":{"owner_installed":None},
          "authority":{"merge_admission":"HOLD","remote_dispatch":False}}
   manifest={"schema":"missioncontrol.n3.readonly_publisher_manifest.v1",
             "presentation_sha":"a"*40,"producer_sha":"b"*40,
             "publisher":"EXISTING_METHOD_ATLAS_PAGES_ONLY",
             "merge_admission":"HOLD","authority_transfer":False,
             "member_sha256":{"n3-metrics.html":"0"*64,"n3-metrics.json":"0"*64}}
   (n/"n3-metrics.json").write_text(json.dumps(state))
   (n/"n3-metrics.html").write_text("<title>forged</title>")
   (n/"n3-manifest.json").write_text(json.dumps(manifest))
   with self.assertRaisesRegex(ValueError,"N3 source member digest mismatch"):
    pages_portal.build(src,p/"out","a"*40)
if __name__=="__main__":unittest.main()
