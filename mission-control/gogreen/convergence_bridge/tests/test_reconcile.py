"""G11 cross-lane exact-identity convergence and hostile metric tests."""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/"convergence_bridge/reconcile.py"
G7=ROOT/"success_graph/samples/native_success_20261017.json"
G9=ROOT/"outcome_convergence/samples/native_full_window_20261017.json"
REGISTRY=ROOT.parent/"grand-missions/GM_DMAIC_EVOLUTION_T7_T14_T21_v1.json"
G10=ROOT/"convergence_bridge/samples/g10_native_quality_20261017.json"
SHA="a"*40
import importlib.util
spec=importlib.util.spec_from_file_location("convergence_bridge",SOURCE)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
g7mod=m.import_source(ROOT/"success_graph/runner_telemetry.py","g7_under_test")
g9mod=m.import_source(ROOT/"outcome_convergence/outcome_flight.py","g9_under_test")


class ConvergenceNative(unittest.TestCase):
    def setUp(self):
        self.g7=json.loads(G7.read_text())
        self.g9=json.loads(G9.read_text())
        self.g10=json.loads(G10.read_text())
        self.registry=json.loads(REGISTRY.read_text())

    def joined(self):
        return m.join(self.g7,self.registry,self.g9,self.g10,g7mod,g9mod)

    def invalid(self):
        with self.assertRaises((ValueError,KeyError,TypeError)):
            self.joined()

    def test_actual_source_join_12_and_69(self):
        r=self.joined()
        self.assertEqual((r["g7_selected_successful_run_ids"],r["g9_complete_window_run_ids"],
                          r["native_run_id_overlap"],r["unique_union_run_ids"]), (24,57,12,69))

    def test_outcome_union_no_false_rate(self):
        r=self.joined()
        self.assertEqual((r["unique_union_successes"],r["union_native_failed"],
                          r["union_native_cancelled"]),(58,10,1))
        self.assertIsNone(r["global_fleet_success_rate"])
        self.assertIsNone(r["union_success_fraction"])

    def test_exact_common_ids_are_unique(self):
        r=self.joined()
        self.assertEqual(len(set(r["common_ids"])),12)
        self.assertEqual(len(r["common_ids"]),12)
        self.assertEqual(sum(r["common_by_repository"].values()),12)

    def test_math_qps_repeated_successes_not_double_counted(self):
        r=self.joined()
        self.assertEqual(r["common_by_repository"],
                         {"GBOGEB/cryoplant-project":6,"GBOGEB/gg_MATH":6})
        self.assertEqual(r["g7_successful_runs_outside_g9_population"],12)
        self.assertEqual(r["g9_runs_outside_g7_population"],45)

    def test_three_scoped_module_receipts(self):
        r=self.joined()
        self.assertEqual(r["tracked_native_test_methods_across_separate_heads"],153)
        self.assertEqual(r["tracked_module_statements"],[531,531])
        self.assertEqual(r["tracked_module_branches"],[90,90])
        self.assertFalse(r["integrated_single_head_all_module_proof"])
        self.assertTrue(all(not x["whole_repo"] for x in r["native_module_coverage"]))

    def test_G10_visual_qa_limits(self):
        g=m.validate_g10(self.g10)
        self.assertEqual(g["graph_nodes"],15)
        self.assertEqual(g["graph_edges"],24)
        self.assertEqual(g["observed_edges"]+g["declared_edges"],24)
        self.assertFalse(g["independent_review"])

    def test_sipoc_graph_edges_declared_no_admission(self):
        r=self.joined()
        graph=m.sipoc(r)
        self.assertEqual(graph["overlap"],12)
        self.assertEqual(graph["unique_runs"],69)
        self.assertTrue(any(e["confidence"]=="DECLARED" for e in graph["edges"]))
        self.assertFalse(graph["merge_authorized"])

    def test_html_uses_unique_not_sum_counts(self):
        h=m.html_page(self.joined())
        self.assertIn('>12</strong>',h)
        self.assertIn('>69</strong>',h)
        self.assertIn('NO fleet success rate',h)

    def test_html_escapes_untrusted_coverage_module(self):
        r=self.joined()
        r["native_module_coverage"][0]["module"]="<script>alert(1)</script>"
        h=m.html_page(r)
        self.assertNotIn("<script>alert",h)
        self.assertIn("&lt;script&gt;",h)

    def test_build_digest_and_exact_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            result,manifest=m.build(ROOT,SHA,Path(tmp))
            self.assertEqual(result["unique_union_run_ids"],69)
            self.assertEqual(manifest["exact_head"],SHA)
            for name,v in manifest["files"].items():
                self.assertEqual(hashlib.sha256((Path(tmp)/name).read_bytes()).hexdigest(),v)

    def test_native_cli_prints_reconciled_denominators(self):
        with tempfile.TemporaryDirectory() as tmp:
            buf=io.StringIO()
            argv=["reconcile.py","--root",str(ROOT),"--out",str(Path(tmp)/"out"),
                  "--source-sha",SHA]
            with patch.object(sys,"argv",argv),contextlib.redirect_stdout(buf):
                runpy.run_path(str(SOURCE),run_name="__main__")
            payload=json.loads(buf.getvalue())
            self.assertEqual(payload["intersection"],12)
            self.assertEqual(payload["unique"],69)
            self.assertTrue((Path(tmp)/"out"/"sipoc_dag.json").exists())

    def test_bad_producer_sha_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                m.build(ROOT,"wrong",Path(tmp))

    def test_missing_canonical_producer_rejected(self):
        with self.assertRaises(ValueError):
            m.import_source(ROOT/"MISSING.py","missing")

    def test_g7_wrong_native_run_head_rejected(self):
        self.g7["workflow_samples"][1]["run_observations"][0]["source_sha"]="f"*40
        self.invalid()

    def test_g7_selected_failure_rejected(self):
        self.g7["workflow_samples"][1]["run_observations"][0]["conclusion"]="failure"
        self.invalid()

    def test_g7_duplicate_run_id_rejected(self):
        a=self.g7["workflow_samples"]
        a[1]["run_observations"][0]["run_id"]=a[0]["run_observations"][0]["run_id"]
        self.invalid()

    def test_g9_missing_run_rejected(self):
        self.g9["cohorts"][0]["runs"].pop()
        self.invalid()

    def test_g9_run_cloned_double_credit_rejected(self):
        c=self.g9["cohorts"][1]
        c["runs"][1]["id"]=c["runs"][0]["id"]
        self.invalid()

    def test_g9_fake_completion_green_rejected(self):
        self.g9["cohorts"][1]["runs"][0]["status"]="queued"
        self.invalid()

    def test_g9_scope_changed_rejected(self):
        self.g9["cohorts"][1]["population_class"]="SUCCESS_ONLY"
        self.invalid()

    def test_overlap_conflicting_attempt_rejected(self):
        r=self.g9["cohorts"][0]["runs"]
        match=next(x for x in r if x["id"]==38955869218)
        match["attempt"]=2
        self.invalid()

    def test_overlap_conflicting_head_rejected(self):
        match=next(x for x in self.g9["cohorts"][0]["runs"] if x["id"]==38955869218)
        match["sha"]="f"*40
        self.invalid()

    def test_overlap_conflicting_workflow_rejected(self):
        match=next(x for x in self.g9["cohorts"][0]["runs"] if x["id"]==38955869218)
        match["workflow"]="FAKE WORKFLOW"
        self.invalid()

    def test_overlap_conflicting_timestamp_rejected(self):
        match=next(x for x in self.g9["cohorts"][0]["runs"] if x["id"]==38955869218)
        match["created_at"]="2026-10-16T19:35:00Z"
        self.invalid()

    def test_overlap_red_not_success_rejected(self):
        match=next(x for x in self.g9["cohorts"][0]["runs"] if x["id"]==38955869218)
        match["conclusion"]="failure"
        self.invalid()

    def test_overlap_subset_dropped_rejected(self):
        q=self.g7["workflow_samples"][1]["run_observations"]
        q.pop()
        self.invalid()

    def test_g10_false_merge_rejected(self):
        self.g10["merge_authorized"]=True
        self.invalid()

    def test_g10_false_independent_review_rejected(self):
        self.g10["independent_review"]=True
        self.invalid()

    def test_g10_forged_visual_browser_ci_rejected(self):
        self.g10["browser_visual_qa_proven"]="FULL_BROWSER_NATIVE"
        self.invalid()

    def test_g10_forged_external_archive_rejected(self):
        self.g10["external_custody_verified"]=True
        self.invalid()

    def test_g10_forged_manifest_sha_rejected(self):
        self.g10["source_manifest_sha256"]="f"*64
        self.invalid()

    def test_g10_missing_manifest_rejected(self):
        self.g10["source_manifest_sha256"]=""
        self.invalid()

    def test_g10_fake_module_sha_rejected(self):
        self.g10["module_source_git_blob"]="f"*40
        self.invalid()

    def test_g10_fake_run_head_rejected(self):
        self.g10["source_sha"]="f"*40
        self.invalid()

    def test_g10_wrong_run_id_rejected(self):
        self.g10["native_run_id"]=1
        self.invalid()

    def test_g10_wrong_job_id_rejected(self):
        self.g10["native_job_id"]=1
        self.invalid()

    def test_g10_wrong_attempt_rejected(self):
        self.g10["attempt"]=2
        self.invalid()

    def test_g10_test_denominator_forged_rejected(self):
        self.g10["tests_passed"]=53
        self.invalid()

    def test_g10_coverage_denominator_shrunk_rejected(self):
        self.g10["statement_eligible"]=150
        self.invalid()

    def test_g10_branch_denominator_shrunk_rejected(self):
        self.g10["branch_eligible"]=30
        self.invalid()

    def test_g10_coverage_tool_drift_rejected(self):
        self.g10["coverage_tool"]="coverage==7.1"
        self.invalid()

    def test_g10_source_scope_changed_rejected(self):
        self.g10["source_scope"]="not real"
        self.invalid()

    def test_g10_nodes_mismatched_rejected(self):
        self.g10["graph_nodes"]=14
        self.invalid()

    def test_g10_edge_confidence_forgery_rejected(self):
        self.g10["observed_edges"]=24
        self.invalid()

    def test_g10_foreign_owner_rejected(self):
        self.g10["repository"]="GBOGEB/other"
        self.invalid()

    def test_g10_false_root_review_rejected(self):
        self.g10["authority_transfer"]=True
        self.invalid()

    def test_root_authority_still_hold(self):
        r=self.joined()
        self.assertEqual(r["root_closure_credit"],0)
        self.assertEqual(r["formal_admission"],"HOLD")
        self.assertFalse(r["dispatch_authorized"])
        self.assertFalse(r["merge_authorized"])


if __name__=="__main__":
    unittest.main()
