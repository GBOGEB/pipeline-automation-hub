"""Behavioral qualification of local admission, contracts, fairness and bounds."""
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest import mock


_spec = importlib.util.spec_from_file_location("atlas_local_broker_tested", Path(__file__).with_name("broker.py"))
broker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(broker)

NOW = "2026-10-19T14:00:00Z"
COHORT = {"repo": "example/hub", "source_sha": "a" * 40}


def task(key, needs=(), repo="example/hub", reads=(), writes=()):
    return {"id": key, "needs": list(needs), "repo": repo,
            "read_paths": list(reads), "write_paths": list(writes), "estimated_seconds": None,
            "input_contract": {}, "output_contract": {}}


def observation(**changes):
    result = dict(COHORT, observed_at="2026-10-19T13:59:30Z", complete_scope=True,
                  queued=7, running=1, worker_slots=4, reserved_capacity=1, regime="STABLE")
    result.update(changes)
    return result


class BrokerPlanTests(unittest.TestCase):
    def remote(self, snapshot, policy=None):
        return broker.plan([task("one")], snapshot,
                           {"cohort": COHORT} if policy is None else policy, now=NOW)["remote"]

    def test_unknown_never_becomes_zero_or_authorization(self):
        result = broker.plan([task("one")], now=NOW)
        self.assertEqual(result["remote"]["status"], "UNKNOWN")
        self.assertIsNone(result["remote"]["available_slots"])
        self.assertIsNone(result["remote"]["queued"])
        for field in ("dispatch_authorized", "merge_authorized", "authority_transfer"):
            self.assertIs(result[field], False)
        json.dumps(result, allow_nan=False)

    def test_snapshot_requires_fresh_complete_matching_cohort(self):
        cases = [
            ({}, "UNKNOWN"),
            (observation(observed_at="2026-10-19T14:00:01Z"), "UNKNOWN"),
            (observation(observed_at="2026-10-19T13:00:00Z"), "STALE"),
            (observation(complete_scope=False), "INCOMPLETE"),
            (observation(repo="example/other"), "COHORT_MISMATCH"),
            (observation(source_sha="b" * 40), "COHORT_MISMATCH"),
            (observation(worker_slots=None), "UNKNOWN"),
        ]
        for snapshot, status in cases:
            with self.subTest(status=status, snapshot=snapshot):
                result = self.remote(snapshot)
                self.assertEqual(result["status"], status)
                self.assertFalse(result["capacity_known"])
                self.assertIsNone(result["queued"])
                self.assertIsNone(result["available_slots"])
                self.assertEqual(result["advisory_dispatch_slots"], 0)
        self.assertEqual(self.remote(observation(), {})["status"], "UNQUALIFIED")

    def test_observation_preserves_controller_regime_without_promoting_it(self):
        for regime, expected_cap in (("CONGESTED", 0), ("RECOVERING", 1), ("STABLE", 2)):
            result = self.remote(observation(regime=regime))
            self.assertEqual(result["status"], "OBSERVED")
            self.assertEqual(result["available_slots"], 2)
            self.assertEqual(result["advisory_dispatch_slots"], expected_cap)
            self.assertEqual(result["regime"], regime)
            self.assertFalse(result["dispatch_authorized"])
        self.assertEqual(self.remote(observation(regime=None))["advisory_dispatch_slots"], 0)
        result = self.remote(observation(last_dispatch_at="2026-10-19T13:59:50Z"))
        self.assertEqual(result["cooldown_remaining_seconds"], 20)
        self.assertEqual(result["advisory_dispatch_slots"], 0)
        no_cooldown = self.remote(observation(last_dispatch_at="2026-10-19T13:59:00Z"))
        self.assertEqual(no_cooldown["advisory_dispatch_slots"], 2)

    def test_malformed_capacity_and_time_fail_closed(self):
        for field in ("queued", "running", "worker_slots", "reserved_capacity"):
            for value in (-1, True, 1.5, "3"):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    self.remote(observation(**{field: value}))
        for changes in ({"regime": "FAST"}, {"complete_scope": "yes"},
                        {"observed_at": "yesterday"}, {"observed_at": "2026-10-19T15:00:00+01:00"},
                        {"running": 4}, {"last_dispatch_at": "2026-10-19T14:00:01Z"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.remote(observation(**changes))
        with self.assertRaises(ValueError):
            self.remote([])

    def test_policy_cannot_grant_authority_or_hide_bad_bounds(self):
        policies = [[], {"schema": "other"}, {"max_workers": 0},
                    {"max_workers": 1}, {"max_pending": 1}, {"snapshot_max_age_seconds": -1},
                    {"advisory_caps": {"STABLE": 99}}, {"advisory_caps": dict.fromkeys(broker.REGIMES, -1)},
                    {"dispatch_authorized": True}, {"merge_authorized": True},
                    {"authority_transfer": True}, {"cohort": {}},
                    {"cohort": {"repo": "r", "source_sha": "a"}}]
        for policy in policies:
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                broker.plan([task("one")], policy=policy, now=NOW)

    def test_graph_and_contract_admission_happens_before_execution(self):
        invalid = [
            [task("a", ("absent",))],
            [task("a", ("b",)), task("b", ("a",))],
            [task("a"), task("a")],
            [task("a", ("a",))],
        ]
        for tasks in invalid:
            with self.subTest(tasks=tasks), self.assertRaises(ValueError):
                broker.plan(tasks, now=NOW)
        mutations = {"id": "", "repo": None, "needs": ["a", "a"],
                     "read_paths": "file", "write_paths": ["../escape"],
                     "estimated_seconds": float("nan"), "input_contract": [],
                     "output_contract": {"required_result_keys": [None]}}
        for field, value in mutations.items():
            row = task("one")
            row[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                broker.plan([row], now=NOW)
        for path in ("", "/absolute", "C:\\output", "x/*", "x/?", "x/[0]", "x\x00"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                broker.plan([task("one", writes=[path])], now=NOW)
        with self.assertRaises(ValueError):
            broker.plan([None], now=NOW)
        with self.assertRaises(ValueError):
            broker.plan({}, now=NOW)
        with self.assertRaises(ValueError):
            broker.plan([task("one"), task("two")], policy={"max_tasks": 1}, now=NOW)
        row = task("one")
        row["output_contract"] = {"constant": object()}
        with self.assertRaises(ValueError):
            broker.plan([row], now=NOW)

    def test_deterministic_topology_fairness_and_prefix_conflicts(self):
        tasks = [task("b", repo="second/repo"), task("a2", repo="first/repo"),
                 task("a1", repo="first/repo"), task("join", ("b", "a1", "a2"))]
        left = broker.plan(tasks, now=NOW)
        right = broker.plan(list(reversed(tasks)), now=NOW)
        self.assertEqual(left, right)
        self.assertEqual(left["initial_eligible_order"], ["a1", "b", "a2"])
        self.assertEqual(left["stages"], [["a1", "a2", "b"], ["join"]])
        cases = [(task("a", writes=["build/site"]), task("b", reads=["build/site/style.css"]), True),
                 (task("a", writes=["build/site"]), task("b", writes=["build/site/cards"]), True),
                 (task("a", writes=["build/site"]), task("b", writes=["build/sitemap"]), False),
                 (task("a", reads=["."]), task("b", writes=["build/site"]), True),
                 (task("a", reads=["build/site"]), task("b", reads=["build/site"]), False)]
        for a, b, expected in cases:
            with self.subTest(a=a, b=b):
                self.assertEqual(bool(broker.plan([a, b], now=NOW)["conflict_pairs"]), expected)
        normalized = broker.plan([task("a", writes=["build\\site"])], now=NOW)
        self.assertEqual(normalized["tasks"][0]["write_paths"], ["build/site"])
        self.assertEqual(broker.plan([], now=NOW)["stages"], [])


class BrokerRunTests(unittest.TestCase):
    def test_disjoint_handlers_actually_overlap_without_executor_flood(self):
        barrier = threading.Barrier(3)
        tasks = [task(str(n), writes=[f"build/{n}"]) for n in range(3)]

        def handler():
            barrier.wait(timeout=3)
            return {"ok": True}

        result = broker.run_local(tasks, {t["id"]: handler for t in tasks}, workers=3, max_pending=3)
        self.assertTrue(result["success"])
        self.assertEqual(result["metrics"]["max_running"], 3)
        self.assertLessEqual(result["metrics"]["peak_ready"], 3)
        self.assertEqual(result["metrics"]["ready_wait_sample_count"], 3)
        self.assertEqual(result["remote_capacity"], "UNKNOWN")
        json.dumps(result, allow_nan=False)

    def test_burst_is_bounded_and_deferral_does_not_drop_work(self):
        tasks = [task(f"job{n:03}") for n in range(40)]
        lock, seen = threading.Lock(), []

        def handler(key):
            def work():
                time.sleep(.002)
                with lock:
                    seen.append(key)
                return key
            return work

        result = broker.run_local(tasks, {t["id"]: handler(t["id"]) for t in tasks}, workers=4, max_pending=5)
        self.assertTrue(result["success"])
        self.assertEqual(sorted(seen), sorted(t["id"] for t in tasks))
        self.assertEqual(result["metrics"]["max_running"], 4)
        self.assertLessEqual(result["metrics"]["peak_ready"], 5)
        self.assertGreater(result["metrics"]["deferred_ready_count"], 0)
        self.assertGreater(result["metrics"]["peak_deferred_ready"], 0)
        self.assertEqual(result["metrics"]["ready_wait_sample_count"], 40)

    def test_small_ready_buffer_still_feeds_all_available_local_workers(self):
        barrier = threading.Barrier(3)
        tasks = [task(str(n)) for n in range(3)]

        def work():
            barrier.wait(timeout=3)

        result = broker.run_local(tasks, {row["id"]: work for row in tasks}, workers=3, max_pending=1)
        self.assertTrue(result["success"])
        self.assertEqual(result["metrics"]["max_running"], 3)
        self.assertEqual(result["metrics"]["peak_ready"], 1)

    def test_fairness_survives_a_single_pending_slot(self):
        tasks = [task(f"a{n}", repo="a/repo") for n in range(9)] + [task("b", repo="b/repo")]
        order = []
        result = broker.run_local(tasks, {t["id"]: lambda key=t["id"]: order.append(key) for t in tasks},
                                  workers=1, max_pending=1)
        self.assertTrue(result["success"])
        self.assertEqual(order[:2], ["a0", "b"])
        self.assertEqual(len(order), len(tasks))

    def test_conflicting_path_leases_serialize_and_readers_share(self):
        tasks = [task("writer", writes=["build/site"]), task("reader", reads=["build/site/cards"])]
        result = broker.run_local(tasks, {t["id"]: lambda: time.sleep(.003) for t in tasks})
        self.assertTrue(result["success"])
        self.assertEqual(result["metrics"]["max_running"], 1)
        barrier = threading.Barrier(2)
        readers = [task("a", reads=["shared"]), task("b", reads=["shared"])]

        def read():
            barrier.wait(timeout=3)

        result = broker.run_local(readers, {"a": read, "b": read})
        self.assertTrue(result["success"])
        self.assertEqual(result["metrics"]["max_running"], 2)

    def test_diamond_dependencies_wait_for_verified_outputs(self):
        tasks = [task("source"), task("slow", ("source",)), task("fast", ("source",)),
                 task("sink", ("slow", "fast"))]
        events = []

        def handler(key):
            def work():
                if key == "slow":
                    time.sleep(.008)
                events.append(key)
                return {"id": key}
            return work

        def verify(row, result):
            events.append("verify:" + row["id"])

        result = broker.run_local(tasks, {t["id"]: handler(t["id"]) for t in tasks}, output_validator=verify)
        self.assertTrue(result["success"])
        self.assertLess(events.index("verify:source"), events.index("fast"))
        self.assertLess(events.index("verify:slow"), events.index("sink"))
        self.assertLess(events.index("verify:fast"), events.index("sink"))
        self.assertEqual(result["tasks"]["source"]["ready_at_seconds"], 0.0)
        self.assertEqual(result["tasks"]["sink"]["ready_at_seconds"], max(
            result["tasks"]["slow"]["finished_at_seconds"], result["tasks"]["fast"]["finished_at_seconds"]))
        for row in result["tasks"].values():
            stamps = [row[k] for k in ("ready_at_seconds", "started_at_seconds", "execution_finished_at_seconds",
                                      "verify_started_at_seconds", "finished_at_seconds")]
            self.assertEqual(stamps, sorted(stamps))
            states = [e["state"] for e in row["events"]]
            self.assertLess(states.index("verifying"), states.index("succeeded"))
        waits = sorted(row["ready_wait_seconds"] for row in result["tasks"].values())
        self.assertEqual(result["metrics"]["ready_wait_p50_seconds"], waits[1])
        self.assertEqual(result["metrics"]["ready_wait_p95_seconds"], waits[-1])

    def test_failure_blocks_descendants_but_not_an_independent_lane(self):
        tasks = [task("a"), task("b", ("a",)), task("c", ("b",)), task("independent")]
        called = []

        def fail():
            raise RuntimeError("source first-red")

        handlers = {key: lambda key=key: called.append(key) for key in ("b", "c", "independent")}
        handlers["a"] = fail
        result = broker.run_local(tasks, handlers)
        self.assertFalse(result["success"])
        self.assertEqual(called, ["independent"])
        self.assertEqual(result["tasks"]["a"]["state"], "failed")
        self.assertEqual(result["tasks"]["a"]["error"]["phase"], "handler")
        self.assertEqual(result["tasks"]["b"]["state"], "blocked")
        self.assertEqual(result["tasks"]["c"]["state"], "blocked")
        self.assertEqual(result["metrics"]["blocked"], 2)
        self.assertEqual(result["metrics"]["ready_wait_sample_count"], 2)

    def test_input_paths_and_semantic_validator_prevent_handler_call(self):
        called = []
        row = task("a")
        row["input_contract"] = {"required_paths": ["missing"]}
        with tempfile.TemporaryDirectory() as root:
            result = broker.run_local([row], {"a": lambda: called.append("a")}, root=root)
            self.assertEqual(result["tasks"]["a"]["error"]["phase"], "input_contract")
        result = broker.run_local([task("a")], {"a": lambda: called.append("a")}, input_validator=lambda _: False)
        self.assertFalse(result["success"])
        self.assertEqual(called, [])

    def test_validator_cannot_mutate_and_relax_the_declared_output_contract(self):
        row = task("a", writes=["build/shared"])
        row["output_contract"] = {"required_result_keys": ["ok"]}

        def accidental_mutation(descriptor):
            descriptor["output_contract"]["required_result_keys"].clear()
            descriptor["write_paths"].clear()

        result = broker.run_local([row], {"a": lambda: {}}, input_validator=accidental_mutation)
        self.assertFalse(result["success"])
        self.assertEqual(result["tasks"]["a"]["error"]["phase"], "output_contract")
        self.assertEqual(row["output_contract"]["required_result_keys"], ["ok"])

    def test_last_failed_chain_drains_to_a_receipt_without_a_runnable_task(self):
        tasks = [task("a"), task("b", ["a"]), task("c", ["b"])]
        called = []

        def fail():
            raise RuntimeError("root failure")

        result = broker.run_local(tasks, {"a": fail, "b": lambda: called.append("b"),
                                          "c": lambda: called.append("c")})
        self.assertEqual(result["outcome"], "LOCAL_GENERATORS_FAIL")
        self.assertEqual(result["metrics"]["failed"], 1)
        self.assertEqual(result["metrics"]["blocked"], 2)
        self.assertEqual(called, [])

    def test_scheduler_fault_halts_instead_of_spinning_or_claiming_success(self):
        # Fault injection models a scheduler that loses its eligible selection.
        # A valid nonempty DAG must never be credited or silently abandoned.
        called = []
        with mock.patch.object(broker, "_fair_order", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "made no progress"):
                broker.run_local([task("a")], {"a": lambda: called.append("a")})
        self.assertEqual(called, [])

    def test_success_requires_real_output_contracts_and_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source.txt").write_text("source")
            row = task("a")
            row["input_contract"] = {"required_paths": ["source.txt"]}
            row["output_contract"] = {"required_paths": ["product.json"], "required_result_keys": ["ok"]}

            def good():
                (root / "product.json").write_text('{"ok":true}')
                return {"ok": True}

            self.assertTrue(broker.run_local([row], {"a": good}, root=root)["success"])
            (root / "product.json").unlink()
            result = broker.run_local([row], {"a": lambda: {"ok": True}}, root=root)
            self.assertEqual(result["tasks"]["a"]["error"]["phase"], "output_contract")
            row["output_contract"] = {"required_result_keys": ["ok"]}
            for output in ({}, None, 2):
                self.assertFalse(broker.run_local([row], {"a": lambda: output}, root=root)["success"])
        for output in (Path("not-json"), float("nan")):
            self.assertFalse(broker.run_local([task("a")], {"a": lambda: output})["success"])
        self.assertFalse(broker.run_local([task("a")], {"a": lambda: {}}, output_validator=lambda *_: False)["success"])

    def test_contract_symlink_cannot_escape_root(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "root"
            root.mkdir()
            outside = parent / "outside"
            outside.write_text("not input")
            try:
                (root / "link").symlink_to(outside)
            except OSError as exc:
                self.skipTest(str(exc))
            row = task("a")
            row["input_contract"] = {"required_paths": ["link"]}
            result = broker.run_local([row], {"a": lambda: {}}, root=root)
            self.assertFalse(result["success"])
            self.assertIn("escapes", result["tasks"]["a"]["error"]["message"])

    def test_invalid_execution_inputs_are_rejected_before_any_handler(self):
        called = []
        handlers = {"a": lambda: called.append("a")}
        cases = [({"workers": 0}), ({"workers": True}), ({"workers": 5}),
                 ({"max_pending": 0}), ({"max_pending": 33}),
                 ({"input_validator": 2}), ({"output_validator": 2})]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                broker.run_local([task("a")], handlers, **kwargs)
        with self.assertRaises(ValueError):
            broker.run_local([task("a")], {})
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                broker.run_local([task("a")], handlers, root=Path(directory) / "missing")
        self.assertEqual(called, [])

    def test_empty_manifest_is_an_empty_local_receipt(self):
        result = broker.run_local([], {})
        self.assertTrue(result["success"])
        self.assertEqual(result["metrics"]["ready_wait_sample_count"], 0)
        self.assertIsNone(result["metrics"]["ready_wait_p95_seconds"])
        self.assertEqual(result["metrics"]["max_running"], 0)


if __name__ == "__main__":
    unittest.main()
