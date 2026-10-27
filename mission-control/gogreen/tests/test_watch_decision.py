"""Fail-closed, replay, reverse and negative controls for the watch consumer."""
from __future__ import annotations

import copy
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("watch_decision", ROOT / "watch_decision.py")
W = importlib.util.module_from_spec(spec)
spec.loader.exec_module(W)

HEAD, BASE, SYNTH, OTHER = "a" * 40, "b" * 40, "c" * 40, "d" * 40
BLOB, BLOB_OTHER = "e" * 40, "f" * 40


def terminal(index=1, *, outcome="failure", fingerprint="FIRST_RED", receipt="PASS",
             covered=9, blob=BLOB, kind="PR_HEAD"):
    identity = {"kind": kind, "pr_number": 17, "pr_head_sha": HEAD,
                "base_sha": BASE, "checkout_sha": HEAD,
                "synthetic_merge_sha": None, "merged_main_sha": None}
    if kind == "SYNTHETIC_MERGE":
        identity.update(checkout_sha=SYNTH, synthetic_merge_sha=SYNTH)
    if kind == "MERGED_MAIN":
        identity = {"kind": kind, "pr_number": None, "pr_head_sha": None,
                    "base_sha": None, "checkout_sha": OTHER,
                    "synthetic_merge_sha": None, "merged_main_sha": OTHER}
    return {
        "schema": W.EVENT_SCHEMA, "repository": "GBOGEB/ABACUS", "lane": "core.py3.12",
        "identity": identity,
        "native": {"run_id": 1000 + index, "attempt": 1, "job_id": 2000 + index,
                   "head_sha": OTHER if kind == "MERGED_MAIN" else HEAD,
                   "completed_at": f"2026-10-26T01:{index:02d}:00Z",
                   "observed_at": f"2026-10-26T01:{index:02d}:10Z"},
        "result": {"conclusion": outcome, "fingerprint": fingerprint,
                   "required_receipts": [{"name": "ruff", "state": receipt}]},
        "coverage": {"files": [{"path": "src/core.py", "blob_sha": blob}],
                     "tool": "coverage.py", "version": "7.13.3",
                     "selection": "core-tests", "config_sha256": "9" * 64,
                     "statements": {"covered": covered, "eligible": 10},
                     "branches": {"covered": 3, "eligible": 5}},
    }


class SourceIdentity(unittest.TestCase):
    def test_exact_pr_head_identity_accepted(self):
        self.assertTrue(W.validate(terminal()))

    def test_synthetic_merge_is_separate_identity(self):
        a = terminal(1, outcome="failure", kind="PR_HEAD")
        b = terminal(2, outcome="success", fingerprint=None, kind="SYNTHETIC_MERGE")
        state, alerts = W.fold([a, b])
        self.assertEqual(len(state["lanes"]), 2)
        self.assertNotIn("RED_TO_GREEN", [y for x in alerts for y in x["reasons"]])

    def test_synthetic_checkout_masquerading_as_pr_head_rejected(self):
        bad = terminal()
        bad["identity"]["checkout_sha"] = SYNTH
        with self.assertRaisesRegex(ValueError, "exact PR head"):
            W.validate(bad)

    def test_main_checkout_cannot_be_attested_as_pr_head(self):
        bad = terminal(kind="MERGED_MAIN")
        bad["identity"]["pr_head_sha"] = HEAD
        with self.assertRaisesRegex(ValueError, "merged main"):
            W.validate(bad)

    def test_stale_run_head_rejected(self):
        bad = terminal()
        bad["native"]["head_sha"] = OTHER
        with self.assertRaisesRegex(ValueError, "run head"):
            W.validate(bad)

    def test_no_private_repository_rows_in_public_projection(self):
        bad = terminal()
        bad["repository"] = "GBOGEB/cryoplant-project"
        with self.assertRaisesRegex(ValueError, "restricted"):
            W.validate(bad)

    def test_unknown_fields_not_permitted_in_public_projection(self):
        bad = terminal()
        bad["private_issue_number"] = 123
        with self.assertRaisesRegex(ValueError, "fields"):
            W.validate(bad)


