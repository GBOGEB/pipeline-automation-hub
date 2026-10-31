"""MissionControl child handoff is reversible and never self-promotes QPS."""
import json
import unittest
from pathlib import Path

INPUT = Path(__file__).resolve().parent / "GLOBAL_DOV_W4_HANDOFF.json"


class GlobalDOVHandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(INPUT.read_text(encoding="utf-8"))

    def test_children_unique_and_source_owned(self):
        children = self.data["children"]
        self.assertEqual(3, len(children))
        self.assertEqual(3, len({c["repo"] for c in children}))
        self.assertEqual(
            {"QPS_ENGINEERING_OWNER", "KEB_SEMANTIC_OWNER",
             "DOW_DIAGNOSTIC_OWNER"},
            {c["role"] for c in children},
        )

    def test_all_children_pending_exact_main_proof(self):
        # 919b9c9b9 and 5d9c906b9 replaced UNVERIFIED_DEDICATED with the gate each
        # child PR head actually reached. A PR-head gate is still not main proof:
        # every child stays a PR candidate with a non-promoting decision.
        self.assertEqual(
            {"GBOGEB/cryoplant-project": "EXACT_HEAD_GUARDS_VERIFIED",
             "GBOGEB/CODEX": "TERMINAL_PENDING_LATEST_HEAD",
             "GBOGEB/ABACUS": "TERMINAL_PENDING"},
            {x["repo"]: x["native_test_gate"] for x in self.data["children"]},
        )
        for x in self.data["children"]:
            self.assertEqual("PR_CANDIDATE", x["source_state"])
            self.assertIn(x["decision"], ("DEFER", "NO_AUTHORITY"))

    def test_purge_denied_by_default(self):
        self.assertEqual("DO_NOT_EXECUTE_YET",
                         self.data["legacy_actions"][1]["state"])
        self.assertEqual(0, self.data["metrics"]["legacy_fields_purged"])
        self.assertGreaterEqual(len(
            self.data["purge_admission_requires"]
        ), 5)

    def test_no_engineering_promotion(self):
        self.assertEqual("DEFER", self.data["hard_gates"]["qps"])
        self.assertEqual("UNKNOWN",
                         self.data["hard_gates"]["native_four_hop"])
        self.assertFalse(self.data["hard_gates"]["auto_approval"])
        self.assertEqual(0, self.data["metrics"]["formal_engineering_credit"])


if __name__ == "__main__":
    unittest.main()
