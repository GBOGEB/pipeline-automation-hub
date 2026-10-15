"""Native negative controls for monochrome G1 SSOT-derived HTML."""
from __future__ import annotations
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import federation_rollup as provider
import render_g1 as view

INPUT = ROOT / "samples" / "federation_g1_observed.json"
SHA = "a" * 40
DIGEST = "b" * 64


def report():
    return provider.build(json.loads(INPUT.read_text()))


class G1HtmlTests(unittest.TestCase):
    def test_native_rollup_is_not_promoted(self):
        r = report()
        view.verify(r, SHA)
        s = view.render(r, SHA, DIGEST)
        self.assertIn("13/66", s)
        self.assertIn("0/66", s)
        self.assertIn("HOLD", s)
        self.assertIn("QPS disposition: DEFER", s)

    def test_empty_native_and_bytes_not_confused_with_test_zero(self):
        r = report()
        s = r["breadth_depth"]
        self.assertEqual((13, 0, 0, 53),
                         (s["source_discovered_cells"], s["native_status_verified_cells"],
                          s["artifact_bytes_verified_cells"], s["unknown_cells"]))

    def test_scope_change_fails_closed(self):
        r = report()
        r["breadth_depth"]["target_repo_surface_cells"] = 42
        with self.assertRaisesRegex(ValueError, "66-cell"):
            view.verify(r, SHA)

    def test_fake_admission_fails_closed(self):
        r = report()
        r["admission"] = "PASS"
        with self.assertRaisesRegex(ValueError, "admission"):
            view.verify(r, SHA)

    def test_fake_owner_transfer_fails_closed(self):
        r = report()
        r["authority_transfer"] = True
        with self.assertRaisesRegex(ValueError, "authority"):
            view.verify(r, SHA)

    def test_source_sha_and_report_digest_required(self):
        r = report()
        with self.assertRaisesRegex(ValueError, "source SHA"):
            view.verify(r, "short")
        with self.assertRaisesRegex(ValueError, "digest"):
            view.render(r, SHA, "short")

    def test_escape_external_display_fields(self):
        r = report()
        r["pulse_id"] = '<script>alert("x")</script>'
        s = view.render(r, SHA, DIGEST)
        self.assertNotIn('<script>alert("x")</script>', s)
        self.assertIn("&lt;script&gt;", s)

    def test_group_count_identity_fail_closed(self):
        r = report()
        group = next(iter(r["surfaces"].values()))
        group["unknown"] = 6
        with self.assertRaisesRegex(ValueError, "grouped census"):
            view.verify(r, SHA)


if __name__ == "__main__":
    unittest.main()
