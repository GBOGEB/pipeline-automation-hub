#!/usr/bin/env python3
"""MIP closure pilot: offline evidence census and dependency admission.

Read-only by design. No GitHub client, subprocess, network access, or repository writes.
Usage: python closure_census.py --manifest manifest.json --out report.json
       python closure_census.py --manifest manifest.json --self-test
Reports UNKNOWN when native run/test/coverage history is absent.
"""
from __future__ import annotations

import argparse
import fnmatch
import importlib.util
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

SCHEMA = "mip.closure-dispatch.v1"
REPORT_SCHEMA = "mip.closure-census.v1"
ALLOWED = {"HOLD", "PROVE", "HEAD_STALE", "MERGED_NOT_ADMITTED", "ACCEPTED_CONTROL"}
ROOT_GROUPS = {
    "FLOW": ("P0-Q1", "P0-Q2"),
    "ADMISSION": ("P0-N6", "P0-G1", "P0-A1", "P0-A2", "P0-A3", "P0-C1"),
    "JADE": ("P0-J1", "P1-N1"),
    "ISSUE_REX": ("P1-I1", "P1-I2", "P1-R1"),
    "COVERAGE_MATH": ("P1-S1", "P1-M1"),
    "PUBLICATION": ("P2-D1", "P2-U1"),
}

class CensusError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CensusError(message)


def validate(doc: dict[str, Any]) -> None:
    require(doc.get("schema") == SCHEMA, "wrong manifest schema")
    require(doc.get("authority") == "DRAFT_NOT_ADMISSION", "manifest cannot assert release authority")
    frozen = doc["frozen"]
    require(frozen["root_count"] == 17 and frozen["primary_groups"] == 6 and
            frozen["known_dependency_edge_count"] == 16, "frozen cohort changed")
    flat = [x for group in ROOT_GROUPS.values() for x in group]
    require(len(flat) == len(set(flat)) == 17, "frozen primary groups must be exclusive")
    owners = doc["owners"]
    owner_ids = [o["id"] for o in owners]
    require(len(owner_ids) == len(set(owner_ids)), "duplicate owner IDs")
    for owner in owners:
        require(owner["state"] in ALLOWED, "unknown status")
        require(isinstance(owner.get("head"), str) and
                re.fullmatch(r"[0-9a-fA-F]{40}", owner["head"]) is not None,
                "unbound owner head SHA")
    root_ids = [r["id"] for r in doc["roots"]]
    require(len(root_ids) == len(set(root_ids)), "duplicate live root IDs")
    for root in doc["roots"]:
        require(root["owner"] in owner_ids, "root has unknown owner")
        require(root.get("source") and root.get("fingerprint"), "missing root evidence")
        require(root["accepted"] is False, "unverified root closure cannot enter this pilot")
        require(root.get("weight") is None, "unapproved root weight is not zero")
        require(root.get("impact") is None and root.get("urgency") is None,
                "unsupported point scores must remain null")
        if root["parent"] is not None:
            require(root["parent"] in flat or root["parent"] in root_ids,
                    "unknown root parent")
    lane_ids = [l["id"] for l in doc["lanes"]]
    require(len(lane_ids) == len(set(lane_ids)), "duplicate commit lane")
    for lane in doc["lanes"]:
        require(lane["owner"] in owner_ids, "lane has unknown owner")
        require(lane["paths"], "lane without owned files")
    nodes = set(owner_ids)
    for edge in doc["edges"]:
        require(edge["from"] in nodes and edge["to"] in nodes, "unknown dependency node")
        require(edge["from"] != edge["to"], "self dependency")
        require(edge.get("kind") in {"REQUIRED_PROVIDER_BEFORE_ADMISSION",
                                    "CONDITIONAL_IF_SVG_LANDS_FIRST"}, "unknown edge")


