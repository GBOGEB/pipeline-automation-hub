"""Native terminal and archive attestation negative tests (offline fixtures)."""
import copy
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from metric_atlas.census import CensusError, request
from metric_atlas.postflight import audit, verify_zip

HEADS = {"ABACUS": None, "CODEX": "b" * 40, "QPS_ENGINEERING": "c" * 40}


def fixture():
    manifest = request("N3", HEADS)
    q = manifest["requests"][0]
    receipt = {
        "schema": "qps-metric-receipt/v1",
        "request_id": q["request_id"], "lane": q["lane"],
        "repo": q["repo"], "target_sha": q["expected_sha"],
        "execution_sha": q["expected_sha"], "route": "native_checks",
        "run_id": 31, "run_attempt": 1, "job_id": 101,
        "outcome": "SUCCESS", "evidence_class": "GITHUB_CHECK_METADATA_ONLY",
        "tests": {}, "coverage": {}, "authority_transfer": False,
        "engineering_acceptance": False
    }
    run = {"id": 31, "head_sha": q["expected_sha"],
           "run_attempt": 1, "event": "workflow_dispatch",
           "path": "GBOGEB/CODEX/.github/workflows/qps-metric-census-receiver.yml",
           "status": "completed", "conclusion": "success"}
    job = {"id": 101, "run_id": 31, "run_attempt": 1,
           "head_sha": q["expected_sha"],
           "name": "native-check-census / QPS Census receiver native_checks",
           "status": "completed", "conclusion": "success"}
    return manifest, receipt, run, job


def zip_receipt(path, receipt, name="qps-census/native_checks.json"):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(name, json.dumps(receipt))


