"""N2 source-bound HTML flightdeck static and tamper tests (stdlib only)."""
from __future__ import annotations
import copy
import hashlib
from html.parser import HTMLParser
import json
import tempfile
import unittest
from pathlib import Path
import build_view as V

SHA = "a" * 40
BLOB = "b" * 40


def owner():
    return {
        "schema": V.OWNER_SCHEMA,
        "authority_transfer": False,
        "merge_admission": "HOLD",
        "dispatch_authorized": False,
        "cohort_id": "REAL-DEFAULT-HEADS-THREE-PUBLIC-REPOS",
        "red_metrics": {"window_pulses": 4, "ever_red_in_window": 6,
                        "red_burndown": -2, "recovery_rate": 0.25,
                        "regression_rate": 0},
        "source_bound_breadth": {"observed": 3, "eligible": 12,
                                 "canonical_six_repo_42_cell_credit": None},
        "dock_consistency": {"state": "CONSISTENT_WHERE_OBSERVED"},
        "shadow_proposals": {"regime": "CONGESTED_HOLD"},
        "docks": {"issue_bd": {"private_qps_open_issues": 999999,
                                "raw_private_title": "SECRET_FIXTURE_MARKER"}},
    }


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = {}
        self.attrs = []
    def handle_starttag(self, tag, attrs):
        self.tags[tag] = self.tags.get(tag, 0) + 1
        self.attrs.append((tag, dict(attrs)))


class Contract(unittest.TestCase):
    def test_owner_fields_verbatim_and_no_private_docks(self):
        src = owner()
        view = V.project(src, SHA, BLOB)
        self.assertEqual(view["classification"], "HISTORICAL_SOURCE_BOUND_READONLY_VIEW")
        self.assertIsNone(view["fresh_authenticated_42_cell_breadth"])
        self.assertEqual(view["merge_admission"], "HOLD")
        metrics = {x["id"]: x for x in view["fields"]}
        self.assertEqual(metrics["observed"]["value"], 3)
        self.assertEqual(metrics["eligible"]["value"], 12)
        self.assertEqual(metrics["regression_rate"]["value"], 0)
        self.assertEqual(metrics["regression_rate"]["state"], "OBSERVED")
        self.assertEqual(len(view["planning"]), 15)
        self.assertEqual(len({x["id"] for x in view["planning"]}), 15)
        raw = json.dumps(view)
        self.assertNotIn("SECRET_FIXTURE_MARKER", raw)
        self.assertNotIn("private_qps_open_issues", raw)
        self.assertNotIn("999999", raw)

    def test_missing_is_unknown_not_zero(self):
        src = owner()
        src["red_metrics"].pop("recovery_rate")
        data = V.project(src, SHA, BLOB)
        recovery = next(x for x in data["fields"] if x["id"] == "recovery_rate")
        self.assertEqual(recovery["state"], "UNKNOWN")
        self.assertIsNone(recovery["value"])
        page = V.render(data)
        self.assertIn("UNKNOWN", page)

    def test_reject_spoofed_source_authority(self):
        for patch in ({"merge_admission": "PASS"}, {"authority_transfer": True},
                      {"dispatch_authorized": True},
                      {"schema": "fabricated.owner"},
                      {"cohort_id": "SIX_REPO_CANONICAL_FRESH"}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                V.project({**owner(), **patch}, SHA, BLOB)

    def test_invalid_observed_population_rejected(self):
        src = owner()
        src["source_bound_breadth"]["observed"] = 13
        with self.assertRaisesRegex(ValueError, "observed population"):
            V.project(src, SHA, BLOB)

    def test_escape_untrusted_source_string_not_executable_html(self):
        src = owner()
        src["dock_consistency"]["state"] = "<script>alert('x')</script>"
        body = V.render(V.project(src, SHA, BLOB))
        self.assertNotIn("<script>", body)
        self.assertIn("&lt;script&gt;", body)
        self.assertIn("default-src 'none'", body)

    def test_semantic_page_structure_and_local_only_assets(self):
        page = V.render(V.project(owner(), SHA, BLOB))
        parser = Tags()
        parser.feed(page)
        self.assertEqual(parser.tags.get("h1"), 1)
        self.assertEqual(parser.tags.get("title"), 1)
        self.assertEqual(parser.tags.get("main"), 1)
        self.assertGreaterEqual(parser.tags.get("nav", 0), 1)
        self.assertGreaterEqual(parser.tags.get("article", 0), 9)
        self.assertEqual(parser.tags.get("details"), 1)
        self.assertIn('name="viewport"', page)
        self.assertIn("MIP-15", page)
        self.assertIn('id="source-sha"', page)
        self.assertNotIn('src="https://', page)
        self.assertNotIn("source authentication: PASS", page)

    def test_source_provenance_link_pinned_to_exact_commit(self):
        page = V.render(V.project(owner(), SHA, BLOB))
        self.assertIn(f"{V.REPO_URL}/blob/{SHA}/{V.SOURCE}", page)
        self.assertIn(f'<code id="source-sha">{SHA}</code>', page)
        self.assertIn(f'<code id="source-blob">{BLOB}</code>', page)

    def test_each_mip_row_displays_row_specific_navigation(self):
        snapshot = V.project(owner(), SHA, BLOB)
        page = V.render(snapshot)
        self.assertIn("<th>Source / PR links</th>", page)
        for number in (881, 882, 530, 531, 533):
            self.assertIn(f'href="{V.REPO_URL}/pull/{number}"', page)
        self.assertEqual(page.count("<tr><th scope='row'>"), 15)
        self.assertIn("ABACUS / CODEX", page)

    def test_navigation_html_cannot_inject_active_elements_or_urls(self):
        p = V.navigation_markup("<img src=x onerror=alert(1)> #881")
        self.assertNotIn("<img", p)
        self.assertIn("&lt;img", p)
        self.assertIn(f'href="{V.REPO_URL}/pull/881"', p)
        with self.assertRaises(ValueError):
            V.navigation_markup(None)

    def test_actual_repository_generation_has_hash_manifest(self):
        with tempfile.TemporaryDirectory() as path:
            out = Path(path)
            manifest = V.build("HEAD", out)
            html_bytes = (out / "index.html").read_bytes()
            json_bytes = (out / "snapshot.json").read_bytes()
            snap = json.loads(json_bytes)
            self.assertEqual(manifest["source_sha"], V.git("rev-parse", "HEAD^{commit}"))
            self.assertEqual(manifest["sha256"]["index.html"],
                             hashlib.sha256(html_bytes).hexdigest())
            self.assertEqual(manifest["sha256"]["snapshot.json"],
                             hashlib.sha256(json_bytes).hexdigest())
            self.assertEqual(snap["source"]["blob_oid"], manifest["source_blob_oid"])
            self.assertEqual(snap["merge_admission"], "HOLD")
            self.assertFalse(snap["published_pages_verified"])
            self.assertEqual(manifest["hosted_qa"], "DEFER")
            self.assertNotIn(b"private_qps_open_issues", html_bytes)
            self.assertNotIn(b"SECRET_FIXTURE_MARKER", html_bytes)


if __name__ == "__main__":
    unittest.main()
