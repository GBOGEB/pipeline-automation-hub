"""Source-bound cross-repository MissionControl V2 read-only consumer checks."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "federation-atlas/MC_OPERATIONS_ATLAS_V2_BRIDGE_20261017.json"


class OperationsBridgeProof(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = json.loads(SOURCE.read_text(encoding="utf-8"))

    def test_type_and_provenance(self):
        self.assertEqual(self.d["schema"], "missioncontrol.federated_operations_atlas_handoff.v2")
        self.assertEqual(self.d["evidence_class"],
                         "PINNED_SOURCE_BLOBS_AND_DECLARED_LINKS_NOT_NATIVE_AUTHENTICATION")

    def test_code_exposes_no_master_dags_authority(self):
        self.assertIsNone(self.d["limits"]["canonical_master_dags_path"])
        self.assertFalse(self.d["limits"]["cross_repository_dispatch_enabled"])
        self.assertFalse(self.d["limits"]["authority_transfer"])
        self.assertFalse(self.d["limits"]["security_waiver"])
        self.assertEqual(self.d["limits"]["merge_admission"], "HOLD")

    def test_original_hub_registry_is_reused(self):
        c = self.d["consumer"]
        self.assertEqual(c["repo"], "GBOGEB/pipeline-automation-hub")
        self.assertEqual(c["pr"], 631)
        self.assertEqual(c["compatibility_manifest_blob"],
                         "84f0fdf2260d8230b7dafd23f4f462cdd5270acb")

    def test_source_pinned_to_exact_blobs(self):
        s = self.d["producer"]
        self.assertEqual(s["repo"], "GBOGEB/CODEX")
        self.assertEqual(s["pr"], 1068)
        for item in ("source_ledger", "visualization", "mermaid"):
            self.assertRegex(s[item]["git_blob_sha"], r"^[0-9a-f]{40}$")
            self.assertNotEqual(s[item]["git_blob_sha"], "0" * 40)
        self.assertRegex(s["head_sha"], r"^[0-9a-f]{40}$")

    def test_graph_atom_denominators_are_separate(self):
        m = self.d["measurement"]
        self.assertEqual((m["repository_views"], m["source_registry_repositories"]),
                         (5, 4))
        self.assertEqual((m["verified_graph_families"], m["typed_nodes"], m["typed_edges"]),
                         (8, 32, 43))
        self.assertIsNone(m["matched_coverage_delta"])

    def test_declared_federation_edges_have_no_execution_receipts(self):
        edges = self.d["edges"]
        self.assertEqual(len(edges), 3)
        self.assertEqual(self.d["measurement"]["declared_cross_repo_links"], 3)
        self.assertTrue(all(not e["executable"] and e["native_receipt"] is None
                            and e["state"] == "DECLARED" for e in edges))
        self.assertEqual(len({(e["from"], e["to"]) for e in edges}), 3)

    def test_unknown_authentication_must_not_be_zero(self):
        m = self.d["measurement"]
        self.assertIsNone(m["authenticated_worker_runs"])
        self.assertIsNone(m["accepted_remote_execution_edges"])
        self.assertIsNone(self.d["consumer"]["native_run_job_binding"])
        self.assertIsNone(self.d["limits"]["causal_root_closure_credit"])

    def test_development_review_cannot_promote_admission(self):
        self.assertIn("existing MASTER_DAGS compatibility bridge",
                      self.d["notices"][0])
        self.assertTrue(self.d["limits"]["approval_by_source_owner_required"])
        self.assertTrue(self.d["limits"]["source_blob_readback_required"])

    def test_replay_fails_on_forged_execution_claim(self):
        bad = json.loads(json.dumps(self.d))
        bad["edges"][0]["executable"] = True
        self.assertFalse(all(not e["executable"] and e["native_receipt"] is None
                             for e in bad["edges"]))


if __name__ == "__main__":
    unittest.main()
