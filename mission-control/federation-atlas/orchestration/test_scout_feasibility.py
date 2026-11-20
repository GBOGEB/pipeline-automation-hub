"""Adversarial and actual-path tests of bounded G9 read-only local scaling."""
from __future__ import annotations
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import textwrap
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
    def test_hash_consistent_wrong_population_with_same_totals_is_rejected(self):
        inputs, _ = scale.load_inputs(ROOT)
        wrong = copy.deepcopy(inputs["baseline"])
        wrong["cohorts"][0]["runs"][0]["head_sha"] = "b" * 40
        with scale.scratch_directory() as temp:
            out = temp / "wrong"
            producer = scale.producer_module(ROOT)
            producer.build(wrong, out, "a" * 40)
            with self.assertRaisesRegex(ValueError, "G9_SOURCE_VARIANT_MISMATCH"):
                scale.verify_output(out, "a" * 40, "baseline",
                                    scale.hash_bytes(scale.canon(inputs["baseline"])))

    def test_tampered_output_member_fails_even_if_manifest_is_stale(self):
        with scale.scratch_directory() as td:
            tmp = Path(td); out = tmp/"out";out.mkdir()
            for name in scale.MEMBERS:
                (out/name).write_bytes(b"{}")
            files = {name:scale.hash_bytes((out/name).read_bytes())
                     for name in scale.MEMBERS}
            (out/"manifest.json").write_bytes(scale.canon(
                {"source_sha":"a"*40,"merge_authorized":False,"files":files}))
            with self.assertRaisesRegex(ValueError, "G9_SEMANTIC_OUTCOME_MISMATCH"):
                scale.verify_output(out, "a"*40, "baseline", "b"*64)
            (out/"metrics.json").write_bytes(b'{"total_native_runs":57}')
            with self.assertRaisesRegex(ValueError,"G9_PRODUCT_HASH_MISMATCH"):
                scale.verify_output(out, "a"*40, "baseline", "b"*64)

    def test_missing_producer_member_and_wrong_source_rejected(self):
        with scale.scratch_directory() as td:
            out=Path(td);out.joinpath("manifest.json").write_text('{"source_sha": "x"}')
            with self.assertRaisesRegex(ValueError,"G9_MEMBER_SET_MISMATCH"):
                scale.verify_output(out,"a"*40,"baseline","b"*64)
            for name in scale.MEMBERS:
                out.joinpath(name).write_text("{}")
            with self.assertRaisesRegex(ValueError,"G9_MANIFEST_SOURCE_OR_MEMBER_MISMATCH"):
                scale.verify_output(out,"a"*40,"baseline","b"*64)

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
        with scale.scratch_directory() as td:
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
        with scale.scratch_directory() as td:
            root=Path(td)
            with self.assertRaisesRegex(ValueError,"SOURCE_HEAD_SHA_INVALID"):
                scale.exact_head(root,"not-a-hash")
            with self.assertRaisesRegex(ValueError,"OUTPUT_DIRECTORY_INSIDE_SOURCE_CHECKOUT"):
                scale.run(root,"a"*40,root/"tmp",1,8)

    def test_declared_governance_is_no_mutation_no_dispatch(self):
        self.assertEqual(scale.MAX_TASKS,32)
        self.assertEqual(scale.MAX_PULSES,4)
        self.assertEqual(scale.LANES["cold32"],(32,"SUBPROCESS_CLI"))
        self.assertEqual(scale.LANES["warm1"],(1,"IN_PROCESS_LIBRARY"))
        self.assertEqual(scale.LANES["warm4"],(4,"IN_PROCESS_LIBRARY"))
        self.assertEqual(scale.LANES["warm16"],(16,"IN_PROCESS_LIBRARY"))
        self.assertEqual(scale.SCHEMA,"method-atlas.g9-local-scale-feasibility.v1")


class ActualProductionSmoke(unittest.TestCase):
    def test_real_g9_two_backend_pilot_has_output_parity_and_negative_rejection(self):
        # Execute the real producer, not a mock: 8 tasks per mode, 1 block (7 modes).
        sha = subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],
                                      text=True).strip()
        with scale.scratch_directory() as td:
            result = scale.run(ROOT,sha,Path(td)/"smoke",pulses=1,task_count=8)
            self.assertEqual(result["workload"]["total_task_executions"],56)
            self.assertEqual(result["workload"]["negative_rejections_total"],7)
            self.assertEqual(len(result["blocks"][0]["cohorts"]),7)
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


