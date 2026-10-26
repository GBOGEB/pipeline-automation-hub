"""Bounded GitHub Actions GREEN scout; metadata-only and never dispatched automatically.

Read exact-SHA workflow/job statuses from declared catalog repositories. Workflow
name category is a candidate hint, not verified test/scope provenance. Errors
remain explicit UNKNOWN and remote repositories are never written to.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from spine import _check_catalog, build, canonical, emit

API = "https://api.github.com"


def get_json(path, token):
    if not path.startswith("/repos/") or ".." in path or "//" in path:
        raise ValueError("GitHub path outside authorized repository surface")
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "GOGREEN-G0-ReadOnly-Scout",
               "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(API + path, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=12) as resp:
        return json.load(resp)


def family_hint(name, allowed):
    x = name.lower()
    groups = (
        ("security", ("security", "bandit", "codeql", "osv", "semgrep", "vulnerab")),
        ("coverage", ("coverage", "mip b0", "branch proof")),
        ("runtime", ("docker", "rhel", "ubi", "lldb", "kubernetes", "port")),
        ("qps_triage", ("qps triage", "qps-triage", "qps perpetual")),
        ("math_model", ("math", "monte carlo", "pca", "bradley", "m02b")),
        ("federation", ("federation", "bridge", "mycelium", "golden thread")),
        ("artifact", ("artifact", "pages", "render", "pdf", "release")),
    )
    for family, matches in groups:
        if any(term in x for term in matches) and family in allowed:
            return family
    return "ci_contract"  # fall back to generic observed CI, not guessed native test family


def scan(catalog, fetcher, max_runs=2, max_jobs=3):
    if type(max_runs) is not int or not 1 <= max_runs <= 8:
        raise ValueError("max_runs must be 1..8")
    if type(max_jobs) is not int or not 1 <= max_jobs <= 8:
        raise ValueError("max_jobs must be 1..8")
    declared = _check_catalog(catalog["repositories"])
    old = list(catalog["observations"])
    seen = {(o["repository"], o["run_id"], o["run_attempt"], o["job_id"]) for o in old}
    summaries, errors, first_reds = [], [], []
    observations = old[:]
    for repo, entry in sorted(declared.items()):
        sha = entry["head_sha"]
        prefix = "/repos/" + repo
        row = {"repository": repo, "source_sha": sha, "runs_considered": 0,
               "successful_jobs_seen": 0, "truncated": None, "fetch_state": "UNKNOWN"}
        try:
            obj = fetcher(prefix + "/actions/runs?" + urllib.parse.urlencode({
                "head_sha": sha, "per_page": max_runs}))
            runs = obj.get("workflow_runs")
            if not isinstance(runs, list):
                raise ValueError("workflow_runs must be array")
            total = obj.get("total_count")
            row["truncated"] = total > len(runs) if type(total) is int else None
            row["runs_considered"] = len(runs)
            row["fetch_state"] = "OBSERVED_PARTIAL_SAMPLE"
            for run in runs:
                if run.get("head_sha") != sha:
                    errors.append({"repository": repo, "run_id": run.get("id"),
                                   "kind": "RUN_SHA_MISMATCH"})
                    continue
                rid, attempt = run.get("id"), run.get("run_attempt")
                if type(rid) is not int or rid < 1 or type(attempt) is not int or attempt < 1:
                    errors.append({"repository": repo, "kind": "INVALID_RUN_IDENTITY"})
                    continue
                if run.get("status") != "completed" or run.get("conclusion") != "success":
                    first_reds.append({"repository": repo, "sha": sha,
                                       "run_id": rid, "run_attempt": attempt,
                                       "workflow": run.get("name"),
                                       "status": run.get("status"),
                                       "conclusion": run.get("conclusion"),
                                       "root_id": None, "classification": "UNATTRIBUTED_OBSERVATION"})
                    continue
                try:
                    jobs_obj = fetcher(prefix + f"/actions/runs/{rid}/jobs?per_page={max_jobs}")
                    jobs = jobs_obj.get("jobs")
                    if not isinstance(jobs, list):
                        raise ValueError("jobs must be array")
                except (ValueError, KeyError, urllib.error.HTTPError, urllib.error.URLError) as exc:
                    errors.append({"repository": repo, "run_id": rid,
                                   "kind": "JOB_FETCH_UNAVAILABLE", "error_type": type(exc).__name__})
                    continue
                for job in jobs:
                    job_id = job.get("id")
                    if type(job_id) is not int or job_id <= 0:
                        errors.append({"repository": repo, "run_id": rid, "kind": "INVALID_JOB_ID"})
                        continue
                    if job.get("status") != "completed" or job.get("conclusion") != "success":
                        first_reds.append({"repository": repo, "sha": sha,
                                           "run_id": rid, "job_id": job_id,
                                           "run_attempt": attempt,
                                           "status": job.get("status"), "conclusion": job.get("conclusion"),
                                           "root_id": None, "classification": "UNATTRIBUTED_OBSERVATION"})
                        continue
                    key = (repo, rid, attempt, job_id)
                    if key in seen:
                        continue
                    seen.add(key)
                    row["successful_jobs_seen"] += 1
                    observations.append({
                        "repository": repo, "source_sha": sha, "base_sha": None,
                        "family": family_hint(str(run.get("name") or ""), entry["target_families"]),
                        "suite_id": str(job.get("name") or "job:" + str(job_id)),
                        "workflow_name": run.get("name"),
                        "discovery_basis": "WORKFLOW_NAME_HEURISTIC_UNVERIFIED",
                        "run_id": rid, "run_number": run.get("run_number"),
                        "run_attempt": attempt, "job_id": job_id,
                        "run_url": f"https://github.com/{repo}/actions/runs/{rid}",
                        "workflow_status": "completed", "workflow_conclusion": "success",
                        "job_status": "completed", "job_conclusion": "success",
                        "evidence_class": "GITHUB_NATIVE_METADATA",
                        "config_identity": "UNKNOWN", "test_counts": None,
                        "scoped_burndown": None, "artifact": None,
                    })
        except (ValueError, KeyError, urllib.error.HTTPError, urllib.error.URLError) as exc:
            row["fetch_state"] = "UNKNOWN_ERROR"
            errors.append({"repository": repo, "kind": "RUN_FETCH_UNAVAILABLE",
                           "error_type": type(exc).__name__})
        summaries.append(row)
    result = dict(catalog, observations=observations)
    # Strict schema verification catches mismatched job/run provenance before writing.
    build(result)
    metadata = {
        "schema": "gogreen.readonly-scout.v1", "mode": "PASSIVE_GET_ONLY",
        "requested_runs_per_repo": max_runs, "requested_jobs_per_run": max_jobs,
        "repositories": summaries, "unattributed_non_green": first_reds,
        "collection_errors": errors, "external_authority_transfer": False,
        "security_waiver": False, "worker_dispatches": 0,
        "complete_fleet_census": False,
        "method": "Bounded sample of actions/runs and jobs pinned to declared SHA; status-only without native tool/config/test/artifact proof",
    }
    return result, metadata


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--catalog", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--max-runs", type=int, default=2)
    ap.add_argument("--max-jobs", type=int, default=3)
    args = ap.parse_args()
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    token = os.environ.get("GITHUB_TOKEN", "")
    result, metadata = scan(catalog, lambda path: get_json(path, token), args.max_runs, args.max_jobs)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "live_intake.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    (args.out / "live_scanner_metadata.json").write_text(json.dumps(metadata, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    emit(result, args.out)
    print(canonical({"errors": len(metadata["collection_errors"]),
                     "unknown_failures": len(metadata["unattributed_non_green"]),
                     "status_only_observations": build(result)[0]["breadth"]["native_green_status_only_observations"]}))


if __name__ == "__main__":
    main()
