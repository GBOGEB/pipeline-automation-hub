#!/usr/bin/env python3
"""CODE MAROON adaptive routing projection.

Read-only planner layered on the existing MAROON operations ledger and hints projection.
It does not claim work, write source, resolve threads, dismiss scanner alerts, or merge.
Metric ownership remains with the existing owners: hints.py owns finding recurrence,
operations.py owns Kahn/leases/closure, and GOGREEN/scale-dock/everred own red metrics.

The purpose here is routing: turn one current root into exactly one next lane and stop
blind self-repair after bounded failed attempts. A real executor must still claim the
root through operations.py and satisfy its source/OID/fencing contract.
"""
from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import os
from pathlib import Path
from typing import Any

SCHEMA = "code_maroon.adaptive-route.v1"
PUBLIC_SCHEMA = "code_maroon.adaptive-route-public.v1"
AUTHORITY = "ADVISORY_ROUTING_NOT_CLOSURE_OR_MERGE_AUTHORITY"
SELF_REPAIR_BUDGET = 2
FAIL_RELEASE_REASONS = {
    "repair_failed",
    "verification_failed",
    "same_root_red",
    "root_red",
    "everred",
}
PASS_ON_CLASSES = {"EVERRED", "GREEN_TO_RED", "FLAKY"}

LANES = {
    "ANALYZE_ONLY_CANARY": {
        "worker": "MAROON_PROBE_READER",
        "writes": False,
        "next": "preserve negative control; analyse only",
    },
    "OWNER_RETURN": {
        "worker": "OWNER_OR_EXTERNAL_BRANCH_OWNER",
        "writes": False,
        "next": "return evidence and exact unblock predicate to owner",
    },
    "LEDGER_RECONCILE": {
        "worker": "MAROON_CLOSER",
        "writes": False,
        "next": "reconcile provider readback and durable ledger closure",
    },
    "RESTACK_FIRST": {
        "worker": "MAROON_RESTACK_WORKER",
        "writes": True,
        "next": "restack owned branch on current default; rescan before source repair",
    },
    "REUSE_METHOD": {
        "worker": "MAROON_METHOD_REUSE_WORKER",
        "writes": True,
        "next": "reuse a previously proved treatment on this exact source packet",
    },
    "PR_LOCAL_REPAIR": {
        "worker": "MAROON_BRANCH_REPAIR_WORKER",
        "writes": True,
        "next": "minimal branch-local repair then verify and close each child",
    },
    "FOLD_BACK_DEFAULT": {
        "worker": "MAROON_FOLDBACK_WORKER",
        "writes": True,
        "next": "one prevention change on an owned default-branch repair PR; then restack children",
    },
    "PASS_ON_ROOT_RED": {
        "worker": "GOGREEN_ROOT_RED",
        "writes": False,
        "next": "stop self-repair; attribute first/root red and return a new source-bound repair packet",
    },
    "PASS_ON_EVERRED": {
        "worker": "GOGREEN_EVERRED",
        "writes": False,
        "next": "stop self-repair; use canonical EVERRED/red-trace evidence before another mutation",
    },
    "HOLD": {
        "worker": "MAROON_COORDINATOR",
        "writes": False,
        "next": "hold until source/admission/dependency evidence becomes current",
    },
}


def _released_failed_attempts(root: dict[str, Any]) -> int:
    attempts = list(root.get("attempts") or [])
    lease = root.get("lease")
    if lease and lease.get("released_at"):
        attempts.append(lease)
    return sum(1 for a in attempts if a.get("release_reason") in FAIL_RELEASE_REASONS)


def _everred_map(red_trace: Any) -> dict[tuple[str, str], str]:
    """Accept one red-trace report, a list, or {reports:[...]}; return repo/path -> class."""
    if not red_trace:
        return {}
    reports = red_trace.get("reports", []) if isinstance(red_trace, dict) and "reports" in red_trace else red_trace
    if isinstance(reports, dict):
        reports = [reports]
    out: dict[tuple[str, str], str] = {}
    for report in reports or []:
        repo = report.get("repository")
        for wf in report.get("workflows", []) or []:
            path, cls = wf.get("path"), wf.get("class")
            if repo and path and cls:
                out[(repo, path)] = cls
    return out


