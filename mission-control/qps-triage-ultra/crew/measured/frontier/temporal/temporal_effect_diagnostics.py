#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

EPS = 1e-12


def _sign(value: float) -> int:
    if value > EPS:
        return 1
    if value < -EPS:
        return -1
    return 0


def signed_effect_from_single(single_strength: float) -> float:
    """Map single-cell normalized strength p in [0,1] to signed preference D in [-1,1]."""
    return 2.0 * float(single_strength) - 1.0


def winner_strength_from_signed(effect: float) -> float:
    """Return magnitude-only winner strength, 0.5 at parity and 1.0 at an extreme."""
    return 0.5 + abs(float(effect)) / 2.0


def _weighted_pool(records: list[dict]) -> tuple[float, float, int]:
    total_pairs = sum(int(r.get("observed_pairs", 0)) for r in records)
    if total_pairs <= 0:
        return 0.5, 0.0, 0
    pooled_single = sum(
        float(r["single_normalized_strength"]) * int(r.get("observed_pairs", 0)) for r in records
    ) / total_pairs
    return pooled_single, signed_effect_from_single(pooled_single), total_pairs


def _transition(previous_effect: float | None, current_effect: float) -> str:
    if previous_effect is None:
        return "INSUFFICIENT_HISTORY"
    ps, cs = _sign(previous_effect), _sign(current_effect)
    if ps and cs and ps != cs:
        return "AGGREGATE_DIRECTION_REVERSAL"
    previous_mag = abs(previous_effect)
    current_mag = abs(current_effect)
    if current_mag < previous_mag - EPS:
        return "ATTENUATING_TOWARD_PARITY"
    if current_mag > previous_mag + EPS:
        return "STRENGTHENING_AWAY_FROM_PARITY"
    return "STABLE_OR_FLAT"


def _direction(effect: float) -> str:
    if effect > EPS:
        return "ALLOC_SINGLE_CELL"
    if effect < -EPS:
        return "ALLOC_PAIRED_CELL"
    return "PARITY"


