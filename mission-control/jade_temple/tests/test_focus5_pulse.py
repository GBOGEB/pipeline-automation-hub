"""Focus-five pulse observer: one SHA per repo per pulse, previous-pulse workflow
evidence re-checked on the new head only, protection and owner gates never
promoted to PASS, and the snapshot is accepted by rolling5."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("focus5_pulse", ROOT / "tools" / "focus5_pulse.py")
fp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fp)
spec5 = importlib.util.spec_from_file_location("rolling5", ROOT / "tools" / "rolling5.py")
r5 = importlib.util.module_from_spec(spec5)
spec5.loader.exec_module(r5)

NEW = "c" * 40


def fake_github(protected=False, rules=(), runs=(), readme=True, tags=(), started=True):
    calls = []

    def lookup(path):
        calls.append(path)
        if path.startswith("repos/O/R/actions/runs/") and "/jobs" in path:
            # started: a runner executed steps; not started: billing/spending-limit refusal
            steps = [{"name": "Run tests", "conclusion": "failure"}] if started else []
            return {"jobs": [{"conclusion": "failure", "run_attempt": 1,
                              "runner_id": 7 if started else 0, "steps": steps}]}
        if path == "repos/O/R":
            return {"default_branch": "main"}
        if path == "repos/O/R/commits/main":
            return {"sha": NEW}
        if path.startswith("repos/O/R/contents"):
            return [{"name": "README.md", "type": "file"}] if readme else [{"name": "x.py", "type": "file"}]
        if path.startswith("repos/O/R/actions/runs?head_sha="):
            assert NEW in path
            return {"workflow_runs": list(runs)}
        if path.startswith("repos/O/R/actions/runs/"):
            return {"path": ".github/workflows/ci.yml"}  # previous-pulse evidence run
        if path == "repos/O/R/branches/main":
            return {"protected": protected}
        if path == "repos/O/R/rules/branches/main":
            return [{"type": t} for t in rules]
        if path.startswith("repos/O/R/tags"):
            return [{"name": t, "commit": {"sha": NEW}} for t in tags]
        raise AssertionError(path)

    lookup.calls = calls
    return lookup


PREV = {"repo": "O/R", "rank": 1, "gates": [
    {"id": "H05", "status": "FAIL", "evidence": "https://github.com/O/R/actions/runs/123", "reason": "old"}]}


def run(path, conclusion, created="2026-10-25T00:00:00Z"):
    return {"path": path, "name": "CI", "status": "completed", "conclusion": conclusion, "id": 9,
            "run_attempt": 1, "html_url": "https://github.com/O/R/actions/runs/9", "created_at": created}


class Focus5PulseTests(unittest.TestCase):
    def gates(self, row):
        return {g["id"]: g["status"] for g in row["gates"]}

    def test_previous_workflow_is_rechecked_on_the_new_head(self):
        row = fp.observe_repo("O/R", PREV, fake_github(runs=[run(".github/workflows/ci.yml", "success")]))
        self.assertEqual(row["source_sha"], NEW)
        self.assertEqual(self.gates(row)["H05"], "PASS")
        self.assertEqual(self.gates(row)["H04"], "UNKNOWN")  # no previous evidence for H04

    def test_latest_completed_run_wins_and_missing_run_is_unknown(self):
        runs = [run(".github/workflows/ci.yml", "success", "2026-10-25T01:00:00Z"),
                run(".github/workflows/ci.yml", "failure", "2026-10-25T02:00:00Z")]
        self.assertEqual(self.gates(fp.observe_repo("O/R", PREV, fake_github(runs=runs)))["H05"], "FAIL")
        self.assertEqual(self.gates(fp.observe_repo("O/R", PREV, fake_github(runs=[])))["H05"], "UNKNOWN")

    def test_protection_never_passes_h08_and_owner_gates_stay_unknown(self):
        open_repo = self.gates(fp.observe_repo("O/R", None, fake_github()))
        self.assertEqual(open_repo["H08"], "FAIL")
        guarded = self.gates(fp.observe_repo("O/R", None, fake_github(True, ["pull_request"], tags=["v1"])))
        self.assertEqual(guarded["H08"], "UNKNOWN")
        for gid in ("H03", "H07", "H09", "H10", "H11", "H12"):
            self.assertEqual(guarded[gid], "UNKNOWN", gid)

    def test_head_sha_is_read_once_per_repo(self):
        gh = fake_github()
        fp.observe_repo("O/R", None, gh)
        self.assertEqual(gh.calls.count("repos/O/R/commits/main"), 1)

    def test_declared_workflows_override_previous_pulse_and_all_must_pass(self):
        declared = {"H05": [".github/workflows/a.yml", ".github/workflows/b.yml"]}
        both = [run(".github/workflows/a.yml", "success"), run(".github/workflows/b.yml", "success")]
        g = self.gates(fp.observe_repo("O/R", PREV, fake_github(runs=both), declared))
        self.assertEqual(g["H05"], "PASS")
        one = [run(".github/workflows/a.yml", "success")]  # b.yml never ran on this SHA
        self.assertEqual(self.gates(fp.observe_repo("O/R", PREV, fake_github(runs=one), declared))["H05"], "UNKNOWN")
        # the previous-pulse workflow (ci.yml) succeeding does not stand in for a declared one
        prev_only = [run(".github/workflows/ci.yml", "success")]
        self.assertEqual(self.gates(fp.observe_repo("O/R", PREV, fake_github(runs=prev_only), declared))["H05"], "UNKNOWN")

    def test_any_declared_failure_fails_and_cancelled_is_unknown(self):
        declared = {"H06": [".github/workflows/a.yml", ".github/workflows/b.yml"]}
        mixed = [run(".github/workflows/a.yml", "success"), run(".github/workflows/b.yml", "failure")]
        self.assertEqual(self.gates(fp.observe_repo("O/R", None, fake_github(runs=mixed), declared))["H06"], "FAIL")
        for c in ("cancelled", "skipped", None):
            runs = [run(".github/workflows/a.yml", "success"), run(".github/workflows/b.yml", c)]
            self.assertEqual(self.gates(fp.observe_repo("O/R", None, fake_github(runs=runs), declared))["H06"], "UNKNOWN", c)

    def test_failed_run_whose_jobs_never_started_is_unknown_not_fail(self):
        declared = {"H05": [".github/workflows/a.yml"]}
        failed = [run(".github/workflows/a.yml", "failure")]
        refused = fp.observe_repo("O/R", None, fake_github(runs=failed, started=False), declared)
        g = {x["id"]: x for x in refused["gates"]}
        self.assertEqual(g["H05"]["status"], "UNKNOWN")
        self.assertIn("not_started", g["H05"]["reason"])
        self.assertFalse([b for b in refused["blockers"] if b.startswith("H05")])
        executed = fp.observe_repo("O/R", None, fake_github(runs=failed, started=True), declared)
        self.assertEqual(self.gates(executed)["H05"], "FAIL")
        # previous-pulse fallback evidence gets the same treatment
        self.assertEqual(self.gates(fp.observe_repo("O/R", PREV, fake_github(
            runs=[run(".github/workflows/ci.yml", "failure")], started=False)))["H05"], "UNKNOWN")

    def test_started_job_on_a_later_page_keeps_the_failure(self):
        # 150 jobs: page 1 holds 100 never-started jobs, page 2 one job that ran and failed.
        calls = []

        def jobs_lookup(path):
            calls.append(path)
            page = int(path.rsplit("page=", 1)[1])
            idle = {"conclusion": "skipped", "run_attempt": 1, "steps": []}
            ran = {"conclusion": "failure", "run_attempt": 1, "steps": [{"name": "Run tests"}]}
            jobs = [idle] * 100 if page == 1 else [idle] * 49 + [ran]
            return {"total_count": 150, "jobs": jobs}

        self.assertTrue(fp.any_job_started("O/R", 9, 1, jobs_lookup))
        self.assertEqual(len(calls), 2)
        self.assertTrue(all("/attempts/1/jobs?" in call for call in calls))
        latest = {"a.yml": run("a.yml", "failure")}
        fp.mark_unstarted_failures("O/R", latest, ["a.yml"], jobs_lookup)
        self.assertEqual(latest["a.yml"]["conclusion"], "failure")

    def test_job_from_another_attempt_cannot_clear_failure(self):
        latest = {"a.yml": run("a.yml", "failure")}

        def jobs_lookup(path):
            page = int(path.rsplit("page=", 1)[1])
            if page == 1:
                jobs = [{"run_attempt": 1, "steps": []}] * 100
            else:
                jobs = [{"run_attempt": 2, "steps": []}]
            return {"total_count": 101, "jobs": jobs}

        fp.mark_unstarted_failures("O/R", latest, ["a.yml"], jobs_lookup)
        self.assertEqual(latest["a.yml"]["conclusion"], "failure")

    def test_all_pages_unstarted_is_not_started_and_paging_stops(self):
        calls = []

        def jobs_lookup(path):
            calls.append(path)
            page = int(path.rsplit("page=", 1)[1])
            return {"total_count": 130, "jobs": [{"run_attempt": 1, "steps": []}] * (100 if page == 1 else 30)}

        self.assertFalse(fp.any_job_started("O/R", 9, 1, jobs_lookup))
        self.assertEqual(len(calls), 2)

    def test_registry_rejects_owner_gates_and_unstated_evidence(self):
        ok = {"schema": "jade.focus5.gate_evidence_registry.v1",
              "repos": {"O/R": {"H05": [{"workflow": ".github/workflows/a.yml", "proves": "tests"}]}}}
        self.assertEqual(fp.validate_registry(ok), {"O/R": {"H05": [".github/workflows/a.yml"]}})
        bad = [("H09", ".github/workflows/a.yml", "tests"), ("H07", ".github/workflows/a.yml", "scan"),
               ("H05", "scripts/a.yml", "tests"), ("H05", ".github/workflows/a.yml", " ")]
        for gid, wfp, proves in bad:
            reg = {"schema": ok["schema"], "repos": {"O/R": {gid: [{"workflow": wfp, "proves": proves}]}}}
            with self.assertRaises(ValueError, msg=(gid, wfp)):
                fp.validate_registry(reg)
        dup = {"schema": ok["schema"], "repos": {"O/R": {"H05": ok["repos"]["O/R"]["H05"] * 2}}}
        with self.assertRaises(ValueError):
            fp.validate_registry(dup)

    def test_committed_registry_is_valid_and_covers_only_the_window(self):
        import json
        reg = fp.load_registry(ROOT)
        window = json.loads((ROOT / fp.WINDOW).read_text(encoding="utf-8"))["window"]["current"]
        self.assertTrue(reg)
        self.assertLessEqual(set(reg), set(window))

    def test_snapshot_shape_is_accepted_by_rolling5(self):
        prev = {"schema": "s", "source": {"observed_date": "2026-10-19"}, "metrics": {}, "rows": [PREV]}
        snap = fp.build_snapshot(prev, ["O/R"], "2026-10-25", fake_github())
        rows = r5.rows_of(snap)
        self.assertEqual(rows["O/R"]["source_sha"], NEW)
        self.assertEqual(snap["metrics"]["required_gate_total"], 12)
        self.assertIsNone(snap["metrics"]["globally_admitted_point_release"])
        self.assertFalse(snap["source"]["release_authority_transfer"])


if __name__ == "__main__":
    unittest.main()
