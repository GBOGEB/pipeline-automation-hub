"""Offline H2 QPS signed-edge, replay, outbox and adversarial tests.

All identifiers are synthetic. No actual QPS-private issue/PR/source references.
"""
from __future__ import annotations

import copy
import hashlib
import hmac
import importlib.util
import pathlib
import sqlite3
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))
import watch_decision as W

spec = importlib.util.spec_from_file_location("watch_qps_edge", ROOT / "watch_qps_edge.py")
Q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(Q)

KEY = b"NONPRODUCTION-SYNTHETIC-QPS-OWNER-KEY-TEST-ONLY"
HEAD, BASE, BLOB = "a" * 40, "b" * 40, "c" * 40
CHILD = hmac.new(KEY, b"fictional-child", hashlib.sha256).hexdigest()
ROOT_TOKEN = hmac.new(KEY, b"fictional-dependency", hashlib.sha256).hexdigest()
RECEIPT = hmac.new(KEY, b"fictional-owner-receipt", hashlib.sha256).hexdigest()


def event(index=1, outcome="failure", *, repo="GBOGEB/ABACUS",
          fingerprint="ROOT401", covered=7, blob=BLOB, denominator=10,
          required="PASS", kind="MERGED_MAIN"):
    identity = {
        "kind": kind, "pr_number": None, "pr_head_sha": None,
        "base_sha": None, "checkout_sha": HEAD,
        "synthetic_merge_sha": None, "merged_main_sha": HEAD,
    }
    if kind == "PR_HEAD":
        identity.update(pr_number=123, pr_head_sha=HEAD, base_sha=BASE,
                        merged_main_sha=None)
    result = {
        "conclusion": outcome,
        "fingerprint": fingerprint if outcome == "failure" else None,
        "required_receipts": [{"name": "required_ci", "state": required}],
    }
    return {
        "schema": W.EVENT_SCHEMA, "repository": repo, "lane": "lane.py3.12",
        "identity": identity,
        "native": {
            "run_id": 1000 + index, "attempt": 1, "job_id": 2000 + index,
            "head_sha": HEAD,
            "completed_at": f"2026-10-26T01:{index:02d}:00Z",
            "observed_at": f"2026-10-26T01:{index:02d}:10Z",
        },
        "result": result,
        "coverage": {
            "files": [{"path": "safe.py", "blob_sha": blob}],
            "tool": "coverage.py", "version": "7.13.3",
            "selection": "matched-tests", "config_sha256": "d" * 64,
            "statements": {"covered": covered, "eligible": denominator},
            "branches": {"covered": 3, "eligible": 5},
        },
    }


def candidates(*events):
    _, notices = W.fold(list(events))
    return notices


def proof(e, c, cls="C", effect="BLOCK", *, baseline=None, overrides=None,
          child=CHILD, dependency=ROOT_TOKEN, key=KEY):
    checks = {
        "source_native_verified": True, "qps_owner_verified": True,
        "source_cohort_complete": baseline is not None,
        "qps_native": "PASS", "security": "PASS",
        "independent_review": True, "required_checks": "PASS",
        "last_push_approval": True, "stale_dismissal": True,
        "threads_resolved": True, "up_to_date": True,
        "blocked_red_canary": True, "matched_coverage": baseline is not None,
        "authenticated_missioncontrol": cls == "D",
    }
    if overrides:
        checks.update(overrides)
    n = e["native"]
    a = {
        "schema": Q.SCHEMA, "class": cls, "effect": effect,
        "event_key": c["event_key"],
        "event_sha256": Q.digest(e),
        "candidate_sha256": Q.digest(c),
        "source_sha": e["identity"]["checkout_sha"],
        "run_id": n["run_id"], "attempt": n["attempt"],
        "job_id": n["job_id"], "completed_at": n["completed_at"],
        "issued_at": n["observed_at"],
        "baseline_sha256": W._digest(baseline) if baseline else None,
        "child_token": child, "dependency_token": dependency,
        "receipt_token": RECEIPT,
        "checks": checks,
    }
    return {"attestation": a, "signature": Q.owner_mac(key, a)}


