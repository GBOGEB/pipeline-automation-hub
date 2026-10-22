"""G3G guardrail tests: no PR-authored proof can self-certify closure."""
import json
import unittest

import g3g_fpc_preflight as fpc

SHA = "a" * 40
BASE = "b" * 40


def pr(body="", head=SHA):
    return {"number": 668, "head_sha": head, "base_sha": BASE, "body": body}


def marker(run_id=123, head=SHA, repo="GBOGEB/pipeline-automation-hub"):
    d = {"schema": "first_pass_closure/v1", "head_sha": head,
         "required_runs": [{"repo": repo, "run_id": run_id}]}
    return "<!-- FPC_RECEIPT_V1 " + json.dumps(d) + " -->"


def native(run_id=123, head=SHA, status="completed", conclusion="success"):
    return {"repo": "GBOGEB/pipeline-automation-hub", "run_id": run_id,
            "head_sha": head, "status": status, "conclusion": conclusion}


class G3GFirstPassDiagnostics(unittest.TestCase):
    def test_real_shape_missing_receipt_is_first_red(self):
        x = fpc.diagnose(pr("Plain PR narrative"), [native()])
        self.assertEqual(x["first_red_fingerprint"], "FPC_MISSING_RECEIPT")
        self.assertEqual(x["merge_admission"], "HOLD")

    def test_bad_json_not_treated_as_absent(self):
        x = fpc.diagnose(pr("<!-- FPC_RECEIPT_V1 {bad} -->"), [native()])
        self.assertEqual(x["first_red_fingerprint"], "FPC_INVALID_RECEIPT_JSON")

    def test_stale_exact_head_rejected(self):
        x = fpc.diagnose(pr(marker(head=BASE)), [native()])
        self.assertEqual(x["first_red_fingerprint"], "FPC_STALE_RECEIPT_HEAD")

    def test_correct_marker_but_no_fetched_run_remains_red(self):
        x = fpc.diagnose(pr(marker()), [])
        self.assertEqual(x["first_red_fingerprint"], "FPC_NATIVE_RUN_NOT_FETCHED")

    def test_failed_native_run_remains_red(self):
        x = fpc.diagnose(pr(marker()), [native(conclusion="failure")])
        self.assertEqual(x["first_red_fingerprint"], "FPC_NATIVE_RUN_NOT_SUCCESS")

    def test_queued_native_run_remains_red(self):
        x = fpc.diagnose(pr(marker()), [native(status="queued", conclusion=None)])
        self.assertEqual(x["first_red_fingerprint"], "FPC_NATIVE_RUN_NOT_SUCCESS")

    def test_unrelated_run_head_rejected(self):
        x = fpc.diagnose(pr(marker()), [native(head=BASE)])
        self.assertEqual(x["first_red_fingerprint"], "FPC_NATIVE_RUN_HEAD_MISMATCH")

    def test_successful_run_cannot_self_attest_three_proof_purposes(self):
        x = fpc.diagnose(pr(marker()), [native()])
        self.assertEqual(x["first_red_fingerprint"],
                         "FPC_TRUSTED_PROOF_AND_REVIEW_UNVERIFIED")
        self.assertIsNone(x["independent_human_approval"])
        self.assertIsNone(x["effective_required_status"])
        self.assertIsNone(x["trusted_controller_verdict"])
        self.assertEqual(x["formal_credit_delta"], 0)

    def test_no_run_ids_rejected(self):
        d = {"schema": "first_pass_closure/v1", "head_sha": SHA,
             "required_runs": []}
        x = fpc.diagnose(pr("<!-- FPC_RECEIPT_V1 " + json.dumps(d) + " -->"), [])
        self.assertEqual(x["first_red_fingerprint"], "FPC_REQUIRED_RUNS_MISSING")

    def test_duplicate_run_spec_cannot_inflate_evidence(self):
        d = {"schema": "first_pass_closure/v1", "head_sha": SHA,
             "required_runs": [{"repo": "GBOGEB/pipeline-automation-hub",
                                "run_id": 123}] * 2}
        x = fpc.diagnose(pr("<!-- FPC_RECEIPT_V1 " + json.dumps(d) + " -->"), [])
        self.assertEqual(x["first_red_fingerprint"], "FPC_DUPLICATE_RUN_ID")

    def test_invalid_run_identity_rejected(self):
        d = {"schema": "first_pass_closure/v1", "head_sha": SHA,
             "required_runs": [{"repo": "GBOGEB/pipeline-automation-hub",
                                "run_id": True}]}
        x = fpc.diagnose(pr("<!-- FPC_RECEIPT_V1 " + json.dumps(d) + " -->"), [])
        self.assertEqual(x["first_red_fingerprint"], "FPC_INVALID_PROOF_IDENTITY")

    def test_invalid_pr_source_sha_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "EXACT_HEAD"):
            fpc.diagnose(pr(head="main"), [])

    def test_malformed_receipt_fields_rejected(self):
        d = {"schema": "first_pass_closure/v1", "head_sha": SHA,
             "required_runs": [{"repo": "GBOGEB/pipeline-automation-hub",
                                "run_id": 123}], "merge_allowed": True}
        x = fpc.diagnose(pr("<!-- FPC_RECEIPT_V1 " + json.dumps(d) + " -->"), [])
        self.assertEqual(x["first_red_fingerprint"],
                         "FPC_RECEIPT_SCHEMA_OR_FIELDS")


if __name__ == "__main__":
    unittest.main()
