"""Exact-SHA workflow delta safety, no-running-metrics and custody controls."""
import copy
import importlib.util
import json
import tempfile
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
          "dag_layers": [["test"]], "jobs": [{"id": "test", "oid": "jade:job:check/test",
                                             "needs": [], "layer": 0,
                                             "def_sha256": "2" * 64}]}
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

    def test_identical_digest_projections_cannot_disagree(self):
        changes = {"reusable": True, "paths_filtered": True,
                   "dag_layers": [["test"], ["deploy"]],
                   "parse_error": "YAML", "dag_cycle": True,
                   "dangling_needs": ["test->missing"], "oid": "different"}
        for field, altered in changes.items():
            with self.subTest(field=field):
                self.b = index("b" * 40)
                self.b["workflows"][0][field] = altered
                result = M.compare(self.a, self.b)
                self.assertEqual(result["verdict"], "CI_SPINE_DELTA_FIRST_RED")
                self.assertIn("parser projection", " ".join(result["errors"]))

    def test_structural_drift_is_not_an_innocuous_source_only_change(self):
        for field, altered in (("parse_error", "YAML"), ("dag_cycle", True),
                               ("dangling_needs", ["a->missing"]),
                               ("jobs", [{"id": "test", "parse_error": "malformed job"}])):
            with self.subTest(field=field):
                self.b = index("b" * 40)
                self.b["workflows"][0]["source_sha256"] = "9" * 64
                self.b["workflows"][0][field] = altered
                result = M.compare(self.a, self.b)
                self.assertEqual(result["counts"]["modified"], 1)
                row = result["workflow_changes"][0]
                self.assertTrue(row["safety_attention"])
                self.assertNotEqual(row["changed_fields"], ["source_only_no_observed_semantic_delta"])
                self.assertEqual(row["merge_admission"], "HOLD")

    def test_malformed_nested_index_writes_structured_first_red(self):
        for field, malformed in (("source", ["bad"]), ("assurance", ["bad"]),
                                 ("source", "bad"), ("assurance", "bad"), ("errors", None)):
            with self.subTest(field=field, malformed=malformed):
                self.b = index("b" * 40)
                self.b[field] = malformed
                outcome = M.compare(self.a, self.b)
                self.assertEqual(outcome["verdict"], "CI_SPINE_DELTA_FIRST_RED")
                self.assertTrue(outcome["errors"])
                self.assertEqual(outcome["limits"]["merge_admission"], "HOLD")
                with tempfile.TemporaryDirectory() as td:
                    before, after, receipt = (Path(td) / x for x in ("before.json", "after.json", "receipt.json"))
                    before.write_text(json.dumps(self.a), encoding="utf-8")
                    after.write_text(json.dumps(self.b), encoding="utf-8")
                    self.assertEqual(M.main(["--before", str(before), "--after", str(after),
                                             "--out", str(receipt), "--check"]), 1)
                    self.assertEqual(json.loads(receipt.read_text())["verdict"], "CI_SPINE_DELTA_FIRST_RED")

    def test_falsy_or_missing_job_inventory_is_not_a_clean_delta(self):
        for malformed in (None, "", {}, 0, False, "MISSING"):
            with self.subTest(value=malformed):
                self.b = index("b" * 40)
                wf = self.b["workflows"][0]
                wf["source_sha256"] = "9" * 64
                if malformed == "MISSING":
                    wf.pop("jobs")
                else:
                    wf["jobs"] = malformed
                result = M.compare(self.a, self.b)
                self.assertEqual(result["verdict"], "CI_SPINE_DELTA_FIRST_RED")
                self.assertIn("malformed jobs inventory", " ".join(result["errors"]))
                row = result["workflow_changes"][0]
                self.assertEqual(row["change"], "MODIFIED")
                self.assertTrue(row["safety_attention"])
                self.assertIn("malformed_job_inventory", row["changed_fields"])
                self.assertEqual(row["merge_admission"], "HOLD")

    def test_duplicate_or_invalid_job_identity_is_first_red(self):
        for invalid in ([None], [{"id": 2}],
                        [{"id": "test"}, {"id": "test"}]):
            with self.subTest(invalid=invalid):
                self.b = index("b" * 40)
                self.b["workflows"][0]["jobs"] = invalid
                self.b["workflows"][0]["source_sha256"] = "a" * 64
                result = M.compare(self.a, self.b)
                self.assertEqual(result["verdict"], "CI_SPINE_DELTA_FIRST_RED")
                self.assertTrue(result["errors"])
                self.assertTrue(result["workflow_changes"][0]["safety_attention"])

    def test_complete_job_projection_is_required_for_all_pulses(self):
        # A malformed projection must not become NO_OBSERVED_SOURCE_DELTA,
        # even when both source hashes and the malformed job are identical.
        variants = (
            {"id": "test", "needs": {}, "layer": [], "def_sha256": "bad",
             "oid": "jade:job:bad"},
            {"id": "", "needs": [], "layer": 0, "def_sha256": "2" * 64,
             "oid": "jade:job:bad"},
            {"id": "test", "needs": [], "layer": 0, "def_sha256": "2" * 64},
            {"id": "test", "oid": "", "needs": [], "layer": 0,
             "def_sha256": "2" * 64},
            {"id": "test", "oid": "jade:job:a", "needs": "build", "layer": 0,
             "def_sha256": "2" * 64},
            {"id": "test", "oid": "jade:job:a", "needs": ["", "build"],
             "layer": 0, "def_sha256": "2" * 64},
            {"id": "test", "oid": "jade:job:a", "needs": [], "layer": True,
             "def_sha256": "2" * 64},
            {"id": "test", "oid": "jade:job:a", "needs": [], "layer": [],
             "def_sha256": "2" * 64},
            {"id": "test", "oid": "jade:job:a", "needs": [], "layer": 0,
             "def_sha256": "bad"},
        )
        for job in variants:
            with self.subTest(job=job):
                old, new = index(), index("b" * 40)
                old["workflows"][0]["jobs"] = [copy.deepcopy(job)]
                new["workflows"][0]["jobs"] = [copy.deepcopy(job)]
                result = M.compare(old, new)
                self.assertEqual(result["verdict"], "CI_SPINE_DELTA_FIRST_RED")
                self.assertTrue(any("malformed job projection" in e for e in result["errors"]))
                self.assertEqual(result["limits"]["merge_admission"], "HOLD")

    def test_valid_job_projection_accepts_null_layer_and_multiple_needs(self):
        old, new = index(), index("b" * 40)
        for row in (old["workflows"][0], new["workflows"][0]):
            row["jobs"] = [{"id": "test", "oid": "jade:job:check/test",
                            "needs": ["build", "check"], "layer": None,
                            "def_sha256": "f" * 64}]
        result = M.compare(old, new)
        self.assertEqual(result["verdict"], "NO_OBSERVED_SOURCE_DELTA")
        self.assertEqual(result["errors"], [])

    def test_anchor_rebinding_is_visible_and_cannot_certify(self):
        self.b["anchors"][0]["phase"] = "GOVERN"
        r = M.compare(self.a, self.b)
        self.assertEqual(r["counts"]["authority_binding_changes"], 1)
        self.assertEqual(r["authority_changes"][0]["status"], "AUTHORITY_REVIEW_REQUIRED")
        self.assertEqual(r["verdict"], "DIFFERENCE_REVIEW_REQUIRED")


if __name__ == "__main__":
    unittest.main()
