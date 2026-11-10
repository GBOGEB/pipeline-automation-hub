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

    def graphql(self, query, variables):
        if "graphql" not in self.mapping:
            raise AssertionError("graphql")
        return self.mapping["graphql"]


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
    inline_findings=(),
    resolved_ids=(),
    summary_body=None,
    extra_comments=(),
):
    summary = summary_body if summary_body is not None else f"""<!-- codex-pull-request-review-summary -->
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
        }, *extra_comments],
        f"/repos/{REPO}/pulls/{PR}/reviews": reviews,
        # inline_findings: (id, priority or None, commit) tuples from the Codex reviewer.
        f"/repos/{REPO}/pulls/{PR}/comments": [
            {"id": cid, "original_commit_id": commit, "path": "x.py",
             "user": {"login": "chatgpt-codex-connector[bot]"},
             "body": (f"**<sub><sub>![{pri} Badge](https://img.shields.io/badge/{pri}-x)</sub></sub> Finding**"
                      if pri else "**Finding without a badge**")}
            for cid, pri, commit in inline_findings
        ],
        "graphql": {"repository": {"pullRequest": {"reviewThreads": {
            "pageInfo": {"hasNextPage": False, "endCursor": None},
            "nodes": [{"isResolved": cid in resolved_ids, "comments": {"nodes": [{"databaseId": cid}]}}
                      for cid, _pri, _commit in inline_findings]}}}},
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

    def test_unfilled_template_receipt_is_derived(self):
        template = (Path(__file__).resolve().parents[2] / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text(
            encoding="utf-8")
        self.assertIn(fpc.TEMPLATE_HEAD_PLACEHOLDER, template)
        receipt = fpc.evaluate(FakeClient(mapping(pr_body=template)), REPO, PR, POLICY)
        self.assertEqual(receipt["status"], fpc.PASS_STATUS)
        self.assertEqual(receipt["receipt_source"], "DERIVED_EXACT_HEAD")

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

    # Owner decision 2026-11-10: a Codex review that quota prevented can be waived by the owner
    # for one exact head; nothing else is waived.
    NOTICE = "You have reached your Codex usage limits for code reviews"
    WAIVER_POLICY = {**POLICY, "codex_quota_waiver": {
        "quota_notice": NOTICE, "owner_logins": ["GBOGEB"], "waives": ["CODEX_REVIEW"]}}

    def waived(self, notice_login="chatgpt-codex-connector[bot]", owner="GBOGEB", head=HEAD,
               notice_at="2026-11-10T09:00:00Z", waiver_at="2026-11-10T09:05:00Z",
               line=None, owner_type="User", **kw):
        line = line if line is not None else f"FPC_WAIVER_V1 head={head} waives=CODEX_REVIEW reason=quota exhausted"
        extra = [
            {"id": 201, "created_at": notice_at, "user": {"login": notice_login, "type": "Bot"},
             "body": self.NOTICE + ". You can see your limits in the dashboard."},
            {"id": 202, "created_at": waiver_at, "user": {"login": owner, "type": owner_type},
             "body": "Merging on proof only.\n" + line + "\n"},
        ]
        return FakeClient(mapping(completed=False, extra_comments=extra, **kw))

    def test_owner_waiver_after_codex_quota_notice_passes_and_is_recorded(self):
        receipt = fpc.evaluate(self.waived(), REPO, PR, self.WAIVER_POLICY)
        self.assertEqual(receipt["status"], fpc.PASS_STATUS)
        waiver = receipt["codex_quota_waiver"]
        self.assertEqual(waiver["waives"], ["CODEX_REVIEW"])
        self.assertEqual((waiver["waiver_comment_id"], waiver["quota_notice_comment_id"]), (202, 201))
        self.assertEqual(waiver["reason"], "quota exhausted")
        self.assertTrue(waiver["post_merge_review_owed"])
        self.assertIsNone(receipt["codex_summary_comment_id"])
        fpc.validate_pass_receipt(receipt, HEAD, BASE)

    def test_completed_review_needs_no_waiver(self):
        receipt = fpc.evaluate(FakeClient(mapping()), REPO, PR, self.WAIVER_POLICY)
        self.assertIsNone(receipt["codex_quota_waiver"])

    def test_waiver_for_another_head_is_void(self):
        with self.assertRaisesRegex(fpc.GateError, "CODEX_REVIEW_NOT_COMPLETED"):
            fpc.evaluate(self.waived(head="b" * 40), REPO, PR, self.WAIVER_POLICY)

    def test_waiver_without_a_codex_quota_notice_is_void(self):
        # The owner quoting the notice is not the reviewer saying it.
        with self.assertRaisesRegex(fpc.GateError, "CODEX_REVIEW_NOT_COMPLETED"):
            fpc.evaluate(self.waived(notice_login="GBOGEB"), REPO, PR, self.WAIVER_POLICY)

    def test_waiver_posted_before_the_quota_notice_is_void(self):
        with self.assertRaisesRegex(fpc.GateError, "CODEX_REVIEW_NOT_COMPLETED"):
            fpc.evaluate(self.waived(waiver_at="2026-11-10T08:00:00Z"), REPO, PR, self.WAIVER_POLICY)

    def test_waiver_from_a_non_owner_or_a_bot_is_void(self):
        for kw in ({"owner": "someone-else"}, {"owner": "GBOGEB[bot]"}, {"owner_type": "Bot"}):
            with self.assertRaisesRegex(fpc.GateError, "CODEX_REVIEW_NOT_COMPLETED"):
                fpc.evaluate(self.waived(**kw), REPO, PR, self.WAIVER_POLICY)

    def test_malformed_waiver_line_is_void(self):
        for line in (f"FPC_WAIVER_V1 head={HEAD[:12]} waives=CODEX_REVIEW reason=x",
                     f"FPC_WAIVER_V1 head={HEAD} waives=EXACT_HEAD_CI reason=x",
                     f"FPC_WAIVER_V1 head={HEAD} waives=CODEX_REVIEW reason=",
                     f"> FPC_WAIVER_V1 head={HEAD} waives=CODEX_REVIEW reason=quoted"):
            with self.assertRaisesRegex(fpc.GateError, "CODEX_REVIEW_NOT_COMPLETED"):
                fpc.evaluate(self.waived(line=line), REPO, PR, self.WAIVER_POLICY)

    def test_waiver_is_off_without_the_policy_rule(self):
        with self.assertRaisesRegex(fpc.GateError, "CODEX_REVIEW_NOT_COMPLETED"):
            fpc.evaluate(self.waived(), REPO, PR, POLICY)

    def test_waiver_never_waives_the_proof_runs(self):
        with self.assertRaisesRegex(fpc.GateError, "RUN_NOT_SUCCESS"):
            fpc.evaluate(self.waived(run_conclusion="failure"), REPO, PR, self.WAIVER_POLICY)

    def test_waiver_never_waives_the_control_plane_rule(self):
        with self.assertRaisesRegex(fpc.GateError, "CONTROL_PLANE_CHANGE_REQUIRES_BOOTSTRAP"):
            fpc.evaluate(self.waived(changed_files=["scripts/first_pass_closure_gate.py"]),
                         REPO, PR, self.WAIVER_POLICY)

    def test_waiver_never_waives_an_open_blocking_finding_on_the_head(self):
        policy = {**self.WAIVER_POLICY,
                  "codex_contract": {**POLICY["codex_contract"], "blocking_priorities": ["P0", "P1"]}}
        with self.assertRaisesRegex(fpc.GateError, "CODEX_MATERIAL_FINDINGS"):
            fpc.evaluate(self.waived(inline_findings=[(1, "P1", HEAD)]), REPO, PR, policy)

    def test_waiver_policy_that_widens_the_rule_is_invalid(self):
        rule = self.WAIVER_POLICY["codex_quota_waiver"]
        for bad in ({"waives": ["CODEX_REVIEW", "EXACT_HEAD_CI"]}, {"owner_logins": []},
                    {"owner_logins": ["dependabot[bot]"]}, {"quota_notice": " "}):
            with self.assertRaisesRegex(fpc.GateError, "POLICY_CODEX_QUOTA_WAIVER_INVALID"):
                fpc.evaluate(self.waived(), REPO, PR, {**POLICY, "codex_quota_waiver": {**rule, **bad}})

    def test_repository_policy_quota_waiver_is_owner_only_and_narrow(self):
        policy = fpc.load_policy(str(ROOT.parent / "mission-control/quality/FIRST_PASS_CLOSURE_POLICY_v1.json"))
        rule = policy["codex_quota_waiver"]
        self.assertEqual(rule["waives"], ["CODEX_REVIEW"])
        self.assertEqual(rule["owner_logins"], ["GBOGEB"])
        self.assertIn("usage limits", rule["quota_notice"])
        self.assertIn("POLICY_CODEX_QUOTA_WAIVER_INVALID", policy["fail_closed_on"])

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

    # Owner decision 2026-10-30: only open P0/P1 Codex findings on the exact head block.
    P01_POLICY = {**POLICY, "codex_contract": {**POLICY["codex_contract"], "blocking_priorities": ["P0", "P1"]}}
    COMMENTED = f"### Codex Review\n**Reviewed commit:** `{HEAD[:10]}`"

    def p01(self, findings, resolved=()):
        return FakeClient(mapping(review_body=self.COMMENTED, inline_findings=findings, resolved_ids=resolved))

    def test_p2_p3_findings_on_head_do_not_block(self):
        receipt = fpc.evaluate(self.p01([(1, "P2", HEAD), (2, "P3", HEAD)]), REPO, PR, self.P01_POLICY)
        self.assertEqual(receipt["status"], fpc.PASS_STATUS)
        self.assertEqual(receipt["codex_finding_counts_on_exact_head"],
                         {"blocking_open": 0, "blocking_resolved": 0, "non_blocking": 2})

    def test_open_p1_on_head_blocks(self):
        with self.assertRaisesRegex(fpc.GateError, "CODEX_MATERIAL_FINDINGS_ON_EXACT_HEAD: 1 open P0/P1"):
            fpc.evaluate(self.p01([(1, "P1", HEAD), (2, "P2", HEAD)]), REPO, PR, self.P01_POLICY)

    def test_open_p0_on_head_blocks(self):
        with self.assertRaisesRegex(fpc.GateError, "CODEX_MATERIAL_FINDINGS_ON_EXACT_HEAD"):
            fpc.evaluate(self.p01([(1, "P0", HEAD)]), REPO, PR, self.P01_POLICY)

    def test_badgeless_codex_finding_blocks(self):
        with self.assertRaisesRegex(fpc.GateError, "CODEX_MATERIAL_FINDINGS_ON_EXACT_HEAD"):
            fpc.evaluate(self.p01([(1, None, HEAD)]), REPO, PR, self.P01_POLICY)

    def test_resolved_p1_thread_does_not_block_and_is_counted(self):
        receipt = fpc.evaluate(self.p01([(1, "P1", HEAD)], resolved=(1,)), REPO, PR, self.P01_POLICY)
        self.assertEqual(receipt["codex_finding_counts_on_exact_head"]["blocking_resolved"], 1)

    def test_p1_raised_on_older_head_does_not_block(self):
        receipt = fpc.evaluate(self.p01([(1, "P1", "b" * 40)]), REPO, PR, self.P01_POLICY)
        self.assertEqual(receipt["status"], fpc.PASS_STATUS)

    def test_review_must_still_be_completed_under_p01_rule(self):
        with self.assertRaisesRegex(fpc.GateError, "CODEX_REVIEW_NOT_COMPLETED"):
            fpc.evaluate(FakeClient(mapping(completed=False)), REPO, PR, self.P01_POLICY)

    def test_invalid_blocking_priorities_fail_closed(self):
        policy = {**POLICY, "codex_contract": {**POLICY["codex_contract"], "blocking_priorities": []}}
        with self.assertRaisesRegex(fpc.GateError, "POLICY_CODEX_BLOCKING_PRIORITIES_INVALID"):
            fpc.evaluate(self.p01([]), REPO, PR, policy)

    def test_strict_rule_without_blocking_priorities_is_unchanged(self):
        with self.assertRaisesRegex(fpc.GateError, "CODEX_MATERIAL_FINDINGS"):
            fpc.evaluate(self.p01([(1, "P3", HEAD)]), REPO, PR, POLICY)

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
        self.assertEqual(policy["codex_contract"]["blocking_priorities"], ["P0", "P1"])


# Heads of GBOGEB/pipeline-automation-hub#1137, where the gate passed at 2026-11-08T23:19:10Z
# while the Codex code review of 9a06106 was still running.
PR1137_HEAD = "9a0610679cb5a5d498d10746118abbea3eb259ea"
PR1137_OLD = "f735e3116781f896551df5d1acd9dbf0467d5998"
CODEX_LOGIN = "chatgpt-codex-connector"


def codex_summary(code=("running", HEAD), security=None, state_json=True):
    """A Codex summary comment in the format Codex posted on #1137 (state JSON plus table).

    code / security: (status, commit_sha) with status "running" or "completed", or None.
    """
    def entry(review):
        if review is None:
            return {"commit_sha": None, "has_any_findings": None,
                    "has_unresolved_findings": None, "status": None}
        status, sha = review
        done = status == "completed"
        return {"commit_sha": sha, "has_any_findings": False if done else None,
                "has_unresolved_findings": False if done else None, "status": status}

    def row(label, review):
        status, sha = review
        when = '<relative-time datetime="2026-11-08T23:18:18Z">2026-11-08T23:18:18Z</relative-time>'
        cell = f"✅ **Completed** {when}" if status == "completed" else f"🔄 **Running** since {when}"
        return f"| {label} | {cell} | `{sha[:7]}` | Manual request |"

    state = {"code_review": entry(code), "security_review": entry(security)}
    lines = ["<!-- codex-pull-request-review-summary -->"]
    if state_json:
        lines.append("<!-- codex-review-state:v1 " + json.dumps(state, separators=(",", ":")) + " -->")
    lines += [
        "<details>",
        "<summary><strong>Codex Review Summary</strong>: 🔄 Running</summary>",
        "",
        "This comment shows the latest Codex review activity on this pull request.",
        "",
        "| Review | Status | Commit | Review trigger |",
        "| --- | --- | --- | --- |",
    ]
    if code is not None:
        lines.append(row("📝 **Code Review**", code))
    if security is not None:
        lines.append(row("🔒 **Security Review**", security))
    lines += ["", "</details>"]
    return "\n".join(lines) + "\n"


def summary_comments(body, login="chatgpt-codex-connector[bot]", cid=6728451856):
    return [{"id": cid, "body": body, "user": {"login": login}}]


class TestCodexSummaryExactHeadCodeReview(unittest.TestCase):
    """Completion is read from the Code Review entry for the exact head, never from another row."""

    def completed(self, body, head):
        return fpc.review_is_completed_for_head(summary_comments(body), head, CODEX_LOGIN)

    def test_pr1137_running_code_review_plus_old_head_security_completed_is_not_completed(self):
        # The body the gate read at 23:19:10Z: the old check took "**Completed**" from the
        # security row (old head) and the head prefix from the code-review row (running).
        body = codex_summary(code=("running", PR1137_HEAD), security=("completed", PR1137_OLD))
        self.assertIn("**Completed**", body)
        self.assertIn(f"`{PR1137_HEAD[:7]}`", body)
        self.assertEqual(self.completed(body, PR1137_HEAD), (False, None))
        # Same answer from the table-row fallback when the state JSON is absent.
        body = codex_summary(code=("running", PR1137_HEAD), security=("completed", PR1137_OLD),
                             state_json=False)
        self.assertEqual(self.completed(body, PR1137_HEAD), (False, None))

    def test_code_review_completed_on_head_is_completed(self):
        body = codex_summary(code=("completed", PR1137_HEAD), security=("completed", PR1137_OLD))
        self.assertEqual(self.completed(body, PR1137_HEAD), (True, 6728451856))

    def test_code_review_completed_on_old_head_only_is_not_completed(self):
        body = codex_summary(code=("completed", PR1137_OLD))
        self.assertEqual(self.completed(body, PR1137_HEAD), (False, None))
        # A security review completed on the head doesn't stand in for the code review.
        body = codex_summary(code=("completed", PR1137_OLD), security=("completed", PR1137_HEAD))
        self.assertEqual(self.completed(body, PR1137_HEAD), (False, None))

    def test_without_state_json_the_code_review_row_decides(self):
        cases = [
            (("completed", PR1137_HEAD), ("running", PR1137_OLD), True),
            (("running", PR1137_HEAD), ("completed", PR1137_HEAD), False),
            (("completed", PR1137_OLD), ("completed", PR1137_HEAD), False),
        ]
        for code, security, expected in cases:
            with self.subTest(code=code, security=security):
                body = codex_summary(code=code, security=security, state_json=False)
                self.assertNotIn("codex-review-state", body)
                self.assertEqual(self.completed(body, PR1137_HEAD)[0], expected)

    def test_row_fallback_fails_closed_without_exactly_one_code_review_row(self):
        body = codex_summary(code=None, security=("completed", PR1137_HEAD), state_json=False)
        self.assertEqual(self.completed(body, PR1137_HEAD), (False, None))
        twice = codex_summary(code=("completed", PR1137_HEAD), state_json=False)
        twice = twice.replace("| Manual request |", "| Manual request |\n" + twice.splitlines()[-3])
        self.assertEqual(twice.count("**Code Review**"), 2)
        self.assertEqual(self.completed(twice, PR1137_HEAD), (False, None))

    def test_state_json_wins_over_a_completed_row(self):
        body = codex_summary(code=("running", PR1137_HEAD))
        body = body.replace("🔄 **Running** since", "✅ **Completed**")
        self.assertIn("**Completed**", body)
        self.assertEqual(self.completed(body, PR1137_HEAD), (False, None))

    def test_malformed_or_ambiguous_state_json_fails_closed(self):
        good = codex_summary(code=("completed", PR1137_HEAD))
        state_line = good.splitlines()[1]
        broken = good.replace(state_line, "<!-- codex-review-state:v1 {\"code_review\": -->")
        no_code = good.replace(state_line, '<!-- codex-review-state:v1 {"code_review":null} -->')
        doubled = good.replace(state_line, state_line + "\n" + state_line)
        for name, body in (("broken", broken), ("no_code", no_code), ("doubled", doubled)):
            with self.subTest(name):
                self.assertEqual(self.completed(body, PR1137_HEAD), (False, None))

    def test_state_json_needs_the_full_head_sha(self):
        body = codex_summary(code=("completed", PR1137_HEAD[:7] + "0" * 33))
        self.assertEqual(self.completed(body, PR1137_HEAD), (False, None))

    def test_summary_from_another_login_is_ignored(self):
        body = codex_summary(code=("completed", PR1137_HEAD))
        comments = summary_comments(body, login="someone-else")
        self.assertEqual(fpc.review_is_completed_for_head(comments, PR1137_HEAD, CODEX_LOGIN), (False, None))

    def test_pr1137_summary_edit_history_passes_only_after_the_head_code_review_completes(self):
        # The seven versions of the #1137 summary comment (GitHub userContentEdits), oldest first.
        history = [
            ("23:08:26", ("running", PR1137_OLD), None),
            ("23:11:10", ("completed", PR1137_OLD), None),
            ("23:13:00", ("running", PR1137_OLD), None),
            ("23:13:10", ("running", PR1137_OLD), ("running", PR1137_OLD)),
            ("23:15:31", ("running", PR1137_OLD), ("completed", PR1137_OLD)),
            ("23:18:18", ("running", PR1137_HEAD), ("completed", PR1137_OLD)),
            ("23:20:36", ("completed", PR1137_HEAD), ("completed", PR1137_OLD)),
        ]
        expected = {
            PR1137_OLD: {"23:11:10"},
            PR1137_HEAD: {"23:20:36"},
        }
        for head, passing in expected.items():
            for edited_at, code, security in history:
                with self.subTest(head=head[:7], edited_at=edited_at):
                    body = codex_summary(code=code, security=security)
                    self.assertEqual(self.completed(body, head)[0], edited_at in passing)

    def test_gate_rejects_running_head_review_beside_completed_old_security_review(self):
        body = codex_summary(code=("running", HEAD), security=("completed", "b" * 40))
        with self.assertRaisesRegex(fpc.GateError, "CODEX_REVIEW_NOT_COMPLETED_ON_EXACT_HEAD"):
            fpc.evaluate(FakeClient(mapping(summary_body=body)), REPO, PR, POLICY)

    def test_gate_passes_when_the_head_code_review_completed(self):
        body = codex_summary(code=("completed", HEAD), security=("completed", "b" * 40))
        receipt = fpc.evaluate(FakeClient(mapping(summary_body=body)), REPO, PR, POLICY)
        self.assertEqual(receipt["status"], fpc.PASS_STATUS)
        self.assertEqual(receipt["codex_summary_comment_id"], 99)


if __name__ == "__main__":
    unittest.main()
