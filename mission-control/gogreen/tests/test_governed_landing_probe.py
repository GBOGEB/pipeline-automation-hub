"""Synthetic negative/adversarial source-bound governance admission QA."""
from __future__ import annotations

import copy
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
HERE = ROOT / "required_gate" / "governed_landing_probe.py"
spec = importlib.util.spec_from_file_location("governed_landing_probe", HERE)
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)

HEAD, BASE = "a" * 40, "b" * 40


def pr():
    return {"number": 881, "state": "open", "draft": False, "merged_at": None,
            "user": {"login": "owner", "type": "User"},
            "head": {"sha": HEAD}, "base": {"sha": BASE}}


def policy():
    return {
        "id": P.RULESET_ID, "target": "branch", "enforcement": "active",
        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
        "bypass_actors": [],
        "rules": [
            {"type": "deletion"}, {"type": "non_fast_forward"},
            {"type": "pull_request", "parameters": {
                "required_approving_review_count": 1,
                "dismiss_stale_reviews_on_push": True,
                "require_last_push_approval": True,
                "required_review_thread_resolution": True}},
            {"type": "required_status_checks", "parameters": {
                "strict_required_status_checks_policy": True,
                "required_status_checks": [
                    {"context": name} for name in P.REQUIRED_NAMES]}}
        ]}


def human():
    return [{"id": 3, "submitted_at": "2026-10-26T02:00:00Z",
             "state": "APPROVED", "commit_id": HEAD,
             "user": {"login": "independent", "type": "User"}}]


def checks():
    return [{"id": 50 + i, "name": name, "head_sha": HEAD,
             "status": "completed", "conclusion": "success",
             "completed_at": "2026-10-26T02:01:00Z"}
            for i, name in enumerate(P.REQUIRED_NAMES)]


def rejection():
    return {"proof_class": "GITHUB_REJECTED_RED_MERGE",
            "head_sha": HEAD, "rule_id": P.RULESET_ID,
            "external_rejection_receipt_digest": "1" * 64}


def result(x=None, *, r=None, v=None, c=None, **kw):
    return P.classify(x if x is not None else pr(),
                      r if r is not None else policy(),
                      v if v is not None else human(),
                      c if c is not None else checks(),
                      checks_complete=True, threads_complete=True,
                      blocked_red_receipt=rejection(), second_head=HEAD,
                      **kw)


def statuses(doc):
    return {g["gate"]: g["state"] for g in doc["gates"]}