def signed(e, c, cls="C", effect="BLOCK", **kw):
    p = proof(e, c, cls, effect, **kw)
    return Q.qualify(e, c, p, KEY, kw.get("baseline"))


class ExactIdentityAndOwnerBoundary(unittest.TestCase):
    def test_signed_first_red_is_only_a_held_notification_candidate(self):
        e = event()
        c = candidates(e)[0]
        q = signed(e, c)
        self.assertEqual(q["class"], "C")
        self.assertEqual(q["merge_admission"], "HOLD")
        self.assertEqual(q["formal_engineering_credit_delta"], 0)
        self.assertEqual(q["delivery"], "NOT_SENT")

    def test_no_owner_key_or_bad_hmac_fails_closed(self):
        e = event()
        c = candidates(e)[0]
        p = proof(e, c)
        with self.assertRaisesRegex(ValueError, "owner key"):
            Q.qualify(e, c, p, b"")
        p["signature"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "HMAC failed"):
            Q.qualify(e, c, p, KEY)

    def test_reject_unapproved_private_input_fields(self):
        e = event()
        c = candidates(e)[0]
        p = proof(e, c)
        p["attestation"]["raw_private_issue"] = "not allowed"
        p["signature"] = Q.owner_mac(KEY, p["attestation"])
        with self.assertRaisesRegex(ValueError, "attestation fields"):
            Q.qualify(e, c, p, KEY)

    def test_reject_private_repo_source(self):
        e = event(repo="GBOGEB/cryoplant-project")
        _, lane = Q._source_key(e)
        c = {"event_key": Q._source_key(e)[0], "lane": lane,
             "reasons": ["ATTRIBUTABLE_RED_CANDIDATE"],
             "source": "CALLER_ASSERTED_NEEDS_NATIVE_READBACK",
             "coverage_delta": None, "admission": "HOLD"}
        with self.assertRaisesRegex(ValueError, "restricted"):
            Q.qualify(e, c, proof(e, c), KEY)

    def test_changed_run_and_stale_native_sha_denied(self):
        e = event()
        c = candidates(e)[0]
        p = proof(e, c)
        p["attestation"]["job_id"] += 1
        p["signature"] = Q.owner_mac(KEY, p["attestation"])
        with self.assertRaisesRegex(ValueError, "native run binding"):
            Q.qualify(e, c, p, KEY)
        e["native"]["head_sha"] = "e" * 40
        with self.assertRaisesRegex(ValueError, "run head"):
            Q.qualify(e, c, proof(event(), c), KEY)

    def test_401_reachability_is_unknown_not_zero(self):
        self.assertEqual(W.visibility(401)["state"], "UNKNOWN")
        self.assertIsNone(W.visibility(401)["qualified_cells"])


