"""Offline controls for the depth census (breadth, depth, penetration, tested, ZERO buckets)."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import admission as a  # noqa: E402
import depth as d  # noqa: E402
import gate as g  # noqa: E402

WF = {
    "unit.yml": ("name: U\non:\n  pull_request:\n    paths: ['pkg/**']\njobs:\n  t:\n    runs-on: ubuntu-latest\n"
                 "    steps:\n      - run: python -m unittest discover -s pkg -p 'test_*.py'\n"),
    "py.yml": ("name: P\non:\n  pull_request:\n    paths: ['lib/**']\njobs:\n  t:\n    runs-on: ubuntu-latest\n"
               "    steps:\n      - run: python -m pytest lib/tests -q\n"),
    "script.yml": ("name: S\non:\n  pull_request:\n    paths: ['docs/**']\njobs:\n  t:\n    runs-on: ubuntu-latest\n"
                   "    steps:\n      - run: python tools/check.py\n"),
    "dead.yml": "name: D\non:\n  pull_request:\n    paths: ['nowhere/**']\njobs: {}\n",
    "all.yml": "name: A\non:\n  pull_request: {}\njobs: {}\n",
    "push.yml": "name: Push\non:\n  push: {}\njobs: {}\n",
}
FILES = {
    "pkg/core.py": "def f():\n    return 1\n",
    "pkg/orphan.py": "X = 1\n",
    "pkg/test_core.py": "import unittest\nimport core\nclass T(unittest.TestCase):\n    def test_a(self):\n        pass\n"
                        "    def test_b(self):\n        pass\n",
    "lib/mod.py": "Y = 2\n",
    "lib/tests/test_mod.py": "from mod import Y\ndef test_y():\n    assert Y\nclass TestK:\n    def test_k(self):\n        pass\n",
    "tools/check.py": "print('ok')\n",
    "loaded/engine.py": "Z = 3\n",
    "loaded/tests/test_engine_by_path.py": ("import importlib.util, pathlib\nROOT = pathlib.Path(__file__).parents[1]\n"
                                           "SPEC = importlib.util.spec_from_file_location('e', ROOT / 'engine.py')\n"),
    "elsewhere/engine2.py": "Q = 4\n",
    "loaded/tests/test_mentions.py": "NOTE = 'engine2.py is far away'\n",
    "tools/browser_qa.py": "print('qa')\n",
    "web/app.config.js": "module.exports = {}\n",
    "web/widget.mjs": "export const w = 1\n",
    "web/widget.test.mjs": "import {w} from './widget.mjs'\ntest('w', () => {})\nit('x', () => {})\n",
    "docs/readme.md": "x\n",
}


class Census(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        (root / ".github" / "workflows").mkdir(parents=True)
        for k, v in WF.items():
            (root / ".github" / "workflows" / k).write_text(v)
        for k, v in FILES.items():
            (root / k).parent.mkdir(parents=True, exist_ok=True)
            (root / k).write_text(v)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
        cls.root = root
        ledger = a.build(root, None, None, {"entries": []}, {})
        cls.doc = d.build(root, ledger, d.load_audit(root))
        cls.w = {Path(x["path"]).name: x for x in cls.doc["workflows"]}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_depth_counts_each_runner(self):
        self.assertEqual(self.w["unit.yml"]["depth"]["tests"], 2)
        self.assertEqual(self.w["py.yml"]["depth"]["by_runner"], {"pytest": 2})
        self.assertIn("ZERO_TESTS", self.w["script.yml"]["zero"])
        self.assertNotIn("ZERO_TESTS", self.w["unit.yml"]["zero"])
        dep = self.doc["totals"]["depth"]
        self.assertEqual((dep["unique_tests"], dep["unique_test_files"], dep["tests_total"]), (4, 2, 4))

    def test_dead_filter_and_catch_all(self):
        self.assertIn("ZERO_PENETRATION", self.w["dead.yml"]["zero"])
        self.assertEqual(self.w["dead.yml"]["penetration"]["files_guarded"], 0)
        self.assertNotIn("ZERO_PENETRATION", self.w["all.yml"]["zero"])
        self.assertFalse(self.w["push.yml"]["penetration"]["pr_scoped"])

    def test_targeted_penetration_ignores_catch_all(self):
        p = self.doc["totals"]["penetration"]
        n = p["tracked_files"]
        self.assertEqual(p["pr_gated_files"], n)  # all.yml fires on everything
        self.assertLess(p["targeted_files"], n)
        self.assertIn("web/widget.mjs", self.doc["zero_targeted_files"])
        self.assertNotIn("pkg/core.py", self.doc["zero_targeted_files"])

    def test_tested_harness_and_non_logic(self):
        z = self.doc["zero_tested_modules"]
        self.assertIn("pkg/orphan.py", z)
        self.assertIn("tools/check.py", z)
        for ok in ("pkg/core.py", "lib/mod.py", "web/widget.mjs", "loaded/engine.py"):
            self.assertNotIn(ok, z)
        self.assertIn("elsewhere/engine2.py", z)  # a bare filename far from the test is not a reference
        self.assertEqual(self.doc["harness_modules"], ["tools/browser_qa.py"])
        self.assertNotIn("web/app.config.js", z + self.doc["harness_modules"])
        t = self.doc["totals"]["tested"]
        self.assertEqual((t["tested"], t["harness"], t["zero_tested"]), (4, 1, 3))

    def test_zero_evidence_without_ledger_and_authority(self):
        self.assertTrue(all("ZERO_EVIDENCE" in x["zero"] for x in self.doc["workflows"]))
        self.assertFalse(self.doc["authority"]["merge_authorized"])
        self.assertIn("ZERO", d.markdown(self.doc))
        json.dumps(self.doc)

    def test_node_counter_and_unresolved_target(self):
        self.assertEqual(d.node_count(self.root / "web/widget.test.mjs"), 2)
        self.assertIsNone(d.resolve_targets(self.root, ".", "missing/dir", "test_*.py"))
        self.assertIsNone(d.resolve_targets(self.root, ".", "$TESTS", "test_*.py"))

    def test_area_keys(self):
        self.assertEqual(d.area("mission-control/gogreen/x.py"), "mission-control/gogreen")
        self.assertEqual(d.area("README.md"), "(root)")
        self.assertEqual(d.area("docs/a/b.md"), "docs")


if __name__ == "__main__":
    unittest.main()
