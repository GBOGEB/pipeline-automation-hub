"""Negative and positive testflight for exact-head rerun planning (read-only)."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "rerun_triage.py"
SPEC = importlib.util.spec_from_file_location("gogreen_rerun_triage", MODULE)
TRIAGE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(TRIAGE)
SHA_A = "a" * 40
SHA_B = "b" * 40
MAIN = "c" * 40


def item(pr=101, head=SHA_A, *, behind=0, created="2026-10-14T08:00:00Z"):
    return {
        "pr": pr,
        "head_sha": head,
        "behind_main": behind,
        "created_at": created,
        "root_id": "ROOT-SAME",
        "run": {
            "id": 38873572319,
            "job_id": 116800012345,
            "attempt": 1,
            "head_sha": head,
            "status": "completed",
            "conclusion": "failure",
            "failure_kind": "DETERMINISTIC",
            "logs_insufficient": False,
            "cause": "workflow_inventory",
        },
    }


def census(items=None):
    return {
        "schema": TRIAGE.SCHEMA,
        "observed_at": "2026-10-16T08:38:22Z",
        "main_sha": MAIN,
        "authority_transfer": False,
        "items": [item()] if items is None else items,
    }


class RerunTriageTests(unittest.TestCase):
    def decide(self, record):
        return TRIAGE.plan(census([record]))["rows"][0]["decision"]

    def test_deterministic_fail_requires_root_not_rerun(self):
        self.assertEqual(self.decide(item()), "REPAIR_CANONICAL_ROOT")

    def test_same_commit_queued_attempt2_waits(self):
        rec = item()
        rec["run"].update(attempt=2, status="queued", conclusion=None)
        self.assertEqual(self.decide(rec), "WAIT_CURRENT_RUN")

    def test_different_run_head_never_carries_green(self):
        rec = item()
        rec["run"].update(head_sha=SHA_B, conclusion="success", failure_kind="NONE")
        self.assertEqual(self.decide(rec), "RUN_NEW_EXACT_HEAD")

    def test_missing_run_requests_new_exact_head(self):
        rec = item()
        rec["run"] = None
        self.assertEqual(self.decide(rec), "RUN_NEW_EXACT_HEAD")

    def test_behind_main_requires_reconciliation(self):
        self.assertEqual(self.decide(item(behind=48)), "RECONCILE_MAIN")

    def test_succeeded_branch_still_needs_independent_gate(self):
        rec = item()
        rec["run"].update(conclusion="success", failure_kind="NONE")
        self.assertEqual(self.decide(rec), "EVALUATE_INDEPENDENT_GATES")

    def test_skipped_workflow_does_not_count_as_proof(self):
        rec = item()
        rec["run"].update(conclusion="skipped", failure_kind="NONE")
        self.assertEqual(self.decide(rec), "NO_ELIGIBLE_TEST")

    def test_transient_known_root_allows_one_candidate(self):
        rec = item()
        rec["run"].update(failure_kind="TRANSIENT", cause="runner_lost")
        self.assertEqual(self.decide(rec), "RERUN_FAILED_JOBS_CANDIDATE")

    def test_transient_unsupported_cause_is_rejected(self):
        rec = item()
        rec["run"].update(failure_kind="TRANSIENT", cause="unknown_network")
        with self.assertRaises(ValueError):
            TRIAGE.plan(census([rec]))

    def test_unknown_firstred_needs_logs(self):
        rec = item()
        rec["run"].update(failure_kind="UNCLASSIFIED")
        self.assertEqual(self.decide(rec), "INSPECT_FIRSTRED")

    def test_debug_only_after_logs_are_insufficient(self):
        rec = item()
        rec["run"].update(failure_kind="UNCLASSIFIED", logs_insufficient=True)
        self.assertEqual(self.decide(rec), "DEBUG_RERUN_CANDIDATE")

    def test_second_unknown_attempt_is_exhausted(self):
        rec = item()
        rec["run"].update(failure_kind="UNCLASSIFIED", logs_insufficient=True, attempt=2)
        self.assertEqual(self.decide(rec), "RETRY_EXHAUSTED")

    def test_duplicate_causal_retry_is_suppressed(self):
        a, b = item(pr=1), item(pr=2)
        a["run"].update(failure_kind="TRANSIENT", cause="github_5xx")
        b["run"].update(failure_kind="TRANSIENT", cause="github_5xx")
        receipt = TRIAGE.plan(census([b, a]))
        self.assertEqual(receipt["kpi"]["retries_recommended"], 1)
        self.assertEqual(receipt["kpi"]["duplicate_root_retries_suppressed"], 1)
        self.assertFalse(receipt["dispatch_authorized"])

    def test_24_hour_age_is_priority_not_retry_authorization(self):
        rec = item(created="2026-10-15T07:30:00Z")
        receipt = TRIAGE.plan(census([rec]))
        self.assertTrue(receipt["rows"][0]["older_than_24h"])
        self.assertEqual(receipt["kpi"]["retries_recommended"], 0)

    def test_young_failed_same_head_needs_root_repair(self):
        rec = item(created="2026-10-16T07:30:00Z")
        receipt = TRIAGE.plan(census([rec]))
        self.assertEqual(receipt["kpi"]["older_than_24h"], 0)
        self.assertEqual(receipt["rows"][0]["decision"], "REPAIR_CANONICAL_ROOT")

    def test_main_source_is_required_exact_sha(self):
        doc = census()
        doc["main_sha"] = "broken"
        with self.assertRaises(ValueError):
            TRIAGE.plan(doc)

    def test_boolean_run_identity_not_accepted(self):
        rec = item()
        rec["run"]["attempt"] = True
        with self.assertRaises(ValueError):
            TRIAGE.plan(census([rec]))

    def test_negative_behind_main_not_accepted(self):
        with self.assertRaises(ValueError):
            TRIAGE.plan(census([item(behind=-1)]))

    def test_completed_without_conclusion_fails_closed(self):
        rec = item()
        rec["run"]["conclusion"] = None
        with self.assertRaises(ValueError):
            TRIAGE.plan(census([rec]))

    def test_queued_cannot_claim_success(self):
        rec = item()
        rec["run"].update(status="queued", conclusion="success", failure_kind="NONE")
        with self.assertRaises(ValueError):
            TRIAGE.plan(census([rec]))

    def test_missing_time_zone_fails_closed(self):
        rec = item(created="2026-10-15T08:00:00")
        with self.assertRaises(ValueError):
            TRIAGE.plan(census([rec]))

    def test_future_pr_creation_fails_closed(self):
        rec = item(created="2026-10-17T08:00:00Z")
        with self.assertRaises(ValueError):
            TRIAGE.plan(census([rec]))

    def test_duplicate_pr_identity_rejected(self):
        with self.assertRaises(ValueError):
            TRIAGE.plan(census([item(), item()]))

    def test_missing_authority_boundary_rejected(self):
        doc = census()
        doc["authority_transfer"] = True
        with self.assertRaises(ValueError):
            TRIAGE.plan(doc)

    def test_empty_or_unbounded_inputs_rejected(self):
        with self.assertRaises(ValueError):
            TRIAGE.plan(census([]))
        with self.assertRaises(ValueError):
            TRIAGE.plan(census([item(pr=i + 1) for i in range(501)]))

    def test_sample_readback_reconciles_eight_stale_prs(self):
        sample = Path(__file__).resolve().parents[1] / "samples" / "cbd_rerun_20261016.json"
        receipt = TRIAGE.plan(json.loads(sample.read_text(encoding="utf-8")))
        self.assertEqual(receipt["kpi"]["prs"], 9)
        self.assertEqual(receipt["kpi"]["older_than_24h"], 8)
        self.assertEqual(receipt["kpi"]["behind_main"], 8)
        self.assertEqual(receipt["kpi"]["retries_recommended"], 0)
        self.assertEqual(receipt["kpi"]["counts"]["WAIT_CURRENT_RUN"], 1)
        self.assertFalse(receipt["merge_authorized"])
        self.assertEqual(receipt["independent_root_closures"], 0)


    def test_completed_without_job_id_fails_closed(self):
        rec = item()
        rec["run"].pop("job_id")
        with self.assertRaises(ValueError):
            TRIAGE.plan(census([rec]))

    def test_queued_can_have_unknown_job_id(self):
        rec = item()
        rec["run"].update(status="queued", conclusion=None, job_id=None)
        self.assertEqual(self.decide(rec), "WAIT_CURRENT_RUN")

    def test_forged_boolean_job_id_is_rejected(self):
        rec = item()
        rec["run"]["job_id"] = True
        with self.assertRaises(ValueError):
            TRIAGE.plan(census([rec]))

    def test_same_root_at_different_source_shas_is_not_reused(self):
        a, b = item(pr=1, head=SHA_A), item(pr=2, head=SHA_B)
        a["run"].update(failure_kind="TRANSIENT", cause="runner_lost")
        b["run"].update(failure_kind="TRANSIENT", cause="runner_lost")
        result = TRIAGE.plan(census([a, b]))
        self.assertEqual(result["kpi"]["retries_recommended"], 2)
        self.assertEqual(result["kpi"]["duplicate_root_retries_suppressed"], 0)

    def test_receipt_output_is_byte_hash_verified(self):
        receipt = TRIAGE.plan(census())
        with tempfile.TemporaryDirectory() as tmp:
            digest = TRIAGE.emit(receipt, Path(tmp))
            raw = (Path(tmp) / "rerun_receipt.json").read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), digest)
            self.assertEqual(
                (Path(tmp) / "rerun_receipt.sha256").read_text().strip(), digest
            )


if __name__ == "__main__":
    unittest.main()
