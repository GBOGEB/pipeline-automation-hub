"""Adversarial and actual-path tests of bounded G9 read-only local scaling."""
from __future__ import annotations
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "method_atlas_scout_feasibility_under_test", HERE / "scout_feasibility.py")
scale = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scale)
ROOT = HERE.parents[2]


class PlannerTests(unittest.TestCase):
    def test_real_workload_has_fixed_positive_and_negative_classes(self):
        tasks, blocks = scale.plan(4, 32)
        self.assertEqual(len(tasks), 32)
        self.assertEqual(len(blocks), 4)
        for b in blocks:
            self.assertEqual(set(b["lanes"]), set(scale.LANES))
            self.assertEqual(len(set(b["task_ids"])), 32)
        self.assertEqual(sum(t["kind"] == "invalid" for t in tasks), 4)
        self.assertEqual(sum(t["kind"] == "counterfactual" for t in tasks), 4)
        self.assertEqual(sum(t["kind"] == "baseline" for t in tasks), 24)

    def test_balanced_sequence_reverses_order_in_the_middle(self):
        _, blocks = scale.plan(4, 32)
        self.assertLess(blocks[0]["lanes"].index("cold16"),
                        blocks[0]["lanes"].index("cold32"))
        self.assertGreater(blocks[1]["lanes"].index("cold16"),
                           blocks[1]["lanes"].index("cold32"))
        self.assertGreater(blocks[2]["lanes"].index("cold16"),
                           blocks[2]["lanes"].index("cold32"))
        self.assertLess(blocks[3]["lanes"].index("cold16"),
                        blocks[3]["lanes"].index("cold32"))

    def test_invalid_task_and_pulse_bounds_fail_closed(self):
        for n in (0, 1, 7, 9, 33, 64, True):
            with self.subTest(tasks=n), self.assertRaisesRegex(ValueError, "TASK_COUNT_OUT_OF_BOUNDS"):
                scale.tasks_for(n)
        for count in (-1, 0, 5, True):
            with self.subTest(pulses=count), self.assertRaisesRegex(ValueError, "PULSE_COUNT_OUT_OF_BOUNDS"):
                scale.plan(count, 8)

    def test_input_fixture_variants_are_not_leaked_or_mixed(self):
        data, sha = scale.load_inputs(ROOT)
        self.assertEqual(len(sha), 64)
        self.assertEqual(data["baseline"]["cohorts"][0]["returned_count"],
                         data["counterfactual"]["cohorts"][0]["returned_count"])
        self.assertEqual(data["invalid"]["cohorts"][0]["returned_count"],
                         data["baseline"]["cohorts"][0]["returned_count"]+1)
        all_base = [row for c in data["baseline"]["cohorts"] for row in c["runs"]]
        all_alt = [row for c in data["counterfactual"]["cohorts"] for row in c["runs"]]
        self.assertEqual(sum(r["conclusion"] == "success" for r in all_base),
                         sum(r["conclusion"] == "success" for r in all_alt)+1)

    def test_nearest_rank_p95_not_inferred_from_four_block_p95_values(self):
        self.assertEqual(scale.percentile_nearest([5, 1, 2, 4, 3], .95), 5)
        self.assertEqual(scale.percentile_nearest([5, 1, 2, 4, 3], .5), 3)
        with self.assertRaisesRegex(ValueError, "PERCENTILE_POPULATION_INVALID"):
            scale.percentile_nearest([], .95)


