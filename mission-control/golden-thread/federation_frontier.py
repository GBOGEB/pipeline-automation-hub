#!/usr/bin/env python3
"""Fleet-only Golden Thread controls.

These controls are deliberately orthogonal to repo-local QPS GT_BDQ sequencing.
They provide deterministic federation utilities for occurrence import/idempotency,
downstream invalidation, latched gate semantics, reflexive DAG validation and
checkpoint operating-policy decisions. They do not transfer engineering authority.
"""
from __future__ import annotations

import copy
import hashlib
import json
from collections import deque


class FederationFrontierError(ValueError):
    pass


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _required(record, key):
    if key not in record:
        raise FederationFrontierError(f"missing required field: {key}")
    return record[key]


def occurrence_identity(record):
    """Return deterministic source identity + idempotency key for a GitHub occurrence."""
    source = {
        "repository": _required(record, "repository"),
        "object_type": _required(record, "object_type"),
        "object_number": _required(record, "object_number"),
        "anchor_sha": _required(record, "anchor_sha"),
        "source_ref": _required(record, "source_ref"),
    }
    payload = copy.deepcopy(record.get("payload") or {})
    payload_digest = digest(payload)
    idempotency_key = digest({"source": source, "payload_digest": payload_digest})
    return source, payload_digest, idempotency_key


def import_occurrences(records, existing=None):
    """Deterministically import captured GitHub occurrences.

    Repeating the same record produces no duplicate obligation. Reusing an
    idempotency key with incompatible content fails closed.
    """
    index = copy.deepcopy(existing or {})
    imported = []
    duplicates = []
    for raw in records:
        source, payload_digest, key = occurrence_identity(raw)
        occurrence = {
            "idempotency_key": key,
            "source": source,
            "payload_digest": payload_digest,
            "payload": copy.deepcopy(raw.get("payload") or {}),
            "authority_transfer": False,
        }
        if key in index:
            if index[key] != occurrence:
                raise FederationFrontierError(f"idempotency conflict: {key}")
            duplicates.append(key)
            continue
        index[key] = occurrence
        imported.append(key)
    ordered = {k: index[k] for k in sorted(index)}
    return {
        "schema": "missioncontrol.golden_thread_occurrence_import.v1",
        "authority_transfer": False,
        "imported_count": len(imported),
        "duplicate_count": len(duplicates),
        "occurrence_count": len(ordered),
        "imported_keys": sorted(imported),
        "duplicate_keys": sorted(duplicates),
        "occurrences": ordered,
        "projection_digest": digest(ordered),
    }


INVALIDATION_SCOPES = {"NODE", "DMAIC_CLUSTER", "DESCENDANT_CONE", "RENDITION_ONLY", "FULL_REPLAY"}


def _descendants(edges, roots):
    children = {}
    for parent, child in edges:
        if parent == child:
            continue
        children.setdefault(parent, set()).add(child)
    seen = set(roots)
    queue = deque(roots)
    while queue:
        node = queue.popleft()
        for child in sorted(children.get(node, ())):
            if child not in seen:
                seen.add(child)
                queue.append(child)
    return seen


def build_invalidation_receipt(nodes, edges, roots, scope, clusters=None, renditions=None, trigger=None):
    """Build a deterministic invalidation plan without mutating source authority."""
    nodes = sorted(set(nodes))
    roots = sorted(set(roots))
    if scope not in INVALIDATION_SCOPES:
        raise FederationFrontierError(f"unsupported invalidation scope: {scope}")
    unknown = sorted(set(roots) - set(nodes))
    if unknown:
        raise FederationFrontierError(f"unknown invalidation roots: {unknown}")
    clusters = clusters or {}
    renditions = renditions or {}

    if scope == "NODE":
        affected = set(roots)
    elif scope == "DESCENDANT_CONE":
        affected = _descendants(edges, roots)
    elif scope == "DMAIC_CLUSTER":
        target_clusters = {clusters.get(root) for root in roots}
        target_clusters.discard(None)
        affected = {n for n in nodes if clusters.get(n) in target_clusters}
        affected.update(roots)
    elif scope == "FULL_REPLAY":
        affected = set(nodes)
    else:  # RENDITION_ONLY
        affected = set()

    affected_renditions = sorted({r for n in (affected or set(roots)) for r in renditions.get(n, [])})
    base = {
        "schema": "missioncontrol.golden_thread_invalidation.v1",
        "scope": scope,
        "trigger": copy.deepcopy(trigger or {}),
        "root_nodes": roots,
        "affected_nodes": sorted(affected),
        "affected_renditions": affected_renditions,
        "non_compensating_gates_preserved": True,
        "authority_transfer": False,
    }
    base["invalidation_digest"] = digest(base)
    return base


