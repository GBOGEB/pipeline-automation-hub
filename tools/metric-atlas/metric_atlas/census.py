"""Read-only QPS TRIAGE federated census and DAG routing, with explicit UNKNOWNs.

A census request is not a native test result; a GitHub Actions metadata receipt is
not test or coverage attestation. Only an explicitly validated native job receipt
may contribute executed test counts. No cross-repo authority or merge control.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

SHA = re.compile(r"^[a-f0-9]{40}$")
SCHEMA = "qps-metric-census/v1"
RECEIPT = "qps-metric-receipt/v1"
ALLOWED_REPOS = {
    "ABACUS": "GBOGEB/ABACUS",
    "CODEX": "GBOGEB/CODEX",
    "QPS_ENGINEERING": "GBOGEB/cryoplant-project",
}
ALLOWED_SELECTORS = {"native_checks", "coverage_catalog", "all"}


class CensusError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def request(wave, heads, selector="all", max_fanout=3):
    """Build deterministic, bounded, source-pinned disjoint producer requests."""
    if not isinstance(wave, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", wave):
        raise CensusError("invalid wave ID")
    if (selector not in ALLOWED_SELECTORS or
            type(max_fanout) is not int or not 1 <= max_fanout <= 3):
        raise CensusError("selector/fanout invalid")
    if not isinstance(heads, dict) or set(heads) != set(ALLOWED_REPOS):
        raise CensusError("require an exact three-lane manifest; unknown is not omitted")
    out = []
    missing = []
    for lane, repo in ALLOWED_REPOS.items():
        sha = heads[lane]
        if sha is None:
            missing.append({"lane": lane, "repo": repo, "expected_sha": None,
                            "request_id": None, "state": "HOLD_SOURCE_HEAD_UNKNOWN",
                            "reason": "NO_AUTHORIZED_SOURCE_READ"})
            continue
        if not isinstance(sha, str) or SHA.fullmatch(sha) is None:
            raise CensusError("invalid exact SHA for " + lane)
        seed = {"wave": wave, "lane": lane, "repo": repo,
                "expected_sha": sha, "selector": selector}
        identifier = "QPS-" + hashlib.sha256(canonical(seed).encode()).hexdigest()[:20]
        out.append(dict(seed, request_id=identifier, state="PLANNED_NOT_DISPATCHED"))
    return {"schema": SCHEMA, "wave": wave, "mode": "READ_ONLY",
            "dispatch_enabled": False, "max_fanout": max_fanout,
            "eligible_repos": len(ALLOWED_REPOS), "requested_repos": len(ALLOWED_REPOS),
            "dispatchable_repos": min(len(out), max_fanout),
            "unknown_head_repos": len(missing),
            "requests": out[:max_fanout],
            "not_dispatched": missing + [dict(q, state="DEFERRED_FANOUT_LIMIT")
                                         for q in out[max_fanout:]],
            "authority_transfer": False, "engineering_acceptance": False}


def _int(value):
    return type(value) is int and value > 0


def validate_receipt(receipt, manifest):
    if not isinstance(receipt, dict) or receipt.get("schema") != RECEIPT:
        raise CensusError("receipt schema mismatch")
    matches = [q for q in manifest.get("requests", [])
               if q["request_id"] == receipt.get("request_id")]
    if len(matches) != 1:
        raise CensusError("unknown request ID")
    q = matches[0]
    if (receipt.get("repo") != q["repo"] or
            receipt.get("target_sha") != q["expected_sha"] or
            receipt.get("lane") != q["lane"]):
        raise CensusError("source/target identity mismatch")
    if receipt.get("route") not in ("native_checks", "coverage_catalog"):
        raise CensusError("invalid DAG route")
    if q["selector"] != "all" and receipt["route"] != q["selector"]:
        raise CensusError("not requested route")
    if not all(_int(receipt.get(k)) for k in ("run_id", "run_attempt", "job_id")):
        raise CensusError("native run/attempt/job ID missing")
    if not isinstance(receipt.get("execution_sha"), str) or not SHA.fullmatch(receipt["execution_sha"]):
        raise CensusError("no real execution source SHA")
    if receipt.get("authority_transfer") is not False or receipt.get("engineering_acceptance") is not False:
        raise CensusError("unauthorized authority transfer")
    if receipt.get("outcome") not in ("SUCCESS", "FAILURE", "CANCELLED"):
        raise CensusError("invalid terminal outcome")
    counts = receipt.get("tests", {})
    if not isinstance(counts, dict):
        raise CensusError("tests must be an object")
    metric_keys = ("executed", "passed", "failed", "skipped")
    if any(counts.get(key) is not None for key in metric_keys):
        if receipt.get("evidence_class") != "NATIVE_TEST_COUNTS_WITH_LOG_RECEIPT":
            raise CensusError("metadata receipt cannot assert test counts")
        if not all(type(counts.get(k)) is int and counts[k] >= 0 for k in metric_keys):
            raise CensusError("incomplete test counts")
        if counts["executed"] != counts["passed"] + counts["failed"] + counts["skipped"]:
            raise CensusError("test totals inconsistent")
        if not receipt.get("test_log_url") or not receipt.get("scope_fingerprint"):
            raise CensusError("test counts lack source log/scope")
    cov = receipt.get("coverage", {})
    if not isinstance(cov, dict):
        raise CensusError("coverage must be an object")
    if any(cov.get(k) is not None for k in ("statements", "covered_statements", "branches", "covered_branches")):
        if receipt.get("evidence_class") != "NATIVE_TEST_COUNTS_WITH_LOG_RECEIPT":
            raise CensusError("metadata-only cannot claim coverage")
        if not cov.get("scope_fingerprint") or not cov.get("artifact_sha256"):
            raise CensusError("coverage unbound to source scope/artifact")
        for covered, total in (("covered_statements", "statements"), ("covered_branches", "branches")):
            if cov.get(total) is not None or cov.get(covered) is not None:
                if not (type(cov.get(total)) is int and cov[total] > 0 and
                        type(cov.get(covered)) is int and 0 <= cov[covered] <= cov[total]):
                    raise CensusError("invalid coverage numerator/denominator")
    return q


def rollup(manifest, receipts):
    if manifest.get("schema") != SCHEMA:
        raise CensusError("manifest schema mismatch")
    observed = defaultdict(set)
    routes = defaultdict(set)
    identities = {}
    state = defaultdict(list)
    for record in receipts:
        q = validate_receipt(record, manifest)
        key = (record["repo"], record["target_sha"], record["run_id"],
               record["run_attempt"], record["job_id"], record["route"])
        if key in identities:
            if canonical(identities[key]) != canonical(record):
                raise CensusError("conflicting duplicate native identity")
            continue
        identities[key] = record
        observed[q["repo"]].add(q["expected_sha"])
        routes[q["repo"]].add(record["route"])
        state[q["repo"]].append(record["outcome"])
    expected_routes = {"native_checks", "coverage_catalog"}
    rows = []
    for q in manifest["requests"]:
        repo = q["repo"]
        target = expected_routes if q["selector"] == "all" else {q["selector"]}
        got = routes[repo]
        rows.append({"repo": repo, "lane": q["lane"], "head_sha": q["expected_sha"],
                     "routes_received": sorted(got), "routes_required": sorted(target),
                     "complete": target.issubset(got),
                     "route_failure": ("FAILURE" in state[repo]) if state[repo] else None,
                     "test_counts": None, "coverage": None,
                     "merge_admission": "HOLD_UNKNOWN_REQUIRED_EVIDENCE"})
    for q in manifest.get("not_dispatched", []):
        unknown = q.get("state") == "HOLD_SOURCE_HEAD_UNKNOWN"
        target = expected_routes if q.get("selector", "all") == "all" else {q["selector"]}
        rows.append({"repo": q["repo"], "lane": q["lane"],
                     "head_sha": q.get("expected_sha"),
                     "routes_received": [], "routes_required": sorted(target),
                     "complete": False, "route_failure": None,
                     "state": "HOLD_SOURCE_HEAD_UNKNOWN" if unknown else "DEFERRED_FANOUT_LIMIT",
                     "test_counts": None, "coverage": None, "merge_admission": "HOLD"})
    return {"schema": "qps-metric-rollup/v1", "wave": manifest["wave"],
            "eligible_repos": manifest.get("eligible_repos", len(manifest["requests"])),
            "unknown_head_repos": manifest.get("unknown_head_repos", 0),
            "planned_repos": len(manifest["requests"]),
            "deferred_repos": sum(r.get("state") == "DEFERRED_FANOUT_LIMIT" for r in rows),
            "represented_repos": len(rows),
            "observed_repos": len(observed),
            "fully_observed_repos": sum(r["complete"] for r in rows),
            "native_job_receipts": len(identities),
            "run_attempts": len(set((r["repo"], r["run_id"], r["run_attempt"]) for r in identities.values())),
            "tests_executed": None, "coverage_scope_matched_uplift": None,
            "worker_hours": None, "distinct_accepted_root_ids": None,
            "global_open_pr_denominator": None,
            "lanes": rows, "authority_transfer": False, "engineering_acceptance": False,
            "note": "Observation only. A complete census is not source code acceptance."}


def dag_mermaid():
    return """flowchart LR
 A[QPS TRIAGE N request] --> B{Exact source SHA + allowlist?}
 B -- no --> HOLD[HOLD / re-census]
 B -- yes --> C[Disjoint repo-specific request - not dispatched]
 C --> D1[ABACUS native-check census]
 C --> D2[CODEX transformation census]
 C --> D3[QPS engineering census]
 D1 --> E[Identity and scope-bound receipts]
 D2 --> E
 D3 --> E
 E --> F{All requested receipts?}
 F -- no --> WAIT[UNKNOWN / missing receiver]
 F -- yes --> G[Metric Atlas normalized / absolute rollup]
 G --> H[Root attribution and coverage comparison]
 H --> I[Owner decision / next N+i wave]
 I -.->|next pulse only| NEXT[New source snapshot N+1]
