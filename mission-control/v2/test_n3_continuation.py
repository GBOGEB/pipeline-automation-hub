"""Positive and adversarial tests for bounded N+3 receipts."""
import copy
import importlib.util
import sys
import unittest
from pathlib import Path

MODULE = Path(__file__).with_name("n3_continuation.py")
spec = importlib.util.spec_from_file_location("n3_continuation", MODULE)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)

A = "a" * 40
B = "b" * 40
C = "c" * 40
D = "d" * 40


def ledger():
    return {"schema": "missioncontrol.n3_continuation.v1", "mode": "N3-AUTO",
            "operation": "3P-CONT", "authority_transfer": False,
            "mission": {"id": "CBD-604", "repo": "GBOGEB/pipeline-automation-hub",
                        "wave": "W-CBD-GRAPH", "start_sha": A},
            "start_ordinal": 7,
            "policy": {"max_pulses": 3, "security_waiver": False,
                       "merge_without_review": False, "unbounded_dispatch": False,
                       "allowed_paths": ["mission-control/v2"]}, "receipts": []}


def receipt(ledger_obj, new_sha=B, status="SOURCE_COMMITTED", blocker=None):
    state = m.validate(ledger_obj)
    number = state["next_ordinal"]
    assert number is not None
    return {"ordinal": number,
            "pulse_id": f"GBOGEB/pipeline-automation-hub::CBD-604::W-CBD-GRAPH::PULSE-{number}",
            "input_source_sha": state["latest_source_sha"],
            "output_source_sha": state["latest_source_sha"] if blocker else new_sha,
            "prev_receipt_digest": state["last_receipt_digest"],
            "status": status, "changed_paths": [] if blocker else ["mission-control/v2/README.md"],
            "tests": {"kind": "NOT_RUN", "passed": 0, "failed": 0},
            "coverage_delta": None, "major_blocker": blocker,
            "merge_admission": "HOLD", "security_waiver": False,
            "authority_transfer": False}


class ContinuationTests(unittest.TestCase):
    def setUp(self):
        self.l = ledger()

    def bad(self, edit):
        before = copy.deepcopy(self.l)
        edit(self.l)
        with self.assertRaises(ValueError):
            m.validate(self.l)
        self.l = before

    def test_initial_state(self):
        x = m.validate(self.l)
        self.assertEqual((x["next_ordinal"], x["target_ordinal"]), (8, 10))

    def test_three_successful_pulses(self):
        for sha in (B, C, D):
            self.l, out = m.record(self.l, receipt(self.l, sha))
        self.assertEqual(out["disposition"], "THREE_PULSES_RECORDED_NON_ADMITTED")
        self.assertEqual(out["completed_receipts"], 3)
        self.assertIsNone(out["next_ordinal"])

    def test_fourth_pulse_rejected(self):
        for sha in (B, C, D):
            self.l, _ = m.record(self.l, receipt(self.l, sha))
        with self.assertRaises(ValueError):
            m.record(self.l, {"ordinal": 11})

    def test_stop_on_major_blocker(self):
        r = receipt(self.l, status="BLOCKED", blocker="OWNER_LEASE_CONFLICT")
        self.l, state = m.record(self.l, r)
        self.assertEqual(state["disposition"], "STOP_MAJOR_BLOCKER")
        self.assertIsNone(state["next_ordinal"])

    def test_no_pulse_after_blocker(self):
        self.l, _ = m.record(self.l, receipt(self.l, status="BLOCKED", blocker="BRANCH_DRIFT"))
        self.l["receipts"].append(copy.deepcopy(self.l["receipts"][0]))
        with self.assertRaises(ValueError):
            m.validate(self.l)

    def test_bad_mode_3w(self):
        self.bad(lambda x: x.__setitem__("mode", "3W"))

    def test_unbounded_dispatch(self):
        self.bad(lambda x: x["policy"].__setitem__("unbounded_dispatch", True))

    def test_merge_without_review(self):
        self.bad(lambda x: x["policy"].__setitem__("merge_without_review", True))

    def test_security_waiver(self):
        self.bad(lambda x: x["policy"].__setitem__("security_waiver", True))

    def test_boolean_ordinal_rejected(self):
        self.bad(lambda x: x.__setitem__("start_ordinal", True))

    def test_bad_sha_rejected(self):
        self.bad(lambda x: x["mission"].__setitem__("start_sha", "main"))

    def test_parent_path_escape(self):
        self.bad(lambda x: x["policy"].__setitem__("allowed_paths", ["../contracts"]))

    def test_absolute_path(self):
        self.bad(lambda x: x["policy"].__setitem__("allowed_paths", ["/tmp"] ))

    def test_skip_ordinal(self):
        r = receipt(self.l)
        r["ordinal"] = 11
        self.l["receipts"].append(r)
        with self.assertRaises(ValueError):
            m.validate(self.l)

    def test_broken_hash_chain(self):
        r = receipt(self.l)
        r["prev_receipt_digest"] = "f" * 64
        self.l["receipts"].append(r)
        with self.assertRaises(ValueError):
            m.validate(self.l)

    def test_unleased_source_change(self):
        r = receipt(self.l)
        r["changed_paths"] = [".github/workflows/workflow.yml"]
        self.l["receipts"].append(r)
        with self.assertRaises(ValueError):
            m.validate(self.l)

    def test_unmatched_coverage(self):
        r = receipt(self.l)
        r["coverage_delta"] = 12.5
        self.l["receipts"].append(r)
        with self.assertRaises(ValueError):
            m.validate(self.l)

    def test_forged_native_exact_head(self):
        r = receipt(self.l)
        r["tests"] = {"kind": "NATIVE_EXACT_HEAD", "passed": 10,
                      "failed": 0, "tested_sha": "c" * 40}
        self.l["receipts"].append(r)
        with self.assertRaises(ValueError):
            m.validate(self.l)

    def test_forged_merge_admission(self):
        r = receipt(self.l)
        r["merge_admission"] = "PASS"
        self.l["receipts"].append(r)
        with self.assertRaises(ValueError):
            m.validate(self.l)

    def test_blocked_pulse_cannot_claim_changes(self):
        r = receipt(self.l, status="BLOCKED", blocker="P0_P1_SECURITY")
        r["changed_paths"] = ["mission-control/v2/README.md"]
        self.l["receipts"].append(r)
        with self.assertRaises(ValueError):
            m.validate(self.l)

    def test_valid_local_test_count(self):
        r = receipt(self.l)
        r["tests"] = {"kind": "LOCAL", "passed": 24, "failed": 0}
        self.l, state = m.record(self.l, r)
        self.assertEqual(state["next_ordinal"], 9)

    def test_invalid_boolean_test_count(self):
        r = receipt(self.l)
        r["tests"]["passed"] = True
        self.l["receipts"].append(r)
        with self.assertRaises(ValueError):
            m.validate(self.l)

    def test_bad_blocker_label(self):
        r = receipt(self.l, status="BLOCKED", blocker="UNCLASSIFIED")
        self.l["receipts"].append(r)
        with self.assertRaises(ValueError):
            m.validate(self.l)

    def test_wrong_source_replay(self):
        self.l, _ = m.record(self.l, receipt(self.l))
        r = receipt(self.l, C)
        r["input_source_sha"] = A
        self.l["receipts"].append(r)
        with self.assertRaises(ValueError):
            m.validate(self.l)


if __name__ == "__main__":
    unittest.main()
