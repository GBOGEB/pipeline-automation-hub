"""Integrity checks for the user-facing, source-driven projection."""

import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("atlas_renderer_under_test", Path(__file__).with_name("render.py"))
RENDERER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RENDERER)


class RendererIntegrity(unittest.TestCase):
    def build(self, model):
        with tempfile.TemporaryDirectory() as directory:
            paths = RENDERER.render(model, Path(directory))
            self.assertEqual(paths, ["index.html", "style.css", "app.js"])
            return {path: (Path(directory) / path).read_text(encoding="utf-8") for path in paths}

    def test_unknown_source_and_capacity_are_not_promoted_to_zero(self):
        result = self.build({"source": {"dirty": None}, "inventory": {}, "broker": {}})["index.html"]
        self.assertIn("TREE STATE UNKNOWN", result)
        self.assertIn("Queue depth</span><strong>UNKNOWN", result)
        self.assertIn("Active workers</span><strong>UNKNOWN", result)
        self.assertNotIn("<strong>0</strong><small>workers", result)

    def test_untrusted_strings_remain_text_and_payload_roundtrips(self):
        attack = '</script><img src=x onerror="alert(1)">'
        model = {"title": attack, "source": {"repository": attack}, "blocks": [{"id": attack}], "graphs": []}
        markup = self.build(model)["index.html"]
        self.assertNotIn(attack, markup)
        self.assertIn("&lt;/script&gt;", markup)
        payload = re.search(r'<script id="source-model" type="application/json">(.*?)</script>', markup, re.S).group(1)
        self.assertEqual(json.loads(payload), model)

    def test_unknown_status_cannot_inherit_verified_colour(self):
        self.assertIn("badge unknown", RENDERER._badge("NOT_VERIFIED"))
        self.assertIn("badge unknown", RENDERER._badge("UNVERIFIED"))
        self.assertIn("badge passed", RENDERER._badge("HISTORICAL_PASS"))

    def test_unsafe_links_are_not_clickable(self):
        for value in ("javascript:alert(1)", "data:text/html,test", "//evil.test/a", "https:\\evil.test", "https://ok.test\n.evil.test"):
            self.assertIsNone(RENDERER._link(value), value)
        self.assertEqual(RENDERER._link("graphs/dag.svg"), "graphs/dag.svg")

    def test_cohort_units_and_invalid_denominators_remain_visible(self):
        model = {"burndown": {"cohorts": [
            {"id": "statements", "label": "One module", "done": 8, "eligible": 10, "unit": "statements", "open": 2},
            {"id": "jobs", "label": "Workflow jobs", "done": 7, "eligible": 3, "unit": "jobs"},
            {"id": "unknown", "done": None, "eligible": None, "unit": "native receipts"},
        ]}}
        result = self.build(model)["index.html"]
        self.assertIn("80.00%", result)
        self.assertIn("INVALID · done exceeds eligible", result)
        self.assertIn("Completed / eligible · statements", result)
        self.assertIn("Completed / eligible · jobs", result)
        self.assertIn("Completed / eligible · native receipts", result)
        self.assertEqual(result.count("<progress "), 1)

    def test_spline_breaks_on_null_and_noncomparable_denominator(self):
        result = RENDERER._cohort_trend({"label": "Scope A", "eligible": 10, "series": [
            {"label": "N1", "open": 8, "comparable": True},
            {"label": "N2", "open": 6, "comparable": True},
            {"label": "N3", "open": None, "comparable": True},
            {"label": "N4", "open": 3, "comparable": True},
            {"label": "N5", "open": 2, "comparable": True, "eligible": 11},
            {"label": "N6", "open": 1},
        ]})
        self.assertEqual(result.count('class="trend-line"'), 1)
        self.assertIn("N3 · UNKNOWN", result)

    def test_remote_plan_preserves_unknown_and_known_zero(self):
        result = self.build({"broker": {"remote": {"queued": 0, "running": None, "worker_slots": None, "status": "UNKNOWN"}, "local_bounds": {"workers": 2, "max_pending": 4}}})["index.html"]
        self.assertIn("Remote queue length</span><strong>0", result)
        self.assertIn("Remote running jobs</span><strong>UNKNOWN", result)
        self.assertIn("Remote pool capacity</span><strong>UNKNOWN", result)

    def test_deterministic_assets_and_no_runtime_network_dependencies(self):
        model = {"source": {"head_sha": "a" * 40}, "title": "Atlas"}
        first, second = self.build(model), self.build(model)
        self.assertEqual(first, second)
        self.assertNotRegex(first["index.html"], r'<script[^>]+src="https?://')
        self.assertNotRegex(first["style.css"], r"@import|url\(['\"]?https?://")
        self.assertNotRegex(first["app.js"], r"\bfetch\s*\(|XMLHttpRequest|WebSocket")

    def test_coverage_qualification_and_missing_module_measurements_are_explicit(self):
        result = self.build({"coverage": {"portfolio": {"qualification": "NOT_QUALIFIED", "statement_pct": None, "branch_pct": None}, "rows": [
            {"id": "historical", "label": "Historical cohort", "repository": "owner/repo", "qualification": "ATTACHMENT_REPORTED_NOT_INDEPENDENTLY_VERIFIED",
             "eligible_modules": 15, "instrumented_modules": None, "zero_covered_modules": None, "unmeasured_modules": None,
             "statements": {"covered": 8, "eligible": 10, "pct": 80, "remaining": 2}, "branches": {"covered": 0, "eligible": 0, "pct": None, "classification": "BRANCHLESS_NOT_APPLICABLE"}}
        ]}})["index.html"]
        self.assertIn("NOT QUALIFIED", result)
        self.assertIn("Eligible: 15<br>Instrumented: UNKNOWN<br>Zero: UNKNOWN<br>Unmeasured: UNKNOWN", result)
        self.assertIn("BRANCHLESS_NOT_APPLICABLE", result)
        self.assertNotIn("10 / 15", result)
        self.assertIn("ATTACHMENT_REPORTED_NOT_INDEPENDENTLY_VERIFIED", result)


if __name__ == "__main__":
    unittest.main()


def test_zz_canary_g_pah():
    assert False, "red canary: proves CI collects this family"
