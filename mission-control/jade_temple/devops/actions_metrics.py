#!/usr/bin/env python3
"""JADE FOCUS5 Actions usage + performance metrics: per workflow, per repo and fleet total.

Rebuilds the columns of the two GitHub Insights pages (Actions usage metrics, Actions
performance metrics) from the REST run and job records. The same rows then exist for every
repo in the JADE FOCUS5 roster, plus a fleet total. It is read-only and never dispatches,
reruns or cancels anything.

Binding (AGENTS.md L5): each repo row records the default-branch head SHA, read once per
pulse, and each workflow row records the blob OID of its workflow file at that SHA.
Dynamic workflows such as `dynamic/github-code-scanning/codeql` have no file, so their OID
is null. Where the DevOps census lists the repo, its `head_sha` is copied next to ours, and
`same_pulse` says whether the two match.

Two tiers, never mixed:
  * run tier (full coverage): runs, run failure / cancel rates, run wall time, run-level queue
    time and the trigger-event mix, all from the runs list.
  * job tier (cached sample): job runs, billable minutes (each job rounded up to a whole
    minute, as billing does), job run time, job queue time, job failure rate and failed-job
    minutes. Rows carry `job_coverage` = runs with jobs read / runs. Below 1.0 every job-tier
    figure is OBSERVED over that sample. `est_total_minutes` is the only extrapolated figure,
    and it is labelled as such.

Completed runs and their job lists are immutable, so --cache keeps them per run attempt.
Each pulse fetches only new runs and spends at most --job-budget job calls per repo, spread
round-robin over (ISO week, workflow) so that no week or workflow goes unsampled.
History therefore builds up across pulses, and `weekly` gives every workflow its ISO-week
series.

  python devops/actions_metrics.py fetch   --cache C:/repos/_cache/jade-actions --since 2026-10-01 [--job-budget 1500]
  python devops/actions_metrics.py project --cache C:/repos/_cache/jade-actions --since 2026-10-01 \\
         --out data/ACTIONS_METRICS_FOCUS5.json [--csv site/actions_metrics.csv]
"""
from __future__ import annotations

import argparse
import hashlib
import concurrent.futures
import csv
import importlib.util
import json
import math
import os
import re
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent  # mission-control/jade_temple


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PB = _load("jade_private_boundary", ROOT / "tools" / "private_boundary.py")
BQ = _load("gogreen_bd_queue_wave", ROOT.parent / "gogreen" / "bd_queue_wave.py")  # owner of utc(), percentile()
STRATA_DOC = "job lists are fetched round-robin over (ISO week, workflow), newest first per stratum"

SCHEMA = "jade.devops.actions-metrics.v1"
ROSTER = ROOT / "data" / "FOCUS5_POINT_RELEASE_NPLUS7.json"  # the FOCUS5 object the CI/CD DAG pins
CENSUS = ROOT / "data" / "DEVOPS_CENSUS_N11.json"
API = "https://api.github.com"
FAILED = {"failure", "timed_out", "startup_failure"}
PAGE_CAP = 10  # the runs search returns at most 1000 records per query

# Duration bands over the mean job run time (the Insights "Avg run time" sort).
BANDS = ((10, "B0_INSTANT_<10s"), (60, "B1_SHORT_10s-1m"), (300, "B2_MEDIUM_1-5m"),
         (900, "B3_LONG_5-15m"), (math.inf, "B4_VERY_LONG_>15m"))
