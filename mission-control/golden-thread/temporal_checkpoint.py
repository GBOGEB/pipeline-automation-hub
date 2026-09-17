#!/usr/bin/env python3
"""Temporal checkpoint layer for MissionControl Golden Thread v1.

This module is deliberately additive. It consumes a sealed v1 Golden Thread
ledger, validates child injection/disposition payloads, and materializes the
higher-order temporal coordinates:

    k = semantic SSOT generation
    e = governed event sequence

A change in e does not imply a change in k. Only an ACCEPT disposition with
`authoritative_delta_applied=true` advances k.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import golden_thread as gt

TEMPORAL_SCHEMA = "missioncontrol.golden_thread_temporal_checkpoint.v1.1"
SHA_RE = re.compile(r"^[0-9a-f]{7,40}$", re.I)
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$", re.I)
ALLOWED_DISPOSITIONS = {"ACCEPT", "REJECT", "DEFER"}


class TemporalGoldenThreadError(ValueError):
    pass


def load_json(path: Path) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TemporalGoldenThreadError(f"{path}: top-level JSON must be an object")
    return value


def require_mapping(parent: Dict[str, Any], key: str, event_id: str) -> Dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise TemporalGoldenThreadError(f"{event_id}: {key} must be an object")
    return value


def require_string(parent: Dict[str, Any], key: str, context: str) -> str:
    value = parent.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TemporalGoldenThreadError(f"{context}: missing/invalid {key}")
    return value


def validate_digest(value: str, context: str) -> None:
    if not DIGEST_RE.fullmatch(value):
        raise TemporalGoldenThreadError(f"{context}: expected sha256:<64 hex> digest")


def scan_child_transactions(ledger: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and summarize child injections/dispositions embedded in v1 payloads."""

    injections: Dict[str, Dict[str, Any]] = {}
    idempotency_keys: Dict[str, str] = {}
    dispositions: Dict[str, Dict[str, Any]] = {}
    accepted_authoritative_deltas: List[Dict[str, Any]] = []

    for event in ledger.get("events", []):
        if not isinstance(event, dict):
            raise TemporalGoldenThreadError("ledger event must be an object")
        event_id = str(event.get("event_id", "?"))
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            raise TemporalGoldenThreadError(f"{event_id}: payload must be an object")

        if "child_injection" in payload:
            injection = require_mapping(payload, "child_injection", event_id)
            injection_key = require_string(injection, "injection_key", event_id)
            child_repo = require_string(injection, "child_repo", event_id)
            source_digest = require_string(injection, "source_digest", event_id)
            idempotency_key = require_string(injection, "idempotency_key", event_id)
            validate_digest(source_digest, f"{event_id}.child_injection.source_digest")
            validate_digest(idempotency_key, f"{event_id}.child_injection.idempotency_key")

            if injection_key in injections:
                raise TemporalGoldenThreadError(
                    f"{event_id}: duplicate child injection_key {injection_key}"
                )
            if idempotency_key in idempotency_keys:
                prior = idempotency_keys[idempotency_key]
                raise TemporalGoldenThreadError(
                    f"{event_id}: duplicate child obligation idempotency_key; first seen in {prior}"
                )

            injections[injection_key] = {
                "event_id": event_id,
                "child_repo": child_repo,
                "source_digest": source_digest,
                "idempotency_key": idempotency_key,
                "authority_domain": event.get("authority_domain"),
                "non_compensating_preserved": event.get("non_compensating_preserved"),
            }
            idempotency_keys[idempotency_key] = event_id

        if "child_disposition" in payload:
            disposition = require_mapping(payload, "child_disposition", event_id)
            injection_key = require_string(disposition, "injection_key", event_id)
            result = require_string(disposition, "disposition", event_id).upper()

            if injection_key not in injections:
                raise TemporalGoldenThreadError(
                    f"{event_id}: child disposition references unknown injection_key {injection_key}"
                )
            if injection_key in dispositions:
                prior = dispositions[injection_key]["event_id"]
                raise TemporalGoldenThreadError(
                    f"{event_id}: injection {injection_key} already dispositioned by {prior}"
                )
            if result not in ALLOWED_DISPOSITIONS:
                raise TemporalGoldenThreadError(
                    f"{event_id}: child disposition must be ACCEPT, REJECT or DEFER"
                )

            authoritative_delta_applied = bool(
                disposition.get("authoritative_delta_applied", False)
            )
            record: Dict[str, Any] = {
                "event_id": event_id,
                "injection_key": injection_key,
                "disposition": result,
                "authoritative_delta_applied": authoritative_delta_applied,
            }

            if result == "ACCEPT":
                record["child_receipt_ref"] = require_string(
                    disposition, "child_receipt_ref", event_id
                )
                if authoritative_delta_applied:
                    delta_digest = require_string(
                        disposition, "accepted_authoritative_delta_digest", event_id
                    )
                    validate_digest(
                        delta_digest,
                        f"{event_id}.child_disposition.accepted_authoritative_delta_digest",
                    )
                    record["accepted_authoritative_delta_digest"] = delta_digest
                    accepted_authoritative_deltas.append(record)

            elif result == "REJECT":
                record["rejection_reason"] = require_string(
                    disposition, "rejection_reason", event_id
                )
                if authoritative_delta_applied:
                    raise TemporalGoldenThreadError(
                        f"{event_id}: REJECT cannot set authoritative_delta_applied=true"
                    )

            elif result == "DEFER":
                record["owner"] = require_string(disposition, "owner", event_id)
                record["reentry_trigger"] = require_string(
                    disposition, "reentry_trigger", event_id
                )
                if authoritative_delta_applied:
                    raise TemporalGoldenThreadError(
                        f"{event_id}: DEFER cannot set authoritative_delta_applied=true"
                    )

            dispositions[injection_key] = record

    unresolved = sorted(set(injections) - set(dispositions))
    accepted = sorted(
        key for key, record in dispositions.items() if record["disposition"] == "ACCEPT"
    )
    rejected = sorted(
        key for key, record in dispositions.items() if record["disposition"] == "REJECT"
    )
    deferred = sorted(
        key for key, record in dispositions.items() if record["disposition"] == "DEFER"
    )

    return {
        "injection_count": len(injections),
        "disposition_count": len(dispositions),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "deferred_count": len(deferred),
        "unresolved_count": len(unresolved),
        "accepted_authoritative_delta_count": len(accepted_authoritative_deltas),
        "accepted_injection_keys": accepted,
        "rejected_injection_keys": rejected,
        "deferred_injection_keys": deferred,
        "unresolved_injection_keys": unresolved,
        "accepted_authoritative_delta_digests": sorted(
            record["accepted_authoritative_delta_digest"]
            for record in accepted_authoritative_deltas
        ),
        "injections": dict(sorted(injections.items())),
        "dispositions": dict(sorted(dispositions.items())),
    }


