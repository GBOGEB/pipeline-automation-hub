"""Governed RUN-i scout decision: value, comparability, and premature halt.

Read-only adapter over subtype_orchestrator.plan. No runners are launched, no
CI is cancelled, no branch is mutated and no acceptance is granted. Data
comes from explicit source-bound observations rather than an HTML truth store.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from subtype_orchestrator import plan as plan_packets

INPUT = "missioncontrol.scout-run-input.v1"
RECEIPT = "missioncontrol.scout-run-receipt.v1"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA64 = re.compile(r"[0-9a-f]{64}\Z")
COUNTS = ("success", "failure", "cancelled", "pending", "queued", "in_progress")
REPO = re.compile(r"GBOGEB/[A-Za-z0-9_.-]+\Z")
ENVIRONMENTS = ("COLD_CLONE", "SCOUT_BRANCH", "INTEGRATION_BRANCH", "MAIN_READONLY")


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def count(value, name):
    require(type(value) is int and value >= 0, "invalid count: " + name)
    return value


def timestamp(value):
    require(isinstance(value, str) and value.endswith("Z"), "UTC timestamp required")
    try:
        when = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid timestamp") from exc
    require(when.utcoffset() is not None and
            when.utcoffset().total_seconds() == 0, "UTC required")
    return when


def observation(item):
    require(isinstance(item, dict), "observation object required")
    require(isinstance(item.get("head_sha"), str) and
            SHA40.fullmatch(item["head_sha"]), "invalid observation head")
    require(item.get("collection") == "PR_HEAD_RUNS_FIRST_PAGE_METADATA",
            "untrusted observation class")
    timestamp(item.get("observed_at_utc"))
    counts = item.get("workflow_counts")
    require(isinstance(counts, dict) and set(counts) == set(COUNTS),
            "workflow count contract")
    require(sum(count(v, k) for k, v in counts.items()) > 0,
            "zero workflow population")
    names = item.get("failed_workflow_names")
    require(isinstance(names, list) and
            all(isinstance(x, str) and bool(x) for x in names) and
            len(set(names)) == len(names) and
            len(names) <= counts["failure"], "unattributed failure names")
    population = item.get("population_sha256")
    require(population is None or
            (isinstance(population, str) and SHA64.fullmatch(population)),
            "invalid population digest")
    require(item.get("archive_bytes_verified") is False and
            item.get("run_population_complete") is False,
            "first-page metadata cannot claim complete native proof")
    return item


def evaluate(data):
    require(isinstance(data, dict) and data.get("schema") == INPUT,
            "invalid scout run input")
    require(data.get("authority_transfer") is False and
            data.get("dispatch_authorized") is False and
            data.get("merge_authorized") is False, "forbidden authority")
    repo, pr = data.get("repository"), data.get("pr")
    require(isinstance(repo, str) and REPO.fullmatch(repo) and
            repo.split("/")[1] not in {".", ".."} and
            type(pr) is int and pr > 0, "invalid canonical PR")
    require(isinstance(data.get("run_i"), str) and
            re.fullmatch(r"N\+[0-9]+(?:\.I[0-9]+)?", data["run_i"]),
            "invalid iteration identity")
    snapshots = data.get("observations")
    require(isinstance(snapshots, list) and len(snapshots) == 2,
            "exactly two observed endpoints required")
    before, after = map(observation, snapshots)
    require(timestamp(before["observed_at_utc"]) <
            timestamp(after["observed_at_utc"]), "nonincreasing observation clock")
    require(before["head_sha"] != after["head_sha"],
            "new revision required; same-SHA reruns use regime_controller")
    require(after["head_sha"] == data.get("expected_head_sha"),
            "stale scout head; revalidate before acting")
    stop = data.get("stop_policy")
    require(isinstance(stop, dict), "missing early-halt policy")
    budget = count(stop.get("max_failed_workflows"), "max_failed_workflows")
    critical = stop.get("critical_failed_names")
    require(isinstance(critical, list) and
            all(isinstance(x, str) and bool(x) for x in critical) and
            len(critical) == len(set(critical)), "invalid critical check list")
    planned = data.get("subtype_plan")
    receipt = plan_packets(planned)
    require(planned["max_parallel"] <= 2,
            "scout pilot above two readonly worker slots")
    for packet in planned["packets"]:
        require(packet["mode"] == "READ_ONLY_ANALYZE" and
                packet["mutation_paths"] == [] and
                packet["accepted_root_ids"] == [] and
                packet["repo"] == repo and
                packet["source_sha"] == after["head_sha"],
                "scout workers must be source-matched, readonly, unpromoted")
    targets = data.get("candidate_reuse_targets")
    require(isinstance(targets, list) and len(targets) <= 12 and
            all(isinstance(t, str) and re.fullmatch(
                r"GBOGEB/[A-Za-z0-9_.-]+#[1-9][0-9]*", t) for t in targets) and
            len(targets) == len(set(targets)), "invalid reuse target candidates")
    scout_environment = data.get("scout_environment")
    require(scout_environment in ENVIRONMENTS, "invalid environment")
    scanner = data.get("advisory_scanner")
    if scanner is not None:
        require(isinstance(scanner, dict) and
                scanner.get("source_sha") == after["head_sha"] and
                scanner.get("enforcement") == "ADVISORY" and
                isinstance(scanner.get("name"), str) and
                type(scanner.get("native_run_id")) is int and
                scanner["native_run_id"] > 0, "invalid scanner provenance")
        for key in ("findings", "files_scanned", "rules_run"):
            count(scanner.get(key), key)
        require(scanner["files_scanned"] > 0 and scanner["rules_run"] > 0,
                "zero scanner denominator")
    matched = (before["population_sha256"] is not None and
               before["population_sha256"] == after["population_sha256"] and
               before["collection"] == after["collection"] and
               sum(before["workflow_counts"].values()) ==
               sum(after["workflow_counts"].values()) and
               all(before["workflow_counts"][k] == 0 and
                   after["workflow_counts"][k] == 0 for k in
                   ("queued", "pending", "in_progress")))
    before_counts, after_counts = before["workflow_counts"], after["workflow_counts"]
    matched_delta = ({k: after_counts[k] - before_counts[k] for k in COUNTS}
                     if matched else None)
    hard_roots = sorted(set(critical) & set(after["failed_workflow_names"]))
    reasons = (["HARD_RED:" + name for name in hard_roots] +
               (["FAILED_WORKFLOW_BUDGET"] if after_counts["failure"] > budget else []) +
               (["MATCHED_WORKFLOW_REGRESSION"]
                if matched and after_counts["failure"] > before_counts["failure"]
                else []))
    state = ("HALT_MUTATION_ALLOW_READONLY_SCOUT" if reasons else
             "READONLY_SCOUT_STAGED_NO_NATIVE_ADMISSION")
    # Existing GOGREEN subtype planner owns dependency and path-lease semantics.
    # This adapter only decides whether wider mutation remains prohibited.
    return {
        "schema": RECEIPT,
        "run_i": data["run_i"], "repository": repo, "pr": pr,
        "environment": scout_environment, "source_start": before["head_sha"],
        "source_end": after["head_sha"],
        "source_class": "GITHUB_FIRST_PAGE_METADATA_NOT_ARTIFACT_PROOF",
        "status": state, "stop_reasons": reasons,
        "next_mutating_wave": "HALT", "read_only_scouts_allowed": True,
        "metric_start": {"observed_at_utc": before["observed_at_utc"],
                         "workflow_counts": before_counts,
                         "workflow_denominator": sum(before_counts.values())},
        "metric_end": {"observed_at_utc": after["observed_at_utc"],
                       "workflow_counts": after_counts,
                       "workflow_denominator": sum(after_counts.values())},
        "matched_population": matched,
        "matched_workflow_delta": matched_delta,
        "unmatched_observed_delta_not_claimed": not matched,
        "native_queue_p50_seconds": None, "native_queue_p95_seconds": None,
        "native_worker_minutes": None, "executed_crew_members": None,
        "existing_subtype_scheduler": {
            "waves_planned": receipt["schedule"]["waves_planned"],
            "packets_planned": receipt["schedule"]["packets_planned"],
            "max_parallel": receipt["schedule"]["max_parallel"],
            "disjoint_path_conflicts_prevented":
                receipt["schedule"]["path_conflicts_prevented"],
            "schedule": receipt["schedule"]["waves"],
        },
        "candidate_reuse_targets": targets,
        "candidate_reuse_target_count": len(targets),
        "verified_reuse_targets": None,
        "advisory_scanner": scanner,
        "dod": {"scout_definition_checked": True,
                "native_candidate_proven": False,
                "regression_control_proven": False,
                "state": "SCOUT_DEFINITION_ONLY"},
        "dov": {"verified_causal_root_closures": None,
                "independent_approval": False, "owner_value_accepted": False,
                "state": "HOLD"},
        "next_admissible_action":
            "SCOUT_READONLY_NATIVE_FIRST_REDS_BEFORE_DISJOINT_REPAIR",
        "no_main_mutation": True,
        "dispatch_authorized": False, "merge_authorized": False,
        "security_waiver": False, "authority_transfer": False,
        "qps_decision": "DEFER", "four_hop_proof": "UNKNOWN",
    }


def emit(receipt, output):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    body = (json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode("utf-8")
    (out / "scout_run.json").write_bytes(body)
    digest = hashlib.sha256(body).hexdigest()
    (out / "scout_run.sha256").write_text(digest + "\n", encoding="ascii", newline="\n")
    b, e = receipt["metric_start"], receipt["metric_end"]
    lines = [
        "# Mission Control RUN-i governed scout",
        "",
        f"Iteration: {receipt['run_i']} | {receipt['repository']}#{receipt['pr']}",
        "",
        "| Metric | Start | End |",
        "|---|---:|---:|",
        f"| Observed workflow count | {b['workflow_denominator']} | {e['workflow_denominator']} |",
        f"| Workflow success | {b['workflow_counts']['success']} | {e['workflow_counts']['success']} |",
        f"| Workflow failure | {b['workflow_counts']['failure']} | {e['workflow_counts']['failure']} |",
        "",
        f"Population matched: {receipt['matched_population']}. "
        "Differing denominators are never converted to a success gain.",
        "",
        f"Mutation fan-out: {receipt['next_mutating_wave']}; "
        f"decision: {receipt['status']}.",
        "",
        "Scout plans are not executed workers or accepted engineering root closures.",
        f"SHA-256: {digest}",
        "",
    ]
    (out / "scout_run.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    result = evaluate(json.loads(args.input.read_text(encoding="utf-8")))
    print(json.dumps({"sha256": emit(result, args.out),
                      "status": result["status"],
                      "merge_authorized": False}, sort_keys=True))


if __name__ == "__main__":
    main()
