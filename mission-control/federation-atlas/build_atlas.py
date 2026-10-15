#!/usr/bin/env python3
"""Read-only CODE PURPLE atlas projection from Mission Control source JSON and YAML."""
import argparse
import html
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ALLOWED = {"SIPOC", "DAG", "DMAIC", "3P*", "MIP", "PCA", "BT", "LDAB"}

def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))

def safe(value):
    return html.escape(str(value), quote=True)

def text_or_unknown(value):
    return "UNKNOWN" if value is None else str(value)

def event_receipt(method, stage, event):
    """Only recommend tasks, never manufacture a pass, write an issue, or merge."""
    if method not in ALLOWED:
        raise ValueError("Invalid method")
    if not isinstance(event, dict):
        raise ValueError("Invalid event")
    steps = event.get("executed_steps")
    if steps is not None and (type(steps) is not int or steps < 0):
        raise ValueError("invalid executed_steps")
    sha = event.get("source_sha")
    red = event.get("observed_application_red") is True
    valid_sha = isinstance(sha, str) and len(sha) == 40 and all(c in "0123456789abcdef" for c in sha.lower())
    if event.get("owner_external") is True:
        route = "RETURN_OWNER"
    elif red and steps == 0:
        route = "DOCKMASTER"
    elif red and steps is not None and steps > 0 and valid_sha:
        route = "DOCTOR_REX_LOOKUP"
    else:
        route = "EVIDENCE_PENDING_OR_3PR"
    return {"schema":"missioncontrol.atlas.method_pulse.v1",
            "method":method,"stage":stage,"source_sha":sha if valid_sha else None,
            "observed_red":red,"executed_steps":steps,"recommended_route":route,
            "disposition":"ADVISORY_ONLY","authority_transfer":False,"formal_credit_delta":0}

def draw(graph):
    nodes = {n["id"]: n for n in graph["nodes"]}
    assert len(nodes) == len(graph["nodes"])
    assert set(nodes) == {"MC","QPS","KEB","DOW","AUX","INF","JOIN","GATE"}
    colors = {"control":"#ae8cff","child":"#56e6cd","semantic":"#a29aff",
              "runtime":"#84b5ff","helper":"#8fcade","infra":"#65d0c9",
              "evidence":"#72b8fc","hold":"#ffc776"}
    parts = ['<svg viewBox="0 0 1000 400" role="img" aria-label="Typed federation execution: parallel lanes joined by evidence" xmlns="http://www.w3.org/2000/svg">',
      '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8 Z" fill="#9aaad9"/></marker></defs>']
    for edge in graph["edges"]:
        if edge.get("binding") not in ("RECEIPT", "DECLARED"):
            raise ValueError(f"edge {edge['from']}->{edge['to']} needs binding RECEIPT or DECLARED")
        a,b = nodes[edge["from"]],nodes[edge["to"]]
        x1,y1 = float(a["x"])+96,float(a["y"])+24
        x2,y2 = float(b["x"])-8,float(b["y"])+24
        c = x1+(x2-x1)*.5
        dash = ' stroke-dasharray="6 5"' if edge["binding"] == "DECLARED" else ""
        parts.append(f'<path d="M{x1:g} {y1:g} C{c:g} {y1:g} {c:g} {y2:g} {x2:g} {y2:g}" fill="none" stroke="#7b8ab8" stroke-width="2"{dash} marker-end="url(#arrow)" opacity=".82" data-binding="{edge["binding"]}"/>')
    for n in graph["nodes"]:
        x,y=float(n["x"])-8,float(n["y"])
        clr=colors[n["class"]]
        parts.append(f'<rect x="{x:g}" y="{y:g}" rx="13" width="208" height="48" fill="#19182e" stroke="{clr}" stroke-width="1.8"/>')
        parts.append(f'<text x="{x+104:g}" y="{y+29:g}" text-anchor="middle" fill="#f5f2ff" font-family="system-ui,Arial" font-size="14" font-weight="600">{safe(n["label"])}</text>')
    parts.append('</svg>')
    return "\n".join(parts)

