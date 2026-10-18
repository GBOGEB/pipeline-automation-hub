#!/usr/bin/env python3
"""JADE_CASTE governed stop controller: read-only, noncompensating, null-preserving.

The controller never dispatches, merges, releases, waives, or transfers authority.
Its plateau control halts only repetitive measurements, not release obligations.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

SHA40 = re.compile(r"^[0-9a-f]{40}$")
REQUIRED_GATES = ("source_integrity", "native_tests", "matched_coverage", "security", "independent_review",
                  "required_checks", "blocked_red_canary", "hosted_parity", "owner_release")
REQUIRED_METRICS = ("accepted_owner_actions", "deduplicated_owner_roots_closed",
                    "comparable_new_branches_covered", "new_evidence_edges_qualified")


def require(condition: bool, reason: str):
    if not condition:
        raise ValueError("JADE_STOP_FAIL_CLOSED: " + reason)


def comparable(a: dict, b: dict) -> bool:
    """Two pulses are matched ONLY when scope, instrumentor and source are pinned."""
    if any(a.get(k) != b.get(k) for k in ("cohort_sha", "eligible_denominator", "instrumentor", "scope")):
        return False
    if a.get("heads") != b.get("heads"):
        return False
    return isinstance(a.get("eligible_denominator"), int) and a["eligible_denominator"] > 0


def plateau(pulses: list[dict], window: int = 3) -> bool:
    """Three source-matched, terminal, zero-gain pulses stop redundant recensus."""
    if len(pulses) < window:
        return False
    last = pulses[-window:]
    for item in last:
        if item.get("native_state") != "TERMINAL" or item.get("pending_roots") != 0:
            return False
        if not all(isinstance(item.get("metrics", {}).get(k), int) for k in REQUIRED_METRICS):
            return False
        if not all(item["metrics"][k] >= 0 for k in REQUIRED_METRICS):
            return False
    return all(comparable(last[0], item) for item in last[1:]) and all(
        last[i]["metrics"] == last[0]["metrics"] for i in range(1, window)
    )


def evaluate(gates: dict, pulses: list[dict], current_first_red: list[dict],
             native_pending: bool, expected_head: str, release_repeat_proofs: list[dict]):
    """Noncompensating stop ladder; HOLD is never overwritten by statistical stability."""
    require(bool(SHA40.fullmatch(expected_head or "")), "invalid current exact head")
    require(set(gates) == set(REQUIRED_GATES), "incomplete or extra gate keys")
    require(all(x in ("PASS", "FAIL", "UNKNOWN", "PENDING", "MISSING") for x in gates.values()), "invalid gate state")
    require(isinstance(native_pending, bool), "pending must be boolean")
    require(isinstance(current_first_red, list), "first-red input must be list")
    require(isinstance(release_repeat_proofs, list), "replay proofs input must be list")
    for r in current_first_red:
        require(r.get("source_sha") == expected_head and r.get("owner") and r.get("url", "").startswith("https://github.com/"), "untrusted first red")
    for r in release_repeat_proofs:
        require(bool(SHA40.fullmatch(r.get("source_sha", ""))) and isinstance(r.get("run_id"), int)
                and r.get("conclusion") == "success", "untrusted repeat proof")
    distinct_proofs = len({(r["source_sha"], r["run_id"]) for r in release_repeat_proofs})
    accepted = (all(s == "PASS" for s in gates.values()) and not current_first_red
                and not native_pending and distinct_proofs >= 2)
    if accepted:
        return {"action": "TARGET_MET_STOP_ENGINEERING", "reason": "all noncompensating gates and independent repeat runs qualified", "merge_admission": "HOLD", "stop_repetitive_waves": True, "formal_release_credit": False, "owner_action": "Separate authorized owner acceptance still required"}
    if current_first_red:
        action, reason = "REPAIR_FIRST_RED", "source-bound current-head failure; do not repeat broad census"
    elif native_pending:
        action, reason = "WAIT_NATIVE", "exact-head native evidence pending; do not duplicate dispatch"
    elif any(gates[k] in ("FAIL", "MISSING") for k in ("security", "independent_review", "required_checks", "blocked_red_canary")):
        action, reason = "OWNER_BLOCKED", "independent governance blockers require owner action"
    elif plateau(pulses):
        action, reason = "PIVOT_DISJOINT_OWNER", "three comparable terminal zero-gain pulses; stop identical recensus only"
    else:
        action, reason = "CONTINUE_DISJOINT_MEASUREMENT", "progress gate still lacks independent source-bound proof"
    return {"action": action, "reason": reason, "merge_admission": "HOLD", "stop_repetitive_waves": action in ("WAIT_NATIVE", "OWNER_BLOCKED", "PIVOT_DISJOINT_OWNER"), "formal_release_credit": False, "owner_action": "Obtain outstanding native, protection and owner receipts"}


def from_snapshot(data: dict):
    require(data.get("schema") == "jade.temple.stopping_model.v2", "model schema")
    require(data.get("authority_transfer") is False and data.get("merge_admission") == "HOLD", "unsafe authority or admission")
    return evaluate(data["gates"], data["pulses"], data["first_red_current_head"],
                    data["native_pending"], data["current_main_sha"],
                    data["release_repeat_proofs"])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", default=str(Path(__file__).resolve().parents[1]/"data/STOP_MODEL_NPLUS2.json"))
    p.add_argument("--receipt")
    a = p.parse_args()
    model = json.loads(Path(a.model).read_text(encoding="utf-8"))
    report = {"schema": "jade.temple.stop_receipt.v2", "source_sha": model["current_main_sha"],
              "proof_level": "SOURCE_MODEL_REPLAY_ONLY", **from_snapshot(model)}
    s = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if a.receipt: Path(a.receipt).write_text(s, encoding="utf-8")
    print(s.strip())

if __name__ == "__main__": main()
