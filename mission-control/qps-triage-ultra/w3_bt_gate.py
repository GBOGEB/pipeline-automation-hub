#!/usr/bin/env python3
"""Observed Bradley-Terry gate for W3-15.

W3-15 receives credit only from explicit current-wave intervention outcomes.
Historical REX remains useful for regression/shape testing but is never project
BT credit.  Current pairs must bind a measured FAIL -> SUCCESS -> CONTROL
sequence before they enter the Bradley-Terry graph.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_CURRENT_FIELDS = (
    "winner",
    "loser",
    "objective",
    "evidence_class",
    "loser_run_id",
    "loser_exact_sha",
    "loser_outcome",
    "winner_run_id",
    "winner_exact_sha",
    "winner_outcome",
    "control_repeat_run_id",
    "control_repeat_exact_sha",
    "control_repeat_outcome",
    "source",
)


def components(names, pairs):
    graph = {n: set() for n in names}
    for a, b in pairs:
        graph[a].add(b)
        graph[b].add(a)
    out, seen = [], set()
    for start in names:
        if start in seen:
            continue
        stack, comp = [start], []
        seen.add(start)
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for nxt in graph[cur]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        out.append(sorted(comp))
    return out


def bt(pairs):
    usable = [
        (p["winner"], p["loser"])
        for p in pairs
        if p.get("winner") and p.get("loser") and p["winner"] != p["loser"]
    ]
    if not usable:
        return {"status": "DEFER_NO_USABLE_COMPARISONS", "scores": {}}
    names = sorted({x for a, b in usable for x in (a, b)})
    comps = components(names, usable)
    if len(comps) > 1:
        return {
            "status": "DEFER_DISCONNECTED_COMPARISON_GRAPH",
            "components": comps,
            "scores": {},
        }
    wins = {x: 0.0 for x in names}
    n = {(a, b): 0 for a in names for b in names if a != b}
    for a, b in usable:
        wins[a] += 1.0
        n[(a, b)] += 1
        n[(b, a)] += 1
    strength = {x: 1.0 for x in names}
    for _ in range(128):
        updated = {}
        for a in names:
            den = sum(
                n[(a, b)] / (strength[a] + strength[b])
                for b in names
                if b != a and n[(a, b)]
            )
            updated[a] = wins[a] / den if den and wins[a] else 1e-12
        scale = sum(updated.values()) / len(updated)
        strength = {k: v / scale for k, v in updated.items()}
    return {
        "status": "PASS_OBSERVED_BT",
        "scores": dict(sorted(strength.items(), key=lambda kv: kv[1], reverse=True)),
    }


def validate_current_pairs(pairs, policy):
    failures = []
    required_class = policy.get("pair_evidence_class_required", "MEASURED")
    for i, pair in enumerate(pairs):
        missing = [f for f in REQUIRED_CURRENT_FIELDS if pair.get(f) in (None, "")]
        if missing:
            failures.append({"pair": i, "reason": "MISSING_FIELDS", "fields": missing})
            continue
        if pair["evidence_class"] != required_class:
            failures.append({"pair": i, "reason": "NON_MEASURED_EVIDENCE_CLASS"})
        if pair["loser_outcome"] != "FAIL":
            failures.append({"pair": i, "reason": "LOSER_NOT_MEASURED_FAIL"})
        if pair["winner_outcome"] != "SUCCESS":
            failures.append({"pair": i, "reason": "WINNER_NOT_MEASURED_SUCCESS"})
        if pair["control_repeat_outcome"] != "SUCCESS":
            failures.append({"pair": i, "reason": "CONTROL_REPEAT_NOT_SUCCESS"})
        if not isinstance(pair["loser_run_id"], int) or not isinstance(pair["winner_run_id"], int):
            failures.append({"pair": i, "reason": "RUN_ID_NOT_INTEGER"})
        if not isinstance(pair["control_repeat_run_id"], int):
            failures.append({"pair": i, "reason": "CONTROL_RUN_ID_NOT_INTEGER"})
    return failures


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--input", default="mission-control/qps-triage-ultra/w3_bt_observations.json"
    )
    ap.add_argument("--out")
    args = ap.parse_args()
    doc = json.loads(Path(args.input).read_text(encoding="utf-8"))

    policy = doc.get("policy", {})
    historical_pairs = doc.get("historical_control_rex", {}).get("pairs", [])
    current_pairs = doc.get("current_frontier", {}).get("pairs", [])
    validation_failures = validate_current_pairs(current_pairs, policy)

    historical = bt(historical_pairs)
    current = bt(current_pairs) if not validation_failures else {
        "status": "DEFER_PAIR_EVIDENCE_VALIDATION_FAILED",
        "scores": {},
    }
    min_current = int(policy.get("minimum_current_frontier_pairs", 2))
    current_eligible = (
        not validation_failures
        and len(current_pairs) >= min_current
        and current.get("status") == "PASS_OBSERVED_BT"
    )

    receipt = {
        "schema": "qps-w3-observed-bt-receipt/v2",
        "evidence_policy": policy,
        "historical_control_rex": {
            "pair_count": len(historical_pairs),
            "eligible_for_w3_15": False,
            "result": historical,
        },
        "current_frontier": {
            "candidates": doc.get("current_frontier", {}).get("candidates", []),
            "pair_count": len(current_pairs),
            "pair_validation_failures": validation_failures,
            "pair_evidence_class": policy.get("pair_evidence_class_required"),
            "result": current,
            "comparison_boundary": policy.get("cross_objective_claim_boundary"),
        },
        "w3_15": (
            "PASS_OBSERVED_INTERVENTION_BT"
            if current_eligible
            else "WITHHELD_NO_VALID_CURRENT_FRONTIER_PAIRWISE_OUTCOMES"
        ),
        "authority_transfer": False,
    }
    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if current_eligible else 2


if __name__ == "__main__":
    raise SystemExit(main())