class OutputTruthTests(unittest.TestCase):
    def test_tampered_output_member_fails_even_if_manifest_is_stale(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td); out = tmp/"out";out.mkdir()
            for name in scale.MEMBERS:
                (out/name).write_bytes(b"{}")
            files = {name:scale.hash_bytes((out/name).read_bytes())
                     for name in scale.MEMBERS}
            (out/"manifest.json").write_bytes(scale.canon(
                {"source_sha":"a"*40,"merge_authorized":False,"files":files}))
            with self.assertRaisesRegex(ValueError, "G9_SEMANTIC_OUTCOME_MISMATCH"):
                scale.verify_output(out, "a"*40, "baseline")
            (out/"metrics.json").write_bytes(b'{"total_native_runs":57}')
            with self.assertRaisesRegex(ValueError,"G9_PRODUCT_HASH_MISMATCH"):
                scale.verify_output(out, "a"*40, "baseline")

    def test_missing_producer_member_and_wrong_source_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td);out.joinpath("manifest.json").write_text('{"source_sha": "x"}')
            with self.assertRaisesRegex(ValueError,"G9_MEMBER_SET_MISMATCH"):
                scale.verify_output(out,"a"*40,"baseline")
            for name in scale.MEMBERS:
                out.joinpath(name).write_text("{}")
            with self.assertRaisesRegex(ValueError,"G9_MANIFEST_SOURCE_OR_MEMBER_MISMATCH"):
                scale.verify_output(out,"a"*40,"baseline")

    def test_fan_in_order_does_not_change_identical_expected_outputs(self):
        a=[{"id":"T001","kind":"baseline","outcome":"VALID_VERIFIED",
            "output_digest":"a"*64},
           {"id":"T000","kind":"invalid","outcome":"REJECTED_EXPECTED",
            "output_digest":"EXPECTED_REJECTION"}]
        def cohort(mode,arr):
            return {"lane":mode,"task_receipts":arr,"negative_rejections":1}
        payload=[cohort(mode,copy.deepcopy(a)) for mode in scale.LANES]
        scale.compare_lanes(payload)
        payload[2]["task_receipts"].reverse()
        scale.compare_lanes(payload)
        payload[3]["task_receipts"][0]["output_digest"]="tampered"
        with self.assertRaisesRegex(ValueError,"CROSS_LANE_OUTCOME_PARITY_FAILURE"):
            scale.compare_lanes(payload)

    def test_missing_lane_or_negative_oracle_cannot_qualify(self):
        records=[{"lane":mode,"task_receipts":[{"id":"T000","kind":"invalid",
                   "outcome":"REJECTED_EXPECTED","output_digest":"EXPECTED_REJECTION"}],
                  "negative_rejections":1} for mode in list(scale.LANES)[:-1]]
        with self.assertRaisesRegex(ValueError,"MISSING_SCALE_LANE"):
            scale.compare_lanes(records)
        records.append({"lane":"warm16","task_receipts":copy.deepcopy(records[0]["task_receipts"]),
                        "negative_rejections":0})
        with self.assertRaisesRegex(ValueError,"NEGATIVE_CONTROL_COHORT_MISMATCH"):
            scale.compare_lanes(records)

    def test_rejected_invalid_cannot_have_output_or_success_status(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);bad=root/"bad.json";bad.write_text("{}")
            out=root/"out"
            tracker={"lock":__import__("threading").Lock(),"active":0,"peak":0}
            task={"id":"T000","kind":"invalid"}
            with mock.patch.object(scale.subprocess,"run",return_value=SimpleNamespace(
                    returncode=0,stderr=b"")):
                with self.assertRaisesRegex(ValueError,"INVALID_INPUT_NOT_REJECTED"):
                    scale.run_case(task,root,{"invalid":bad},{"invalid":{}},
                                   out,"a"*40,"SUBPROCESS_CLI",None,tracker)
            self.assertEqual(tracker["active"],0)
            with mock.patch.object(scale.subprocess,"run",return_value=SimpleNamespace(
                    returncode=1,stderr=scale.NEGATIVE.encode())):
                out.mkdir();out.joinpath("unexpected.txt").write_text("x")
                with self.assertRaisesRegex(ValueError,"INVALID_INPUT_PRODUCED_UNAUTHORIZED_OUTPUT"):
                    scale.run_case(task,root,{"invalid":bad},{"invalid":{}},
                                   out,"a"*40,"SUBPROCESS_CLI",None,tracker)

    def test_source_head_and_output_boundary_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            with self.assertRaisesRegex(ValueError,"SOURCE_HEAD_SHA_INVALID"):
                scale.exact_head(root,"not-a-hash")
            with self.assertRaisesRegex(ValueError,"OUTPUT_DIRECTORY_INSIDE_SOURCE_CHECKOUT"):
                scale.run(root,"a"*40,root/"tmp",1,8)

    def test_declared_governance_is_no_mutation_no_dispatch(self):
        self.assertEqual(scale.MAX_TASKS,32)
        self.assertEqual(scale.MAX_PULSES,4)
        self.assertEqual(scale.LANES["cold32"],(32,"SUBPROCESS_CLI"))
        self.assertEqual(scale.LANES["warm16"],(16,"IN_PROCESS_LIBRARY"))
        self.assertEqual(scale.SCHEMA,"method-atlas.g9-local-scale-feasibility.v1")


class ActualProductionSmoke(unittest.TestCase):
    def test_real_g9_two_backend_pilot_has_output_parity_and_negative_rejection(self):
        # Execute the real producer, not a mock: 8 tasks per mode, 1 block.
        sha = subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],
                                      text=True).strip()
        with tempfile.TemporaryDirectory() as td:
            result = scale.run(ROOT,sha,Path(td)/"smoke",pulses=1,task_count=8)
            self.assertEqual(result["workload"]["total_task_executions"],40)
            self.assertEqual(result["workload"]["negative_rejections_total"],5)
            self.assertEqual(len(result["blocks"][0]["cohorts"]),5)
            self.assertFalse(result["summary"]["causal_fleet_scale_proven"])
            self.assertFalse(result["safety"]["remote_github_dispatch_performed"])
            for row in result["blocks"][0]["cohorts"]:
                self.assertEqual(row["accepted_outputs"],7)
                self.assertEqual(row["negative_rejections"],1)
                self.assertGreater(row["wall_seconds"],0)
                self.assertLessEqual(row["observed_peak_local_tasks"],row["requested_workers"])
            manifest=json.loads((Path(td)/"smoke"/"manifest.json").read_text())
            for name,hash_ in manifest["files"].items():
                self.assertEqual(scale.hash_bytes((Path(td)/"smoke"/name).read_bytes()),hash_)


if __name__ == "__main__":
    unittest.main()
