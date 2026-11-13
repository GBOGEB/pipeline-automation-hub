#!/usr/bin/env python3
"""JQ-09: deterministic, read-only source-SVG to selectable HTML bridge.

One QPS-owned SVG is treated as source, never edited or re-authored.
An annotated derivative supplies view selection and does not invent a PDF map,
a test admission, or an executable browser-side watcher.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE_REL = "mission-control/qps-triage-ultra/site/assets/diagrams/qps-web-architecture.svg"
SOURCE = ROOT / SOURCE_REL
SOURCE_REF = "54e6b01ac7ada5bfad15562b4f99f7381a4fd73f"
EXPECTED_BLOB = "8a947a18a76bd87029b0c237be81505eb86f0891"
OUT = HERE / "index.html"
MANIFEST = HERE / "SOURCE_SVG_POINTERS_v1.json"
SVG_NS = "{http://www.w3.org/2000/svg}"
IDS = ("ssot", "next", "jekyll", "tokens", "parity")
LABELS = ("MissionControl SSOT", "Next / React", "Jekyll / HTML",
          "QPS UI Tokens v1.2", "Release parity")
BRIDGE_SCHEMA = "gbo.ci-spine.svg-provenance-bridge.v1"


def require(value: bool, code: str) -> None:
    if not value:
        raise ValueError("CI_SPINE_SVG_BRIDGE_FIRST_RED:" + code)


def blob_oid(data: bytes) -> str:
    header = ("blob " + str(len(data)) + "\0").encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def parse_source(raw: bytes) -> tuple[str, list[dict], str]:
    require(blob_oid(raw) == EXPECTED_BLOB, "SOURCE_BLOB_DRIFT")
    require(raw.startswith(b"<svg "), "NOT_SVG")
    root = ET.fromstring(raw)
    require(root.tag == SVG_NS + "svg", "SVG_NAMESPACE")
    require(root.get("viewBox") == "0 0 1200 360", "VIEWBOX_MISMATCH")
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        require(tag not in {"script", "foreignObject", "image", "use"}, "ACTIVE_OR_REMOTE_SVG")
        for key, value in el.attrib.items():
            k = key.split("}")[-1].lower()
            require(not k.startswith("on") and k not in {"href", "src"}, "ACTIVE_SVG_ATTRIBUTE")
            require("http:" not in value.lower() and "https:" not in value.lower(), "REMOTE_SVG_REFERENCE")
    children = list(root)
    rectangles = [x for x in children if x.tag == SVG_NS + "rect" and x.get("class") == "box"]
    labels = [x.text for x in children if x.tag == SVG_NS + "text" and x.get("class") == "label"]
    flows = [x for x in children if x.tag == SVG_NS + "path" and "flow" in x.get("class", "").split()]
    require(len(rectangles) == len(IDS) == len(labels) == 5, "NODE_POPULATION")
    require(tuple(labels) == LABELS, "SEMANTIC_LABEL_DRIFT")
    require(len(flows) == 6, "EDGE_POPULATION")
    line_numbers = [n for n, s in enumerate(raw.decode("utf-8").splitlines(), 1)
                    if '<rect class="box"' in s]
    require(len(line_numbers) == 5, "SOURCE_LINE_MAPPING")
    result = []
    for i, rect in enumerate(rectangles):
        try:
            x, y, width, height = (float(rect.get(key, "nan")) for key in
                                   ("x", "y", "width", "height"))
        except ValueError as exc:
            raise ValueError("CI_SPINE_SVG_BRIDGE_FIRST_RED:BAD_GEOMETRY") from exc
        require(all(math.isfinite(z) for z in (x, y, width, height)), "NONFINITE_GEOMETRY")
        require(x >= 0 and y >= 0 and width > 0 and height > 0 and
                x + width <= 1200 and y + height <= 360, "OUT_OF_BOUNDS_RECT")
        rect.set("id", "source-node-" + IDS[i])
        rect.set("data-bridge-id", IDS[i])
        rect.set("tabindex", "0")
        rect.set("role", "button")
        rect.set("aria-label", labels[i] + " - inspect source")
        result.append({
            "id": IDS[i], "label": LABELS[i], "svg_element_id": "source-node-" + IDS[i],
            "source_line": line_numbers[i],
            "source_href": "https://github.com/GBOGEB/pipeline-automation-hub/blob/" +
                           SOURCE_REF + "/" + SOURCE_REL + "#L" + str(line_numbers[i]),
            "geometry": {"x": x, "y": y, "width": width, "height": height},
            "normalized_bbox": [round(x / 1200, 6), round(y / 360, 6),
                                round((x + width) / 1200, 6), round((y + height) / 360, 6)],
            "precision": "SVG_RECT_SOURCE_GEOMETRY",
            "relation": "EXACT_RENDERED_SVG_RECT_FROM_FROZEN_SOURCE",
        })
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    svg = ET.tostring(root, encoding="unicode")
    return svg, result, hashlib.sha256(raw).hexdigest()


STYLE = """
:root{font:14px/1.5 system-ui,Arial,sans-serif;color-scheme:dark;
--bg:#160e20;--panel:#26172f;--line:#62496d;--fg:#f7eff9;--muted:#c8b5d0;--violet:#c89bf0;--blush:#f0b6d3}
*{box-sizing:border-box}body{margin:0;min-width:320px;background:var(--bg);color:var(--fg)}
a{color:var(--blush)}button,input{font:inherit}button{cursor:pointer}
button:focus-visible,input:focus-visible,a:focus-visible,[data-bridge-id]:focus-visible{outline:3px solid #f3ce73;outline-offset:3px}
header,footer{max-width:1580px;margin:auto;padding:20px 24px}
header{border-bottom:1px solid var(--line);display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}
h1{font-size:clamp(24px,3vw,38px);margin:0 0 6px}h2{font-size:18px;margin:0 0 10px}
.sub{color:var(--muted);max-width:940px;margin:0}.stamp{padding:8px;border:1px solid var(--line);border-radius:8px;align-self:start}
.layout{max-width:1580px;margin:auto;padding:20px 24px;display:grid;grid-template-columns:210px minmax(0,1fr) 310px;gap:14px}
.panel{border:1px solid var(--line);border-radius:12px;padding:16px;background:var(--panel);min-width:0}
#objects button{display:block;width:100%;text-align:left;padding:10px;margin:6px 0;border-radius:8px;background:#34223f;color:var(--fg);border:1px solid #62496d}
#objects button[aria-pressed=true]{background:#603973;border-color:var(--blush)}
.toolbar{display:flex;gap:9px;align-items:center;flex-wrap:wrap;margin-bottom:12px}
.toolbar button{background:#3b2847;color:var(--fg);border:1px solid var(--line);padding:6px 12px;border-radius:6px}
.toolbar label{white-space:nowrap}.viewport{width:100%;min-width:0;overflow:auto;background:#1f1726;border:1px solid var(--line);border-radius:8px;min-height:285px;max-height:500px}
#drawing{display:block;height:auto;max-width:none;color:#e7c5ea;background:#211725}
#drawing .box{stroke:#c6a4d9}#drawing .label,#drawing .small{fill:#f4e6f3}
#drawing [data-bridge-id]{cursor:pointer;pointer-events:all;transition:fill .15s}
#drawing [data-bridge-id]:hover{fill:#ad72c1;fill-opacity:.18}
#drawing [data-bridge-id].selected{fill:#ea96c0;fill-opacity:.32;stroke:#f0b6d3;stroke-width:4}
#drawing.flows-off .flow{display:none}#drawing.labels-off .label,#drawing.labels-off .small{display:none}
.code{overflow-wrap:anywhere;font:12px/1.6 ui-monospace,Consolas,monospace}
.k{color:var(--muted);display:block;font-size:12px}.value{font-weight:650;margin:2px 0 13px}
.note{padding:12px;background:#382a3a;border-left:3px solid var(--blush);color:#f4e0ed}
footer{font-size:12px;color:var(--muted);border-top:1px solid var(--line)}
@media(max-width:1050px){.layout{grid-template-columns:180px minmax(0,1fr)}.inspector{grid-column:1/-1}}
@media(max-width:700px){.layout{grid-template-columns:minmax(0,1fr)}.inspector{grid-column:auto}
header,footer{padding:16px}.layout{padding:14px}.viewport{min-height:220px}}
"""


def render(svg: str, nodes: list[dict], source_digest: str) -> bytes:
    rows = "".join('<button type="button" data-choice="' + html.escape(n["id"]) +
                   '" aria-pressed="false">' + html.escape(n["label"]) + "</button>"
                   for n in nodes)
    source_link = "https://github.com/GBOGEB/pipeline-automation-hub/blob/" + SOURCE_REF + "/" + SOURCE_REL
    data = json.dumps({n["id"]: n for n in nodes}, sort_keys=True, separators=(",", ":"))
    data = data.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    page = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'none'; object-src 'none'; frame-src 'none'; img-src data:; base-uri 'none'; form-action 'none'">
<title>CI Spine · JQ09 source ↔ SVG bridge</title><style>@@STYLE@@</style></head>
<body><header><div><h1>Source ↔ diagram</h1>
<p class="sub">JQ09 · a real QPS architecture SVG, rendered as a read-only derivative. Select any box, reveal its exact frozen source line, toggle layers, or zoom without losing provenance.</p></div>
<div class="stamp">FROZEN SVG / SOURCE-BOUND<br>ADVISORY · NO PDF MAPPING · NO ADMISSION</div></header>
<main class="layout"><nav class="panel" aria-label="Diagram objects"><h2>Source objects</h2>
<div id="objects">@@ROWS@@</div><p class="note">Only five visible boxes are mapped. The six connection arrows are visible but not independently claimed as engineering requirements.</p>
<p><a href="../explorer.html">Five-lens CI Explorer</a><br><a href="../notebook.html">Jacquard-style Notebook</a><br><a href="../pointers/index.html">Source pointer atlas</a></p></nav>
<section class="panel" aria-label="Interactive diagram"><h2>QPS web architecture</h2>
<div class="toolbar">
<button type="button" id="zoom-out" aria-label="Zoom out">−</button>
<button type="button" id="zoom-reset">75%</button>
<button type="button" id="zoom-in" aria-label="Zoom in">+</button>
<label><input id="toggle-flows" type="checkbox" checked> Connections</label>
<label><input id="toggle-labels" type="checkbox" checked> Labels</label>
</div>
<div class="viewport" id="viewport" tabindex="0" aria-label="Scrollable diagram with source-linked objects">@@SVG@@</div>
<p class="sub">The diagram's geometry comes directly from the committed SVG. Overlay IDs and selection are added only in this review derivative.</p>
</section>
<aside class="panel inspector" aria-label="Provenance inspector"><h2>Selected source</h2>
<span class="k">Object</span><p id="selected-label" class="value"></p>
<span class="k">Source line</span><p id="selected-line" class="value"></p>
<span class="k">SVG rectangle · viewBox coordinate</span><p id="selected-bbox" class="value code"></p>
<span class="k">Precision</span><p class="value">SVG_RECT_SOURCE_GEOMETRY</p>
<a id="source-link" rel="noopener noreferrer" target="_blank">Open immutable source line</a>
<p class="note" id="selection-status" role="status" aria-live="polite">Select a mapped object.</p>
<span class="k">Source blob OID</span><p class="value code">@@BLOB@@</p>
<span class="k">Source SHA-256</span><p class="value code">@@DIGEST@@</p>
<span class="k">Frozen source commit</span><p class="value code">@@COMMIT@@</p>
<a href="@@SOURCE_LINK@@" target="_blank" rel="noopener noreferrer">Full source SVG</a>
<p class="sub">This maps a source SVG rectangle to its rendered SVG rectangle. It does <strong>not</strong> locate a PDF page, optional-content group, engineering object ID or approval decision.</p>
</aside></main>
<footer>JQ09 · read-only source-derived geometry · no external scripts or network requests during viewing · no watchers or workflow dispatch.</footer>
<script>
(function(){
"use strict";
const records=Object.freeze(@@DATA@@);
const svg=document.getElementById("drawing");
const buttons=Array.from(document.querySelectorAll("#objects [data-choice]"));
let active="ssot",scale=.75;
function choose(id,withHash){
 if(!Object.prototype.hasOwnProperty.call(records,id)){
   document.getElementById("selection-status").textContent="UNMAPPED: no verified source object";
   return;
 }
 active=id;
 const n=records[id];
 document.querySelectorAll("[data-bridge-id]").forEach(e=>e.classList.toggle("selected",e.getAttribute("data-bridge-id")===id));
 buttons.forEach(b=>b.setAttribute("aria-pressed",String(b.dataset.choice===id)));
 document.getElementById("selected-label").textContent=n.label;
 document.getElementById("selected-line").textContent=String(n.source_line);
 const g=n.geometry;
 document.getElementById("selected-bbox").textContent="x="+g.x+", y="+g.y+", width="+g.width+", height="+g.height;
 document.getElementById("source-link").href=n.source_href;
 document.getElementById("selection-status").textContent="SOURCE-BOUND: element "+n.svg_element_id+"; no PDF region mapping";
 if(withHash)location.hash="node="+encodeURIComponent(id);
}
function zoom(v){
 scale=Math.max(.45,Math.min(2.2,Number(v)||.75));
 svg.style.width=String(Math.round(1200*scale))+"px";
 document.getElementById("zoom-reset").textContent=String(Math.round(scale*100))+"%";
}
buttons.forEach(b=>b.addEventListener("click",()=>choose(b.dataset.choice,true)));
svg.querySelectorAll("[data-bridge-id]").forEach(el=>{
 el.addEventListener("click",()=>choose(el.getAttribute("data-bridge-id"),true));
 el.addEventListener("keydown",ev=>{if(ev.key==="Enter"||ev.key===" "){ev.preventDefault();choose(el.getAttribute("data-bridge-id"),true);}});
});
document.getElementById("zoom-in").addEventListener("click",()=>zoom(scale+.2));
document.getElementById("zoom-out").addEventListener("click",()=>zoom(scale-.2));
document.getElementById("zoom-reset").addEventListener("dblclick",()=>zoom(.75));
document.getElementById("toggle-flows").addEventListener("change",e=>svg.classList.toggle("flows-off",!e.target.checked));
document.getElementById("toggle-labels").addEventListener("change",e=>svg.classList.toggle("labels-off",!e.target.checked));
window.addEventListener("hashchange",()=>{const p=new URLSearchParams(location.hash.slice(1));choose(p.get("node"),false);});
zoom(.75);
const p=new URLSearchParams(location.hash.slice(1));
choose(p.get("node")||"ssot",false);
})();
</script></body></html>
"""
    for key, value in {
        "@@STYLE@@": STYLE, "@@ROWS@@": rows, "@@SVG@@": svg,
        "@@BLOB@@": EXPECTED_BLOB, "@@DIGEST@@": source_digest,
        "@@COMMIT@@": SOURCE_REF, "@@SOURCE_LINK@@": html.escape(source_link, quote=True),
        "@@DATA@@": data,
    }.items():
        page = page.replace(key, value)
    page = page.replace('<svg xmlns=', '<svg id="drawing" xmlns=', 1)
    require(page.count('id="drawing"') == 1, "MISSING_DRAWING")
    require("document.write" not in page, "UNSAFE_RENDERER")
    return page.encode("utf-8")


def project(raw: bytes) -> tuple[bytes, bytes]:
    svg, nodes, source_digest = parse_source(raw)
    output = render(svg, nodes, source_digest)
    digest = hashlib.sha256(output).hexdigest()
    manifest = {
        "schema": BRIDGE_SCHEMA,
        "kind": "DERIVED_READONLY_SVG_OBJECT_NAVIGATION",
        "source": {"repository": "GBOGEB/pipeline-automation-hub",
                   "path": SOURCE_REL, "commit_sha": SOURCE_REF,
                   "git_blob_oid": EXPECTED_BLOB, "sha256": source_digest},
        "output": {"path": "docs/ci-spine/svg-bridge/index.html", "sha256": digest,
                   "bytes": len(output), "media_type": "text/html"},
        "elements": nodes, "node_count": len(nodes), "flow_path_count": 6,
        "precision": "SVG_RECT_SOURCE_GEOMETRY",
        "pdf_mapping": "UNMAPPED_NO_VERIFIED_BINARY",
        "authority_transfer": False, "merge_authorized": False,
        "execution": False, "external_runtime_dependency": False,
    }
    return output, (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify committed derivative and manifest bytes")
    args = parser.parse_args(argv)
    output, manifest = project(SOURCE.read_bytes())
    if args.check:
        require(OUT.exists() and OUT.read_bytes() == output, "HTML_STALE")
        require(MANIFEST.exists() and MANIFEST.read_bytes() == manifest, "MANIFEST_STALE")
        print("CI_SPINE_SVG_BRIDGE_CHECK=PASS; source_blob=" + EXPECTED_BLOB)
    else:
        OUT.write_bytes(output)
        MANIFEST.write_bytes(manifest)
        print("CI_SPINE_SVG_BRIDGE_BUILD=PASS; nodes=5; flows=6")
    return 0


if __name__ == "__main__":
    sys.exit(main())
