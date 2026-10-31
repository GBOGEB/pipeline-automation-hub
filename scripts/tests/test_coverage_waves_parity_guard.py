import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import coverage_waves_parity_guard as g

CASES = {
    "pass": '<testcase classname="t" name="a"/>',
    "fail": '<testcase classname="t" name="b"><failure message="assert False"/></testcase>',
    "xpass": '<testcase classname="t" name="c"><failure message="[XPASS(strict)] pd"/></testcase>',
    "error": '<testcase classname="t" name="d"><error message="boom"/></testcase>',
    "skip": '<testcase classname="t" name="e"><skipped type="pytest.skip" message="no dep"/></testcase>',
    "xfail": '<testcase classname="t" name="f"><skipped type="pytest.xfail" message="pd"/></testcase>',
}


def junit(*kinds):
    body = "".join(CASES[k] for k in kinds)
    path = Path(tempfile.mkdtemp()) / "junit.xml"
    path.write_text(f'<testsuites><testsuite name="pytest">{body}</testsuite></testsuites>', encoding="utf-8")
    return path


class ParityGuardTest(unittest.TestCase):
    def test_counts_each_outcome_separately(self):
        c = g.count(junit(*CASES))["counts"]
        self.assertEqual(c, {"collected": 6, "passed": 1, "failed": 1, "errors": 1,
                             "skipped": 1, "xfailed": 1, "xpassed": 1})

    def test_zero_collected_is_a_failure(self):
        self.assertEqual(g.main([str(junit()), "--expected-min", "0"]), 1)

    def test_below_expected_min_fails(self):
        self.assertEqual(g.main([str(junit("pass")), "--expected-min", "2"]), 1)

    def test_xfail_is_not_a_pass_and_missing_xfail_fails(self):
        self.assertEqual(g.main([str(junit("pass", "xfail")), "--expected-min", "2", "--expect-xfail", "1"]), 0)
        self.assertEqual(g.main([str(junit("pass", "pass")), "--expected-min", "2", "--expect-xfail", "1"]), 1)

    def test_strict_xpass_and_skip_fail(self):
        self.assertEqual(g.main([str(junit("pass", "xpass")), "--expected-min", "2"]), 1)
        self.assertEqual(g.main([str(junit("pass", "skip")), "--expected-min", "2"]), 1)
        self.assertEqual(g.main([str(junit("pass", "skip")), "--expected-min", "2", "--max-skips", "1"]), 0)


if __name__ == "__main__":
    unittest.main()
