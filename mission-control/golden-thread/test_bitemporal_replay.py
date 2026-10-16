"""Knowledge-time replay: hindsight exclusion, source custody and N->N+1.
These tests do not claim child ACCEPT or engineering root closure.
"""
import copy
import json
import unittest
from pathlib import Path

import golden_thread as gt

HERE=Path(__file__).resolve().parent
FIXTURE=HERE/"fixtures"/"COLD_TAIL_BOOTSTRAP_LEDGER_v1.json"
KNOWN_12="2026-09-17T00:56:11Z"
KNOWN_14="2026-09-17T00:56:13Z"


class GoldenThreadKnowledgeTimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger=json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_hindsight_excluded_when_source_was_known_later(self):
        # Historical occurrence in June was only reconstructed in September.
        event_time=gt.rebuild(self.ledger,"2026-06-20T00:00:00Z")
        known_time=gt.rebuild_known_at(self.ledger,"2026-08-01T00:00:00Z")
        self.assertEqual(4,event_time["metrics"]["occurrence_count"])
        self.assertEqual(0,known_time["metrics"]["event_count"])
        self.assertEqual([],known_time["temporal_selection"]["selected_event_ids"])
        self.assertNotEqual(event_time["projection_digest"],
                            known_time["projection_digest"])

    def test_before_and_after_have_source_matched_denominator(self):
        a=gt.rebuild_known_at(self.ledger,KNOWN_12)
        b=gt.rebuild_known_at(self.ledger,KNOWN_14)
        self.assertEqual(12,a["metrics"]["event_count"])
        self.assertEqual(14,b["metrics"]["event_count"])
        self.assertEqual(3,a["metrics"]["occurrence_count"])
        self.assertEqual(4,b["metrics"]["occurrence_count"])
        self.assertEqual(1,b["metrics"]["unknown_needs_reader_count"])
        self.assertEqual(self.ledger["head_event_digest"],
                         a["temporal_selection"]["full_ledger_head_event_digest"])
        self.assertTrue(a["temporal_selection"]["full_ledger_verified"])
        self.assertFalse(a["temporal_selection"]["partial_selection_is_new_authority"])

    def test_actual_timestamp_diff_has_two_new_events(self):
        delta=gt.diff_known_at(self.ledger,KNOWN_12,KNOWN_14)
        self.assertEqual(["GT-0013","GT-0014"],
                         [v["event_id"] for v in delta["events_added"]])
        self.assertEqual(2,delta["metric_delta"]["event_count"])
        self.assertEqual(1,delta["metric_delta"]["occurrence_count"])
        self.assertEqual(1,delta["metric_delta"]["unknown_needs_reader_count"])
        self.assertIsNone(delta["formal_root_closure_credit"])
        self.assertFalse(delta["authority_transfer"])

    def test_sparse_occurrence_window_is_not_resealed_prefix(self):
        view=gt.rebuild_known_at(self.ledger,KNOWN_14,"2026-06-20T00:00:00Z")
        sel=view["temporal_selection"]
        self.assertEqual(["GT-0001","GT-0005","GT-0009","GT-0013"],
                         sel["selected_event_ids"])
        self.assertFalse(sel["chain_prefix"])
        self.assertTrue(sel["full_ledger_verified"])
        self.assertEqual(4,view["metrics"]["occurrence_count"])
        self.assertEqual(0,view["metrics"]["root_count"])
        self.assertEqual(10,sel["excluded_event_count"])

    def test_utc_offset_normalized_to_same_projection_digest(self):
        z=gt.rebuild_known_at(self.ledger,KNOWN_14)
        offset=gt.rebuild_known_at(self.ledger,"2026-09-17T02:56:13+02:00")
        self.assertEqual(z["projection_digest"],offset["projection_digest"])
        self.assertEqual("2026-09-17T00:56:13Z",
                         offset["temporal_selection"]["known_at_utc"])

    def test_selection_is_deterministic_and_cannot_mutate_ledger(self):
        original=copy.deepcopy(self.ledger)
        a=gt.rebuild_known_at(self.ledger,KNOWN_14)
        b=gt.rebuild_known_at(self.ledger,KNOWN_14)
        self.assertEqual(a,b)
        self.assertEqual(original,self.ledger)
        self.assertEqual("PASS",gt.verify(self.ledger)["status"])

    def test_tampering_still_rejected_even_when_outside_time_window(self):
        bad=copy.deepcopy(self.ledger)
        bad["events"][-1]["payload"]={"fabricated":"green"}
        with self.assertRaises(gt.GoldenThreadError):
            gt.rebuild_known_at(bad,"2026-08-01T00:00:00Z")

    def test_reversed_knowledge_windows_fail_closed(self):
        with self.assertRaisesRegex(gt.GoldenThreadError,"chronological"):
            gt.diff_known_at(self.ledger,KNOWN_14,KNOWN_12)

    def test_naive_knowledge_time_fails_closed(self):
        with self.assertRaises(gt.GoldenThreadError):
            gt.rebuild_known_at(self.ledger,"2026-09-17T00:56:13")

    def test_unknown_source_time_fails_closed(self):
        with self.assertRaises(gt.GoldenThreadError):
            gt.rebuild_known_at(self.ledger,KNOWN_14,"not-an-instant")

    def test_existing_current_boundary_remains_unchanged(self):
        before=gt.rebuild(self.ledger,"GT-0012")
        now=gt.rebuild(self.ledger)
        self.assertEqual(3,before["metrics"]["occurrence_count"])
        self.assertEqual(4,now["metrics"]["occurrence_count"])
        self.assertFalse(before["authority_transfer"])
        self.assertFalse(now["authority_transfer"])


if __name__=="__main__":
    unittest.main()
