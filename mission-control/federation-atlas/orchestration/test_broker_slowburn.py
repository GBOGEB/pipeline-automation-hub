"""Negative and boundary contracts for Mission Control slow-burn read-only planning."""
import importlib.util
import json
from pathlib import Path
import unittest

_spec = importlib.util.spec_from_file_location(
    "atlas_broker_slowburn_test", Path(__file__).with_name("broker.py")
)
broker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(broker)
NOW = "2026-10-26T15:40:00Z"
COHORT = {"repo": "sample/hub", "source_sha": "a" * 40}


def task(key, needs=(), writes=(), repo="sample/hub"):
    return {"id": key, "repo": repo, "needs": list(needs),
            "read_paths": [f"src/{key}"], "write_paths": list(writes),
            "estimated_seconds": None, "input_contract": {},
            "output_contract": {}}


def observed(**updates):
    value = dict(COHORT, observed_at="2026-10-26T15:39:30Z",
                 complete_scope=True, queued=5, running=1, worker_slots=4,
                 reserved_capacity=1, regime="STABLE")
    value.update(updates)
    return value


class SlowBurnTests(unittest.TestCase):
    def plan(self, tasks, snapshot=None, **params):
        return broker.plan_slow_burn(
            tasks, snapshot, {"cohort": COHORT}, now=NOW, **params
        )

    def test_eight_conditional_waves_are_not_eight_proven_runs(self):
        tasks = [task(f"s{i}", [f"s{i-1}"] if i else []) for i in range(8)]
        report = self.plan(tasks, max_waves=8)
        self.assertEqual(len(report["waves"]), 8)
        self.assertEqual(report["packet_count"], 8)
        self.assertEqual(report["waves"][0]["status"], "STAGED_NOT_LAUNCHED")
        self.assertTrue(all(w["status"] == "CONDITIONAL_PREDECESSOR_PROOF"
                            for w in report["waves"][1:]))
        self.assertEqual(report["launches"], 0)
        self.assertIsNone(report["verified_root_closures"])
        self.assertIsNone(report["matched_coverage_delta_pp"])

    def test_bounded_horizon_and_fair_diverse_scans(self):
        tasks = [task(f"a{i:02}", repo="sample/hub") for i in range(13)]
        tasks += [task(f"b{i:02}", repo="sample/other") for i in range(13)]
        report = self.plan(tasks, max_waves=8, max_per_wave=3)
        self.assertEqual(report["packet_count"], 24)
        self.assertLessEqual(max(len(w["task_ids"]) for w in report["waves"]), 3)
        self.assertEqual(len(report["held"]), 2)
        self.assertEqual({h["reason"] for h in report["held"]}, {"WAVE_BUDGET_EXHAUSTED"})

    def test_source_writes_hold_even_when_queue_is_empty(self):
        report = self.plan([task("write", writes=["mission-control"]),
                            task("read")], observed(queued=0))
        self.assertEqual(report["waves"][0]["task_ids"], ["read"])
        self.assertEqual(report["held"][0]["reason"],
                         "WRITE_REQUIRES_SOURCE_OWNER_AND_PATH_LEASE")
        self.assertFalse(report["dispatch_authorized"])
        self.assertFalse(report["merge_authorized"])
        self.assertFalse(report["authority_transfer"])

    def test_no_successor_if_source_predecessor_held(self):
        report = self.plan([task("writer", writes=["src"]),
                            task("dependent", needs=["writer"])])
        self.assertEqual(report["waves"], [])
        self.assertIn("DEPENDENCY_NOT_PROVEN",
                      {row["reason"] for row in report["held"]})

    def test_remote_evidence_unknown_or_stale_fails_closed(self):
        jobs = [task("a")]
        for snapshot in (None, observed(complete_scope=False),
                         observed(observed_at="2026-10-26T14:00:00Z"),
                         observed(source_sha="b" * 40),
                         observed(regime="CONGESTED"),
                         observed(queued=13),
                         observed(last_dispatch_at="2026-10-26T15:39:50Z")):
            with self.subTest(snapshot=snapshot):
                report = self.plan(jobs, snapshot)
                self.assertEqual(report["remote_advisory_slots"], 0)
                self.assertEqual(report["launches"], 0)

    def test_fresh_matching_observation_is_advice_not_dispatch(self):
        report = self.plan([task("a")], observed())
        self.assertEqual(report["remote_observation_status"], "OBSERVED")
        self.assertEqual(report["remote_advisory_slots"], 2)
        self.assertFalse(report["dispatch_authorized"])
        json.dumps(report, allow_nan=False)

    def test_invalid_bounds_and_dag_are_rejected(self):
        for param, value in (("max_waves", 0), ("max_waves", 13),
                             ("max_waves", True), ("max_per_wave", 0),
                             ("max_per_wave", 5), ("queue_limit", -1)):
            with self.subTest(param=param), self.assertRaises(ValueError):
                self.plan([task("a")], **{param: value})
        with self.assertRaises(ValueError):
            self.plan([task("a", needs=["b"])])

    def test_plans_are_deterministic_at_same_observation(self):
        tasks = [task(str(i)) for i in range(8)]
        a = self.plan(tasks, observed())
        b = self.plan(list(reversed(tasks)), observed())
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
