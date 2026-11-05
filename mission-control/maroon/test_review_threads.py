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

    def test_review_only_build_takes_the_review_read_time(self):
        receipt = M.build({"owner": "O", "fetched_at": "none", "repos": {}}, review_raw())
        self.assertEqual(receipt["fetched_at"], "2026-11-04T19:00:00+00:00")

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
        self.assertEqual(entry["threads_deferred_to_code_scanning"], 0)

    def test_codeql_threads_are_left_to_the_code_scanning_source(self):
        codeql = comment(9, "github-advanced-security[bot]", "## Clear-text logging of sensitive information")

        def gh(args):
            path = args[1]
            if path.endswith("commits/HEAD"):
                return 0, json.dumps({"sha": "d" * 40}), ""
            if "pulls?state=closed" in path:
                return 0, json.dumps([PR] if path.endswith("&page=1") else []), ""
            if path.endswith("/comments?per_page=100"):
                return 0, json.dumps([COMMENTS + [codeql]]), ""
            return 0, json.dumps([[]]), ""

        entry = RT.fetch(["O/pub"], limit=1, gh=gh, resolved=lambda *a: set())["repos"]["O/pub"]
        self.assertEqual(entry["threads_deferred_to_code_scanning"], 1)
        self.assertNotIn(9, [t["number"] for t in entry["alerts"]])

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



def closed_pr(number, closed, updated, merged=True, body=""):
    return {"number": number, "merged_at": closed if merged else None, "closed_at": closed, "updated_at": updated,
            "merge_commit_sha": "e" * 40 if merged else None, "head": {"sha": "f" * 40}, "body": body}


def paged(pages):
    """A fake `gh` serving closed-PR pages by number; full pages hold 100 entries, as the API does."""
    calls = []

    def gh(args):
        path = args[1]
        calls.append(path)
        page = int(path.rsplit("&page=", 1)[1])
        return 0, json.dumps(pages[page - 1] if page <= len(pages) else []), ""
    return gh, calls


def filler(start, n, closed, updated):
    return [closed_pr(start + i, closed, updated) for i in range(n)]


class Window(unittest.TestCase):
    """#1128 review (r4472364594, r4472368522): select by closure time, stop only when proven."""

    def test_recent_closure_behind_a_page_of_older_updates_is_found(self):
        # 100 PRs closed in January get comments in November; two quiet PRs closed in early November sit on page 2.
        page1 = filler(1000, 100, "2026-01-05T00:00:00Z", "2026-11-09T00:00:00Z")
        page2 = [closed_pr(7, "2026-11-05T00:00:00Z", "2026-11-05T00:00:00Z"),
                 closed_pr(6, "2026-11-04T00:00:00Z", "2026-11-04T00:00:00Z")]
        prs, proven = RT.recent_closed(paged([page1, page2])[0], "O/pub", 2)
        self.assertEqual(([p["number"] for p in prs], proven), ([7, 6], True))

    def test_stops_as_soon_as_later_pages_cannot_hold_a_newer_closure(self):
        page1 = [closed_pr(i, f"2026-11-{30 - i:02d}T00:00:00Z", f"2026-11-{30 - i:02d}T00:00:00Z") for i in range(100)]
        gh, calls = paged([page1, filler(500, 100, "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z")])
        prs, proven = RT.recent_closed(gh, "O/pub", 3)
        self.assertEqual(([p["number"] for p in prs], proven, len(calls)), ([0, 1, 2], True, 1))

    def test_page_budget_without_proof_is_a_coverage_gap(self):
        pages = [filler(i * 100, 100, "2026-01-01T00:00:00Z", "2026-11-09T00:00:00Z") for i in range(3)]
        prs, proven = RT.recent_closed(paged(pages)[0], "O/pub", 2, max_pages=2)
        self.assertFalse(proven)

        def gh(args):
            path = args[1]
            if path.endswith("commits/HEAD"):
                return 0, json.dumps({"sha": "d" * 40}), ""
            if "pulls?state=closed" in path:
                return 0, json.dumps(pages[0]), ""
            return 0, json.dumps([[]]), ""
        saved = RT.MAX_PAGES
        RT.MAX_PAGES = 2
        try:
            entry = RT.fetch(["O/pub"], limit=2, gh=gh, resolved=lambda *a: set())["repos"]["O/pub"]
        finally:
            RT.MAX_PAGES = saved
        self.assertEqual(entry["coverage"], "window_unproven")

    def test_raw_records_the_sample_and_each_threads_anchor(self):
        pr = closed_pr(7, "2026-11-04T18:00:00Z", "2026-11-04T18:00:00Z", body="Refs #2160 and #7 and GBOGEB/x#99")
        hunk = comment(1, CODEX, "Reject output paths that alias an input")
        hunk["diff_hunk"] = "@@ -1,2 +1,3 @@\n context line\n+    out.write_text(report_body)\n+x"

        def gh(args):
            path = args[1]
            if path.endswith("commits/HEAD"):
                return 0, json.dumps({"sha": "d" * 40}), ""
            if "pulls?state=closed" in path:
                return 0, json.dumps([pr]), ""
            if path.endswith("/comments?per_page=100"):
                return 0, json.dumps([[hunk]]), ""
            return 0, json.dumps([[]]), ""
        entry = RT.fetch(["O/pub"], limit=5, gh=gh, resolved=lambda *a: set())["repos"]["O/pub"]
        self.assertEqual(entry["prs"], [{"number": 7, "merged": True, "closed_at": "2026-11-04T18:00:00Z",
                                         "merge_commit_sha": "e" * 40, "refs": [2160]}])
        # The target is the hunk's last line, however short (#1129 r4473193611); no earlier line stands in.
        self.assertEqual((entry["alerts"][0]["anchor"], entry["alerts"][0]["anchor_side"]), ("x", "added"))


