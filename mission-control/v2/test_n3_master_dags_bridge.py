"""Negative and integration tests for the non-authoritative graph crosswalk."""
import copy
import json
import sys
import tempfile
from unittest.mock import patch
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from n3_master_dags_bridge import project, main

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

    def test_reject_duplicate_repository(self):
        m = fixture(); m["sources"][1] = copy.deepcopy(m["sources"][0])
        with self.assertRaisesRegex(ValueError, "duplicate source repository"):
            project(m)

    def test_reject_missing_source_blob_sha(self):
        m = fixture(); m["sources"][1].pop("blob_sha")
        with self.assertRaisesRegex(ValueError, "source SHA"):
            project(m)

    def test_reject_untrusted_graph_identifier(self):
        m = fixture(); m["sources"][1]["graph_ids"] = ["../../evil"]
        with self.assertRaisesRegex(ValueError, "malformed graph ID"):
            project(m)

    def test_reject_empty_graph_family(self):
        m = fixture(); m["sources"][1]["graph_ids"] = []
        with self.assertRaisesRegex(ValueError, "missing graph IDs"):
            project(m)

    def test_reject_wrong_expected_hub_base(self):
        with self.assertRaisesRegex(ValueError, "stale hub base SHA"):
            project(fixture(), expected_hub_base="a" * 40)

    def test_reject_undeclared_native_receipt(self):
        m = fixture(); m["native_receipt"] = {"run_id": 1}
        with self.assertRaisesRegex(ValueError, "native receipt"):
            project(m)

    def test_reject_fake_crew_dispatch_ids(self):
        m = fixture(); m["authenticated_crew_ids"] = []
        with self.assertRaisesRegex(ValueError, "crew identity"):
            project(m)

    def test_reject_admitted_root_counts(self):
        m = fixture(); m["root_closures"] = 0
        with self.assertRaisesRegex(ValueError, "causal root"):
            project(m)

    def test_reject_same_repo_federation_edge(self):
        m = fixture()
        m["links"][0]["to"] = "GBOGEB/ABACUS::AGENT_EXECUTION_GRAPH"
        with self.assertRaisesRegex(ValueError, "cross repository"):
            project(m)

    def test_reject_duplicated_federation_edge(self):
        m = fixture(); m["links"].append(copy.deepcopy(m["links"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate candidate edge"):
            project(m)

    def test_cli_writes_source_bound_projection_and_unknowns(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "projection.json"
            args = ["master_dags_bridge", "--manifest", str(MANIFEST),
                    "--out", str(out), "--expected-hub-base",
                    fixture()["hub_base_sha"]]
            with patch.object(sys, "argv", args):
                main()
            result = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(result["metrics"]["graph_families"], 8)
            self.assertIsNone(result["metrics"]["accepted_coverage_delta"])
            self.assertIsNone(result["accepted_n_delta"])
            self.assertEqual(result["merge_admission"], "HOLD")
            self.assertEqual(len(result["source_digest_sha256"]), 64)

    def test_cli_bad_manifest_is_fail_closed_without_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bad = root / "bad.json"
            bad.write_text('{"schema":"unsafe"}', encoding="utf-8")
            out = root / "projection.json"
            with patch.object(sys, "argv", ["master_dags_bridge", "--manifest",
                                           str(bad), "--out", str(out)]):
                with self.assertRaisesRegex(ValueError, "incompatible contract"):
                    main()
            self.assertFalse(out.exists())

    def test_declared_edge_cannot_masquerade_as_verified(self):
        x = project(fixture())
        self.assertTrue(all(edge["binding"] == "DECLARED" and
                            edge["accepted"] is False and edge["receipt"] is None
                            for edge in x["edges"]))
        self.assertIsNone(x["metrics"]["native_verified_edges"])
        self.assertIsNone(x["metrics"]["formal_root_closures"])

    def test_source_digest_is_stable_against_manifest_key_order(self):
        m = fixture()
        a = project(m)
        b = project(dict(reversed(list(m.items()))))
        self.assertEqual(a["source_digest_sha256"], b["source_digest_sha256"])
        self.assertEqual(a["topological_order"], b["topological_order"])

    def test_reject_unrecognized_edge_kind(self):
        m = fixture(); m["links"][0]["kind"] = "CAUSES"
        with self.assertRaisesRegex(ValueError, "unrecognized edge semantics"):
            project(m)

    def test_graph_with_no_declared_edges_is_not_false_positive(self):
        m = fixture(); m["links"] = []
        x = project(m)
        self.assertEqual(x["metrics"]["declared_cross_repository_edges"], 0)
        self.assertEqual(x["metrics"]["graph_families"], 8)
        self.assertEqual(x["merge_admission"], "HOLD")
