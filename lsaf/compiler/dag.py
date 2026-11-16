"""Deterministic Kahn projection for LSAF semantic nodes.

This is not a replacement for the Hub CI/CD DAG metric owner. It projects LSAF
session/fragment dependencies only. Cross-system metric facts should be supplied by
canonical providers named in lsaf/assimilation/canonical_owners.yaml.
"""
from __future__ import annotations

import heapq
from collections import defaultdict, deque
from typing import Any

UNKNOWN = "UNKNOWN"
EXECUTABLE_EVIDENCE = {"SOURCE", "DERIVED"}


def compile_dag(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    """Compile a stable READY/BLOCKED/CYCLE projection.

    Node contract:
      id: unique string
      requires: list[node id]
      authority: truthy string or UNKNOWN/None
      evidence: SOURCE or DERIVED to be executable; all other classes fail closed

    Missing requirements are BLOCKED, not cycles. Nodes missing authority/evidence
    are classified separately and do not enter READY. Any node depending directly
    or transitively on a blocked node is also BLOCKED. Only the remaining executable
    subgraph participates in cycle detection.
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
        n for n in ids if by_id[n].get("evidence") not in EXECUTABLE_EVIDENCE
    )

    direct_blocked = (
        set(missing_requirements)
        | set(missing_authority)
        | set(missing_evidence)
    )

    dependents: dict[str, list[str]] = defaultdict(list)
    edges: list[tuple[str, str]] = []
    for n in ids:
        for dep in requires[n]:
            if dep in by_id:
                dependents[dep].append(n)
                edges.append((dep, n))

    # Propagate non-executable status through the dependency graph. This prevents
    # an acyclic A(blocked)->B->C chain from being misreported as a cycle.
    blocked = set(direct_blocked)
    q = deque(sorted(direct_blocked))
    while q:
        source = q.popleft()
        for child in sorted(dependents.get(source, [])):
            if child not in blocked:
                blocked.add(child)
                q.append(child)

    executable = sorted(set(ids) - blocked)
    executable_set = set(executable)
    indegree = {n: 0 for n in executable}
    outgoing = {n: [] for n in executable}
    for n in executable:
        for dep in requires[n]:
            if dep in executable_set:
                indegree[n] += 1
                outgoing[dep].append(n)

    ready_heap = [n for n, degree in indegree.items() if degree == 0]
    heapq.heapify(ready_heap)
    initially_ready = sorted(ready_heap)
    order: list[str] = []

    while ready_heap:
        n = heapq.heappop(ready_heap)
        order.append(n)
        for nxt in sorted(outgoing[n]):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                heapq.heappush(ready_heap, nxt)

    cycle = sorted(set(executable) - set(order))
    blocked |= set(cycle)

    return {
        "schema": "lsaf/dag-projection/v0.1",
        "nodes": ids,
        "edges": [{"from": a, "to": b} for a, b in sorted(edges)],
        "ready": initially_ready,
        "order": order,
        "blocked": sorted(blocked),
        "cycle": cycle,
        "missing_authority": missing_authority,
        "missing_evidence": missing_evidence,
        "missing_requirements": {k: missing_requirements[k] for k in sorted(missing_requirements)},
    }
