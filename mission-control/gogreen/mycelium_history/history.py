#!/usr/bin/env python3
"""Mycelium W6 history: source-bound, denominator-safe analytics + HTML/SVG.

A read-only consumer of CODEX Actions evidence, existing GoGREEN merged-outcome
census and CODE PURPLE causal-root owners. No source says green == admitted.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

SCHEMA = "missioncontrol.mycelium.history_capture.v1"
RESULT = "missioncontrol.mycelium.history_metrics.v1"
SHA = re.compile(r"^[a-f0-9]{40}$")
TERMINAL = frozenset({"success", "failure", "cancelled", "skipped", "timed_out",
                      "neutral", "action_required"})
SYMBOLS = {
    "fix": ("🔧", "REPAIR"), "feat": ("✨", "FEATURE"),
    "ci": ("⚙️", "CI"), "test": ("🧪", "TEST"),
    "docs": ("📖", "DOCS"), "refactor": ("♻️", "REFACTOR"),
    "perf": ("⚡", "PERFORMANCE"), "build": ("🏗️", "BUILD"),
    "chore": ("🧹", "CHORE"), "revert": ("↩️", "REVERT"),
    "merge": ("🔀", "MERGE"),
}
FAMILIES = {
    "mycelium": ("🧬", "MYCELIUM"), "code purple": ("🟣", "CODE_PURPLE"),
    "everred": ("🔴", "EVERRED"), "gogreen": ("🟢", "GOGREEN"),
    "spine": ("🕸️", "SPINE"), "go green": ("🟢", "GOGREEN"),
    "ci": ("⚙️", "CI"), "security": ("🛡️", "SECURITY"),
    "coverage": ("📈", "COVERAGE"), "mip": ("📊", "MIP"),
    "dmaic": ("📊", "DMAIC"), "ldab": ("🧭", "LDAB"),
    "lldb": ("🪲", "LLDB"), "dependabot": ("📦", "DEPENDENCY"),
    "swift": ("🕊️", "SWIFT"),
    "w003": ("🛡️", "GOVERNANCE"), "governance": ("🛡️", "GOVERNANCE"),
    "qps": ("❄️", "QPS"), "gg_math": ("∑", "GG_MATH"),
}
NAME = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*)\(([^)]{1,90})\):\s*(.+)$")
WAVE = re.compile(r"\b(?:W|N)\d{1,4}\b", re.I)


def require(value, reason):
    if not value:
        raise ValueError("MYCELIUM_W6_HOLD: " + reason)


def utc(value):
    require(isinstance(value, str) and value.endswith("Z"), "UTC timestamp")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("MYCELIUM_W6_HOLD: malformed UTC timestamp") from exc


def canonical(obj):
    return (json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=True) +
            "\n").encode("ascii")


def norm_title(title):
    """Stabilize glyphs by conventional verb(scope Wn), never as proof badges."""
    title = str(title or "").strip()
    match = NAME.match(title)
    if match:
        verb, scope, description = match.groups()
    elif title.lower().startswith("merge pull request"):
        verb, scope, description = "merge", "", title
    else:
        verb, scope, description = "unknown", "", title
    kind = verb.lower()
    glyph, kind_name = SYMBOLS.get(kind, ("•", "OTHER"))
    lower = (scope + " " + title).lower()
    candidates = sorted((len(key), key, val) for key, val in FAMILIES.items()
                        if key in lower)
    family = candidates[-1][2] if candidates else ("•", "UNCLASSIFIED")
    wave = WAVE.search(scope) or WAVE.search(title)
    return {
        "icon": glyph, "kind": kind_name, "scope": scope,
        "scope_icon": family[0], "family": family[1],
        "wave": wave.group().upper() if wave else None,
        "description": description[:260], "title": title[:320],
    }


def fingerprint(job):
    step = job.get("first_failed_step")
    require(isinstance(step, str) and step, "first-red job step")
    error = job.get("log_first_error")
    # A signature is a symptom, never a verified causal root.
    if isinstance(error, str) and error:
        clue = re.sub(r"\b[0-9a-f]{40,64}\b", "<sha>", error.lower())
        clue = re.sub(r"\b\d{6,}\b", "<id>", clue)
        clue = re.sub(r"\s+", " ", clue.strip())[:140]
        source = "ERROR_LINE_CLASS"
    else:
        clue = "STEP_ONLY_NO_VERIFIED_LOG_CAUSE"
        source = "STEP_NAME_ONLY"
    signature = "|".join((job["name"].lower(), step.lower(), clue))
    return {"id": hashlib.sha256(signature.encode()).hexdigest()[:16],
            "label": (step + " / " + clue)[:220], "evidence_class": source}


def validate(d):
    require(isinstance(d, dict) and d.get("schema") == SCHEMA and
            d.get("repository") == "GBOGEB/CODEX" and
            d.get("workflow_file") == "missioncontrol-mycelium.yml",
            "source identity")
    require(d.get("merge_admission") == "HOLD" and
            d.get("authority_transfer") is False and
            d.get("security_waiver") is False and
            d.get("qps_acceptance") == "WITHHELD" and
            d.get("root_closure_credit") == 0, "false-governed admission")
    require(d.get("worker_hours") is None and
            d.get("runner_capacity_slots") is None, "capacity not measured")
    utc(d["capture_at"])
    for k in ("source_main_before", "source_main_after"):
        require(isinstance(d.get(k), str) and SHA.fullmatch(d[k]), "main SHA")
    count = d.get("api_total_count")
    require(type(count) is int and count >= 0, "API denominator")
    runs = d.get("runs")
    require(isinstance(runs, list) and
            type(d.get("observed_run_count")) is int and
            len(runs) == d["observed_run_count"] and len(runs) <= count,
            "run denominator")
    if d.get("run_inventory_complete"):
        require(len(runs) == count and d.get("pagination_nonatomic_or_capped") is False
                and d.get("duplicated_ids") == [],
                "fabricated full-history completion")
    ids, keyed = set(), {}
    for run in runs:
        rid, attempt = run.get("id"), run.get("attempt")
        require(type(rid) is int and rid > 0 and rid not in ids and
                type(attempt) is int and attempt > 0,
                "run/attempt identity")
        ids.add(rid)
        require(isinstance(run.get("head_sha"), str) and
                SHA.fullmatch(run["head_sha"]), "run head")
        require(run.get("workflow_id") == d.get("workflow_id"),
                "run workflow provenance")
        s, c = run.get("status"), run.get("conclusion")
        require(s in ("completed", "queued", "in_progress", "pending",
                      "requested", "waiting"), "run status")
        require((s == "completed" and c in TERMINAL) or
                (s != "completed" and c is None), "run terminal mismatch")
        utc(run["created_at"])
        require(run.get("previous_attempts_collected") == (attempt == 1),
                "rerun history completeness")
        keyed[str(rid)] = run
    details = d.get("selected_job_details")
    require(isinstance(details, dict), "selected job census")
    require(type(d.get("selected_job_run_count")) is int and
            d["selected_job_run_count"] == len(details), "job cohort count")
    for rid, detail in details.items():
        require(rid in keyed and keyed[rid]["status"] == "completed",
                "job evidence tied to nonterminal run")
        require(rid in keyed and type(detail.get("run_id")) is int and
                detail["run_id"] == int(rid) and
                detail.get("attempt") == keyed[rid]["attempt"], "job/run binding")
        require(type(detail.get("api_job_total")) is int and
                detail["api_job_total"] >= 0 and
                isinstance(detail.get("jobs"), list), "job denominator missing")
        if detail.get("jobs_complete"):
            require(len(detail["jobs"]) == detail["api_job_total"],
                    "claimed complete job page truncated")
        job_ids = set()
        for job in detail["jobs"]:
            jid = job.get("id")
            require(type(jid) is int and jid > 0 and jid not in job_ids and
                    job.get("run_id") == int(rid) and
                    job.get("attempt") == detail["attempt"], "job identity")
            job_ids.add(jid)
            steps = job.get("steps")
            require(isinstance(steps, list), "job step detail")
            failed = [s for s in steps if s.get("conclusion") == "failure"]
            if failed:
                require(job.get("first_failed_step") == failed[0]["name"],
                        "first-red first step mismatch")
            else:
                require(job.get("first_failed_step") is None,
                        "fabricated job failure")
            require(job.get("log_read_status") != "READ_BOUNDED" or
                    (isinstance(job.get("log_bytes_sha256"), str) and
                     re.fullmatch(r"[a-f0-9]{64}", job["log_bytes_sha256"])),
                    "forged log byte readback")
    prs = d.get("merged_pr_sample")
    require(isinstance(prs, list) and
            d.get("merged_pr_sample_is_complete") is False,
            "merged PR sample cannot claim fleet completeness")
    pr_numbers = set()
    for pr in prs:
        n = pr.get("number")
        require(type(n) is int and n > 0 and n not in pr_numbers,
                "duplicate PR number")
        pr_numbers.add(n)
        require(isinstance(pr.get("head_sha"), str) and
                SHA.fullmatch(pr["head_sha"]), "merged PR head")
        if pr.get("merge_sha") is not None:
            require(SHA.fullmatch(pr["merge_sha"]), "merge SHA")
        utc(pr["merged_at"])
    return keyed


def bins(runs, *, limit=21):
    # Daily UTC bars: integer observed counts; not causal roots or tested lines.
    buckets = defaultdict(Counter)
    for run in runs:
        day = utc(run["created_at"]).date().isoformat()
        buckets[day][run["conclusion"] or "nonterminal"] += 1
    data = []
    if not buckets:
        return []
    end = max(datetime.fromisoformat(x).date() for x in buckets)
    begin = max(min(datetime.fromisoformat(x).date() for x in buckets),
                end - timedelta(days=limit - 1))
    for offset in range((end - begin).days + 1):
        day = (begin + timedelta(days=offset)).isoformat()
        b = buckets[day]
        data.append({"date": day, "pass": b["success"], "red": (
            b["failure"] + b["timed_out"] + b["action_required"]),
            "cancelled": b["cancelled"], "skipped": b["skipped"],
            "other": sum(v for k, v in b.items()
                         if k not in {"success", "failure", "timed_out",
                                      "action_required", "cancelled", "skipped"}),
            "observed": sum(b.values())})
    return data


def compare_pr(pr, runs, selected_job_details=None):
    merge_time = utc(pr["merged_at"])
    matched = [
        r for r in runs if r["head_sha"] in
        {pr["head_sha"], pr.get("merge_sha")} and
        r["status"] == "completed"
    ]
    pre, post = [], []
    native_fail_before, native_fail_after = 0, 0
    native_timed_jobs = 0
    selected_job_run_ids = []
    detail = selected_job_details if isinstance(selected_job_details, dict) else {}
    for r in matched:
        # Weak observation, retained distinctly from actual job completion.
        stamp = utc(r.get("updated_at") or r["created_at"])
        (pre if stamp <= merge_time else post).append(r)
        jobs = detail.get(str(r["id"]))
        if not jobs or jobs.get("jobs_complete") is not True:
            continue
        selected_job_run_ids.append(r["id"])
        for job in jobs["jobs"]:
            end = job.get("completed_at")
            if end is None:
                continue
            job_end = utc(end)
            native_timed_jobs += 1
            if job.get("conclusion") in {"failure", "timed_out", "action_required"}:
                if job_end <= merge_time:
                    native_fail_before += 1
                else:
                    native_fail_after += 1
    return {
        "number": pr["number"], "title": norm_title(pr.get("title", "")),
        "url": pr["url"], "head_sha": pr["head_sha"],
        "merge_sha": pr.get("merge_sha"),
        "merged_at": pr["merged_at"],
        "observed_runs_on_head_or_merge_sha": len(matched),
        "red_before_merge": sum(x["conclusion"] in
                                {"failure", "timed_out", "action_required"} for x in pre),
        "red_after_merge": sum(x["conclusion"] in
                               {"failure", "timed_out", "action_required"} for x in post),
        "run_timing_basis": "RUN_UPDATED_AT_PROXY_NOT_CHECK_COMPLETION",
        "selected_native_job_run_ids": selected_job_run_ids,
        "native_jobs_with_completion_timestamps": native_timed_jobs,
        "native_failed_jobs_completed_before_merge": native_fail_before,
        "native_failed_jobs_completed_after_merge": native_fail_after,
        "native_job_timing_complete_for_all_runs": False,
        "successful_pre_merge": sum(x["conclusion"] == "success" for x in pre),
        "successful_post_merge": sum(x["conclusion"] == "success" for x in post),
        "complete_required_checks": None,
        "independent_approval": None,
        "governed_admission": "UNKNOWN_NOT_CREDITED",
    }


def summarize(data):
    keyed = validate(data)
    runs = data["runs"]
    outcomes = Counter(x["conclusion"] or "nonterminal" for x in runs)
    episodes, fingerprints = [], {}
    for key, detail in data["selected_job_details"].items():
        run = keyed[key]
        for job in detail["jobs"]:
            if job["first_failed_step"] is None:
                continue
            f = fingerprint(job)
            rec = fingerprints.setdefault(f["id"], {
                "id": f["id"], "label": f["label"],
                "evidence_class": f["evidence_class"], "occurrences": 0,
                "distinct_run_ids": [], "first_red": [],
            })
            rec["occurrences"] += 1
            rec["distinct_run_ids"].append(run["id"])
            rec["first_red"].append({
                "run_id": run["id"], "attempt": run["attempt"],
                "job_id": job["id"], "job": job["name"],
                "step": job["first_failed_step"], "sha": run["head_sha"],
                "downstream_skipped_step_count": len(job["downstream_skipped_steps"]),
                "log_status": job["log_read_status"],
                "url": run["url"] + "/job/" + str(job["id"]),
            })
            episodes.append(rec["first_red"][-1])
    for rec in fingerprints.values():
        rec["distinct_run_ids"] = sorted(set(rec["distinct_run_ids"]))
    daily = bins(runs)
    sample = [compare_pr(pr, runs, data["selected_job_details"]) for pr in data["merged_pr_sample"]]
    terminal_count = sum(outcomes[x] for x in TERMINAL)
    first_red_occurrences = len(episodes)
    merged_red = [pr for pr in sample
                  if pr["red_before_merge"] or pr["red_after_merge"]]
    prev = [r for r in runs if r["attempt"] > 1]
    return {
        "schema": RESULT,
        "producer": data["repository"] + "/actions/workflows/" + data["workflow_file"],
        "capture_at": data["capture_at"],
        "CODEX_main_start": data["source_main_before"],
        "CODEX_main_end": data["source_main_after"],
        "source_main_stable_during_scan": data["source_main_stable_during_scan"],
        "run_population": {
            "observed": len(runs), "eligible_api_reported": data["api_total_count"],
            "complete": data["run_inventory_complete"],
            "non_atomic_or_capped": data["pagination_nonatomic_or_capped"],
            "terminal": terminal_count,
            "nonterminal": len(runs) - terminal_count,
            "successful": outcomes["success"],
            "failed": outcomes["failure"] + outcomes["timed_out"] +
                      outcomes["action_required"],
            "cancelled": outcomes["cancelled"],
            "skipped": outcomes["skipped"],
            "other_terminal": outcomes["neutral"],
            "not_independent_trials": True,
        },
        "attempts": {
            "latest_attempt_records": len(runs),
            "rerun_latest_attempts": len(prev),
            "earlier_attempt_history_complete": data["older_attempts_collected"],
            "independence": "NOT_PROVEN",
        },
        "job_detail": {
            "observed_run_records": len(data["selected_job_details"]),
            "failed_run_detail_population": sum(
                keyed[k]["conclusion"] in
                {"failure", "timed_out", "action_required"}
                for k in data["selected_job_details"]),
            "sampling": data["job_detail_policy"],
            "detail_errors": data["job_detail_error_count"],
            "failure_log_reads": data["failure_log_reads"],
            "log_read_attempts": data.get("log_read_attempts"),
            "unreadable_log_attempts": data.get("unreadable_log_attempts"),
            "sampled_failed_runs": sum(
                keyed[k]["conclusion"] in {"failure","timed_out","action_required"}
                for k in data["selected_job_details"]),
            "sampled_successful_runs": sum(
                keyed[k]["conclusion"] == "success"
                for k in data["selected_job_details"]),
            "observed_error_annotations_in_green_jobs": None,
            "full_fleet_job_breadth": None,
        },
        "first_red": {
            "sampled_occurrences": first_red_occurrences,
            "sampled_distinct_fingerprints": len(fingerprints),
            "clusters": sorted(fingerprints.values(),
                               key=lambda x: (-x["occurrences"], x["id"])),
            "causal_root_ids_verified": [],
            "accepted_root_closures": 0,
            "downstream_skipped_step_occurrences": sum(
                e["downstream_skipped_step_count"] for e in episodes),
        },
        "merged_with_red": {
            "sampling": "RECENT_CLOSED_PR_SELECTION_NOT_LIFETIME_POPULATION",
            "sampled_merged_prs": len(sample),
            "with_observed_native_red": len(merged_red),
            "red_before_merge": sum(bool(x["red_before_merge"]) for x in sample),
            "red_after_merge": sum(bool(x["red_after_merge"]) for x in sample),
            "sampled_native_failed_job_before_merge": sum(
                x["native_failed_jobs_completed_before_merge"] for x in sample),
            "sampled_native_failed_job_after_merge": sum(
                x["native_failed_jobs_completed_after_merge"] for x in sample),
            "native_job_timing_not_a_required_status_census": True,
            "prs": sample,
            "no_admission_inference": True,
        },
        "daily_bins": daily,
        "symbol_contract": {"first_token": "type→glyph",
                            "parenthesized_scope": "family→glyph",
                            "wave": "W/N ordinal chip",
                            "icons": SYMBOLS, "families": FAMILIES},
        "statistics": {
            "M1": "PARTIAL_SOURCE_BOUND",
            "M2": "NOT_QUALIFIED_CORRELATED_RUNS",
            "M3": "NOT_QUALIFIED_NO_CAPABILITY_STABILITY",
            "PCA": "NOT_QUALIFIED",
            "Bradley_Terry": "NOT_QUALIFIED",
            "Six_Sigma": "NOT_QUALIFIED",
            "worker_hours": None, "runner_capacity_slots": None,
            "matched_statement_coverage": None,
            "matched_branch_coverage": None,
            "capacity_forecast": None,
        },
        "lineage_contract": {
            "run_to_job": "OBSERVED_ONLY_IF_JOB_DETAIL_FETCHED",
            "job_to_first_red": "FIRST_FAILED_STEP_OBSERVED",
            "first_red_to_skips": "CHRONOLOGIC_PRECEDENCE_NOT_CAUSATION",
            "pr_to_merge": "MERGED_OBSERVED_NOT_ADMITTED",
            "merge_to_main_ci": "REQUIRES_EXACT_MERGE_SHA_AND_POSTMERGE_RUN",
            "n_to_n_plus_one": "DECLARED_RECURSIVE_FEEDBACK_NOT_A_RUN",
        },
        "authority": {
            "ZIP_VERIFIER": "#530", "SIX_REPO_BREADTH": "#531",
            "METHOD_VIEWER": "#533", "MERGED_OUTCOMES": "GoGREEN Top21",
            "HISTORY": "READ_ONLY_MYCIELIUM_CONSUMER",
            "merge_authorized": False, "security_waiver": False,
            "QPS_owner_accepted": False, "formal_root_closures": 0,
            "public_deployed": False, "admission": "HOLD",
        },
    }


def mini_chart(report):
    rows = report["daily_bins"]
    width, height = 980, 310
    maximum = max([x["observed"] for x in rows] + [1])
    tick = max(1, ((maximum + 4) // 5))  # integer-only Y-axis ticks
    cap = ((maximum + tick - 1) // tick) * tick
    x0, plot_w = 64, 880
    y0, h = 252, 206
    bars = []
    for i, d in enumerate(rows):
        unit_w = plot_w / max(1, len(rows))
        w = max(7, unit_w * .69)
        x = x0 + i * unit_w + (unit_w - w) / 2
        bottom = y0
        for key, color in (("pass", "#45cda6"), ("red", "#f27d86"),
                           ("cancelled", "#f4bd60"), ("other", "#718ba7"),
                           ("skipped", "#718ba7")):
            value = d[key]
            dh = h * value / cap
            bottom -= dh
            if value:
                bars.append(
                    f'<rect x="{x:.1f}" y="{bottom:.1f}" width="{w:.1f}" '
                    f'height="{dh:.1f}" fill="{color}">'
                    f'<title>{html.escape(d["date"])} {key}: {value}</title></rect>')
        label = d["date"][5:]
        bars.append(f'<text x="{x+w/2:.1f}" y="{y0+17}" '
                    f'font-size="10" fill="#cbd8eb" text-anchor="middle">{label}</text>')
    grid = []
    for v in range(0, cap + 1, tick):
        yy = y0 - h * v / cap
        grid.append(f'<line x1="{x0}" y1="{yy:.1f}" x2="{x0+plot_w}" '
                    f'y2="{yy:.1f}" stroke="#30465f" stroke-width="1"/>'
                    f'<text x="52" y="{yy+4:.1f}" text-anchor="end" '
                    f'font-size="11" fill="#cbd8eb">{v}</text>')
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 980 310" '
            'role="img" aria-label="Native workflow run outcomes by UTC date">'
            '<title>CODEX Mycelium terminal workflow run outcomes, integer counts</title>' +
            ''.join(grid + bars) + '</svg>\n')


def lineage_dag(report):
    return {
        "schema": "missioncontrol.mycelium.history_spine.v1",
        "nodes": [
            {"id": "SOURCE", "name": "CODEX workflow source, exact SHA", "evidence": "API"},
            {"id": "RUN", "name": "run ID + attempt + conclusion", "evidence": "OBSERVED"},
            {"id": "JOB", "name": "job ID + full step chain", "evidence": "SELECTED"},
            {"id": "FIRST_RED", "name": "first failing step + fingerprint", "evidence": "SAMPLED"},
            {"id": "SKIPS", "name": "downstream skipped steps", "evidence": "CHRONOLOGY"},
            {"id": "PR_MERGE", "name": "PR merge chronology vs checks", "evidence": "SAMPLED"},
            {"id": "RECURSE", "name": "owner repair → new run", "evidence": "DECLARED"},
            {"id": "CONTROL", "name": "independent acceptance gates", "evidence": "HOLD"},
        ],
        "edges": [
            {"from": "SOURCE", "to": "RUN", "evidence": "API"},
            {"from": "RUN", "to": "JOB", "evidence": "SAMPLED_RUN_JOB"},
            {"from": "JOB", "to": "FIRST_RED", "evidence": "SAMPLED_JOB_STEP"},
            {"from": "FIRST_RED", "to": "SKIPS", "evidence": "PRECEDES_NOT_CAUSES"},
            {"from": "RUN", "to": "PR_MERGE", "evidence": "EXACT_SHA_ONLY"},
            {"from": "PR_MERGE", "to": "CONTROL", "evidence": "OWNER_GATED"},
            {"from": "SKIPS", "to": "RECURSE", "evidence": "DECLARED"},
            {"from": "RECURSE", "to": "SOURCE", "evidence": "NEXT_PULSE_ONLY"},
        ],
        "sipoc": {
            "supplier": "CODEX GitHub Actions and GoGREEN merged outcome owner",
            "input": "pinned run, attempt, job, step and sampled PR metadata",
            "process": "typed census → terminality → first red → lineage → metric",
            "output": "read-only history, dashboard, source-bound candidates",
            "customer": "CODE PURPLE/EVERRED owner and independent reviewer",
        },
        "authority_transfer": False, "formal_root_credit": 0,
    }


def mermaid(dag):
    lines = ["flowchart LR"]
    for n in dag["nodes"]:
        lines.append('  ' + n["id"] + '["' + n["name"] + '"]')
    for e in dag["edges"]:
        sep = " -.-> " if e["evidence"] in {"DECLARED", "NEXT_PULSE_ONLY"} else " --> "
        lines.append("  " + e["from"] + sep + e["to"])
    return "\n".join(lines) + "\n"


def html_page(report, graph):
    pop = report["run_population"]
    summary = [
        ("Runs observed", str(pop["observed"]) + "/" +
         str(pop["eligible_api_reported"])),
        ("Terminal", str(pop["terminal"])),
        ("Successful", str(pop["successful"])),
        ("Failing", str(pop["failed"])),
        ("Job detail sampled", str(report["job_detail"]["observed_run_records"])),
        ("First-red fingerprints", str(report["first_red"]["sampled_distinct_fingerprints"])),
        ("Merged PRs with RED", str(report["merged_with_red"]["with_observed_native_red"])),
    ]
    cards = ''.join('<article class="metric"><small>' + html.escape(label) +
                    '</small><strong>' + html.escape(value) + '</strong></article>'
                    for label, value in summary)
    clusters = []
    for row in report["first_red"]["clusters"][:22]:
        first = row["first_red"][0]
        clusters.append(
            '<tr><td><code>' + html.escape(row["id"]) + '</code></td><td>' +
            html.escape(row["label"]) + '</td><td class="number">' +
            str(row["occurrences"]) + '</td><td><a href="' +
            html.escape(first["url"], quote=True) + '">run ' +
            str(first["run_id"]) + ' · job ' + str(first["job_id"]) +
            '</a></td><td>' + str(first["downstream_skipped_step_count"]) +
            '</td></tr>')
    prs = []
    for item in report["merged_with_red"]["prs"][:30]:
        icon = item["title"]
        status = "RED OBSERVED" if (
            item["red_before_merge"] or item["red_after_merge"]) else "NO OBSERVED RED"
        prs.append('<tr><td><span class="sym">' +
                   html.escape(icon["icon"]) + ' ' +
                   html.escape(icon["scope_icon"]) + '</span> ' +
                   '<a href="' + html.escape(item["url"], quote=True) + '" title="' +
                   html.escape(icon["title"], quote=True) + '">#' +
                   str(item["number"]) + '</a></td><td>' +
                   html.escape(icon["kind"]) + ' / ' +
                   html.escape(icon["family"]) +
                   (' / ' + html.escape(icon["wave"]) if icon["wave"] else '') +
                   '</td><td class="number">' + str(item["red_before_merge"]) +
                   '</td><td class="number">' + str(item["red_after_merge"]) +
                   '</td><td class="number">' +
                   str(item["native_failed_jobs_completed_before_merge"]) +
                   '</td><td class="number">' +
                   str(item["native_failed_jobs_completed_after_merge"]) +
                   '</td><td>' + status + '</td></tr>')
    svg = mini_chart(report)
    return (
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>CODE PURPLE · Mycelium historical run DAG</title>'
        '<style>:root{color-scheme:dark;background:#0b1627;color:#edf5ff;'
        'font:14px/1.5 system-ui}*{box-sizing:border-box}body{margin:auto;'
        'padding:18px;max-width:1320px}h1{font-size:24px;margin:0}'
        'h2{font-size:17px}.muted,small{color:#b9cbe0}'
        '.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));'
        'gap:10px}.metric,section{border:1px solid #465a70;border-radius:10px;'
        'padding:14px;background:#122238}.metric small,.metric strong{display:block}'
        '.metric strong{font-size:23px;font-variant-numeric:tabular-nums}'
        '.grid{display:grid;grid-template-columns:1.1fr 1fr;gap:14px;margin-top:14px}'
        '@media(max-width:850px){.grid{grid-template-columns:1fr}}'
        '.wide{overflow-x:auto}table{border-collapse:collapse;min-width:590px;width:100%}'
        'th,td{text-align:left;padding:7px;border-bottom:1px solid #34485d}'
        'th{font-size:12px;color:#c7d9e7}a{color:#91d8ff}'
        '.number{text-align:right;font-variant-numeric:tabular-nums}'
        '.sym{white-space:nowrap}code{font-size:12px;overflow-wrap:anywhere}'
        '.chips{display:flex;gap:12px;flex-wrap:wrap;margin:8px 0}'
        '.chip{border:1px solid #687f96;border-radius:8px;padding:4px 8px}'
        '</style><body><header><h1>🟣 CODE PURPLE · 🧬 MYCELIUM run-history DAG</h1>'
        '<p class="muted">Read-only GitHub native Actions history. Partial job/log '
        'sampling is not a full causal-root census. Merged ≠ qualified admission.</p>'
        '<div class="chips"><span class="chip">🔧 fix(scope W5) = repair / family / wave</span>'
        '<span class="chip">🧪 test(scope) = test</span>'
        '<span class="chip">🟢 GoGREEN = positive evidence</span>'
        '<span class="chip">🔴 EVERRED = persistent symptom</span></div>'
        '</header><div class="summary">' + cards + '</div>'
        '<div class="grid"><section><h2>Native run burndown · integer counts</h2>' +
        svg + '<small>UTC daily observations, not test counts. Days with no runs '
        'are absent; sampled job detail shown separately.</small></section>'
        '<section><h2>Proof, propagation, capability</h2>'
        '<p>Workflow run completeness: <strong>' +
        ('COMPLETE AT CAPTURE' if pop["complete"] else 'PARTIAL / NONATOMIC') +
        '</strong>. Job detail: ' + str(report["job_detail"]["observed_run_records"]) +
        ' selected run IDs; prior rerun attempts and full archive ZIP member '
        'verification: <strong>UNKNOWN</strong> unless separately verified.</p>'
        '<p>Sampling strata: RED ' +
        str(report["job_detail"]["sampled_failed_runs"]) +
        ' / GREEN ' + str(report["job_detail"]["sampled_successful_runs"]) +
        ' selected runs; bounded log reads ' +
        str(report["job_detail"]["failure_log_reads"]) + '/' +
        str(report["job_detail"]["log_read_attempts"]) +
        '. Annotated-green severity: <strong>UNKNOWN</strong>.</p>'
        '<p>First-red occurrences: ' +
        str(report["first_red"]["sampled_occurrences"]) +
        '; distinct fingerprints: ' +
        str(report["first_red"]["sampled_distinct_fingerprints"]) +
        '; downstream skips: ' +
        str(report["first_red"]["downstream_skipped_step_occurrences"]) +
        '; independently accepted root closures: <strong>0</strong>.</p>'
        '<p>M1 partial; M2/M3 HOLD; PCA, BT, Six Sigma NOT QUALIFIED. '
        'Worker-hours/capacity UNKNOWN. #530 ZIP custody, #531 fleet breadth, '
        '#533 method viewer unchanged.</p></section></div>'
        '<div class="grid"><section><h2>EVERRED · attributable first-step clusters</h2>'
        '<div class="wide"><table><tr><th>Fingerprint</th><th>First failing step '
        '(not causal root)</th><th>Occurrences</th><th>Native job</th><th>Skipped '
        'downstream</th></tr>' + ''.join(clusters) +
        '</table></div></section>'
        '<section><h2>GoGREEN · merged outcomes with unqualified red</h2>'
        '<div class="wide"><table><tr><th>PR</th><th>Type / scope / wave</th>'
        '<th>Run proxy before</th><th>Run proxy after</th>'
        '<th>Native failed jobs before*</th><th>Native failed jobs after*</th>'
        '<th>Observation</th></tr>' +
        ''.join(prs) + '</table></div>'
        '<p class="muted">Recent PR selection, not lifetime merge denominator. '
        'Run columns use updated_at and remain weak proxies. *Native-job columns '
        'count only timestamped failures in the selected job-detail cohort '
        '(unknown jobs are not zero). Neither view establishes required-status '
        'or independent-review admission. Checking merged main is separate.</p>'
        '</section></div><p class="muted">Native source: ' +
        html.escape(report["producer"]) + '. Captured ' +
        html.escape(report["capture_at"]) +
        '. Actions artifact preview only; no Pages publication or owner authority.</p>'
        '</body></html>\n')


def plotly_payload(report):
    return {
        "schema": "missioncontrol.mycelium.plotly_traces.v1",
        "data": [{"type": "bar", "name": name,
                  "x": [b["date"] for b in report["daily_bins"]],
                  "y": [b[key] for b in report["daily_bins"]]}
                 for key, name in (("pass", "Success"), ("red", "Fail"),
                                   ("cancelled", "Cancelled"),
                                   ("other", "Nonterminal/neutral"),
                                   ("skipped", "Skipped"))],
        "layout": {"barmode": "stack", "xaxis": {"type": "category"},
                   "yaxis": {"dtick": 1, "rangemode": "tozero",
                             "title": "Whole workflow runs (not roots)"}},
        "publisher": "EXISTING_ATLAS_OPTIONAL_CLIENT_NOT_NEW_PAGES",
    }


def build(source, source_sha, out, *, check=False):
    require(isinstance(source_sha, str) and SHA.fullmatch(source_sha),
            "renderer source SHA required")
    report = summarize(source)
    graph = lineage_dag(report)
    files = {
        "metrics.json": canonical(report),
        "spine.json": canonical(graph),
        "spine.mmd": mermaid(graph).encode("utf-8"),
        "burndown.svg": mini_chart(report).encode("utf-8"),
        "plotly.json": canonical(plotly_payload(report)),
        "index.html": html_page(report, graph).encode("utf-8"),
    }
    manifest = {
        "schema": "missioncontrol.mycelium.history_preview.v1",
        "hub_renderer_head": source_sha,
        "CODEX_main_at_capture": source["source_main_after"],
        "run_inventory_complete": source["run_inventory_complete"],
        "file_sha256": {name: hashlib.sha256(raw).hexdigest()
                        for name, raw in sorted(files.items())},
        "artifact_zip_bytes_independently_verified": False,
        "public_pages_deployed": False, "admission": "HOLD",
        "root_closures": 0, "authority_transfer": False,
    }
    files["manifest.json"] = canonical(manifest)
    if check:
        require(out.is_dir(), "candidate output not found")
        require(sorted(x.name for x in out.iterdir()) == sorted(files),
                "unexpected or missing preview member")
        for name, raw in files.items():
            require((out / name).read_bytes() == raw,
                    "determinism drift: " + name)
    else:
        out.mkdir(parents=True, exist_ok=True)
        for name, raw in files.items():
            (out / name).write_bytes(raw)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--source-sha", required=True)
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    report = build(payload, args.source_sha, args.out, check=args.check)
    print(json.dumps({
        "observed_runs": report["run_population"]["observed"],
        "eligible": report["run_population"]["eligible_api_reported"],
        "first_red_sampled": report["first_red"]["sampled_occurrences"],
        "distinct_fingerprints": report["first_red"]["sampled_distinct_fingerprints"],
        "accepted_roots": 0, "admission": "HOLD",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
