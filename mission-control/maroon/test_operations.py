"""Operational regressions: identity, proof-bound closure, durable leases and worker recovery."""
import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import operations as O

NOW = "2026-11-11T10:00:00+00:00"
LATER = "2026-11-11T10:00:01+00:00"


def thread(number=1, *, path="src/a.py", branch="fix/topic", pr=7, head="a" * 40, title="Validate the input", repo="O/r"):
    pull = {"number": pr, "state": "open", "head": {"sha": head, "ref": branch, "repo": {"full_name": repo}},
            "base": {"sha": "b" * 40, "ref": "main"}, "draft": False, "title": "Fix parser validation", "body": "Review the source repair."}
    comment = {"id": number, "body": title, "user": {"login": "reviewer"}, "path": path,
               "created_at": NOW, "updated_at": NOW, "original_commit_id": head,
               "diff_hunk": "@@ -1 +1 @@\n+return parse(value)"}
    row = O.RT.threads_of(pull, [comment], [], O.RT.ResolvedThreads([], {number: {"id": f"PRRT_{number}"}}))[0]
    row["blob_oids"] = {path: "c" * 40}
    row["core_oids"] = O.runtime_core_oids()
    return row


def raw(*threads, repo="O/r", coverage="ok", linked=False):
    return {"schema": O.RT.SCHEMA, "state": "open", "fetched_at": NOW,
            "repos": {repo: {"coverage": coverage, "head_sha": "e" * 40,
                              "alerts": [] if linked else list(threads), "linked_alerts": list(threads) if linked else []}}}


