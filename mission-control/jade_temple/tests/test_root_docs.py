"""Root docs keep one masthead, one nav footer and resolvable links (tools/root_docs.py)."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import root_docs as rd  # noqa: E402

ORDER = (("A.md", "JT-A", "A", "ACTIVE"), ("00_START_HERE.md", "JT-00", "Index", "ACTIVE"))
TODAY = "2026-10-31"


class RootDocs(unittest.TestCase):
    def test_committed_root_docs_are_canonical(self):
        self.assertEqual(rd.problems(), [])

    def tmp(self, pages):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        root = Path(d.name)
        for name, text in pages.items():
            (root / name).write_text(text, encoding="utf-8", newline="\n")
        return root

    def canonical(self, body_a="Body.\n"):
        root = self.tmp({"A.md": "# A\n\n" + body_a, "00_START_HERE.md": "# Index\n\nBody.\n"})
        rd.write(root, ORDER, TODAY)
        return root

    def test_write_is_idempotent_and_keeps_body(self):
        root = self.canonical("Body with [a link](00_START_HERE.md).\n")
        first = (root / "A.md").read_text(encoding="utf-8")
        self.assertEqual(rd.write(root, ORDER, "2027-01-01"), ([], []))
        self.assertEqual((root / "A.md").read_text(encoding="utf-8"), first)
        self.assertIn("Body with [a link](00_START_HERE.md).", first)
        self.assertIn("**Updated** 2026-10-31", first)
        self.assertTrue(first.endswith("**Nav:** [Index](00_START_HERE.md) · [Index →](00_START_HERE.md)\n"))
        self.assertEqual(rd.problems(root, ORDER, {}, TODAY), [])

    def test_banner_above_h1_fails_and_is_not_rewritten(self):
        root = self.tmp({"A.md": "**N+12 update:** new.\n\n# A\n", "00_START_HERE.md": "# Index\n"})
        self.assertEqual(rd.write(root, ORDER, TODAY)[1], ["A.md"])
        self.assertTrue(any("first line is not the H1" in p for p in rd.problems(root, ORDER, {}, TODAY)))

    def test_broken_link_fails_outside_code_only(self):
        root = self.canonical("[gone](site/missing.html) and [web](https://example.org)\n\n```\n[x](nope.md)\n```\n")
        self.assertEqual(rd.problems(root, ORDER, {}, TODAY), ["A.md: broken link site/missing.html"])

    def test_tilde_and_longer_fences_match_their_own_delimiter(self):
        root = self.canonical("~~~md\n[x](t1.md)\n```\n[y](t2.md)\n~~~\n[a](gone1.md)\n\n"
                              "````\n```\n[z](t3.md)\n```\n````\n[b](gone2.md)\n")
        self.assertEqual(rd.problems(root, ORDER, {}, TODAY),
                         ["A.md: broken link gone1.md", "A.md: broken link gone2.md"])

    def test_titled_angle_and_reference_links_are_checked(self):
        root = self.canonical('[t](gone.md "Title") [a](<sp ace.md>) [ok](00_START_HERE.md \'T\')\n\n'
                              "[ref][r]\n\n[r]: refgone.md\n[i]: <00_START_HERE.md> \"Index\"\n")
        self.assertEqual(rd.problems(root, ORDER, {}, TODAY),
                         ["A.md: broken link gone.md", "A.md: broken link sp ace.md", "A.md: broken link refgone.md"])

    def test_h1_only_page_reports_instead_of_crashing(self):
        root = self.tmp({"A.md": "# A\n", "00_START_HERE.md": "# Index\n"})
        found = rd.problems(root, ORDER, {}, TODAY)
        self.assertIn("A.md: masthead/footer not canonical (run root_docs.py --write)", found)
        self.assertIn("00_START_HERE.md: masthead/footer not canonical (run root_docs.py --write)", found)

    def test_unlisted_root_page_and_future_date_fail(self):
        root = self.canonical()
        (root / "NEW.md").write_text("# New\n", encoding="utf-8", newline="\n")
        found = rd.problems(root, ORDER, {}, "2026-10-30")
        self.assertIn("NEW.md: root page is neither in ORDER nor DEFERRED", found)
        self.assertIn("A.md: Updated 2026-10-31 is after 2026-10-30", found)


if __name__ == "__main__":
    unittest.main()
