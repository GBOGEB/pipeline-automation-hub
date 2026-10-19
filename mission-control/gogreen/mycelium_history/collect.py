#!/usr/bin/env python3
"""Get-only, bounded CODEX Mycelium Actions history snapshot.

The workflow-specific API is the source of run population. This collector is
not a second BD ledger, a merger, a CI dispatcher, or a source of formal credit.
All non-atomic, partial, censored and unauthorized observations stay explicit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = "GBOGEB/CODEX"
WORKFLOW = "missioncontrol-mycelium.yml"
API = "https://api.github.com"
SHA40 = re.compile(r"^[a-f0-9]{40}$")
TERMINAL = {"success", "failure", "cancelled", "skipped", "timed_out",
            "neutral", "action_required"}
SCHEMA = "missioncontrol.mycelium.history_capture.v1"


def demand(value, message):
    if not value:
        raise ValueError("MYCELIUM_CAPTURE_HOLD: " + message)


def request_json(path, *, token=None):
    demand(path.startswith("/repos/GBOGEB/CODEX/") and "//" not in path
           and "://" not in path, "external or unsafe request")
    headers = {"Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28",
               "User-Agent": "mycelium-readonly-history-census"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(API + path, headers=headers, method="GET")
    with urllib.request.urlopen(request, timeout=35) as response:
        value = json.load(response)
    demand(isinstance(value, (dict, list)), "GitHub API unexpected document type")
    return value


def normalize_run(raw, expected_workflow_id=None):
    demand(isinstance(raw, dict), "run object")
    run_id, attempt = raw.get("id"), raw.get("run_attempt")
    head = raw.get("head_sha")
    demand(type(run_id) is int and run_id > 0 and
           type(attempt) is int and attempt > 0 and
           isinstance(head, str) and SHA40.fullmatch(head), "run identity")
    if expected_workflow_id is not None:
        demand(raw.get("workflow_id") == expected_workflow_id, "wrong workflow ID")
    status, conclusion = raw.get("status"), raw.get("conclusion")
    demand(status in {"completed", "queued", "in_progress", "requested",
                      "waiting", "pending"}, "unknown run status")
    demand((status != "completed" and conclusion is None) or
           (status == "completed" and conclusion in TERMINAL),
           "run is not terminal but claims a conclusion")
    return {
        "id": run_id, "attempt": attempt, "workflow_id": raw.get("workflow_id"),
        "name": raw.get("name", "UNKNOWN"), "status": status,
        "conclusion": conclusion, "head_sha": head,
        "event": raw.get("event"), "head_branch": raw.get("head_branch"),
        "created_at": raw.get("created_at"), "updated_at": raw.get("updated_at"),
        "run_started_at": raw.get("run_started_at"),
        "url": "https://github.com/" + REPO + "/actions/runs/" + str(run_id),
        "previous_attempts_collected": attempt == 1,
    }


def read_run_pages(fetch, *, max_runs=1000, max_pages=12):
    base = "/repos/" + REPO + "/actions/workflows/" + WORKFLOW + "/runs"
    first = fetch(base + "?per_page=100&page=1")
    total = first.get("total_count")
    demand(type(total) is int and total >= 0, "total count UNKNOWN")
    demand(isinstance(first.get("workflow_runs"), list), "missing workflow runs")
    expected_id = None
    if first["workflow_runs"]:
        expected_id = first["workflow_runs"][0].get("workflow_id")
        demand(type(expected_id) is int and expected_id > 0, "workflow identity")
    rows, pages, duplicates = [], 0, []
    seen = set()
    limited = total > max_runs or (total + 99) // 100 > max_pages
    limit_pages = min(max_pages, (min(total, max_runs) + 99) // 100)
    for page in range(1, max(1, limit_pages) + 1):
        d = first if page == 1 else fetch(base + "?per_page=100&page=" + str(page))
        demand(isinstance(d.get("workflow_runs"), list), "unreadable run page")
        if d.get("total_count") != total:
            limited = True  # Snapshot is non-atomic, never claim full population.
        pages += 1
        for raw in d["workflow_runs"]:
            row = normalize_run(raw, expected_id)
            if row["id"] in seen:
                duplicates.append(row["id"])
                limited = True
                continue
            seen.add(row["id"])
            rows.append(row)
        if len(d["workflow_runs"]) < 100:
            break
    complete = (not limited and not duplicates and len(rows) == total)
    return {"runs": rows, "api_total_count": total, "observed_run_count": len(rows),
            "page_count": pages, "run_inventory_complete": complete,
            "pagination_nonatomic_or_capped": not complete,
            "duplicated_ids": duplicates[:20],
            "workflow_id": expected_id}


def normalize_job(raw, run_id, attempt):
    demand(isinstance(raw, dict) and type(raw.get("id")) is int and
           raw["id"] > 0, "job identity")
    steps = []
    for step in raw.get("steps") or []:
        demand(isinstance(step, dict), "invalid step")
        status, conclusion = step.get("status"), step.get("conclusion")
        demand(status in (None, "completed", "in_progress", "pending", "queued"),
               "step status invalid")
        steps.append({
            "number": step.get("number"), "name": str(step.get("name", ""))[:220],
            "status": status, "conclusion": conclusion,
            "started_at": step.get("started_at"),
            "completed_at": step.get("completed_at"),
        })
    first = next((s for s in steps if s["conclusion"] == "failure"), None)
    subsequent = [s["name"] for s in steps
                  if first is not None and
                  type(s["number"]) is int and type(first["number"]) is int
                  and s["number"] > first["number"] and
                  s["conclusion"] == "skipped"]
    return {
        "id": raw["id"], "run_id": run_id, "attempt": attempt,
        "name": str(raw.get("name", "UNKNOWN"))[:200],
        "status": raw.get("status"), "conclusion": raw.get("conclusion"),
        "started_at": raw.get("started_at"), "completed_at": raw.get("completed_at"),
        "steps": steps, "first_failed_step": first["name"] if first else None,
        "downstream_skipped_steps": subsequent,
        "log_bytes_sha256": None, "log_first_error": None,
        "log_read_status": "NOT_REQUESTED",
    }


def read_jobs(fetch, run, *, max_pages=4):
    uri = "/repos/" + REPO + "/actions/runs/" + str(run["id"]) + "/jobs"
    first = fetch(uri + "?per_page=100&page=1")
    total = first.get("total_count")
    demand(type(total) is int and total >= 0 and
           isinstance(first.get("jobs"), list), "missing jobs denominator")
    jobs, pages = [], 0
    seen = set()
    for page in range(1, min(max_pages, max(1, (total + 99) // 100)) + 1):
        page_json = first if page == 1 else fetch(
            uri + "?per_page=100&page=" + str(page))
        demand(page_json.get("total_count") == total, "job denominator changed")
        for job in page_json["jobs"]:
            norm = normalize_job(job, run["id"], run["attempt"])
            demand(norm["id"] not in seen, "duplicate job ID")
            seen.add(norm["id"])
            jobs.append(norm)
        pages += 1
    return {"run_id": run["id"], "attempt": run["attempt"], "jobs": jobs,
            "api_job_total": total, "jobs_complete": len(jobs) == total,
            "job_pages": pages,
            "previous_attempts_collected": run["attempt"] == 1}


def parse_error(log: bytes):
    """Return a safe error CLASS, never arbitrary untrusted raw log text.

    Log SHA-256 retains a byte-level identity. The readable artifact must not
    disclose tokens, private paths, user emails or terminal output contents.
    """
    value = log[:3_000_000].decode("utf-8", errors="replace")
    for line in value.splitlines():
        if "##[error]" not in line or "echo " in line:
            continue
        clue = line.split("##[error]", 1)[1].strip().lower()
        if "inventory" in clue and ("drift" in clue or "generated" in clue):
            return "GENERATED_EXECUTABLE_INVENTORY_DRIFT"
        if "untracked public" in clue or "stale artifact" in clue:
            return "PUBLICATION_MANIFEST_DRIFT"
        if "pr-007" in clue or "governance header" in clue:
            return "GOVERNANCE_HEADER_FIRST_RED"
        if "timeout" in clue or "timed out" in clue:
            return "EXECUTION_TIMEOUT"
        if "401" in clue or "403" in clue or "permission denied" in clue:
            return "OWNER_AUTHORIZATION_GATE"
        if "test" in clue or "assert" in clue:
            return "NATIVE_TEST_ASSERTION"
        return "UNCLASSIFIED_ERROR_" + hashlib.sha256(
            clue.encode("utf-8")).hexdigest()[:12]
    return None


def get_log_bytes(job_id, *, token=None):
    path = "/repos/" + REPO + "/actions/jobs/" + str(job_id) + "/logs"
    demand(type(job_id) is int and job_id > 0, "log job ID")
    req = urllib.request.Request(
        API + path, headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "mycelium-readonly-log-first-red",
            **({"Authorization": "Bearer " + token} if token else {}),
        }, method="GET")
    with urllib.request.urlopen(req, timeout=40) as stream:
        result = stream.read(3_000_001)
    demand(len(result) <= 3_000_000, "log exceeds bounded readable size")
    return result


def select_for_jobs(runs, max_jobs):
    """Use explicitly stratified red/green recent samples, never random fleet rate.

    Source cohort is complete workflow RUN metadata; JOB detail is sampled.
    Prefer 5/8 red and 3/8 green when both populations exist. Missing strata
    lend capacity to the other cohort without manufacturing green observations.
    """
    demand(type(max_jobs) is int and max_jobs > 0, "job selection size")
    candidates = sorted(runs, key=lambda r: (r["created_at"] or "", r["id"]),
                        reverse=True)
    reds = [r for r in candidates if r["conclusion"] in
            {"failure", "timed_out", "action_required"}]
    greens = [r for r in candidates if r["conclusion"] == "success"]
    other = [r for r in candidates if r not in reds and r not in greens]
    red_quota = max(1, (5 * max_jobs + 7) // 8) if reds else 0
    green_quota = max_jobs - red_quota if greens else 0
    selected = reds[:red_quota] + greens[:green_quota]
    chosen = {r["id"] for r in selected}
    for row in reds[red_quota:] + greens[green_quota:] + other:
        if len(selected) >= max_jobs:
            break
        if row["id"] not in chosen:
            selected.append(row)
            chosen.add(row["id"])
    return selected


def merged_pr_sample(fetch, *, max_pages=2):
    """Bounded closed PR sample, never a complete historic merge denominator."""
    found = []
    for page in range(1, max_pages + 1):
        arr = fetch("/repos/" + REPO +
                    "/pulls?state=closed&sort=updated&direction=desc&per_page=100&page=" +
                    str(page))
        demand(isinstance(arr, list), "merged PR page invalid")
        for pr in arr:
            if pr.get("merged_at") is None:
                continue
            head = (pr.get("head") or {}).get("sha")
            merge_sha = pr.get("merge_commit_sha")
            demand(isinstance(head, str) and SHA40.fullmatch(head),
                   "PR head missing")
            found.append({
                "number": pr["number"], "title": str(pr.get("title", ""))[:250],
                "head_sha": head,
                "merge_sha": (merge_sha if isinstance(merge_sha, str)
                              and SHA40.fullmatch(merge_sha) else None),
                "base": (pr.get("base") or {}).get("ref"),
                "merged_at": pr["merged_at"],
                "url": "https://github.com/" + REPO + "/pull/" + str(pr["number"]),
            })
        if len(arr) < 100:
            break
    return found


def collect(fetch, get_logs, *, max_runs=1000, max_job_runs=120,
            max_failure_logs=18):
    branch0 = fetch("/repos/" + REPO + "/branches/main")
    sha0 = (branch0.get("commit") or {}).get("sha")
    demand(isinstance(sha0, str) and SHA40.fullmatch(sha0), "CODEX main SHA")
    inventory = read_run_pages(fetch, max_runs=max_runs)
    runs = inventory["runs"]
    details = {}
    selected = select_for_jobs(runs, max_job_runs)
    failures_read = 0
    attempted_log_reads = 0
    unreadable_log_attempts = 0
    job_errors = []
    for run in selected:
        try:
            detail = read_jobs(fetch, run)
        except (ValueError, urllib.error.HTTPError, urllib.error.URLError) as error:
            job_errors.append({"run_id": run["id"], "kind":type(error).__name__})
            continue
        for job in detail["jobs"]:
            if (attempted_log_reads < max_failure_logs and
                job["first_failed_step"] is not None):
                attempted_log_reads += 1
                try:
                    raw = get_logs(job["id"])
                    job["log_bytes_sha256"] = hashlib.sha256(raw).hexdigest()
                    job["log_first_error"] = parse_error(raw)
                    job["log_read_status"] = "READ_BOUNDED"
                    failures_read += 1
                except (ValueError, urllib.error.HTTPError, urllib.error.URLError) as e:
                    unreadable_log_attempts += 1
                    job["log_read_status"] = type(e).__name__.upper()
        details[str(run["id"])] = detail
    prs = merged_pr_sample(fetch)
    branch1 = fetch("/repos/" + REPO + "/branches/main")
    sha1 = (branch1.get("commit") or {}).get("sha")
    demand(isinstance(sha1, str) and SHA40.fullmatch(sha1), "CODEX current SHA")
    return {
        "schema": SCHEMA, "repository": REPO, "workflow_file": WORKFLOW,
        "capture_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_main_before": sha0, "source_main_after": sha1,
        "source_main_stable_during_scan": sha0 == sha1,
        **inventory,
        "selected_job_details": details,
        "job_detail_policy": "STRATIFIED_FIVE_EIGHTHS_RED_THREE_EIGHTHS_GREEN_NOT_RANDOM",
        "selected_job_run_count": len(details),
        "job_detail_error_count": len(job_errors), "job_detail_errors": job_errors[:100],
        "failure_log_reads": failures_read,
        "log_read_attempts": attempted_log_reads,
        "unreadable_log_attempts": unreadable_log_attempts,
        "older_attempts_collected": all(r["attempt"] == 1 for r in runs),
        "merged_pr_sample": prs, "merged_pr_sample_is_complete": False,
        "merge_admission": "HOLD", "authority_transfer": False,
        "security_waiver": False, "qps_acceptance": "WITHHELD",
        "root_closure_credit": 0, "worker_hours": None,
        "runner_capacity_slots": None,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--max-runs", type=int, default=1000)
    p.add_argument("--job-detail-limit", type=int, default=160)
    p.add_argument("--failure-log-limit", type=int, default=18)
    args = p.parse_args()
    demand(0 < args.max_runs <= 1200 and
           0 < args.job_detail_limit <= args.max_runs and
           0 <= args.failure_log_limit <= 40, "bounds")
    token = os.environ.get("GITHUB_TOKEN")
    demand(bool(token), "authenticated read-only GitHub token required")
    # No no-token fallback if authorized source APIs reject this identity.
    result = collect(lambda path: request_json(path, token=token),
                     lambda job_id: get_log_bytes(job_id, token=token),
                     max_runs=args.max_runs,
                     max_job_runs=args.job_detail_limit,
                     max_failure_logs=args.failure_log_limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({
        "observed": result["observed_run_count"],
        "api_total": result["api_total_count"],
        "complete": result["run_inventory_complete"],
        "detail_jobs": result["selected_job_run_count"],
        "errors": result["job_detail_error_count"],
        "merge_admission": "HOLD",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