class NonCompensatingGovernance(unittest.TestCase):
    def test_complete_fixture_still_never_grants_merge_authority(self):
        x = result()
        self.assertEqual(x["hold_count"], 0)
        self.assertEqual(x["readiness"], "CANDIDATE_REQUIRES_HUMAN_ADMISSION")
        self.assertFalse(x["merge_allowed"])
        self.assertEqual(x["formal_engineering_credit_delta"], 0)
        self.assertEqual(x["qps_owner_acceptance"], "NOT_ESTABLISHED")

    def test_actual_hub_ruleset_zero_reviews_and_no_last_push_holds(self):
        p = policy()
        rules = next(x["parameters"] for x in p["rules"] if x["type"] == "pull_request")
        rules["required_approving_review_count"] = 0
        rules["require_last_push_approval"] = False
        s = next(x["parameters"] for x in p["rules"] if x["type"] == "required_status_checks")
        s["strict_required_status_checks_policy"] = False
        x = result(r=p)
        self.assertEqual(x["readiness"], "HOLD")
        self.assertEqual(statuses(x)["at_least_one_required_human_approval"], "HOLD")
        self.assertEqual(statuses(x)["last_push_approval_enforced"], "HOLD")
        self.assertEqual(statuses(x)["up_to_date_before_merge"], "HOLD")

    def test_bot_comment_is_not_human_approval(self):
        reviews = [{"id": 7, "submitted_at": "2026-10-26T02:00:00Z",
                    "state": "COMMENTED", "commit_id": HEAD,
                    "user": {"login": "chatgpt-codex-connector", "type": "Bot"}}]
        x = result(v=reviews)
        self.assertEqual(x["observed_eligible_human_approvals"], 0)
        self.assertEqual(statuses(x)["eligible_independent_exact_head_human_review"], "HOLD")

    def test_owner_self_approval_rejected(self):
        v = human()
        v[0]["user"]["login"] = "owner"
        self.assertEqual(result(v=v)["observed_eligible_human_approvals"], 0)

    def test_stale_head_approval_rejected(self):
        v = human()
        v[0]["commit_id"] = BASE
        self.assertEqual(result(v=v)["observed_eligible_human_approvals"], 0)

    def test_later_request_for_changes_supersedes_approval(self):
        v = human()
        v.append({**copy.deepcopy(v[0]), "id": 4,
                  "submitted_at": "2026-10-26T02:03:00Z",
                  "state": "CHANGES_REQUESTED"})
        self.assertEqual(result(v=v)["observed_eligible_human_approvals"], 0)

    def test_source_head_moved_mid_census_is_hold(self):
        x = P.classify(pr(), policy(), human(), checks(),
                       checks_complete=True, threads_complete=True,
                       blocked_red_receipt=rejection(), second_head=BASE)
        self.assertEqual(statuses(x)["same_exact_pr_head_twice"], "HOLD")

    def test_required_status_missing_is_unknown_not_pass(self):
        x = result(c=checks()[:-1])
        self.assertEqual(statuses(x)["latest_exact_head_native_required_checks"], "HOLD")

    def test_latest_cancelled_overrides_previous_success(self):
        c = checks()
        c.append({**c[0], "id": 901, "completed_at": "2026-10-26T02:02:00Z",
                  "status": "completed", "conclusion": "cancelled"})
        self.assertEqual(statuses(result(c=c))["latest_exact_head_native_required_checks"], "HOLD")

    def test_incomplete_paginated_check_population_is_hold(self):
        x = P.classify(pr(), policy(), human(), checks(),
                       checks_complete=False, threads_complete=True,
                       blocked_red_receipt=rejection(), second_head=HEAD)
        self.assertEqual(statuses(x)["latest_exact_head_native_required_checks"], "HOLD")

    def test_unresolved_or_unread_threads_is_hold(self):
        x = P.classify(pr(), policy(), human(), checks(),
                       checks_complete=True, threads_complete=False,
                       blocked_red_receipt=rejection(), second_head=HEAD)
        self.assertEqual(statuses(x)["all_review_threads_verified_resolved"], "HOLD")

    def test_missing_platform_rejected_red_canary_is_hold(self):
        x = P.classify(pr(), policy(), human(), checks(),
                       checks_complete=True, threads_complete=True,
                       blocked_red_receipt=None, second_head=HEAD)
        self.assertEqual(statuses(x)["blocked_red_canary_platform_rejection"], "HOLD")

    def test_rule_bypass_or_inactive_enforcement_holds(self):
        p = policy()
        p["bypass_actors"] = [{"actor_id": 123, "bypass_mode": "always"}]
        self.assertEqual(statuses(result(r=p))[
            "effective_ruleset_applies_no_bypass"], "HOLD")
        p = policy()
        p["enforcement"] = "disabled"
        self.assertEqual(statuses(result(r=p))[
            "effective_ruleset_applies_no_bypass"], "HOLD")

    def test_different_source_sha_check_not_accepted(self):
        c = checks()
        c[0]["head_sha"] = BASE
        self.assertEqual(statuses(result(c=c))[
            "latest_exact_head_native_required_checks"], "HOLD")

    def test_draft_or_merged_pr_is_not_landing_candidate(self):
        x = pr()
        x["draft"] = True
        self.assertEqual(statuses(result(x))["candidate_open_non_draft"], "HOLD")
        y = pr()
        y["merged_at"] = "2026-10-26T02:00:00Z"
        self.assertEqual(statuses(result(y))["candidate_open_non_draft"], "HOLD")

    def test_collector_does_not_accept_non_allowlisted_repository(self):
        class MockOpener:
            pass
        obj = P.Reader("synthetic-token-not-real")
        with self.assertRaisesRegex(ValueError, "non-allowlisted"):
            obj.get("/repos/other/repo/issues")

    def test_external_access_errors_do_not_create_green_evidence(self):
        x = P.classify(pr(), policy(), human(), checks(),
                       checks_complete=True, threads_complete=True,
                       blocked_red_receipt=rejection(),
                       read_error="403", second_head=HEAD)
        self.assertEqual(statuses(x)["authenticated_complete_readback"], "HOLD")


if __name__ == "__main__":
    unittest.main()
