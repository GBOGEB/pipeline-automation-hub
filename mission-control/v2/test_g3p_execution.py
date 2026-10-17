"""G3P receipt positive, negative, temporal, security and forecast controls."""

import copy
import unittest

import g3p_execution as g3p

REPO = "GBOGEB/ABACUS"
MISSION = "CODE-PURPLE"
WAVE = REPO + "::" + MISSION + "::WG3P-EXAMPLE"
STAMP = [
    ("2026-10-17T09:01:00Z", "2026-10-17T09:02:00Z"),
    ("2026-10-17T09:03:00Z", "2026-10-17T09:04:00Z"),
    ("2026-10-17T09:05:00Z", "2026-10-17T09:06:00Z"),
]


def metrics(n=4):
    return {
        "tests_passed": n, "tests_failed": 0, "statement_covered": 7,
        "statement_total": 10, "branch_covered": 3, "branch_total": 6,
        "changed_lines_covered": None, "changed_lines_total": None,
        "run_duration_ms": 1200, "run_attempt": 1,
    }


def executed(ordinal, original, next_sha, *, status="EXECUTED_PASS"):
    first, measured = STAMP[ordinal - 1]
    is_mutation = original != next_sha
    action = {
        "kind": "COMMIT" if is_mutation else "TEST",
        "owner_lease": "OWNER_A",
        "changed_paths": [f"scripts/pulse{ordinal}.py"] if is_mutation else [],
        "outcome": "DONE",
        "started_at": first.replace(":00Z", ":15Z"),
        "completed_at": first.replace(":00Z", ":45Z"),
        "evidence_ref": "https://github.com/GBOGEB/ABACUS/commit/" + next_sha,
    }
    return {
        "ordinal": ordinal,
        "pulse_id": WAVE + f"::PULSE-{ordinal}",
        "status": status,
        "input_source_sha": original,
        "next_source_sha": next_sha,
        "forecast": {
            "frozen_at": first, "hypothesis": "Test improvement with hold gates",
            "population_id": "same-4-tests", "metrics": {"tests_passed": 4},
        },
        "observed": {
            "measured_at": measured, "source_sha": next_sha,
            "population_id": "same-4-tests", "metrics": metrics(),
            "summary": "Four tests observed on the exact source",
            "executed_steps": 2, "check_outcome": "PASS",
        },
        "actions": [action],
        "evidence_refs": ["https://github.com/GBOGEB/ABACUS/actions/runs/123"],
        "blocker": None,
    }


def valid():
    a, b, c = "a" * 40, "b" * 40, "c" * 40
    return {
        "schema": g3p.SCHEMA,
        "repository": REPO,
        "mission_id": MISSION,
        "wave_id": WAVE,
        "execution_mode": "HANDS_OFF_BOUNDED",
        "objective": {"predicate": "measured test/coverage uplift without waivers"},
        "policy": {
            "main_merge_authorized": False, "security_waiver": False,
            "authority_transfer": False, "max_parallel_mutation_leases": 2,
            "global_stop_policy": "STOP_ON_MAJOR_BLOCKER_NO_AUTO_WAIVER",
        },
        "baseline_N": {
            "source_sha": a, "observed_at": "2026-10-17T09:00:00Z",
            "evidence_ref": "https://github.com/GBOGEB/ABACUS/commit/" + a,
        },
        "pulses": [
            executed(1, a, b),
            executed(2, b, b),
            executed(3, b, c),
        ],
    }


