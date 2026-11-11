"""resolve_answered.py: which evidence replies close a thread, and that only those are resolved. Fake gh only."""
import importlib.util
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("resolve_answered", HERE / "resolve_answered.py")
RA = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RA)

ME = "owner"


class FakeGh:
    """One merged PR (#7) with five answered threads; #9 merged, #10 open."""

    def __init__(self):
        self.posts = []
        self.threads = [
            {"comment_ids": [1, 11], "resolved": False},
            {"comment_ids": [2, 12], "resolved": False},
            {"comment_ids": [3, 13], "resolved": False},
            {"comment_ids": [4, 14], "resolved": False},
            {"comment_ids": [5, 15], "resolved": False},
            {"comment_ids": [6], "resolved": False},
            {"comment_ids": [8, 18], "resolved": True},
        ]
        self.comments = {
            11: (ME, "Already fixed on main by abc1234."),
            12: (ME, "<!-- marker -->\n**Evidence.** Fixed by merged #9 head deadbeef."),
            13: (ME, "Fixed in #10 (draft)."),
            14: ("someone-else", "Fixed in #9."),
            15: (ME, "@copilot please fix all comments"),
        }

    def __call__(self, args):
        if args[:3] == ["api", "-X", "POST"]:
            self.posts.append(args[3])
            return 0, "{}", ""
        path = args[1]
        if path == "user":
            return 0, json.dumps({"login": ME}), ""
        if "/pulls?state=closed" in path:
            return 0, json.dumps([{"number": 7, "merged_at": "2026-11-09T10:00:00Z", "closed_at": "2026-11-09T10:00:00Z",
                                   "updated_at": "2026-11-09T10:00:00Z"}]), ""
        if path.endswith("/ccr/review_threads"):
            return 0, json.dumps(self.threads), ""
        if "/pulls/comments/" in path:
            login, body = self.comments[int(path.rsplit("/", 1)[1])]
            return 0, json.dumps({"user": {"login": login}, "body": body}), ""
        if path.endswith("/pulls/9"):
            return 0, json.dumps({"merged_at": "2026-11-09T09:00:00Z"}), ""
        if path.endswith("/pulls/10"):
            return 0, json.dumps({"merged_at": None}), ""
        return 1, "", "unexpected " + path


class Verdicts(unittest.TestCase):
    def test_reply_forms(self):
        merged = {9: True, 10: False}.get
        for text in ("Already fixed on main, confirmed by a deep read.", "Fixed in #9 (draft).",
                     "<!-- m -->\n**Title.** Fixed by merged #9.",
                     "#2281 merged first, so the fix is in #9 (draft).", "Kept as is."):
            self.assertTrue(RA.verdict_of(text, merged).startswith(RA.WAIT))
        self.assertTrue(RA.verdict_of("Fixed in #10 (draft).", merged).startswith(RA.WAIT))
        self.assertTrue(RA.verdict_of("Fixed in 963e6d5. ...", merged).startswith(RA.WAIT))
        self.assertTrue(RA.verdict_of("@copilot fix this", merged).startswith(RA.SKIP))


class Apply(unittest.TestCase):
    def test_apply_without_proof_and_lease_is_rejected(self):
        gh = FakeGh()
        with self.assertRaises(SystemExit) as error:
            RA.main(["--repos", "O/r", "--apply"], gh=gh)
        self.assertEqual(error.exception.code, 2)
        self.assertEqual(gh.posts, [])

    def test_an_unreadable_pr_is_a_gap_not_a_crash(self):
        gh = FakeGh()
        real = gh.__call__

        def flaky(args):
            if args[1:2] and args[1].endswith("/ccr/review_threads"):
                return 1, "", "gh: GitHub is temporarily unavailable. (HTTP 503)"
            return real(args)
        self.assertEqual(RA.main(["--repos", "O/r"], gh=flaky), 0)
        self.assertEqual(gh.posts, [])

    def test_dry_run_resolves_nothing(self):
        gh = FakeGh()
        RA.main(["--repos", "O/r"], gh=gh)
        self.assertEqual(gh.posts, [])


if __name__ == "__main__":
    unittest.main()
