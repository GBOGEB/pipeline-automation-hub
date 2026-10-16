"""Read-only, source-bound rerun triage for MissionControl CBD subtype packets.

The input is an operator snapshot, not live GitHub authority. Nothing here
dispatches Actions, rebases branches, closes roots, or approves merges.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "missioncontrol.cbd-rerun-input.v1"
OUTPUT_SCHEMA = "missioncontrol.cbd-rerun-receipt.v1"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
RUNNING = {"queued", "pending", "in_progress", "waiting", "requested"}
CONCLUSIONS = {"success", "failure", "cancelled", "timed_out", "skipped", "neutral", "action_required"}
KINDS = {"DETERMINISTIC", "TRANSIENT", "UNCLASSIFIED", "NONE"}
TRANSIENT_CAUSES = {"runner_lost", "github_5xx", "rate_limit", "network_timeout"}
DECISIONS = {
    "WAIT_CURRENT_RUN", "RUN_NEW_EXACT_HEAD", "RECONCILE_MAIN",
    "REPAIR_CANONICAL_ROOT", "RERUN_FAILED_JOBS_CANDIDATE",
    "DEBUG_RERUN_CANDIDATE", "INSPECT_FIRSTRED", "RETRY_EXHAUSTED",
    "EVALUATE_INDEPENDENT_GATES", "NO_ELIGIBLE_TEST", "DUPLICATE_ROOT_WAIT",
}


def _timestamp(value, field):
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid {field}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} requires a timezone")
    return parsed.astimezone(timezone.utc)


def _sha(value, field):
    if not isinstance(value, str) or not HEX40.fullmatch(value):
        raise ValueError(f"invalid {field}")


def _positive(value, field):
    if type(value) is not int or value <= 0:
        raise ValueError(f"invalid {field}")


def _nonnegative(value, field):
    if type(value) is not int or value < 0:
        raise ValueError(f"invalid {field}")


def _validate_item(item, observed):
    if not isinstance(item, dict):
        raise ValueError("invalid item")
    _positive(item.get("pr"), "pr")
    _sha(item.get("head_sha"), "head_sha")
    _nonnegative(item.get("behind_main"), "behind_main")
    created = _timestamp(item.get("created_at"), "created_at")
    if created > observed:
        raise ValueError("future created_at")
    run = item.get("run")
    if run is not None:
        if not isinstance(run, dict):
            raise ValueError("invalid run")
        _positive(run.get("id"), "run_id")
        _positive(run.get("attempt"), "run_attempt")
        _sha(run.get("head_sha"), "run_head_sha")
        if run.get("status") == "completed" or run.get("job_id") is not None:
            _positive(run.get("job_id"), "job_id")
        status = run.get("status")
        if status not in RUNNING | {"completed"}:
            raise ValueError("invalid run status")
        if status == "completed" and run.get("conclusion") not in CONCLUSIONS:
            raise ValueError("completed run needs conclusion")
        if status in RUNNING and run.get("conclusion") is not None:
            raise ValueError("incomplete run cannot have conclusion")
        kind = run.get("failure_kind")
        if kind not in KINDS:
            raise ValueError("invalid failure_kind")
        if type(run.get("logs_insufficient")) is not bool:
            raise ValueError("logs_insufficient must be boolean")
        if run.get("cause") is not None and (
            not isinstance(run["cause"], str) or not run["cause"]
        ):
            raise ValueError("invalid cause")
        if kind == "TRANSIENT" and run.get("cause") not in TRANSIENT_CAUSES:
            raise ValueError("unsupported transient classification")
        if run.get("conclusion") == "success" and kind != "NONE":
            raise ValueError("green cannot claim a failure kind")
    root = item.get("root_id")
    if root is not None and (not isinstance(root, str) or not root.strip()):
        raise ValueError("invalid root_id")
    return created


def _decide(item):
    run = item["run"]
    if run is None:
        return "RUN_NEW_EXACT_HEAD", "No current-head native run supplied"
    if run["head_sha"] != item["head_sha"]:
        return "RUN_NEW_EXACT_HEAD", "Existing run belongs to another commit"
    if run["status"] in RUNNING:
        return "WAIT_CURRENT_RUN", "A current-head run is already active or queued"
    if item["behind_main"] > 0:
        return "RECONCILE_MAIN", "Current main has source commits absent from branch"
    if run["conclusion"] == "success":
        return "EVALUATE_INDEPENDENT_GATES", "Success does not satisfy security or approval"
    if run["conclusion"] in {"skipped", "neutral", "action_required"}:
        return "NO_ELIGIBLE_TEST", "No passing native execution of the required test"
    if run["failure_kind"] == "DETERMINISTIC":
        return "REPAIR_CANONICAL_ROOT", "Source/policy/root repair precedes exact-head CI"
    if run["attempt"] >= 2:
        return "RETRY_EXHAUSTED", "Multiple attempts do not establish a repaired root"
    if run["failure_kind"] == "TRANSIENT":
        return "RERUN_FAILED_JOBS_CANDIDATE", "Transient category has a bounded reason"
    if run["logs_insufficient"]:
        return "DEBUG_RERUN_CANDIDATE", "Review whether missing logs justify debug"
    return "INSPECT_FIRSTRED", "Read failed job steps and artifacts before spending CI"


def plan(snapshot):
    if not isinstance(snapshot, dict) or snapshot.get("schema") != SCHEMA:
        raise ValueError("wrong snapshot schema")
    if snapshot.get("authority_transfer") is not False:
        raise ValueError("authority transfer forbidden")
    observed = _timestamp(snapshot.get("observed_at"), "observed_at")
    _sha(snapshot.get("main_sha"), "main_sha")
    items = snapshot.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("nonempty items required")
    if len(items) > 500:
        raise ValueError("unbounded census")
    rows, ids, retry_roots = [], set(), set()
    for item in sorted(items, key=lambda x: x.get("pr", -1)):
        created = _validate_item(item, observed)
        if item["pr"] in ids:
            raise ValueError("duplicate PR identity")
        ids.add(item["pr"])
        decision, reason = _decide(item)
        root = item.get("root_id")
        if decision == "RERUN_FAILED_JOBS_CANDIDATE" and root:
            cohort_key = (root, item["head_sha"])
            if cohort_key in retry_roots:
                decision = "DUPLICATE_ROOT_WAIT"
                reason = "Same root and source already have a diagnostic candidate"
            retry_roots.add(cohort_key)
        hours = round((observed - created).total_seconds() / 3600, 2)
        rows.append({
            "pr": item["pr"],
            "head_sha": item["head_sha"],
            "behind_main": item["behind_main"],
            "age_hours": hours,
            "older_than_24h": hours >= 24,
            "run_id": item["run"]["id"] if item["run"] else None,
            "job_id": item["run"].get("job_id") if item["run"] else None,
            "run_attempt": item["run"]["attempt"] if item["run"] else None,
            "run_head_sha": item["run"]["head_sha"] if item["run"] else None,
            "root_id": root,
            "decision": decision,
            "reason": reason,
            "rerun_executed": False,
            "debug_enabled": False,
            "proof_authenticated": False,
        })
    counts = {d: sum(r["decision"] == d for r in rows) for d in sorted(DECISIONS)}
    return {
        "schema": OUTPUT_SCHEMA,
        "observed_at": snapshot["observed_at"],
        "main_sha": snapshot["main_sha"],
        "source": "UNTRUSTED_OPERATOR_SNAPSHOT",
        "authority_transfer": False,
        "dispatch_authorized": False,
        "merge_authorized": False,
        "security_waiver": False,
        "independent_root_closures": 0,
        "kpi": {
            "prs": len(rows),
            "older_than_24h": sum(r["older_than_24h"] for r in rows),
            "behind_main": sum(r["behind_main"] > 0 for r in rows),
            "head_mismatch": sum(
                r["run_head_sha"] is not None and r["run_head_sha"] != r["head_sha"]
                for r in rows
            ),
            "retries_recommended": counts["RERUN_FAILED_JOBS_CANDIDATE"],
            "debug_candidates": counts["DEBUG_RERUN_CANDIDATE"],
            "duplicate_root_retries_suppressed": counts["DUPLICATE_ROOT_WAIT"],
            "dispatched_workers": None,
            "matched_coverage_change_pp": None,
            "counts": counts,
        },
        "rows": rows,
    }


def emit(receipt, out):
    """Write a deterministic local projection, never an independent SSOT."""
    out.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    (out / "rerun_receipt.json").write_bytes(raw)
    (out / "rerun_receipt.sha256").write_text(digest + "\n", encoding="ascii")
    return digest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    receipt = plan(json.loads(args.input.read_text(encoding="utf-8")))
    print(json.dumps({"sha256": emit(receipt, args.out), "kpi": receipt["kpi"]}, sort_keys=True))
