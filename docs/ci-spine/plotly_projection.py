#!/usr/bin/env python3
"""Optional OFFLINE Plotly companion for the eight frozen GitHub-run timing samples.

Presentation only; no new telemetry, test results or admission metrics.
Follows existing federation-atlas/mission_rebuild/w2_plotly.py offline pattern.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import os
import re
import shutil
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "RUN_TIMING_SAMPLES_20261028.json"
EXPLORER = HERE / "explorer.html"
HEAD = "ca623ab83793df6edd245942884ad5428a5fe079"


def rows():
    d = json.loads(DATA.read_text("utf-8"))
    if d.get("schema") != "gbo.ci-spine.run-timing-sample.v1" or d.get("sample_count") != 8:
        raise ValueError("PLOTLY_SAMPLE_SOURCE_FIRST_RED")
    observed = []
    for run in d["runs"]:
        candidates = [j for j in run["jobs"] if isinstance(j.get("execution_seconds"), (int, float))]
        if not candidates:
            raise ValueError("PLOTLY_MISSING_MEASURED_JOB_FIRST_RED")
        job = max(candidates, key=lambda x: x["execution_seconds"])
        q, t = job.get("queue_seconds"), job["execution_seconds"]
        # A null queue is UNKNOWN (as in the explorer): kept as None, so Plotly omits that segment.
        if (q is not None and (not isinstance(q, (int, float)) or q < 0)) or t < 0:
            raise ValueError("PLOTLY_NEGATIVE_OR_MISSING_CLOCK_FIRST_RED")
        observed.append({
            "run_id": run["run_id"],
            "attempt": run["attempt"],
            "name": run["name"],
            "job": job["name"],
            "queue_seconds": q,
            "execution_seconds": t,
            "source_sha": run["source_sha"],
        })
    if len({x["run_id"] for x in observed}) != 8:
        raise ValueError("PLOTLY_SAMPLE_POPULATION_FIRST_RED")
    return observed



RUN_ID = re.compile(r"^[1-9][0-9]*$")
SHA40 = re.compile(r"^[0-9a-f]{40}$")
# Local read-only navigation. The chart is presentation, never a source of authority.
LOCAL_EXPLORER = re.compile(r"^(?:[.][.]/)*(?:[A-Za-z0-9_-]+/)*explorer[.]html$")


def point_bindings(samples, explorer: str) -> list[dict]:
    """Project stable, source-verified UI point identities, not new metrics.

    The identities travel with both Plotly bar traces, so reordering traces or
    regenerating labels cannot change which run/attempt a click selects.
    """
    if not isinstance(explorer, str) or not LOCAL_EXPLORER.fullmatch(explorer):
        raise ValueError("PLOTLY_UNTRUSTED_EXPLORER_ROUTE_FIRST_RED")
    out, seen = [], set()
    for row in samples:
        rid, attempt, sha = row.get("run_id"), row.get("attempt"), row.get("source_sha")
        if (type(rid) is not int or type(attempt) is not int or
                not RUN_ID.fullmatch(str(rid)) or not RUN_ID.fullmatch(str(attempt)) or
                not isinstance(sha, str) or SHA40.fullmatch(sha) is None or
                not isinstance(row.get("job"), str) or not row["job"]):
            raise ValueError("PLOTLY_INVALID_RUN_SOURCE_FIRST_RED")
        point = f"run:{rid}:attempt:{attempt}"
        if point in seen:
            raise ValueError("PLOTLY_DUPLICATE_POINT_FIRST_RED")
        seen.add(point)
        out.append({
            "point_id": point,
            "run_id": rid,
            "attempt": attempt,
            "source_sha": sha,
            "job": row["job"],
            "explorer_href": f"{explorer}#lens=timing&kind=run&id={rid}",
            "github_href": (f"https://github.com/GBOGEB/pipeline-automation-hub/"
                            f"actions/runs/{rid}/attempts/{attempt}"),
            "precision": "PLOTLY_POINT_SELECTION",
        })
    if len(out) != 8:
        raise ValueError("PLOTLY_POINT_POPULATION_FIRST_RED")
    return out


def point_inspector(bindings: list[dict]) -> str:
    """Read-only source inspector; no arbitrary URLs or HTML from click payload.

    Plotly pointNumber is checked against a stable trace id and customdata,
    and source links come from a server-authored allowlist rather than labels.
    """
    catalog = json.dumps({b["point_id"]: b for b in bindings}, sort_keys=True, separators=(",", ":"))
    catalog = catalog.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    panel = (
        '<section id="ci-spine-point-inspector" aria-label="Source-bound point selection" '
        'style="font:13px system-ui;padding:16px 25px;background:#271d34;'
        'color:#efe7fb;max-width:1100px;margin:0 auto;border-top:1px solid #7c5f98">'
        '<b>JQ-08 · POINT → SOURCE (ADVISORY)</b>'
        '<p id="ci-spine-selection" role="status" aria-live="polite">'
        'Click a queue or execution bar to inspect its exact historical run.</p>'
        '<p><a id="ci-spine-explorer-link" hidden>View selected run in DAG / SIPOC explorer</a>'
        ' · <a id="ci-spine-github-link" hidden target="_blank" rel="noopener noreferrer">'
        'Open exact GitHub run attempt</a></p>'
        '<small>Selection precision: Plotly point identity. PDF page, bbox and OCG remain UNMAPPED. '
        'This view cannot approve or execute a workflow.</small></section>'
    )
    script = r'''<script>
(function() {
  "use strict";
  const points = Object.freeze(__POINT_CATALOG__);
  const selection = document.getElementById("ci-spine-selection");
  const explorer = document.getElementById("ci-spine-explorer-link");
  const github = document.getElementById("ci-spine-github-link");
  function unmapped() {
    selection.textContent = "UNMAPPED: point identity or source receipt mismatch";
    explorer.hidden = true; github.hidden = true;
    explorer.removeAttribute("href"); github.removeAttribute("href");
  }
  function selectPoint(event) {
    const p = event && event.points && event.points[0];
    const d = p && p.customdata;
    if (!Array.isArray(d) || d.length !== 5 || typeof d[4] !== "string") {
      unmapped(); return;
    }
    const id = d[4], b = Object.hasOwn(points, id) ? points[id] : null;
    const traceId = p.data && Array.isArray(p.data.ids) ? p.data.ids[p.pointNumber] : null;
    if (!b || traceId !== id || String(d[0]) !== String(b.run_id) ||
        String(d[1]) !== String(b.attempt) || d[2] !== b.source_sha ||
        d[3] !== b.job) { unmapped(); return; }
    selection.textContent = "SOURCE_BOUND selection: run " + b.run_id +
      " / attempt " + b.attempt + " / head " + b.source_sha.slice(0, 12) +
      " / job " + b.job + " (historical, not current admission)";
    explorer.href = b.explorer_href;
    github.href = b.github_href;
    explorer.hidden = false; github.hidden = false;
  }
  window.addEventListener("load", function() {
    const gd = document.getElementById("ci-spine-sampled-jobs");
    if (!gd || typeof gd.on !== "function") { unmapped(); return; }
    gd.on("plotly_click", selectPoint);
  });
})();
</script>'''
    return panel + script.replace("__POINT_CATALOG__", catalog)


def point_receipt(rendered: bytes, bindings: list[dict]) -> dict:
    """Sidecar binds actual HTML bytes to the frozen input; never self-attests."""
    return {
        "schema": "gbo.ci-spine.plotly-point-receipt.v1",
        "record_type": "offline_source_to_chart_navigation_only",
        "source": {
            "path": "docs/ci-spine/RUN_TIMING_SAMPLES_20261028.json",
            "sha256": hashlib.sha256(DATA.read_bytes()).hexdigest(),
            "snapshot_commit": HEAD,
        },
        "chart": {"sha256": hashlib.sha256(rendered).hexdigest(), "bytes": len(rendered)},
        "points": bindings,
        "count": len(bindings),
        "precision": "PLOTLY_POINT_SELECTION",
        "pdf_mapping": "UNMAPPED_NO_VERIFIED_BINARY",
        "authority_transfer": False,
        "merge_authorized": False,
    }

class _AssetParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.has_script_dependency = False

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "script" and dict(attrs).get("src"):
            self.has_script_dependency = True


def external_scripts(document: str) -> bool:
    """Only parsed script src= tags are dependencies, not embedded JS strings."""
    parser = _AssetParser()
    parser.feed(document)
    return parser.has_script_dependency


def explorer_href(out: Path) -> str:
    """Link to the explorer from where the chart is written, never an assumed sibling."""
    try:
        rel = os.path.relpath(EXPLORER.resolve(), out.resolve().parent)
    except ValueError as exc:  # different Windows drive: no relative path exists
        raise ValueError("PLOTLY_EXPLORER_UNREACHABLE_FIRST_RED: use --bundle-explorer") from exc
    return Path(rel).as_posix()


def render(explorer="explorer.html"):
    try:
        from plotly import graph_objects as go
        from plotly.io import to_html
    except ImportError as exc:
        raise RuntimeError("Install the existing Plotly rendering dependency (plotly==6.5.2)") from exc

    data = sorted(rows(), key=lambda x: -x["execution_seconds"])
    bindings = point_bindings(data, explorer)
    uids = [b["point_id"] for b in bindings]
    labels = [x["name"][:64]+" #"+str(x["run_id"]) for x in data]
    custom = [[x["run_id"], x["attempt"], x["source_sha"], x["job"]] for x in data]
    fig = go.Figure()
    fig.add_bar(name="Runner queue (s)", x=[x["queue_seconds"] for x in data], y=labels,
                orientation="h", marker_color="#d7a75f", customdata=custom, ids=uids,
                hovertemplate="%{y}<br>Queue %{x}s<br>Run #%{customdata[0]} attempt %{customdata[1]}<extra></extra>")
    fig.add_bar(name="Representative job execution (s)", x=[x["execution_seconds"] for x in data],
                y=labels, orientation="h", marker_color="#70c6ad", customdata=custom, ids=uids,
                hovertemplate="%{y}<br>Execution %{x}s<br>Run #%{customdata[0]}<extra></extra>")
    fig.update_layout(
        barmode="stack", template="plotly_dark", height=610,
        margin=dict(l=310,r=55,t=95,b=65),
        title="CI Spine · sampled GitHub Actions run clocks (advisory)",
        xaxis_title="Measured seconds (not billable minutes or fleet performance)",
        legend=dict(orientation="h",y=1.12,x=0),
        paper_bgcolor="#081719",plot_bgcolor="#0e2528",
        font=dict(color="#e8f5f1"),
    )
    fig.update_yaxes(autorange="reversed")
    rendered = to_html(fig, include_plotlyjs=True, full_html=True,
                       div_id="ci-spine-sampled-jobs", config={"responsive": True,
                       "displaylogo": False,"scrollZoom": True})
    links = "".join(
        '<li><a target="_blank" rel="noopener noreferrer" href="https://github.com/'
        'GBOGEB/pipeline-automation-hub/actions/runs/'+str(x["run_id"])+
        '/attempts/'+str(x["attempt"])+'">'+html.escape(x["name"])+
        ' (run '+str(x["run_id"])+')</a></li>'
        for x in data
    )
    intro = ('<section style="font:13px system-ui;padding:20px 25px;background:#10292c;'
             'color:#dbeae6;max-width:1100px;margin:auto"><b>FROZEN / READ-ONLY / NO '
             'ADMISSION AUTHORITY</b><p>Eight selected runs on 2026-10-28, not a representative '
             'fleet time series. Representative longest completed job per run; queue and '
             'execution are distinct. Navigate the <a href="'+html.escape(explorer, quote=True)+
             '">offline DAG/SIPOC explorer</a> for source and DoD/DoV. Snapshot: <code>'+HEAD+
             '</code>. No API calls.</p><details><summary>Open source run attempts</summary>'
             '<ul>'+links+'</ul></details></section>')
    if rendered.count("<body>") != 1:
        raise ValueError("PLOTLY_INVALID_TEMPLATE")
    rendered = rendered.replace("<body>", "<body>"+intro+point_inspector(bindings), 1)
    # The fully embedded Plotly.js source contains CDN strings as inert code/text.
    # Only an actual network script dependency is disallowed; substring scanning
    # of the vendored JS creates an incorrect first-red.
    if external_scripts(rendered):
        raise ValueError("PLOTLY_EXTERNAL_SCRIPT_FIRST_RED")
    return rendered.encode("utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--bundle-explorer", action="store_true",
                        help="copy explorer.html beside the chart (for a standalone artifact)")
    parser.add_argument("--receipt", type=Path, help="sidecar JSON path (default: chart stem .receipt.json)")
    args = parser.parse_args(argv)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.bundle_explorer:
        if args.out.resolve().parent != HERE.resolve():
            shutil.copyfile(EXPLORER, args.out.parent / EXPLORER.name)
        href = EXPLORER.name
    else:
        href = explorer_href(args.out)
    out = render(href)
    args.out.write_bytes(out)
    receipt = point_receipt(out, point_bindings(
        sorted(rows(), key=lambda x: -x["execution_seconds"]), href))
    receipt_path = args.receipt or args.out.with_suffix(".receipt.json")
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n",
                            encoding="utf-8", newline="\n")
    if b"ci-spine-sampled-jobs" not in out or b"FROZEN" not in out:
        raise ValueError("PLOTLY_OUTPUT_INVALID")
    print(json.dumps({"bytes":len(out),"sha256":hashlib.sha256(out).hexdigest(),
                      "sample_count":8,"plotly_source":"OFFLINE_EMBEDDED",
                      "point_count":receipt["count"], "receipt":str(receipt_path),
                      "merge_authorized":False}, sort_keys=True))


if __name__ == "__main__":
    main()
