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

# Paths the CI/CD DAG binds by blob OID that the JADE workflow's pull_request filter does not cover.
# Editing one merges green and turns the next JADE PR red. Ratchet: a new gap fails here; Phase 2 widens
# the filter and empties this list.
KNOWN_UNFILTERED = {
    ".github/workflows/gm-iv-recon4-governor.yml",
    ".github/workflows/gm-v-3pstar-mip-control.yml",
    ".github/workflows/gm-v-governor-readiness.yml",
    ".github/workflows/mission-control-n3-evidence.yml",
    ".github/workflows/zero-test-gate-guard.yml",
    "mission-control/federation-atlas/CODE_PURPLE_BD_QUEUE_v1.json",
    "mission-control/federation-atlas/CODE_PURPLE_BEAMS_DAG_v1.json",
    "mission-control/gogreen/red_trace/README.md",
    "scripts/zero_test_gate_audit.py",
}


# Scripts the JADE workflow runs that produce no committed output (receipt run, browser QA job).
NOT_GENERATORS = re.compile(r"stop_rules\.py|run_\w+_browser_qa\.py")


def workflow_filters():
    wf = WORKFLOW.read_text(encoding="utf-8")
    return re.findall(r"- '([^']+)'", wf.split("pull_request:", 1)[1].split("workflow_dispatch", 1)[0])


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
    def test_no_new_pinned_path_outside_the_workflow_filter(self):
        pats = [g.replace("**", "*") for g in workflow_filters()]
        gaps = {p for p in dag_bound_paths() if not any(fnmatch.fnmatchcase(p, g) for g in pats)}
        self.assertEqual(gaps - KNOWN_UNFILTERED, set(), "pinned by the DAG but not a trigger of JADE QA")


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
