"""Canonical public pulse -> watch feed: proof of no minted clocks/private output."""
from __future__ import annotations

import copy
import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("watch_feed", ROOT / "watch_feed.py")
F = importlib.util.module_from_spec(spec)
spec.loader.exec_module(F)
SHA = "a" * 40
T1 = "2026-10-26T01:10:00Z"
T2 = "2026-10-26T01:12:00Z"


def rec(*, stamp=T2, complete=T1, repo="GBOGEB/ABACUS", state="RED"):
    finding = {
        "id": "GBOGEB/ABACUS::CI :: python 3.12",
        "repo": repo, "source_sha": SHA, "state": state,
        "run_id": 1077, "attempt": 1, "job_id": 2077,
        "fingerprint": "diagnostic text should not be copied into output",
        "owner_accepted": False, "completed_at": complete,
    }
    if complete is None:
        finding.pop("completed_at")
    return {
        "schema": F.source.LEDGER_SCHEMA,
        "authority": F.SOURCE_AUTHORITY,
        "n": 0, "observed_at": stamp, "prev_sha256": None,
        "pulse": {"n": 0, "observed_at": stamp,
                  "source_heads": {"GBOGEB/ABACUS": SHA},
                  "findings": [finding]},
        "issue_bd": {"private_qps_open_issues": 9999999,
                     "private_row_should_not_cross": "SECRET_TEST_MARKER"},
    }


class PublicAdapter(unittest.TestCase):
    def test_native_clock_exact_main_and_public_only(self):
        events, report = F.project([rec()])
        self.assertEqual(report["events_exported"], 1)
        e = events[0]
        self.assertEqual(e["identity"]["kind"], "MERGED_MAIN")
        self.assertEqual(e["identity"]["merged_main_sha"], SHA)
        self.assertEqual(e["native"]["completed_at"], T1)
        self.assertEqual(e["native"]["observed_at"], T2)
        self.assertIsNone(e["coverage"])
        self.assertEqual(e["result"]["required_receipts"], [])
        self.assertNotIn("SECRET_TEST_MARKER", json.dumps(events))
        self.assertNotIn("9999999", json.dumps(events))
        self.assertNotIn("diagnostic text", json.dumps(events))
        state, notices = F.decision.fold(events)
        self.assertEqual(state["authority"]["merge_admission"], "HOLD")
        self.assertEqual(len(notices), 1)

    def test_legacy_pulse_without_native_completion_is_gap_not_success(self):
        events, report = F.project([rec(complete=None)])
        self.assertEqual(events, [])
        self.assertEqual(report["gaps"]["MISSING_NATIVE_COMPLETION"], 1)
        self.assertIsNone(report["fresh_six_repo_breadth"])

    def test_legacy_pulse_without_native_identity_is_gap(self):
        row = rec()
        row["pulse"]["findings"][0]["job_id"] = None
        events, report = F.project([row])
        self.assertEqual(events, [])
        self.assertEqual(report["gaps"]["MISSING_NATIVE_IDENTITY"], 1)

    def test_private_repo_in_public_ledger_is_rejected(self):
        row = rec(repo="GBOGEB/cryoplant-project")
        row["pulse"]["source_heads"]["GBOGEB/cryoplant-project"] = SHA
        with self.assertRaisesRegex(ValueError, "restricted/private"):
            F.project([row])

    def test_native_job_completion_must_precede_observation(self):
        with self.assertRaisesRegex(ValueError, "native completion after"):
            F.project([rec(stamp=T1, complete=T2)])

    def test_source_sha_mismatch_is_not_a_candidate(self):
        row = rec()
        row["pulse"]["findings"][0]["source_sha"] = "f" * 40
        with self.assertRaisesRegex(ValueError, "source-head drift"):
            F.project([row])

    def test_owner_acceptance_cannot_be_imported(self):
        row = rec()
        row["pulse"]["findings"][0]["owner_accepted"] = True
        with self.assertRaisesRegex(ValueError, "root acceptance"):
            F.project([row])

    def test_repeat_poll_is_same_native_event_not_second_notification(self):
        earlier, later = rec(stamp=T1, complete="2026-10-26T01:09:00Z"), rec(
            stamp=T2, complete="2026-10-26T01:09:00Z")
        events, report = F.project([earlier, later])
        self.assertEqual(report["events_exported"], 2)
        cursor, alerts = F.decision.fold(events)
        self.assertEqual(len(cursor["seen"]), 1)
        self.assertEqual(len(alerts), 1)

    def test_source_schema_mismatch_fails_closed(self):
        row = rec()
        row["schema"] = "foreign.metric.producer"
        with self.assertRaisesRegex(ValueError, "noncanonical"):
            F.project([row])

    def test_native_ledger_cli_verifies_chain_before_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "pulse.jsonl"
            out = pathlib.Path(tmp) / "public.jsonl"
            r = rec()
            p.write_text(F.source.line(r) + "\n", encoding="ascii")
            self.assertEqual(F.main(["--ledger", str(p), "--output", str(out)]), 0)
            self.assertEqual(len(out.read_text().splitlines()), 1)
            r["prev_sha256"] = "f" * 64
            p.write_text(F.source.line(r) + "\n", encoding="ascii")
            with self.assertRaisesRegex(ValueError, "ledger chain"):
                F.main(["--ledger", str(p), "--output", str(out)])


if __name__ == "__main__":
    unittest.main()
