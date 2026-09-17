#!/usr/bin/env python3
"""Golden Thread external side-effect idempotency registry.

This module governs external writes (GitHub comments/issues/PRs, child writes,
CI dispatches, publication actions) as explicit transactions. It does not
perform the side effect. It decides whether an intent is NEW or an exact REPLAY
and binds the completed action to an immutable external receipt.

Identical governed intent => same transaction_id => do not re-emit.
Changed source state or payload => new transaction_id => explicit lineage edge.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REGISTRY_SCHEMA = "missioncontrol.golden_thread_side_effect_registry.v1"
RECEIPT_SCHEMA = "missioncontrol.golden_thread_side_effect_receipt.v1"
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$", re.I)
ALLOWED_STATUS = {"PLANNED", "COMPLETED", "FAILED", "DEFERRED"}


class SideEffectError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_json(path: Path) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SideEffectError(f"{path}: top-level JSON must be an object")
    return value


def empty_registry() -> Dict[str, Any]:
    return {
        "schema": REGISTRY_SCHEMA,
        "authority_transfer": False,
        "transactions": {},
        "obligation_heads": {},
    }


def _require_string(parent: Dict[str, Any], key: str) -> str:
    value = parent.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SideEffectError(f"missing/invalid {key}")
    return value.strip()


def _require_digest(parent: Dict[str, Any], key: str) -> str:
    value = _require_string(parent, key)
    if not DIGEST_RE.fullmatch(value):
        raise SideEffectError(f"{key} must be sha256:<64 hex>")
    return value.lower()


def canonical_intent(intent: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(intent, dict):
        raise SideEffectError("intent must be an object")
    value = {
        "authority_domain": _require_string(intent, "authority_domain"),
        "action": _require_string(intent, "action"),
        "target": _require_string(intent, "target"),
        "mechanism": _require_string(intent, "mechanism"),
        "source_state_digest": _require_digest(intent, "source_state_digest"),
        "payload_digest": _require_digest(intent, "payload_digest"),
        "schema_version": _require_string(intent, "schema_version"),
    }
    if "expected_semantic_delta" in intent:
        value["expected_semantic_delta"] = intent["expected_semantic_delta"]
    return value


def obligation_identity(intent: Dict[str, Any]) -> Dict[str, Any]:
    c = canonical_intent(intent)
    return {
        "authority_domain": c["authority_domain"],
        "action": c["action"],
        "target": c["target"],
        "mechanism": c["mechanism"],
        "schema_version": c["schema_version"],
    }


def transaction_id(intent: Dict[str, Any]) -> str:
    return digest({"side_effect_intent": canonical_intent(intent)})


def obligation_id(intent: Dict[str, Any]) -> str:
    return digest({"side_effect_obligation": obligation_identity(intent)})


def _validate_registry(registry: Dict[str, Any]) -> None:
    if registry.get("schema") != REGISTRY_SCHEMA:
        raise SideEffectError("registry schema mismatch")
    if registry.get("authority_transfer") is not False:
        raise SideEffectError("registry authority_transfer must remain false")
    if not isinstance(registry.get("transactions"), dict):
        raise SideEffectError("transactions must be an object")
    if not isinstance(registry.get("obligation_heads"), dict):
        raise SideEffectError("obligation_heads must be an object")


def plan(registry: Dict[str, Any], intent: Dict[str, Any]) -> Dict[str, Any]:
    """Return a deterministic execution decision for an external side effect."""
    _validate_registry(registry)
    c = canonical_intent(intent)
    tx_id = transaction_id(c)
    obl_id = obligation_id(c)
    existing = registry["transactions"].get(tx_id)

    if existing is not None:
        if existing.get("intent") != c:
            raise SideEffectError("transaction hash collision or registry corruption")
        return {
            "schema": "missioncontrol.golden_thread_side_effect_plan.v1",
            "decision": "REPLAY_EXISTING",
            "emit_side_effect": False,
            "transaction_id": tx_id,
            "obligation_id": obl_id,
            "status": existing.get("status"),
            "receipt": copy.deepcopy(existing.get("receipt")),
            "authority_transfer": False,
        }

    parent = registry["obligation_heads"].get(obl_id)
    return {
        "schema": "missioncontrol.golden_thread_side_effect_plan.v1",
        "decision": "NEW_TRANSACTION",
        "emit_side_effect": True,
        "transaction_id": tx_id,
        "obligation_id": obl_id,
        "parent_transaction_id": parent,
        "changed_from_parent": parent is not None,
        "authority_transfer": False,
    }


def register_planned(registry: Dict[str, Any], intent: Dict[str, Any]) -> Dict[str, Any]:
    _validate_registry(registry)
    decision = plan(registry, intent)
    if decision["decision"] == "REPLAY_EXISTING":
        return copy.deepcopy(registry)

    c = canonical_intent(intent)
    tx_id = decision["transaction_id"]
    obl_id = decision["obligation_id"]
    parent = decision["parent_transaction_id"]
    out = copy.deepcopy(registry)
    out["transactions"][tx_id] = {
        "transaction_id": tx_id,
        "obligation_id": obl_id,
        "parent_transaction_id": parent,
        "intent": c,
        "status": "PLANNED",
        "receipt": None,
    }
    out["obligation_heads"][obl_id] = tx_id
    return out


def bind_receipt(
    registry: Dict[str, Any],
    tx_id: str,
    *,
    provider: str,
    external_ref: str,
    observed_result_digest: str,
    status: str = "COMPLETED",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    _validate_registry(registry)
    if tx_id not in registry["transactions"]:
        raise SideEffectError(f"unknown transaction_id {tx_id}")
    if status not in ALLOWED_STATUS:
        raise SideEffectError(f"unsupported status {status}")
    if not DIGEST_RE.fullmatch(observed_result_digest):
        raise SideEffectError("observed_result_digest must be sha256:<64 hex>")

    out = copy.deepcopy(registry)
    tx = out["transactions"][tx_id]
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "transaction_id": tx_id,
        "provider": provider,
        "external_ref": external_ref,
        "observed_result_digest": observed_result_digest.lower(),
        "intent_digest": digest(tx["intent"]),
        "authority_transfer": False,
    }
    if metadata:
        receipt["metadata"] = copy.deepcopy(metadata)
    receipt["receipt_digest"] = digest(receipt)

    prior = tx.get("receipt")
    if prior is not None and prior != receipt:
        raise SideEffectError("attempt to replace an immutable external receipt")

    tx["status"] = status
    tx["receipt"] = receipt
    return out


def verify_registry(registry: Dict[str, Any]) -> Dict[str, Any]:
    _validate_registry(registry)
    completed = 0
    lineage_edges = 0
    for tx_id, tx in registry["transactions"].items():
        if tx.get("transaction_id") != tx_id:
            raise SideEffectError(f"transaction key mismatch {tx_id}")
        if transaction_id(tx.get("intent") or {}) != tx_id:
            raise SideEffectError(f"transaction identity mismatch {tx_id}")
        if obligation_id(tx["intent"]) != tx.get("obligation_id"):
            raise SideEffectError(f"obligation identity mismatch {tx_id}")
        if tx.get("parent_transaction_id"):
            parent = tx["parent_transaction_id"]
            if parent not in registry["transactions"]:
                raise SideEffectError(f"missing parent transaction {parent}")
            if registry["transactions"][parent]["obligation_id"] != tx["obligation_id"]:
                raise SideEffectError(f"cross-obligation parent edge {tx_id}")
            lineage_edges += 1
        if tx.get("status") not in ALLOWED_STATUS:
            raise SideEffectError(f"bad transaction status {tx_id}")
        receipt = tx.get("receipt")
        if receipt is not None:
            if receipt.get("transaction_id") != tx_id:
                raise SideEffectError(f"receipt transaction mismatch {tx_id}")
            expected = copy.deepcopy(receipt)
            claimed = expected.pop("receipt_digest", None)
            if claimed != digest(expected):
                raise SideEffectError(f"receipt digest mismatch {tx_id}")
            if receipt.get("authority_transfer") is not False:
                raise SideEffectError(f"receipt authority transfer {tx_id}")
            completed += 1

    for obl_id, head in registry["obligation_heads"].items():
        if head not in registry["transactions"]:
            raise SideEffectError(f"obligation head missing transaction {obl_id}")
        if registry["transactions"][head]["obligation_id"] != obl_id:
            raise SideEffectError(f"obligation head mismatch {obl_id}")

    return {
        "schema": "missioncontrol.golden_thread_side_effect_registry_verification.v1",
        "status": "PASS",
        "transaction_count": len(registry["transactions"]),
        "completed_receipt_count": completed,
        "lineage_edge_count": lineage_edges,
        "registry_digest": digest(registry),
        "authority_transfer": False,
    }


def dump_json(value: Dict[str, Any], out: Optional[Path]) -> None:
    rendered = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("plan")
    p.add_argument("registry", type=Path)
    p.add_argument("intent", type=Path)

    p = sub.add_parser("register")
    p.add_argument("registry", type=Path)
    p.add_argument("intent", type=Path)
    p.add_argument("--out", type=Path, required=True)

    p = sub.add_parser("verify")
    p.add_argument("registry", type=Path)

    args = parser.parse_args(argv)
    try:
        registry = load_json(args.registry)
        if args.command == "plan":
            dump_json(plan(registry, load_json(args.intent)), None)
        elif args.command == "register":
            dump_json(register_planned(registry, load_json(args.intent)), args.out)
        else:
            dump_json(verify_registry(registry), None)
        return 0
    except SideEffectError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
