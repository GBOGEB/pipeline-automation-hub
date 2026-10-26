#!/usr/bin/env python3
"""QPS-private-owner signed bridge for PUBLIC CODE PURPLE watch candidates.

Extends watch_decision, never replaces the canonical scale-dock journal, never
fetches GitHub, sends alerts, creates QPS acceptance, or authorizes a merge.
Only opaque QPS child/dependency/receipt tokens cross this public boundary.
The HMAC key is provisioned solely by the owner-side execution environment.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import hmac
import json
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import watch_decision as decision

SCHEMA = "codepurple.qps.owner_bridge.v1"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
CLASSES = frozenset("ABCD")
CHECK_KEYS = frozenset({
    "source_native_verified", "qps_owner_verified", "source_cohort_complete", "qps_native",
    "security", "independent_review", "required_checks",
    "last_push_approval", "stale_dismissal", "threads_resolved",
    "up_to_date", "blocked_red_canary", "matched_coverage",
    "authenticated_missioncontrol",
})
FULL_GOVERNANCE = frozenset({
    "independent_review", "last_push_approval", "stale_dismissal",
    "threads_resolved", "up_to_date", "blocked_red_canary",
})
STATUSES = frozenset({"PASS", "FAIL", "UNKNOWN"})


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError("QPS_EDGE_HOLD:" + reason)


def exact(value, keys, label):
    require(type(value) is dict and set(value) == set(keys), label + " fields")
    return value


def digest(value) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False)


def owner_mac(key: bytes, attestation: dict) -> str:
    """Used by the private QPS owner signer; never store key in Git or logs."""
    require(type(key) is bytes and len(key) >= 32, "owner signing key unavailable")
    return hmac.new(key, canonical(attestation).encode("ascii"),
                    hashlib.sha256).hexdigest()


def utc(value: str) -> datetime:
    return decision._utc(value)


def _hex(value, name, sha=False):
    require(type(value) is str and
            (SHA40 if sha else HEX64).fullmatch(value) is not None,
            name + " must be full digest")
    return value


def _source_key(event: dict):
    identity, native = event["identity"], event["native"]
    lane = event["repository"] + "::" + event["lane"] + "::" + identity["kind"]
    return decision._digest([lane, identity["checkout_sha"], native["run_id"],
                             native["attempt"], native["job_id"]]), lane


def qualify(event: dict, candidate: dict, envelope: dict, key: bytes,
            baseline: dict | None = None) -> dict:
    """Fail-closed, signed qualification; NEVER native acceptance authority.

    Authenticity is conditional on QPS private key custody and the QPS signer
    having independently verified the upstream native and owner receipts.
    Caller-asserted GitHub values remain insufficient without that signing.
    """
    require(type(key) is bytes and len(key) >= 32, "owner key required")
    decision.validate(event)  # public-only, exact source and native time contract
    exact(candidate, {"event_key", "lane", "reasons", "source",
                      "coverage_delta", "admission"}, "candidate")
    require(candidate["source"] == "CALLER_ASSERTED_NEEDS_NATIVE_READBACK"
            and candidate["admission"] == "HOLD", "noncanonical candidate")
    event_key, lane = _source_key(event)
    require(candidate["event_key"] == event_key and candidate["lane"] == lane,
            "candidate native identity mismatch")
    require(type(candidate["reasons"]) is list and candidate["reasons"]
            and all(type(x) is str for x in candidate["reasons"]),
            "candidate must describe a transition")
    exact(envelope, {"attestation", "signature"}, "signed proof")
    a = exact(envelope["attestation"], {
        "schema", "class", "effect", "event_key", "source_sha",
        "run_id", "attempt", "job_id", "completed_at", "issued_at",
        "event_sha256", "candidate_sha256", "baseline_sha256",
        "child_token", "dependency_token", "receipt_token", "checks",
    }, "attestation")
    require(a["schema"] == SCHEMA, "attestation schema")
    _hex(envelope["signature"], "signature")
    require(hmac.compare_digest(owner_mac(key, a), envelope["signature"]),
            "QPS owner HMAC failed")
    require(a["class"] in CLASSES, "unknown alert class")
    for k in ("child_token", "dependency_token", "receipt_token"):
        _hex(a[k], k)
    _hex(a["source_sha"], "source SHA", sha=True)
    require(a["event_key"] == event_key, "signed event mismatch")
    _hex(a["event_sha256"], "event digest")
    require(a["event_sha256"] == digest(event), "signed event payload mismatch")
    _hex(a["candidate_sha256"], "candidate digest")
    require(a["candidate_sha256"] == digest(candidate),
            "signed candidate justification mismatch")
    require(a["source_sha"] == event["identity"]["checkout_sha"],
            "signed source checkout mismatch")
    n = event["native"]
    require(all(type(a[k]) is int and a[k] == n[k]
                for k in ("run_id", "attempt", "job_id")), "native run binding")
    require(a["completed_at"] == n["completed_at"]
            and utc(a["completed_at"]) <= utc(a["issued_at"]),
            "signed completion / issued clock")
    c = exact(a["checks"], CHECK_KEYS, "checks")
    for k in ("source_native_verified", "qps_owner_verified",
              "source_cohort_complete", "independent_review", "last_push_approval",
              "stale_dismissal", "threads_resolved", "up_to_date",
              "blocked_red_canary", "matched_coverage",
              "authenticated_missioncontrol"):
        require(type(c[k]) is bool, "check must be boolean " + k)
    for k in ("qps_native", "security", "required_checks"):
        require(c[k] in STATUSES, "invalid check " + k)
    require(c["source_native_verified"] and c["qps_owner_verified"],
            "native and owner attestation required")
    reasons = set(candidate["reasons"])
    success = event["result"]["conclusion"] == "success"
    failure = event["result"]["conclusion"] == "failure"
    full = (all(c[k] for k in FULL_GOVERNANCE)
            and c["qps_native"] == "PASS"
            and c["security"] == "PASS"
            and c["required_checks"] == "PASS")
    cls, effect = a["class"], a["effect"]
    if cls in {"A", "B", "D"} or (cls == "C" and effect == "UNBLOCK"):
        require(event["identity"]["kind"] != "SYNTHETIC_MERGE",
                "synthetic merge is not exact native admission")
        require(all(x["state"] == "PASS" for x in event["result"]["required_receipts"]),
                "raw required-check veto")
    if cls != "B":
        require(a["baseline_sha256"] is None, "non-B baseline not permitted")
    if cls == "A":
        require(effect == "ACCEPT" and success and full
                and bool(reasons & {"RED_TO_GREEN",
                                    "REQUIRED_RECEIPT_RECOVERY_CANDIDATE"}),
                "A requires governed parent and a recovered named QPS edge")
    elif cls == "B":
        require(baseline is not None and type(baseline) is dict
                and c["source_cohort_complete"], "B baseline/cohort completeness absent")
        decision.validate(baseline)
        require(a["baseline_sha256"] == decision._digest(baseline),
                "B signed baseline mismatch")
        require(baseline["repository"] == event["repository"]
                and baseline["lane"] == event["lane"]
                and baseline["identity"]["kind"] == event["identity"]["kind"]
                and utc(baseline["native"]["completed_at"]) < utc(n["completed_at"])
                and baseline["coverage"] is not None
                and event["coverage"] is not None
                and decision._coverage(baseline["coverage"]) == decision._coverage(event["coverage"]),
                "B source/instrumentation/denominator cohort mismatch")
        computed = {axis: event["coverage"][axis]["covered"] - baseline["coverage"][axis]["covered"]
                    for axis in ("statements", "branches")}
        delta = candidate["coverage_delta"]
        require(delta == computed, "B coverage delta differs from native observations")
        require(effect == "ACCEPT" and success and full
                and c["matched_coverage"] and
                "SOURCE_MATCHED_COVERAGE_CHANGE" in reasons
                and type(delta) is dict
                and set(delta) == {"statements", "branches"}
                and all(type(delta[k]) is int and delta[k] >= 0 for k in delta)
                and any(delta[k] > 0 for k in delta),
                "B requires matched source/cohort coverage improvement")
    elif cls == "C":
        require(effect in ("BLOCK", "UNBLOCK"), "C effect")
        if effect == "BLOCK":
            require(failure and
                    bool(reasons & {"ATTRIBUTABLE_RED_CANDIDATE",
                                    "GREEN_TO_RED"}),
                    "C block must be attributable first-red")
        else:
            require(success and full
                    and bool(reasons & {"RED_TO_GREEN",
                                        "REQUIRED_RECEIPT_RECOVERY_CANDIDATE"}),
                    "C unblock requires owner-verified native recovery")
    else:
        require(effect == "ACCEPT" and full and success
                and event["repository"] == "GBOGEB/pipeline-automation-hub"
                and c["authenticated_missioncontrol"]
                and bool(reasons & {"RED_TO_GREEN",
                                    "REQUIRED_RECEIPT_RECOVERY_CANDIDATE"}),
                "D requires authenticated MissionControl milestone")
    proof_digest = digest(envelope)
    notification_id = digest(["QPS_EDGE_NOTIFY_V1", cls, event_key,
                              a["child_token"], a["dependency_token"]])
    return {
        "notification_id": notification_id,
        "event_key": event_key,
        "class": cls,
        "effect": effect,
        "child_token": a["child_token"],
        "dependency_token": a["dependency_token"],
        "receipt_token": a["receipt_token"],
        "completed_at": a["completed_at"],
        "proof_digest": proof_digest,
        "source_sha": a["source_sha"],
        "envelope": canonical(envelope),
        "formal_engineering_credit_delta": 0,
        "merge_admission": "HOLD",
        "delivery": "NOT_SENT",
    }


DDL = """
CREATE TABLE IF NOT EXISTS native_observations (
 event_key TEXT PRIMARY KEY, repository TEXT NOT NULL, lane TEXT NOT NULL,
 fingerprint TEXT, payload_sha256 TEXT NOT NULL,
 payload_json TEXT NOT NULL, completed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS observations (
 event_key TEXT NOT NULL, child_token TEXT NOT NULL,
 class TEXT NOT NULL, proof_digest TEXT NOT NULL,
 proof_json TEXT NOT NULL, completed_at TEXT NOT NULL,
 disposition TEXT NOT NULL,
 PRIMARY KEY(event_key,child_token)
);
CREATE TABLE IF NOT EXISTS root_state (
 child_token TEXT NOT NULL, dependency_token TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('OPEN','CLOSED')),
 completed_at TEXT NOT NULL,
 PRIMARY KEY(child_token,dependency_token)
);
CREATE TABLE IF NOT EXISTS outbox (
 notification_id TEXT PRIMARY KEY, event_key TEXT NOT NULL,
 child_token TEXT NOT NULL, class TEXT NOT NULL,
 payload_json TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('PENDING','CLAIMED','ACKED')),
 claimed_at TEXT, ack_digest TEXT
);
CREATE TABLE IF NOT EXISTS audit (
 seq INTEGER PRIMARY KEY AUTOINCREMENT,
 previous_sha256 TEXT, entry_sha256 TEXT NOT NULL,
 action TEXT NOT NULL, event_key TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL
);
"""


def connect(path: Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path), timeout=20, isolation_level=None)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=FULL")
    db.executescript(DDL)
    return db


def _audit(db, action: str, event_key: str, payload_digest: str) -> None:
    previous = db.execute("SELECT entry_sha256 FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
    parent = previous[0] if previous else None
    entry = digest([parent, action, event_key, payload_digest])
    db.execute("INSERT INTO audit(previous_sha256,entry_sha256,action,event_key,payload_sha256)"
               " VALUES(?,?,?,?,?)", (parent, entry, action, event_key, payload_digest))


def _insert_native(db: sqlite3.Connection, event: dict) -> tuple[str, bool]:
    decision.validate(event)
    eid, lane = _source_key(event)
    immutable = copy.deepcopy(event)
    immutable["native"].pop("observed_at")  # poll timing not source identity
    payload = canonical(immutable)
    checksum = digest(immutable)
    row = db.execute(
        "SELECT payload_sha256 FROM native_observations WHERE event_key=?",
        (eid,)).fetchone()
    if row:
        require(row[0] == checksum, "native observation digest collision")
        return eid, False
    db.execute("INSERT INTO native_observations VALUES(?,?,?,?,?,?,?)",
               (eid, event["repository"], lane,
                event["result"]["fingerprint"], checksum,
                payload, event["native"]["completed_at"]))
    _audit(db, "NATIVE_OBSERVED", eid, checksum)
    return eid, True


def _check_latest_baseline(db: sqlite3.Connection, event: dict,
                           baseline: dict) -> None:
    """Class B must use the immediately prior persisted native event in lane.

    The owner-side signature additionally attests completeness of the
    underlying source cohort. Database order alone cannot prove that GitHub
    returned all eligible jobs when the native API was inaccessible.
    """
    current_id, lane = _source_key(event)
    previous_id, previous_lane = _source_key(baseline)
    require(lane == previous_lane, "B previous lane mismatch")
    previous_row = db.execute(
        "SELECT payload_sha256 FROM native_observations WHERE event_key=?",
        (previous_id,)).fetchone()
    immutable = copy.deepcopy(baseline)
    immutable["native"].pop("observed_at")
    require(previous_row is not None and previous_row[0] == digest(immutable),
            "B predecessor not present with immutable native evidence")
    n = event["native"]
    current_order = (utc(n["completed_at"]), n["run_id"], n["attempt"], n["job_id"])
    nearest = None
    nearest_id = None
    for eid, payload in db.execute(
            "SELECT event_key,payload_json FROM native_observations WHERE lane=?",
            (lane,)):
        if eid == current_id:
            continue
        previous = json.loads(payload)["native"]
        ordering = (utc(previous["completed_at"]), previous["run_id"],
                    previous["attempt"], previous["job_id"])
        if ordering < current_order and (nearest is None or ordering > nearest):
            nearest, nearest_id = ordering, eid
    require(nearest_id == previous_id,
            "B baseline is not immediately preceding native observation")


def observe(db: sqlite3.Connection, event: dict) -> dict:
    """Store public native evidence without inventing a new QPS transition."""
    db.execute("BEGIN IMMEDIATE")
    try:
        key, inserted = _insert_native(db, event)
        db.execute("COMMIT")
        return {"event_key": key, "new_native_observation": inserted,
                "notification_emission": "NONE"}
    except BaseException:
        db.execute("ROLLBACK")
        raise


def record(db: sqlite3.Connection, event: dict, candidate: dict,
           envelope: dict, key: bytes, baseline: dict | None = None) -> dict:
    """Transactional append-only evidence + at-most-once local outbox enqueue.

    No network delivery. On a crash after CLAIMED, reconcile provider receipt
    manually; never automatically resend a claimed notification.
    """
    q = qualify(event, candidate, envelope, key, baseline)
    eid, child, root = q["event_key"], q["child_token"], q["dependency_token"]
    db.execute("BEGIN IMMEDIATE")
    try:
        verify(db, key)
        _insert_native(db, event)
        if q["class"] == "B":
            _check_latest_baseline(db, event, baseline)
        row = db.execute(
            "SELECT proof_digest FROM observations WHERE event_key=? AND child_token=?",
            (eid, child)).fetchone()
        if row:
            require(row[0] == q["proof_digest"],
                    "immutable native/child observation collision")
            db.execute("COMMIT")
            return {"status": "DUPLICATE", "queued": False,
                    "notification_id": None, "admission": "HOLD"}
        disposition = "QUEUED"
        if q["class"] == "C":
            old = db.execute(
                "SELECT state,completed_at FROM root_state"
                " WHERE child_token=? AND dependency_token=?",
                (child, root)).fetchone()
            if old and utc(q["completed_at"]) <= utc(old[1]):
                disposition = "SUPPRESSED_OUT_OF_ORDER"
            elif q["effect"] == "BLOCK":
                if old and old[0] == "OPEN":
                    disposition = "SUPPRESSED_UNRESOLVED_ROOT"
                else:
                    db.execute(
                        "INSERT INTO root_state VALUES(?,?,?,?)"
                        " ON CONFLICT(child_token,dependency_token)"
                        " DO UPDATE SET state=excluded.state,completed_at=excluded.completed_at",
                        (child, root, "OPEN", q["completed_at"]))
            elif not old or old[0] == "CLOSED":
                disposition = "SUPPRESSED_NO_OPEN_ROOT"
            else:
                db.execute(
                    "UPDATE root_state SET state='CLOSED',completed_at=?"
                    " WHERE child_token=? AND dependency_token=?",
                    (q["completed_at"], child, root))
        db.execute("INSERT INTO observations VALUES(?,?,?,?,?,?,?)",
                   (eid, child, q["class"], q["proof_digest"],
                    q["envelope"], q["completed_at"], disposition))
        _audit(db, "OBSERVATION_" + disposition, eid, q["proof_digest"])
        if disposition == "QUEUED":
            payload = {k: q[k] for k in (
                "notification_id", "event_key", "class", "effect",
                "child_token", "dependency_token", "receipt_token",
                "completed_at", "proof_digest", "source_sha",
                "formal_engineering_credit_delta", "merge_admission", "delivery")}
            db.execute("INSERT INTO outbox VALUES(?,?,?,?,?,'PENDING',NULL,NULL)",
                       (q["notification_id"], eid, child, q["class"],
                        canonical(payload)))
            _audit(db, "OUTBOX_QUEUED", q["notification_id"], digest(payload))
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK")
        raise
    return {"status": disposition, "queued": disposition == "QUEUED",
            "notification_id": q["notification_id"] if disposition == "QUEUED" else None,
            "admission": "HOLD"}


def claim(db: sqlite3.Connection, notification_id: str, claimed_at: str):
    """Opt-in single-use claim. No retry after a crash without reconciliation."""
    _hex(notification_id, "notification")
    utc(claimed_at)
    db.execute("BEGIN IMMEDIATE")
    try:
        verify(db)
        row = db.execute("SELECT payload_json,state FROM outbox WHERE notification_id=?",
                         (notification_id,)).fetchone()
        require(row is not None, "unknown outbox identity")
        if row[1] != "PENDING":
            db.execute("COMMIT")
            return None
        db.execute("UPDATE outbox SET state='CLAIMED',claimed_at=? WHERE notification_id=?",
                   (claimed_at, notification_id))
        _audit(db, "OUTBOX_CLAIMED", notification_id, digest([claimed_at]))
        db.execute("COMMIT")
        return json.loads(row[0])
    except BaseException:
        db.execute("ROLLBACK")
        raise


def acknowledge(db: sqlite3.Connection, notification_id: str, provider_digest: str):
    """Record an externally obtained provider receipt digest. No send implied."""
    _hex(notification_id, "notification")
    _hex(provider_digest, "provider receipt")
    db.execute("BEGIN IMMEDIATE")
    try:
        verify(db)
        row = db.execute("SELECT state,ack_digest FROM outbox WHERE notification_id=?",
                         (notification_id,)).fetchone()
        require(row is not None, "unknown outbox identity")
        if row[0] == "ACKED":
            require(row[1] == provider_digest, "ack receipt collision")
            db.execute("COMMIT")
            return False
        require(row[0] == "CLAIMED", "cannot acknowledge unclaimed delivery")
        db.execute("UPDATE outbox SET state='ACKED',ack_digest=? WHERE notification_id=?",
                   (provider_digest, notification_id))
        _audit(db, "OUTBOX_ACKED", notification_id, provider_digest)
        db.execute("COMMIT")
        return True
    except BaseException:
        db.execute("ROLLBACK")
        raise



def _verify_tables_against_audit(db: sqlite3.Connection, audit_rows: list,
                                 key: bytes | None) -> tuple[int, int]:
    """Replay signed/audited native, root and outbox state; reject silent edits.

    The chain is integrity evidence only with independently anchored root.
    This function also protects runtime claim() from trusting a mutated table.
    """
    native = {}
    for eid, repo, lane, fingerprint, checksum, payload, completed in db.execute(
            "SELECT event_key,repository,lane,fingerprint,payload_sha256,"
            "payload_json,completed_at FROM native_observations"):
        value = json.loads(payload)
        require(digest(value) == checksum, "immutable native payload tampering")
        i, n = value["identity"], value["native"]
        actual_lane = repo + "::" + value["lane"] + "::" + i["kind"]
        derived_eid = decision._digest([actual_lane, i["checkout_sha"],
                                       n["run_id"], n["attempt"], n["job_id"]])
        require(repo == value["repository"] and lane == actual_lane
                and eid == derived_eid and completed == n["completed_at"]
                and fingerprint == value["result"]["fingerprint"],
                "native metadata tampering")
        require(eid not in native, "duplicate native event")
        native[eid] = checksum

    observations = {}
    for eid, child, cls, checksum, payload, completed, disposition in db.execute(
            "SELECT event_key,child_token,class,proof_digest,proof_json,"
            "completed_at,disposition FROM observations"):
        doc = json.loads(payload)
        require(digest(doc) == checksum, "observation payload tampering")
        a = doc["attestation"]
        require(eid == a["event_key"] and child == a["child_token"]
                and cls == a["class"] and completed == a["completed_at"]
                and eid in native, "signed observation metadata tampering")
        if key is not None:
            require(hmac.compare_digest(owner_mac(key, a), doc["signature"]),
                    "owner MAC tampering")
        require((eid, checksum) not in observations, "duplicate signed observation")
        observations[(eid, checksum)] = (a, disposition)

    outbox = {}
    for nid, eid, child, cls, payload_json, status, claimed, ack in db.execute(
            "SELECT notification_id,event_key,child_token,class,payload_json,"
            "state,claimed_at,ack_digest FROM outbox"):
        payload = json.loads(payload_json)
        require(type(payload) is dict and payload.get("notification_id") == nid
                and payload.get("event_key") == eid
                and payload.get("child_token") == child
                and payload.get("class") == cls
                and payload.get("merge_admission") == "HOLD"
                and payload.get("formal_engineering_credit_delta") == 0
                and payload.get("delivery") == "NOT_SENT",
                "outbox payload metadata tampering")
        require(nid not in outbox, "duplicate notification id")
        outbox[nid] = (eid, child, cls, payload, status, claimed, ack)

    seen_native, seen_obs = set(), set()
    replay_outbox, replay_roots = {}, {}
    for _seq, _parent, _entry, action, subject, payload_digest in audit_rows:
        if action == "NATIVE_OBSERVED":
            require(subject in native and native[subject] == payload_digest
                    and subject not in seen_native,
                    "native inventory vs audit mismatch")
            seen_native.add(subject)
        elif action.startswith("OBSERVATION_"):
            receipt = (subject, payload_digest)
            require(receipt in observations and receipt not in seen_obs,
                    "signed observation vs audit mismatch")
            a, disposition = observations[receipt]
            require(action == "OBSERVATION_" + disposition
                    and subject in seen_native, "observation transition mismatch")
            seen_obs.add(receipt)
            if a["class"] == "C" and disposition == "QUEUED":
                desired = "OPEN" if a["effect"] == "BLOCK" else "CLOSED"
                replay_roots[(a["child_token"], a["dependency_token"])] = (
                    desired, a["completed_at"])
        elif action == "OUTBOX_QUEUED":
            require(subject in outbox and subject not in replay_outbox,
                    "outbox enqueue vs audit mismatch")
            eid, child, cls, payload, status, claimed, ack = outbox[subject]
            require(digest(payload) == payload_digest, "outbox payload vs audit mismatch")
            receipt = (eid, payload.get("proof_digest"))
            require(receipt in seen_obs, "unbacked outbox signed receipt")
            signed, disposition = observations[receipt]
            require(disposition == "QUEUED" and child == signed["child_token"]
                    and cls == signed["class"]
                    and subject == digest(["QPS_EDGE_NOTIFY_V1", cls, eid,
                                           child, signed["dependency_token"]])
                    and payload.get("dependency_token") == signed["dependency_token"]
                    and payload.get("receipt_token") == signed["receipt_token"]
                    and payload.get("completed_at") == signed["completed_at"]
                    and payload.get("source_sha") == signed["source_sha"]
                    and payload.get("effect") == signed["effect"],
                    "outbox does not bind signed acceptance observation")
            replay_outbox[subject] = "PENDING"
        elif action == "OUTBOX_CLAIMED":
            require(subject in replay_outbox and replay_outbox[subject] == "PENDING",
                    "outbox claim history mismatch")
            claimed = outbox[subject][5]
            require(claimed is not None and digest([claimed]) == payload_digest,
                    "outbox claim timestamp mismatch")
            replay_outbox[subject] = "CLAIMED"
        elif action == "OUTBOX_ACKED":
            require(subject in replay_outbox and replay_outbox[subject] == "CLAIMED",
                    "outbox acknowledgment history mismatch")
            ack = outbox[subject][6]
            require(ack is not None and ack == payload_digest,
                    "outbox acknowledgment digest mismatch")
            replay_outbox[subject] = "ACKED"
        else:
            require(False, "unrecognized audit mutation action")

    require(seen_native == set(native) and seen_obs == set(observations),
            "orphan native/signed observations not in audit")
    require(set(replay_outbox) == set(outbox), "outbox queue vs audit inventory mismatch")
    for nid, state in replay_outbox.items():
        _eid, _child, _cls, _payload, actual_state, claimed, ack = outbox[nid]
        require(actual_state == state, "outbox delivery state tampering")
        require((claimed is None) == (state == "PENDING"),
                "outbox claim metadata tampering")
        require((ack is None) == (state != "ACKED"),
                "outbox acknowledgement state tampering")
    stored_roots = {
        (child, dep): (state, complete)
        for child, dep, state, complete in db.execute(
            "SELECT child_token,dependency_token,state,completed_at FROM root_state")
    }
    require(stored_roots == replay_roots, "root_state diverges from audited evidence")
    return len(native), len(observations)



def verify(db: sqlite3.Connection, key: bytes | None = None,
           expected_root: str | None = None) -> dict:
    """Verify audit chain, owner MAC and (when independently anchored) final root.

    This DB is append-only by application contract, not tamperproof against a
    database administrator. A separately stored trusted expected_root detects
    truncation or rollback of a correctly chained ledger.
    """
    previous = None
    audit_rows = list(db.execute(
        "SELECT seq,previous_sha256,entry_sha256,action,event_key,payload_sha256"
        " FROM audit ORDER BY seq"))
    previous_sequence = 0
    for seq, parent, entry, action, event_key, payload in audit_rows:
        require(seq > previous_sequence and parent == previous and
                digest([parent, action, event_key, payload]) == entry,
                "audit chain tampering")
        previous, previous_sequence = entry, seq
    count = len(audit_rows)
    if expected_root is not None:
        _hex(expected_root, "trusted external audit root")
        require(previous == expected_root, "audit root rollback / mismatch")
    native, observations = _verify_tables_against_audit(db, audit_rows, key)
    return {"audit_entries": count, "native_observations": native,
            "observations": observations,
            "pending": db.execute("SELECT COUNT(*) FROM outbox WHERE state='PENDING'").fetchone()[0],
            "claimed": db.execute("SELECT COUNT(*) FROM outbox WHERE state='CLAIMED'").fetchone()[0],
            "acked": db.execute("SELECT COUNT(*) FROM outbox WHERE state='ACKED'").fetchone()[0],
            "last_audit_sha256": previous,
            "formal_engineering_credit_delta": 0}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Offline signed QPS-effect gate (no alert sender)")
    for arg in ("event", "candidate", "proof"):
        parser.add_argument("--" + arg, type=Path, required=True)
    parser.add_argument("--baseline", type=Path,
                        help="required for B: exact previous native comparator")
    parser.add_argument("--database", type=Path)
    parser.add_argument("--record", action="store_true",
                        help="opt-in local SQLite observation/outbox write")
    args = parser.parse_args(argv)
    try:
        secret = bytes.fromhex(os.environ.get("QPS_OWNER_PROOF_KEY_HEX", ""))
    except ValueError as exc:
        raise ValueError("QPS_EDGE_HOLD:invalid key encoding") from exc
    event = json.loads(args.event.read_text(encoding="utf-8"))
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    proof = json.loads(args.proof.read_text(encoding="utf-8"))
    baseline = json.loads(args.baseline.read_text(encoding="utf-8")) if args.baseline else None
    verdict = qualify(event, candidate, proof, secret, baseline)
    if args.record:
        require(args.database is not None, "database required to record")
        with connect(args.database) as db:
            result = record(db, event, candidate, proof, secret, baseline)
            result["local_store"] = verify(db, secret)
    else:
        result = {"status": "SIGNED_CANDIDATE_DRY_RUN", "queued": False,
                  "notification_emission": "NONE",
                  "requires_owner_native_readback": True}
    # Do not echo signed QPS tokens or private linkage to public CI logs.
    print(canonical(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
