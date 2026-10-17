#!/usr/bin/env python3
"""Source-bound GREEN execution lineage and temporal SIPOC projection.

Read-only projection over observed GitHub run and job records. It never
dispatches work, claims independent trials, validates cryptographic
artifacts, promotes repo admission, or turns a workflow name into a root.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA = "gogreen.success-temporal.census.v1"
OUTPUT = "gogreen.success-temporal.projection.v1"
SHA = re.compile(r"[0-9a-f]{40}\Z")
REPO = re.compile(r"GBOGEB/[A-Za-z0-9_.-]+\Z")
COMMIT_STATES = {"OBSERVED_NATIVE_SUCCESS", "LOCAL_NATIVE_STEP_ONLY_NOT_WORKFLOW_ADMITTED",
                 "MERGED_IMPLEMENTATION_NATIVE_GATE_RED", "CROSS_REPO_DRAFT_TESTS_PASS_ADMISSION_HOLD"}
COHORTS = ("TOP7", "TOP14_EXTENSION", "TOP21_EXTENSION")
GATES = ("authority_transfer", "merge_authorized", "security_waiver")
STEP_STATES = {"success", "skipped"}


def check(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode("utf-8")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def timestamp(value):
    check(isinstance(value, str) and value.endswith("Z"), "strict UTC timestamp required")
    try:
        t = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("malformed source timestamp") from exc
    check(t.utcoffset() == timedelta(0), "not UTC")
    return t


def count(value, name, minimum=0):
    check(type(value) is int and value >= minimum, "invalid " + name)
    return value


def sha(value):
    check(isinstance(value, str) and SHA.fullmatch(value), "invalid exact SHA")
    return value


def registry_names(registry):
    check(registry.get("schema") == "missioncontrol.gm_dmaic_evolution.v1",
          "wrong canonical cohort authority")
    c = registry.get("cohorts", {})
    names = []
    for field, cohort in (("top7", COHORTS[0]), ("top14_extension", COHORTS[1]),
                          ("top21_extension", COHORTS[2])):
        v = c.get(field)
        check(isinstance(v, list) and len(v) == 7, "Top21 cohort contract drift")
        names += [(s, cohort) for s in v]
    check(len({s for s, _ in names}) == 21, "duplicate canonical repository")
    return names


def validate(census, registry):
    check(isinstance(census, dict) and census.get("schema") == SCHEMA, "census schema mismatch")
    check(all(census.get(k) is False for k in GATES), "forbidden authority transfer")
    check(census.get("root_closure_credit") == 0, "no formal root credit")
    check(census.get("canonical_roster_path") ==
          "mission-control/grand-missions/GM_DMAIC_EVOLUTION_T7_T14_T21_v1.json",
          "canonical roster path changed")
    check(census.get("source_registry_git_blob") and SHA.fullmatch(
        census["source_registry_git_blob"]), "missing registry blob provenance")
    start = timestamp(census.get("window_start_utc"))
    stop = timestamp(census.get("window_end_exclusive_utc"))
    check(start < stop and (stop - start).days <= 3, "invalid temporal window")
    check(census.get("observed_on_date") == "2026-10-17",
          "frozen snapshot cannot claim new observation")
    cohort = registry_names(registry)
    entries = census.get("repo_heads")
    check(isinstance(entries, list) and len(entries) == 21, "incomplete Top21 census")
    check([(x.get("repository"), x.get("cohort")) for x in entries] == cohort,
          "Top21 roster changed or reordered")
    heads = {}
    for row in entries:
        repo = row["repository"]
        check(REPO.fullmatch(repo) and row.get("discovery") == "NATIVE_DEFAULT_BRANCH_API",
              "untrusted source head")
        sha(row.get("head_sha"))
        check(row.get("default_branch") in {"main", "master"}, "unknown default branch")
        check(row.get("ci_at_current_head") == "UNKNOWN_UNTIL_MATCHED",
              "head discovery promoted to CI success")
        check(type(row.get("protected_branch")) is bool, "missing branch-protection observation")
        heads[repo] = row["head_sha"]

    caps = census.get("capabilities")
    check(isinstance(caps, list) and len(caps) > 0, "missing capability provenance")
    capability_ids = set()
    for cap in caps:
        ident = cap.get("id")
        check(isinstance(ident, str) and re.fullmatch(r"[A-Z][A-Z0-9]{1,31}", ident),
              "invalid capability identity")
        check(ident not in capability_ids, "duplicate capability")
        capability_ids.add(ident)
        check(cap.get("owner_repo") in heads, "capability owner missing")
        check(cap.get("evidence_level") in COMMIT_STATES, "unknown proof class")
        for name in ("entrypoint", "operation", "input", "output", "next"):
            check(isinstance(cap.get(name), str) and cap[name], "capability documentation missing")

    families = census.get("workflow_samples")
    check(isinstance(families, list) and families, "empty runner evidence")
    all_runs, rows = {}, []
    family_keys = set()
    for family in families:
        repo, name = family.get("repository"), family.get("name")
        check(repo in heads and isinstance(name, str) and 1 <= len(name) <= 180,
              "unrecognized workflow")
        key = (repo, name)
        check(key not in family_keys, "duplicate workflow family")
        family_keys.add(key)
        check(family.get("capability_id") in capability_ids, "no capability producer")
        cap = next(c for c in caps if c["id"] == family["capability_id"])
        check(cap["owner_repo"] == repo and cap["workflow"] == name and
              cap["evidence_level"] == "OBSERVED_NATIVE_SUCCESS", "capability source mismatch")
        check(type(family.get("sample_only")) is bool, "missing completeness class")
        check(family.get("population_class") ==
              ("SELECTED_LATEST_100_MAIN_RUNS_PARTIAL" if family["sample_only"] else
               "ALL_MATCHING_MAIN_WORKFLOWS_RETURNED_IN_DATE_WINDOW"),
              "contradictory completeness")
        runs = family.get("run_observations")
        check(isinstance(runs, list) and runs and len(runs) <= 40,
              "bounded per-family native sample required")
        ids, numbers, times = set(), set(), set()
        for run in runs:
            rid = count(run.get("run_id"), "run id", 1)
            n = count(run.get("run_number"), "run sequence number", 1)
            attempt = count(run.get("attempt"), "run attempt", 1)
            source = sha(run.get("source_sha"))
            t = timestamp(run.get("created_at"))
            check(start <= t < stop, "run outside sampled window")
            check(run.get("status") == "completed" and run.get("conclusion") == "success",
                  "red or nonterminal falsely credited as green")
            check(run.get("event") in {"push", "schedule", "workflow_dispatch", "pull_request"},
                  "unknown workflow trigger")
            check(rid not in all_runs and rid not in ids and n not in numbers,
                  "duplicate run or ordinal credit")
            check(t not in times or rid not in ids, "duplicate observation")
            ids.add(rid); numbers.add(n); times.add(t)
            all_runs[rid] = (repo, source, attempt, family["capability_id"])
            rows.append({"repository": repo, "workflow": name, "run_id": rid,
                         "attempt": attempt, "run_number": n, "created_at": run["created_at"],
                         "source_sha": source, "current_head_match": source == heads[repo]})
        bynum = sorted(runs, key=lambda r: r["run_number"])
        check(all(timestamp(bynum[i]["created_at"]) <= timestamp(bynum[i+1]["created_at"])
                  for i in range(len(bynum) - 1)), "run number/time sequence inversion")

    seen_jobs, measured = set(), []
    jobs = census.get("native_jobs")
    check(isinstance(jobs, list), "native job array required")
    for job in jobs:
        jid = count(job.get("job_id"), "job id", 1)
        check(jid not in seen_jobs, "duplicate native job")
        seen_jobs.add(jid)
        rid = count(job.get("run_id"), "job run id", 1)
        check(rid in all_runs, "job not linked to observed workflow")
        repo, source, attempt, _ = all_runs[rid]
        check(job.get("repository") == repo and sha(job.get("source_sha")) == source and
              job.get("attempt") == attempt, "job attempt/head/owner mismatch")
        status = job.get("conclusion")
        check(status in STEP_STATES, "nonterminal or failed job credited as success")
        check(isinstance(job.get("name"), str) and job["name"], "unnamed job")
        if status == "success":
            runner = count(job.get("runner_id"), "runner id", 1)
            began = timestamp(job.get("started_at")); ended = timestamp(job.get("completed_at"))
            check(ended >= began and ended - began <= timedelta(days=1), "invalid runner duration")
            check(job.get("steps_success_eligible") is True, "successful-step contract missing")
            measured.append({**job, "runner_seconds": round((ended - began).total_seconds(), 3),
                             "runner_id": runner})
        else:
            check(job.get("runner_id") is None and job.get("started_at") is None
                  and job.get("completed_at") is None
                  and job.get("steps_success_eligible") is False,
                  "skipped job must not invent runner-time or success")
    failures = census.get("red_controls")
    check(isinstance(failures, list) and failures, "no anti-cherry-picking control")
    failed_ids = set()
    for red in failures:
        rid = count(red.get("run_id"), "red run id", 1)
        check(red.get("repository") in heads and rid not in all_runs and rid not in failed_ids,
              "red/success run identity collision")
        failed_ids.add(rid)
        sha(red.get("source_sha"))
        count(red.get("attempt"), "red run attempt", 1)
        check(red.get("status") == "completed" and red.get("conclusion") == "failure"
              and red.get("root_confirmed") is False, "red controls cannot close causes")
    return heads, rows, all_runs, measured


def peak_parallelism(jobs):
    edges = []
    for job in jobs:
        edges += [(timestamp(job["started_at"]), 1), (timestamp(job["completed_at"]), -1)]
    # A completing job does not overlap a job starting at the same instant.
    total, peak = 0, 0
    for _, diff in sorted(edges, key=lambda x: (x[0], x[1])):
        total += diff
        peak = max(total, peak)
    return peak


def metrics(census, registry):
    heads, rows, run_lookup, measured = validate(census, registry)
    wf = []
    for family in census["workflow_samples"]:
        runs = family["run_observations"]
        ordered = sorted(runs, key=lambda x: x["run_number"])
        gaps = ordered[-1]["run_number"] - ordered[0]["run_number"] + 1 - len(runs)
        check(gaps >= 0, "run ordinal denominator corrupted")
        latest, earliest = max(timestamp(x["created_at"]) for x in runs), min(
            timestamp(x["created_at"]) for x in runs)
        matched = sum(x["source_sha"] == heads[family["repository"]] for x in runs)
        # These are observed successful rows, deliberately not a success-rate denominator.
        wf.append({"repository": family["repository"], "name": family["name"],
                   "capability_id": family["capability_id"], "observed_successful_runs": len(runs),
                   "unique_source_heads": len({r["source_sha"] for r in runs}),
                   "current_head_success_observations": matched,
                   "first_observed_utc": earliest.isoformat().replace("+00:00", "Z"),
                   "latest_observed_utc": latest.isoformat().replace("+00:00", "Z"),
                   "observed_maturity_span_hours": round((latest - earliest).total_seconds()/3600, 3),
                   "unobserved_run_number_gaps": gaps,
                   "observed_run_sequence_numbers": [x["run_number"] for x in ordered],
                   "sample_only": family["sample_only"],
                   "population_success_rate": None,
                   "independent_trial_count": None})
    measured_repos = sorted({x["repository"] for x in measured})
    job_metrics = []
    for repo in measured_repos:
        a = [x for x in measured if x["repository"] == repo]
        secs = sum(x["runner_seconds"] for x in a)
        first = min(timestamp(x["started_at"]) for x in a)
        end = max(timestamp(x["completed_at"]) for x in a)
        # Across noncontemporaneous sample jobs, do not claim concurrency.
        per_run = {}
        for x in a:
            per_run.setdefault(x["run_id"], []).append(x)
        job_metrics.append({"repository": repo, "measured_success_jobs": len(a),
                            "observed_runner_ids": len({x["runner_id"] for x in a}),
                            "sampled_runner_seconds": round(secs, 3),
                            "sampled_runner_minutes_not_billed": round(secs/60, 4),
                            "per_run": [{"run_id": rid,
                                         "successful_jobs": len(v),
                                         "sampled_runner_seconds": round(sum(t["runner_seconds"] for t in v), 3),
                                         "max_observed_parallel_jobs": peak_parallelism(v)}
                                        for rid, v in sorted(per_run.items())]})
    return {"schema": OUTPUT, "evidence_class": "NATIVE_API_TRANSCRIPTION_NOT_ARTIFACT_BYTES",
            "window_start_utc": census["window_start_utc"],
            "window_end_exclusive_utc": census["window_end_exclusive_utc"],
            "top21_head_discovered": len(heads), "cohort_counts": dict(
                Counter(x["cohort"] for x in census["repo_heads"])),
            "current_head_protection_observed": sum(x["protected_branch"] for x in census["repo_heads"]),
            "effective_merge_admission": None,
            "workflow_families": wf,
            "observed_successful_run_ids": len(rows),
            "current_head_successful_run_observations": sum(x["current_head_match"] for x in rows),
            "red_control_runs": len(census["red_controls"]),
            "sampled_terminal_native_jobs": len(census["native_jobs"]),
            "measured_successful_native_jobs": len(measured),
            "skipped_native_jobs_excluded": len(census["native_jobs"]) - len(measured),
            "sampled_runner_seconds_total": round(sum(x["runner_seconds"] for x in measured), 3),
            "sampled_runner_minutes_not_billed": round(sum(x["runner_seconds"] for x in measured)/60, 4),
            "runner_by_repository": job_metrics,
            "scope_matched_statement_coverage_pp": None,
            "scope_matched_branch_coverage_pp": None,
            "fleet_success_rate": None, "statistical_independent_trials": None,
            "root_closure_credit": 0, "dispatch_authorized": False,
            "security_waiver": False, "merge_authorized": False}


def dag(census, aggregate):
    nodes = [
        {"id": "S", "role": "S", "label": "Supplier: canonical Top21 registry and native repository heads",
         "evidence": "OBSERVED_NATIVE_DEFAULT_HEAD", "owner": "Mission Control"},
        {"id": "I", "role": "I", "label": "Input: workflow run+attempt+SHA and job+runner data",
         "evidence": "NATIVE_API_TRANSCRIPTION", "owner": "GitHub Actions"},
        {"id": "P_SOURCE", "role": "P", "label": "Process: source-bound join and sample-safe temporal metrics",
         "evidence": "REPRODUCIBLE_COMPUTATION", "owner": "GoGREEN"},
        {"id": "P_REVERSE", "role": "P", "label": "Process: reverse/negative tests of successful capability edges",
         "evidence": "NATIVE_TESTFLIGHT_PENDING", "owner": "GoGREEN test pilot"},
        {"id": "P_REX", "role": "P", "label": "Process: candidate root fingerprint/REX lookup only",
         "evidence": "DECLARED_OWNER_DEPENDENCY", "owner": "EVERRED/REX"},
        {"id": "O", "role": "O", "label": "Output: JSON metrics, offline HTML and SHA256 file manifest",
         "evidence": "LOCAL_OUTPUT_GENERATED", "owner": "Mission Control"},
        {"id": "C", "role": "C", "label": "Customer: source owners and independent admission",
         "evidence": "HOLD_NO_AUTHORITY_TRANSFER", "owner": "CODEX/QPS/gg_MATH/ABACUS"},
    ]
    edges = [
        {"source": "S", "target": "I", "binding": "OBSERVED", "kind": "SUPPLIES_PROVENANCE"},
        {"source": "I", "target": "P_SOURCE", "binding": "OBSERVED", "kind": "RUN_JOB_JOIN"},
        {"source": "P_SOURCE", "target": "P_REVERSE", "binding": "DECLARED", "kind": "CHALLENGE_GREEN"},
        {"source": "P_SOURCE", "target": "P_REX", "binding": "DECLARED", "kind": "SHARED_ROOT_LOOKUP"},
        {"source": "P_SOURCE", "target": "O", "binding": "OBSERVED", "kind": "DETERMINISTIC_METRIC"},
        {"source": "P_REVERSE", "target": "C", "binding": "DECLARED", "kind": "REQUIRES_TEST_CONTROL"},
        {"source": "P_REX", "target": "C", "binding": "DECLARED", "kind": "REQUIRES_ROOT_OWNER"},
        {"source": "O", "target": "C", "binding": "DECLARED", "kind": "REQUIRES_INDEPENDENT_REVIEW"},
    ]
    for cap in census["capabilities"]:
        ident = "CAP_" + cap["id"]
        nodes.append({"id": ident, "role": "P", "label": cap["operation"],
                      "evidence": cap["evidence_level"], "owner": cap["owner_repo"],
                      "entrypoint": cap["entrypoint"], "input": cap["input"], "output": cap["output"],
                      "next": cap["next"]})
        edges.append({"source": "I", "target": ident,
                      "binding": "OBSERVED" if cap["evidence_level"] == "OBSERVED_NATIVE_SUCCESS"
                      else "DECLARED", "kind": "SOURCE_TO_CAPABILITY"})
        edges.append({"source": ident, "target": "O", "binding": "DECLARED",
                      "kind": "CAPABILITY_TO_PROVEN_OUTPUT_NOT_BYTE_VERIFIED"})
    check(len({n["id"] for n in nodes}) == len(nodes), "duplicate graph node")
    return {"schema": "gogreen.success-temporal.sipoc-dag.v1", "canonical_planner":
            "mission-control/gogreen/sipoc_instances.py", "canonical_roster":
            census["canonical_roster_path"], "nodes": nodes, "edges": edges,
            "repo_inventory": [{"repository": x["repository"], "cohort": x["cohort"],
                                "source_sha": x["head_sha"], "runner_admission": None}
                               for x in census["repo_heads"]],
            "green_observed_run_ids": aggregate["observed_successful_run_ids"],
            "authority_transfer": False, "dispatch_authorized": False,
            "merge_authorized": False, "admission": "HOLD"}


def render_html(agg, graph, census):
    esc = lambda x: html.escape(str(x), quote=True)
    rows = []
    for item in agg["workflow_families"]:
        rows.append("<tr><td>" + esc(item["repository"]) + "</td><td>" +
                    esc(item["name"]) + "</td><td>" +
                    esc(item["observed_successful_runs"]) + "</td><td>" +
                    esc(item["current_head_success_observations"]) + "</td><td>" +
                    esc(item["unobserved_run_number_gaps"]) + "</td><td>" +
                    esc(item["observed_maturity_span_hours"]) + "</td></tr>")
    graph_rows = ["<li><b>" + esc(n["id"]) + "</b> [" + esc(n["role"]) + "] " +
                  esc(n["label"]) + " — " + esc(n["evidence"]) + "</li>"
                  for n in graph["nodes"]]
    link_rows = ["<li>" + esc(e["source"]) + " → " + esc(e["target"]) +
                 " (" + esc(e["binding"]) + ", " + esc(e["kind"]) + ")</li>"
                 for e in graph["edges"]]
    return ("""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport"
