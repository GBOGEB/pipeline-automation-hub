import base64
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "first_pass_closure_gate.py"
spec = importlib.util.spec_from_file_location("fpc", SCRIPT)
fpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fpc)

HEAD = "a" * 40
BASE = "c" * 40
REPO = "GBOGEB/example"
PR = 7
RUN = 12345
TRUSTED_WORKFLOW = "name: Trusted Proof\n"
PROTECTED = [
    "scripts/first_pass_closure_gate.py",
    "scripts/tests/test_first_pass_closure_gate.py",
    ".github/workflows/first-pass-closure-gate.yml",
    ".github/workflows/first-pass-closure-proof.yml",
    "mission-control/quality/FIRST_PASS_CLOSURE_POLICY_v1.json",
]
POLICY = {
    "codex_contract": {"reviewer_login": "chatgpt-codex-connector"},
    "protected_control_paths": PROTECTED,
    "proof_identity_allowlist": {
        "canonical_self_test": [
            {"repo": REPO, "workflow_name": "Trusted Proof", "workflow_path": ".github/workflows/trusted.yml"}
        ],
        "mutation_test": [
            {"repo": REPO, "workflow_name": "Trusted Proof", "workflow_path": ".github/workflows/trusted.yml"}
        ],
        "exact_head_ci": [
            {"repo": REPO, "workflow_name": "Trusted Proof", "workflow_path": ".github/workflows/trusted.yml"}
        ],
    },
}


class FakeClient:
    def __init__(self, mapping):
        self.mapping = mapping

    def get(self, path):
        if path not in self.mapping:
            raise AssertionError(path)
        return self.mapping[path]

    def get_all(self, path):
        if path not in self.mapping:
            raise AssertionError(path)
        return self.mapping[path]


def body(head=HEAD):
    obj = {
        "schema": "first_pass_closure/v1",
        "head_sha": head,
        "required_runs": [{"repo": REPO, "run_id": RUN}],
    }
    return "<!-- FPC_RECEIPT_V1 " + json.dumps(obj) + " -->"


def content_payload(text):
    return {
        "encoding": "base64",
        "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
    }


def mapping(
    pr_body=None,
    review_body=None,
    review_state=None,
    run_head=HEAD,
    run_conclusion="success",
    completed=True,
    summary_login="chatgpt-codex-connector[bot]",
    run_name="Trusted Proof",
    run_path=".github/workflows/trusted.yml",
    head_workflow=TRUSTED_WORKFLOW,
    base_workflow=TRUSTED_WORKFLOW,
    changed_files=None,
):
    summary = f"""<!-- codex-pull-request-review-summary -->
| Review | Status | Commit |
| --- | --- | --- |
| Code Review | {'**Completed**' if completed else '**Running**'} | `{HEAD[:7]}` |
"""
    reviews = []
    if review_body is not None:
        reviews = [{
            "state": review_state or "COMMENTED",
            "body": review_body,
            "user": {"login": "chatgpt-codex-connector[bot]"},
        }]
    return {
        f"/repos/{REPO}/pulls/{PR}": {
            "head": {"sha": HEAD},
            "base": {"sha": BASE},
            "body": pr_body if pr_body is not None else body(),
        },
        f"/repos/{REPO}/pulls/{PR}/files": [
            {"filename": path} for path in (changed_files or ["docs/canary.md"])
        ],
        f"/repos/{REPO}/actions/runs/{RUN}": {
            "status": "completed",
            "conclusion": run_conclusion,
            "head_sha": run_head,
            "name": run_name,
            "path": run_path,
        },
        f"/repos/{REPO}/contents/{run_path}?ref={run_head}": content_payload(head_workflow),
        f"/repos/{REPO}/contents/{run_path}?ref={BASE}": content_payload(base_workflow),
        f"/repos/{REPO}/issues/{PR}/comments": [{
            "id": 99,
            "body": summary,
            "user": {"login": summary_login},
        }],
        f"/repos/{REPO}/pulls/{PR}/reviews": reviews,
    }


