"""Offline proof: real source ledger is never inferred from a synthetic fixture."""
import copy
import json
import unittest
from pathlib import Path
from temporal_burndown import review, path_conflict, lane_collisions, CensusError

HERE = Path(__file__).resolve().parent

class TemporalBurndownTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.observation = json.loads((HERE / "bsln_20261116.json").read_text())
        cls.manifest = json.loads((HERE / "manifest.json").read_text())

    def test_baseline_is_not_claimed_as_current_admission(self):
        r = review(self.observation, self.manifest)
        self.assertEqual(r["burndown"]["frozen_weight"], 65)
        self.assertEqual(r["burndown"]["verified_accepted_weight"], 0)
        self.assertIsNone(r["burndown"]["live_weighted"])
        self.assertEqual(r["gates"]["merge_admission"], "HOLD")

    def test_16_handover_edges_and_six_edge_chain(self):
        r = review(self.observation, self.manifest)
        self.assertEqual(r["historical_dag"]["edge_count"], 16)
        self.assertEqual(r["historical_dag"]["longest_chain_edges"], 6)
        self.assertEqual(r["historical_dag"]["kahn_layers"][0],
                         ["P0-A1", "P0-A2", "P0-J1", "P0-Q1"])

    def test_queued_thresholds_are_strict_and_non_atomic(self):
        q = review(self.observation, self.manifest)["queue_baseline"]
        self.assertEqual(q["Hub"]["minimum_queued_reduction_for_lt60"], 49)
        self.assertEqual(q["CODEX"]["minimum_queued_reduction_for_lt60"], 18)
        self.assertFalse(q["ABACUS"]["queue_breach"])

    def test_four_stale_heads_are_rejected_for_reuse(self):
        r = review(self.observation, self.manifest)
        self.assertEqual(r["pilot"]["stale_owner_heads"], 4)
        self.assertFalse(r["pilot"]["worker_dispatch_authorized"])

    def test_invalid_sha_rejected(self):
        x = copy.deepcopy(self.observation)
        x["owner_heads"]["A2746"] = "stale"
        with self.assertRaisesRegex(CensusError, "owner head"):
            review(x, self.manifest)

    def test_partial_owner_census_rejected(self):
        x = copy.deepcopy(self.observation)
        del x["owner_heads"]["A2746"]
        with self.assertRaisesRegex(CensusError, "owner census"):
            review(x, self.manifest)

    def test_fake_certificate_cannot_generate_credit(self):
        x = copy.deepcopy(self.observation)
        x["certificates"] = ["P0-Q1"]
        with self.assertRaisesRegex(CensusError, "unverified admission"):
            review(x, self.manifest)

    def test_false_original_hash_proof_is_rejected(self):
        x = copy.deepcopy(self.observation)
        x["original_frozen_sha_verified"] = True
        with self.assertRaisesRegex(CensusError, "hash verification"):
            review(x, self.manifest)

    def test_exact_path_conflict(self):
        self.assertTrue(path_conflict("a/x.py", "a/x.py"))

    def test_directory_path_conflict(self):
        self.assertTrue(path_conflict("a/b/", "a/b/test.py"))

    def test_glob_path_conflict(self):
        self.assertTrue(path_conflict("a/*.yaml", "a/input.yaml"))

    def test_two_globs_conservative(self):
        self.assertTrue(path_conflict("a/*.yaml", "a/f*.yaml"))

    def test_disjoint_literal_paths(self):
        self.assertFalse(path_conflict("a/README.md", "a/*.yaml"))

    def test_reject_overlapping_lane_globs(self):
        m = copy.deepcopy(self.manifest)
        m["lanes"][1]["paths"] = ["mission-control/gogreen/"]
        self.assertTrue(lane_collisions(m))
        with self.assertRaisesRegex(CensusError, "write collision"):
            review(self.observation, m)

    def test_source_scope_isolation_across_repositories(self):
        m = copy.deepcopy(self.manifest)
        m["lanes"][2]["paths"] = ["mission-control/gogreen/pr_intervention.py"]
        self.assertFalse(lane_collisions(m))

    def test_missing_queue_invalid_not_zero(self):
        x = copy.deepcopy(self.observation)
        x["queue_baseline"]["CODEX"]["queued"] = None
        with self.assertRaisesRegex(CensusError, "invalid queue"):
            review(x, self.manifest)

if __name__ == "__main__":
    unittest.main()
