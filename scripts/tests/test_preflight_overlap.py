import contextlib
import importlib.util
import io
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("preflight_overlap", ROOT / "preflight_overlap.py")
po = importlib.util.module_from_spec(spec)
spec.loader.exec_module(po)

REF = "origin/master"
PRS = [
    {"number": 787, "title": "feat(jade): CI/CD DAG with rolling-5 pulses", "headRefName": "feat/jade-cicd-dag",
     "url": "https://github.com/o/r/pull/787", "isDraft": False, "author": {"login": "alice"},
     "files": [{"path": "mission-control/jade_temple/tools/cicd_dag.py"},
               {"path": "mission-control/jade_temple/tools/rolling5.py"}]},
    {"number": 781, "title": "feat(scale-dock): EVERRED dock", "headRefName": "feat/scale-dock",
     "url": "https://github.com/o/r/pull/781", "isDraft": True, "author": {"login": "bob"},
     "files": [{"path": "mission-control/gogreen/scale_dock.py"}]},
    {"number": 9, "title": "docs: unrelated", "headRefName": "docs/x", "url": "u", "isDraft": False,
     "author": None, "files": [{"path": "README.md"}]},
]
TREE = [
    "mission-control/gogreen/scale_dock.py",
    "mission-control/jade_temple/tools/rolling5.py",
    "mission-control/jade_temple/tools/cicd_dag.py",
    "mission-control/qps-triage-ultra/p-process/everred/harvest.py",
    "README.md",
]


class FakeRunner:
    """Answers gh/git calls from canned data and records every command."""

    def __init__(self, prs=PRS, gh_rc=0, git_rc=0):
        self.prs, self.gh_rc, self.git_rc, self.calls = prs, gh_rc, git_rc, []

    def __call__(self, cmd):
        cmd = list(cmd)
        self.calls.append(cmd)
        if cmd[0] == "gh":
            if self.gh_rc:
                return self.gh_rc, "", "HTTP 401: Bad credentials"
            return 0, json.dumps(self.prs), ""
        if self.git_rc:
            return self.git_rc, "", "fatal: not a git repository"
        sub = cmd[1]
        if sub == "fetch":
            return 0, "", ""
        if sub == "ls-tree":
            return 0, "\n".join(TREE) + "\n", ""
        if sub == "log":
            return 0, "abc1234 GBOGEB 2026-10-23 feat(scale-dock): docks\n", ""
        if sub == "grep" and "-E" in cmd:
            pattern = cmd[cmd.index("-e") + 1]
            if "dock_everred" in pattern:
                return 0, f"{REF}:mission-control/gogreen/scale_dock.py:328:def dock_everred(e, candidate_roots):\n", ""
            if "rolling5" in pattern:
                return 0, f"{REF}:mission-control/jade_temple/tools/rolling5.py:1:def rolling5_window():\n", ""
            return 1, "", ""
        if sub == "grep" and "-l" in cmd:
            term = cmd[cmd.index("-e") + 1]
            if term == "dock_everred":
                return 0, f"{REF}:mission-control/gogreen/scale_dock.py\n{REF}:mission-control/jade_temple/tools/cicd_dag.py\n", ""
            return 1, "", ""
        return 1, "", ""


class HelperTests(unittest.TestCase):
    def test_norm_ignores_case_and_punctuation(self):
        self.assertTrue(po.term_hit("Rolling-5", "mission-control/jade_temple/tools/rolling5.py"))
        self.assertTrue(po.term_hit("scale-dock", "scale_dock.py"))
        self.assertFalse(po.term_hit("everred", "scale_dock.py"))

    def test_path_hit_is_prefix_on_path_boundaries(self):
        self.assertTrue(po.path_hit("mission-control/gogreen", "mission-control/gogreen/scale_dock.py"))
        self.assertTrue(po.path_hit("mission-control/gogreen/", "mission-control/gogreen/scale_dock.py"))
        self.assertTrue(po.path_hit("README.md", "README.md"))
        self.assertFalse(po.path_hit("mission-control/go", "mission-control/gogreen/scale_dock.py"))

    def test_ere_escape(self):
        self.assertEqual(po.ere_escape("a.b(c)"), r"a\.b\(c\)")


