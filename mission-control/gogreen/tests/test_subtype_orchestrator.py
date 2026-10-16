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
        self.assertEqual(receipt["kpi"]["packets_total"], 18)
        self.assertEqual(receipt["kpi"]["ready_now"], 7)
        self.assertEqual(receipt["kpi"]["blocked"], 3)
        self.assertEqual(receipt["kpi"]["proof_pending"], 8)
        self.assertEqual(receipt["schedule"]["waves_planned"], 3)
        self.assertEqual(receipt["kpi"]["independently_accepted_root_closures"], 0)


    @staticmethod
    def mutating(pid, paths, repo="GBOGEB/ABACUS"):
        p = packet(pid, pid)
        p.update(mode="MUTATING_REPAIR", phase="REPAIR", repo=repo, mutation_paths=paths)
        return p

    def test_nested_directory_and_file_leases_cannot_share_wave(self):
        a = self.mutating("A", ["ci/governance"])
        b = self.mutating("B", ["ci/governance/workflow_policy.json"])
        receipt = MOD.plan(self.base([a, b]))
        self.assertEqual(receipt["schedule"]["waves_planned"], 2)
        self.assertEqual(receipt["schedule"]["path_conflicts_prevented"], 1)
        self.assertFalse(receipt["dispatch_authorized"])

    def test_identical_mutation_file_leases_conflict(self):
        a = self.mutating("A", ["src/engine.py"])
        b = self.mutating("B", ["src/engine.py"])
        receipt = MOD.plan(self.base([a, b]))
        self.assertEqual(receipt["schedule"]["waves_planned"], 2)

    def test_sibling_files_can_share_wave_with_two_worker_ceiling(self):
        a = self.mutating("A", ["ci/governance/workflow_policy.json"])
        b = self.mutating("B", ["ci/governance/audit_ci_workflows.py"])
        receipt = MOD.plan(self.base([a, b]))
        self.assertEqual(receipt["schedule"]["waves_planned"], 1)

    def test_same_path_in_distinct_repository_is_not_a_collision(self):
        a = self.mutating("A", ["ci/governance"])
        b = self.mutating("B", ["ci/governance/config.json"], "GBOGEB/CODEX")
        receipt = MOD.plan(self.base([a, b]))
        self.assertEqual(receipt["schedule"]["waves_planned"], 1)

    def test_unsafe_or_noncanonical_path_leases_fail_closed(self):
        invalid = ["/absolute/path", "src//file.py", "src/../file.py",
                   "./src/file.py", "src\\file.py", "C:/temp/file.py",
                   ".git/config", "src/"]
        for i, path in enumerate(invalid):
            with self.subTest(path=path):
                with self.assertRaisesRegex(ValueError, "unsafe mutation path lease"):
                    MOD.plan(self.base([self.mutating(f"A{i}", [path])]))

    def test_explicit_mutating_lease_required_and_no_authority(self):
        p = self.mutating("A", [])
        with self.assertRaisesRegex(ValueError, "path lease"):
            MOD.plan(self.base([p]))
        ok = MOD.plan(self.base([self.mutating("B", ["src/core.py"])]))
        self.assertFalse(ok["merge_authorized"])
        self.assertFalse(ok["dispatch_authorized"])

if __name__ == "__main__":
    unittest.main()