def _obs_hints(hints_result: dict[str, Any], item_id: str) -> set[str]:
    row = (hints_result.get("observations") or {}).get(item_id) or {}
    return {h.get("code") for h in row.get("hints", []) if h.get("code")}


def _finding_rows(hints_result: dict[str, Any], item_ids: list[str]) -> list[dict[str, Any]]:
    findings = hints_result.get("findings") or {}
    observations = hints_result.get("observations") or {}
    rows = []
    for item_id in item_ids:
        finding_id = (observations.get(item_id) or {}).get("finding")
        if finding_id in findings:
            rows.append({"id": finding_id, **findings[finding_id]})
    return rows


def route_root(
    root: dict[str, Any],
    members: list[dict[str, Any]],
    finding_rows: list[dict[str, Any]],
    hint_codes: set[str],
    everred: dict[tuple[str, str], str] | None = None,
    source_signals: set[str] | None = None,
) -> dict[str, Any]:
    """Choose one next lane for a root. Strong stop/pass-on rules win over repair advice."""
    everred = everred or {}
    source_signals = source_signals or set()
    reasons: list[str] = []

    if root.get("state") in {"CLOSED", "SUPERSEDED"}:
        lane = "HOLD"
        reasons.append(root.get("state"))
    elif any(m.get("negative_canary") is not False for m in members):
        lane = "ANALYZE_ONLY_CANARY"
        reasons.append("NEGATIVE_CANARY_OR_UNKNOWN_INTENT")
    elif "NO_PUSH_FORK" in hint_codes:
        lane = "OWNER_RETURN"
        reasons.append("FOREIGN_HEAD_REPOSITORY")
    elif any(m.get("provider_state") == "resolved" and m.get("semantic_state") != "closed" for m in members):
        lane = "LEDGER_RECONCILE"
        reasons.append("PROVIDER_RESOLVED_LEDGER_OPEN")
    else:
        red_classes = sorted({everred.get((m.get("repo"), m.get("path"))) for m in members} - {None})
        failed_attempts = _released_failed_attempts(root)
        if any(cls in PASS_ON_CLASSES for cls in red_classes):
            lane = "PASS_ON_EVERRED"
            reasons += ["RED_TRACE_" + cls for cls in red_classes if cls in PASS_ON_CLASSES]
        elif failed_attempts >= SELF_REPAIR_BUDGET or "SELF_REPAIR_EXHAUSTED" in source_signals:
            lane = "PASS_ON_ROOT_RED"
            reasons.append(f"SELF_REPAIR_BUDGET_EXHAUSTED:{failed_attempts}")
        elif "STALE_BASE_DEFAULT_CHANGED" in source_signals or "DEFAULT_PATH_ABSENT" in source_signals:
            lane = "RESTACK_FIRST"
            reasons.append("STALE_OR_REMOVED_DEFAULT_SOURCE")
        elif "NO_PUSH_BOT_BRANCH" in hint_codes:
            lane = "FOLD_BACK_DEFAULT"
            reasons.append("BOT_BRANCH_NO_DIRECT_PUSH")
        elif "DEFAULT_HAS_SAME_DEFECT" in source_signals:
            lane = "FOLD_BACK_DEFAULT"
            reasons.append("DEFECT_PRESENT_ON_DEFAULT")
        elif any(f.get("recurrence") == "SYSTEMIC" for f in finding_rows):
            lane = "FOLD_BACK_DEFAULT"
            reasons.append("SYSTEMIC_RECURRENCE")
        elif "SEEN_FIXED" in hint_codes:
            lane = "REUSE_METHOD"
            reasons.append("PRIOR_PROVED_METHOD_AVAILABLE")
        else:
            lane = "PR_LOCAL_REPAIR"
            reasons.append("CURRENT_BRANCH_LOCAL_WORK")

    spec = LANES[lane]
    paths = sorted({m.get("path") for m in members if m.get("path")})
    repo = root.get("target_repo") or root.get("repo")
    branch = root.get("branch")
    return {
        "root_id": root.get("id"),
        "lane": lane,
        "worker": spec["worker"],
        "writes": spec["writes"],
        "next": spec["next"],
        "reason_codes": reasons,
        "self_repair_failures": _released_failed_attempts(root),
        "self_repair_budget": SELF_REPAIR_BUDGET,
        "repo": repo,
        "branch": branch,
        "paths": paths,
        "concurrency_key": [repo, branch, paths],
        "member_ids": sorted(root.get("member_ids") or []),
        "finding_ids": sorted({f["id"] for f in finding_rows}),
    }


