"""Contract tests for burndown_apply on synthetic data (no network, no issue edits)."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import burndown_apply as ba  # noqa: E402

HUB = "GBOGEB/pipeline-automation-hub"


def pr(merged=True, state="MERGED", checks="SUCCESS"):
    return {"__typename": "PullRequest", "state": state, "merged": merged, "mergedAt": "2026-10-20T00:00:00Z",
            "reviewDecision": None, "mergeCommit": {"oid": "a" * 40, "statusCheckRollup": {"state": checks}}}


def iss(state="CLOSED", reason="COMPLETED"):
    return {"__typename": "Issue", "state": state, "stateReason": reason, "closedAt": "2026-10-20T00:00:00Z"}


class Classify(unittest.TestCase):
    def test_bare(self):
        self.assertTrue(ba.bare("#858"))
        self.assertTrue(ba.bare("**#858** hub runner fix"))
        self.assertFalse(ba.bare("#858 exact-head CI and independent review"))
        self.assertFalse(ba.bare("OWNER: decide on #858"))
        self.assertFalse(ba.bare("#858 " + "x" * 60))

    def test_child_verdict(self):
        self.assertEqual(ba.child_verdict(pr()), "DONE")
        self.assertEqual(ba.child_verdict(pr(merged=False, state="CLOSED")), "UNMERGED")
        self.assertEqual(ba.child_verdict(pr(merged=False, state="OPEN")), "OPEN")
        self.assertEqual(ba.child_verdict(iss()), "DONE")
        self.assertEqual(ba.child_verdict(iss(reason="NOT_PLANNED")), "NOT_PLANNED")
        self.assertEqual(ba.child_verdict(None), "UNKNOWN")

    def test_verify_items_classes(self):
        body = "\n".join(["- [ ] #1", "- [ ] #2 verify exact-head CI", "- [ ] #3", "- [ ] #4", "- [x] #1",
                          "- [ ] see #1 and #5"])
        ev = {f"{HUB}#1": pr(), f"{HUB}#2": pr(), f"{HUB}#3": pr(merged=False, state="CLOSED"),
              f"{HUB}#4": iss(state="OPEN", reason=None), f"{HUB}#5": pr(merged=False, state="OPEN")}
        rows = ba.verify_items({"repo": HUB, "body": body}, ev)
        self.assertEqual([(r["line"], r["class"]) for r in rows],
                         [(0, "TICK_READY"), (1, "VERIFY"), (2, "WITHDRAW_CANDIDATE"), (5, "WAIT")])
        self.assertEqual(rows[0]["children"][f"{HUB}#1"]["merge_checks"], "SUCCESS")


class Checkbox(unittest.TestCase):
    BODY = ("## Context\n- not a criterion\n## Done when\n- first criterion\n1. second criterion\n"
            "- [x] already tracked\n```\n- fenced bullet\n```\n## DoV\n  - nested proof\n")

    def test_converts_only_declared_bullets(self):
        new, n = ba.checkbox_body(self.BODY)
        self.assertEqual(n, 3)
        self.assertIn("- [ ] first criterion\n", new)
        self.assertIn("1. [ ] second criterion\n", new)
        self.assertIn("  - [ ] nested proof\n", new)
        self.assertIn("- not a criterion\n", new)
        self.assertIn("- fenced bullet\n", new)
        self.assertIn("- [x] already tracked\n", new)
        self.assertEqual(ba.checkbox_body(new), (new, 0))  # idempotent

    def test_wrapped_declared_bullet_is_matchable_and_idempotent(self):
        src = "## Done when\n- Deploy to staging\n  and run smoke tests\n- owner signs\n"
        updated, count = ba.checkbox_body(src)
        self.assertEqual(count, 2)
        self.assertIn("- [ ] Deploy to staging\n  and run smoke tests", updated)
        self.assertIn("- [ ] owner signs", updated)
        self.assertEqual(ba.checkbox_body(updated), (updated, 0))

    def test_tick_body_ticks_only_listed_lines(self):
        self.assertEqual(ba.tick_body("- [ ] #1\n- [ ] #2\n", {1}), "- [ ] #1\n- [x] #2\n")


class Apply(unittest.TestCase):
    def test_apply_guards_changed_body_and_chains_ledger(self):
        snap = {"repos": {HUB: {"issues": [{"number": 1, "body": "## DoD\n- a\n"},
                                            {"number": 2, "body": "## DoD\n- b\n"}]}}}
        report = {"verify": [], "checkbox": [{"issue": f"{HUB}#1"}, {"issue": f"{HUB}#2"}]}
        live = {1: "## DoD\n- a\n", 2: "## DoD\n- b changed\n"}
        patched = {}
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(ba, "live_body", lambda r, n: live[n]), \
                mock.patch.object(ba, "patch_body", lambda r, n, b: patched.__setitem__(n, b)):
            ledger = Path(d) / "edits.jsonl"
            res = ba.apply(report, snap, "checkbox", ledger)
            self.assertEqual([r["status"] for r in res], ["APPLIED", "SKIPPED_BODY_CHANGED"])
            self.assertEqual(patched, {1: "## DoD\n- [ ] a\n"})
            row = json.loads(ledger.read_text(encoding="utf-8"))
            self.assertIsNone(row["prev_sha256"])
            self.assertEqual(row["after_sha256"], ba.sha("## DoD\n- [ ] a\n"))
            ba.append_edit(ledger, {"issue": "x"})
            rows = [json.loads(x) for x in ledger.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(rows[1]["prev_sha256"], rows[0]["row_sha256"])

    def test_slices_end_to_end_with_fake_gh(self):
        snap = {"fetched_at": "t", "repos": {HUB: {"head_sha": "h", "issues": [
            {"number": 1, "body": "- [ ] #9\n## DoD\n- criterion"}]}}}
        model = {"items": [{"key": f"{HUB}#1", "type": "Issue", "rank_global": 1, "lane": "TRACK_DOD",
                            "progress": "0/1", "private": False}]}
        gh = lambda q, allow_not_found=False: {"c0": {"issueOrPullRequest": pr()}}  # noqa: E731
        r = ba.slices(snap, model, gh)
        self.assertEqual(r["summary"]["verify_items"], {"TICK_READY": 1})
        self.assertEqual(r["summary"]["checkbox_items"], 1)
        self.assertFalse(r["authority_transfer"])
        self.assertEqual(ba.slices(snap, model, gh, skip={f"{HUB}#1"})["summary"]["checkbox_issues"], 0)


class Evidence(unittest.TestCase):
    def merged(self, title, body="", checks="SUCCESS", merged=True):
        return {"__typename": "PullRequest", "title": title, "body": body, "merged": merged, "url": "u",
                "mergedAt": "2026-10-28T00:00:00Z", "mergeCommit": {"oid": "b" * 40, "statusCheckRollup": {"state": checks}}}

    def test_tokens(self):
        t = ba.tokens("Add `QPS_MASTER_INPUT_RETURN.json` receipt for W373, with every row")
        self.assertIn("qps_master_input_return.json", t)
        self.assertIn("w373", t)
        self.assertNotIn("every", t)
        self.assertNotIn("for", t)

    def test_direct_text_and_noise(self):
        body = ("- [ ] #5 lands\n- [ ] generate `QPS_MASTER_INPUT_RETURN.json` with recursive manifest receipt\n"
                "- [x] already ticked `QPS_MASTER_INPUT_RETURN.json` recursive manifest receipt\n- [ ] unrelated zebra work")
        prs = {f"{HUB}#5": self.merged("small fix", checks="FAILURE"),
               f"{HUB}#6": self.merged("feat: generate QPS_MASTER_INPUT_RETURN.json", "recursive manifest and receipt hashes"),
               f"{HUB}#7": self.merged("emit QPS_MASTER_INPUT_RETURN.json recursive manifest receipt", merged=False),
               f"{HUB}#8": None}
        for pr in prs.values():
            if pr:
                pr["_tokens"] = ba.tokens(pr["title"] + "\n" + pr["body"])
        rows = ba.evidence_items({"repo": HUB, "body": body}, prs, {}, 40)
        self.assertEqual([(r["line"], r["class"]) for r in rows], [(0, "EVIDENCE_RED_DIRECT"), (1, "EVIDENCE_GREEN_TEXT")])
        self.assertEqual(rows[1]["candidates"][0]["pr"], f"{HUB}#6")
        self.assertEqual([rows[0]["candidates"][0]["confidence"], rows[1]["candidates"][0]["confidence"]], ["HIGH", "MEDIUM"])
        self.assertEqual([c["pr"] for c in rows[1]["candidates"]], [f"{HUB}#6"])  # unmerged #7 never counts

    def test_common_tokens_are_not_distinctive(self):
        prs = {f"{HUB}#6": self.merged("exact head review gate proof")}
        prs[f"{HUB}#6"]["_tokens"] = ba.tokens(prs[f"{HUB}#6"]["title"])
        df = {t: 30 for t in ("exact", "head", "review", "gate", "proof")}
        rows = ba.evidence_items({"repo": HUB, "body": "- [ ] exact head review gate proof"}, prs, df, 40)
        self.assertEqual(rows, [])

    def test_evidence_slice_end_to_end(self):
        snap = {"fetched_at": "t", "repos": {HUB: {"issues": [
            {"number": 1, "body": "- [ ] #9 merged\n- [ ] other", "refs_in": [
                {"repo": HUB, "number": 9, "type": "PullRequest", "state": "MERGED"},
                {"repo": HUB, "number": 10, "type": "PullRequest", "state": "CLOSED"}]}]}}}
        model = {"items": [{"key": f"{HUB}#1", "type": "Issue", "rank_global": 1, "lane": "BLOCKED",
                            "progress": "0/2", "private": False}]}
        seen = []

        def gh(q, allow_not_found=False):
            seen.append(q)
            return {"p0": {"issueOrPullRequest": self.merged("x")}}
        r = ba.evidence_slice(snap, model, gh)
        self.assertEqual(r["summary"]["open_items"], 2)
        self.assertEqual(r["summary"]["by_class"], {"EVIDENCE_GREEN_DIRECT": 1})
        self.assertEqual(r["ticks"], 0)
        self.assertFalse(r["authority_transfer"])
        self.assertNotIn("number:10", seen[0])  # closed-unmerged PRs are not fetched


if __name__ == "__main__":
    unittest.main()
