"""Adversarial regression tests for public QBD planning, never admission."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import qbd_contract  # noqa: E402

SOURCE = ROOT / "QBD_W49_PUBLIC_DISJOINT_COHORT_20261019.json"


class QBDContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads(SOURCE.read_text(encoding="utf-8"))

    def doc(self):
        return copy.deepcopy(self.source)

    def assert_rejects(self, document):
        with self.assertRaises(ValueError):
            qbd_contract.validate(document)

    def test_frozen_structural_projection(self):
        result = qbd_contract.validate(self.doc())
        self.assertEqual(result["status"], "STRUCTURAL_PASS_NOT_NATIVE_AUTHENTICATION")
        self.assertEqual(result["historic_failed_associations"], 260)
        self.assertIsNone(result["accepted_root_closures"])

    def test_false_security_or_admission_credit(self):
        obj = self.doc()
        obj["source_authority"]["merge_admission"] = "PASS"
        self.assert_rejects(obj)
        obj = self.doc()
        obj["source_authority"]["security_waiver"] = True
        self.assert_rejects(obj)

    def test_private_qps_counts_never_public(self):
        obj = self.doc()
        obj["private_qps"]["open_issue_count"] = 58
        self.assert_rejects(obj)

    def test_denominator_mismatch(self):
        obj = self.doc()
        obj["metrics"]["issue_count_public_three_repos"] += 1
        self.assert_rejects(obj)

    def test_forged_root_closure(self):
        obj = self.doc()
        obj["historical_abacus_n0"]["causal_root_count"] = 5
        self.assert_rejects(obj)

    def test_wrong_or_missing_job_identity(self):
        obj = self.doc()
        obj["observed_abacus_pr2077"]["native_failure_jobs"][0]["native_job"] = 0
        self.assert_rejects(obj)
        obj = self.doc()
        obj["observed_abacus_pr2077"]["native_failure_jobs"][0]["run_attempt"] = None
        self.assert_rejects(obj)

    def test_unverified_native_receipt_promotion(self):
        obj = self.doc()
        obj["observed_abacus_pr2077"]["native_failure_jobs"][0]["causal_root_confirmed"] = True
        self.assert_rejects(obj)

    def test_overlapping_worker_lease(self):
        obj = self.doc()
        obj["proposed_writers"][1]["scope"] = ["tools/everred_v3/scripts"]
        self.assert_rejects(obj)

    def test_unauthorized_dispatch(self):
        obj = self.doc()
        obj["parallel_capacity"]["writer_dispatch_executed"] = True
        self.assert_rejects(obj)

    def test_graph_cycle(self):
        obj = self.doc()
        obj["diagram"]["edges"].append({
            "from": "ROOT_CLOSE", "to": "LEASE", "relation": "depends_on",
            "binding": "DECLARED_NO_NATIVE_CROSS_REPO_PROOF",
        })
        self.assert_rejects(obj)

    def test_missing_graph_node(self):
        obj = self.doc()
        obj["diagram"]["edges"][0]["to"] = "MISSING_RECEIVER"
        self.assert_rejects(obj)

    def test_cannot_promote_private_repositories(self):
        obj = self.doc()
        obj["public_issue_counts"][0]["repo"] = "GBOGEB/cryoplant-project"
        self.assert_rejects(obj)


if __name__ == "__main__":
    unittest.main()
