#!/usr/bin/env python3
"""Authenticated GET-only Github telemetry; source freshness, run/job/attempt, no dispatch.

A sample of jobs is NOT the entire exact-head check population. Unknown access,
rate limits, missing steps and different heads remain explicit unknowns.
"""
from __future__ import annotations
import argparse
import datetime
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHA = re.compile(r"^[0-9a-f]{40}$")
REPO = re.compile(r"^GBOGEB/[A-Za-z0-9_.-]+$")
ORIGIN = "https://api.github.com"
SCHEMA = "missioncontrol.recursive_recovery.native_readback.v1"


def source_sha(x):
    if not isinstance(x, str) or not SHA.fullmatch(x):
        raise ValueError("SOURCE_SHA_MISSING_OR_INVALID")
    return x


def classify_job(job):
    steps = job.get("steps")
    if job.get("conclusion") != "failure":
        return {"kind": "NONFAILURE_OR_NONTERMINAL", "step": None}
    if not isinstance(steps, list) or not any(s.get("status") == "completed" for s in steps):
        return {"kind": "NO_EXECUTED_STEP_HABITAT_OR_UNKNOWN", "step": None}
    failures = [x for x in steps if x.get("conclusion") == "failure"]
    return {"kind": "EXECUTED_GT0_FIRST_RED_STEP_NAME_ONLY" if failures else "FAILED_UNKNOWN_STEP",
            "step": failures[0].get("name") if failures else None}


class Reader:
    """GET only, authenticated token never serialized."""
    def __init__(self, token=None):
        self.token = token if token is not None else os.getenv("GITHUB_TOKEN", "")
    def get(self, endpoint):
        if not endpoint.startswith("/repos/GBOGEB/") or ".." in endpoint or "\\" in endpoint:
            raise ValueError("UNAPPROVED_GITHUB_ENDPOINT")
        headers = {"Accept": "application/vnd.github+json",
                   "User-Agent": "mission-control-n12-readonly-1.0",
                   "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        req = urllib.request.Request(ORIGIN + endpoint, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=14) as response:
            return json.load(response)


def attempt_get(reader, url):
    try:
        return reader.get(url), None
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 404, 429):
            return None, "INACCESSIBLE_OR_RATE_LIMITED_HTTP_" + str(e.code)
        return None, "GITHUB_HTTP_" + str(e.code)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return None, "NETWORK_OR_RUNTIME_UNKNOWN_" + type(e).__name__


def trim_checks(checks):
    if checks is None:
        return {"quality": "UNKNOWN_UNAVAILABLE", "counts": None, "total_count": None}
    rows = checks.get("check_runs")
    n = checks.get("total_count")
    if not isinstance(rows, list) or not isinstance(n, int):
        return {"quality": "UNKNOWN_MALFORMED", "counts": None, "total_count": None}
    counts = {}
    for c in rows:
        k = (c.get("status") or "unknown") + "/" + (c.get("conclusion") or "-")
        counts[k] = counts.get(k, 0) + 1
    return {"quality": "COMPLETE_FIRST_PAGE" if len(rows) == n else "TRUNCATED_MORE_PAGES",
            "counts": counts, "total_count": n,
            "checks_returned": len(rows)}


def sample_jobs(reader, repo, run, max_jobs):
    number = run.get("id")
    if not isinstance(number, int) or not isinstance(run.get("run_attempt"), int):
        return {"state": "UNKNOWN_RUN_ID_OR_ATTEMPT", "jobs": []}
    payload, error = attempt_get(reader, "/repos/" + repo + "/actions/runs/" + str(number) +
                                 "/jobs?per_page=" + str(max_jobs))
    if error:
        return {"state": error, "run": number, "attempt": run["run_attempt"], "jobs": []}
    rows = payload.get("jobs")
    total = payload.get("total_count")
    if not isinstance(rows, list) or not isinstance(total, int):
        return {"state": "UNKNOWN_MALFORMED_JOB_PAGE", "run": number, "attempt": run["run_attempt"], "jobs": []}
    jobs = []
    for job in rows:
        j = {"id": job.get("id"), "run": number, "attempt": run["run_attempt"],
             "name": job.get("name"), "status": job.get("status"), "conclusion": job.get("conclusion"),
             "runner_id": job.get("runner_id"), "started_at": job.get("started_at"),
             "completed_at": job.get("completed_at"), "first_red": classify_job(job)}
        jobs.append(j)
    return {"state": "COMPLETE" if len(rows) == total else "TRUNCATED_MORE_PAGES",
            "run": number, "attempt": run["run_attempt"], "total_jobs": total, "jobs": jobs}


