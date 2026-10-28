"""Crosswalk must reuse canonical title parser and never infer bundle from prose."""
import importlib.util
import json
import sys
import unittest
from pathlib import Path

DEVOPS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEVOPS))
spec = importlib.util.spec_from_file_location("ci_bundle_title_crosswalk", DEVOPS / "ci_bundle_title_crosswalk.py")
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)
CATALOG = json.loads((DEVOPS / "CI_BUNDLE_CATALOG_V1.json").read_text(encoding="utf-8"))


class CanonicalCrosswalk(unittest.TestCase):
    def test_explicit_bundle_in_conventional_scope_only(self):
        row = C.crosswalk("refactor(ci/B02): first-red test partition", CATALOG)
        self.assertEqual(row["family"], "refactor")
        self.assertEqual(row["bundle_candidates"], ["B02"])
        self.assertIn("B02 / unit-test", row["bundle_display_aliases"])
        self.assertEqual(row["authority"], "ADVISORY_ONLY")
        self.assertFalse(row["merge_authorized"])

    def test_body_mentions_never_create_bundle_identity(self):
        row = C.crosswalk("fix(ci): B09 security test debt", CATALOG)
        self.assertEqual(row["bundle_candidates"], [])
        self.assertIn("ci", row["scope_facets"])

    def test_unclassified_is_not_green(self):
        row = C.crosswalk("B02 tests are passing in my opinion", CATALOG)
        self.assertEqual(row["bundle_candidates"], [])
        self.assertEqual(row["family"], "UNCLASSIFIED")

    def test_unknown_bundle_cannot_create_catalog_entry(self):
        row = C.crosswalk("feat(ci/B99): unregistered test bundle", CATALOG)
        self.assertEqual(row["bundle_candidates"], [])

    def test_multiple_explicit_candidates_deduplicated(self):
        row = C.crosswalk("test(ci/B02/B02/B09): matrix", CATALOG)
        self.assertEqual(row["bundle_candidates"], ["B02", "B09"])
        self.assertEqual(row["explicit_bundle_count"], 2)

    def test_no_rename_or_admission_even_for_governance_title(self):
        row = C.crosswalk("governance(ci/B12): required checks", CATALOG)
        self.assertFalse(row["workflow_names_renamed"])
        self.assertFalse(row["required_check_contexts_modified"])
        self.assertFalse(row["merge_authorized"])

    def test_uses_one_canonical_parser(self):
        calls = []

        def mock_parser(value, item_type=None):
            calls.append((value, item_type))
            return {"schema": "canonical", "family": "ci", "classification": "EXPLICIT_ACTION",
                    "prefix_segments": [{"value": "B03"}], "lint": []}

        row = C.crosswalk("anything", CATALOG, parser=mock_parser)
        self.assertEqual(calls, [("anything", "PullRequest")])
        self.assertEqual(row["bundle_candidates"], ["B03"])

    def test_nontext_title_rejected(self):
        with self.assertRaises(TypeError):
            C.crosswalk(None, CATALOG)


if __name__ == "__main__":
    unittest.main()
