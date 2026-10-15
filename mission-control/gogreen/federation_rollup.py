"""Read-only, six-repo GOGREEN/MissionControl pulse roll-up.

Reports *discoverability* separately from native quality and from admission.
No network, runtime dispatch, worker scheduling or authority transfer.
Two non-atomic API snapshots cannot establish throughput or causality.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

SCHEMA = "gogreen.federation.pulse.v1"
OUT_SCHEMA = "gogreen.federation.rollup.v1"
SURFACES = (
    "MISSION_CONTROL", "MIP", "DMAIC", "PCA", "REX", "LDAB", "LLDB",
    "CENSUS", "3PSTAR", "GOGREEN", "QPS_TRIAGE",
)
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA = re.compile(r"^[a-f0-9]{40}$")
DIGEST = re.compile(r"^[a-f0-9]{64}$")
SOURCE_STATES = ("UNKNOWN", "SOURCE_DISCOVERED", "NATIVE_STATUS", "VERIFIED_BYTES")
CLOCK_STATES = ("OBSERVED", "UNAVAILABLE")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def utc(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("timestamp must be UTC ISO8601 Z")
    try:
        stamp = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("invalid UTC timestamp") from exc
    if stamp.utcoffset() != dt.timedelta(0):
        raise ValueError("timestamp not UTC")
    return stamp


def exact_int(value, name):
    if type(value) is not int or value < 0:
        raise ValueError(name + " must be nonnegative int, not bool")
    return value


def check_receipt(receipt, repo, sha, name):
    if not isinstance(receipt, dict):
        raise ValueError("nonempty native receipt required")
    if receipt.get("repository") != repo or receipt.get("sha") != sha:
        raise ValueError("native receipt source mismatch")
    for key in ("run_id", "job_id", "attempt"):
        if exact_int(receipt.get(key), key) == 0:
            raise ValueError(key + " must be positive")
    if receipt.get("status") != "completed" or receipt.get("conclusion") != "success":
        raise ValueError("native evidence must be terminal success")
    if receipt.get("surface") != name:
        raise ValueError("native receipt surface mismatch")


def validate(raw):
    if not isinstance(raw, dict) or raw.get("schema") != SCHEMA:
        raise ValueError("invalid pulse schema")
    if not isinstance(raw.get("pulse_id"), str) or not raw["pulse_id"]:
        raise ValueError("pulse_id required")
    observed = utc(raw.get("observed_at_utc"))
    entries = raw.get("repositories")
    if not isinstance(entries, list) or not entries:
        raise ValueError("repository array required")
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("invalid repository entry")
        repo, sha = entry.get("repository"), entry.get("sha")
        if not isinstance(repo, str) or not REPO.fullmatch(repo) or repo in seen:
            raise ValueError("invalid/duplicated repo")
        seen.add(repo)
        if not isinstance(sha, str) or not SHA.fullmatch(sha):
            raise ValueError("invalid source SHA")
        if not (type(entry.get("branch_protected")) is bool or entry.get("branch_protected") == "UNKNOWN"):
            raise ValueError("branch_protected must be boolean or UNKNOWN")
        q = entry.get("queue")
        if not isinstance(q, dict) or q.get("state") not in CLOCK_STATES:
            raise ValueError("queue state missing")
        if q["state"] == "OBSERVED":
            stamp = utc(q.get("observed_at_utc"))
            if stamp > observed:
                raise ValueError("future sample relative to pulse")
            exact_int(q.get("queued"), "queued")
            exact_int(q.get("in_progress"), "in_progress")
        elif q.get("queued") is not None or q.get("in_progress") is not None:
            raise ValueError("UNAVAILABLE queue must not encode 0")
        surfaces = entry.get("surfaces")
        if not isinstance(surfaces, dict) or set(surfaces) != set(SURFACES):
            raise ValueError("complete named surface coordinates required")
        for name, surface in surfaces.items():
            if not isinstance(surface, dict) or surface.get("state") not in SOURCE_STATES:
                raise ValueError("invalid source surface")
            state = surface["state"]
            if state == "UNKNOWN":
                if surface.get("path") is not None or surface.get("receipt") is not None:
                    raise ValueError("UNKNOWN surface may not claim path or proof")
                continue
            if not isinstance(surface.get("path"), str) or not surface["path"] or surface["path"].startswith("/") or ".." in surface["path"].split("/"):
                raise ValueError("source discovery requires safe repository relative path")
            if state in ("NATIVE_STATUS", "VERIFIED_BYTES"):
                check_receipt(surface.get("receipt"), repo, sha, name)
            elif surface.get("receipt") is not None:
                raise ValueError("discovery does not imply native job")
            if state == "VERIFIED_BYTES":
                digest = surface["receipt"].get("artifact_sha256")
                if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
                    raise ValueError("bytes require verified artifact sha256")
                if surface["receipt"].get("independent_byte_verifier") is not True:
                    raise ValueError("bytes require independent verifier")
    if raw.get("authority_transfer") is not False or raw.get("merge_authorized") is not False:
        raise ValueError("authority must remain false")
    return entries


def _dimensions(entries):
    discovered, native, bytes_proven = [], [], []
    by_surface = {}
    for name in SURFACES:
        cells = [(e["repository"], e["surfaces"][name]["state"]) for e in entries]
        vals = Counter(state for _, state in cells)
        by_surface[name] = {
            "target_cells": len(entries),
            "source_discovered": sum(vals[s] for s in SOURCE_STATES if s != "UNKNOWN"),
            "native_status_verified": vals["NATIVE_STATUS"] + vals["VERIFIED_BYTES"],
            "artifact_bytes_verified": vals["VERIFIED_BYTES"],
            "unknown": vals["UNKNOWN"],
        }
        for repo, state in cells:
            if state != "UNKNOWN":
                discovered.append((repo, name))
            if state in ("NATIVE_STATUS", "VERIFIED_BYTES"):
                native.append((repo, name))
            if state == "VERIFIED_BYTES":
                bytes_proven.append((repo, name))
    return {"by_surface": by_surface, "source_discovered": discovered,
            "native_status_verified": native, "artifact_bytes_verified": bytes_proven}


def build(current, previous=None):
    entries = validate(current)
    if previous is not None:
        old_entries = validate(previous)
        if utc(previous["observed_at_utc"]) >= utc(current["observed_at_utc"]):
            raise ValueError("pulse time must increase")
        if current["pulse_id"] == previous["pulse_id"]:
            raise ValueError("pulse ID must change")
    else:
        old_entries = []
    dim = _dimensions(entries)
    total = len(entries) * len(SURFACES)
    queue_records = {e["repository"]: e["queue"] for e in entries}
    complete = all(q["state"] == "OBSERVED" for q in queue_records.values())
    fleet_queued = sum(q["queued"] for q in queue_records.values()) if complete else None
    fleet_running = sum(q["in_progress"] for q in queue_records.values()) if complete else None
    older = {e["repository"]: e for e in old_entries}
    transitions = []
    for e in entries:
        repo = e["repository"]
        prev = older.get(repo)
        same = prev is not None and prev["sha"] == e["sha"]
        before_q = prev["queue"] if same else None
        next_q = e["queue"]
        compare_q = bool(before_q and before_q["state"] == next_q["state"] == "OBSERVED")
        transitions.append({
            "repository": repo,
            "previous_sha": prev["sha"] if prev else None,
            "sha": e["sha"], "same_source_sha": same if prev else None,
            "queued_before": before_q["queued"] if compare_q else None,
            "queued_after": next_q["queued"] if next_q["state"] == "OBSERVED" else None,
            "queued_change": next_q["queued"] - before_q["queued"] if compare_q else None,
            "queue_delta_state": "DESCRIPTIVE_NOT_CAUSAL" if compare_q else "UNKNOWN",
            "matched_coverage_delta": None,
            "root_closures_verified": None,
            "arrival_count": None,
            "completion_count": None,
            "cancellation_count": None,
        })
    n_native = len(dim["native_status_verified"])
    bysurface = dim.pop("by_surface")
    stats = {
        "repositories": len(entries), "target_repo_surface_cells": total,
        "source_discovered_cells": len(dim["source_discovered"]),
        "native_status_verified_cells": n_native,
        "artifact_bytes_verified_cells": len(dim["artifact_bytes_verified"]),
        "unknown_cells": total - len(dim["source_discovered"]),
        "source_discovery_breadth_pct": round(100 * len(dim["source_discovered"]) / total, 2),
        "native_verification_depth_pct": round(100 * n_native / total, 2),
        "fleet_queued_observed_sum": fleet_queued,
        "fleet_in_progress_observed_sum": fleet_running,
        "queue_measurement_state": "OBSERVED_NONATOMIC" if complete else "INCOMPLETE",
        "independent_cycles": None,
        "source_matched_test_coverage_gain": None,
        "root_closures_verified": None,
        "worker_runtime_minutes": None,
        "fanout_pressure_ratio": None,
    }
    # Multivariate PCA requires a defensible independent observation matrix.
    # The local contract does not claim any cycle independence, covariance or BT comparison graph.
    methods = {method: {"status": "HOLD", "reason": reason}
               for method, reason in {
                   "PCA": "No independently repeated comparable multivariate observation matrix or eigengap proof",
                   "BT": "No connected, independent pairwise worker-outcome comparison graph",
                   "3PSTAR": "Discovery/workflow identity does not prove native 3PSTAR effect or accepted policy",
                   "MIP": "Producer discovery is not a measured process-improvement qualification",
                   "DMAIC": "No signed causal root-closure, baseline or post-control recurrence certificate",
               }.items()}
    out = {"schema": OUT_SCHEMA, "pulse_id": current["pulse_id"],
           "observed_at_utc": current["observed_at_utc"],
           "breadth_depth": stats, "surfaces": bysurface,
           "queue_by_repo": {e["repository"]: e["queue"] for e in entries},
           "queue_transitions": transitions, "methods": methods,
           "federation_hops": {"gg_MATH": "UNKNOWN", "CODEX": "UNKNOWN", "ABACUS": "UNKNOWN", "QPS_TRIAGE": "DEFER"},
           "scout_read_only": True, "worker_dispatches": 0,
           "admission": "HOLD", "authority_transfer": False, "merge_authorized": False,
           "mathematical_maturity": "CORE_DESCRIPTIVE",
           "source_lineage_rule": "exact SHA, scoped receipts; UNKNOWN is not zero",
           "temporal_contract": "revisions and logical recovery cycles separate; measured queue deltas non-causal"}
    return out


def emit(current, previous, outdir):
    out = build(current, previous)
    target = Path(outdir)
    target.mkdir(parents=True, exist_ok=True)
    data = (canonical(out) + "\n").encode("utf8")
    (target / "rollup.json").write_bytes(data)
    manifest = {"schema": "gogreen.federation.rollup.manifest.v1",
                "sha256": {"rollup.json": hashlib.sha256(data).hexdigest()},
                "pulse_id": out["pulse_id"], "authority_transfer": False}
    (target / "manifest.json").write_text(canonical(manifest) + "\n", encoding="utf8")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--current", type=Path, required=True)
    ap.add_argument("--previous", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    current = json.loads(args.current.read_text(encoding="utf8"))
    prev = json.loads(args.previous.read_text(encoding="utf8")) if args.previous else None
    result = emit(current, prev, args.output)
    print(canonical(result["breadth_depth"]))


if __name__ == "__main__":
    main()
