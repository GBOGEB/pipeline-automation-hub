import copy
import json
import unittest
from pathlib import Path

import golden_thread as gt

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "COLD_TAIL_BOOTSTRAP_LEDGER_v1.json"


class GoldenThreadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_verify_hash_chain(self):
        receipt = gt.verify_ledger(self.ledger)
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["event_count"], 14)

    def test_rebuild_is_deterministic(self):
        a = gt.rebuild(self.ledger)
        b = gt.rebuild(self.ledger)
        self.assertEqual(a["projection_digest"], b["projection_digest"])
        self.assertEqual(a, b)

    def test_expand_root_recovers_three_line_s_occurrences(self):
        expanded = gt.expand_root(self.ledger, "ROOT-LS")
        self.assertEqual(
            set(expanded["occurrences"]),
            {"GBOGEB/ABACUS#581", "GBOGEB/ABACUS#583", "GBOGEB/ABACUS#585"},
        )
        self.assertIn("WO-LS-583", expanded["work_orders"])

    def test_as_of_before_codex_occurrence(self):
        proj = gt.rebuild(self.ledger, "GT-0012")
        self.assertNotIn("GBOGEB/CODEX#237", proj["occurrences"])
        self.assertEqual(proj["metrics"]["occurrence_count"], 3)

    def test_diff_adds_codex_reader_item(self):
        diff = gt.diff_boundaries(self.ledger, "GT-0012", "GT-0014")
        ids = [e["event_id"] for e in diff["events_added"]]
        self.assertEqual(ids, ["GT-0013", "GT-0014"])
        self.assertEqual(diff["metric_delta"]["occurrence_count"], 1)
        self.assertEqual(diff["metric_delta"]["unknown_needs_reader_count"], 1)

    def test_tamper_is_detected(self):
        bad = copy.deepcopy(self.ledger)
        bad["events"][4]["reason"] = "tampered"
        with self.assertRaises(gt.GoldenThreadError):
            gt.verify_ledger(bad)

    def test_bootstrap_source_time_is_distinct_from_reconstruction_time(self):
        event = self.ledger["events"][0]
        self.assertEqual(event["event_type"], "BOOTSTRAP_RECONSTRUCTED")
        self.assertNotEqual(event["observed_source_timestamp"], event["reconstruction_timestamp"])

    def test_projection_preserves_authority_false(self):
        proj = gt.rebuild(self.ledger)
        self.assertFalse(proj["authority_transfer"])
        self.assertEqual(proj["roots"]["ROOT-LS"]["root_authority"], "PROJECTION_ONLY")
        self.assertEqual(proj["metrics"]["orphan_occurrence_count"], 0)
        self.assertEqual(proj["metrics"]["lineage_retention_coverage"], 1.0)


if __name__ == "__main__":
    unittest.main()
