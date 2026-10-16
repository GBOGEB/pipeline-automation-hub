from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "subtype_orchestrator.py"
SPEC = importlib.util.spec_from_file_location("subtype_orchestrator", MODULE_PATH)
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MOD)

SHA = "a" * 40

def packet(pid, subtype, state="READY", category="SECURITY"):
    return {
        "id": pid, "category": category, "subtype": subtype, "priority": "P1",
        "phase": "ANALYZE", "mode": "READ_ONLY_ANALYZE",
        "repo": "GBOGEB/ABACUS", "source_sha": SHA, "owner_issue": 1738,
        "mutation_paths": [], "blockers": ["owner"] if state == "BLOCKED" else [],
        "success_predicate": "source-bound proof", "occurrence_count": 1,
        "fingerprint_count": 1, "proof": None, "independent_approval": False,
        "accepted_root_ids": [], "state": state,
    }

class SubtypePlannerTests(unittest.TestCase):
    def base(self, packets):
        return {"schema": MOD.SCHEMA, "cohort": "test",
                "observed_at": "2026-10-16T06:30:00Z",
                "authority_transfer": False, "max_parallel": 2, "packets": packets}

    def test_disjoint_packets_share_wave(self):
        receipt = MOD.plan(self.base([packet("A", "B3"), packet("B", "B4")]))
        self.assertEqual(receipt["schedule"]["waves_planned"], 1)
        self.assertFalse(receipt["dispatch_authorized"])

    def test_blocked_not_scheduled(self):
        receipt = MOD.plan(self.base([
            packet("A", "B3"),
            packet("B", "A10", state="BLOCKED", category="GOVERNANCE")]))
        self.assertEqual(receipt["kpi"]["blocked"], 1)
        self.assertEqual(receipt["schedule"]["packets_planned"], 1)

    def test_root_closure_requires_independent_proof(self):
        p = packet("A", "B3")
        p["accepted_root_ids"] = ["ROOT-1"]
        with self.assertRaises(ValueError):
            MOD.plan(self.base([p]))

    def test_sample(self):
        sample = Path(__file__).resolve().parents[1] / "samples" / "cbd_abacus_20261016.json"
        receipt = MOD.plan(json.loads(sample.read_text()))
        self.assertEqual(receipt["kpi"]["packets_total"], 14)
        self.assertEqual(receipt["kpi"]["ready_now"], 7)
        self.assertEqual(receipt["kpi"]["blocked"], 3)\n        self.assertEqual(receipt["kpi"]["proof_pending"], 4)\n        self.assertEqual(receipt["schedule"]["waves_planned"], 3)
        self.assertEqual(receipt["kpi"]["independently_accepted_root_closures"], 0)

if __name__ == "__main__":
    unittest.main()
