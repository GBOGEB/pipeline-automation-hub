"""Negative-first lossless lineage for old B00-B09 vs new candidate B00-B12."""
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OLD = ROOT / "docs/ci-spine/LOGICAL_BUNDLE_DAG_v1.json"
INDEX = ROOT / "docs/ci-spine/WORKFLOW_INDEX_20261028.json"
MAP = ROOT / "docs/ci-spine/BUNDLE_B00_B09_TO_CANDIDATE_B00_B12_V1.json"
CATALOG = ROOT / "mission-control/jade_temple/devops/CI_BUNDLE_CATALOG_V1.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


class LosslessLegacyCrosswalk(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = load(OLD)
        cls.index = load(INDEX)
        cls.map = load(MAP)
        cls.catalog = load(CATALOG)

    def test_legacy_bundles_are_complete_and_not_assumed_equivalent(self):
        got = {r["legacy_design"]["id"] for r in self.map["mapping"]}
        self.assertEqual(got, {f"B{i:02d}" for i in range(10)})
        for row in self.map["mapping"]:
            self.assertTrue(row["losslessness_gap"])
            self.assertTrue(row["representative_only"])
            self.assertTrue(all(x["relationship"] == "PARTIAL_SEMANTIC_OVERLAP_NOT_EQUIVALENCE"
                                for x in row["candidate_overlaps"]))
        self.assertEqual(self.map["identity_rule"], "LEGACY_BXX_NEVER_EQUALS_CANDIDATE_BXX_BY_ID")

    def test_all_candidate_ids_accounted_for_but_not_promoted(self):
        ids = {x["id"] for x in self.catalog["bundles"]}
        mapped = {x["id"] for row in self.map["mapping"] for x in row["candidate_overlaps"]}
        self.assertEqual(ids, mapped)
        self.assertEqual(self.catalog["status"], "ADVISORY_CANDIDATE_OVERLAY_NOT_CANONICAL")
        self.assertFalse(self.catalog["reconciliation"]["owner_approved"])

    def test_each_workflow_anchor_preserves_exact_source_oid_and_disposition(self):
        idx = {x["path"]: x for x in self.index["workflows"]}
        for row in self.map["mapping"]:
            anchor = row["legacy_design"]["representative_workflow"]
            official = idx[anchor["path"]]
            self.assertEqual(anchor["source_blob_oid"], official["blob_oid"])
            self.assertEqual(anchor["admission_disposition_at_source"], official["admission_snapshot"])
            self.assertEqual(anchor["legacy_workflow_name"], official["legacy_name"])
            self.assertTrue(anchor["triggers_at_source"])
            self.assertFalse(anchor["alias_approved"])
            self.assertFalse(row["consumer_migration"]["approved"])

    def test_old_dag_edges_and_temporal_feedback_unchanged(self):
        old = self.old["edges"]
        graph = self.map["legacy_graph"]
        self.assertEqual(graph["feedforward_edges"], [e for e in old if e["kind"] == "FEEDFORWARD"])
        self.assertEqual(graph["temporal_feedback_edges"], [e for e in old if e["kind"] == "FEEDBACK_NEXT_PULSE"])
        self.assertEqual(len(graph["temporal_feedback_edges"]), 1)
        self.assertEqual(graph["join_contract"]["bundle"], "B07")
        self.assertEqual(graph["join_contract"]["owner"], "mission-control/gogreen/required_gate/gate.py")

    def test_source_commit_is_not_git_tree_oid(self):
        source = self.map["legacy_source"]
        self.assertFalse(source["tree_oid_claim_matches_actual"])
        actual = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", f"{source['commit_sha']}^{{tree}}"],
            check=True, capture_output=True, text=True, encoding="utf-8"
        ).stdout.strip()
        self.assertEqual(actual, source["actual_git_tree_oid"])
        self.assertNotEqual(actual, source["workflow_index_tree_oid_claim"])

    def test_no_authority_transfer_or_status_rename(self):
        effects = self.map["effects"]
        self.assertEqual(effects["required_check_contexts_changed"], 0)
        self.assertEqual(effects["live_workflow_names_changed"], 0)
        self.assertEqual(effects["live_job_ids_changed"], 0)
        self.assertFalse(effects["admission_json_changed"])
        self.assertFalse(effects["merge_authorized"])
        self.assertFalse(effects["owner_approved"])
        self.assertEqual(effects["formal_credit_delta"], 0)

    def test_old_b07_fanin_is_not_new_b07_scientific_math(self):
        row = next(x for x in self.map["mapping"] if x["legacy_design"]["id"] == "B07")
        self.assertEqual(row["legacy_design"]["name"] if "name" in row["legacy_design"] else row["legacy_design"]["label"], "fanin")
        self.assertEqual([x["id"] for x in row["candidate_overlaps"]], ["B12"])
        self.assertEqual(next(x["key"] for x in self.catalog["bundles"] if x["id"] == "B07"), "scientific-math")

    def test_cache_and_next_pulse_gaps_must_be_stated(self):
        rows = {x["legacy_design"]["id"]: x for x in self.map["mapping"]}
        self.assertIn("dedicated", " ".join(rows["B02"]["losslessness_gap"]))
        self.assertIn("next-pulse", " ".join(rows["B09"]["losslessness_gap"]))


if __name__ == "__main__":
    unittest.main()
