#!/usr/bin/env python3
"""Read-only, fail-closed disjoint wave planner over the canonical CI spine index.

No GitHub API calls, commits, runners, merges, timers or promotion authority.
The wave is proposed, NOT executed. Receipt inputs are untrusted local claims,
never independently verified; preserve this boundary in every output.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import deque
from pathlib import PurePosixPath, Path

POLICY_SCHEMA = "jade.devops.ci-spine.waves.v1"
INDEX_SCHEMA = "jade.devops.ci-spine.index.v1"
OUTPUT_SCHEMA = "jade.devops.ci-spine.wave-plan.v1"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
TASK_ID = re.compile(r"^[A-Z][A-Z0-9-]{2,63}$")
SHORT_NAME_MARKER = re.compile(r"~[0-9]")
STAGES = ("DISCOVER", "PREPARE", "BUILD", "VERIFY", "INTEGRATE", "CONTROL")


def valid_path(name):
    if not isinstance(name, str) or not name or "\\" in name or "\x00" in name:
        return False
    # Ownership supports exact paths or a terminal "/**" subtree only.
    # All other glob syntax would evade the literal overlap detector.
    raw = name[:-3] if name.endswith("/**") else name
    if not raw or any(char in raw for char in "*?[]{}!"):
        return False
    p = PurePosixPath(raw)
    if p.is_absolute() or str(p) != raw:
        return False
    # Win32 aliases: trailing spaces/dots are discarded, device names are
    # reserved even when followed by an extension, and ':' is an ADS separator.
    # Refuse these claims rather than silently allocating overlapping workers.
    # 8.3 short names (PROGRA~1, LONGFI~12.TXT) alias a long-named sibling on
    # NTFS and cannot be expanded without the target filesystem, so any
    # component carrying the "~<digit>" short-name marker is refused.
    for component in p.parts:
        if (component in (".", "..") or (component.rstrip(" .") != component or component.lstrip(" ") != component)
                or SHORT_NAME_MARKER.search(component)
                or any(ord(c) < 32 or c in '<>:"|\\' for c in component)
                or re.fullmatch(r"(?:con|conin\$|conout\$|prn|aux|nul|com[1-9\u00b9\u00b2\u00b3]|lpt[1-9\u00b9\u00b2\u00b3])(?:\..*)?",
                                component, re.IGNORECASE)):
            return False
    return True


def collision(left, right):
    """Two workers may not own a file/ancestor subtree simultaneously."""
    # Conservative cross-platform overlap: Windows worktrees are case-insensitive.
    # Case-folding also makes Linux planning safe for Windows downstream workers.
    x, y = left.rstrip("/").casefold(), right.rstrip("/").casefold()
    if x.endswith("/**"):
        x = x[:-3]
    if y.endswith("/**"):
        y = y[:-3]
    return x == y or x.startswith(y + "/") or y.startswith(x + "/")


def cycles(nodes):
    """Iterative Kahn traversal: deterministic O(nodes + edges), no recursion limit."""
    indegree = {task["id"]: len(task["depends"]) for task in nodes}
    downstream = {task["id"]: [] for task in nodes}
    for task in nodes:
        for prerequisite in task["depends"]:
            # build() verifies references before calling this function.
            downstream[prerequisite].append(task["id"])
    frontier = deque(sorted(tid for tid, degree in indegree.items() if degree == 0))
    completed = 0
    while frontier:
        tid = frontier.popleft()
        completed += 1
        for child in sorted(downstream[tid]):
            indegree[child] -= 1
            if indegree[child] == 0:
                frontier.append(child)
    return completed != len(indegree)


def build(index, policy, receipts=None):
    errors = []
    if receipts is None:
        receipts = {}
    if not isinstance(index, dict) or index.get("schema") != INDEX_SCHEMA:
        errors.append("invalid source index schema")
        index = {}
    if not isinstance(policy, dict) or policy.get("schema") != POLICY_SCHEMA:
        errors.append("invalid wave policy schema")
        policy = {}
    source = index.get("source")
    if not isinstance(source, dict):
        errors.append("malformed source object")
        source = {}
    assurance = index.get("assurance")
    if not isinstance(assurance, dict):
        errors.append("malformed assurance object")
        assurance = {}
    if not isinstance(index.get("errors"), list):
        errors.append("malformed index errors list")
    sha = source.get("checkout_sha")
    if not isinstance(sha, str) or not SHA40.fullmatch(sha):
        errors.append("missing exact source SHA")
    if index.get("verdict") != "PASS_STATIC_BINDINGS_ONLY":
        errors.append("source topology is not statically qualified")
    if source.get("expected_sha") not in (None, sha):
        errors.append("index expected-head mismatch")
    if index.get("errors"):
        errors.append("source index reports errors")
    if assurance.get("merge_admission") != "HOLD":
        errors.append("source index incorrectly claims merge admission")
    max_workers = policy.get("max_workers")
    if not isinstance(max_workers, int) or isinstance(max_workers, bool) or not (1 <= max_workers <= 12):
        errors.append("max_workers must be integer 1..12")
        max_workers = 1
    tasks = policy.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        errors.append("missing tasks")
        tasks = []
    seen, norm = set(), []
    for raw in tasks:
        if not isinstance(raw, dict):
            errors.append("non-object task")
            continue
        name, lane, stage = raw.get("id"), raw.get("lane"), raw.get("stage")
        dep, owns = raw.get("depends"), raw.get("owns")
        if not isinstance(name, str) or not TASK_ID.fullmatch(name) or name in seen:
            errors.append("duplicate or invalid task id")
            continue
        seen.add(name)
        if not isinstance(lane, str) or not TASK_ID.fullmatch(lane):
            errors.append(name + ": invalid lane")
        if stage not in STAGES:
            errors.append(name + ": invalid stage")
        if not isinstance(dep, list) or len(dep) != len(set(map(str, dep))) or not all(isinstance(x, str) for x in dep):
            errors.append(name + ": invalid dependencies")
            dep = []
        if not isinstance(owns, list) or not owns or not all(valid_path(x) for x in owns):
            errors.append(name + ": invalid ownership paths")
            owns = []
        prio = raw.get("priority", 3)
        if type(prio) is not int or not (1 <= prio <= 5):
            errors.append(name + ": invalid priority")
            prio = 3
        norm.append({"id": name, "lane": lane, "stage": stage, "depends": dep, "owns": owns,
                     "priority": prio, "purpose": str(raw.get("purpose", ""))[:180]})
    ids = {t["id"] for t in norm}
    for t in norm:
        if any(d not in ids or d == t["id"] for d in t["depends"]):
            errors.append(t["id"] + ": dangling/self dependency")
    if not errors and cycles(norm):
        errors.append("task dependency DAG contains cycle")
    if not isinstance(receipts, dict):
        errors.append("receipt input must be a mapping")
        receipts = {}
    if any(not isinstance(k, str) for k in receipts):
        errors.append("receipt keys must be strings")
    unknown = sorted(str(k) for k in receipts if k not in ids)
    if unknown:
        errors.append("unknown receipt tasks: " + ", ".join(unknown))
    accepted = set()
    for t in norm:
        receipt = receipts.get(t["id"])
        if not isinstance(receipt, dict):
            continue
        if (receipt.get("source_sha") == sha and receipt.get("verdict") == "PASS"
                and type(receipt.get("run_id")) is int and receipt["run_id"] > 0
                and type(receipt.get("tests_ran")) is int and receipt["tests_ran"] > 0):
            accepted.add(t["id"])
    selected, lanes, claims = [], set(), []
    rows = []
    for t in sorted(norm, key=lambda x: (x["priority"], STAGES.index(x["stage"]) if x["stage"] in STAGES else 999, x["id"])):
        missing = [d for d in t["depends"] if d not in accepted]
        if t["id"] in accepted:
            state, why = "RECEIPT_DECLARED_UNVERIFIED", []
        elif errors:
            state, why = "HOLD_INVALID_INPUT", errors
        elif missing:
            state, why = "BLOCKED_DEPENDENCY", missing
        elif t["lane"] in lanes:
            state, why = "DEFER_LANE_OCCUPIED", [t["lane"]]
        elif any(collision(x, y) for x in t["owns"] for y in claims):
            state, why = "DEFER_OWNERSHIP_COLLISION", []
        elif len(selected) >= max_workers:
            state, why = "DEFER_WORKER_CAPACITY", []
        else:
            selected.append(t["id"])
            lanes.add(t["lane"])
            claims.extend(t["owns"])
            state, why = "PROPOSED_NOT_EXECUTED", []
        rows.append({**t, "disposition": state, "blockers": why})
    if errors:
        selected = []
    return {
        "schema": OUTPUT_SCHEMA,
        "verdict": "WAVE_POLICY_FIRST_RED" if errors else "PROPOSED_ONLY_NOT_EXECUTED",
        "source_sha": sha, "max_workers": max_workers,
        "candidate_workers": selected, "ready_count": len(selected),
        "declared_receipts_not_revalidated": sorted(accepted),
        "rows": sorted(rows, key=lambda x: x["id"]),
        "errors": errors,
        "authority": {"execution": "NONE", "merge": "HOLD", "release": "HOLD",
                      "approval": "REQUIRES_ELIGIBLE_INDEPENDENT_REVIEW",
                      "next_pulse": "RETAKE_EXACT_HEAD_AND_REVALIDATE_RECEIPTS"},
    }


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--index", type=Path, required=True)
    a.add_argument("--policy", type=Path, required=True)
    a.add_argument("--receipts", type=Path)
    a.add_argument("--out", type=Path)
    a.add_argument("--check", action="store_true")
    args = a.parse_args(argv)
    try:
        index = json.loads(args.index.read_text(encoding="utf-8"))
        policy = json.loads(args.policy.read_text(encoding="utf-8"))
        receipts = json.loads(args.receipts.read_text(encoding="utf-8")) if args.receipts else {}
        result = build(index, policy, receipts)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        result = {"schema": OUTPUT_SCHEMA, "verdict": "WAVE_POLICY_FIRST_RED",
                  "errors": [type(exc).__name__], "candidate_workers": [],
                  "authority": {"execution": "NONE", "merge": "HOLD"}}
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return int(args.check and bool(result.get("errors")))


if __name__ == "__main__":
    sys.exit(main())
