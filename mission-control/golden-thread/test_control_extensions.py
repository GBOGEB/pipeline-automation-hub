import copy
import json
import unittest
from pathlib import Path

import checkpoint_replay as cp
import golden_thread as gt
import rendition_family as rf

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "COLD_TAIL_BOOTSTRAP_LEDGER_v1.json"


class GoldenThreadControlExtensionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_checkpoint_replay_equals_genesis_replay(self):
        checkpoint = cp.create_checkpoint(
            self.ledger,
            "GT-0012",
            "CP-COLD-TAIL-0012",
            created_at="2026-09-17T02:00:00Z",
        )
        verification = cp.verify_checkpoint(self.ledger, checkpoint)
        self.assertEqual(verification["status"], "PASS")

        equivalence = cp.verify_replay_equivalence(self.ledger, checkpoint)
        self.assertEqual(equivalence["status"], "PASS")
        self.assertEqual(equivalence["tail_event_count"], 2)
        self.assertEqual(
            equivalence["genesis_projection_digest"],
            equivalence["checkpoint_projection_digest"],
        )

    def test_checkpoint_tamper_is_detected(self):
        checkpoint = cp.create_checkpoint(
            self.ledger,
            "GT-0012",
            "CP-COLD-TAIL-TAMPER",
            created_at="2026-09-17T02:00:00Z",
        )
        bad = copy.deepcopy(checkpoint)
        bad["projection_snapshot"]["authority_transfer"] = True
        with self.assertRaises(gt.GoldenThreadError):
            cp.verify_checkpoint(self.ledger, bad)

    def test_checkpoint_cannot_replay_to_earlier_boundary(self):
        checkpoint = cp.create_checkpoint(
            self.ledger,
            "GT-0012",
            "CP-COLD-TAIL-BOUNDARY",
            created_at="2026-09-17T02:00:00Z",
        )
        with self.assertRaises(gt.GoldenThreadError):
            cp.replay_from_checkpoint(self.ledger, checkpoint, "GT-0008")

    def test_rendition_family_zero_delta(self):
        truth = gt.rebuild(self.ledger)
        family = rf.render_family(truth)
        verification = rf.verify_family(truth, family)
        self.assertEqual(verification["status"], "PASS")
        self.assertEqual(verification["rendition_count"], 4)
        self.assertTrue(
            all(row["status"] == "PASS" for row in verification["results"].values())
        )

    def test_rendition_family_detects_semantic_delta(self):
        truth = gt.rebuild(self.ledger)
        family = rf.render_family(truth)
        family["renditions"]["json"]["content"] = '{"authority_transfer":true}\n'
        verification = rf.verify_family(truth, family)
        self.assertEqual(verification["status"], "FAIL")
        self.assertEqual(verification["results"]["json"]["status"], "FAIL")

    def test_yaml_rendition_is_real_yaml_json_subset_and_exact_truth(self):
        truth = gt.rebuild(self.ledger)
        family = rf.render_family(truth)
        extracted = rf.extract_rendition("yaml", family["renditions"]["yaml"]["content"])
        self.assertEqual(extracted, truth)
        self.assertEqual(rf.canonical_truth_digest(extracted), truth["projection_digest"] if False else gt.digest(truth))


if __name__ == "__main__":
    unittest.main()
