"""N+3 controls: matched denominators, causal restraint, fail-closed receipts."""
from datetime import datetime, timedelta, timezone
import copy
import unittest

from wave_control import summarize


def pulse(seq, *, issues=10, prs=2, ticks=1, scope_added=0,
          flow="GROWING", net=(-1.0, -2.0, -0.2), heads=None):
    when = datetime(2026, 10, 1, tzinfo=timezone.utc) + timedelta(days=seq)
    heads = heads or {"GBOGEB/public": "a" * 40}
    return {"schema": "jade.issue-rank.ledger.v1", "seq": seq,
            "row_sha256": ("ab" * 32), "prev_sha256": ("ab" * 32) if seq else None, "telemetry": {
                "fetched_at": when.isoformat(),
                "heads": heads,
                "method": {"version": "issue-rank-method/2.0"},
                "delta": {"baseline": False, "tasks_ticked_net": ticks,
                          "scope_added_net": scope_added},
                "scopes": {"USER": {
                    "open_issues": issues, "open_prs": prs,
                    "tasks_done": 3 + seq, "tasks_total": 15 + scope_added,
                    "criteria_untracked": 7, "measurable": .5,
                    "dod_declared": .3 + seq * .05, "dov_declared": .2,
                    "checklist_coverage": .4, "prs_red": 1,
                    "prs_unreviewed": 2, "stale_21d": 0,
                    "actionable": 5, "parked": 0, "deadlocked": 0,
                    "flow": {"window_days": 14, "status": flow,
                             "net_burn_per_day": {"est": net[0], "lo": net[1], "hi": net[2]}}}}}}


