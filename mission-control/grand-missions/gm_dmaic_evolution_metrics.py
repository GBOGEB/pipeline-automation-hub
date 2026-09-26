#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path

def fail(msg: str) -> None:
    raise SystemExit("GM_DMAIC_EVOLUTION_FAIL: " + msg)

def cohort_sets(doc: dict):
    t7 = list(doc["cohorts"]["top7"])
    e14 = list(doc["cohorts"]["top14_extension"])
    e21 = list(doc["cohorts"]["top21_extension"])
    t14 = t7 + e14
    t21 = t14 + e21
    if len(t7) != 7 or len(t14) != 14 or len(t21) != 21:
        fail("cohort sizes must be exactly 7/14/21")
    if len(set(t21)) != 21:
        fail("all Top21 repositories must be unique")
    return t7, t14, t21

def evaluate(doc: dict) -> dict:
    if doc.get("authority_transfer") is not False:
        fail("authority_transfer must remain false")
    if doc.get("formal_credit_delta") != 0 or doc.get("engineering_credit_delta") != 0:
        fail("credit deltas must remain zero")
    t7, t14, t21 = cohort_sets(doc)
    cur = doc["current"]
    g714 = doc["promotion_gates"]["top7_to_top14"]
    g1421 = doc["promotion_gates"]["top14_to_top21"]

    evo = doc["iteration_evolution"]
    repeat = cur.get("max_unchanged_root_auto_repeat_after_control")
    repeat_ok_714 = repeat is not None and repeat <= g714["unchanged_root_auto_repeat_max"]
    repeat_ok_1421 = repeat is not None and repeat <= g1421["unchanged_root_auto_repeat_max"]
    chain_ok = evo.get("iteration_chain_integrity") is True
    recursive_handoffs = int(evo.get("recursive_control_handoff_count", 0))

    top14_ready = (
        cur.get("top7_classified_observed", 0) >= g714["classified_min"]
        and cur.get("top7_green_control_observed", 0) >= g714["green_control_min"]
        and cur.get("top7_unclassified_observed", 999) <= g714["unclassified_max"]
        and cur.get("mission_era_full_dmaic_iterations", 0) >= g714["full_dmaic_iterations_min"]
        and cur.get("abacus", {}).get("d1", {}).get("state") == "CONTROL_AND_FRESH_HEAD_RECENSUS"
        and cur.get("top7_proof_debt_two_pulse_nonincreasing") is True
        and repeat_ok_714
        and chain_ok
        and recursive_handoffs >= g714["recursive_control_handoff_min"]
    )

    proof_debt = cur.get("top14_proof_debt_observed")
    top21_ready = (
        cur.get("top14_classified_observed", 0) >= g1421["classified_min"]
        and cur.get("top14_green_control_observed", 0) >= g1421["green_control_min"]
        and cur.get("top14_unclassified_observed", 999) <= g1421["unclassified_max"]
        and proof_debt is not None and proof_debt <= g1421["proof_debt_max"]
        and cur.get("mission_era_distinct_repos_full_dmaic", 0) >= g1421["full_dmaic_iterations_distinct_repos_min"]
        and cur.get("recurrent_controls_with_distinct_source_repeat", 0) >= g1421["recurrent_control_distinct_source_repeat_min"]
        and cur.get("top14_two_pulse_net_semantic_delta_le_zero") is True
        and cur.get("top14_two_pulse_proof_yield_nondegrading") is True
        and repeat_ok_1421
        and chain_ok
        and recursive_handoffs >= g1421["recursive_control_handoff_min"]
    )
    return {
        "mission_id": doc["mission_id"],
        "cohort_sizes": {"top7": len(t7), "top14": len(t14), "top21": len(t21)},
        "top14_promotion_ready": top14_ready,
        "top21_promotion_ready": top21_ready,
        "declared_states": {
            "top7": cur["top7_state"],
            "top14": cur["top14_state"],
            "top21": cur["top21_state"],
        },
        "abacus_depth": {
            "d1": cur["abacus"]["d1"]["state"],
            "d2": cur["abacus"]["d2"]["state"],
            "d3": cur["abacus"]["d3"]["state"],
        },
        "iteration_evolution": {
            "current_level": evo["current_level"],
            "complete_iteration_count": int(evo.get("complete_iteration_count", 0)),
            "recursive_control_handoff_count": recursive_handoffs,
            "iteration_chain_integrity": chain_ok,
            "active_iteration": evo.get("active_iteration", {}).get("iteration_id"),
        },
        "fail_closed": {
            "proof_debt_unknown_blocks_top21": proof_debt is None,
            "unknown_repeat_metric_blocks_promotion": repeat is None,
            "missing_evidence_is_not_green": True,
        },
    }

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contract", required=True)
    ap.add_argument("--out")
    args = ap.parse_args()
    doc = json.loads(Path(args.contract).read_text(encoding="utf-8"))
    result = evaluate(doc)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