class Operations(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = O.LedgerStore(Path(self.tmp.name) / "ledger.json")

    def seed(self, *rows):
        O.ingest(self.store, raw(*(rows or (thread(),))), "pulse-1", now=NOW)
        data = self.store.read()
        return sorted(data["roots"]), sorted(data["observations"])

    def acquire(self, root=None):
        root = root or next(iter(self.store.read()["roots"]))
        return O.claim(self.store, root, "worker-a", now=NOW)

    def test_evidenced_regrouping_uses_one_packet_and_survives_unchanged_scan(self):
        a, b = thread(1, title="Check first use"), thread(2, title="Check second use")
        roots, items = self.seed(a, b)
        self.assertEqual(len(roots), 2)
        grouped = O.group_findings(self.store, items, "same-control-flow", method="Both sites share the same dominating initialization.",
                                   proof_refs=["source:proof"], now=NOW)
        self.assertEqual(O.plan(self.store, now=NOW)["ready"], [grouped])
        claim = self.acquire(grouped)
        first = O.mark_closed(self.store, items[0], self.receipt(claim, items[0]), now=LATER)
        self.assertEqual(first["semantic_state"], "closed")
        self.assertEqual(self.store.read()["roots"][grouped]["state"], "OPEN")

    def test_manual_group_binding_expires_on_changed_head(self):
        a, b = thread(1, title="first"), thread(2, title="second")
        _, items = self.seed(a, b)
        grouped = O.group_findings(self.store, items, "shared", method="Shared source analysis", proof_refs=["source:proof"], now=NOW)
        O.ingest(self.store, raw(a, b), "p2", now=LATER)
        self.assertEqual({r["root_id"] for r in self.store.read()["observations"].values()}, {grouped})
        a["pr_head"] = b["pr_head"] = "d" * 40
        O.ingest(self.store, raw(a, b), "p3", now=LATER)
        self.assertEqual({r["root_id"] for r in self.store.read()["observations"].values()}, {grouped})
        packet = next(p for p in O.plan(self.store, now=LATER)["packets"] if p["root_id"] == grouped)
        self.assertIn("GROUP_REDIAGNOSIS_REQUIRED", packet["admission_reasons"])
        self.assertEqual(O.group_findings(self.store, items, "shared", method="Re-diagnosed new source", proof_refs=["new-proof"], now=LATER), grouped)
        self.assertIn(grouped, O.plan(self.store, now=LATER)["ready"])

    def test_group_source_drift_does_not_orphan_downstream_dependencies(self):
        a, b, child = thread(1, title="first"), thread(2, title="second"), thread(3, path="src/c.py", branch="fix/child", pr=8)
        self.seed(a, b, child)
        items = [O.observation_id("O/r", 7, n) for n in (1, 2)]
        grouped = O.group_findings(self.store, items, "shared", method="Shared source", proof_refs=["proof"], now=NOW)
        dependent = self.store.read()["observations"][O.observation_id("O/r", 8, 3)]["root_id"]
        O.set_dependencies(self.store, dependent, [grouped])
        a["pr_head"] = "d" * 40  # A partial changed-head observation must hold, not split the DAG.
        O.ingest(self.store, raw(a, b, child), "p2", now=LATER)
        current = self.store.read()
        self.assertEqual(current["roots"][dependent]["depends_on"], [grouped])
        self.assertEqual(set(current["roots"][grouped]["member_ids"]), set(items))
        self.assertEqual(current["roots"][grouped]["state"], "OPEN")
        self.assertNotIn(grouped, O.plan(self.store, now=LATER)["ready"])

    def test_regrouping_rejects_active_lease_and_cross_branch(self):
        roots, items = self.seed(thread(1, title="first"), thread(2, title="second"))
        self.acquire(roots[0])
        with self.assertRaises(O.LeaseError):
            O.group_findings(self.store, items, "shared", method="Shared analysis", proof_refs=["proof"], now=NOW)

    def receipt(self, claim, item_id=None, **updates):
        item_id = item_id or claim["member_ids"][0]
        item = self.store.read()["observations"][item_id]
        receipt = {"item_id": item_id, "root_id": item["root_id"], "lease_token": claim["lease_token"],
                   "fence": claim["fence"], "head_sha": item["head_sha"], "base_sha": item["base_sha"],
                   "discussion_hash": item["discussion_hash"], "thread_id": item["thread_id"],
                   "blob_oids": item["blob_oids"], "core_oids": item["core_oids"],
                   "disposition": "already_fixed", "method": "Inspected the exact source and verified the regression test.",
                   "proof_refs": ["https://github.com/O/r/actions/runs/10"],
                   "provider_readback": {"resolved": True, "observed_at": LATER,
                       "reference": "https://github.com/O/r/pull/7#discussion_r1", "head_sha": item["head_sha"],
                       "discussion_hash": item["discussion_hash"], "thread_id": item["thread_id"]}}
        receipt.update(updates)
        return receipt

    def test_pulse_replay_is_idempotent_and_revisions_are_not_new_observations(self):
        rows = raw(thread())
        O.ingest(self.store, rows, "p1", now=NOW)
        before = self.store.read()
        O.ingest(self.store, rows, "p1", now=LATER)
        self.assertEqual(before, self.store.read())
        O.ingest(self.store, rows, "p2", now=LATER)
        edited = copy.deepcopy(rows)
        edited["repos"]["O/r"]["alerts"][0]["discussion_hash"] = "f" * 64
        O.ingest(self.store, edited, "p3", now=LATER)
        item = next(iter(self.store.read()["observations"].values()))
        self.assertEqual((item["sighting_count"], item["revision_count"], item["reopen_count"]), (3, 1, 0))
        self.assertEqual(len(self.store.read()["observations"]), 1)
        with self.assertRaises(ValueError):
            O.ingest(self.store, edited, "p1", now=LATER)

    def test_missing_or_unreadable_never_means_semantic_closure(self):
        self.seed()
        O.ingest(self.store, raw(coverage="not_readable"), "p2", now=LATER)
        item = next(iter(self.store.read()["observations"].values()))
        self.assertEqual((item["observation_status"], item["semantic_state"]), ("UNKNOWN", "open"))
        self.assertEqual(O.plan(self.store, now=LATER)["ready"], [])

    def test_narrow_scope_does_not_invalidate_other_repository(self):
        self.seed()
        claim = self.acquire()
        O.ingest(self.store, raw(thread(repo="O/other"), repo="O/other"), "p2", now=LATER)
        current = O.check_lease(self.store, claim["root_id"], claim["lease_token"], claim["fence"], now=LATER)
        self.assertEqual(current["idempotency_key"], claim["idempotency_key"])

    def test_provider_resolution_is_not_semantic_closure_and_reopen_is_counted_once(self):
        self.seed()
        row = thread()
        row["state"] = "resolved"
        O.ingest(self.store, raw(row), "p2", now=LATER)
        item = next(iter(self.store.read()["observations"].values()))
        self.assertEqual((item["provider_state"], item["semantic_state"]), ("resolved", "open"))
        row["state"] = "open"
        O.ingest(self.store, raw(row), "p3", now=LATER)
        O.ingest(self.store, raw(row), "p4", now=LATER)
        self.assertEqual(next(iter(self.store.read()["observations"].values()))["reopen_count"], 1)

    def test_diagnosis_grouping_keeps_distinct_member_ids(self):
        roots, items = self.seed(thread(1), thread(2), thread(3, path="src/b.py"))
        self.assertEqual((len(roots), len(items)), (2, 3))
        self.assertEqual(sorted(len(root["member_ids"]) for root in self.store.read()["roots"].values()), [1, 2])

    def test_reclassification_preserves_assignment_history(self):
        roots, items = self.seed()
        O.ingest(self.store, raw(thread(title="Different independent problem")), "p2", now=LATER)
        item = self.store.read()["observations"][items[0]]
        self.assertEqual(len(item["root_history"]), 2)
        self.assertNotEqual(item["root_id"], roots[0])
        self.assertEqual(self.store.read()["roots"][roots[0]]["state"], "SUPERSEDED")

    def test_codeql_linked_reviews_remain_actionable_obligations(self):
        row = thread()
        row.update(provider_alert_owner="code_scanning", scanner_alert_state="UNKNOWN")
        O.ingest(self.store, raw(row, linked=True), "p1", now=NOW)
        item = next(iter(self.store.read()["observations"].values()))
        self.assertEqual(item["provider_alert_owner"], "code_scanning")
        self.assertEqual(item["scanner_alert_state"], "UNKNOWN")
        self.assertEqual(len(O.plan(self.store, now=NOW)["ready"]), 1)

    def test_kahn_layers_and_cycle_rejection_are_atomic(self):
        roots, _ = self.seed(thread(), thread(2, path="src/b.py", branch="fix/second"))
        O.set_dependencies(self.store, roots[1], [roots[0]])
        planned = O.plan(self.store, now=NOW)
        self.assertEqual(len(planned["layers"]), len(O.STAGES) * 2)
        before = self.store.read()
        with self.assertRaises(ValueError):
            O.set_dependencies(self.store, roots[0], [roots[1]])
        self.assertEqual(before, self.store.read())
        with self.assertRaises(ValueError):
            O.set_dependencies(self.store, roots[0], ["unknown-root"])

    def test_one_branch_writer_even_for_disjoint_paths(self):
        roots, _ = self.seed(thread(), thread(2, path="src/b.py"))
        self.acquire(roots[0])
        with self.assertRaises(O.LeaseError):
            self.acquire(roots[1])

    def test_overlapping_paths_conflict_across_branches(self):
        roots, _ = self.seed(thread(), thread(2, branch="fix/second"))
        self.acquire(roots[0])
        with self.assertRaises(O.LeaseError):
            self.acquire(roots[1])

    def test_two_disjoint_claims_and_default_backpressure(self):
        roots, _ = self.seed(thread(), thread(2, path="src/b.py", branch="fix/second"),
                            thread(3, path="src/c.py", branch="fix/third"))
        self.acquire(roots[0])
        self.acquire(roots[1])
        with self.assertRaises(O.LeaseError):
            self.acquire(roots[2])

    def test_expiry_requires_reconciliation_and_stale_fence_cannot_affect_successor(self):
        roots, _ = self.seed()
        claim = O.claim(self.store, roots[0], "first", ttl_seconds=1, now=NOW)
        expired = "2026-11-11T10:00:02+00:00"
        with self.assertRaises(O.LeaseError):
            O.check_lease(self.store, roots[0], claim["lease_token"], claim["fence"], now=expired)
        with self.assertRaises(O.LeaseError):
            O.claim(self.store, roots[0], "replacement", now=expired)
        O.reconcile_claim(self.store, roots[0], claim["lease_token"], claim["fence"], owner_stopped=True,
                          proof_refs=["executor://confirmed-stopped"], now=expired)
        successor = O.claim(self.store, roots[0], "replacement", now=expired)
        self.assertGreater(successor["fence"], claim["fence"])
        with self.assertRaises(O.LeaseError):
            O.release(self.store, roots[0], claim["lease_token"], claim["fence"], now=expired)

    def test_unexpected_head_or_oid_drift_invalidates_claim(self):
        for field in ("pr_head", "blob_oids", "core_oids"):
            with self.subTest(field=field):
                path = Path(self.tmp.name) / (field + ".json")
                store = O.LedgerStore(path)
                O.ingest(store, raw(thread()), "p1", now=NOW)
                root_id = next(iter(store.read()["roots"]))
                claim = O.claim(store, root_id, "worker", now=NOW)
                changed = thread()
                changed[field] = "f" * 40 if field == "pr_head" else {"src/a.py" if field == "blob_oids" else "policy.json": "f" * 40}
                O.ingest(store, raw(changed), "p2", now=LATER)
                with self.assertRaises(O.LeaseError):
                    O.check_lease(store, root_id, claim["lease_token"], claim["fence"], now=LATER)

    def test_intended_verified_commit_can_advance_claim(self):
        self.seed()
        claim = self.acquire()
        current = O.advance_claim(self.store, claim["root_id"], claim["lease_token"], claim["fence"],
                                  {item: {"head_sha": "f" * 40, "blob_oids": {"src/a.py": "e" * 40}} for item in claim["member_ids"]},
                                  reason="Native compare confirms the intended tested commit", proof_refs=["commit://f"], now=LATER)
        self.assertEqual(current["head_sha"], "f" * 40)
        self.assertNotEqual(current["idempotency_key"], claim["idempotency_key"])
        self.assertEqual(current["fence"], claim["fence"])

    def test_closure_requires_exact_positive_readback_and_is_idempotent(self):
        roots, items = self.seed()
        claim = self.acquire()
        receipt = self.receipt(claim)
        invalid = copy.deepcopy(receipt)
        invalid["provider_readback"]["resolved"] = False
        with self.assertRaises(ValueError):
            O.mark_closed(self.store, items[0], invalid, now=LATER)
        self.assertEqual(self.store.read()["roots"][roots[0]]["state"], "OPEN")
        O.mark_closed(self.store, items[0], receipt, now=LATER)
        O.mark_closed(self.store, items[0], receipt, now=LATER)
        self.assertEqual(self.store.read()["roots"][roots[0]]["state"], "CLOSED")
        self.assertEqual(len(self.store.read()["observations"][items[0]]["closure_receipts"]), 1)

    def test_one_closed_member_does_not_close_diagnosis_batch(self):
        roots, items = self.seed(thread(1), thread(2))
        claim = self.acquire()
        O.mark_closed(self.store, items[0], self.receipt(claim, items[0]), now=LATER)
        self.assertEqual(self.store.read()["roots"][roots[0]]["state"], "OPEN")
        O.mark_closed(self.store, items[1], self.receipt(claim, items[1]), now=LATER)
        self.assertEqual(self.store.read()["roots"][roots[0]]["state"], "CLOSED")

    def test_dependency_waits_for_rex_after_semantic_closure(self):
        roots, _ = self.seed(thread(), thread(2, path="src/b.py", branch="fix/second"))
        O.set_dependencies(self.store, roots[1], [roots[0]])
        claim = self.acquire(roots[0])
        O.mark_closed(self.store, claim["member_ids"][0], self.receipt(claim), now=LATER)
        planned = O.plan(self.store, now=LATER)
        self.assertNotIn(roots[1], planned["ready"])
        held = next(p for p in planned["packets"] if p["root_id"] == roots[1])
        self.assertIn("PREDECESSOR_REX_NOT_COMPLETE", held["admission_reasons"])

    def test_own_verified_reply_does_not_reopen_closed_item_but_edits_do(self):
        self.seed()
        claim = self.acquire()
        receipt = self.receipt(claim, reply_id=10, reply_body_hash=hashlib.sha256(b"Verified evidence reply").hexdigest())
        O.mark_closed(self.store, claim["member_ids"][0], receipt, now=LATER)
        row = thread()
        row["state"] = "resolved"
        row["comments"].append({"id": 10, "body": "Verified evidence reply", "author": "maroon",
                                "created_at": LATER, "updated_at": LATER, "commit_id": "a" * 40})
        row["discussion_hash"] = hashlib.sha256(json.dumps(row["comments"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        O.ingest(self.store, raw(row), "p2", now=LATER)
        self.assertEqual(self.store.read()["observations"][claim["member_ids"][0]]["semantic_state"], "closed")
        row["comments"][-1]["body"] = "An altered evidence claim"
        row["discussion_hash"] = hashlib.sha256(json.dumps(row["comments"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        O.ingest(self.store, raw(row), "p3", now=LATER)
        self.assertEqual(self.store.read()["observations"][claim["member_ids"][0]]["semantic_state"], "revalidation_required")

    def test_native_scan_omitting_blob_pins_preserves_same_head_closure(self):
        self.seed()
        claim = self.acquire()
        receipt = self.receipt(claim, reply_id=10, reply_body_hash=hashlib.sha256(b"Verified evidence reply").hexdigest())
        O.mark_closed(self.store, claim["member_ids"][0], receipt, now=LATER)
        row = thread()
        row["state"] = "resolved"
        row.pop("blob_oids")
        row.pop("core_oids")
        row["comments"].append({"id": 10, "body": "Verified evidence reply", "author": "maroon",
                                "created_at": LATER, "updated_at": LATER, "commit_id": "a" * 40})
        row["discussion_hash"] = hashlib.sha256(json.dumps(row["comments"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        O.ingest(self.store, raw(row), "p2", now=LATER)
        item = self.store.read()["observations"][claim["member_ids"][0]]
        self.assertEqual((item["semantic_state"], item["blob_oids"]), ("closed", {"src/a.py": "c" * 40}))
        row["blob_oids"] = {}  # explicitly observed empty is not an omitted field
        O.ingest(self.store, raw(row), "p3", now=LATER)
        self.assertEqual(self.store.read()["observations"][claim["member_ids"][0]]["semantic_state"], "revalidation_required")

    def test_canary_and_unknown_intent_are_analysis_only(self):
        for value in (True, None):
            with self.subTest(value=value):
                row = thread()
                row["negative_canary"] = value
                store = O.LedgerStore(Path(self.tmp.name) / f"canary-{value}.json")
                O.ingest(store, raw(row), "p1", now=NOW)
                self.assertEqual(O.plan(store, now=NOW)["ready"], [])
                root = next(iter(store.read()["roots"]))
                with self.assertRaises(O.LeaseError):
                    O.claim(store, root, "writer", now=NOW)

    def test_changed_executor_core_invalidates_existing_claim(self):
        self.seed()
        claim = self.acquire()
        altered = O.runtime_core_oids()
        altered["mission-control/maroon/closure.py"] = "f" * 40
        with mock.patch.object(O, "_core_manifest", return_value=altered):
            with self.assertRaises(O.LeaseError):
                O.check_lease(self.store, claim["root_id"], claim["lease_token"], claim["fence"], now=LATER)

    def test_failed_predecessor_blocks_worker_descendants(self):
        self.seed()
        claim = self.acquire()
        called = []
        handlers = {stage: lambda stage=stage: called.append(stage) or {"ok": stage != "verify"} for stage in O.STAGES}
        result = O.run_claimed(self.store, claim["root_id"], claim["lease_token"], claim["fence"], handlers, now=NOW)
        self.assertFalse(result["success"])
        self.assertEqual(called, ["diagnose", "treat", "verify"])
        self.assertEqual(result["tasks"][claim["root_id"] + ":publish"]["state"], "blocked")

    def test_resume_skips_verified_handlers_and_close_requires_provider_receipts(self):
        self.seed()
        claim = self.acquire()
        called = []
        handlers = {stage: lambda stage=stage: called.append(stage) or {"ok": stage != "verify"} for stage in O.STAGES}
        O.run_claimed(self.store, claim["root_id"], claim["lease_token"], claim["fence"], handlers, now=NOW)
        called.clear()
        handlers = {stage: lambda stage=stage: called.append(stage) or {"ok": True} for stage in O.STAGES}
        result = O.run_claimed(self.store, claim["root_id"], claim["lease_token"], claim["fence"], handlers, now=NOW)
        self.assertEqual(called, ["verify", "publish", "reply", "resolve", "readback", "close"])
        self.assertFalse(result["success"])
        self.assertEqual(result["tasks"][claim["root_id"] + ":rex"]["state"], "blocked")
        with self.assertRaises(O.LeaseError):
            O.run_claimed(self.store, claim["root_id"], claim["lease_token"], claim["fence"], handlers, now=NOW)

    def test_ambiguous_publish_is_not_replayed_on_restart(self):
        self.seed()
        claim = self.acquire()
        calls = []
        handlers = {stage: lambda: {"ok": True} for stage in O.STAGES}

        def publish():
            calls.append("publish")
            raise TimeoutError("provider outcome unknown")

        handlers["publish"] = publish
        O.run_claimed(self.store, claim["root_id"], claim["lease_token"], claim["fence"], handlers, now=NOW)
        with self.assertRaises(O.LeaseError):
            O.run_claimed(self.store, claim["root_id"], claim["lease_token"], claim["fence"], handlers, now=NOW)
        self.assertEqual(calls, ["publish"])
        with self.assertRaises(O.LeaseError):
            O.release(self.store, claim["root_id"], claim["lease_token"], claim["fence"], now=NOW)

    def test_successful_full_run_resumes_without_replaying_native_handlers(self):
        self.seed()
        claim = self.acquire()
        calls = []
        handlers = {stage: lambda stage=stage: calls.append(stage) or {"ok": True} for stage in O.STAGES}
        receipt = self.receipt(claim)

        def close():
            calls.append("close")
            O.mark_closed(self.store, claim["member_ids"][0], receipt, now=LATER)
            return {"ok": True}

        handlers["close"] = close
        result = O.run_claimed(self.store, claim["root_id"], claim["lease_token"], claim["fence"], handlers, now=LATER)
        self.assertTrue(result["success"])
        self.assertEqual(calls, list(O.STAGES))
        calls.clear()
        repeated = O.run_claimed(self.store, claim["root_id"], claim["lease_token"], claim["fence"], handlers, now=LATER)
        self.assertTrue(repeated["success"])
        self.assertEqual(calls, [])

    def test_shared_ledger_updates_do_not_lose_sightings(self):
        def write(index):
            row = thread(repo=f"O/r{index}")
            O.ingest(O.LedgerStore(self.store.path), raw(row, repo=f"O/r{index}"), f"p{index}", now=NOW)

        with ThreadPoolExecutor(max_workers=4) as workers:
            list(workers.map(write, range(8)))
        data = self.store.read()
        self.assertEqual((len(data["observations"]), len(data["pulses"])), (8, 8))
        self.assertTrue(all(row["sighting_count"] == 1 for row in data["observations"].values()))
        self.assertTrue(all(row["observation_status"] == "OBSERVED" for row in data["observations"].values()))


if __name__ == "__main__":
    unittest.main()
