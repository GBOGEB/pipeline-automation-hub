#!/usr/bin/env python3
"""G3P — governed N-to-N+3 wave receipt validator and report projection.

This is a contract verifier, NOT a background worker, runner dispatcher,
GitHub authorization layer, SSOT replacement, or merge-admission tool.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA = "missioncontrol.g3p.execution.v1"
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
HEX_SHA = re.compile(r"^[a-f0-9]{40}$")
STATES = {
    "EXECUTED_PASS",
    "EXECUTED_FAIL",
    "HOLD_EVIDENCED",
    "DEFER_EVIDENCED",
    "NOT_RUN_GLOBAL_BLOCKER",
}
TERMINAL = STATES - {"NOT_RUN_GLOBAL_BLOCKER"}
MUTATIONS = {"COMMIT", "PR_DRAFT", "MERGE_FEATURE_BRANCH"}
ACTION_KINDS = MUTATIONS | {"READ", "SCOUT", "TEST", "VERIFY", "HOLD"}
GLOBAL_BLOCKERS = {
    "AUTHORITY_UNAVAILABLE",
    "MISSING_PERMISSION",
    "SECURITY_OR_GOVERNANCE_BYPASS_REQUIRED",
    "DESTRUCTIVE_ACTION_UNAUTHORIZED",
    "SOURCE_IDENTITY_CONTRADICTION",
    "NO_SAFE_NEXT_ACTION",
    "CONFLICTING_SOURCE_OWNER_LEASE",
    "EVIDENCE_UNTRUSTED",
}
FORBIDDEN_FIELDS = {
    "main_merge_authorized",
    "security_waiver",
    "authority_transfer",
}
MEASURES = {
    "tests_passed", "tests_failed", "statement_covered", "statement_total",
    "branch_covered", "branch_total", "changed_lines_covered",
    "changed_lines_total", "run_duration_ms", "run_attempt",
}


class G3PContractError(ValueError):
    """Malformed evidence must fail closed instead of being inferred."""


def need(condition: bool, message: str) -> None:
    if not condition:
        raise G3PContractError(message)


def utc(value: str) -> datetime:
    need(isinstance(value, str) and bool(value), "missing UTC time")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError) as exc:
        raise G3PContractError("invalid UTC timestamp") from exc
    need(parsed.utcoffset() is not None, "naive timestamp not accepted")
    return parsed


def source_sha(value: Any) -> bool:
    return isinstance(value, str) and HEX_SHA.fullmatch(value) is not None


def checked_count(value: Any, name: str) -> None:
    need(value is None or (type(value) is int and value >= 0),
         "invalid numeric evidence: " + name)


def check_metrics(metrics: Any, sha: str) -> None:
    """Null counts remain unknown; coverage pairs cannot be half populated."""
    need(isinstance(metrics, dict), "metrics must be a dictionary")
    need(set(metrics) <= MEASURES, "unexpected measured field")
    for key in MEASURES:
        checked_count(metrics.get(key), key)
    pairs = (
        ("statement_covered", "statement_total"),
        ("branch_covered", "branch_total"),
        ("changed_lines_covered", "changed_lines_total"),
    )
    for numerator, denominator in pairs:
        a, b = metrics.get(numerator), metrics.get(denominator)
        need((a is None) == (b is None),
             "coverage requires numerator and denominator together")
        if a is not None:
            need(b > 0 and a <= b, "invalid coverage population")
    need(metrics.get("run_attempt") is None
         or metrics["run_attempt"] >= 1,
         "run attempt must be positive")
    need(source_sha(sha), "metric receipt must bind exact source SHA")


def check_actions(actions: Any, status: str, input_sha: str,
                  next_sha: str, lease_cap: int,
                  forecast_time: datetime, observed_time: datetime) -> list[str]:
    need(isinstance(actions, list), "action records must be a list")
    mutation = False
    leases: dict[str, str] = {}
    paths: set[str] = set()
    for action in actions:
        need(isinstance(action, dict), "invalid action record")
        kind = action.get("kind")
        owner = action.get("owner_lease")
        outcome = action.get("outcome")
        need(kind in ACTION_KINDS, "unrecognized action kind")
        need(isinstance(owner, str) and owner.strip(),
             "action requires accountable owner lease")
        need(outcome in {"DONE", "FAILED", "HOLD"},
             "action requires explicit actual outcome")
        began = utc(action.get("started_at"))
        ended = utc(action.get("completed_at"))
        need(forecast_time <= began <= ended <= observed_time,
             "action must start after frozen forecast and end before actual")
        changed = action.get("changed_paths")
        need(isinstance(changed, list), "changed paths missing")
        if kind not in MUTATIONS:
            need(not changed, "nonmutating action may not claim path mutation")
        if kind in MUTATIONS:
            mutation = mutation or outcome == "DONE"
            need(outcome != "DONE" or bool(action.get("evidence_ref")),
                 "committed change requires source evidence ref")
        for path in changed:
            need(isinstance(path, str) and path.strip()
                 and not path.startswith("/") and ".." not in path.split("/"),
                 "unsafe or invalid changed path")
            prior = leases.get(path)
            need(prior is None or prior == owner,
                 "disjoint worker collision at " + path)
            leases[path] = owner
            paths.add(path)
    need(len(set(leases.values())) <= lease_cap,
         "source owner concurrency cap exceeded")
    if next_sha != input_sha:
        need(mutation, "head changed without an evidenced source mutation")
    if status == "NOT_RUN_GLOBAL_BLOCKER":
        need(not actions, "NOT_RUN pulse has action records")
    return sorted(paths)


def validate_record(doc: Any) -> dict[str, Any]:
    """Validate source/evidence continuity and return a truthful summary."""
    need(isinstance(doc, dict) and doc.get("schema") == SCHEMA,
         "incorrect G3P schema")
    repo = doc.get("repository")
    mission = doc.get("mission_id")
    wave_id = doc.get("wave_id")
    need(isinstance(repo, str) and REPOSITORY.fullmatch(repo),
         "repository identity must be owner/name")
    need(isinstance(mission, str) and mission.strip(),
         "mission identity missing")
    need(isinstance(wave_id, str) and
         wave_id.startswith(repo + "::" + mission + "::W"),
         "fully qualified wave identity missing")
    need(doc.get("execution_mode") == "HANDS_OFF_BOUNDED",
         "only bounded in-turn execution is declared")
    objective = doc.get("objective")
    need(isinstance(objective, dict) and
         isinstance(objective.get("predicate"), str) and
         bool(objective["predicate"].strip()),
         "bounded objective predicate required")
    policy = doc.get("policy")
    need(isinstance(policy, dict), "missing policy")
    need(all(policy.get(field) is False for field in FORBIDDEN_FIELDS),
         "unauthorized main merge, security waiver or authority transfer")
    lease_cap = policy.get("max_parallel_mutation_leases")
    need(type(lease_cap) is int and 1 <= lease_cap <= 2,
         "source owner cap must remain one or two")
    need(policy.get("global_stop_policy") ==
         "STOP_ON_MAJOR_BLOCKER_NO_AUTO_WAIVER",
         "major stop rule is required")
    baseline = doc.get("baseline_N")
    need(isinstance(baseline, dict) and
         source_sha(baseline.get("source_sha")) and
         isinstance(baseline.get("evidence_ref"), str) and
         bool(baseline["evidence_ref"]),
         "baseline N requires source-bound evidence")
    time_n = utc(baseline.get("observed_at"))
    pulses = doc.get("pulses")
    need(isinstance(pulses, list) and len(pulses) == 3,
         "one wave requires exactly three pulse slots")
    previous_sha = baseline["source_sha"]
    previous_time = time_n
    global_stop = False
    inspected = []
    completed = 0
    for index, pulse in enumerate(pulses, start=1):
        need(isinstance(pulse, dict), "invalid pulse record")
        identity = f"{wave_id}::PULSE-{index}"
        need(pulse.get("ordinal") == index and
             pulse.get("pulse_id") == identity,
             "pulse order/identity drift")
        status = pulse.get("status")
        need(status in STATES, "unsupported pulse outcome")
        if global_stop:
            need(status == "NOT_RUN_GLOBAL_BLOCKER",
                 "pulse executed after global stop")
        if status == "NOT_RUN_GLOBAL_BLOCKER":
            need(global_stop, "NOT_RUN must follow evidenced global blocker")
            need(pulse.get("forecast") is None and
                 pulse.get("observed") is None and
                 pulse.get("next_source_sha") is None and
                 pulse.get("actions") == [] and
                 pulse.get("evidence_refs") == [],
                 "unexecuted pulse must claim no results")
            inspected.append({"ordinal": index, "pulse_id": identity,
                              "status": status, "source_sha": None,
                              "measured_metrics": None,
                              "evidence_refs": []})
            continue
        input_sha = pulse.get("input_source_sha")
        next_sha = pulse.get("next_source_sha")
        need(input_sha == previous_sha and source_sha(next_sha),
             "sequential source/head continuity broken")
        forecast = pulse.get("forecast")
        observed = pulse.get("observed")
        need(isinstance(forecast, dict) and isinstance(observed, dict),
             "pulse needs expected and actual receipts")
        forecast_time = utc(forecast.get("frozen_at"))
        observed_time = utc(observed.get("measured_at"))
        need(previous_time <= forecast_time <= observed_time,
             "forecast must precede measured outcome")
        need(isinstance(forecast.get("hypothesis"), str) and
             forecast["hypothesis"].strip(),
             "missing before-action expected outcome")
        projected = forecast.get("metrics")
        need(isinstance(projected, dict) and
             set(projected) <= MEASURES,
             "invalid forecast metric keys")
        for metric, estimate in projected.items():
            checked_count(estimate, "forecast:" + metric)
        forecast_population = forecast.get("population_id")
        need(isinstance(forecast_population, str) and
             forecast_population.strip(),
             "forecast requires declared observation population")
        actual_population = observed.get("population_id")
        need(isinstance(actual_population, str) and
             actual_population.strip(),
             "actual requires observed population identity")
        observed_sha = observed.get("source_sha")
        need(observed_sha == next_sha, "observed result not on next exact source")
        check_metrics(observed.get("metrics"), observed_sha)
        need(isinstance(observed.get("summary"), str) and
             observed["summary"].strip(),
             "observed summary required")
        steps = observed.get("executed_steps")
        need(type(steps) is int and steps >= 0,
             "executed steps must be counted")
        evid = pulse.get("evidence_refs")
        need(isinstance(evid, list) and len(evid) > 0 and
             all(isinstance(x, str) and x.strip() for x in evid),
             "terminal pulse requires evidence locator")
        paths = check_actions(pulse.get("actions"), status, input_sha,
                              next_sha, lease_cap, forecast_time, observed_time)
        if status in ("EXECUTED_PASS", "EXECUTED_FAIL"):
            need(bool(pulse["actions"]),
                 "executed pulse requires action or test records")
        comparisons = {}
        for metric, prediction in projected.items():
            actual_value = observed["metrics"].get(metric)
            comparable = (forecast_population == actual_population
                          and prediction is not None
                          and actual_value is not None)
            comparisons[metric] = {
                "expected": prediction,
                "actual": actual_value,
                "population_matched": forecast_population == actual_population,
                "delta_actual_minus_expected":
                    actual_value - prediction if comparable else None,
                "state": "COMPARABLE" if comparable else "UNKNOWN_OR_UNMATCHED",
            }
        if status == "EXECUTED_PASS":
            need(steps > 0, "zero-step cannot be PASS")
            need(observed.get("check_outcome") == "PASS",
                 "green pulse requires actual passing check")
        if status == "EXECUTED_FAIL":
            need(observed.get("check_outcome") == "FAIL",
                 "failed execution requires failing evidence")
        blocker = pulse.get("blocker")
        if status in {"HOLD_EVIDENCED", "DEFER_EVIDENCED"}:
            need(isinstance(blocker, dict) and
                 blocker.get("scope") in ("LOCAL", "GLOBAL"),
                 "HOLD/DEFER needs scoped blocker")
        if blocker is not None:
            need(isinstance(blocker, dict) and
                 blocker.get("scope") in ("LOCAL", "GLOBAL"),
                 "invalid blocker scope")
            if blocker["scope"] == "GLOBAL":
                need(blocker.get("reason") in GLOBAL_BLOCKERS,
                     "global stop reason must be controlled")
                global_stop = True
        inspected.append({
            "ordinal": index, "pulse_id": identity,
            "status": status, "source_sha": next_sha,
            "changed_paths": paths,
            "measured_metrics": observed["metrics"],
            "evidence_refs": evid,
            "blocker": blocker,
            "expected_hypothesis": forecast["hypothesis"],
            "observed_summary": observed["summary"],
            "expected_vs_actual": comparisons,
        })
        completed += 1
        previous_sha, previous_time = next_sha, observed_time
    wave_status = (
        "STOPPED_MAJOR_BLOCKER" if global_stop
        else "COMPLETED_THREE_EVIDENCED_PULSES"
    )
    return {
        "schema": "missioncontrol.g3p.report.v1",
        "mission_id": mission,
        "wave_id": wave_id,
        "repository": repo,
        "baseline_N_source_sha": baseline["source_sha"],
        "last_observed_source_sha": previous_sha,
        "wave_status": wave_status,
        "pulse_slots": 3,
        "terminal_evidenced_pulses": completed,
        "N_plus_3_ordinal_reached": completed == 3,
        "engineering_acceptance": None,
        "formal_closure": None,
        "independent_security_governance_review": None,
        "main_merge_admitted": False,
        "automatic_background_execution_claimed": False,
        "evidence_locator_authentication":
            "DECLARED_ONLY_NOT_VERIFIED_BY_THIS_VALIDATOR",
        "pulses": inspected,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate G3P N-to-N+3 evidence.")
    parser.add_argument("source", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        document = json.loads(args.source.read_text(encoding="utf-8"))
        report = validate_record(document)
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "error": str(exc)}))
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8", newline="\n")
    print(json.dumps({"wave_status": report["wave_status"],
                      "terminal_evidenced_pulses":
                      report["terminal_evidenced_pulses"],
                      "main_merge_admitted": False}, sort_keys=True))
    # Exit 0 means the three receipt slots have terminal traceability,
    # never security/merge approval. A major global stop is exit 2 even
    # when encountered during the third pulse.
    return 0 if (report["N_plus_3_ordinal_reached"]
                 and report["wave_status"] ==
                 "COMPLETED_THREE_EVIDENCED_PULSES") else 2


if __name__ == "__main__":
    raise SystemExit(main())
