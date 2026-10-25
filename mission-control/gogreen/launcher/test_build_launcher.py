"""GoGreen launcher: committed outputs current, verbatim reads, no coercion, safe render."""
import importlib.util
import json
import posixpath
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_launcher as bl  # noqa: E402


class Pick(unittest.TestCase):
    def test_dotted_path_and_missing(self):
        doc = {"a": {"b": 3, "n": None}}
        self.assertEqual(bl.pick(doc, "a.b"), (3, True))
        self.assertEqual(bl.pick(doc, "a.n"), (None, True))
        self.assertEqual(bl.pick(doc, "a.zz"), (None, False))
        self.assertEqual(bl.pick(doc, "a.b.c"), (None, False))

    def test_unknown_is_not_zero(self):
        value, found = bl.pick({"metrics": {"cov": None}}, "metrics.cov")
        self.assertIsNone(value)
        self.assertTrue(found)

    def test_list_mapping_and_csv_root(self):
        doc = {"repos": [{"r": "x", "g": {"p": 1}}, {"r": "y", "g": {}}]}
        self.assertEqual(bl.pick(doc, "repos[].r"), (["x", "y"], True))
        self.assertEqual(bl.pick(doc, "repos[].g.p"), ([1, None], True))
        self.assertEqual(bl.pick(doc, "nope[].r"), (None, False))
        rows = bl.parse("q.csv", "id,status\nJ1,DONE\n")
        self.assertEqual(bl.pick(rows, "[]"), ([{"id": "J1", "status": "DONE"}], True))

    def test_mapping_entries_keep_owner_order_and_values(self):
        doc = {"repos": {"GBOGEB/B": {"mode": "EVERRED"}, "GBOGEB/A": {"mode": None}}}
        entries, found = bl.pick(doc, "repos{}")
        self.assertTrue(found)
        self.assertEqual([e["key"] for e in entries], ["GBOGEB/B", "GBOGEB/A"])
        self.assertEqual(bl.pick(doc, "repos{}.value.mode"), (["EVERRED", None], True))
        self.assertEqual(bl.pick(doc, "nope{}"), (None, False))
        self.assertEqual(bl.pick({"repos": [1]}, "repos{}"), (None, False))


class Committed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snap = json.loads(bl.SNAPSHOT.read_text(encoding="utf-8"))
        cls.spec = json.loads(bl.SOURCES.read_text(encoding="utf-8"))

    def test_outputs_current_at_head(self):
        sha = bl.git("rev-parse", "HEAD^{commit}").strip()
        self.assertEqual(bl.check(sha), [])

    def test_contract(self):
        s = self.snap
        self.assertEqual(s["schema"], bl.SCHEMA)
        self.assertIs(s["computes_metrics"], False)
        self.assertRegex(s["source_sha"], r"^[0-9a-f]{40}$")
        self.assertEqual(s["missing_fields"], [])
        self.assertEqual([t["id"] for t in s["tiles"]], [t["id"] for t in self.spec["tiles"]])

    def test_every_tile_names_an_owner_or_is_unresolved(self):
        for t in self.snap["tiles"]:
            with self.subTest(tile=t["id"]):
                if "unresolved" in t:
                    self.assertNotIn("headline", t)
                    self.assertNotIn("fields", t)
                else:
                    self.assertTrue(t["owner"])
                    self.assertRegex(t["input_oid"], r"^[0-9a-f]{40}$")
                    self.assertEqual(self.snap["inputs"][t["input"]], t["input_oid"])

    def test_values_are_verbatim_owner_values(self):
        # Read by recorded blob OID: CI's shallow clone may not hold the build commit.
        for t in self.snap["tiles"]:
            if "input" not in t:
                continue
            doc = bl.parse(t["input"], bl.git("cat-file", "blob", t["input_oid"]))
            for f in t["fields"] + ([t["headline"]] if "headline" in t else []):
                with self.subTest(tile=t["id"], path=f["path"]):
                    self.assertEqual(f["value"], bl.pick(doc, f["path"])[0])

    def test_page_links_resolve_inside_repo(self):
        for p in self.snap["pages"]:
            with self.subTest(page=p["path"]):
                self.assertNotIn("oid", p)  # linked pages are navigation, not inputs
                self.assertTrue(p["title"])
                self.assertEqual(posixpath.normpath(posixpath.join(bl.SELF_DIR, p["href"])), p["path"])

    def test_discover_lists_every_committed_html_page_once(self):
        found = [p["path"] for p in self.snap["discover"]]
        self.assertEqual(len(found), len(set(found)))
        self.assertIn(bl.SELF_DIR + "/index.html", found)
        for p in self.spec["pages"]:
            self.assertIn(p["path"], found)
        for p in self.snap["discover"]:
            with self.subTest(page=p["path"]):
                self.assertTrue(p["title"])
                self.assertNotIn("&amp;", p["title"])  # titles are unescaped once, escaped at render
                self.assertEqual(posixpath.normpath(posixpath.join(bl.SELF_DIR, p["href"])), p["path"])

    def test_access_block_is_declared_not_probed(self):
        a = self.snap["access"]
        self.assertEqual(a, self.spec["access"])
        self.assertTrue(a["clone_url"].startswith(self.snap["repo_url"]))
        self.assertIn("J03", a["pages_note"])  # hosting is qualified by its owner, not here


