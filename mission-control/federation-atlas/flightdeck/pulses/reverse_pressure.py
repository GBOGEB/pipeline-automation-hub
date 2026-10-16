"""Read-only reverse dependency pressure for canonical CBQ/CH-BD census.

A policy-guided prioritizer, not PCA loadings, Bradley-Terry fit, dispatcher,
merge admission, REX receipt, or engineering-root closure.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

SCHEMA = "code-purple.reverse-pressure.v1"
DELTA_SCHEMA = "code-purple.source-bound-delta.v1"
ALIASES = {
    "FORMAT": "DOW_BLACK_ISORT",
    "SECURITY": "DOW_BANDIT_SAFETY",
    "PY_COMPAT": "PY310_DEPENDENCY",
    "WORKFLOW_POLICY": "GOVERNANCE_CANONICAL",
    "COVERAGE_MODE": None,
    "REPLAY": "FOUR_HOP",
}
# Human-proposed, not an authoritative priority change: no named coverage-mode
# family existed in the frozen CBQ snapshot.
DEFAULT_PRIORITY = {"COVERAGE_MODE": "P1"}
PRIORITY_WEIGHT = {"P0": 3, "P1": 2, "P2": 1, "P3": 1}
SHA = re.compile(r"[0-9a-f]{40}\Z")
IDENT = re.compile(r"GBOGEB/[A-Za-z0-9_.-]+#[1-9][0-9]*\Z")


def require(test, message):
    if not test:
        raise ValueError(message)


def identity(row):
    require(isinstance(row, dict), "INVALID_OBSERVATION_ROW")
    repo, pr = row.get("repository"), row.get("pr")
    require(isinstance(repo, str) and repo.startswith("GBOGEB/")
            and type(pr) is int and pr > 0, "INVALID_PR_IDENTITY")
    sha = row.get("head_sha")
    require(isinstance(sha, str) and SHA.fullmatch(sha), "INVALID_HEAD_SHA")
    return f"{repo}#{pr}"


def validate_delta(delta):
    if delta is None:
        return {}
    require(isinstance(delta, dict)
            and delta.get("schema") == DELTA_SCHEMA
            and delta.get("observation_grade") == "METADATA_ONLY"
            and delta.get("authority_transfer") is False
            and delta.get("merge_authorized") is False
            and delta.get("accepted_root_closures") == 0,
            "DELTA_AUTHORITY_OR_SCHEMA")
    rows = delta.get("rows")
    require(isinstance(rows, list) and rows, "DELTA_MISSING_ROWS")
    result = {}
    for row in rows:
        key = identity(row)
        require(key not in result, "DELTA_DUPLICATE_PR")
        require(row.get("state") in ("open", "merged", "closed"),
                "DELTA_INVALID_STATE")
        c = row.get("counts")
        require(isinstance(c, dict) and set(c) == {
            "success", "failure", "cancelled", "pending", "queued", "in_progress", "other"
        }, "DELTA_COUNTS_SCHEMA")
        require(all(type(v) is int and v >= 0 for v in c.values()),
                "DELTA_COUNTS_INVALID")
        require(type(row.get("observed_workflow_runs")) is int
                and row["observed_workflow_runs"] == sum(c.values())
                and row["observed_workflow_runs"] > 0,
                "DELTA_COUNTS_NOT_EXHAUSTIVE")
        require(row.get("reused_artifact_bytes") is False,
                "DELTA_FORGED_ARTIFACT_PROOF")
        result[key] = row
    return result


def analyze(pulse, recensus, delta=None):
    # Reuse the strict native CBQ/N+1 validators instead of duplicating a SSOT.
    from cbq_ch_bd_render import validate as verify_pulse
    from cbq_impact_census import validate as verify_recensus
    verify_pulse(pulse)
    verify_recensus(pulse, recensus)
    latest = validate_delta(delta)
    frozen = {identity(r): r for r in recensus["all_observations"]}
    families = {r["id"]: r for r in pulse["families"]}
    require(set(ALIASES) == {r["id"] for r in recensus["root_owners"]},
            "CANONICAL_OWNER_TAXONOMY_DRIFT")
    roots = []
    for owner in recensus["root_owners"]:
        rid = owner["id"]
        alias = ALIASES[rid]
        if alias is None:
            priority = DEFAULT_PRIORITY[rid]
            priority_basis = "PROVISIONAL_COVERAGE_POLICY"
        else:
            require(alias in families, "FAMILY_ALIAS_MISSING")
            priority = families[alias]["priority"]
            priority_basis = "FROZEN_CBQ_POLICY"
        require(priority in PRIORITY_WEIGHT, "INVALID_PRIORITY")
        references = [owner["canonical"], *owner["related"]]
        require(len(references) == len(set(references))
                and all(isinstance(s, str) and IDENT.fullmatch(s) for s in references)
                and all(s in frozen for s in references), "UNSUPPORTED_DEPENDENCY_EDGE")
        selected = [latest.get(s, frozen[s]) for s in references]
        open_prs = sorted(s for s, value in zip(references, selected)
                          if value["state"] == "open")
        stale = sorted(s for s in references
                       if s in latest and latest[s]["head_sha"] != frozen[s]["head_sha"])
        unrefreshed = sorted(s for s in references if s not in latest)
        # This is a *policy-weighted count of referenced open PRs*, not an
        # expected number of repaired roots, causal effect, or PCA component.
        score = PRIORITY_WEIGHT[priority] * len(open_prs)
        roots.append({
            "root_id": rid,
            "priority": priority,
            "priority_basis": priority_basis,
            "canonical_owner_pr": owner["canonical"],
            "owner_state": owner["status"],
            "direct_references": references,
            "referenced_open_prs": open_prs,
            "reverse_reach": len(open_prs),
            "pressure_score": score,
            "pressure_units": "POLICY_POINTS_TIMES_REFERENCED_OPEN_PRS",
            "owner_reconciliation_required": owner["status"].startswith("MULTIPLE_OVERLAPPING"),
            "changed_head_refs": stale,
            "not_refreshed_refs": unrefreshed,
            "source_matched_for_delta": not stale and not unrefreshed,
            "failed_workflow_manifestations": sum(
                value.get("failure", value.get("failed", 0)) for value in selected
            ),
            "first_red_attributed_to_root": None,
            "ready_for_readonly_scout": True,
            "eligible_for_mutating_worker": False,
            "verified_root_closure": False,
        })
    roots.sort(key=lambda r: (
        -PRIORITY_WEIGHT[r["priority"]], -r["pressure_score"], r["root_id"]
    ))
    total_score = sum(r["pressure_score"] for r in roots)
    for rank, row in enumerate(roots, 1):
        row["rank_within_policy_tiers"] = rank
        row["descriptive_pressure_share"] = (
            round(row["pressure_score"] / total_score, 6) if total_score else None
        )
    observed = list(latest.values())
    observed_count = sum(r["observed_workflow_runs"] for r in observed)
    terminal_count = sum(sum(r["counts"][s] for s in
                             ("success", "failure", "cancelled")) for r in observed)
    distinct_open = {key for row in roots for key in row["referenced_open_prs"]}
    proof_drain = []
    for key, entry in latest.items():
        c = entry["counts"]
        terminal = c["success"] + c["failure"] + c["cancelled"]
        nonterminal = c["pending"] + c["queued"] + c["in_progress"] + c["other"]
        proof_drain.append({
            "pr": key,
            "source_sha": entry["head_sha"],
            "nonterminal_run_observations": nonterminal,
            "terminal_run_observations": terminal,
            "terminal_fraction_descriptive": round(terminal / entry["observed_workflow_runs"], 6),
            "run_cohort": "FIRST_PAGE_HEAD_ASSOCIATED_METADATA_NOT_QUEUE_P95",
            "verified_artifact_bytes": False,
            "source_root_closed": False,
        })
    proof_drain.sort(key=lambda r: (-r["nonterminal_run_observations"], r["pr"]))
    run_tallies = {state: sum(x["counts"][state] for x in observed)
                   for state in ("success", "failure", "cancelled",
                                 "pending", "queued", "in_progress", "other")}
    return {
        "schema": SCHEMA,
        "snapshot_grade": "DATED_SUPPORTING_CENSUS_NOT_LIVE_AUTHORITY",
        "root_owners": roots,
        "proof_drain": proof_drain,
        "metrics": {
            "owner_clusters": len(roots),
            "canonical_owner_overlap_clusters": sum(
                r["owner_reconciliation_required"] for r in roots),
            "unique_open_referenced_prs": len(distinct_open),
            "overlapping_pressure_total_not_unique_roots": total_score,
            "delta_observed_prs": len(observed),
            "delta_workflow_observations": observed_count,
            "delta_terminal_workflow_observations": terminal_count,
            "delta_nonterminal_workflow_observations": observed_count - terminal_count,
            "delta_workflow_status_counts": run_tallies,
            "delta_terminal_fraction_descriptive": (
                round(terminal_count / observed_count, 6) if observed_count else None),
            "queue_p95_seconds": None,
            "native_worker_hours": None,
            "native_worker_concurrency": None,
            "accepted_engineering_roots_closed": 0,
            "matched_statement_coverage_gain_pp": None,
            "matched_branch_coverage_gain_pp": None,
            "rex_verified_reopens": None,
        },
        "ranking_diagnostics": {
            "method": "LEXICOGRAPHIC_PRIORITY_AND_POLICY_WEIGHTED_REVERSE_REACH",
            "assumed_priority_weights": PRIORITY_WEIGHT,
            "not_a_causal_effect": True,
            "not_pca_loadings": True,
            "pca_ready": False,
            "pca_reason": "NO_COMPLETE_INDEPENDENT_ALIGNED_MULTIVARIATE_SERIES",
            "pca_loadings": None,
            "bt_ready": False,
            "bt_reason": "NO_INDEPENDENT_SAME_TASK_PAIRED_WORKER_TRIALS",
            "bt_strengths": None,
            "bt_independent_comparisons": 0,
        },
        "worker_proposals": {
            "max_parallel_readonly": 2,
            "candidate_root_ids": [x["root_id"] for x in roots[:2]],
            "proposed_readonly_waves": [
                {"wave": "PRESSURE_OWNER_SCOUT", "root_ids": [x["root_id"] for x in roots[:2]]},
                {"wave": "PROOF_DRAIN_SCOUT", "pr_ids": [x["pr"] for x in proof_drain[:2]]},
            ],
            "dispatch_authorized": False,
            "path_lease_verified": False,
            "mutation_authorized": False,
            "integration_target": "GBOGEB/pipeline-automation-hub#561",
        },
        "rolling_n_plus_2": [
            {"horizon": "N+1", "target": "NATIVE_MIP2_EXACT_HEAD_AND_COVERAGE_RECEIPT",
             "prediction": "HOLD_UNTIL_TERMINAL_SOURCE_BOUND_PROOF",
             "kind": "POLICY_CONDITIONAL_NOT_PROBABILISTIC"},
            {"horizon": "N+2", "target": "QPS_FOUR_HOP_ENGINEERING_ACCEPTANCE",
             "prediction": "DEFER_UNLESS_OWNER_AND_NATIVE_RECEIPTS",
             "kind": "POLICY_CONDITIONAL_NOT_PROBABILISTIC"},
        ],
        "authority": {
            "dispatch_authorized": False,
            "merge_authorized": False,
            "security_waiver": False,
            "authority_transfer": False,
            "qps_decision": "DEFER",
            "four_hop_native": "UNKNOWN",
            "root_closure_credited": 0,
        },
    }


def produce(pulse_path, recensus_path, delta_path, out_path):
    paths = [Path(pulse_path), Path(recensus_path)]
    if delta_path:
        paths.append(Path(delta_path))
    raw = [p.read_bytes() for p in paths]
    value = analyze(json.loads(raw[0]), json.loads(raw[1]),
                    json.loads(raw[2]) if len(raw) > 2 else None)
    value["source_hashes"] = {p.name: hashlib.sha256(b).hexdigest()
                              for p, b in zip(paths, raw)}
    out = Path(out_path)
    out.mkdir(parents=True, exist_ok=True)
    data_path = out / "reverse_pressure.json"
    data_path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8")
    with (out / "reverse_pressure.csv").open("w", newline="", encoding="utf-8") as fp:
        keys = ["rank_within_policy_tiers", "root_id", "priority", "reverse_reach",
                "pressure_score", "descriptive_pressure_share",
                "owner_reconciliation_required", "source_matched_for_delta"]
        writer = csv.DictWriter(fp, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(value["root_owners"])
    lines = ["# CODE PURPLE — reverse-pressure diagnostic", "",
             "Policy-weighted direct PR references, not PCA/BT or verified causal reduction.",
             "", "| Rank | Root | Tier | Open references | Score | Freshness |",
             "|---:|---|---|---:|---:|---|"]
    for r in value["root_owners"]:
        fresh = "MATCHED" if r["source_matched_for_delta"] else "PARTIAL_OR_DRIFT"
        lines.append(f'| {r["rank_within_policy_tiers"]} | {r["root_id"]} | '
                     f'{r["priority"]} | {r["reverse_reach"]} | '
                     f'{r["pressure_score"]} | {fresh} |')
    lines.extend(["", "## Proof-drain queue (not queue latency)", "",
                  "| PR | Nonterminal runs | Terminal runs | Terminal fraction |",
                  "|---|---:|---:|---:|"])
    for row in value["proof_drain"]:
        lines.append(f'| {row["pr"]} | {row["nonterminal_run_observations"]} | '
                     f'{row["terminal_run_observations"]} | '
                     f'{row["terminal_fraction_descriptive"]:.2%} |')
    lines.extend(["", "## Boundaries", "",
                  "PCA and Bradley-Terry withheld: no eligible multivariate/paired trials.",
                  "Source metadata does not attribute failures to a specific root.",
                  "Maximum two planned read-only scouts; no Crew launch implied.",
                  "Source owners, A10, Safety, effective required checks and QPS owner remain independent.",
                  "Root closure=0, REX reopening=UNKNOWN, QPS=DEFER.", ""])
    (out / "reverse_pressure.md").write_text("\n".join(lines), encoding="utf-8")
    output = {name: hashlib.sha256((out / name).read_bytes()).hexdigest()
              for name in ("reverse_pressure.json", "reverse_pressure.csv",
                           "reverse_pressure.md")}
    manifest = {"schema": "code-purple.reverse-pressure.manifest.v1",
                "input_sha256": value["source_hashes"],
                "output_sha256": output,
                "grade": "LOCAL_OR_NATIVE_READONLY_PROJECTION_NOT_REVIEW_AUTHORITY"}
    (out / "reverse_pressure_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pulse", required=True)
    p.add_argument("--recensus", required=True)
    p.add_argument("--delta")
    p.add_argument("--out", required=True)
    a = p.parse_args()
    print(json.dumps(produce(a.pulse, a.recensus, a.delta, a.out), sort_keys=True))


if __name__ == "__main__":
    main()
