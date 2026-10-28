"""W380 P2 bounded train: no fabricated native capacity or external ACK proof."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from metric_atlas import topic_wave_train as m

SEED=Path(__file__).with_name("pilot_6topic.json")


def sample():
    return json.loads(SEED.read_text(encoding="utf-8"))


def scenario():
    return m.synthetic_twin(sample())


class TrainTests(unittest.TestCase):
    def setUp(self):
        self.input=scenario()

    def bad(self,action,reason):
        d=copy.deepcopy(self.input)
        action(d)
        with self.assertRaisesRegex(ValueError,reason):
            m.plan(d)

    def test_twelve_declared_topic_ids_but_not_twelve_new_sources(self):
        r=m.plan(self.input)
        self.assertEqual(r["topics_unique_declared"],12)
        self.assertEqual(r["topic_evaluations"],12)
        self.assertEqual(r["distinct_source_fingerprints"],6)
        self.assertEqual(r["within_pulse_waves"],4)
        self.assertEqual(r["wave_barriers"],2)
        self.assertTrue(r["declared_goal_reached"])
        self.assertFalse(r["real_goal_verified"])
        self.assertEqual(r["mode"],"SYNTHETIC_REPEAT_TEST_ONLY")
        self.assertEqual(r["scale_admission"],"HOLD")

    def test_no_physical_execution_and_unknown_telemetry(self):
        r=m.plan(self.input)
        self.assertEqual(r["metrics"]["source_writers"],0)
        self.assertEqual(r["metrics"]["native_runners_launched"],0)
        self.assertEqual(r["metrics"]["new_cron_jobs_created"],0)
        self.assertEqual(r["metrics"]["formal_credit_delta"],0)
        for k in ("actual_reader_jobs","actual_queue_p95_seconds","actual_runner_minutes",
                  "verified_external_acks","saved_scan_minutes","accepted_root_closures"):
            self.assertIsNone(r["metrics"][k])

    def test_receipts_are_source_and_predecessor_bound(self):
        r=m.plan(self.input)
        self.assertIsNone(r["partitions"][0]["parent_sha256"])
        self.assertEqual(r["partitions"][1]["parent_sha256"],
                         r["partitions"][0]["receipt_sha256"])
        self.assertEqual(len(r["partitions"][0]["wave_receipts"]),2)
        self.assertEqual(r["pinned_graph_sha256"],r["partitions"][1]["source_graph_sha256"])

    def test_deterministic_and_digest_manifest(self):
        a=m.plan(self.input)
        self.assertEqual(a,m.plan(scenario()))
        with tempfile.TemporaryDirectory() as tmp:
            b=m.emit(self.input,tmp)
            self.assertEqual(b,a)
            q=Path(tmp)
            manifest=json.loads((q/"manifest.json").read_text())
            for path,digest in manifest["files_sha256"].items():
                self.assertEqual(hashlib.sha256((q/path).read_bytes()).hexdigest(),digest)
            self.assertEqual(len(manifest["files_sha256"]),3)
            self.assertIn("NEXT_PULSE",json.dumps(a["dag"]))

    def test_sipoc_has_five_columns_and_per_partition_provenance(self):
        r=m.plan(self.input)
        self.assertEqual(len(r["sipoc"]),2)
        for row in r["sipoc"]:
            self.assertTrue(set("SIPOC").issubset(row))
            self.assertTrue(row["I"]["p1_plan_sha256"])

    def test_same_pulse_dag_remains_acyclic(self):
        r=m.plan(self.input)
        self.assertTrue(r["dag"]["same_pulse_acyclic"])
        self.assertEqual(r["dag"]["temporal_feedback_edges"],1)
        self.assertEqual(sum(e["kind"]=="NEXT_PULSE" for e in r["dag"]["edges"]),1)
        self.assertEqual(len(r["dag"]["nodes"]),8)
        self.assertEqual(len(r["dag"]["edges"]),8)

    def test_goal_above_declared_capacity_stops_finitely(self):
        self.input["goal_unique_topic_ids"]=13
        r=m.plan(self.input)
        self.assertFalse(r["declared_goal_reached"])
        self.assertFalse(r["real_goal_verified"])
        self.assertEqual(r["stop_reason"],"DECLARED_PLAN_EXHAUSTED")
        self.assertEqual(r["wave_barriers"],2)

    def test_schema_and_mode_denied(self):
        self.bad(lambda x:x.update(schema="other"),"INVALID_TRAIN_MODE")
        self.bad(lambda x:x.update(mode="LIVE_APPROVED"),"INVALID_TRAIN_MODE")
        self.bad(lambda x:x.update(fake_authority=True),"INVALID_TRAIN_FIELDS")

    def test_truthful_authority_no_optimizations(self):
        self.bad(lambda x:x.update(authority_transfer=True),"AUTHORITY_ESCALATION")
        self.bad(lambda x:x.update(merge_admission="PASS"),"AUTHORITY_ESCALATION")

    def test_no_spurious_native_workers_or_source_writers(self):
        self.bad(lambda x:x.update(native_runners_launched=1),"UNPROVEN_PHYSICAL_EXECUTION")
        self.bad(lambda x:x.update(source_writers=1),"UNPROVEN_PHYSICAL_EXECUTION")
        self.bad(lambda x:x.update(native_runners_launched=True),"UNPROVEN_PHYSICAL_EXECUTION")

    def test_bounds(self):
        self.bad(lambda x:x.update(max_parallel_readers=3),"UNPROVEN_READER_CAPACITY")
        self.bad(lambda x:x.update(max_parallel_readers=1),"UNPROVEN_READER_CAPACITY")
        self.bad(lambda x:x.update(goal_unique_topic_ids=1000),"UNBOUNDED_GOAL")
        self.bad(lambda x:x.update(goal_unique_topic_ids=True),"UNBOUNDED_GOAL")
        self.bad(lambda x:x.update(partitions=[]),"UNBOUNDED_PARTITION_COUNT")
        self.bad(lambda x:x.update(partitions=x["partitions"]*3),"UNBOUNDED_PARTITION_COUNT")

    def test_no_cross_partition_topic_alias_collisions(self):
        def mutation(d):
            d["partitions"][1]["waves"][0]["packets"][0]=copy.deepcopy(
                d["partitions"][0]["waves"][0]["packets"][0])
        self.bad(mutation,"CROSS_PARTITION_TOPIC_COLLISION")

    def test_no_cross_partition_bd_identity_collision(self):
        def mutation(d):
            t=copy.deepcopy(d["partitions"][0]["bd_targets"][0])
            t["topic"]="w380."+t["topic"]
            d["partitions"][1]["bd_targets"].append(t)
        self.bad(mutation,"CROSS_PARTITION_TARGET_COLLISION")

    def test_graph_must_match_all_partitions(self):
        def mutation(d):
            for w in d["partitions"][1]["waves"]:
                w["nodes"][0]["function"]="rewritten-owner"
        self.bad(mutation,"CROSS_PARTITION_GRAPH_DRIFT")

    def test_inner_p1_reader_limit_is_not_bypassed(self):
        self.bad(lambda x:x["partitions"][1].update(max_parallel_readers=1),"INCONSISTENT_READER_CAP")

    def test_p1_source_digest_proof_is_still_required(self):
        self.bad(lambda x:x["partitions"][1]["waves"][0]["packets"][0]["packet"].update(
            source_sha256="a"*64),"PACKET_DIGEST_MISMATCH")

    def test_same_graph_more_than_one_source_scope_is_not_twelve_verified(self):
        r=m.plan(self.input)
        self.assertEqual(r["cohort"],"DECLARED_TOPICS_NOT_ACTUAL_SOURCE_COVERAGE")
        self.assertEqual(r["distinct_source_fingerprints"],6)
        self.assertEqual(r["stop_reason"],"MISSING_NATIVE_QUEUE_AND_CONTROLLER_ACK")

    def test_consecutive_p1_partitions_do_not_duplicate_issue_claims(self):
        self.assertEqual(len(self.input["partitions"][0]["bd_targets"]),5)
        self.assertEqual(len(self.input["partitions"][1]["bd_targets"]),0)
        self.assertTrue(all(p["pause_state"].startswith("RECONCILE_")
                            for p in m.plan(self.input)["partitions"]))


if __name__=="__main__":
    unittest.main()