def kahn_layers(nodes: list[str], edges: list[dict[str, Any]]) -> list[list[str]]:
    """Adapter to JADE's sole source-owned Kahn implementation."""
    require(len(nodes) == len(set(nodes)), "duplicate DAG node")
    owner = Path(__file__).resolve().parents[2] / "jade_temple" / "devops" / "lifecycle.py"
    require(owner.is_file(), "canonical JADE Kahn owner unavailable")
    spec = importlib.util.spec_from_file_location("mip_canonical_jade_kahn", owner)
    require(spec is not None and spec.loader is not None, "canonical JADE Kahn owner unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    active = [(e["from"], e["to"], "FEEDFORWARD")
              for e in edges if e.get("enabled", True) is not False]
    try:
        return module.topo_layers(nodes, active)
    except ValueError as exc:
        raise CensusError(str(exc)) from exc


_GLOB_META = re.compile(r"[*?\\[]")


def _static_prefix(pattern: str) -> str:
    """Literal prefix ending before the first wildcard, for fail-closed overlap."""
    match = _GLOB_META.search(pattern)
    return pattern[:match.start()] if match else pattern


def validate_lane_path(path: Any) -> None:
    require(isinstance(path, str) and path.strip() and
            not path.startswith("/") and "\\" not in path and
            re.match(r"^[A-Za-z]:", path) is None and
            all(p not in {"", ".", ".."} for p in path.rstrip("/").split("/")),
            "unsafe commit lane path")


def path_overlap(a: str, b: str) -> bool:
    """Reject same-file, parent-folder, glob/file, and possibly intersecting glob lanes.

    When two globs cannot be proven disjoint, conservatively serialize them.
    """
    validate_lane_path(a)
    validate_lane_path(b)
    a, b = a.rstrip("/"), b.rstrip("/")
    if a == b or not a or not b:
        return True
    if a.startswith(b + "/") or b.startswith(a + "/"):
        return True
    a_glob, b_glob = bool(_GLOB_META.search(a)), bool(_GLOB_META.search(b))
    if not a_glob and not b_glob:
        return False
    if a_glob and not b_glob:
        return (fnmatch.fnmatchcase(b, a) or b.startswith(_static_prefix(a)) or
                _static_prefix(a).startswith(b + "/"))
    if b_glob and not a_glob:
        return (fnmatch.fnmatchcase(a, b) or a.startswith(_static_prefix(b)) or
                _static_prefix(b).startswith(a + "/"))
    pa, pb = _static_prefix(a), _static_prefix(b)
    return pa.startswith(pb) or pb.startswith(pa)



def score_range(parts: list[float | None], weights: list[float]) -> list[float]:
    """Unknown inputs vary independently in [0,1]; NEVER renormalize weights."""
    require(len(parts) == len(weights), "dimensions differ")
    require(abs(sum(weights) - 1.0) < 1e-9, "weights must sum to 1")
    lo = hi = 0.0
    for part, w in zip(parts, weights):
        require(w >= 0, "negative dimension weight")
        if part is None:
            hi += w
        else:
            require(0 <= part <= 1, "dimension outside [0,1]")
            lo += part * w
            hi += part * w
    return [round(100 * lo, 6), round(100 * hi, 6)]


def classify_tests(tests: list[dict[str, Any]] | None) -> dict[str, Any]:
    """NEVERGREEN is known only for a stable test with complete comparable history.

    A failed workflow without JUnit/test IDs yields UNKNOWN, not zero or EVERRED.
    """
    if tests is None:
        return {"denominator": None, "nevergreen": None, "evergreen": None,
                "zero_coverage_modules": None, "reason": "no_complete_native_test_inventory"}
    never = evergreen = 0
    seen_ids: set[tuple[str, str, str]] = set()
    for t in tests:
        require(bool(t.get("test_id")) and bool(t.get("contract_version")) and
                bool(t.get("runner")), "test identity incomplete")
        identity = (t["test_id"], t["contract_version"], t["runner"])
        require(identity not in seen_ids, "duplicate test identity")
        seen_ids.add(identity)
        history = t.get("outcomes")
        require(t.get("history_complete") is True and history, "history is incomplete")
        require(all(x in ("PASS", "FAIL", "ERROR", "SKIP") for x in history),
                "unknown test outcome")
        if all(x in ("FAIL", "ERROR") for x in history):
            never += 1
        if "PASS" in history:
            evergreen += 1
    return {"denominator": len(tests), "nevergreen": never, "evergreen": evergreen,
            "zero_coverage_modules": None, "reason": "coverage_requires_separate_module_census"}


