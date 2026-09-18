#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def _direction(counts: Counter) -> str:
    single = counts.get("ALLOC_SINGLE_CELL", 0)
    paired = counts.get("ALLOC_PAIRED_CELL", 0)
    if single > paired:
        return "ALLOC_SINGLE_CELL"
    if paired > single:
        return "ALLOC_PAIRED_CELL"
    return "INDETERMINATE"


def diagnose(pc3: dict, task_class: str, prior_strength: float | None = None, prior_pairs: int | None = None) -> dict:
    block = pc3["bt_conditional_by_task_class"][task_class]
    edges = [e for e in block["edges"] if e.get("comparable", True)]
    if not edges:
        raise ValueError("no comparable edges")

    habitat = defaultdict(Counter)
    lane = defaultdict(Counter)
    overall = Counter()
    rows = []
    for edge in edges:
        winner = edge["winner"]
        habitat[edge["habitat"]][winner] += 1
        lane[edge["lane"]][winner] += 1
        overall[winner] += 1
        rows.append({
            "cell_id": edge["cell_id"],
            "habitat": edge["habitat"],
            "lane": edge["lane"],
            "winner": winner,
            "relative_gap": float(edge["relative_gap"]),
            "single_seconds": float(edge["seconds_a"]),
            "paired_seconds": float(edge["seconds_b"]),
        })

    habitat_rows = {
        key: {
            "counts": dict(counts),
            "direction": _direction(counts),
        }
        for key, counts in sorted(habitat.items())
    }
    lane_rows = {
        key: {
            "counts": dict(counts),
            "direction": _direction(counts),
        }
        for key, counts in sorted(lane.items())
    }

    habitat_dirs = {v["direction"] for v in habitat_rows.values()}
    lane_dirs = {v["direction"] for v in lane_rows.values()}
    habitat_heterogeneous = len(habitat_dirs - {"INDETERMINATE"}) > 1 or "INDETERMINATE" in habitat_dirs
    lane_heterogeneous = len(lane_dirs - {"INDETERMINATE"}) > 1 or "INDETERMINATE" in lane_dirs

    if habitat_heterogeneous and lane_heterogeneous:
        regime = "HABITAT_AND_LANE_HETEROGENEITY_OBSERVED"
    elif habitat_heterogeneous:
        regime = "HABITAT_HETEROGENEITY_OBSERVED"
    elif lane_heterogeneous:
        regime = "LANE_HETEROGENEITY_OBSERVED"
    else:
        regime = "NO_GROUP_HETEROGENEITY_OBSERVED"

    nodes = {row["strategy"]: float(row["normalized_strength"]) for row in block["nodes"]}
    current_single_strength = nodes["ALLOC_SINGLE_CELL"]
    observed_pairs = int(block["observed_pairs"])

    weighted_identity = None
    if prior_strength is not None and prior_pairs is not None:
        recomputed = (
            float(prior_strength) * int(prior_pairs)
            + current_single_strength * observed_pairs
        ) / (int(prior_pairs) + observed_pairs)
        weighted_identity = {
            "prior_single_strength": float(prior_strength),
            "prior_observed_pairs": int(prior_pairs),
            "latest_single_strength": current_single_strength,
            "latest_observed_pairs": observed_pairs,
            "recomputed_pooled_single_strength": recomputed,
        }

    return {
        "schema": "missioncontrol.temporal_regression_diagnostic.v1",
        "task_class": task_class,
        "source_sha": pc3["source_sha"],
        "run_id": str(pc3["run_id"]),
        "observed_pairs": observed_pairs,
        "global_counts": dict(overall),
        "global_direction": _direction(overall),
        "global_single_normalized_strength": current_single_strength,
        "cells": rows,
        "by_habitat": habitat_rows,
        "by_lane": lane_rows,
        "regime": regime,
        "weighted_history_identity": weighted_identity,
        "authority_transfer": False,
        "competency_promotions": 0,
        "claim": "DIAGNOSTIC_ONLY_NO_CONTROL_CREDIT",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pc3", required=True)
    ap.add_argument("--task-class", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--prior-strength", type=float)
    ap.add_argument("--prior-pairs", type=int)
    args = ap.parse_args()

    pc3 = json.loads(Path(args.pc3).read_text(encoding="utf-8"))
    result = diagnose(pc3, args.task_class, args.prior_strength, args.prior_pairs)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS_TEMPORAL_REGRESSION_DIAGNOSTIC",
        "task_class": result["task_class"],
        "regime": result["regime"],
        "global_direction": result["global_direction"],
        "global_single_strength": result["global_single_normalized_strength"],
        "authority_transfer": False,
        "competency_promotions": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
