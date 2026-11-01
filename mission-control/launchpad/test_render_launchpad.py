"""MissionControl launcher structural, spoofed-input and hash-parity QA."""
from __future__ import annotations
import hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("render_launchpad",HERE/"render_launchpad.py")
import sys
sys.path.insert(0,str(HERE))
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
import nav_model
SHA="a"*40

class LauncherTests(unittest.TestCase):
    def test_build_all_pages_and_hashes(self):
        with tempfile.TemporaryDirectory() as td:
            m=mod.build(td,SHA)
            self.assertEqual(m["schema"],"missioncontrol.launchpad.publication_manifest.v1")
            self.assertEqual(set(m["files_sha256"]),set(mod.FILES))
            for name,digest in m["files_sha256"].items():
                self.assertEqual(hashlib.sha256((Path(td)/name).read_bytes()).hexdigest(),digest)
            self.assertEqual(m["merge_admission"],"HOLD")
            self.assertIsNone(m["native_qa"])
            self.assertFalse(m["hosted_http_verified"])
    def test_repeatable_source_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            mod.build(td,SHA)
            first={name:(Path(td)/name).read_bytes() for name in mod.FILES}
            mod.build(td,SHA)
            self.assertEqual(first,{name:(Path(td)/name).read_bytes() for name in mod.FILES})
    def test_outputs_are_lf_on_every_os(self):
        with tempfile.TemporaryDirectory() as td:
            mod.build(td,SHA)
            for name in (*mod.FILES,"manifest.json"):
                self.assertNotIn(b"\r",(Path(td)/name).read_bytes(),name)
        with tempfile.TemporaryDirectory() as td:
            nav_model.generate(out=td)
            for name in ("snapshot.json","federation.mmd","SIPOC.md"):
                self.assertNotIn(b"\r",(Path(td)/name).read_bytes(),name)
    def test_reject_non_sha(self):
        with tempfile.TemporaryDirectory() as td:
            for bad in ("short","g"*40,"A"*40):
                with self.assertRaises(ValueError):mod.build(td,bad)
    def test_escaping_does_not_close_script(self):
        d=json.loads(nav_model.CONFIG.read_text())
        d["nodes"][0]["label"]='</script><script>alert("forgery")</script>'
        page=mod.render(nav_model.project(d),SHA)
        self.assertNotIn('</script><script>alert("forgery")</script>',page)
        self.assertIn('\\u003c/script\\u003e',page)
    def test_no_javascript_network_or_dispatch(self):
        html=mod.TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("connect-src 'none'",html)
        self.assertIn("Dispatch disabled",html)
        self.assertIn("id=\"search\"",html)
        self.assertIn("id=\"graph-mode\"",html)
        self.assertIn("id=\"repo-list\"",html)
        self.assertIn("id=\"graph-expand\"",html)
        self.assertIn("keydown",html)
        self.assertNotIn("https://cdn.",html)
        self.assertNotIn("fetch(",html)
    def test_reports_panel_and_deep_links(self):
        html=mod.TEMPLATE.read_text(encoding="utf-8")
        self.assertIn('id="report-list"',html)
        self.assertIn('"report-"+x.repo+"-"+x.id',html)
        self.assertIn("hashchange",html)
        reports=json.loads(nav_model.CONFIG.read_text(encoding="utf-8"))["reports"]
        page=mod.render(nav_model.project(json.loads(nav_model.CONFIG.read_text(encoding="utf-8"))),SHA)
        for x in reports:self.assertIn('"id":"'+x["id"]+'"',page)
    def test_invalid_payload_cannot_promote(self):
        d=nav_model.project(json.loads(nav_model.CONFIG.read_text()))
        d["policy"]["remote_dispatch_enabled"]=True
        with self.assertRaises(ValueError):mod.render(d,SHA)
        d["policy"]["remote_dispatch_enabled"]=False
        d["admission"]="GO"
        with self.assertRaises(ValueError):mod.render(d,SHA)
    def test_legacy_owner_bypass_not_added(self):
        with tempfile.TemporaryDirectory() as td:
            m=mod.build(td,SHA)
            self.assertFalse(m["authority_transfer"])
            self.assertFalse(m["qps_engineering_acceptance"])
            self.assertFalse(m["security_waiver"])
if __name__=="__main__":unittest.main()
