"""Negative/positive controls for Mission Control RUN-i scouts."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import scout_run_control as m  # noqa: E402

START = "a" * 40
END = "b" * 40


def packet(name, category):
    return {
        "id": name, "category": category, "subtype": "FIRST_RED",
        "priority": "P1", "phase": "ANALYZE", "mode": "READ_ONLY_ANALYZE",
        "repo": "GBOGEB/ABACUS", "source_sha": END, "owner_issue": 2047,
        "mutation_paths": [], "blockers": [],
        "success_predicate": "source-bound first-red fingerprint",
        "occurrence_count": None, "fingerprint_count": None,
        "proof": None, "independent_approval": None,
        "accepted_root_ids": [], "state": "READY",
    }


def sample():
    return {
        "schema": m.INPUT, "authority_transfer": False,
        "dispatch_authorized": False, "merge_authorized": False,
        "repository": "GBOGEB/ABACUS", "pr": 2047,
        "run_i": "N+22", "expected_head_sha": END,
        "scout_environment": "COLD_CLONE",
        "observations": [
            {
                "head_sha": START,
                "observed_at_utc": "2026-10-16T12:30:00Z",
                "collection": "PR_HEAD_RUNS_FIRST_PAGE_METADATA",
                "workflow_counts": dict(success=15, failure=6, cancelled=0,
                                        queued=0, pending=0, in_progress=0),
                "failed_workflow_names": ["CI Workflow Governance",
                                          "CI/CD Test Suite"],
                "population_sha256": None,
                "archive_bytes_verified": False,
                "run_population_complete": False,
            },
            {
                "head_sha": END,
                "observed_at_utc": "2026-10-16T13:36:00Z",
                "collection": "PR_HEAD_RUNS_FIRST_PAGE_METADATA",
                "workflow_counts": dict(success=18, failure=5, cancelled=0,
                                        queued=0, pending=0, in_progress=0),
                "failed_workflow_names": ["CI Workflow Governance",
                                          "CI/CD Test Suite",
                                          "ABACUS v032 - CI/CD Pipeline",
                                          "CI - ABACUS Matrix",
                                          "EVERRED V3 Governed Control Plane"],
                "population_sha256": None,
                "archive_bytes_verified": False,
                "run_population_complete": False,
            },
        ],
        "stop_policy": {
            "max_failed_workflows": 0,
            "critical_failed_names": ["CI Workflow Governance", "CI/CD Test Suite"],
        },
        "candidate_reuse_targets": ["GBOGEB/ABACUS#2004"],
        "subtype_plan": {
            "schema": "missioncontrol.cbd-subtype-plan.v1",
            "authority_transfer": False, "max_parallel": 2,
            "packets": [
                packet("SCOUT-YAML-SECURITY", "SECURITY"),
                packet("SCOUT-FORMAT-REUSE", "GOVERNANCE"),
            ],
        },
        "advisory_scanner": {
            "name": "Semgrep YAML", "source_sha": END,
            "enforcement": "ADVISORY", "native_run_id": 38908374433,
            "findings": 756, "files_scanned": 160, "rules_run": 3,
        },
    }


class RunIScoutTests(unittest.TestCase):
    def test_realistic_failure_census_halts_mutation_not_readonly(self):
        report = m.evaluate(sample())
        self.assertEqual(report["status"], "HALT_MUTATION_ALLOW_READONLY_SCOUT")
        self.assertEqual(report["metric_start"]["workflow_denominator"], 21)
        self.assertEqual(report["metric_end"]["workflow_denominator"], 23)
        self.assertIsNone(report["matched_workflow_delta"])
        self.assertTrue(report["read_only_scouts_allowed"])
        self.assertEqual(report["existing_subtype_scheduler"]["max_parallel"], 2)
        self.assertEqual(report["existing_subtype_scheduler"]["waves_planned"], 1)
        self.assertEqual(report["advisory_scanner"]["findings"], 756)
        self.assertFalse(report["merge_authorized"])
        self.assertIsNone(report["executed_crew_members"])

    def test_comparable_paired_head_population_can_report_delta(self):
        doc = sample()
        doc["observations"][0]["workflow_counts"]["success"] = 17
        digest = "c" * 64
        for wave in doc["observations"]:
            wave["population_sha256"] = digest
        doc["stop_policy"]["critical_failed_names"] = []
        doc["stop_policy"]["max_failed_workflows"] = 10
        report = m.evaluate(doc)
        self.assertTrue(report["matched_population"])
        self.assertEqual(report["matched_workflow_delta"]["success"], 1)
        self.assertEqual(report["matched_workflow_delta"]["failure"], -1)
        self.assertIsNone(report["dov"]["verified_causal_root_closures"])

    def test_head_drift_rejected(self):
        doc = sample()
        doc["expected_head_sha"] = "c" * 40
        with self.assertRaisesRegex(ValueError, "stale"):
            m.evaluate(doc)

    def test_missing_native_population_does_not_promote_to_complete(self):
        doc = sample()
        doc["observations"][1]["run_population_complete"] = True
        with self.assertRaisesRegex(ValueError, "complete"):
            m.evaluate(doc)

    def test_negative_and_boolean_workflow_counts_rejected(self):
        for bad in (-1, True, None):
            doc = sample()
            doc["observations"][1]["workflow_counts"]["failure"] = bad
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, "count"):
                m.evaluate(doc)

    def test_false_accepted_root_is_forbidden(self):
        doc = sample()
        doc["subtype_plan"]["packets"][0]["accepted_root_ids"] = ["R1"]
        with self.assertRaises(ValueError):
            m.evaluate(doc)

    def test_mutating_scout_forbidden_even_with_path_lease(self):
        doc = sample()
        doc["subtype_plan"]["packets"][0]["mode"] = "MUTATING_REPAIR"
        doc["subtype_plan"]["packets"][0]["mutation_paths"] = ["src/x.py"]
        with self.assertRaisesRegex(ValueError, "readonly"):
            m.evaluate(doc)

    def test_overparallel_scout_rejected(self):
        doc = sample()
        doc["subtype_plan"]["max_parallel"] = 3
        with self.assertRaisesRegex(ValueError, "above two"):
            m.evaluate(doc)

    def test_cross_head_scanner_rejected(self):
        doc = sample()
        doc["advisory_scanner"]["source_sha"] = START
        with self.assertRaisesRegex(ValueError, "scanner provenance"):
            m.evaluate(doc)

    def test_no_authority_transfer_even_on_green_candidate(self):
        doc = sample()
        doc["dispatch_authorized"] = True
        with self.assertRaisesRegex(ValueError, "authority"):
            m.evaluate(doc)

    def test_dod_dov_and_hash_manifest(self):
        report = m.evaluate(sample())
        self.assertEqual(report["dod"]["state"], "SCOUT_DEFINITION_ONLY")
        self.assertEqual(report["dov"]["state"], "HOLD")
        with tempfile.TemporaryDirectory() as temp:
            digest = m.emit(report, Path(temp))
            raw = (Path(temp) / "scout_run.json").read_bytes()
            self.assertEqual(digest, hashlib.sha256(raw).hexdigest())
            self.assertEqual((Path(temp) / "scout_run.sha256").read_text().strip(),
                             digest)
            self.assertIn("21 | 23", (Path(temp) / "scout_run.md").read_text())

    def test_terminal_status_claims_remain_metadata_only(self):
        doc = sample()
        doc["observations"][1]["archive_bytes_verified"] = True
        with self.assertRaisesRegex(ValueError, "metadata cannot"):
            m.evaluate(doc)

    def test_duplicate_target_and_invalid_clock_rejected(self):
        doc = sample()
        doc["candidate_reuse_targets"].append("GBOGEB/ABACUS#2004")
        with self.assertRaisesRegex(ValueError, "target candidates"):
            m.evaluate(doc)
        doc = sample()
        doc["observations"][1]["observed_at_utc"] = "2026-10-16T12:20:00Z"
        with self.assertRaisesRegex(ValueError, "clock"):
            m.evaluate(doc)


if __name__ == "__main__":
    unittest.main()
