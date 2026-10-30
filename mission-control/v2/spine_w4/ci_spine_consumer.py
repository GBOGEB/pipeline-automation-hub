#!/usr/bin/env python3
"""W4/JADE CI-spine read-only consumer; imports the canonical W4 graph renderer.

No scheduler, live fetch, gate, independent approval, metric calculation or
publisher. All input snapshots retain their original identities and periods.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
HUB = "GBOGEB/pipeline-automation-hub"
SOURCE_SCHEMA = "jade.devops.ci-spine.index.v1"
DELTA_SCHEMA = "jade.devops.ci-spine.source-delta.v1"
METRICS_SCHEMA = "jade.devops.actions-metrics.v1"
WAVE_SCHEMA = "jade.devops.ci-spine.waves.v1"
OUTPUT_SCHEMA = "missioncontrol.w4.ci-spine.consumer.v1"
SHA40 = re.compile(r"^[0-9a-f]{40}$")

spec = importlib.util.spec_from_file_location("existing_w4_spine_renderer", HERE / "spine_control.py")
if spec is None or spec.loader is None:
    raise RuntimeError("canonical W4 graph renderer is missing")
W4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(W4)


def need(ok, reason):
    if not ok:
        raise ValueError("CI_SPINE_VIEW_HOLD: " + reason)


def esc(s):
    return html.escape(str(s) if s is not None else "UNKNOWN", quote=True)


def table(cols, rows):
    head = "".join("<th scope='col'>" + esc(c) + "</th>" for c in cols)
    body = "".join("<tr>" + "".join("<td>" + esc(c) + "</td>" for c in row) + "</tr>" for row in rows)
    return "<div style='overflow-x:auto'><table><thead><tr>" + head + "</tr></thead><tbody>" + body + "</tbody></table></div>"


def render(index, control, metrics=None, delta=None, wave=None, expected_head=""):
    """Return HTML + source-bound viewing receipt. Never upgrade a HOLD."""
    w4_receipt = W4.validate(control)
    need(isinstance(index, dict) and index.get("schema") == SOURCE_SCHEMA, "index schema")
    source = index.get("source")
    assurance = index.get("assurance")
    anchors = index.get("anchors")
    need(isinstance(source, dict) and isinstance(assurance, dict), "nested index identity")
    sha = source.get("checkout_sha")
    need(isinstance(sha, str) and SHA40.fullmatch(sha), "40-hex index source")
    need(source.get("expected_sha") in (None, sha), "mixed index heads")
    need(not expected_head or (SHA40.fullmatch(expected_head) and expected_head == sha), "wrong expected source")
    need(index.get("verdict") == "PASS_STATIC_BINDINGS_ONLY"
         and index.get("errors") == [] and assurance.get("merge_admission") == "HOLD",
         "static source qualified, but non-authoritative")
    need(isinstance(anchors, list) and anchors and all(
        isinstance(a, dict) and a.get("static_binding") == "PASS"
        and isinstance(a.get("id"), str) and isinstance(a.get("path"), str)
        for a in anchors), "incomplete authority anchor list")

    metric_status, metric_rows, metric_asof = "NOT_SUPPLIED", [], None
    if metrics is not None:
        need(isinstance(metrics, dict) and metrics.get("schema") == METRICS_SCHEMA,
             "canonical Actions metrics schema")
        need(isinstance(metrics.get("repos"), list), "Actions metrics missing repository cohorts")
        hub = next((x for x in metrics["repos"]
                    if isinstance(x, dict) and x.get("repo") == HUB), None)
        need(isinstance(hub, dict) and isinstance(hub.get("totals"), dict), "Hub metrics cohort missing")
        metric_asof = metrics.get("observed_at_utc")
        need(isinstance(metric_asof, str) and metric_asof, "metrics observation date missing")
        metric_status = ("SOURCE_MATCHED_HISTORICAL_SAMPLE" if
                         hub.get("head_sha") == sha and hub.get("same_pulse") is True
                         else "HISTORICAL_UNMATCHED_SOURCE")
        totals = hub["totals"]  # exact provider values; NO recomputation or interpolation
        metric_rows = [(key, totals.get(key), "Canonical Actions metric (sample if job-based)")
                       for key in ("job_coverage", "p95_job_queue_s", "avg_job_queue_s",
                                   "job_failure_rate", "total_minutes", "workflow_runs")]
    delta_status, changes, authority_changes = "NOT_SUPPLIED", [], []
    if delta is not None:
        need(isinstance(delta, dict) and delta.get("schema") == DELTA_SCHEMA, "delta schema")
        need(delta.get("verdict") in ("DIFFERENCE_REVIEW_REQUIRED", "NO_OBSERVED_SOURCE_DELTA")
             and delta.get("errors") == [], "delta has unresolved structural first-red")
        dsource = delta.get("source")
        need(isinstance(dsource, dict) and isinstance(dsource.get("current_sha"), str)
             and SHA40.fullmatch(dsource["current_sha"]), "delta source identity")
        changes = delta.get("workflow_changes")
        authority_changes = delta.get("authority_changes")
        need(isinstance(changes, list) and all(isinstance(row, dict) for row in changes),
             "delta workflow changes")
        need(isinstance(authority_changes, list) and all(
            isinstance(row, dict) and isinstance(row.get("id"), str) and row["id"]
            and row.get("status") == "AUTHORITY_REVIEW_REQUIRED"
            and "before" in row and "after" in row
            and row["before"] != row["after"]
            and all(binding is None or (
                isinstance(binding, dict)
                and isinstance(binding.get("path"), str) and bool(binding["path"])
            ) for binding in (row["before"], row["after"]))
            and (row["before"] is not None or row["after"] is not None)
            for row in authority_changes), "delta authority-binding change contract")
        need(delta["verdict"] != "NO_OBSERVED_SOURCE_DELTA"
             or (not changes and not authority_changes), "contradictory delta verdict")
        delta_status = ("SAME_CURRENT_SOURCE_REVIEW_ONLY" if dsource["current_sha"] == sha
                        else "STALE_DIFFERENT_SOURCE_NOT_JOINED")
    wave_status, tasks = "NOT_SUPPLIED", []
    if wave is not None:
        need(isinstance(wave, dict) and wave.get("schema") == WAVE_SCHEMA
             and type(wave.get("max_workers")) is int
             and isinstance(wave.get("tasks"), list), "wave plan schema")
        tasks = wave["tasks"]
        need(all(isinstance(t, dict) for t in tasks), "invalid worker task")
        wave_status = "DECLARED_ONLY_NO_DISPATCH"

    # Reuse the exact existing W+4 graph and HTML layout, without copying DAG/SIPOC logic.
    existing = W4.html_view(control, w4_receipt, W4.svg(control))
    marker = "</main></body></html>"
    need(existing.count(marker) == 1, "W4 renderer layout changed")
    anchor_rows = [(a.get("id"), a.get("phase"), a.get("path"), a.get("static_binding"))
                   for a in anchors]
    change_rows = [(c.get("path"), c.get("change"), c.get("safety_attention"),
                    ", ".join(map(str, c.get("changed_fields", [])))) for c in changes]
    authority_rows = [(a["id"], a["status"],
                       json.dumps(a["before"], sort_keys=True, ensure_ascii=True),
                       json.dumps(a["after"], sort_keys=True, ensure_ascii=True))
                      for a in authority_changes]
    task_rows = [(t.get("id"), t.get("stage"), t.get("lane"), "NOT_EXECUTED") for t in tasks]
    section = (
        "<section class='panel' id='ci-spine-evidence'><h2>CI source evidence · read-only consumer</h2>"
        "<p><strong>Admission: HOLD.</strong> Workflow status, static binding and sampled timing "
        "cannot certify a release, dispatch a worker or replace independent review.</p>"
        "<p>Source index SHA: <code>" + esc(sha) + "</code>; anchors: " + esc(len(anchors))
        + ". W4 source baseline SHA: <code>" + esc(w4_receipt["source_sha"]) + "</code>.</p>"
        "<p>Existing graph owner: <a href='https://github.com/GBOGEB/pipeline-automation-hub/blob/master/"
        "mission-control/jade_temple/site/cicd_dag.html'>JADE DAG / SIPOC (source view)</a>. "
        "No replicated graph or metric engine is embedded.</p>"
        "<h3>Authoritative anchor crosswalk (static only)</h3>"
        + table(("Anchor", "Phase", "Canonical workflow", "Static binding"), anchor_rows)
        + "<h3>Actions provider data</h3><p>Binding: <strong>" + esc(metric_status)
        + "</strong>. Observed at " + esc(metric_asof)
        + ". Data are provider-supplied historical values; no current-head timing or improvement inferred.</p>"
        + table(("Provider field", "Value", "Evidence class"), metric_rows)
        + "<h3>Two-pulse source delta</h3><p>Binding: <strong>" + esc(delta_status)
        + "</strong>. Source changes do not imply a passed CI gate.</p>"
        + table(("Workflow", "Change", "Safety attention", "Changed projection"), change_rows)
        + "<h3>Authority-binding changes</h3><p>Source binding: <strong>" + esc(delta_status)
        + "</strong>. Each AUTHORITY_REVIEW_REQUIRED row requires a reviewer disposition; "
        "historical or mismatched sources are not joined to the current index.</p>"
        + table(("Anchor ID", "Disposition", "Previous binding", "Current binding"), authority_rows)
        + "<h3>Worker stage matrix</h3><p>Binding: <strong>" + esc(wave_status)
        + "</strong>. This is a policy declaration, not an executed schedule.</p>"
        + table(("Task", "Stage", "Lane", "Execution"), task_rows)
        + "</section>"
    )
    out = existing.replace(marker, section + marker, 1)
    receipt = {
        "schema": OUTPUT_SCHEMA, "index_source_sha": sha,
        "w4_snapshot_source_sha": w4_receipt["source_sha"],
        "actions_metrics_observed_at": metric_asof,
        "actions_metric_binding": metric_status, "delta_binding": delta_status,
        "worker_binding": wave_status, "anchor_count": len(anchors),
        "authority_changes_count": len(authority_changes),
        "admission": "HOLD", "dispatch_authorized": False,
        "runtime_nonregression": "NOT_PROVEN",
        "review": "INDEPENDENT_ELIGIBLE_APPROVAL_REQUIRED",
        "publication": "NOT_AUTHORIZED",
    }
    return out, receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--control", type=Path, default=HERE / "control_view.json")
    parser.add_argument("--metrics", type=Path)
    parser.add_argument("--delta", type=Path)
    parser.add_argument("--wave", type=Path)
    parser.add_argument("--expected-head", default="")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    paths = {"index": args.index, "control": args.control,
             "metrics": args.metrics, "delta": args.delta, "wave": args.wave}
    raw = {k: p.read_bytes() for k, p in paths.items() if p is not None}
    docs = {k: json.loads(v) for k, v in raw.items()}
    page, receipt = render(docs["index"], docs["control"], docs.get("metrics"),
                           docs.get("delta"), docs.get("wave"), args.expected_head)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    data = page.encode("utf-8")
    args.out.write_bytes(data)
    manifest = {**receipt, "input_sha256": {k: hashlib.sha256(v).hexdigest() for k, v in sorted(raw.items())},
                "html_sha256": hashlib.sha256(data).hexdigest()}
    output = args.out.with_suffix(".manifest.json")
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8", newline="\n")
    print(json.dumps({"output": str(args.out), "receipt": str(output),
                      "index_source_sha": receipt["index_source_sha"],
                      "admission": "HOLD"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
