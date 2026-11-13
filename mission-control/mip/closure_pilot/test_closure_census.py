"""Offline negative and positive contracts for the read-only MIP closure pilot.

Execute: python -m unittest discover -s mission-control/mip/closure_pilot -p 'test_*.py'
No GitHub calls, git writes, runners or third-party dependencies.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("mip_closure_census", HERE / "closure_census.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))

    def test_valid_manifest_has_no_claimed_admission(self):
        report = module.census(copy.deepcopy(self.manifest))
        self.assertEqual(report["closure"]["admission"], "NOT_ADMISSION")
        self.assertEqual(report["closure"]["accepted_live"], 0)
        self.assertIsNone(report["closure"]["frozen_weighted"])
        self.assertIsNone(report["proof"]["nevergreen"])
        self.assertEqual(report["evidence"]["live_root_candidates"], 8)
        self.assertEqual(report["evidence"]["pr_review_unresolved"], 38)

    def test_kahn_provider_precedes_consumer(self):
        layers = module.kahn_layers(["M136", "A2746", "A2745"], [
            {"from": "M136", "to": "A2746"},
            {"from": "A2745", "to": "A2746", "enabled": False},
        ])
        self.assertEqual(layers, [["A2745", "M136"], ["A2746"]])

    def test_cycle_rejected(self):
        with self.assertRaisesRegex(module.CensusError, "cycle"):
            module.kahn_layers(["A", "B"], [
                {"from": "A", "to": "B"}, {"from": "B", "to": "A"}
            ])

    def test_conditional_edge_is_not_silent_authority(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["edges"][1]["enabled"] = True
        report = module.census(manifest)
        self.assertIn("A2745", report["dag"]["kahn_layers"][0])
        self.assertEqual(report["dag"]["kahn_layers"][-1], ["A2746"])

    def test_duplicate_root_rejected(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["roots"].append(copy.deepcopy(manifest["roots"][0]))
        with self.assertRaisesRegex(module.CensusError, "duplicate live root"):
            module.census(manifest)

    def test_frozen_denominator_cannot_be_reset(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["frozen"]["root_count"] = 18
        with self.assertRaisesRegex(module.CensusError, "frozen cohort"):
            module.census(manifest)

    def test_unsupported_closure_is_rejected(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["roots"][0]["accepted"] = True
        with self.assertRaisesRegex(module.CensusError, "unverified root closure"):
            module.census(manifest)

    def test_colliding_commit_worker_paths_are_rejected(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["lanes"][1]["paths"] = list(manifest["lanes"][0]["paths"])
        with self.assertRaisesRegex(module.CensusError, "collision"):
            module.census(manifest)

    def test_missing_test_inventory_is_unknown_not_everred(self):
        self.assertIsNone(module.classify_tests(None)["nevergreen"])

    def test_nevergreen_requires_complete_comparable_history(self):
        with self.assertRaisesRegex(module.CensusError, "history is incomplete"):
            module.classify_tests([{"test_id": "x", "contract_version": "1",
                                   "runner": "ubuntu-24.04 / 3.14",
                                   "outcomes": ["FAIL", "FAIL"], "history_complete": False}])

    def test_nevergreen_excludes_skipped_and_retries(self):
        items = [
            {"test_id": "always_red", "contract_version": "v1", "runner": "3.14",
             "history_complete": True, "outcomes": ["FAIL", "ERROR"]},
            {"test_id": "once_green", "contract_version": "v1", "runner": "3.14",
             "history_complete": True, "outcomes": ["FAIL", "PASS"]},
            {"test_id": "always_skipped", "contract_version": "v1", "runner": "3.14",
             "history_complete": True, "outcomes": ["SKIP", "SKIP"]},
        ]
        result = module.classify_tests(items)
        self.assertEqual(result["nevergreen"], 1)
        self.assertEqual(result["evergreen"], 1)
        self.assertEqual(result["denominator"], 3)

    def test_unknown_priority_never_becomes_zero(self):
        self.assertEqual(module.score_range([None] * 4, [0.35, 0.25, 0.2, 0.2]),
                         [0.0, 100.0])
        self.assertEqual(module.score_range([1, None, None, None],
                                            [0.35, 0.25, 0.2, 0.2]), [35.0, 100.0])


if __name__ == "__main__":
    unittest.main()
