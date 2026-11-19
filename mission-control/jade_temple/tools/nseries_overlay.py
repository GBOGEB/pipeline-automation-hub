#!/usr/bin/env python3
"""Read-only JADE N-series overlay: validate, project, and render offline views.

A projection only. It does not fetch live evidence, change owner systems, or
promote source/engineering identity to authority. Reuse lifecycle.topo_layers.
"""
from __future__ import annotations

import argparse
import html
import importlib.util
import json
from pathlib import Path

JADE = Path(__file__).resolve().parents[1]
INPUT = JADE / "data" / "N_SERIES_REGISTRY_v1.json"
DIAGRAMS = JADE / "diagrams"
SITE = JADE / "site"
HARD = "HARD_DAG"
KINDS = {HARD, "TEMPORAL_SUCCESSOR", "CANDIDATE_LINEAGE", "REFERENCE_ONLY", "NEXT_PULSE"}
CLASSIFICATIONS = {"PROPOSED_METHOD", "HISTORICAL_SOURCE", "CANDIDATE_CROSSWALK", "OPERATIONAL_REFERENCE"}


def _topo_layers(nodes: list[str], edges: list[tuple[str, str, str]]) -> list[list[str]]:
    """Delegate to the single JADE Kahn owner, not a copy of its logic."""
    module_path = JADE / "devops" / "lifecycle.py"
    spec = importlib.util.spec_from_file_location("jade_existing_lifecycle", module_path)
    if spec is None or spec.loader is None:
        raise ValueError("JADE lifecycle Kahn owner unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.topo_layers(nodes, edges)


def validate(data: dict) -> dict:
    if data.get("schema") != "jade.nseries.overlay.v1":
        raise ValueError("unknown N-series overlay schema")
    if data.get("authority") != "READ_ONLY_PROJECTION" or data.get("authority_transfer") is not False:
        raise ValueError("authority boundary violated")
    if data.get("merge_admission") != "HOLD":
        raise ValueError("overlay cannot declare merge admission")
    nodes = data.get("nodes")
    edges = data.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list) or not nodes:
        raise ValueError("missing nodes or edges")
    ids: set[str] = set()
    for n in nodes:
        if not isinstance(n, dict):
            raise ValueError("node is not an object")
        ident = n.get("id")
        if not isinstance(ident, str) or ":" not in ident:
            raise ValueError("node missing namespaced ID")
        if ident in ids:
            raise ValueError("duplicate node: " + ident)
        ids.add(ident)
        if ident.split(":", 1)[0] != n.get("namespace"):
            raise ValueError("namespace mismatch: " + ident)
        if n.get("classification") not in CLASSIFICATIONS or not n.get("owner"):
            raise ValueError("unowned or unclassified node: " + ident)
        if n.get("status") in {"PASS", "APPROVED", "ADMITTED"}:
            raise ValueError("projection cannot assert success: " + ident)
    pairs: set[tuple[str, str, str]] = set()
    hard: list[tuple[str, str, str]] = []
    for e in edges:
        a, b, kind = e.get("from"), e.get("to"), e.get("kind")
        if a not in ids or b not in ids:
            raise ValueError("unknown edge endpoint")
        if kind not in KINDS or not e.get("evidence"):
            raise ValueError("untyped or ungrounded edge")
        key = a, b, kind
        if key in pairs:
            raise ValueError("duplicate typed edge")
        pairs.add(key)
        if kind == HARD:
            if not (a.startswith("GLOBAL:") and b.startswith("GLOBAL:")):
                raise ValueError("unverified cross-namespace hard dependency")
            hard.append((a, b, "FEEDFORWARD"))
    layers = _topo_layers(sorted(ids), hard)
    return {"schema": data["schema"], "authority": data["authority"],
            "merge_admission": "HOLD", "nodes": len(ids), "edges": len(edges),
            "hard_edges": len(hard), "layers": layers,
            "native_execution_receipt": None, "independent_approval": None}


