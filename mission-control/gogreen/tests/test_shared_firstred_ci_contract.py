"""Static and hostile contract checks for shared native GoGREEN CI first-red repair."""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import re
import unittest

GOGREEN = Path(__file__).resolve().parents[1]
ROOT = GOGREEN.parents[1]
TEST_FILE = GOGREEN / "tests" / "test_bd_queue_wave.py"
PRODUCER = GOGREEN / "bd_queue_wave.py"
TARGETS = (
    ".github/workflows/gogreen-g0.yml",
    ".github/workflows/gogreen-g1-metrics.yml",
    ".github/workflows/gogreen-g4-fleet.yml",
    ".github/workflows/gogreen-pulses.yml",
)
PIN = "cryptography==46.0.4"
CORRECT = "here.parent/'bd_queue_wave.py'"
WRONG = "here/'bd_queue_wave.py'"


def safe_import_binding(text):
    return text.count(CORRECT) == 1 and WRONG not in text


def dependency_before_tests(text):
    step = "Install pinned GoGREEN receipt-signature dependency"
    return text.count(step) == 1 and text.count(PIN) == 1 and (
        "python -m unittest discover" in text
    ) and text.index(PIN) < text.index("-m unittest")


class SharedFirstRedContractTests(unittest.TestCase):
    def test_source_producer_exists(self):
        self.assertTrue(PRODUCER.is_file())

    def test_module_spec_can_be_resolved_without_loading(self):
        spec = importlib.util.spec_from_file_location("bd_queue_wave", PRODUCER)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)

    def test_test_import_points_to_production_sibling(self):
        self.assertTrue(safe_import_binding(TEST_FILE.read_text()))

    def test_existing_test_parses(self):
        ast.parse(TEST_FILE.read_text())

    def test_hostile_test_relative_path_rejected(self):
        mutated = TEST_FILE.read_text().replace(CORRECT, WRONG)
        self.assertFalse(safe_import_binding(mutated))

    def test_missing_producer_link_rejected(self):
        self.assertFalse(safe_import_binding(TEST_FILE.read_text().replace(CORRECT, "")))

    def test_all_workflows_install_signature_dependency(self):
        for path in TARGETS:
            with self.subTest(path=path):
                self.assertTrue(dependency_before_tests((ROOT / path).read_text()))

    def test_hostile_omitted_dependency_rejected(self):
        for path in TARGETS:
            text = (ROOT / path).read_text()
            with self.subTest(path=path):
                self.assertFalse(dependency_before_tests(text.replace(PIN, "no-crypto-pin")))

    def test_duplicate_install_step_rejected(self):
        text = (ROOT / TARGETS[0]).read_text()
        self.assertFalse(dependency_before_tests(text + "\n" +
            "Install pinned GoGREEN receipt-signature dependency"))

    def test_dependency_installed_before_suite(self):
        for path in TARGETS:
            with self.subTest(path=path):
                text = (ROOT / path).read_text()
                self.assertLess(text.index(PIN), text.index("-m unittest"))

    def test_no_weakening_by_unconditional_skip(self):
        for path in TARGETS:
            with self.subTest(path=path):
                text = (ROOT / path).read_text()
                self.assertNotRegex(text, r"(?:--ignore|skipIf|--maxfail=0)")

    def test_read_only_workflow_permissions_preserved(self):
        for path in TARGETS:
            with self.subTest(path=path):
                text = (ROOT / path).read_text()
                self.assertNotRegex(text, r"(?m)^\\s*(?:contents|actions|pull-requests):\\s*write\\s*$")

    def test_checkout_still_source_bound(self):
        for path in TARGETS:
            with self.subTest(path=path):
                text = (ROOT / path).read_text()
                self.assertIn("github.event.pull_request.head.sha || github.sha", text)

    def test_no_test_discovery_diversion(self):
        for path in TARGETS:
            with self.subTest(path=path):
                self.assertIn("mission-control/gogreen/tests", (ROOT / path).read_text())


if __name__ == "__main__":
    unittest.main()
