import copy
import json
import unittest
from pathlib import Path

import golden_thread as gt
import temporal_checkpoint as tc

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "COLD_TAIL_BOOTSTRAP_LEDGER_v1.json"


def raw_event(event_id, event_type, subject_ref, payload=None):
    return {
        "event_id": event_id,
        "event_type": event_type,
        "occurred_at": "2026-09-17T01:30:00Z",
        "recorded_at": "2026-09-17T01:30:00Z",
        "actor": "MissionControl.Test",
        "subject_ref": subject_ref,
        "authority_domain": "GBOGEB/child",
        "evidence_class": "TEST_FIXTURE",
        "evidence_refs": [],
        "non_compensating_preserved": True,
        "payload": payload or {},
    }


def sealed(events):
    return gt.seal(
        {
            "schema": gt.LEDGER_SCHEMA,
            "projection_schema_version": 1,
            "authority_transfer": False,
            "events": events,
        }
    )


class TemporalGoldenThreadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cold_tail = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_control_only_checkpoint_advances_e_not_k(self):
        checkpoint = tc.checkpoint_payload(
            self.cold_tail,
            base_semantic_generation_k=0,
            ssot_digest=None,
            git_repo="GBOGEB/pipeline-automation-hub",
            git_commit_sha="a" * 40,
            milestone="GT-M0-COLDTAIL",
        )
        self.assertEqual(checkpoint["semantic_generation_k"], 0)
        self.assertEqual(checkpoint["event_sequence_e"], 14)
        self.assertFalse(checkpoint["engineering_ssot_changed"])
        self.assertIsNone(checkpoint["ssot_digest"])
        self.assertEqual(
            checkpoint["thread_digest"], self.cold_tail["head_event_digest"]
        )

    def test_same_ledger_rebuilds_same_checkpoint_digest(self):
        kwargs = dict(
            base_semantic_generation_k=3,
            ssot_digest="sha256:" + "0" * 64,
            git_repo="GBOGEB/pipeline-automation-hub",
            git_commit_sha="b" * 40,
            milestone="W253",
        )
        a = tc.checkpoint_payload(self.cold_tail, **kwargs)
        b = tc.checkpoint_payload(self.cold_tail, **kwargs)
        self.assertEqual(a, b)
        self.assertEqual(a["checkpoint_digest"], b["checkpoint_digest"])
        receipt = tc.verify_checkpoint(self.cold_tail, a)
        self.assertEqual(receipt["status"], "PASS")

    def test_authoritative_accept_advances_k_once(self):
        ledger = sealed(
            [
                raw_event(
                    "T-0001",
                    "WORK_ORDER_CREATED",
                    "WO-1",
                    {
                        "child_injection": {
                            "injection_key": "INJ-1",
                            "child_repo": "GBOGEB/child",
                            "source_digest": "sha256:" + "1" * 64,
                            "idempotency_key": "sha256:" + "2" * 64,
                        }
                    },
                ),
                raw_event(
                    "T-0002",
                    "STATE_CHANGED",
                    "WO-1",
                    {
                        "state": "DONE",
                        "child_disposition": {
                            "injection_key": "INJ-1",
                            "disposition": "ACCEPT",
                            "child_receipt_ref": "GBOGEB/child#receipt-1",
                            "authoritative_delta_applied": True,
                            "accepted_authoritative_delta_digest": "sha256:"
                            + "3" * 64,
                        },
                    },
                ),
            ]
        )
        checkpoint = tc.checkpoint_payload(
            ledger,
            base_semantic_generation_k=7,
            ssot_digest="sha256:" + "4" * 64,
            git_repo="GBOGEB/pipeline-automation-hub",
            git_commit_sha="c" * 40,
        )
        self.assertEqual(checkpoint["semantic_generation_k"], 8)
        self.assertEqual(checkpoint["event_sequence_e"], 2)
        self.assertTrue(checkpoint["engineering_ssot_changed"])
        self.assertEqual(
            checkpoint["child_transaction_summary"][
                "accepted_authoritative_delta_count"
            ],
            1,
        )

    def test_authoritative_accept_requires_result_ssot_digest(self):
        ledger = sealed(
            [
                raw_event(
                    "T-0001",
                    "WORK_ORDER_CREATED",
                    "WO-1",
                    {
                        "child_injection": {
                            "injection_key": "INJ-1",
                            "child_repo": "GBOGEB/child",
                            "source_digest": "sha256:" + "1" * 64,
                            "idempotency_key": "sha256:" + "2" * 64,
                        }
                    },
                ),
                raw_event(
                    "T-0002",
                    "STATE_CHANGED",
                    "WO-1",
                    {
                        "state": "DONE",
                        "child_disposition": {
                            "injection_key": "INJ-1",
                            "disposition": "ACCEPT",
                            "child_receipt_ref": "receipt",
                            "authoritative_delta_applied": True,
                            "accepted_authoritative_delta_digest": "sha256:"
                            + "3" * 64,
                        },
                    },
                ),
            ]
        )
        with self.assertRaises(tc.TemporalGoldenThreadError):
            tc.checkpoint_payload(
                ledger,
                base_semantic_generation_k=0,
                ssot_digest=None,
                git_repo="GBOGEB/pipeline-automation-hub",
                git_commit_sha="d" * 40,
            )

    def test_reject_and_defer_do_not_advance_k(self):
        ledger = sealed(
            [
                raw_event(
                    "T-0001",
                    "WORK_ORDER_CREATED",
                    "WO-R",
                    {
                        "child_injection": {
                            "injection_key": "INJ-R",
                            "child_repo": "GBOGEB/child",
                            "source_digest": "sha256:" + "1" * 64,
                            "idempotency_key": "sha256:" + "2" * 64,
                        }
                    },
                ),
                raw_event(
                    "T-0002",
                    "STATE_CHANGED",
                    "WO-R",
                    {
                        "state": "REJECTED",
                        "child_disposition": {
                            "injection_key": "INJ-R",
                            "disposition": "REJECT",
                            "rejection_reason": "fails child authority contract",
                        },
                    },
                ),
                raw_event(
                    "T-0003",
                    "WORK_ORDER_CREATED",
                    "WO-D",
                    {
                        "child_injection": {
                            "injection_key": "INJ-D",
                            "child_repo": "GBOGEB/child",
                            "source_digest": "sha256:" + "5" * 64,
                            "idempotency_key": "sha256:" + "6" * 64,
                        }
                    },
                ),
                raw_event(
                    "T-0004",
                    "STATE_CHANGED",
                    "WO-D",
                    {
                        "state": "DEFERRED",
                        "child_disposition": {
                            "injection_key": "INJ-D",
                            "disposition": "DEFER",
                            "owner": "GBOGEB/child",
                            "reentry_trigger": "exact child runtime receipt exists",
                        },
                    },
                ),
            ]
        )
        checkpoint = tc.checkpoint_payload(
            ledger,
            base_semantic_generation_k=11,
            ssot_digest="sha256:" + "7" * 64,
            git_repo="GBOGEB/pipeline-automation-hub",
            git_commit_sha="e" * 40,
        )
        self.assertEqual(checkpoint["semantic_generation_k"], 11)
        self.assertEqual(checkpoint["event_sequence_e"], 4)
        self.assertFalse(checkpoint["engineering_ssot_changed"])
        summary = checkpoint["child_transaction_summary"]
        self.assertEqual(summary["rejected_count"], 1)
        self.assertEqual(summary["deferred_count"], 1)

    def test_duplicate_idempotency_key_fails_closed(self):
        ledger = sealed(
            [
                raw_event(
                    "T-0001",
                    "WORK_ORDER_CREATED",
                    "WO-1",
                    {
                        "child_injection": {
                            "injection_key": "INJ-1",
                            "child_repo": "GBOGEB/child",
                            "source_digest": "sha256:" + "1" * 64,
                            "idempotency_key": "sha256:" + "9" * 64,
                        }
                    },
                ),
                raw_event(
                    "T-0002",
                    "WORK_ORDER_CREATED",
                    "WO-2",
                    {
                        "child_injection": {
                            "injection_key": "INJ-2",
                            "child_repo": "GBOGEB/child",
                            "source_digest": "sha256:" + "2" * 64,
                            "idempotency_key": "sha256:" + "9" * 64,
                        }
                    },
                ),
            ]
        )
        with self.assertRaises(tc.TemporalGoldenThreadError):
            tc.scan_child_transactions(ledger)

    def test_defer_without_reentry_trigger_fails_closed(self):
        ledger = sealed(
            [
                raw_event(
                    "T-0001",
                    "WORK_ORDER_CREATED",
                    "WO-1",
                    {
                        "child_injection": {
                            "injection_key": "INJ-1",
                            "child_repo": "GBOGEB/child",
                            "source_digest": "sha256:" + "1" * 64,
                            "idempotency_key": "sha256:" + "2" * 64,
                        }
                    },
                ),
                raw_event(
                    "T-0002",
                    "STATE_CHANGED",
                    "WO-1",
                    {
                        "state": "DEFERRED",
                        "child_disposition": {
                            "injection_key": "INJ-1",
                            "disposition": "DEFER",
                            "owner": "GBOGEB/child",
                        },
                    },
                ),
            ]
        )
        with self.assertRaises(tc.TemporalGoldenThreadError):
            tc.scan_child_transactions(ledger)


if __name__ == "__main__":
    unittest.main()