class FourClassNoncompensatingGates(unittest.TestCase):
    def test_A_recovered_but_independent_review_missing_is_held(self):
        e0, e1 = event(1), event(2, outcome="success")
        cand = candidates(e0, e1)[-1]
        p = proof(e1, cand, "A", "ACCEPT",
                  overrides={"independent_review": False})
        with self.assertRaisesRegex(ValueError, "governed parent"):
            Q.qualify(e1, cand, p, KEY)
        self.assertEqual(signed(e1, cand, "A", "ACCEPT")["class"], "A")

    def test_raw_ci_red_cannot_be_hidden_by_signed_green_flags(self):
        e0 = event(1)
        e1 = event(2, outcome="success", required="FAIL")
        cand = candidates(e0, e1)[-1]
        with self.assertRaisesRegex(ValueError, "raw required-check veto"):
            signed(e1, cand, "A", "ACCEPT")

    def test_B_requires_exact_cohort_comparator_and_gain(self):
        a = event(1, outcome="success", covered=7)
        b = event(2, outcome="success", covered=9)
        cand = candidates(a, b)[0]
        result = signed(b, cand, "B", "ACCEPT", baseline=a)
        self.assertEqual(result["class"], "B")
        with self.assertRaisesRegex(ValueError, "baseline"):
            signed(b, cand, "B", "ACCEPT")
        wrong_blob = event(1, outcome="success", covered=7, blob="e" * 40)
        with self.assertRaisesRegex(ValueError, "cohort mismatch"):
            signed(b, cand, "B", "ACCEPT", baseline=wrong_blob)
        wrong_den = event(1, outcome="success", covered=7, denominator=12)
        with self.assertRaisesRegex(ValueError, "cohort mismatch"):
            signed(b, cand, "B", "ACCEPT", baseline=wrong_den)

    def test_B_store_requires_nearest_preceding_native_not_reused_old_baseline(self):
        db = Q.connect(pathlib.Path(tempfile.mkdtemp()) / "test.db")
        self.addCleanup(db.close)
        self.addCleanup(lambda: None)
        older = event(1, outcome="success", covered=7)
        middle = event(2, outcome="success", covered=9)
        latest = event(3, outcome="success", covered=9)
        Q.observe(db, older)
        Q.observe(db, middle)
        baseline_candidate = candidates(older, middle)[0]
        good = Q.record(db, middle, baseline_candidate,
                        proof(middle, baseline_candidate, "B", "ACCEPT", baseline=older),
                        KEY, baseline=older)
        self.assertTrue(good["queued"])
        # Caller can fabricate an old-baseline +2 delta, but current native
        # predecessor already has 9/10 and cannot yield another uplift.
        forged = copy.deepcopy(baseline_candidate)
        forged["event_key"], forged["lane"] = Q._source_key(latest)
        envelope = proof(latest, forged, "B", "ACCEPT", baseline=older)
        with self.assertRaisesRegex(ValueError, "not immediately preceding"):
            Q.record(db, latest, forged, envelope, KEY, baseline=older)
        self.assertEqual(Q.verify(db, KEY)["pending"], 1)

    def test_B_store_rejects_unrecorded_predecessor(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Q.connect(pathlib.Path(tmp) / "test.db")
            try:
                old = event(1, outcome="success", covered=7)
                new = event(2, outcome="success", covered=9)
                candidate = candidates(old, new)[0]
                with self.assertRaisesRegex(ValueError, "predecessor not present"):
                    Q.record(db, new, candidate,
                             proof(new, candidate, "B", "ACCEPT", baseline=old),
                             KEY, baseline=old)
            finally:
                # Close before TemporaryDirectory cleanup: Windows cannot
                # unlink an open SQLite file (WinError 32).
                db.close()

    def test_B_no_gain_or_wrong_delta_rejected(self):
        a = event(1, outcome="success", covered=7)
        b = event(2, outcome="success", covered=9)
        cand = copy.deepcopy(candidates(a, b)[0])
        cand["coverage_delta"]["statements"] = -2
        with self.assertRaisesRegex(ValueError, "delta differs"):
            signed(b, cand, "B", "ACCEPT", baseline=a)

    def test_C_unblock_requires_effective_gates(self):
        a, b = event(1), event(2, outcome="success")
        cand = candidates(a, b)[-1]
        with self.assertRaisesRegex(ValueError, "raw required-check veto|unblock"):
            bad = copy.deepcopy(b)
            bad["result"]["required_receipts"][0]["state"] = "FAIL"
            signed(bad, cand, "C", "UNBLOCK")
        self.assertEqual(signed(b, cand, "C", "UNBLOCK")["effect"], "UNBLOCK")

    def test_D_requires_native_authenticated_missioncontrol(self):
        a = event(1, repo="GBOGEB/pipeline-automation-hub")
        b = event(2, outcome="success", repo="GBOGEB/pipeline-automation-hub")
        cand = candidates(a, b)[-1]
        p = proof(b, cand, "D", "ACCEPT",
                  overrides={"authenticated_missioncontrol": False})
        with self.assertRaisesRegex(ValueError, "authenticated MissionControl"):
            Q.qualify(b, cand, p, KEY)
        self.assertEqual(signed(b, cand, "D", "ACCEPT")["class"], "D")
        with self.assertRaisesRegex(ValueError, "authenticated MissionControl"):
            signed(event(2, outcome="success"), candidates(event(1), event(2, outcome="success"))[-1],
                   "D", "ACCEPT")

    def test_signature_cannot_be_reused_with_changed_notification_reason(self):
        e = event()
        candidate = candidates(e)[0]
        signed_original = proof(e, candidate)
        tampered_candidate = copy.deepcopy(candidate)
        tampered_candidate["reasons"] = ["RED_TO_GREEN"]
        with self.assertRaisesRegex(ValueError, "signed candidate justification mismatch"):
            Q.qualify(e, tampered_candidate, signed_original, KEY)

    def test_signed_proof_rejects_changed_native_event_payload(self):
        native = event()
        candidate = candidates(native)[0]
        signed_by_owner = proof(native, candidate)
        changed = copy.deepcopy(native)
        changed["result"]["conclusion"] = "success"
        changed["result"]["fingerprint"] = None
        with self.assertRaisesRegex(ValueError, "signed event payload mismatch"):
            Q.qualify(changed, candidate, signed_by_owner, KEY)

    def test_owner_signed_digest_field_must_be_hex64(self):
        native = event()
        candidate = candidates(native)[0]
        signed_by_owner = proof(native, candidate)
        signed_by_owner["attestation"]["event_sha256"] = "malformed"
        signed_by_owner["signature"] = Q.owner_mac(KEY, signed_by_owner["attestation"])
        with self.assertRaisesRegex(ValueError, "event digest"):
            Q.qualify(native, candidate, signed_by_owner, KEY)

    def test_mixed_axis_coverage_regression_does_not_qualify(self):
        original = event(1, outcome="success", covered=7)
        changed = event(2, outcome="success", covered=9)
        changed["coverage"]["branches"]["covered"] = 1
        candidate = candidates(original, changed)[0]
        self.assertEqual(candidate["coverage_delta"],
                         {"statements": 2, "branches": -2})
        with self.assertRaisesRegex(ValueError, "coverage improvement"):
            Q.qualify(changed, candidate,
                      proof(changed, candidate, "B", "ACCEPT", baseline=original),
                      KEY, baseline=original)

    def test_unsigned_changed_candidate_reason_fails(self):
        e = event()
        cand = copy.deepcopy(candidates(e)[0])
        cand["event_key"] = "a" * 64
        with self.assertRaisesRegex(ValueError, "native identity mismatch"):
            Q.qualify(e, cand, proof(e, cand), KEY)


    def test_signed_receipt_rejects_required_check_state_relabel(self):
        native = event()
        candidate = candidates(native)[0]
        signed_by_owner = proof(native, candidate)
        altered = copy.deepcopy(native)
        altered["result"]["required_receipts"][0]["state"] = "UNKNOWN"
        with self.assertRaisesRegex(ValueError, "signed event payload mismatch"):
            Q.qualify(altered, candidate, signed_by_owner, KEY)

    def test_branch_gain_cannot_compensate_statement_regression(self):
        original = event(1, outcome="success", covered=9)
        changed = event(2, outcome="success", covered=8)
        changed["coverage"]["branches"]["covered"] = 4
        candidate = candidates(original, changed)[0]
        self.assertEqual(candidate["coverage_delta"],
                         {"statements": -1, "branches": 1})
        with self.assertRaisesRegex(ValueError, "coverage improvement"):
            Q.qualify(changed, candidate,
                      proof(changed, candidate, "B", "ACCEPT", baseline=original),
                      KEY, baseline=original)


class DurableReplayAndOutbox(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_path = pathlib.Path(self.tmp.name) / "watch.db"

    def db(self):
        db = Q.connect(self.db_path)
        self.addCleanup(db.close)
        return db

    def test_twelve_recurrent_native_observations_one_root_one_outbox(self):
        db = self.db()
        failures = [event(i) for i in range(1, 13)]
        first = candidates(*failures)[0]
        for e in failures:
            self.assertTrue(Q.observe(db, e)["new_native_observation"])
        self.assertFalse(Q.observe(db, failures[0])["new_native_observation"])
        a = Q.record(db, failures[0], first, proof(failures[0], first), KEY)
        self.assertEqual(a["status"], "QUEUED")
        self.assertEqual(Q.record(db, failures[0], first,
                                  proof(failures[0], first), KEY)["status"], "DUPLICATE")
        receipt = Q.verify(db, KEY)
        self.assertEqual(receipt["native_observations"], 12)
        self.assertEqual(receipt["pending"], 1)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM root_state").fetchone()[0], 1)
        self.assertEqual(db.execute(
            "SELECT COUNT(*) FROM native_observations WHERE fingerprint='ROOT401'"
        ).fetchone()[0], 12)

    def test_root_block_unblock_reblock_A_B_A_and_stale_suppression(self):
        db = self.db()
        a = event(1)
        b = event(2, outcome="success")
        c = event(3)
        notices = candidates(a, b, c)
        self.assertEqual(len(notices), 3)
        p1 = Q.record(db, a, notices[0], proof(a, notices[0]), KEY)
        p2 = Q.record(db, b, notices[1],
                      proof(b, notices[1], effect="UNBLOCK"), KEY)
        p3 = Q.record(db, c, notices[2], proof(c, notices[2]), KEY)
        self.assertTrue(all(x["queued"] for x in (p1, p2, p3)))
        self.assertEqual(Q.verify(db, KEY)["pending"], 3)
        self.assertEqual(db.execute(
            "SELECT state FROM root_state").fetchone()[0], "OPEN")
        self.assertEqual(Q.record(db, a, notices[0], proof(a, notices[0]), KEY)["status"],
                         "DUPLICATE")

    def test_cannot_unblock_root_never_observed(self):
        db = self.db()
        a = event(1)
        b = event(2, outcome="success")
        notice = candidates(a, b)[-1]
        result = Q.record(db, b, notice, proof(b, notice, effect="UNBLOCK"), KEY)
        self.assertEqual(result["status"], "SUPPRESSED_NO_OPEN_ROOT")
        self.assertEqual(Q.verify(db)["pending"], 0)

    def test_out_of_order_root_event_is_persisted_not_retriggered(self):
        db = self.db()
        newer, older = event(5), event(2)
        # The older event has a candidate when viewed as its own source pulse.
        n1 = candidates(newer)[0]
        n2 = candidates(older)[0]
        self.assertEqual(Q.record(db, newer, n1, proof(newer, n1), KEY)["status"],
                         "QUEUED")
        self.assertEqual(Q.record(db, older, n2, proof(older, n2), KEY)["status"],
                         "SUPPRESSED_OUT_OF_ORDER")
        self.assertEqual(Q.verify(db)["pending"], 1)
        self.assertEqual(Q.verify(db)["native_observations"], 2)

    def test_single_claim_and_ack_no_resend_even_after_restart(self):
        db = self.db()
        e = event()
        c = candidates(e)[0]
        queued = Q.record(db, e, c, proof(e, c), KEY)
        nid = queued["notification_id"]
        payload = Q.claim(db, nid, "2026-10-26T02:00:00Z")
        self.assertEqual(payload["notification_id"], nid)
        self.assertIsNone(Q.claim(db, nid, "2026-10-26T02:01:00Z"))
        db.close()
        db2 = self.db()
        self.assertIsNone(Q.claim(db2, nid, "2026-10-26T02:02:00Z"))
        self.assertTrue(Q.acknowledge(db2, nid, "e" * 64))
        self.assertFalse(Q.acknowledge(db2, nid, "e" * 64))
        self.assertEqual(Q.verify(db2, KEY)["acked"], 1)
        self.assertIsNone(Q.claim(db2, nid, "2026-10-26T02:03:00Z"))
        with self.assertRaisesRegex(ValueError, "ack receipt collision"):
            Q.acknowledge(db2, nid, "f" * 64)

    def test_unclaimed_delivery_cannot_be_acknowledged(self):
        db = self.db()
        e, c = event(), candidates(event())[0]
        nid = Q.record(db, e, c, proof(e, c), KEY)["notification_id"]
        with self.assertRaisesRegex(ValueError, "unclaimed"):
            Q.acknowledge(db, nid, "f" * 64)

    def test_immutable_native_collision_rolls_back(self):
        db = self.db()
        e = event()
        Q.observe(db, e)
        tampered = copy.deepcopy(e)
        tampered["result"]["fingerprint"] = "ANOTHER_ROOT"
        with self.assertRaisesRegex(ValueError, "digest collision"):
            Q.observe(db, tampered)
        self.assertEqual(Q.verify(db)["native_observations"], 1)

    def test_chain_and_payload_tampering_detected(self):
        db = self.db()
        e, c = event(), candidates(event())[0]
        Q.record(db, e, c, proof(e, c), KEY)
        self.assertGreater(Q.verify(db)["audit_entries"], 0)
        db.execute("UPDATE audit SET entry_sha256=? WHERE seq=1", ("f" * 64,))
        with self.assertRaisesRegex(ValueError, "audit chain"):
            Q.verify(db)

    def test_outbox_payload_tampering_rejected_before_claim(self):
        db = self.db()
        e, cand = event(), candidates(event())[0]
        notification = Q.record(db, e, cand, proof(e, cand), KEY)["notification_id"]
        db.execute("UPDATE outbox SET payload_json='{}' WHERE notification_id=?",
                   (notification,))
        with self.assertRaisesRegex(ValueError, "outbox payload metadata"):
            Q.verify(db, KEY)
        with self.assertRaisesRegex(ValueError, "outbox payload metadata"):
            Q.claim(db, notification, "2026-10-26T02:00:00Z")

    def test_forged_ack_state_rejected_by_replayed_audit(self):
        db = self.db()
        e, cand = event(), candidates(event())[0]
        notification = Q.record(db, e, cand, proof(e, cand), KEY)["notification_id"]
        db.execute(
            "UPDATE outbox SET state='ACKED',claimed_at=?,ack_digest=?"
            " WHERE notification_id=?",
            ("2026-10-26T02:00:00Z", "f" * 64, notification))
        with self.assertRaisesRegex(ValueError, "outbox delivery state tampering"):
            Q.verify(db, KEY)

    def test_forged_closed_root_cannot_suppress_next_root_event(self):
        db = self.db()
        e, cand = event(), candidates(event())[0]
        Q.record(db, e, cand, proof(e, cand), KEY)
        db.execute("UPDATE root_state SET state='CLOSED'")
        with self.assertRaisesRegex(ValueError, "root_state diverges"):
            Q.verify(db, KEY)
        newer = event(2)
        changed = copy.deepcopy(candidates(newer)[0])
        with self.assertRaisesRegex(ValueError, "root_state diverges"):
            Q.record(db, newer, changed, proof(newer, changed), KEY)

    def test_deleted_outbox_row_is_detected_from_append_only_audit(self):
        db = self.db()
        e, cand = event(), candidates(event())[0]
        Q.record(db, e, cand, proof(e, cand), KEY)
        db.execute("DELETE FROM outbox")
        with self.assertRaisesRegex(ValueError, "outbox enqueue vs audit"):
            Q.verify(db, KEY)

    def test_externally_trusted_audit_root_rejects_tail_truncation(self):
        db = self.db()
        e, candidate = event(), candidates(event())[0]
        Q.record(db, e, candidate, proof(e, candidate), KEY)
        receipt = Q.verify(db, KEY)
        root = receipt["last_audit_sha256"]
        self.assertEqual(Q.verify(db, KEY, expected_root=root)["last_audit_sha256"], root)
        # A database admin could delete a correctly chained final row.
        db.execute("DELETE FROM audit WHERE seq=(SELECT MAX(seq) FROM audit)")
        # The replay verifier rejects the deleted queue event even without a
        # trusted external anchor; the anchor separately detects rollback.
        with self.assertRaisesRegex(ValueError, "outbox queue vs audit inventory"):
            Q.verify(db, KEY)
        with self.assertRaisesRegex(ValueError, "audit root rollback"):
            Q.verify(db, KEY, expected_root=root)

    def test_no_state_written_when_owner_signature_invalid(self):
        db = self.db()
        e, c = event(), candidates(event())[0]
        p = proof(e, c)
        p["signature"] = "1" * 64
        with self.assertRaisesRegex(ValueError, "HMAC"):
            Q.record(db, e, c, p, KEY)
        self.assertEqual(Q.verify(db)["native_observations"], 0)


if __name__ == "__main__":
    unittest.main()
