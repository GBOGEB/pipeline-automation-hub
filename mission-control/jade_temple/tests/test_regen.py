"""regen.py: one ordered chain for the committed JADE outputs, kept in sync with CI and the pin graph."""
import fnmatch
import importlib.util
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
JT = ROOT / "mission-control/jade_temple"
WORKFLOW = ROOT / ".github/workflows/jade-temple-readonly-qa.yml"
spec = importlib.util.spec_from_file_location("regen", JT / "tools/regen.py")
regen = importlib.util.module_from_spec(spec)
sys.modules["regen"] = regen  # dataclasses resolve annotations through sys.modules
spec.loader.exec_module(regen)

# Scripts the JADE workflow runs that produce no committed output (receipt run, browser QA job).
NOT_GENERATORS = re.compile(r"stop_rules\.py|run_\w+_browser_qa\.py")


def workflow_filters(event="pull_request"):
    """Path filter of one trigger: the pull_request block ends at push:, the push block at workflow_dispatch."""
    on = WORKFLOW.read_text(encoding="utf-8").split("\njobs:", 1)[0]
    block = on.split(f"  {event}:", 1)[1]
    block = block.split("  push:", 1)[0] if event == "pull_request" else block
    return re.findall(r"- '([^']+)'", block.split("workflow_dispatch", 1)[0])


def dag_bound_paths():
    txt = (JT / "site/cicd_dag_crosswalk.csv").read_text(encoding="utf-8")
    out = set()
    for m in re.finditer(r"\b[0-9a-f]{40}:([A-Za-z0-9_.][^,|@\s]*)", txt):
        p = m.group(1).split("::")[0]
        if not p.startswith("GBOGEB/") and (ROOT / p).exists():
            out.add(p)
    return out


class Chain(unittest.TestCase):
    def test_ids_unique_and_dependencies_come_first(self):
        ids = [s.id for s in regen.CHAIN]
        self.assertEqual(len(ids), len(set(ids)))
        for i, s in enumerate(regen.CHAIN):
            for dep in s.after:
                self.assertIn(dep, ids, f"{s.id} depends on unknown {dep}")
                self.assertLess(ids.index(dep), i, f"{s.id} runs before its input {dep}")

    def test_scripts_exist(self):
        for s in regen.CHAIN:
            self.assertTrue((ROOT / s.script).is_file(), s.script)

    def test_dag_runs_after_everything_it_hashes(self):
        ids = [s.id for s in regen.CHAIN]
        for dep in ("pprocess", "redtrace", "rolling5"):
            self.assertLess(ids.index(dep), ids.index("cicd_dag"))
        self.assertEqual(ids[-1], "launcher")  # reads every owner output at HEAD
        self.assertTrue(regen.by_id()["launcher"].needs_commit)

    def test_every_ci_check_is_in_the_chain(self):
        wf = WORKFLOW.read_text(encoding="utf-8")
        ci = re.findall(r"python (mission-control/jade_temple/\S+\.py)( --check)?\s*$", wf, re.M)
        chain = {(s.script, s.check) for s in regen.CHAIN if s.check is not None}
        for script, flag in ci:
            if NOT_GENERATORS.fullmatch(script.rsplit("/", 1)[-1]):
                continue
            self.assertIn((script, ("--check",) if flag else ()), chain, f"CI runs {script}{flag} but regen.py does not")


class PinCoverage(unittest.TestCase):
    def test_every_pinned_path_triggers_jade_qa(self):
        # A pinned path outside the filter merges green and turns the next JADE PR red (10-23..10-25: 18 of 18
        # non-canary JADE reds). Add the path to both triggers in jade-temple-readonly-qa.yml.
        pats = [g.replace("**", "*") for g in workflow_filters()]
        gaps = {p for p in dag_bound_paths() if not any(fnmatch.fnmatchcase(p, g) for g in pats)}
        self.assertEqual(gaps, set(), "pinned by the CI/CD DAG but not a trigger of JADE QA")

    def test_master_runs_on_every_push(self):
        # Owner decision 2026-11-01: every master SHA must carry JADE QA evidence (FOCUS5 H05), so the
        # push trigger has no path filter; pull requests keep the complete filter checked above.
        on = WORKFLOW.read_text(encoding="utf-8").split("\njobs:", 1)[0]
        self.assertRegex(on, r"\n  push:\n    branches: \[master\]\n  workflow_dispatch:")
        self.assertEqual(workflow_filters("push"), [])
        self.assertTrue(workflow_filters("pull_request"))

    def test_launcher_runs_on_every_pr_and_on_master(self):
        wf = (ROOT / ".github/workflows/gogreen-launcher.yml").read_text(encoding="utf-8").split("\njobs:", 1)[0]
        self.assertNotIn("paths:", wf, "the launcher pins page titles across the repository; a path filter misses them")
        self.assertIn("  push:\n    branches: [master]", wf)


class Report(unittest.TestCase):
    def test_clean_report_passes(self):
        self.assertEqual(regen.report([]), 0)

    def test_stale_report_names_first_step_and_fix(self):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = regen.report([(regen.by_id()["cicd_dag"], "stale"), (regen.by_id()["cicd_dag_page"], "stale")])
        self.assertEqual(rc, 1)
        self.assertIn("first stale step: cicd_dag; fix: python mission-control/jade_temple/tools/regen.py --write",
                      buf.getvalue())

    def test_external_step_points_at_its_note(self):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            regen.report([(regen.by_id()["pprocess"], "stale")])
        self.assertIn("external: live EVERRED harvest", buf.getvalue())

    def test_list_mode(self):
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(regen.main(["--list"]), 0)


if __name__ == "__main__":
    unittest.main()
