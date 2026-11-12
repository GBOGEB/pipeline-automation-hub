"""Offline tests for build_tool_catalog.py. Run: python -m unittest tools/workstation/test_build_tool_catalog.py -v"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("build_tool_catalog_under_test", HERE / "build_tool_catalog.py")
btc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(btc)


def run(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def catalog(tools: list[dict]) -> dict:
    return {"schema": btc.SCHEMA, "repo": "o/r", "groups": [{"id": "g", "title": "G"}], "tools": tools}


def tool(**kw) -> dict:
    base = {"id": "t1", "group": "g", "name": "Tool.ps1", "path": "tools/Tool.ps1", "goal": "Do the thing",
            "when": "When needed", "writes": "Read-only.", "commands": ["Set-Location \"{hub}\"", "pwsh -File tools/Tool.ps1"]}
    base.update(kw)
    return base


class FixtureRepo(unittest.TestCase):
    def setUp(self):
        # Not mkdtemp: on Windows with Python 3.12 its owner-only ACL makes `git init` fail with Permission denied.
        self.root = Path(tempfile.gettempdir()) / f"btc_test_{os.urandom(6).hex()}"
        self.root.mkdir()
        # Some Windows hosts create it owned by Administrators; trust only this temp repo, for this test.
        self._env = {k: os.environ.get(k) for k in ("GIT_CONFIG_COUNT", "GIT_CONFIG_KEY_0", "GIT_CONFIG_VALUE_0")}
        os.environ.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="safe.directory",
                          GIT_CONFIG_VALUE_0=str(self.root).replace("\\", "/"))
        run(self.root, "init", "-q", "-b", "main")
        run(self.root, "config", "user.email", "t@t")
        run(self.root, "config", "user.name", "t")
        run(self.root, "config", "core.autocrlf", "false")
        (self.root / "tools").mkdir()
        (self.root / "tools" / "Tool.ps1").write_text("param()\n'<b>&</b>'\n", encoding="utf-8", newline="\n")
        run(self.root, "add", ".")
        run(self.root, "commit", "-qm", "add tool")

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.root, ignore_errors=True)

    def build(self, tools: list[dict], fragment: bool = False) -> tuple[dict, str]:
        p = self.root / "cat.json"
        p.write_text(json.dumps(catalog(tools)), encoding="utf-8")
        model = btc.build(btc.load_catalog(p), self.root, None, "2026-11-12 10:00 +0100")
        return model, btc.render(model, fragment=fragment)

    def test_code_facts_from_git_and_escaped_source(self):
        model, page = self.build([tool()])
        facts = model["tools"][0]["facts"]
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.root, capture_output=True, text=True).stdout.strip()
        self.assertTrue(facts["present"])
        self.assertEqual(facts["commit"], head)
        self.assertEqual(facts["lines"], 2)
        self.assertIn(facts["blob"][:12], page)
        self.assertIn("&lt;b&gt;&amp;&lt;/b&gt;", page)  # source is escaped, never injected
        self.assertIn(f"https://github.com/o/r/blob/{head}/tools/Tool.ps1", page)

    def test_hub_placeholder_becomes_the_checkout_path(self):
        _, page = self.build([tool()])
        # The path exactly as given (a Windows runner may hand out 8.3 short names; never compare resolved forms).
        self.assertIn(f'Set-Location "{self.root}"', page.replace("&quot;", '"'))
        self.assertNotIn("{hub}", page)

    def test_blob_whitespace_is_preserved(self):
        (self.root / "tools" / "Blank.ps1").write_text("\n  indented\n\n", encoding="utf-8", newline="\n")
        (self.root / "tools" / "Newline.ps1").write_text("\n", encoding="utf-8", newline="\n")
        run(self.root, "add", ".")
        run(self.root, "commit", "-qm", "whitespace")
        model, _ = self.build([tool(id="a", path="tools/Blank.ps1"), tool(id="b", path="tools/Newline.ps1")])
        a, b = (t["facts"] for t in model["tools"])
        self.assertEqual(a["source"], "\n  indented\n\n")
        self.assertEqual(a["lines"], 3)
        self.assertEqual(b["lines"], 1)

    def test_missing_file_is_flagged_not_fatal(self):
        model, page = self.build([tool(path="tools/Gone.ps1")])
        self.assertFalse(model["tools"][0]["facts"]["present"])
        self.assertIn("Not in this checkout", page)

    def test_local_edits_are_flagged(self):
        (self.root / "tools" / "Tool.ps1").write_text("changed\n", encoding="utf-8")
        _, page = self.build([tool()])
        self.assertIn("Local changes in this checkout are not shown", page)

    def test_levels(self):
        self.assertEqual(btc.write_level("Read-only."), "read")
        self.assertEqual(btc.write_level("Pushes only with -Publish"), "push")
        self.assertEqual(btc.write_level("Writes a report file."), "write")
        model, _ = self.build([tool(level="push")])
        self.assertEqual(model["tools"][0]["level"], "push")

    def test_offline_refs_render_unknown_with_checkout(self):
        _, page = self.build([tool(prs=[7], issues=[9])])
        self.assertIn("o/r#7", page)
        self.assertIn("gh pr checkout 7 -R o/r", page)
        self.assertIn("o/r#9", page)
        self.assertIn("state not read (offline)", page)
        _, bare = self.build([tool()])
        self.assertIn("Build with --online", bare)

    def test_fragment_has_no_document_wrapper(self):
        _, frag = self.build([tool()], fragment=True)
        self.assertNotIn("<!doctype", frag.lower())
        self.assertNotIn("<body", frag.lower())
        self.assertTrue(frag.startswith("<title>"))
        _, full = self.build([tool()])
        self.assertTrue(full.lower().startswith("<!doctype html>"))

    def test_validation(self):
        p = self.root / "bad.json"
        for bad in (catalog([tool(), tool()]), catalog([tool(group="nope")]), catalog([tool(related=["x"])]),
                    catalog([tool(level="maybe")]), catalog([tool(goal="")]), {"schema": "x", "groups": [], "tools": []}):
            p.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(ValueError):
                btc.load_catalog(p)


class RealCatalog(unittest.TestCase):
    def test_catalog_loads_and_every_tool_is_at_head_or_names_its_pr(self):
        cat = btc.load_catalog(HERE / "TOOLS_CATALOG.json")
        root = Path(btc.git(HERE, "rev-parse", "--show-toplevel"))
        for t in cat["tools"]:
            at_head = bool(btc.git(root, "rev-parse", f"HEAD:{t['path']}"))
            self.assertTrue(at_head or t.get("prs"), f"{t['id']}: {t['path']} is not at HEAD and lists no PR")
            self.assertTrue(t["commands"][0].startswith('Set-Location "{hub}"'), f"{t['id']}: commands must start in the repo")


if __name__ == "__main__":
    unittest.main()