def _quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def diagram(data: dict, *, only_hard: bool) -> str:
    nodes = {n["id"]: n for n in data["nodes"]}
    selected = [e for e in data["edges"] if not only_hard or e["kind"] == HARD]
    kept = sorted(
        {v for e in selected for v in (e["from"], e["to"])}
        | ({n for n in nodes if n.startswith("GLOBAL:")} if only_hard else set(nodes))
    )
    aliases = {n: "n" + str(i) for i, n in enumerate(kept)}
    lines = ["flowchart LR"]
    for n in kept:
        lines.append("  " + aliases[n] + "[" + _quote(n + " | " + nodes[n]["label"]) + "]")
    for e in selected:
        a, b = aliases[e["from"]], aliases[e["to"]]
        if e["kind"] == HARD:
            lines.append(f"  {a} --> {b}")
        else:
            lines.append(f"  {a} -.->|{e['kind']}| {b}")
    lines += [
        "  classDef proposed fill:#43304D,stroke:#A878B2,color:#FFFFFF",
        "  classDef reference fill:#36363B,stroke:#9D9DA4,color:#FFFFFF",
        "  classDef hold fill:#713546,stroke:#C78896,color:#FFFFFF",
    ]
    for n in kept:
        style = "hold" if n == "GLOBAL:N6" else ("proposed" if n.startswith("GLOBAL:") else "reference")
        lines.append(f"  class {aliases[n]} {style}")
    return "\n".join(lines) + "\n"


def webpage(data: dict, evidence: dict) -> str:
    """Self-contained offline browser with search/filter, clickable reference rows."""
    payload = json.dumps(data, ensure_ascii=True, sort_keys=True).replace("<", "\\u003c")
    counts = f"{evidence['nodes']} nodes / {evidence['edges']} typed edges / {evidence['hard_edges']} proposed hard edges"
    template = r"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>JADE Namespaced N-series / OID reference overlay</title>
