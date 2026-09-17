#!/usr/bin/env python3
"""Golden Thread P3: governed checkpoint registry and deterministic cadence policy.

The registry indexes verified checkpoint identities. It does not become a new
snapshot authority and does not contain projection snapshots. Selection is
purely deterministic: choose the newest compatible checkpoint whose event
sequence is <= the requested replay target.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import checkpoint_replay as cpr
import golden_thread as gt

REGISTRY_SCHEMA = "missioncontrol.golden_thread_checkpoint_registry.v1"
POLICY_SCHEMA = "missioncontrol.golden_thread_checkpoint_cadence_policy.v1"
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$", re.I)
DEFAULT_TRIGGERS = [
    "WAVE_CLOSED",
    "DMAIC_CLUSTER_CLOSED",
    "RELEASE_BOUNDARY",
    "CONTROL_PROMOTED",
    "SCHEMA_MIGRATED",
    "FEDERATION_TRANSACTION_ACCEPTED",
]


class CheckpointRegistryError(ValueError):
    pass


def cadence_policy(every_n_events: int = 10, triggers: Optional[List[str]] = None) -> Dict[str, Any]:
    if not isinstance(every_n_events, int) or every_n_events < 1:
        raise CheckpointRegistryError("every_n_events must be >= 1")
    values = sorted(set(triggers or DEFAULT_TRIGGERS))
    if any(not isinstance(v, str) or not v for v in values):
        raise CheckpointRegistryError("checkpoint triggers must be non-empty strings")
    policy = {
        "schema": POLICY_SCHEMA,
        "every_n_events": every_n_events,
        "milestone_triggers": values,
        "wall_clock_cadence_authoritative": False,
        "visual_fidelity_credit": False,
        "authority_transfer": False,
    }
    policy["policy_digest"] = gt.digest(policy)
    return policy


def verify_policy(policy: Dict[str, Any]) -> Dict[str, Any]:
    if policy.get("schema") != POLICY_SCHEMA:
        raise CheckpointRegistryError("cadence policy schema mismatch")
    if policy.get("authority_transfer") is not False:
        raise CheckpointRegistryError("cadence policy authority_transfer must remain false")
    if policy.get("wall_clock_cadence_authoritative") is not False:
        raise CheckpointRegistryError("wall-clock cadence may not be authoritative")
    if policy.get("visual_fidelity_credit") is not False:
        raise CheckpointRegistryError("checkpoint policy may not grant visual fidelity credit")
    if not isinstance(policy.get("every_n_events"), int) or policy["every_n_events"] < 1:
        raise CheckpointRegistryError("cadence policy every_n_events invalid")
    triggers = policy.get("milestone_triggers")
    if not isinstance(triggers, list) or triggers != sorted(set(triggers)):
        raise CheckpointRegistryError("cadence policy milestone_triggers must be sorted unique list")
    body = copy.deepcopy(policy)
    supplied = body.pop("policy_digest", None)
    if supplied != gt.digest(body):
        raise CheckpointRegistryError("cadence policy digest mismatch")
    return {"status": "PASS", "policy_digest": supplied, "authority_transfer": False}


def lineage_anchor(ledger: Dict[str, Any]) -> str:
    gt.verify_ledger(ledger)
    events = ledger.get("events", [])
    if not events:
        return gt.digest({"genesis": gt.GENESIS, "projection_schema_version": ledger.get("projection_schema_version")})
    first = events[0]
    return gt.digest(
        {
            "first_event_id": first["event_id"],
            "first_event_digest": first["this_event_digest"],
            "projection_schema_version": ledger.get("projection_schema_version"),
        }
    )


def empty_registry(ledger: Dict[str, Any], policy: Dict[str, Any]) -> Dict[str, Any]:
    verify_policy(policy)
    registry = {
        "schema": REGISTRY_SCHEMA,
        "lineage_anchor_digest": lineage_anchor(ledger),
        "projection_schema_version": ledger.get("projection_schema_version"),
        "cadence_policy_digest": policy["policy_digest"],
        "entries": [],
        "authority_transfer": False,
    }
    return _seal_registry(registry)


def _seal_registry(registry: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(registry)
    out.pop("registry_digest", None)
    out["registry_digest"] = gt.digest(out)
    return out


def _verify_registry_digest(registry: Dict[str, Any]) -> None:
    body = copy.deepcopy(registry)
    supplied = body.pop("registry_digest", None)
    if supplied != gt.digest(body):
        raise CheckpointRegistryError("checkpoint registry digest mismatch")


def checkpoint_descriptor(
    checkpoint: Dict[str, Any],
    *,
    trigger: str,
    policy: Dict[str, Any],
    checkpoint_ref: Optional[str] = None,
    parent_checkpoint_digest: Optional[str] = None,
) -> Dict[str, Any]:
    if not isinstance(trigger, str) or not trigger:
        raise CheckpointRegistryError("checkpoint trigger required")
    descriptor = {
        "checkpoint_id": checkpoint["checkpoint_id"],
        "checkpoint_digest": checkpoint["checkpoint_digest"],
        "through_event_id": checkpoint["through_event_id"],
        "through_event_seq": checkpoint["through_event_seq"],
        "through_event_digest": checkpoint["through_event_digest"],
        "projection_schema_version": checkpoint["projection_schema_version"],
        "projection_digest": checkpoint["projection_digest"],
        "source_manifest_digest": checkpoint["source_manifest_digest"],
        "authority_digest": checkpoint["authority_digest"],
        "gate_digest": checkpoint["gate_digest"],
        "created_at": checkpoint["created_at"],
        "trigger": trigger,
        "cadence_policy_digest": policy["policy_digest"],
        "checkpoint_ref": checkpoint_ref,
        "parent_checkpoint_digest": parent_checkpoint_digest,
        "authority_transfer": False,
    }
    descriptor["descriptor_digest"] = gt.digest(descriptor)
    return descriptor


def verify_registry(registry: Dict[str, Any], ledger: Dict[str, Any], policy: Dict[str, Any]) -> Dict[str, Any]:
    verify_policy(policy)
    gt.verify_ledger(ledger)
    if registry.get("schema") != REGISTRY_SCHEMA:
        raise CheckpointRegistryError("checkpoint registry schema mismatch")
    if registry.get("authority_transfer") is not False:
        raise CheckpointRegistryError("checkpoint registry authority_transfer must remain false")
    _verify_registry_digest(registry)
    if registry.get("lineage_anchor_digest") != lineage_anchor(ledger):
        raise CheckpointRegistryError("checkpoint registry lineage anchor mismatch")
    if registry.get("projection_schema_version") != ledger.get("projection_schema_version"):
        raise CheckpointRegistryError("checkpoint registry projection schema mismatch")
    if registry.get("cadence_policy_digest") != policy.get("policy_digest"):
        raise CheckpointRegistryError("checkpoint registry cadence policy mismatch")

    events = ledger.get("events", [])
    entries = registry.get("entries")
    if not isinstance(entries, list):
        raise CheckpointRegistryError("checkpoint registry entries must be a list")
    ids, checkpoint_digests, descriptor_digests = set(), set(), set()
    prior_seq = 0
    prior_checkpoint_digest = None
    for entry in entries:
        if not isinstance(entry, dict):
            raise CheckpointRegistryError("checkpoint registry entry must be an object")
        if entry.get("authority_transfer") is not False:
            raise CheckpointRegistryError("checkpoint registry entry authority_transfer must remain false")
        body = copy.deepcopy(entry)
        supplied_descriptor = body.pop("descriptor_digest", None)
        if supplied_descriptor != gt.digest(body):
            raise CheckpointRegistryError("checkpoint descriptor digest mismatch")
        if entry.get("cadence_policy_digest") != policy["policy_digest"]:
            raise CheckpointRegistryError("checkpoint descriptor policy mismatch")
        checkpoint_id = entry.get("checkpoint_id")
        checkpoint_digest = entry.get("checkpoint_digest")
        if checkpoint_id in ids or checkpoint_digest in checkpoint_digests or supplied_descriptor in descriptor_digests:
            raise CheckpointRegistryError("duplicate checkpoint registry identity")
        ids.add(checkpoint_id)
        checkpoint_digests.add(checkpoint_digest)
        descriptor_digests.add(supplied_descriptor)
        seq = entry.get("through_event_seq")
        if not isinstance(seq, int) or seq <= prior_seq or seq > len(events):
            raise CheckpointRegistryError("checkpoint registry sequence must be strictly increasing and in-ledger")
        event = events[seq - 1]
        if event["event_id"] != entry.get("through_event_id"):
            raise CheckpointRegistryError("checkpoint registry event id mismatch")
        if event["this_event_digest"] != entry.get("through_event_digest"):
            raise CheckpointRegistryError("checkpoint registry event digest mismatch")
        if entry.get("projection_schema_version") != ledger.get("projection_schema_version"):
            raise CheckpointRegistryError("checkpoint descriptor projection schema mismatch")
        if entry.get("parent_checkpoint_digest") != prior_checkpoint_digest:
            raise CheckpointRegistryError("checkpoint parent chain mismatch")
        prior_seq = seq
        prior_checkpoint_digest = checkpoint_digest
    return {
        "status": "PASS",
        "checkpoint_count": len(entries),
        "latest_through_event_seq": prior_seq,
        "registry_digest": registry["registry_digest"],
        "authority_transfer": False,
    }


def cadence_decision(
    registry: Dict[str, Any],
    ledger: Dict[str, Any],
    policy: Dict[str, Any],
    *,
    boundary: Optional[str] = None,
    trigger: Optional[str] = None,
) -> Dict[str, Any]:
    verify_registry(registry, ledger, policy)
    target_events = gt.select(ledger, boundary)
    target_seq = len(target_events)
    if target_seq == 0:
        raise CheckpointRegistryError("cadence target resolves to no events")
    entries = registry["entries"]
    latest = entries[-1] if entries else None
    if latest and latest["through_event_seq"] == target_seq:
        return {
            "status": "NOT_DUE",
            "reason": "ALREADY_CHECKPOINTED",
            "target_event_seq": target_seq,
            "events_since_latest": 0,
            "authority_transfer": False,
        }
    if latest and latest["through_event_seq"] > target_seq:
        return {
            "status": "NOT_DUE",
            "reason": "TARGET_PREDATES_LATEST_REGISTERED",
            "target_event_seq": target_seq,
            "events_since_latest": target_seq - latest["through_event_seq"],
            "authority_transfer": False,
        }
    events_since = target_seq - (latest["through_event_seq"] if latest else 0)
    if not entries:
        reason = "GENESIS_NO_CHECKPOINT"
        due = True
    elif trigger and trigger in policy["milestone_triggers"]:
        reason = f"MILESTONE:{trigger}"
        due = True
    elif events_since >= policy["every_n_events"]:
        reason = "EVENT_INTERVAL"
        due = True
    else:
        reason = "CADENCE_NOT_REACHED"
        due = False
    return {
        "status": "DUE" if due else "NOT_DUE",
        "reason": reason,
        "target_event_seq": target_seq,
        "events_since_latest": events_since,
        "trigger": trigger,
        "policy_digest": policy["policy_digest"],
        "authority_transfer": False,
    }


def register_checkpoint(
    registry: Dict[str, Any],
    ledger: Dict[str, Any],
    policy: Dict[str, Any],
    checkpoint: Dict[str, Any],
    *,
    trigger: str,
    checkpoint_ref: Optional[str] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    verify_registry(registry, ledger, policy)
    cpr.verify_checkpoint(ledger, checkpoint)
    seq = checkpoint["through_event_seq"]
    same_seq = [e for e in registry["entries"] if e["through_event_seq"] == seq]
    if same_seq:
        existing = same_seq[0]
        if existing["checkpoint_digest"] != checkpoint["checkpoint_digest"]:
            raise CheckpointRegistryError("same checkpoint boundary has conflicting checkpoint digest")
        return copy.deepcopy(registry), {
            "status": "UNCHANGED_REPLAY",
            "checkpoint_id": existing["checkpoint_id"],
            "checkpoint_digest": existing["checkpoint_digest"],
            "authority_transfer": False,
        }
    if registry["entries"] and seq < registry["entries"][-1]["through_event_seq"]:
        raise CheckpointRegistryError("checkpoint registry is append-only by event sequence")
    parent = registry["entries"][-1]["checkpoint_digest"] if registry["entries"] else None
    descriptor = checkpoint_descriptor(
        checkpoint,
        trigger=trigger,
        policy=policy,
        checkpoint_ref=checkpoint_ref,
        parent_checkpoint_digest=parent,
    )
    out = copy.deepcopy(registry)
    out["entries"].append(descriptor)
    out = _seal_registry(out)
    verify_registry(out, ledger, policy)
    return out, {
        "status": "REGISTERED",
        "checkpoint_id": checkpoint["checkpoint_id"],
        "checkpoint_digest": checkpoint["checkpoint_digest"],
        "descriptor_digest": descriptor["descriptor_digest"],
        "parent_checkpoint_digest": parent,
        "authority_transfer": False,
    }


def select_checkpoint(
    registry: Dict[str, Any],
    ledger: Dict[str, Any],
    policy: Dict[str, Any],
    *,
    boundary: Optional[str] = None,
) -> Dict[str, Any]:
    verify_registry(registry, ledger, policy)
    target_events = gt.select(ledger, boundary)
    target_seq = len(target_events)
    compatible = [
        entry
        for entry in registry["entries"]
        if entry["through_event_seq"] <= target_seq
        and entry["projection_schema_version"] == ledger.get("projection_schema_version")
    ]
    if not compatible:
        return {
            "status": "GENESIS_REQUIRED",
            "target_event_seq": target_seq,
            "checkpoint": None,
            "authority_transfer": False,
        }
    selected = compatible[-1]
    return {
        "status": "CHECKPOINT_SELECTED",
        "target_event_seq": target_seq,
        "checkpoint": copy.deepcopy(selected),
        "tail_event_count": target_seq - selected["through_event_seq"],
        "authority_transfer": False,
    }


def _load(path: Path) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CheckpointRegistryError(f"{path}: top-level JSON must be an object")
    return value


def _dump(value: Dict[str, Any], out: Optional[Path] = None) -> None:
    text = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if out:
        out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("new")
    p.add_argument("ledger", type=Path)
    p.add_argument("--every-n-events", type=int, default=10)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("verify")
    p.add_argument("ledger", type=Path)
    p.add_argument("registry", type=Path)
    p.add_argument("policy", type=Path)
    p = sub.add_parser("select")
    p.add_argument("ledger", type=Path)
    p.add_argument("registry", type=Path)
    p.add_argument("policy", type=Path)
    p.add_argument("--as-of")
    args = parser.parse_args(argv)
    try:
        ledger = _load(args.ledger)
        if args.command == "new":
            policy = cadence_policy(args.every_n_events)
            registry = empty_registry(ledger, policy)
            _dump({"policy": policy, "registry": registry}, args.out)
            return 0
        registry = _load(args.registry)
        policy = _load(args.policy)
        if args.command == "verify":
            result = verify_registry(registry, ledger, policy)
        else:
            result = select_checkpoint(registry, ledger, policy, boundary=args.as_of)
        _dump(result)
        return 0 if result.get("status") in {"PASS", "CHECKPOINT_SELECTED", "GENESIS_REQUIRED"} else 2
    except (OSError, ValueError, KeyError, CheckpointRegistryError, gt.GoldenThreadError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