def scoped(alerts_by_pr, prs, merged=True):
    alerts = []
    for pr_number, ids in alerts_by_pr.items():
        pr = closed_pr(pr_number, "2026-11-04T18:00:00Z", "2026-11-04T18:00:00Z", merged=merged)
        alerts += [t for t in RT.threads_of(pr, [comment(i, CODEX, "Reject output paths that alias an input") for i in ids], [], set())]
    return {"schema": RT.SCHEMA, "fetched_at": "2026-11-04T19:00:00+00:00", "limit": 30, "repos": {
        "O/pub": {"coverage": "ok", "head_sha": "c" * 40, "prs_read": len(prs), "prs": [{"number": n} for n in prs], "alerts": alerts}}}


class Scope(unittest.TestCase):
    EMPTY = {"owner": "O", "fetched_at": "none", "repos": {}}

    def test_threads_on_unmerged_prs_are_deferred_not_outstanding(self):
        """#2236 review (r4472173680): a change that never landed is not post-merge debt."""
        receipt = M.build(self.EMPTY, scoped({8: [41]}, [8], merged=False))
        self.assertEqual(receipt["totals"]["review_threads"], {"outstanding": 0, "closed": 0, "deferred": 1})
        self.assertEqual(receipt["lanes"], [])

    def test_overrides_move_a_thread_to_its_corrected_root(self):
        """#2236 review (r4472139908): a deep-read re-theme must reach the roots and the fix list."""
        receipt = M.build(self.EMPTY, scoped({7: [1, 2]}, [7]), {"2": {"theme": "wave-claims"}})
        roots = {r["subject"]: r["alerts"] for r in receipt["roots"]}
        self.assertEqual((roots["path-alias"], roots["wave-claims"]), ([1], [2]))

    def test_rethemed_thread_is_not_counted_as_resolved_or_new(self):
        review = scoped({7: [1]}, [7])
        old = M.build(self.EMPTY, review)
        new = M.build(self.EMPTY, review, {"1": {"theme": "wave-claims"}})
        delta = M.diff(old, new)
        self.assertEqual((delta["alerts_left"], delta["alerts_joined"], delta["roots_cleared"],
                          delta["roots_new"]), (0, 0, 0, 0))

    def test_receipt_records_the_sample_and_each_alerts_pr(self):
        receipt = M.build(self.EMPTY, scoped({7: [1], 8: [2]}, [7, 8]))
        self.assertEqual(receipt["review_scope"]["O/pub"]["prs"], [7, 8])
        root = next(r for r in receipt["roots"] if r["source"] == "review_threads")
        self.assertEqual(root["alert_prs"], {"1": 7, "2": 8})

    def test_a_thread_that_ages_out_is_evicted_not_resolved(self):
        """#1128 review (r4472368445): leaving the sample is not a fix."""
        old = M.build(self.EMPTY, scoped({7: [1], 8: [2]}, [7, 8]))
        aged = M.build(self.EMPTY, scoped({8: [2]}, [8, 9]))       # PR 7 left the window
        fixed = M.build(self.EMPTY, scoped({8: [2]}, [7, 8, 9]))    # PR 7 still sampled, thread 1 resolved
        d = M.diff(old, aged)
        self.assertEqual((d["alerts_evicted"], d["alerts_left"], d["roots_cleared"]), (1, 0, 0))
        self.assertEqual(M.delta_counts(d)["alerts_evicted"], 1)
        d = M.diff(old, fixed)
        self.assertEqual((d["alerts_evicted"], d["alerts_left"]), (0, 1))

    def test_a_root_that_only_aged_out_is_not_cleared(self):
        old = M.build(self.EMPTY, scoped({7: [1]}, [7]))
        d = M.diff(old, M.build(self.EMPTY, scoped({}, [9])))
        self.assertEqual((d["alerts_evicted"], d["roots_cleared"], d["left"]), (1, 0, []))

    def test_receipts_without_a_sample_keep_the_old_behaviour(self):
        old, new = M.build(self.EMPTY, scoped({7: [1]}, [7])), M.build(self.EMPTY, scoped({}, [9]))
        old.pop("review_scope")
        d = M.diff(old, new)
        self.assertEqual((d["alerts_evicted"], d["alerts_left"]), (0, 1))

    def test_missing_repository_sample_keeps_the_old_behaviour(self):
        def without_prs(alerts_by_pr, prs):
            review = scoped(alerts_by_pr, prs)
            del review["repos"]["O/pub"]["prs"]
            return M.build(self.EMPTY, review)

        old = M.build(self.EMPTY, scoped({7: [1]}, [7]))
        new = without_prs({}, [])
        d = M.diff(old, new)
        self.assertEqual((d["alerts_evicted"], d["alerts_left"], d["roots_cleared"]), (0, 1, 1))

        old = without_prs({7: [1]}, [7])
        new = M.build(self.EMPTY, scoped({}, []))
        d = M.diff(old, new)
        self.assertEqual((d["alerts_evicted"], d["alerts_left"], d["roots_cleared"]), (0, 1, 1))

    def test_build_command_reads_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw, review, over, out = (Path(tmp) / n for n in ("raw.json", "review.json", "over.json", "out"))
            raw.write_text(json.dumps(self.EMPTY), encoding="utf-8")
            review.write_text(json.dumps(scoped({7: [1, 2]}, [7])), encoding="utf-8")
            over.write_text(json.dumps({"2": {"theme": "wave-claims"}}), encoding="utf-8")
            self.assertEqual(M.main(["build", "--raw", str(raw), "--review", str(review), "--review-overrides", str(over),
                                     "--out", str(out)]), 0)
            subjects = {r["subject"] for r in json.loads((out / "MAROON_RECEIPT.json").read_text(encoding="utf-8"))["roots"]}
            self.assertIn("wave-claims", subjects)



