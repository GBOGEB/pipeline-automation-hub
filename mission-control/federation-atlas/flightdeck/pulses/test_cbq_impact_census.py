"""Root and impact CENSUS negative tests, without invented closure."""
import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("impact", HERE / "cbq_impact_census.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class ImpactCensusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent = json.loads(
            (HERE / "CBQ_CH_BD_20261016.json").read_text(encoding="utf-8")
        )
        cls.current = json.loads(
            (HERE / "RE_CENSUS_IMPACT_20261016.json").read_text(encoding="utf-8")
        )

    def test_original_parent_preserved_and_new_breadth(self):
        result = M.compare(self.parent, self.current)
        self.assertEqual(5, result["metrics"]["N_pr_population"])
        self.assertEqual(15, result["metrics"]["N_plus_1_pr_population"])
        self.assertEqual(10, result["metrics"]["additional_prs"])
        self.assertEqual(0, result["metrics"]["accepted_root_closure_delta"])
        self.assertEqual(0, result["metrics"]["accepted_engineering_dov_delta"])
        self.assertIsNone(result["metrics"]["matched_coverage_gain"])

    def test_sealed_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = M.produce(
                HERE / "CBQ_CH_BD_20261016.json",
                HERE / "RE_CENSUS_IMPACT_20261016.json",
                tmp,
            )
            for name, expected in manifest["output_sha256"].items():
                self.assertEqual(
                    hashlib.sha256((Path(tmp) / name).read_bytes()).hexdigest(),
                    expected,
                )
            self.assertEqual(3, len(manifest["output_sha256"]))

    def test_missing_original_pr_fails(self):
        current = copy.deepcopy(self.current)
        current["all_observations"] = current["all_observations"][1:]
        with self.assertRaises(ValueError):
            M.compare(self.parent, current)

    def test_duplicate_pr_fails(self):
        current = copy.deepcopy(self.current)
        current["all_observations"].append(
            copy.deepcopy(current["all_observations"][0])
        )
        with self.assertRaisesRegex(ValueError, "duplicate or lost"):
            M.compare(self.parent, current)

    def test_invalid_sha_fails(self):
        current = copy.deepcopy(self.current)
        current["all_observations"][0]["head_sha"] = "not-a-sha"
        with self.assertRaises(ValueError):
            M.compare(self.parent, current)

    def test_workflow_count_boolean_not_accepted(self):
        current = copy.deepcopy(self.current)
        current["all_observations"][0]["success"] = True
        with self.assertRaises(ValueError):
            M.compare(self.parent, current)

    def test_unrelated_owner_absent_fails(self):
        current = copy.deepcopy(self.current)
        current["root_owners"][0]["canonical"] = "GBOGEB/ABACUS#900000"
        with self.assertRaisesRegex(ValueError, "root owner"):
            M.compare(self.parent, current)

    def test_branch_sha_missing_fails(self):
        current = copy.deepcopy(self.current)
        current["default_branch_heads"][0]["sha"] = ""
        with self.assertRaisesRegex(ValueError, "invalid exact main"):
            M.compare(self.parent, current)

    def test_unauthorized_approval_fails(self):
        current = copy.deepcopy(self.current)
        current["federation_holds"]["qps"] = "ACCEPT"
        with self.assertRaisesRegex(ValueError, "authority promotion"):
            M.compare(self.parent, current)

    def test_synthetic_native_promotion_fails(self):
        current = copy.deepcopy(self.current)
        current["federation_holds"]["native_replay"] = "PASS"
        with self.assertRaises(ValueError):
            M.compare(self.parent, current)

    def test_changed_head_stops_like_for_like_credit(self):
        current = copy.deepcopy(self.current)
        row = next(x for x in current["all_observations"]
                   if x["pr"] == 1993 and x["repository"] == "GBOGEB/ABACUS")
        row["head_sha"] = "f" * 40
        row["failed"] = 0
        result = M.compare(self.parent, current)
        matching = next(x for x in result["matched_cohort"]
                        if x["pr"] == "GBOGEB/ABACUS#1993")
        self.assertFalse(matching["source_matched"])
        self.assertIsNone(matching["failure_delta"])
        self.assertFalse(matching["accepted_root_closed"])

    def test_label_is_source_only(self):
        result = M.compare(self.parent, self.current)
        self.assertEqual("UNKNOWN", result["authority"]["native_replay"])
        self.assertEqual(2, result["metrics"]["overlapping_canonical_owners"])


if __name__ == "__main__":
    unittest.main()