class G3PContractTests(unittest.TestCase):
    def test_three_distinct_pulses_advance_ordinal(self):
        r = g3p.validate_record(valid())
        self.assertEqual(3, r["terminal_evidenced_pulses"])
        self.assertTrue(r["N_plus_3_ordinal_reached"])
        self.assertEqual("COMPLETED_THREE_EVIDENCED_PULSES",
                         r["wave_status"])

    def test_three_pulses_do_not_claim_main_admission(self):
        r = g3p.validate_record(valid())
        self.assertFalse(r["main_merge_admitted"])
        self.assertIsNone(r["engineering_acceptance"])
        self.assertIsNone(r["formal_closure"])
        self.assertFalse(r["automatic_background_execution_claimed"])
        self.assertIn("NOT_VERIFIED", r["evidence_locator_authentication"])

    def test_expected_actual_metrics_require_population_parity(self):
        r = g3p.validate_record(valid())
        comparison = r["pulses"][0]["expected_vs_actual"]["tests_passed"]
        self.assertEqual("COMPARABLE", comparison["state"])
        self.assertEqual(0, comparison["delta_actual_minus_expected"])

    def test_mismatched_population_refuses_delta(self):
        doc = valid()
        doc["pulses"][0]["observed"]["population_id"] = "other-population"
        r = g3p.validate_record(doc)
        comp = r["pulses"][0]["expected_vs_actual"]["tests_passed"]
        self.assertIsNone(comp["delta_actual_minus_expected"])
        self.assertEqual("UNKNOWN_OR_UNMATCHED", comp["state"])

    def test_deterministic_without_mutation(self):
        doc = valid()
        previous = copy.deepcopy(doc)
        self.assertEqual(g3p.validate_record(doc), g3p.validate_record(doc))
        self.assertEqual(previous, doc)

    def test_local_hold_still_allows_next_pulse(self):
        doc = valid()
        p = doc["pulses"][1]
        p["status"] = "HOLD_EVIDENCED"
        p["observed"]["executed_steps"] = 0
        p["observed"]["check_outcome"] = "UNKNOWN"
        p["actions"] = []
        p["blocker"] = {"scope": "LOCAL", "reason": "UNRELATED_QUALITY_OWNER"}
        self.assertTrue(g3p.validate_record(doc)["N_plus_3_ordinal_reached"])

    def test_global_blocker_stops_future_pulses(self):
        doc = valid()
        blocked = doc["pulses"][1]
        blocked["status"] = "HOLD_EVIDENCED"
        blocked["blocker"] = {"scope": "GLOBAL",
                              "reason": "MISSING_PERMISSION"}
        blocked["actions"] = []
        doc["pulses"][2] = {
            "ordinal": 3, "pulse_id": WAVE + "::PULSE-3",
            "status": "NOT_RUN_GLOBAL_BLOCKER",
            "forecast": None, "observed": None, "next_source_sha": None,
            "actions": [], "evidence_refs": [],
        }
        report = g3p.validate_record(doc)
        self.assertEqual("STOPPED_MAJOR_BLOCKER", report["wave_status"])
        self.assertEqual(2, report["terminal_evidenced_pulses"])
        self.assertFalse(report["N_plus_3_ordinal_reached"])

    def test_cannot_skip_pulse_without_global_blocker(self):
        doc = valid()
        doc["pulses"][2] = {
            "ordinal": 3, "pulse_id": WAVE + "::PULSE-3",
            "status": "NOT_RUN_GLOBAL_BLOCKER",
            "forecast": None, "observed": None, "next_source_sha": None,
            "actions": [], "evidence_refs": [],
        }
        with self.assertRaisesRegex(g3p.G3PContractError, "NOT_RUN"):
            g3p.validate_record(doc)

    def test_no_unauthorized_main_merge_waiver_or_transfer(self):
        for key in ("main_merge_authorized", "security_waiver",
                    "authority_transfer"):
            with self.subTest(key=key):
                doc = valid()
                doc["policy"][key] = True
                with self.assertRaisesRegex(g3p.G3PContractError,
                                            "unauthorized"):
                    g3p.validate_record(doc)

    def test_new_head_requires_actual_mutation(self):
        doc = valid()
        doc["pulses"][0]["actions"][0]["kind"] = "READ"
        doc["pulses"][0]["actions"][0]["changed_paths"] = []
        with self.assertRaisesRegex(g3p.G3PContractError,
                                    "head changed"):
            g3p.validate_record(doc)

    def test_source_sha_must_be_contiguous(self):
        doc = valid()
        doc["pulses"][1]["input_source_sha"] = "f" * 40
        with self.assertRaisesRegex(g3p.G3PContractError,
                                    "continuity"):
            g3p.validate_record(doc)

    def test_observed_head_mismatch_rejected(self):
        doc = valid()
        doc["pulses"][0]["observed"]["source_sha"] = "f" * 40
        with self.assertRaisesRegex(g3p.G3PContractError, "next exact"):
            g3p.validate_record(doc)

    def test_bare_priority_cannot_be_pulse_identity(self):
        doc = valid()
        doc["pulses"][0]["pulse_id"] = "P1"
        with self.assertRaisesRegex(g3p.G3PContractError, "order/identity"):
            g3p.validate_record(doc)

    def test_missing_forecast_denied(self):
        doc = valid()
        doc["pulses"][0]["forecast"] = None
        with self.assertRaisesRegex(g3p.G3PContractError, "expected"):
            g3p.validate_record(doc)

    def test_backdated_forecast_denied(self):
        doc = valid()
        doc["pulses"][1]["forecast"]["frozen_at"] = (
            "2026-10-17T09:01:00Z"
        )
        with self.assertRaisesRegex(g3p.G3PContractError, "forecast"):
            g3p.validate_record(doc)

    def test_unexecuted_zero_step_cannot_be_green(self):
        doc = valid()
        doc["pulses"][0]["observed"]["executed_steps"] = 0
        with self.assertRaisesRegex(g3p.G3PContractError, "zero-step"):
            g3p.validate_record(doc)

    def test_invalid_coverage_pair_never_green(self):
        doc = valid()
        doc["pulses"][0]["observed"]["metrics"]["branch_total"] = None
        with self.assertRaisesRegex(g3p.G3PContractError, "numerator"):
            g3p.validate_record(doc)

    def test_coverage_numerator_cannot_exceed_denominator(self):
        doc = valid()
        doc["pulses"][0]["observed"]["metrics"]["statement_covered"] = 11
        with self.assertRaisesRegex(g3p.G3PContractError, "population"):
            g3p.validate_record(doc)

    def test_invalid_bool_count_denied(self):
        doc = valid()
        doc["pulses"][0]["observed"]["metrics"]["tests_passed"] = True
        with self.assertRaisesRegex(g3p.G3PContractError, "numeric"):
            g3p.validate_record(doc)

    def test_overlap_between_distinct_worker_path_leases_denied(self):
        doc = valid()
        a = doc["pulses"][0]["actions"][0]
        b = copy.deepcopy(a)
        b["owner_lease"] = "OWNER_B"
        doc["pulses"][0]["actions"].append(b)
        with self.assertRaisesRegex(g3p.G3PContractError, "collision"):
            g3p.validate_record(doc)

    def test_nonmutating_worker_cannot_claim_source_path(self):
        doc = valid()
        action = doc["pulses"][1]["actions"][0]
        action["changed_paths"] = ["ci/workflow.yml"]
        with self.assertRaisesRegex(g3p.G3PContractError, "nonmutating"):
            g3p.validate_record(doc)

    def test_changed_head_without_commit_evidence_denied(self):
        doc = valid()
        doc["pulses"][0]["actions"][0]["evidence_ref"] = None
        with self.assertRaisesRegex(g3p.G3PContractError, "evidence ref"):
            g3p.validate_record(doc)

    def test_missing_terminal_evidence_denied(self):
        doc = valid()
        doc["pulses"][2]["evidence_refs"] = []
        with self.assertRaisesRegex(g3p.G3PContractError, "locator"):
            g3p.validate_record(doc)

    def test_failed_execution_needs_fail_result(self):
        doc = valid()
        doc["pulses"][0]["status"] = "EXECUTED_FAIL"
        with self.assertRaisesRegex(g3p.G3PContractError, "failing"):
            g3p.validate_record(doc)

    def test_global_stop_cannot_be_followed_by_success(self):
        doc = valid()
        doc["pulses"][1]["blocker"] = {
            "scope": "GLOBAL", "reason": "NO_SAFE_NEXT_ACTION"
        }
        with self.assertRaisesRegex(g3p.G3PContractError, "global stop"):
            g3p.validate_record(doc)

    def test_g3p_is_one_wave_not_three_nested_wave_identities(self):
        doc = valid()
        doc["wave_id"] = "W1/W2/W3"
        with self.assertRaisesRegex(g3p.G3PContractError,
                                    "fully qualified wave"):
            g3p.validate_record(doc)


    def test_action_started_before_forecast_is_rejected(self):
        doc = valid()
        doc["pulses"][0]["actions"][0]["started_at"] = (
            "2026-10-17T08:59:59Z"
        )
        with self.assertRaisesRegex(g3p.G3PContractError,
                                    "after frozen forecast"):
            g3p.validate_record(doc)

    def test_inverted_action_clock_is_rejected(self):
        doc = valid()
        doc["pulses"][0]["actions"][0]["completed_at"] = (
            "2026-10-17T09:00:20Z"
        )
        with self.assertRaisesRegex(g3p.G3PContractError,
                                    "after frozen forecast"):
            g3p.validate_record(doc)

    def test_action_start_after_actual_measured_is_rejected(self):
        doc = valid()
        doc["pulses"][2]["actions"][0]["started_at"] = (
            "2026-10-17T09:07:01Z"
        )
        with self.assertRaisesRegex(g3p.G3PContractError,
                                    "before actual"):
            g3p.validate_record(doc)

    def test_global_blocker_on_last_pulse_marks_wave_stopped(self):
        doc = valid()
        doc["pulses"][2]["status"] = "HOLD_EVIDENCED"
        doc["pulses"][2]["blocker"] = {
            "scope": "GLOBAL", "reason": "NO_SAFE_NEXT_ACTION"
        }
        report = g3p.validate_record(doc)
        self.assertEqual("STOPPED_MAJOR_BLOCKER", report["wave_status"])
        self.assertFalse(report["main_merge_admitted"])

    def test_three_pulse_slots_not_three_runners(self):
        doc = valid()
        doc["pulses"].append(copy.deepcopy(doc["pulses"][-1]))
        with self.assertRaisesRegex(g3p.G3PContractError,
                                    "exactly three"):
            g3p.validate_record(doc)


if __name__ == "__main__":
    unittest.main()
