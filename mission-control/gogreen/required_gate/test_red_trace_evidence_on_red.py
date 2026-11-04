"""Ensure the source-owned RED producer always leaves replayable evidence."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github/workflows/gogreen-red-trace.yml"


class SourceOwnedRedEvidenceTests(unittest.TestCase):
    def test_native_proposal_precedes_failing_offline_guard(self):
        content = WORKFLOW.read_text(encoding="utf-8")
        producer = content.index("- name: Trace master history (GET only)")
        proposal = content.index("- name: Admission ledger drift (trust -> authority, offline proposal)")
        checks = content.index("- name: Offline classification and guard tests (fail closed)")
        upload = content.index("- uses: actions/upload-artifact@")
        self.assertLess(producer, proposal)
        self.assertLess(proposal, checks)
        self.assertLess(checks, upload)
        self.assertIn("if: always()", content[checks:upload])
        self.assertIn("if: always()", content[upload:])

    def test_both_original_unittest_populations_remain_mandatory(self):
        content = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(
            "python -m unittest discover -s mission-control/gogreen/red_trace -p 'test_*.py' -v",
            content,
        )
        self.assertIn(
            "python -m unittest discover -s mission-control/gogreen/required_gate -p 'test_*.py' -v",
            content,
        )
        self.assertIn("python mission-control/gogreen/required_gate/admission.py --root .", content)
        self.assertIn("python mission-control/gogreen/red_trace/red_trace.py", content)
        self.assertIn("permissions:\n  contents: read\n  actions: read", content)
