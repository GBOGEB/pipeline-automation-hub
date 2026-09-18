#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


GATE_ORDER = (
    "independent_windows",
    "distinct_source_shas",
    "temporal_span_seconds",
    "directional_windows",
    "direction_consistency",
    "pooled_winner_strength",
    "latest_two_directional_windows_agree",
    "hosted_runner_classes",
    "baseline_and_held_lanes",
)


def _failed_gates(policy: dict, gate: dict) -> list[str]:
    control = policy.get("control_frontier", {})
    lanes = set(control.get("lanes", []))
    rows = {
        "independent_windows": int(control.get("independent_windows", 0)) >= int(gate["min_independent_windows"]),
        "distinct_source_shas": int(control.get("distinct_source_shas", 0)) >= int(gate["min_distinct_source_shas"]),
        "temporal_span_seconds": float(control.get("temporal_span_seconds", 0.0)) >= float(gate["min_temporal_span_seconds"]),
        "directional_windows": int(control.get("directional_windows", 0)) >= int(gate["min_directional_windows"]),
        "direction_consistency": float(control.get("direction_consistency", 0.0)) >= float(gate["min_direction_consistency"]),
        "pooled_winner_strength": float(control.get("pooled_winner_strength", 0.0)) >= float(gate["min_pooled_winner_strength"]),
        "latest_two_directional_windows_agree": (
            not gate.get("latest_two_directional_windows_must_agree", False)
            or bool(control.get("latest_two_directional_windows_agree", False))
        ),
        "hosted_runner_classes": len(control.get("hosted_runner_classes", [])) >= int(gate.get("min_hosted_runner_classes", 0)),
        "baseline_and_held_lanes": (
            not gate.get("requires_baseline_and_held_lanes", False)
            or {"baseline", "held"}.issubset(lanes)
        ),
    }
    return [name for name in GATE_ORDER if not rows[name]]


def _min_clean_dominant_windows(direction_counts: dict, dominant: str, threshold: float) -> int | None:
    if dominant == "INDETERMINATE":
        return None
    dominant_count = int(direction_counts.get(dominant, 0))
    total = sum(int(v) for v in direction_counts.values())
    if total <= 0:
        return None
    for extra in range(0, 10001):
        if (dominant_count + extra) / (total + extra) >= threshold:
            return extra
    raise ValueError("consistency target not reachable within bounded search")


def _regime_class(surveillance: dict) -> str:
    if surveillance.get("early_vs_late_direction_agreement") is False:
        return "REGIME_REVERSAL_OBSERVED"
    flips = int(surveillance.get("direction_flip_count", 0))
    indeterminate = surveillance.get("indeterminate_window_fraction")
    if flips >= 3 or (indeterminate is not None and float(indeterminate) >= 0.20):
        return "WEAK_OR_NOISY_DIRECTION"
    return "MARGIN_OR_SAMPLE_DEFICIT"


def _next_action(regime: str, task_class: str, regression_from_control: bool = False) -> str:
    if regression_from_control:
        return "DECOMPOSE_CONTROL_REGRESSION_AND_REEARN_FROZEN_GATE"
    if regime == "REGIME_REVERSAL_OBSERVED":
        return "DECOMPOSE_SIGNED_EFFECT_BY_RUNNER_LANE_AND_TEMPORAL_HALF"
    if task_class == "human_dependency_wait_proxy":
        return "KEEP_PROXY_CLAIM_BOUNDARY_AND_CONTINUE_GENUINE_SCHEDULED_STABILITY_MEASUREMENT"
    if regime == "WEAK_OR_NOISY_DIRECTION":
        return "CONTINUE_GENUINE_SCHEDULED_STABILITY_MEASUREMENT"
    return "CONTINUE_GENUINE_SCHEDULED_SURVEILLANCE"


