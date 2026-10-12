import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "GM_DAB_FLAKE8_PROPAGATION_T7_T14_T21_v1.json"


def load():
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def cohorts(doc):
    t7 = list(doc["cohorts"]["top7"])
    t14 = t7 + list(doc["cohorts"]["top14_extension"])
    t21 = t14 + list(doc["cohorts"]["top21_extension"])
    return t7, t14, t21


class GMDabFlake8PropagationTests(unittest.TestCase):
    """unittest-collectable so `python -m unittest <path>` executes >0 tests."""

    def test_cohort_sizes_nesting_and_uniqueness(self):
        doc = load()
        t7, t14, t21 = cohorts(doc)
        self.assertEqual(len(t7), 7)
        self.assertEqual(len(t14), 14)
        self.assertEqual(len(t21), 21)
        self.assertTrue(set(t7).issubset(t14))
        self.assertTrue(set(t14).issubset(t21))
        self.assertEqual(len(set(t21)), 21)

    def test_breadth_modes_fail_closed(self):
        breadth = load()["breadth_control"]
        self.assertEqual(breadth["top7"]["mode"], "ACTIVE_CENSUS_AND_REPAIR")
        self.assertIs(breadth["top7"]["repair_admission"], True)
        self.assertEqual(breadth["top14"]["mode"], "SHADOW_MEASURE_AND_CLASSIFY")
        self.assertIs(breadth["top14"]["repair_admission"], False)
        self.assertEqual(breadth["top21"]["mode"], "HOLD_TELEMETRY_ONLY")
        self.assertIs(breadth["top21"]["repair_admission"], False)

    def test_abacus_seed_is_exact_yield_and_hard_lane_stays_bounded(self):
        doc = load()
        mech = doc["seed_evidence"]["mechanical"]
        hard = doc["seed_evidence"]["hard"]
        self.assertEqual(mech["pre_total"] - mech["post_total"], 394)
        self.assertEqual(mech["pre_w293"] - mech["post_w293"], 394)
        self.assertEqual(mech["result"], "PASS_EXACT_YIELD")
        self.assertEqual(hard["reconstructable_repairs"], 5)
        self.assertEqual(hard["postmerge_exact_census"], "PENDING_BIND")
        self.assertIs(doc["operating_model"]["dab_hard"]["bulk_semantic_autofix"], False)

    def test_noncompensation_blocks_breadth_credit_leakage(self):
        doc = load()
        guards = set(doc["noncompensation"])
        self.assertIn("DAB_CENSUS_NE_COHORT_PROMOTION", guards)
        self.assertIn("TOP14_SHADOW_NE_REPAIR_ADMISSION", guards)
        self.assertIn("TOP21_TELEMETRY_NE_REPAIR_ADMISSION", guards)
        self.assertIs(doc["authority_transfer"], False)
        self.assertEqual(doc["formal_credit_delta"], 0)
        self.assertEqual(doc["engineering_credit_delta"], 0)


if __name__ == "__main__":
    unittest.main()