def collect(reader, config):
    if config.get("authority_transfer") is not False or config.get("execution_mode") != "GET_ONLY_NO_RERUN":
        raise ValueError("UNAUTHORIZED_COLLECTOR_CONFIG")
    seen = set()
    results = []
    sampled_jobs, sampled_failures, sampled_successes = 0, 0, 0
    for target in config["targets"]:
        repo = target["repo"]
        if not REPO.fullmatch(repo) or repo in seen:
            raise ValueError("INVALID_OR_DUPLICATE_REPOSITORY")
        seen.add(repo)
        branch = target["branch"]
        row = {"repo": repo, "branch": branch, "authority": target["class"],
               "source_head_sha": None, "source_quality": "UNKNOWN", "prs": [], "issues": []}
        br, er = attempt_get(reader, "/repos/" + repo + "/branches/" + urllib.parse.quote(branch, safe=""))
        if er:
            row["source_quality"] = er
        else:
            try:
                row["source_head_sha"] = source_sha(br["commit"]["sha"])
                row["source_quality"] = "EXACT_DEFAULT_BRANCH_GITHUB_API"
            except (ValueError, KeyError, TypeError):
                row["source_quality"] = "UNKNOWN_BRANCH_SOURCE_IDENTITY"
        for n in target.get("issues", []):
            if not isinstance(n, int) or n < 1:
                raise ValueError("INVALID_ISSUE_ID")
            issue, er = attempt_get(reader, "/repos/" + repo + "/issues/" + str(n))
            row["issues"].append({"number": n, "state": issue.get("state") if issue else None,
                                  "observed": er is None, "error": er, "evidence_class": "ISSUE_OBJECT_NOT_ROOT_CLOSURE"})
        for n in target.get("prs", []):
            if not isinstance(n, int) or n < 1:
                raise ValueError("INVALID_PR_ID")
            p, er = attempt_get(reader, "/repos/" + repo + "/pulls/" + str(n))
            if er:
                row["prs"].append({"number": n, "state": "UNKNOWN", "error": er, "head_sha": None})
                continue
            try:
                head = source_sha(p["head"]["sha"])
                base = source_sha(p["base"]["sha"])
            except (ValueError, KeyError, TypeError):
                row["prs"].append({"number": n, "state": "UNKNOWN", "error": "MALFORMED_PR_SHA", "head_sha": None})
                continue
            info = {"number": n, "state": p.get("state"), "merged": p.get("merged"),
                    "head_sha": head, "base_sha": base, "base_branch": p["base"].get("ref"),
                    "source_class": "GITHUB_PR_HEAD_METADATA", "check_runs": None,
                    "runs": [], "native_acceptance": "NOT_INFERRED"}
            checks, er = attempt_get(reader, "/repos/" + repo + "/commits/" + head + "/check-runs?per_page=100")
            info["check_runs"] = trim_checks(checks)
            if er:
                info["check_runs"]["error"] = er
            runs, er = attempt_get(reader, "/repos/" + repo + "/actions/runs?head_sha=" + head + "&per_page=100")
            if er:
                info["run_access_error"] = er
            else:
                all_runs = runs.get("workflow_runs") or []
                if not isinstance(all_runs, list):
                    all_runs = []
                    info["run_access_error"] = "UNKNOWN_MALFORMED_RUNS"
                if runs.get("total_count", 0) > len(all_runs):
                    info["run_access_error"] = "RUN_LIST_TRUNCATED"
                exact = [x for x in all_runs if x.get("head_sha") == head and isinstance(x.get("run_attempt"), int)]
                exact.sort(key=lambda x: (x.get("created_at") or "", x["id"]), reverse=True)
                for run in exact[:config["max_runs_per_pr"]]:
                    rec = {"id": run["id"], "head_sha": head, "attempt": run["run_attempt"],
                           "name": run.get("name"), "status": run.get("status"),
                           "conclusion": run.get("conclusion"), "url": run.get("html_url")}
                    rec["job_receipt"] = sample_jobs(reader, repo, run, config["max_jobs_per_run"])
                    for job in rec["job_receipt"]["jobs"]:
                        sampled_jobs += 1
                        sampled_failures += job["conclusion"] == "failure"
                        sampled_successes += job["conclusion"] == "success"
                    info["runs"].append(rec)
                info["total_matching_runs_reported"] = runs.get("total_count")
                info["sample_limit_runs"] = config["max_runs_per_pr"]
            row["prs"].append(info)
        results.append(row)
    observation = {"schema": SCHEMA,
                   "observed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   "authority_transfer": False, "mutation_enabled": False,
                   "merge_admission": "HOLD", "source_class": "NATIVE_GITHUB_AUTHENTICATED_GET_OBSERVATION",
                   "source_limitations": ["Cross-repo token access can fail; unknown not zero",
                                          "Jobs sampled only from at most the two newest run records per PR",
                                          "GitHub head_sha association does not prove job checkout provenance",
                                          "No submitted review/ruleset or QPS acceptance proof inferred",
                                          "Run success does not transfer engineering authority"],
                   "targets": results,
                   "sampling": {"target_repos": len(results), "source_accessible_repos":
                                sum(r["source_quality"] == "EXACT_DEFAULT_BRANCH_GITHUB_API" for r in results),
                                "sampled_jobs": sampled_jobs, "sampled_success_jobs": sampled_successes,
                                "sampled_failed_jobs": sampled_failures, "is_complete_ci_population": False},
                   "dispatch_count": 0, "root_closure_credit": None}
    observation["semantic_sha256"] = hashlib.sha256(json.dumps(observation, sort_keys=True).encode()).hexdigest()
    return observation


