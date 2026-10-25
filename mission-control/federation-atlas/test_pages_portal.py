import tempfile,unittest,json,hashlib
from pathlib import Path
from unittest import mock
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
 def test_j03_linked_atlas_children_are_published(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);src=p/"atlas";(src/"flightdeck").mkdir(parents=True)
   (src/"index.html").write_text("<html>Atlas</html>")
   for n in ("federation-wave.html","phase02-temporal.html","phase02-temporal.json"):
    (src/n).write_text("x")
   for n in ("GUIDE.md","evidence_register.xlsx","federation_report.docx","mission_brief.pptx","linked_evidence_book.pdf"):
    (src/"flightdeck"/n).write_text("x")
   pages_portal.build(src,p/"out","a"*40)
   a=p/"out"/"atlas"
   for n in ("federation-wave.html","phase02-temporal.html","phase02-temporal.json","flightdeck/GUIDE.md"):
    self.assertTrue((a/n).is_file(),n)
   for n in ("evidence_register.xlsx","federation_report.docx","mission_brief.pptx","linked_evidence_book.pdf"):
    self.assertFalse((a/"flightdeck"/n).exists(),n)
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
 def test_convergence_hub_existing_publisher_entrypoint(self):
  import convergence_hub
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);src=p/"atlas";src.mkdir();(src/"index.html").write_text("<title>Atlas</title>")
   convergence_hub.build(convergence_hub.HERE/convergence_hub.SOURCE_NAME,
                         src/"convergence","a"*40)
   m=pages_portal.build(src,p/"pages","a"*40)
   self.assertTrue((p/"pages"/"convergence"/"index.html").is_file())
   self.assertTrue((p/"pages"/"convergence"/"ledger.json").is_file())
   self.assertIn("GLOBAL DoV", (p/"pages"/"index.html").read_text())
   self.assertIn("convergence/index.html",m["public_files_sha256"])
 def test_convergence_hub_partial_is_fatal(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);src=p/"atlas";src.mkdir();(src/"index.html").write_text("Atlas")
   c=src/"convergence";c.mkdir();(c/"index.html").write_text("incomplete")
   with self.assertRaisesRegex(ValueError,"partial Convergence Hub"):
    pages_portal.build(src,p/"pages","a"*40)
 def test_convergence_hub_tampered_byte_is_fatal(self):
  import convergence_hub
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);src=p/"atlas";src.mkdir();(src/"index.html").write_text("Atlas")
   convergence_hub.build(convergence_hub.HERE/convergence_hub.SOURCE_NAME,
                         src/"convergence","a"*40)
   (src/"convergence"/"index.html").write_text("FORGED",encoding="utf-8")
   with self.assertRaisesRegex(ValueError,"Convergence Hub source member hash mismatch"):
    pages_portal.build(src,p/"pages","a"*40)

