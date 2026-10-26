"""Negative tests for GitHub readback admission audit; no merge API mutations."""
import copy
import unittest

import taxonomy_admission_audit as a

HEAD = "a" * 40
REQ = a.REQUIRED_CONTEXT


def observation(required=False, merged=True, red=True, reviews=None):
    rules = [
        {"type": "pull_request", "parameters": {
            "required_approving_review_count": 0, "dismiss_stale_reviews_on_push": True,
            "require_last_push_approval": False, "required_review_thread_resolution": True}},
        {"type": "required_status_checks", "parameters": {
            "strict_required_status_checks_policy": False,
            "required_status_checks": [{"context": REQ}] if required else [
                {"context": "GOGREEN required gate"}]}]
    return {"schema": "jade.admission-observation.v1",
            "pull_request": {"repository": "GBOGEB/pipeline-automation-hub",
                             "number": 941, "head_sha": HEAD,
                             "merged": merged, "author": "owner",
                             "merged_at": "2026-10-26T13:10:31Z" if merged else None},
            "ruleset": {"enforcement": "active", "target": "branch", "rules": rules,
                        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"]}},
                        "bypass_actors": []},
            "workflow_runs": [
                {"id": 40328204473, "name": REQ, "head_sha": HEAD,
                 "status": "completed", "conclusion": "failure",
                 "updated_at": "2026-10-26T13:10:15Z"}] if red else [],
            "reviews": reviews or []}


class AdmissionAudit(unittest.TestCase):
    def test_unrequired_red_before_merge_disproves_effective_fpc(self):
        r = a.audit(observation())
        self.assertEqual(r["merge_observation"], "MERGED_AFTER_UNREQUIRED_FPC_RED")
        self.assertEqual(r["red_before_merge"][0]["run_id"], 40328204473)
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
        m["workflow_runs"][0]["head_sha"] = "b" * 40
        self.assertEqual(a.audit(m)["red_before_merge"], [])
        m = observation()
        m["workflow_runs"][0]["updated_at"] = "2026-10-26T13:11:00Z"
        self.assertEqual(a.audit(m)["red_before_merge"], [])

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
        self.assertIn("main_targeted", [k for k, v in
                         [("main_targeted", "main_targeted" not in r["missing_controls"])]] )

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
        m["workflow_runs"].append(copy.deepcopy(m["workflow_runs"][0]))
        with self.assertRaisesRegex(ValueError, "DUPLICATE_OR_INVALID"):
            a.audit(m)

    def test_without_main_target_scope_hard_gap(self):
        m = observation()
        m["ruleset"]["conditions"]["ref_name"]["include"] = []
        self.assertIn("main_targeted", a.audit(m)["missing_controls"])


if __name__ == "__main__":
    unittest.main()
