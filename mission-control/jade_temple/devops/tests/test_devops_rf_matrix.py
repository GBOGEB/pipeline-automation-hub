"""Negative-first verification of the read-only RF matrix and existing B00..B09 family."""
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # mission-control/jade_temple
REPO = ROOT.parent.parent
path = ROOT / "tools" / "rf_matrix_wave.py"
spec = importlib.util.spec_from_file_location("jade_rf_matrix", path)
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
SHA = "a" * 40


def data():
    matrix = json.loads((REPO / "docs/ci-spine/RF_MATRIX_WAVE_v1.json").read_text(encoding="utf-8"))
    bundles = json.loads((REPO / "docs/ci-spine/LOGICAL_BUNDLE_DAG_v1.json").read_text(encoding="utf-8"))
    return matrix, bundles


def sample(value=0.19, sha=SHA, n=1000):
    return {"metric": "recheck_workflow_record_share",
            "metric_owner": M.METRIC_OWNER, "source_sha": sha,
            "sample_method": "last_1000_repo_workflow_runs", "value": value,
            "sample_n": n, "observed_at": "2026-10-29T15:00:00Z",
            "receipt_sha256": "f" * 64}


class RFWaveProjection(unittest.TestCase):
    def test_real_bundle_registry_has_10_sipoc_nodes_and_temporal_edge(self):
        matrix, dag = data()
        nodes, edges = M.dag_index(dag)
        self.assertEqual(len(nodes), 10)
        self.assertEqual(len(edges), 17)
        self.assertEqual(len([e for e in edges if e[2] == "FEEDBACK_NEXT_PULSE"]), 1)

    def test_11_lanes_delegate_to_existing_pulse_scheduler(self):
        matrix, dag = data()
        r = M.project(matrix, dag, SHA)
        self.assertEqual(r["schema"], "jade.devops.rf-matrix-projection.v1")
        self.assertEqual(r["matrix"]["schema"], "jade.devops.rf-pulse-plan.v1")
        self.assertFalse(r["authority"]["dispatch_performed"])
        self.assertFalse(r["authority"]["merge_authorized"])
        self.assertEqual(len(matrix["lanes"]), 11)

    def test_first_wave_is_disjoint_and_off_interval_is_not_idle(self):
        matrix, dag = data()
        p = M.project(matrix, dag, SHA)["matrix"]
        ids = {z["id"] for z in p["on"]}
        self.assertEqual(ids, {"P0_BASELINE_READER", "P0_RECHECK_DOCTOR",
                               "P0_SECURITY_AUDITOR", "P1_COVERAGE_GUARD", "P1_CACHE_PILOT"})
        self.assertTrue(all(z["sipoc"]["output"] for z in p["on"]))
        self.assertTrue(all(z["mode"] == "TAKE_STOCK_NEXT_PULSE" for z in p["off"]))
        self.assertEqual({x["crew"] for x in p["on"]}, {"READER", "DOCTOR", "AUDITOR", "BUILDER", "RUNNER"})

    def test_unknown_future_telemetry_is_not_zero_or_goal_met(self):
        matrix, dag = data()
        result = M.project(matrix, dag, SHA)
        self.assertEqual(result["goal"]["status"], "UNKNOWN")
        self.assertEqual(result["goal"]["action"], "WAIT_FOR_MATCHED_T1")
        self.assertEqual(result["goal"]["admission"], "HOLD")

    def test_invalid_source_head_fails_closed(self):
        matrix, dag = data()
        with self.assertRaises(ValueError):
            M.project(matrix, dag, "not-a-sha")

    def test_missing_sipoc_field_fails_closed(self):
        matrix, dag = data()
        dag["nodes"][0]["sipoc"].pop("input")
        with self.assertRaisesRegex(ValueError, "SIPOC"):
            M.project(matrix, dag, SHA)

    def test_duplicate_bundle_identity_rejected(self):
        matrix, dag = data()
        dag["nodes"][1]["short_id"] = dag["nodes"][0]["short_id"]
        with self.assertRaises(ValueError):
            M.project(matrix, dag, SHA)

    def test_new_feedforward_cycle_in_design_cannot_be_hidden(self):
        matrix, dag = data()
        dag["edges"].append({"from": "ci-spine:bundle:B01", "to": "ci-spine:bundle:B00",
                             "kind": "FEEDFORWARD"})
        with self.assertRaisesRegex(ValueError, "cycle"):
            M.project(matrix, dag, SHA)

    def test_feedback_must_unroll_to_next_pulse(self):
        matrix, dag = data()
        dag["edges"][-1]["to"] = "ci-spine:bundle:B01"
        with self.assertRaisesRegex(ValueError, "temporal feedback"):
            M.project(matrix, dag, SHA)

    def test_stage_must_match_bundle_source(self):
        matrix, dag = data()
        matrix["lanes"][0]["devops_stage"] = "S8_MONITOR"
        with self.assertRaisesRegex(ValueError, "stage"):
            M.project(matrix, dag, SHA)

    def test_reverse_lane_dependency_not_mistaken_for_bundle_edge(self):
        matrix, dag = data()
        matrix["lanes"][0]["depends_on"] = ["P3_EXACT_HEAD_FANIN"]
        with self.assertRaisesRegex(ValueError, "ancestry"):
            M.project(matrix, dag, SHA)

    def test_done_requires_real_shaped_execution_receipt(self):
        matrix, dag = data()
        matrix["lanes"][0]["state"] = "DONE"
        with self.assertRaisesRegex(ValueError, "execution receipt"):
            M.project(matrix, dag, SHA)
        matrix["lanes"][0]["execution_receipt"] = {
            "head_sha": SHA, "run_id": 1, "attempt": 1,
            "result": "success", "test_population": 1, "digest": "f" * 64}
        p = M.project(matrix, dag, SHA)["matrix"]
        self.assertNotIn("P0_BASELINE_READER", [s["id"] for s in p["on"]])

    def test_five_pr_stack_cap_protects_main_from_new_write(self):
        matrix, dag = data()
        p = M.project(matrix, dag, SHA, open_stack=5)["matrix"]
        self.assertIn({"id": "P1_CACHE_PILOT", "reason": "PR_STACK_CAP",
                       "bundle": "B02", "devops_stage": "S2_BUILD",
                       "sipoc": M.dag_index(dag)[0]["B02"]["sipoc"]}, p["held"])

    def test_matching_goal_is_advisory_stop_never_merge(self):
        matrix, dag = data()
        result = M.project(matrix, dag, SHA, sample(0.19))
        self.assertEqual(result["goal"]["status"], "TARGET_REACHED_UNVERIFIED")
        self.assertEqual(result["goal"]["action"], "STOP_EXPERIMENT_FOR_INDEPENDENT_REVIEW")
        self.assertFalse(result["authority"]["merge_authorized"])

    def test_goal_not_reached_remains_recurrent_without_dispatch(self):
        matrix, dag = data()
        result = M.project(matrix, dag, SHA, sample(0.31))
        self.assertEqual(result["goal"]["status"], "TARGET_NOT_YET_REACHED")
        self.assertEqual(result["goal"]["action"], "CONTINUE_RF_WAVES")
        self.assertFalse(result["authority"]["dispatch_performed"])

    def test_stale_or_different_metric_cohort_fails_closed(self):
        matrix, dag = data()
        for changed in ({"source_sha": "b" * 40}, {"sample_n": 10}, {"value": float("nan")},
                        {"receipt_sha256": ""}, {"sample_method": "random_10"}, {"observed_at": "2020-01-01T00:00:00Z"}):
            with self.subTest(changed=changed):
                obs = dict(sample(), **changed)
                report = M.project(matrix, dag, SHA, obs)["goal"]
                self.assertEqual(report["status"], "UNKNOWN")

    def test_cli_writes_stable_json_with_explicit_no_authority(self):
        matrix, dag = data()
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "rf.json"
            code = M.main(["--source-sha", SHA, "--out", str(out)])
            self.assertEqual(code, 0)
            rep = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(rep["source_sha"], SHA)
            self.assertEqual(rep["authority"]["admission"], "HOLD")
            self.assertEqual(rep["goal"]["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
