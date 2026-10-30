"""GoGreen launcher: committed outputs current, verbatim reads, no coercion, safe render."""
import importlib.util
import json
import posixpath
import re
import subprocess
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


class Catalog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snap = json.loads(bl.SNAPSHOT.read_text(encoding="utf-8"))
        cls.cat = cls.snap["catalog"]

    def _tree_rev(self):
        # CI checks out a shallow clone that may not hold the read-at commit; check() at HEAD
        # already proves the catalog matches HEAD, so fall back to HEAD only then.
        sha = self.snap["source_sha"]
        r = subprocess.run(["git", "cat-file", "-e", sha + "^{commit}"], cwd=bl.HERE, capture_output=True)
        return sha if r.returncode == 0 else "HEAD"

    def test_catalog_is_every_committed_html_page(self):
        paths = [e["path"] for e in self.cat]
        self.assertEqual(len(paths), len(set(paths)))
        self.assertEqual(sorted(paths), bl.html_paths(self._tree_rev()))
        self.assertGreater(len(paths), len(self.snap["pages"]))
        self.assertIn(bl.SELF_DIR + "/index.html", paths)

    def test_catalog_sorted_grouped_and_navigation_only(self):
        self.assertEqual(self.cat, sorted(self.cat, key=lambda e: (e["group"], e["path"])))
        for e in self.cat:
            with self.subTest(page=e["path"]):
                self.assertEqual(set(e), {"path", "group", "title", "href", "github"})
                self.assertEqual(e["group"], bl.group_of(e["path"]))
                self.assertTrue(e["path"].startswith(e["group"] + "/") or e["group"] == ".")
                self.assertTrue(e["title"])

    def test_catalog_href_resolves_to_path_inside_repo(self):
        for e in self.cat:
            with self.subTest(page=e["path"]):
                target = posixpath.normpath(posixpath.join(bl.SELF_DIR, e["href"]))
                self.assertEqual(target, e["path"])
                self.assertFalse(target.startswith(".."))

    def test_github_urls_from_repo_url_and_source_sha(self):
        for e in self.cat:
            self.assertEqual(e["github"], f"{self.snap['repo_url']}/blob/{self.snap['source_sha']}/{e['path']}")

    def test_group_of(self):
        self.assertEqual(bl.group_of("docs/mission-control/m2/index.html"), "docs/mission-control")
        self.assertEqual(bl.group_of("docs/index.html"), "docs")
        self.assertEqual(bl.group_of("index.html"), ".")

    def test_pages_site_is_verified_root_only(self):
        site = self.snap["pages_site"]
        self.assertEqual(site, json.loads(bl.SOURCES.read_text(encoding="utf-8"))["pages_site"])
        self.assertRegex(site["url"], r"^https://[a-z0-9-]+\.github\.io/[A-Za-z0-9._-]+/$")
        self.assertRegex(site["verified_on"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertTrue(site["verified_by"] and site["observed"])
        # No per-page Pages URL is inferred from committed HTML.
        self.assertNotIn("github.io", json.dumps(self.cat))

    def test_rebuild_on_other_commit_only_changes_github_sha(self):
        snap = json.loads(bl.SNAPSHOT.read_text(encoding="utf-8"))
        for e in snap["catalog"]:
            e["github"] = e["github"].replace(snap["source_sha"], "f" * 40)
        snap["source_sha"] = "f" * 40
        self.assertEqual(bl.strip_pulse(snap), bl.strip_pulse(self.snap))

    def test_catalog_change_is_named(self):
        old = {"inputs": {}, "pages": [], "catalog": [{"path": "a.html", "title": "A"}, {"path": "b.html", "title": "B"}]}
        new = {"inputs": {}, "pages": [], "catalog": [{"path": "a.html", "title": "A2"}, {"path": "c.html", "title": "C"}]}
        self.assertEqual(bl.stale_reason(old, new),
                         "catalog added: c.html; catalog removed: b.html; catalog retitled: a.html")


class Hub(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snap = json.loads(bl.SNAPSHOT.read_text(encoding="utf-8"))
        cls.spec = json.loads(bl.SOURCES.read_text(encoding="utf-8"))["hub"]
        cls.hub = cls.snap["hub"]

    def test_entries_follow_the_declaration_order(self):
        self.assertEqual([e.get("path") or e.get("url") for e in self.hub["entries"]],
                         [e.get("path") or e.get("url") for e in self.spec["entries"]])

    def test_in_repo_entries_resolve_and_are_titled_from_the_page(self):
        catalog = {e["path"]: e["title"] for e in self.snap["catalog"]}
        local = [e for e in self.hub["entries"] if "repo" not in e and "url" not in e]
        self.assertTrue(local)
        for e in local:
            with self.subTest(path=e["path"]):
                self.assertEqual(posixpath.normpath(posixpath.join(bl.SELF_DIR, e["href"])), e["path"])
                declared = next(d for d in self.spec["entries"] if d.get("path") == e["path"])
                # The page's own <title> wins; a declared title only fills in for a page without one.
                expected = declared.get("title", catalog[e["path"]]) if catalog[e["path"]] == posixpath.basename(e["path"]) else catalog[e["path"]]
                self.assertEqual(e["title"], expected)

    def test_cross_repo_entries_are_declared_verbatim(self):
        declared = [e for e in self.spec["entries"] if "repo" in e or "url" in e]
        self.assertEqual([e for e in self.hub["entries"] if "repo" in e or "url" in e], declared)
        for e in declared:
            with self.subTest(entry=e.get("path") or e.get("url")):
                self.assertTrue(e["title"])
                if "repo" in e:
                    self.assertRegex(e["repo"], r"^GBOGEB/[\w.-]+$")
                    self.assertTrue(e["ref"] and e["path"])
                else:
                    self.assertTrue(e["url"].startswith("https://"))
        self.assertTrue(self.hub["verified"]["on"] and self.hub["verified"]["by"])

    def test_requested_dashboards_are_listed(self):
        keys = " ".join((e.get("path") or e.get("url")) for e in self.hub["entries"])
        for want in ("claude.ai/artifact/", "QPS_DASHBOARD_LAUNCHER_CURRENT.html", "master_input_cleanup/repo_ledger.html",
                     "code_bnb/", "everred/index.html", "G3P_LIVE_LEDGER.html",
                     "claude.ai/artifact/RARdwhuvVk2emp2iCRRhDw"):
            self.assertIn(want, keys)
        title_census = next(e for e in self.hub["entries"] if e.get("url") == "https://claude.ai/artifact/RARdwhuvVk2emp2iCRRhDw")
        self.assertIn("private until shared", title_census["note"])

    def test_cross_repo_rows_get_clone_and_open_commands(self):
        html = bl.TEMPLATE.read_text(encoding="utf-8")
        self.assertIn('"git clone https://github.com/"+r+".git"', html)
        self.assertIn('"start "+e.repo.split("/")[1]', html)
        self.assertIn("data-copy=\"'+esc(opener(e))", html)

    def test_missing_in_repo_entry_fails_the_build(self):
        sha = bl.git("rev-parse", "HEAD^{commit}").strip()
        with self.assertRaises(FileNotFoundError):
            bl.hub({"note": "", "verified": {}, "entries": [{"group": "g", "path": "no/such/page.html"}]}, sha)

    def test_retitled_hub_page_is_named(self):
        old = {"inputs": {}, "pages": [], "hub": {"entries": [{"path": "a.html", "title": "A"}]}}
        new = {"inputs": {}, "pages": [], "hub": {"entries": [{"path": "a.html", "title": "B"}]}}
        self.assertEqual(bl.stale_reason(old, new), "hub changed: a.html")


class Render(unittest.TestCase):
    def test_page_is_self_contained(self):
        html = bl.TEMPLATE.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"<script[^>]+src=", html, re.I))
        self.assertIsNone(re.search(r"<link[^>]+stylesheet", html, re.I))
        self.assertIn("default-src 'none'", html)
        self.assertEqual(html.count(bl.DATA_HOLE), 1)
        self.assertNotRegex(html, r"\b(?:src|href)=\"(?:https?:)?//")  # no hard-coded external loads
        for anchor in ('id="hub"', 'id="access"', 'id="catalog"', 'id="acc-local"', "location.protocol"):
            self.assertIn(anchor, html)

    def test_catalog_rows_link_history_and_copy_local_path(self):
        html = bl.TEMPLATE.read_text(encoding="utf-8")
        self.assertIn('"/commits/"+D.source_sha+"/"+e.path,"History"', html)
        # The local path column exists only when the clone root was found from the page's file:// URL.
        self.assertIn("ROOT===null?\"\":'<th scope=\"col\">Local path</th>'", html)
        self.assertIn('data-copy="', html)
        self.assertIn("navigator.clipboard", html)

    def test_page_passes_static_html_contract(self):
        # Reuse the html_qa owner's static contract (AGENTS.md L4) instead of re-checking here.
        path = HERE.parents[1] / "html_qa" / "html_contract.py"
        spec = importlib.util.spec_from_file_location("html_contract", path)
        contract = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(contract)
        snap = json.loads(bl.SNAPSHOT.read_text(encoding="utf-8"))
        result = contract.inspect(bl.render(snap), base_dir=HERE, strict_local=True)
        self.assertEqual(result["errors"], [])

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
            fake.write_text(bl.dump(snap), encoding="utf-8", newline="\n")
            with mock.patch.object(bl, "SNAPSHOT", fake):
                problems = bl.check(bl.git("rev-parse", "HEAD^{commit}").strip())
        self.assertTrue(any(first in p for p in problems), problems)

    def _check_with_page(self, transform, target=None):
        """check(HEAD) with one page's text (default: first linked page) passed through ``transform``."""
        target = target or json.loads(bl.SOURCES.read_text(encoding="utf-8"))["pages"][0]["path"]
        real = bl.read_texts

        def fake(sha, paths):
            return {p: (transform(x) if p == target else x) for p, x in real(sha, paths).items()}

        with mock.patch.object(bl, "read_texts", fake):
            return target, bl.check(bl.git("rev-parse", "HEAD^{commit}").strip())

    def test_regenerated_page_with_same_title_is_not_stale(self):
        _, problems = self._check_with_page(lambda t: t + "\n<!-- regenerated -->\n")
        self.assertEqual(problems, [])

    def _unrelated_page(self):
        snap = json.loads(bl.SNAPSHOT.read_text(encoding="utf-8"))
        linked = {p["path"] for p in snap["pages"]} | {bl.SELF_DIR + "/index.html"}
        return next(e["path"] for e in snap["catalog"] if e["path"] not in linked)

    def test_regenerated_unrelated_catalog_page_is_not_stale(self):
        target = self._unrelated_page()
        _, problems = self._check_with_page(lambda t: t + "\n<p>new content</p>\n", target)
        self.assertEqual(problems, [])

    def test_retitled_unrelated_catalog_page_is_named(self):
        target = self._unrelated_page()
        _, problems = self._check_with_page(
            lambda t: bl.TITLE.sub("<title>Renamed page</title>", t, count=1)
            if bl.TITLE.search(t) else "<title>Renamed page</title>" + t, target)
        self.assertTrue(any("catalog retitled: " + target in p for p in problems), problems)

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

    def test_pulse_fields_alone_are_not_stale(self):
        snap = json.loads(bl.SNAPSHOT.read_text(encoding="utf-8"))
        snap["source_sha"], snap["source_date"] = "f" * 40, "2000-01-01T00:00:00+00:00"
        with tempfile.TemporaryDirectory() as tmp:
            fake, page = Path(tmp) / "launcher.json", Path(tmp) / "index.html"
            fake.write_text(bl.dump(snap), encoding="utf-8", newline="\n")
            page.write_text(bl.render(snap), encoding="utf-8", newline="\n")
            with mock.patch.object(bl, "SNAPSHOT", fake), mock.patch.object(bl, "PAGE", page):
                self.assertEqual(bl.check(bl.git("rev-parse", "HEAD^{commit}").strip()), [])


if __name__ == "__main__":
    unittest.main()
