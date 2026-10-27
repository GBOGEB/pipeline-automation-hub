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


if __name__ == "__main__":
    unittest.main()
