"""Bounded native GitHub REST intake tests using the real pinned ABACUS producer."""
import copy
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mip_native_bridge import (
    collect, canonical_producer, https_get, main, project, validate_manifest,
)

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

    def test_verified_pr_census_exact_event_population(self):
        from mip_native_bridge import validate_manifest
        manifest = {
            "schema": "code-purple.mip.native-pr-census.v1",
            "repository": "GBOGEB/ABACUS", "event": "pull_request",
            "head_sha": SHA, "expected_total": 2,
            "run_attempts": [[401, 1], [402, 1]],
        }
        getter, native_runs, _ = getter_factory()
        def census_get(path):
            if "event=pull_request" in path:
                return {"total_count": 2, "workflow_runs": [
                    {**copy.deepcopy(run), "event": "pull_request"}
                    for run in native_runs.values()
                ]}
            return getter(path)
        source, ids = validate_manifest(manifest, census_get)
        self.assertEqual(source, SHA)
        self.assertEqual(ids, [[401, 1], [402, 1]])
        changed = copy.deepcopy(manifest)
        changed["run_attempts"][0][1] = 2
        with self.assertRaisesRegex(ValueError, "not equal to full"):
            validate_manifest(changed, census_get)
        changed = copy.deepcopy(manifest)
        changed["expected_total"] = 3
        with self.assertRaisesRegex(ValueError, "incomplete"):
            validate_manifest(changed, census_get)
        def new_native_run(path):
            if "event=pull_request" in path:
                return {"total_count": 3, "workflow_runs": []}
            return getter(path)
        with self.assertRaisesRegex(ValueError, "population changed"):
            validate_manifest(manifest, new_native_run)

    def test_manifest_malformed_source_and_authority_rejected(self):
        from mip_native_bridge import validate_manifest
        base = {
            "schema": "code-purple.mip.native-pr-census.v1",
            "repository": "GBOGEB/ABACUS", "event": "pull_request",
            "head_sha": SHA, "expected_total": 2,
            "run_attempts": [[401, 1], [402, 1]],
        }
        for key, value in (("head_sha", "not-sha"),
                           ("repository", "GBOGEB/other"),
                           ("event", "workflow_dispatch"),
                           ("expected_total", True)):
            with self.subTest(key=key):
                q = copy.deepcopy(base)
                q[key] = value
                with self.assertRaises(ValueError):
                    validate_manifest(q, getter=lambda url: {})

    def test_http_non_200_never_redirects_with_token(self):
        connections = []

        class Response:
            def __init__(self, status):
                self.status = status

            def read(self, size=-1):
                return io.BytesIO(b'{"id":401}').read(size)

        class Connection:
            default_status = 302

            def __init__(self, host, timeout):
                self.host, self.timeout = host, timeout
                self.status = self.default_status
                self.closed = False
                connections.append(self)

            def request(self, method, path, headers):
                self.method, self.path, self.headers = method, path, headers

            def getresponse(self):
                return Response(self.status)

            def close(self):
                self.closed = True

        with patch("mip_native_bridge.HTTPSConnection", Connection):
            path = "/repos/GBOGEB/ABACUS/actions/runs/401"
            with self.assertRaisesRegex(ValueError, "HTTP 302"):
                https_get(path, token="synthetic-test-token")
            self.assertEqual(connections[0].host, "api.github.com")
            self.assertEqual(connections[0].headers["Authorization"],
                             "Bearer synthetic-test-token")
            self.assertTrue(connections[0].closed)
            Connection.default_status = 200
            self.assertEqual(https_get(path)["id"], 401)
            self.assertTrue(connections[-1].closed)

    def test_101_native_jobs_paginate_without_duplicate_credit(self):
        getter, runs, _ = getter_factory()
        observed = [job(i + 1000, 401, "success") for i in range(101)]

        def paged(path):
            if "/jobs?" in path:
                page = int(path.split("page=")[-1])
                return {"total_count": 101,
                        "jobs": copy.deepcopy(observed[(page-1)*100:page*100])}
            return getter(path)

        result = collect(SHA, [[401, 1]], paged)
        self.assertEqual(len(result["jobs"]), 101)
        self.assertEqual(len({x["id"] for x in result["jobs"]}), 101)
        observed[-1]["id"] = observed[0]["id"]
        with self.assertRaisesRegex(ValueError, "native job"):
            collect(SHA, [[401, 1]], paged)

    def test_main_manifest_source_binding_and_atomic_replay(self):
        if not (PROVIDER / "tools" / "mip_ci_wave_telemetry.py").is_file():
            self.skipTest("pinned producer checkout absent")
        getter, runs, _ = getter_factory()

        def api(path, token=None):
            if "event=pull_request" in path:
                return {"total_count": 2, "workflow_runs": [
                    {**copy.deepcopy(run), "event": "pull_request"}
                    for run in runs.values()
                ]}
            return getter(path)

        manifest = {
            "schema": "code-purple.mip.native-pr-census.v1",
            "repository": "GBOGEB/ABACUS", "event": "pull_request",
            "head_sha": SHA, "expected_total": 2,
            "run_attempts": [[401, 1], [402, 1]],
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path = root / "manifest.json"
            output_path = root / "native.json"
            manifest_path.write_text(json.dumps(manifest))
            command = ["--sha", SHA, "--abacus-checkout", str(PROVIDER),
                       "--producer-sha", PIN, "--manifest",
                       str(manifest_path), "--out", str(output_path)]
            with patch("mip_native_bridge.https_get", side_effect=api):
                self.assertEqual(main(command), 0)
                expected = output_path.read_bytes()
                result = json.loads(expected)
                self.assertTrue(result["pull_request_event_head_cohort_verified"])
                self.assertEqual(result["observed"]["workflow_total_n"], 2)
                self.assertIsNone(result["formal_root_closures"])
                self.assertEqual(main(command), 0)
                self.assertEqual(output_path.read_bytes(), expected)
                with self.assertRaisesRegex(ValueError, "use exact"):
                    main(command + ["--run", "401:1"])
                with self.assertRaisesRegex(ValueError, "CLI source head"):
                    main(["--sha", "b" * 40] + command[2:])
            self.assertEqual(json.loads(output_path.read_text())["admission"],
                             "HOLD")

    def test_invalid_native_step_list_and_oversized_job_denominator(self):
        getter, runs, jobs = getter_factory()
        jobs[401][0]["steps"] = "untrusted"
        with self.assertRaisesRegex(ValueError, "step list"):
            collect(SHA, [[401, 1]], getter)
        jobs[401][0]["steps"] = []
        def huge(path):
            if "/jobs?" in path:
                return {"total_count": 1201, "jobs": []}
            return getter(path)
        with self.assertRaisesRegex(ValueError, "jobs page"):
            collect(SHA, [[401, 1]], huge)

    def test_provider_sha_mismatch_fails_without_source_fallback(self):
        if not PROVIDER.is_dir():
            self.skipTest("no local ABACUS checkout")
        with self.assertRaisesRegex(ValueError, "source drift"):
            canonical_producer(PROVIDER, "b" * 40)


if __name__ == "__main__":
    unittest.main()
