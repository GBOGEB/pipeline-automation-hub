"""Regression tests for the real side-effect boundary and interrupted closure."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("maroon_closure", HERE / "closure.py")
C = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(C)


def fixture():
    comments = [{"id": 1, "body": "Check the source.", "author": "reviewer",
                 "created_at": "2026-11-11T00:00:00Z", "updated_at": "2026-11-11T00:00:00Z", "commit_id": "a" * 40}]
    proof = {"schema": "code_maroon.closure-proof.v1", "item_id": C.OPS.observation_id("O/r", 7, 1), "repo": "O/r", "pr": 7,
             "thread_id": "T1", "comment_id": 1, "head_sha": "a" * 40, "base_sha": "b" * 40,
             "discussion_hash": C.discussion_hash(comments), "blob_oids": {"src/a.py": "c" * 40},
             "classification": "false_positive", "method": "Inspect the guarded control flow and test all exits.",
             "evidence": [{"kind": "local_test", "source_sha": "a" * 40, "conclusion": "PASS", "ref": "proof:test-16"}]}
    live = {k: proof[k] for k in ("repo", "pr", "thread_id", "head_sha", "base_sha", "blob_oids")}
    live.update(pr_state="open", complete=True, negative_canary=False, comments=comments,
                provider_resolved=False, viewer_can_resolve=True, url="https://github.com/O/r/pull/7#discussion_r1")
    return proof, live


class Provider:
    def __init__(self, live):
        self.live = copy.deepcopy(live)
        self.posts = self.resolves = 0
        self.timeout_after_reply = False
        self.move_after_reply = False

    def read(self, proof):
        return copy.deepcopy(self.live)

    def own_replies(self, live, body):
        return [c for c in live["comments"] if c["author"] == "worker" and c["body"] == body]

    def reply(self, proof, body):
        self.posts += 1
        self.live["comments"].append({"id": 2, "body": body, "author": "worker",
                                     "created_at": "2026-11-11T01:00:00Z", "updated_at": "2026-11-11T01:00:00Z", "commit_id": "a" * 40})
        if self.move_after_reply:
            self.live["head_sha"] = "d" * 40
        if self.timeout_after_reply:
            raise TimeoutError("unknown response")

    def resolve(self, thread):
        self.resolves += 1
        self.live["provider_resolved"] = True


class Closure(unittest.TestCase):
    def setUp(self):
        self.proof, self.live = fixture()
        self.provider = Provider(self.live)
        self.journal, self.saved, self.closed = {}, [], []

    def apply(self, close=None, checkpoint=None, lease=None):
        return C.apply_close(self.proof, self.provider, self.journal,
                             checkpoint or self.saved.append, close or self.closed.append, lease or (lambda: True))

    def test_reply_resolve_readback_and_close(self):
        receipt = self.apply()
        self.assertEqual((self.provider.posts, self.provider.resolves, len(self.closed)), (1, 1, 1))
        self.assertEqual(receipt["provider_readback"]["thread_id"], "T1")
        self.assertEqual(self.journal["phase"], "closed")
        replay = self.apply()
        self.assertEqual(replay, receipt)
        self.assertEqual(len(self.closed), 1)

    def test_missing_or_wrong_item_id_never_mutates(self):
        for item in (None, "different-item"):
            self.proof["item_id"] = item
            self.journal = {}
            with self.assertRaises(C.Hold):
                self.apply()
            self.assertEqual((self.provider.posts, self.provider.resolves), (0, 0))

    def test_new_provider_proof_cannot_use_old_source_claim(self):
        member = {key: self.proof[key] for key in ("pr", "comment_id", "thread_id", "head_sha", "base_sha", "discussion_hash", "blob_oids")}
        member.update(id=self.proof["item_id"], core_oids=C.OPS.runtime_core_oids())
        packet = {"repo": "O/r", "member_ids": [member["id"]], "members": [member], "core_oids": C.OPS.runtime_core_oids()}
        self.proof["head_sha"] = self.provider.live["head_sha"] = "d" * 40
        self.proof["evidence"][0]["source_sha"] = "d" * 40
        with self.assertRaisesRegex(C.Hold, "claimed source"):
            self.apply(lease=lambda: C.validate_claim(self.proof, packet))
        self.assertEqual((self.provider.posts, self.provider.resolves), (0, 0))

    def test_changed_head_blob_or_discussion_never_mutates(self):
        for key, value in (("head_sha", "d" * 40), ("base_sha", "d" * 40),
                           ("blob_oids", {"src/a.py": "e" * 40}), ("comments", []),
                           ("negative_canary", True), ("complete", False)):
            with self.subTest(key=key):
                self.provider = Provider({**self.live, key: value})
                self.journal = {}
                with self.assertRaises(C.Hold):
                    self.apply()
                self.assertEqual(self.provider.posts, 0)

    def test_checkpoint_failure_blocks_side_effects(self):
        def fail(_):
            raise OSError("disk unavailable")
        with self.assertRaises(OSError):
            self.apply(checkpoint=fail)
        self.assertEqual(self.provider.posts, 0)

    def test_expired_lease_blocks_side_effects(self):
        def fail():
            raise C.Hold("lease expired")
        with self.assertRaises(C.Hold):
            self.apply(lease=fail)
        self.assertEqual(self.provider.posts, 0)

    def test_reply_timeout_is_healed_without_duplicate_message(self):
        self.provider.timeout_after_reply = True
        with self.assertRaises(TimeoutError):
            self.apply()
        self.provider.timeout_after_reply = False
        self.apply()
        self.assertEqual(self.provider.posts, 1)

    def test_uncertain_absent_reply_is_not_reposted(self):
        self.journal.update(operation_id=C.digest(self.proof), phase="reply_uncertain")
        with self.assertRaisesRegex(C.Hold, "do not repost"):
            self.apply()
        self.assertEqual(self.provider.posts, 0)

    def test_ledger_failure_resumes_after_resolution(self):
        def fail(_):
            raise OSError("ledger unavailable")
        with self.assertRaises(OSError):
            self.apply(close=fail)
        self.assertEqual(self.journal["phase"], "resolved")
        self.apply()
        self.assertEqual((self.provider.posts, self.provider.resolves), (1, 1))

    def test_head_moves_after_reply_thread_stays_open(self):
        self.provider.move_after_reply = True
        with self.assertRaises(C.Hold):
            self.apply()
        self.assertEqual((self.provider.posts, self.provider.resolves), (1, 0))

    def test_other_author_cannot_forge_idempotency_reply(self):
        body = C.evidence_reply(self.proof, f"<!-- MAROON_CLOSURE_V1 {C.digest(self.proof)} -->")
        self.provider.live["comments"].append({**self.live["comments"][0], "id": 3, "body": body, "author": "other"})
        with self.assertRaises(C.Hold):
            self.apply()
        self.assertEqual(self.provider.posts, 0)

    def test_text_and_short_sha_are_not_proof(self):
        self.proof.update(head_sha="abcdef0", method="Already fixed")
        with self.assertRaises(C.Hold):
            self.apply()

    def test_real_canary_titles_are_preserved(self):
        for title in ("DO NOT MERGE — MACH-II red canary (required checks must reject)",
                      "PROBE - DO NOT MERGE - close after reading", "negative-canary", "testflight red"):
            self.assertTrue(C.is_negative_canary(title, ""))
        self.assertFalse(C.is_negative_canary("formatting lane", "Do not merge unless green."))


class NativeAuthorIdentity(unittest.TestCase):
    """REST intake and GraphQL readback must hash the same actual scanner author."""

    def native_read(self, *, login="github-advanced-security", actor_type="Bot", body="Check the source.",
                    rest_login="github-advanced-security[bot]"):
        proof, _ = fixture()
        pr = {"number": 7, "state": "open", "title": "Fix the source", "body": "Review this repair.",
              "head": {"sha": proof["head_sha"]}, "base": {"sha": proof["base_sha"]}}
        rest_comment = {"id": 1, "body": "Check the source.", "user": {"login": rest_login},
                        "created_at": "2026-11-11T00:00:00Z", "updated_at": "2026-11-11T00:00:00Z",
                        "original_commit_id": proof["head_sha"]}
        intake = C.RT.threads_of(pr, [rest_comment], [], set())[0]
        proof["discussion_hash"] = intake["discussion_hash"]
        query_calls = []

        def gh(args):
            route = args[1]
            if route == "user":
                result = {"login": "worker"}
            elif route == "repos/O/r/pulls/7":
                result = pr
            elif route.startswith("repos/O/r/contents/src/a.py?"):
                result = {"type": "file", "sha": proof["blob_oids"]["src/a.py"]}
            elif route == "graphql":
                query_calls.append(args)
                result = {"data": {"node": {"id": "T1", "isResolved": False, "viewerCanResolve": True,
                    "pullRequest": {"number": 7, "repository": {"nameWithOwner": "O/r"}},
                    "comments": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": [{
                        "databaseId": 1, "body": body, "author": {"login": login, "__typename": actor_type},
                        "createdAt": rest_comment["created_at"], "updatedAt": rest_comment["updated_at"],
                        "originalCommit": {"oid": proof["head_sha"]}, "commit": {"oid": proof["head_sha"]},
                        "url": "https://github.com/O/r/pull/7#discussion_r1"}]}}}}
            else:
                self.fail("unexpected native read route: " + route)
            return 0, json.dumps(result), ""

        live = C.GitHub(gh=gh).read(proof)
        self.assertIn("author{__typename login}", next(arg for arg in query_calls[0] if arg.startswith("query=")))
        return proof, live

    def test_known_graphql_bot_matches_existing_rest_ledger_hash(self):
        proof, live = self.native_read()
        self.assertEqual(live["comments"][0]["author"], "github-advanced-security[bot]")
        self.assertTrue(C.validate(proof, live))

    def test_suffix_is_not_added_twice(self):
        proof, live = self.native_read(login="github-advanced-security[bot]")
        self.assertTrue(C.validate(proof, live))

    def test_other_provider_typed_bots_use_the_same_rest_identity_rule(self):
        for login in ("chatgpt-codex-connector", "sonarcloud", "review-agent"):
            with self.subTest(login=login):
                proof, live = self.native_read(login=login, rest_login=login + "[bot]")
                self.assertTrue(C.validate(proof, live))

    def test_same_login_on_a_user_or_unknown_actor_does_not_impersonate_bot(self):
        for actor_type in ("User", None):
            with self.subTest(actor_type=actor_type):
                proof, live = self.native_read(actor_type=actor_type)
                self.assertEqual(live["comments"][0]["author"], "github-advanced-security")
                with self.assertRaisesRegex(C.Hold, "discussion changed"):
                    C.validate(proof, live)

    def test_actual_author_or_body_changes_still_invalidate_proof(self):
        for change in ({"login": "another-security-app"}, {"body": "The finding has changed."}):
            with self.subTest(change=change):
                proof, live = self.native_read(**change)
                with self.assertRaisesRegex(C.Hold, "discussion changed"):
                    C.validate(proof, live)


if __name__ == "__main__":
    unittest.main()