# Workflow role, first match on "<name> <path>". Used to bind test, check and experimental data.
_r = lambda p: re.compile(p, re.I)
CLASSES = (
    ("SECURITY", _r(r"codeql|security|secret|dependabot|scorecard|bandit|semgrep|osv|token.census")),
    ("GATE", _r(r"gate|guard|closure|required|admission|fail.?closed|first.?red|everred|red.trace|contract|"
                r"policy|integrity")),
    ("TEST_QA", _r(r"\btests?\b|test-|pytest|\bqa\b|-qa\b|qualification|regression|coverage|smoke|verify|\bci\b")),
    ("CENSUS_TELEMETRY", _r(r"census|telemetry|metric|pulse|recon|triage|harvest|frequency|history|ledger")),
    ("EXPERIMENT_PROBE", _r(r"probe|experiment|proof|\bbt\b|-bt\b|pca|sandbox|spike|frontier|launchpad|pilot|"
                            r"testflight|monte.carlo|reference|bridge")),
    ("BUILD_DEPLOY", _r(r"build|deploy|pages|publish|release|site|dashboard|atlas|render")),
    ("DOCS_LINT", _r(r"lint|format|markdown|docs?\b|yaml|link")),
)


def band(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    return next(label for top, label in BANDS if seconds < top)


def wf_class(name: str, path: str) -> str:
    text = f"{name} {path}"
    return next((label for label, rx in CLASSES if rx.search(text)), "OTHER")


def seconds(a, b) -> float | None:
    t0, t1 = BQ.utc(a), BQ.utc(b)
    if not (t0 and t1):
        return None
    s = (t1 - t0).total_seconds()
    return s if 0 <= s <= 86400 * 7 else None


def runner_of(job: dict) -> tuple[str, str]:
    labels = [str(x).lower() for x in job.get("labels") or []]
    hosted = "self-hosted" not in labels and (job.get("runner_group_name") in (None, "GitHub Actions")
                                              or any(re.match(r"(ubuntu|windows|macos)-", x) for x in labels))
    os_ = next((o for o, k in (("linux", "ubuntu"), ("windows", "windows"), ("macos", "macos"), ("linux", "linux"))
                if any(k in x for x in labels)), "unknown")
    return ("hosted" if hosted else "self-hosted"), os_


def mean(xs):
    return round(statistics.fmean(xs), 1) if xs else None


def pct(n, d):
    return round(100.0 * n / d, 1) if d else None


# --------------------------------------------------------------------------------------- fetch

def token() -> str:
    """gh keyring first (respects GH_TOKEN in CI); a stale user-level GITHUB_TOKEN is the fallback only."""
    try:
        env = {k: v for k, v in os.environ.items() if k != "GITHUB_TOKEN"}
        out = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=20, env=env)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return os.environ.get("GITHUB_TOKEN", "")


class Reader:
    def __init__(self, tok: str = "", base: str = API):
        self.tok, self.base, self.calls = tok, base.rstrip("/"), 0

    def get(self, route: str) -> dict:
        if not route.startswith("/") or ".." in route.split("?")[0] or "\\" in route:
            raise ValueError("noncanonical API path")
        req = urllib.request.Request(self.base + route, headers={
            "Accept": "application/vnd.github+json", "User-Agent": "jade-actions-metrics-v1",
            **({"Authorization": "Bearer " + self.tok} if self.tok else {})})
        for attempt in range(4):  # transient socket / 5xx only; 4xx is an answer, not a retry
            self.calls += 1
            try:
                with urllib.request.urlopen(req, timeout=40) as r:
                    return json.load(r)
            except urllib.error.HTTPError as exc:
                if exc.code < 500 or attempt == 3:
                    raise
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                if attempt == 3:
                    raise
            time.sleep(2 ** attempt * 3)

    def pages(self, route: str, key: str) -> tuple[list, int]:
        out, total = [], 0
        for page in range(1, PAGE_CAP + 1):
            sep = "&" if "?" in route else "?"
            data = self.get(f"{route}{sep}per_page=100&page={page}")
            items, total = data.get(key) or [], data.get("total_count", 0)
            out.extend(items)
            if len(items) < 100:
                break
        return out, total


RUN_KEYS = ("id", "name", "path", "event", "status", "conclusion", "created_at", "run_started_at", "updated_at",
            "run_attempt", "head_branch")
JOB_KEYS = ("id", "run_id", "run_attempt", "name", "status", "conclusion", "created_at", "started_at",
            "completed_at", "labels", "runner_group_name")


