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
        for field in p.MUTABLE_COMMIT_FIELDS:
            self.assertNotIn(field, doc)
            self.assertNotIn(field, doc["viewer"])
        self.assertEqual(p.tree_blob(doc["viewer"]["path"]), doc["viewer"]["blob_oid"])
        raw = p.file_bytes(doc["viewer"]["path"])
        self.assertEqual(p.git_blob_oid(raw), doc["viewer"]["blob_oid"])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), doc["viewer"]["sha256"])
        self.assertIsNone(doc["viewer"]["build_workflow_run_id"])
        self.assertEqual(doc["viewer"]["build_receipt_state"], "NATIVE_EXACT_HEAD_RUN_PENDING")

    def test_pinned_bytes_must_be_committed_at_checkout(self):
        # Matching working-tree bytes are not enough: the checked-out HEAD tree must hold them.
        with mock.patch.object(p, "tree_blob", return_value="0"*40):
            with self.assertRaisesRegex(ValueError, "OUTPUT_NOT_AT_CHECKOUT"):
                self.validate()
        viewer = self.doc["viewer"]
        with mock.patch.object(p, "tree_blob",
                               side_effect=lambda path: viewer["blob_oid"]
                               if path == viewer["path"] else "0"*40):
            with self.assertRaisesRegex(ValueError, "SOURCE_NOT_AT_CHECKOUT"):
                self.validate()

    def test_unresolvable_checkout_fails_closed(self):
        failed = mock.Mock(returncode=128, stdout=b"")
        with mock.patch.object(p.subprocess, "run", return_value=failed):
            with self.assertRaisesRegex(ValueError, "UNRESOLVED_CHECKOUT"):
                self.validate()

    def test_unmapped_pdf_link_outside_publication_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            nav = Path(temp) / "index.html"
            nav.write_text(p.NAV.read_text("utf-8") +
                           '<a href="../fake.pdf#page=1">PDF page</a>',
                           encoding="utf-8")
            with mock.patch.object(p, "NAV", nav):
                with self.assertRaisesRegex(ValueError, "NAV_UNDECLARED_LINK"):
                    self.validate()

    def test_source_file_drift_fails(self):
        self.expect_red("SOURCE_BLOB_STALE", lambda d: d["pointers"][0]["source"].__setitem__("blob_oid", "a"*40))

    def test_render_binary_drift_fails(self):
        self.expect_red("OUTPUT_SHA256_STALE", lambda d: d["viewer"].__setitem__("sha256", "a"*64))

    def test_mutable_commit_binding_is_rejected(self):
        # A branch SHA is orphaned by rebase or squash merge, so it can never be the binding.
        self.expect_red("MUTABLE_COMMIT_BINDING", lambda d: d.__setitem__("source_commit", "f"*40))
        self.expect_red("MUTABLE_COMMIT_BINDING", lambda d: d["viewer"].__setitem__("head_sha", "f"*40))
        self.expect_red("MUTABLE_COMMIT_BINDING", lambda d: d["pointers"][2].__setitem__("output_commit", "f"*40))
        self.expect_red("HEAD_IDENTITY", lambda d: d.__setitem__("catalog_snapshot_commit", "main"))

    def test_lens_must_match_object_kind(self):
        # Lens, DOM id and href changed together still route to fallback B05, not the run.
        def to_sipoc(d):
            out = d["pointers"][2]["output"]
            out.update(lens="sipoc", dom_id="sipoc-body",
                       href="../explorer.html#lens=sipoc&kind=run&id=" + str(out["selection_id"]))
        self.expect_red("LENS_KIND_MISMATCH", to_sipoc)

        def bundle_to_timing(d):
            out = d["pointers"][0]["output"]
            out.update(lens="timing", dom_id="timing-rows",
                       href="../explorer.html#lens=timing&kind=bundle&id=B05")
        self.expect_red("LENS_KIND_MISMATCH", bundle_to_timing)

    def test_atlas_cannot_display_stale_provenance(self):
        stale = ("a7cbae8da2753404241b99a50f999f3f7526f111c30e86c102025d81aa283e0c",
                 "build run 40726398983", "e866b340b81a1287c8d05b34203d57f28ee4553e")
        for extra in stale:
            with self.subTest(extra=extra), tempfile.TemporaryDirectory() as temp:
                nav = Path(temp) / "index.html"
                nav.write_text(p.NAV.read_text("utf-8").replace(
                    "</main>", "<p>" + extra + "</p></main>"), encoding="utf-8")
                with mock.patch.object(p, "NAV", nav):
                    with self.assertRaisesRegex(ValueError, "NAV_STALE_PROVENANCE"):
                        self.validate()

    def test_atlas_displays_current_viewer_digest(self):
        shown = p.nav_bindings(p.NAV.read_text("utf-8"))
        self.assertEqual(shown, p.declared_bindings(self.doc))
        self.assertIn(self.doc["viewer"]["sha256"], shown["sha256"])

    def test_rebind_moves_only_content_identities(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for path in p.ALLOWED:
                destination = root / path
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(p.ROOT / path, destination)
            target = root / "docs/ci-spine/explorer.html"
            target.write_bytes(target.read_bytes() + b"\n<!-- rebuilt -->")
            doc, nav = p.rebind(self.doc, p.NAV.read_text("utf-8"), root)
        new_sha = hashlib.sha256(p.ROOT.joinpath("docs/ci-spine/explorer.html").read_bytes()
                                 + b"\n<!-- rebuilt -->").hexdigest()
        self.assertEqual(doc["viewer"]["sha256"], new_sha)
        self.assertNotIn(self.doc["viewer"]["sha256"], nav)
        self.assertIn(new_sha, nav)
        self.assertEqual([r["output"]["href"] for r in doc["pointers"]],
                         [r["output"]["href"] for r in self.doc["pointers"]])
        self.assertEqual({r["output"]["sha256"] for r in doc["pointers"]}, {new_sha})

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


    def test_layer_comparison_is_native_offline_disclosure(self):
        html = p.NAV.read_text("utf-8")
        self.assertEqual(html.count('class="layer-stage"'), 3)
        for layer in ("source", "views", "publication"):
            self.assertIn(f'data-layer="{layer}"', html)
        self.assertIn("Source → derived view is currently VIEW_SELECTION precision", html)
        self.assertIn("Derived view → PDF geometry is UNKNOWN", html)
        self.assertIn("script-src 'none'", html)
        self.assertEqual(html.count('class="action"'), 3)

    def test_unverified_publication_layer_has_no_navigation(self):
        html = p.NAV.read_text("utf-8")
        start = html.index('data-layer="publication"')
        end = html.index("</details>", start)
        publication = html[start:end]
        self.assertIn("UNMAPPED", publication)
        self.assertIn("no verified owner PDF", publication)
        self.assertNotIn("<a ", publication)
        self.assertNotIn('href=', publication)
        self.assertIn("never migrate them using page numbers alone", publication)

if __name__ == "__main__":
    unittest.main(verbosity=2)