class AnalyseTests(unittest.TestCase):
    def test_open_prs_matched_by_title_branch_and_files(self):
        r = po.analyse(["rolling-5", "scale_dock"], [], runner=FakeRunner())
        nums = [p["number"] for p in r["open_prs"]]
        self.assertEqual(nums, [787, 781])
        why787 = " ".join(r["open_prs"][0]["why"])
        self.assertIn("title", why787)
        self.assertIn("rolling5.py", why787)
        self.assertTrue(r["open_prs"][1]["draft"])

    def test_path_matches_pr_files_and_master(self):
        r = po.analyse([], ["mission-control/gogreen"], runner=FakeRunner())
        self.assertEqual([p["number"] for p in r["open_prs"]], [781])
        m = r["master"]["paths"]["mission-control/gogreen"]
        self.assertEqual(m["files"], ["mission-control/gogreen/scale_dock.py"])
        self.assertTrue(m["last_commit"].startswith("abc1234"))

    def test_master_defs_and_content_strip_ref_prefix(self):
        r = po.analyse(["dock_everred"], [], runner=FakeRunner())
        m = r["master"]["terms"]["dock_everred"]
        self.assertEqual(m["defs"], ["mission-control/gogreen/scale_dock.py:328:def dock_everred(e, candidate_roots):"])
        self.assertEqual(len(m["content_files"]), 2)
        self.assertFalse(any(f.startswith(REF) for f in m["content_files"]))
        self.assertIn("master: mission-control/gogreen/scale_dock.py:328:def dock_everred(e, candidate_roots):",
                      r["owners"]["dock_everred"])

    def test_hyphenated_term_tries_underscore_and_joined_idents(self):
        runner = FakeRunner()
        r = po.analyse(["rolling-5"], [], runner=runner)
        grep = next(c for c in runner.calls if c[:2] == ["git", "grep"] and "-E" in c)
        pattern = grep[grep.index("-e") + 1]
        self.assertIn("rolling_5", pattern)
        self.assertIn("rolling5", pattern)
        self.assertEqual(len(r["master"]["terms"]["rolling-5"]["defs"]), 1)

    def test_paths_narrow_master_term_search(self):
        runner = FakeRunner()
        r = po.analyse(["rolling5"], ["mission-control/gogreen"], runner=runner)
        self.assertEqual(r["master"]["terms"]["rolling5"]["paths"], [])
        grep = next(c for c in runner.calls if c[:2] == ["git", "grep"] and "-E" in c)
        self.assertEqual(grep[grep.index("--") + 1:], ["mission-control/gogreen"])

    def test_owners_summary(self):
        r = po.analyse(["cicd_dag", "nothing-here"], [], runner=FakeRunner())
        self.assertIn("PR #787 (feat/jade-cicd-dag)", r["owners"]["cicd_dag"])
        self.assertIn("master: mission-control/jade_temple/tools/cicd_dag.py", r["owners"]["cicd_dag"])
        self.assertEqual(r["owners"]["nothing-here"], [])
        text = po.render(r)
        self.assertIn("Already owned by:", text)
        self.assertIn("nothing-here: nothing found", text)

    def test_repo_flag_passed_to_gh(self):
        runner = FakeRunner()
        po.analyse(["x"], [], runner=runner, repo="GBOGEB/pipeline-automation-hub")
        gh = next(c for c in runner.calls if c[0] == "gh")
        self.assertEqual(gh[gh.index("--repo") + 1], "GBOGEB/pipeline-automation-hub")
        self.assertIn("files", gh[gh.index("--json") + 1])


class FailureTests(unittest.TestCase):
    def _main(self, argv, runner):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = po.main(argv, runner=runner)
        return rc, buf.getvalue()

    def test_gh_failure_is_warning_and_exit_zero(self):
        rc, out = self._main(["scale_dock", "--no-fetch"], FakeRunner(gh_rc=1))
        self.assertEqual(rc, 0)
        self.assertIn("WARNING: gh pr list failed", out)
        self.assertIn("master: mission-control/gogreen/scale_dock.py", out)

    def test_git_failure_is_warning_and_exit_zero(self):
        rc, out = self._main(["scale_dock"], FakeRunner(git_rc=128))
        self.assertEqual(rc, 0)
        self.assertIn("git fetch origin failed", out)
        self.assertIn("git ls-tree origin/master failed", out)
        self.assertIn("PR #781", out)

    def test_bad_json_and_no_args_exit_zero(self):
        class Bad(FakeRunner):
            def __call__(self, cmd):
                if cmd[0] == "gh":
                    return 0, "not json", ""
                return super().__call__(cmd)

        rc, out = self._main(["x", "--no-fetch"], Bad())
        self.assertEqual(rc, 0)
        self.assertIn("non-JSON", out)
        rc, out = self._main([], FakeRunner())
        self.assertEqual(rc, 0)
        self.assertIn("give at least one search term", out)

    def test_unexpected_exception_still_exit_zero(self):
        def boom(cmd):
            raise RuntimeError("kaput")

        rc, out = self._main(["x", "--no-fetch"], boom)
        self.assertEqual(rc, 0)
        self.assertIn("could not finish", out)

    def test_fetch_runs_by_default_and_json_output(self):
        runner = FakeRunner()
        rc, out = self._main(["scale_dock", "--json"], runner)
        self.assertEqual(rc, 0)
        self.assertEqual(runner.calls[0], ["git", "fetch", "-q", "origin"])
        self.assertEqual(json.loads(out)["owners"]["scale_dock"][0], "PR #781 (feat/scale-dock)")

    def test_real_runner_missing_binary(self):
        rc, out, err = po.run(["definitely-not-a-real-binary-xyz"])
        self.assertEqual(rc, 127)
        self.assertTrue(err)


if __name__ == "__main__":
    unittest.main()