class Render(unittest.TestCase):
    def test_page_passes_static_html_contract(self):
        # Reuse the html_qa owner's static contract (AGENTS.md L4) instead of re-checking here.
        path = HERE.parents[1] / "html_qa" / "html_contract.py"
        spec = importlib.util.spec_from_file_location("html_contract", path)
        contract = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(contract)
        snap = json.loads(bl.SNAPSHOT.read_text(encoding="utf-8"))
        result = contract.inspect(bl.render(snap), base_dir=HERE, strict_local=True)
        self.assertEqual(result["errors"], [])

    def test_page_is_self_contained(self):
        html = bl.TEMPLATE.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"<script[^>]+src=", html, re.I))
        self.assertIsNone(re.search(r"<link[^>]+stylesheet", html, re.I))
        self.assertIn("default-src 'none'", html)
        self.assertEqual(html.count(bl.DATA_HOLE), 1)

    def test_data_cannot_close_the_script(self):
        snap = {"x": "</script><img src=x onerror=alert(1)>&"}
        out = bl.render(snap)
        self.assertNotIn("</script><img", out)
        self.assertIn("\\u003c/script\\u003e", out)


class Stale(unittest.TestCase):
    def test_changed_input_oid_is_reported(self):
        snap = json.loads(bl.SNAPSHOT.read_text(encoding="utf-8"))
        first = sorted(snap["inputs"])[0]
        snap["inputs"][first] = "0" * 40
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "launcher.json"
            fake.write_text(bl.dump(snap), encoding="utf-8")
            with mock.patch.object(bl, "SNAPSHOT", fake):
                problems = bl.check(bl.git("rev-parse", "HEAD^{commit}").strip())
        self.assertTrue(any(first in p for p in problems), problems)

    def _check_with_page(self, transform):
        """check(HEAD) with the first linked page's text passed through ``transform``."""
        target = json.loads(bl.SOURCES.read_text(encoding="utf-8"))["pages"][0]["path"]
        real = bl.read_at

        def fake(sha, path):
            oid, text = real(sha, path)
            return (("f" * 40, transform(text)) if path == target else (oid, text))

        with mock.patch.object(bl, "read_at", fake):
            return target, bl.check(bl.git("rev-parse", "HEAD^{commit}").strip())

    def test_regenerated_page_with_same_title_is_not_stale(self):
        _, problems = self._check_with_page(lambda t: t + "\n<!-- regenerated -->\n")
        self.assertEqual(problems, [])

    def test_changed_page_title_is_named(self):
        target, problems = self._check_with_page(
            lambda t: bl.TITLE.sub("<title>Renamed page</title>", t, count=1))
        self.assertTrue(any("changed pages: " + target in p for p in problems), problems)
        self.assertFalse(any("sources.json" in p for p in problems), problems)

    def test_stale_reason_names_inputs_and_pages(self):
        old = {"inputs": {"a.json": "1", "b.json": "2"}, "pages": [{"path": "x.html", "title": "X"}]}
        new = {"inputs": {"a.json": "1", "b.json": "3"}, "pages": [{"path": "x.html", "title": "Y"}]}
        self.assertEqual(bl.stale_reason(old, new), "changed inputs: b.json; changed pages: x.html")
        self.assertIn("declarations", bl.stale_reason(old, old))

    def test_stale_reason_names_discovered_pages(self):
        old = {"inputs": {}, "pages": [], "discover": [{"path": "a.html", "title": "A"}]}
        new = {"inputs": {}, "pages": [], "discover": [{"path": "a.html", "title": "A"}, {"path": "b.html", "title": "B"}]}
        self.assertEqual(bl.stale_reason(old, new), "changed discovered pages: b.html")

    def test_pulse_fields_alone_are_not_stale(self):
        snap = json.loads(bl.SNAPSHOT.read_text(encoding="utf-8"))
        snap["source_sha"], snap["source_date"] = "f" * 40, "2000-01-01T00:00:00+00:00"
        with tempfile.TemporaryDirectory() as tmp:
            fake, page = Path(tmp) / "launcher.json", Path(tmp) / "index.html"
            fake.write_text(bl.dump(snap), encoding="utf-8")
            page.write_text(bl.render(snap), encoding="utf-8")
            with mock.patch.object(bl, "SNAPSHOT", fake), mock.patch.object(bl, "PAGE", page):
                self.assertEqual(bl.check(bl.git("rev-parse", "HEAD^{commit}").strip()), [])


if __name__ == "__main__":
    unittest.main()
