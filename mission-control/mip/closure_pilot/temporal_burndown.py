#!/usr/bin/env python3
"""Read-only temporal MIP burndown overlay for the existing closure pilot.

A handover-derived DAG is a secondary witness, NOT promotion of the frozen SSOT.
No API calls, workflow dispatch, Git writes, admission, or scaling actions.
"""
from __future__ import annotations
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from closure_census import CensusError, kahn_layers, path_overlap, validate_lane_path

SCHEMA = "mip.temporal-burndown.v1"
SHA = re.compile(r"^[0-9a-f]{40}$")
WEIGHTS = {
    "P0-Q1": 5, "P0-Q2": 5, "P0-N6": 5, "P0-G1": 5,
    "P0-A1": 5, "P0-A2": 5, "P0-A3": 5, "P0-J1": 5,
    "P0-C1": 5, "P1-I1": 3, "P1-I2": 3, "P1-S1": 3,
    "P1-N1": 3, "P1-M1": 3, "P1-R1": 3, "P2-D1": 1,
    "P2-U1": 1,
}
PARENTS = {
    "P0-Q1": [], "P0-Q2": ["P0-Q1"], "P0-N6": ["P0-Q1"],
    "P0-G1": ["P0-N6"], "P0-A1": [], "P0-A2": [],
    "P0-A3": ["P0-A1"], "P0-J1": [], "P0-C1": ["P0-G1"],
    "P1-I1": ["P0-G1"], "P1-I2": ["P1-I1"],
    "P1-S1": ["P0-Q2"], "P1-N1": ["P0-J1"],
    "P1-M1": ["P1-I2"],
    "P1-R1": ["P0-A1", "P0-A2", "P0-J1", "P1-I2"],
    "P2-D1": ["P1-R1"], "P2-U1": ["P1-I2"],
}

def need(ok: bool, why: str) -> None:
    if not ok:
        raise CensusError(why)

def path_conflict(left: str, right: str) -> bool:
    """Use the closure census's single lane ownership contract."""
    return path_overlap(left, right)

def lane_collisions(manifest: dict[str, Any]) -> list[dict[str, str]]:
    owners = {o["id"]: o["repo"] for o in manifest["owners"]}
    lanes = manifest["lanes"]
    for lane in lanes:
        need(lane["owner"] in owners, "unbound lane owner")
        need(isinstance(lane["paths"], list) and bool(lane["paths"]), "lane without owned files")
        for path in lane["paths"]:
            validate_lane_path(path)
    conflicts = []
    for i, left in enumerate(lanes):
        for right in lanes[i + 1:]:
            need(left["owner"] in owners and right["owner"] in owners,
                 "unbound lane owner")
            if owners[left["owner"]] != owners[right["owner"]]:
                continue
            for a in left["paths"]:
                for b in right["paths"]:
                    if path_conflict(a, b):
                        conflicts.append({"lanes": f"{left['id']}:{right['id']}",
                                          "paths": f"{a} | {b}"})
    return conflicts

