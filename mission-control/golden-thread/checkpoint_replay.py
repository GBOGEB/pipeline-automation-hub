#!/usr/bin/env python3
"""Temporal checkpoint cache and replay-equivalence proof for Golden Thread v1."""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import sys
from pathlib import Path

import golden_thread as gt

CHECKPOINT_SCHEMA = "missioncontrol.golden_thread_checkpoint.v1"


def _projection_digest(projection):
    candidate = copy.deepcopy(projection)
    candidate.pop("projection_digest", None)
    return gt.digest(candidate)


def _finalize_projection(projection, events, boundary=None):
    p = projection
    for key in ("occurrences", "roots", "work_orders", "campaigns", "evidence"):
        p[key] = dict(sorted(p[key].items()))
    p["lineage_edges"] = sorted(p["lineage_edges"], key=lambda x: (x["seq"], x["event_id"]))

    terminal = {
        "SUPERSEDED_WITH_REPLACEMENT",
        "INVALIDATED",
        "CONTROL_ORCHESTRATION",
        "EVIDENCE_ONLY",
        "WORK_ORDER_CHILD",
        "ROOT_EXISTING",
        "ROOT_NEW",
        "CAMPAIGN_MEMBER_ONLY",
        "UNKNOWN_NEEDS_READER",
    }
    orphan = [
        ref
        for ref, obj in p["occurrences"].items()
        if not obj.get("root_ref") and obj.get("routing_disposition") not in terminal
    ]
    unknown = [
        ref
        for ref, obj in p["occurrences"].items()
        if "UNKNOWN_NEEDS_READER" in (obj.get("historian_state"), obj.get("bd_state"))
    ]
    p["metrics"] = {
        "event_count": len(events),
        "occurrence_count": len(p["occurrences"]),
        "root_count": len(p["roots"]),
        "work_order_count": len(p["work_orders"]),
        "campaign_count": len(p["campaigns"]),
        "evidence_count": len(p["evidence"]),
        "lineage_edge_count": len(p["lineage_edges"]),
        "orphan_occurrence_count": len(orphan),
        "orphan_occurrences": orphan,
        "unknown_needs_reader_count": len(unknown),
        "unknown_needs_reader": unknown,
        "lineage_retention_coverage": (
            1.0
            if not p["occurrences"]
            else round((len(p["occurrences"]) - len(orphan)) / len(p["occurrences"]), 6)
        ),
    }
    p["boundary"] = boundary or "CURRENT"
    p["head_event_digest"] = events[-1]["this_event_digest"] if events else gt.GENESIS
    p.pop("projection_digest", None)
    p["projection_digest"] = gt.digest(p)
    return p


def _source_manifest(events):
    manifest = []
    for event in events:
        row = {
            "event_id": event["event_id"],
            "event_digest": event["this_event_digest"],
        }
        for key in ("source_sha", "source_snapshot_digest"):
            if key in event:
                row[key] = event[key]
        manifest.append(row)
    return manifest


def _authority_manifest(projection):
    rows = []
    for family in ("occurrences", "roots", "work_orders", "campaigns", "evidence"):
        for ref, obj in projection[family].items():
            rows.append(
                {
                    "family": family,
                    "ref": ref,
                    "authority_domain": obj.get("authority_domain"),
                    "root_authority": obj.get("root_authority"),
                }
            )
    return sorted(rows, key=lambda x: (x["family"], x["ref"]))


def _gate_manifest(projection):
    rows = []
    for family in ("occurrences", "roots", "work_orders", "campaigns", "evidence"):
        for ref, obj in projection[family].items():
            if obj.get("non_compensating") or obj.get("blocking_predicate") or obj.get("reentry_trigger"):
                rows.append(
                    {
                        "family": family,
                        "ref": ref,
                        "non_compensating": bool(obj.get("non_compensating")),
                        "blocking_predicate": obj.get("blocking_predicate"),
                        "reentry_trigger": obj.get("reentry_trigger"),
                    }
                )
    return sorted(rows, key=lambda x: (x["family"], x["ref"]))


def create_checkpoint(ledger, boundary, checkpoint_id, created_at=None):
    gt.verify_ledger(ledger)
    events = gt.select(ledger, boundary)
    if not events:
        raise gt.GoldenThreadError("checkpoint boundary resolves to no events")
    projection = gt.rebuild(ledger, boundary)
    through = events[-1]
    source_manifest = _source_manifest(events)
    authority_manifest = _authority_manifest(projection)
    gate_manifest = _gate_manifest(projection)
    checkpoint = {
        "schema": CHECKPOINT_SCHEMA,
        "checkpoint_id": checkpoint_id,
        "through_event_id": through["event_id"],
        "through_event_seq": through["seq"],
        "through_event_digest": through["this_event_digest"],
        "projection_schema_version": projection["projection_schema_version"],
        "projection_digest": projection["projection_digest"],
        "source_manifest_digest": gt.digest(source_manifest),
        "authority_digest": gt.digest(authority_manifest),
        "gate_digest": gt.digest(gate_manifest),
        "created_at": created_at
        or dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "authority_transfer": False,
        "projection_snapshot": projection,
    }
    checkpoint["checkpoint_digest"] = gt.digest(checkpoint)
    return checkpoint


