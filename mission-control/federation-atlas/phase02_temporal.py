#!/usr/bin/env python3
"""Read-only measured Phase-02 dashboard. No fetched/fabricated time series."""
import datetime as dt
import html
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
IDS = ["QUEUE_P95","EXACT_HEAD_PROOF_YIELD","FIRST_RED_COUNT",
       "ACCEPTED_RECEIPT_YIELD","PREDICTION_VS_ACTUAL","RUNNER_HEALTH"]

def load(name):
    return json.loads((HERE/name).read_text(encoding="utf-8"))

def parse_utc(value):
    if not isinstance(value,str) or not value.endswith("Z"):
        raise ValueError("Exact UTC time required")
    return dt.datetime.fromisoformat(value.replace("Z","+00:00"))

def p95(values):
    if not values:
        return None
    return sorted(values)[math.ceil(.95*len(values))-1]

def queue_samples(observation):
    out = []
    seen = set()
    for job in observation["queue_jobs"]:
        if job["id"] in seen:
            raise ValueError("duplicate job id")
        seen.add(job["id"])
        seconds = (parse_utc(job["started"])-parse_utc(job["created"])).total_seconds()
        if seconds < 0:
            raise ValueError("negative queue interval")
        out.append({"job_id":job["id"],"run_id":job["run"],
                    "name":job["name"],"seconds":seconds,
                    "source_url":"https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/"+str(job["run"])})
    return out

def optional_test_decision(test, policy):
    deny = policy["optional_skip"]
    if test.get("required") is not False or test.get("lane") in deny["non_skippable"]:
        return "EXECUTE_REQUIRED"
    hist = test.get("distinct_head_history")
    if not isinstance(hist,list) or len(hist) < deny["min_distinct_head_passes"]:
        return "EXECUTE_UNKNOWN_HISTORY"
    sample = hist[-deny["min_distinct_head_passes"]:]
    if len({x.get("sha") for x in sample}) != len(sample):
        return "EXECUTE_DUPLICATE_HEAD"
    if any(x.get("conclusion")!="success" or x.get("executed_steps",0)<=0 for x in sample):
        return "EXECUTE_NOT_CONSISTENTLY_GREEN"
    if not test.get("impact_map_verified") or test.get("touched_dependencies"):
        return "EXECUTE_DEPENDENCY_PRESSURE"
    if not all(test.get(k) for k in ("current_smoke_green","canary_admitted","full_sweep_within_7d")):
        return "EXECUTE_CANARY_OR_FULL_SWEEP"
    return "OPTIONAL_SHADOW_DEFER_ONLY"

def control_disposition(receipts,policy):
    control=policy["control"]
    admissible=[r for r in receipts if r.get("root_closed") is True
                and r.get("exact_head_admitted") is True
                and r.get("independent_repeat") is True]
    heads={r.get("sha") for r in admissible}
    pulses={r.get("pulse") for r in admissible}
    if len(heads)>=control["distinct_heads_min"] and len(pulses)>=control["independent_pulses_min"] and all(isinstance(s,str) and len(s)==40 for s in heads):
        return "ELIGIBLE_FOR_OWNER_REVIEW"
    return "HOLD"

def classify(observation):
    check=observation["checks"]
    if check["terminal"]!=sum(check[x] for x in ("passed","failed","skipped")):
        raise ValueError("bad check denominator")
    samples=queue_samples(observation)
    events=observation["red_events"]
    if len({e["id"] for e in events})!=len(events):
        raise ValueError("duplicate first-red root identity")
    m={
      "QUEUE_P95":{"value":p95([j["seconds"] for j in samples]),"unit":"seconds","status":"SCOPED_OBSERVED_PARTIAL","denominator":len(samples),
                   "scope":"7 selected GitHub-hosted jobs; not full fleet","samples":samples},
      "EXACT_HEAD_PROOF_YIELD":{"value":None,"status":"UNBOUND","reason":"First-Pass Closure required receipt missing"},
      "FIRST_RED_COUNT":{"value":None,"status":"UNBOUND","reason":"Global application first-red census absent","governance_reds_observed":len(events)},
      "ACCEPTED_RECEIPT_YIELD":{"value":None,"status":"UNBOUND","reason":"No complete terminal receipt population"},
      "PREDICTION_VS_ACTUAL":{"value":None,"status":"NOT_MEASURED","reason":"No timestamped pre-outcome predictions"},
      "RUNNER_HEALTH":{"value":None,"status":"UNBOUND","reason":"No admitted-runner heartbeat denominator"}}
    return {"schema":"missioncontrol.phase02.temporal.v1","source_repo":observation["owner"],
      "source_head_sha":observation["head_sha"],"main_sha":observation["main_sha"],
      "observation_date":observation["observed_date"],"scope":"HISTORICAL_PR519_NOT_LIVE",
      "kpis":m,"observed_pr_check_census":check,"observed_postmerge_workflows":observation["postmerge"],
      "first_red_events":events,"control":"HOLD","authority_transfer":False}