def slim(rec: dict, keys) -> dict:
    return {k: rec.get(k) for k in keys}


def repo_dir(cache: Path, repo: str) -> Path:
    return Path(cache) / repo.replace("/", "__")


def fetch_runs_day(rd: Reader, repo: str, day: date) -> list:
    """All runs created on one UTC day; hour slices when the day exceeds the 1000-record search cap."""
    route = f"/repos/{repo}/actions/runs?created={day.isoformat()}"
    runs, total = rd.pages(route, "workflow_runs")
    if total > len(runs):
        runs, seen = [], set()
        for h in range(24):
            lo, hi = f"{day}T{h:02d}:00:00Z", f"{day}T{h:02d}:59:59Z"
            part, ptotal = rd.pages(f"/repos/{repo}/actions/runs?created={lo}..{hi}", "workflow_runs")
            if ptotal > len(part):
                raise ValueError(f"{repo} {lo}: {ptotal} runs in one hour exceeds the search cap")
            runs.extend(r for r in part if r["id"] not in seen and not seen.add(r["id"]))
    return [slim(r, RUN_KEYS) for r in runs]


def stratified(runs: list) -> list:
    """Round-robin over (ISO week, workflow), newest first in each stratum.

    A newest-first budget only samples the last days and hides past queue storms. This order
    gives every week and every workflow job-tier coverage before any stratum gets a second run.
    """
    strata = defaultdict(list)
    for r in sorted(runs, key=lambda r: r["created_at"], reverse=True):
        strata[(iso_week(r["created_at"]), r.get("path") or "")].append(r)
    queues, out = [strata[k] for k in sorted(strata, reverse=True)], []
    while queues:
        out.extend(q.pop(0) for q in queues)
        queues = [q for q in queues if q]
    return out


def fetch(cache: Path, repos: list, since: date, until: date, job_budget: int, rd: Reader,
          workers: int = 6, log=print) -> dict:
    today = datetime.now(timezone.utc).date()
    summary = {}
    for repo in repos:
        d = repo_dir(cache, repo)
        (d / "runs").mkdir(parents=True, exist_ok=True)
        (d / "jobs").mkdir(parents=True, exist_ok=True)
        day, fetched_days = since, 0
        try:
            while day <= until:
                p = d / "runs" / f"{day}.json"
                stale = not p.exists() or day >= today - timedelta(days=1) or any(
                    r["status"] != "completed" for r in json.loads(p.read_text(encoding="utf-8")))
                if stale:
                    p.write_text(json.dumps(fetch_runs_day(rd, repo, day), sort_keys=True), encoding="utf-8", newline="\n")
                    fetched_days += 1
                day += timedelta(days=1)
        except (urllib.error.URLError, ValueError) as exc:  # one unreadable repo is UNKNOWN, not a fleet abort
            summary[repo] = {"error": f"{type(exc).__name__}: {exc}"[:200], "stopped_at": day.isoformat()}
            log(f"{repo}: {summary[repo]}")
            continue
        runs = [r for r in load_runs(cache, repo, since, until) if r["status"] == "completed"]
        missing = [r for r in runs if not (d / "jobs" / f"{r['id']}-{r['run_attempt']}.json").exists()]
        todo = stratified(missing)[:max(0, job_budget)]

        def one(r):
            jobs, _ = rd.pages(f"/repos/{repo}/actions/runs/{r['id']}/jobs?filter=all", "jobs")
            (d / "jobs" / f"{r['id']}-{r['run_attempt']}.json").write_text(
                json.dumps([slim(j, JOB_KEYS) for j in jobs], sort_keys=True), encoding="utf-8", newline="\n")

        errors = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
            for fut in concurrent.futures.as_completed([ex.submit(one, r) for r in todo]):
                try:
                    fut.result()
                except (urllib.error.URLError, ValueError, OSError):
                    errors += 1
        summary[repo] = {"days_fetched": fetched_days, "runs": len(runs), "job_lists_fetched": len(todo) - errors,
                         "job_errors": errors}
        log(f"{repo}: {summary[repo]}")
    return summary