def census(doc: dict[str, Any], tests: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    validate(doc)
    owners = doc["owners"]
    paths: dict[str, list[str]] = defaultdict(list)
    declared: list[tuple[str, str, str]] = []
    owner_repos = {o["id"]: o["repo"] for o in owners}
    for lane in doc["lanes"]:
        for path in lane["paths"]:
            validate_lane_path(path)
            paths[path].append(lane["id"])
            declared.append((owner_repos[lane["owner"]], lane["id"], path))
    collisions: list[tuple[str, str, str, str]] = []
    for i, (repo_a, lane_a, path_a) in enumerate(declared):
        for repo_b, lane_b, path_b in declared[i + 1:]:
            if repo_a == repo_b and lane_a != lane_b and path_overlap(path_a, path_b):
                collisions.append((lane_a, path_a, lane_b, path_b))
    require(not collisions, "commit lane path collision: " + repr(collisions))
    layers = kahn_layers([o["id"] for o in owners], doc["edges"])
    counts = {s: sum(o["state"] == s for o in owners) for s in sorted(ALLOWED)}
    evidence = {
        "owner_prs": len(owners), "live_root_candidates": len(doc["roots"]),
        "disjoint_commit_lanes": len(doc["lanes"]),
        "distinct_exact_file_owners": len(paths),
        "native_run_count_newly_verified": None,
        "test_executions_newly_verified": None,
        "native_pass": None, "native_fail": None,
        "pr_review_approved": sum(o["independent_approved"] for o in owners),
        "pr_review_unresolved": sum(o["review_threads_unresolved"] for o in owners),
        "pr_review_total": sum(o["review_threads_total"] for o in owners),
        "disjoint_path_collisions": 0,
    }
    return {
        "schema": REPORT_SCHEMA, "authority": "DRAFT_NOT_ADMISSION",
        "source_base_sha": doc["source_base_sha"],
        "cohort": "live-discovery-2026-11-13",
        "frozen": doc["frozen"], "historical_baseline": doc["baseline_workflows"],
        "status": counts, "evidence": evidence, "dag": {
            "kahn_layers": layers, "eligible_parallel_first_layer": layers[0],
            "active_edges": [e for e in doc["edges"] if e.get("enabled", True)],
            "conditional_edges_not_assumed": [e for e in doc["edges"] if e.get("enabled") is False],
            "historical_16_edge_topology": None,
            "historical_blocked_descendants": None, "historical_longest_path": None,
        },
        "proof": classify_tests(tests),
        "closure": {"accepted_live": 0, "frozen_weighted": None, "live_weighted": None,
                    "per_lane_weighted": None, "portfolio_composite": None,
                    "admission": "NOT_ADMISSION"},
        "score_policy": {"priority_weights": [0.35, 0.25, 0.20, 0.20],
                         "urgency_weights": [0.45, 0.35, 0.20],
                         "dispatch_weights": [0.65, 0.35],
                         "all_unknown_priority": score_range([None] * 4, [0.35, 0.25, 0.20, 0.20]),
                         "all_unknown_urgency": score_range([None] * 3, [0.45, 0.35, 0.20])},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("manifest.json"))
    parser.add_argument("--tests", type=Path, help="optional complete, test-ID keyed history JSON list")
    parser.add_argument("--out", type=Path, help="optional output; stdout remains usable")
    parser.add_argument("--self-test", action="store_true", help="run offline smoke assertions")
    args = parser.parse_args()
    doc = json.loads(args.manifest.read_text(encoding="utf-8"))
    tests = json.loads(args.tests.read_text(encoding="utf-8")) if args.tests else None
    report = census(doc, tests)
    if args.self_test:
        assert report["evidence"]["owner_prs"] == 5
        assert report["evidence"]["live_root_candidates"] == 8
        assert report["evidence"]["disjoint_commit_lanes"] == 9
        assert report["evidence"]["pr_review_unresolved"] == 38
        assert report["closure"]["accepted_live"] == 0
        assert report["dag"]["kahn_layers"][-1] == ["A2746"]
        assert score_range([1, None, None, None], [0.35, 0.25, 0.2, 0.2]) == [35.0, 100.0]
        print("offline smoke: OK")
    output = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(output, encoding="utf-8", newline="\n")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
