"""JQ-04: negative-first, no-network source/view pointer tests.

The B05 and run anchors reference one immutable exploratory HTML build, not a
new live census, precise SVG bbox, PDF page or release admission decision.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pointer_contract as p  # noqa: E402


class PointerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads(p.MANIFEST.read_text("utf-8"))

    def validate(self, doc=None, root=None):
        return p.validate(copy.deepcopy(self.doc if doc is None else doc),
                          p.ROOT if root is None else root)

    def changed(self, fn):
        doc = copy.deepcopy(self.doc)
        fn(doc)
        return doc

    def expect_red(self, code, fn):
        with self.assertRaisesRegex(ValueError, "CI_SPINE_POINTER_FIRST_RED:" + code):
            self.validate(self.changed(fn))

    def test_three_pointers_and_one_explicitly_unmapped_pdf(self):
        r = self.validate()
        self.assertEqual(r["verdict"], "SOURCE_BOUND_VIEW_SELECTION_ONLY")
        self.assertEqual(len(r["mapped"]), 3)
        self.assertEqual(r["unknown_pdf_pointers"], 1)
        self.assertEqual(r["pdf_rectangles_verified"], 0)
        self.assertIs(r["merge_authorized"], False)

    def test_exact_blob_and_sha256_from_qualified_head(self):
        doc = self.doc
        self.assertEqual(doc["viewer"]["head_sha"], doc["source_commit"])
        self.assertNotEqual(doc["catalog_snapshot_commit"], doc["source_commit"])
        raw = p.file_bytes(doc["viewer"]["path"])
        self.assertEqual(p.git_blob_oid(raw), doc["viewer"]["blob_oid"])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), doc["viewer"]["sha256"])
        self.assertEqual(doc["viewer"]["build_workflow_run_id"], 40726398983)

    def test_source_file_drift_fails(self):
        self.expect_red("SOURCE_BLOB_STALE", lambda d: d["pointers"][0]["source"].__setitem__("blob_oid", "a"*40))

    def test_render_binary_drift_fails(self):
        self.expect_red("OUTPUT_SHA256_STALE", lambda d: d["viewer"].__setitem__("sha256", "a"*64))

    def test_source_commit_switch_fails(self):
        self.expect_red("HEAD_IDENTITY", lambda d: d.__setitem__("source_commit", "f"*40))

    def test_target_digest_is_not_independently_guessed(self):
        self.expect_red("MISMATCHED_OUTPUT", lambda d: d["pointers"][1]["output"].__setitem__("sha256", "f"*64))

    def test_target_view_anchor_must_exist(self):
        self.expect_red("MISSING_VIEW_ANCHOR", lambda d: d["pointers"][0]["output"].__setitem__("dom_id", "pdf-fake-rectangle"))

    def test_hash_routing_must_match_semantic_selection(self):
        self.expect_red("WRONG_SELECTION_HASH", lambda d: d["pointers"][0]["output"].__setitem__("href", "../explorer.html#lens=graph&kind=bundle&id=B07"))

    def test_external_navigation_is_not_a_local_pointer(self):
        self.expect_red("UNTRUSTED_OUTPUT_URL", lambda d: d["pointers"][0]["output"].__setitem__("href", "https://evil.example/#lens=graph&kind=bundle&id=B05"))

    def test_extra_query_parameter_or_duplicated_hash_is_rejected(self):
        self.expect_red("UNTRUSTED_OUTPUT_URL", lambda d: d["pointers"][0]["output"].__setitem__("href", "../explorer.html?q=anything#lens=graph&kind=bundle&id=B05"))
        self.expect_red("WRONG_SELECTION_HASH", lambda d: d["pointers"][0]["output"].__setitem__("href", "../explorer.html#lens=graph&lens=sipoc&kind=bundle&id=B05"))

    def test_wrong_object_id_is_rejected(self):
        self.expect_red("OBJECT_SEMANTIC_MISMATCH", lambda d: d["pointers"][0]["source"].__setitem__("object_id", "ci-spine:bundle:B09"))

    def test_wrong_run_id_cannot_link_other_run(self):
        self.expect_red("RUN_SEMANTIC_MISMATCH", lambda d: d["pointers"][2]["source"].__setitem__("object_id", "run:0"))

    def test_wrong_json_pointer_does_not_silently_remap(self):
        self.expect_red("POINTER_OUT_OF_RANGE", lambda d: d["pointers"][0]["source"].__setitem__("json_pointer", "/nodes/5000"))
        self.expect_red("INVALID_JSON_POINTER", lambda d: d["pointers"][0]["source"].__setitem__("json_pointer", "/nodes/-1"))

    def test_deny_path_traversal_and_remote_source(self):
        self.expect_red("PATH_NOT_ALLOWLISTED", lambda d: d["pointers"][0]["source"].__setitem__("path", "../../secrets.json"))

    def test_source_to_output_precision_cannot_claim_pdf_exactness(self):
        self.expect_red("CLAIMED_EXACTNESS_OR_AUTHORITY", lambda d: d["pointers"][0].__setitem__("precision", "PDF_RECT_EXACT"))

    def test_missing_pdf_binary_cannot_have_made_up_page(self):
        self.expect_red("FALSE_PDF_PROVENANCE", lambda d: d["pending"][0].__setitem__("output", {"page": 1, "bbox": [0,0,1,1]}))

    def test_pending_pdf_may_not_link_as_if_qualified(self):
        self.expect_red("FALSE_PDF_PROVENANCE", lambda d: d["pending"][0].__setitem__("href", "../explorer.html#pdf=1"))

    def test_multiple_identical_pointers_are_not_independent_proof(self):
        self.expect_red("DUPLICATE_POINTER", lambda d: d["pointers"][1].__setitem__("id", d["pointers"][0]["id"]))

    def test_companion_gui_links_are_all_sourced_from_manifest(self):
        nav = p.Anchors()
        text = p.NAV.read_text("utf-8")
        nav.feed(text)
        self.assertEqual(nav.scripts, [])
        self.assertIn("connect-src 'none'", text)
        self.assertTrue({x["output"]["href"] for x in self.doc["pointers"]} <= nav.links)
        self.assertIn("0 PDF RECTANGLES VERIFIED", text)

    def test_decorative_arrow_cannot_capture_pointer_events(self):
        html = p.NAV.read_text("utf-8")
        self.assertRegex(html, r"\.arrow\{[^}]*pointer-events:none")
        self.assertEqual(html.count('class="action"'), 3)

    def test_companion_gui_script_injection_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            nav = Path(temp) / "index.html"
            nav.write_text(p.NAV.read_text("utf-8") + "<script>alert(1)</script>",
                           encoding="utf-8")
            with mock.patch.object(p, "NAV", nav):
                with self.assertRaisesRegex(ValueError, "NAV_REMOTE_EXECUTION"):
                    self.validate()

    def test_companion_gui_wrong_link_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            nav = Path(temp) / "index.html"
            original = self.doc["pointers"][0]["output"]["href"]
            nav.write_text(p.NAV.read_text("utf-8").replace(
                original.replace("&", "&amp;"), "../explorer.html#lens=graph&kind=bundle&id=FAKE"),
                encoding="utf-8")
            with mock.patch.object(p, "NAV", nav):
                with self.assertRaisesRegex(ValueError, "NAV_BROKEN_POINTER_LINK"):
                    self.validate()

    def test_mutated_real_html_bytes_cannot_satisfy_pinned_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for path in p.ALLOWED:
                destination = root / path
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(p.ROOT / path, destination)
            target = root / "docs/ci-spine/explorer.html"
            target.write_bytes(target.read_bytes() + b"\n<!-- unexpected mutation -->")
            with self.assertRaisesRegex(ValueError, "OUTPUT_BLOB_STALE"):
                self.validate(root=root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
