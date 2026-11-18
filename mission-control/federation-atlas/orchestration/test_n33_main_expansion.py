"""N3.3 exact-source, arc-identity and fail-closed oracle tests (no remote work)."""
from __future__ import annotations
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("n33_under_test",HERE/"n33_main_expansion.py")
n=importlib.util.module_from_spec(spec)
spec.loader.exec_module(n)
ROOT=HERE.parents[2]
HEAD="a"*40


def fake_coverage(arcs,eligible=276):
    return {"meta":{"version":"7.13.3","branch_coverage":True},
            "files":{"/repo/"+n.MAIN:{"summary":{
                "num_branches":eligible,"covered_branches":len(arcs),
                "num_statements":500},"executed_branches":[list(x) for x in arcs]}}}


class SourceAndArcContract(unittest.TestCase):
    def test_exact_original_main_blob_is_pinned(self):
        self.assertEqual(n.BASELINE_BLOB,"41f04e8719981be6564cf6de33f365d83c7a2264")
        self.assertEqual((n.BASELINE_BRANCHES,n.BASELINE_ELIGIBLE),(27,276))
        self.assertEqual(n.EXPECTED_TASKS,{"validate","method","control","superstitch",
                                        "convergence","orchestration","assemble","portal"})
        self.assertEqual(n.git(ROOT,"hash-object",n.MAIN),n.BASELINE_BLOB)

    def test_branch_arcs_are_identities_not_just_summary_percentages(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"c.json"
            p.write_text(json.dumps(fake_coverage([(1,2),(2,3)])))
            measured,arcs=n.arcs(p)
            self.assertEqual(measured["covered"],2)
            self.assertEqual(arcs,{(1,2),(2,3)})

    def test_native_relative_main_path_is_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"native.json"
            obj=fake_coverage([(1,2)])
            # Coverage may use a repository-relative key; preserve it.
            obj["files"]={n.MAIN:next(iter(obj["files"].values()))}
            p.write_text(json.dumps(obj))
            measured, found=n.arcs(p)
            self.assertEqual(measured["file"],n.MAIN)
            self.assertEqual(found,{(1,2)})

    def test_native_absolute_main_path_preserves_source_key(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"absolute.json"
            p.write_text(json.dumps(fake_coverage([(1,2)])))
            measured, found=n.arcs(p)
            self.assertEqual(measured["file"],"/repo/"+n.MAIN)
            self.assertEqual(found,{(1,2)})

    def test_zero_or_multiple_main_population_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"ambiguous.json"
            obj=fake_coverage([(1,2)])
            obj["files"]={"/repo/other.py":next(iter(obj["files"].values()))}
            p.write_text(json.dumps(obj))
            with self.assertRaisesRegex(ValueError,"MAIN_SOURCE_ARC_POPULATION_NOT_UNIQUE"):
                n.arcs(p)
            item=next(iter(obj["files"].values()))
            obj["files"]={n.MAIN:item,"/repo/"+n.MAIN:copy.deepcopy(item)}
            p.write_text(json.dumps(obj))
            with self.assertRaisesRegex(ValueError,"MAIN_SOURCE_ARC_POPULATION_NOT_UNIQUE"):
                n.arcs(p)

    def test_missing_arc_identity_rejected_even_if_green_percentage_claimed(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"c.json"
            bogus=fake_coverage([(1,2)])
            bogus["files"]["/repo/"+n.MAIN]["summary"]["covered_branches"]=5
            p.write_text(json.dumps(bogus))
            with self.assertRaisesRegex(ValueError,"ARC_IDENTITY_DENOMINATOR_MISMATCH"):
                n.arcs(p)

    def test_denominator_must_match_source_locked_276(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"c.json"
            p.write_text(json.dumps(fake_coverage([(1,2)],275)))
            with self.assertRaisesRegex(ValueError,"ELIGIBLE_DENOMINATOR_CHANGED"):
                n.arcs(p)

    def test_27_arc_baseline_preserved_and_new_arcs_counted(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            baseline={(i,i+1) for i in range(27)}
            for name,arcs in [("baseline",baseline),
                               ("plan",baseline|{(100,101)}),
                               ("build",baseline|{(101,102)})]:
                (root/(name+".json")).write_text(json.dumps(fake_coverage(arcs)))
            report=n.compare_coverage(root/"baseline.json",{
                  "plan":root/"plan.json","build":root/"build.json"})
            self.assertEqual(report["union_covered"],29)
            self.assertEqual(report["newly_reached"],2)
            self.assertEqual(report["previously_covered_preserved"],27)
            self.assertIsNone(report["whole_repository_coverage"])

    def test_false_green_new_arcs_without_old_arcs_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            baseline={(i,i+1) for i in range(27)}
            (root/"old.json").write_text(json.dumps(fake_coverage(baseline)))
            (root/"new.json").write_text(json.dumps(fake_coverage({(200,201)})))
            with self.assertRaisesRegex(ValueError,"PREVIOUS_RUNTIME_ARCS_NOT_REACHED"):
                n.compare_coverage(root/"old.json",{"plan":root/"new.json"})

    def test_plan_does_not_fake_source_head_embedded_in_native_broker(self):
        original=[{"id":t,"needs":[]} for t in sorted(n.EXPECTED_TASKS)]
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"broker-plan.json"
            obj={"schema":"atlas.local-broker.plan.v1",
                 "generated_at":None,
                 "time_basis":"DETERMINISTIC_SOURCE_PLAN_NO_RUNTIME_OBSERVATION",
                 "dispatch_authorized":False,"merge_authorized":False,"tasks":original}
            p.write_text(json.dumps(obj))
            report=n.plan_proof(p,HEAD)
            self.assertEqual(report["tasks"],8)
            self.assertEqual(report["declared_edges"],0)
            self.assertNotIn("source_sha",obj)
            obj["dispatch_authorized"]=True
            p.write_text(json.dumps(obj))
            with self.assertRaisesRegex(ValueError,"PLAN_SCHEMA_OR_AUTHORITY_INVALID"):
                n.plan_proof(p,HEAD)

    def test_output_and_worker_bounds_and_positive_outcomes_are_noncompensating(self):
        api=n.producer(ROOT,n.MAIN,"n33_owner_test")
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)
            result={"schema":"atlas.local-broker.receipt.v1","source_sha":HEAD,
                    "source_changed_during_run":False,"source_dirty":False,
                    "success":True,"outcome":"LOCAL_GENERATORS_PASS",
                    "tasks":{},"metrics":{"max_running":5,"ready_wait_sample_count":0},
                    "bounds":{"workers":4}}
            (out/"local-run.json").write_text(json.dumps(result))
            with self.assertRaisesRegex(ValueError,"LOCAL_DAG_INCOMPLETE_OR_RED"):
                n.run_proof(out,ROOT,HEAD,4,api)

    def test_no_false_roundtrip_fleet_or_owner_authority(self):
        self.assertEqual(n.SCHEMA,"method-atlas.n33.main-execution-coverage.v1")
        self.assertEqual(n.MAX_SECONDS["run4"],540)
        self.assertEqual(len(n.CHECKS),6)
        for workers in (1,2,4):
            self.assertIn("run"+str(workers),n.MAX_SECONDS)


if __name__=="__main__":
    unittest.main()
