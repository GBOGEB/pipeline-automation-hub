"""Deterministic Kahn projection for LSAF semantic nodes.

This is not a replacement for the Hub CI/CD DAG metric owner. It projects LSAF
session/fragment dependencies only. Cross-system metric facts should be supplied by
canonical providers named in lsaf/assimilation/canonical_owners.yaml.
"""
from __future__ import annotations

import heapq
from typing import Any

UNKNOWN = "UNKNOWN"


def compile_dag(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    """Compile a stable READY/BLOCKED/CYCLE projection.

    Node contract:
      id: unique string
      requires: list[node id]
      authority: truthy string or UNKNOWN/None
      evidence: truthy value or UNKNOWN/None

    Missing requirements are BLOCKED, not cycles. Nodes missing authority/evidence
    are classified separately and do not enter READY.
    """
    by_id: dict[str, dict[str, Any]] = {}
    for raw in nodes:
        node_id = str(raw["id"])
        if node_id in by_id:
            raise ValueError(f"duplicate node id: {node_id}")
        by_id[node_id] = dict(raw)

    ids = sorted(by_id)
    requires = {n: sorted(set(str(x) for x in (by_id[n].get("requires") or []))) for n in ids}
    missing_requirements = {
        n: sorted(r for r in requires[n] if r not in by_id)
        for n in ids
        if any(r not in by_id for r in requires[n])
    }
    missing_authority = sorted(
        n for n in ids if by_id[n].get("authority") in (None, "", UNKNOWN)
    )
    missing_evidence = sorted(
        n for n in ids if by_id[n].get("evidence") in (None, "", False, UNKNOWN)
    )

    eligible = set(ids) - set(missing_requirements) - set(missing_authority) - set(missing_evidence)
    indegree = {n: 0 for n in eligible}
    outgoing = {n: [] for n in eligible}
    edges: list[tuple[str, str]] = []

    for n in sorted(eligible):
        for dep in requires[n]:
            edges.append((dep, n))
            if dep in eligible:
                indegree[n] += 1
                outgoing[dep].append(n)
            elif dep in by_id:
                # Dependency exists but is not executable because it is itself missing
                # authority/evidence/requirements. Keep this node blocked rather than
                # accidentally making it READY.
                indegree[n] += 1

    ready_heap = [n for n, degree in indegree.items() if degree == 0]
    heapq.heapify(ready_heap)
    order: list[str] = []
    initially_ready = sorted(ready_heap)

    while ready_heap:
        n = heapq.heappop(ready_heap)
        order.append(n)
        for nxt in sorted(outgoing[n]):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                heapq.heappush(ready_heap, nxt)

    remaining = sorted(n for n in eligible if n not in set(order))
    blocked_by_nonexecutable = sorted(
        n for n in remaining
        if any(dep in by_id and dep not in eligible for dep in requires[n])
    )
    cycle = sorted(set(remaining) - set(blocked_by_nonexecutable))

    blocked = sorted(
        set(missing_requirements)
        | set(missing_authority)
        | set(missing_evidence)
        | set(blocked_by_nonexecutable)
        | set(cycle)
    )

    return {
        "schema": "lsaf/dag-projection/v0.1",
        "nodes": ids,
        "edges": [{"from": a, "to": b} for a, b in sorted(edges)],
        "ready": initially_ready,
        "order": order,
        "blocked": blocked,
        "cycle": cycle,
        "missing_authority": missing_authority,
        "missing_evidence": missing_evidence,
        "missing_requirements": {k: missing_requirements[k] for k in sorted(missing_requirements)},
    }
