"""Bounded native GitHub REST intake tests using the real pinned ABACUS producer."""
import copy
import os
import unittest
from pathlib import Path

from mip_native_bridge import collect, canonical_producer, https_get, project

SHA = "a" * 40
PROVIDER = Path(os.environ.get("MIP_ABACUS_ROOT", "providers/ABACUS"))
PIN = os.environ.get("MIP_ABACUS_SHA", "22c90e0412d0ecc8384917df5e7e19a3195ce86b")


def run(identity, conclusion):
    return {
        "id": identity, "run_attempt": 1, "head_sha": SHA,
        "name": "CI", "path": ".github/workflows/ci.yml",
        "html_url": f"https://github.com/GBOGEB/ABACUS/actions/runs/{identity}",
        "status": "completed", "conclusion": conclusion,
        "created_at": "2026-10-16T10:00:00Z",
    }


def job(identity, run_id, conclusion):
    return {
        "id": identity, "run_id": run_id, "run_attempt": 1,
        "head_sha": SHA, "name": f"test-job-{run_id}",
        "status": "completed", "conclusion": conclusion,
        "created_at": "2026-10-16T10:00:05Z",
        "started_at": "2026-10-16T10:00:25Z",
        "completed_at": "2026-10-16T10:01:00Z",
        "steps": [
            {"name": "checkout", "number": 1, "status": "completed",
             "conclusion": "success"},
            {"name": "pytest", "number": 2, "status": "completed",
             "conclusion": conclusion},
        ],
    }


def source():
    return {401: run(401, "success"), 402: run(402, "failure")}, {
        401: [job(601, 401, "success")],
        402: [job(602, 402, "failure")],
    }


def getter_factory():
    runs, jobs = source()
    def get(path):
        parts = path.split("/")
        identity = int(parts[6])
        if "/jobs?" in path:
            return {"total_count": len(jobs[identity]),
                    "jobs": copy.deepcopy(jobs[identity])}
        return copy.deepcopy(runs[identity])
    return get, runs, jobs


class NativeBridgeTests(unittest.TestCase):
    def test_mocked_exact_native_source_and_job_denominators(self):
        getter, _, _ = getter_factory()
        result = collect(SHA, [[401, 1], [402, 1]], getter)
        self.assertEqual(len(result["runs"]), 2)
        self.assertEqual(len(result["jobs"]), 2)
        self.assertEqual(result["jobs"][1]["steps"][1]["name"], "pytest")
        self.assertEqual(result["gate_bindings"], {})

    def test_native_canonical_producer_consumer_receipt(self):
        if not (PROVIDER / "tools" / "mip_ci_wave_telemetry.py").is_file():
            self.skipTest("exact pinned ABACUS checkout required")
        module = canonical_producer(PROVIDER, PIN)
        getter, _, _ = getter_factory()
        result = project(SHA, [[401, 1], [402, 1]], module, getter=getter)
        self.assertEqual(result["selected_workflow_count"], 2)
        self.assertEqual(result["selected_job_count"], 2)
        self.assertEqual(result["observed"]["workflow_success_n"], 1)
        self.assertEqual(result["first_red"]["unique_signatures"], 1)
        self.assertEqual(result["first_red"]["manifestations"], 1)
        self.assertEqual(result["first_red"]["red_job_denominator"], 1)
        self.assertEqual(result["first_red"]["attribution_fraction"], 1.0)
        self.assertEqual(result["confidence_intervals"]["95"]["estimate"], None)
        self.assertFalse(result["native_artifact_zip_bytes_authenticated"])
        self.assertIsNone(result["formal_root_closures"])
        self.assertEqual(result["admission"], "HOLD")

    def test_native_mismatched_run_head_and_attempt_rejected(self):
        getter, runs, _ = getter_factory()
        for key, value in (("head_sha", "b" * 40), ("run_attempt", 2)):
            with self.subTest(key=key):
                before = runs[401][key]
                runs[401][key] = value
                with self.assertRaises(ValueError):
                    collect(SHA, [[401, 1]], getter)
                runs[401][key] = before

    def test_wrong_job_sha_id_and_attempt_rejected(self):
        getter, _, jobs = getter_factory()
        for key, value in (("head_sha", "b" * 40),
                           ("run_attempt", 2), ("run_id", 5555)):
            with self.subTest(key=key):
                old = jobs[401][0][key]
                jobs[401][0][key] = value
                with self.assertRaises(ValueError):
                    collect(SHA, [[401, 1]], getter)
                jobs[401][0][key] = old

    def test_duplicate_run_selection_and_false_numbers_rejected(self):
        getter, _, _ = getter_factory()
        for selection in ([[401, 1], [401, 1]], [[401, True]], [[0, 1]],
                          [[401, 0]], [["401", 1]]):
            with self.subTest(selection=selection):
                with self.assertRaises(ValueError):
                    collect(SHA, selection, getter)

    def test_partial_pagination_or_mismatched_total_rejected(self):
        getter, _, _ = getter_factory()
        def partial(url):
            if "/jobs?" in url:
                return {"total_count": 2, "jobs": []}
            return getter(url)
        with self.assertRaises(ValueError):
            collect(SHA, [[401, 1]], partial)

    def test_reject_url_traversal_no_network_request(self):
        for path in (
            "/repos/GBOGEB/ABACUS/actions/runs/../secrets",
            "https://attacker.invalid/anything",
            "/repos/GBOGEB/ABACUS/actions/runs/401/jobs",
        ):
            with self.subTest(path=path):
                with self.assertRaisesRegex(ValueError, "exact native"):
                    https_get(path)

    def test_provider_sha_mismatch_fails_without_source_fallback(self):
        if not PROVIDER.is_dir():
            self.skipTest("no local ABACUS checkout")
        with self.assertRaisesRegex(ValueError, "source drift"):
            canonical_producer(PROVIDER, "b" * 40)


if __name__ == "__main__":
    unittest.main()
