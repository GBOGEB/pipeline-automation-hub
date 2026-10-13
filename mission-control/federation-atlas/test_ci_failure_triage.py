"""Regression contracts for four-lane CI evidence; no fabricated green states."""
import json
import unittest
from pathlib import Path

RECEIPT = Path(__file__).with_name("CI_FAILURE_TRIAGE_20261013_v1.json")


class CIFailureTriageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(RECEIPT.read_text(encoding="utf-8"))

    def test_distinct_lanes_and_known_pull_requests(self):
        records = self.data["records"]
        self.assertEqual({r["pr"] for r in records}, {1902, 1907, 523})
        for record in records:
            self.assertTrue(all(k in record for k in (
                "engineering", "security", "governance", "execution")))

    def test_unknown_metrics_never_default_to_zero(self):
        for record in self.data["records"]:
            self.assertIsNone(record["execution"]["active_workers"])
            self.assertIsNone(record["execution"]["queue_seconds"])
            self.assertIsNone(record["execution"]["time_to_green_seconds"])
            self.assertIsNone(record["engineering"]["coverage"]["covered"])
            self.assertIsNone(record["engineering"]["coverage"]["eligible"])

    def test_governance_authority_not_transferred(self):
        self.assertIs(self.data["authority_transfer"], False)
        self.assertEqual(self.data["formal_credit_delta"], 0)
        self.assertEqual(self.data["engineering_credit_delta"], 0)

    def test_unverified_codeql_alerts_cannot_be_credited_closed(self):
        record = next(r for r in self.data["records"] if r["pr"] == 523)
        self.assertEqual(record["security"]["reported_new_high_alerts"], 10)
        self.assertIsNone(record["security"]["introduced_count"])
        self.assertIsNone(record["security"]["existing_count"])
        self.assertIn("pending", record["security"]["independent_disposition"])

    def test_crew_and_rhel_gates_require_real_evidence(self):
        gates = self.data["action_triggers"]
        self.assertIn("authenticated", gates["LDAB"])
        self.assertIn("RHEL8", gates["RHEL"])
        self.assertIn("RHEL9", gates["RHEL"])
        self.assertIn("paired outcomes", gates["BT"])
        self.assertIn("comparable", gates["PCA"])

    def test_repair_head_and_pending_test_admission(self):
        record = next(r for r in self.data["records"] if r["pr"] == 1907)
        self.assertEqual(record["head_at_read"], record["engineering"]["docker_fix_commit"])
        self.assertIn("pending", record["engineering"]["docker_fix_verification"])
        self.assertEqual(record["governance"]["feedback_gate"], "success on repair head")


if __name__ == "__main__":
    unittest.main()
