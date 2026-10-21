"""QPS TRIAGE read-only per-repository census receiver.

Never executes instructions from the dispatch payload or promotes check metadata
into test/coverage proof. Only recognized GBOGEB repositories may respond.
"""
import argparse
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

LANES = {
    "GBOGEB/ABACUS": "ABACUS",
    "GBOGEB/CODEX": "CODEX",
    "GBOGEB/cryoplant-project": "QPS_ENGINEERING",
}
SHA = re.compile(r"^[a-f0-9]{40}$")
ID = re.compile(r"^QPS-[a-f0-9]{20}$")
MAX_API_PAGES = 4  # Hard cap: 4 x 100 per endpoint, never unbounded read fan-out.
PAGE_SIZE = 100


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def request_id(wave, lane, repo, sha, selector):
    seed = {"wave": wave, "lane": lane, "repo": repo,
            "expected_sha": sha, "selector": selector}
    return "QPS-" + hashlib.sha256(canonical(seed).encode()).hexdigest()[:20]


def check_request(env, route):
    repo, sha = env.get("GITHUB_REPOSITORY"), env.get("GITHUB_SHA")
    lane = LANES.get(repo)
    wave, selector = env.get("QPS_WAVE"), env.get("QPS_SELECTOR")
    requested_id = env.get("QPS_REQUEST_ID")
    expected_sha = env.get("QPS_EXPECTED_SHA")
    if not lane or not isinstance(sha, str) or not SHA.fullmatch(sha):
        raise ValueError("unrecognized repository/execution head")
    if not isinstance(expected_sha, str) or not SHA.fullmatch(expected_sha) or sha != expected_sha:
        raise ValueError("STALE_OR_MISMATCHED_HEAD: regenerate census wave")
    if not wave or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", wave):
        raise ValueError("invalid wave")
    if selector not in ("all", "native_checks", "coverage_catalog"):
        raise ValueError("disallowed selector")
    if route not in ("native_checks", "coverage_catalog"):
        raise ValueError("unknown route")
    if selector != "all" and selector != route:
        raise ValueError("unrequested route")
    if not requested_id or not ID.fullmatch(requested_id):
        raise ValueError("invalid request ID")
    if request_id(wave, lane, repo, sha, selector) != requested_id:
        raise ValueError("request ID not bound to source, wave and selector")
    for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
        if not env.get(key, "").isdigit() or int(env[key]) <= 0:
            raise ValueError("missing real workflow identity " + key)
    return lane


