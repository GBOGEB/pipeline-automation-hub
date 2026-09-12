#!/usr/bin/env python3
"""Observed Bradley-Terry gate for W3-15.

Historical REX may prove the evidence shape and engine, but W3-15 only passes
from explicit current-frontier intervention outcomes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


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
    usable = [(p["winner"], p["loser"]) for p in pairs if p.get("winner") and p.get("loser") and p["winner"] != p["loser"]]
    if not usable:
        return {"status": "DEFER_NO_USABLE_COMPARISONS", "scores": {}}
    names = sorted({x for a, b in usable for x in (a, b)})
    comps = components(names, usable)
    if len(comps) > 1:
        return {"status": "DEFER_DISCONNECTED_COMPARISON_GRAPH", "components": comps, "scores": {}}
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
            den = sum(n[(a, b)] / (strength[a] + strength[b]) for b in names if b != a and n[(a, b)])
            updated[a] = wins[a] / den if den and wins[a] else 1e-12
        scale = sum(updated.values()) / len(updated)
        strength = {k: v / scale for k, v in updated.items()}
    return {"status": "PASS_OBSERVED_BT", "scores": dict(sorted(strength.items(), key=lambda kv: kv[1], reverse=True))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="mission-control/qps-triage-ultra/w3_bt_observations.json")
    ap.add_argument("--out")
    args = ap.parse_args()
    doc = json.loads(Path(args.input).read_text(encoding="utf-8"))

    historical_pairs = doc.get("historical_control_rex", {}).get("pairs", [])
    current_pairs = doc.get("current_frontier", {}).get("pairs", [])
    historical = bt(historical_pairs)
    current = bt(current_pairs)
    min_current = int(doc.get("policy", {}).get("minimum_current_frontier_pairs", 2))

    current_eligible = len(current_pairs) >= min_current and current.get("status") == "PASS_OBSERVED_BT"
    receipt = {
        "schema": "qps-w3-observed-bt-receipt/v1",
        "evidence_policy": doc.get("policy"),
        "historical_control_rex": {
            "pair_count": len(historical_pairs),
            "eligible_for_w3_15": False,
            "result": historical
        },
        "current_frontier": {
            "candidates": doc.get("current_frontier", {}).get("candidates", []),
            "pair_count": len(current_pairs),
            "result": current
        },
        "w3_15": "PASS_OBSERVED_INTERVENTION_BT" if current_eligible else "WITHHELD_NO_CURRENT_FRONTIER_PAIRWISE_OUTCOMES",
        "authority_transfer": False
    }
    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