def build(out, method=None, stage=None, event=None):
    try:
        import yaml
    except ImportError as exc:
        raise SystemExit("PyYAML is required: install pinned pyyaml==6.0.3") from exc
    cat=load("mission-control/federation-atlas/METHOD_OBSERVABILITY_v1.json")
    mission=load(cat["sources"]["canonical_mc"])
    evolution=load(cat["sources"]["fleet_contract"])
    graph=yaml.safe_load((HERE/"ATLAS_GRAPH_v1.yaml").read_text(encoding="utf-8"))
    assert graph["schema"] == "missioncontrol.federation_atlas.graph.v1"
    assert cat["authority_transfer"] is False
    assert evolution["cohorts"]["top7"] and len(evolution["cohorts"]["top14_extension"]) == 7
    assert len(evolution["cohorts"]["top21_extension"]) == 7
    assert cat["cohorts"] == {"top7":"ACTIVE","top14":"SHADOW_MEASURE","top21":"HOLD_TELEMETRY"}
    ids=[m["id"] for m in cat["methods"]]
    assert len(ids)==len(set(ids)) and set(ids)==ALLOWED
    for m in cat["methods"]:
        assert m["stages"] and m["metric"]
    if method is not None and method not in ALLOWED:
        raise ValueError("Unknown method")
    if stage is not None and method is None:
        raise ValueError("Stage requires method")
    if stage is not None and stage not in next(m["stages"] for m in cat["methods"] if m["id"]==method):
        raise ValueError("Unregistered stage")
    if event is not None and (method is None or stage is None):
        raise ValueError("Method + stage required for observed event")
    receipt = event_receipt(method,stage,event) if event is not None else None
    kpi_contract=load("mission-control/federation-atlas/PHASE02_KPI_TAXONOMY_v1.json")
    if kpi_contract["schema"] != "missioncontrol.phase02_kpi_taxonomy.v1" or len(kpi_contract["kpis"]) != 6:
        raise ValueError("Phase 02 KPI taxonomy mismatch")
    if "BRADLEY_TERRY" not in next(m["role"] for m in cat["methods"] if m["id"]=="BT"):
        raise ValueError("BT taxonomy must mean Bradley-Terry")
    snapshot=mission.get("snapshot_at")
    missions=mission.get("missions",[])
    known=sum(m.get("metrics",{}).get("evidence_state") not in (None,"UNKNOWN") for m in missions)
    metrics={
      "schema":"missioncontrol.federation_atlas.metrics.v1",
      "source_snapshot_at":snapshot,"build_sha":os.environ.get("GITHUB_SHA"),
      "evidence_state":"HISTORICAL_SOURCE_SNAPSHOT_NOT_LIVE",
      "mission_rows":len(missions),"missions_with_known_evidence":known,
      "missions_unknown_evidence":len(missions)-known,
      "top7_repositories":len(evolution["cohorts"]["top7"]),
      "top14_repositories":len(evolution["cohorts"]["top7"])+len(evolution["cohorts"]["top14_extension"]),
      "top21_repositories":sum(len(evolution["cohorts"][k]) for k in ("top7","top14_extension","top21_extension")),
      "phase02_kpis":kpi_contract["kpis"],
      "active_method":method,"active_stage":stage,
      "advisory_receipt":receipt,"authority_transfer":False
    }
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    svg=draw(graph)
    (out/"federation.svg").write_text(svg,encoding="utf-8")
    import phase02_temporal
    phase02_temporal.build(out)
    import lane_process
    lane_process.build(out)
    (out/"metrics.json").write_text(json.dumps(metrics,indent=2)+"\n",encoding="utf-8")
    if receipt:
        (out/"method-pulse.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
    method_cards="".join(
        '<article class="tile method" data-method="'+safe(m["id"])+'"><h3>'+safe(m["id"])+'</h3><p>'+safe(m["role"])+'</p><p><strong>Stages:</strong> '+safe(" → ".join(m["stages"]))+'</p><p><strong>Trigger:</strong> '+safe(m["trigger"])+'</p><p><strong>Metric:</strong> '+safe(m["metric"])+'</p></article>'
        for m in cat["methods"])
    refs="".join(
        '<a class="link" href="'+safe(v["url"])+'" rel="noopener noreferrer" target="_blank">'+safe(v["label"])+
        '<small>'+("Hosted candidate · readback UNKNOWN" if v["kind"]=="HOSTED_CANDIDATE" else "Authoritative source navigation")+'</small></a>'
        for v in cat["links"])
    refs += ('<a class="link" href="federation-wave.html">'
             'Measured federation pulses · historical source-bound coverage'
             '<small>Not a live status or admission view</small></a>')
    kpi_cards="".join(
        '<article class="tile"><h3>'+safe(k["label"])+'</h3><div class="metric">UNKNOWN</div>'
        '<p>'+safe(k["definition"])+'</p><p><strong>Owner:</strong> '+safe(k["source_owner"])+
        '</p><p><strong>State:</strong> UNBOUND · no exact-current receipt</p></article>'
        for k in kpi_contract["kpis"])
    repo_items="".join(
        '<a class="chip" href="https://github.com/'+safe(r)+'" target="_blank" rel="noopener noreferrer">'+safe(r.split("/")[-1])+'</a>'
        for r in evolution["cohorts"]["top7"])
    mission_rows="".join(
       "<tr><td>"+safe(m.get("mission_id","UNKNOWN"))+"</td><td>"+safe(m.get("lifecycle",{}).get("state","UNKNOWN"))+
       "</td><td>"+safe(m.get("status",{}).get("execution","UNKNOWN"))+"</td><td>"+safe(m.get("metrics",{}).get("evidence_state","UNKNOWN"))+"</td></tr>"
       for m in missions)
    style="""html{background:#0b0b18;color:#e9e8fb;font:15px system-ui,Segoe UI,sans-serif}body{max-width:1480px;margin:auto;padding:32px}h1{font-size:2rem;color:#dfc5ff}h2{color:#d9c6ff}.sub{color:#9ba4cc}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px}.tile,.link{background:#17182d;border:1px solid #484579;border-radius:14px;padding:16px;display:block}.tile h3{margin:0 0 6px;color:#cfb9fc}.tile p{font-size:13px;color:#b5bad7}.metric{font-size:28px;font-weight:700;color:#78ded1}.band{display:flex;gap:14px;flex-wrap:wrap}.chip{display:inline-block;margin:5px;padding:7px 10px;background:#25223e;color:#b8d7ff;border-radius:8px}a{color:#a5c9ff;text-decoration:none}a:hover{text-decoration:underline}.link{margin-bottom:8px}.link small{display:block;color:#eabf78;margin-top:6px}svg{width:100%;height:auto;background:#121226;border:1px solid #353052;border-radius:18px}.table{overflow:auto}table{border-collapse:collapse;width:100%}th,td{text-align:left;border-bottom:1px solid #393550;padding:10px}label,select{font-size:14px}select{background:#26203c;color:white;border:1px solid #7860b0;padding:8px;border-radius:8px}button{background:#3c3066;color:#fff;border:1px solid #7c65a9;border-radius:7px;padding:8px}section{margin:30px 0}.foot{color:#b3accc;border-top:1px solid #40385f;padding-top:20px}@media(max-width:700px){body{padding:14px}h1{font-size:1.6rem}}"""
    page=f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>CODE PURPLE | Federation Mission Atlas</title><style>{style}</style></head><body>
<header><div class="sub">Mission Control / Federation / Observability · READ-ONLY HISTORICAL SNAPSHOT</div><h1>CODE PURPLE · Federation Mission Atlas</h1>
<p class="sub">Exact-source navigation, method-pulse projections, TOP7/TOP14/TOP21, mission evidence and independent-hosted dashboard catalogue. No live status inferred.</p></header>
<section><div class="grid"><article class="tile"><h3>Mission records</h3><div class="metric">{len(missions)}</div><p>Mission Control snapshot {safe(text_or_unknown(snapshot))}</p></article>
<article class="tile"><h3>Known evidence</h3><div class="metric">{known} / {len(missions)}</div><p>Source-classified; UNKNOWN is not green</p></article>
<article class="tile"><h3>TOP7</h3><div class="metric">7</div><p>Active repair admission by governed scope</p></article>
<article class="tile"><h3>TOP14 / TOP21</h3><div class="metric">14 / 21</div><p>Shadow measurement / telemetry HOLD</p></article></div></section>
<section><h2>Federation execution backbone</h2><p class="sub">YAML-driven SVG: dispatch → independent lanes → exact-SHA join → admission/HOLD.</p>{svg}</section>
<section><h2>Granular SIPOC + federation control lanes</h2><a class="link" href="lane-process.html">Open 39-node swimlanes, method stage pressure cards, guarded P5–P9 process gates and verified G4 sample KPIs</a><p class="sub">Companion Mermaid source: <a href="lane-process.mmd">lane-process.mmd</a> · <a href="lane-process.json">machine-readable receipt</a>. This read-only view does not change the canonical method lifecycle or confer admission.</p></section>
<section><h2>Federation Flight Deck · W3 source-bound navigation</h2><a class="link" href="flightdeck/index.html">Open six-repository / 42-cell evidence census, all 36 UNKNOWN work leaves and five historical anchor checks</a><p class="sub">Deterministic source-generated read-only view, with JSON/Markdown/SVG and SHA-bound manifest. No new Pages publisher, corporate acceptance or merge authority. <a href="flightdeck/manifest.json">Manifest</a> · <a href="flightdeck/GUIDE.md">Operator guide</a>.</p></section>
<section><h2>Measured Phase 02 CONTROL (scoped)</h2><a class="link" href="phase02-temporal.html">Open measured/UNBOUND temporal KPI cards, log SVG, evidence and lane matrix</a></section><section><h2>Phase 02 · six evidence KPIs</h2><p class="sub">Definitions updated {safe(kpi_contract["as_of"])} · mission census snapshot {safe(text_or_unknown(snapshot))}. UNBOUND values are not zero and mockups are not live telemetry. <a href="https://github.com/GBOGEB/pipeline-automation-hub/blob/master/mission-control/federation-atlas/PHASE02_KPI_TAXONOMY_v1.json">Source contract (pending merge)</a></p><div class="grid">{{kpi_cards}}</div></section>
<section><h2>Method execution catalogue</h2><label for="method">Filter method: </label><select id="method"><option value="ALL">All methods</option>{''.join('<option value="'+safe(k)+'">'+safe(k)+'</option>' for k in ids)}</select>
<div id="method-grid" class="grid" style="margin-top:15px">{method_cards}</div></section>
<section><h2>Live task / Doctor + REX decision</h2><article class="tile"><p>Doctor is conditionally admissible only on an observed application failure with executed steps &gt; 0 and valid exact source SHA. Zero-step red → Dockmaster. Owner-external → return to owner. REX lookup searches source-bound prior resolution before a repair proposal.</p>
<p>Selected method pulse: <strong>{safe(text_or_unknown(method))} / {safe(text_or_unknown(stage))}</strong> · Recommended route: <strong>{safe(receipt["recommended_route"] if receipt else "NO_EVENT_ADMITTED")}</strong></p></article></section>
<section><h2>TOP7 executing repository links</h2><div class="band">{repo_items}</div></section>
<section><h2>Mission status and task-reader entry</h2><p class="sub">Source snapshot, not an authenticated live PR census. Each mission references governed hierarchy: Mission → Sprint → Wave → Pulse → Run.</p><div class="table"><table><thead><tr><th>Mission</th><th>Lifecycle</th><th>Execution</th><th>Evidence</th></tr></thead><tbody>{mission_rows}</tbody></table></div></section>
<section><h2>Source dashboards & hosted navigation</h2><div class="grid">{refs}</div><p class="sub">Hosted candidates are labelled unverified until exact deployed URL + identity readback exists. This build does not publish GitHub Pages or replace the single authorized publisher.</p></section>
<footer class="foot">Source SHA: {safe(os.environ.get("GITHUB_SHA","UNBOUND"))} · Snapshot: {safe(text_or_unknown(snapshot))} · Authority transfer: false · Generated view, no formal engineering credit.</footer>
<script>document.getElementById('method').addEventListener('change', function(){{var value=this.value;document.querySelectorAll('.method').forEach(function(n){{n.hidden=value!=='ALL'&&n.dataset.method!==value}})}});</script></body></html>"""
    (out/"index.html").write_text(page,encoding="utf-8")
    return metrics

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",default="/tmp/code-purple-atlas")
    p.add_argument("--method",choices=sorted(ALLOWED))
    p.add_argument("--stage")
    p.add_argument("--event-file")
    a=p.parse_args()
    event=json.loads(Path(a.event_file).read_text(encoding="utf-8")) if a.event_file else None
    print(json.dumps(build(a.out,a.method,a.stage,event),indent=2))

if __name__=="__main__":
    main()