def verify(data):
    if data.get("schema") != SCHEMA or data.get("authority_transfer") is not False:
        raise ValueError("SCHEMA_OR_AUTHORITY")
    if data.get("mutation_enabled") is not False or data.get("merge_admission") != "HOLD":
        raise ValueError("ILLEGAL_ADMISSION_PROMOTION")
    if data.get("dispatch_count") != 0 or data.get("root_closure_credit") is not None:
        raise ValueError("FORGED_WORKER_OR_ROOT")
    for row in data.get("targets", []):
        if row.get("source_head_sha") is not None:
            source_sha(row["source_head_sha"])
        for pr in row.get("prs", []):
            if pr.get("head_sha") is not None:
                source_sha(pr["head_sha"])
            if pr.get("native_acceptance") not in ("NOT_INFERRED", None):
                raise ValueError("FORGED_GATE")
            for run in pr.get("runs", []):
                if run.get("head_sha") != pr.get("head_sha") or run.get("attempt", 0) < 1:
                    raise ValueError("STALE_RUN_OR_BAD_ATTEMPT")
                for job in run["job_receipt"].get("jobs", []):
                    if job["run"] != run["id"] or job["attempt"] != run["attempt"]:
                        raise ValueError("JOB_RUN_ATTEMPT_MISMATCH")
    return True


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--config", default=str(HERE / "N12_NATIVE_TARGETS.json"))
    p.add_argument("--out", required=True)
    p.add_argument("--require-controller", action="store_true")
    args = p.parse_args(argv)
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    obs = collect(Reader(), config)
    verify(obs)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(obs, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    control = obs["targets"][0]
    complete = control["source_quality"] == "EXACT_DEFAULT_BRANCH_GITHUB_API"
    print(json.dumps({"status": "PARTIAL_PROJECTION_NEVER_ADMISSION",
                      "targets": len(obs["targets"]), **obs["sampling"],
                      "controller_bound": complete, "file": str(out)}))
    if args.require_controller and not complete:
        raise SystemExit("NO_CONTROLLER_SOURCE_IDENTITY: HOLD")


if __name__ == "__main__":
    main()
