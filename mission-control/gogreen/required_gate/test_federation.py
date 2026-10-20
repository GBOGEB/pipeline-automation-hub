"""Offline controls for the federation spine rollup."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import federation as f  # noqa: E402

WF = ("name: U\non:\n  pull_request:\n    paths: ['pkg/**']\njobs:\n  t:\n    runs-on: ubuntu-latest\n"
      "    steps:\n      - run: python -m unittest discover -s pkg -p 'test_*.py'\n")


def make_repo(d):
    root = Path(d)
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "unit.yml").write_text(WF)
    (root / "pkg").mkdir()
    (root / "pkg" / "core.py").write_text("X = 1\n")
    (root / "pkg" / "test_core.py").write_text("import unittest\nimport core\nclass T(unittest.TestCase):\n"
                                               "    def test_a(self):\n        pass\n")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    return root


def lane(path, streak):
    return {"path": path, "class": "STABLE_GREEN", "current": "GREEN", "green_streak": streak, "latest_age_days": 0.2,
            "latest": {"sha": "c" * 40}, "nondeterminism": {"nondeterministic": False}, "pinned_historical_ids": []}


class Spine(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(Path(self.tmp.name) / "r")
        self.traces = Path(self.tmp.name) / "t"
        self.traces.mkdir()
        (self.traces / "red_trace.json").write_text(json.dumps({
            "workflows": [lane(".github/workflows/unit.yml", 5)], "counts": {"STABLE_GREEN": 1},
            "currently_red": [], "currently_red_stale": [], "shared_break_roots": [], "digest_sha256": "m"}))
        (self.traces / "red_trace_pr.json").write_text(json.dumps({
            "repository": "o/r", "base": "main", "workflows": [], "counts": {}, "window": {"merged_prs": 2},
            "merge_timing": {}, "merged_with_red": [{"pr": 2, "workflows": [".github/workflows/unit.yml"]}],
            "merged_with_pending": [], "digest_sha256": "p",
            "merge_matrix": [{"pr": 1, "merged_at": "2026-10-19T01:00:00Z", "at_merge": {".github/workflows/unit.yml": "success"}},
                             {"pr": 2, "merged_at": "2026-10-19T02:00:00Z", "at_merge": {".github/workflows/unit.yml": "failure"}}]}))

    def tearDown(self):
        self.tmp.cleanup()

    def test_observed_row_composes_ledger_backtest_and_census(self):
        spec = {"repo": "o/r", "branch": "main", "root": str(self.root), "trace_dir": str(self.traces)}
        r = f.repo_row(spec, {1: ["pkg/a.py"], 2: ["pkg/b.py"]}, 10)
        self.assertEqual(r["state"], "OBSERVED")
        self.assertEqual(r["proposed_admission"]["counts"], {"ENFORCED": 1})
        self.assertEqual(r["backtest"]["would_have_caught_red"], 1)
        self.assertEqual(r["depth"]["unique_tests"], 1)
        self.assertEqual(r["pr_lane"]["merged_with_red"], 1)

    def test_deferred_and_static_rows_are_listed_not_dropped(self):
        rows = [f.repo_row({"repo": "o/private", "root": None, "deferred_reason": "private: no cross-repo credential"}, None, 5),
                f.repo_row({"repo": "o/static", "root": str(self.root)}, None, 5),
                f.repo_row({"repo": "o/r", "root": str(self.root), "trace_dir": str(self.traces)}, None, 5)]
        self.assertEqual([r["state"] for r in rows], ["DEFERRED", "STATIC_ONLY", "OBSERVED"])
        self.assertIn("credential", rows[0]["reason"])
        self.assertEqual(rows[1]["proposed_admission"]["counts"], {"OBSERVED": 1})  # no evidence -> never enforced
        t = f.rollup(rows)
        self.assertEqual((t["repositories"], t["observed"], t["static_only"], t["deferred"]), (3, 1, 1, 1))
        self.assertEqual(t["workflows"], 2)
        self.assertEqual(t["proposed_enforced"], 1)
        self.assertEqual(t["merged_with_red"], 1)
        md = f.markdown({"repositories": rows, "totals": t})
        self.assertIn("DEFERRED: private", md)
        self.assertIn("DEFERRED is not green", md)

    def test_hub_ledger_ratchet_is_respected(self):
        prev = Path(self.tmp.name) / "ADMISSION.json"
        prev.write_text(json.dumps({"entries": [{"path": ".github/workflows/unit.yml", "disposition": "ENFORCED"}]}))
        r = f.repo_row({"repo": "o/r", "root": str(self.root), "ledger": str(prev)}, None, 5)
        self.assertEqual(r["proposed_admission"]["counts"], {"ENFORCED": 1})  # incumbent kept without evidence

    def test_cli_writes_outputs(self):
        spec = Path(self.tmp.name) / "spec.json"
        spec.write_text(json.dumps([{"repo": "o/r", "root": str(self.root), "trace_dir": str(self.traces)}]))
        out = Path(self.tmp.name) / "out"
        doc = f.main(["--spec", str(spec), "--backtest-limit", "0", "--out", str(out)])
        self.assertTrue((out / "federation.md").read_text().startswith("### GOGREEN federation spine"))
        self.assertFalse(doc["authority"]["enforced_anywhere_but_hub"])


if __name__ == "__main__":
    unittest.main()
