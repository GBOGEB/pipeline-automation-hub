"""N3 Method Atlas warm broker: genuine two-producer DAG and adversarial checks."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
spec=importlib.util.spec_from_file_location("n3_warm_broker_under_test",HERE/"warm_broker_pilot.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class SourceAndDagContracts(unittest.TestCase):
    def test_only_two_explicit_real_producers_are_registered(self):
        self.assertEqual(m.ATLAS.as_posix(),"mission-control/federation-atlas/orchestration/main.py")
        self.assertEqual(m.G9.as_posix(),"mission-control/gogreen/outcome_convergence/outcome_flight.py")
        self.assertEqual(len(m.MODES),6)
        self.assertEqual(max(x[1] for x in m.MODES.values()),4)
        self.assertNotIn("remote",str(m.MODES).lower())

    def test_existing_broker_kahn_topology_and_unique_port_leases(self):
        broker=m.load_module("n3_test_broker",ROOT/m.BROKER)
        found,stages=broker._tasks(m.tasks(),broker.load_policy())
        self.assertEqual(stages,[["pin"],["g9","profile"],["join"]])
        self.assertEqual(len(found),4)
        self.assertEqual(len({x for t in found.values() for x in t["write_paths"]}),3)
        self.assertFalse(broker.conflicts(found["profile"],found["g9"]))
        self.assertEqual(set(found["join"]["needs"]),{"profile","g9"})

    def test_existing_broker_circular_dep_negative_contract(self):
        broker=m.load_module("n3_test_broker_cycle",ROOT/m.BROKER)
        bad=m.tasks()
        bad[0]["needs"]=["join"]
        with self.assertRaisesRegex(ValueError,"cycle"):
            broker._tasks(bad,broker.load_policy())

    def test_pilot_enforces_exact_head_and_no_source_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/m.ATLAS).parent.mkdir(parents=True)
            with self.assertRaisesRegex(ValueError,"SOURCE_HEAD_SHA_INVALID"):
                m.pin(root,"invalid")
            with self.assertRaisesRegex(ValueError,"OUTPUT_PATH_OVERLAPS_SOURCE"):
                m.run(ROOT,"a"*40,ROOT/"bad",pulses=1)

    def test_all_variants_have_same_source_populations(self):
        found=m.input_variants(ROOT)
        self.assertEqual(set(found),{"baseline","counterfactual","invalid_census","invalid_clock"})
        self.assertEqual(found["invalid_census"]["cohorts"][0]["returned_count"],
                         found["baseline"]["cohorts"][0]["returned_count"]+1)
        self.assertEqual(found["invalid_clock"]["cohorts"][0]["runs"][0]["run_started_at"],
                         "2026-10-15T00:00:00Z")
        original=[r for c in found["baseline"]["cohorts"] for r in c["runs"]]
        changed=[r for c in found["counterfactual"]["cohorts"] for r in c["runs"]]
        self.assertEqual(sum(r["conclusion"]=="failure" for r in changed),
                         sum(r["conclusion"]=="failure" for r in original)+1)

    def test_unsafe_pilot_bounds_and_duplicate_worker_mode_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/"out"
            for k in (0,5,True):
                with self.subTest(pulses=k),self.assertRaisesRegex(ValueError,"PILOT_BOUNDS_INVALID"):
                    m.run(ROOT,"a"*40,out,pulses=k)
            with self.assertRaisesRegex(ValueError,"PILOT_BOUNDS_INVALID"):
                m.run(ROOT,"a"*40,out,modes=["cold1","cold1"])
            with self.assertRaisesRegex(ValueError,"PILOT_BOUNDS_INVALID"):
                m.run(ROOT,"a"*40,out,modes=["cold5"])


class ProductAndFaultContracts(unittest.TestCase):
    def test_profile_source_identity_cannot_be_claimed_by_wrong_output(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/"source-check.json").write_text('{"status":"PASS"}')
            with self.assertRaisesRegex(ValueError,"SEMANTIC_OR_AUTHORITY_MISMATCH"):
                m.read_profile(p,"a"*40)
            (p/"surprise.json").write_text("{}")
            with self.assertRaisesRegex(ValueError,"METHOD_PROFILE_MEMBERS_INVALID"):
                m.read_profile(p,"a"*40)

    def test_incomplete_g9_manifest_and_bad_source_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            with self.assertRaisesRegex(ValueError,"G9_OUTPUT_MEMBER_SET_INVALID"):
                m.read_g9(p,"a"*40,"baseline")
            for name in m.G9_MEMBERS:
                (p/name).write_text("{}")
            (p/"manifest.json").write_text('{"source_sha":"b","files":{}}')
            with self.assertRaisesRegex(ValueError,"G9_SOURCE_HEAD_OR_AUTHORITY_INVALID"):
                m.read_g9(p,"a"*40,"baseline")

    def test_fault_after_production_must_block_fan_in_in_both_backends(self):
        head=subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip()
        variants=m.input_variants(ROOT)
        broker=m.load_module("n3_test_broker_fault",ROOT/m.BROKER)
        pool={"broker":broker,"atlas":m.load_module("n3_test_atlas_fault",ROOT/m.ATLAS),
              "g9":m.load_module("n3_test_g9_fault",ROOT/m.G9),"inputs":variants}
        with tempfile.TemporaryDirectory() as td:
            base=Path(td);files={}
            for name,obj in variants.items():
                f=base/(name+".json");f.write_bytes(m.canonical(obj));files[name]=f
            for mode in ("cold2","warm2"):
                with self.subTest(mode=mode):
                    row,receipt=m.trial(ROOT,head,base/mode,mode,"baseline",
                                        pool,files,injected=True)
                    self.assertEqual(row["state"]["g9"],"failed")
                    self.assertEqual(row["state"]["join"],"blocked")
                    self.assertEqual(row["error_phase"],"output_contract")
                    self.assertFalse(row["accepted_fan_in"])
                    self.assertEqual(receipt["metrics"]["blocked"],1)
                    self.assertFalse((base/mode/"join").exists())

    def test_legacy_existing_broker_ownership_not_extended(self):
        broker=m.load_module("n3_test_broker_policy",ROOT/m.BROKER)
        policy=broker.load_policy()
        self.assertEqual(policy["max_workers"],4)
        self.assertEqual(policy["default_workers"],2)
        self.assertIs(policy["dispatch_authorized"],False)
        self.assertIs(policy["merge_authorized"],False)
        self.assertIs(policy["authority_transfer"],False)

    def test_negative_source_error_mapping_uses_exact_existing_oracle(self):
        self.assertIn("first-page census",m.NEGATIVE_ERRORS["invalid_census"])
        self.assertIn("clock progression",m.NEGATIVE_ERRORS["invalid_clock"])
        self.assertEqual(set(m.EXPECTED),{"baseline","counterfactual"})

    def test_replay_template_population_prose_must_reflect_actual_broker(self):
        markup=("<style></style><header>"
                "Eight registered tasks, their dependency order and their generated products."
                "Receipt source identity, dependency completion before successors start, "
                "output contracts, exact producer-to-assembly bytes, and package member hashes.")
        updated=m.adapt_recorded_replay(markup,4)
        self.assertIn("4 registered local broker tasks",updated)
        self.assertNotIn("Eight registered tasks",updated)
        self.assertIn("ALL-join verification",updated)
        self.assertIn("min-width:590px",updated)
        with self.assertRaisesRegex(ValueError,"CANONICAL_REPLAY_TEMPLATE_ANCHOR_DRIFT"):
            m.adapt_recorded_replay(markup.replace("Eight registered tasks","Seven registered tasks"),4)
        with self.assertRaisesRegex(ValueError,"N3_REPLAY_COUNT_INVALID"):
            m.adapt_recorded_replay(markup,8)

    def test_summary_comparisons_are_descriptive_without_fake_independent_cis(self):
        rows=[]
        for mode in m.MODES:
            rows.append({"mode":mode,"variant":"baseline","injected":False,
                         "elapsed_seconds":.2,"ready_p95_seconds":.01})
            rows.append({"mode":mode,"variant":"invalid_census","injected":False,
                         "elapsed_seconds":.1,"ready_p95_seconds":.01})
        result=m.summary(rows,list(m.MODES))
        self.assertIsNone(result["ci"])
        self.assertEqual(result["independent_native_fleet_pulses"],0)
        self.assertEqual(result["cold_to_warm_speedup_by_worker_count"],
                         {"1":1,"2":1,"4":1})


class ActualMethodAtlasDAG(unittest.TestCase):
    def test_real_cold_and_warm_method_atlas_and_g9_with_negative_clock(self):
        head=subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip()
        with tempfile.TemporaryDirectory() as td:
            target=Path(td)/"real-pilot"
            report=m.run(ROOT,head,target,pulses=2,modes=("cold1","warm1"),tamper=False)
            self.assertEqual(report["plan"]["positive_dag_count"],4)
            self.assertEqual(report["plan"]["invalid_dag_count"],4)
            self.assertEqual(report["plan"]["tamper_dag_count"],0)
            self.assertEqual(len(report["rows"]),8)
            self.assertEqual(sum(r["accepted_fan_in"] for r in report["rows"]),4)
            self.assertEqual(set(r["variant"] for r in report["rows"]),
                             {"baseline","counterfactual","invalid_census","invalid_clock"})
            self.assertTrue(all(r["max_running"]<=r["workers"]<=4 for r in report["rows"]))
            self.assertFalse(report["safety"]["remote_dispatch"])
            self.assertFalse(report["safety"]["fleet_capacity_proven"])
            self.assertIn("cold_to_warm_speedup_by_worker_count",report["summary"])
            self.assertTrue((target/"runtime-replay.html").is_file())
            text=(target/"runtime-replay.html").read_text()
            self.assertIn('id="play"',text)
            self.assertIn('id="timeline"',text)
            self.assertIn("Recorded execution",text)
            self.assertIn("4 registered local broker tasks",text)
            self.assertNotIn("Eight registered tasks",text)
            self.assertIn("Swipe horizontally for all execution columns",text)
            self.assertEqual(set(json.loads((target/"manifest.json").read_text())["files_sha256"]),
                             {"n3_receipt.json","index.html","runtime-replay.html","n3_dag.mmd"})
            manifest=json.loads((target/"manifest.json").read_text())
            for name,sha in manifest["files_sha256"].items():
                self.assertEqual(m.digest((target/name).read_bytes()),sha)


if __name__=="__main__":
    unittest.main()
