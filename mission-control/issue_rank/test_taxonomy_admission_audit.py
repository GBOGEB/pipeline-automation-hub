"""Negative tests for GitHub readback admission audit; no merge API mutations."""
import copy
import unittest

import taxonomy_admission_audit as a

HEAD = "a" * 40
REQ = a.REQUIRED_CONTEXT


RUN_URL = "https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/40328204473"


def status(ident=40328204473, state="failure", when="2026-10-26T13:10:15Z",
           creator="github-actions[bot]", context=REQ, url=RUN_URL):
    return {"id": ident, "context": context, "state": state, "updated_at": when,
            "creator": {"login": creator}, "target_url": url}


def observation(required=False, merged=True, red=True, reviews=None, attested=True):
    rules = [
        {"type": "pull_request", "parameters": {
            "required_approving_review_count": 0, "dismiss_stale_reviews_on_push": True,
            "require_last_push_approval": False, "required_review_thread_resolution": True}},
        {"type": "required_status_checks", "parameters": {
            "strict_required_status_checks_policy": False,
            "required_status_checks": [{"context": REQ}] if required else [
                {"context": "GOGREEN required gate"}]}}]
    return {"schema": "jade.admission-observation.v1",
            "pull_request": {"repository": "GBOGEB/pipeline-automation-hub",
                             "number": 941, "head_sha": HEAD,
                             "merged": merged, "author": "owner",
                             "merged_at": "2026-10-26T13:10:31Z" if merged else None},
            "ruleset": {"enforcement": "active", "target": "branch", "rules": rules,
                        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"]}},
                        "bypass_actors": []},
            "commit_statuses": {"sha": HEAD, "statuses": [status()] if red else []},
            "effective_policy": {"sources": {
                "rules_for_branch": [REQ] if required else ["GOGREEN required gate"],
                "classic_branch_protection": []}} if attested else None,
            "reviews": reviews or []}


