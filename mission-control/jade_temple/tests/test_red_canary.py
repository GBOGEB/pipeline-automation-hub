"""RED CANARY (JADE J3). Never merge: this test fails on purpose.

It proves the hub master ruleset (25789280) blocks a PR whose required
`GOGREEN required gate` is red. The PR is closed unmerged once the block is observed.
"""
import unittest


class RedCanary(unittest.TestCase):
    def test_deliberately_red(self):
        self.fail("JADE_RED_CANARY: deliberate failure; the platform must block this merge")


if __name__ == "__main__":
    unittest.main()
