"""Fail-closed structural regression for CODE PURPLE M3 Actions workflow.

This checks the concrete duplicate-job and shell quoting regressions only.
GitHub Actions must still validate the full workflow and execute it natively.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import shlex
import unittest

_HERE = Path(__file__).resolve()
WORKFLOW = _HERE.parents[4] / '.github/workflows/code-purple-m3-lossless.yml'
EXPECTED_JOBS = ['m3-source-invariants', 'inherited-golden-thread']
EXPECTED_GREP = "grep -q '^Ran 36 M3 tests: PASS$' \"$RUNNER_TEMP/m3/m3_testflight.log\""


def validate_workflow(text: str) -> None:
    headers = re.findall(r'^  ([a-z][a-z0-9-]*):\s*$', text, flags=re.MULTILINE)
    if headers != EXPECTED_JOBS:
        raise ValueError(f'M3 workflow jobs must be unique and ordered: {headers!r}')
    for marker in ('name: Existing canonical M2 portal regressions',
                   'name: Generate and replay deterministic source-bound full handover',
                   'name: Existing native session projection builds on exact source'):
        if text.count(marker) != 1:
            raise ValueError(f'M3 step missing or duplicated: {marker}')
    commands = [line.strip() for line in text.splitlines() if 'grep -q' in line]
    if len(commands) != 2 or EXPECTED_GREP not in commands:
        raise ValueError('M3 count assertions missing, duplicated or malformed')
    for command in commands:
        try:
            tokens = shlex.split(command)
        except ValueError as exc:
            raise ValueError('M3 grep has unbalanced shell quoting') from exc
        if tokens[:2] != ['grep', '-q'] or len(tokens) != 4:
            raise ValueError('M3 grep must take one pattern and one path')
    if '\n "' in text:
        raise ValueError('Unexpected dedented shell fragment')


GOOD = '''name: CODE PURPLE M3 Lossless Stabilization
jobs:
  m3-source-invariants:
    steps:
      - name: M3 unit tests and counterfactual negative controls
        run: |
          grep -q '^Ran 36 M3 tests: PASS$' "$RUNNER_TEMP/m3/m3_testflight.log"
      - name: Existing canonical M2 portal regressions
        run: |
          grep -q '^Ran 12 M2 source-bound HTML tests: PASS$' "$RUNNER_TEMP/m3/m2_testflight.log"
      - name: Generate and replay deterministic source-bound full handover
  inherited-golden-thread:
    steps:
      - name: Existing native session projection builds on exact source
'''


class M3WorkflowContractTests(unittest.TestCase):
    def test_fixture_accepts(self):
        validate_workflow(GOOD)

    def test_reject_unbalanced_grep(self):
        bad = GOOD.replace("PASS$' \"$RUNNER_TEMP/m3/m3_testflight.log\"",
                           'PASS "$RUNNER_TEMP/m3/m3_testflight.log"')
        with self.assertRaises(ValueError):
            validate_workflow(bad)

    def test_reject_duplicate_job(self):
        with self.assertRaises(ValueError):
            validate_workflow(GOOD + '\n  inherited-golden-thread:\n')

    def test_reject_test_denominator_drift(self):
        with self.assertRaises(ValueError):
            validate_workflow(GOOD.replace('Ran 36 M3 tests', 'Ran 35 M3 tests'))

    def test_reject_duplicate_producer(self):
        with self.assertRaises(ValueError):
            validate_workflow(GOOD + '      - name: Generate and replay deterministic source-bound full handover\n')

    def test_repo_workflow(self):
        path = Path(os.environ.get('M3_WORKFLOW_SOURCE', str(WORKFLOW)))
        validate_workflow(path.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
