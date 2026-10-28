"""W380 process-family projections: same 70 lane/stage IDs in matrix, SIPOC and DAG.

All stage definitions, probe levels and SIPOC cells are imported from the
existing JADE lifecycle owner. No stage scores, metric registries or approvals
are derived. G.S9 -> A.S0 is NEXT_PULSE only, never a same-pulse dependency.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from metric_atlas import lane_lifecycle

SCHEMA = "jade.w380.lane-process.receipt.v1"
STAGES = lane_lifecycle.STAGES
LANES = tuple(lane_lifecycle.LANES)
OWNER = lane_lifecycle.OWNER

# Cross-lane contract edges are always earlier-stage -> later-stage.
# These are proposed *process* relationships, not evidence of job dispatch.
INTERFACES = (
    ("C","S0_PLAN","G","S1_CODE","TRIAGE"),
    ("A","S2_BUILD","B","S3_TEST","SOURCE_SNAPSHOT"),
    ("A","S2_BUILD","D","S3_TEST","OID_INPUT"),
    ("B","S3_TEST","G","S4_SECURE","FIRST_RED"),
    ("C","S3_TEST","D","S4_SECURE","BLOCKER_GRAPH"),
    ("D","S3_TEST","F","S5_RELEASE","GRAPH_PARITY"),
    ("E","S3_TEST","F","S5_RELEASE","OWNER_EVIDENCE"),
    ("G","S4_SECURE","F","S5_RELEASE","PROVENANCE"),
    ("F","S5_RELEASE","G","S6_DEPLOY","PUBLICATION_GATE"),
    ("A","S8_MONITOR","G","S9_CONTROL","SCAN_TELEMETRY"),
    ("B","S8_MONITOR","G","S9_CONTROL","RECURRENCE"),
    ("F","S8_MONITOR","G","S9_CONTROL","ACK_LIVENESS"),
    ("E","S8_MONITOR","G","S9_CONTROL","ENGINEERING_HOLD"),
)


def require(ok,msg):
    if not ok:
        raise ValueError(msg)


def identifier(lane,stage):
    require(lane in LANES and stage in STAGES,"INVALID_LANE_STAGE")
    return lane+"."+stage


def project(snapshot, interfaces=INTERFACES):
    src=lane_lifecycle.project(snapshot)
    require(src["merge_admission"]=="HOLD" and
            src["real_lane_maturity_verified"] is False,"LANE_OWNER_AUTHORITY_DRIFT")
    nodes=[]
    for cell in src["cells"]:
        nodes.append({
            "id":identifier(cell["lane"],cell["stage"]),
            "lane":cell["lane"],"stage":cell["stage"],
            "stage_title":cell["stage_title"],"owner":cell["owner"],
            "activity":cell["activity"],"status":cell["status"],
            "maturity_level":cell["maturity_level"],
            "canonical_probe_ids":cell["canonical_probe_ids"],
            "source_head":cell["source_head"],
            "receipt_sha256":cell["receipt_sha256"],
            "evidence_url":cell["evidence_url"],
            "sipoc":OWNER.SIPOC[cell["stage"]]})
    require(len(nodes)==70 and len({n["id"] for n in nodes})==70,"CANONICAL_CELL_POPULATION_DRIFT")
    edges=[]
    for lane in LANES:
        for a,b in zip(STAGES,STAGES[1:]):
            edges.append({"from":identifier(lane,a),"to":identifier(lane,b),
                          "relation":"STAGE_FEEDFORWARD"})
    require(isinstance(interfaces,(tuple,list)) and len(interfaces)<=20,"UNBOUNDED_INTERFACES")
    seen=set()
    for member in interfaces:
        require(type(member) in (list,tuple) and len(member)==5,"BAD_INTERFACE_SHAPE")
        a,sa,b,sb,kind=member
        left,right=identifier(a,sa),identifier(b,sb)
        require(STAGES.index(sa)<STAGES.index(sb) and a!=b,"BACK_EDGE_OR_SELF_INTERFACE")
        require(type(kind) is str and kind.isupper() and kind.replace("_","").isalpha(),
                "BAD_INTERFACE_LABEL")
        key=(left,right)
        require(key not in seen,"DUPLICATE_INTERFACE")
        seen.add(key)
        edges.append({"from":left,"to":right,"relation":"INTERFACE_"+kind})
    temporal={"from":identifier("G","S9_CONTROL"),"to":identifier("A","S0_PLAN"),
              "relation":"FEEDBACK_NEXT_PULSE"}
    edges.append(temporal)
    topo=OWNER.topo_layers([n["id"] for n in nodes],
          [(e["from"],e["to"],"FEEDBACK_NEXT_PULSE" if e["relation"]=="FEEDBACK_NEXT_PULSE"
           else "FEEDFORWARD") for e in edges])
    require(len({key for level in topo for key in level})==len(nodes),"DAG_NODE_LOSS")
    report={"schema":SCHEMA,"source_crosswalk_sha256":src["digest_sha256"],
            "cohort":src["cohort"],"stage_owner":src["stage_owner"],
            "node_ids_stable_across_views":True,
            "nodes":nodes,"edges":edges,
            "topological_layers":topo,
            "graph_metrics":{"nodes":len(nodes),"within_pulse_edges":len(edges)-1,
                             "cross_lane_edges":len(interfaces),
                             "next_pulse_edges":1,"actual_worker_runs":None,
                             "actual_queue_p95_seconds":None},
            "views":["DAG","SIPOC","SPINE","MATRIX"],
            "merge_admission":"HOLD","authority_transfer":False}
    report["sha256"]=lane_lifecycle._digest(report)
    return report


def mermaid(report,view):
    require(view in ("DAG","SIPOC","SPINE"),"UNKNOWN_GRAPH_VIEW")
    aliases={n["id"]:"N"+str(i) for i,n in enumerate(report["nodes"])}
    output=["flowchart LR","%% identical node and edge IDs, projection: "+view]
    for n in report["nodes"]:
        val=(n["lane"]+" "+n["stage"].split("_")[0]+" "+n["activity"] if view=="DAG"
             else n["lane"]+" "+n["stage"].split("_")[0]+" SIPOC:S/I/P/O/C" if view=="SIPOC"
             else n["owner"]+" :: "+n["stage_title"])
        val=val.replace('"',"'").replace("<","(").replace(">",")")
        output.append("  "+aliases[n["id"]]+'["'+val[:105]+'"]')
    for e in report["edges"]:
        arrow="-.->" if e["relation"]=="FEEDBACK_NEXT_PULSE" else "-->"
        output.append("  "+aliases[e["from"]]+" "+arrow+" "+aliases[e["to"]])
    return "\n".join(output)+"\n"


def html_view(report):
    """Self-contained inspectable 70-cell matrix; never interpolate data as HTML."""
    raw=json.dumps({"nodes":report["nodes"],"edges":report["edges"]},
                   separators=(",",":"),ensure_ascii=True).replace("</","<\\/")
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>W380 Lane × DevOps Lifecycle</title>
<style>
:root{font:14px system-ui,sans-serif;color-scheme:light dark}
body{margin:2rem auto;max-width:1200px;padding:0 1.2rem;line-height:1.45}
h1{letter-spacing:-.03em} .sub{opacity:.72} .toolbar{display:flex;gap:1rem;flex-wrap:wrap;margin:1.5rem 0}
select,button{font:inherit;padding:.6rem;border:1px solid #8996a4;border-radius:.5rem;background:Canvas;color:CanvasText}
button{cursor:pointer;text-align:left}button:focus-visible{outline:3px solid #6086ed}
.matrix{display:grid;grid-template-columns:120px repeat(10,minmax(85px,1fr));min-width:1050px;gap:4px}
.matrix>div,.matrix>button{padding:.6rem;border-radius:.3rem;border:1px solid #9099a355}
.matrix>.head{font-weight:700;background:color-mix(in srgb,CanvasText 7%,Canvas)}
.unknown{border-style:dashed!important}.bad{background:#f7c4c4;color:#562e2e}
.good{background:#d1f3db;color:#1c5030}.panel{overflow:auto;max-width:100%}
#detail{white-space:pre-wrap;overflow-wrap:anywhere;border:1px solid #8996a4;padding:1rem;border-radius:10px}
@media(max-width:540px){body{margin:1rem auto}.toolbar{display:block}.toolbar label{display:block;margin-bottom:.8rem}}
</style></head><body>
<h1>W380 · Lane / stage / evidence</h1>
<p class="sub">Seven disjoint work lanes × ten canonical JADE stages. Read-only.
UNKNOWN is never PASS. A declared green observation is not maturity or merge approval.</p>
<div class="toolbar"><label>Lane <select id="lane"><option value="ALL">All lanes</option></select></label>
<label>Stage <select id="stage"><option value="ALL">All stages</option></select></label></div>
<div class="panel"><div class="matrix" id="matrix" role="group" aria-label="Stage evidence matrix"></div></div>
<h2>Object BIOS / SIPOC</h2><pre id="detail" tabindex="0">Select a lane-stage cell.</pre>
<p class="sub">Temporal G.S9 CONTROL → A.S0 PLAN applies to NEXT pulse only.
Native queue timing, worker capacity, controller ACK and release credit: UNKNOWN.</p>
<script>
const M='''+raw+''';
const stageKeys=[...new Set(M.nodes.map(n=>n.stage))];
const laneKeys=[...new Set(M.nodes.map(n=>n.lane))];
const lane=document.getElementById("lane"),stage=document.getElementById("stage");
const grid=document.getElementById("matrix"),detail=document.getElementById("detail");
function el(tag,cls,s){const e=document.createElement(tag);if(cls)e.className=cls;if(s!==undefined)e.textContent=s;return e}
for(const k of laneKeys){const o=el("option","",k);o.value=k;lane.appendChild(o)}
for(const k of stageKeys){const o=el("option","",k);o.value=k;stage.appendChild(o)}
function render(){grid.replaceChildren();
 const activeLane=lane.value,activeStage=stage.value;
 const heads=["Lane",...stageKeys];
 for(const h of heads)grid.appendChild(el("div","head",h));
 for(const l of laneKeys){if(activeLane!=="ALL"&&activeLane!==l)continue;
  grid.appendChild(el("div","head",l));
  for(const s of stageKeys){const n=M.nodes.find(x=>x.lane===l&&x.stage===s);
   const cls=n.status==="OBSERVED_PASS_UNVERIFIED"?"good":n.status==="OBSERVED_FAIL_HOLD"?"bad":"unknown";
   const b=el("button",cls,n.status==="UNKNOWN"?"? UNKNOWN":n.status==="OBSERVED_PASS_UNVERIFIED"?"OBSERVED +":"HOLD");
   b.disabled=activeStage!=="ALL"&&activeStage!==s;
   b.setAttribute("aria-label",n.id+" "+n.status);
   b.addEventListener("click",()=>{detail.textContent=JSON.stringify(n,null,2)});
   grid.appendChild(b);
  }
 }
}
lane.addEventListener("change",render);stage.addEventListener("change",render);render();
</script></body></html>'''


def emit(snapshot,out):
    report=project(snapshot)
    folder=Path(out);folder.mkdir(parents=True,exist_ok=True)
    assets={"lane-process.json":json.dumps(report,indent=2,sort_keys=True)+"\n",
            "matrix.html":html_view(report)}
    for view in ("DAG","SIPOC","SPINE"):
        assets["graph_"+view.lower()+".mmd"]=mermaid(report,view)
    manifest={"schema":"jade.w380.lane-process.manifest.v1",
              "source_crosswalk_sha256":report["source_crosswalk_sha256"],
              "files_sha256":{},"merge_admission":"HOLD","authority_transfer":False}
    for name,data in assets.items():
        blob=data.encode("utf-8")
        (folder/name).write_bytes(blob)
        manifest["files_sha256"][name]=hashlib.sha256(blob).hexdigest()
    (folder/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",
                                         encoding="utf-8",newline="\n")
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshot",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args(argv)
    r=emit(json.loads(a.snapshot.read_text(encoding="utf-8")),a.out)
    print(json.dumps({"nodes":len(r["nodes"]),"edges":len(r["edges"]),
                      "authority":r["merge_admission"]},sort_keys=True))


if __name__=="__main__":
    main()
