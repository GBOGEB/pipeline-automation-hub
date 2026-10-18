#!/usr/bin/env python3
"""Offline Plotly presentation of the gg_MATH/MissionControl native observation.

Plots API-observed counts only; the scientific gg_MATH convergence model remains
in GBOGEB/gg_MATH/kernels/convergence_control.py, NOT duplicated here.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
from pathlib import Path

try:
    from plotly import graph_objects as go
    from plotly.io import to_html
    from plotly.offline import get_plotlyjs
except ImportError as exc:
    raise SystemExit("plotly==6.5.2 is required for this offline renderer") from exc

SCHEMA = "missioncontrol.makeover.w2_native_observation.v1"


def require(ok, why):
    if not ok:
        raise ValueError("MC_W2_PLOT_FAIL_CLOSED:" + why)


def h(value):
    return html.escape(str(value), quote=True)


def validate(d):
    require(d.get("schema") == SCHEMA, "typed observation")
    require(d.get("evidence_class") in
            ("GITHUB_API_METADATA_READ_ONLY", "SYNTHETIC_TEST_FIXTURE_NOT_NATIVE"),
            "source classification")
    require(d.get("governance", {}).get("merge_admission") == "HOLD"
            and d["governance"]["authority_transfer"] is False
            and d["governance"]["security_waiver"] is False,
            "governance custody")
    require(d.get("gg_math", {}).get("native_live_pulse_receipts_ingested") == 0,
            "unproven live mathematical series")
    require(d["gg_math"].get("provider_plotly_artifact_bytes_verified_by_this_consumer") is False,
            "independent artifact promotion")
    require(d["w1"]["source_head_sha"] ==
            "28b6b0dd6910cf730456fcdbf0c95b157626773b",
            "W1 original source")
    require(d["w1"]["attempt_2"] in
            ("NOT_PRESENT", "ATTEMPT_EXISTS_NEEDS_JOB_CHECK", "UNKNOWN"),
            "W1 attempt identity")
    require(d["unknown_burndown"]["coverage"]["covered_statements"] is None
            and d["unknown_burndown"]["coverage"]["total_statements"] is None
            and d["fleet"]["capacity_slots"] is None
            and d["fleet"]["actual_worker_hours"] is None,
            "unknown counts may not be imputed")
    for metric in ("queued_run_count", "in_progress_run_count"):
        v = d["fleet"][metric]
        require(v is None or (type(v) is int and v >= 0), "invalid queue census")
    for run in d["gg_math"]["provider"]:
        if run["run"] is not None:
            require(run["run"]["conclusion"] in
                    (None, "success", "failure", "cancelled", "timed_out", "skipped", "neutral"),
                    "provider native conclusion")
    return d


def layout(fig, height=180):
    fig.update_layout(
        height=height, margin={"t": 15, "b": 39, "l": 40, "r": 12},
        autosize=True, showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Arial,sans-serif", "size": 11, "color": "#c4d9e5"},
        xaxis={"showgrid": False, "fixedrange": True, "linecolor": "#66899e"},
        yaxis={"gridcolor": "#365268", "fixedrange": True, "rangemode": "tozero",
               "zeroline": False, "tickformat": ",d"})
    return fig


def queue_plot(d):
    vals = [d["fleet"]["queued_run_count"], d["fleet"]["in_progress_run_count"]]
    fig = go.Figure()
    if any(v is None for v in vals):
        fig.add_annotation(x=0.5, y=0.5, xref="paper", yref="paper",
                           text="Native queue API unavailable · UNKNOWN", showarrow=False)
    else:
        fig.add_trace(go.Bar(x=["Queued", "In progress"], y=vals,
                             marker_color=["#d2a45c", "#6fb3d0"],
                             text=[str(v) for v in vals], textposition="outside",
                             hovertemplate="%{x} %{y:,} native runs<extra></extra>"))
        fig.update_yaxes(range=[0, max(1, max(vals))*1.18])
    return layout(fig)


def job_plot(d):
    names, green, waiting = [], [], []
    samples = [("W1 #669", d["w1"]["jobs"])]
    for item, label in zip(d["gg_math"]["provider"], ("gg_MATH #61", "gg_MATH #63")):
        samples.append((label, item["jobs"]))
    for name, job in samples:
        if not job or not job["complete"]:
            continue
        names.append(name)
        green.append(job["passing"])
        waiting.append(job["queued"])
    fig = go.Figure()
    if not names:
        fig.add_annotation(x=0.5, y=0.5, xref="paper", yref="paper",
                           text="No complete native job census", showarrow=False)
    else:
        fig.add_trace(go.Bar(x=names, y=green, name="Successful jobs",
                             marker_color="#5db9a2", hovertemplate="%{x}: %{y} success jobs<extra></extra>"))
        fig.add_trace(go.Bar(x=names, y=waiting, name="Queued jobs",
                             marker_color="#d4a96c", hovertemplate="%{x}: %{y} queued jobs<extra></extra>"))
        fig.update_layout(barmode="stack", showlegend=True,
                          legend={"orientation":"h","y":1.32,"x":0})
    return layout(fig, 206)


def unknowns_plot(d):
    v=d["unknown_burndown"]
    labels=["Coverage", "Worker capacity", "Reviews", "M1 / M2 / M3"]
    statuses=[
        v["coverage"]["status"],
        v["worker"]["status"],
        v["reviews"]["status"],
        "STRUCTURAL / HOLD / HOLD"
    ]
    fig=go.Figure(data=[go.Table(
        header={"values":["Metric", "Evidence classification"],
                "fill_color":"#294a61","font":{"color":"#eaf5fa","size":12},
                "align":"left","height":29},
        cells={"values":[labels,statuses],"fill_color":"#193247",
               "font":{"color":"#d0e0eb","size":11},"align":"left",
               "height":28})])
    fig.update_layout(height=220,margin={"t":0,"b":0,"l":0,"r":0},
                      paper_bgcolor="rgba(0,0,0,0)")
    return fig


def method_plot(d):
    classifications = [
        ("gg_MATH provider native", "SOURCE_RUN_COMPLETE" if all(
            x["run"] is not None and x["run"]["conclusion"] == "success"
            for x in d["gg_math"]["provider"]) else "UNKNOWN"),
        ("Provider to MissionControl", d["gg_math"]["stale_bridge_classification"]),
        ("PCA model stability", "NOT_ASSESSABLE"),
        ("BT ranking stability", "NOT_ASSESSABLE"),
        ("Six Sigma capability", "NOT_ATTESTED"),
    ]
    fig=go.Figure(data=[go.Table(
        header={"values":["Evidence layer","State"],"fill_color":"#294a61",
                "font":{"color":"#eaf5fa","size":12},"align":"left","height":27},
        cells={"values":[[x[0] for x in classifications],
                         [x[1] for x in classifications]],"fill_color":"#193247",
               "font":{"color":"#d0e0eb","size":11},"align":"left","height":28})])
    fig.update_layout(height=245,margin={"t":0,"b":0,"l":0,"r":0},
                      paper_bgcolor="rgba(0,0,0,0)")
    return fig


def render(d):
    validate(d)
    charts=[
        ("queue","Queue pressure","Measured native run count · one non-atomic census",queue_plot(d),"runtime"),
        ("jobs","Execution receipt fan-in","Comparable job outcomes, NOT coverage or branch approval",job_plot(d),"runtime"),
        ("unknown","Four-row W2 burndown","UNKNOWN is not numerical zero and cannot score as a success",unknowns_plot(d),"governance"),
        ("math","gg_MATH convergence readiness","Canonical provider module; no duplicate statistical kernel",method_plot(d),"statistics"),
    ]
    specs, cards = {}, []
    for ident,title,detail,figure,group in charts:
        specs[ident]=figure.to_plotly_json()
        fragment=to_html(figure,full_html=False,include_plotlyjs=False,
                         div_id="plot-"+ident,config={"responsive":True,"displayModeBar":False})
        cards.append('<article class="card" data-group="'+group+'"><div class="card-head"><h2>'+
                     h(title)+'</h2><button type="button" data-expand="'+ident+'">Expand ↗</button></div><p>'+
                     h(detail)+'</p><div class="inlay">'+fragment+'</div></article>')
    w=d["w1"]; attempt=w["run"]["attempt"] if w["run"] else "UNKNOWN"
    qp=d["fleet"]["queued_run_count"];running=d["fleet"]["in_progress_run_count"]
    source_ref="https://github.com/GBOGEB/pipeline-automation-hub/blob/"+d["source_head_sha"]+"/mission-control/federation-atlas/mission_rebuild"
    gg_ref="https://github.com/GBOGEB/gg_MATH/actions/runs/39047980808"
    payload=json.dumps(specs,ensure_ascii=False).replace("<","\\u003c").replace("&","\\u0026")
    page=r'''<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer"><title>MISSION CONTROL W2 · gg_MATH evidence</title>
<style>
:root{color-scheme:dark;font-family:system-ui,sans-serif;color:#e8f3fa;background:#0b1725}
*{box-sizing:border-box}body{margin:0}header{background:#123047;padding:24px clamp(18px,3vw,45px);border-bottom:1px solid #385b70}
h1{font-size:clamp(25px,3.4vw,39px);margin:9px 0}h2{font-size:18px;margin:0}p{color:#adc7d9;line-height:1.5}main{max-width:1550px;margin:auto;padding:20px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,390px),1fr));gap:12px}
.card{background:#172c3d;border:1px solid #36566a;border-radius:14px;padding:14px;min-width:0}
.card-head{display:flex;gap:10px;align-items:center;justify-content:space-between;flex-wrap:wrap}
.inlay{height:245px;max-width:100%;overflow:hidden}.inlay .plotly-graph-div{max-width:100%}
.card p{font-size:13px;min-height:30px}button{background:#26516a;color:#e6f8fb;border:1px solid #6592a5;border-radius:9px;padding:8px 11px;cursor:pointer}
button:hover,button:focus-visible{outline:2px solid #b6eeff}.filters{display:flex;gap:8px;flex-wrap:wrap;margin:18px 0}
.notice{border:1px solid #b3976d;background:#322c22;padding:12px;border-radius:9px;color:#f1dfc3}
.meta{color:#afcbdc;font-size:12px;overflow-wrap:anywhere}
footer{margin:24px 0;color:#aec9db;font-size:13px}
dialog{width:min(95vw,1100px);max-height:92vh;border:1px solid #6b91a7;border-radius:15px;background:#10253a;color:#e7f4fa;padding:17px}
dialog::backdrop{background:#020810cd}.modal-head{display:flex;justify-content:space-between;align-items:center;gap:8px}
#expanded{width:100%;min-height:425px}a{color:#b2eaf7}
[hidden]{display:none!important}
@media(max-width:430px){.card{padding:11px}.inlay{height:235px}.card-head h2{font-size:16px}}
</style></head><body><script>__PLOTLY_LIBRARY__</script><header><div class="meta">CODE PURPLE / MISSION CONTROL W2 / MIP · gg_MATH provider</div>
<h1>Federation evidence and convergence</h1><p>Native run census · queue pressure · blocked-vs-stable classification · Plotly inlay diagnostics</p>
<div class="notice">Read-only API observation; not an atomic snapshot or Six Sigma certificate. Provider's built-in Plotly demonstrations are SYNTHETIC, not actual federation coverage. W1 historical merge does not imply admission.</div></header><main>
<p class="meta">Consumer checkout <code>__SHA__</code> · observation __OBS__ · W1 run attempt __ATTEMPT__ · queued __QUEUED__ / active __ACTIVE__</p>
<div class="filters"><button data-filter="all" aria-pressed="true">All</button><button data-filter="runtime" aria-pressed="false">Runner & queue</button><button data-filter="governance" aria-pressed="false">Unknowns & DoV</button><button data-filter="statistics" aria-pressed="false">DMAIC / PCA / BT</button></div>
<section class="cards">__CARDS__</section>
<section class="card" style="margin-top:13px"><h2>DMAIC → MIP → gg_MATH handoff</h2>
<p><strong>Define:</strong> CTQ is source-bound terminal first-red resolution and valid evidence, not prettier cards.
<strong>Measure:</strong> compare exact-SHA run/job/attempt and scoped numerator/denominator; quote queue counts by observation time.
<strong>Analyze:</strong> separate missing capacity, queued jobs and stale bridge from a statistically stable process.
<strong>Improve:</strong> source-owner repair, artifact identity/bytes, and reviewer eligibility.
<strong>Control:</strong> 8+ independent matched pulses for a proposed equivalence check are a study design, not a guarantee; hold admission until native results.</p>
<p><strong>MIP:</strong> Modernize the stale consumer bridge; Innovate through typed job/artifact joins and human-readable plots; Perpetuate only after authenticated reproducible receipts and DoV.</p>
<p><strong>PCA:</strong> same features and preprocessing, adequate independent n (gg_MATH uses n≥max(20,5p)), bootstrap congruence/eigengap checks; none established here.
<strong>BT:</strong> connected, matched, independent pairwise trial graph and uncertainty intervals; no authenticated comparison population here.
<strong>Six Sigma:</strong> CTQ opportunity/independence needed; conventional 3.4 DPMO cannot be inferred from a zero-failure small test set.</p>
<p><a href="__GG_REF__">Canonical gg_MATH native Plotly artifact run ↗</a> · <a href="evidence.json">Typed readback JSON</a> · <a href="evidence-manifest.json">Hash manifest</a> · <a href="__SOURCE_REF__">Mission Control source checkout ↗</a></p>
</section>
<dialog id="detail"><div class="modal-head"><h2 id="modalTitle">Expanded evidence</h2><button id="closeDialog">Close</button></div><div id="expanded"></div></dialog>
<footer>Current queue snapshot is a single observation and has no valid trend slope, p95 wait-time or worker capacity inference. UNKNOWN ≠ zero; provider PASS ≠ federation acceptance; merged ≠ DoV.</footer>
</main>
<script id="plot-specs" type="application/json">__SPECS__</script>
<script>(function(){"use strict";
// Inline card fragments call Plotly.newPlot while parsing, so the library is loaded at
// the top of <body>. Resize once every grid card is mounted (same fix as N3 dabefbc).
window.addEventListener("load",function(){document.querySelectorAll(".inlay .js-plotly-plot").forEach(function(el){Plotly.Plots.resize(el)})});
var specs=JSON.parse(document.getElementById("plot-specs").textContent);
document.querySelectorAll("[data-filter]").forEach(function(b){b.addEventListener("click",function(){
 var v=b.dataset.filter;document.querySelectorAll("[data-filter]").forEach(function(x){x.setAttribute("aria-pressed",String(x===b))});
 document.querySelectorAll(".card[data-group]").forEach(function(c){c.hidden=(v!=="all"&&c.dataset.group!==v)});
 window.dispatchEvent(new Event("resize"));})});
var dlg=document.getElementById("detail");
document.querySelectorAll("[data-expand]").forEach(function(b){b.addEventListener("click",function(){
 var key=b.dataset.expand,s=specs[key];if(!s)return;
 document.getElementById("modalTitle").textContent="Source-bound "+key+" evidence";
 dlg.showModal();Plotly.newPlot("expanded",s.data,Object.assign({},s.layout,{autosize:true,height:450}),{responsive:true,displayModeBar:true});})});
document.getElementById("closeDialog").addEventListener("click",function(){dlg.close()});
dlg.addEventListener("close",function(){Plotly.purge("expanded")});
})();</script></body></html>'''
    subs={"__SHA__":h(d["source_head_sha"]),"__OBS__":h(d["observed_at_utc"]),
          "__ATTEMPT__":h(attempt),"__QUEUED__":h(qp if qp is not None else "UNKNOWN"),
          "__ACTIVE__":h(running if running is not None else "UNKNOWN"),
          "__CARDS__":"\n".join(cards),"__GG_REF__":h(gg_ref),
          "__SOURCE_REF__":h(source_ref),"__PLOTLY_LIBRARY__":get_plotlyjs().replace("</script","<\\/script"),
          "__SPECS__":payload}
    for k,v in subs.items():
        require(page.count(k) == 1, "template token " + k)
        page=page.replace(k,v)
    require("<script src=" not in page, "external JS dependency")
    return page


def build(snapshot, output):
    snapshot=Path(snapshot)
    d=json.loads(snapshot.read_text(encoding="utf-8"))
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    evidence=output/"evidence.json"
    if evidence.resolve() != snapshot.resolve():
        evidence.write_bytes(snapshot.read_bytes())
    page=render(d)
    (output/"evidence.html").write_text(page,encoding="utf-8")
    manifest={"schema":"missioncontrol.makeover.w2_plotly_manifest.v1",
              "source_sha":d["source_head_sha"],
              "observation_class":d["evidence_class"],
              "publisher":"EXISTING_METHOD_ATLAS_PAGES_ONLY",
              "merge_admission":"HOLD","security_waiver":False,
              "authority_transfer":False,"gg_math_kernel_duplicated":False,
              "member_sha256":{n:hashlib.sha256((output/n).read_bytes()).hexdigest()
                              for n in ("evidence.json","evidence.html")}}
    (output/"evidence-manifest.json").write_text(
        json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return manifest


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--snapshot",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    m=build(a.snapshot,a.out)
    print(json.dumps({"W2_PLOTLY":"RENDERED_SOURCE_BOUNDED", "members":m["member_sha256"],
                      "evidence_class":m["observation_class"]},sort_keys=True))
