"""Adversarial and determinism contracts for shadow CI bundle inventory."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

DEVOPS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEVOPS))
spec = importlib.util.spec_from_file_location("ci_bundle_inventory", DEVOPS / "ci_bundle_inventory.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
CATALOG = json.loads((DEVOPS / "CI_BUNDLE_CATALOG_V1.json").read_text(encoding="utf-8"))
SHA = "a" * 40


class BundleInventory(unittest.TestCase):
    def make(self, content):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        folder = root / ".github/workflows"
        folder.mkdir(parents=True)
        (folder / "test.yml").write_text(content, encoding="utf-8", newline="\n")
        self.addCleanup(temp.cleanup)
        return root

    def test_catalog_has_unique_acyclic_bundles(self):
        result = module.inventory(self.make("name: Unit tests\non: push\njobs: {test: {runs-on: ubuntu-latest, steps: [{run: python -m pytest}]}}"), CATALOG, SHA)
        self.assertEqual(result["workflow_count"], 1)
        self.assertEqual(result["authority"], "ADVISORY_ONLY")
        self.assertFalse(result["merge_authorized"])
        self.assertIn("B02", result["workflows"][0]["bundle_candidates"])

    def test_cannot_promote_heuristics_to_verified_tests(self):
        result = module.inventory(self.make("name: Unit tests\non: push\njobs: {noop: {runs-on: ubuntu-latest, steps: [{run: echo done}]}}"), CATALOG, SHA)
        self.assertEqual(result["workflows"][0]["classification_authority"], "HEURISTIC_ONLY")
        self.assertNotIn("tests_executed", result["workflows"][0])

    def test_dangling_job_and_parse_failure_reported(self):
        root = self.make("name: Broken\non: push\njobs: {one: {needs: absent, steps: []}}")
        report = module.inventory(root, CATALOG, SHA)
        self.assertEqual(report["dag_anomalies"], 1)
        (root / ".github/workflows/test.yml").write_text("on: [push\njobs:", encoding="utf-8", newline="\n")
        self.assertEqual(module.inventory(root, CATALOG, SHA)["parse_errors"], 1)

    def test_invalid_identity_and_duplicate_bundle_rejected(self):
        root = self.make("jobs: {a: {steps: []}}")
        with self.assertRaises(ValueError):
            module.inventory(root, CATALOG, "master")
        bad = dict(CATALOG, bundles=CATALOG["bundles"] + [CATALOG["bundles"][0]])
        with self.assertRaises(ValueError):
            module.inventory(root, bad, SHA)

    def test_determinism_and_cycle_rejection(self):
        root = self.make("name: sample\non: push\njobs: {b: {needs: a, steps: []}, a: {steps: []}}")
        self.assertEqual(module.inventory(root, CATALOG, SHA), module.inventory(root, CATALOG, SHA))
        bad = json.loads(json.dumps(CATALOG))
        bad["bundles"][0]["planning_dependencies"] = ["B12"]
        with self.assertRaises(ValueError):
            module.inventory(root, bad, SHA)


if __name__ == "__main__":
    unittest.main()
