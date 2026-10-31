"""Offline tests for build_dashboards.py: temp git repos only, no network, no gh."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("build_dashboards", HERE / "build_dashboards.py")
bd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bd)


def make_repo(path: Path, remote: str, files: dict[str, str]) -> None:
    path.mkdir(parents=True)
    run = lambda *a: subprocess.run(["git", "-C", str(path), *a], check=True, capture_output=True)
    run("init", "-q")
    run("config", "user.email", "t@example.invalid")
    run("config", "user.name", "t")
    run("remote", "add", "origin", remote)
    for rel, body in files.items():
        f = path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(body, encoding="utf-8")
    (path / ".gitignore").write_text("ignored/\n", encoding="utf-8")
    run("add", "-A")
    run("commit", "-q", "-m", "init")


class SlugTests(unittest.TestCase):
    def test_https_ssh_and_other(self):
        self.assertEqual(bd.slug("https://github.com/GBOGEB/ABACUS.git"), "GBOGEB/ABACUS")
        self.assertEqual(bd.slug("git@github.com:gbogeb/codex"), "gbogeb/codex")
        self.assertEqual(bd.slug("https://example.com/x/y.git"), "")

    def test_unique_slugs_is_case_insensitive(self):
        repos = [{"slug": "GBOGEB/CODEX"}, {"slug": "gbogeb/codex"}, {"slug": ""}]
        self.assertEqual(bd.unique_slugs(repos, ["GBOGEB/GEMINI", "gbogeb/gemini"]),
                         ["GBOGEB/CODEX", "GBOGEB/GEMINI"])


class BuildTests(unittest.TestCase):
    def setUp(self):
        # Not mkdtemp: on Windows it sets an owner-only ACL that some git setups cannot enter.
        self.root = Path(tempfile.gettempdir()) / ("dashboards-test-" + uuid.uuid4().hex[:12])
        self.root.mkdir()
        # Temp repos may be owned by another account (sandboxes, CI); trust them for this test only.
        env = mock.patch.dict(os.environ, {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "safe.directory",
                                           "GIT_CONFIG_VALUE_0": "*"})
        env.start()
        self.addCleanup(env.stop)
        make_repo(self.root / "work" / "alpha", "https://github.com/GBOGEB/alpha.git", {
            "docs/index.html": "<html><title>Alpha &amp; home</title></html>",
            "docs/notes.html": "<p>no title</p>",
            "node_modules/pkg/x.html": "<title>vendor</title>",
            "tpl/page_template.html": "<title>template</title>",
        })
        (self.root / "work" / "alpha" / "ignored").mkdir()
        (self.root / "work" / "alpha" / "ignored" / "gen.html").write_text("<title>ignored</title>")
        (self.root / "work" / "alpha" / "fresh_dashboard.html").write_text("<title>Untracked dash</title>")
        # a clone nested inside a clone is not scanned separately; one deeper than depth is not found
        make_repo(self.root / "work" / "a" / "b" / "c" / "deep", "https://github.com/GBOGEB/deep", {"i.html": ""})
        self.cfg = {
            "scan_roots": [{"path": str(self.root / "wo*"), "depth": 2}],
            "skip_dirs": ["node_modules"],
            "skip_html_patterns": ["node_modules/", "_template.html"],
            "entry_name_pattern": "(^|/)index\\.html$|dashboard",
            "top": [
                {"title": "Alpha home", "repo": "gbogeb/ALPHA", "path": "docs/index.html", "kind": "local"},
                {"title": "Missing", "repo": "GBOGEB/alpha", "path": "nope.html", "kind": "local"},
                {"title": "Hosted", "url": "https://example.invalid/", "kind": "hosted"},
            ],
            "artifacts": [],
        }

    def tearDown(self):
        def unlock(func, path, _exc):  # git object files are read-only on Windows
            os.chmod(path, stat.S_IWRITE)
            func(path)
        if sys.version_info >= (3, 12):
            shutil.rmtree(self.root, onexc=unlock)
        else:
            shutil.rmtree(self.root, onerror=unlock)

    def test_find_clones_respects_glob_and_depth(self):
        found = bd.find_clones(self.cfg)
        self.assertEqual([p.name for p in found], ["alpha"])

    def test_scan_repo_lists_tracked_and_untracked_but_not_ignored_or_skipped(self):
        r = bd.scan_repo(self.root / "work" / "alpha", self.cfg, re.compile(self.cfg["entry_name_pattern"]))
        self.assertEqual(r["slug"], "GBOGEB/alpha")
        pages = {p["rel"]: p for p in r["pages"]}
        self.assertEqual(sorted(pages), ["docs/index.html", "docs/notes.html", "fresh_dashboard.html"])
        self.assertEqual(pages["docs/index.html"]["title"], "Alpha & home")
        self.assertTrue(pages["docs/index.html"]["entry"])
        self.assertTrue(pages["fresh_dashboard.html"]["entry"])
        self.assertFalse(pages["docs/notes.html"]["entry"])
        self.assertTrue(pages["docs/index.html"]["uri"].startswith("file:"))

    def test_build_writes_page_with_resolved_top_entries(self):
        cfg_path = self.root / "dashboards.json"
        cfg_path.write_text(json.dumps(self.cfg), encoding="utf-8")
        out = self.root / "site" / "index.html"
        out.parent.mkdir()
        data = bd.build(cfg_path, out, offline=True)
        top = {t["title"]: t for t in data["top"]}
        self.assertTrue(top["Alpha home"]["url"].endswith("docs/index.html"))
        self.assertIsNone(top["Missing"]["url"])
        self.assertEqual(top["Hosted"]["url"], "https://example.invalid/")
        page = out.read_text(encoding="utf-8")
        self.assertNotIn("/*__DATA__*/null", page)
        payload = re.search(r"const DATA = (.*?);\nconst PIN_KEY", page, re.S).group(1)
        self.assertEqual(json.loads(payload)["repos"][0]["slug"], "GBOGEB/alpha")
        self.assertNotIn("</title></html>", payload)  # '</' is escaped inside the script


if __name__ == "__main__":
    unittest.main()