class NonCompensatingGates(unittest.TestCase):
    def test_workflow_green_but_ruff_red_holds(self):
        event = terminal(outcome="success", fingerprint=None, receipt="FAIL")
        state, alerts = W.fold([event])
        self.assertEqual(state["authority"]["merge_admission"], "HOLD")
        self.assertIn("REQUIRED_RECEIPT_VETO", alerts[0]["reasons"])
        self.assertEqual(alerts[0]["admission"], "HOLD")

    def test_missing_required_receipt_is_not_success(self):
        state, alerts = W.fold([terminal(outcome="success", fingerprint=None, receipt="MISSING")])
        self.assertEqual(state["lanes"][next(iter(state["lanes"]))]["veto"], ["ruff:MISSING"])
        self.assertIn("REQUIRED_RECEIPT_VETO", alerts[0]["reasons"])

    def test_http_401_is_unknown_not_zero(self):
        self.assertEqual(W.visibility(401)["state"], "UNKNOWN")
        self.assertIsNone(W.visibility(401)["qualified_cells"])
        self.assertEqual(W.visibility(None)["admission"], "HOLD")
        self.assertIsNone(W.visibility(200)["qualified_cells"])

    def test_cursor_authority_cannot_be_forged(self):
        c = W.empty_cursor()
        c["authority"]["merge_admission"] = "PASS"
        with self.assertRaisesRegex(ValueError, "forged authority"):
            W.fold([], c)

    def test_skipped_job_cannot_recover_failure(self):
        failed = terminal(1)
        cancelled = terminal(2, outcome="cancelled", fingerprint=None)
        state, alerts = W.fold([failed, cancelled])
        self.assertEqual(len(alerts), 1)
        self.assertEqual(state["lanes"][next(iter(state["lanes"]))]["conclusion"], "failure")


