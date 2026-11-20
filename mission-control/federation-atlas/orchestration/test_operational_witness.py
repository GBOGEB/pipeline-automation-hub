"""Operational witness contracts; real producer is also run separately in native CI."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("method_atlas_witness_under_test",HERE/"operational_witness.py")
w=importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)


class Classification(unittest.TestCase):
    def test_test_and_historical_not_treated_as_live_executable(self):
        self.assertEqual(w.kind("archive/data.py"),"HISTORICAL_OR_GENERATED")
        self.assertEqual(w.kind("tests/test_oracle.py"),"TEST_SOURCE")
        self.assertEqual(w.kind(".github/workflows/real.yml"),"WORKFLOW_DECLARATION")
        self.assertEqual(w.kind("src/tool.ts"),"EXECUTABLE_CANDIDATE")
        self.assertEqual(w.kind("src/tool.js"),"EXECUTABLE_CANDIDATE")
        self.assertEqual(w.kind("src/rules.json"),"CONTRACT_OR_CONFIGURATION")
        self.assertEqual(w.kind("requirements.toml"),"CONTRACT_OR_CONFIGURATION")

    def test_coverage_is_not_inferred_from_file_presence(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            wf=root/".github/workflows"
            wf.mkdir(parents=True)
            (root/"tools").mkdir()
            (root/"web").mkdir()
            (root/"tools/live.py").write_text("print(1)\n")
            (root/"tools/loose.py").write_text("print(2)\n")
            (root/"web/main.js").write_text("console.log(1)\n")
            (root/"config.json").write_text("{}\n")
            (wf/"real.yml").write_text(
                "name: Example\non:\n  schedule:\n    - cron: '0 1 * * *'\n"
                "jobs:\n  run:\n    runs-on: ubuntu-latest\n    steps:\n"
                "      - run: |\n          python tools/live.py\n          node web/main.js\n"
            )
            class Owner:
                @staticmethod
                def source_files(x):
                    return ["tools/live.py","tools/loose.py","web/main.js",
                            "config.json",".github/workflows/real.yml"]
                @staticmethod
                def inventory(x):
                    return {"workflow_count":1,"workflow_jobs":1,"workflow_steps":1,
                            "workflows":[{"path":".github/workflows/real.yml","errors":[]}]}
            registry={"local_repo":"test/sample","peers":[{"repo":"test/sample","role":"LOCAL"},
                        {"repo":"test/remote","role":"PEER"}]}
            data=w.inventory(root,Owner,registry)
            self.assertEqual(data["direct_executable_targets"],2)
            self.assertEqual(data["not_directly_linked_executable_candidates"],1)
            self.assertIsNone(data["whole_pipeline_coverage_pct"])
            self.assertIsNone(data["python_branch_coverage_pct"])
            self.assertTrue(data["unlinked_is_not_zero_coverage"])
            self.assertEqual(data["peers"][1]["source_state"],"EXTERNAL_NOT_ACCESSED")
            self.assertEqual(data["watchers"][0]["liveness"],"UNOBSERVED")

    def test_unresolved_dynamic_cannot_be_marked_reachable(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/".github/workflows").mkdir(parents=True)
            (root/".github/workflows/dynamic.yml").write_text(
                "name: Dynamic\non: workflow_dispatch\njobs:\n  run:\n"
                "    steps:\n      - run: python src/$" + "{{ inputs.script }}\n"
            )
            class Owner:
                @staticmethod
                def source_files(x):return [".github/workflows/dynamic.yml"]
                @staticmethod
                def inventory(x):
                    return {"workflow_count":1,"workflow_jobs":1,"workflow_steps":1,
                            "workflows":[{"path":".github/workflows/dynamic.yml","errors":[]}]}
            data=w.inventory(root,Owner,{"local_repo":"local","peers":[]})
            self.assertGreater(data["unresolved_static_refs"],0)
            self.assertEqual(data["direct_executable_targets"],0)


class OutcomeAndAuthority(unittest.TestCase):
    def test_frozen_g9_population_contract(self):
        self.assertEqual(w.COUNTS,{"total_native_runs":57,
                                  "native_terminal_success":46,
                                  "native_terminal_failure":10,
                                  "native_terminal_cancelled":1})

    def test_output_member_hash_or_head_wrong_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td);(out/"metrics.json").write_text('{"total_native_runs":57}')
            m={"source_sha":"a"*40,"merge_authorized":False,
               "files":{"metrics.json":w.digest((out/"metrics.json").read_bytes())}}
            (out/"manifest.json").write_bytes(w.canonical(m))
            stats,seen=w.verify_artifacts(out,"a"*40)
            self.assertEqual(stats["total_native_runs"],57)
            (out/"metrics.json").write_text('{"total_native_runs":58}')
            with self.assertRaisesRegex(ValueError,"OUTPUT_HASH"):
                w.verify_artifacts(out,"a"*40)
            with self.assertRaisesRegex(ValueError,"BAD_PRODUCTION"):
                w.verify_artifacts(out,"b"*40)

    def test_invalid_head_and_output_path_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            with self.assertRaisesRegex(ValueError,"EXACT_SOURCE_HEAD"):
                w.source_head(root,"not-a-sha")
            with self.assertRaisesRegex(ValueError,"OUTPUT_MUST_BE_EMPTY"):
                w.main(["--root",str(root),"--head","a"*40,"--out",str(root/"out")])

    def test_g9_runtime_coverage_separate_from_unit_coverage(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"source";root.mkdir()
            slot=Path(td)/"actual-g9-runtime-coverage"
            with mock.patch.dict("os.environ",{"WITNESS_G9_COVERAGE_FILE":str(slot)}), \
                 mock.patch.object(w.subprocess,"run") as mocked:
                mocked.return_value.returncode=0
                w.execute(root,"a"*40,root/"fixture.json",Path(td)/"output")
                cmd=mocked.call_args.args[0]
                self.assertEqual(cmd[:5],[w.sys.executable,"-m","coverage","run","-a"])
                self.assertIn("--branch",cmd)
                self.assertIn("outcome_flight.py"," ".join(cmd))
                self.assertEqual(mocked.call_args.kwargs["env"]["COVERAGE_FILE"],str(slot))
            with mock.patch.dict("os.environ",{"WITNESS_G9_COVERAGE_FILE":str(root/"bad")}), \
                 self.assertRaisesRegex(ValueError,"COVERAGE_OUTPUT_INSIDE_CHECKOUT"):
                w.execute(root,"a"*40,root/"fixture.json",Path(td)/"output")

    def test_no_false_production_coverage_without_opt_in(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"source";root.mkdir()
            with mock.patch.dict("os.environ",{"WITNESS_G9_COVERAGE_FILE":""}), \
                 mock.patch.object(w.subprocess,"run") as mocked:
                w.execute(root,"a"*40,root/"fixture.json",Path(td)/"output")
                cmd=mocked.call_args.args[0]
                self.assertEqual(cmd[0],w.sys.executable)
                self.assertNotIn("coverage",cmd)
                self.assertIsNone(mocked.call_args.kwargs["env"])

    def test_source_and_owner_mismatch_are_fail_closed(self):
        from types import SimpleNamespace
        from unittest import mock
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            fake=SimpleNamespace(returncode=0,stdout="b"*40)
            with mock.patch.object(w.subprocess,"run",return_value=fake), \
                 self.assertRaisesRegex(ValueError,"CHECKOUT_HEAD_MISMATCH"):
                w.source_head(root,"a"*40)
            with mock.patch.object(w.importlib.util,"spec_from_file_location",return_value=None), \
                 self.assertRaisesRegex(ValueError,"METHOD_ATLAS_OWNER_MISSING"):
                w.existing_atlas()

    def test_malformed_workflow_source_kept_unknown_not_covered(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/".github/workflows").mkdir(parents=True)
            f=root/".github/workflows/malformed.yml"
            f.write_text(
                "name: Broken\non: workflow_dispatch\njobs:\n"
                "  invalid: []\n"
                "  live:\n    steps:\n      - 42\n"
            )
            class Owner:
                @staticmethod
                def source_files(x):return [".github/workflows/malformed.yml"]
                @staticmethod
                def inventory(x):
                    return {"workflow_count":2,"workflow_jobs":2,"workflow_steps":1,
                            "workflows":[{"path":"ignored.yml","errors":["BROKEN_AST"]},
                                         {"path":".github/workflows/malformed.yml",
                                          "errors":[]}]}
            data=w.inventory(root,Owner,{"local_repo":"local","peers":[]})
            self.assertGreaterEqual(data["unresolved_static_refs"],3)
            self.assertIsNone(data["whole_pipeline_coverage_pct"])

    def test_production_witness_rejects_all_eight_false_positive_modes(self):
        from types import SimpleNamespace
        from unittest import mock
        good=dict(w.COUNTS)
        delta=dict(good,native_terminal_success=45,native_terminal_failure=11)
        wrong=dict(good,native_terminal_success=47)
        # Failure modes deliberately target *real* witness decision branches.
        cases={
            "PRODUCTION_ENTRYPOINT_DID_NOT_RUN":([1],[],True),
            "G9_SOURCE_BOUND_57_RUN_DENOMINATOR_DRIFT":([0,0],[wrong,good],True),
            "PRODUCTION_OUTPUT_NOT_IDEMPOTENT":([0,0],[good,wrong],True),
            "MISSING_COUNTERFACTUAL_ROW":([0,0],[good,good],False),
            "CONTROLLED_VALID_INPUT_REJECTED":([0,0,1],[good,good],True),
            "NO_EXPECTED_INPUT_OUTPUT_SENSITIVITY":([0,0,0],[good,good,good],True),
            "INCOMPLETE_NATIVE_DENOMINATOR_FALSE_PASS":([0,0,0,0],[good,good,delta],True),
            "OUT_OF_ORDER_NATIVE_CLOCK_FALSE_PASS":([0,0,0,1,0],[good,good,delta],True),
        }
        for expected,(codes,outputs,has_success) in cases.items():
            with self.subTest(expected=expected),tempfile.TemporaryDirectory() as td:
                root=Path(td)
                source=root/w.SAMPLE
                source.parent.mkdir(parents=True)
                source.write_text(__import__('json').dumps({
                    "cohorts":[{"returned_count":1,"runs":[{
                        "conclusion":"success" if has_success else "failure",
                        "run_started_at":"2026-10-17T12:00:00Z"}]}]
                }))
                observed=[SimpleNamespace(returncode=x) for x in codes]
                received=[(v,{"files":{}}) for v in outputs]
                with mock.patch.object(w,"execute",side_effect=observed), \
                     mock.patch.object(w,"verify_artifacts",side_effect=received), \
                     self.assertRaisesRegex(ValueError,expected):
                    w.actual_outcome_witness(root,"a"*40)

    def test_registry_schema_mismatch_is_rejected_before_any_execution(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as td:
            base=Path(td);root=base/"repo";root.mkdir()
            fake=base/"registry.json"
            fake.write_text('{"schema":"wrong","peers":[]}')
            with mock.patch.object(w,"source_head",return_value="a"*40), \
                 mock.patch.object(w,"REGISTRY",fake), \
                 self.assertRaisesRegex(ValueError,"REGISTRY_SCHEMA_MISMATCH"):
                w.main(["--root",str(root),"--head","a"*40,
                        "--out",str(base/"output")])

    def test_no_new_metric_or_watcher_owner(self):
        reg=json.loads(w.REGISTRY.read_text())
        self.assertEqual(reg["schema"],"method-atlas.operational-surface-registry.v1")
        self.assertEqual(reg["owner"],"mission-control/federation-atlas/orchestration/main.py")
        self.assertEqual(reg["metric_owner"],"mission-control/federation-atlas/orchestration/coverage_contract.py")
        self.assertEqual(len(reg["peers"]),7)
        self.assertFalse(reg["release_authority"])
        self.assertFalse(reg["remote_dispatch_authorized"])
        self.assertFalse(reg["private_source_export_authorized"])
        self.assertEqual(len({(x["repo"],x["path"],x["role"]) for x in reg["surfaces"]}),
                         len(reg["surfaces"]))

    def test_review_page_escapes_untrusted_inputs(self):
        report={"head":"a"*40,"inventory":{"files":4,"workflows":1,
                "direct_link_count":2,"by_class":{"<script>alert(1)</script>":3},
                "peers":[{"repo":"<b>X</b>","role":"viewer",
                          "source_state":"EXTERNAL_NOT_ACCESSED"}]},
                "witness":{"baseline":dict(w.COUNTS)}}
        page=w.visual(report)
        self.assertNotIn("<script>alert(1)</script>",page)
        self.assertIn("&lt;script&gt;",page)
        self.assertNotIn("<b>X</b>",page)
        self.assertIn("Controlled",page)


if __name__=="__main__":
    unittest.main()
