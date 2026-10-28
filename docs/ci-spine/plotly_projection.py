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
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "RUN_TIMING_SAMPLES_20261028.json"
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
        if not isinstance(q, (int, float)) or q < 0 or t < 0:
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


def render():
    try:
        from plotly import graph_objects as go
        from plotly.io import to_html
    except ImportError as exc:
        raise RuntimeError("Install the existing Plotly rendering dependency (plotly==6.5.2)") from exc

    data = sorted(rows(), key=lambda x: -x["execution_seconds"])
    labels = [x["name"][:64]+" #"+str(x["run_id"]) for x in data]
    custom = [[x["run_id"], x["attempt"], x["source_sha"], x["job"]] for x in data]
    fig = go.Figure()
    fig.add_bar(name="Runner queue (s)", x=[x["queue_seconds"] for x in data], y=labels,
                orientation="h", marker_color="#d7a75f", customdata=custom,
                hovertemplate="%{y}<br>Queue %{x}s<br>Run #%{customdata[0]} attempt %{customdata[1]}<extra></extra>")
    fig.add_bar(name="Representative job execution (s)", x=[x["execution_seconds"] for x in data],
                y=labels, orientation="h", marker_color="#70c6ad", customdata=custom,
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
             'execution are distinct. Navigate the <a href="explorer.html">offline DAG/SIPOC'
             ' explorer</a> for source and DoD/DoV. Snapshot: <code>'+HEAD+
             '</code>. No API calls.</p><details><summary>Open source run attempts</summary>'
             '<ul>'+links+'</ul></details></section>')
    if rendered.count("<body>") != 1:
        raise ValueError("PLOTLY_INVALID_TEMPLATE")
    rendered = rendered.replace("<body>", "<body>"+intro, 1)
    if "https://cdn.plot.ly" in rendered:
        raise ValueError("PLOTLY_EXTERNAL_SCRIPT_FIRST_RED")
    return rendered.encode("utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    out = render()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(out)
    if b"ci-spine-sampled-jobs" not in out or b"FROZEN" not in out:
        raise ValueError("PLOTLY_OUTPUT_INVALID")
    print(json.dumps({"bytes":len(out),"sha256":hashlib.sha256(out).hexdigest(),
                      "sample_count":8,"plotly_source":"OFFLINE_EMBEDDED",
                      "merge_authorized":False}, sort_keys=True))


if __name__ == "__main__":
    main()
