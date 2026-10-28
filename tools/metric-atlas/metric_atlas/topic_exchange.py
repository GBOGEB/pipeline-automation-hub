"""Source-bound topic census exchange, subscriptions and ACK-based cache reuse.

Source owners retain census authority. This module only stages immutable metadata,
checks independently evidenced delivery/ACK receipts and decides targeted pull vs
re-census. It performs no network I/O, dispatch, source writes or engineering approval.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path

PACKET_SCHEMA = "qps.topic-census.packet.v1"
PUB_SCHEMA = "qps.topic-census.publication.v1"
ACK_SCHEMA = "qps.topic-census.ack.v1"
LEDGER_SCHEMA = "qps.topic-census.ledger.v1"
DECISION_SCHEMA = "qps.topic-census.decision.v1"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA64 = re.compile(r"[0-9a-f]{64}\Z")
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
TOPIC = re.compile(r"[a-z0-9][a-z0-9._-]{2,119}\Z")
MAX_RECIPIENTS = 8  # subscribers, not workers
MAX_TTL_SECONDS = 7 * 86400


class ExchangeError(ValueError):
    """Bad provenance or stale concurrency evidence; fail closed."""


def require(ok, reason):
    if not ok:
        raise ExchangeError(reason)


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def digest(obj):
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


def timestamp(value):
    require(isinstance(value, str) and value.endswith("Z"), "NON_UTC_TIMESTAMP")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExchangeError("INVALID_TIMESTAMP") from exc
    require(dt.tzinfo is not None and dt.utcoffset().total_seconds() == 0, "NON_UTC_TIMESTAMP")
    return dt


def _sha(value, length):
    return isinstance(value, str) and bool((SHA40 if length == 40 else SHA64).fullmatch(value))


def _repo(value):
    return isinstance(value, str) and bool(REPO.fullmatch(value))


def _unsigned(record, own_hash_field):
    return {k: v for k, v in record.items() if k != own_hash_field}


def create_packet(*, topic, producer_repo, producer_head, scope_sha256, source_sha256,
                  receipt_sha256, recipients, sequence, observed_at, expires_at,
                  prior_packet_sha256=None, evidence_class="REVIEW_OBSERVATION"):
    """Stage an immutable metadata packet; never call this proof of delivery."""
    require(isinstance(topic, str) and TOPIC.fullmatch(topic), "INVALID_TOPIC")
    require(_repo(producer_repo) and _sha(producer_head, 40), "INVALID_PRODUCER_HEAD")
    require(all(_sha(v, 64) for v in (scope_sha256, source_sha256, receipt_sha256)), "INVALID_SOURCE_HASH")
    require(type(sequence) is int and sequence >= 1, "INVALID_TOPIC_SEQUENCE")
    require((sequence == 1 and prior_packet_sha256 is None) or
            (sequence > 1 and _sha(prior_packet_sha256, 64)), "MISSING_PREVIOUS_PACKET")
    require(isinstance(recipients, list) and 1 <= len(recipients) <= MAX_RECIPIENTS and
            all(_repo(r) for r in recipients) and len(set(recipients)) == len(recipients),
            "INVALID_RECIPIENTS")
    require(evidence_class in {"REVIEW_OBSERVATION", "EXACT_HEAD_CI_OBSERVATION", "CANONICAL_METRIC_RECEIPT"},
            "INVALID_EVIDENCE_CLASS")
    duration = (timestamp(expires_at) - timestamp(observed_at)).total_seconds()
    require(0 < duration <= MAX_TTL_SECONDS, "UNBOUNDED_OR_NEGATIVE_TTL")
    packet = {"schema": PACKET_SCHEMA, "topic": topic, "producer_repo": producer_repo,
              "producer_head": producer_head, "scope_sha256": scope_sha256,
              "source_sha256": source_sha256, "receipt_sha256": receipt_sha256,
              "recipients": sorted(recipients), "sequence": sequence,
              "prior_packet_sha256": prior_packet_sha256,
              "observed_at": observed_at, "expires_at": expires_at,
              "evidence_class": evidence_class, "transport": "STAGED_ONLY",
              "source_mutation": False, "engineering_approval": False,
              "merge_authorized": False, "authority_transfer": False}
    packet["packet_sha256"] = digest(packet)
    return packet


def verify_packet(p):
    require(isinstance(p, dict) and p.get("schema") == PACKET_SCHEMA, "INVALID_PACKET_SCHEMA")
    require(p.get("packet_sha256") == digest(_unsigned(p, "packet_sha256")), "PACKET_DIGEST_MISMATCH")
    expected = create_packet(topic=p["topic"], producer_repo=p["producer_repo"],
                             producer_head=p["producer_head"], scope_sha256=p["scope_sha256"],
                             source_sha256=p["source_sha256"], receipt_sha256=p["receipt_sha256"],
                             recipients=p["recipients"], sequence=p["sequence"],
                             observed_at=p["observed_at"], expires_at=p["expires_at"],
                             prior_packet_sha256=p["prior_packet_sha256"],
                             evidence_class=p["evidence_class"])
    require(expected == p, "PACKET_CONTAINS_UNSUPPORTED_CLAIM")
    return p


def make_publication(packet, *, transport, locator, evidence_id, observed_at):
    """A recorded external delivery pointer, not recipient acknowledgment."""
    verify_packet(packet)
    require(transport in {"GITHUB_PR_COMMENT", "GITHUB_ISSUE_COMMENT", "ACTIONS_ARTIFACT", "OWNER_DMS"},
            "UNSUPPORTED_PUBLICATION_TRANSPORT")
    require(isinstance(locator, str) and locator.startswith("https://") and len(locator) <= 2000,
            "INVALID_DELIVERY_LOCATOR")
    require(isinstance(evidence_id, str) and evidence_id and len(evidence_id) <= 120,
            "INVALID_DELIVERY_EVIDENCE")
    require(timestamp(observed_at) >= timestamp(packet["observed_at"]), "PUBLICATION_BEFORE_PACKET")
    pub = {"schema": PUB_SCHEMA, "packet_sha256": packet["packet_sha256"],
           "transport": transport, "locator": locator, "evidence_id": evidence_id,
           "observed_at": observed_at, "delivery_state": "POSTED_NOT_ACKNOWLEDGED",
           "authority_transfer": False}
    pub["publication_sha256"] = digest(pub)
    return pub


def verify_publication(packet, pub):
    verify_packet(packet)
    require(isinstance(pub, dict) and pub.get("schema") == PUB_SCHEMA, "INVALID_PUBLICATION")
    require(pub.get("publication_sha256") == digest({k:v for k,v in pub.items() if k != "publication_sha256"}),
            "PUBLICATION_DIGEST_MISMATCH")
    expected = make_publication(packet, transport=pub["transport"], locator=pub["locator"],
                                evidence_id=pub["evidence_id"], observed_at=pub["observed_at"])
    require(expected == pub, "PUBLICATION_FORGED_FIELDS")
    return pub


def create_ack(packet, pub, *, recipient, recipient_head, ack_at, proof_locator,
               proof_id, externally_verified=False):
    """Controller must independently read back the proof to set verified=True."""
    verify_publication(packet, pub)
    require(recipient in packet["recipients"] and _sha(recipient_head, 40), "UNSUBSCRIBED_OR_INVALID_ACK_SOURCE")
    require(timestamp(ack_at) >= timestamp(pub["observed_at"]), "ACK_BEFORE_PUBLICATION")
    require(isinstance(proof_locator, str) and proof_locator.startswith("https://"), "ACK_MISSING_EXTERNAL_PROOF")
    require(isinstance(proof_id, str) and bool(proof_id), "ACK_MISSING_PROOF_ID")
    require(type(externally_verified) is bool, "INVALID_VERIFICATION_FLAG")
    ack = {"schema": ACK_SCHEMA, "packet_sha256": packet["packet_sha256"],
           "publication_sha256": pub["publication_sha256"], "recipient": recipient,
           "recipient_head": recipient_head, "ack_at": ack_at, "proof_locator": proof_locator,
           "proof_id": proof_id, "verification": ("CONTROLLER_READBACK_VERIFIED" if externally_verified
                                                 else "CLAIMED_NOT_VERIFIED"),
           "authority_transfer": False}
    ack["ack_sha256"] = digest(ack)
    return ack


def verify_ack(packet, pub, ack):
    verify_publication(packet, pub)
    require(isinstance(ack, dict) and ack.get("schema") == ACK_SCHEMA, "INVALID_ACK_SCHEMA")
    require(ack.get("ack_sha256") == digest(_unsigned(ack, "ack_sha256")), "ACK_DIGEST_MISMATCH")
    expected = create_ack(packet, pub, recipient=ack["recipient"], recipient_head=ack["recipient_head"],
                          ack_at=ack["ack_at"], proof_locator=ack["proof_locator"],
                          proof_id=ack["proof_id"],
                          externally_verified=(ack["verification"] == "CONTROLLER_READBACK_VERIFIED"))
    require(expected == ack, "ACK_FORGED_FIELDS")
    return ack


def decide(packet, *, recipient, current_head, current_scope_sha256,
           current_source_sha256, at, publication=None, acknowledgments=(),
           latest_sequence=None, invalidated=False):
    """Conservative per-topic recipient decision, never a CI or merge admission."""
    verify_packet(packet)
    require(_repo(recipient) and _sha(current_head, 40), "BAD_CURRENT_HEAD")
    require(_sha(current_scope_sha256, 64) and _sha(current_source_sha256, 64), "BAD_CURRENT_SOURCE")
    require(timestamp(at) >= timestamp(packet["observed_at"]), "DECISION_BEFORE_OBSERVATION")
    require(type(invalidated) is bool, "INVALID_INVALIDATION_FLAG")
    require(latest_sequence is None or (type(latest_sequence) is int and latest_sequence >= packet["sequence"]),
            "INVALID_LATEST_SEQUENCE")
    require(isinstance(acknowledgments, (list, tuple)), "INVALID_ACK_LIST")
    result = {"schema": DECISION_SCHEMA, "topic": packet["topic"],
              "recipient": recipient, "packet_sha256": packet["packet_sha256"],
              "at": at, "decision": None, "producer_recensus_required": False,
              "recipient_pull_required": False, "ci_retest_authorized": False,
              "merge_authorized": False, "authority_transfer": False}
    if recipient not in packet["recipients"]:
        decision = "NOT_SUBSCRIBED"
    elif invalidated or (latest_sequence is not None and latest_sequence > packet["sequence"]):
        decision = "STALE_PACKET_PULL_LATEST"
        result["recipient_pull_required"] = True
    elif current_source_sha256 != packet["source_sha256"] or current_scope_sha256 != packet["scope_sha256"]:
        decision = "TARGETED_RECENSUS_REQUIRED"
        result["producer_recensus_required"] = True
    elif timestamp(at) >= timestamp(packet["expires_at"]):
        decision = "TARGETED_RECENSUS_REQUIRED"
        result["producer_recensus_required"] = True
    elif current_head != packet["producer_head"]:
        decision = "VERIFY_HEAD_BRIDGE_NO_FULL_RECENSUS"
    elif publication is None:
        decision = "STAGED_NOT_DELIVERED"
    else:
        verify_publication(packet, publication)
        matched = []
        for a in acknowledgments:
            verify_ack(packet, publication, a)
            if a["recipient"] == recipient:
                matched.append(a)
        require(len(matched) <= 1 or len({a["ack_sha256"] for a in matched}) == 1,
                "CONFLICTING_RECIPIENT_ACKS")
        verified = bool(matched and matched[0]["verification"] == "CONTROLLER_READBACK_VERIFIED")
        decision = "REUSE_ACKNOWLEDGED_NO_RECENSUS" if verified else "PULL_EXISTING_PACKET_NO_RECENSUS"
        result["recipient_pull_required"] = not verified
    result["decision"] = decision
    return result


def new_ledger():
    return {"schema": LEDGER_SCHEMA, "events": [], "tail_sha256": None,
            "authority_transfer": False, "merge_authorized": False}


def append_event(ledger, *, kind, topic, packet_sha256, recipient=None,
                 evidence_sha256, at, expected_tail_sha256):
    """Optimistic CAS, strict chain and idempotent exact replay; no network writes."""
    validate_ledger(ledger)
    require(kind in {"STAGED", "PUBLICATION_POSTED", "RECIPIENT_ACK", "SOURCE_DRIFT", "INVALIDATED"},
            "INVALID_EVENT_KIND")
    require(isinstance(topic, str) and TOPIC.fullmatch(topic), "BAD_EVENT_TOPIC")
    require(_sha(packet_sha256, 64) and _sha(evidence_sha256, 64), "BAD_EVENT_HASH")
    require(recipient is None or _repo(recipient), "BAD_EVENT_RECIPIENT")
    timestamp(at)
    unique = [topic, packet_sha256, kind, recipient]
    payload = {"kind": kind, "topic": topic, "packet_sha256": packet_sha256,
               "recipient": recipient, "evidence_sha256": evidence_sha256, "at": at,
               "event_id": digest(unique)}
    for old in ledger["events"]:
        if old["event_id"] == payload["event_id"]:
            require(all(old.get(k) == v for k,v in payload.items()), "CONFLICTING_REPLAY")
            return ledger  # exact replay is idempotent even with an old CAS token
    require(expected_tail_sha256 == ledger["tail_sha256"], "STALE_TAIL_CAS")
    event = {**payload, "previous_event_sha256": ledger["tail_sha256"]}
    event["event_sha256"] = digest(event)
    out = {**ledger, "events": [*ledger["events"], event], "tail_sha256": event["event_sha256"]}
    validate_ledger(out)
    return out


def validate_ledger(ledger):
    require(isinstance(ledger, dict) and ledger.get("schema") == LEDGER_SCHEMA and
            ledger.get("merge_authorized") is False and ledger.get("authority_transfer") is False and
            isinstance(ledger.get("events"), list), "INVALID_LEDGER")
    parent = None
    event_ids = set()
    for event in ledger["events"]:
        require(isinstance(event, dict) and event.get("previous_event_sha256") == parent,
                "BROKEN_EVENT_CHAIN")
        require(event.get("event_sha256") == digest(_unsigned(event, "event_sha256")), "EVENT_HASH_MISMATCH")
        require(event.get("event_id") not in event_ids, "DUPLICATE_EVENT_ID")
        event_ids.add(event["event_id"])
        parent = event["event_sha256"]
    require(ledger.get("tail_sha256") == parent, "STALE_LEDGER_TAIL")
    return ledger


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", required=True, type=Path)
    parser.add_argument("--current", required=True, type=Path,
                        help="JSON with recipient,current_head,current_scope_sha256,current_source_sha256,at")
    parser.add_argument("--publication", type=Path)
    parser.add_argument("--acks", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    data = json.loads(args.current.read_text(encoding="utf-8"))
    pub = json.loads(args.publication.read_text(encoding="utf-8")) if args.publication else None
    acks = json.loads(args.acks.read_text(encoding="utf-8")) if args.acks else []
    d = decide(json.loads(args.packet.read_text(encoding="utf-8")), publication=pub,
               acknowledgments=acks, **data)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(d, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(d["decision"])


if __name__ == "__main__":
    main()