def diagnose_policy(receipt: dict, task_class: str, control_threshold: float) -> dict:
    policy = receipt["policies"][task_class]
    control = policy["control_frontier"]
    ids = {str(x) for x in control.get("window_ids", [])}
    records = [r for r in policy.get("window_evidence", []) if str(r.get("window_id")) in ids]
    records.sort(key=lambda r: (r.get("created_at", ""), int(r.get("window_id", 0))))

    pooled_single = float(control["pooled_single_strength"])
    current_effect = signed_effect_from_single(pooled_single)
    current_winner = float(control["pooled_winner_strength"])
    expected_winner = winner_strength_from_signed(current_effect)
    if not math.isclose(current_winner, expected_winner, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError(f"{task_class}: winner-strength/sign relation violated")

    previous_effect = None
    previous_winner = None
    if len(records) >= 2:
        _, previous_effect, _ = _weighted_pool(records[:-1])
        previous_winner = winner_strength_from_signed(previous_effect)

    per_window = []
    for row in records:
        effect = signed_effect_from_single(float(row["single_normalized_strength"]))
        per_window.append({
            "window_id": str(row["window_id"]),
            "created_at": row.get("created_at"),
            "observed_pairs": int(row.get("observed_pairs", 0)),
            "single_normalized_strength": float(row["single_normalized_strength"]),
            "signed_effect": effect,
            "effect_direction": _direction(effect),
            "effect_magnitude": abs(effect),
            "winner_strength_equivalent": winner_strength_from_signed(effect),
        })

    transition = _transition(previous_effect, current_effect)
    threshold_margin = current_winner - float(control_threshold)
    threshold_crossing = "NO_PREVIOUS_CUMULATIVE_STATE"
    if previous_winner is not None:
        before = previous_winner >= control_threshold
        now = current_winner >= control_threshold
        threshold_crossing = (
            "PASS_TO_FAIL" if before and not now else
            "FAIL_TO_PASS" if not before and now else
            "REMAINS_PASS" if before and now else
            "REMAINS_FAIL"
        )

    if transition == "ATTENUATING_TOWARD_PARITY":
        interpretation = (
            f"{task_class} has not reversed aggregate direction; its {_direction(current_effect)} advantage "
            "is temporally attenuating toward parity. The policy receipt alone cannot distinguish sampling "
            "variation from genuine effect decay or deblocking-driven convergence."
        )
    elif transition == "AGGREGATE_DIRECTION_REVERSAL":
        interpretation = (
            f"{task_class} shows an aggregate signed-effect reversal in the genuine scheduled CONTROL subset."
        )
    else:
        interpretation = (
            f"{task_class} aggregate signed effect is {_direction(current_effect)} with transition {transition}."
        )

    return {
        "task_class": task_class,
        "governed_clock_source": "GENUINE_SCHEDULED_CONTROL_FRONTIER_ONLY",
        "control_windows": int(control["independent_windows"]),
        "temporal_span_seconds": float(control["temporal_span_seconds"]),
        "pooled_single_strength": pooled_single,
        "signed_pooled_effect": current_effect,
        "effect_direction": _direction(current_effect),
        "effect_magnitude": abs(current_effect),
        "pooled_winner_strength": current_winner,
        "winner_excess_over_parity": current_winner - 0.5,
        "control_strength_threshold": float(control_threshold),
        "control_strength_margin": threshold_margin,
        "control_strength_gate": "PASS" if threshold_margin >= 0.0 else "FAIL",
        "previous_cumulative_signed_effect": previous_effect,
        "previous_cumulative_winner_strength": previous_winner,
        "latest_cumulative_transition": transition,
        "latest_cumulative_threshold_crossing": threshold_crossing,
        "aggregate_direction_reversed_since_previous_pulse": (
            previous_effect is not None and _sign(previous_effect) != 0 and _sign(current_effect) != 0
            and _sign(previous_effect) != _sign(current_effect)
        ),
        "per_window_signed_effect": per_window,
        "cause_disposition": "UNRESOLVED_FROM_BT_POLICY_RECEIPT_ALONE",
        "candidate_explanations": [
            "SAMPLING_OR_RUNTIME_VARIATION",
            "GENUINE_TEMPORAL_EFFECT_DECAY",
            "DEBLOCKING_DRIVEN_CONVERGENCE",
        ],
        "deblocking_identifiability": {
            "status": "REQUIRES_JOINT_COVARIATE_EVIDENCE",
            "required_covariates": [
                "queue_or_admission_pressure",
                "scarcity_or_contention",
                "runner_class",
                "lane",
                "source_sha",
                "time",
            ],
        },
        "pca_policy_relation": {
            "pca_loading_sign_is_not_policy_direction": True,
            "pca_polarity_enters_control_gate": False,
            "statement": (
                "CONTROL strength is Bradley-Terry derived. PCA component sign is orientation-indeterminate "
                "unless aligned across fits and cannot explain CONTROL loss by itself."
            ),
        },
        "interpretation": interpretation,
    }


def build_diagnostics(receipt: dict, config: dict) -> dict:
    if receipt.get("competency_promotions") != 0:
        raise ValueError("competency_promotions must remain zero")
    if receipt.get("authority_transfer") is not False:
        raise ValueError("authority_transfer must remain false")

    threshold = float(config["control_policy_gate"]["min_pooled_winner_strength"])
    classes = ["short_compute", "long_compute_contended"]
    rows = {name: diagnose_policy(receipt, name, threshold) for name in classes}
    control_ids = [str(x) for x in receipt.get("scheduled_control_frontier", {}).get("window_ids", [])]
    latest_control = None
    if control_ids:
        wanted = control_ids[-1]
        latest_control = next(
            (w for w in reversed(receipt.get("windows", [])) if str(w.get("window_id")) == wanted),
            None,
        )
    return {
        "schema": "missioncontrol.temporal_effect_diagnostics.v1",
        "source_sha": (latest_control or {}).get("source_sha") or receipt.get("source_sha"),
        "source_window_id": (latest_control or {}).get("window_id"),
        "source_window_event": (latest_control or {}).get("event"),
        "mission_id": receipt.get("mission_id"),
        "control_policy_thresholds_unchanged": True,
        "control_strength_threshold": threshold,
        "synthetic_or_noop_clock_evidence_admitted": False,
        "competency_promotions": 0,
        "authority_transfer": False,
        "diagnostics": rows,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    receipt = json.loads(Path(args.policy).read_text(encoding="utf-8"))
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    result = build_diagnostics(receipt, config)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
