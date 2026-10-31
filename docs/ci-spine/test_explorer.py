"""Source-bound, negative-first tests for the static Jacquard-inspired CI spine viewer.

No API reads, cache writes or changes to required checks.
"""
from __future__ import annotations
import copy
from html.parser import HTMLParser
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_explorer as explorer  # noqa: E402
import plotly_projection as plotly_companion  # noqa: E402


class InlineScriptReader(HTMLParser):
    """HTML-aware inline script collector; accepts legal end-tag whitespace."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.inline_scripts = []
        self.has_external_script = False
        self._in_script = False
        self._body = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "script":
            self.has_external_script |= bool(dict(attrs).get("src"))
            self._in_script = True
            self._body = []

    def handle_data(self, data):
        if self._in_script:
            self._body.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "script" and self._in_script:
            self.inline_scripts.append("".join(self._body))
            self._in_script = False


class ExplorerProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = explorer.load_sources()

    def project(self, index=None, replacement=None):
        sources = list(copy.deepcopy(self.sources))
        if index is not None:
            sources[index] = replacement
        return explorer.project(*sources)

    def test_exact_merged_source_boundaries_are_distinct(self):
        payload = self.project()
        self.assertEqual(payload["source"]["snapshot_head"],
                         "ca623ab83793df6edd245942884ad5428a5fe079")
        self.assertNotEqual(payload["source"]["snapshot_head"],
                            payload["source"]["main_head_at_readback"])
        self.assertEqual(payload["source"]["authority"], "ADVISORY_FROZEN_NOT_CURRENT_CI")

    def test_full_nonempty_bounded_populations(self):
        d = self.project()
        self.assertEqual((len(d["workflows"]), d["counts"]["test_named_files"],
                          len(d["nodes"]), len(d["edges"]), len(d["runs"])),
                         (182, 307, 10, 17, 8))
        self.assertEqual(d["counts"]["admission_ledger_entries"], 181)

    def test_all_aliases_remain_unapproved(self):
        d = self.project()
        self.assertTrue(all(x["alias_approved"] is False for x in d["workflows"]))
        self.assertIn("UNLISTED", {x["admission_snapshot"] for x in d["workflows"]})

    def test_all_edges_resolve_and_one_feedback_is_next_pulse_only(self):
        d = self.project()
        ids = {x["id"] for x in d["nodes"]}
        self.assertTrue(all(e["from"] in ids and e["to"] in ids for e in d["edges"]))
        self.assertEqual(sum(e["kind"] == "FEEDBACK_NEXT_PULSE" for e in d["edges"]), 1)

    def test_dag_rejects_dangling_edge(self):
        d = copy.deepcopy(self.sources[2])
        d["edges"][0]["to"] = "fake:missing"
        with self.assertRaisesRegex(ValueError, "EDGE_SET"):
            self.project(2, d)

    def test_dag_rejects_within_pulse_cycle(self):
        d = copy.deepcopy(self.sources[2])
        d["edges"][0]["from"] = "ci-spine:bundle:B08"
        d["edges"][0]["to"] = "ci-spine:bundle:B00"
        with self.assertRaisesRegex(ValueError, "DAG_CYCLE"):
            self.project(2, d)

    def test_dag_rejects_temporal_as_authority(self):
        d = copy.deepcopy(self.sources[2])
        feedback = next(e for e in d["edges"] if e["kind"] == "FEEDBACK_NEXT_PULSE")
        feedback["kind"] = "FEEDFORWARD"
        with self.assertRaisesRegex(ValueError, "TEMPORAL_BOUNDARY"):
            self.project(2, d)

    def test_stale_mismatched_source_is_rejected(self):
        d = copy.deepcopy(self.sources[4])
        d["source"]["catalog_snapshot_head"] = "f" * 40
        with self.assertRaisesRegex(ValueError, "SINGLE_SNAPSHOT_SOURCE"):
            self.project(4, d)

    def test_approved_alias_false_green_is_rejected(self):
        d = copy.deepcopy(self.sources[0])
        d["workflows"][0]["alias_approved"] = True
        with self.assertRaisesRegex(ValueError, "PROPOSED_ALIAS_ONLY"):
            self.project(0, d)

    def test_bad_blob_oid_rejected(self):
        d = copy.deepcopy(self.sources[0])
        d["workflows"][0]["blob_oid"] = "deadbeef"
        with self.assertRaisesRegex(ValueError, "SOURCE_BLOB_SHAPES"):
            self.project(0, d)

    def test_negative_job_clock_rejected(self):
        d = copy.deepcopy(self.sources[3])
        j = next(j for j in d["runs"][0]["jobs"] if j["started_at"] and j["completed_at"])
        j["execution_seconds"] = -30
        with self.assertRaisesRegex(ValueError, "NONNEGATIVE_JOB_CLOCK"):
            self.project(3, d)

    def test_sample_is_not_misrepresented_as_fleet(self):
        d = self.project()
        self.assertEqual({r["run_id"] for r in d["runs"]}.__len__(), 8)
        self.assertNotIn("fleet_success_rate", d)
        self.assertTrue(all(r["source_sha"] and r["attempt"] for r in d["runs"]))

    def test_malformed_input_is_not_a_safe_script_string(self):
        payload = {"source": "</script><script>alert(1)</script>", "other": "&<>", "note": "“quoted”"}
        safe = explorer.compact_json(payload)
        self.assertNotIn("</script>", safe)
        self.assertNotIn("<script>", safe)
        self.assertEqual(json.loads(safe), payload)

    def test_deterministic_output_matches_committed_html(self):
        html = explorer.render()
        self.assertEqual(html, explorer.OUTPUT.read_bytes())
        self.assertGreater(len(html), 100_000)
        self.assertNotIn(b"__SPINE_JSON__", html)
        self.assertIn(b"connect-src 'none'", html)
        self.assertIn(b"FROZEN", html)

    def test_no_external_scripts_or_dynamic_network(self):
        s = explorer.OUTPUT.read_text("utf-8")
        self.assertFalse(plotly_companion.external_scripts(s))
        self.assertIn("connect-src 'none'", s)
        self.assertIn("source_head", s)
        self.assertIn("JACQUARD_CROSSWALK.md", s)

    def test_keyboard_and_lens_navigation_code_present(self):
        s = explorer.OUTPUT.read_text("utf-8")
        for term in ('data-lens="graph"', 'data-lens="sipoc"',
                     'data-lens="catalog"', 'data-lens="timing"', 'data-lens="plan"',
                     'aria-label="DAG zoom"', 'addEventListener("keydown"',
                     'hashchange', 'XMLSerializer', 'window.print()'):
            self.assertIn(term, s)

    def test_pinned_mainline_not_falsely_stamped_current(self):
        s = explorer.OUTPUT.read_text("utf-8")
        self.assertIn("ca623ab83793df6edd245942884ad5428a5fe079", s)
        self.assertIn("6f7cf145c4ebf585dbb341ba5863e77098ad36b0", s)
        self.assertIn("older than merged PRs", s)

    def test_local_workstream_docs_do_not_point_to_old_catalog_commit(self):
        page = explorer.OUTPUT.read_text("utf-8")
        self.assertIn('String(x).startsWith("docs/ci-spine/")', page)
        self.assertIn('detailLink(x.slice("docs/ci-spine/".length),x)', page)
        # A live checkout-relative document is not a GitHub blob at the
        # historical test catalog head where that document did not exist.
        self.assertIn("JACQUARD_CROSSWALK.md", page)

    def test_unknown_queue_time_is_never_rendered_as_zero(self):
        page = explorer.OUTPUT.read_text("utf-8")
        self.assertIn("queueKnown=Number.isFinite(job?.queue_seconds)", page)
        self.assertIn('(queueKnown?q+"s":"UNKNOWN")+" queue', page)
        self.assertNotIn('time.textContent=q+"s queue', page)
        self.assertIn('Queue "+(queueKnown?q+" seconds":"UNKNOWN")', page)

    def test_plotly_inline_source_url_is_not_active_network_dependency(self):
        inline = "<html><script>const locationHint='https://cdn.plot.ly/plotly.min.js';</script></html>"
        self.assertFalse(plotly_companion.external_scripts(inline))

    def test_plotly_external_script_src_fails_closed(self):
        for doc in ('<script src="https://cdn.plot.ly/plotly.min.js"></script>',
                    "<script src='plotly.min.js'></script>"):
            with self.subTest(document=doc):
                self.assertTrue(plotly_companion.external_scripts(doc))

    def test_html_parser_handles_script_end_tag_whitespace(self):
        html = "<script>first</script ><script src='https://example.test/a.js'>second</script>"
        parser = InlineScriptReader()
        parser.feed(html)
        self.assertEqual(parser.inline_scripts, ["first", "second"])
        self.assertTrue(parser.has_external_script)
        self.assertTrue(plotly_companion.external_scripts(html))

    def test_hash_router_rejects_inherited_ids_and_restores_defaults(self):
        page = explorer.OUTPUT.read_text("utf-8")
        self.assertIn("const byId = Object.assign(Object.create(null),", page)
        self.assertIn('k==="bundle"&&Object.hasOwn(byId,id)', page)
        self.assertNotIn('k==="bundle"&&byId[id]', page)
        restore = page[page.index("function restore(){"):page.index("function setSelected(")]
        self.assertLess(restore.index("lens=DEFAULT_LENS;selected={...DEFAULT_SELECTED};"),
                        restore.index('if(["graph"'))

    def test_redraw_restores_keyboard_focus_by_stable_key(self):
        page = explorer.OUTPUT.read_text("utf-8")
        self.assertIn('b.dataset.focusKey="nav:"+kind+":"+id;', page)
        self.assertIn('"data-focus-key":"graph:bundle:"+n.short_id', page)
        refresh = page[page.index("function refresh("):page.index("function navItem(")]
        self.assertIn("const focusKey=document.activeElement?.dataset?.focusKey;", refresh)
        self.assertIn("t.focus({preventScroll:true})", refresh)

    def test_plotly_explorer_link_resolves_from_output_location(self):
        repo = HERE.parents[1]
        self.assertEqual(plotly_companion.explorer_href(repo / "ci-spine-plotly.html"),
                         "docs/ci-spine/explorer.html")
        self.assertEqual(plotly_companion.explorer_href(HERE / "chart.html"), "explorer.html")
        self.assertEqual(plotly_companion.explorer_href(HERE / "qa" / "plotly" / "c.html"),
                         "../../explorer.html")

    def test_plotly_unknown_queue_projects_but_negative_queue_fails_closed(self):
        source = json.loads(plotly_companion.DATA.read_text("utf-8"))
        original = plotly_companion.DATA
        try:
            for queue, ok in ((None, True), (-1, False), ("5", False)):
                with self.subTest(queue=queue), tempfile.TemporaryDirectory() as tmp:
                    doc = copy.deepcopy(source)
                    for job in doc["runs"][0]["jobs"]:
                        job["queue_seconds"] = queue
                    path = Path(tmp) / "timing.json"
                    path.write_text(json.dumps(doc), "utf-8")
                    plotly_companion.DATA = path
                    if ok:
                        self.assertIsNone(plotly_companion.rows()[0]["queue_seconds"])
                    else:
                        with self.assertRaisesRegex(ValueError, "PLOTLY_NEGATIVE_OR_MISSING_CLOCK_FIRST_RED"):
                            plotly_companion.rows()
        finally:
            plotly_companion.DATA = original

    def test_unknown_queue_inspector_is_not_null_seconds(self):
        page = explorer.OUTPUT.read_text("utf-8")
        self.assertIn('(Number.isFinite(j?.queue_seconds)?E(j.queue_seconds)+" seconds":"UNKNOWN")', page)
        self.assertNotIn('E(j?.queue_seconds)+" seconds"', page)

    @unittest.skipUnless(shutil.which("node"), "Node not installed; native browser QA must separately run")
    def test_inline_javascript_parses_in_node(self):
        html = explorer.OUTPUT.read_text("utf-8")
        parser = InlineScriptReader()
        parser.feed(html)
        self.assertFalse(parser.has_external_script)
        scripts = parser.inline_scripts
        self.assertEqual(len(scripts), 2)
        with tempfile.TemporaryDirectory() as d:
            js = Path(d) / "explorer.js"
            js.write_text(scripts[-1], "utf-8")
            proc = subprocess.run(["node", "--check", str(js)], capture_output=True,
                                  text=True, timeout=20)
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