class ReplayAndStability(unittest.TestCase):
    def test_duplicate_native_event_idempotent_across_restart(self):
        e = terminal(1)
        state, alerts = W.fold([e])
        next_state, replay_alerts = W.fold([e], state)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(replay_alerts, [])
        self.assertEqual(state, next_state)

    def test_same_terminal_job_seen_on_later_poll_is_suppressed(self):
        first = terminal(1)
        repeated = copy.deepcopy(first)
        repeated["native"]["observed_at"] = "2026-10-26T01:09:10Z"
        state, alerts = W.fold([first, repeated])
        self.assertEqual(len(state["seen"]), 1)
        self.assertEqual(len(alerts), 1)

    def test_native_identity_collision_with_changed_payload_fails(self):
        a = terminal(1)
        b = copy.deepcopy(a)
        b["result"]["fingerprint"] = "SILENT_OVERWRITE"
        with self.assertRaisesRegex(ValueError, "native identity reused"):
            W.fold([a, b])

    def test_four_distinct_equal_comparable_events_enter_stable_hold(self):
        state, alerts = W.fold([terminal(i) for i in (1, 2, 3, 4)])
        lane = next(iter(state["lanes"].values()))
        self.assertEqual(lane["equal_transitions"], 3)
        self.assertEqual(lane["mode"], "STABLE_HOLD")
        self.assertEqual(len(alerts), 1)

    def test_three_events_not_enough_to_claim_three_transitions(self):
        state, _ = W.fold([terminal(i) for i in (1, 2, 3)])
        self.assertEqual(next(iter(state["lanes"].values()))["mode"], "ACTIVE")

    def test_new_first_red_fingerprint_reactivates_only_its_lane(self):
        s, _ = W.fold([terminal(i) for i in (1, 2, 3, 4)])
        s2, alerts = W.fold([terminal(5, fingerprint="DIFFERENT_FIRST_RED")], s)
        lane = next(iter(s2["lanes"].values()))
        self.assertEqual(lane["mode"], "ACTIVE")
        self.assertEqual(lane["equal_transitions"], 0)
        self.assertEqual(len(alerts), 1)

    def test_source_matched_coverage_gain_is_not_global_coverage(self):
        a = terminal(1, outcome="success", fingerprint=None, covered=7)
        b = terminal(2, outcome="success", fingerprint=None, covered=9)
        _, alerts = W.fold([a, b])
        self.assertEqual(len(alerts), 1)
        self.assertIn("SOURCE_MATCHED_COVERAGE_CHANGE", alerts[0]["reasons"])
        self.assertEqual(alerts[0]["coverage_delta"]["statements"], 2)

    def test_changed_blob_denies_numeric_uplift_and_stability(self):
        a = terminal(1, outcome="success", fingerprint=None, covered=7)
        b = terminal(2, outcome="success", fingerprint=None, covered=9, blob=BLOB_OTHER)
        state, alerts = W.fold([a, b])
        self.assertEqual(alerts, [])
        self.assertEqual(next(iter(state["lanes"].values()))["equal_transitions"], 0)

    def test_failed_coverage_denominator_rejected(self):
        e = terminal()
        e["coverage"]["statements"]["eligible"] = 8
        with self.assertRaisesRegex(ValueError, "denominator"):
            W.validate(e)

    def test_reverse_arrival_does_not_overwrite_latest(self):
        late = terminal(2, outcome="success", fingerprint=None)
        old = terminal(1)
        state, alerts = W.fold([late, old])
        lane = next(iter(state["lanes"].values()))
        self.assertEqual(lane["conclusion"], "success")
        self.assertEqual(len(state["seen"]), 2)
        self.assertEqual(alerts, [])

    def test_two_terminal_jobs_in_one_poll_keep_native_completion_order(self):
        first = terminal(1)
        second = terminal(2, outcome="success", fingerprint=None)
        # Source collector attaches the same poll observed_at to both jobs.
        same_poll = "2026-10-26T01:03:10Z"
        first["native"]["observed_at"] = same_poll
        second["native"]["observed_at"] = same_poll
        state, alerts = W.fold([first, second])
        lane = next(iter(state["lanes"].values()))
        self.assertEqual(lane["conclusion"], "success")
        self.assertEqual(len(state["seen"]), 2)
        self.assertIn("RED_TO_GREEN", [reason for x in alerts for reason in x["reasons"]])

    def test_same_native_completion_clock_uses_job_identity_tiebreaker(self):
        first = terminal(1)
        second = terminal(2, outcome="success", fingerprint=None)
        second["native"]["completed_at"] = first["native"]["completed_at"]
        second["native"]["observed_at"] = first["native"]["observed_at"]
        state, alerts = W.fold([first, second])
        self.assertEqual(next(iter(state["lanes"].values()))["conclusion"], "success")
        self.assertIn("RED_TO_GREEN", [r for x in alerts for r in x["reasons"]])

    def test_delayed_old_completion_cannot_roll_back_newer_state(self):
        newer = terminal(3, outcome="success", fingerprint=None)
        older = terminal(2)
        # The older completed event was discovered by the reader much later.
        older["native"]["observed_at"] = "2026-10-26T01:05:10Z"
        state, alerts = W.fold([newer, older])
        lane = next(iter(state["lanes"].values()))
        self.assertEqual(lane["conclusion"], "success")
        self.assertEqual(lane["completed_at"], newer["native"]["completed_at"])
        self.assertEqual(len(alerts), 0)
        self.assertEqual(len(state["seen"]), 2)

    def test_invalid_source_blob_scope_rejected(self):
        bad = terminal()
        bad["coverage"]["files"].append({"path": "../private.json", "blob_sha": BLOB})
        with self.assertRaisesRegex(ValueError, "unsafe source path"):
            W.validate(bad)



