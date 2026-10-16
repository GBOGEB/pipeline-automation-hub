"""Issue_Register full-pagination negatives: issue ≠ causal root."""

import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from central import recensus  # noqa: E402


REPO = "GBOGEB/ABACUS"


def issue(number, state="open"):
    return {
        "number": number,
        "title": "Source-bound test issue",
        "state": state,
        "html_url": f"https://github.com/{REPO}/issues/{number}",
        "created_at": "2026-10-15T12:00:00Z",
        "updated_at": "2026-10-16T08:00:00Z",
        "closed_at": None,
        "labels": [{"name": "bd-candidate"}],
    }


def getter_from(items, *, reported_count=None, incomplete=False):
    def get(path):
        self_query = parse_qs(path.split("?", 1)[1])
        if self_query.get("q") != [f"repo:{REPO} is:issue is:open"]:
            raise ValueError("unrecognized scoped query")
        return {
            "total_count": (
                len(items) if reported_count is None else reported_count
            ),
            "incomplete_results": incomplete,
            "items": items,
        }
    return get


class FullIssueRegisterTests(unittest.TestCase):
    def test_two_native_issue_records_are_not_two_bd_roots(self):
        rows = recensus.retrieve_issue_register(
            getter_from([issue(99), issue(98)]), REPO, "open", 2
        )
        self.assertEqual([r["number"] for r in rows], [99, 98])
        self.assertTrue(all(r["bd_root_id"] is None for r in rows))
        self.assertTrue(all(r["accepted_root_closure"] is None for r in rows))
        self.assertEqual(rows[0]["labels"], ["bd-candidate"])

    def test_reported_total_and_page_members_must_match(self):
        with self.assertRaisesRegex(ValueError, "coverage incomplete"):
            recensus.retrieve_issue_register(
                getter_from([issue(11)] ,reported_count=2), REPO, "open", 2
            )

    def test_search_incomplete_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "incomplete or changing"):
            recensus.retrieve_issue_register(
                getter_from([issue(1)], incomplete=True), REPO, "open", 1
            )

    def test_wrong_repo_issue_url_rejected(self):
        bad = issue(12)
        bad["html_url"] = "https://github.com/GBOGEB/CODEX/issues/12"
        with self.assertRaisesRegex(ValueError, "wrong or duplicate"):
            recensus.retrieve_issue_register(
                getter_from([bad]), REPO, "open", 1
            )

    def test_no_duplicate_page_identity(self):
        with self.assertRaisesRegex(ValueError, "wrong or duplicate"):
            recensus.retrieve_issue_register(
                getter_from([issue(5), issue(5)]), REPO, "open", 2
            )

    def test_pull_request_record_never_enters_issue_register(self):
        bad = issue(35)
        bad["pull_request"] = {"url": "https://api.github.com/some-pr"}
        with self.assertRaisesRegex(ValueError, "wrong or duplicate"):
            recensus.retrieve_issue_register(
                getter_from([bad]), REPO, "open", 1
            )

    def test_invalid_population_or_repo_fails_closed(self):
        with self.assertRaises(ValueError):
            recensus.retrieve_issue_register(
                getter_from([]), REPO, "open", 1001
            )
        with self.assertRaises(ValueError):
            recensus.retrieve_issue_register(
                getter_from([]), "FOREIGN/ABACUS", "open", 0
            )


if __name__ == "__main__":
    unittest.main()