<style>
:root{color-scheme:dark;font:15px/1.5 system-ui,Arial;background:#201B23;color:#EEE8F0}
body{max-width:1200px;margin:auto;padding:22px}header{border-bottom:2px solid #8D4D9A}
h1,h2{color:#E7BFEF}.mute{color:#B7AEBB}.warn{color:#FFCFD3}
.controls{display:flex;gap:12px;flex-wrap:wrap;padding:16px 0}input,select{padding:9px 11px;background:#302B33;color:white;border:1px solid #807287;border-radius:6px}
.panel{background:#2A2630;border:1px solid #5A5261;border-radius:8px;padding:12px;margin:12px 0}
table{border-collapse:collapse;width:100%}th,td{padding:8px;text-align:left;border-bottom:1px solid #524857;vertical-align:top}
th{color:#E8B8DF}small{color:#CDBFD0}a{color:#F0B6E8}code{color:#DFC4E9}
.tag{font-size:11px;border:1px solid #94819C;border-radius:12px;padding:2px 7px;white-space:nowrap}
svg{max-width:100%;height:auto;background:#261F2A;border-radius:8px}
</style><body>
<header><h1>JADE N-series &amp; OID relationship overlay</h1>
<p class="warn">READ-ONLY · DECLARED · NOT NATIVE CI · NOT ENGINEERING OR MERGE AUTHORITY</p>
<p id="counts" class="mute">COUNTS</p></header>
<div class="controls"><label>Search <input id="search" type="search" placeholder="namespace, OID, owner, source, status"></label>
<label>Namespace <select id="namespace"><option value="">All namespaces</option></select></label>
<label>Edge <select id="edge"><option value="">All typed edges</option></select></label></div>
<section class="panel"><h2>Global workflow DAG (proposed)</h2><svg id="graph" viewBox="0 0 1090 130" role="img" aria-label="Eight source-to-admission steps; N6 is held"></svg>
<p class="mute">Only HARD_DAG relationships participate in same-pulse Kahn checks. Temporal, reference and next-pulse links never promote execution readiness.</p></section>
<section class="panel"><h2>N-series registry</h2><table><thead><tr><th>ID</th><th>Meaning</th><th>Owner</th><th>Evidence class</th><th>Status</th></tr></thead><tbody id="nodes"></tbody></table></section>
<section class="panel"><h2>Typed dependencies and references</h2><table><thead><tr><th>From</th><th>Type</th><th>To</th><th>Provenance</th></tr></thead><tbody id="edges"></tbody></table></section>
<section class="panel"><h2>Source-owner links</h2><div id="sources"></div>
<p class="warn">OID in JADE can mean a Git blob; QPS Object BIOS engineering identities and publication workflow OIDs are separate authority classes. No automatic alias acceptance or cross-source promotion.</p></section>
<script id="registry" type="application/json">PAYLOAD</script><script>
"use strict";
const data=JSON.parse(document.getElementById("registry").textContent);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const nsel=document.getElementById("namespace"), esel=document.getElementById("edge"), search=document.getElementById("search");
for(const n of [...new Set(data.nodes.map(x=>x.namespace))].sort()){const o=document.createElement("option");o.value=o.textContent=n;nsel.append(o)}
for(const n of [...new Set(data.edges.map(x=>x.kind))].sort()){const o=document.createElement("option");o.value=o.textContent=n;esel.append(o)}
function draw(){
const q=search.value.toLowerCase().trim(), ns=nsel.value, et=esel.value;
const match=x=>!q||JSON.stringify(x).toLowerCase().includes(q);
const nodes=data.nodes.filter(x=>(!ns||x.namespace===ns)&&match(x));
const nodeIds=new Set(nodes.map(x=>x.id));
document.getElementById("nodes").innerHTML=nodes.map(x=>"<tr><td><code>"+esc(x.id)+"</code></td><td>"+esc(x.label)+"</td><td>"+esc(x.owner)+"</td><td><span class=tag>"+esc(x.classification)+"</span></td><td>"+esc(x.status)+"</td></tr>").join("");
const edges=data.edges.filter(x=>(!et||x.kind===et)&&(!ns||(nodeIds.has(x.from)||nodeIds.has(x.to)))&&match(x));
document.getElementById("edges").innerHTML=edges.map(x=>"<tr><td><code>"+esc(x.from)+"</code></td><td>"+esc(x.kind)+"</td><td><code>"+esc(x.to)+"</code></td><td>"+esc(x.evidence)+"</td></tr>").join("");
}
function graph(){
const svg=document.getElementById("graph"), NS="http://www.w3.org/2000/svg";
const make=(tag,attrs,content)=>{const el=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))el.setAttribute(k,v);if(content)el.textContent=content;svg.appendChild(el);return el};
for(let i=0;i<8;i++){const x=12+i*136; if(i<7){make("path",{d:"M"+(x+113)+" 58 L"+(x+133)+" 58",stroke:"#BA92C5","stroke-width":2,fill:"none"});make("path",{d:"M"+(x+133)+" 58 l-7 -4 v8 z",fill:"#BA92C5"})}
make("rect",{x,y:20,width:113,height:75,rx:9,fill:i===6?"#723D4E":"#4A3453",stroke:i===6?"#DFA0A9":"#AB83B5"});
make("text",{x:x+56,y:46,"text-anchor":"middle",fill:"#FFF","font-size":16,"font-weight":700},"N"+i);
make("text",{x:x+56,y:69,"text-anchor":"middle",fill:"#EBD3F0","font-size":10},["INVENTORY","SHA PROOF","ROOT / OID","DAG / BD","LANES","QA / REVIEW","HOLD","RECENSUS"][i])}
}
document.getElementById("sources").innerHTML=data.sources.map(x=>{const name=esc(x.owner)+"/"+esc(x.path);const link=(typeof x.url==="string"&&x.url.startsWith("https://github.com/GBOGEB/pipeline-automation-hub/"))?"<a target=_blank rel=noopener href='"+esc(x.url)+"'>"+name+"</a>":name;return "<p>"+link+" <small>"+esc(x.role)+"</small></p>";}).join("");
document.getElementById("counts").textContent="COUNTS";
for(const e of [nsel,esel,search])e.addEventListener("input",draw);
draw();graph();
</script></body></html>
"""
    return template.replace("PAYLOAD", payload).replace("COUNTS", html.escape(counts))


def outputs(data: dict) -> dict[Path, str]:
    evidence = validate(data)
    return {
        DIAGRAMS / "GLOBAL_N_SERIES.mmd": diagram(data, only_hard=True),
        DIAGRAMS / "N_SERIES_DEPENDENCIES.mmd": diagram(data, only_hard=False),
        SITE / "nseries_atlas.html": webpage(data, evidence),
        SITE / "nseries_atlas.json": json.dumps(evidence, indent=2, sort_keys=True) + "\n",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    produced = outputs(data)
    if args.check:
        stale = [str(p) for p, body in produced.items()
                 if not p.is_file() or p.read_text(encoding="utf-8") != body]
        if stale:
            print("STALE / missing generated files: " + ", ".join(stale))
            return 1
    else:
        for path, body in produced.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8", newline="\n") as out:
                out.write(body)
    print(json.dumps(validate(data), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