class ReviewFollowUps(unittest.TestCase):
    """Codex on #1129: r4472801630 (unproven windows), r4473193611 (anchors), r4473193623 (refs)."""
    EMPTY = {"owner": "O", "fetched_at": "none", "repos": {}}

    def test_an_unproven_window_never_proves_an_eviction(self):
        old = M.build(self.EMPTY, scoped({7: [1]}, [7]))
        partial = scoped({}, [9])
        partial["repos"]["O/pub"]["coverage"] = "window_unproven"
        d = M.diff(old, M.build(self.EMPTY, partial))
        self.assertEqual((d["alerts_evicted"], d["alerts_left"]), (0, 1))
        unproven_old = scoped({7: [1]}, [7])
        unproven_old["repos"]["O/pub"]["coverage"] = "window_unproven"
        d = M.diff(M.build(self.EMPTY, unproven_old), M.build(self.EMPTY, scoped({}, [9])))
        self.assertEqual((d["alerts_evicted"], d["alerts_left"]), (0, 1))

    def test_scope_records_whether_the_window_was_proven(self):
        partial = scoped({7: [1]}, [7])
        partial["repos"]["O/pub"]["coverage"] = "window_unproven"
        self.assertFalse(M.build(self.EMPTY, partial)["review_scope"]["O/pub"]["proven"])
        self.assertTrue(M.build(self.EMPTY, scoped({7: [1]}, [7]))["review_scope"]["O/pub"]["proven"])

    def test_anchor_is_the_target_line_even_when_short(self):
        hunk = "@@ -1,3 +1,3 @@\n     long enough context line\n+    x = 1"
        self.assertEqual(RT.anchor_of(hunk), {"text": "x = 1", "side": "added"})

    def test_anchor_keeps_a_deleted_target_line(self):
        hunk = "@@ -1,3 +1,2 @@\n     long enough context line\n-    os.replace(tmp, out)"
        self.assertEqual(RT.anchor_of(hunk), {"text": "os.replace(tmp, out)", "side": "deleted"})

    def test_anchor_of_a_context_or_blank_target(self):
        self.assertEqual(RT.anchor_of("@@ -1 +1 @@\n  return value"), {"text": "return value", "side": "context"})
        self.assertIsNone(RT.anchor_of("@@ -1,2 +1,2 @@\n+real line\n+   "))
        self.assertIsNone(RT.anchor_of(None))

    def test_anchor_skips_the_no_newline_marker(self):
        """#1129 r4477419118: a target on a file's last line, with no trailing newline, keeps its anchor."""
        for sign, side in (("+", "added"), ("-", "deleted"), (" ", "context")):
            with self.subTest(side=side):
                hunk = f"@@ -1,2 +1,2 @@\n     long enough context line\n{sign}    write(final)\n\\ No newline at end of file"
                self.assertEqual(RT.anchor_of(hunk), {"text": "write(final)", "side": side})

    def test_threads_carry_the_anchor_and_its_side(self):
        c = comment(1, CODEX, "Reject output paths that alias an input")
        c["diff_hunk"] = "@@ -4,2 +4,1 @@\n context line here\n-    shutil.copy(a, b)"
        t = RT.threads_of(PR, [c], [], set())[0]
        self.assertEqual((t["anchor"], t["anchor_side"]), ("shutil.copy(a, b)", "deleted"))

    def test_refs_of_every_length(self):
        body = "Refs #5, #42, #1234567 and #0; not GBOGEB/x#99, abc#3 or #7 itself"
        self.assertEqual(RT.refs_of(body, 7), [5, 42, 1234567])


if __name__ == "__main__":
    unittest.main()