class ExecutionAtlasPackagingTests(unittest.TestCase):
    """Exercise the real child verifier through the single existing packager."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.atlas = self.root / "atlas"
        self.out = self.root / "pages"
        self.atlas.mkdir()
        (self.atlas / "index.html").write_text("<html>Parent Atlas</html>", encoding="utf-8")
        self.sha = "a" * 40

    @staticmethod
    def canonical(value):
        return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()

    def execution_child(self):
        child = self.atlas / "orchestration"
        child.mkdir()
        repo = Path(pages_portal.__file__).resolve().parents[2]
        source = "mission-control/federation-atlas/orchestration/BROKER_POLICY_v1.json"
        source_hashes = {source: hashlib.sha256((repo / source).read_bytes()).hexdigest()}
        source_digest = hashlib.sha256(self.canonical(source_hashes)).hexdigest()
        model = {"schema": "missioncontrol.orchestration.atlas.v1",
                 "source": {"head_sha": self.sha, "dirty": False,
                            "source_files_sha256": source_hashes, "source_digest": source_digest},
                 "authority_transfer": False, "remote_dispatch": False, "merge_admission": "HOLD"}
        members = {"index.html": b"<html>Child Atlas</html>", "style.css": b"body{}",
                   "app.js": b"'use strict';", "atlas.json": self.canonical(model),
                   "inventory.json": b"{}\n", "burndown.json": b"{}\n",
                   "broker-plan.json": b"{}\n", "source-check.json": b"{}\n"}
        for name, raw in members.items():
            (child / name).write_bytes(raw)
        manifest = {"schema": "missioncontrol.orchestration.manifest.v1",
                    "source_sha": self.sha, "source_dirty": False, "source_digest": source_digest,
                    "publisher": "EXISTING_METHOD_ATLAS_PAGES_ONLY", "authority_transfer": False,
                    "remote_dispatch": False, "merge_admission": "HOLD",
                    "files_sha256": {name: hashlib.sha256(raw).hexdigest() for name, raw in members.items()},
                    "files_bytes": {name: len(raw) for name, raw in members.items()}}
        (child / "manifest.json").write_bytes(self.canonical(manifest))
        return child, manifest

    def test_canonical_code_purple_json_is_preserved_with_its_hash(self):
        raw = self.canonical({"schema": "missioncontrol.code_purple.page.v1", "items": []})
        (self.atlas / "code-purple.json").write_bytes(raw)
        result = pages_portal.build(self.atlas, self.out, self.sha)
        self.assertEqual((self.out / "atlas" / "code-purple.json").read_bytes(), raw)
        self.assertEqual(result["public_files_sha256"]["atlas/code-purple.json"], hashlib.sha256(raw).hexdigest())

    def test_verified_child_is_an_owned_member_of_existing_parent(self):
        child, manifest = self.execution_child()
        result = pages_portal.build(self.atlas, self.out, self.sha)
        for name in [*manifest["files_sha256"], "manifest.json"]:
            raw = (child / name).read_bytes()
            self.assertEqual((self.out / "orchestration" / name).read_bytes(), raw)
            self.assertEqual(result["public_files_sha256"]["orchestration/" + name], hashlib.sha256(raw).hexdigest())
        self.assertEqual(result["schema"], "codepurple.pages.readonly/v1")
        self.assertFalse(result["merge_authorized"])
        self.assertFalse(result["security_waiver"])
        self.assertEqual(manifest["publisher"], "EXISTING_METHOD_ATLAS_PAGES_ONLY")
        self.assertIn('href="orchestration/index.html"', (self.out / "index.html").read_text())

    def test_tampered_child_fails_before_parent_manifest_is_written(self):
        child, _ = self.execution_child()
        (child / "app.js").write_bytes(b"tampered();")
        with self.assertRaisesRegex(ValueError, "member hash mismatch"):
            pages_portal.build(self.atlas, self.out, self.sha)
        self.assertFalse((self.out / "site-manifest.json").exists())
        self.assertFalse((self.out / "orchestration").exists())

    def test_child_cannot_claim_another_publisher_or_remote_authority(self):
        child, manifest = self.execution_child()
        for field, value in (("publisher", "ANOTHER_PUBLISHER"), ("remote_dispatch", True), ("authority_transfer", True)):
            with self.subTest(field=field):
                modified = {**manifest, field: value}
                (child / "manifest.json").write_bytes(self.canonical(modified))
                with self.assertRaisesRegex(ValueError, "manifest authority violation"):
                    pages_portal.build(self.atlas, self.out, self.sha)
        self.assertFalse((self.out / "site-manifest.json").exists())

    def test_different_child_head_cannot_be_relabelled_by_parent(self):
        self.execution_child()
        with self.assertRaisesRegex(ValueError, "bundle head mismatch"):
            pages_portal.build(self.atlas, self.out, "b" * 40)
        self.assertFalse((self.out / "site-manifest.json").exists())

    def test_unmanifested_child_file_is_not_silently_published(self):
        child, _ = self.execution_child()
        (child / "extra.json").write_bytes(b"{}")
        with self.assertRaisesRegex(ValueError, "unmanifested bundle member"):
            pages_portal.build(self.atlas, self.out, self.sha)
        self.assertFalse((self.out / "site-manifest.json").exists())

    def test_copy_time_corruption_is_detected_before_parent_sealing(self):
        self.execution_child()
        original_copy = pages_portal.shutil.copyfile

        def damaged_copy(source, destination, *args, **kwargs):
            result = original_copy(source, destination, *args, **kwargs)
            if Path(destination) == self.out / "orchestration" / "app.js":
                Path(destination).write_bytes(b"damaged during copy")
            return result

        with mock.patch.object(pages_portal.shutil, "copyfile", side_effect=damaged_copy):
            with self.assertRaisesRegex(ValueError, "member hash mismatch"):
                pages_portal.build(self.atlas, self.out, self.sha)
        self.assertFalse((self.out / "site-manifest.json").exists())


if __name__=="__main__":unittest.main()
