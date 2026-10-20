"""Offline controls for the GOGREEN required-gate aggregator."""
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gate as g  # noqa: E402

ROOT = HERE.parents[2]
SHA = "a" * 40


class Globs(unittest.TestCase):
    def test_github_glob_semantics(self):
        r = g.glob_to_regex("mission-control/federation-atlas/**")
        self.assertTrue(r.match("mission-control/federation-atlas/a/b.py"))
        self.assertFalse(r.match("mission-control/federation-atlasX/a.py"))
        star = g.glob_to_regex("docs/*.md")
        self.assertTrue(star.match("docs/a.md"))
        self.assertFalse(star.match("docs/x/a.md"))
        self.assertTrue(g.glob_to_regex("**/*.yml").match("a/b/c.yml"))
        self.assertTrue(g.glob_to_regex("**/*.yml").match("c.yml"))
        self.assertTrue(g.glob_to_regex(".github/workflows/x.yml").match(".github/workflows/x.yml"))
        self.assertFalse(g.glob_to_regex(".github/workflows/x.yml").match(".github/workflowsXx.yml"))

    def test_negation(self):
        self.assertEqual(g.applies(["a/x.py", "a/skip.md"], ["a/**", "!a/*.md"]), ["a/x.py"])

    def test_no_filter_always_applies(self):
        self.assertEqual(g.applies(["anything"], None), ["anything"])


class RealWorkflows(unittest.TestCase):
    def test_guarded_workflows_parse_from_repo(self):
        for wf in g.GUARDED:
            with self.subTest(wf=wf):
                f = g.path_filters(ROOT / wf)
                self.assertTrue(f, "guarded workflow must declare pull_request.paths")
                self.assertIn(wf, f, "workflow should trigger on its own edits")

    def test_unrelated_change_not_applicable_related_applies(self):
        atlas = g.path_filters(ROOT / g.GUARDED[0])
        self.assertEqual(g.applies(["README.md"], atlas), [])
        self.assertTrue(g.applies(["mission-control/federation-atlas/build_atlas.py"], atlas))

    def test_rejects_unsupported_triggers(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "w.yml"
            p.write_text("on:\n  push: {}\n")
            with self.assertRaises(ValueError):
                g.path_filters(p)
            p.write_text("on:\n  pull_request:\n    paths-ignore: ['x']\n")
            with self.assertRaises(ValueError):
                g.path_filters(p)


class Verdicts(unittest.TestCase):
    def r(self, status, conclusion, attempt=1, rid=1):
        return {"status": status, "conclusion": conclusion, "run_attempt": attempt, "id": rid,
                "created_at": "2026-10-19T00:00:00Z"}

    def test_states(self):
        self.assertEqual(g.verdict([]), g.WAIT)
        self.assertEqual(g.verdict([self.r("in_progress", None)]), g.WAIT)
        self.assertEqual(g.verdict([self.r("completed", "success")]), g.PASS)
        for bad in ("failure", "cancelled", "timed_out", "skipped"):
            self.assertEqual(g.verdict([self.r("completed", bad)]), g.FAIL)

    def test_latest_attempt_wins(self):
        runs = [self.r("completed", "failure", 1), self.r("completed", "success", 2)]
        self.assertEqual(g.verdict(runs), g.PASS)
        self.assertEqual(g.verdict(list(reversed(runs))), g.PASS)


class Evaluate(unittest.TestCase):
    def reader(self, files, runs_by_wf):
        def opener(req, timeout):
            u = req.full_url
            if "/pulls/" in u:
                body = [{"filename": f} for f in files] if "page=1" in u else []
            else:
                name = u.split("/actions/workflows/")[1].split("/")[0]
                body = {"workflow_runs": runs_by_wf.get(name, [])}
            return io.BytesIO(json.dumps(body).encode())
        return g.Reader("GBOGEB/pipeline-automation-hub", token="", opener=opener)

    def test_not_applicable_passes_without_waiting(self):
        rep = g.evaluate(self.reader(["README.md"], {}), ROOT, 1, SHA, deadline_s=0, sleep=lambda s: None)
        self.assertEqual(rep["verdict"], g.PASS)
        self.assertTrue(all(x["state"] == g.NA for x in rep["gates"]))

    def test_applicable_red_fails(self):
        runs = {"code-purple-method-atlas.yml": [{"status": "completed", "conclusion": "failure", "id": 1}]}
        rep = g.evaluate(self.reader(["mission-control/federation-atlas/x.py"], runs), ROOT, 1, SHA, 0,
                         sleep=lambda s: None)
        self.assertEqual(rep["verdict"], g.FAIL)

    def test_applicable_green_passes(self):
        runs = {"code-purple-method-atlas.yml": [{"status": "completed", "conclusion": "success", "id": 1}]}
        rep = g.evaluate(self.reader(["mission-control/federation-atlas/x.py"], runs), ROOT, 1, SHA, 0,
                         sleep=lambda s: None)
        self.assertEqual(rep["verdict"], g.PASS)
        self.assertFalse(rep["merge_authorized"])

    def test_missing_run_fails_closed_at_deadline(self):
        t = iter([0, 0, 999, 999])
        rep = g.evaluate(self.reader(["mission-control/federation-atlas/x.py"], {}), ROOT, 1, SHA, 10,
                         clock=lambda: next(t), sleep=lambda s: None)
        self.assertEqual(rep["verdict"], g.FAIL)
        self.assertIn("deadline", [x for x in rep["gates"] if x["state"] == g.FAIL][0]["reason"])

    def test_both_gates_apply_to_shared_workflow_file(self):
        both = ".github/workflows/code-purple-method-atlas.yml"
        rep = g.evaluate(self.reader([both], {}), ROOT, 1, SHA, 0, sleep=lambda s: None)
        self.assertEqual({x["workflow"] for x in rep["gates"] if x["matched_files"]}, set(g.GUARDED))


if __name__ == "__main__":
    unittest.main()
