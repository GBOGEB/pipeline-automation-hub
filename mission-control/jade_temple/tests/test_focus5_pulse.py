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


def fake_github(protected=False, rules=(), runs=(), readme=True, tags=()):
    calls = []

    def lookup(path):
        calls.append(path)
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
            "html_url": "https://github.com/O/R/actions/runs/9", "created_at": created}


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
