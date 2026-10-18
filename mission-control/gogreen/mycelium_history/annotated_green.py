#!/usr/bin/env python3
"""W10 append-only CODEX check-run / annotated-GREEN return.

Consumes native GitHub checks with immutable commit identities. No mutation,
no credential fallback, no raw annotations, no merge/coverage/root authority.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = "/repos/GBOGEB/CODEX"
API = "https://api.github.com"
SHA40 = re.compile(r"^[a-f0-9]{40}$")
SCHEMA = "missioncontrol.mycelium.annotated_green_w10.v1"
STATE = {"completed", "queued", "in_progress", "requested", "waiting", "pending"}
CONCLUSION = {"success", "failure", "cancelled", "skipped", "neutral",
              "timed_out", "action_required", "startup_failure"}
LEVELS = {"notice", "warning", "failure"}


def require(ok, reason):
    if not ok:
        raise ValueError("W10_CHECKS_HOLD: " + reason)


def native_get(path, token):
    require(bool(token), "CROSS_REPO_READ_TOKEN required; no public fallback")
    require(path.startswith(ROOT + "/") and "://" not in path and "//" not in path,
            "external API endpoint")
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "code-purple-mycelium-w10-readonly",
               "X-GitHub-Api-Version": "2022-11-28",
               "Authorization": "Bearer " + token}
    req = Request(API + path, headers=headers, method="GET")
    with urlopen(req, timeout=30) as resp:
        return json.load(resp)


def sha_of(branch):
    sha = (branch.get("commit") or {}).get("sha")
    require(isinstance(sha, str) and SHA40.fullmatch(sha), "branch source head")
    return sha


def list_merged(fetch, limit=3):
    require(type(limit) is int and 1 <= limit <= 5, "bounded PR limit")
    docs = fetch(ROOT + "/pulls?state=closed&sort=updated&direction=desc&per_page=100&page=1")
    require(isinstance(docs, list), "closed PR return")
    candidates = []
    for p in docs:
        if p.get("merged_at") is None or (p.get("base") or {}).get("ref") != "main":
            continue
        head = (p.get("head") or {}).get("sha")
        require(isinstance(head, str) and SHA40.fullmatch(head), "merged PR head")
        require(type(p.get("number")) is int and p["number"] > 0,
                "merged PR number")
        candidates.append({"number": p["number"], "head": head,
                           "merged_at": p["merged_at"]})
    candidates.sort(key=lambda x: (x["merged_at"], x["number"]), reverse=True)
    selected, seen = [], set()
    for pr in candidates:
        if pr["number"] not in seen:
            seen.add(pr["number"])
            selected.append(pr)
        if len(selected) == limit:
            break
    return selected


def check_run(raw, source_sha):
    require(isinstance(raw, dict), "check-run object")
    ident = raw.get("id")
    require(type(ident) is int and ident > 0, "check ID")
    require(raw.get("head_sha") == source_sha, "check HEAD not source-bound")
    name = raw.get("name")
    require(isinstance(name, str) and name.strip(), "check name")
    status, conclusion = raw.get("status"), raw.get("conclusion")
    require(status in STATE, "unknown check status")
    require((status == "completed" and conclusion in CONCLUSION) or
            (status != "completed" and conclusion is None),
            "check status-conclusion mismatch")
    ann = (raw.get("output") or {}).get("annotations_count")
    require(ann is None or (type(ann) is int and ann >= 0),
            "annotation count invalid")
    return {"id": ident, "name": name[:180], "head_sha": source_sha,
            "status": status, "conclusion": conclusion,
            "annotation_count": ann, "completed_at": raw.get("completed_at"),
            "url": "https://github.com/GBOGEB/CODEX/actions/runs" +
                   ("/" + str(ident) if False else ""),
            "annotation_severity": "UNKNOWN_NOT_INSPECTED",
            "annotation_levels": None}


def get_commit_checks(fetch, sha, max_pages=4):
    require(isinstance(sha, str) and SHA40.fullmatch(sha), "commit SHA")
    page_url = ROOT + "/commits/" + sha + "/check-runs?per_page=100&page="
    first = fetch(page_url + "1")
    require(isinstance(first, dict) and type(first.get("total_count")) is int and
            first["total_count"] >= 0 and
            isinstance(first.get("check_runs"), list), "check-run population")
    total = first["total_count"]
    observed, ids = [], set()
    drift = False
    for page in range(1, min(max_pages, max(1, (total + 99) // 100)) + 1):
        d = first if page == 1 else fetch(page_url + str(page))
        require(isinstance(d, dict) and isinstance(d.get("check_runs"), list),
                "missing check page")
        if d.get("total_count") != total:
            drift = True
        for raw in d["check_runs"]:
            item = check_run(raw, sha)
            require(item["id"] not in ids, "duplicate check-run ID")
            ids.add(item["id"])
            observed.append(item)
        if len(d["check_runs"]) < 100:
            break
    complete = (len(observed) == total and not drift)
    return {"head_sha": sha, "api_total": total, "observed": len(observed),
            "complete": complete, "page_drift": drift, "checks": observed}


def priority(item):
    name = item["name"].lower()
    rank = (0 if "test" in name else
            1 if "validate" in name else
            2 if "governance" in name else
            3 if "security" in name else 4)
    return (rank, -(item["annotation_count"] or 0), item["id"])


def read_level_sample(fetch, cohort, limit=6):
    require(0 <= limit <= 12, "annotation detail probe cap")
    candidates = sorted((x for x in cohort["checks"]
                         if x["conclusion"] == "success" and
                         x["annotation_count"] is not None and
                         x["annotation_count"] > 0), key=priority)
    for item in candidates[:limit]:
        count = item["annotation_count"]
        if count > 100:
            item["annotation_severity"] = "UNKNOWN_TOO_MANY_ANNOTATIONS"
            continue
        path = ROOT + "/check-runs/" + str(item["id"]) + "/annotations?per_page=100&page=1"
        try:
            response = fetch(path)
        except HTTPError as err:
            if err.code in (401, 403, 404, 429):
                item["annotation_severity"] = "UNKNOWN_HTTP_" + str(err.code)
                continue
            raise
        require(isinstance(response, list), "annotation detail is not a list")
        if len(response) != count:
            item["annotation_severity"] = "UNKNOWN_COUNT_MISMATCH"
            continue
        vals = Counter()
        for ann in response:
            require(isinstance(ann, dict) and ann.get("annotation_level") in LEVELS,
                    "invalid annotation level")
            vals[ann["annotation_level"]] += 1
        item["annotation_levels"] = dict(sorted(vals.items()))
        item["annotation_severity"] = "SOURCE_BOUND_LEVELS_VERIFIED"
        # Privacy boundary: never emit annotation raw message, title or file path.
    return cohort


def cohort_rollup(cohort):
    checks = cohort["checks"]
    positive = [x for x in checks if x["conclusion"] == "success"]
    annotated = [x for x in positive if type(x["annotation_count"]) is int
                 and x["annotation_count"] > 0]
    known = [x for x in positive if type(x["annotation_count"]) is int]
    levels_ok = [x for x in annotated
                 if x["annotation_severity"] == "SOURCE_BOUND_LEVELS_VERIFIED"]
    errors_known = sum(x["annotation_levels"].get("failure", 0) for x in levels_ok)
    return {
        "head_sha": cohort["head_sha"], "check_runs_observed": cohort["observed"],
        "check_runs_api_total": cohort["api_total"],
        "complete": cohort["complete"],
        "successful_checks": len(positive),
        "successful_checks_with_count": len(known),
        "successful_annotated_checks_observed": len(annotated),
        "annotation_items_reported": sum(x["annotation_count"] for x in annotated),
        "detail_severity_verified_check_count": len(levels_ok),
        "verified_failure_level_items_in_sample": errors_known,
        "total_failure_level_annotations": None,
        "total_notice_level_annotations": None,
        "total_warning_level_annotations": None,
        "sample_is_complete_annotation_severity": (
            len(levels_ok) == len(annotated) and len(known) == len(positive)
            and cohort["complete"]),
        "terminal_red_check_count": sum(
            x["conclusion"] in {"failure", "timed_out", "action_required",
                                "startup_failure"} for x in checks),
        "unknown_or_pending_check_count": sum(
            x["status"] != "completed" for x in checks),
        "annotated_green_does_not_imply_error_severity": True,
        "causal_root_accepted": 0,
    }


def collect(fetch, *, pr_limit=3, detail_limit=6):
    main0 = sha_of(fetch(ROOT + "/branches/main"))
    prs = list_merged(fetch, limit=pr_limit)
    cohorts = [{"kind": "CURRENT_MAIN", "pr": None, "head_sha": main0}]
    cohorts.extend({"kind": "MERGED_PR_HEAD", "pr": p["number"],
                    "head_sha": p["head"], "merged_at": p["merged_at"]}
                   for p in prs)
    out = []
    for entry in cohorts:
        try:
            census = get_commit_checks(fetch, entry["head_sha"])
            read_level_sample(fetch, census, limit=detail_limit)
            rollup = cohort_rollup(census)
            out.append({**entry, "availability": "CHECK_RUN_API_OBSERVED",
                        "metrics": rollup,
                        "checks": census["checks"]})
        except HTTPError as err:
            if err.code not in (401, 403, 404, 429):
                raise
            out.append({**entry, "availability": "SOURCE_READ_BLOCKED_HTTP_" + str(err.code),
                        "metrics": None, "checks": []})
    main1 = sha_of(fetch(ROOT + "/branches/main"))
    return {
        "schema": SCHEMA, "producer_repo": "GBOGEB/CODEX",
        "consumer_repo": "GBOGEB/pipeline-automation-hub",
        "capture_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "last_accepted_w9_hub_merge_sha":
            "2cc9b4d433c404b50d7afc661f863b96d42e97cc",
        "main_sha_before": main0, "main_sha_after": main1,
        "main_head_unchanged_during_capture": main0 == main1,
        "selection": "MAIN_PLUS_3_LATEST_MERGED_FROM_FIRST_100_UPDATED_CLOSED",
        "source_bound_cohorts": out,
        "cohort_count": len(out),
        "annotated_green_is_severity_agnostic": True,
        "error_level_annotation_population_complete": False,
        "accepted_root_closures": 0,
        "merge_authorized": False, "qps_owner_accepted": False,
        "security_waiver": False, "public_deployed": False,
        "worker_hours": None, "capacity_slots": None,
        "M1": "PARTIAL_SOURCE_BOUND",
        "M2": "HOLD_CORRELATED_COHORT",
        "M3": "HOLD_NO_STABLE_CAPABILITY",
        "PCA": "NOT_QUALIFIED", "BT": "NOT_QUALIFIED",
        "admission": "HOLD",
    }


def validate(data, expected_sha):
    require(data.get("schema") == SCHEMA and
            data.get("consumer_repo") == "GBOGEB/pipeline-automation-hub",
            "annotated-green schema")
    require(data.get("hub_source_sha") == expected_sha and
            SHA40.fullmatch(expected_sha), "exact hub head")
    require(data.get("admission") == "HOLD" and
            data.get("merge_authorized") is False and
            data.get("security_waiver") is False and
            data.get("accepted_root_closures") == 0 and
            data.get("qps_owner_accepted") is False and
            data.get("public_deployed") is False,
            "false admission or root credit")
    require(data.get("worker_hours") is None and
            data.get("capacity_slots") is None, "falsified capacity")
    require(isinstance(data.get("source_bound_cohorts"), list) and
            data.get("cohort_count") == len(data["source_bound_cohorts"]),
            "cohort denominator")
    for c in data["source_bound_cohorts"]:
        require(SHA40.fullmatch(c["head_sha"]), "cohort SHA")
        if c["metrics"] is None:
            require(c["availability"].startswith("SOURCE_READ_BLOCKED_HTTP_"),
                    "unmeasured cohort claimed success")
        else:
            m = c["metrics"]
            require(m["head_sha"] == c["head_sha"], "cohort binding")
            require(m["successful_annotated_checks_observed"] <=
                    m["successful_checks"] <= m["check_runs_observed"] <=
                    m["check_runs_api_total"], "invalid check denominator")
            require(m["total_failure_level_annotations"] is None and
                    m["annotated_green_does_not_imply_error_severity"] is True,
                    "invented full error severity")
    return True


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--source-sha", required=True)
    p.add_argument("--validate", action="store_true")
    args = p.parse_args()
    require(bool(SHA40.fullmatch(args.source_sha)), "40-hex source SHA required")
    if args.validate:
        data = json.loads(args.output.read_text(encoding="utf-8"))
    else:
        token = os.environ.get("GITHUB_TOKEN")
        require(bool(token), "authorized GitHub token required")
        data = collect(lambda path: native_get(path, token))
        data["hub_source_sha"] = args.source_sha
        data["run_id"] = (int(os.environ["GITHUB_RUN_ID"])
                          if os.environ.get("GITHUB_RUN_ID") else None)
        data["run_attempt"] = (int(os.environ["GITHUB_RUN_ATTEMPT"])
                               if os.environ.get("GITHUB_RUN_ATTEMPT") else None)
        data["numeric_job_id"] = None
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(data, sort_keys=True,
                                         indent=2) + "\n", encoding="utf-8")
    validate(data, args.source_sha)
    summary = [{**{"kind": x["kind"], "PR": x["pr"],
                    "availability": x["availability"]},
                **({"annotated_green": x["metrics"]["successful_annotated_checks_observed"],
                    "all_checks": x["metrics"]["check_runs_observed"],
                    "severity_complete": x["metrics"]["sample_is_complete_annotation_severity"]}
                   if x["metrics"] else {})}
               for x in data["source_bound_cohorts"]]
    print(json.dumps({"W10": "APPEND_ONLY", "source_sha": args.source_sha,
                      "cohorts": summary, "admission": "HOLD"},
                     sort_keys=True))


if __name__ == "__main__":
    main()
