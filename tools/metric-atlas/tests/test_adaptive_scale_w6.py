"""W6 source-bound scale guard: adversarial, reverse and boundary tests."""
import copy
import unittest
from metric_atlas.adaptive_scale import ScaleError, decide
from test_adaptive_scale import DEFAULT, GREEN, HOLD, pulse


class ScaleW6NegativeTests(unittest.TestCase):
    def assert_repeat_hold(self, current=None, previous=None, flags=None):
        out = decide(current if current is not None else pulse(GREEN, 6),
                     flags if flags is not None else DEFAULT,
                     previous=previous if previous is not None else pulse(GREEN, 5))
        self.assertNotEqual(out["status"], "PROPOSE_3x6_OWNER_REVIEW")
        self.assertFalse(out["dispatch_performed"])
        self.assertEqual(out["merge_admission"], "HOLD")

    def test_unverified_previous_terminal_cannot_promote(self):
        prior = pulse(GREEN, 5)
        prior["terminal_native_jobs"] = 0
        self.assert_repeat_hold(previous=prior)

    def test_missing_scope_fingerprint_both_sides_is_not_comparability(self):
        prev = pulse(GREEN, 5); curr = pulse(GREEN, 6)
        prev.pop("scope_fingerprint"); curr.pop("scope_fingerprint")
        self.assert_repeat_hold(current=curr, previous=prev)

    def test_reused_native_receipt_set_is_not_second_trial(self):
        prior = pulse(GREEN, 5); current = pulse(GREEN, 6)
        current["native_receipt_set_sha256"] = prior["native_receipt_set_sha256"]
        self.assert_repeat_hold(current=current, previous=prior)

    def test_unknown_security_presence_does_not_promote(self):
        flags=dict(DEFAULT); flags.pop("security_p0_p1_present")
        out=decide(pulse(GREEN,6),flags,previous=pulse(GREEN,5))
        self.assertEqual(out["status"],"HOLD_SECURITY_CLASSIFICATION")

    def test_cleared_flag_cannot_override_known_critical_findings(self):
        out=decide(pulse(GREEN,6),dict(DEFAULT,security_p0_p1_present=True),previous=pulse(GREEN,5))
        self.assertEqual(out["status"],"HOLD_CRITICAL_SECURITY")

    def test_wrong_previous_schema_denominator_and_authority(self):
        keys={"schema":"other", "eligible_repos":9, "eligible_routes":99,
              "merge_admission":"GO", "qps_engineering_acceptance":True,
              "verified_zip_routes":0, "terminal_native_jobs":0, "planned_routes":3}
        for key,val in keys.items():
            with self.subTest(key=key):
                prior=pulse(GREEN,5);prior[key]=val
                self.assert_repeat_hold(previous=prior)

    def test_source_heads_drift_and_missing_digest(self):
        for key, val in (("source_heads_sha256", "b"*64),
                         ("source_heads_sha256", None),
                         ("native_receipt_set_sha256", "zz"),
                         ("scope_fingerprint", "../escape")):
            with self.subTest(key=key,val=val):
                prior=pulse(GREEN,5);prior[key]=val
                self.assert_repeat_hold(previous=prior)

    def test_reverse_trial_order_or_repeat_index_is_invalid(self):
        for prior_index, current_index in ((6, 6), (7, 6), (True, 6), (-1, 6)):
            with self.subTest(prev=prior_index):
                prev=pulse(GREEN,prior_index);cur=pulse(GREEN,current_index)
                self.assert_repeat_hold(current=cur, previous=prev)

    def test_false_pulse_index_is_not_numeric(self):
        cur=pulse(GREEN,True)
        self.assert_repeat_hold(current=cur)

    def test_previous_not_dictionary_is_hold(self):
        for value in (None, [], "5", False, 5):
            with self.subTest(previous=value):
                out=decide(pulse(GREEN,6),DEFAULT,previous=value)
                self.assertEqual(out["status"],"HOLD_REPEATABILITY")

    def test_reject_boolean_and_nonnumeric_counters(self):
        for name in ("planned_routes", "verified_zip_routes", "terminal_native_jobs"):
            for bad in (True, False, -1, 7, 4.0, "4", None):
                m=pulse(GREEN,6);m[name]=bad
                with self.subTest(counter=name,bad=bad), self.assertRaises(ScaleError):
                    decide(m,DEFAULT)

    def test_wrong_current_schema_and_authority_rejected(self):
        for name,bad in (("schema","wrong"),("eligible_repos",2),
                         ("eligible_routes",7),("merge_admission","PASS"),
                         ("qps_engineering_acceptance",None)):
            m=pulse(GREEN,6);m[name]=bad
            with self.subTest(name=name), self.assertRaises(ScaleError):
                decide(m,DEFAULT)

    def test_missing_owner_flags_never_grant_execution(self):
        for key in DEFAULT:
            with self.subTest(missing=key):
                f=dict(DEFAULT);f.pop(key)
                o=decide(pulse(GREEN,6),f,previous=pulse(GREEN,5))
                self.assertNotEqual(o["status"],"PROPOSE_3x6_OWNER_REVIEW")

    def test_no_forged_worker_hours_coverage_or_native_tests(self):
        for states in (HOLD, GREEN):
            o=decide(pulse(states),DEFAULT)
            self.assertIsNone(o["worker_hour_yield"])
            self.assertIsNone(o["matched_statement_branch_uplift"])
            self.assertIsNone(o["new_native_tests_credited"])
            self.assertFalse(o["dispatch_performed"])

    def test_repeated_calls_preserve_inputs(self):
        old=pulse(GREEN,5);current=pulse(GREEN,6);flags=copy.deepcopy(DEFAULT)
        frozen=(copy.deepcopy(old),copy.deepcopy(current),copy.deepcopy(flags))
        for i in range(16):
            self.assertEqual(decide(current,flags,previous=old)["status"],"PROPOSE_3x6_OWNER_REVIEW")
        self.assertEqual((old,current,flags),frozen)

    def test_unknown_population_and_invalid_flags_fail_closed(self):
        for m in (None,{},[],"wrong"):
            with self.subTest(metrics=m), self.assertRaises(ScaleError): decide(m,DEFAULT)
        for f in (None,[],"true"):
            with self.subTest(flags=f), self.assertRaises(ScaleError):decide(pulse(GREEN),f)


if __name__ == '__main__':unittest.main()