class TestFirstPassClosureGate(unittest.TestCase):
    def test_clean_exact_head_passes_from_non_controller_candidate(self):
        receipt = fpc.evaluate(FakeClient(mapping()), REPO, PR, POLICY)
        self.assertEqual(receipt["status"], fpc.PASS_STATUS)
        self.assertEqual(set(receipt["proven_purposes"]), fpc.REQUIRED_PURPOSES)
        self.assertEqual(receipt["trusted_controller_revision"], BASE)

    def test_control_plane_mutation_rejected(self):
        with self.assertRaisesRegex(fpc.GateError, "CONTROL_PLANE_CHANGE_REQUIRES_BOOTSTRAP"):
            fpc.evaluate(
                FakeClient(mapping(changed_files=["scripts/first_pass_closure_gate.py"])),
                REPO,
                PR,
                POLICY,
            )

    def test_missing_receipt_rejected(self):
        with self.assertRaisesRegex(fpc.GateError, "MISSING_RECEIPT"):
            fpc.evaluate(FakeClient(mapping(pr_body="")), REPO, PR, POLICY)

    def test_stale_head_rejected(self):
        with self.assertRaisesRegex(fpc.GateError, "STALE_HEAD"):
            fpc.evaluate(FakeClient(mapping(pr_body=body("b" * 40))), REPO, PR, POLICY)

    def test_failed_run_rejected(self):
        with self.assertRaisesRegex(fpc.GateError, "RUN_NOT_SUCCESS"):
            fpc.evaluate(FakeClient(mapping(run_conclusion="failure")), REPO, PR, POLICY)

    def test_wrong_run_head_rejected(self):
        with self.assertRaisesRegex(fpc.GateError, "RUN_HEAD_MISMATCH"):
            fpc.evaluate(FakeClient(mapping(run_head="b" * 40)), REPO, PR, POLICY)

    def test_untrusted_workflow_identity_rejected(self):
        with self.assertRaisesRegex(fpc.GateError, "UNTRUSTED_PROOF_WORKFLOW_IDENTITY"):
            fpc.evaluate(FakeClient(mapping(run_name="Unrelated Workflow")), REPO, PR, POLICY)

    def test_mutated_allowlisted_workflow_rejected(self):
        with self.assertRaisesRegex(fpc.GateError, "PROOF_WORKFLOW_MUTATED_FROM_TRUSTED_BASE"):
            fpc.evaluate(
                FakeClient(mapping(head_workflow="name: Mutated Proof\n")),
                REPO,
                PR,
                POLICY,
            )

    def test_bot_suffix_is_bound_to_expected_codex_identity(self):
        self.assertTrue(
            fpc.login_matches(
                "chatgpt-codex-connector[bot]", "chatgpt-codex-connector"
            )
        )
        self.assertFalse(fpc.login_matches("other-bot[bot]", "chatgpt-codex-connector"))

    def test_review_not_completed_rejected(self):
        with self.assertRaisesRegex(fpc.GateError, "CODEX_REVIEW_NOT_COMPLETED"):
            fpc.evaluate(FakeClient(mapping(completed=False)), REPO, PR, POLICY)

    def test_exact_head_codex_finding_rejected(self):
        review = f"### Codex Review\n**Reviewed commit:** `{HEAD[:10]}`"
        with self.assertRaisesRegex(fpc.GateError, "CODEX_MATERIAL_FINDINGS"):
            fpc.evaluate(FakeClient(mapping(review_body=review)), REPO, PR, POLICY)

    def test_old_head_codex_finding_does_not_block(self):
        review = "### Codex Review\n**Reviewed commit:** `bbbbbbbbbb`"
        receipt = fpc.evaluate(FakeClient(mapping(review_body=review)), REPO, PR, POLICY)
        self.assertTrue(receipt["merge_allowed"])

    def test_missing_policy_becomes_gate_error(self):
        with self.assertRaisesRegex(fpc.GateError, "POLICY_LOAD_FAILED:MISSING"):
            fpc.load_policy("/definitely/not/present/fpc-policy.json")

    def test_invalid_policy_json_becomes_gate_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.json"
            path.write_text("{broken", encoding="utf-8")
            with self.assertRaisesRegex(fpc.GateError, "POLICY_LOAD_FAILED:INVALID_JSON"):
                fpc.load_policy(str(path))

    def test_policy_without_protected_paths_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.json"
            path.write_text(json.dumps({"proof_identity_allowlist": {}}), encoding="utf-8")
            with self.assertRaisesRegex(fpc.GateError, "PROTECTED_CONTROL_PATHS_MISSING"):
                fpc.load_policy(str(path))

    def test_final_receipt_validator_accepts_only_bound_pass(self):
        receipt = {
            "schema": fpc.PASS_SCHEMA,
            "status": fpc.PASS_STATUS,
            "head_sha": HEAD,
            "base_sha": BASE,
            "trusted_controller_revision": BASE,
            "merge_allowed": True,
            "codex_material_finding_review_count": 0,
            "authority_transfer": False,
            "formal_credit_delta": 0,
        }
        fpc.validate_pass_receipt(receipt, HEAD, BASE)

    def test_final_receipt_validator_rejects_synthesized_fail(self):
        receipt = fpc.fail_receipt("PRE_EVALUATOR_FAILURE")
        with self.assertRaisesRegex(fpc.GateError, "FINAL_RECEIPT_STATUS_NOT_PASS"):
            fpc.validate_pass_receipt(receipt, HEAD, BASE)

    def test_final_receipt_validator_rejects_wrong_head(self):
        receipt = {
            "schema": fpc.PASS_SCHEMA,
            "status": fpc.PASS_STATUS,
            "head_sha": "b" * 40,
            "base_sha": BASE,
            "trusted_controller_revision": BASE,
            "merge_allowed": True,
            "codex_material_finding_review_count": 0,
            "authority_transfer": False,
            "formal_credit_delta": 0,
        }
        with self.assertRaisesRegex(fpc.GateError, "FINAL_RECEIPT_HEAD_MISMATCH"):
            fpc.validate_pass_receipt(receipt, HEAD, BASE)


if __name__ == "__main__":
    unittest.main()