content="width=device-width,initial-scale=1"><title>GoGREEN Native Runner and SIPOC</title>
<style>:root{font:15px system-ui;color-scheme:dark;background:#0e192a;color:#eef5ff}
body{max-width:1140px;margin:auto;padding:24px}h1{font-size:2rem}section{border:1px solid #38495f;
padding:17px;margin:16px 0;border-radius:12px;background:#15263b}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}
.metric{font-size:2rem;font-weight:700;color:#73dfbc}table{border-collapse:collapse;width:100%;overflow:auto}
td,th{border-bottom:1px solid #35445b;padding:8px;text-align:left}
small{color:#b1bed2}a{color:#99cbff}li{margin:7px 0}@media(max-width:650px){body{padding:12px}td,th{font-size:.8rem}}
</style><body><h1>GoGREEN / GREEN-to-GREENER</h1><p>Native runner sample · 16–17 Oct 2026 UTC ·
Historical evidence, not an admission decision</p>
<div class="grid">
<section><small>Top21 source heads</small><div class="metric">""" +
            esc(agg["top21_head_discovered"]) + """/21</div></section>
<section><small>Selected successful runs</small><div class="metric">""" +
            esc(agg["observed_successful_run_ids"]) + """</div></section>
<section><small>Successful sampled jobs</small><div class="metric">""" +
            esc(agg["measured_successful_native_jobs"]) + """</div></section>
<section><small>Measured runner-seconds</small><div class="metric">""" +
            esc(agg["sampled_runner_seconds_total"]) + """</div></section></div>
<section><h2>Source-linked workflow sequences</h2><p>Current-head matches refer only to the selected
successful workflow, not complete repository CI. Unobserved ordinal gaps are UNKNOWN, not failures.</p>
<table><thead><tr><th>Repository</th><th>Workflow</th><th>Selected PASS</th><th>Current-head matches</th>
<th>Unobserved ordinal gaps</th><th>Observation span (h)</th></tr></thead><tbody>""" +
            "".join(rows) + """</tbody></table></section>
<section><h2>SIPOC process graph</h2><ol>""" + "".join(graph_rows) + """</ol>
<h3>Typed dependencies</h3><ul>""" + "".join(link_rows) + """</ul></section>
<section><h2>Capabilities enabled by working code</h2><ul>""" +
            "".join("<li><b>" + esc(x["id"]) + "</b> " + esc(x["operation"]) +
                    "; next: " + esc(x["next"]) + " — " + esc(x["evidence_level"]) + "</li>"
                    for x in census["capabilities"]) + """</ul></section>
<section><h2>Important exclusions</h2><p>24 selected GREEN runs are not 24 independent trials.
Skipped jobs do not count as successful runner execution. The recorded runner-seconds are occupied
execution time, not billed minutes. We do not claim branch coverage gains, artifact-byte custody,
fleet health, root closure, statistical reliability or owner-approved merge. Native red controls: """ +
            esc(agg["red_control_runs"]) + """.</p></section></body></html>\n""")


def build(census, registry, producer_sha, out):
    sha(producer_sha)
    agg = metrics(census, registry)
    graph = dag(census, agg)
    out.mkdir(parents=True, exist_ok=True)
    files = {"metrics.json": canonical(agg), "sipoc_dag.json": canonical(graph),
             "index.html": render_html(agg, graph, census).encode("utf-8"),
             "source_census.json": canonical(census)}
    hashes = {}
    for name, content in files.items():
        (out / name).write_bytes(content)
        hashes[name] = digest(content)
    manifest = {"schema": "gogreen.success-temporal.artifact-manifest.v1",
                "producer_source_sha": producer_sha,
                "source_census_sha256": digest(canonical(census)),
                "canonical_registry_sha256": digest(canonical(registry)),
                "files": hashes, "artifact_bytes_verified_external": False,
                "authority_transfer": False, "merge_authorized": False}
    (out / "manifest.json").write_bytes(canonical(manifest))
    return {"metrics": agg, "manifest": manifest}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    evidence = json.loads(args.input.read_text(encoding="utf-8"))
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    result = build(evidence, registry, args.source_sha, args.out)
    print(json.dumps({"top21_head_discovered": result["metrics"]["top21_head_discovered"],
                      "selected_green_runs": result["metrics"]["observed_successful_run_ids"],
                      "runner_seconds": result["metrics"]["sampled_runner_seconds_total"],
                      "admission": "HOLD"}, sort_keys=True))


if __name__ == "__main__":
    main()
