"""Security/identity/measurement regression checks for disjoint QPS census."""
import copy
import unittest
from metric_atlas.census import CensusError, request, rollup, validate_receipt

H = {"ABACUS": "a" * 40, "CODEX": "b" * 40, "QPS_ENGINEERING": "c" * 40}


def good_receipt(m, lane=0, route="native_checks", job_id=100):
    q = m["requests"][lane]
    return {"schema": "qps-metric-receipt/v1", "request_id": q["request_id"],
            "lane": q["lane"], "repo": q["repo"], "target_sha": q["expected_sha"],
            "execution_sha": q["expected_sha"], "route": route, "run_id": 2,
            "run_attempt": 1, "job_id": job_id, "outcome": "SUCCESS",
            "evidence_class": "GITHUB_CHECK_METADATA_ONLY", "tests": {}, "coverage": {},
            "authority_transfer": False, "engineering_acceptance": False}


class CensusTests(unittest.TestCase):
    def setUp(self):
        self.m = request("N1", H)

    def test_stable_disjoint_ids(self):
        self.assertEqual(self.m, request("N1", H))
        self.assertEqual(len({r["request_id"] for r in self.m["requests"]}), 3)

    def test_allowlist_and_sha(self):
        with self.assertRaises(CensusError):
            request("N1", dict(H, BAD="d"*40))
        with self.assertRaises(CensusError):
            request("N1", dict(H, ABACUS="deadbeef"))

    def test_unreceived_preserves_unknown(self):
        summary = rollup(self.m, [])
        self.assertEqual(summary["observed_repos"], 0)
        self.assertIsNone(summary["tests_executed"])
        self.assertIsNone(summary["worker_hours"])

    def test_partial_breadth_and_route_dag(self):
        a = good_receipt(self.m)
        b = good_receipt(self.m, route="coverage_catalog", job_id=101)
        result = rollup(self.m, [a, b])
        self.assertEqual((result["observed_repos"], result["fully_observed_repos"]), (1, 1))
        self.assertEqual(result["native_job_receipts"], 2)

    def test_duplicate_dedup_and_conflict(self):
        a = good_receipt(self.m)
        self.assertEqual(rollup(self.m, [a, a])["native_job_receipts"], 1)
        x = copy.deepcopy(a)
        x["outcome"] = "FAILURE"
        with self.assertRaises(CensusError):
            rollup(self.m, [a, x])

    def test_wrong_head_cannot_promote(self):
        a = good_receipt(self.m)
        a["target_sha"] = "f" * 40
        with self.assertRaises(CensusError):
            validate_receipt(a, self.m)

    def test_incomplete_native_identity_rejected(self):
        a = good_receipt(self.m)
        a["job_id"] = None
        with self.assertRaises(CensusError):
            validate_receipt(a, self.m)

    def test_test_counts_must_be_native_log_bound(self):
        a = good_receipt(self.m)
        a["tests"] = {"executed": 10, "passed": 10, "failed": 0, "skipped": 0}
        with self.assertRaises(CensusError):
            validate_receipt(a, self.m)
        a["evidence_class"] = "NATIVE_TEST_COUNTS_WITH_LOG_RECEIPT"
        a["test_log_url"] = "https://github.com/GBOGEB/ABACUS/actions/runs/2"
        a["scope_fingerprint"] = "pytest-3.12-v1"
        validate_receipt(a, self.m)

    def test_coverage_requires_matching_denominator_receipt(self):
        a = good_receipt(self.m)
        a["evidence_class"] = "NATIVE_TEST_COUNTS_WITH_LOG_RECEIPT"
        a["coverage"] = {"statements": 66, "covered_statements": 80,
                         "scope_fingerprint": "fp", "artifact_sha256": "a"*64}
        with self.assertRaises(CensusError):
            validate_receipt(a, self.m)

    def test_authority_never_transfers(self):
        a = good_receipt(self.m)
        a["engineering_acceptance"] = True
        with self.assertRaises(CensusError):
            validate_receipt(a, self.m)

    def test_unknown_dispatch_selector(self):
        with self.assertRaises(CensusError):
            request("N1", H, selector="arbitrary_shell")


if __name__ == "__main__":
    unittest.main()
