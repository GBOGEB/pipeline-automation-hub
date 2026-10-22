"""W55 conditional bridge tests for verified historical coverage views.

Fixtures are synthetic. No current-main, bidder or review authority implied.
"""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pages_portal


class CoverageIntegrityBridgeTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.atlas = self.root / "atlas"
        self.atlas.mkdir()
        (self.atlas / "index.html").write_text("Atlas landing", encoding="utf-8")
        self.child = self.atlas / "coverage-integrity"
        self.child.mkdir()
        self.public = self.root / "pages"
        self.head = "a" * 40
        self.source = self.root / "source.json"
        self.source.write_text(json.dumps({
            "schema": "codepurple.coverage_integrity.observations.v1",
            "authority": {"merge_admission": "HOLD",
                          "engineering_acceptance": "WITHHELD",
                          "security_waiver": "NONE", "formal_credit_delta": 0,
                          "is_six_repo_canonical_breadth": False},
        }), encoding="utf-8")
        self.members = {
            name: (b"<svg xmlns='http://www.w3.org/2000/svg'/>"
                   if name.endswith(".svg") else b"flowchart LR\n A --> B\n"
                   if name.endswith(".mmd") else b"<html>synthetic</html>"
                   if name == "index.html" else b"")
            for name in pages_portal.COVERAGE_INTEGRITY_MEMBERS
        }
        self.seal()

    def seal(self, **snapshot_override):
        source_digest = hashlib.sha256(self.source.read_bytes()).hexdigest()
        snap = {"schema": "codepurple.coverage_integrity.snapshot.v1",
                "presentation_head_sha": self.head,
                "source_json_sha256": source_digest,
                "portfolio_total_coverage": None,
                "authority": {"merge_admission": "HOLD",
                              "engineering_acceptance": "WITHHELD",
                              "security_waiver": "NONE",
                              "formal_credit_delta": 0,
                              "is_native_current_attestation": False,
                              "run_dispatch": False}}
        snap.update(snapshot_override)
        self.members["snapshot.json"] = (json.dumps(snap, sort_keys=True) + "\n").encode()
        for name, raw in self.members.items():
            (self.child / name).write_bytes(raw)
        manifest = {
            "schema": "codepurple.coverage_integrity.manifest.v1",
            "presentation_head_sha": self.head,
            "source_json_sha256": source_digest,
            "merge_admission": "HOLD", "authority_transfer": False,
            "formal_credit_delta": 0,
            "current_main_coverage_attestation": None,
            "member_sha256": {name: hashlib.sha256(raw).hexdigest()
                              for name, raw in self.members.items()},
            "member_bytes": {name: len(raw) for name, raw in self.members.items()}}
        (self.child / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def stage(self, head=None):
        return pages_portal.stage_coverage_integrity(
            self.atlas, self.public, head or self.head, {},
            source_path=self.source)

    def test_missing_incubator_is_not_coverage_attestation(self):
        for path in self.child.iterdir():
            path.unlink()
        self.child.rmdir()
        self.assertIs(self.stage(), False)

    def test_pinned_source_manifest_member_bytes_and_hashes_pass(self):
        hashes = {}
        self.assertTrue(pages_portal.stage_coverage_integrity(
            self.atlas, self.public, self.head, hashes, self.source))
        self.assertEqual(len(hashes), len(self.members) + 1)
        for name, raw in self.members.items():
            self.assertEqual((self.public / "coverage-integrity" / name).read_bytes(), raw)

    def test_existing_portal_links_once_to_verified_child(self):
        with mock.patch.object(pages_portal, "COVERAGE_INTEGRITY_SOURCE", self.source):
            result = pages_portal.build(self.atlas, self.public, self.head)
        self.assertIn('href="coverage-integrity/index.html"',
                      (self.public / "index.html").read_text())
        self.assertIn("coverage-integrity/index.html", result["public_files_sha256"])
        self.assertFalse(result["merge_authorized"])

    def test_missing_source_owner_fails_closed(self):
        self.source.unlink()
        with self.assertRaisesRegex(ValueError, "SOURCE_OWNER"):
            self.stage()

    def test_changed_source_bytes_block_stale_view(self):
        self.source.write_bytes(self.source.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "HEAD_SOURCE"):
            self.stage()

    def test_partial_or_extra_child_fails(self):
        (self.child / "graph-dark.svg").unlink()
        with self.assertRaisesRegex(ValueError, "MEMBER_POPULATION"):
            self.stage()
        self.seal()
        (self.child / "extra.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "MEMBER_POPULATION"):
            self.stage()

    def test_foreign_presentation_head_fails(self):
        with self.assertRaisesRegex(ValueError, "HEAD_SOURCE"):
            self.stage("b" * 40)

    def test_tampered_svg_fails_even_with_other_perfect_members(self):
        (self.child / "graph-light.svg").write_text("<svg/>")
        with self.assertRaisesRegex(ValueError, "DIGEST_MISMATCH"):
            self.stage()

    def test_resealed_global_coverage_forgery_still_fails(self):
        self.seal(portfolio_total_coverage=99.99)
        with self.assertRaisesRegex(ValueError, "SNAPSHOT_AUTHORITY"):
            self.stage()

    def test_forged_six_repo_authority_is_rejected(self):
        source = json.loads(self.source.read_text())
        source["authority"]["is_six_repo_canonical_breadth"] = True
        self.source.write_text(json.dumps(source))
        self.seal()
        with self.assertRaisesRegex(ValueError, "SOURCE_AUTHORITY"):
            self.stage()

    def test_invalid_svg_with_resealed_digest_is_still_rejected(self):
        self.members["graph-dark.svg"] = b"not xml"
        self.seal()
        with self.assertRaises(Exception):
            self.stage()

    def test_copy_time_mutation_detected_before_parent_seal(self):
        original = pages_portal.shutil.copyfile

        def tamper_after_copy(src, dst):
            result = original(src, dst)
            if Path(dst) == self.public / "coverage-integrity" / "index.html":
                Path(dst).write_bytes(b"damaged")
            return result

        with mock.patch.object(pages_portal.shutil, "copyfile",
                               side_effect=tamper_after_copy):
            with self.assertRaisesRegex(ValueError, "COPY_TIME_MUTATION"):
                self.stage()
        self.assertFalse((self.public / "site-manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
