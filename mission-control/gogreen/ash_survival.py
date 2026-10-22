"""ASH survival control over existing CBD packets: plan, fail closed, learn.

What remains usable after a planned worker, receipt, or gate fails? This is a
read-only projection, NOT a dispatcher, mutation executor, scheduler or SSOT.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
from pathlib import Path
import sys

SOURCE = Path(__file__).with_name("subtype_orchestrator.py")
SPEC = importlib.util.spec_from_file_location("cbd_subtype_orchestrator", SOURCE)
assert SPEC and SPEC.loader
CBD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CBD)

SCHEMA = "missioncontrol.cbd.ash_survival_receipt.v1"


def analyze(payload: dict, simulated_loss: str | None = None) -> dict:
    """Derive an ASH receipt; never convert missing worker evidence into zero."""
    data = copy.deepcopy(payload)
    original = CBD.plan(data)
    if simulated_loss is not None:
        affected = [p for p in data["packets"] if p["id"] == simulated_loss]
        if len(affected) != 1 or affected[0]["state"] != "READY":
            raise ValueError("ASH loss must identify exactly one READY packet")
        worker = affected[0]
        worker["state"] = "BLOCKED"
        worker["blockers"] = ["ASH_SIMULATED_WORKER_LOSS"]
        worker["proof"] = None
        worker["independent_approval"] = False
        worker["accepted_root_ids"] = []
    after = CBD.plan(data)
    unknown_occurrence = sum(
        p.get("occurrence_count") is None for p in data["packets"]
    )
    unknown_fingerprints = sum(
        p.get("fingerprint_count") is None for p in data["packets"]
    )
    source_bound = [
        {"id": p["id"], "repo": p["repo"], "source_sha": p["source_sha"],
         "run_id": p["proof"]["run_id"], "run_attempt": p["proof"]["run_attempt"],
         "job_id": p["proof"]["job_id"], "archive_bytes_verified":
             p["proof"]["archive_bytes_verified"]}
        for p in data["packets"]
        if p.get("proof") is not None
    ]
    blocked_p0 = [
        p["id"] for p in data["packets"]
        if p["state"] == "BLOCKED" and p["priority"] == "P0"
    ]
    runner_proof = [
        r for r in source_bound if r["archive_bytes_verified"] is True
    ]
    if original.get("dispatch_authorized") is not False:
        raise ValueError("CBD dispatcher authority must remain false")
    if (after["dispatch_authorized"] is not False
            or after["merge_authorized"] is not False
            or after["security_waiver"] is not False
            or after["authority_transfer"] is not False):
        raise ValueError("ASH cannot transfer authority or bypass gates")
    return {
        "schema": SCHEMA,
        "cohort": data.get("cohort"),
        "observation_kind": (
            "SIMULATED_FAILURE_NOT_NATIVE_EXECUTION"
            if simulated_loss is not None else "SOURCE_BOUND_CONTROL_PROJECTION"
        ),
        "simulated_failed_packet_id": simulated_loss,
        "source_observed_at": data.get("observed_at"),
        "reused_scheduler": "mission-control/gogreen/subtype_orchestrator.py",
        "survival": {
            "state": (
                "PARTIAL_READ_ONLY_WITH_OWNER_HOLDS" if blocked_p0
                else "PROOF_PENDING_INDEPENDENT_ADMISSION"
            ),
            "ready_scouts_remaining": after["kpi"]["ready_now"],
            "waves_planned": after["schedule"]["waves_planned"],
            "packets_planned": after["schedule"]["packets_planned"],
            "planned_max_parallel": after["schedule"]["max_parallel"],
            "disjoint_path_conflicts_prevented":
                after["schedule"]["path_conflicts_prevented"],
            "native_proof_packets_still_present":
                after["kpi"]["source_bound_proof_packets"],
            "native_bytes_verified_packets":
                after["kpi"]["byte_verified_proof_packets"],
            "independently_accepted_root_closures":
                after["kpi"]["independently_accepted_root_closures"],
            "blocked_p0_packets": blocked_p0,
            "occurrence_counts_unknown_packets": unknown_occurrence,
            "fingerprint_counts_unknown_packets": unknown_fingerprints,
            "total_observed_occurrences_known_scope":
                after["kpi"]["occurrence_count_observed"],
            "worker_launches_observed": None,
            "runner_minutes_observed": None,
            "matched_coverage_uplift_pp": None,
            "remote_keb_qps_acceptance": None,
        },
        "recovery": {
            "read_only_scouts_remain_plan_eligible":
                after["kpi"]["ready_now"] > 0,
            "mutation_fanout_admitted": False,
            "fleet_or_crew_dispatched_by_this_adapter": False,
            "parent_action_required": (
                "RESOLVE_BLOCKED_P0_OWNER_GATES" if blocked_p0
                else "OBTAIN_EXACT_HEAD_AND_INDEPENDENT_NATIVE_PROOF"
            ),
            "retained_native_run_job_refs": source_bound,
            "independently_byte_verified_refs": runner_proof,
            "original_ready_scouts": original["kpi"]["ready_now"],
            "postfailure_ready_scouts": after["kpi"]["ready_now"],
        },
        "boundary": {
            "merge_admission": "HOLD",
            "security_waiver": False,
            "authority_transfer": False,
            "qps_engineering_acceptance": None,
            "crew_competence_from_packet_count": False,
            "proposed_worker_schedule_is_not_actual_worker_execution": True,
            "unverified_artifacts_cannot_grant_root_closure": True,
            "simulated_failure_cannot_cancel_a_native_runner": True,
        },
        "cbd_schedule": after["schedule"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--simulate-loss", default=None)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        receipt = analyze(payload, args.simulate_loss)
        raw = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
        if args.out is None:
            print(raw, end="")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(raw, encoding="utf-8")
        return 0
    except (ValueError, KeyError, TypeError, OSError) as err:
        print(f"CBD_ASH_FAIL_CLOSED: {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
