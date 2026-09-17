import copy
import unittest

import side_effect_receipts as sr


class SideEffectReceiptTests(unittest.TestCase):
    def setUp(self):
        self.registry = sr.empty_registry()
        self.intent = {
            "authority_domain": "GBOGEB/pipeline-automation-hub",
            "action": "GITHUB_ISSUE_COMMENT_CREATE",
            "target": "GBOGEB/pipeline-automation-hub#153",
            "mechanism": "REG",
            "source_state_digest": sr.digest({"projection": "k42"}),
            "payload_digest": sr.digest({"comment": "golden thread receipt"}),
            "schema_version": "github.issue_comment.v1",
            "expected_semantic_delta": "NONE_CONTROL_RECEIPT_ONLY",
        }

    def test_first_intent_is_new_transaction(self):
        plan = sr.plan(self.registry, self.intent)
        self.assertEqual(plan["decision"], "NEW_TRANSACTION")
        self.assertTrue(plan["emit_side_effect"])
        self.assertIsNone(plan["parent_transaction_id"])
        self.assertFalse(plan["authority_transfer"])

    def test_exact_replay_does_not_reemit(self):
        registered = sr.register_planned(self.registry, self.intent)
        plan = sr.plan(registered, self.intent)
        self.assertEqual(plan["decision"], "REPLAY_EXISTING")
        self.assertFalse(plan["emit_side_effect"])
        self.assertEqual(plan["status"], "PLANNED")

    def test_completed_replay_returns_prior_exact_receipt(self):
        registered = sr.register_planned(self.registry, self.intent)
        tx_id = sr.transaction_id(self.intent)
        completed = sr.bind_receipt(
            registered,
            tx_id,
            provider="github",
            external_ref="issue-comment:5706943820",
            observed_result_digest=sr.digest({"comment_id": 5706943820}),
            metadata={"repository": "GBOGEB/pipeline-automation-hub", "issue": 153},
        )
        replay = sr.plan(completed, self.intent)
        self.assertEqual(replay["decision"], "REPLAY_EXISTING")
        self.assertFalse(replay["emit_side_effect"])
        self.assertEqual(replay["status"], "COMPLETED")
        self.assertEqual(replay["receipt"]["external_ref"], "issue-comment:5706943820")
        self.assertEqual(sr.verify_registry(completed)["status"], "PASS")

    def test_changed_payload_forces_successor_transaction(self):
        first = sr.register_planned(self.registry, self.intent)
        first_tx = sr.transaction_id(self.intent)
        changed = copy.deepcopy(self.intent)
        changed["payload_digest"] = sr.digest({"comment": "changed governed payload"})
        plan = sr.plan(first, changed)
        self.assertEqual(plan["decision"], "NEW_TRANSACTION")
        self.assertTrue(plan["emit_side_effect"])
        self.assertTrue(plan["changed_from_parent"])
        self.assertEqual(plan["parent_transaction_id"], first_tx)
        self.assertNotEqual(plan["transaction_id"], first_tx)
        self.assertEqual(plan["obligation_id"], sr.obligation_id(self.intent))

    def test_changed_source_state_forces_successor_transaction(self):
        first = sr.register_planned(self.registry, self.intent)
        changed = copy.deepcopy(self.intent)
        changed["source_state_digest"] = sr.digest({"projection": "k43"})
        plan = sr.plan(first, changed)
        self.assertEqual(plan["decision"], "NEW_TRANSACTION")
        self.assertTrue(plan["changed_from_parent"])
        self.assertNotEqual(plan["transaction_id"], sr.transaction_id(self.intent))

    def test_receipt_is_immutable(self):
        registered = sr.register_planned(self.registry, self.intent)
        tx_id = sr.transaction_id(self.intent)
        completed = sr.bind_receipt(
            registered,
            tx_id,
            provider="github",
            external_ref="issue-comment:1",
            observed_result_digest=sr.digest({"comment_id": 1}),
        )
        with self.assertRaises(sr.SideEffectError):
            sr.bind_receipt(
                completed,
                tx_id,
                provider="github",
                external_ref="issue-comment:2",
                observed_result_digest=sr.digest({"comment_id": 2}),
            )

    def test_receipt_tamper_is_detected(self):
        registered = sr.register_planned(self.registry, self.intent)
        tx_id = sr.transaction_id(self.intent)
        completed = sr.bind_receipt(
            registered,
            tx_id,
            provider="github",
            external_ref="issue-comment:1",
            observed_result_digest=sr.digest({"comment_id": 1}),
        )
        bad = copy.deepcopy(completed)
        bad["transactions"][tx_id]["receipt"]["external_ref"] = "issue-comment:tampered"
        with self.assertRaises(sr.SideEffectError):
            sr.verify_registry(bad)

    def test_successor_lineage_verifies(self):
        first = sr.register_planned(self.registry, self.intent)
        changed = copy.deepcopy(self.intent)
        changed["payload_digest"] = sr.digest({"comment": "version 2"})
        second = sr.register_planned(first, changed)
        receipt = sr.verify_registry(second)
        self.assertEqual(receipt["transaction_count"], 2)
        self.assertEqual(receipt["lineage_edge_count"], 1)
        self.assertFalse(receipt["authority_transfer"])


if __name__ == "__main__":
    unittest.main()
