#!/usr/bin/env python3
"""G10 native graph visual QA for the existing G7 SIPOC projection.

Interactive SVG is a viewer, not authoritative evidence. Validate node/edge
provenance before rendering; only the G7 canonical module may create that DAG.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import re
from pathlib import Path

SCHEMA = "gogreen.success-temporal.sipoc-dag.v1"
RECEIPT = "gogreen.g10.graph-visual-qa.v1"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
ID = re.compile(r"(?:CAP_[A-Z0-9]{2,32}|S|I|P_SOURCE|P_REVERSE|P_REX|O|C)\Z")
BINDINGS = ("OBSERVED", "DECLARED")
ROLES = ("S", "I", "P", "O", "C")
REQUIRED = {"S","I","P_SOURCE","P_REVERSE","P_REX","O","C"}
ROLE_COLOR = {"S":"#22d3ee","I":"#38bdf8","P":"#a78bfa","O":"#34d399","C":"#fbbf24"}
EDGE_COLOR = {"OBSERVED":"#28d3ad","DECLARED":"#f5b54b"}
WEIGHT = {"OBSERVED":3.0,"DECLARED":1.6}


def require(ok,why):
    if not ok:
        raise ValueError(why)


def canonical(x):
    return (json.dumps(x,sort_keys=True,indent=2,ensure_ascii=True)+"\n").encode("ascii")


def validate(graph):
    require(isinstance(graph,dict) and graph.get("schema")==SCHEMA,"wrong SIPOC graph source")
    require(graph.get("authority_transfer") is False and
            graph.get("dispatch_authorized") is False and
            graph.get("merge_authorized") is False and
            graph.get("admission")=="HOLD","unqualified graph promotion")
    nodes=graph.get("nodes")
    edges=graph.get("edges")
    require(isinstance(nodes,list) and isinstance(edges,list)
            and 7<=len(nodes)<=64 and 6<=len(edges)<=256,"graph bounds")
    by_id={}
    for node in nodes:
        require(isinstance(node,dict),"non-node in DAG")
        ident=node.get("id")
        require(isinstance(ident,str) and ID.fullmatch(ident) and ident not in by_id,
                "invalid/duplicate node identity")
        require(node.get("role") in ROLES,"invalid SIPOC role")
        require(isinstance(node.get("label"),str) and
                0<len(node["label"])<=400,"invalid label")
        require(isinstance(node.get("owner"),str) and node["owner"],"no owner")
        require(isinstance(node.get("evidence"),str) and node["evidence"],"no source evidence class")
        if ident.startswith("CAP_"):
            require(node["role"]=="P" and
                    isinstance(node.get("entrypoint"),str) and node["entrypoint"] and
                    isinstance(node.get("input"),str) and node["input"] and
                    isinstance(node.get("output"),str) and node["output"],"capability provenance incomplete")
        by_id[ident]=node
    require(REQUIRED.issubset(by_id),"missing SIPOC canonical base node")
    for name,role in {"S":"S","I":"I","P_SOURCE":"P","P_REVERSE":"P",
                      "P_REX":"P","O":"O","C":"C"}.items():
        require(by_id[name]["role"]==role,"role drift")
    pairs=set()
    adj={k:[] for k in by_id}
    incoming={k:[] for k in by_id}
    for edge in edges:
        require(isinstance(edge,dict),"invalid edge")
        source,target,kind=edge.get("source"),edge.get("target"),edge.get("kind")
        binding=edge.get("binding")
        require(source in by_id and target in by_id and source!=target,"unknown/self-loop edge")
        require(binding in BINDINGS,"unsupported graph confidence")
        require(isinstance(kind,str) and kind and len(kind)<=100,"invalid edge type")
        key=(source,target,kind)
        require(key not in pairs,"duplicate typed edge")
        pairs.add(key)
        adj[source].append(target)
        incoming[target].append(source)
    require(len(incoming["S"])==0 and len(adj["C"])==0,
            "source and customer terminal degree semantics")
    require("I" in adj["S"] and "P_SOURCE" in adj["I"] and
            "O" in adj["P_SOURCE"] and "C" in adj["O"],
            "mandatory verified spine missing")
    state={}
    order=[]
    def visit(node):
        mark=state.get(node,0)
        require(mark!=1,"cyclic DAG not renderable")
        if mark==2:return
        state[node]=1
        for nxt in adj[node]:visit(nxt)
        state[node]=2
        order.append(node)
    for node in by_id:visit(node)
    reachable={"S"}
    todo=["S"]
    while todo:
        node=todo.pop()
        for target in adj[node]:
            if target not in reachable:
                reachable.add(target);todo.append(target)
    require(reachable==set(by_id),"disconnected or unreachable node")
    # Do not draw arbitrary edge into a SIPOC supplier or out of customer.
    return {"nodes":by_id,"adj":adj,"incoming":incoming,"order":list(reversed(order))}


def layout(graph):
    validated=validate(graph)
    nodes=validated["nodes"]
    caps=sorted(n for n in nodes if n.startswith("CAP_"))
    positions={
        "S":(85,160),"I":(300,160),"P_SOURCE":(520,160),
        "P_REVERSE":(735,75),"P_REX":(735,190),
        "O":(1050,230),"C":(1270,230)}
    for idx,ident in enumerate(caps):
        positions[ident]=(750,330+idx*88)
    require(len(positions)==len(nodes),"unpositioned or duplicated atom")
    h=max(620,430+len(caps)*88)
    return positions,1450,h


def edge_path(src,tgt,positions):
    a=positions[src];b=positions[tgt]
    x1,y1=a;x2,y2=b
    # Keep heads terminating outside the node center for clear in/out arrows.
    if x2>=x1:
        sx=x1+78; ex=x2-80
    else:
        sx=x1-78; ex=x2+80
    delta=ex-sx
    curve=round(abs(delta)*0.45,2)
    cp1x=sx+(curve if delta>=0 else -curve)
    cp2x=ex-(curve if delta>=0 else -curve)
    return (f"M {sx:.1f},{y1:.1f} C {cp1x:.1f},{y1:.1f} "
            f"{cp2x:.1f},{y2:.1f} {ex:.1f},{y2:.1f}")


def svg(graph):
    positions,w,h=layout(graph)
    lines=[
        f'<svg id="native-dag" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" role="img" '
        'aria-label="Read-only source-bound SIPOC process graph with directed, confidence-coded edges">',
        '<defs>',
        '<marker id="arrow-observed" markerWidth="10" markerHeight="9" refX="9" refY="4.5" '
        'orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0L9 4.5L0 9Z" fill="#28d3ad"/></marker>',
        '<marker id="arrow-declared" markerWidth="10" markerHeight="9" refX="9" refY="4.5" '
        'orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0L9 4.5L0 9Z" fill="#f5b54b"/></marker>',
        '</defs>',
    ]
    for e in graph["edges"]:
        binding=e["binding"]
        col=EDGE_COLOR[binding]
        width=WEIGHT[binding]
        source,target=e["source"],e["target"]
        d=edge_path(source,target,positions)
        lines.append(
            '<path class="dag-edge" tabindex="0" data-source="'+html.escape(source,quote=True)+
            '" data-target="'+html.escape(target,quote=True)+'" data-evidence="'+binding+
            '" data-kind="'+html.escape(e["kind"],quote=True)+'" d="'+d+
            '" fill="none" stroke="'+col+'" stroke-width="'+str(width)+
            '" opacity="0.82" marker-end="url(#arrow-'+binding.lower()+')"/>')
    for n in graph["nodes"]:
        ident=n["id"];role=n["role"];x,y=positions[ident]
        col=ROLE_COLOR[role]
        label=n["label"]
        headline=ident if len(ident)<20 else ident[:17]+"..."
        lines.append(
            '<g class="dag-node" tabindex="0" data-node="'+html.escape(ident,quote=True)+
            '" data-role="'+role+'" transform="translate('+str(x)+','+str(y)+')">'
            '<title>'+html.escape(ident+" | "+label,quote=False)+'</title>'
            '<rect x="-78" y="-25" width="156" height="50" rx="10" '
            'fill="#12263d" stroke="'+col+'" stroke-width="2.2"/>'
            '<text text-anchor="middle" dominant-baseline="middle" fill="#f0f8ff" '
            'font-size="12.5">'+html.escape(headline,quote=False)+'</text></g>')
    lines.append('</svg>')
    return "\n".join(lines)+"\n"


def html_page(graph):
    safe_svg=svg(graph)
    # Hostile untrusted labels are always HTML-escaped in SVG attributes/content.
    return '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GoGREEN G10 · SIPOC visual QA</title>
<style>
:root{color-scheme:dark;font:15px system-ui;background:#0b1728;color:#e7f3ff}
body{max-width:1400px;margin:auto;padding:16px}h1{font-size:1.7rem}
.panel{background:#14283e;border:1px solid #435674;border-radius:12px;padding:14px}
.graph{overflow:auto;border:1px solid #425a70;border-radius:12px;background:#0e2136}
#native-dag{min-width:650px;width:100%;height:auto;transform-origin:top left}
.dag-node:focus rect,.dag-edge:focus{stroke:#fff;outline:3px solid #fff;outline-offset:2px}
.controls{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:14px 0}
button{background:#204366;color:white;border:1px solid #6b99bd;border-radius:7px;padding:9px;cursor:pointer}
label{font-weight:600}input{width:160px}
.small{color:#b8c6d8} .o{color:#28d3ad}.d{color:#f5b54b}
</style><body><h1>GoGREEN G10 · SIPOC directed graph</h1>
<p>Source-bound G7 DAG viewer. Edge colors &amp; line weights encode observed versus declared evidence;
arrowheads identify direction. No worker dispatch or merge admission.</p>
<div class="panel"><div class="controls"><label for="scale">Graph zoom</label>
<input id="scale" type="range" min="55" max="210" step="5" value="100"
 aria-label="Graph zoom percentage"><output id="zoom-percent">100%</output>
<button type="button" id="reset">Reset zoom</button>
<button type="button" id="fit">Fit</button>
</div><p class="small"><span class="o">━━▶ OBSERVED</span> (3.0 px) ·
<span class="d">─▶ DECLARED</span> (1.6 px) · SIPOC role border colors</p>
<div id="graph-frame" class="graph">'''+safe_svg+'''</div>
<p class="small">Keyboard: Tab to focus individual nodes and directed edges. SVG provides
title text for full node identity. Zoom controls change presentation only.</p></div>
<script>
const graph=document.getElementById('native-dag');
const scale=document.getElementById('scale');
const output=document.getElementById('zoom-percent');
function applyZoom(){let n=Number(scale.value);if(!Number.isFinite(n)||n<55||n>210)return;
  graph.style.width=n+'%';output.textContent=n+'%';}
scale.addEventListener('input',applyZoom);
document.getElementById('reset').addEventListener('click',()=>{scale.value='100';applyZoom()});
document.getElementById('fit').addEventListener('click',()=>{scale.value='75';applyZoom()});
applyZoom();
</script></body></html>
'''


def qa_receipt(graph):
    v=validate(graph)
    positions,w,h=layout(graph)
    content=svg(graph)
    edge_counts={k:sum(e["binding"]==k for e in graph["edges"]) for k in BINDINGS}
    require(sum(edge_counts.values())==len(graph["edges"]),"edge count drift")
    for e in graph["edges"]:
        require('data-source="'+e["source"]+'"' in content and
                'data-target="'+e["target"]+'"' in content, "directed arrow missing")
    return {"schema":RECEIPT,"source_schema":SCHEMA,
            "node_count":len(v["nodes"]),"edge_count":len(graph["edges"]),
            "capability_nodes":sum(x.startswith("CAP_") for x in v["nodes"]),
            "observed_edges":edge_counts["OBSERVED"],
            "declared_edges":edge_counts["DECLARED"],
            "canvas_width":w,"canvas_height":h,
            "stroke_weight_px":dict(WEIGHT),"edges_role_typed":True,
            "directed_arrows_verified":True,"acyclic_verified":True,
            "all_nodes_reachable_from_supplier":True,
            "observable_semantics_not_admission":True,
            "browser_visual_inspection":None,"external_custody_verified":False,
            "independent_root_trials":None,"merge_authorized":False}


def build(graph,out,source_sha):
    require(isinstance(source_sha,str) and SHA40.fullmatch(source_sha),"producer source SHA required")
    receipt=qa_receipt(graph)
    out.mkdir(parents=True,exist_ok=True)
    files={"index.html":html_page(graph).encode("utf-8"),
           "graph.svg":svg(graph).encode("utf-8"),
           "qa.json":canonical(receipt),
           "source_dag.json":canonical(graph)}
    for name,content in files.items():
        (out/name).write_bytes(content)
    manifest={"schema":"gogreen.g10.artifact-manifest.v1","source_sha":source_sha,
              "files":{k:hashlib.sha256(v).hexdigest() for k,v in files.items()},
              "html_svg_source_bound":True,"admission":"HOLD",
              "external_custody_verified":False,"merge_authorized":False}
    (out/"manifest.json").write_bytes(canonical(manifest))
    return receipt,manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--source-sha",required=True)
    a=parser.parse_args()
    x=json.loads(a.input.read_text(encoding="utf-8"))
    receipt,manifest=build(x,a.out,a.source_sha)
    print(json.dumps({"nodes":receipt["node_count"],"edges":receipt["edge_count"],
                      "observed":receipt["observed_edges"],
                      "declared":receipt["declared_edges"],
                      "admission":manifest["admission"]},sort_keys=True))


if __name__=="__main__":
    main()
