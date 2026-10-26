"""N+6 deterministic aggressive queue governor adversarial regression."""
import copy
import importlib.util
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("n6_slow_burn", HERE / "slow_burn.py")
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def sample():
    sha = "a" * 40
    def lane(name, repo, path, *, prio="P1", red=1, zero=2):
        return dict(
            id=name, repo=repo, head_sha=sha, paths=[path], role="ENGINEER",
            priority=prio, state="READY", first_red=red,
            zero_covered_files=zero, budget_minutes=20,
            merge_authorized=False, coverage=dict(source_sha=sha, covered=10, eligible=20)
        )
    return dict(schema=mod.SCHEMA, execution="BRANCH_ONLY_NO_MERGE",
                authority_transfer=False, observed_utc="2026-10-26T16:00:00Z",
                queue=dict(queued=10, running=5, queued_limit=40, running_limit=10),
                lanes=[
                    lane("a-high", "GBOGEB/ABACUS", "tools/coverage/**",
                         prio="P0", red=6, zero=40),
                    lane("b-overlap", "GBOGEB/ABACUS", "tools/coverage/same.py",
                         prio="P1"),
                    lane("c-codex", "GBOGEB/CODEX", "pca_engine/**", prio="P1"),
                    lane("d-cryoplant", "GBOGEB/cryoplant-project", "tests/**",
                         prio="P2"),
                    lane("e-gg-math", "GBOGEB/gg_MATH", "kernels/**", prio="P3")
                ])


class SlowBurnTests(unittest.TestCase):
    def reject(self, mutate, expected):
        data = sample()
        mutate(data)
        with self.assertRaisesRegex(ValueError, expected):
            mod.make_plan(data)

    def test_top_two_disjoint_sources_selected_without_run_credit(self):
        x = mod.make_plan(sample())
        self.assertEqual([s["id"] for s in x["slots"]], ["a-high", "c-codex"])
        self.assertEqual(x["terminal_native_run_receipts"], 0)
        self.assertEqual(x["worker_runs_started"], 0)
        self.assertEqual(x["admission"], "HOLD")
        self.assertFalse(x["merge_authorized"])
        self.assertEqual(x["horizon_target"], "N+6")
        self.assertEqual(x["measured_coverage_delta"], None)

    def test_lease_overlap_excluded(self):
        x = mod.make_plan(sample(), max_slots=3)
        self.assertIn(dict(id="b-overlap", reason="SOURCE_PATH_LEASE_CONFLICT"),
                      x["deferred"])

    def test_empty_queue_still_bounded(self):
        d = sample()
        d["queue"]["queued"] = 0
        d["queue"]["running"] = 0
        self.assertEqual(len(mod.make_plan(d)["slots"]), 2)

    def test_queue_queued_backpressure(self):
        d = sample()
        d["queue"]["queued"] = 40
        x = mod.make_plan(d)
        self.assertEqual(x["queue_admission"], "DEFER")
        self.assertEqual(x["proposed_slots"], 0)
        self.assertTrue(all(y["reason"] == "DEFER_QUEUE_PRESSURE"
                            for y in x["deferred"]))

    def test_runner_capacity_backpressure(self):
        d = sample()
        d["queue"]["running"] = 10
        self.assertEqual(mod.make_plan(d)["proposed_slots"], 0)

    def test_no_overbooking_near_capacity(self):
        d = sample()
        d["queue"]["running"] = 9
        self.assertEqual(mod.make_plan(d, max_slots=3)["proposed_slots"], 1)

    def test_waiting_lane_not_dispatched(self):
        d = sample()
        d["lanes"][0]["state"] = "WAITING"
        p = mod.make_plan(d)
        self.assertIn(dict(id="a-high", reason="WAITING_FOR_DEPENDENCY"),
                      p["deferred"])

    def test_exact_job_lease_conflict(self):
        self.assertTrue(mod.collides("tests/a.py", "tests/a.py"))
        self.assertTrue(mod.collides("tests/**", "tests/a.py"))
        self.assertTrue(mod.collides("tests/a.py", "tests/**"))
        self.assertFalse(mod.collides("tests/a.py", "tests/b.py"))
        self.assertFalse(mod.collides("tests/a/**", "tests/b/**"))

    def test_deterministic_tickets_replay(self):
        x = mod.make_plan(sample())
        self.assertEqual(x, mod.make_plan(copy.deepcopy(sample())))
        self.assertEqual(len(x["slots"][0]["ticket"]), 20)

    def test_false_merge_authorization_rejected(self):
        self.reject(lambda d: d["lanes"][0].update(merge_authorized=True),
                    "cannot authorize merge")

    def test_authority_transfer_rejected(self):
        self.reject(lambda d: d.update(authority_transfer=True), "authority transfer")

    def test_wrong_schema_rejected(self):
        self.reject(lambda d: d.update(schema="v2"), "schema")

    def test_forged_source_sha_rejected(self):
        self.reject(lambda d: d["lanes"][0].update(head_sha="bad"), "source SHA")

    def test_coverage_source_sha_mismatch(self):
        self.reject(lambda d: d["lanes"][0]["coverage"].update(source_sha="b" * 40),
                    "coverage population")

    def test_zero_denominator_not_coverage(self):
        self.reject(lambda d: d["lanes"][0]["coverage"].update(eligible=0),
                    "coverage population")

    def test_bool_burden_rejected(self):
        self.reject(lambda d: d["lanes"][0].update(zero_covered_files=True),
                    "burden counts")

    def test_path_escape_rejected(self):
        self.reject(lambda d: d["lanes"][0].update(paths=["../secrets"]),
                    "path leases")

    def test_path_backslash_rejected(self):
        self.reject(lambda d: d["lanes"][0].update(paths=["src\\secret.py"]),
                    "path leases")

    def test_duplicate_lane_identity_rejected(self):
        self.reject(lambda d: d["lanes"][1].update(id="a-high"), "lane id")

    def test_unknown_crew_role_rejected(self):
        self.reject(lambda d: d["lanes"][0].update(role="GOD_MODE"), "CREW")

    def test_unbounded_budget_rejected(self):
        self.reject(lambda d: d["lanes"][0].update(budget_minutes=60), "budget")

    def test_malformed_queue_rejected(self):
        self.reject(lambda d: d["queue"].update(queued=False), "queue count")

    def test_capacity_cannot_be_invented(self):
        with self.assertRaisesRegex(ValueError, "concurrent"):
            mod.make_plan(sample(), max_slots=9)

    def test_horizon_is_bounded(self):
        with self.assertRaisesRegex(ValueError, "horizon"):
            mod.make_plan(sample(), horizon=99)

    def test_tampered_calendar_rejected(self):
        self.reject(lambda d: d.update(observed_utc="whenever"), "UTC")

    def test_unknown_repository_rejected(self):
        self.reject(lambda d: d["lanes"][0].update(repo="GBOGEB/unknown"),
                    "repository")

    def test_sparse_intake_valid_with_no_coverage_claim(self):
        d = sample()
        d["lanes"][0]["coverage"] = None
        self.assertIsNone(mod.make_plan(d)["measured_coverage_delta"])


if __name__ == "__main__":
    unittest.main()