def close_invalidation(receipt, recomputed_nodes=None, regenerated_renditions=None):
    recomputed_nodes = set(recomputed_nodes or [])
    regenerated_renditions = set(regenerated_renditions or [])
    expected_nodes = set(receipt.get("affected_nodes") or [])
    expected_renditions = set(receipt.get("affected_renditions") or [])
    stale_nodes = sorted(expected_nodes - recomputed_nodes)
    stale_renditions = sorted(expected_renditions - regenerated_renditions)
    closure = {
        "schema": "missioncontrol.golden_thread_invalidation_closure.v1",
        "invalidation_digest": receipt["invalidation_digest"],
        "expected_affected_count": len(expected_nodes),
        "recomputed_count": len(expected_nodes & recomputed_nodes),
        "stale_survivor_count": len(stale_nodes),
        "stale_survivors": stale_nodes,
        "expected_rendition_count": len(expected_renditions),
        "regenerated_rendition_count": len(expected_renditions & regenerated_renditions),
        "stale_rendition_count": len(stale_renditions),
        "stale_renditions": stale_renditions,
        "non_compensating_gates_preserved": receipt.get("non_compensating_gates_preserved") is True,
        "authority_transfer": False,
    }
    closure["status"] = "PASS" if not stale_nodes and not stale_renditions and closure["non_compensating_gates_preserved"] else "WITHHELD"
    closure["closure_digest"] = digest(closure)
    return closure


def new_gate(required_children):
    children = sorted(set(required_children))
    if not children:
        raise FederationFrontierError("gate requires at least one child")
    return {
        "schema": "missioncontrol.golden_thread_gate_state.v1",
        "required_children": children,
        "child_permissives": {child: False for child in children},
        "latched_inhibit": False,
        "inhibit_sources": [],
        "gate_open": False,
        "reset_counter": 0,
        "authority_transfer": False,
    }


def apply_gate_event(state, event):
    """Apply bottom-up permissive / latching-inhibit semantics.

    INHIBIT latches until an explicitly authorized RESET. RESET deliberately
    clears child permissives so the gate cannot silently reopen.
    """
    s = copy.deepcopy(state)
    kind = _required(event, "type")
    child = event.get("child")
    if kind in {"PERMISSIVE", "INHIBIT"} and child not in s["child_permissives"]:
        raise FederationFrontierError(f"unknown gate child: {child}")

    if kind == "PERMISSIVE":
        s["child_permissives"][child] = True
    elif kind == "INHIBIT":
        s["latched_inhibit"] = True
        if child not in s["inhibit_sources"]:
            s["inhibit_sources"].append(child)
    elif kind == "RESET":
        if event.get("authorized") is not True:
            raise FederationFrontierError("gate reset requires authorized=true")
        if not event.get("reason"):
            raise FederationFrontierError("gate reset requires reason")
        s["latched_inhibit"] = False
        s["inhibit_sources"] = []
        s["child_permissives"] = {child: False for child in s["required_children"]}
        s["reset_counter"] += 1
    else:
        raise FederationFrontierError(f"unsupported gate event: {kind}")

    s["gate_open"] = (not s["latched_inhibit"]) and all(s["child_permissives"].values())
    s["state_digest"] = digest({k: v for k, v in s.items() if k != "state_digest"})
    return s


def validate_reflexive_resequence(nodes, edges, reflexive_nodes, proposed_order):
    """Validate a topological resequence while permitting declared self-reflexive nodes."""
    nodes = sorted(set(nodes))
    reflexive_nodes = set(reflexive_nodes)
    order = list(proposed_order)
    if len(order) != len(set(order)) or set(order) != set(nodes):
        raise FederationFrontierError("proposed order must contain every node exactly once")
    position = {node: i for i, node in enumerate(order)}
    normalized_edges = []
    for parent, child in edges:
        if parent not in position or child not in position:
            raise FederationFrontierError(f"edge references unknown node: {(parent, child)}")
        if parent == child:
            if parent not in reflexive_nodes:
                raise FederationFrontierError(f"undeclared reflexive edge: {parent}")
        elif position[parent] >= position[child]:
            raise FederationFrontierError(f"dependency order violation: {parent}->{child}")
        normalized_edges.append((parent, child))
    semantic_graph = {
        "nodes": nodes,
        "edges": sorted(set(normalized_edges)),
        "reflexive_nodes": sorted(reflexive_nodes),
    }
    return {
        "status": "PASS",
        "proposed_order": order,
        "semantic_graph_digest": digest(semantic_graph),
        "authority_transfer": False,
    }


def checkpoint_decision(metrics, policy):
    """Return a deterministic fleet checkpoint recommendation without truncating history."""
    triggers = []
    if metrics.get("events_since_checkpoint", 0) >= policy.get("max_events_since_checkpoint", 10**18):
        triggers.append("EVENT_COUNT")
    if metrics.get("replay_cost_ms", 0) >= policy.get("max_replay_cost_ms", 10**18):
        triggers.append("REPLAY_COST")
    if metrics.get("hours_since_checkpoint", 0) >= policy.get("max_hours_since_checkpoint", 10**18):
        triggers.append("AGE")
    if metrics.get("ledger_bytes", 0) >= policy.get("hot_tier_max_bytes", 10**18):
        triggers.append("STORAGE_TIER")
    decision = {
        "schema": "missioncontrol.golden_thread_checkpoint_policy.v1",
        "create_checkpoint": bool(triggers),
        "triggers": sorted(triggers),
        "history_truncation_allowed": False,
        "checkpoint_is_authority": False,
        "authority_transfer": False,
        "metrics": copy.deepcopy(metrics),
        "policy": copy.deepcopy(policy),
    }
    decision["decision_digest"] = digest(decision)
    return decision
