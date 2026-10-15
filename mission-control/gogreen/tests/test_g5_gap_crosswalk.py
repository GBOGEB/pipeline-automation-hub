"""G5 fresh-head discovery contract: never promote historical cells automatically."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "g5_gap_crosswalk_20261015.json"
SHA = re.compile(r"[0-9a-f]{40}\\Z")


class G5GapCrosswalkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(DATA.read_text(encoding="utf-8"))

    def test_fixed_cohort_and_missing_packets(self):
        d = self.data
        self.assertEqual(d["historical_g1"]["observed_cells"], 6)
        self.assertEqual(d["historical_g1"]["missing_cells"], 36)
        self.assertEqual(d["current_cohort"]["eligible_cells"], 42)
        self.assertIsNone(d["current_cohort"]["validated_observed_cells"])
        self.assertIsNone(d["current_cohort"]["verified_bytes_cells"])
        self.assertEqual(len(d["current_cohort"]["repos"]), 6)
        self.assertEqual(len(d["gap_packets"]), 36)

    def test_packets_are_unique_and_source_bound(self):
        d = self.data
        cat = {r["repository"]: r for r in d["current_cohort"]["repos"]}
        seen = set()
        for p in d["gap_packets"]:
            self.assertRegex(p["source_sha"], SHA)
            self.assertEqual(p["source_sha"], cat[p["repository"]]["source_sha"])
            self.assertIn(p["family"], cat[p["repository"]]["families"])
            self.assertNotEqual(p["family"], cat[p["repository"]]["observed_g1_family"])
            key = (p["repository"], p["family"])
            self.assertNotIn(key, seen)
            seen.add(key)
            self.assertEqual(p["state"], "UNKNOWN")
            self.assertFalse(p["dispatch_authorized"])
            self.assertFalse(p["archive_bytes_verified"])
            self.assertIsNone(p["native_run_id"])
            self.assertIsNone(p["worker_hours"])
        self.assertEqual(len(seen), 36)

    def test_authority_and_historical_nonpromotion(self):
        d = self.data
        for r in d["current_cohort"]["repos"]:
            self.assertFalse(r["historical_observation_carried_forward"])
        c = d["controls"]
        for field in ("merge_authorized", "security_waiver",
                      "authority_transfer", "qps_owner_acceptance"):
            self.assertIs(c[field], False)
        self.assertEqual(c["authenticated_workers"], 0)
        self.assertIsNone(c["worker_hours"])


if __name__ == "__main__":
    unittest.main()