def review(doc: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    need(doc.get("schema") == SCHEMA, "wrong temporal schema")
    need(doc.get("authority") == "READ_ONLY_NOT_ADMISSION", "authority escalation")
    need(doc.get("topology_source_class") == "HANDOVER_TEXT_WITNESS",
         "frozen original not directly verified")
    need(doc.get("original_frozen_sha_verified") is False,
         "unsupported original hash verification")
    need(doc.get("certificates") == [], "unverified admission certificates")
    need(manifest.get("authority") == "DRAFT_NOT_ADMISSION", "pilot authority changed")
    need(sum(WEIGHTS.values()) == 65 and len(WEIGHTS) == 17,
         "frozen weight invariant")
    edges = [{"from": p, "to": child}
             for child, parents in PARENTS.items() for p in parents]
    need(len(edges) == 16 and len({(e["from"], e["to"]) for e in edges}) == 16,
         "handover edge-count invariant")
    layers = kahn_layers(list(WEIGHTS), edges)
    distances = {root: 0 for root in WEIGHTS}
    descendants = {root: set() for root in WEIGHTS}
    for layer in layers:
        for root in layer:
            for edge in edges:
                if edge["from"] == root:
                    child = edge["to"]
                    distances[child] = max(distances[child], distances[root] + 1)
    for root in WEIGHTS:
        frontier = [root]
        while frontier:
            node = frontier.pop()
            for edge in edges:
                child = edge["to"]
                if edge["from"] == node and child not in descendants[root]:
                    descendants[root].add(child)
                    frontier.append(child)
    need(max(distances.values()) == 6, "critical chain drift")
    owners = {o["id"]: o["head"] for o in manifest["owners"]}
    observed = doc["owner_heads"]
    need(len(observed) == len(owners) == len(set(observed)),
         "owner census must be complete and unique")
    drift = []
    for owner, head in observed.items():
        need(owner in owners and isinstance(head, str) and bool(SHA.fullmatch(head)),
             "invalid or unknown owner head")
        drift.append({"owner": owner, "pinned_sha": owners[owner],
                      "observed_sha": head,
                      "state": "HEAD_STALE" if head != owners[owner] else "HEAD_MATCH"})
    need(len(doc["queue_baseline"]) == 4, "four-repository stock required")
    queue = {}
    for repo, value in doc["queue_baseline"].items():
        q, running = value["queued"], value["running"]
        need(all(type(x) is int and x >= 0 for x in (q, running)),
             "invalid queue observation")
        queue[repo] = {
            "queued": q, "running": running,
            "queue_breach": q >= 60, "running_breach": running >= 20,
            "minimum_queued_reduction_for_lt60": max(0, q - 59),
            "snapshot_only_no_cancellation_authority": True,
        }
    conflicts = lane_collisions(manifest)
    need(not conflicts, "write collision: " + json.dumps(conflicts))
    pilot_layers = kahn_layers([o["id"] for o in manifest["owners"]],
                               manifest["edges"])
    return {
        "schema": "mip.temporal-burndown-report.v1",
        "authority": "READ_ONLY_NOT_ADMISSION",
        "source": {"baseline_date": doc["baseline_date"],
                   "source_class": doc["topology_source_class"],
                   "original_frozen_sha_verified": False,
                   "live_readback": "NON_ATOMIC"},
        "burndown": {"frozen_roots": 17, "frozen_weight": 65,
                     "verified_accepted_weight": 0, "verified_acceptance_floor": 0.0,
                     "live_weighted": None, "missing_certificate_count": 17},
        "historical_dag": {"edge_count": len(edges), "kahn_layers": layers,
                           "longest_chain_edges": max(distances.values()),
                           "descendant_counts": {r: len(descendants[r]) for r in sorted(descendants)},
                           "topology_is_secondary_witness": True},
        "queue_baseline": queue,
        "pilot": {"source_owner_head_drift": drift,
                  "stale_owner_heads": sum(x["state"] == "HEAD_STALE" for x in drift),
                  "source_work_kahn_layers": pilot_layers,
                  "write_collision_count": len(conflicts),
                  "actual_commits_by_this_report": 0,
                  "worker_dispatch_authorized": False},
        "gates": {"native_exact_head": None, "independent_approval": None,
                  "fpc": None, "owner_acceptance": None, "temporal_control": None,
                  "merge_admission": "HOLD", "scale": "WITHHELD"},
    }

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parent
    p.add_argument("--snapshot", type=Path, default=root / "bsln_20261116.json")
    p.add_argument("--manifest", type=Path, default=root / "manifest.json")
    p.add_argument("--out", type=Path)
    args = p.parse_args()
    data = review(json.loads(args.snapshot.read_text(encoding="utf-8")),
                  json.loads(args.manifest.read_text(encoding="utf-8")))
    out = json.dumps(data, sort_keys=True, indent=2) + "\n"
    if args.out:
        args.out.write_text(out, encoding="utf-8")
    else:
        print(out, end="")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
