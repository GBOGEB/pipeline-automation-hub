"""N2: do not mix independently executed test populations or claim absent runs."""
import importlib.util
import unittest
from pathlib import Path

DEVOPS = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ci_bundle_population_evidence", DEVOPS / "ci_bundle_population_evidence.py")
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)
SHA = "b" * 40


def log(n, result="OK"):
    return f"test_fixture ... ok\n\nRan {n} tests in 1.250s\n\n{result}\n"


class PopulationEvidence(unittest.TestCase):
    def test_one_step_sees_seventy_seven_not_eighty_nine(self):
        first = E.observe(log(77), SHA, 123)
        self.assertEqual(first["ran"], 77)
        self.assertEqual(first["executed"], 77)
        self.assertEqual(first["state"], "LOG_PASS")
        self.assertIsNone(first["selected"])
        self.assertIsNone(first["collected"])

    def test_separate_matched_12_can_reconcile_to_89(self):
        first = E.observe(log(77), SHA, 123)
        second = E.observe(log(12), SHA, 123)
        result = E.reconcile({"devops": first, "actions_metrics": second})
        self.assertEqual(result["observed_executed_total"], 89)
        self.assertTrue(result["complete_groups"])
        self.assertFalse(result["merge_authorized"])

    def test_missing_second_step_is_not_eighty_nine(self):
        result = E.reconcile({"devops": E.observe(log(77), SHA, 123)})
        self.assertFalse(result["complete_groups"])
        self.assertIsNone(result["observed_executed_total"])

    def test_not_executed_cohort_is_unknown_not_zero(self):
        row = E.observe(None, SHA, 123)
        self.assertEqual(row["state"], "NOT_EXECUTED")
        self.assertIsNone(row["executed"])
        result = E.reconcile({"devops": E.observe(log(77), SHA, 123), "actions_metrics": row})
        self.assertIsNone(result["observed_executed_total"])

    def test_mismatched_head_refuses_combination(self):
        result = E.reconcile({"devops": E.observe(log(77), SHA, 123),
                              "actions_metrics": E.observe(log(12), "c" * 40, 123)})
        self.assertFalse(result["same_run_claim"])
        self.assertIsNone(result["observed_executed_total"])

    def test_mismatched_run_id_refuses_combination(self):
        result = E.reconcile({"devops": E.observe(log(77), SHA, 123),
                              "actions_metrics": E.observe(log(12), SHA, 124)})
        self.assertIsNone(result["observed_executed_total"])

    def test_skipped_tests_do_not_count_as_executed(self):
        row = E.observe(log(4, "OK (skipped=1)"), SHA, 123)
        self.assertEqual((row["ran"], row["executed"], row["skipped"]), (4, 3, 1))
        result = E.reconcile({"devops": row, "actions_metrics": E.observe(log(12), SHA, 123)})
        self.assertIsNone(result["observed_executed_total"])

    def test_failures_cannot_be_reported_as_success(self):
        row = E.observe(log(77, "FAILED (failures=1)"), SHA, 123)
        self.assertEqual(row["state"], "LOG_FAIL")
        self.assertIsNone(E.reconcile({"devops": row, "actions_metrics": E.observe(log(12), SHA, 123)})["observed_executed_total"])

    def test_missing_footer_and_unrecognized_summary(self):
        self.assertEqual(E.observe("Ran 77 tests in 1.2s\n", SHA, 1)["state"], "UNKNOWN_NO_OUTCOME")
        self.assertEqual(E.observe("nothing useful", SHA, 1)["state"], "UNKNOWN_NO_SUMMARY")

    def test_corrupt_skip_counts_are_not_accepted(self):
        row = E.observe(log(4, "OK (skipped=5)"), SHA, 123)
        self.assertEqual(row["state"], "INVALID_SKIP_COUNT")
        self.assertIsNone(row["executed"])

    def test_source_and_run_id_validation(self):
        with self.assertRaises(ValueError):
            E.observe(log(1), "master", 123)
        with self.assertRaises(ValueError):
            E.observe(log(1), SHA, 0)


    def test_extra_cohort_cannot_inflate_total(self):
        rows = {"devops": E.observe(log(77), SHA, 123),
                "actions_metrics": E.observe(log(12), SHA, 123),
                "unrelated": E.observe(log(900), SHA, 123)}
        result = E.reconcile(rows)
        self.assertFalse(result["scope_exact"])
        self.assertTrue(result["complete_groups"])
        self.assertEqual(result["unexpected_groups"], ["unrelated"])
        self.assertIsNone(result["observed_executed_total"])

    def test_multiple_summaries_not_mistaken_for_one_cohort(self):
        row = E.observe(log(77) + log(12), SHA, 123)
        self.assertEqual(row["state"], "AMBIGUOUS_MULTIPLE_SUMMARIES")
        self.assertIsNone(row["executed"])

    def test_disconnected_footer_cannot_rescue_a_failed_test(self):
        row = E.observe("Ran 77 tests in 1.2s\nerror: lost footer\nOK\n", SHA, 123)
        self.assertEqual(row["state"], "UNKNOWN_NO_OUTCOME")
        row = E.observe(log(77, "FAILED (failures=1)") + "OK\n", SHA, 123)
        self.assertEqual(row["state"], "LOG_FAIL")

    def test_run_attempt_mismatch_refuses_reconciliation(self):
        rows = {"devops": E.observe(log(77), SHA, 123, run_attempt=1),
                "actions_metrics": E.observe(log(12), SHA, 123, run_attempt=2)}
        result = E.reconcile(rows)
        self.assertFalse(result["same_run_claim"])
        self.assertIsNone(result["observed_executed_total"])

    def test_malformed_record_and_invalid_required_scope_refused(self):
        rows = {"devops": E.observe(log(77), SHA, 123),
                "actions_metrics": E.observe(log(12), SHA, 123)}
        rows["actions_metrics"]["executed"] = 10_000
        self.assertFalse(E.reconcile(rows)["all_logs_good"])
        self.assertIsNone(E.reconcile(rows)["observed_executed_total"])
        with self.assertRaises(ValueError):
            E.reconcile(rows, required=("devops", "devops"))
        with self.assertRaises(ValueError):
            E.observe(log(1), SHA, 123, run_attempt=0)

    def test_windows_crlf_footers_are_accepted_as_text(self):
        row = E.observe(log(3).replace("\n", "\r\n"), SHA, 123)
        self.assertEqual((row["ran"], row["executed"], row["state"]), (3, 3, "LOG_PASS"))


if __name__ == "__main__":
    unittest.main()
