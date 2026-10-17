import unittest
from metric_atlas.adaptive_scale import ScaleError, decide

DEFAULT = {
    "codex_receiver_merged": True, "qps_receiver_merged": True,
    "private_qps_read_authorized": True, "source_owner_dispatch_approved": True,
    "canonical_530_zip_verifier_accepted": True,
    "abacus_receiver_merged": True, "abacus_effective_required_checks_green": True,
    "security_p0_p1_cleared_or_accepted": True,
}


def pulse(states, index=4):
    verified = sum(x == "VERIFIED_LOCAL_ZIP_AND_NATIVE_JOB" for x in states)
    return {"schema": "qps-metric-pulse/v1", "wave": "N5",
            "eligible_repos": 3, "eligible_routes": 6,
            "planned_routes": len(states), "verified_zip_routes": verified,
            "terminal_native_jobs": verified, "pulse_index": index,
            "scope_fingerprint": f"pilot-{len(states)}",
            "merge_admission": "HOLD", "qps_engineering_acceptance": False}


HOLD = ["HOLD_RECEIPT_MISSING"] * 4
GREEN = ["VERIFIED_LOCAL_ZIP_AND_NATIVE_JOB"] * 4


class AdaptiveScaleTests(unittest.TestCase):
    def test_private_unreadable_blocks(self):
        flags = dict(DEFAULT, private_qps_read_authorized=False)
        out = decide(pulse(HOLD), flags)
        self.assertEqual(out["status"], "HOLD_PRIVATE_READ")
        self.assertEqual(out["next_read_only_routes"], 0)

    def test_unknown_auth_is_hold(self):
        flags = dict(DEFAULT, source_owner_dispatch_approved=None)
        self.assertEqual(decide(pulse(HOLD), flags)["status"], "HOLD_OWNER_APPROVAL")

    def test_zero_receipts_is_pilot_not_proof(self):
        out = decide(pulse(HOLD), DEFAULT)
        self.assertEqual(out["status"], "GO_PILOT_2x4_ONLY")
        self.assertFalse(out["dispatch_performed"])
        self.assertIsNone(out["worker_hour_yield"])

    def test_full_pilot_with_abacus_open_is_hold(self):
        out = decide(pulse(GREEN, 5), dict(DEFAULT, abacus_receiver_merged=False))
        self.assertEqual(out["status"], "HOLD_ABACUS_ADMISSION")

    def test_canonical_zip_missing_blocks_expansion(self):
        out = decide(pulse(GREEN, 5),
                     dict(DEFAULT, canonical_530_zip_verifier_accepted=None))
        self.assertEqual(out["status"], "HOLD_CANONICAL_ZIP")

    def test_safety_wins_even_with_green_census(self):
        out = decide(pulse(GREEN, 5), dict(DEFAULT, security_p0_p1_present=True))
        self.assertEqual(out["status"], "HOLD_CRITICAL_SECURITY")

    def test_single_full_pilot_not_repeatable(self):
        self.assertEqual(decide(pulse(GREEN, 5), DEFAULT)["status"],
                         "HOLD_REPEATABILITY")

    def test_two_comparable_full_pulses_qualify_proposal(self):
        out = decide(pulse(GREEN, 6), DEFAULT, previous=pulse(GREEN, 5))
        self.assertEqual(out["status"], "PROPOSE_3x6_OWNER_REVIEW")
        self.assertEqual(out["next_read_only_routes"], 6)
        self.assertEqual(out["merge_admission"], "HOLD")

    def test_changing_cohort_disqualifies_repeatability(self):
        out = decide(pulse(GREEN, 6), DEFAULT,
                     previous=pulse(GREEN[:2], 5))
        self.assertEqual(out["status"], "HOLD_REPEATABILITY")

    def test_inconsistent_counts_rejected(self):
        metric = pulse(HOLD)
        metric["terminal_native_jobs"] = 8
        with self.assertRaises(ScaleError):
            decide(metric, DEFAULT)

    def test_current_realistic_not_autopromoted(self):
        out = decide(pulse(HOLD),
                     dict(DEFAULT, private_qps_read_authorized=False,
                          abacus_receiver_merged=False))
        self.assertEqual(out["status"], "HOLD_PRIVATE_READ")
        self.assertEqual(out["next_read_only_routes"], 0)


if __name__ == "__main__":
    unittest.main()
