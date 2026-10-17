#!/usr/bin/env python3
"""Read-only CODE PURPLE BD census; no root closure or dispatch authority.

Consumes live GitHub REST PR, issue and PR-head Actions metadata. The output
is an observed workflow-manifestation index, NOT a causal root diagnosis.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
import hashlib
import json
import math
import os
import re
import statistics
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "codepurple.bd-queue-wave.v1"
REPOS = ("GBOGEB/ABACUS", "GBOGEB/CODEX", "GBOGEB/pipeline-automation-hub", "GBOGEB/cryoplant-project")
SHA = re.compile(r"^[a-f0-9]{40}$")
RULES = (
    ("CONFIDENTIALITY", r"a10-guard|confidentiality"),
    ("GOVERNANCE", r"governance|policy.and.inventory"),
    ("SECURITY", r"security scanning|bandit|semgrep|codeql|osv|safety"),
    ("FORMAT", r"format check|validate docs|lint|markdown|yaml"),
    ("PYTHON_MATRIX", r"abacus matrix|python matrix"),
    ("V032", r"abacus v032"),
    ("EVERRED", r"everred"),
    ("DOW", r"dow|recursive dmaic"),
    ("COVERAGE", r"coverage|mip b0"),
    ("INTEGRATED_SUITE", r"ci/cd test suite|cicd pipeline"),
)
OWNER_CANDIDATES = {
    "CONFIDENTIALITY": "ABACUS#1996", "GOVERNANCE": "ABACUS#1996/PR#2041",
    "SECURITY": "ABACUS#1738", "FORMAT": "ABACUS#2049/PR#2004",
    "PYTHON_MATRIX": "ABACUS#1874/PR#2026", "V032": "ABACUS#1874/PR#2026",
    "EVERRED": "ABACUS#2049", "DOW": "ABACUS#1991",
    "COVERAGE": "ABACUS#1991", "INTEGRATED_SUITE": "ABACUS#1860",
    "OTHER": "UNASSIGNED_NEEDS_READER",
}


def stable(obj):
    return (json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def family(name):
    if not isinstance(name, str) or not name.strip():
        return "OTHER"
    for label, pattern in RULES:
        if re.search(pattern, name, re.I):
            return label
    return "OTHER"


def utc(value):
    if not isinstance(value, str):
        return None
    try:
        t = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return t.astimezone(timezone.utc) if t.tzinfo else None
    except ValueError:
        return None


def queue_seconds(run):
    created, started = utc(run.get("created_at")), utc(run.get("run_started_at"))
    if not (created and started):
        return None
    seconds = (started - created).total_seconds()
    return round(seconds, 3) if 0 <= seconds <= 86400 * 7 else None


def percentile(data, percent):
    a = sorted(v for v in data if type(v) in (int, float) and math.isfinite(v) and v >= 0)
    return a[max(0, math.ceil(len(a) * percent) - 1)] if a else None


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_prs(prs, repo):
    _require(isinstance(prs, list), "PR page is not a list")
    ids = set()
    out = []
    for pr in prs:
        _require(isinstance(pr, dict), "invalid PR")
        number = pr.get("number")
        sha = pr.get("head", {}).get("sha") if isinstance(pr.get("head"), dict) else None
        _require(type(number) is int and number > 0 and number not in ids, "duplicate/invalid PR")
        _require(isinstance(sha, str) and SHA.fullmatch(sha), "missing source SHA")
        _require(pr.get("state") == "open", "non-open PR in census")
        ids.add(number)
        out.append({"repo": repo, "number": number, "head_sha": sha,
                    "base": pr.get("base", {}).get("ref"), "draft": pr.get("draft") is True})
    return sorted(out, key=lambda x: (x["repo"], x["number"]))


def summarize_runs(pr, payload):
    _require(isinstance(payload, dict) and isinstance(payload.get("workflow_runs"), list), "bad run page")
    runs = payload["workflow_runs"]
    total = payload.get("total_count")
    _require(type(total) is int and total >= 0, "missing run total_count")
    _require(total <= len(runs), "partial Actions page: refuse complete coverage credit")
    chosen = {}
    for run in runs:
        _require(isinstance(run, dict), "invalid workflow run")
        _require(run.get("head_sha") == pr["head_sha"], "run exact-head mismatch")
        _require(run.get("event") == "pull_request", "non-PR run mixed with PR cohort")
        rid, attempt = run.get("id"), run.get("run_attempt", 1)
        _require(type(rid) is int and rid > 0, "run ID invalid")
        _require(type(attempt) is int and attempt > 0, "run attempt invalid")
        wid = run.get("workflow_id")
        key = str(wid) if type(wid) is int and wid > 0 else str(run.get("name", ""))
        _require(key, "workflow identity missing")
        # Highest attempt, followed by newest run ID, wins a single workflow family slot.
        if key not in chosen or (attempt, rid) > (chosen[key]["run_attempt"], chosen[key]["id"]):
            chosen[key] = run
    all_values = list(chosen.values())
    reds = []
    green = unknown = cancelled = 0
    durations = []
    attempts_excess = 0
    for run in all_values:
        status, conclusion = run.get("status"), run.get("conclusion")
        if status != "completed" or conclusion is None:
            unknown += 1
        elif conclusion == "failure":
            reds.append({"repo": pr["repo"], "pr": pr["number"], "head_sha": pr["head_sha"],
                         "run_id": run["id"], "attempt": run.get("run_attempt", 1),
                         "workflow": run.get("name", ""), "family": family(run.get("name")),
                         "candidate_owner": OWNER_CANDIDATES[family(run.get("name"))],
                         "causal_root_verified": False})
        elif conclusion == "success":
            green += 1
        elif conclusion == "cancelled":
            cancelled += 1
        else:
            unknown += 1
        q = queue_seconds(run)
        if q is not None:
            durations.append(q)
        attempts_excess += run.get("run_attempt", 1) - 1
    status = "RED" if reds else "UNKNOWN" if unknown or not all_values else "NO_OBSERVED_RED"
    return {**pr, "status": status, "run_cohort_count": len(all_values),
            "green_workflows": green, "red_workflows": len(reds),
            "unknown_workflows": unknown, "cancelled_workflows": cancelled,
            "retry_attempt_excess_proxy": attempts_excess,
            "queue_latency_samples_seconds": durations,
            "manifestations": sorted(reds, key=lambda x: (x["family"], x["run_id"]))}


def summarize_issue_page(items, repo, total):
    _require(isinstance(items, list) and type(total) is int and total == len(items), "incomplete issue census")
    nums = set()
    for issue in items:
        _require(issue.get("pull_request") is None, "pull request mixed into issue census")
        n = issue.get("number")
        _require(type(n) is int and n > 0 and n not in nums and issue.get("state") == "open", "invalid issue census")
        nums.add(n)
    return {"repository": repo, "open_issues": len(nums), "issue_ids": sorted(nums)}


def aggregate(prs, issues, errors=()):
    _require(isinstance(prs, list) and isinstance(issues, list), "invalid census")
    unique = {(p["repo"], p["number"]) for p in prs}
    _require(len(unique) == len(prs), "duplicate PR row")
    manifest = [m for pr in prs for m in pr.get("manifestations", [])]
    family_counts = defaultdict(lambda: {"prs": set(), "runs": 0, "candidate_owner": None})
    for m in manifest:
        f = m["family"]
        family_counts[f]["prs"].add((m["repo"], m["pr"]))
        family_counts[f]["runs"] += 1
        family_counts[f]["candidate_owner"] = m["candidate_owner"]
    groups = [{"family": f, "affected_prs": len(row["prs"]), "failed_workflows": row["runs"],
               "candidate_owner": row["candidate_owner"], "causal_root_count": None}
              for f, row in family_counts.items()]
    groups.sort(key=lambda x: (-x["affected_prs"], x["family"]))
    latencies = [q for row in prs for q in row.get("queue_latency_samples_seconds", [])]
    out = {"schema": SCHEMA, "scope": "LIVE_READ_ONLY_API_CENSUS",
           "open_prs": len(prs), "open_issues": sum(x["open_issues"] for x in issues),
           "open_items": len(prs) + sum(x["open_issues"] for x in issues),
           "prs_with_failed_workflows": sum(p["status"] == "RED" for p in prs),
           "prs_without_observed_failure": sum(p["status"] == "NO_OBSERVED_RED" for p in prs),
           "prs_unknown": sum(p["status"] == "UNKNOWN" for p in prs),
           "manifestations": len(manifest), "family_groups": groups,
           "queue_latency_workflow_level": {"n": len(latencies),
                                           "p50_seconds": percentile(latencies, 0.5),
                                           "p95_seconds": percentile(latencies, 0.95)},
           "retry_attempt_excess_proxy": sum(p.get("retry_attempt_excess_proxy", 0) for p in prs),
           "independent_root_count": None, "root_closure_delta": 0,
           "matched_coverage_numerator": None, "matched_coverage_denominator": None,
           "accepted_proof_yield": None, "blocked_time_seconds": None,
           "resource_contention": None, "retry_amplification": None,
           "authority_transfer": False, "dispatch_authorized": False, "merge_authorized": False,
           "issues": sorted(issues, key=lambda x: x["repository"]),
           "errors": list(errors)}
    return out, manifest


class GitHubReader:
    def __init__(self, token="", base_url="https://api.github.com"):
        self.token = token
        self.base_url = base_url.rstrip("/")

    def get(self, route):
        if not route.startswith("/") or ".." in route or "\\" in route:
            raise ValueError("noncanonical API path")
        req = urllib.request.Request(self.base_url + route,
                                     headers={"Accept": "application/vnd.github+json",
                                              "User-Agent": "codepurple-bd-census-v1",
                                              **({"Authorization": "Bearer " + self.token} if self.token else {})})
        with urllib.request.urlopen(req, timeout=35) as result:
            return json.load(result)

    def paginate(self, route, key=None):
        records = []
        page = 1
        while page <= 10:
            delimiter = "&" if "?" in route else "?"
            data = self.get(f"{route}{delimiter}per_page=100&page={page}")
            items = data.get(key, []) if key else data
            _require(isinstance(items, list), "invalid paged API response")
            records.extend(items)
            if len(items) < 100:
                if key is not None and type(data.get("total_count")) is int:
                    _require(data["total_count"] == len(records), "incomplete total_count")
                return records
            page += 1
        raise ValueError("pagination capacity exceeded")


def scan(reader, repos=REPOS, max_parallel=4):
    _require(set(repos) <= set(REPOS) and len(repos) == len(set(repos)), "unapproved repo list")
    _require(type(max_parallel) is int and 1 <= max_parallel <= 6, "invalid parallel limit")
    prs, issues = [], []
    for repo in repos:
        raw_prs = reader.paginate(f"/repos/{repo}/pulls?state=open")
        prs += validate_prs(raw_prs, repo)
        q = urllib.parse.quote(f"repo:{repo} is:issue is:open")
        raw_issues = reader.paginate(f"/search/issues?q={q}", key="items")
        issues.append(summarize_issue_page(raw_issues, repo, len(raw_issues)))
    def probe(pr):
        try:
            payload = reader.get(f"/repos/{pr['repo']}/actions/runs?head_sha={pr['head_sha']}&event=pull_request&per_page=100")
            return summarize_runs(pr, payload), None
        except (ValueError, OSError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
            return {**pr, "status": "UNKNOWN", "run_cohort_count": 0, "green_workflows": 0,
                    "red_workflows": 0, "unknown_workflows": None, "cancelled_workflows": 0,
                    "retry_attempt_excess_proxy": 0, "queue_latency_samples_seconds": [],
                    "manifestations": []}, {"repo": pr["repo"], "pr": pr["number"], "type": type(exc).__name__}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel) as pool:
        results = list(pool.map(probe, prs))
    out_rows, errors = [r for r, _ in results], [err for _, err in results if err]
    summary, manifests = aggregate(out_rows, issues, errors)
    return summary, out_rows, manifests


def write_outputs(dest, summary, prs, manifest):
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    payloads = {"bd_summary.json": stable(summary),
                "bd_pr_queue.json": stable(prs), "bd_manifestations.json": stable(manifest)}
    rows = ["repository,pr,source_sha,status,green,failed,unknown,run_cohort\n"]
    for p in sorted(prs, key=lambda x: (x["repo"], x["number"])):
        rows.append(f"{p['repo']},{p['number']},{p['head_sha']},{p['status']},{p['green_workflows']},{p['red_workflows']},{p['unknown_workflows']},{p['run_cohort_count']}\n")
    payloads["bd_pr_queue.csv"] = "".join(rows).encode()
    view = ["# CODE PURPLE read-only BD queue\n", "\n", f"Open PRs: **{summary['open_prs']}**; issues: **{summary['open_issues']}**; failures: **{summary['manifestations']}**.\n",
            "\n", "Workflow failure families are manifestations, **not verified causal roots**.\n\n",
            "| Family | Affected PRs | Failed workflows | Candidate owner |\n", "|---|---:|---:|---|\n"]
    for g in summary["family_groups"]:
        view.append(f"| {g['family']} | {g['affected_prs']} | {g['failed_workflows']} | {g['candidate_owner']} |\n")
    view.append("\nIndependent root count, accepted proof yield, matched coverage and promotion remain UNKNOWN/HOLD.\n")
    payloads["BD_REPORT.md"] = "".join(view).encode()
    for filename, data in payloads.items():
        (dest / filename).write_bytes(data)
    manifest_receipt = {"schema": "codepurple.bd-wave-files.v1", "files_sha256": {name: digest(data) for name, data in sorted(payloads.items())},
                        "source_is_live_api": summary["scope"] == "LIVE_READ_ONLY_API_CENSUS", "dispatch_authorized": False, "root_closure_delta": 0}
    receipt = stable(manifest_receipt)
    (dest / "bd_files_sha256.json").write_bytes(receipt)
    return {"files": sorted([*payloads, "bd_files_sha256.json"]), "manifest_sha256": digest(receipt)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True)
    p.add_argument("--token-env", default="GITHUB_TOKEN")
    p.add_argument("--max-parallel", type=int, default=4)
    a = p.parse_args()
    summary, rows, failures = scan(GitHubReader(os.environ.get(a.token_env, "")), max_parallel=a.max_parallel)
    receipt = write_outputs(a.out, summary, rows, failures)
    print(json.dumps({"scope": summary["scope"], "open_items": summary["open_items"],
                      "open_prs": summary["open_prs"], "manifestations": summary["manifestations"],
                      "unknown": summary["prs_unknown"], "file_receipt": receipt}, sort_keys=True))
    # Partial APIs are visible and nonfatal; never equate UNKNOWN with a green PR.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
