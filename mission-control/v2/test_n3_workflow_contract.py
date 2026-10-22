"""N11 regression controls for Mission Control native evidence testflight.

Source-bound static invariants plus executable coverage.py CLI preflight. Never
promote a green test into merge, security, or accepted causal-root authority.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "mission-control-n3-evidence.yml"
GOOD = "python -m coverage json -o /tmp/n3-coverage.json"
BAD = "python -m coverage json --output=/tmp/n3-coverage.json"


def workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def coverage_command_is_valid(text: str) -> bool:
    return text.count(GOOD) == 1 and BAD not in text


def checkout_is_bound(text: str) -> bool:
    return (
        'ref: ${{ github.event.pull_request.head.sha || github.sha }}' in text
        and 'run: test "$(git rev-parse HEAD)" = "$SOURCE_SHA"' in text
        and "permissions:\n  contents: read" in text
    )


class N11WorkflowContractTests(unittest.TestCase):
    def test_native_coverage_json_output_uses_supported_short_option(self):
        self.assertTrue(coverage_command_is_valid(workflow()))

    def test_reverse_regression_rejects_the_old_unsupported_long_option(self):
        self.assertFalse(coverage_command_is_valid(workflow().replace(GOOD, BAD)))

    def test_checkout_and_repository_permissions_are_fail_closed(self):
        src = workflow()
        self.assertTrue(checkout_is_bound(src))
        self.assertFalse(checkout_is_bound(src.replace(
            'run: test "$(git rev-parse HEAD)" = "$SOURCE_SHA"',
            "run: echo skipped", 1)))

    def test_python_311_and_312_are_separate_matrix_lanes(self):
        src = workflow()
        self.assertIn("python-version: ['3.11', '3.12']", src)
        self.assertIn("fail-fast: false", src)
        self.assertNotIn("python-version: ['3.10']", src)

    def test_nine_module_denominators_and_negative_coverage_gates_preserved(self):
        src = workflow()
        names = (
            "n3_continuation.py", "n3_integrity.py", "n3_metrics.py",
            "n3_dashboard.py", "n3_native_join.py", "n3_wave_federation.py",
            "n3_workflow_census.py", "n3_g3a_assessment.py", "n3_master_dags_bridge.py",
        )
        for name in names:
            with self.subTest(module=name):
                self.assertEqual(src.count("'" + name + "'"), 1)
        for invariant in (
            "--branch --source=mission-control/v2",
            "assert len(s)==9", "assert denominator>0",
            "assert pct>=80", "100*branches/branch_total>=80",
            "'HOLD'", "if-no-files-found: warn",
        ):
            with self.subTest(invariant=invariant):
                self.assertIn(invariant, src)

    def test_nine_module_reverse_pressure_preserves_source_and_floor(self):
        src = workflow()
        eight = (
            "n3_continuation.py", "n3_integrity.py", "n3_metrics.py",
            "n3_dashboard.py", "n3_native_join.py", "n3_wave_federation.py",
            "n3_workflow_census.py", "n3_g3a_assessment.py", "n3_master_dags_bridge.py",
        )
        self.assertEqual(src.count("assert len(s)==9"), 1)
        self.assertNotIn("assert len(s)==6", src)
        for name in eight:
            with self.subTest(missing_module=name):
                changed = src.replace("'" + name + "'", "'unregistered.py'", 1)
                self.assertFalse(all(changed.count("'" + item + "'") == 1 for item in eight))
        self.assertIn("assert pct>=80", src)
        self.assertIn("100*branches/branch_total>=80", src)
        self.assertNotIn("assert pct>=0", src)

    def test_live_coverage_cli_positive_and_negative_output_contracts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sample = root / "probe.py"
            sample.write_text("value = 1\nif value:\n    value += 1\n", encoding="utf-8")
            output = root / "probe.json"
            env = dict(__import__("os").environ)
            env["COVERAGE_FILE"] = str(root / ".coverage")
            good_run = subprocess.run(
                [sys.executable, "-m", "coverage", "run", "--branch", str(sample)],
                cwd=root, env=env, text=True, capture_output=True,
                check=False, timeout=15,
            )
            self.assertEqual(good_run.returncode, 0, good_run.stderr)
            short = subprocess.run(
                [sys.executable, "-m", "coverage", "json", "-o", str(output)],
                cwd=root, env=env, text=True, capture_output=True,
                check=False, timeout=15,
            )
            self.assertEqual(short.returncode, 0, short.stderr)
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertGreater(data["totals"]["num_statements"], 0)
            bad = subprocess.run(
                [sys.executable, "-m", "coverage", "json", "--output=" + str(output)],
                cwd=root, env=env, text=True, capture_output=True,
                check=False, timeout=15,
            )
            self.assertNotEqual(bad.returncode, 0)


    def test_graph_manifest_triggers_both_pr_and_master_push(self):
        src = workflow()
        manifest = "'mission-control/federation-atlas/G3A_N13_N15_MASTER_DAGS_COMPAT_20261017.json'"
        self.assertEqual(src.count("      - " + manifest), 2)
        pr, rest = src.split("  push:\n", 1)
        push, _ = rest.split("  workflow_dispatch:", 1)
        self.assertIn(manifest, pr)
        self.assertIn(manifest, push)
        self.assertNotIn("permissions:\n  contents: write", src)

    def test_operations_atlas_fixture_triggers_both_pr_and_master_push(self):
        src = workflow()
        fixture = "'mission-control/federation-atlas/MC_OPERATIONS_ATLAS_V2_BRIDGE_20261017.json'"
        self.assertEqual(src.count("      - " + fixture), 2)
        pr, rest = src.split("  push:\n", 1)
        push, _ = rest.split("  workflow_dispatch:", 1)
        self.assertIn(fixture, pr)
        self.assertIn(fixture, push)

    def test_graph_bridge_module_is_coverage_denominator_member(self):
        src = workflow()
        self.assertIn("'n3_master_dags_bridge.py'", src)
        self.assertIn("assert len(s)==9", src)
        self.assertNotIn("assert len(s)==8", src)
        self.assertIn("assert pct>=80", src)
        self.assertIn("100*branches/branch_total>=80", src)
        broken = src.replace("'n3_master_dags_bridge.py'", "'unregistered.py'", 1)
        self.assertNotIn("'n3_master_dags_bridge.py'", broken)



if __name__ == "__main__":
    unittest.main()
