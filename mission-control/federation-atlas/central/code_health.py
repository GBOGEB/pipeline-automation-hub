#!/usr/bin/env python3
"""Mission Control Central / CODE-HEALTH — source-bound read-only projection.

Extends the controlled Method Atlas. It never triggers a worker, modifies
GitHub, certifies root closure, or promotes a candidate to main authority.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REGISTRY = HERE / "CODE_HEALTH_CENTRAL_v1.json"
PROCESS = HERE.parent / "PROCESS_LANES_v1.json"
TEMPLATE = HERE / "dashboard_template.html"
SHA = re.compile(r"^[0-9a-f]{40}$")
TRIAD = ("N-1", "N", "N+1")
PRIORITIES = ("P0", "P1", "P2", "P3")
VALID_BINDINGS = ("DECLARED", "OBSERVED_HISTORICAL", "NATIVE_CURRENT")
VALID_ROUTING = ("WAIT_OWNER", "WAIT_INPUT", "WAIT_CAPACITY", "PREPARE_ONLY",
                 "MAY_START", "BLOCKED_P0", "RECENSUS_REQUIRED")


def require(value, reason):
    if not value:
        raise ValueError(reason)


def safe(value):
    return html.escape(str(value), quote=True)


def read_json(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), "controlled JSON required")
    require(0 < path.stat().st_size <= 2_000_000, "JSON size out of bounds")
    return json.loads(path.read_text(encoding="utf-8"))


def qualified_integer(value):
    return type(value) is int and value >= 0


def validate(source, *, process_path=PROCESS):
    """Reject promotion by null filling, unbounded totals, or dangling edges."""
    require(isinstance(source, dict), "source object required")
    require(source.get("schema") == "missioncontrol.code_health_frontier.v1",
            "unsupported CODE-HEALTH schema")
    authority = source["authority"]
    require(authority["repository"] == "GBOGEB/pipeline-automation-hub",
            "wrong owning repository")
    require(bool(SHA.fullmatch(authority["source_sha"])), "invalid authority SHA")
    require(authority["mode"] == "READ_ONLY_CANDIDATE", "authority escalation")
    for flag in ("authority_transfer", "mutation_enabled", "merge_authorized",
                 "rename_authorized"):
        require(authority.get(flag) is False, "non-authorized transition: " + flag)

    census = source["census"]
    repos = census["repositories"]
    require(isinstance(repos, list) and 1 <= len(repos) <= 90,
            "bounded repository census required")
    require(not census["population_complete_for_fleet"],
            "six-repo scope cannot claim full-fleet coverage")
    require(census["scope"] == "SIX_NAMED_REPOSITORIES_NOT_ALL_FLEET",
            "unmatched census scope")
    require(len(repos) == 6, "this version binds six exact repositories")
    ids = [r["id"] for r in repos]
    require(len(set(ids)) == len(ids), "duplicate repository")
    totals = {"open_issues": 0, "closed_issues": 0, "open_prs": 0, "closed_prs": 0}
    for repo in repos:
        require(repo["id"].startswith("GBOGEB/"), "foreign repository")
        require(bool(SHA.fullmatch(repo["source_sha"])), "missing exact repo head")
        require(repo["default_branch"] in ("main", "master"), "unknown branch")
        require(repo["root_open"] is None and repo["root_closed"] is None,
                "GitHub issues do not establish BD roots")
        for field, key in (("open_issues", "open"), ("closed_issues", "closed")):
            value = repo["issue_register"][key]
            require(qualified_integer(value), "invalid GitHub issue count")
            totals[field] += value
        for field, key in (("open_prs", "open"), ("closed_prs", "closed")):
            value = repo["pull_request_register"][key]
            require(qualified_integer(value), "invalid GitHub PR count")
            totals[field] += value
    require(totals == census["totals"], "GitHub issue/PR totals mismatch")
    require(census["global_issue_counts"] is None, "not a whole-fleet census")

    process = read_json(process_path)
    lanes = process["lanes"]
    require(len(lanes) == 10 and sum(len(x["stages"]) for x in lanes) == 39,
            "canonical PROCESS_LANES population drift")
    lane_ids = [x["id"] for x in lanes]
    require(len(set(lane_ids)) == 10, "duplicate canonical lane")
    require(len(source["pillars"]) == 2 and
            {x["id"] for x in source["pillars"]} == {"L", "R"},
            "both execution pillars required")
    local = next(x for x in source["pillars"] if x["id"] == "L")
    require(local["machine_accessed"] is False and local["runtime_receipts"] is None,
            "no authenticated local cold pilot")
    runner = source["runner_capacity"]
    require(runner["policy_mode"] == "ADVISORY_ONLY_NO_AUTO_DISPATCH",
            "scheduler authority escalation")
    require(runner["native_available_slots"] is None,
            "unmeasured runner capacity cannot become a numeric slot count")

    graph = source["graph"]
    nodes = graph["nodes"]
    node_ids = [x["id"] for x in nodes]
    require(len(node_ids) == len(set(node_ids)), "duplicate graph node")
    edge_ids = set()
    for edge in graph["edges"]:
        require(edge["id"] not in edge_ids, "duplicate graph edge")
        edge_ids.add(edge["id"])
        require(edge["from"] in node_ids and edge["to"] in node_ids,
                "dangling graph edge")
        require(edge["binding"] in VALID_BINDINGS, "unknown edge evidence class")
        if edge["binding"] != "DECLARED":
            require(bool(edge["evidence"]), "bound edge needs source link")
    work = source["work"]
    work_ids = [row["id"] for row in work]
    require(len(work_ids) == len(set(work_ids)), "duplicate work item")
    for row in work:
        require(row["repo"] in ids, "work has no scoped repository")
        require(row["priority"] in PRIORITIES, "invalid work priority")
        require(row["url"].startswith("https://github.com/GBOGEB/"),
                "work URL outside governed owner")
        require(row["native_receipt"] is None,
                "this snapshot does not admit new worker receipts")
        require(all(d in work_ids or not d.startswith("W")
                    for d in row["depends"]), "work dependency missing")
    require(tuple(c["id"] for c in source["cycles"]) == TRIAD,
            "N-1/N/N+1 is mandatory and ordered")
    require(source["cycles"][0]["immutable"] and
            source["cycles"][1]["immutable"] and
            not source["cycles"][2]["immutable"], "temporal role drift")
    require(source["cycles"][1]["metrics"]["open_issues"] == totals["open_issues"],
            "N issue population mismatch")
    require(source["root_ledger"]["canonical_open"] is None and
            source["root_ledger"]["canonical_closed"] is None,
            "do not translate issue counts into root counts")
    crew = source["crew"]
    require(crew["authenticated_launch_count"] is None and
            crew["accepted_rex_count"] is None and
            crew["crew_status"] == "STAGED_NOT_LAUNCHED" and
            not crew["remote_mutation_permission"], "Crew launch invented")
    for forecast in source["forecasts"]:
        require(forecast["actual_next"] is None,
                "predicted N+1 is not an observed future outcome")
        require(forecast["credit_to_engineering_roots"] is False,
                "forecast cannot close an engineering root")
    return {
        "schema": "missioncontrol.code_health.validation.v1",
        "repositories": len(repos),
        "open_issues": totals["open_issues"],
        "closed_issues": totals["closed_issues"],
        "open_prs": totals["open_prs"],
        "closed_prs": totals["closed_prs"],
        "lane_count": len(lanes),
        "stage_count": sum(len(x["stages"]) for x in lanes),
        "graph_nodes": len(nodes),
        "graph_edges": len(graph["edges"]),
        "work_items": len(work),
        "cohort_types": len(source["cohort_taxonomy"]),
        "verified_crew_launches": None,
        "canonical_root_closures": None,
        "admission": "HOLD",
        "authority_transfer": False,
    }


def forecast_score(record):
    """Pre-outcome forecast remains unscored; only same-unit actuals count."""
    predicted, actual = record["predicted_next"], record["actual_next"]
    if (predicted is None or actual is None or
            type(predicted) not in (int, float) or
            type(actual) not in (int, float)):
        return None
    require(math.isfinite(predicted) and math.isfinite(actual),
            "nonfinite predicted or actual")
    return abs(predicted - actual)


def matching_coverage(before, after):
    """Matched cohort only: total line AND branch populations must agree."""
    fields = ("repo", "scope", "config_id", "eligible_lines",
              "eligible_branches")
    require(isinstance(before, dict) and isinstance(after, dict),
            "coverage records required")
    require(all(key in before and key in after for key in fields),
            "incomplete coverage cohort")
    if any(before[k] != after[k] for k in fields):
        return {"status": "INCOMPARABLE", "delta_pp": None}
    total = after["eligible_lines"] + after["eligible_branches"]
    require(qualified_integer(total) and total > 0, "invalid coverage scope")
    for obj in (before, after):
        for covered, eligible in (("covered_lines", "eligible_lines"),
                                  ("covered_branches", "eligible_branches")):
            require(qualified_integer(obj.get(covered)) and
                    obj[covered] <= obj[eligible], "invalid coverage numerator")
    b = before["covered_lines"] + before["covered_branches"]
    a = after["covered_lines"] + after["covered_branches"]
    return {"status": "COMPARABLE", "delta_pp": round(100 * (a-b)/total, 8),
            "numerator_delta": a-b, "eligible": total}


def duration_seconds(start_utc, end_utc):
    """No native timestamps -> UNKNOWN, never inferred 0 seconds."""
    if start_utc is None or end_utc is None:
        return None
    try:
        start = datetime.fromisoformat(start_utc.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_utc.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if start.tzinfo is None or end.tzinfo is None:
        return None
    seconds = (end.astimezone(timezone.utc) -
               start.astimezone(timezone.utc)).total_seconds()
    return seconds if seconds >= 0 else None


def native_p95(values):
    """Nearest rank, positive observations; empty -> UNKNOWN."""
    require(all(type(x) in (int, float) and math.isfinite(x) and x >= 0
                for x in values), "invalid native latency")
    if not values:
        return None
    return sorted(values)[math.ceil(len(values) * 0.95)-1]


def route_work(work, runner):
    """ADVISORY scheduling only; nothing here dispatches a job."""
    by_id = {item["id"]: item for item in work}
    rows = []
    for item in work:
        if item["status"] in ("HOLD", "P0_REVIEW_PENDING", "DEFER"):
            route = "WAIT_OWNER"
        elif item["status"] in ("STAGED_NOT_LAUNCHED",):
            route = "BLOCKED_P0"
        elif any(by_id[d]["status"] not in ("CONTROL", "VERIFIED")
                 for d in item["depends"] if d in by_id):
            route = "WAIT_INPUT"
        elif runner["native_available_slots"] is None:
            route = "WAIT_CAPACITY"
        elif runner["native_available_slots"] <= 0:
            route = "WAIT_CAPACITY"
        elif item["status"] in ("PROOF_PENDING", "BACKLOG",
                                "DRAFT_PROOF_PENDING", "ONGOING_CO_DEVELOPMENT"):
            route = "MAY_START"
        else:
            route = "RECENSUS_REQUIRED"
        require(route in VALID_ROUTING, "unknown bounded routing")
        rows.append({"id": item["id"], "route": route,
                     "owner": item["owner"], "priority": item["priority"],
                     "automatically_launched": False})
    return rows


def mermaid(source):
    """Readable dependency view: declared edges do not imply execution."""
    lines = ["flowchart LR", '  LOCAL["Pillar L: Cold / PC"]',
             '  CLOUD["Pillar R: GitHub CI"]', '  PIN["SHA / evidence pin"]',
             '  ROOT["Root / BD ownership"]', '  GATE{"P0 admission?"}',
             '  WAIT["HOLD / WAIT"]', '  CONTROL["Main readback + REX"]',
             "  LOCAL --> PIN", "  CLOUD --> PIN", "  PIN --> ROOT",
             "  ROOT --> GATE", "  GATE -->|UNKNOWN or FAIL| WAIT",
             "  GATE -->|independently admitted| CONTROL"]
    for row in source["work"]:
        if row["id"] in ("W01", "W02", "W03", "W04", "W05", "W06",
                          "W07", "W08", "W09", "W10", "W11", "W12"):
            lines.append('  ' + row["id"] + '["' +
                         row["id"] + " " + row["root_family"] + '"]')
            for dep in row["depends"]:
                if dep.startswith("W"):
                    lines.append("  " + dep + " --> " + row["id"])
    lines.extend(["  ROOT --> W01", "  ROOT --> W03",
                  "  ROOT --> W04", "  ROOT --> W05",
                  "  W02 --> GATE", "  W06 --> GATE"])
    return "\n".join(lines) + "\n"


def graph_svg(source):
    """Native SVG view of all typed nodes and edges, no external library."""
    graph = source["graph"]
    groups = {"PILLAR": [], "REPOSITORY": [], "LANE": [], "ROOT": [],
              "CONTROL": []}
    for node in graph["nodes"]:
        groups[node["kind"]].append(node)
    coords = {}
    x_by_type = {"PILLAR": 30, "REPOSITORY": 270, "LANE": 510,
                 "ROOT": 750, "CONTROL": 990}
    for kind, group in groups.items():
        for index, node in enumerate(group):
            coords[node["id"]] = (x_by_type[kind], 82 + index * 80)
    height = max(y for x, y in coords.values()) + 105
    parts = [
        '<svg viewBox="0 0 1225 ' + str(height) +
        '" role="img" aria-label="26 node source-bound Mission Control graph"',
        ' xmlns="http://www.w3.org/2000/svg">',
        '<defs><marker id="arrow" markerWidth="7" markerHeight="7" refX="6" '
        'refY="3.5" orient="auto"><path d="M0 0 L7 3.5 L0 7 Z" '
        'fill="#88a1b6"/></marker></defs>',
    ]
    for edge in graph["edges"]:
        xa, ya = coords[edge["from"]]
        xb, yb = coords[edge["to"]]
        dashed = ' stroke-dasharray="5 5"' if edge["binding"] == "DECLARED" else ""
        parts.append(
            '<path d="M' + str(xa+205) + " " + str(ya+18) +
            " C" + str((xa+xb+205)/2) + " " + str(ya+18) + " " +
            str((xa+xb+205)/2) + " " + str(yb+18) + " " +
            str(xb-6) + " " + str(yb+18) +
            '" fill="none" stroke="#67849c" stroke-width="1.4" '
            'marker-end="url(#arrow)" opacity=".48"' + dashed + '>'
            '<title>' + safe(edge["type"] + ": " + edge["binding"]) +
            "</title></path>"
        )
    for node in graph["nodes"]:
        x, y = coords[node["id"]]
        color = {"PILLAR": "#58c0d6", "REPOSITORY": "#82a8ed",
                 "LANE": "#d6b377", "ROOT": "#ed9d86",
                 "CONTROL": "#c5a1f2"}[node["kind"]]
        parts.extend([
            f'<rect x="{x}" y="{y}" width="205" height="39" rx="8" '
            f'fill="#182538" stroke="{color}" stroke-width="1.5"/>',
            f'<text x="{x+12}" y="{y+25}" fill="#e5f2fa" font-size="12" '
            'font-family="system-ui">' + safe(node["label"][:27]) + "</text>",
        ])
    parts.append("</svg>")
    return "".join(parts)


def row_cells(*items):
    return "<tr>" + "".join("<td>" + safe(x) + "</td>" for x in items) + "</tr>"


def summary_cards(metrics):
    pairs = [("Repos in scope", metrics["repositories"], "of named scope only"),
             ("Issues open", metrics["open_issues"], "not causal BD roots"),
             ("Issues closed", metrics["closed_issues"], "GitHub records"),
             ("Open PRs", metrics["open_prs"], "concurrent source candidates"),
             ("Graph", str(metrics["graph_nodes"]) + " / " +
              str(metrics["graph_edges"]), "nodes / typed edges"),
             ("Canonical lanes", str(metrics["lane_count"]) + " / " +
              str(metrics["stage_count"]), "lanes / stages")]
    return "".join(
        '<article class="card kpi"><div class="eyebrow">' + safe(name) +
        '</div><strong>' + safe(value) + '</strong><small>' + safe(note) +
        "</small></article>" for name, value, note in pairs
    )


def render(source, metrics, routes, *, checkout_sha):
    template = TEMPLATE.read_text(encoding="utf-8")
    work_routes = {r["id"]: r for r in routes}
    repo_rows = "".join(
        "<tr><td><a href=" + json.dumps("https://github.com/" + r["id"]) +
        ">" + safe(r["id"]) + "</a></td><td><code>" +
        safe(r["source_sha"][:11]) + "</code> · " +
        safe(r["default_branch"]) + "</td><td>" +
        safe(r["issue_register"]["open"]) + "</td><td>" +
        safe(r["issue_register"]["closed"]) + "</td><td>" +
        safe(r["pull_request_register"]["open"]) + "</td><td>" +
        safe(r["pull_request_register"]["closed"]) + "</td></tr>"
        for r in source["census"]["repositories"]
    )
    work_rows = "".join(
        '<tr data-priority="' + safe(w["priority"]) + '" data-repo="' +
        safe(w["repo"]) + '"><td>' + safe(w["id"]) + "</td><td>" +
        '<a href="' + safe(w["url"]) + '">' + safe(w["root_family"]) +
        "</a><small>" + safe(w["repo"]) + "</small></td><td>" +
        safe(w["owner"]) + "</td><td>" +
        safe(w["status"]) + "</td><td><strong>" +
        safe(work_routes[w["id"]]["route"]) + "</strong></td><td>" +
        safe(",".join(w["depends"]) or "—") + "</td></tr>"
        for w in source["work"]
    )
    cycle_cards = "".join(
        '<article class="card cycle"><div class="eyebrow">' +
        safe(c["id"] + " / " + c["label"]) + "</div><p>" +
        safe(c["source_kind"]) + "</p><dl>" +
        "".join("<div><dt>" + safe(k.replace("_", " ")) + "</dt><dd>" +
                safe("UNKNOWN" if v is None else v) + "</dd></div>"
                for k, v in list(c["metrics"].items())[:7]) +
        "</dl></article>"
        for c in source["cycles"]
    )
    sipoc = source["sipoc"]
    sipoc_cards = "".join(
        '<article class="card"><h3>' + safe(k.upper()) + "</h3><p>" +
        safe(" → ".join(v)) + "</p></article>"
        for k, v in sipoc.items()
    )
    forecast = "".join(
        row_cells(r["id"], r["metric"],
                  r["baseline"] if r["baseline"] is not None else "UNKNOWN",
                  r["predicted_next"] if r["predicted_next"] is not None else "UNKNOWN",
                  r["target_next"] if r["target_next"] is not None else "UNKNOWN",
                  r["actual_next"] if r["actual_next"] is not None else "PENDING",
                  r["basis"]) for r in source["forecasts"]
    )
    columns = [
        ("Pillar L - local", "UNVERIFIED", "C:\\repos is proposed, no PC access"),
        ("Pillar R - GitHub", "PARTIAL", "Native PR/issue/head observation only"),
        ("Crew launches", "UNKNOWN", "Eight DAB proposal jobs are not launches"),
        ("REX acceptance", "UNKNOWN", "No authenticated accepted Crew return"),
        ("Capacity/queue", "UNKNOWN", "No eligible runner heartbeat/job sample"),
        ("Engineering roots", "UNKNOWN", "GitHub issues are not root counts"),
        ("P0 admission", "HOLD", "A10, governance, security, review independent"),
    ]
    telemetry = "".join(row_cells(*line) for line in columns)
    replacements = {
        "__SOURCE_CHECKOUT_SHA__": safe(checkout_sha),
        "__SNAPSHOT_SHA__": safe(source["authority"]["source_sha"]),
        "__CENSUS_DATE__": safe(source["census_date"]),
        "__CARDS__": summary_cards(metrics),
        "__REPOS__": repo_rows,
        "__WORK__": work_rows,
        "__CYCLES__": cycle_cards,
        "__SIPOC__": sipoc_cards,
        "__FORECASTS__": forecast,
        "__TELEMETRY__": telemetry,
        "__GRAPH__": graph_svg(source),
        "__WORK_COUNT__": str(len(source["work"])),
        "__NODE_COUNT__": str(len(source["graph"]["nodes"])),
        "__EDGE_COUNT__": str(len(source["graph"]["edges"])),
        "__ALIAS__": safe(source["authority"]["alias_candidate"]),
    }
    for marker, content in replacements.items():
        require(template.count(marker) >= 1, "dashboard placeholder missing: " + marker)
        template = template.replace(marker, content)
    require(not re.search(r"__[A-Z_]+__", template),
            "unbound dashboard template variable")
    return template


def build(source_path, out, *, checkout_sha):
    source_path = Path(source_path)
    source = read_json(source_path)
    metrics = validate(source)
    require(bool(SHA.fullmatch(checkout_sha)), "exact checkout SHA required")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    route = route_work(source["work"], source["runner_capacity"])
    proof = {
        **metrics,
        "checkout_sha": checkout_sha,
        "snapshot_main_sha": source["authority"]["source_sha"],
        "snapshot_date": source["census_date"],
        "snapshot_readback_class": source["census"]["source_type"],
        "snapshot_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "crew_proposal_jobs_user_reported": source["crew"]["dab_proposal_jobs_passed_historical"],
        "crew_auth_launches": None,
        "runner_capacity_slots": None,
        "prediction_scored": 0,
        "work_routing": route,
        "admission": "HOLD",
        "merge_authorized": False,
    }
    outputs = {
        "code-health.html": render(source, metrics, route,
                                   checkout_sha=checkout_sha),
        "code-health.json": json.dumps(proof, indent=2, sort_keys=True) + "\n",
        "code-health-dag.mmd": mermaid(source),
    }
    file_hashes = {}
    for name, content in outputs.items():
        path = out / name
        path.write_text(content, encoding="utf-8")
        file_hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {
        "schema": "missioncontrol.code_health.artifact_manifest.v1",
        "checkout_sha": checkout_sha,
        "source_sha256": proof["snapshot_sha256"],
        "files_sha256": file_hashes,
        "admission": "HOLD",
        "authority_transfer": False,
        "merge_authorized": False,
    }
    (out / "code-health-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return proof


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=REGISTRY)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--exact-git-sha")
    args = parser.parse_args(argv)
    source = read_json(args.source)
    metrics = validate(source)
    if args.out:
        require(args.exact_git_sha is not None,
                "artifact generation needs checked-out source SHA")
        result = build(args.source, args.out, checkout_sha=args.exact_git_sha)
        print(json.dumps(result, sort_keys=True))
    else:
        print(json.dumps(metrics, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