class PostflightTests(unittest.TestCase):
    def test_no_receipts_no_native_proof(self):
        m, _, _, _ = fixture()
        r = audit(m, [])
        self.assertEqual(r["eligible_repos"], 3)
        self.assertEqual(r["planned_routes"], 4)
        self.assertEqual(r["terminal_native_jobs_confirmed"], 0)
        self.assertEqual(r["byte_verified_routes"], 0)
        self.assertIsNone(r["native_test_count"])

    def test_receiver_success_claim_is_not_terminal_proof(self):
        m, rec, _, _ = fixture()
        r = audit(m, [rec])
        self.assertEqual(r["rows"][0]["status"], "HOLD_NATIVE_LOOKUP_REQUIRED")
        self.assertEqual(r["terminal_native_jobs_confirmed"], 0)

    def test_live_terminal_but_zip_unknown(self):
        m, rec, run, job = fixture()
        r = audit(m, [rec], native_fetch=lambda *_: (run, job))
        self.assertEqual(r["terminal_native_jobs_confirmed"], 1)
        self.assertEqual(r["rows"][0]["status"], "HOLD_ARTIFACT_BYTES_UNKNOWN")
        self.assertEqual(r["byte_verified_routes"], 0)
        self.assertEqual(r["merge_admission"], "HOLD")

    def test_native_and_real_zip_bytes(self):
        m, rec, run, job = fixture()
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "native.zip"
            zip_receipt(path, rec)
            key = f"{rec['repo']}|{rec['run_id']}|{rec['route']}"
            r = audit(m, [rec], native_fetch=lambda *_: (run, job),
                      zip_paths={key: str(path)})
        self.assertEqual(r["byte_verified_routes"], 1)
        self.assertEqual(r["rows"][0]["status"], "VERIFIED_LOCAL_ZIP_AND_NATIVE_JOB")
        self.assertEqual(len(r["rows"][0]["artifact"]["zip_sha256"]), 64)
        self.assertFalse(r["canonical_530_zip_acceptance"])
        self.assertIsNone(r["coverage_branch_uplift"])

    def test_wrong_source_sha_rejected(self):
        m, rec, run, job = fixture()
        run["head_sha"] = "a" * 40
        r = audit(m, [rec], native_fetch=lambda *_: (run, job))
        self.assertEqual(r["rows"][0]["status"], "HOLD_RUN_IDENTITY_MISMATCH")

    def test_wrong_attempt_rejected(self):
        m, rec, run, job = fixture()
        job["run_attempt"] = 2
        r = audit(m, [rec], native_fetch=lambda *_: (run, job))
        self.assertEqual(r["rows"][0]["status"], "HOLD_ATTEMPT_MISMATCH")

    def test_wrong_job_id_rejected(self):
        m, rec, run, job = fixture()
        job["id"] = 999
        r = audit(m, [rec], native_fetch=lambda *_: (run, job))
        self.assertEqual(r["rows"][0]["status"], "HOLD_JOB_IDENTITY_MISMATCH")

    def test_job_failure_is_not_success(self):
        m, rec, run, job = fixture()
        job["conclusion"] = "failure"
        r = audit(m, [rec], native_fetch=lambda *_: (run, job))
        self.assertEqual(r["rows"][0]["status"], "HOLD_TERMINAL_FIRST_RED")

    def test_ongoing_workflow_not_terminal(self):
        m, rec, run, job = fixture()
        run["status"] = "in_progress"
        r = audit(m, [rec], native_fetch=lambda *_: (run, job))
        self.assertEqual(r["rows"][0]["status"], "HOLD_RUN_NOT_TERMINAL")

    def test_wrong_trigger_rejected(self):
        m, rec, run, job = fixture()
        run["event"] = "push"
        r = audit(m, [rec], native_fetch=lambda *_: (run, job))
        self.assertEqual(r["rows"][0]["status"], "HOLD_UNEXPECTED_TRIGGER")

    def test_job_name_cannot_change_route(self):
        m, rec, run, job = fixture()
        job["name"] = "native-check-census / QPS Census receiver coverage_catalog"
        r = audit(m, [rec], native_fetch=lambda *_: (run, job))
        self.assertIn("HOLD_JOB", r["rows"][0]["status"])

    def test_missing_private_read_holds(self):
        m, rec, _, _ = fixture()
        def denied(*_):
            raise RuntimeError("private access denied")
        r = audit(m, [rec], native_fetch=denied)
        self.assertEqual(r["rows"][0]["status"], "HOLD_NATIVE_LOOKUP_DENIED")

    def test_duplicate_exact_receipt_not_counted_twice(self):
        m, rec, run, job = fixture()
        r = audit(m, [rec, copy.deepcopy(rec)],
                  native_fetch=lambda *_: (run, job))
        self.assertEqual(r["terminal_native_jobs_confirmed"], 1)

    def test_conflicting_distinct_receipts_hold(self):
        m, rec, run, job = fixture()
        newer = copy.deepcopy(rec)
        newer["job_id"] = 102
        r = audit(m, [rec, newer], native_fetch=lambda *_: (run, job))
        self.assertEqual(r["rows"][0]["status"], "HOLD_MULTIPLE_DISTINCT_RECEIPTS")

    def test_wrong_execution_sha_is_not_accepted(self):
        m, rec, _, _ = fixture()
        rec["execution_sha"] = "d" * 40
        with self.assertRaises(CensusError):
            audit(m, [rec])

    def test_zip_member_mismatch_is_rejected(self):
        _, rec, _, _ = fixture()
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.zip"
            other = dict(rec, request_id="QPS-" + "0" * 20)
            zip_receipt(p, other)
            with self.assertRaises(CensusError):
                verify_zip(p, rec)

    def test_zip_traversal_is_rejected_without_extraction(self):
        _, rec, _, _ = fixture()
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.zip"
            zip_receipt(p, rec, "../native_checks.json")
            with self.assertRaises(CensusError):
                verify_zip(p, rec)

    def test_unbounded_source_manifest_rejected(self):
        m, _, _, _ = fixture()
        m["eligible_repos"] = 4
        with self.assertRaises(CensusError):
            audit(m, [])

    def test_absent_security_or_coverage_is_not_pass(self):
        m, rec, run, job = fixture()
        r = audit(m, [rec], native_fetch=lambda *_: (run, job))
        self.assertIsNone(r["native_test_count"])
        self.assertIsNone(r["coverage_statement_uplift"])
        self.assertIsNone(r["root_closures_accepted"])
        self.assertFalse(r["qps_engineering_acceptance"])


if __name__ == "__main__":
    unittest.main()