def graph(events,method="log1p"):
    if method not in ("log1p","linear"):
        raise ValueError("bad scale")
    parts=['<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="First-red events, observed only" viewBox="0 0 720 185">',
      '<rect width="720" height="185" fill="#171a2c" rx="14"/>',
      '<path d="M55 18V154H680" fill="none" stroke="#9ea6c9"/>']
    for i,e in enumerate(sorted(events,key=lambda x:parse_utc(x["time"]))):
        y=58 if method=="log1p" else 60
        x=360 if len(events)==1 else 90+500*i/max(1,len(events)-1)
        parts.append('<circle cx="'+str(round(x,1))+'" cy="'+str(y)+'" r="7" fill="#fa637b"><title>'+
                     html.escape(e["reason"]+" "+e["time"])+'</title></circle>')
    if not events:
        parts.append('<text x="110" y="85" fill="#dde2fb">UNKNOWN / no observations</text>')
    parts.append('<text x="65" y="175" fill="#bfc5db" font-size="12">'+method+' scale · observed points only · no inferred trend</text></svg>')
    return "".join(parts)

def render(result):
    metrics=result["kpis"]
    buttons=[]
    for key in IDS:
        m=metrics[key]
        value="UNKNOWN" if m["value"] is None else str(m["value"])+" "+m.get("unit","")
        buttons.append('<button class="kpi" data-id="'+key+'"><b>'+key.replace("_"," ")+'</b><strong>'+html.escape(value)+'</strong><small>'+m["status"]+'</small></button>')
    payload=json.dumps(result).replace("<","\\u003c")
    page=r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>CODE PURPLE Phase 02 Temporal</title>