class CursorPersistence(unittest.TestCase):
    def test_cli_dry_run_and_opt_in_restart_replay(self):
        import contextlib
        import io
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as folder:
            source = pathlib.Path(folder) / "source.jsonl"
            cursor = pathlib.Path(folder) / "watch_cursor.json"
            source.write_text(json.dumps(terminal(1)) + "\n", encoding="utf-8", newline="\n")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(W.main(["--events", str(source), "--cursor", str(cursor)]), 0)
            self.assertFalse(cursor.exists(), "default must be a read-only dry run")
            self.assertEqual(json.loads(out.getvalue())["new_native_identities"], 1)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(W.main(["--events", str(source), "--cursor", str(cursor),
                                         "--write-cursor"]), 0)
            self.assertTrue(cursor.exists())
            first = cursor.read_bytes()
            self.assertEqual(json.loads(out.getvalue())["new_native_identities"], 1)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(W.main(["--events", str(source), "--cursor", str(cursor),
                                         "--write-cursor"]), 0)
            self.assertEqual(cursor.read_bytes(), first)
            self.assertEqual(json.loads(out.getvalue())["new_native_identities"], 0)
            self.assertEqual(json.loads(out.getvalue())["notifications"], [])

    def test_posix_cursor_replace_fsyncs_directory_entry(self):
        import contextlib
        import io
        import json
        import os
        import tempfile
        from unittest import mock

        if os.name != "posix":
            self.skipTest("directory fsync requires POSIX")
        with tempfile.TemporaryDirectory() as folder:
            events = pathlib.Path(folder) / "events.jsonl"
            cursor = pathlib.Path(folder) / "cursor.json"
            events.write_text(json.dumps(terminal(1)) + "\n", encoding="utf-8", newline="\n")
            with mock.patch("os.fsync", wraps=os.fsync) as syncing:
                with contextlib.redirect_stdout(io.StringIO()):
                    W.main(["--events", str(events), "--cursor", str(cursor),
                            "--write-cursor"])
            self.assertTrue(cursor.exists())
            self.assertGreaterEqual(syncing.call_count, 2)

    def test_crash_leftover_marker_does_not_block_new_owner(self):
        import contextlib
        import io
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as folder:
            events = pathlib.Path(folder) / "events.jsonl"
            cursor = pathlib.Path(folder) / "cursor.json"
            marker = cursor.with_name(cursor.name + ".lock")
            events.write_text(json.dumps(terminal(1)) + "\n", encoding="utf-8", newline="\n")
            marker.write_text("orphaned-old-exclusive-lock", encoding="utf-8", newline="\n")
            # Old O_EXCL locking failed here forever; advisory lock acquires
            # because no live process holds a lease on the inode.
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(W.main(["--events", str(events),
                                         "--cursor", str(cursor),
                                         "--write-cursor"]), 0)
            self.assertTrue(cursor.exists())
            self.assertTrue(marker.exists(), "lock inode remains stable for all writers")

    def test_concurrent_writer_is_refused_without_mutating_cursor(self):
        import contextlib
        import io
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as folder:
            events = pathlib.Path(folder) / "events.jsonl"
            cursor = pathlib.Path(folder) / "cursor.json"
            events.write_text(json.dumps(terminal(1)) + "\n", encoding="utf-8", newline="\n")
            marker = cursor.with_name(cursor.name + ".lock")
            with W.cursor_writer_lock(marker):
                with self.assertRaisesRegex(ValueError, "single-writer lock held"):
                    with contextlib.redirect_stdout(io.StringIO()):
                        W.main(["--events", str(events), "--cursor", str(cursor),
                                "--write-cursor"])
                self.assertFalse(cursor.exists())
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(W.main(["--events", str(events), "--cursor", str(cursor),
                                         "--write-cursor"]), 0)
            self.assertTrue(cursor.exists())

    def test_source_private_row_rejected_before_cursor_mutation(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            source = pathlib.Path(folder) / "source.jsonl"
            cursor = pathlib.Path(folder) / "watch_cursor.json"
            bad = terminal()
            bad["repository"] = "GBOGEB/cryoplant-project"
            source.write_text(json.dumps(bad) + "\n", encoding="utf-8", newline="\n")
            with self.assertRaisesRegex(ValueError, "restricted"):
                W.main(["--events", str(source), "--cursor", str(cursor),
                        "--write-cursor"])
            self.assertFalse(cursor.exists())

if __name__ == "__main__":
    unittest.main()
