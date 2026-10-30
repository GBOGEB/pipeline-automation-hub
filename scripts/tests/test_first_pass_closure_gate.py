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
    changed_file_rows=None,
    head_runs=None,
    pr_author="GBOGEB",
    commit_authors=("GBOGEB",),
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
            "user": {"login": pr_author},
        },
        f"/repos/{REPO}/pulls/{PR}/commits": [{"author": {"login": a}} for a in commit_authors],
        f"/repos/{REPO}/actions/runs?head_sha={HEAD}&per_page=100&page=1": {
            "workflow_runs": head_runs if head_runs is not None else [
                {"id": RUN, "run_number": 5, "head_sha": run_head, "name": run_name, "path": run_path}
            ]
        },
        f"/repos/{REPO}/pulls/{PR}/files": (
            changed_file_rows
            if changed_file_rows is not None
            else [{"filename": path} for path in (changed_files or ["docs/canary.md"])]
        ),
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

    def test_renamed_control_plane_path_rejected(self):
        with self.assertRaisesRegex(
            fpc.GateError, "CONTROL_PLANE_CHANGE_REQUIRES_BOOTSTRAP"
        ):
            fpc.evaluate(
                FakeClient(
                    mapping(
                        changed_file_rows=[
                            {
                                "filename": "archive/first-pass-closure-gate.yml",
                                "previous_filename": ".github/workflows/first-pass-closure-gate.yml",
                                "status": "renamed",
                            }
                        ]
                    )
                ),
                REPO,
                PR,
                POLICY,
            )

    def test_malformed_body_receipt_rejected(self):
        bad = "<!-- FPC_RECEIPT_V1 {\"schema\": \"first_pass_closure/v1\"} -->"
        with self.assertRaisesRegex(fpc.GateError, "INVALID_RECEIPT_FIELDS"):
            fpc.evaluate(FakeClient(mapping(pr_body=bad)), REPO, PR, POLICY)

    # Without a body receipt the trusted controller derives the proof runs on the exact head.
    def test_receipt_derived_from_exact_head_runs_passes(self):
        receipt = fpc.evaluate(FakeClient(mapping(pr_body="")), REPO, PR, POLICY)
        self.assertEqual(receipt["status"], fpc.PASS_STATUS)
        self.assertEqual(receipt["receipt_source"], "DERIVED_EXACT_HEAD")
        self.assertEqual([r["run_id"] for r in receipt["required_runs"]], [RUN])

    def test_body_receipt_is_still_the_source_when_present(self):
        receipt = fpc.evaluate(FakeClient(mapping()), REPO, PR, POLICY)
        self.assertEqual(receipt["receipt_source"], "PR_BODY")

    def test_derived_newest_red_run_is_not_hidden_by_older_green(self):
        newer = RUN + 1
        m = mapping(pr_body="", head_runs=[
            {"id": RUN, "run_number": 5, "head_sha": HEAD, "name": "Trusted Proof", "path": ".github/workflows/trusted.yml"},
            {"id": newer, "run_number": 6, "head_sha": HEAD, "name": "Trusted Proof", "path": ".github/workflows/trusted.yml"},
        ])
        m[f"/repos/{REPO}/actions/runs/{newer}"] = {**m[f"/repos/{REPO}/actions/runs/{RUN}"], "conclusion": "failure"}
        with self.assertRaisesRegex(fpc.GateError, f"RUN_NOT_SUCCESS: {REPO}#{newer}"):
            fpc.evaluate(FakeClient(m), REPO, PR, POLICY)

    def test_derived_without_allowlisted_run_rejected(self):
        runs = [{"id": 9, "run_number": 1, "head_sha": HEAD, "name": "Unrelated", "path": ".github/workflows/other.yml"},
                {"id": 8, "run_number": 1, "head_sha": "b" * 40, "name": "Trusted Proof",
                 "path": ".github/workflows/trusted.yml"}]
        with self.assertRaisesRegex(fpc.GateError, "NO_ALLOWLISTED_PROOF_RUN_ON_EXACT_HEAD"):
            fpc.evaluate(FakeClient(mapping(pr_body="", head_runs=runs)), REPO, PR, POLICY)

    def test_derived_failed_proof_rejected(self):
        with self.assertRaisesRegex(fpc.GateError, "RUN_NOT_SUCCESS"):
            fpc.evaluate(FakeClient(mapping(pr_body="", run_conclusion="failure")), REPO, PR, POLICY)

    # Dependency-update exemption: only the declared bot, only dependency paths, proofs still required.
    DEP_POLICY = {**POLICY, "dependency_update_exemption": {
        "author_login": "dependabot[bot]",
        "allowed_path_patterns": ["requirements*.txt", "*/requirements*.txt", ".github/workflows/*.yml"],
        "waives": ["CODEX_REVIEW"]}}

    def dep(self, **kw):
        args = {"pr_body": "", "completed": False, "pr_author": "dependabot[bot]",
                "commit_authors": ("dependabot[bot]",), "changed_files": ["scripts/requirements.txt"], **kw}
        return FakeClient(mapping(**args))

    def test_dependabot_update_waives_codex_only(self):
        receipt = fpc.evaluate(self.dep(), REPO, PR, self.DEP_POLICY)
        self.assertEqual(receipt["status"], fpc.PASS_STATUS)
        self.assertEqual(receipt["dependency_update_exemption"]["waives"], ["CODEX_REVIEW"])
        self.assertIsNone(receipt["codex_summary_comment_id"])

    def test_dependabot_update_still_needs_green_proof(self):
        with self.assertRaisesRegex(fpc.GateError, "RUN_NOT_SUCCESS"):
            fpc.evaluate(self.dep(run_conclusion="failure"), REPO, PR, self.DEP_POLICY)

    def test_human_commit_on_dependabot_branch_loses_exemption(self):
        with self.assertRaisesRegex(fpc.GateError, "CODEX_REVIEW_NOT_COMPLETED"):
            fpc.evaluate(self.dep(commit_authors=("dependabot[bot]", "GBOGEB")), REPO, PR, self.DEP_POLICY)

    def test_dependabot_change_outside_dependency_paths_loses_exemption(self):
        with self.assertRaisesRegex(fpc.GateError, "CODEX_REVIEW_NOT_COMPLETED"):
            fpc.evaluate(self.dep(changed_files=["scripts/requirements.txt", "scripts/run.py"]),
                         REPO, PR, self.DEP_POLICY)

    def test_other_author_never_gets_exemption(self):
        with self.assertRaisesRegex(fpc.GateError, "CODEX_REVIEW_NOT_COMPLETED"):
            fpc.evaluate(self.dep(pr_author="GBOGEB"), REPO, PR, self.DEP_POLICY)

    def test_exemption_cannot_touch_control_plane(self):
        with self.assertRaisesRegex(fpc.GateError, "CONTROL_PLANE_CHANGE_REQUIRES_BOOTSTRAP"):
            fpc.evaluate(self.dep(changed_files=[".github/workflows/first-pass-closure-gate.yml"]),
                         REPO, PR, self.DEP_POLICY)

    def test_exemption_waiving_anything_but_codex_is_invalid_policy(self):
        policy = {**POLICY, "dependency_update_exemption": {
            **self.DEP_POLICY["dependency_update_exemption"], "waives": ["CODEX_REVIEW", "EXACT_HEAD_CI"]}}
        with self.assertRaisesRegex(fpc.GateError, "POLICY_DEPENDENCY_EXEMPTION_INVALID"):
            fpc.evaluate(self.dep(), REPO, PR, policy)

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


    def test_workflow_never_falls_back_to_event_ref_after_pr_resolution_failure(self):
        workflow = (
            ROOT.parent / ".github/workflows/first-pass-closure-gate.yml"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "if: steps.pr.outcome == 'success' && steps.pr.outputs.base_sha != ''",
            workflow,
        )
        self.assertIn("ref: ${{ steps.pr.outputs.base_sha }}", workflow)

    def test_workflow_rechecks_when_the_proof_completes(self):
        # A derived receipt exists only after the proof run finishes, so that completion must
        # re-run the gate, serialised per PR and never trusting the triggering run's checkout.
        workflow = (
            ROOT.parent / ".github/workflows/first-pass-closure-gate.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("workflow_run:\n    workflows: [First-Pass Closure Proof]\n    types: [completed]", workflow)
        self.assertIn("github.event.workflow_run.pull_requests[0].number || inputs.pr_number", workflow)
        self.assertIn("github.event.workflow_run.head_repository.full_name == github.repository", workflow)
        self.assertIn('TRIGGER_HEAD_SHA="${{ github.event.workflow_run.head_sha }}"', workflow)
        self.assertNotIn("workflow_run.head_branch", workflow)

    def test_repository_policy_exemption_is_valid_and_narrow(self):
        policy = fpc.load_policy(str(ROOT.parent / "mission-control/quality/FIRST_PASS_CLOSURE_POLICY_v1.json"))
        rule = policy["dependency_update_exemption"]
        self.assertEqual(rule["waives"], ["CODEX_REVIEW"])
        self.assertEqual(rule["author_login"], "dependabot[bot]")
        import fnmatch
        self.assertFalse(any(fnmatch.fnmatchcase("scripts/first_pass_closure_gate.py", p)
                             for p in rule["allowed_path_patterns"]))



if __name__ == "__main__":
    unittest.main()
