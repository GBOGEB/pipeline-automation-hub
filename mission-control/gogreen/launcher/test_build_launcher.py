"""GoGreen launcher: committed outputs current, verbatim reads, no coercion, safe render."""
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
                self.assertRegex(p["oid"], r"^[0-9a-f]{40}$")
                self.assertEqual(posixpath.normpath(posixpath.join(bl.SELF_DIR, p["href"])), p["path"])


class Render(unittest.TestCase):
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
