"""Confirm existing Pages portal (one owner) exports G3P source/manifest unchanged."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
ATLAS=HERE.parent/"federation-atlas"
sys.path.insert(0,str(ATLAS))
import pages_portal
from html_contract import inspect


class PagesBridgeTests(unittest.TestCase):
    def test_sanitized_single_portal_packs_g3p(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            atlas=root/"atlas"
            atlas.mkdir()
            (atlas/"index.html").write_text("<html>Mock Atlas</html>",encoding="utf-8")
            (atlas/"lane-process.mmd").write_text("flowchart LR\n A-->B\n",encoding="utf-8")
            result=pages_portal.build(atlas,root/"published","a"*40)
            g3p=root/"published"/"g3p"
            page=g3p/"index.html"
            source=ATLAS/"G3P_LIVE_LEDGER.html"
            manifest=g3p/"G3P_LIVE_SOURCES_v1.json"
            self.assertEqual(page.read_bytes(),source.read_bytes())
            self.assertEqual(manifest.read_bytes(),(ATLAS/manifest.name).read_bytes())
            self.assertIn("g3p/index.html",result["public_files_sha256"])
            self.assertEqual(result["public_files_sha256"]["g3p/index.html"],hashlib.sha256(page.read_bytes()).hexdigest())
            self.assertIn('href="g3p/index.html"',(root/"published"/"index.html").read_text(encoding="utf-8"))
            self.assertEqual(inspect(page.read_text(),base_dir=g3p)["status"],"PASS")
            self.assertFalse(result["merge_authorized"])
            self.assertFalse(result["security_waiver"])

    def test_manifest_is_identity_bounded(self):
        m=json.loads((ATLAS/"G3P_LIVE_SOURCES_v1.json").read_text())
        self.assertEqual(m["repository"],"GBOGEB/pipeline-automation-hub")
        self.assertEqual(m["mission_id"],"CBD-GOLDEN-GRAPH-604")
        self.assertEqual(m["merge_admission"],"HOLD")

if __name__=="__main__":
    unittest.main()