class WaveControl(unittest.TestCase):
    def four(self):
        return [pulse(i, issues=10 - i) for i in range(4)]

    def test_horizon_at_least_three(self):
        with self.assertRaises(ValueError):
            summarize(self.four(), j=2)
        with self.assertRaises(ValueError):
            summarize(self.four(), j=3.0)

    def test_withheld_when_less_than_four_pulses(self):
        r = summarize(self.four()[:3])
        self.assertEqual(r["status"], "WITHHELD_MISSING_PULSES")
        self.assertEqual(r["required"], 4)
        self.assertEqual(r["merge_admission"], "HOLD")

    def test_matched_n3_delta_and_explicit_no_authority(self):
        r = summarize(self.four())
        self.assertEqual(r["status"], "COMPARABLE_ADVISORY")
        self.assertEqual([x["label"] for x in r["waves"]], ["N", "N+1", "N+2", "N+3"])
        self.assertEqual(r["comparison"]["delta"]["open_issues"], -3)
        self.assertAlmostEqual(r["comparison"]["delta"]["dod_declared_pp"], 15)
        self.assertEqual(r["comparison"]["matched_items_ticked_net"], 3)
        self.assertEqual(r["control"]["closure_credit"], 0)
        self.assertFalse(r["control"]["formally_verified_dod"])
        self.assertEqual(r["merge_admission"], "HOLD")

    def test_scope_membership_drift_withholds_deltas(self):
        rows = self.four()
        rows[-1]["telemetry"]["heads"]["GBOGEB/another"] = "b" * 40
        r = summarize(rows)
        self.assertEqual(r["status"], "WITHHELD_UNMATCHED")
        self.assertEqual(r["comparison"]["delta"], {})
        self.assertIn("SCOPE_MEMBERSHIP_DRIFT", r["control"]["notes"])

    def test_saturated_nested_source_withholds_comparable_burn(self):
        rows = self.four()
        rows[2]["telemetry"]["method"]["relations_complete"] = False
        result = summarize(rows)
        self.assertEqual(result["status"], "WITHHELD_UNMATCHED")
        self.assertEqual(result["comparison"]["delta"], {})
        self.assertIn("INCOMPLETE_NESTED_RELATIONS", result["control"]["notes"])
        self.assertFalse(result["control"]["sustained_positive_burn_observed"])

    def test_head_sha_change_is_allowed_and_counted(self):
        rows = self.four()
        rows[2]["telemetry"]["heads"]["GBOGEB/public"] = "b" * 40
        r = summarize(rows)
        self.assertEqual(r["status"], "COMPARABLE_ADVISORY")
        self.assertEqual(r["waves"][2]["source_head_changes"], 1)
        self.assertEqual(r["waves"][3]["source_head_changes"], 1)

    def test_method_drift_withholds_comparison(self):
        rows = self.four()
        rows[2]["telemetry"]["method"]["version"] = "method/3"
        self.assertEqual(summarize(rows)["status"], "WITHHELD_UNMATCHED")

    def test_timestamp_and_sequence_must_advance(self):
        rows = self.four()
        rows[3]["telemetry"]["fetched_at"] = rows[2]["telemetry"]["fetched_at"]
        with self.assertRaisesRegex(ValueError, "time"):
            summarize(rows)
        rows = self.four()
        rows[2]["seq"] = 9
        with self.assertRaisesRegex(ValueError, "sequence"):
            summarize(rows)

    def test_no_false_zero_when_net_ticked_is_unknown(self):
        rows = self.four()
        del rows[2]["telemetry"]["delta"]["tasks_ticked_net"]
        r = summarize(rows)
        self.assertIsNone(r["comparison"]["matched_items_ticked_net"])

    def test_scope_growth_separate_from_ticks(self):
        rows = self.four()
        rows[1]["telemetry"]["delta"]["scope_added_net"] = 3
        r = summarize(rows)
        self.assertEqual(r["comparison"]["matched_items_ticked_net"], 3)
        self.assertEqual(r["comparison"]["matched_items_scope_added_net"], 3)

    def test_overlapping_windows_are_not_independent_burn_proof(self):
        r = summarize(self.four())
        self.assertFalse(r["control"]["independent_flow_windows"])
        self.assertFalse(r["control"]["sustained_positive_burn_observed"])
        self.assertIn("OVERLAPPING_OR_UNKNOWN_FLOW_WINDOWS", r["control"]["notes"])

    def test_independent_positive_windows_are_observation_only(self):
        rows = self.four()
        for i, row in enumerate(rows):
            row["telemetry"]["fetched_at"] = (datetime(2026, 8, 1, tzinfo=timezone.utc)
                                                + timedelta(days=i * 15)).isoformat()
            f = row["telemetry"]["scopes"]["USER"]["flow"]
            f["status"] = "BURNING_DOWN"
            f["net_burn_per_day"] = {"est": 2.0, "lo": .5, "hi": 4.0}
        r = summarize(rows)
        self.assertTrue(r["control"]["independent_flow_windows"])
        self.assertTrue(r["control"]["sustained_positive_burn_observed"])
        self.assertEqual(r["authority"], "ADVISORY_ONLY")

    def test_invalid_burn_bounds_fail_closed(self):
        rows = self.four()
        rows[1]["telemetry"]["scopes"]["USER"]["flow"]["net_burn_per_day"]["lo"] = 20.0
        with self.assertRaisesRegex(ValueError, "inverted"):
            summarize(rows)

    def test_invalid_coverage_and_nan_fail_closed(self):
        rows = self.four()
        rows[1]["telemetry"]["scopes"]["USER"]["dod_declared"] = 1.1
        with self.assertRaisesRegex(ValueError, "out-of-range"):
            summarize(rows)
        rows = self.four()
        rows[1]["telemetry"]["scopes"]["USER"]["open_issues"] = float("nan")
        with self.assertRaisesRegex(ValueError, "invalid numeric"):
            summarize(rows)

    def test_reject_malformed_source_sha(self):
        rows = self.four()
        rows[-1]["telemetry"]["heads"]["GBOGEB/public"] = "not-a-sha"
        with self.assertRaisesRegex(ValueError, "source head"):
            summarize(rows)

    def test_reject_malformed_receipt_shape(self):
        rows = self.four()
        rows[-1]["row_sha256"] = "bad"
        with self.assertRaisesRegex(ValueError, "ledger receipt"):
            summarize(rows)

    def test_reject_mismatched_previous_receipt(self):
        rows = self.four()
        rows[2]["prev_sha256"] = "ff" * 32
        with self.assertRaisesRegex(ValueError, "previous ledger receipt"):
            summarize(rows)

    def test_reject_fractional_count(self):
        rows = self.four()
        rows[1]["telemetry"]["scopes"]["USER"]["open_issues"] = 4.5
        with self.assertRaisesRegex(ValueError, "fractional count"):
            summarize(rows)

    def test_reject_count_subset_larger_than_total(self):
        rows = self.four()
        rows[1]["telemetry"]["scopes"]["USER"]["prs_red"] = 3
        with self.assertRaisesRegex(ValueError, "impossible count subset"):
            summarize(rows)

    def test_no_positive_burn_from_mixed_or_missing_final_flow(self):
        rows = self.four()
        for i, row in enumerate(rows):
            row["telemetry"]["fetched_at"] = (
                datetime(2026, 8, 1, tzinfo=timezone.utc)
                + timedelta(days=i * 15)).isoformat()
            row["telemetry"]["scopes"]["USER"]["flow"].update(
                {"window_days": 14, "status": "BURNING_DOWN",
                 "net_burn_per_day": {"est": 2.0, "lo": .5, "hi": 4.0}})
        rows[-1]["telemetry"]["scopes"]["USER"]["flow"]["window_days"] = 7
        result = summarize(rows)
        self.assertFalse(result["control"]["sustained_positive_burn_observed"])
        self.assertIn("MISSING_OR_MIXED_FINAL_14D_FLOW", result["control"]["notes"])

    def test_missing_successor_link_is_rejected(self):
        rows = self.four()
        rows[2].pop("prev_sha256")
        with self.assertRaisesRegex(ValueError, "previous ledger receipt"):
            summarize(rows)

    def test_private_head_redaction_is_allowed(self):
        rows = self.four()
        for row in rows:
            row["telemetry"]["heads"]["GBOGEB/private"] = None
        self.assertEqual(summarize(rows)["status"], "COMPARABLE_ADVISORY")

    def test_missing_receipt_is_withheld(self):
        rows = self.four()
        rows[2].pop("row_sha256")
        with self.assertRaisesRegex(ValueError, "previous ledger receipt"):
            summarize(rows)


if __name__ == "__main__":
    unittest.main()


def test_zz_canary_g_pah():
    assert False, "red canary: proves CI collects this family"
