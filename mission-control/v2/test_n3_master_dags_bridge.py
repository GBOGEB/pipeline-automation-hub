"""Negative and integration tests for the non-authoritative graph crosswalk."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from n3_master_dags_bridge import project

ROOT = Path(__file__).resolve().parents[1] / "federation-atlas"
MANIFEST = ROOT / "G3A_N13_N15_MASTER_DAGS_COMPAT_20261017.json"


def fixture():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


class BridgeContracts(unittest.TestCase):
    def test_four_source_graph_families_and_declared_links(self):
        r = project(fixture())
        self.assertEqual((r["metrics"]["sources"], r["metrics"]["graph_families"],
                          r["metrics"]["declared_cross_repository_edges"]), (4, 8, 3))
        self.assertEqual(len(r["topological_order"]), 8)
        self.assertEqual(r["evidence_class"], "SOURCE_REFERENCE_DECLARED_NOT_NATIVE_AUTHENTICATED")

    def test_cannot_promote_admission_or_canonical_master_path(self):
        a = fixture(); a["merge_admission"] = "PASS"
        with self.assertRaisesRegex(ValueError, "authority escalation"):
            project(a)
        b = fixture(); b["canonical_master_dags_path"] = "MASTER_DAGS"
        with self.assertRaisesRegex(ValueError, "MASTER_DAGS"):
            project(b)

    def test_source_sha_exact_and_lowercase(self):
        a = fixture(); a["sources"][0]["commit_sha"] = "A" * 40
        with self.assertRaisesRegex(ValueError, "source SHA"):
            project(a)

    def test_collision_of_graph_id_rejected(self):
        a = fixture(); a["sources"][0]["graph_ids"].append("DMAIC_WORK_GRAPH")
        with self.assertRaisesRegex(ValueError, "duplicate graph"):
            project(a)

    def test_reject_unregistered_path(self):
        a = fixture(); a["sources"][0]["path"] = "../MASTER_DAGS.yaml"
        with self.assertRaisesRegex(ValueError, "unregistered source path"):
            project(a)

    def test_reject_unregistered_endpoint(self):
        a = fixture(); a["links"][0]["to"] = "GBOGEB/CODEX::PHANTOM"
        with self.assertRaisesRegex(ValueError, "unregistered graph endpoint"):
            project(a)

    def test_reject_forced_receipt_binding(self):
        a = fixture(); a["links"][0]["binding"] = "RECEIPT_BOUND"
        with self.assertRaisesRegex(ValueError, "unverified receipt"):
            project(a)

    def test_reject_cycle(self):
        a = fixture()
        a["links"].append({"from": "GBOGEB/pipeline-automation-hub::CODE_PURPLE_BEAMS_DAG",
                           "to": "GBOGEB/ABACUS::DMAIC_WORK_GRAPH", "binding": "DECLARED",
                           "kind": "FEDERATION_CANDIDATE", "receipt": None})
        with self.assertRaisesRegex(ValueError, "cyclic"):
            project(a)
