#!/usr/bin/env python3
"""QBD! public-safe read-only closure contract; structural proof only.

Consumes a committed, historical source-bound JSON projection. Never calls
GitHub, runs workers, mutates issues, approves a PR, or accepts QPS evidence.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SCHEMA = "codepurple.qbd.disjoint_convergence.public_ro.v1"
PUBLIC_REPOS = {
    "GBOGEB/ABACUS",
    "GBOGEB/CODEX",
    "GBOGEB/pipeline-automation-hub",
}
HEX40 = re.compile(r"^[0-9a-f]{40}$")
ALLOWED_RELATIONS = {
    "observes", "source_lineage", "candidate", "depends_on",
    "advisory_handoff",
}


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def clean_scope(path: str) -> bool:
    if not isinstance(path, str) or not path or path.startswith("/"):
        return False
    if "\\" in path or ":" in path:
        return False
    return all(bit not in ("", ".", "..") for bit in path.split("/"))


def overlaps(first: str, second: str) -> bool:
    return first == second or first.startswith(second + "/") or second.startswith(first + "/")


def validate(document: dict) -> dict:
    require(isinstance(document, dict), "INVALID_DOCUMENT")
    require(document.get("schema") == SCHEMA, "SCHEMA_OR_AUTHORITY_MISMATCH")
    require(document.get("public_safe") is True, "NOT_PUBLIC_SAFE")
    require(bool(HEX40.fullmatch(str(document.get("observed_main", "")))), "MAIN_SHA")
    authority = document.get("source_authority", {})
    require(isinstance(authority, dict), "AUTHORITY")
    expected = {
        "authority_transfer": False, "merge_admission": "HOLD",
        "dispatch_authorized": False, "source_mutation_authorized": False,
        "issue_closure_authorized": False, "action_closure_authorized": False,
        "security_waiver": False, "formal_root_closure_credit_delta": 0,
        "engineering_credit_delta": 0,
    }
    require(authority == expected, "UNAUTHORIZED_CREDIT_OR_DISPATCH")
    private = document.get("private_qps", {})
    require(isinstance(private, dict) and private.get("repository") ==
            "GBOGEB/cryoplant-project", "PRIVATE_REPOSITORY_ID")
    for field in ("open_issue_count", "neg_mom_action_count", "private_issue_ids", "private_source_sha"):
        require(private.get(field) is None, "PRIVATE_DATA_MUST_BE_REDACTED")
    require(private.get("owner_source_required") is True, "QPS_OWNER_REQUIRED")

    public = document.get("public_issue_counts", [])
    require(isinstance(public, list) and len(public) == 3, "PUBLIC_POPULATION")
    require({r.get("repo") for r in public} == PUBLIC_REPOS, "PUBLIC_REPOSITORY_SET")
    for row in public:
        require(type(row.get("open_issues")) is int and row["open_issues"] >= 0,
                "INVALID_ISSUE_COUNT")
        require(type(row.get("open_prs")) is int and row["open_prs"] >= 0,
                "INVALID_PR_COUNT")
        require(row.get("pr_page_complete") is True, "INCOMPLETE_PR_CENSUS")

    metrics = document.get("metrics", {})
    require(metrics.get("issue_count_public_three_repos") ==
            sum(r["open_issues"] for r in public), "ISSUE_DENOMINATOR_DRIFT")
    require(metrics.get("current_public_open_prs") ==
            sum(r["open_prs"] for r in public), "PR_DENOMINATOR_DRIFT")
    require(metrics.get("qps_hidden_unknown_not_zero") is True, "PRIVATE_UNKNOWN_ZEROED")
    for field in ("root_burndown_delta", "proof_yield", "recurrence",
                  "coverage_matched", "bt_rank"):
        require(metrics.get(field) is None, "UNVERIFIED_METRIC_PROMOTION")

    historical = document.get("historical_abacus_n0", {})
    require(historical.get("source_status") ==
            "FROZEN_FIRST_PAGE_HISTORICAL_NOT_CURRENT_CENSUS", "N0_LIVE_PROMOTION")
    require(historical.get("declared_pr_heads") == 75, "PR_POPULATION_DRIFT")
    require(historical.get("failed_workflow_associations") == 260 and
            historical.get("distinct_failed_run_ids") == 253 and
            historical.get("duplicate_aliases") == 7, "N0_COHORT_DRIFT")
    require(historical.get("causal_root_count") is None and
            historical.get("eligible_root_closures") is None, "CAUSAL_ROOT_PROMOTION")
    require(bool(HEX40.fullmatch(str(historical.get("source_pr_head", "")))),
            "HISTORICAL_PR_SOURCE")

    actual = document.get("observed_abacus_pr2077", {})
    require(actual.get("complete_first_page") is True, "PARTIAL_PR_PAGE")
    require(actual.get("head") == historical["source_pr_head"], "PR_HEAD_DRIFT")
    require((actual.get("workflow_runs"), actual.get("success"),
             actual.get("failure"), actual.get("cancelled")) == (29, 23, 5, 1),
            "PR_RUN_COHORT_DRIFT")
    require(actual.get("verified_causal_root_count") is None, "FALSE_ROOT_COUNT")
    jobs = actual.get("native_failure_jobs", [])
    require(isinstance(jobs, list) and len(jobs) == 5, "FIRST_RED_SAMPLE_DRIFT")
    seen = set()
    for row in jobs:
        run, attempt, job = row.get("workflow_run"), row.get("run_attempt"), row.get("native_job")
        require(all(type(x) is int and x > 0 for x in (run, attempt, job)),
                "MISSING_EXACT_NATIVE_TUPLE")
        require((run, attempt, job) not in seen, "DUPLICATE_JOB")
        seen.add((run, attempt, job))
        url = f"https://github.com/GBOGEB/ABACUS/actions/runs/{run}/job/{job}"
        require(row.get("job_url") == url and row.get("sha") == actual["head"],
                "FORGED_JOB_BINDING")
        require(row.get("native_job_failure_observed") is True and
                row.get("causal_root_confirmed") is False, "FALSE_CAUSAL_PROOF")
        require(row.get("receipt_class") ==
                "HISTORICAL_PR_HEAD_NATIVE_JOB_NOT_CURRENT_MAIN", "HISTORICAL_PROMOTION")

    capacity = document.get("parallel_capacity", {})
    require(capacity.get("read_only_scouts") == 4 and
            capacity.get("source_writer_max") == 2 and
            capacity.get("writer_claims_committed") == 0 and
            capacity.get("reader_dispatch_executed") is False and
            capacity.get("writer_dispatch_executed") is False,
            "FALSE_WORKER_DISPATCH")
    writers = document.get("proposed_writers", [])
    require(isinstance(writers, list) and len(writers) == 2, "WRITER_CAPACITY")
    leased = []
    for worker in writers:
        require(worker.get("repo") == "GBOGEB/ABACUS" and
                worker.get("mutation_authorized") is False and
                worker.get("lease_state") == "PROPOSED_NOT_CLAIMED", "FALSE_LEASE")
        require(type(worker.get("owner_pr")) is int and worker["owner_pr"] > 0,
                "MISSING_SOURCE_OWNER")
        paths = worker.get("scope", [])
        require(isinstance(paths, list) and bool(paths), "EMPTY_WRITER_SCOPE")
        for path in paths:
            require(clean_scope(path), "UNSAFE_SOURCE_PATH")
            require(not any(overlaps(path, prior) for prior in leased),
                    "OVERLAPPING_WRITER_PATH")
            leased.append(path)

    graph = document.get("diagram", {})
    nodes, edges = graph.get("nodes"), graph.get("edges")
    require(isinstance(nodes, list) and isinstance(edges, list), "MISSING_GRAPH")
    ids = [node.get("id") for node in nodes]
    require(all(isinstance(node, str) and node for node in ids) and
            len(set(ids)) == len(ids), "DUPLICATE_GRAPH_NODE")
    neighbors = {node: [] for node in ids}
    for edge in edges:
        require(edge.get("from") in neighbors and edge.get("to") in neighbors and
                edge.get("from") != edge.get("to"), "ORPHAN_OR_SELF_EDGE")
        require(edge.get("relation") in ALLOWED_RELATIONS, "UNKNOWN_EDGE_RELATION")
        require(edge.get("binding") in (
            "DECLARED_CURRENT_GRAPH", "DECLARED_NO_NATIVE_CROSS_REPO_PROOF"),
            "FALSE_RECEIPT_EDGE")
        if edge["relation"] == "depends_on":
            neighbors[edge["from"]].append(edge["to"])
    active, done = set(), set()

    def visit(node: str) -> None:
        require(node not in active, "DEPENDENCY_CYCLE")
        if node in done:
            return
        active.add(node)
        for child in neighbors[node]:
            visit(child)
        active.remove(node)
        done.add(node)

    for node in ids:
        visit(node)
    return {
        "schema": "codepurple.qbd.local_contract_check.v1",
        "status": "STRUCTURAL_PASS_NOT_NATIVE_AUTHENTICATION",
        "public_repositories": 3, "public_open_issues": metrics["issue_count_public_three_repos"],
        "historic_failed_associations": 260, "historical_job_examples": len(jobs),
        "graph_nodes": len(ids), "graph_edges": len(edges),
        "reader_slots_proposed": 4, "writer_slots_proposed": 2,
        "accepted_root_closures": None, "source_mutation": False,
        "merge_admission": "HOLD",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = validate(json.loads(args.input.read_text(encoding="utf-8")))
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "REJECT", "reason": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
