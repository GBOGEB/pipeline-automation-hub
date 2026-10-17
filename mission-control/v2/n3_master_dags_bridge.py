"""Read-only projection over existing governed graph registries.

A compatible 'MASTER_DAGS' path has not been independently located. This
module does not define one, merge source authorities, or authenticate receipts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import deque
from pathlib import Path

SHA40 = re.compile(r"[0-9a-f]{40}\Z")
GRAPH_ID = re.compile(r"[A-Z][A-Z0-9_]*\Z")
SOURCE_PATHS = {
    "GBOGEB/ABACUS": "triage/GRAPH_REGISTRY.yaml",
    "GBOGEB/CODEX": "triage/GRAPH_REGISTRY.yaml",
    "GBOGEB/pipeline-automation-hub":
        "mission-control/federation-atlas/CODE_PURPLE_BEAMS_DAG_v1.json",
    "GBOGEB/cryoplant-project": "federation/acceptance_dashboard/dag.json",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _sha(value: object) -> bool:
    return isinstance(value, str) and SHA40.fullmatch(value) is not None


def _digest(value: object) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _order(nodes: set[str], edges: list[tuple[str, str]]) -> list[str]:
    outgoing = {name: set() for name in nodes}
    degree = {name: 0 for name in nodes}
    for src, dst in edges:
        _require(src in nodes and dst in nodes, "unregistered graph endpoint")
        _require(src != dst, "self-cycle in execution graph")
        if dst not in outgoing[src]:
            outgoing[src].add(dst)
            degree[dst] += 1
    ready = deque(sorted(key for key, count in degree.items() if count == 0))
    output = []
    while ready:
        node = ready.popleft()
        output.append(node)
        for nxt in sorted(outgoing[node]):
            degree[nxt] -= 1
            if degree[nxt] == 0:
                ready.append(nxt)
    _require(len(output) == len(nodes), "execution graph is cyclic")
    return output


def project(manifest: dict, *, expected_hub_base: str | None = None) -> dict:
    """Validate and project source-declared graph identities, without promotion.

    Source blob hashes are externally fetched declarations. Their existence and
    content MUST be independently read back by an authorized source connector.
    Cross-repository links remain DECLARED; these are not authenticated jobs.
    """
    _require(isinstance(manifest, dict), "object manifest required")
    _require(manifest.get("schema") == "code-purple.g3a.master-dags-compat.v1",
             "incompatible contract")
    _require(manifest.get("authority_transfer") is False and
             manifest.get("merge_admission") == "HOLD" and
             manifest.get("accepted_n_delta") is None, "authority escalation")
    _require(manifest.get("canonical_master_dags_path") is None,
             "unverified MASTER_DAGS must remain UNKNOWN")
    hub_base = manifest.get("hub_base_sha")
    _require(_sha(hub_base), "invalid hub base SHA")
    if expected_hub_base is not None:
        _require(_sha(expected_hub_base) and expected_hub_base == hub_base,
                 "stale hub base SHA")
    sources = manifest.get("sources")
    _require(isinstance(sources, list) and len(sources) == len(SOURCE_PATHS),
             "all four source registries required")
    seen_repos, nodes, all_nodes = set(), [], set()
    for entry in sources:
        _require(isinstance(entry, dict), "malformed source registry entry")
        repo = entry.get("repository")
        _require(isinstance(repo, str) and repo in SOURCE_PATHS and
                 repo not in seen_repos, "invalid/duplicate source repository")
        seen_repos.add(repo)
        _require(entry.get("path") == SOURCE_PATHS[repo],
                 "unregistered source path")
        _require(_sha(entry.get("commit_sha")) and _sha(entry.get("blob_sha")),
                 "unverified source SHA declaration")
        ids = entry.get("graph_ids")
        _require(isinstance(ids, list) and bool(ids), "missing graph IDs")
        _require(all(isinstance(x, str) and GRAPH_ID.fullmatch(x) for x in ids),
                 "malformed graph ID")
        _require(len(ids) == len(set(ids)), "duplicate graph ID in registry")
        for graph_id in ids:
            node_id = f"{repo}::{graph_id}"
            _require(node_id not in all_nodes, "duplicate namespaced graph")
            all_nodes.add(node_id)
            nodes.append({"id": node_id, "repository": repo,
                          "graph_id": graph_id, "path": entry["path"],
                          "source_sha": entry["commit_sha"],
                          "source_blob_sha": entry["blob_sha"],
                          "binding": "DECLARED_SOURCE_REFERENCE"})
    _require(seen_repos == set(SOURCE_PATHS), "registry population mismatch")
    links = manifest.get("links")
    _require(isinstance(links, list), "edge list required")
    seen_edges, edges, pairs = set(), [], []
    for entry in links:
        _require(isinstance(entry, dict), "malformed graph edge")
        start, end = entry.get("from"), entry.get("to")
        _require(isinstance(start, str) and isinstance(end, str) and
                 start in all_nodes and end in all_nodes,
                 "unregistered graph endpoint")
        _require(entry.get("binding") == "DECLARED" and
                 entry.get("receipt") is None, "unverified receipt promotion")
        _require(entry.get("kind") == "FEDERATION_CANDIDATE",
                 "unrecognized edge semantics")
        _require(start.split("::")[0] != end.split("::")[0],
                 "candidate link must cross repository boundary")
        pair = (start, end)
        _require(pair not in seen_edges, "duplicate candidate edge")
        seen_edges.add(pair)
        pairs.append(pair)
        edges.append({"from": start, "to": end,
                      "kind": "FEDERATION_CANDIDATE",
                      "binding": "DECLARED", "receipt": None,
                      "accepted": False})
    order = _order(all_nodes, pairs)
    _require(manifest.get("native_receipt") is None, "unverified native receipt")
    _require(manifest.get("authenticated_crew_ids") is None,
             "unverified crew identity")
    _require(manifest.get("root_closures") is None,
             "unverified causal root closure")
    return {
        "schema": "code-purple.g3a.master-dags-projection.v1",
        "source_digest_sha256": _digest(manifest),
        "hub_base_sha": hub_base,
        "canonical_master_dags_path": None,
        "nodes": sorted(nodes, key=lambda row: row["id"]),
        "edges": sorted(edges, key=lambda row: (row["from"], row["to"])),
        "topological_order": order,
        "metrics": {"sources": len(sources), "graph_families": len(nodes),
                    "declared_cross_repository_edges": len(edges),
                    "native_verified_edges": None,
                    "accepted_coverage_delta": None,
                    "queue_p95_ms": None,
                    "formal_root_closures": None},
        "merge_admission": "HOLD", "accepted_n_delta": None,
        "authority_transfer": False,
        "evidence_class": "SOURCE_REFERENCE_DECLARED_NOT_NATIVE_AUTHENTICATED",
        "scope_notice": "Read-only candidate projection; not a master graph SSOT",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--expected-hub-base")
    args = ap.parse_args()
    src = json.loads(args.manifest.read_text(encoding="utf-8"))
    result = project(src, expected_hub_base=args.expected_hub_base)
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(payload, encoding="utf-8")


if __name__ == "__main__":
    main()
