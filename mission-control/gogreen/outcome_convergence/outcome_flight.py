#!/usr/bin/env python3
"""G9 complete-window outcome convergence, no green-only survivorship bias.

Run-attempt metadata is a distinct unit from job steps; this is descriptive
snapshot evidence, not independence, causal repair, REX root CONTROL or a
licensed GitHub dispatcher.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

SCHEMA = "gogreen.native-outcome-population.v1"
OUTPUT = "gogreen.outcome-convergence.v1"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
REPOSITORY = re.compile(r"GBOGEB/[A-Za-z0-9_.-]+\Z")
OUTCOMES = frozenset({"success", "failure", "cancelled", "skipped", "timed_out", "action_required", "neutral"})
COMPLETENESS = "COMPLETE_API_FILTERED_BRANCH_DATE_WINDOW_AT_CAPTURE"


def require(condition, why):
    if not condition:
        raise ValueError(why)


def utc(value):
    require(isinstance(value, str) and value.endswith("Z"), "source timestamp UTC required")
    try:
        stamp = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ValueError("malformed UTC timestamp") from error
    require(stamp.utcoffset() == timedelta(0), "non-UTC timestamp")
    return stamp


def positive(value, name):
    require(type(value) is int and value > 0, "positive integer required: " + name)
    return value


def sha(value):
    require(isinstance(value, str) and SHA40.fullmatch(value), "invalid exact SHA")
    return value


def canonical(data):
    return (json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("ascii")


def validate(data):
    require(isinstance(data, dict) and data.get("schema") == SCHEMA, "untrusted population schema")
    require(data.get("authority_transfer") is False and
            data.get("dispatch_authorized") is False and
            data.get("merge_authorized") is False and
            data.get("formal_root_closures") == 0, "forbidden authority or closure")
    require(data.get("collection_is_atomic") is False, "API first pages are not atomic")
    require(data.get("observed_date_utc") == "2026-10-17", "frozen native observation date")
    require(data.get("source") ==
            "GitHub REST Actions branch=main&created=2026-10-16..2026-10-17&per_page=100",
            "source request window/provenance mismatch")
    begin = utc(data.get("window_start_utc"))
    end = utc(data.get("window_end_exclusive_utc"))
    require(begin < end and end - begin == timedelta(days=2), "incorrect comparison window")
    cohorts = data.get("cohorts")
    require(isinstance(cohorts, list) and len(cohorts) == 2,
            "both complete native comparison cohorts are mandatory")
    all_ids, all_urls, repos, rows = set(), set(), set(), []
    for cohort in cohorts:
        require(isinstance(cohort, dict), "invalid cohort")
        repo = cohort.get("repo")
        require(isinstance(repo, str) and REPOSITORY.fullmatch(repo) and repo not in repos,
                "duplicate or invalid canonical repo")
        repos.add(repo)
        require(cohort.get("branch") == "main" and
                cohort.get("window") == "2026-10-16..2026-10-17" and
                cohort.get("population_class") == COMPLETENESS, "noncomparable branch/date scope")
        count = positive(cohort.get("api_total_count"), "api_total_count")
        returned = positive(cohort.get("returned_count"), "returned_count")
        runs = cohort.get("runs")
        require(type(runs) is list and len(runs) == count == returned and count <= 100,
                "incomplete or overlarge first-page census")
        numbered, per_name_and_number = set(), set()
        for row in runs:
            require(isinstance(row, dict), "invalid run record")
            rid = positive(row.get("id"), "run id")
            number = positive(row.get("number"), "run number")
            attempt = positive(row.get("attempt"), "run attempt")
            require(rid not in all_ids, "duplicate native ID across cohorts")
            all_ids.add(rid)
            name = row.get("workflow")
            require(isinstance(name, str) and 0 < len(name) <= 160,
                    "unrecognized workflow identity")
            key = (name, number, attempt)
            require(key not in per_name_and_number, "duplicate per-family run ordinal/attempt")
            per_name_and_number.add(key)
            require(row.get("status") == "completed" and row.get("conclusion") in OUTCOMES,
                    "nonterminal run cannot be included in terminal denominator")
            source_sha = sha(row.get("sha"))
            require(row.get("branch") == "main" and row.get("event") in
                    {"push", "schedule", "workflow_dispatch", "pull_request"},
                    "inconsistent source branch or trigger")
            created = utc(row.get("created_at"))
            started = utc(row.get("run_started_at"))
            updated = utc(row.get("updated_at"))
            require(begin <= created < end, "run outside study time window")
            require(created <= updated and created <= started <= updated,
                    "invalid clock progression")
            require(updated - created <= timedelta(days=2), "stale/unbounded completion proxy")
            uri = f"https://github.com/{repo}/actions/runs/{rid}"
            require(row.get("run_url") == uri and uri not in all_urls,
                    "run URL identity mismatch")
            all_urls.add(uri)
            rows.append({
                "repository": repo, "workflow": name, "id": rid,
                "number": number, "attempt": attempt, "source_sha": source_sha,
                "conclusion": row["conclusion"], "created_at": row["created_at"],
                "run_started_at": row["run_started_at"], "updated_at": row["updated_at"],
                "queue_seconds_proxy": round((started-created).total_seconds(), 3),
                "execution_seconds_proxy": round((updated-started).total_seconds(), 3),
                "run_url": uri,
            })
        require(len(numbered) == 0, "unexpected mutation of first-page census")
    require(repos == {"GBOGEB/gg_MATH", "GBOGEB/cryoplant-project"},
            "unsupported scope expansion without native API proof")
    return rows


def per_family(rows):
    buckets = defaultdict(list)
    for row in rows:
        buckets[(row["repository"], row["workflow"])].append(row)
    results = []
    for (repo, name), group in sorted(buckets.items()):
        seq = sorted(group, key=lambda x: (x["created_at"], x["id"]))
        count = Counter(r["conclusion"] for r in group)
        # Repeated workflows, shared source and correlated fanout are not IID trials.
        # Conditional comparisons are purely descriptive counts.
        successes = count.get("success", 0)
        failures = count.get("failure", 0)
        unique = {r["source_sha"] for r in group}
        distinct_head_outcomes = {}
        for source in sorted(unique):
            members = [r for r in group if r["source_sha"] == source]
            distinct_head_outcomes[source] = dict(sorted(
                Counter(r["conclusion"] for r in members).items()))
        n = len(group)
        start, finish = utc(seq[0]["created_at"]), utc(seq[-1]["created_at"])
        latest = seq[-1]
        results.append({
            "repository": repo, "workflow": name, "observed_total": n,
            "completed_success": successes, "completed_failure": failures,
            "completed_other": n - successes - failures,
            "observed_success_share": round(successes / n, 6),
            "failure_share": round(failures / n, 6),
            "observed_distinct_source_heads": len(unique),
            "source_head_outcomes": distinct_head_outcomes,
            "current_in_window_latest_outcome": latest["conclusion"],
            "last_observed_run_id": latest["id"],
            "window_span_hours": round((finish - start).total_seconds()/3600, 4),
            "execution_seconds_proxy_median": median(
                [r["execution_seconds_proxy"] for r in group]),
            "queue_seconds_proxy_median": median(
                [r["queue_seconds_proxy"] for r in group]),
            "unobserved_ordinals_in_sample": max(
                r["number"] for r in group) - min(r["number"] for r in group)+1 - n,
            "independent_trial_count": None, "causality_attributed": False,
            "native_jobs_complete": False,
            "normalized_first_red_root": None,
        })
    return results


def median(values):
    require(type(values) is list and bool(values) and all(
        isinstance(x, (float,int)) and not isinstance(x, bool) and x >= 0 for x in values),
        "nonempty nonnegative median population required")
    s = sorted(values)
    k = len(s)//2
    return round(float(s[k] if len(s)%2 else (s[k-1]+s[k])/2), 3)


def summarize(data):
    rows = validate(data)
    families = per_family(rows)
    total = len(rows)
    out = Counter(r["conclusion"] for r in rows)
    repo_rows = []
    for repo in ("GBOGEB/gg_MATH", "GBOGEB/cryoplant-project"):
        sample = [r for r in rows if r["repository"] == repo]
        x = Counter(r["conclusion"] for r in sample)
        repo_rows.append({
            "repository": repo, "complete_observed_runs": len(sample),
            "success": x.get("success",0), "failure": x.get("failure",0),
            "cancelled": x.get("cancelled",0),
            "other": len(sample)-x.get("success",0)-x.get("failure",0)-x.get("cancelled",0),
            "workflow_families": len({r["workflow"] for r in sample}),
            "source_heads_observed": len({r["source_sha"] for r in sample}),
            "observed_success_share": round(x.get("success",0)/len(sample),6)
        })
    return {
        "schema": OUTPUT, "observed_date_utc": data["observed_date_utc"],
        "population_class": COMPLETENESS, "scope": "TWO_NATIVE_REPO_BRANCH_WINDOWS",
        "source_window": [data["window_start_utc"],data["window_end_exclusive_utc"]],
        "total_native_runs": total, "complete_branch_windows": len(repo_rows),
        "native_terminal_success": out.get("success",0),
        "native_terminal_failure": out.get("failure",0),
        "native_terminal_cancelled": out.get("cancelled",0),
        "other_terminal": total-out.get("success",0)-out.get("failure",0)-out.get("cancelled",0),
        "per_repository": repo_rows, "per_workflow": families,
        "per_workflow_sample_completeness": "FULL_BRANCH_DATE_POPULATION_AT_CAPTURE",
        "sampled_job_run_join": "REQUIRES_NATIVE_JOB_PAGINATION",
        "actual_runner_capacity": None,
        "queue_seconds_are_started_minus_created_proxy": True,
        "execution_seconds_are_updated_minus_started_proxy": True,
        "uncertainty_intervals": None,
        "independent_native_trials": None,
        "first_red_root_population": None,
        "root_closure_credit": 0, "formal_admission": "HOLD",
        "authority_transfer": False,"dispatch_authorized": False,
        "merge_authorized": False
    }


def sipoc(report):
    nodes = [
        {"id":"S_NATIVE","role":"S","owner":"GitHub Actions API","evidence":"NATIVE_API"},
        {"id":"I_COHORT","role":"I","owner":"GoGREEN G9","evidence":"RUN_ID_ATTEMPT_EXACT_SHA"},
        {"id":"P_JOIN","role":"P","owner":"GoGREEN G9","evidence":"FULL_WINDOW_VALIDATED"},
        {"id":"P_FIRST_RED","role":"P","owner":"EVERRED root owner","evidence":"REQUIRES_NATIVE_JOB_FIRST_RED"},
        {"id":"P_N_PLUS","role":"P","owner":"Mission Control MIP","evidence":"DESCRIPTIVE_ONLY"},
        {"id":"O_METRICS","role":"O","owner":"Mission Control","evidence":"HASHED_LOCAL"},
        {"id":"C_GATE","role":"C","owner":"Independent review/security","evidence":"HOLD"}]
    pairs=[("S_NATIVE","I_COHORT","OBSERVED"),("I_COHORT","P_JOIN","OBSERVED"),
           ("P_JOIN","O_METRICS","OBSERVED"),("P_JOIN","P_FIRST_RED","DECLARED"),
           ("P_JOIN","P_N_PLUS","OBSERVED"),("P_FIRST_RED","C_GATE","DECLARED"),
           ("P_N_PLUS","O_METRICS","OBSERVED"),("O_METRICS","C_GATE","DECLARED")]
    return {"schema":"gogreen.g9.sipoc-dag.v1",
            "nodes":nodes,"edges":[{"from":a,"to":b,"evidence":c} for a,b,c in pairs],
            "run_observations":report["total_native_runs"],"closed_roots":0,
            "authority_transfer":False, "merge_authorized":False}


def html_page(report):
    escape=lambda x:html.escape(str(x),quote=True)
    rows=[]
    for f in report["per_workflow"]:
        rows.append("<tr><td>"+escape(f["repository"])+"</td><td>"+escape(f["workflow"])+"</td>"+
                    "<td>"+escape(f["observed_total"])+"</td><td>"+escape(f["completed_success"])+
                    "</td><td>"+escape(f["completed_failure"])+"</td><td>"+
                    escape(f["completed_other"])+"</td><td>"+
                    escape(f["observed_distinct_source_heads"])+"</td></tr>")
    return ("<!doctype html><html lang='en'><meta charset='utf-8'><title>GoGREEN G9 outcome convergence</title>"
            "<style>body{font:16px system-ui;max-width:1250px;margin:auto;padding:30px;background:#0c1b30;color:#f1f6ff}"
            "table{border-collapse:collapse;width:100%}th,td{padding:9px;border-bottom:1px solid #475b71;text-align:left}"
            "section{border:1px solid #536275;border-radius:12px;padding:20px;margin-top:16px}"
            "strong{color:#80e3bb}</style><body><h1>GoGREEN G9 | All-outcome convergence</h1>"
            "<p>Two complete native branch/time-window cohorts. Not all-repository health or source-root closure.</p>"
            "<section><h2>Observed native runs <strong>"+escape(report["total_native_runs"])+
            "</strong></h2><p>Success "+escape(report["native_terminal_success"])+
            " · Failure "+escape(report["native_terminal_failure"])+
            " · Cancelled "+escape(report["native_terminal_cancelled"])+
            "</p><p>Denominator: 57 source-bound runs, including failed and cancelled outcomes. "
            "Job/step pagination, independence and whole-repo coverage remain unverified.</p></section>"
            "<section><h2>Workflow-family denominators</h2><table><tr><th>Repo</th><th>Workflow</th>"
            "<th>Observed</th><th>Success</th><th>Failure</th><th>Other</th><th>Distinct SHAs</th>"
            "</tr>"+"".join(rows)+"</table></section><section><h2>SIPOC</h2>"
            "<p>Supplier GitHub → full run/attempt/SHA input → validated temporal process → "
            "hashed metric output → independent owner gate. EVERRED root edges are DECLARED, not accepted.</p>"
            "</section><p>Admission HOLD; no GitHub write, no synthetic trial and no waiver.</p></body></html>\n")


def build(data, out, source_sha):
    sha(source_sha)
    report=summarize(data)
    graph=sipoc(report)
    out.mkdir(parents=True,exist_ok=True)
    blobs={"metrics.json":canonical(report),
           "sipoc_dag.json":canonical(graph),
           "source_window.json":canonical(data),
           "index.html":html_page(report).encode("utf-8")}
    for name,blob in blobs.items():
        (out/name).write_bytes(blob)
    manifest={"schema":"gogreen.g9.manifest.v1","source_sha":source_sha,
              "files":{k:hashlib.sha256(v).hexdigest() for k,v in blobs.items()},
              "root_closure_credit":0,"merge_authorized":False}
    (out/"manifest.json").write_bytes(canonical(manifest))
    return report,manifest


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--source-sha",required=True)
    a=ap.parse_args()
    r,m=build(json.loads(a.input.read_text(encoding="utf-8")),a.out,a.source_sha)
    print(json.dumps({"native_runs":r["total_native_runs"],
                      "success":r["native_terminal_success"],
                      "failure":r["native_terminal_failure"],
                      "cancelled":r["native_terminal_cancelled"],
                      "admission":r["formal_admission"]},sort_keys=True))


if __name__=="__main__":
    main()