class AdmissionAudit(unittest.TestCase):
    def test_unrequired_red_before_merge_disproves_effective_fpc(self):
        r = a.audit(observation())
        self.assertEqual(r["merge_observation"], "MERGED_AFTER_UNREQUIRED_FPC_RED")
        self.assertEqual(r["red_before_merge"][0]["status_id"], 40328204473)
        self.assertIn("required_fpc_context", r["missing_controls"])
        self.assertFalse(r["blocked_red_canary_verified"])
        self.assertEqual(r["governed_admission"], "HOLD")

    def test_required_red_not_automatically_called_bypass(self):
        r = a.audit(observation(required=True))
        self.assertEqual(r["merge_observation"],
                         "POSSIBLE_ENFORCEMENT_FAILURE_REQUIRES_MERGE_API_AND_BYPASS_AUDIT")
        self.assertNotIn("required_fpc_context", r["missing_controls"])
        self.assertEqual(r["formal_credit_delta"], 0)

    def test_stale_wrong_head_or_late_red_is_not_before_merge(self):
        m = observation()
        m["commit_statuses"]["sha"] = "b" * 40
        with self.assertRaisesRegex(ValueError, "COMMIT_STATUSES_NOT_FOR_PR_HEAD"):
            a.audit(m)
        m = observation()
        m["commit_statuses"]["statuses"][0]["updated_at"] = "2026-10-26T13:11:00Z"
        self.assertEqual(a.audit(m)["red_before_merge"], [])

    def test_real_fpc_commit_status_shape_is_consumed(self):
        # Shape of GET /repos/{r}/commits/{sha}/statuses for the evaluator's post.
        r = a.audit(observation())
        self.assertEqual(r["red_before_merge"][0]["state"], "failure")
        self.assertEqual(r["red_before_merge"][0]["target_url"], RUN_URL)

    def test_red_replaced_by_green_before_merge_is_not_red(self):
        m = observation()
        m["commit_statuses"]["statuses"].append(
            status(ident=2, state="success", when="2026-10-26T13:10:20Z"))
        r = a.audit(m)
        self.assertEqual(r["red_before_merge"], [])
        self.assertEqual(r["merge_observation"], "MERGED_NO_QUALIFYING_RED_RECEIPT")

    def test_unauthenticated_fpc_status_is_ignored(self):
        for bad in (status(creator="mallory"),
                    status(url="https://evil.example/actions/runs/1")):
            m = observation()
            m["commit_statuses"]["statuses"] = [bad]
            self.assertEqual(a.audit(m)["red_before_merge"], [])

    def test_unrequired_needs_complete_effective_policy(self):
        r = a.audit(observation(attested=False))
        self.assertEqual(r["merge_observation"], "MERGED_AFTER_FPC_RED_REQUIREMENT_UNKNOWN")
        self.assertFalse(r["effective_policy_attested"])
        m = observation()
        del m["effective_policy"]["sources"]["classic_branch_protection"]
        self.assertEqual(a.audit(m)["merge_observation"],
                         "MERGED_AFTER_FPC_RED_REQUIREMENT_UNKNOWN")
        m = observation()
        m["effective_policy"]["sources"]["classic_branch_protection"] = [REQ]
        self.assertEqual(a.audit(m)["merge_observation"],
                         "POSSIBLE_ENFORCEMENT_FAILURE_REQUIRES_MERGE_API_AND_BYPASS_AUDIT")

    def test_no_merge_and_no_review_does_not_give_green(self):
        m = observation(merged=False)
        m["reviews"] = [{"state": "APPROVED", "user": "owner", "commit_id": HEAD}]
        r = a.audit(m)
        self.assertEqual(r["merge_observation"], "NO_MERGE_OBSERVED")
        self.assertFalse(r["eligible_approval_on_last_head_observed"])
        self.assertFalse(r["blocked_red_canary_verified"])

    def test_independent_exact_head_review_is_observation_not_authority(self):
        m = observation()
        m["reviews"] = [{"state": "APPROVED", "user": "reviewer2", "commit_id": HEAD},
                        {"state": "APPROVED", "user": "owner", "commit_id": "b"*40}]
        r = a.audit(m)
        self.assertTrue(r["eligible_approval_on_last_head_observed"])
        self.assertEqual(r["governed_admission"], "HOLD")

    def test_fabricated_boolean_canary_never_becomes_qualified_proof(self):
        m = observation(required=True, merged=False)
        m["canary"] = {"head_sha": HEAD, "merge_api_rejected": True,
                       "required_check_failed": True}
        r = a.audit(m)
        self.assertFalse(r["blocked_red_canary_verified"])
        self.assertNotIn("main_targeted", r["missing_controls"])

    def test_canary_consistency_requires_eligible_approval(self):
        m = observation(required=True, merged=False)
        rules = m["ruleset"]["rules"]
        rules[0]["parameters"].update(required_approving_review_count=1,
                                      require_last_push_approval=True)
        rules[1]["parameters"]["strict_required_status_checks_policy"] = True
        m["canary"] = {"head_sha": HEAD, "merge_api_rejected": True,
                       "required_check_failed": True}
        r = a.audit(m)
        self.assertEqual(r["missing_controls"], [])
        self.assertFalse(r["blocked_red_canary_claim_consistent"])
        m["reviews"] = [{"state": "APPROVED", "user": "reviewer2", "commit_id": HEAD}]
        self.assertTrue(a.audit(m)["blocked_red_canary_claim_consistent"])

    def test_fail_closed_unknown_schema_shas_rules_review_and_times(self):
        m = observation()
        m["schema"] = "fake"
        with self.assertRaisesRegex(ValueError, "OBSERVATION_SCHEMA"):
            a.audit(m)
        m = observation()
        m["pull_request"]["head_sha"] = "abc"
        with self.assertRaisesRegex(ValueError, "PR_HEAD_NOT_EXACT"):
            a.audit(m)
        m = observation()
        m["reviews"] = None
        with self.assertRaisesRegex(ValueError, "REVIEW_LIST_NOT_RETURNED"):
            a.audit(m)
        m = observation()
        m["commit_statuses"]["statuses"].append(
            copy.deepcopy(m["commit_statuses"]["statuses"][0]))
        with self.assertRaisesRegex(ValueError, "DUPLICATE_OR_INVALID"):
            a.audit(m)

    def test_without_main_target_scope_hard_gap(self):
        m = observation()
        m["ruleset"]["conditions"]["ref_name"]["include"] = []
        self.assertIn("main_targeted", a.audit(m)["missing_controls"])


if __name__ == "__main__":
    unittest.main()