"""


def sipoc_mermaid():
    return """flowchart LR
 S[Suppliers: QPS TRIAGE + repo owners] --> I[Inputs: exact SHAs, jobs, log receipts]
 I --> P[Process: request - route - classify - rollup - compare]
 P --> O[Outputs: CSV/JSON telemetry, DAG, priority queue]
 O --> C[Customers: repo maintainers + Mission Control]
"""


def main(argv=None):
    p = argparse.ArgumentParser(description="Governed disjoint QPS census")
    sp = p.add_subparsers(dest="command", required=True)
    a = sp.add_parser("request")
    a.add_argument("--wave", required=True)
    a.add_argument("--heads", type=Path, required=True)
    a.add_argument("--selector", choices=sorted(ALLOWED_SELECTORS), default="all")
    a.add_argument("--max-fanout", type=int, default=3)
    a.add_argument("--output", type=Path, required=True)
    b = sp.add_parser("rollup")
    b.add_argument("--manifest", type=Path, required=True)
    b.add_argument("--receipts", type=Path, required=True)
    b.add_argument("--output", type=Path, required=True)
    c = sp.add_parser("diagrams")
    c.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        if args.command == "request":
            heads = json.loads(args.heads.read_text(encoding="utf-8"))
            output = request(args.wave, heads, args.selector, args.max_fanout)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
        elif args.command == "rollup":
            output = rollup(json.loads(args.manifest.read_text()), json.loads(args.receipts.read_text()))
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
        else:
            args.output.mkdir(parents=True, exist_ok=True)
            (args.output / "QPS_CENSUS_DAG.mmd").write_text(dag_mermaid(), encoding="utf-8")
            (args.output / "QPS_CENSUS_SIPOC.mmd").write_text(sipoc_mermaid(), encoding="utf-8")
            output = {"state": "DIAGRAMS_WRITTEN", "path": str(args.output)}
        print(json.dumps(output, indent=2))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        p.exit(2, "CENSUS_HOLD: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
