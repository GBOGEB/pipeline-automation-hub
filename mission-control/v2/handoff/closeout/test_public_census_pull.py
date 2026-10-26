"""Offline negative regression for the public GET-only CENSUS adapter."""
from datetime import datetime, timezone
import json
import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import public_census_pull as census

CLOCK = datetime(2026, 10, 18, 14, 8, tzinfo=timezone.utc)


def fixture(*, private=False, malformed_sha=False, short_page=False,
            duplicate=False, pr_in_issues=False):
    called = []
    def get(path):
        called.append(path)
        if path.startswith("/search/issues?"):
            parsed = parse_qs(urlsplit(path).query)
            query = parsed["q"][0]
            if "is:pr" in query:
                return {"total_count": 1, "items":[{"number":10}], "incomplete_results":False}
            rows = [
                {"number":1,"created_at":"2026-10-17T12:00:00Z"},
                {"number":2 if not duplicate else 1,"created_at":"2026-10-01T12:00:00Z"},
            ]
            if short_page:
                rows.pop()
            if pr_in_issues:
                rows[0]["pull_request"] = {}
            return {"total_count":2,"items":rows,"incomplete_results":False}
        if "/branches/" in path:
            return {"commit":{"sha":("z"*40 if malformed_sha else "a"*40)},
                    "protected":False}
        if path.startswith("/repos/"):
            repo = path.split("/repos/",1)[1]
            return {"full_name":repo,"default_branch":dict(census.PUBLIC).get(repo),
                    "private":private}
        raise AssertionError("unexpected route")
    return get, called


class CensusTests(unittest.TestCase):
    def test_all_four_repos_complete_and_prs_not_counted_as_issues(self):
        get, calls = fixture()
        d = census.collect(get, CLOCK)
        self.assertEqual(len(d["repositories"]), 4)
        self.assertEqual((d["ordinary_open_issues"], d["open_prs"]), (8, 4))
        self.assertEqual(d["age_bins"], [4, 0, 4, 0])
        self.assertIsNone(d["causal_bd_roots_closed"])
        self.assertIsNone(d["comparable_main_coverage"])
        self.assertIsNone(d["accepted_rex"])
        self.assertEqual(d["merge_admission"],"HOLD")
        self.assertFalse(d["authority_transfer"])
        self.assertTrue(all(c.startswith("/repos/") or c.startswith("/search/issues?") for c in calls))
        self.assertNotIn("cryoplant-project",json.dumps(d))

    def test_private_source_does_not_leak_into_public(self):
        with self.assertRaisesRegex(ValueError,"private"):
            census.collect(fixture(private=True)[0], CLOCK)

    def test_invalid_sha_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"exact"):
            census.collect(fixture(malformed_sha=True)[0],CLOCK)

    def test_missing_paginated_issue_not_replaced_with_zero(self):
        with self.assertRaisesRegex(ValueError,"incomplete issue"):
            census.collect(fixture(short_page=True)[0],CLOCK)

    def test_duplicate_issue_object_rejected(self):
        with self.assertRaisesRegex(ValueError,"duplicate"):
            census.collect(fixture(duplicate=True)[0],CLOCK)

    def test_pr_labeled_as_issue_rejected(self):
        with self.assertRaisesRegex(ValueError,"PR/duplicate"):
            census.collect(fixture(pr_in_issues=True)[0],CLOCK)

    def test_naive_clock_rejected(self):
        with self.assertRaisesRegex(ValueError,"timezone"):
            census.collect(fixture()[0],CLOCK.replace(tzinfo=None))

    def test_non_github_get_rejected_before_network(self):
        with self.assertRaisesRegex(ValueError,"unsafe"):
            census.get_json("https://invalid.example.invalid/x")

    def test_restricted_repo_cannot_be_added_without_owner_change(self):
        self.assertEqual(len(census.PUBLIC),4)
        self.assertTrue(all(repo.startswith("GBOGEB/") for repo,_ in census.PUBLIC))
        self.assertFalse(any("cryoplant-project" in repo for repo,_ in census.PUBLIC))

    def test_no_provider_token_in_serialized_output(self):
        encoded=json.dumps(census.collect(fixture()[0],CLOCK))
        self.assertNotIn("GITHUB_TOKEN", encoded)
        self.assertNotIn("Bearer", encoded)


if __name__=="__main__":
    unittest.main()
