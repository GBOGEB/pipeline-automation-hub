import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import source_freshness as sf

class FreshnessContractTests(unittest.TestCase):
    def test_fresh_age_and_boundary(self):
        x=sf.annotate([{"name":"s","as_of":"2026-10-02","as_of_basis":"observed_on"}],"2026-10-16")
        self.assertEqual(x["sources"][0]["age_days"],14)
        self.assertEqual(x["sources"][0]["state"],"FRESH")
    def test_stale_beyond_ttl(self):
        x=sf.annotate([{"name":"s","as_of":"2026-09-28","as_of_basis":"observed_on"}],"2026-10-16")
        self.assertEqual(x["sources"][0]["state"],"STALE")
        self.assertEqual(x["sources"][0]["age_days"],18)
    def test_future_is_not_fresh(self):
        x=sf.annotate([{"name":"s","as_of":"2026-10-18","as_of_basis":"captured_at"}],"2026-10-16")
        self.assertEqual(x["sources"][0]["state"],"FUTURE_INVALID")
    def test_unknown_without_clock(self):
        x=sf.annotate([{"name":"s","as_of":"2026-10-15","as_of_basis":"observed_on"}])
        self.assertIsNone(x["sources"][0]["age_days"])
        self.assertEqual(x["sources"][0]["state"],"UNKNOWN")
    def test_ordinal_not_timestamp(self):
        x=sf.annotate([{"name":"s","as_of":None,"as_of_basis":"ordinal W1.C1.I2.S1"}],"2026-10-16")
        self.assertEqual(x["sources"][0]["state"],"UNKNOWN")
    def test_mission_id_suffix_untrusted(self):
        x=sf.annotate([{"name":"mission","as_of":"2026-10-16","as_of_basis":"mission_id suffix"}],"2026-10-16")
        self.assertEqual(x["sources"][0]["state"],"UNKNOWN")
    def test_no_timestamp_forgery(self):
        with self.assertRaises(ValueError):
            sf.annotate([],"tomorrow")
        with self.assertRaises(ValueError):
            sf.annotate([],"2026-10-16",True)
        with self.assertRaises(ValueError):
            sf.annotate([],"2026-10-16",-1)
    def test_no_authority_transfer(self):
        x=sf.annotate([{"name":"a","as_of":"2026-10-16","as_of_basis":"snapshot_at"}],"2026-10-16")
        self.assertIs(x["authority_transfer"],False)
        self.assertEqual(x["formal_credit_delta"],0)

if __name__ == "__main__":
    unittest.main()
