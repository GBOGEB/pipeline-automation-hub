import json
import unittest
from pathlib import Path

import golden_thread as gt
import temporal_checkpoint as tc

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "QPS_W57_P02_PVPS_DEFER_LEDGER_v1.json"


class QPSW57ObservedDeferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_observed_ledger_hash_chain_verifies(self):
        receipt = gt.verify(self.ledger)
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["event_count"], 10)
        self.assertEqual(
            receipt["head_event_digest"],
            "sha256:0a1598dee6498c42b550dc16deaf0a5cbdada77610d9a81ab21b463d3c72d571",
        )
        self.assertFalse(receipt["authority_transfer"])

    def test_real_child_defer_is_complete_and_non_authoritative(self):
        summary = tc.scan_child_transactions(self.ledger)
        self.assertEqual(summary["injection_count"], 1)
        self.assertEqual(summary["disposition_count"], 1)
        self.assertEqual(summary["deferred_count"], 1)
        self.assertEqual(summary["accepted_count"], 0)
        self.assertEqual(summary["rejected_count"], 0)
        self.assertEqual(summary["unresolved_count"], 0)
        self.assertEqual(summary["accepted_authoritative_delta_count"], 0)
        self.assertEqual(
            summary["deferred_injection_keys"], ["QPS-W57-P02-PVPS-83KW"]
        )
        disposition = summary["dispositions"]["QPS-W57-P02-PVPS-83KW"]
        self.assertEqual(disposition["owner"], "GBOGEB/cryoplant-project")
        self.assertIn("six W111 blocking inputs", disposition["reentry_trigger"])
        self.assertFalse(disposition["authoritative_delta_applied"])

    def test_projection_retains_gate_and_deferred_work_order(self):
        projection = gt.rebuild(self.ledger)
        self.assertEqual(projection["metrics"]["occurrence_count"], 1)
        self.assertEqual(projection["metrics"]["root_count"], 1)
        self.assertEqual(projection["metrics"]["work_order_count"], 1)
        self.assertEqual(projection["metrics"]["orphan_occurrence_count"], 0)
        self.assertEqual(projection["metrics"]["lineage_retention_coverage"], 1.0)
        root = projection["roots"]["ROOT-QPS-W57-P02-PVPS-83KW"]
        self.assertTrue(root["non_compensating"])
        self.assertIn("same-point PVPS package boundary", root["blocking_predicate"])
        self.assertIn("source-bound return", root["reentry_trigger"])
        work_order = projection["work_orders"]["WO-QPS-W57-P02-PVPS-FEDERATION"]
        self.assertEqual(work_order["state"], "DEFERRED")

    def test_temporal_checkpoint_advances_e_not_k(self):
        checkpoint = tc.checkpoint_payload(
            self.ledger,
            base_semantic_generation_k=0,
            ssot_digest=None,
            git_repo="GBOGEB/pipeline-automation-hub",
            git_commit_sha="a" * 40,
            milestone="GT-M1-QPS-W57-P02-DEFER",
        )
        self.assertEqual(checkpoint["base_semantic_generation_k"], 0)
        self.assertEqual(checkpoint["semantic_generation_k"], 0)
        self.assertEqual(checkpoint["event_sequence_e"], 10)
        self.assertFalse(checkpoint["engineering_ssot_changed"])
        self.assertIsNone(checkpoint["ssot_digest"])
        self.assertEqual(
            checkpoint["thread_digest"],
            "sha256:0a1598dee6498c42b550dc16deaf0a5cbdada77610d9a81ab21b463d3c72d571",
        )
        replay = tc.verify_checkpoint(self.ledger, checkpoint)
        self.assertEqual(replay["status"], "PASS")
        self.assertEqual(replay["semantic_generation_k"], 0)
        self.assertEqual(replay["event_sequence_e"], 10)

    def test_checkpoint_is_replay_idempotent(self):
        kwargs = dict(
            base_semantic_generation_k=0,
            ssot_digest=None,
            git_repo="GBOGEB/pipeline-automation-hub",
            git_commit_sha="b" * 40,
            milestone="GT-M1-QPS-W57-P02-DEFER",
        )
        first = tc.checkpoint_payload(self.ledger, **kwargs)
        second = tc.checkpoint_payload(self.ledger, **kwargs)
        self.assertEqual(first, second)
        self.assertEqual(first["checkpoint_digest"], second["checkpoint_digest"])


if __name__ == "__main__":
    unittest.main()
