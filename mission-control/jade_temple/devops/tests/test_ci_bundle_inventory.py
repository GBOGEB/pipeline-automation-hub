"""Negative controls for source-bound shadow CI bundle inventory."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

DEVOPS = Path(__file__).resolve().parents[1]
REPO = DEVOPS.parents[2]
sys.path.insert(0, str(DEVOPS))
spec = importlib.util.spec_from_file_location("ci_bundle_inventory", DEVOPS / "ci_bundle_inventory.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
CATALOG = json.loads((DEVOPS / "CI_BUNDLE_CATALOG_V1.json").read_text(encoding="utf-8"))


def git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True, check=True, text=True, encoding="utf-8"
    ).stdout.strip()


class BundleInventory(unittest.TestCase):
    def make(self, content):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        folder = root / ".github/workflows"
        folder.mkdir(parents=True)
        (folder / "test.yml").write_text(content, encoding="utf-8", newline="\n")
        git(root, "init", "-q")
        git(root, "add", ".github/workflows/test.yml")
        git(root, "-c", "user.name=CI Fixture", "-c", "user.email=ci-fixture@example.invalid",
            "commit", "-qm", "test fixture")
        sha = git(root, "rev-parse", "HEAD")
        self.addCleanup(temp.cleanup)
        return root, sha

    def test_catalog_has_unique_acyclic_bundles(self):
        root, sha = self.make("name: Unit tests\non: push\njobs: {test: {runs-on: ubuntu-latest, steps: [{run: python -m pytest}]}}")
        report = module.inventory(root, CATALOG, sha)
        self.assertEqual(report["workflow_count"], 1)
        self.assertEqual(report["source_binding"], "IMMUTABLE_GIT_OBJECT_AT_SHA")
        self.assertFalse(report["merge_authorized"])
        self.assertIn("B02", report["workflows"][0]["bundle_candidates"])

    def test_cannot_promote_heuristics_to_verified_tests(self):
        root, sha = self.make("name: Unit tests\non: push\njobs: {noop: {runs-on: ubuntu-latest, steps: [{run: echo done}]}}")
        result = module.inventory(root, CATALOG, sha)
        self.assertEqual(result["workflows"][0]["classification_authority"], "HEURISTIC_ONLY")
        self.assertNotIn("tests_executed", result["workflows"][0])

    def test_dangling_job_and_parse_failure_reported(self):
        root, sha = self.make("name: Broken\non: push\njobs: {one: {needs: absent, steps: []}}")
        report = module.inventory(root, CATALOG, sha)
        self.assertEqual(report["dag_anomalies"], 1)
        self.assertEqual(report["parse_errors"], 0)
        root2, sha2 = self.make("on: [push\njobs:")
        self.assertEqual(module.inventory(root2, CATALOG, sha2)["parse_errors"], 1)

    def test_malformed_job_fails_closed_not_zero(self):
        root, sha = self.make("on: push\njobs: {bad: string}")
        report = module.inventory(root, CATALOG, sha)
        self.assertEqual(report["parse_errors"], 1)
        self.assertEqual(report["job_parse_errors"], 1)
        self.assertIn("SHAPE: job is not a mapping", report["workflows"][0]["job_parse_errors"][0])
        self.assertIn("JOB_PARSE_ERROR", report["workflows"][0]["diagnostics"])

    def test_malformed_source_and_duplicate_bundle_rejected(self):
        root, sha = self.make("jobs: {a: {steps: []}}")
        with self.assertRaises(ValueError):
            module.inventory(root, CATALOG, "master")
        with self.assertRaises(ValueError):
            module.inventory(root, CATALOG, "a" * 40)
        bad = dict(CATALOG, bundles=CATALOG["bundles"] + [CATALOG["bundles"][0]])
        with self.assertRaises(ValueError):
            module.inventory(root, bad, sha)

    def test_determinism_and_catalog_cycle_rejection(self):
        root, sha = self.make("name: sample\non: push\njobs: {b: {needs: a, steps: []}, a: {steps: []}}")
        self.assertEqual(module.inventory(root, CATALOG, sha), module.inventory(root, CATALOG, sha))
        bad = json.loads(json.dumps(CATALOG))
        bad["bundles"][0]["planning_dependencies"] = ["B12"]
        with self.assertRaises(ValueError):
            module.inventory(root, bad, sha)

    def test_dirty_worktree_does_not_spoof_source(self):
        root, sha = self.make("name: Original\non: push\njobs: {a: {steps: []}}")
        before = module.inventory(root, CATALOG, sha)
        (root / ".github/workflows/test.yml").write_text(
            "name: Forged\non: push\njobs: {a: {steps: [{run: echo changed}]}}",
            encoding="utf-8", newline="\n"
        )
        after = module.inventory(root, CATALOG, sha)
        self.assertEqual(before, after)
        self.assertEqual(after["workflows"][0]["name"], "Original")

    def test_root_must_match_git_repository(self):
        root, sha = self.make("jobs: {a: {steps: []}}")
        with self.assertRaisesRegex(ValueError, "ROOT_MUST_BE_REPOSITORY_TOPLEVEL"):
            module.inventory(root / ".github", CATALOG, sha)

    def test_tree_or_blob_oid_is_not_a_source_commit(self):
        root, sha = self.make("name: sample\non: push\njobs: {a: {steps: []}}")
        for oid in (git(root, "rev-parse", "HEAD^{tree}"),
                    git(root, "rev-parse", "HEAD:.github/workflows/test.yml")):
            with self.assertRaisesRegex(ValueError, "SOURCE_SHA_MUST_NAME_A_COMMIT"):
                module.inventory(root, CATALOG, oid)
        self.assertEqual(module.inventory(root, CATALOG, sha)["source_sha"], sha)

    def test_live_repository_shadow_scan_source_bound(self):
        sha = git(REPO, "rev-parse", "HEAD")
        report = module.inventory(REPO, CATALOG, sha)
        self.assertGreater(report["workflow_count"], 0)
        self.assertEqual(report["source_sha"], sha)
        self.assertEqual(report["source_binding"], "IMMUTABLE_GIT_OBJECT_AT_SHA")
        self.assertFalse(report["merge_authorized"])
        print("CI_BUNDLE_SHADOW_SOURCE_SCAN " + json.dumps({
            k: report[k] for k in ("source_sha", "source_binding", "workflow_count",
                                   "parse_errors", "job_parse_errors", "dag_anomalies",
                                   "unclassified", "authority")
        }, sort_keys=True), flush=True)


if __name__ == "__main__":
    unittest.main()