def build_burndown(receipt: dict, config: dict, prior_acceptance: dict | None = None) -> dict:
    if receipt.get("authority_transfer") is not False:
        raise ValueError("authority_transfer must remain false")
    if receipt.get("competency_promotions") != 0:
        raise ValueError("competency_promotions must remain zero")

    gate = config["control_policy_gate"]
    surveillance = receipt.get("temporal_surveillance", {}).get("classes", {})
    policies = receipt["policies"]
    prior_control_classes = {
        row["task_class"]
        for row in (prior_acceptance or {}).get("control_classes", [])
        if row.get("policy_status") == "CONTROL_POLICY"
    }

    control_classes = sorted(
        name for name, policy in policies.items()
        if policy.get("policy_status") == "CONTROL_POLICY"
    )
    frontier = []
    for name, policy in policies.items():
        if policy.get("policy_status") == "CONTROL_POLICY":
            continue
        control = policy.get("control_frontier", {})
        direction_counts = control.get("direction_counts", {})
        dominant = control.get("dominant_direction", "INDETERMINATE")
        failed = _failed_gates(policy, gate)
        surv = surveillance.get(name, {})
        regression_from_control = name in prior_control_classes
        regime = "CONTROL_REGRESSION" if regression_from_control else _regime_class(surv)
        consistency = float(control.get("direction_consistency", 0.0))
        strength = float(control.get("pooled_winner_strength", 0.0))
        row = {
            "task_class": name,
            "policy_status": policy.get("policy_status"),
            "dominant_direction": dominant,
            "direction_counts": direction_counts,
            "directional_windows": int(control.get("directional_windows", 0)),
            "direction_consistency": consistency,
            "consistency_threshold": float(gate["min_direction_consistency"]),
            "consistency_deficit": max(0.0, float(gate["min_direction_consistency"]) - consistency),
            "min_consecutive_clean_dominant_windows_to_consistency": _min_clean_dominant_windows(
                direction_counts, dominant, float(gate["min_direction_consistency"])
            ),
            "pooled_winner_strength": strength,
            "winner_strength_threshold": float(gate["min_pooled_winner_strength"]),
            "winner_strength_deficit": max(0.0, float(gate["min_pooled_winner_strength"]) - strength),
            "latest_two_directional_windows_agree": bool(control.get("latest_two_directional_windows_agree", False)),
            "failed_control_gates": failed,
            "first_red_gate": failed[0] if failed else None,
            "surveillance": {
                "direction_flip_count": int(surv.get("direction_flip_count", 0)),
                "indeterminate_window_fraction": surv.get("indeterminate_window_fraction"),
                "early_direction": surv.get("early_direction"),
                "late_direction": surv.get("late_direction"),
                "early_vs_late_direction_agreement": surv.get("early_vs_late_direction_agreement"),
                "jackknife_min_pooled_winner_strength": (surv.get("jackknife") or {}).get("min_pooled_winner_strength"),
                "jackknife_direction_preservation_fraction": (surv.get("jackknife") or {}).get("direction_preservation_fraction"),
            },
            "regime_classification": regime,
            "regression_from_control": regression_from_control,
            "next_action": _next_action(regime, name, regression_from_control),
            "claim_boundary": (
                "CONTROLLED_WAIT_PROXY_ONLY_NOT_REAL_HUMAN_INTERVENTION_EVIDENCE"
                if name == "human_dependency_wait_proxy" else None
            ),
        }
        frontier.append(row)

    frontier.sort(
        key=lambda row: (
            0 if row["regression_from_control"] else 1 if row["regime_classification"] == "REGIME_REVERSAL_OBSERVED" else 2,
            -int(row["min_consecutive_clean_dominant_windows_to_consistency"] or 0),
            -float(row["winner_strength_deficit"]),
            row["task_class"],
        )
    )
    for idx, row in enumerate(frontier, 1):
        row["priority_rank"] = idx

    horizon = receipt.get("temporal_surveillance", {}).get("horizons", {})
    return {
        "schema": "missioncontrol.temporal_3pstar_mip_burndown.v1",
        "mission_id": receipt.get("mission_id"),
        "source": {
            "generated_at": receipt.get("generated_at"),
            "scheduled_control_frontier": receipt.get("scheduled_control_frontier"),
        },
        "three_p_star": {
            "refresh": "PASS_SOURCE_AND_FROZEN_GATES_BOUND",
            "probe": "PASS_CLASS_SPECIFIC_FIRST_REDS_AND_SURVEILLANCE_DECOMPOSED",
            "rank": "PASS_NONCONTROL_FRONTIER_ORDERED",
            "prepare": "PASS_DETERMINISTIC_BURNDOWN_CONTRACT",
            "prove": "REQUIRES_EXACT_HEAD_RUNTIME",
            "commit": "HOLD_UNTIL_EXACT_HEAD_RUNTIME_PASS",
            "propagate_perpetuate": "POSTMERGE_HANDOVER_AND_CURRENT_POINTER_REQUIRED",
        },
        "mip": {
            "modernize": "SEPARATE_REGIME_REVERSAL_FROM_WEAK_OR_NOISY_DIRECTION",
            "innovate": "ADD_CONSISTENCY_DEBT_AND_MINIMUM_CLEAN_WINDOW_PRESSURE",
            "perpetuate": "TRIGGER_ON_EACH_GENUINE_SCHEDULED_TEMPORAL_RETURN_AND_PERSIST_RESTART_CHAIN",
        },
        "control_classes": control_classes,
        "control_class_count": len(control_classes),
        "regression_classes": sorted(row["task_class"] for row in frontier if row["regression_from_control"]),
        "task_class_count": len(policies),
        "full_control_policy": len(control_classes) == len(policies),
        "active_frontier": frontier,
        "surveillance_horizons": horizon,
        "invariants": {
            "thresholds_changed": False,
            "synthetic_or_manual_clock_credit": False,
            "competency_promotions": 0,
            "authority_transfer": False,
            "persistent_or_regression_rex_veto_remains_authoritative": True,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--prior-acceptance")
    args = ap.parse_args()

    receipt = json.loads(Path(args.policy).read_text(encoding="utf-8"))
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    prior_acceptance = (
        json.loads(Path(args.prior_acceptance).read_text(encoding="utf-8"))
        if args.prior_acceptance else None
    )
    result = build_burndown(receipt, config, prior_acceptance)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS_TEMPORAL_3PSTAR_MIP_BURNDOWN",
        "control_classes": result["control_classes"],
        "regression_classes": result["regression_classes"],
        "frontier": [
            {
                "priority": row["priority_rank"],
                "task_class": row["task_class"],
                "first_red": row["first_red_gate"],
                "regime": row["regime_classification"],
                "min_clean_windows": row["min_consecutive_clean_dominant_windows_to_consistency"],
            }
            for row in result["active_frontier"]
        ],
        "authority_transfer": False,
        "competency_promotions": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
