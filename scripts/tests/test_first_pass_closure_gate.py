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
REPO = "GBOGEB/example"
PR = 7
RUN = 12345
TRUSTED_PATHS = [
    ".github/workflows/trusted.yml",
    "scripts/trusted.py",
]

POLICY = {
    "proof_identity_allowlist": {
        "canonical_self_test": [
            {
                "repo": REPO,
                "workflow_name": "Trusted Proof",
                "workflow_path": ".github/workflows/trusted.yml",
            }
        ],
        "mutation_test": [
            {
                "repo": REPO,
                "workflow_name": "Trusted Proof",
                "workflow_path": ".github/workflows/trusted.yml",
            }
        ],
        "exact_head_ci": [
            {
                "repo": REPO,
                "workflow_name": "Trusted Proof",
                "workflow_path": ".github/workflows/trusted.yml",
            }
        ],
    },
    "trusted_proof_surface": {
        "reference_ref": "master",
        "paths": TRUSTED_PATHS,
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


def mapping(
    pr_body=None,
    review_body=None,
    review_state=None,
    run_head=HEAD,
    run_conclusion="success",
    completed=True,
    summary_login="chatgpt-codex-connector",
    run_name="Trusted Proof",
    run_path=".github/workflows/trusted.yml",
    mutate_path=None,
):
    summary = f"""<!-- codex-pull-request-review-summary -->
| Review | Status | Commit |
| --- | --- | --- |
| Code Review | {'**Completed**' if completed else '**Running**'} | `{HEAD[:7]}` |
"""
    reviews = []
    if review_body is not None:
        reviews = [
            {
                "state": review_state or "COMMENTED",
                "body": review_body,
                "user": {"login": "chatgpt-codex-connector"},
            }
        ]
    rows = {
        f"/repos/{REPO}/pulls/{PR}": {
            "head": {"sha": HEAD},
            "body": pr_body if pr_body is not None else body(),
        },
        f"/repos/{REPO}/actions/runs/{RUN}": {
            "status": "completed",
            "conclusion": run_conclusion,
            "head_sha": run_head,
            "name": run_name,
            "path": run_path,
        },
        f"/repos/{REPO}/issues/{PR}/comments": [
            {"id": 99, "body": summary, "user": {"login": summary_login}}
        ],
        f"/repos/{REPO}/pulls/{PR}/reviews": reviews,
    }
    for i, path in enumerate(TRUSTED_PATHS):
        trusted_sha = f"sha-{i}"
        head_sha = "different" if path == mutate_path else trusted_sha
        rows[f"/repos/{REPO}/contents/{path}?ref=master"] = {"sha": trusted_sha}
        rows[f"/repos/{REPO}/contents/{path}?ref={HEAD}"] = {"sha": head_sha}
    return rows


class TestFirstPassClosureGate(unittest.TestCase):
    def test_clean_exact_head_passes(self):
        r = fpc.evaluate(FakeClient(mapping()), REPO, PR, POLICY)
        self.assertEqual(r["status"], "PASS_FIRST_PASS_CLOSURE_GATE")
        self.assertEqual(set(r["proven_purposes"]), fpc.REQUIRED_PURPOSES)
        self.assertEqual(len(r["trusted_proof_surface"]), len(TRUSTED_PATHS))

    def test_trusted_surface_mutation_rejected(self):
        with self.assertRaisesRegex(
            fpc.GateError, "UNTRUSTED_PROOF_SURFACE_MUTATION"
        ):
            fpc.evaluate(
                FakeClient(mapping(mutate_path=TRUSTED_PATHS[0])),
                REPO,
                PR,
                POLICY,
            )

    def test_missing_receipt_rejected(self):
        with self.assertRaisesRegex(fpc.GateError, "MISSING_RECEIPT"):
            fpc.evaluate(FakeClient(mapping(pr_body="")), REPO, PR, POLICY)

    def test_stale_head_rejected(self):
        with self.assertRaisesRegex(fpc.GateError, "STALE_HEAD"):
            fpc.evaluate(
                FakeClient(mapping(pr_body=body("b" * 40))), REPO, PR, POLICY
            )

    def test_failed_run_rejected(self):
        with self.assertRaisesRegex(fpc.GateError, "RUN_NOT_SUCCESS"):
            fpc.evaluate(
                FakeClient(mapping(run_conclusion="failure")), REPO, PR, POLICY
            )

    def test_wrong_run_head_rejected(self):
        with self.assertRaisesRegex(fpc.GateError, "RUN_HEAD_MISMATCH"):
            fpc.evaluate(
                FakeClient(mapping(run_head="b" * 40)), REPO, PR, POLICY
            )

    def test_untrusted_workflow_identity_rejected(self):
        with self.assertRaisesRegex(
            fpc.GateError, "UNTRUSTED_PROOF_WORKFLOW_IDENTITY"
        ):
            fpc.evaluate(
                FakeClient(mapping(run_name="Unrelated Workflow")),
                REPO,
                PR,
                POLICY,
            )

    def test_spoofed_summary_author_rejected(self):
        with self.assertRaisesRegex(
            fpc.GateError, "CODEX_REVIEW_NOT_COMPLETED"
        ):
            fpc.evaluate(
                FakeClient(mapping(summary_login="GBOGEB")), REPO, PR, POLICY
            )

    def test_review_not_completed_rejected(self):
        with self.assertRaisesRegex(
            fpc.GateError, "CODEX_REVIEW_NOT_COMPLETED"
        ):
            fpc.evaluate(
                FakeClient(mapping(completed=False)), REPO, PR, POLICY
            )

    def test_exact_head_codex_finding_rejected(self):
        review = f"### Codex Review\n**Reviewed commit:** `{HEAD[:10]}`"
        with self.assertRaisesRegex(
            fpc.GateError, "CODEX_MATERIAL_FINDINGS"
        ):
            fpc.evaluate(
                FakeClient(mapping(review_body=review)), REPO, PR, POLICY
            )

    def test_old_head_codex_finding_does_not_block(self):
        review = "### Codex Review\n**Reviewed commit:** `bbbbbbbbbb`"
        r = fpc.evaluate(
            FakeClient(mapping(review_body=review)), REPO, PR, POLICY
        )
        self.assertTrue(r["merge_allowed"])

    def test_policy_load_failure_is_gate_error(self):
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "bad.json"
            bad.write_text("{not-json", encoding="utf-8")
            with self.assertRaisesRegex(fpc.GateError, "POLICY_LOAD_FAILED"):
                fpc.load_policy(str(bad))

    def test_failure_receipt_is_deterministic_and_non_authoritative(self):
        r = fpc.failure_receipt("POLICY_LOAD_FAILED")
        self.assertEqual(r["status"], "FAIL_FIRST_PASS_CLOSURE_GATE")
        self.assertFalse(r["merge_allowed"])
        self.assertFalse(r["authority_transfer"])
        self.assertEqual(r["formal_credit_delta"], 0)


if __name__ == "__main__":
    unittest.main()