def _wave_by_root(queue_plan: dict[str, Any] | None) -> dict[str, int]:
    if not queue_plan:
        return {}
    out = {}
    for index, layer in enumerate(queue_plan.get("layers") or []):
        for node in layer:
            if isinstance(node, str) and ":" in node:
                root, stage = node.rsplit(":", 1)
                if stage == "diagnose":
                    out[root] = index
    return out


def project(
    ledger: dict[str, Any],
    hints_result: dict[str, Any],
    *,
    queue_plan: dict[str, Any] | None = None,
    red_trace: Any = None,
    source_signals: dict[str, list[str]] | None = None,
    max_workers: int = 4,
) -> dict[str, Any]:
    """Build the heterogeneous worker matrix from canonical owner projections."""
    source_signals = source_signals or {}
    everred = _everred_map(red_trace)
    wave_index = _wave_by_root(queue_plan)
    packets = {p.get("root_id"): p for p in (queue_plan or {}).get("packets", [])}
    rows = []
    for root_id, root in sorted((ledger.get("roots") or {}).items()):
        item_ids = list(root.get("member_ids") or [])
        if not item_ids:
            continue
        members = [(ledger.get("observations") or {}).get(i, {}) for i in item_ids]
        finding_rows = _finding_rows(hints_result, item_ids)
        codes = set().union(*(_obs_hints(hints_result, i) for i in item_ids)) if item_ids else set()
        row = route_root(root, members, finding_rows, codes, everred, set(source_signals.get(root_id) or []))
        packet = packets.get(root_id)
        row["kahn_wave"] = wave_index.get(root_id)
        row["admission_reasons"] = list((packet or {}).get("admission_reasons") or [])
        row["admitted_by_kahn"] = (
            queue_plan is not None
            and packet is not None
            and not row["admission_reasons"]
            and root.get("state") == "OPEN"
        )
        rows.append(row)

    open_obs = [o for o in (ledger.get("observations") or {}).values() if o.get("semantic_state") != "closed"]
    open_findings = {
        o.get("finding") for o in (hints_result.get("observations") or {}).values() if o.get("finding")
    }
    proposals = hints_result.get("proposals") or []
    group_savings = sum(max(0, len(p.get("item_ids") or []) - 1) for p in proposals if p.get("kind") == "GROUP_FINDINGS")
    open_roots = sum(1 for r in rows if r["lane"] != "HOLD")
    after_grouping = max(0, open_roots - group_savings)
    route_counts = collections.Counter(r["lane"] for r in rows)

    # Advisory first wave only. Canonical operations.claim still performs the real conflict check.
    selected, occupied = [], set()
    order = sorted(
        rows,
        key=lambda r: (
            r["kahn_wave"] is None,
            r["kahn_wave"] if r["kahn_wave"] is not None else 10**9,
            r["root_id"] or "",
        ),
    )
    executable = {"PR_LOCAL_REPAIR", "REUSE_METHOD", "RESTACK_FIRST", "FOLD_BACK_DEFAULT", "LEDGER_RECONCILE"}
    for row in order:
        if len(selected) >= max_workers or row["lane"] not in executable or not row["admitted_by_kahn"]:
            continue
        repo_branch = (row["repo"], row["branch"])
        if repo_branch in occupied:
            continue
        selected.append(row["root_id"])
        occupied.add(repo_branch)

    return {
        "schema": SCHEMA,
        "authority": AUTHORITY,
        "self_repair_budget": SELF_REPAIR_BUDGET,
        "actors": {
            "scanner": "MAROON intake: provider census -> operations.ingest",
            "planner": "hints.py + this advisory router + operations.py Kahn plan",
            "coordinator": "existing JADE CREW and MAROON worker; one CAS/fencing authority",
            "repair_workers": "disjoint branch/path workers selected by lane",
            "closer": "closure.py provider reply/resolve/readback/ledger closure",
            "root_red": "GOGREEN red-trace/scale-dock owner after bounded self-repair",
            "everred": "canonical EVERRED harvest/red-trace owners",
            "owner_return": "human/provider owner for credentials, forks, policy, or authority decisions",
        },
        "phases": ["normalize", "diagnose", "treat", "verify", "publish", "reply", "resolve", "readback", "close", "rex", "control"],
        "matrix": rows,
        "dispatch_preview": {
            "max_workers": max_workers,
            "selected_root_ids": selected,
            "native_actions_executed": 0,
            "claim_required": True,
        },
        "telemetry": {
            "open_observations": len(open_obs),
            "open_findings": len(open_findings),
            "open_routed_roots": open_roots,
            "group_candidates": sum(p.get("kind") == "GROUP_FINDINGS" for p in proposals),
            "cross_pr_method_candidates": sum(p.get("kind") == "ONE_METHOD_MANY_PACKETS" for p in proposals),
            "foldback_candidates": sum(p.get("kind") == "FOLD_BACK" for p in proposals),
            "potential_root_savings_from_grouping": group_savings,
            "potential_packets_after_grouping": after_grouping,
            "potential_compression_ratio": round(len(open_obs) / after_grouping, 2) if after_grouping else None,
            "route_counts": dict(sorted(route_counts.items())),
            "pass_on_root_red": route_counts.get("PASS_ON_ROOT_RED", 0),
            "pass_on_everred": route_counts.get("PASS_ON_EVERRED", 0),
        },
        "sipoc": {
            "suppliers": ["GitHub PR/review/scanner state", "MAROON ledger", "hints recurrence", "GOGREEN/EVERRED owners", "prior REX"],
            "inputs": ["exact head/base/OIDs", "Kahn dependencies", "finding identity", "retry receipts", "red-trace class"],
            "process": ["normalize", "classify route", "select disjoint Kahn roots", "claim", "repair or pass-on", "verify", "close", "REX/fold-back"],
            "outputs": ["one next lane per root", "bounded worker wave", "closure receipts", "root-red/everred handoff", "prevention candidate"],
            "customers": ["PR owners", "JADE/MAROON coordinator", "dependent roots", "next intake pulse"],
        },
    }