def load_runs(cache: Path, repo: str, since: date, until: date) -> list:
    out, day = {}, since
    while day <= until:
        p = repo_dir(cache, repo) / "runs" / f"{day}.json"
        if p.exists():
            for r in json.loads(p.read_text(encoding="utf-8")):
                out[r["id"]] = r
        day += timedelta(days=1)
    return list(out.values())


def load_jobs(cache: Path, repo: str, run: dict) -> list | None:
    p = repo_dir(cache, repo) / "jobs" / f"{run['id']}-{run['run_attempt']}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def head_and_oids(rd: Reader, repo: str) -> dict:
    """Default branch, its head SHA and the blob OID of every workflow file at that SHA (one pulse)."""
    meta = rd.get(f"/repos/{repo}")
    branch = meta["default_branch"]
    sha = rd.get(f"/repos/{repo}/commits/{branch}")["sha"]
    oids = {}
    try:
        tree = rd.get(f"/repos/{repo}/git/trees/{sha}:.github/workflows")
        oids = {f".github/workflows/{t['path']}": t["sha"] for t in tree.get("tree", []) if t["type"] == "blob"}
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
    return {"branch": branch, "head_sha": sha, "visibility": meta.get("visibility"), "oids": oids}


# ------------------------------------------------------------------------------------- project

def aggregate(runs: list, jobs_by_run: dict) -> dict:
    """The Insights columns over one set of runs (a workflow, a repo, or the fleet)."""
    read = [r for r in runs if jobs_by_run.get(r["id"]) is not None]
    jobs = [j for r in read for j in jobs_by_run[r["id"]] if j.get("conclusion") != "skipped"]
    skipped = sum(1 for r in read for j in jobs_by_run[r["id"]] if j.get("conclusion") == "skipped")
    run_s = [s for j in jobs if (s := seconds(j.get("started_at"), j.get("completed_at"))) is not None]
    queue_s = [s for j in jobs if (s := seconds(j.get("created_at"), j.get("started_at"))) is not None]
    failed = [j for j in jobs if j.get("conclusion") in FAILED]
    billable = sum(math.ceil(s / 60) for j in jobs
                   if (s := seconds(j.get("started_at"), j.get("completed_at"))))
    failed_min = sum(math.ceil(s / 60) for j in failed
                     if (s := seconds(j.get("started_at"), j.get("completed_at"))))
    runners = Counter(runner_of(j) for j in jobs)
    # Wall time of the latest attempt only; created -> run_started measures rerun delay, not queueing,
    # so queue time is job-tier only (job created -> started, as Insights reports it).
    wall = [s for r in runs if (s := seconds(r.get("run_started_at"), r.get("updated_at"))) is not None]
    concl = Counter(r.get("conclusion") or r.get("status") for r in runs)
    cov = round(len(read) / len(runs), 4) if runs else None
    return {
        # run tier
        "workflow_runs": len(runs),
        "run_failure_rate": pct(sum(concl[c] for c in FAILED), len(runs)),
        "run_cancel_rate": pct(concl["cancelled"], len(runs)),
        "rerun_rate": pct(sum(1 for r in runs if (r.get("run_attempt") or 1) > 1), len(runs)),
        "avg_run_wall_s": mean(wall), "p50_run_wall_s": BQ.percentile(wall, 0.5),
        "p95_run_wall_s": BQ.percentile(wall, 0.95),
        "events": dict(Counter(r.get("event") for r in runs).most_common()),
        "conclusions": dict(concl.most_common()),
        # job tier
        "job_coverage": cov,
        "jobs": len({j.get("name") for j in jobs}),
        "job_runs": len(jobs), "jobs_skipped": skipped,
        "total_minutes": billable,
        "est_total_minutes": round(billable / cov) if cov else None,
        "runner_type": "/".join(sorted({k for k, _ in runners})) or None,
        "runtime_os": "/".join(sorted({o for _, o in runners})) or None,
        "has_job_failures_pct": pct(sum(1 for r in read if any(
            j.get("conclusion") in FAILED for j in jobs_by_run[r["id"]])), len(read)),
        "avg_job_run_s": mean(run_s), "p50_job_run_s": BQ.percentile(run_s, 0.5),
        "p95_job_run_s": BQ.percentile(run_s, 0.95),
        "avg_job_queue_s": mean(queue_s), "p50_job_queue_s": BQ.percentile(queue_s, 0.5),
        "p95_job_queue_s": BQ.percentile(queue_s, 0.95),
        "job_failure_rate": pct(len(failed), len(jobs)),
        "failed_job_minutes": failed_min,
    }



