"""N+8 red-trace child: fail-closed staging into the EXISTING publisher and hosted parity."""
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def mod(rel, name):
    s = importlib.util.spec_from_file_location(name, ROOT / rel)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


bridge = mod("portal_bridge.py", "jade_bridge_n8")
hosted = mod("tools/hosted_parity.py", "jade_hosted_n8")


def copy_project(t):
    proj = Path(t) / "proj"
    (proj / "site").mkdir(parents=True)
    (proj / "data").mkdir()
    for n in bridge.REDTRACE_REQUIRED:
        shutil.copyfile(ROOT / "site" / n, proj / "site" / n)
    for rel in bridge.REDTRACE_SOURCES:
        shutil.copyfile(ROOT / rel, proj / rel)
    return proj


class N8Pages(unittest.TestCase):
    def test_stages_all_four_and_hashes_match(self):
        with tempfile.TemporaryDirectory() as t:
            h = {}
            n = bridge.stage_redtrace(ROOT, Path(t) / "out", h)
            self.assertEqual(n, 4)
            for name in bridge.REDTRACE_REQUIRED:
                self.assertEqual(h["jade/" + name], bridge.sha256(ROOT / "site" / name))

    def test_hosted_population_includes_n8(self):
        want = {"jade/" + n for n in bridge.REDTRACE_REQUIRED}
        self.assertTrue(want <= hosted.REQUIRED_JADE)

    def test_absent_child_is_optional(self):
        with tempfile.TemporaryDirectory() as t:
            proj = Path(t) / "p"
            (proj / "site").mkdir(parents=True)
            self.assertEqual(bridge.stage_redtrace(proj, Path(t) / "o", {}), 0)

    def test_partial_site_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            proj = copy_project(t)
            (proj / "site/redtrace-slides.pdf").unlink()
            with self.assertRaisesRegex(ValueError, "PARTIAL"):
                bridge.stage_redtrace(proj, Path(t) / "o", {})

    def test_source_drift_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            proj = copy_project(t)
            p = proj / "data/GAP_ANALYSIS_N8.json"
            p.write_text(p.read_text(encoding='utf-8') + " ",encoding='utf-8')
            with self.assertRaisesRegex(ValueError, "SOURCE_DIGEST_DRIFT"):
                bridge.stage_redtrace(proj, Path(t) / "o", {})

    def test_html_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            proj = copy_project(t)
            (proj / "site/redtrace.html").write_text("<p>forged</p>",encoding='utf-8')
            with self.assertRaisesRegex(ValueError, "STATIC_DIGEST_DRIFT"):
                bridge.stage_redtrace(proj, Path(t) / "o", {})

    def test_bad_or_truncated_pdf_rejected(self):
        for body in (b"not a pdf", b"%PDF-1.7\n" + b"x" * 100, b"%PDF-" + b"x" * (bridge.REDTRACE_PDF_MAX + 1)):
            with self.subTest(n=len(body)), tempfile.TemporaryDirectory() as t:
                proj = copy_project(t)
                (proj / "site/redtrace-slides.pdf").write_bytes(body)
                with self.assertRaisesRegex(ValueError, "BAD_PDF"):
                    bridge.stage_redtrace(proj, Path(t) / "o", {})

    def test_authority_claim_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            proj = copy_project(t)
            p = proj / "site/redtrace-manifest.json"
            m = json.loads(p.read_text(encoding='utf-8'))
            m["merge_authorized"] = True
            p.write_text(json.dumps(m),encoding='utf-8')
            with self.assertRaisesRegex(ValueError, "UNSAFE_MANIFEST"):
                bridge.stage_redtrace(proj, Path(t) / "o", {})

    def test_published_page_has_no_relative_data_links(self):
        html = (ROOT / "site/redtrace.html").read_text(encoding='utf-8')
        self.assertNotIn('href="../', html, "Pages publishes only jade/; ../ links would 404")


if __name__ == "__main__":
    unittest.main()