def checkpoint_payload(
    ledger: Dict[str, Any],
    *,
    base_semantic_generation_k: int,
    ssot_digest: str | None,
    git_repo: str,
    git_commit_sha: str,
    milestone: str | None = None,
) -> Dict[str, Any]:
    if not isinstance(base_semantic_generation_k, int) or base_semantic_generation_k < 0:
        raise TemporalGoldenThreadError("base_semantic_generation_k must be >= 0")
    if not isinstance(git_repo, str) or "/" not in git_repo:
        raise TemporalGoldenThreadError("git_repo must be owner/repo")
    if not SHA_RE.fullmatch(git_commit_sha):
        raise TemporalGoldenThreadError("git_commit_sha must be 7-40 hexadecimal characters")
    if ssot_digest is not None:
        validate_digest(ssot_digest, "ssot_digest")

    gt.verify_ledger(ledger)
    projection = gt.rebuild(ledger)
    child_summary = scan_child_transactions(ledger)

    delta_count = child_summary["accepted_authoritative_delta_count"]
    engineering_ssot_changed = delta_count > 0
    semantic_generation_k = base_semantic_generation_k + delta_count

    if engineering_ssot_changed and ssot_digest is None:
        raise TemporalGoldenThreadError(
            "authoritative ACCEPT exists but resulting ssot_digest was not supplied"
        )

    payload: Dict[str, Any] = {
        "schema": TEMPORAL_SCHEMA,
        "base_semantic_generation_k": base_semantic_generation_k,
        "semantic_generation_k": semantic_generation_k,
        "event_sequence_e": len(ledger.get("events", [])),
        "engineering_ssot_changed": engineering_ssot_changed,
        "ssot_digest": ssot_digest,
        "thread_digest": ledger.get("head_event_digest"),
        "projection_digest": projection.get("projection_digest"),
        "git_anchor": {
            "repository": git_repo,
            "commit_sha": git_commit_sha,
        },
        "milestone": milestone,
        "child_transaction_summary": child_summary,
        "authority_transfer": False,
        "credit_rule": "ZERO_ENGINEERING_COMPLIANCE_NEGOTIATION_RELEASE_CREDIT_FROM_CHECKPOINT_ALONE",
    }
    payload["checkpoint_digest"] = gt.digest(payload)
    return payload