def public_counts(result: dict[str, Any]) -> dict[str, Any]:
    t = result["telemetry"]
    return {
        "schema": PUBLIC_SCHEMA,
        "authority": AUTHORITY,
        "self_repair_budget": result["self_repair_budget"],
        "open_observations": t["open_observations"],
        "open_findings": t["open_findings"],
        "open_routed_roots": t["open_routed_roots"],
        "route_counts": t["route_counts"],
        "group_candidates": t["group_candidates"],
        "cross_pr_method_candidates": t["cross_pr_method_candidates"],
        "foldback_candidates": t["foldback_candidates"],
        "potential_compression_ratio": t["potential_compression_ratio"],
    }


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ledger", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--hints", type=Path, help="existing MAROON_HINTS.json; otherwise compute with hints.py")
    ap.add_argument("--queue-plan", type=Path, help="operations.py plan JSON for Kahn admission/waves")
    ap.add_argument("--red-trace", type=Path, help="optional canonical GOGREEN red-trace JSON")
    ap.add_argument("--source-signals", type=Path, help="optional root_id -> source comparison signal list")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args(argv)
    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    if args.hints:
        hints_result = json.loads(args.hints.read_text(encoding="utf-8"))
    else:
        hints = _load_module("maroon_adaptive_hints", Path(__file__).with_name("hints.py"))
        hints_result = hints.analyse(ledger)
    queue_plan = json.loads(args.queue_plan.read_text(encoding="utf-8")) if args.queue_plan else None
    red_trace = json.loads(args.red_trace.read_text(encoding="utf-8")) if args.red_trace else None
    source_signals = json.loads(args.source_signals.read_text(encoding="utf-8")) if args.source_signals else None
    result = project(ledger, hints_result, queue_plan=queue_plan, red_trace=red_trace,
                     source_signals=source_signals, max_workers=args.workers)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "MAROON_ADAPTIVE.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.out / "MAROON_ADAPTIVE_PUBLIC.json").write_text(json.dumps(public_counts(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("MAROON_ADAPTIVE=PASS", json.dumps(public_counts(result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
