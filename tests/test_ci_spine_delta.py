"""Exact-SHA workflow delta safety, no-running-metrics and custody controls."""
import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ci_spine_delta", ROOT / "scripts/ci_spine_delta.py")
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)


def index(sha="a" * 40):
    path = ".github/workflows/check.yml"
    wf = {"path": path, "name": "Check", "class": "TEST_QA",
          "source_sha256": "1" * 64, "triggers": ["pull_request"],
          "schedules": [], "permissions": "read", "reusable": False,
          "paths_filtered": False, "dag_edges": [],
          "dag_layers": [["test"]], "jobs": [{"id": "test", "needs": [],
                                             "layer": 0, "def_sha256": "2" * 64}]}
    return {"schema": M.SCHEMA_IN,
            "verdict": "PASS_STATIC_BINDINGS_ONLY",
            "source": {"checkout_sha": sha, "expected_sha": sha},
            "assurance": {"merge_admission": "HOLD"},
            "errors": [], "workflows": [wf],
            "anchors": [{"id": "CI-TEST", "path": path, "phase": "TEST",
                         "workflow_oid": "jade:wf:test", "static_binding": "PASS"}]}


class Delta(unittest.TestCase):
    def setUp(self):
        self.a, self.b = index(), index("b" * 40)

    def test_no_false_runtime_or_merge_admission(self):
        r = M.compare(self.a, self.b)
        self.assertEqual(r["verdict"], "NO_OBSERVED_SOURCE_DELTA")
        self.assertEqual(r["counts"]["unchanged"], 1)
        self.assertEqual(r["limits"]["runtime_seconds"], "NOT_MEASURED")
        self.assertEqual(r["limits"]["merge_admission"], "HOLD")

    def test_add_delete_and_no_automatic_prune(self):
        self.b["workflows"] = []
        r = M.compare(self.a, self.b)
        self.assertEqual(r["counts"]["removed"], 1)
        self.assertEqual(r["workflow_changes"][0]["change"], "REMOVED_REQUIRES_CUSTODY_PROOF")
        self.assertFalse(r["limits"]["branch_delete_authorized"])
        self.b["workflows"] = [copy.deepcopy(self.a["workflows"][0])]
        self.b["workflows"][0]["path"] = ".github/workflows/new.yml"
        r = M.compare(self.a, self.b)
        self.assertEqual((r["counts"]["added"], r["counts"]["removed"]), (1, 1))

    def test_trigger_permission_dag_changes_need_attention(self):
        wf = self.b["workflows"][0]
        wf["source_sha256"] = "3" * 64
        wf["permissions"] = "write:contents"
        wf["triggers"] = ["push"]
        wf["dag_edges"] = [["test", "deploy"]]
        r = M.compare(self.a, self.b)
        self.assertTrue(r["workflow_changes"][0]["safety_attention"])
        self.assertEqual(r["counts"]["modified"], 1)
        self.assertIn("permissions", r["workflow_changes"][0]["changed_fields"])
        self.assertIn("dag_edges", r["workflow_changes"][0]["changed_fields"])

    def test_semantic_noop_still_detects_digest_change(self):
        self.b["workflows"][0]["source_sha256"] = "4" * 64
        r = M.compare(self.a, self.b)
        self.assertEqual(r["workflow_changes"][0]["changed_fields"], ["source_only_no_observed_semantic_delta"])

    def test_digest_same_projection_diff_fails_closed(self):
        self.b["workflows"][0]["triggers"] = ["push"]
        self.assertIn("parser projection", " ".join(M.compare(self.a, self.b)["errors"]))

    def test_bad_and_duplicate_inputs_fail(self):
        self.b["verdict"] = "CI_SPINE_CONTRACT_FIRST_RED"
        self.assertEqual(M.compare(self.a, self.b)["verdict"], "CI_SPINE_DELTA_FIRST_RED")
        self.b = index("b" * 40)
        self.b["workflows"].append(copy.deepcopy(self.b["workflows"][0]))
        self.assertIn("duplicate", " ".join(M.compare(self.a, self.b)["errors"]))

    def test_drift_same_commit_never_passes(self):
        self.b = copy.deepcopy(self.a)
        self.b["workflows"][0]["source_sha256"] = "5" * 64
        self.assertIn("same source SHA", " ".join(M.compare(self.a, self.b)["errors"]))

    def test_anchor_rebinding_is_visible_and_cannot_certify(self):
        self.b["anchors"][0]["phase"] = "GOVERN"
        r = M.compare(self.a, self.b)
        self.assertEqual(r["counts"]["authority_binding_changes"], 1)
        self.assertEqual(r["authority_changes"][0]["status"], "AUTHORITY_REVIEW_REQUIRED")
        self.assertEqual(r["verdict"], "DIFFERENCE_REVIEW_REQUIRED")


if __name__ == "__main__":
    unittest.main()