def github_json(env, endpoint):
    token = env.get("GH_TOKEN")
    if not token:
        raise ValueError("read-only GitHub token missing")
    req = urllib.request.Request(
        "https://api.github.com/" + endpoint,
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "QPS-Metric-Census/1.0"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def bounded_github_rows(env, endpoint, field):
    """Read up to 400 stable metadata rows or HOLD; never report partial as full.

    GitHub's jobs/check-runs endpoints both return total_count and a paged list.
    A changing total, duplicate ID, missing page, bool count or excess breadth
    makes the result unusable as native-source observation.
    """
    if field not in ("jobs", "check_runs") or not isinstance(endpoint, str):
        raise ValueError("unsupported bounded evidence route")
    sep = "&" if "?" in endpoint else "?"
    total = None
    rows = []
    seen = set()
    for page in range(1, MAX_API_PAGES + 1):
        url = f"{endpoint}{sep}per_page={PAGE_SIZE}&page={page}"
        response = github_json(env, url)
        if not isinstance(response, dict):
            raise ValueError("untrusted GitHub pagination response")
        count = response.get("total_count")
        current = response.get(field)
        if (type(count) is not int or count < 0 or
                count > PAGE_SIZE * MAX_API_PAGES or
                not isinstance(current, list) or len(current) > PAGE_SIZE):
            raise ValueError("invalid or unbounded GitHub metadata population")
        if total is not None and total != count:
            raise ValueError("GitHub metadata population changed during pagination")
        total = count
        needed = min(PAGE_SIZE, total - len(rows))
        if len(current) != needed:
            raise ValueError("GitHub metadata page incomplete or inconsistent")
        for item in current:
            if not isinstance(item, dict) or type(item.get("id")) is not int or item["id"] <= 0:
                raise ValueError("GitHub metadata object without unique positive ID")
            if item["id"] in seen:
                raise ValueError("duplicate GitHub metadata ID across pages")
            seen.add(item["id"])
        rows.extend(current)
        if len(rows) == total:
            return rows, total
    raise ValueError("GitHub metadata pagination exceeded bounded limit")


def platform_job(env):
    repo, run, target_name = (
        env["GITHUB_REPOSITORY"], env["GITHUB_RUN_ID"], env.get("QPS_JOB_NAME")
    )
    if not target_name:
        raise ValueError("job name missing")
    all_jobs, _ = bounded_github_rows(
        env, "repos/{}/actions/runs/{}/jobs?filter=latest".format(repo, run), "jobs")
    jobs = [j for j in all_jobs
            if j.get("name") == target_name or
            str(j.get("name", "")).endswith(" / " + target_name)]
    if len(jobs) != 1 or type(jobs[0].get("id")) is not int:
        raise ValueError("native job ID not uniquely identified")
    return jobs[0]["id"]


def source_catalog():
    completed = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, check=True, timeout=15
    )
    tracked = [x.strip() for x in completed.stdout.splitlines() if x.strip()]
    tests = [x for x in tracked if (
        x.endswith(".py") and
        (Path(x).name.startswith("test_") or Path(x).name.endswith("_test.py"))
    ) or fnmatch.fnmatch(x, "*/*.test.*")]
    configs = [x for x in tracked if Path(x).name in (
        "pytest.ini", "pyproject.toml", "tox.ini", ".coveragerc", "jest.config.js"
    )]
    return {"tracked_source_files": len(tracked), "candidate_test_files": len(set(tests)),
            "tracked_test_paths": sorted(set(tests))[:100],
            "test_paths_truncated": len(set(tests)) > 100,
            "coverage_config_paths": sorted(set(configs)),
            "executed_test_count": None, "branch_coverage": None,
            "disclaimer": "Source catalog only; no test execution or measured coverage"}


def collect(env, route):
    lane = check_request(env, route)
    job_id = platform_job(env)
    repo, sha = env["GITHUB_REPOSITORY"], env["GITHUB_SHA"]
    payload = source_catalog() if route == "coverage_catalog" else {}
    if route == "native_checks":
        checks, total = bounded_github_rows(
            env, "repos/{}/commits/{}/check-runs".format(repo, sha), "check_runs")
        payload = {"observed_check_runs": len(checks),
                   "reported_total_checks": total,
                   "pagination_complete": True,
                   "check_statuses": [
                       {"id": c.get("id"), "name": c.get("name"),
                        "status": c.get("status"), "conclusion": c.get("conclusion")}
                       for c in checks
                   ], "first_red_root_ids": None,
                   "disclaimer": "Check names/conclusions are not causal-root attribution"}
    return {"schema": "qps-metric-receipt/v1", "repo": repo, "lane": lane,
            "request_id": env["QPS_REQUEST_ID"], "route": route,
            "target_sha": sha, "execution_sha": sha,
            "run_id": int(env["GITHUB_RUN_ID"]),
            "run_attempt": int(env["GITHUB_RUN_ATTEMPT"]),
            "job_id": job_id, "outcome": "SUCCESS",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "evidence_class": "GITHUB_CHECK_METADATA_ONLY", "tests": {}, "coverage": {},
            "observation": payload, "authority_transfer": False,
            "engineering_acceptance": False, "merge_admission": "HOLD"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--route", choices=("native_checks", "coverage_catalog"), required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    try:
        result = collect(os.environ, a.route)
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print("QPS census metadata emitted:", a.output)
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as exc:
        p.exit(2, "QPS_CENSUS_HOLD: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
