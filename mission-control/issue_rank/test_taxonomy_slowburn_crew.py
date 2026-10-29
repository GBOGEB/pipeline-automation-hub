"""CREW N+8 to N+12 slow-burn budget, queue and role negative tests."""
from __future__ import annotations
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace
import taxonomy_slowburn_crew as crew

SHA="a"*40


def ok(cmd,wd,timeout):
    return SimpleNamespace(returncode=0,stdout="Ran 24 tests\nOK",stderr="")


def red(cmd,wd,timeout):
    return SimpleNamespace(returncode=1,stdout="Ran 24 tests",stderr="FAIL: first red")


def controls():
    return ["REX-001","REX-002","REX-005","REX-006"]


def invoke(lane="grammar",waves=8,queue=3,runner=ok,**kwargs):
    return crew.run(lane=lane,head=SHA,waves=waves,queue_depth=queue,
                    runner=runner,sleep=lambda s:None,rex_check=controls,**kwargs)


class Crew(unittest.TestCase):
    def test_twelve_waves_can_advance_without_extra_git_jobs(self):
        r=invoke(waves=12)
        self.assertEqual(r["waves_executed"],12)
        self.assertEqual(r["status"],"PASS_ALL_BOUNDED_WAVES")
        self.assertEqual([x["wave"] for x in r["test_invocations"]],list(range(1,13)))
        self.assertEqual(sum(x["executed_steps"] for x in r["test_invocations"]),12)
        self.assertFalse(r["main_mutation"])
        self.assertEqual(r["formal_credit_delta"],0)

    def test_slow_burn_four_disjoint_task_families(self):
        for lane in crew.LANES:
            with self.subTest(lane=lane):
                r=invoke(lane=lane,waves=2)
                self.assertEqual(r["lane"],lane)
                self.assertTrue(r["crew_role"])
                self.assertEqual(r["waves_executed"],2)

    def test_first_red_stop_before_next_wave(self):
        calls=[]
        def fail_second(cmd,wd,timeout):
            calls.append(len(calls)+1)
            return ok(cmd,wd,timeout) if len(calls)==1 else red(cmd,wd,timeout)
        r=invoke(waves=12,runner=fail_second)
        self.assertEqual(calls,[1,2])
        self.assertEqual(r["status"],"FIRST_RED_STOP")
        self.assertEqual(r["waves_executed"],2)
        self.assertEqual(r["test_invocations"][-1]["exit_code"],1)
        self.assertNotIn("FAIL: first red",json.dumps(r))

    def test_backpressure_holds_without_any_execution(self):
        def forbidden(*args):
            raise AssertionError("should not start subprocess under queue pressure")
        r=invoke(queue=21,runner=forbidden)
        self.assertEqual(r["status"],"BACKPRESSURE_HOLD_NO_TEST_PROOF")
        self.assertEqual(r["waves_executed"],0)
        self.assertFalse(r["terminal_native_proof"])
        self.assertEqual(len(r["test_invocations"]),0)

    def test_no_proof_receipt_cannot_exit_ci_green(self):
        # On merged #972, all four matrix jobs returned SUCCESS while
        # their receipts recorded BACKPRESSURE_HOLD with ZERO waves.
        sample=invoke(queue=21,waves=12)
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/"receipt.json"
            with patch.object(crew,"run",return_value=sample):
                rc=crew.main(["--lane","grammar","--head",SHA,
                              "--waves","12","--queue-depth","21",
                              "--out",str(dest)])
            self.assertNotEqual(rc,0)
            receipt=json.loads(dest.read_text())
            self.assertEqual(receipt["waves_executed"],0)
            self.assertFalse(receipt["terminal_native_proof"])

    def test_true_native_proof_can_exit_zero(self):
        sample=invoke(waves=2,queue=1)
        self.assertTrue(sample["terminal_native_proof"])
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/"receipt.json"
            with patch.object(crew,"run",return_value=sample):
                rc=crew.main(["--lane","grammar","--head",SHA,
                              "--waves","2","--queue-depth","1",
                              "--out",str(dest)])
            self.assertEqual(rc,0)
            self.assertEqual(json.loads(dest.read_text())["waves_executed"],2)

    def test_budget_stop_cannot_be_green(self):
        # Mock an exhausted elapsed clock without running a subprocess.
        times=iter([0.0,31.0])
        r=crew.run(lane="grammar",head=SHA,waves=2,queue_depth=1,
                   budget_seconds=30,clock=lambda:next(times),
                   rex_check=controls,sleep=lambda _:None)
        self.assertEqual(r["status"],"BUDGET_EXHAUSTED_HOLD")
        self.assertFalse(r["terminal_native_proof"])

    def test_budget_and_max_wave_bounded(self):
        for bad in (0,-1,13,100):
            with self.subTest(waves=bad),self.assertRaisesRegex(ValueError,"WAVES_OUT_OF_BOUND"):
                invoke(waves=bad)
        with self.assertRaisesRegex(ValueError,"BUDGET_OUT_OF_RANGE"):
            invoke(budget_seconds=1200)

    def test_invalid_head_queue_and_role_fail_closed(self):
        with self.assertRaisesRegex(ValueError,"EXACT_HEAD"):
            crew.run(lane="grammar",head="abc",waves=1,queue_depth=1,
                     rex_check=controls)
        with self.assertRaisesRegex(ValueError,"QUEUE_DEPTH"):
            invoke(queue=-1)
        with self.assertRaisesRegex(ValueError,"CREW_LANE_UNKNOWN"):
            invoke(lane="unauthorized")

    def test_real_registered_rex_controls_not_optional(self):
        actual=crew.rex_preflight()
        self.assertTrue(set(controls()).issubset(set(actual)))
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/"bad.json"
            f.write_text(json.dumps({"schema":"missioncontrol.crew.rex_learning_ledger.v1",
                                     "entries":[{"rex_id":"REX-001"}]}))
            with self.assertRaisesRegex(ValueError,"REX_CONTROLS_MISSING"):
                crew.rex_preflight(f)

    def test_repeat_is_deterministic_with_fake_runner(self):
        a=invoke(waves=2,gap_seconds=0)
        b=invoke(waves=2,gap_seconds=0)
        a.pop("receipt_sha256")
        b.pop("receipt_sha256")
        # Timing fields are observational; exact receipts can differ in duration.
        for entry in a["test_invocations"]:
            entry.pop("elapsed_seconds")
        for entry in b["test_invocations"]:
            entry.pop("elapsed_seconds")
        self.assertEqual(a,b)


if __name__=="__main__":
    unittest.main()