def verify_checkpoint(ledger: Dict[str, Any], checkpoint: Dict[str, Any]) -> Dict[str, Any]:
    if checkpoint.get("schema") != TEMPORAL_SCHEMA:
        raise TemporalGoldenThreadError("checkpoint schema mismatch")
    if checkpoint.get("authority_transfer") is not False:
        raise TemporalGoldenThreadError("checkpoint authority_transfer must remain false")

    git_anchor = checkpoint.get("git_anchor")
    if not isinstance(git_anchor, dict):
        raise TemporalGoldenThreadError("checkpoint git_anchor must be an object")

    expected = checkpoint_payload(
        ledger,
        base_semantic_generation_k=checkpoint.get("base_semantic_generation_k"),
        ssot_digest=checkpoint.get("ssot_digest"),
        git_repo=git_anchor.get("repository"),
        git_commit_sha=git_anchor.get("commit_sha"),
        milestone=checkpoint.get("milestone"),
    )

    if expected != checkpoint:
        differing = sorted(
            key
            for key in set(expected) | set(checkpoint)
            if expected.get(key) != checkpoint.get(key)
        )
        raise TemporalGoldenThreadError(
            "checkpoint does not reproduce from ledger; differing fields: "
            + ", ".join(differing)
        )

    return {
        "status": "PASS",
        "semantic_generation_k": checkpoint["semantic_generation_k"],
        "event_sequence_e": checkpoint["event_sequence_e"],
        "thread_digest": checkpoint["thread_digest"],
        "projection_digest": checkpoint["projection_digest"],
        "checkpoint_digest": checkpoint["checkpoint_digest"],
        "authority_transfer": False,
    }


def dump_json(value: Dict[str, Any], out: Path | None) -> None:
    rendered = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if out is None:
        sys.stdout.write(rendered)
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered, encoding="utf-8")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build")
    build.add_argument("ledger", type=Path)
    build.add_argument("--base-k", type=int, required=True)
    build.add_argument("--ssot-digest")
    build.add_argument("--git-repo", required=True)
    build.add_argument("--git-commit-sha", required=True)
    build.add_argument("--milestone")
    build.add_argument("--out", type=Path)

    verify = sub.add_parser("verify")
    verify.add_argument("ledger", type=Path)
    verify.add_argument("checkpoint", type=Path)

    args = parser.parse_args(argv)

    try:
        ledger = load_json(args.ledger)
        if args.command == "build":
            result = checkpoint_payload(
                ledger,
                base_semantic_generation_k=args.base_k,
                ssot_digest=args.ssot_digest,
                git_repo=args.git_repo,
                git_commit_sha=args.git_commit_sha,
                milestone=args.milestone,
            )
            dump_json(result, args.out)
        else:
            checkpoint = load_json(args.checkpoint)
            result = verify_checkpoint(ledger, checkpoint)
            dump_json(result, None)
        return 0
    except (gt.GoldenThreadError, TemporalGoldenThreadError, KeyError, TypeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