def verify_checkpoint(ledger, checkpoint):
    gt.verify_ledger(ledger)
    if checkpoint.get("schema") != CHECKPOINT_SCHEMA:
        raise gt.GoldenThreadError("checkpoint schema mismatch")
    if checkpoint.get("authority_transfer") is not False:
        raise gt.GoldenThreadError("checkpoint authority_transfer must remain false")

    supplied_digest = checkpoint.get("checkpoint_digest")
    body = copy.deepcopy(checkpoint)
    body.pop("checkpoint_digest", None)
    if supplied_digest != gt.digest(body):
        raise gt.GoldenThreadError("checkpoint digest mismatch")

    through_id = checkpoint.get("through_event_id")
    matching = [e for e in ledger["events"] if e["event_id"] == through_id]
    if len(matching) != 1:
        raise gt.GoldenThreadError("checkpoint through_event_id not unique in ledger")
    through = matching[0]
    if through["seq"] != checkpoint.get("through_event_seq"):
        raise gt.GoldenThreadError("checkpoint through_event_seq mismatch")
    if through["this_event_digest"] != checkpoint.get("through_event_digest"):
        raise gt.GoldenThreadError("checkpoint through_event_digest mismatch")

    snapshot = checkpoint.get("projection_snapshot")
    if not isinstance(snapshot, dict):
        raise gt.GoldenThreadError("checkpoint projection_snapshot missing")
    if snapshot.get("projection_digest") != checkpoint.get("projection_digest"):
        raise gt.GoldenThreadError("checkpoint projection digest binding mismatch")
    if _projection_digest(snapshot) != checkpoint.get("projection_digest"):
        raise gt.GoldenThreadError("checkpoint projection snapshot tampered")
    if not snapshot.get("events_applied") or snapshot["events_applied"][-1] != through_id:
        raise gt.GoldenThreadError("checkpoint snapshot does not terminate at through_event_id")

    source_manifest = _source_manifest(ledger["events"][: through["seq"]])
    if gt.digest(source_manifest) != checkpoint.get("source_manifest_digest"):
        raise gt.GoldenThreadError("checkpoint source manifest digest mismatch")
    if gt.digest(_authority_manifest(snapshot)) != checkpoint.get("authority_digest"):
        raise gt.GoldenThreadError("checkpoint authority digest mismatch")
    if gt.digest(_gate_manifest(snapshot)) != checkpoint.get("gate_digest"):
        raise gt.GoldenThreadError("checkpoint gate digest mismatch")

    return {
        "status": "PASS",
        "checkpoint_id": checkpoint["checkpoint_id"],
        "through_event_id": through_id,
        "projection_digest": checkpoint["projection_digest"],
        "authority_transfer": False,
    }


def replay_from_checkpoint(ledger, checkpoint, boundary=None):
    verify_checkpoint(ledger, checkpoint)
    target_events = gt.select(ledger, boundary)
    through_id = checkpoint["through_event_id"]
    positions = [i for i, event in enumerate(target_events) if event["event_id"] == through_id]
    if len(positions) != 1:
        raise gt.GoldenThreadError("target boundary predates or excludes checkpoint")

    projection = copy.deepcopy(checkpoint["projection_snapshot"])
    projection.pop("projection_digest", None)
    for event in target_events[positions[0] + 1 :]:
        gt.apply(projection, event)
    return _finalize_projection(projection, target_events, boundary)


def verify_replay_equivalence(ledger, checkpoint, boundary=None):
    genesis = gt.rebuild(ledger, boundary)
    replayed = replay_from_checkpoint(ledger, checkpoint, boundary)
    status = "PASS" if genesis["projection_digest"] == replayed["projection_digest"] else "FAIL"
    return {
        "schema": "missioncontrol.golden_thread_checkpoint_equivalence.v1",
        "status": status,
        "checkpoint_id": checkpoint["checkpoint_id"],
        "target_boundary": boundary or "CURRENT",
        "genesis_projection_digest": genesis["projection_digest"],
        "checkpoint_projection_digest": replayed["projection_digest"],
        "tail_event_count": len(genesis["events_applied"]) - checkpoint["through_event_seq"],
        "authority_transfer": False,
    }


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _dump(value, path=None):
    text = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if path:
        Path(path).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("create")
    p.add_argument("ledger")
    p.add_argument("boundary")
    p.add_argument("checkpoint_id")
    p.add_argument("--created-at")
    p.add_argument("--out")

    p = sub.add_parser("verify")
    p.add_argument("ledger")
    p.add_argument("checkpoint")

    p = sub.add_parser("replay")
    p.add_argument("ledger")
    p.add_argument("checkpoint")
    p.add_argument("--as-of")
    p.add_argument("--out")

    p = sub.add_parser("verify-equivalence")
    p.add_argument("ledger")
    p.add_argument("checkpoint")
    p.add_argument("--as-of")

    args = parser.parse_args(argv)
    try:
        ledger = _load(args.ledger)
        if args.cmd == "create":
            value = create_checkpoint(
                ledger, args.boundary, args.checkpoint_id, created_at=args.created_at
            )
            _dump(value, args.out)
        else:
            checkpoint = _load(args.checkpoint)
            if args.cmd == "verify":
                value = verify_checkpoint(ledger, checkpoint)
            elif args.cmd == "replay":
                value = replay_from_checkpoint(ledger, checkpoint, args.as_of)
                _dump(value, args.out)
                return 0
            else:
                value = verify_replay_equivalence(ledger, checkpoint, args.as_of)
            _dump(value)
        return 0 if value.get("status", "PASS") == "PASS" else 2
    except gt.GoldenThreadError as exc:
        print("FAIL:", exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
