"""CP.CLOSEOUT positive and adversarial nonpromotion tests."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import unittest

from validate_chat_closeout import count_normalized_export, validate

HERE = Path(__file__).resolve().parent
PROFILE = json.loads((HERE / "CHAT_CLOSEOUT_PROFILE_V1.json").read_text(encoding="utf-8"))
RECEIPT = json.loads((HERE / "chat-closeouts" / "CP-HUB-HANDOFF-20261017" /
                      "RECEIPT.json").read_text(encoding="utf-8"))


class ChatCloseoutContractTests(unittest.TestCase):
    def test_partial_session_structurally_valid(self):
        result = validate(PROFILE, RECEIPT)
        self.assertEqual(result["stage"], "COMMITTED_TO_PR")
        self.assertTrue(result["full_chat_statistics_missing"])
        self.assertEqual(result["engineering_merge_admission"], "HOLD")
        self.assertEqual(result["bd_items"], 5)

    def reject(self, change):
        data = copy.deepcopy(RECEIPT)
        change(data)
        with self.assertRaises(ValueError):
            validate(PROFILE, data)

    def test_reject_unexported_full_prompt_total(self):
        self.reject(lambda r: r["statistics"]["full_counts"].update(
            user_prompts=2, assistant_replies=1, tool_calls=3))

    def test_reject_full_scope_without_original_bytes(self):
        def change(r):
            r["session"]["source_scope"] = "FULL_EXPORT_VERIFIED"
            r["session"]["export_sha256"] = "a" * 64
            r["statistics"]["full_counts"] = {
                "user_prompts": 2, "assistant_replies": 1, "tool_calls": 3}
        self.reject(change)

    def test_reject_false_token_count(self):
        self.reject(lambda r: r["statistics"].update(token_count=12345))

    def test_reject_excerpt_count_as_full_basis(self):
        self.reject(lambda r: r["statistics"]["visible_context_counts"].update(
            basis="FULL_EXPORT_VERIFIED"))

    def test_reject_deletion_by_assistant(self):
        self.reject(lambda r: r["controls"].update(chat_deleted_by_assistant=True))

    def test_reject_raw_chat_transcript_in_git(self):
        self.reject(lambda r: r["controls"].update(raw_transcript_committed=True))

    def test_reject_security_waiver(self):
        self.reject(lambda r: r["controls"].update(security_waiver=True))

    def test_reject_unverified_default_merge(self):
        self.reject(lambda r: r["custody"].update(stage="MERGED_TO_DEFAULT"))

    def test_reject_unverified_exact_main(self):
        self.reject(lambda r: r["custody"].update(stage="EXACT_MAIN_VERIFIED"))

    def test_reject_fabricated_branch_head(self):
        self.reject(lambda r: r["lineage"]["prs"][0].update(head_sha="1" * 39))

    def test_reject_bad_pr_source_url(self):
        self.reject(lambda r: r["lineage"]["prs"][0].update(
            url="https://example.com/citation"))

    def test_reject_duplicate_bd_identity(self):
        self.reject(lambda r: r["bd_queue"].append(copy.deepcopy(r["bd_queue"][0])))

    def test_reject_no_dov_on_bd(self):
        self.reject(lambda r: r["bd_queue"][0].update(definition_of_verification=""))

    def test_reject_missing_narrative(self):
        self.reject(lambda r: r["narrative"].update(original_intent="  "))

    def test_reject_unsupported_priority(self):
        self.reject(lambda r: r["bd_queue"][0].update(priority="P-999"))

    def test_reject_atomic_multi_repo_readback(self):
        self.reject(lambda r: r["session"].update(snapshot_atomic=True))

    def test_optional_export_count_matches_bytes(self):
        normalized = {
            "schema": "code_purple.normalized_chat_export.v1",
            "complete": True,
            "messages": [
                {"id": "u1", "role": "user", "content": "Request"},
                {"id": "a1", "role": "assistant", "content": "Answer"},
                {"id": "tc1", "role": "tool_call", "content": "Run"},
                {"id": "tr1", "role": "tool_result", "content": "Result"},
                {"id": "u2", "role": "user", "content": "Follow-up"},
            ],
        }
        raw = json.dumps(normalized, sort_keys=True).encode("utf-8")
        self.assertEqual(count_normalized_export(raw), {
            "user_prompts": 2, "assistant_replies": 1, "tool_calls": 1})
        data = copy.deepcopy(RECEIPT)
        data["session"]["source_scope"] = "FULL_EXPORT_VERIFIED"
        data["session"]["export_sha256"] = hashlib.sha256(raw).hexdigest()
        data["statistics"]["full_counts"] = {
            "user_prompts": 2, "assistant_replies": 1, "tool_calls": 1}
        result = validate(PROFILE, data, raw)
        self.assertTrue(result["exact_full_chat_counts_verified"])
        self.assertFalse(result["full_chat_statistics_missing"])

    def test_export_bytes_mismatch_rejected(self):
        payload = {"schema": "code_purple.normalized_chat_export.v1",
                   "complete": True, "messages": []}
        raw = json.dumps(payload).encode()
        data = copy.deepcopy(RECEIPT)
        data["session"]["source_scope"] = "FULL_EXPORT_VERIFIED"
        data["session"]["export_sha256"] = "a" * 64
        data["statistics"]["full_counts"] = {
            "user_prompts": 0, "assistant_replies": 0, "tool_calls": 0}
        with self.assertRaises(ValueError):
            validate(PROFILE, data, raw)

    def test_export_duplicate_identity_rejected(self):
        raw = json.dumps({
            "schema": "code_purple.normalized_chat_export.v1",
            "complete": True,
            "messages": [{"id": "x", "role": "user"}, {"id": "x", "role": "assistant"}],
        }).encode()
        with self.assertRaises(ValueError):
            count_normalized_export(raw)


if __name__ == "__main__":
    unittest.main()
