"""Mocked GitHub API boundaries: no writes, no invented GREEN or root closures."""
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("gogreen_collect", ROOT / "collect_readonly.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
import spine


def fixture():
    return json.loads((ROOT / "samples/fleet_g0.json").read_text(encoding="utf-8"))


class TestPassiveLiveScanner(unittest.TestCase):
    def test_strict_green_candidate_not_native_test_credit(self):
        f = fixture()
        sha = f["repositories"][0]["head_sha"]
        repo = "GBOGEB/ABACUS"
        def fetch(path):
            if path.endswith("/actions/runs?head_sha=" + sha + "&per_page=2"):
                return {"total_count": 30, "workflow_runs": [
                    {"id": 400, "head_sha": sha, "run_attempt": 1,
                     "run_number": 8, "status": "completed", "conclusion": "success",
                     "name": "CODEQL scanner"},
                    {"id": 401, "head_sha": sha, "run_attempt": 1,
                     "run_number": 9, "status": "completed", "conclusion": "failure",
                     "name": "Expected security first-red"}]}
            if path.endswith("/actions/runs/400/jobs?per_page=3"):
                return {"jobs": [{"id": 500, "status": "completed", "conclusion": "success", "name": "Scan"}]}
            return {"total_count": 0, "workflow_runs": []}
        scan, meta = mod.scan(f, fetch)
        p, _, _ = spine.build(scan)
        self.assertEqual(p["breadth"]["native_green_status_only_observations"], 1)
        self.assertEqual(p["breadth"]["native_green_metadata_observations"], 1)
        self.assertEqual(p["breadth"]["native_green_bytes_verified_observations"], 0)
        self.assertEqual(p["breadth"]["coverage_gain_percentage_points"], None)
        self.assertEqual(len(meta["unattributed_non_green"]), 1)
        self.assertEqual(meta["unattributed_non_green"][0]["root_id"], None)
        self.assertTrue(meta["repositories"][0]["truncated"])
        self.assertFalse(meta["complete_fleet_census"])
        self.assertEqual(scan["observations"][-1]["config_identity"], "UNKNOWN")

    def test_cross_source_sha_spoof_never_admitted(self):
        f = fixture()
        def fetch(path):
            if "/actions/runs?" in path:
                return {"total_count": 1, "workflow_runs": [{"id": 777,
                    "head_sha": "e" * 40, "run_attempt": 1,
                    "run_number": 7, "status": "completed", "conclusion": "success"}]}
            raise AssertionError("must not fetch a mismatched source's jobs")
        _, meta = mod.scan(f, fetch)
        self.assertEqual(len(meta["collection_errors"]), 6)
        self.assertTrue(all(e["kind"] == "RUN_SHA_MISMATCH" for e in meta["collection_errors"]))

    def test_http_errors_remain_unknown_not_zero(self):
        def fetch(_):
            raise ValueError("unavailable repo")
        f, meta = mod.scan(fixture(), fetch)
        self.assertEqual(len(meta["collection_errors"]), 6)
        self.assertTrue(all(r["fetch_state"] == "UNKNOWN_ERROR" for r in meta["repositories"]))
        self.assertEqual(len(f["observations"]), 1)  # historical proof preserved

    def test_invalid_budget_rejected(self):
        for k in (0, 9, True):
            with self.subTest(k=k), self.assertRaises(ValueError):
                mod.scan(fixture(), lambda _: {}, max_runs=k)

    def test_known_baseline_requires_exact_sha(self):
        f = fixture()
        f["observations"][0]["source_sha"] = "c" * 40
        with self.assertRaises(ValueError):
            mod.scan(f, lambda _: {"workflow_runs": []})


if __name__ == "__main__":
    unittest.main()
