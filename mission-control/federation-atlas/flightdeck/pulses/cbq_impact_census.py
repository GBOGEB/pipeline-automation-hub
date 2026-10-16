"""Reconcile frozen N and N+1 CBQ snapshots without granting root closure."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def key(row):
    require(isinstance(row, dict), "invalid census row")
    require(isinstance(row.get("repository"), str)
            and row["repository"].startswith("GBOGEB/")
            and type(row.get("pr")) is int and row["pr"] > 0,
            "invalid PR identity")
    require(isinstance(row.get("head_sha"), str)
            and re.fullmatch(r"[0-9a-f]{40}", row["head_sha"]),
            "invalid exact SHA")
    return f'{row["repository"]}#{row["pr"]}'


def validate(parent, recensus):
    require(parent.get("schema") == "code-purple.cbq_ch_bd.pulse.v1",
            "wrong N schema")
    require(recensus.get("schema") == "code-purple.cbq_ch_bd.recensus.v1"
            and recensus.get("parent") == "CBQ_CH_BD_20261016.json"
            and recensus.get("snapshot_kind") ==
            "FROZEN_GITHUB_READBACK_NOT_CURRENT_AUTHORITY",
            "invalid N+1 source lineage")
    before, after = parent["snapshots"], recensus["all_observations"]
    require(len(before) == 5 and len(after) >= len(before)
            and recensus["base_cohort_size"] == len(before),
            "incomparable PR cohort")
    old = {key(x): x for x in before}
    new = {key(x): x for x in after}
    require(len(old) == len(before) and len(new) == len(after)
            and set(old) <= set(new), "duplicate or lost PR")
    for row in after:
        for col in ("success", "failed", "cancelled", "nonterminal"):
            require(type(row.get(col)) is int and row[col] >= 0,
                    "invalid workflow count")
        require(sum(row[x] for x in (
            "success", "failed", "cancelled", "nonterminal")) > 0
            and row.get("readback") == "GITHUB_PR_AND_WORKFLOW_RUNS"
            and row.get("observation_grade") == "METADATA_ONLY"
            and row.get("state") in ("open", "merged"),
            "invalid or promoted source readback")
    heads = recensus["default_branch_heads"]
    require(len(heads) == 5 and len({h["repo"] for h in heads}) == 5,
            "missing or duplicate default branches")
    for head in heads:
        require(re.fullmatch(r"[0-9a-f]{40}", head["sha"])
                and type(head["protected"]) is bool,
                "invalid exact main SHA/protection")
    owners = recensus["root_owners"]
    require(len({x["id"] for x in owners}) == len(owners),
            "duplicate root owner")
    for owner in owners:
        require(owner["canonical"] in new and
                all(x in new for x in owner["related"]),
                "root owner not grounded in recensus")
    require(recensus["federation_holds"] == {
        "qps": "DEFER", "native_replay": "UNKNOWN",
        "a10": "INDEPENDENT_REQUIRED",
        "security": "INDEPENDENT_REQUIRED",
        "merged_is_engineering_accept": False,
        "formal_credit_delta": 0,
    }, "authority promotion")
    return old, new


def compare(parent, recensus):
    old, new = validate(parent, recensus)
    matched = []
    for ident, a in sorted(old.items()):
        b = new[ident]
        comparable = a["head_sha"] == b["head_sha"]
        matched.append({
            "pr": ident,
            "status": ("MATCHED_HEAD" if comparable else "HEAD_CHANGED"),
            "source_matched": comparable,
            "failure_delta": (b["failed"] - a["failed"] if comparable else None),
            "pass_delta": (b["success"] - a["success"] if comparable else None),
            "accepted_root_closed": False,
        })
    ambiguous = sorted(x["id"] for x in recensus["root_owners"]
                       if x["status"].startswith("MULTIPLE_OVERLAPPING"))
    return {
        "schema": "code-purple.cbq_ch_bd.impact_projection.v1",
        "metrics": {
            "N_pr_population": len(old),
            "N_plus_1_pr_population": len(new),
            "additional_prs": len(new) - len(old),
            "repository_main_heads": len(recensus["default_branch_heads"]),
            "causal_root_families": len(recensus["root_owners"]),
            "overlapping_canonical_owners": len(ambiguous),
            "matched_prs": sum(x["source_matched"] for x in matched),
            "rebaseline_required": sum(not x["source_matched"] for x in matched),
            "accepted_root_closure_delta": 0,
            "accepted_engineering_dov_delta": 0,
            "actual_workers": None,
            "matched_coverage_gain": None,
        },
        "matched_cohort": matched,
        "new_pr_ids": sorted(set(new) - set(old)),
        "owner_conflicts": ambiguous,
        "root_owners": recensus["root_owners"],
        "default_branch_heads": recensus["default_branch_heads"],
        "authority": recensus["federation_holds"],
        "grade": "SOURCE_OBSERVATION_ONLY_NOT_ENGINEERING_CREDIT",
    }


def produce(parent_path, source_path, target):
    parent, source, out = Path(parent_path), Path(source_path), Path(target)
    a, b = parent.read_bytes(), source.read_bytes()
    result = compare(json.loads(a), json.loads(b))
    result["parent_sha256"] = hashlib.sha256(a).hexdigest()
    result["source_sha256"] = hashlib.sha256(b).hexdigest()
    out.mkdir(parents=True, exist_ok=True)
    (out / "impact.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out / "cohort.csv").open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=[
            "pr", "status", "source_matched", "failure_delta",
            "pass_delta", "accepted_root_closed"
        ])
        writer.writeheader()
        writer.writerows(result["matched_cohort"])
    m = result["metrics"]
    lines = [
        "# CODE PURPLE N to N+1 impact recensus",
        "",
        f"PRs: {m['N_pr_population']} to {m['N_plus_1_pr_population']}",
        f"Additional observations: {m['additional_prs']}",
        f"Canonical ownership overlaps: {m['overlapping_canonical_owners']}",
        "Engineering closure delta: 0",
        "Same-SHA workflow outcomes do not automatically prove root closure.",
        "",
        "## Dependency DAG",
        "~~~mermaid",
        "flowchart TD",
        " A[Fresh exact-head recensus] --> B{Head matched?}",
        " B -->|No| C[Rebaseline and native retest]",
        " B -->|Yes| D[Compare same-cohort first-reds]",
        " D --> E[Disjoint canonical root repair]",
        " C --> E",
        " E --> F[Native CI coverage security A10]",
        " F --> G{Independent admissible proof?}",
        " G -->|No| H[HOLD and retain root]",
        " G -->|Yes| I[KEB/DOW native artifact proof]",
        " I --> J[QPS private owner disposition]",
        "~~~",
        "",
        "## SIPOC",
        "| Supplier | Input | Process | Output | Customer |",
        "|---|---|---|---|---|",
        "| Repo owner | SHA, run/job/attempt | Census + compare | Impact receipt | MissionControl |",
        "| Security owner | Bandit, Safety, A10 | Independent disposition | Gate result | Merge admission |",
        "| gg_MATH/KEB/DOW | Artifact bytes | Semantic/replay verification | Native handoff | QPS |",
        "| QPS owner | Population, units, thresholds | Engineering review | Decision | Product delivery |",
        "",
        "**QPS DEFER; root closures 0; four-hop UNKNOWN**",
    ]
    (out / "impact.md").write_text("\n".join(lines) + "\n",
                                   encoding="utf-8")
    hashes = {x: hashlib.sha256((out / x).read_bytes()).hexdigest()
              for x in ("impact.json", "cohort.csv", "impact.md")}
    manifest = {
        "parent_sha256": result["parent_sha256"],
        "source_sha256": result["source_sha256"],
        "output_sha256": hashes,
        "evidence_level": "LOCAL_REPRODUCIBILITY",
    }
    (out / "impact_manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--parent", required=True)
    p.add_argument("--source", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    print(json.dumps(produce(args.parent, args.source, args.out)))
