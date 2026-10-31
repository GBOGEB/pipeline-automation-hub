"""Behavioural controls for scripts/ci/qa_trap.sh (runs real bash, no network)."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

HELPER = Path(__file__).resolve().parent / "qa_trap.sh"
LINE = '[ -f "{h}" ] && QA_TITLE="{t}" . "{h}"\n'


def run(body, title="My QA step", helper=HELPER):
    with tempfile.TemporaryDirectory() as d:
        script = Path(d) / "step.sh"
        script.write_text(LINE.format(h=helper, t=title) + body)
        env = dict(os.environ, RUNNER_TEMP=d)
        # GitHub's default bash invocation for run: steps
        p = subprocess.run(["bash", "--noprofile", "--norc", "-eo", "pipefail", str(script)],
                           capture_output=True, text=True, env=env, timeout=30)
        return p.returncode, p.stdout + p.stderr


# qa_trap.sh is sourced only by ubuntu run: steps. On Windows, Python >= 3.12.4 gives
# TemporaryDirectory an owner-only ACL that MSYS bash cannot read, and python3 is not on PATH.
@unittest.skipIf(os.name == "nt", "POSIX bash helper for ubuntu runners only")
class QaTrap(unittest.TestCase):
    def test_failure_emits_annotation_and_keeps_exit_code(self):
        rc, out = run("echo start\npython3 -c \"raise AssertionError('three viewports: overflow 12px')\"\necho never\n")
        self.assertEqual(rc, 1)
        self.assertIn("::error title=My QA step::", out)
        self.assertIn("AssertionError: three viewports: overflow 12px", out)
        self.assertNotIn("never", out)

    def test_success_is_silent_and_unchanged(self):
        rc, out = run("echo ok\necho done\n")
        self.assertEqual(rc, 0)
        self.assertNotIn("::error", out)
        self.assertIn("done", out)

    def test_explicit_exit_code_preserved(self):
        rc, out = run("echo 'FAIL: gate red'\nexit 7\n")
        self.assertEqual(rc, 7)
        self.assertIn("FAIL: gate red", out.split("::error", 1)[1])

    def test_set_u_and_pipefail_in_step_still_work(self):
        rc, out = run("set -euo pipefail\nfalse | cat\necho never\n")
        self.assertEqual(rc, 1)
        self.assertIn("::error", out)
        self.assertNotIn("never", out)

    def test_no_text_fallback(self):
        rc, out = run("exit 3\n")
        self.assertEqual(rc, 3)
        self.assertIn("exit 3 (no assertion text captured)", out)

    def test_title_sanitised_for_workflow_command(self):
        rc, out = run("exit 1\n", title="a: b, c")
        self.assertIn("::error title=a  b  c::", out)

    def test_missing_helper_is_noop(self):
        rc, out = run("echo ok\n", helper=Path("/nonexistent/qa_trap.sh"))
        self.assertEqual(rc, 0)
        self.assertNotIn("::error", out)


if __name__ == "__main__":
    unittest.main()
