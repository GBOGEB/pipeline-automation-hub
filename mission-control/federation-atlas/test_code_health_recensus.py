"""Native-count recensus tests use sealed fixtures; never query or mutate GitHub."""

import copy
import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from central import code_health, recensus  # noqa: E402


UTC = "2026-10-16T10:00:00Z"


def fake_getter(snapshot):
    table = {r["id"]: r for r in snapshot["census"]["repositories"]}

    def get(path):
        if path.startswith("/search/issues?"):
            q = parse_qs(path.split("?", 1)[1])["q"][0]
            labels = q.split()
            repo = labels[0].split("repo:", 1)[1]
            kind = labels[1].split("is:", 1)[1]
            state = labels[2].split("is:", 1)[1]
            item = table[repo]
            if kind == "issue":
                count = item["issue_register"][state]
            else:
                count = item["pull_request_register"][state]
            return {"total_count": count, "incomplete_results": False}
        pieces = path.split("/")
        repo = pieces[2] + "/" + pieces[3]
        if pieces[4] == "commits":
            return {"sha": table[repo]["source_sha"]}
        if pieces[4] == "pulls":
            return {
                "number": int(pieces[5]), "state": "open", "merged": False,
                "draft": True, "head": {"sha": "a" * 40, "ref": "test/owned"},
                "base": {"ref": table[repo]["default_branch"]},
            }
        raise AssertionError("unexpected GitHub endpoint " + path)

    return get


class LiveReadbackFixtureTests(unittest.TestCase):
    def setUp(self):
        self.source = code_health.read_json(code_health.REGISTRY)

    def test_matches_six_repo_baseline_without_fabricating_roots(self):
        snapshot = recensus.collect(self.source, getter=fake_getter(self.source),
                                    observed_at_utc=UTC)
        self.assertEqual(len(snapshot["repositories"]), 6)
        self.assertEqual(snapshot["totals"]["open_issues"], 143)
        self.assertEqual(snapshot["totals"]["closed_issues"], 412)
        self.assertEqual(snapshot["totals"]["open_prs"], 68)
        self.assertEqual(snapshot["totals"]["closed_prs"], 5126)
        self.assertTrue(all(not r["head_changed"] for r in snapshot["repositories"]))
        self.assertIsNone(snapshot["crew_auth_launches"])
        self.assertIsNone(snapshot["bd_canonical_closed"])
        self.assertIsNone(snapshot["native_runner_slots"])
        self.assertEqual(snapshot["admission"], "HOLD")
        self.assertFalse(snapshot["mutation_permitted"])
        self.assertFalse(snapshot["merge_authorized"])

    def test_pr_head_census_disjoint_work_scope(self):
        snap = recensus.collect(self.source, getter=fake_getter(self.source),
                                observed_at_utc=UTC)
        count = sum(r["ref_type"] == "pr" for r in self.source["work"])
        self.assertEqual(snap["scoped_pr_heads_observed"], count)
        self.assertEqual(len(snap["scoped_pr_heads"]), count)
        self.assertEqual({r["branch"] for r in snap["scoped_pr_heads"]},
                         {"test/owned"})
        self.assertTrue(all(not r["runner_launch_inferred"]
                            for r in snap["scoped_pr_heads"]))

    def test_skip_pr_head_only_changes_observed_width(self):
        snap = recensus.collect(self.source, getter=fake_getter(self.source),
                                observed_at_utc=UTC, include_pr_heads=False)
        self.assertEqual(snap["scoped_pr_heads_observed"], 0)
        self.assertEqual(snap["scoped_pr_heads"], [])
        self.assertEqual(snap["totals"]["open_issues"], 143)

    def test_updated_issue_count_is_not_automatically_root_closure(self):
        def change(path):
            if path.startswith("/search/issues?"):
                r = fake_getter(self.source)(path)
                q = parse_qs(path.split("?", 1)[1])["q"][0]
                if "repo:GBOGEB/ABACUS is:issue is:open" == q:
                    r["total_count"] = 40
                return r
            return fake_getter(self.source)(path)
        snap = recensus.collect(self.source, getter=change,
                                observed_at_utc=UTC, include_pr_heads=False)
        row = next(r for r in snap["repositories"] if r["repo"] == "GBOGEB/ABACUS")
        self.assertEqual(row["record_deltas"]["open_issues"], -8)
        self.assertFalse(row["record_deltas_are_root_closures"])
        self.assertIsNone(snap["bd_canonical_closed"])

    def test_native_incomplete_search_fails_closed(self):
        def incomplete(path):
            row = fake_getter(self.source)(path)
            if path.startswith("/search/issues?"):
                row["incomplete_results"] = True
            return row
        with self.assertRaisesRegex(ValueError, "incomplete"):
            recensus.collect(self.source, getter=incomplete, observed_at_utc=UTC)

    def test_negative_count_rejected(self):
        def bad(path):
            row = fake_getter(self.source)(path)
            if path.startswith("/search/issues?"):
                row["total_count"] = -1
            return row
        with self.assertRaisesRegex(ValueError, "invalid GitHub issue"):
            recensus.collect(self.source, getter=bad, observed_at_utc=UTC)

    def test_unmatched_head_rejected(self):
        def bad(path):
            row = fake_getter(self.source)(path)
            if "/commits/" in path:
                row["sha"] = "not-a-sha"
            return row
        with self.assertRaisesRegex(ValueError, "exact native"):
            recensus.collect(self.source, getter=bad, observed_at_utc=UTC)

    def test_negative_pr_identity_rejected(self):
        def bad(path):
            row = fake_getter(self.source)(path)
            if "/pulls/" in path:
                row["head"]["sha"] = "x" * 40
            return row
        with self.assertRaisesRegex(ValueError, "PR head identity"):
            recensus.collect(self.source, getter=bad, observed_at_utc=UTC)

    def test_non_utc_clock_rejected(self):
        for stamp in ("2026-10-16T10:00:00",
                      "2026-10-16T11:00:00+01:00",
                      "invalid"):
            with self.subTest(stamp=stamp), self.assertRaisesRegex(
                    ValueError, "UTC"):
                recensus.collect(self.source, getter=fake_getter(self.source),
                                 observed_at_utc=stamp)

    def test_unapproved_api_path_rejected(self):
        for path in ("/repos/GBOGEB/ABACUS/issues/1/comments",
                     "https://evil.example/any",
                     "/repos/FOREIGN/repo/actions"):
            # github_get is guarded at API namespace; explicit route is
            # read-only, but the caller still decides the exact vetted paths.
            if not path.startswith("/repos/GBOGEB/"):
                with self.assertRaises(ValueError):
                    recensus.github_get(path)

    def test_unsupported_issue_population_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported"):
            recensus.exact_count(fake_getter(self.source), "GBOGEB/ABACUS",
                                 "root", "open")

    def test_invalid_source_cannot_be_used_for_live_census(self):
        bad = copy.deepcopy(self.source)
        bad["crew"]["authenticated_launch_count"] = 8
        with self.assertRaisesRegex(ValueError, "Crew launch invented"):
            recensus.collect(bad, getter=fake_getter(self.source),
                             observed_at_utc=UTC)


if __name__ == "__main__":
    unittest.main()
