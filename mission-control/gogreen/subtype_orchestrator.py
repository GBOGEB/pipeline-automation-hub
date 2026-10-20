"""Subtype-aware CBD work-packet planner for Mission Control.

Plans disjoint evidence/repair packets and deterministic KPI receipts.
It never dispatches remote workers, merges code, grants a security waiver,
or transfers repository authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

SCHEMA = "missioncontrol.cbd-subtype-plan.v1"
RECEIPT = "missioncontrol.cbd-subtype-receipt.v1"
SHA = re.compile(r"^[0-9a-f]{40}$")
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
PRIORITY = {"P0": 0, "P1": 1, "P2": 2}
CATEGORY = {
    "GOVERNANCE": 0,
    "SECURITY": 1,
    "COMPATIBILITY": 2,
    "COVERAGE": 3,
    "EVIDENCE": 4,
    "FEDERATION": 5,
    "STATISTICS": 6,
}
STATES = {"BLOCKED", "READY", "ACTIVE", "PROOF_PENDING", "VERIFIED"}
MODES = {"READ_ONLY_ANALYZE", "MUTATING_REPAIR", "NATIVE_PROVE", "CONTROL"}
PHASES = {"DISCOVER", "ANALYZE", "REPAIR", "PROVE", "CONTROL"}


def _positive(value, field):
    if type(value) is not int or value < 1:
        raise ValueError(f"invalid {field}")
    return value


def _count(value, field):
    if value is None:
        return None
    if type(value) is not int or value < 0:
        raise ValueError(f"invalid {field}")
    return value


def _strings(value, field):
    if not isinstance(value, list) or any(not isinstance(x, str) or not x for x in value):
        raise ValueError(f"invalid {field}")
    if len(value) != len(set(value)):
        raise ValueError(f"duplicate {field}")
    return value


def _validate_path_lease(value):
    """Enforce canonical repo-relative POSIX leases before cross-worker comparison."""
    if (not isinstance(value, str) or not value or len(value) > 1024
            or value.startswith("/") or "\\" in value or "\x00" in value
            or re.match(r"^[A-Za-z]:", value)):
        raise ValueError("unsafe mutation path lease")
    segments = value.split("/")
    if any(part in ("", ".", "..", ".git") for part in segments):
        raise ValueError("unsafe mutation path lease")
    return value


def _validate_proof(proof, source_sha):
    if proof is None:
        return None
    if not isinstance(proof, dict):
        raise ValueError("invalid proof")
    if proof.get("source_sha") != source_sha:
        raise ValueError("proof source mismatch")
    _positive(proof.get("run_id"), "run_id")
    _positive(proof.get("run_attempt"), "run_attempt")
    _positive(proof.get("job_id"), "job_id")
    if proof.get("conclusion") not in {"PASS", "FAIL"}:
        raise ValueError("invalid proof conclusion")
    artifact_id = proof.get("artifact_id")
    if artifact_id is not None:
        _positive(artifact_id, "artifact_id")
    if proof.get("archive_bytes_verified") is not None and type(proof.get("archive_bytes_verified")) is not bool:
        raise ValueError("invalid byte-verification state")
    return proof


def validate(data):
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise ValueError("schema")
    if data.get("authority_transfer") is not False:
        raise ValueError("authority boundary")
    max_parallel = _positive(data.get("max_parallel"), "max_parallel")
    if max_parallel > 16:
        raise ValueError("unsafe parallelism")
    packets = data.get("packets")
    if not isinstance(packets, list) or not packets:
        raise ValueError("packets")
    ids = set()
    for packet in packets:
        pid = packet.get("id")
        if not isinstance(pid, str) or not pid or pid in ids:
            raise ValueError("packet identity")
        ids.add(pid)
        if packet.get("category") not in CATEGORY:
            raise ValueError("category")
        if not isinstance(packet.get("subtype"), str) or not packet["subtype"]:
            raise ValueError("subtype")
        if packet.get("priority") not in PRIORITY:
            raise ValueError("priority")
        if packet.get("state") not in STATES:
            raise ValueError("state")
        if packet.get("mode") not in MODES:
            raise ValueError("mode")
        if packet.get("phase") not in PHASES:
            raise ValueError("phase")
        if (not isinstance(packet.get("repo"), str)
                or not REPO.fullmatch(packet["repo"])
                or any(part in {".", ".."} for part in packet["repo"].split("/"))):
            raise ValueError("repo")
        if not isinstance(packet.get("source_sha"), str) or not SHA.fullmatch(packet["source_sha"]):
            raise ValueError("source_sha")
        _positive(packet.get("owner_issue"), "owner_issue")
        paths = _strings(packet.get("mutation_paths", []), "mutation_paths")
        for lease in paths:
            _validate_path_lease(lease)
        blockers = _strings(packet.get("blockers", []), "blockers")
        if packet["mode"] == "MUTATING_REPAIR" and not paths:
            raise ValueError("mutating repair requires path lease")
        if packet["state"] == "BLOCKED" and not blockers:
            raise ValueError("blocked packet requires blocker")
        if packet["state"] == "READY" and blockers:
            raise ValueError("ready packet cannot have blockers")
        if not isinstance(packet.get("success_predicate"), str) or not packet["success_predicate"]:
            raise ValueError("success_predicate")
        _count(packet.get("occurrence_count"), "occurrence_count")
        _count(packet.get("fingerprint_count"), "fingerprint_count")
        _validate_proof(packet.get("proof"), packet["source_sha"])
        approved = packet.get("independent_approval")
        if approved is not None and type(approved) is not bool:
            raise ValueError("independent_approval")
        roots = _strings(packet.get("accepted_root_ids", []), "accepted_root_ids")
        if roots:
            # This read-only planner accepts caller-supplied JSON, not a signed
            # independent approval channel. Even PASS + approval=true is merely
            # a claim; accepting it would fabricate causal-root closure.
            raise ValueError("untrusted accepted root closure requires authenticated independent channel")
    return data


def _conflicts(a, b):
    if a["repo"] != b["repo"]:
        return False
    for first in a["mutation_paths"]:
        for second in b["mutation_paths"]:
            if (first == second or first.startswith(second + "/")
                    or second.startswith(first + "/")):
                return True
    return False


def _rank(packet):
    return (
        PRIORITY[packet["priority"]],
        CATEGORY[packet["category"]],
        packet["subtype"],
        packet["id"],
    )


def _packet_view(packet):
    return {
        "id": packet["id"],
        "category": packet["category"],
        "subtype": packet["subtype"],
        "priority": packet["priority"],
        "phase": packet["phase"],
        "mode": packet["mode"],
        "repo": packet["repo"],
        "source_sha": packet["source_sha"],
        "owner_issue": packet["owner_issue"],
        "mutation_paths": packet["mutation_paths"],
        "success_predicate": packet["success_predicate"],
    }


def plan(data):
    validate(data)
    packets = sorted(data["packets"], key=_rank)
    runnable = [p for p in packets if p["state"] == "READY"]
    waves, pending, conflicts_prevented = [], list(runnable), 0
    while pending:
        wave, deferred = [], []
        for packet in pending:
            has_conflict = any(_conflicts(packet, other) for other in wave)
            if len(wave) >= data["max_parallel"] or has_conflict:
                if has_conflict:
                    conflicts_prevented += 1
                deferred.append(packet)
                continue
            wave.append(packet)
        if not wave:
            raise ValueError("unable to schedule packets")
        waves.append([_packet_view(p) for p in wave])
        pending = deferred

    by_category = {}
    by_subtype = {}
    for packet in packets:
        cat = by_category.setdefault(
            packet["category"], {"total": 0, "ready": 0, "blocked": 0, "verified": 0}
        )
        cat["total"] += 1
        cat["ready"] += int(packet["state"] == "READY")
        cat["blocked"] += int(packet["state"] == "BLOCKED")
        cat["verified"] += int(packet["state"] == "VERIFIED")
        key = f'{packet["category"]}:{packet["subtype"]}'
        by_subtype[key] = by_subtype.get(key, 0) + 1

    proof_bound = sum(
        1
        for p in packets
        if p.get("proof")
        and p["proof"]["source_sha"] == p["source_sha"]
        and p["proof"].get("run_id")
        and p["proof"].get("job_id")
    )
    byte_verified = sum(
        1 for p in packets if p.get("proof") and p["proof"].get("archive_bytes_verified") is True
    )
    occurrence_total = sum(p.get("occurrence_count") or 0 for p in packets)
    fingerprint_total = sum(p.get("fingerprint_count") or 0 for p in packets)
    accepted_roots = sorted({rid for p in packets for rid in p.get("accepted_root_ids", [])})

    return {
        "schema": RECEIPT,
        "cohort": data.get("cohort"),
        "source_observed_at": data.get("observed_at"),
        "authority_transfer": False,
        "dispatch_authorized": False,
        "merge_authorized": False,
        "security_waiver": False,
        "qps_disposition": "DEFER",
        "schedule": {
            "max_parallel": data["max_parallel"],
            "waves_planned": len(waves),
            "packets_planned": len(runnable),
            "path_conflicts_prevented": conflicts_prevented,
            "waves": waves,
        },
        "kpi": {
            "packets_total": len(packets),
            "ready_now": sum(p["state"] == "READY" for p in packets),
            "blocked": sum(p["state"] == "BLOCKED" for p in packets),
            "active": sum(p["state"] == "ACTIVE" for p in packets),
            "proof_pending": sum(p["state"] == "PROOF_PENDING" for p in packets),
            "verified": sum(p["state"] == "VERIFIED" for p in packets),
            "source_bound_proof_packets": proof_bound,
            "byte_verified_proof_packets": byte_verified,
            "occurrence_count_observed": occurrence_total,
            "fingerprint_count_observed": fingerprint_total,
            "independently_accepted_root_closures": len(accepted_roots),
            "accepted_root_ids": accepted_roots,
            "worker_minutes_observed": None,
            "real_worker_capacity": None,
            "throughput_prediction": None,
            "matched_coverage_uplift_pp": None,
            "m2_ready": False,
            "m3_ready": False,
            "pca_ready": False,
            "bt_ready": False,
        },
        "by_category": by_category,
        "by_subtype": by_subtype,
        "blocked_packets": [
            {"id": p["id"], "blockers": p["blockers"], "owner_issue": p["owner_issue"]}
            for p in packets
            if p["state"] == "BLOCKED"
        ],
        "measurement_boundaries": {
            "occurrences_are_not_causal_roots": True,
            "planned_workers_are_not_launched_workers": True,
            "proof_without_independent_approval_is_not_root_closure": True,
            "caller_asserted_approval_is_not_trusted_root_closure": True,
            "source_bound_proof_counts_are_unverified_claims": True,
            "cross_head_metrics_are_not_coverage_uplift": True,
        },
    }


def emit(receipt, out):
    out.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode()
    digest = hashlib.sha256(raw).hexdigest()
    (out / "subtype_receipt.json").write_bytes(raw)
    (out / "subtype_receipt.sha256").write_text(digest + "\n", encoding="ascii")
    lines = [
        "# CBD subtype worker roll-up",
        "",
        "| Category | Total | Ready | Blocked | Verified |",
        "|---|---:|---:|---:|---:|",
    ]
    for category, row in sorted(receipt["by_category"].items(), key=lambda x: CATEGORY[x[0]]):
        lines.append(
            f"| {category} | {row['total']} | {row['ready']} | {row['blocked']} | {row['verified']} |"
        )
    kpi = receipt["kpi"]
    lines += [
        "",
        (
            f"Planned packets: {receipt['schedule']['packets_planned']} across "
            f"{receipt['schedule']['waves_planned']} wave(s), max parallel "
            f"{receipt['schedule']['max_parallel']}."
        ),
        (
            f"Observed occurrences: {kpi['occurrence_count_observed']}; fingerprints: "
            f"{kpi['fingerprint_count_observed']}; independently accepted causal-root "
            f"closures: {kpi['independently_accepted_root_closures']}."
        ),
        (
            "Worker-hours/capacity, matched coverage uplift, M2/M3 and PCA/BT remain "
            "UNKNOWN/HOLD unless independently supplied."
        ),
        "",
        f"SHA-256: {digest}",
        "",
    ]
    (out / "subtype_receipt.md").write_text("\n".join(lines), encoding="utf-8")
    return digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    receipt = plan(json.loads(args.input.read_text(encoding="utf-8")))
    digest = emit(receipt, args.out)
    print(
        json.dumps(
            {
                "packets": receipt["kpi"]["packets_total"],
                "ready": receipt["kpi"]["ready_now"],
                "blocked": receipt["kpi"]["blocked"],
                "waves": receipt["schedule"]["waves_planned"],
                "accepted_root_closures": receipt["kpi"]["independently_accepted_root_closures"],
                "sha256": digest,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