# B09 / RF goal observation. This *canonical* Actions Metrics owner computes the
# run-record share; the RF planner compares the value to a policy threshold but
# may not recompute it or turn it into merge authority.
RECHECK_WORKFLOW_NAME = "GOGREEN Required Gate Re-check"
PRESSURE_SCHEMA = "jade.devops.recheck-pressure.v1"
PRESSURE_SAMPLE_METHOD = "last_1000_repo_workflow_runs"


def missing_run_days(cache: Path, repo: str, since: date, until: date) -> list[str]:
    """Days in [since, until] that have no cached runs file (an incomplete source window)."""
    out, day = [], since
    while day <= until:
        if not (repo_dir(cache, repo) / "runs" / f"{day}.json").is_file():
            out.append(day.isoformat())
        day += timedelta(days=1)
    return out


def recheck_pressure(runs: list[dict], repo: str, source_sha: str,
                     observed_at: str, sample_size: int = 1000,
                     missing_days: list[str] | None = None) -> dict:
    """Project a source-bound, fixed-count run cohort without confusing runs and jobs.

    source_sha is the *collector's* exact repository head for this pulse, not a
    claim that all historical workflow runs originated at that SHA.
    The receipt hash is reproducibility evidence, not an independently verified
    GitHub artifact attestation or merge predicate.

    Only completed runs enter the cohort. Any missing source-window day
    (missing_days) keeps the observation PARTIAL_UNKNOWN with a null value, so
    an interrupted fetch cannot yield a stale "last 1000" cohort.
    """
    if not isinstance(source_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise ValueError("pressure requires exact collector source_sha")
    if not isinstance(repo, str) or "/" not in repo or ".." in repo:
        raise ValueError("pressure requires owner/repo identity")
    if not isinstance(sample_size, int) or isinstance(sample_size, bool) or sample_size != 1000:
        raise ValueError("pressure contract is the last 1000 runs, no silent denominator change")
    observed = BQ.utc(observed_at)
    if observed is None or not isinstance(runs, list):
        raise ValueError("pressure requires UTC observation and run list")
    ids = set()
    for rec in runs:
        if (not isinstance(rec, dict) or not isinstance(rec.get("id"), int) or
                isinstance(rec.get("id"), bool) or rec["id"] <= 0 or
                rec["id"] in ids or not isinstance(rec.get("name"), str) or
                not rec["name"] or BQ.utc(rec.get("created_at")) is None):
            raise ValueError("duplicate, malformed or missing workflow-run evidence")
        if BQ.utc(rec["created_at"]) > observed:
            raise ValueError("workflow run created after observation")
        ids.add(rec["id"])
    missing = sorted(set(missing_days or []))
    completed = [rec for rec in runs if rec.get("status") == "completed"]
    selected = sorted(completed, key=lambda rec: (BQ.utc(rec["created_at"]), rec["id"]),
                      reverse=True)[:sample_size]
    n = len(selected)
    complete = n == sample_size and not missing
    # Canonical cohort identity: the fields this metric reads, per selected run.
    cohort = [[rec["id"], rec.get("run_attempt"), rec["created_at"], rec["name"],
               rec.get("event"), rec.get("conclusion")] for rec in selected]
    cohort_sha = hashlib.sha256(json.dumps(cohort, separators=(",", ":"), ensure_ascii=True)
                                .encode("utf-8")).hexdigest()
    target = [rec for rec in selected if rec.get("name") == RECHECK_WORKFLOW_NAME and
              rec.get("event") == "workflow_run"]
    conclusions = Counter(rec.get("conclusion") or rec.get("status") or "UNKNOWN" for rec in target)
    # A sub-1000 cohort is incomplete. Report counts, not a 0% success rate.
    doc = {"schema": PRESSURE_SCHEMA,
           "metric": "recheck_workflow_record_share",
           "metric_owner": "mission-control/jade_temple/devops/actions_metrics.py",
           "repository": repo, "source_sha": source_sha,
           "source_binding": "collector_repo_head_not_all_historical_run_heads",
           "observed_at": observed_at,
           "sample_method": PRESSURE_SAMPLE_METHOD, "sample_n": n,
           "expected_n": sample_size,
           "record_type": "SOURCE_BOUND_OBSERVATION_NOT_ADMISSION",
           "coverage": "COMPLETE" if complete else "PARTIAL_UNKNOWN",
           "value": round(len(target) / n, 6) if complete else None,
           "missing_source_days": missing,
           "excluded_incomplete_runs": len(runs) - len(completed),
           "cohort_sha256": cohort_sha,
           "recheck_records": len(target),
           "recheck_cancelled": conclusions.get("cancelled", 0),
           "recheck_outcomes": dict(sorted(conclusions.items())),
           "cohort_earliest": selected[-1]["created_at"] if selected else None,
           "cohort_latest": selected[0]["created_at"] if selected else None,
           "method_note": "workflow-run records, not executed tests or billable job-minutes",
           "merge_authorized": False}
    payload = json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    doc["receipt_sha256"] = hashlib.sha256(payload).hexdigest()
    return doc


def iso_week(ts: str) -> str:
    y, w, _ = BQ.utc(ts).isocalendar()
    return f"{y}-W{w:02d}"


def weekly(runs: list, jobs_by_run: dict) -> dict:
    out = defaultdict(lambda: {"runs": 0, "failed_runs": 0, "minutes": 0, "job_runs": 0})
    for r in runs:
        wk = out[iso_week(r["created_at"])]
        wk["runs"] += 1
        wk["failed_runs"] += r.get("conclusion") in FAILED
        for j in jobs_by_run.get(r["id"]) or []:
            s = seconds(j.get("started_at"), j.get("completed_at"))
            if j.get("conclusion") != "skipped":
                wk["job_runs"] += 1
                wk["minutes"] += math.ceil(s / 60) if s else 0
    return dict(sorted(out.items()))


def group(rows: list, key: str) -> dict:
    """Roll workflow rows up by one attribute (class, band, dominant event)."""
    out = defaultdict(lambda: {"workflows": 0, "workflow_runs": 0, "job_runs": 0, "total_minutes": 0,
                               "failed_job_minutes": 0, "failed_jobs": 0})
    for w in rows:
        g = out[w.get(key) or "UNKNOWN"]
        g["workflows"] += 1
        for k in ("workflow_runs", "job_runs", "total_minutes", "failed_job_minutes"):
            g[k] += w.get(k) or 0
        g["failed_jobs"] += round((w.get("job_failure_rate") or 0) * (w.get("job_runs") or 0) / 100)
    for g in out.values():
        g["job_failure_rate"] = pct(g.pop("failed_jobs"), g["job_runs"])
        g["minutes_per_run"] = round(g["total_minutes"] / g["workflow_runs"], 2) if g["workflow_runs"] else None
    return dict(sorted(out.items(), key=lambda kv: -kv[1]["total_minutes"]))


def stratified_estimate(rows: list) -> dict:
    """Repo-level ESTIMATES from per-workflow samples (each workflow scaled by its own coverage).

    The job sample is stratified by workflow, so one repo-wide coverage ratio would over-weight
    rarely-run workflows. Workflows with no job list read add nothing; their runs are counted in
    `est_unsampled_runs`.
    """
    ws = [w for w in rows if w.get("job_coverage")]
    if not ws:
        return {"est_total_minutes": None, "est_job_runs": None, "est_failed_job_minutes": None,
                "est_job_failure_rate": None, "est_unsampled_runs": sum(w["workflow_runs"] for w in rows)}
    jr = sum(w["job_runs"] / w["job_coverage"] for w in ws)
    failed = sum((w["job_failure_rate"] or 0) / 100 * w["job_runs"] / w["job_coverage"] for w in ws)
    return {"est_total_minutes": round(sum(w["total_minutes"] / w["job_coverage"] for w in ws)),
            "est_job_runs": round(jr),
            "est_failed_job_minutes": round(sum(w["failed_job_minutes"] / w["job_coverage"] for w in ws)),
            "est_job_failure_rate": pct(failed, jr),
            "est_unsampled_runs": sum(w["workflow_runs"] for w in rows if not w.get("job_coverage"))}


def repo_metrics(repo: str, runs: list, jobs_by_run: dict, head: dict, census_sha: str | None) -> dict:
    by_wf = defaultdict(list)
    for r in runs:
        by_wf[(r.get("path") or "", r.get("name") or "")].append(r)
    rows = []
    for (path, name), rs in by_wf.items():
        a = aggregate(rs, jobs_by_run)
        rows.append({"workflow": name, "path": path,
                     "blob_oid": head.get("oids", {}).get(path) if path.startswith(".github/") else None,
                     "class": wf_class(name, path), "band": band(a["avg_job_run_s"]),
                     "dominant_event": next(iter(a["events"]), None), **a, "weekly": weekly(rs, jobs_by_run)})
    rows.sort(key=lambda w: (-(w["total_minutes"] or 0), -w["workflow_runs"], w["workflow"]))
    total = {**aggregate(runs, jobs_by_run), **stratified_estimate(rows)}
    return {"repo": repo, "branch": head.get("branch"), "visibility": head.get("visibility"),
            "head_sha": head.get("head_sha"), "census_head_sha": census_sha,
            "same_pulse": None if census_sha is None else census_sha == head.get("head_sha"),
            "totals": total, "weekly": weekly(runs, jobs_by_run),
            "by_class": group(rows, "class"), "by_band": group(rows, "band"),
            "by_event": group(rows, "dominant_event"), "workflows": rows}


def project(cache: Path, repos: list, since: date, until: date, heads: dict, census: dict | None,
            observed_at: str) -> dict:
    census_sha = {r["repo"]: r.get("head_sha") for r in (census or {}).get("repos", [])}
    out, all_runs, all_jobs = [], [], {}
    for repo in repos:
        runs = load_runs(cache, repo, since, until)
        jobs = {r["id"]: load_jobs(cache, repo, r) for r in runs}
        out.append(repo_metrics(repo, runs, jobs, heads.get(repo, {}), census_sha.get(repo)))
        all_runs += runs
        all_jobs.update(jobs)
    wf_rows = [w for r in out for w in r["workflows"]]
    doc = {
        "schema": SCHEMA, "observed_at_utc": observed_at,
        "period": {"since": since.isoformat(), "until": until.isoformat()},
        "roster": {"source": ROSTER.relative_to(ROOT).as_posix(), "repos": repos},
        "method": {"failed_conclusions": sorted(FAILED), "skipped_jobs": "excluded from job runs, minutes and timings",
                   "total_minutes": "sum of per-job ceil(run seconds / 60), the billing rounding",
                   "bands": [label for _, label in BANDS], "classes": [label for label, _ in CLASSES] + ["OTHER"],
                   "job_tier_basis": "OBSERVED over job_coverage; est_* = sum over workflows of observed / that "
                                     "workflow's job_coverage (stratified estimator), ESTIMATE not observation",
                   "job_sample": STRATA_DOC},
        "fleet": {"totals": {**aggregate(all_runs, all_jobs), **{
                      k: (sum(r["totals"][k] for r in out if r["totals"][k] is not None)
                          if any(r["totals"][k] is not None for r in out) else None)
                      for k in ("est_total_minutes", "est_job_runs", "est_failed_job_minutes", "est_unsampled_runs")}},
                  "weekly": weekly(all_runs, all_jobs),
                  "by_class": group(wf_rows, "class"), "by_band": group(wf_rows, "band"),
                  "by_event": group(wf_rows, "dominant_event")},
        "repos": out,
    }
    return PB.project(doc)


CSV_COLS = ("repo", "workflow", "path", "class", "band", "dominant_event", "workflow_runs", "jobs", "job_runs",
            "total_minutes", "est_total_minutes", "runner_type", "runtime_os", "has_job_failures_pct",
            "avg_job_run_s", "p95_job_run_s", "avg_job_queue_s", "p95_job_queue_s", "job_failure_rate",
            "failed_job_minutes", "run_failure_rate", "run_cancel_rate", "rerun_rate", "avg_run_wall_s",
            "job_coverage", "blob_oid")


def write_csv(doc: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLS, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in doc["repos"]:
            for row in r["workflows"]:
                w.writerow({"repo": r["repo"], **row})


def roster(path: Path = ROSTER) -> list:
    return [r["repo"] for r in json.loads(path.read_text(encoding="utf-8"))["rows"]]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("cmd", choices=("fetch", "project", "pressure"))
    p.add_argument("--cache", required=True, type=Path)
    p.add_argument("--since", required=True, type=date.fromisoformat)
    p.add_argument("--until", type=date.fromisoformat, default=datetime.now(timezone.utc).date())
    p.add_argument("--roster", type=Path, default=ROSTER)
    p.add_argument("--repo", action="append", help="limit to these repos (default: the roster)")
    p.add_argument("--job-budget", type=int, default=1500, help="job-list API calls per repo this pulse (stratified by week x workflow)")
    p.add_argument("--census", type=Path, default=CENSUS)
    p.add_argument("--out", type=Path)
    p.add_argument("--csv", type=Path)
    p.add_argument("--source-sha", help="exact collector repository head for pressure observations")
    a = p.parse_args(argv)
    if a.cmd == "pressure":
        if not a.repo or len(a.repo) != 1:
            p.error("pressure requires exactly one --repo")
        observed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        doc = recheck_pressure(load_runs(a.cache, a.repo[0], a.since, a.until),
                               a.repo[0], a.source_sha or "", observed,
                               missing_days=missing_run_days(a.cache, a.repo[0], a.since, a.until))
        txt = json.dumps(doc, sort_keys=True, indent=2) + "\n"
        if a.out:
            a.out.parent.mkdir(parents=True, exist_ok=True)
            a.out.write_text(txt, encoding="utf-8", newline="\n")
        else:
            sys.stdout.write(txt)
        return 0
    repos = a.repo or roster(a.roster)
    rd = Reader(token())
    if a.cmd == "fetch":
        fetch(a.cache, repos, a.since, a.until, a.job_budget, rd)
        print(f"api calls: {rd.calls}")
        return 0
    heads = {}
    for r in repos:
        try:
            heads[r] = head_and_oids(rd, r)
        except (urllib.error.URLError, KeyError) as exc:  # head UNKNOWN: same_pulse stays null, never PASS
            heads[r] = {"error": f"{type(exc).__name__}: {exc}"[:200]}
    census = json.loads(a.census.read_text(encoding="utf-8")) if a.census and a.census.exists() else None
    observed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = project(a.cache, repos, a.since, a.until, heads, census, observed)
    text = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n"
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(text, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(text)
    if a.csv:
        write_csv(doc, a.csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
