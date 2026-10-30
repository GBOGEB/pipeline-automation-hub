"""The slow-burn crew is bounded; no merge/release or external mutation."""
from pathlib import Path
import unittest

WORKFLOW = Path(__file__).resolve().parents[3] / ".github/workflows/jade-crew-slowburn.yml"


class SlowBurnSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_daily_default_branch_only_after_governed_land(self):
        self.assertIn("cron: '13 4 * * *'", self.text)
        self.assertIn("github.ref == 'refs/heads/master'", self.text)

    def test_no_write_or_merge_authority(self):
        self.assertIn("contents: read", self.text)
        self.assertNotIn("contents: write", self.text)
        self.assertIn("'merge_admission': 'HOLD'", self.text)
        self.assertIn("'formal_credit_delta': 0", self.text)

    def test_bounded_nonduplicative_fanout(self):
        self.assertIn("max-parallel: 3", self.text)
        self.assertIn("timeout-minutes: 30", self.text)
        self.assertIn("cancel-in-progress: true", self.text)
        self.assertIn("for repeat in 1 2 3", self.text)

    def test_exact_source_and_receipts(self):
        self.assertIn('test "$(git rev-parse HEAD)" = "$EXPECTED_SHA"', self.text)
        self.assertIn("slowburn/receipt.json", self.text)
        self.assertIn("retention-days: 14", self.text)


if __name__ == "__main__":
    unittest.main()
