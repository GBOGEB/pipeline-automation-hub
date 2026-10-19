"""Offline, source-driven Method Atlas projection.

The renderer has no dispatch authority and performs no network requests.  Missing
measurements stay unknown; counts are only rolled up inside their source cohort.
"""

from __future__ import annotations

import html
import json
import math
import re
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit


ASSETS = Path(__file__).resolve().parent


def _obj(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _seq(value: Any) -> list:
    return value if isinstance(value, list) else []


def _text(value: Any, fallback: str = "UNKNOWN") -> str:
    if value is None or value == "":
        return fallback
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _e(value: Any, fallback: str = "UNKNOWN") -> str:
    return html.escape(_text(value, fallback), quote=True)


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) and value >= 0 else None


def _number(value: Any) -> str:
    number = _num(value)
    if number is None:
        return "UNKNOWN"
    return f"{number:,.0f}" if number.is_integer() else f"{number:,.2f}".rstrip("0").rstrip(".")


def _link(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    if any(ord(char) < 32 for char in value) or "\\" in value:
        return None
    parsed = urlsplit(value)
    if parsed.scheme:
        return value if parsed.scheme in {"https", "http"} and parsed.netloc else None
    return value if not value.startswith(("//", "/")) and ":" not in value.split("/")[0] else None


def _source_url(record: dict, source: dict) -> str | None:
    explicit = _link(record.get("source_url"))
    if explicit:
        return explicit
    repository = record.get("repo") or source.get("repository")
    head = record.get("head_sha") or source.get("head_sha")
    path = record.get("source_path")
    if isinstance(repository, str) and re.fullmatch(r"[\w.-]+/[\w.-]+", repository) and head and path:
        return f"https://github.com/{repository}/blob/{quote(str(head), safe='')}/{quote(str(path), safe='/')}"
    return None


def _source_ref(record: dict, source: dict) -> str:
    path = _e(record.get("source_path"))
    url = _source_url(record, source)
    if url:
        return f'<a class="source-path" href="{_e(url)}" target="_blank" rel="noreferrer">{path}<span aria-hidden="true"> ↗</span></a>'
    return f'<span class="source-path">{path}</span>'


def _details(data: dict, *, skip: set[str] | None = None) -> str:
    rows = []
    for key, value in data.items():
        if skip and key in skip:
            continue
        rows.append(f'<div><dt>{_e(str(key).replace("_", " "))}</dt><dd>{_e(value)}</dd></div>')
    return '<dl class="metadata">' + "".join(rows) + "</dl>" if rows else '<p class="empty">UNKNOWN · no source fields supplied.</p>'


def _badge(value: Any, category: str = "") -> str:
    label = _text(value)
    state = "unknown"
    upper = label.upper()
    if any(token in upper for token in ("UNKNOWN", "UNVERIFIED", "NOT_", "NOT ", "MISSING", "UNQUALIFIED")):
        state = "unknown"
    elif any(token in upper for token in ("FAIL", "BLOCK", "RED", "HOLD", "DEFER")):
        state = "blocked"
    elif any(token in upper for token in ("PASS", "DONE", "CLOSED", "VERIFIED", "SUCCEEDED")):
        state = "passed"
    elif any(token in upper for token in ("PROPOSED", "DESIGN", "DECLARED", "ROLE", "POLICY")):
        state = "declared"
    return f'<span class="badge {state} {_e(category, "")}">{_e(label)}</span>'


def _stats(model: dict) -> str:
    inventory = _obj(model.get("inventory"))
    cohorts = _seq(_obj(model.get("burndown")).get("cohorts"))
    metrics = [
        ("Functional blocks", len(_seq(model.get("blocks"))), "Source-declared roles and contracts"),
        ("Workflow files", inventory.get("workflow_count"), "Scanned repository scope"),
        ("Graph views", len(_seq(model.get("graphs"))), _number(inventory.get("diagram_count")) + " checked-in Mermaid sources · light/dark exports"),
        ("Burndown cohorts", len(cohorts), "Independent source populations"),
    ]
    return "".join(
        f'<article class="stat"><span>{_e(label)}</span><strong>{_number(value)}</strong><small>{_e(note)}</small></article>'
        for label, value, note in metrics
    )


def _programmes(taxonomy: dict, source: dict) -> str:
    cards = []
    for item in _seq(taxonomy.get("programmes")):
        item = _obj(item)
        aliases = ", ".join(str(alias) for alias in _seq(item.get("aliases"))) or "None supplied"
        refs = _seq(item.get("source_refs"))
        reference_list = "".join(
            f"<li>{_e(ref)}</li>" if not isinstance(ref, dict) else f"<li>{_source_ref(ref, source)}</li>"
            for ref in refs
        )
        cards.append(
            f'<article class="programme-card" data-programme="{_e(item.get("id"))}">'
            f'<div class="card-top"><span class="eyebrow">{_e(item.get("id"))}</span>'
            f'{_badge(item.get("definition_status") or item.get("status"))}</div>'
            f'<h3>{_e(item.get("label") or item.get("id"))}</h3>'
            f'<p>{_e(item.get("definition") or item.get("purpose"))}</p>'
            f'<dl class="compact-dl"><dt>Aliases</dt><dd>{_e(aliases)}</dd>'
            f'<dt>Authority</dt><dd>{_e(item.get("authority_boundary"))}</dd></dl>'
            + (f'<details><summary>Definition sources</summary><ul>{reference_list}</ul></details>' if refs else "")
            + "</article>"
        )
    if not cards:
        cards.append('<p class="empty">UNKNOWN · no programme taxonomy supplied.</p>')
    terms = _seq(taxonomy.get("terms")) or _seq(taxonomy.get("glossary")) or _seq(_obj(taxonomy.get("glossary")).get("terms"))
    glossary = "".join(
        f'<div class="term"><dt>{_e(_obj(term).get("term") or _obj(term).get("id"))}</dt>'
        f'<dd>{_e(_obj(term).get("definition"))}</dd></div>'
        for term in terms
    )
    return '<div class="programme-grid">' + "".join(cards) + "</div>" + (
        '<details class="glossary"><summary>Method glossary and naming rules</summary><dl>' + glossary + "</dl></details>"
        if glossary else ""
    )


def _cohort_trend(cohort: dict) -> str:
    series = _seq(cohort.get("series"))
    metric = str(cohort.get("series_metric") or "open")
    if not series:
        return '<p class="empty trend-empty">SPLINE · no recorded series. Next observation: UNKNOWN.</p>'
    values = []
    for point in series:
        point = _obj(point)
        value = point.get(metric)
        if value is None and point.get("metric") == metric:
            value = point.get("value")
        values.append(_num(value))
    known = [value for value in values if value is not None]
    if not known:
        return '<p class="empty trend-empty">SPLINE · all recorded values are UNKNOWN; no line is interpolated.</p>'
    width, height, left, bottom = 560, 148, 40, 115
    scale = max(max(known), 1)
    step = (width - left - 20) / max(len(series) - 1, 1)
    svg = [
        f'<svg class="trend" viewBox="0 0 {width} {height}" role="img" aria-label="{_e(metric)} observations for {_e(cohort.get("label"))}">',
        f'<path class="trend-axis" d="M {left} 16 V {bottom} H {width - 12}"/>',
        f'<text class="axis-label" x="8" y="22">{_e(_number(scale))}</text>',
        f'<text class="axis-label" x="20" y="{bottom + 3}">0</text>',
    ]
    previous = None
    for index, (point, value) in enumerate(zip(series, values)):
        point = _obj(point)
        x = left + index * step
        label = _text(point.get("label") or point.get("pulse") or point.get("observed_at") or f"N={index + 1}")
        if value is None:
            svg.append(f'<text class="unknown-marker" x="{x}" y="65" text-anchor="middle"><title>{_e(label)} · UNKNOWN</title>?</text>')
            previous = None
        else:
            y = bottom - value / scale * 94
            denominator = point.get("eligible", cohort.get("eligible"))
            if previous is not None and point.get("comparable") is True and previous[3] is True and denominator == previous[4]:
                svg.append(f'<path class="trend-line" d="M {previous[0]:.2f} {previous[1]:.2f} L {x:.2f} {y:.2f}"/>')
            svg.append(f'<circle class="trend-point" cx="{x:.2f}" cy="{y:.2f}" r="4"><title>{_e(label)} · {_e(metric)}: {_number(value)} · denominator: {_number(denominator)}</title></circle>')
            previous = (x, y, index, point.get("comparable"), denominator)
        if index in {0, len(series) - 1}:
            anchor = "start" if index == 0 else "end"
            svg.append(f'<text class="axis-label" x="{x:.2f}" y="138" text-anchor="{anchor}">{_e(label[:40])}</text>')
    svg.append("</svg>")
    return "".join(svg) + f'<p class="fine">Series metric: {_e(metric)} · points retain their original cohort; connections require explicit comparability.</p>'


def _burndown(model: dict) -> str:
    source = _obj(model.get("source"))
    cohorts = _seq(_obj(model.get("burndown")).get("cohorts"))
    cards = []
    for cohort in cohorts:
        cohort = _obj(cohort)
        eligible, done = _num(cohort.get("eligible")), _num(cohort.get("done"))
        unit = cohort.get("unit") or cohort.get("denominator_label") or "source units"
        percentage = "UNKNOWN"
        progress = '<div class="progress unknown-progress" aria-label="Completion unknown"></div>'
        if eligible is not None and done is not None and eligible > 0 and done <= eligible:
            percentage = f"{done / eligible * 100:.2f}%"
            progress = f'<progress max="{eligible:g}" value="{done:g}" aria-label="{_e(cohort.get("label"))} completed"></progress>'
        elif eligible == 0 and done == 0:
            percentage = "No eligible population"
        elif eligible is not None and done is not None and done > eligible:
            percentage = "INVALID · done exceeds eligible"
        fields = "".join(
            f'<div><dt>{_e(label)}</dt><dd>{_number(cohort.get(key))}</dd></div>'
            for label, key in (("Eligible", "eligible"), ("Done", "done"), ("Open", "open"), ("Blocked", "blocked"), ("Unknown", "unknown"))
        )
        rows = []
        for raw_item in _seq(cohort.get("items")):
            item = _obj(raw_item)
            rows.append(f'<tr><td>{_e(item.get("id"))}</td><td>{_e(item.get("label") or item.get("title") or item.get("path"))}</td><td>{_badge(item.get("status") or item.get("state"))}</td><td>{_e(item.get("evidence_class") or item.get("evidence"))}</td></tr>')
        cards.append(
            f'<article class="cohort-card" data-cohort="{_e(cohort.get("id"))}">'
            f'<div class="card-top"><span class="eyebrow">{_e(cohort.get("id"))}</span>{_badge(cohort.get("evidence_class"))}</div>'
            f'<h3>{_e(cohort.get("label") or cohort.get("id"))}</h3>'
            f'<div class="cohort-ratio"><strong>{_number(cohort.get("done"))}<span> / {_number(cohort.get("eligible"))}</span></strong><span>{_e(percentage)}</span></div>'
            f'<p class="fine">Completed / eligible · {_e(unit)}</p>{progress}'
            f'<dl class="cohort-counts">{fields}</dl>{_cohort_trend(cohort)}'
            f'<p class="fine">{_e(cohort.get("note") or cohort.get("notes"), "Open and blocked may overlap; source definitions retain their meaning.")}</p>'
            f'<div class="source-line">{_source_ref(cohort, source)}</div>'
            + ('<details><summary>Inspect cohort items (' + str(len(rows)) + ')</summary><div class="table-scroll"><table><thead><tr><th>ID</th><th>Item</th><th>Status</th><th>Evidence</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table></div></details>' if rows else '')
            + '</article>'
        )
    return '<div class="cohort-grid">' + "".join(cards) + '</div>' if cards else '<p class="empty">UNKNOWN · no source-bound burndown cohorts supplied.</p>'


def _broker(model: dict) -> str:
    broker = _obj(model.get("broker"))
    remote = _obj(broker.get("remote"))
    metrics = broker.get("metrics")
    if isinstance(metrics, dict):
        metrics = [dict(value, id=key) if isinstance(value, dict) else {"id": key, "value": value} for key, value in metrics.items()]
    if (not isinstance(metrics, list) or not metrics) and remote:
        metrics = [
            {"id": "queued", "label": "Remote queue length", "value": remote.get("queued"), "unit": "jobs waiting", "evidence_class": remote.get("status"), "window": remote.get("observed_at")},
            {"id": "running", "label": "Remote running jobs", "value": remote.get("running"), "unit": "occupied worker slots", "evidence_class": remote.get("status"), "window": remote.get("observed_at")},
            {"id": "worker_slots", "label": "Remote pool capacity", "value": remote.get("worker_slots"), "unit": "worker slots", "evidence_class": remote.get("status"), "window": remote.get("observed_at")},
            {"id": "available_slots", "label": "Remote available slots", "value": remote.get("available_slots"), "unit": "worker slots after reservations", "evidence_class": remote.get("status"), "window": remote.get("observed_at")},
        ]
    if not isinstance(metrics, list) or not metrics:
        metrics = [
            {"id": "queue_depth", "label": "Queue depth", "value": broker.get("queue_depth"), "unit": "jobs waiting"},
            {"id": "active_workers", "label": "Active workers", "value": broker.get("active_workers"), "unit": "workers"},
            {"id": "queue_age_p95", "label": "Queue age p95", "value": broker.get("queue_age_p95"), "unit": "seconds"},
            {"id": "execution_p95", "label": "Execution p95", "value": broker.get("execution_p95"), "unit": "seconds"},
        ]
    cards = []
    for metric in metrics:
        metric = _obj(metric)
        value = metric.get("value")
        value_text = _number(value) if value is None or isinstance(value, (int, float)) else _text(value)
        cards.append(
            f'<article class="broker-metric"><span>{_e(metric.get("label") or metric.get("id"))}</span><strong>{_e(value_text)}</strong>'
            f'<small>{_e(metric.get("unit"))}</small><small>Denominator / window: {_e(metric.get("denominator") or metric.get("window"))}</small>'
            f'<span class="fine">{_e(metric.get("evidence_class") or broker.get("evidence_class"))}</span></article>'
        )
    policy = _obj(broker.get("policy")) or _obj(broker.get("local_bounds"))
    decision = broker.get("decision") or remote
    decision_html = _details(decision) if isinstance(decision, dict) else f'<p>{_e(decision)}</p>'
    other = {key: value for key, value in broker.items() if key not in {"metrics", "policy", "decision", "source_path", "source_url", "remote", "local_bounds", "tasks", "local_receipt"}}
    if broker.get("tasks"):
        other["task_inventory"] = f'{len(_seq(broker.get("tasks")))} declared task adapters; inspect the source model for read/write leases and contracts.'
    local = _obj(broker.get("local_receipt"))
    local_html = ""
    if local:
        local_metrics = _obj(local.get("metrics"))
        local_rows = "".join(
            f'<tr><td>{_e(identity)}</td><td>{_badge(_obj(task).get("state"))}</td>'
            f'<td>{_number(_obj(task).get("execution_seconds"))}</td><td>{_number(_obj(task).get("verification_seconds"))}</td>'
            f'<td>{_number(_obj(task).get("ready_wait_seconds"))}</td><td>{_e(_obj(task).get("error"))}</td></tr>'
            for identity, task in _obj(local.get("tasks")).items()
        )
        local_html = (
            '<article class="subpanel local-proof"><div class="card-top"><h3>Measured local generator receipt</h3>'
            + _badge(local.get("evidence_class")) + '</div>'
            + _details({"outcome": local.get("outcome"), "started_at": local.get("started_at"), "bounds": local.get("bounds"), **local_metrics})
            + ('<details><summary>Local task outcomes</summary><div class="table-scroll"><table><thead><tr><th>Task</th><th>State</th><th>Execution seconds</th><th>Verification seconds</th><th>Ready-wait seconds</th><th>Error</th></tr></thead><tbody>' + local_rows + '</tbody></table></div></details>' if local_rows else '')
            + '<p class="fine">Measured execution within this local process. Remote worker-pool capacity retains the independent evidence shown above.</p></article>'
        )
    return (
        '<div class="broker-grid">' + "".join(cards) + '</div><div class="two-up">'
        '<article class="subpanel"><h3>Admission and pressure response</h3>' + decision_html + _details(other) + '</article>'
        '<article class="subpanel"><h3>Source-owned policy</h3>' + _details(policy) + '</article></div>'
        + local_html
        + f'<p class="source-line">{_source_ref(broker, _obj(model.get("source")))}</p>'
    )


def _percentage(value: Any) -> str:
    number = _num(value)
    return f"{number:.2f}%" if number is not None and number <= 100 else "UNKNOWN"


def _coverage_metric(value: Any) -> str:
    metric = _obj(value)
    classification = metric.get("classification")
    if classification == "NOT_APPLICABLE_BREADTH":
        return '<span class="fine">N/A · federation breadth</span>'
    if classification in {"BRANCHLESS_NOT_APPLICABLE", "NO_EXECUTABLE_ITEMS"}:
        return f'<span class="fine">{_e(classification)}</span>'
    return (
        f'<strong>{_percentage(metric.get("pct"))}</strong>'
        f'<span class="metric-ratio">{_number(metric.get("covered"))} / {_number(metric.get("eligible"))}</span>'
        f'<span class="fine">Remaining: {_number(metric.get("remaining"))}</span>'
    )


def _coverage(model: dict) -> str:
    coverage = _obj(model.get("coverage"))
    portfolio = _obj(coverage.get("portfolio"))
    rows = _seq(coverage.get("rows"))
    qualification = portfolio.get("qualification") or "NOT_QUALIFIED"
    summary = (
        '<div class="coverage-summary">'
        f'<article class="stat"><span>Portfolio statements</span><strong>{_percentage(portfolio.get("statement_pct"))}</strong><small>Verified common population required</small></article>'
        f'<article class="stat"><span>Portfolio branches</span><strong>{_percentage(portfolio.get("branch_pct"))}</strong><small>Verified common population required</small></article>'
        f'<article class="stat qualification-stat"><span>Portfolio qualification</span><strong>{_e(qualification.replace("_", " "))}</strong><small>{_e(portfolio.get("rule"), "No verified portfolio population supplied.")}</small></article></div>'
    )
    table_rows = []
    for index, value in enumerate(rows):
        row = _obj(value)
        modules = '<br>'.join(f'{label}: {_number(row.get(field))}' for label, field in (("Eligible", "eligible_modules"), ("Instrumented", "instrumented_modules"), ("Zero", "zero_covered_modules"), ("Unmeasured", "unmeasured_modules")))
        table_rows.append(
            f'<tr data-coverage="{index}" data-repository="{_e(row.get("repository"))}" data-kind="{_e(row.get("observation_kind"))}">'
            f'<td><strong>{_e(row.get("label") or row.get("id"))}</strong><span class="source-path">{_e(row.get("repository"))}</span><span class="fine">{_e(row.get("cohort_id"))}</span></td>'
            f'<td><span class="role-label">{_e(row.get("observation_kind"))}</span>{_badge(row.get("qualification"))}</td>'
            f'<td>{_coverage_metric(row.get("statements"))}</td><td>{_coverage_metric(row.get("branches"))}</td>'
            f'<td class="module-counts">{modules}</td><td>{_percentage(row.get("worst_file_coverage_pct"))}</td>'
            f'<td><button type="button" class="small-button inspect-coverage" data-index="{index}">Inspect cohort</button></td></tr>'
        )
    if not rows:
        table_rows.append('<tr><td colspan="7" class="empty">UNKNOWN · no source-bound coverage observations supplied.</td></tr>')
    gates = []
    for value in _seq(coverage.get("gates")):
        gate = _obj(value)
        gates.append(f'<tr><td>{_e(gate.get("row_id"))}</td><td>{_e(gate.get("stage"))}</td><td>{_badge(gate.get("status"))}</td><td>{_e(gate.get("reported_condition_met"))}</td></tr>')
    comparison_html = []
    for raw in _seq(coverage.get("comparisons")):
        comparison = _obj(raw)
        cells = []
        for unit in ("statements", "branches"):
            metric = _obj(comparison.get(unit))
            delta, delta_pp = metric.get("delta_covered"), metric.get("delta_pp")
            count = f"{delta:+d}" if type(delta) is int else "UNKNOWN"
            pp = f"{delta_pp:+.6f}" if type(delta_pp) in (int, float) and math.isfinite(delta_pp) else "UNKNOWN"
            cells.append(f'<tr><td>{unit.title()}</td><td>{_percentage(metric.get("before_pct"))}</td><td>{_percentage(metric.get("after_pct"))}</td><td>{_e(count)}</td><td>{_e(pp)} pp</td><td>{_number(metric.get("eligible"))}</td></tr>')
        comparison_html.append(
            '<article class="subpanel"><div class="card-top"><h3>Reported matched-history comparison</h3>' + _badge(comparison.get("qualification")) + '</div>'
            f'<p class="fine">Anchor {_e(comparison.get("from"))} → {_e(comparison.get("to"))}</p>'
            '<div class="table-scroll"><table><thead><tr><th>Metric</th><th>Before</th><th>After</th><th>Covered change</th><th>Percentage-point change</th><th>Denominator</th></tr></thead><tbody>' + "".join(cells) + '</tbody></table></div>'
            f'<p class="fine">Independently verified: {_e(comparison.get("independently_verified"))}. Qualified for a live series: {_e(comparison.get("comparable_for_live_series"))}.</p>'
            f'<p class="fine">{_e(comparison.get("rounding_note"), "Changes use original numerators and denominators.")}</p></article>'
        )
    return (
        summary
        + '<div class="coverage-table-wrap table-scroll"><table class="coverage-table"><thead><tr><th>Cohort / identity</th><th>Observation / qualification</th><th>Statements</th><th>Branches</th><th>Module population</th><th>Worst file</th><th><span class="sr-only">Action</span></th></tr></thead><tbody id="coverage-rows">' + "".join(table_rows) + '</tbody></table></div>'
        + '<aside class="inspector coverage-inspector" id="coverage-inspector" aria-live="polite"><h3>Coverage identity and denominator inspector</h3><p class="empty">Select a cohort for source population, module completeness, comparison anchor, tests, freshness and native receipt identity.</p></aside>'
        + '<div class="comparison-grid">' + "".join(comparison_html) + '</div>'
        + ('<details><summary>Noncompensating inventory, zero-coverage, behavioural and native gates</summary><p class="fine">Each required gate retains its own result. Aggregate coverage does not compensate for missing inventory or native evidence.</p><div class="table-scroll"><table><thead><tr><th>Cohort</th><th>Stage</th><th>Qualification</th><th>Reported condition met</th></tr></thead><tbody>' + "".join(gates) + '</tbody></table></div></details>' if gates else '')
        + f'<p class="fine">{_e(coverage.get("history_contract"), "Observation history is UNKNOWN.")}</p>'
        + '<p class="source-line">' + _source_ref(coverage, _obj(model.get("source"))) + '</p>'
    )


def _build(model: dict) -> str:
    build = _obj(model.get("build"))
    commands = _seq(build.get("commands"))
    content = []
    for index, command in enumerate(commands):
        command = _obj(command)
        content.append(
            f'<article class="command"><div><h3>{_e(command.get("label"))}</h3><button type="button" class="copy-command" data-command="command-{index}">Copy command</button></div>'
            f'<pre id="command-{index}"><code>{_e(command.get("command"))}</code></pre></article>'
        )
    if not commands:
        content.append('<p class="empty">UNKNOWN · a rebuild command has not been supplied by the source model.</p>')
    output_rows = "".join(
        f'<tr><td><code>{_e(_obj(item).get("path") or _obj(item).get("name"))}</code></td><td>{_e(_obj(item).get("purpose"))}</td></tr>'
        for item in _seq(build.get("outputs"))
    )
    if output_rows:
        content.append('<div class="table-scroll"><table><thead><tr><th>Generated output</th><th>Functional purpose</th></tr></thead><tbody>' + output_rows + '</tbody></table></div>')
    if build.get("source_path"):
        content.append('<p class="source-line">' + _source_ref(build, _obj(model.get("source"))) + '</p>')
    return "".join(content)


def render(model: dict, out: Path) -> list[str]:
    """Write deterministic HTML and local assets; return relative output paths."""
    if not isinstance(model, dict):
        raise TypeError("Atlas renderer requires a dictionary model")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    source = _obj(model.get("source"))
    title = model.get("title") or "Method Atlas · execution and evidence"
    taxonomy = _obj(model.get("taxonomy"))
    clean = dict(model)
    clean.setdefault("blocks", [])
    clean.setdefault("graphs", [])
    payload = json.dumps(clean, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    payload = payload.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    dirty = source.get("dirty")
    dirty_label = "WORKING TREE" if dirty is True else "COMMITTED SNAPSHOT" if dirty is False else "TREE STATE UNKNOWN"
    replacements = {
        "__TITLE__": _e(title),
        "__SOURCE_CLASS__": "Source inventory · runtime unknown" if source.get("evidence_class") == "LOCAL_SOURCE_INVENTORY_NOT_RUNTIME" else _e(source.get("evidence_class")),
        "__SOURCE_REPO__": _e(source.get("repository")),
        "__SOURCE_HEAD__": _e(source.get("head_sha")),
        "__OBSERVED_AT__": _e(source.get("observed_at") or source.get("observed_at_utc")),
        "__COMMIT_AT__": _e(source.get("commit_at")),
        "__DIRTY_LABEL__": _e(dirty_label),
        "__STATS__": _stats(clean),
        "__PROGRAMMES__": _programmes(taxonomy, source),
        "__BURNDOWN__": _burndown(clean),
        "__BROKER__": _broker(clean),
        "__COVERAGE__": _coverage(clean),
        "__BUILD__": _build(clean),
        "__SOURCE_DETAILS__": _details(source),
        "__INVENTORY_DETAILS__": _details(_obj(model.get("inventory")), skip={"python_modules", "workflows", "diagrams"}),
        "__IO_DETAILS__": _details(_obj(model.get("io_rules"))),
        "__MODEL_JSON__": payload,
    }
    template = (ASSETS / "template.html").read_text(encoding="utf-8")
    rendered = re.sub(r"__[A-Z_]+__", lambda match: replacements.get(match.group(), match.group()), template)
    (out / "index.html").write_text(rendered, encoding="utf-8")
    for asset in ("style.css", "app.js"):
        target = out / asset
        if target.resolve() != (ASSETS / asset).resolve():
            shutil.copyfile(ASSETS / asset, target)
    return ["index.html", "style.css", "app.js"]
