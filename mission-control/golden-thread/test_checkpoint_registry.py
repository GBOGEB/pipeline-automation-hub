import copy
import json
import unittest
from pathlib import Path

import checkpoint_registry as cr
import checkpoint_replay as cpr

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "COLD_TAIL_BOOTSTRAP_LEDGER_v1.json"


class CheckpointRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls.policy = cr.cadence_policy(every_n_events=4)

    def setUp(self):
        self.registry = cr.empty_registry(self.ledger, self.policy)

    def _register(self, boundary, checkpoint_id, trigger):
        cp = cpr.create_checkpoint(
            self.ledger,
            boundary,
            checkpoint_id,
            created_at=f"2026-09-17T02:{int(boundary.split('-')[1]):02d}:00Z",
        )
        self.registry, receipt = cr.register_checkpoint(
            self.registry,
            self.ledger,
            self.policy,
            cp,
            trigger=trigger,
            checkpoint_ref=f"fixtures/{checkpoint_id}.json",
        )
        return cp, receipt

    def test_genesis_is_due(self):
        decision = cr.cadence_decision(self.registry, self.ledger, self.policy, boundary="GT-0008")
        self.assertEqual(decision["status"], "DUE")
        self.assertEqual(decision["reason"], "GENESIS_NO_CHECKPOINT")

    def test_event_interval_and_selection(self):
        cp8, _ = self._register("GT-0008", "CP-0008", "GENESIS_NO_CHECKPOINT")
        not_due = cr.cadence_decision(self.registry, self.ledger, self.policy, boundary="GT-0011")
        self.assertEqual(not_due["status"], "NOT_DUE")
        due = cr.cadence_decision(self.registry, self.ledger, self.policy, boundary="GT-0012")
        self.assertEqual(due["status"], "DUE")
        self.assertEqual(due["reason"], "EVENT_INTERVAL")
        cp12, _ = self._register("GT-0012", "CP-0012", "EVENT_INTERVAL")

        selected_10 = cr.select_checkpoint(self.registry, self.ledger, self.policy, boundary="GT-0010")
        self.assertEqual(selected_10["checkpoint"]["checkpoint_id"], "CP-0008")
        self.assertEqual(selected_10["tail_event_count"], 2)
        selected_current = cr.select_checkpoint(self.registry, self.ledger, self.policy)
        self.assertEqual(selected_current["checkpoint"]["checkpoint_id"], "CP-0012")
        self.assertEqual(selected_current["tail_event_count"], 2)

        replay_10 = cpr.verify_replay_equivalence(self.ledger, cp8, "GT-0010")
        self.assertEqual(replay_10["status"], "PASS")
        replay_current = cpr.verify_replay_equivalence(self.ledger, cp12)
        self.assertEqual(replay_current["status"], "PASS")

    def test_milestone_trigger_forces_checkpoint_before_interval(self):
        self._register("GT-0008", "CP-0008", "GENESIS_NO_CHECKPOINT")
        decision = cr.cadence_decision(
            self.registry,
            self.ledger,
            self.policy,
            boundary="GT-0010",
            trigger="RELEASE_BOUNDARY",
        )
        self.assertEqual(decision["status"], "DUE")
        self.assertEqual(decision["reason"], "MILESTONE:RELEASE_BOUNDARY")

    def test_same_boundary_replay_is_not_duplicate(self):
        cp8, receipt = self._register("GT-0008", "CP-0008", "GENESIS_NO_CHECKPOINT")
        replay_registry, replay = cr.register_checkpoint(
            self.registry,
            self.ledger,
            self.policy,
            cp8,
            trigger="GENESIS_NO_CHECKPOINT",
            checkpoint_ref="fixtures/CP-0008.json",
        )
        self.assertEqual(replay["status"], "UNCHANGED_REPLAY")
        self.assertEqual(replay_registry, self.registry)
        self.assertEqual(len(replay_registry["entries"]), 1)

    def test_registry_tamper_fails_closed(self):
        self._register("GT-0008", "CP-0008", "GENESIS_NO_CHECKPOINT")
        bad = copy.deepcopy(self.registry)
        bad["entries"][0]["through_event_seq"] = 7
        with self.assertRaises(cr.CheckpointRegistryError):
            cr.verify_registry(bad, self.ledger, self.policy)

    def test_policy_tamper_fails_closed(self):
        bad = copy.deepcopy(self.policy)
        bad["every_n_events"] = 3
        with self.assertRaises(cr.CheckpointRegistryError):
            cr.verify_policy(bad)

    def test_registry_is_append_only(self):
        self._register("GT-0008", "CP-0008", "GENESIS_NO_CHECKPOINT")
        self._register("GT-0012", "CP-0012", "EVENT_INTERVAL")
        older = cpr.create_checkpoint(
            self.ledger,
            "GT-0010",
            "CP-0010",
            created_at="2026-09-17T02:10:00Z",
        )
        with self.assertRaises(cr.CheckpointRegistryError):
            cr.register_checkpoint(
                self.registry,
                self.ledger,
                self.policy,
                older,
                trigger="RELEASE_BOUNDARY",
            )


if __name__ == "__main__":
    unittest.main()
