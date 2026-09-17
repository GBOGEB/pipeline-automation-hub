#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import pathlib
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("federation_frontier", HERE / "federation_frontier.py")
ff = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(ff)


class FederationFrontierTests(unittest.TestCase):
    def test_live_occurrence_import_is_idempotent(self):
        fixture = json.loads((HERE / "fixtures" / "LIVE_GITHUB_OCCURRENCE_FAMILY_20260917.json").read_text(encoding="utf-8"))
        first = ff.import_occurrences(fixture["records"])
        self.assertEqual(first["imported_count"], 2)
        self.assertEqual(first["duplicate_count"], 0)
        second = ff.import_occurrences(fixture["records"], first["occurrences"])
        self.assertEqual(second["imported_count"], 0)
        self.assertEqual(second["duplicate_count"], 2)
        self.assertEqual(second["occurrence_count"], 2)
        self.assertEqual(second["projection_digest"], first["projection_digest"])
        self.assertFalse(second["authority_transfer"])

    def test_occurrence_payload_change_gets_distinct_identity(self):
        base = {
            "repository": "GBOGEB/x",
            "object_type": "issue",
            "object_number": 1,
            "anchor_sha": "abcdef1",
            "source_ref": "GBOGEB/x#1",
            "payload": {"state": "open"},
        }
        changed = dict(base)
        changed["payload"] = {"state": "closed"}
        result = ff.import_occurrences([base, changed])
        self.assertEqual(result["occurrence_count"], 2)

    def test_descendant_invalidation_requires_complete_recompute(self):
        receipt = ff.build_invalidation_receipt(
            nodes=["A", "B", "C", "D"],
            edges=[("A", "B"), ("B", "C"), ("D", "D")],
            roots=["A"],
            scope="DESCENDANT_CONE",
            renditions={"A": ["A.html"], "B": ["B.json"], "C": ["C.docx"]},
            trigger={"event_id": "E1"},
        )
        self.assertEqual(receipt["affected_nodes"], ["A", "B", "C"])
        partial = ff.close_invalidation(receipt, recomputed_nodes=["A", "B"], regenerated_renditions=receipt["affected_renditions"])
        self.assertEqual(partial["status"], "WITHHELD")
        self.assertEqual(partial["stale_survivors"], ["C"])
        closed = ff.close_invalidation(receipt, recomputed_nodes=["A", "B", "C"], regenerated_renditions=receipt["affected_renditions"])
        self.assertEqual(closed["status"], "PASS")
        self.assertEqual(closed["stale_survivor_count"], 0)

    def test_cluster_invalidation_is_bounded(self):
        receipt = ff.build_invalidation_receipt(
            nodes=["A", "B", "C"],
            edges=[],
            roots=["A"],
            scope="DMAIC_CLUSTER",
            clusters={"A": "MEASURE", "B": "MEASURE", "C": "CONTROL"},
        )
        self.assertEqual(receipt["affected_nodes"], ["A", "B"])

    def test_gate_inhibit_latches_until_authorized_reset(self):
        state = ff.new_gate(["child-a", "child-b"])
        state = ff.apply_gate_event(state, {"type": "PERMISSIVE", "child": "child-a"})
        state = ff.apply_gate_event(state, {"type": "INHIBIT", "child": "child-b"})
        state = ff.apply_gate_event(state, {"type": "PERMISSIVE", "child": "child-b"})
        self.assertTrue(state["latched_inhibit"])
        self.assertFalse(state["gate_open"])
        with self.assertRaises(ff.FederationFrontierError):
            ff.apply_gate_event(state, {"type": "RESET", "authorized": False, "reason": "no"})
        state = ff.apply_gate_event(state, {"type": "RESET", "authorized": True, "reason": "child evidence cleared"})
        self.assertFalse(state["latched_inhibit"])
        self.assertFalse(state["gate_open"])
        self.assertEqual(state["child_permissives"], {"child-a": False, "child-b": False})
        state = ff.apply_gate_event(state, {"type": "PERMISSIVE", "child": "child-a"})
        state = ff.apply_gate_event(state, {"type": "PERMISSIVE", "child": "child-b"})
        self.assertTrue(state["gate_open"])

    def test_reflexive_dag_resequence_preserves_semantic_digest(self):
        nodes = ["A", "B", "C"]
        edges = [("A", "A"), ("A", "C"), ("B", "C")]
        first = ff.validate_reflexive_resequence(nodes, edges, ["A"], ["A", "B", "C"])
        second = ff.validate_reflexive_resequence(nodes, edges, ["A"], ["B", "A", "C"])
        self.assertEqual(first["semantic_graph_digest"], second["semantic_graph_digest"])
        with self.assertRaises(ff.FederationFrontierError):
            ff.validate_reflexive_resequence(nodes, edges, [], ["A", "B", "C"])
        with self.assertRaises(ff.FederationFrontierError):
            ff.validate_reflexive_resequence(nodes, edges, ["A"], ["C", "A", "B"])

    def test_checkpoint_policy_never_truncates_history(self):
        policy = {
            "max_events_since_checkpoint": 100,
            "max_replay_cost_ms": 1000,
            "max_hours_since_checkpoint": 24,
            "hot_tier_max_bytes": 1000000,
        }
        quiet = ff.checkpoint_decision({"events_since_checkpoint": 10, "replay_cost_ms": 20, "hours_since_checkpoint": 2, "ledger_bytes": 1000}, policy)
        self.assertFalse(quiet["create_checkpoint"])
        hot = ff.checkpoint_decision({"events_since_checkpoint": 101, "replay_cost_ms": 20, "hours_since_checkpoint": 2, "ledger_bytes": 1000}, policy)
        self.assertTrue(hot["create_checkpoint"])
        self.assertIn("EVENT_COUNT", hot["triggers"])
        self.assertFalse(hot["history_truncation_allowed"])
        self.assertFalse(hot["checkpoint_is_authority"])


if __name__ == "__main__":
    unittest.main()
