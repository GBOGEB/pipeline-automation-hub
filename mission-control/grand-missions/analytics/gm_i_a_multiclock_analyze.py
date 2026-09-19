#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path

QUEUE_FEATURES = {
    "heavy_queue_seconds",
    "fast_queue_seconds",
    "dow_queue_seconds",
    "keb_queue_seconds",
}

def strongly_connected(nodes: list[str], edges: list[tuple[str, str]]) -> bool:
    if not nodes:
        return False
    graph = {n: set() for n in nodes}
    rev = {n: set() for n in nodes}
    for winner, loser in edges:
        graph[winner].add(loser)
        rev[loser].add(winner)

    def visit(g: dict[str, set[str]], start: str) -> set[str]:
        seen, stack = set(), [start]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(g[cur] - seen)
        return seen

    root = nodes[0]
    return len(visit(graph, root)) == len(nodes) and len(visit(rev, root)) == len(nodes)

def bidirectional_pairs(edges: list[tuple[str, str]]) -> int:
    directed = set(edges)
    seen = set()
    count = 0
    for a, b in directed:
        key = tuple(sorted((a, b)))
        if key in seen:
            continue
        seen.add(key)
        if (b, a) in directed:
            count += 1
    return count

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--append-row")
    ap.add_argument("--out", required=True)
    ap.add_argument("--pairs-out", required=True)
    ap.add_argument("--csv-out", required=True)
    ap.add_argument("--dataset-out")
    args = ap.parse_args()

    source = Path(args.input)
    raw = source.read_bytes()
    doc = json.loads(raw)
    features = list(doc["features"])
    rows = list(doc["rows"])
    if args.append_row:
        extra = json.loads(Path(args.append_row).read_text(encoding="utf-8"))
        rows.append(extra["row"] if "row" in extra else extra)

    if len(features) != 9 or len(set(features)) != len(features):
        raise SystemExit("FAIL expected nine unique multi-clock features")
    if set(QUEUE_FEATURES) - set(features):
        raise SystemExit("FAIL queue clock family incomplete")

    pulse_ids = set()
    for row in rows:
        pid = row.get("pulse_id")
        if not pid or pid in pulse_ids:
            raise SystemExit("FAIL missing or duplicate pulse_id")
        pulse_ids.add(pid)
        if row.get("evidence_class") != "MEASURED":
            raise SystemExit("FAIL non-MEASURED row")
        for f in features:
            value = row.get(f)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise SystemExit(f"FAIL nonnumeric feature {f} in {pid}")
            if not math.isfinite(float(value)) or value < 0:
                raise SystemExit(f"FAIL invalid duration {f} in {pid}")

    comparisons = []
    directed = []
    for row in rows:
        for a, b in itertools.combinations(features, 2):
            av, bv = float(row[a]), float(row[b])
            if av > bv:
                winner, loser, outcome = a, b, "A_GT_B"
                directed.append((a, b))
            elif bv > av:
                winner, loser, outcome = b, a, "B_GT_A"
                directed.append((b, a))
            else:
                winner = loser = None
                outcome = "TIE"
            comparisons.append({
                "pulse_id": row["pulse_id"],
                "objective": "RUNTIME_PRESSURE_LONGER_DURATION",
                "feature_a": a,
                "feature_b": b,
                "duration_a_seconds": av,
                "duration_b_seconds": bv,
                "winner": winner,
                "loser": loser,
                "outcome": outcome,
                "evidence_class": "DERIVED_FROM_MEASURED_DURATION",
                "eligible_for_intervention_bt": False
            })

    n, p = len(rows), len(features)
    min_pca_rows = max(10, 3 * p)
    varying = [f for f in features if len({float(row[f]) for row in rows}) > 1]
    covariance_rank_upper_bound = min(p, max(0, n - 1))
    pca_ready = n >= min_pca_rows and len(varying) >= 2

    bt_min_pulses = int(doc["bt_gate"]["minimum_repeat_pulses"])
    bt_graph_strong = strongly_connected(features, directed)
    reverse_pairs = bidirectional_pairs(directed)
    bt_ready = n >= bt_min_pulses and bt_graph_strong

    latest = rows[-1]
    duration_order = sorted(
        ({"feature": f, "seconds": float(latest[f])} for f in features),
        key=lambda x: x["seconds"],
        reverse=True,
    )
    queue_seconds = sum(float(latest[f]) for f in QUEUE_FEATURES)
    selected_total = sum(float(latest[f]) for f in features)
    nonqueue_seconds = selected_total - queue_seconds
    shares = [
        {
            "feature": item["feature"],
            "seconds": item["seconds"],
            "share": item["seconds"] / selected_total if selected_total else None,
            "family": "QUEUE" if item["feature"] in QUEUE_FEATURES else "WORK",
        }
        for item in duration_order
    ]
    hhi = sum((item["share"] or 0.0) ** 2 for item in shares)
    effective_clock_count = (1.0 / hhi) if hhi > 0 else None
    top4_fraction = (
        sum(item["seconds"] for item in duration_order[:4]) / selected_total
        if selected_total else None
    )

    expanded_doc = dict(doc)
    expanded_doc["rows"] = rows
    expanded_raw = (json.dumps(expanded_doc, indent=2, sort_keys=True) + "\n").encode("utf-8")

    readiness = {
        "schema": "missioncontrol.gm_i_a.multiclock_readiness.v2",
        "dataset_sha256": hashlib.sha256(expanded_raw).hexdigest(),
        "mission": doc["mission"],
        "row_evidence_class": "MEASURED",
        "measured_pulses": n,
        "features": features,
        "feature_count_p": p,
        "p_over_n": p / n,
        "pca": {
            "status": "READY_FOR_GG_MATH_PROVIDER_FIT" if pca_ready else "DEFER_INSUFFICIENT_COMPARABLE_MEASURED_PULSES",
            "minimum_rule": "n >= max(10, 3*p)",
            "minimum_rows_required": min_pca_rows,
            "rows_remaining_to_minimum": max(0, min_pca_rows - n),
            "varying_features": varying,
            "covariance_rank_upper_bound": covariance_rank_upper_bound,
            "standardization": "sample_z_score_after_gate",
            "synthetic_rows": 0,
            "expert_seeded_rows": 0
        },
        "bt_reverse_pressure": {
            "status": "READY_FOR_GG_MATH_PROVIDER_FIT" if bt_ready else "DEFER_NO_FINITE_MLE_REPEAT_STRUCTURE",
            "model_family": "Bradley-Terry",
            "comparison_semantics": "longer measured duration wins runtime-pressure comparison",
            "pair_records": len(comparisons),
            "strict_pair_records": len(directed),
            "minimum_repeat_pulses": bt_min_pulses,
            "repeat_pulses_remaining": max(0, bt_min_pulses - n),
            "directed_win_graph_strongly_connected": bt_graph_strong,
            "bidirectional_pair_count": reverse_pairs,
            "unordered_pair_count": p * (p - 1) // 2,
            "intervention_bt_credit": False
        },
        "latest_pulse_descriptive_pressure": {
            "pulse_id": latest["pulse_id"],
            "order": duration_order,
            "shares": shares,
            "classification": "MEASURED_DURATION_ORDER_NOT_BT_FIT",
            "selected_clock_seconds": selected_total,
            "queue_seconds": queue_seconds,
            "nonqueue_seconds": nonqueue_seconds,
            "queue_fraction": queue_seconds / selected_total if selected_total else None,
            "queue_to_nonqueue_ratio": queue_seconds / nonqueue_seconds if nonqueue_seconds else None,
            "pressure_hhi": hhi,
            "effective_clock_count": effective_clock_count,
            "top4_fraction": top4_fraction
        },
        "improvement_interpretation": {
            "queue_exposure_dominates": (queue_seconds / selected_total) > 0.5 if selected_total else False,
            "concentration_note": "HHI and top4_fraction are descriptive concentration diagnostics, not causal attribution.",
            "routing_note": "Use repeated exact pulses to distinguish persistent queue pressure from one-wave scheduling coincidence."
        },
        "interpretation_guards": [
            "QUEUE_AND_EXECUTION_ARE_SEPARATE_AXES",
            "SELECTED_CLOCK_SUM_IS_PRESSURE_EXPOSURE_NOT_END_TO_END_WALL_TIME",
            "PCA_LOADINGS_ARE_STRUCTURE_NOT_CAUSALITY",
            "BT_DURATION_PAIRS_ARE_PRESSURE_COMPARISONS_NOT_INTERVENTION_SUPERIORITY",
            "NO_ENGINEERING_HEPAK_QEQ_AUTHORITY_TRANSFER"
        ],
        "next_measurement_target": {
            "minimum_pca_rows": min_pca_rows,
            "minimum_bt_repeat_pulses": bt_min_pulses,
            "priority": "REPEAT_SAME_NINE_CLOCK_VECTOR_WITH_EXACT_RUN_JOB_ARTIFACT_BINDING"
        },
        "authority_transfer": False,
        "formal_credit_delta": 0
    }

    Path(args.out).write_text(json.dumps(readiness, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    Path(args.pairs_out).write_text(json.dumps({
        "schema": "missioncontrol.gm_i_a.runtime_pressure_pairs.v2",
        "comparisons": comparisons,
        "authority_transfer": False
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with Path(args.csv_out).open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["pulse_id", *features])
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row[k] for k in writer.fieldnames})

    if args.dataset_out:
        Path(args.dataset_out).write_bytes(expanded_raw)

    print(json.dumps(readiness, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
