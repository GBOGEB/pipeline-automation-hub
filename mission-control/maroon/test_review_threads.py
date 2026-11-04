"""CODE MAROON review-thread source: threads -> themed roots, reviewer severity, coverage, no text in public."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import maroon as M  # noqa: E402
import review_threads as RT  # noqa: E402
from test_maroon import RAW  # noqa: E402

CODEX = "chatgpt-codex-connector[bot]"


def comment(cid, login, body, path="src/a.py", reply_to=None):
    c = {"id": cid, "user": {"login": login}, "body": body, "path": path, "line": 10,
         "html_url": f"https://github.com/O/pub/pull/7#discussion_r{cid}", "original_commit_id": "a" * 40}
    if reply_to:
        c["in_reply_to_id"] = reply_to
    return c


PR = {"number": 7, "merged_at": "2026-11-04T18:00:00Z", "closed_at": "2026-11-04T18:00:00Z", "head": {"sha": "b" * 40}}
COMMENTS = [
    comment(1, CODEX, "**<sub>![P1 Badge](https://img.shields.io/badge/P1-orange)</sub> Reject output paths that alias an input**"),
    comment(2, "Copilot", "The output may alias the source file, including through a symlink or hard link."),
    comment(3, "Copilot", "Receipts are written inside the Git checkout."),
    comment(4, "alice", "Fixed in abc1234.", reply_to=3),
    comment(5, "bob", "Nit: rename this variable."),
]
REVIEWS = [{"user": {"login": "copilot-pull-request-reviewer[bot]"}, "body":
            '<img alt="High severity"> [Reject aliases](https://x/pull/7#discussion_r2) '
            '<img alt="Medium severity"> [Keep out of checkouts](https://x/pull/7#discussion_r3)'}]


class Threads(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t = {t["number"]: t for t in RT.threads_of(PR, COMMENTS, REVIEWS, resolved={3})}

    def test_one_record_per_thread_with_replies_counted(self):
        self.assertEqual(sorted(self.t), [1, 2, 3, 5])
        self.assertEqual((self.t[3]["replies"], self.t[3]["human_replied"]), (1, True))

    def test_resolution_comes_from_the_resolved_set(self):
        self.assertEqual(self.t[3]["state"], "resolved")
        self.assertEqual(self.t[1]["state"], "open")

    def test_severity_is_the_reviewers_own(self):
        self.assertEqual(self.t[1]["severity"], "high")    # Codex P1
        self.assertEqual(self.t[2]["severity"], "high")    # Copilot overview: High
        self.assertEqual(self.t[3]["severity"], "medium")  # Copilot overview: Medium
        self.assertEqual(self.t[5]["severity"], "note")    # unrated human comment

    def test_reviewer_families(self):
        self.assertEqual([self.t[n]["reviewer_family"] for n in (1, 2, 5)], ["codex", "copilot", "human"])
        self.assertEqual(RT.reviewer_family("github-advanced-security[bot]"), "codeql")
        self.assertEqual(RT.reviewer_family("semgrep-app[bot]"), "semgrep")
        self.assertEqual(RT.reviewer_family("renovate[bot]"), "other-bot")

    def test_title_drops_badges_and_markup(self):
        self.assertEqual(self.t[1]["title"], "Reject output paths that alias an input")

    def test_themes(self):
        self.assertEqual((self.t[1]["theme"], self.t[2]["theme"], self.t[3]["theme"]), ("path-alias", "path-alias", "private-leak"))
        self.assertEqual(RT.theme_of("Enforce the frozen source digests"), "provenance-pin")
        self.assertEqual(RT.theme_of("rename this variable"), "other")


def review_raw():
    return {"schema": RT.SCHEMA, "fetched_at": "2026-11-04T19:00:00+00:00", "limit": 30, "repos": {
        "O/pub": {"coverage": "ok", "head_sha": "c" * 40, "prs_read": 1, "alerts": RT.threads_of(PR, COMMENTS, REVIEWS, {3})},
        "O/gone": {"coverage": "not_readable", "error": "HTTP 404"}}}


class Receipt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = M.build(copy.deepcopy(RAW), review_raw())
        cls.roots = {x["id"]: x for x in cls.r["roots"]}

    def test_copilot_and_codex_on_the_same_defect_are_one_root(self):
        root = self.roots["O/pub|review_threads|path-alias|path-alias"]
        self.assertEqual((root["outstanding"], root["closed"]), (2, 0))
        self.assertEqual(root["advisories"], ["#7"])
        self.assertIn("one follow-up PR", root["fix"])

    def test_resolved_thread_is_closed(self):
        root = self.roots["O/pub|review_threads|private-leak|private-leak"]
        self.assertEqual((root["outstanding"], root["closed"], root["severity"]), (0, 1, None))

    def test_totals_and_lane(self):
        self.assertEqual(self.r["totals"]["review_threads"], {"outstanding": 3, "closed": 1, "deferred": 0})
        self.assertIn("pub:review-path-alias", [lane["id"] for lane in self.r["lanes"]])

    def test_coverage_names_scope_and_gaps(self):
        cov = self.r["coverage"]
        self.assertEqual(cov["O/priv"]["review_threads"], "not_in_scope")
        self.assertEqual(cov["O/gone"]["review_threads"], "not_readable")
        self.assertEqual(cov["O/gone"]["dependabot"], "absent")

    def test_alert_sources_are_unchanged_by_the_review_read(self):
        alone = M.build(copy.deepcopy(RAW))
        for source in ("dependabot", "code_scanning", "secret_scanning"):
            self.assertEqual(self.r["totals"][source], alone["totals"][source])

    def test_public_projection_holds_no_review_text_paths_or_prs(self):
        text = json.dumps(M.public_projection(self.r))
        for secret in ("alias", "checkout", "src/a.py", "#7", "discussion_r", "Copilot", "alice"):
            self.assertNotIn(secret, text)
        self.assertIn("review_threads", text)

    def test_build_command_reads_the_review_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw, review, out = Path(tmp) / "raw.json", Path(tmp) / "raw_review.json", Path(tmp) / "out"
            raw.write_text(json.dumps(RAW), encoding="utf-8")
            review.write_text(json.dumps(review_raw()), encoding="utf-8")
            self.assertEqual(M.main(["build", "--raw", str(raw), "--review", str(review), "--out", str(out)]), 0)
            receipt = json.loads((out / "MAROON_RECEIPT.json").read_text(encoding="utf-8"))
            self.assertEqual(receipt["totals"]["review_threads"]["outstanding"], 3)


class Fetch(unittest.TestCase):
    def test_fetch_reads_newest_first_and_records_the_head(self):
        older = dict(PR, number=6, merged_at="2026-11-01T00:00:00Z", closed_at="2026-11-01T00:00:00Z")
        calls = []

        def gh(args):
            path = args[1]
            calls.append(path)
            if path.endswith("commits/HEAD"):
                return 0, json.dumps({"sha": "d" * 40}), ""
            if "pulls?state=closed" in path:
                return 0, json.dumps([older, PR] if path.endswith("&page=1") else []), ""
            if path.endswith("/pulls/7/comments?per_page=100"):
                return 0, json.dumps([COMMENTS]), ""
            if path.endswith("/reviews?per_page=100"):
                return 0, json.dumps([REVIEWS]), ""
            return 0, json.dumps([[]]), ""

        raw = RT.fetch(["O/pub"], limit=2, gh=gh, resolved=lambda gh, repo, n: {3})
        entry = raw["repos"]["O/pub"]
        self.assertEqual((entry["coverage"], entry["head_sha"], entry["prs_read"]), ("ok", "d" * 40, 2))
        self.assertEqual(entry["window"], ["2026-11-01T00:00:00Z", "2026-11-04T18:00:00Z"])
        self.assertEqual(len(entry["alerts"]), 4)

    def test_unreadable_repo_is_a_gap_not_zero(self):
        raw = RT.fetch(["O/x"], limit=5, gh=lambda args: (1, "", "HTTP 404: Not Found"), resolved=lambda *a: set())
        self.assertEqual(raw["repos"]["O/x"]["coverage"], "not_readable")
        self.assertNotIn("alerts", raw["repos"]["O/x"])

    def test_graphql_adapter_feeds_the_gate_reader(self):
        page = {"data": {"repository": {"pullRequest": {"reviewThreads": {
            "pageInfo": {"hasNextPage": False, "endCursor": None},
            "nodes": [{"isResolved": True, "comments": {"nodes": [{"databaseId": 3}]}},
                      {"isResolved": False, "comments": {"nodes": [{"databaseId": 1}]}}]}}}}}
        seen = []

        def gh(args):
            seen.append(args)
            return 0, json.dumps(page), ""
        self.assertEqual(RT.resolved_via_graphql(gh, "O/pub", 7), {3})
        self.assertEqual(seen[0][:2], ["api", "graphql"])
        self.assertIn("number=7", seen[0])

    def test_ccr_reader(self):
        threads = [{"resolved": True, "comment_ids": [3, 4]}, {"resolved": False, "comment_ids": [1]}]
        self.assertEqual(RT.resolved_via_ccr(lambda args: (0, json.dumps(threads), ""), "O/pub", 7), {3})


if __name__ == "__main__":
    unittest.main()
