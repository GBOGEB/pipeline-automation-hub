"""Session-recursive intake: real Golden Thread roundtrip and fail-closed controls."""
from __future__ import annotations
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import session_hook as hook

INPUT = HERE / "SESSION_INTAKE_V1.json"
SHA = "a" * 40


class SessionHookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(INPUT.read_text(encoding="utf-8"))

    def data(self):
        return copy.deepcopy(self.fixture)

    def test_reconstructed_intents_and_owners(self):
        ledger = hook.build(self.data())
        report = hook.projection(self.data(), ledger, SHA)
        self.assertEqual(report["intent_count"], 2)
        self.assertEqual(report["work_order_count"], 2)
        self.assertEqual(report["source_turns_unbound"], 2)
        self.assertEqual(report["native_verified_actions"], 0)
        self.assertEqual(report["root_authority"], "PROJECTION_ONLY")
        self.assertEqual(report["qps_disposition"], "DEFER")
        self.assertFalse(report["merge_authorized"])

    def test_real_golden_thread_hashchain_and_replay(self):
        ledger = hook.build(self.data())
        self.assertEqual(hook.gt.verify(ledger)["status"], "PASS")
        proj1 = hook.gt.rebuild(ledger)
        proj2 = hook.gt.rebuild(ledger)
        self.assertEqual(proj1["projection_digest"], proj2["projection_digest"])
        self.assertEqual(proj1["metrics"]["orphan_occurrence_count"], 0)
        self.assertEqual(proj1["metrics"]["lineage_retention_coverage"], 1.0)

    def test_current_intent_refines_not_supersedes_previous(self):
        ledger = hook.build(self.data())
        types = [event["event_type"] for event in ledger["events"]]
        self.assertIn("CLASSIFIED", types)
        self.assertNotIn("SUPERSEDED_BY", types)
        graph = hook.make_mermaid(hook.projection(self.data(), ledger, SHA))
        self.assertIn("|refines|", graph)
        self.assertNotIn("MERGE_ADMITTED", graph)

    def test_native_gate_remains_noncompensating(self):
        events = hook.build(self.data())["events"]
        hold = [event for event in events if event["event_type"] == "NON_COMPENSATING_GATE_SET"]
        self.assertEqual(len(hold), 2)
        self.assertTrue(all(e["non_compensating_preserved"] is True for e in hold))
        self.assertTrue(all(e["payload"]["reentry_trigger"] for e in hold))

    def test_deterministic_byte_and_checksum_manifest(self):
        d = self.data()
        ledger = hook.build(d)
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            report1 = hook.emit(d, ledger, out, SHA)
            initial = (out / "session_projection.json").read_bytes()
            report2 = hook.emit(d, ledger, out, SHA)
            self.assertEqual(report1, report2)
            self.assertEqual(initial, (out / "session_projection.json").read_bytes())
            receipt = json.loads((out / "session_receipt.json").read_text())
            for filename, info in receipt["files"].items():
                raw = (out / filename).read_bytes()
                self.assertEqual(info["sha256"], "sha256:" + hashlib.sha256(raw).hexdigest())
            self.assertFalse(receipt["merge_authorized"])

    def test_html_escaped_and_filterable(self):
        d = self.data()
        d["intent_events"][0]["summary"] += ' <img src=x onerror="alert(1)">'
        report = hook.projection(d, hook.build(d), SHA)
        page = hook.make_html(report)
        self.assertNotIn('<img src=x onerror="alert(1)">', page)
        self.assertIn("&lt;img", page)
        self.assertIn('id="filter"', page)
        self.assertIn("viewport", page)

    def test_no_original_turn_id_fabrication(self):
        d = self.data()
        d["intent_events"][0]["original_turn_id"] = "fake-chat-message-123"
        with self.assertRaisesRegex(hook.SessionHookError, "message identity"):
            hook.build(d)

    def test_unverified_original_timestamp_rejected(self):
        d = self.data()
        d["intent_events"][0]["original_message_time_utc"] = "2026-10-15T12:42:00Z"
        with self.assertRaisesRegex(hook.SessionHookError, "message identity"):
            hook.build(d)

    def test_refuse_raw_chat_and_secret_bearing_fields(self):
        for field in ("prompt", "raw_chat", "transcript", "api_key"):
            d = self.data()
            d[field] = "raw user text"
            with self.subTest(field=field), self.assertRaisesRegex(hook.SessionHookError, "raw chat"):
                hook.build(d)

    def test_no_false_approval_or_engineering_credit(self):
        for k, value in (("merge_authorized", True),
                         ("authority_transfer", True),
                         ("engineering_credit", 1),
                         ("qps_disposition", "ACCEPT")):
            d = self.data()
            d[k] = value
            with self.subTest(k=k), self.assertRaisesRegex(hook.SessionHookError, "boundary"):
                hook.build(d)

    def test_native_success_receipt_cannot_be_self_asserted(self):
        d = self.data()
        d["intent_events"][0]["action"]["status"] = "VERIFIED_NATIVE"
        with self.assertRaisesRegex(hook.SessionHookError, "manual intake cannot claim"):
            hook.build(d)

    def test_invalid_parent_future_dependency_rejected(self):
        d = self.data()
        d["intent_events"][0]["parent_intent_id"] = d["intent_events"][1]["intent_id"]
        d["intent_events"][0]["relation_to_parent"] = "REFINES_WITHOUT_SUPERSEDING"
        with self.assertRaisesRegex(hook.SessionHookError, "parent must precede"):
            hook.build(d)

    def test_owner_mismatch_rejected(self):
        d = self.data()
        d["intent_events"][0]["action"]["owner_issue"] = 154
        with self.assertRaisesRegex(hook.SessionHookError, "owner mismatch"):
            hook.build(d)

    def test_duplicate_intent_rejected(self):
        d = self.data()
        d["intent_events"][1]["intent_id"] = d["intent_events"][0]["intent_id"]
        with self.assertRaisesRegex(hook.SessionHookError, "duplicate intent"):
            hook.build(d)

    def test_source_blob_must_be_exact(self):
        d = self.data()
        d["existing_source_refs"][0]["blob_sha"] = "short"
        with self.assertRaisesRegex(hook.SessionHookError, "exact blob"):
            hook.build(d)

    def test_forecast_actual_remains_pending_until_native(self):
        d = self.data()
        d["forecast_pre_registered"]["actual_native_adapter_result"] = "PASS"
        with self.assertRaisesRegex(hook.SessionHookError, "forecast outcome"):
            hook.build(d)

    def test_append_only_recursion_preserves_parent_chain(self):
        d = self.data()
        previous = hook.build(d)
        successor = copy.deepcopy(d)
        successor["intent_events"] = [copy.deepcopy(d["intent_events"][1])]
        e = successor["intent_events"][0]
        e["intent_id"] = "CP-SESSION-20261015-003"
        e["logical_index"] = 1
        e["parent_intent_id"] = "CP-SESSION-20261015-002"
        e["action"]["action_id"] = "CP-ACTION-20261015-003"
        current = hook.build(successor, previous=previous)
        self.assertEqual(
            [row["this_event_digest"] for row in previous["events"]],
            [row["this_event_digest"] for row in current["events"][:len(previous["events"])]])
        self.assertGreater(len(current["events"]), len(previous["events"]))
        self.assertEqual(hook.gt.verify(current)["status"], "PASS")

    def test_prior_event_cannot_be_replayed_as_new(self):
        d = self.data()
        old = hook.build(d)
        with self.assertRaisesRegex(hook.SessionHookError, "duplicate intent"):
            hook.build(d, previous=old)

    def test_wrong_session_alias_and_backdated_checkpoint_rejected(self):
        old = hook.build(self.data())
        d = self.data()
        d["session_alias"] = "OTHER_SESSION_ALIAS_20261015"
        with self.assertRaisesRegex(hook.SessionHookError, "cross-session"):
            hook.build(d, previous=old)
        d = self.data()
        d["capture_checkpoint_utc"] = "2026-10-14T12:43:00Z"
        for event in d["intent_events"]:
            event["capture_checkpoint_utc"] = d["capture_checkpoint_utc"]
        with self.assertRaisesRegex(hook.SessionHookError, "backwards"):
            hook.build(d, previous=old)


if __name__ == "__main__":
    unittest.main()
