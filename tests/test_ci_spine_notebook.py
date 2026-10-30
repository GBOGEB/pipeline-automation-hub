"""Read-only Jacquard-inspired notebook: structural, source and security negatives."""
import copy
import hashlib
import importlib.util
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/ci_spine_notebook.py"
spec = importlib.util.spec_from_file_location("ci_spine_notebook_tested", MODULE)
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)


class Notebook(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph, cls.runs, cls.gdigest, cls.rdigest = M.load_sources(ROOT)
        cls.text = (ROOT / M.GRAPH).read_text(encoding="utf-8")

    def proj(self, graph=None, runs=None, text=None, source_ref=M.INPUT_REF):
        return M.project(graph if graph is not None else copy.deepcopy(self.graph),
                         runs if runs is not None else copy.deepcopy(self.runs),
                         graph_digest=self.gdigest, runs_digest=self.rdigest,
                         graph_text=self.text if text is None else text,
                         source_ref=source_ref)

    def test_exhaustive_bundle_and_clock_source_populations(self):
        p = self.proj()
        self.assertEqual(p["schema"], M.SCHEMA)
        self.assertEqual([n["short_id"] for n in p["nodes"]],
                         ["B%02d" % i for i in range(10)])
        self.assertEqual(len(p["edges"]), 17)
        self.assertEqual(len(p["timings"]), sum(len(r["jobs"]) for r in self.runs["runs"]))
        self.assertEqual(p["sources"]["graph_sha256"], hashlib.sha256(
            (ROOT / M.GRAPH).read_bytes()).hexdigest())
        self.assertEqual(p["sources"]["timing_sha256"], hashlib.sha256(
            (ROOT / M.RUNS).read_bytes()).hexdigest())

    def test_governance_separation_is_noncompensating(self):
        p = self.proj()
        self.assertEqual(p["assurance"]["merge_admission"], "HOLD")
        self.assertEqual(p["assurance"]["pdf_location_mapping"], "UNAVAILABLE")
        self.assertIs(p["assurance"]["run_dispatch"], False)
        self.assertIs(p["assurance"]["authority_transfer"], False)
        self.assertTrue(p["assurance"]["not_live"])
        self.assertTrue(all(n["source_class"] == "PROPOSED_DESIGN" for n in p["nodes"]))

    def test_bidirectional_html_json_pointers_are_exact(self):
        p = self.proj()
        for i, n in enumerate(p["nodes"]):
            pointer = n["source_pointer"]
            self.assertEqual(pointer["pointer"], "/nodes/%d" % i)
            self.assertEqual(pointer["stable_view_anchor"], "#bundle=" + n["short_id"])
            self.assertEqual(pointer["line"], M.safe_lines(self.text, n["short_id"]))
            self.assertIn(M.INPUT_REF, pointer["href"])
            self.assertEqual(pointer["mapping_accuracy"],
                             "EXACT_FILE_AND_JSON_MEMBER_NOT_PDF_COORDINATES")

    def test_only_next_pulse_feedback_and_dag_acyclic(self):
        p = self.proj()
        feedback = [e for e in p["edges"] if e["kind"] == "FEEDBACK_NEXT_PULSE"]
        self.assertEqual(len(feedback), 1)
        self.assertEqual(feedback[0]["from"], "ci-spine:bundle:B09")
        self.assertEqual(feedback[0]["to"], "ci-spine:bundle:B00")
        self.assertGreater(p["nodes"][7]["layer"], p["nodes"][0]["layer"])

    def test_rejects_same_pulse_cycle(self):
        d = copy.deepcopy(self.graph)
        d["edges"][15] = {"from": "ci-spine:bundle:B07",
                           "to": "ci-spine:bundle:B00", "kind": "FEEDFORWARD"}
        with self.assertRaisesRegex(ValueError, "WITHIN_PULSE_CYCLE"):
            self.proj(graph=d)

    def test_duplicate_or_dangling_nodes_fail(self):
        d = copy.deepcopy(self.graph)
        d["nodes"][1]["id"] = d["nodes"][0]["id"]
        with self.assertRaisesRegex(ValueError, "NODE_ID_BINDING|DUPLICATE_NODE_ID"):
            self.proj(graph=d)
        d = copy.deepcopy(self.graph)
        d["edges"][0]["to"] = "missing"
        with self.assertRaisesRegex(ValueError, "DANGLING_EDGE"):
            self.proj(graph=d)

    def test_fabricated_pdf_or_authority_promotion_fails(self):
        d = copy.deepcopy(self.graph)
        d["nodes"][0]["source_class"] = "ACCEPTED"
        with self.assertRaisesRegex(ValueError, "ILLEGAL_AUTHORITY_PROMOTION"):
            self.proj(graph=d)
        d = copy.deepcopy(self.graph)
        d["record_type"] = "authoritative_runner"
        with self.assertRaisesRegex(ValueError, "DAG_AUTHORITY_BOUNDARY"):
            self.proj(graph=d)

    def test_rejects_unsafe_workflow_binding(self):
        d = copy.deepcopy(self.graph)
        d["nodes"][0]["example_workflow"] = "../../secrets.yml"
        with self.assertRaisesRegex(ValueError, "UNSAFE_WORKFLOW_LINK"):
            self.proj(graph=d)

    def test_rejects_broken_sample_and_unknown_clock_fabrication(self):
        d = copy.deepcopy(self.runs)
        d["sample_count"] -= 1
        with self.assertRaisesRegex(ValueError, "RUN_POPULATION"):
            self.proj(runs=d)
        d = copy.deepcopy(self.runs)
        d["runs"][0]["jobs"][0]["execution_seconds"] = -5
        with self.assertRaisesRegex(ValueError, "EXECUTION_CLOCK"):
            self.proj(runs=d)
        d = copy.deepcopy(self.runs)
        d["runs"][0]["source_sha"] = "not-sha"
        with self.assertRaisesRegex(ValueError, "RUN_SOURCE_SHA"):
            self.proj(runs=d)

    def test_source_line_mapping_requires_one_unique_reference(self):
        with self.assertRaisesRegex(ValueError, "SOURCE_ANCHOR_NOT_UNIQUE"):
            M.safe_lines("", "B00")
        with self.assertRaisesRegex(ValueError, "SOURCE_ANCHOR_NOT_UNIQUE"):
            M.safe_lines('"short_id": "B00"\n"short_id": "B00"', "B00")

    def test_source_ref_must_be_exact_hash(self):
        with self.assertRaisesRegex(ValueError, "INVALID_SOURCE_REF"):
            self.proj(source_ref="master")

    def test_untrusted_script_text_is_json_escaped(self):
        p = self.proj()
        p["nodes"][0]["description"] = '</script><script>alert("unsafe")</script>&'
        output = M.render('<script type="application/json">' + M.PLACEHOLDER + '</script>', p)
        self.assertNotIn('</script><script>', output)
        self.assertNotIn('&', output)
        self.assertIn('\\u003c', output)

    def test_rejects_template_missing_or_duplicate_slot(self):
        for value in ("abc", M.PLACEHOLDER + M.PLACEHOLDER):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "TEMPLATE_SLOT"):
                M.render(value, self.proj())

    def test_source_bound_page_parity_cli(self):
        self.assertEqual(M.main(["--root", str(ROOT), "--check"]), 0)
        html = (ROOT / M.OUTPUT).read_text(encoding="utf-8")
        self.assertIn('id="map"', html)
        self.assertIn('id="view-sipoc"', html)
        self.assertIn('id="view-timing"', html)
        self.assertIn('id="view-document"', html)
        self.assertIn('id="view-compendium"', html)
        self.assertNotIn(M.PLACEHOLDER, html)
        self.assertNotIn("<script src=", html)
        self.assertNotIn("fetch(", html)

    def temp_copy(self):
        d = tempfile.TemporaryDirectory()
        root = Path(d.name)
        for p in (M.GRAPH, M.RUNS, M.TEMPLATE, M.OUTPUT):
            dst = root / p
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / p, dst)
        return d, root

    def test_tampered_json_page_fails_check(self):
        d, root = self.temp_copy()
        self.addCleanup(d.cleanup)
        target = root / M.OUTPUT
        target.write_text(target.read_text(encoding="utf-8").replace(
            '"merge_admission":"HOLD"', '"merge_admission":"PASS"', 1),
            encoding="utf-8")
        self.assertEqual(M.main(["--root", str(root), "--check"]), 1)

    def test_raw_html_injection_into_json_is_rejected(self):
        d, root = self.temp_copy()
        self.addCleanup(d.cleanup)
        target = root / M.OUTPUT
        content = target.read_text(encoding="utf-8").replace(
            '"merge_admission":"HOLD"', '"merge_admission":"<img src=x>"', 1)
        target.write_text(content, encoding="utf-8")
        self.assertEqual(M.main(["--root", str(root), "--check"]), 1)

    def test_dom_sourced_urls_never_reach_href_unvalidated(self):
        # CodeQL js/xss-through-dom (#66/#67): payload JSON is DOM text, so every
        # href assignment must go through the integer run builder or blob-prefix guard.
        template = (ROOT / M.TEMPLATE).read_text(encoding="utf-8")
        self.assertNotIn("a.href=t.url", template)
        self.assertEqual(sorted(re.findall(r"\.href=(\w+)", template)), ["h", "rh"])
        self.assertIn('const GH="https://github.com/' + M.REPO + '/";', template)
        p = self.proj()
        for n in p["nodes"]:
            for href in (n["source_pointer"]["href"], n["workflow_href"]):
                self.assertTrue(href.startswith("https://github.com/" + M.REPO + "/blob/"))
                self.assertIsNone(re.search(r"[\s\"'<>\\]", href))

    def test_render_is_deterministic_and_no_external_data_fetch(self):
        first, second = M.build(ROOT), M.build(ROOT)
        self.assertEqual(first, second)
        self.assertNotIn(M.PLACEHOLDER, first)
        self.assertNotIn("<script src=", first)
        self.assertNotIn("fetch(", first)
        self.assertNotIn("XMLHttpRequest", first)


if __name__ == "__main__":
    unittest.main()
