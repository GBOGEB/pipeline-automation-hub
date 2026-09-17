import json
import unittest
from pathlib import Path

import side_effect_receipts as sr

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "LIVE_GITHUB_SIDE_EFFECT_RECEIPT_v1.json"


class LiveSideEffectReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def build_intent(self):
        f = self.fixture
        return {
            "authority_domain": f["repository"],
            "action": f["action"],
            "target": f["target"],
            "mechanism": f["mechanism"],
            "source_state_digest": sr.digest({
                "repository": f["repository"],
                "pull_request": f["pull_request"],
                "head_sha": f["source_head"],
            }),
            "payload_digest": sr.digest({"comment_body": f["comment_body"]}),
            "schema_version": f["schema_version"],
            "expected_semantic_delta": f["expected_semantic_delta"],
        }

    def test_live_github_receipt_replays_without_duplicate_emission(self):
        f = self.fixture
        self.assertFalse(f["authority_transfer"])
        intent = self.build_intent()
        registry = sr.empty_registry()
        first = sr.plan(registry, intent)
        self.assertEqual(first["decision"], "NEW_TRANSACTION")
        self.assertTrue(first["emit_side_effect"])

        registry = sr.register_planned(registry, intent)
        tx_id = first["transaction_id"]
        registry = sr.bind_receipt(
            registry,
            tx_id,
            provider=f["provider"],
            external_ref=f["external_ref"],
            observed_result_digest=sr.digest({
                "provider": f["provider"],
                "comment_id": f["comment_id"],
                "target": f["target"],
            }),
            metadata={
                "repository": f["repository"],
                "pull_request": f["pull_request"],
                "source_head": f["source_head"],
                "comment_id": f["comment_id"],
            },
        )

        replay = sr.plan(registry, intent)
        self.assertEqual(replay["decision"], "REPLAY_EXISTING")
        self.assertFalse(replay["emit_side_effect"])
        self.assertEqual(replay["status"], "COMPLETED")
        self.assertEqual(replay["receipt"]["external_ref"], f["external_ref"])
        self.assertEqual(replay["receipt"]["metadata"]["comment_id"], f["comment_id"])
        self.assertEqual(sr.verify_registry(registry)["status"], "PASS")

    def test_changed_live_payload_branches_instead_of_reusing_receipt(self):
        intent = self.build_intent()
        registry = sr.register_planned(sr.empty_registry(), intent)
        first_tx = sr.transaction_id(intent)
        changed = dict(intent)
        changed["payload_digest"] = sr.digest({"comment_body": self.fixture["comment_body"] + "\nchanged"})
        successor = sr.plan(registry, changed)
        self.assertEqual(successor["decision"], "NEW_TRANSACTION")
        self.assertTrue(successor["emit_side_effect"])
        self.assertEqual(successor["parent_transaction_id"], first_tx)
        self.assertNotEqual(successor["transaction_id"], first_tx)


if __name__ == "__main__":
    unittest.main()
