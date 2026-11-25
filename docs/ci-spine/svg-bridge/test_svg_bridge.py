"""Negative-first, stdlib-only contracts for the JQ09 SVG provenance bridge."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest import TestCase, main, mock

import svg_bridge as bridge


class SVGBridgeContracts(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = bridge.SOURCE.read_bytes()

    def mutated(self, data: bytes):
        with mock.patch.object(bridge, "EXPECTED_BLOB", bridge.blob_oid(data)):
            return bridge.parse_source(data)

    def test_real_source_is_pinned_to_existing_blob(self):
        self.assertEqual(bridge.blob_oid(self.raw), "8a947a18a76bd87029b0c237be81505eb86f0891")
        self.assertEqual(bridge.SOURCE_REF, "54e6b01ac7ada5bfad15562b4f99f7381a4fd73f")

    def test_populations_and_provenance(self):
        svg, rows, digest = bridge.parse_source(self.raw)
        self.assertEqual(len(rows), 5)
        self.assertEqual(len(set(x["id"] for x in rows)), 5)
        self.assertEqual([x["label"] for x in rows], list(bridge.LABELS))
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(), digest)
        self.assertEqual(svg.count("data-bridge-id="), 5)
        self.assertIn('viewBox="0 0 1200 360"', svg)

    def test_all_real_source_lines_and_github_routes(self):
        _, rows, _ = bridge.parse_source(self.raw)
        lines = self.raw.decode("utf-8").splitlines()
        for row in rows:
            self.assertIn('<rect class="box"', lines[row["source_line"] - 1])
            self.assertIn("#L" + str(row["source_line"]), row["source_href"])
            self.assertIn(bridge.SOURCE_REF, row["source_href"])

    def test_normalized_geometry_is_valid(self):
        _, rows, _ = bridge.parse_source(self.raw)
        for row in rows:
            x0, y0, x1, y1 = row["normalized_bbox"]
            self.assertLess(x0, x1)
            self.assertLess(y0, y1)
            self.assertTrue(all(0 <= v <= 1 for v in (x0, y0, x1, y1)))

    def test_source_change_is_explicitly_stale(self):
        changed = self.raw.replace(b"MissionControl SSOT", b"MissionControl V2 SSOT")
        with self.assertRaisesRegex(ValueError, "SOURCE_BLOB_DRIFT"):
            bridge.parse_source(changed)

    def test_semantic_label_mutation_fails_even_with_rebind(self):
        changed = self.raw.replace(b"MissionControl SSOT", b"MissionControl V2 SSOT")
        with self.assertRaisesRegex(ValueError, "SEMANTIC_LABEL_DRIFT"):
            self.mutated(changed)

    def test_new_script_is_not_allowed_as_source(self):
        changed = self.raw.replace(b"</svg>", b'<script>alert(1)</script></svg>')
        with self.assertRaisesRegex(ValueError, "ACTIVE_OR_REMOTE_SVG"):
            self.mutated(changed)

    def test_remote_resource_and_inline_event_fail(self):
        for fragment in (b'<image href="https://invalid.example/x.png" />',
                         b'<rect onclick="alert(1)" />'):
            with self.subTest(fragment=fragment), self.assertRaisesRegex(
                    ValueError, "ACTIVE_OR_REMOTE_SVG|ACTIVE_SVG_ATTRIBUTE"):
                self.mutated(self.raw.replace(b"</svg>", fragment + b"</svg>"))

    def test_extra_render_box_or_flow_cannot_silently_pass(self):
        box = b'<rect class="box" x="1" y="1" width="10" height="10"/>'
        with self.assertRaisesRegex(ValueError, "NODE_POPULATION"):
            self.mutated(self.raw.replace(b"</svg>", box + b"</svg>"))

    def test_out_of_bounds_coordinates_fail_after_source_rebind(self):
        changed = self.raw.replace(b'width="230" height="90"', b'width="1230" height="90"', 1)
        with self.assertRaisesRegex(ValueError, "OUT_OF_BOUNDS_RECT"):
            self.mutated(changed)

    def test_invalid_viewbox_is_not_guessable(self):
        changed = self.raw.replace(b'viewBox="0 0 1200 360"', b'viewBox="0 0 1200 0"')
        with self.assertRaisesRegex(ValueError, "VIEWBOX_MISMATCH"):
            self.mutated(changed)

    def test_deterministic_output_and_sidecar_sha(self):
        h1, m1 = bridge.project(self.raw)
        h2, m2 = bridge.project(self.raw)
        self.assertEqual((h1, m1), (h2, m2))
        j = json.loads(m1)
        self.assertEqual(j["output"]["sha256"], hashlib.sha256(h1).hexdigest())
        self.assertEqual(j["source"]["sha256"], hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(j["node_count"], 5)
        self.assertEqual(j["flow_path_count"], 6)
        self.assertFalse(j["authority_transfer"])
        self.assertFalse(j["merge_authorized"])
        self.assertFalse(j["execution"])
        self.assertEqual(j["pdf_mapping"], "UNMAPPED_NO_VERIFIED_BINARY")

    def test_html_has_only_local_inline_scripts_and_review_links(self):
        html = bridge.project(self.raw)[0].decode("utf-8")
        self.assertIn("Content-Security-Policy", html)
        self.assertIn("connect-src 'none'", html)
        self.assertNotIn("<script src=", html)
        self.assertIn('id="zoom-in"', html)
        self.assertIn('id="toggle-flows"', html)
        self.assertIn('id="toggle-labels"', html)
        self.assertIn("UNMAPPED: no verified source object", html)
        self.assertIn('document.getElementById("source-link").removeAttribute("href")', html)
        self.assertIn('buttons.forEach(b=>b.setAttribute("aria-pressed","false"))', html)
        self.assertIn("document.getElementById", html)
        self.assertIn("source-node-", html)
        self.assertIn('id="drawing"', html)

    def test_output_artifacts_match_the_generator_when_built(self):
        if not bridge.OUT.exists() or not bridge.MANIFEST.exists():
            self.skipTest("Generate first with svg_bridge.py; native CI invokes generator before suite")
        h, m = bridge.project(self.raw)
        self.assertEqual(bridge.OUT.read_bytes(), h)
        self.assertEqual(bridge.MANIFEST.read_bytes(), m)


if __name__ == "__main__":
    main(verbosity=2)
