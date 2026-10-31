"""Offline safeguards for the governed ruleset controller."""
import copy
import json
import pathlib
import tempfile
import unittest

import ctl

ROOT = pathlib.Path(__file__).resolve().parent


class ProtectionPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = ctl.load_policy(ROOT / "policy.json")

    def entry(self, name):
        return ctl.select(self.policy, "GBOGEB/" + name)

    def test_four_explicit_pilot_repositories(self):
        self.assertEqual({x["repo"] for x in self.policy["repositories"]}, {
            "GBOGEB/ABACUS", "GBOGEB/CODEX",
            "GBOGEB/cryoplant-project", "GBOGEB/pipeline-automation-hub"
        })

    def test_fail_closed_review_integrity(self):
        for e in self.policy["repositories"]:
            p = ctl.render(self.policy, e, "core")
            self.assertEqual(p["bypass_actors"], [])
            self.assertEqual(p["conditions"]["ref_name"]["include"],
                             ["~DEFAULT_BRANCH"])
            self.assertEqual({x["type"] for x in p["rules"]},
                             {"deletion", "non_fast_forward", "pull_request"})
            req = next(x for x in p["rules"] if x["type"] == "pull_request")
            params = req["parameters"]
            self.assertGreaterEqual(params["required_approving_review_count"], 1)
            self.assertTrue(params["required_review_thread_resolution"])
            self.assertTrue(params["require_last_push_approval"])
            self.assertTrue(params["dismiss_stale_reviews_on_push"])

    def test_core_has_no_unproven_required_checks(self):
        for e in self.policy["repositories"]:
            p = ctl.render(self.policy, e, "core")
            self.assertNotIn("required_status_checks", [r["type"] for r in p["rules"]])

    def test_full_preserves_core_and_strict_checks(self):
        e = self.entry("pipeline-automation-hub")
        base = ctl.render(self.policy, e, "core")
        full = ctl.render(self.policy, e, "full")
        self.assertEqual(full["rules"][:3], base["rules"])
        checks = full["rules"][-1]["parameters"]
        self.assertEqual([x["context"] for x in checks["required_status_checks"]],
                         ["First-Pass Closure Gate / first-pass-closure"])
        self.assertTrue(checks["strict_required_status_checks_policy"])

    def test_qps_cannot_require_missing_always_on_check(self):
        with self.assertRaisesRegex(ctl.Hold, "Full stage"):
            ctl.render(self.policy, self.entry("cryoplant-project"), "full")

    def test_only_abacus_empty_ruleset_is_repairable(self):
        e = self.entry("ABACUS")
        core = ctl.render(self.policy, e, "core")
        old = copy.deepcopy(core)
        old["rules"] = []
        old["id"] = 24494381
        self.assertEqual(ctl.candidate_write(old, core, core, e, "core"),
                         "REPAIR_EMPTY_EXISTING")
        old["id"] = 10
        with self.assertRaises(ctl.Hold):
            ctl.candidate_write(old, core, core, e, "core")

    def test_full_promotion_only_from_exact_core(self):
        e = self.entry("CODEX")
        base = ctl.render(self.policy, e, "core")
        full = ctl.render(self.policy, e, "full")
        self.assertEqual(ctl.candidate_write(base, full, base, e, "full"),
                         "PROMOTE_VERIFIED_CORE")
        with self.assertRaises(ctl.Hold):
            ctl.candidate_write(full, base, base, e, "core")

    def test_unknown_or_weakened_policy_rejected(self):
        p = copy.deepcopy(self.policy)
        p["common"]["required_approving_review_count"] = 0
        with tempfile.TemporaryDirectory() as d:
            f = pathlib.Path(d) / "policy.json"
            f.write_text(json.dumps(p), encoding="utf-8")
            with self.assertRaises(ctl.Hold):
                ctl.load_policy(f)

    def test_no_implicit_extra_repository(self):
        with self.assertRaises(ctl.Hold):
            ctl.select(self.policy, "GBOGEB/unknown")

    def test_no_live_api_needed_for_offline_plan(self):
        self.assertEqual(ctl.render(self.policy, self.entry("ABACUS"), "core")["enforcement"], "active")


if __name__ == "__main__":
    unittest.main()


def test_zz_canary_g_pah():
    assert False, "red canary: proves CI collects this family"