<style>
:root{color-scheme:dark;--bg:#0e1224;--card:#1c1d34;--ink:#f5f2ff;--muted:#bac0d8;--border:#524a7f}
:root[data-theme=light]{color-scheme:light;--bg:#f5f7fc;--card:white;--ink:#242243;--muted:#5c6683;--border:#d5d9ec}
body{background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,Segoe UI,sans-serif;max-width:1370px;margin:auto;padding:24px}
h1{font-size:28px;margin:4px 0}h2{font-size:18px}.sub,small{color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}.box,.kpi,dialog{background:var(--card);color:var(--ink);border:1px solid var(--border);border-radius:14px;padding:15px}
.kpi{text-align:left;min-height:126px;display:flex;flex-direction:column;gap:10px;cursor:pointer}.kpi strong{font-size:20px}.kpi:hover,.kpi:focus{outline:2px solid #8b6fed}
button,select{font:inherit;color:var(--ink);background:var(--card);border:1px solid var(--border);border-radius:9px;padding:7px 10px;cursor:pointer}
.row{display:grid;grid-template-columns:2fr 1fr;gap:12px}.toolbar{display:flex;gap:9px;flex-wrap:wrap;margin:16px 0}
svg{width:100%;height:auto}a{color:#759aee}p{max-width:980px}dialog{max-width:630px;width:90%}dialog::backdrop{background:#0009}pre{white-space:pre-wrap;overflow-wrap:anywhere}
[hidden]{display:none!important}@media(max-width:760px){.row{grid-template-columns:1fr}body{padding:12px}}
</style></head><body>
<header><small>MISSION CONTROL / PHASE 02 · SOURCE-BOUND HISTORICAL PR SAMPLE · NOT LIVE</small><h1>CODE PURPLE · first-red temporal CONTROL</h1>
<p class="sub">11 passed / 1 failed / 1 skipped at PR #519 head; 16/16 successful post-merge workflows. Neither proves exact-head admission or fleet-wide KPI health.</p>
<div class="toolbar"><button id="theme">Toggle light/dark</button><select id="window"><option>24h</option><option>7d</option><option>14d</option><option>21d</option></select>
<select id="scale"><option value="log1p">Zero-safe log1p</option><option value="linear">Linear</option></select><button id="legendButton">Legend</button><button id="laneButton">Execution lanes</button></div></header>
<section><h2>Six quantified KPI states · select for evidence</h2><div class="grid">@@CARDS@@</div></section>
<section class="row"><div class="box"><h2>First-red observations</h2><p class="sub">1 observed governance failure (MISSING_RECEIPT), not a full 24-hour fleet first-red count.</p><div id="plot">@@PLOT@@</div><small id="scope">24h selected · incomplete time series; missing points not filled with zero</small></div>
<div class="box"><h2>Two edges · one source lineage</h2><p><b style="color:#ed6c82">First red</b> → missing exact-head closure receipt (<a href="https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/38254267546">run</a>)</p>
<p><b style="color:#48cc9c">Last observed pass</b> → 16/16 successful main workflows (<a href="https://github.com/GBOGEB/pipeline-automation-hub/commit/8839d367e76ce9d877b92b60a8b4faf6e102394c">main SHA</a>)</p>
<p><strong>DMAIC CONTROL:</strong> HOLD, not baseline promoted. Require root closure, two distinct exact-head CONTROL repetitions, independent proof and owner review.</p></div></section>
<section id="laneMatrix" class="box"><h2>Task and test execution matrix</h2><div class="grid"><div><h3>Short Python triage</h3><p>Fast smoke/unit/diagnostic, run on change and first-red; isolate impacted tests.</p></div>
<div><h3>User CI/CD long</h3><p>Dedicated long-run lane and queue; security, integration, release and performance. Never blanket skip.</p></div>
<div><h3>Governance / admission</h3><p>Non-waivable exact-head closure, review, source identity; no skip based on historical greens.</p></div></div>
<p class="sub">Task states: HOLD · BLOCKED · ACTIVE · LINKED · SPLIT · PARALLEL · CONTROL. Optional test deferral needs 10 distinct source-head green receipts, impact isolation, canary and 7-day full sweep; no workflow is actually skipped by this view.</p></section>
<div id="legend" class="box" hidden>Green = observed scoped pass; red = first-red evidence; amber = HOLD; grey/UNKNOWN = no admissible observed denominator. A single point is not a trend or a 75% improvement.</div>
<dialog id="detail"><h2 id="title"></h2><pre id="json"></pre><button id="close">Close</button></dialog>
<footer class="sub"><p>Source snapshot: 2026-10-12 · current fleet KPI population incomplete · canonical source not mutated. <a href="https://github.com/GBOGEB/pipeline-automation-hub/issues/520">Telemetry issue #520</a> · <a href="https://github.com/GBOGEB/pipeline-automation-hub/issues/336">Closure receipt issue #336</a></p></footer>
<script>
const values=@@DATA@@;
const dlg=document.getElementById("detail");
document.querySelectorAll("[data-id]").forEach(b=>b.addEventListener("click",()=>{
document.getElementById("title").textContent=b.dataset.id;
document.getElementById("json").textContent=JSON.stringify(values.kpis[b.dataset.id],null,2);dlg.showModal()}));
document.getElementById("close").onclick=()=>dlg.close();
document.getElementById("theme").onclick=()=>{document.documentElement.dataset.theme=document.documentElement.dataset.theme==="light"?"dark":"light"};
document.getElementById("legendButton").onclick=()=>{const n=document.getElementById("legend");n.hidden=!n.hidden};
document.getElementById("laneButton").onclick=()=>{const n=document.getElementById("laneMatrix");n.hidden=!n.hidden};
document.getElementById("window").onchange=e=>{document.getElementById("scope").textContent=e.target.value+" · incomplete population; no synthetic zero-filled buckets"};
document.getElementById("scale").onchange=e=>{document.getElementById("plot").innerHTML=e.target.value==="linear"?@@LINEAR@@:@@LOG@@};
</script></body></html>"""
    return (page.replace("@@CARDS@@","".join(buttons))
      .replace("@@PLOT@@",graph(result["first_red_events"]))
      .replace("@@DATA@@",payload)
      .replace("@@LINEAR@@",json.dumps(graph(result["first_red_events"],"linear")))
      .replace("@@LOG@@",json.dumps(graph(result["first_red_events"],"log1p"))))

def build(out):
    observation=load("OBSERVED_PR519_20261012.json")
    result=classify(observation)
    dest=Path(out);dest.mkdir(parents=True,exist_ok=True)
    (dest/"phase02-temporal.html").write_text(render(result),encoding="utf-8")
    (dest/"phase02-first-red.svg").write_text(graph(result["first_red_events"]),encoding="utf-8")
    (dest/"phase02-temporal.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    return result

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--out",default="/tmp/phase02-temporal")
    a=p.parse_args()
    print(json.dumps(build(a.out)["kpis"],indent=2))
