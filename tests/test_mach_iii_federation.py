import unittest
from scripts.mach_iii_federation import evaluate


class FederationTests(unittest.TestCase):
    def test_label_overlap_is_not_root_proof(self):
        x = [{"pr": p, "job": "Security", "status": "failure"} for p in [1, 2]]
        y = evaluate({"active": False}, x)
        self.assertEqual(y["job_label_overlap"]["Security"], 2)
        self.assertEqual(y["proven_root_leverage"], {})
        self.assertEqual(y["admission"], "HOLD")

    def test_evidence_bound_dedup(self):
        x = {"pr": 1, "head_sha": "sha", "run_id": 2, "job_id": 3,
             "status": "failure", "job": "Black", "root_id": "R",
             "root_evidence": "receipt", "first_red_signature": "black check"}
        y = evaluate({"active": False}, [x, x, dict(x, pr=2)])
        self.assertEqual(y["observed_records"], 2)
        self.assertEqual(y["proven_root_leverage"]["R"], 2)

    def test_active_flag_cannot_authorize_merge(self):
        self.assertEqual(evaluate({"active": True}, [])["admission"], "HOLD")


if __name__ == "__main__":
    unittest.main()