class SourceAndFailureTests(unittest.TestCase):
    def test_raw_blob_pin_rejects_hidden_changes_and_clean_filter(self):
        for flag in ("--assume-unchanged", "--skip-worktree"):
            with self.subTest(flag=flag), scale.scratch_directory() as root:
                def git(*args):
                    return subprocess.check_output(["git", "-C", str(root), *args],
                                                   stderr=subprocess.PIPE, text=True).strip()
                git("init", "-q")
                git("config", "user.email", "fixture@example.invalid")
                git("config", "user.name", "Fixture")
                path = Path("source.py")
                (root / path).write_bytes(b"value = 1\n")
                git("add", ".")
                git("-c", "core.hooksPath=/dev/null", "commit", "-qm", "fixture")
                head = git("rev-parse", "HEAD")
                # A filter that hides appended executable lines, in a real repo.
                filt = root / ".git" / "firstline.py"
                filt.write_text("import sys\nsys.stdout.buffer.write(sys.stdin.buffer.readline())\n")
                git("config", "filter.firstline.clean", f'"{sys.executable}" "{filt}"')
                (root / ".git" / "info" / "attributes").write_text("source.py filter=firstline\n")
                git("update-index", flag, str(path))
                with mock.patch.object(scale, "SOURCE_FILES", (path,)):
                    self.assertEqual(scale.exact_head(root, head), head)
                    (root / path).write_bytes(b"value = 1\nvalue = 2\n")
                    self.assertEqual(git("status", "--porcelain", "--untracked-files=no"), "")
                    self.assertEqual(git("hash-object", "--path=source.py", "source.py"),
                                     git("rev-parse", "HEAD:source.py"))
                    with self.assertRaisesRegex(ValueError, "SOURCE_BYTES_NOT_IN_REQUESTED_HEAD"):
                        scale.exact_head(root, head)

    def test_raw_blob_pin_rejects_deleted_and_uncommitted_sources(self):
        with scale.scratch_directory() as root:
            with mock.patch.object(scale.subprocess, "run", side_effect=[
                    mock.Mock(returncode=0, stdout="a"*40),
                    mock.Mock(returncode=0, stdout=b"committed")]), \
                    mock.patch.object(scale, "SOURCE_FILES", (Path("missing"),)):
                with self.assertRaisesRegex(ValueError, "SOURCE_BYTES_NOT_IN_REQUESTED_HEAD"):
                    scale.exact_head(root, "a"*40)

    def test_warm_import_creates_no_bytecode_and_restores_setting_on_error(self):
        previous = sys.dont_write_bytecode
        with scale.scratch_directory() as root:
            path = root / "producer.py"
            for source in ("value = 1\n", "raise RuntimeError('import-failure')\n"):
                path.write_text(source)
                with mock.patch.object(scale, "G9", Path("producer.py")):
                    if source.startswith("raise"):
                        with self.assertRaisesRegex(RuntimeError, "import-failure"):
                            scale.producer_module(root)
                    else:
                        self.assertEqual(scale.producer_module(root).value, 1)
                self.assertEqual(sys.dont_write_bytecode, previous)
                self.assertFalse((root / "__pycache__").exists())

    def test_scratch_cleanup_on_failure(self):
        with self.assertRaisesRegex(RuntimeError, "first-red"):
            with scale.scratch_directory() as scratch:
                (scratch / "child-output").write_text("actual")
                raise RuntimeError("first-red")
        self.assertFalse(scratch.exists())

    def test_scratch_cleanup_includes_readonly_git_style_files(self):
        with scale.scratch_directory() as scratch:
            readonly = scratch / "readonly-object"
            readonly.write_bytes(b"git-style object")
            readonly.chmod(scale.stat.S_IREAD)
        self.assertFalse(scratch.exists())

    def test_cold_timeout_preserves_partial_streams_and_releases_task_counter(self):
        timeout = subprocess.TimeoutExpired("g9", 30, output=b"partial stdout", stderr=b"\xffpartial stderr")
        tracker = {"lock": scale.threading.Lock(), "active": 0, "peak": 0}
        with scale.scratch_directory() as tmp, \
                mock.patch.object(scale.subprocess, "run", side_effect=timeout), \
                self.assertRaises(subprocess.TimeoutExpired) as caught:
            scale.run_case({"id":"T001", "kind":"baseline"}, ROOT,
                           {"baseline":tmp/"baseline.json"}, {}, tmp/"out",
                           "a"*40, "SUBPROCESS_CLI", None, tracker)
        self.assertIs(caught.exception, timeout)
        self.assertEqual(caught.exception.stderr, b"\xffpartial stderr")
        self.assertEqual(tracker["active"], 0)

    def test_failure_preserves_prior_blocks_all_completed_tasks_and_actual_outputs(self):
        original = scale.run_case
        for failure in (ValueError("G9_SEMANTIC_OUTCOME_MISMATCH"),
                        subprocess.TimeoutExpired("g9", 30, output=b"partial stdout", stderr=b"\xffpartial stderr")):
            with self.subTest(failure=type(failure).__name__), scale.scratch_directory() as tmp:
                out = tmp / "evidence"
                def injected(task, root, files, objects, product, *args):
                    if product.parent.name == "pulse2-warm16" and task["id"] == "T001":
                        product.mkdir(parents=True)
                        (product / "failed-output.txt").write_text("diagnostic bytes")
                        raise failure
                    return original(task, root, files, objects, product, *args)
                with mock.patch.object(scale, "exact_head", return_value="a"*40), \
                        mock.patch.object(scale, "run_case", side_effect=injected), \
                        self.assertRaisesRegex(ValueError, "G9_LANE_FAILED"):
                    scale.run(ROOT, "a"*40, out, pulses=2, task_count=8)
                report = json.loads((out / "failure.json").read_bytes())
                self.assertEqual(len(report["completed_blocks"]), 1)
                self.assertEqual(report["current_pulse"], 2)
                self.assertEqual(report["current_lane"], "warm16")
                partial = out / "failure-outputs" / "pulse2-warm16"
                receipt = json.loads((partial / "partial_receipts.json").read_bytes())
                self.assertEqual(len(receipt["task_receipts"]), 7)
                self.assertEqual(receipt["failures"][0]["task_id"], "T001")
                if isinstance(failure, subprocess.TimeoutExpired):
                    streams = receipt["failures"][0]["partial_streams_base64"]
                    self.assertEqual(scale.base64.b64decode(streams["stdout"]), b"partial stdout")
                    self.assertEqual(scale.base64.b64decode(streams["stderr"]), b"\xffpartial stderr")
                self.assertEqual((partial / "T001" / "failed-output.txt").read_text(),
                                 "diagnostic bytes")
                self.assertFalse((out / "scale_feasibility.json").exists())
                manifest = json.loads((out / "manifest.json").read_bytes())
                self.assertEqual(manifest["status"], "FAIL")
                self.assertEqual(set(manifest["files"]),
                    {p.relative_to(out).as_posix() for p in out.rglob("*")
                     if p.is_file() and p != out / "manifest.json"})
                for name, digest in manifest["files"].items():
                    self.assertEqual(scale.hash_bytes((out / name).read_bytes()), digest)

    def test_workflow_seals_hold_and_test_log_without_rehashing_tampered_members(self):
        workflow = (ROOT / ".github/workflows/method-atlas-g9-scout-feasibility.yml").read_text()
        script = textwrap.dedent(workflow.split("          import hashlib,json,os,shutil\n")[1]
                                 .split("          PY\n")[0])
        script = "import hashlib,json,os,shutil\n" + script
        with scale.scratch_directory() as tmp:
            out = tmp / "g9-local-scale"
            out.mkdir()
            (out / "index.html").write_text("verified report")
            scale.write_manifest(out, "a" * 40, "b" * 64, "PASS")
            (out / "native_gate_hold.json").write_text('{"classification":"HOLD_NO_MATCHED_NATIVE_OBSERVATIONS"}')
            (tmp / "g9-scale-tests.log").write_text("test log")
            with mock.patch.dict(scale.os.environ, {"RUNNER_TEMP": str(tmp)}):
                exec(script, {})
                manifest = json.loads((out / "manifest.json").read_bytes())
                self.assertEqual(set(manifest["files"]),
                                 {"index.html", "native_gate_hold.json", "g9-scale-tests.log"})
                for name, digest in manifest["files"].items():
                    self.assertEqual(scale.hash_bytes((out / name).read_bytes()), digest)
                (out / "index.html").write_text("tampered after validation")
                with self.assertRaisesRegex(SystemExit, "SCALE_MEMBER_HASH_TAMPER_BEFORE_FINAL_SEAL"):
                    exec(script, {})
        # A pre-benchmark test failure still has a sealed FAIL artifact and log.
        with scale.scratch_directory() as tmp:
            (tmp / "g9-scale-tests.log").write_text("FAILED before benchmark")
            with mock.patch.dict(scale.os.environ, {"RUNNER_TEMP": str(tmp), "EXACT_HEAD": "a"*40}):
                exec(script, {})
            manifest = json.loads((tmp / "g9-local-scale" / "manifest.json").read_bytes())
            self.assertEqual(manifest["status"], "FAIL")
            self.assertEqual(manifest["source_head"], "a"*40)
            self.assertEqual(set(manifest["files"]), {"g9-scale-tests.log"})

    def test_workflow_filters_cover_all_runtime_source_dependencies(self):
        workflow = (ROOT / ".github/workflows/method-atlas-g9-scout-feasibility.yml").read_text()
        paths = workflow.split("    paths:\n", 1)[1].split("  workflow_dispatch:", 1)[0]
        for source in scale.SOURCE_FILES:
            self.assertIn("'" + source.as_posix() + "'", paths)


if __name__ == "__main__":
    unittest.main()
