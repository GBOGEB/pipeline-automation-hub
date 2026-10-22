"""W+4 read-only governance/SPINE/DAG/SIPOC projection.

A consumer of existing owner contracts, not an authority or a dispatcher.
No network, environment credentials, current-state inference or source mutation.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import re
from collections import deque
from pathlib import Path

SHA = re.compile(r"[0-9a-f]{40}\Z")
KINDS = frozenset({"CONTROL","SOURCE","EVIDENCE","HUMAN","GATE","ADMISSION",
                   "OBSERVATION","CONSUMER","ANALYSIS","REVIEW_VIEW"})
AUTH = ("GBOGEB/ABACUS","GBOGEB/CODEX","GBOGEB/pipeline-automation-hub")
STATE = frozenset({"OWNER_BLOCKED","UNQUALIFIED","MAIN_SOURCE_OBSERVED",
                   "PR_OPEN","NOT_TESTED","HISTORICAL_GREEN_ONLY","QUEUED",
                   "NOT_VERIFIED","HOLD","PARTIAL_QUEUED","OBSERVED_HISTORICAL",
                   "WITHHELD","PARTIAL_OBSERVED","LATEST_CI_UNKNOWN","DEFERRED"})
REQUIRED_GATE = frozenset({"effective_owner_controls","failed_RED_canary",
                            "native_exact_head_checks","eligible_independent_approval"})


def demand(ok, why):
    if not ok:
        raise ValueError("SPINE_W4_HOLD: " + why)


def validate(d):
    demand(isinstance(d,dict) and d.get("schema") ==
           "missioncontrol.spine.governance_dag_sipoc.v1","source schema")
    demand(d.get("intent") == "READ_ONLY_CONTROL_VIEW_NOT_NEW_SSOT" and
           d.get("merge_admission") == "HOLD" and
           d.get("formal_credit_delta") == 0 and
           d.get("authority_transfer") is False and
           d.get("dispatch_authorized") is False,"authority promotion")
    source=d.get("source_snapshot")
    demand(isinstance(source,dict) and source.get("repository")=="GBOGEB/pipeline-automation-hub"
           and isinstance(source.get("sha"),str) and SHA.fullmatch(source["sha"])
           and source.get("freshness")=="SNAPSHOT_NOT_LIVE","source provenance")
    refs=d.get("authority_refs")
    demand(isinstance(refs,list) and len(refs)>=5 and
           all(isinstance(x,dict) and isinstance(x.get("repo"),str)
               and isinstance(x.get("path"),str) and
               not x["path"].startswith("/") and ".." not in x["path"].split("/")
               and x.get("authority") for x in refs), "canonical refs")
    demand(len(set((x["repo"],x["path"]) for x in refs)) == len(refs),
           "duplicate authority ref")
    all_nodes=d.get("nodes")
    demand(isinstance(all_nodes,list) and len(all_nodes)>=15,"node population")
    nodes={}
    for n in all_nodes:
        demand(isinstance(n,dict) and isinstance(n.get("id"),str) and
               re.fullmatch(r"[A-Z][A-Z0-9_]*",n["id"]) and
               n["id"] not in nodes and
               n.get("owner") in AUTH and n.get("kind") in KINDS and
               n.get("state") in STATE and
               type(n.get("rank")) is int and 0<=n["rank"]<=8 and
               type(n.get("lane")) is int and 0<=n["lane"]<=7 and
               isinstance(n.get("label"),str) and n["label"],"node identity")
        nodes[n["id"]]=n
    required=("ABACUS_POLICY","HUB_POLICY","CODEX_POLICY","HUB_REPAIR",
              "CODEX_REPAIR","ABACUS_CANARY","HUB_CANARY","HUB_PR_CI",
              "CODEX_PR_CI","HUB_REVIEW","CODEX_REVIEW","HUB_ADMISSION",
              "CODEX_ADMISSION","HUB_MAIN_CI","CODEX_MAIN_CI","CENSUS",
              "MYCELIUM","TELEMETRY","G3C","PUBLICATION")
    demand(set(nodes)==set(required),"fixed controls incomplete")
    demand(all(nodes[n]["state"]=="HOLD" for n in ("HUB_ADMISSION","CODEX_ADMISSION"))
           and nodes["MYCELIUM"]["state"]=="WITHHELD"
           and nodes["PUBLICATION"]["state"]=="DEFERRED","false-green snapshot")
    edges=d.get("edges")
    demand(isinstance(edges,list) and len(edges)>=20,"edge population")
    forward=[];feedback=[];seen=set()
    for edge in edges:
        demand(isinstance(edge,dict) and edge.get("from") in nodes and
               edge.get("to") in nodes and edge["from"]!=edge["to"] and
               edge.get("binding")=="DECLARED_DEPENDENCY" and
               isinstance(edge.get("condition"),str) and edge["condition"] and
               edge.get("type") in ("FEEDFORWARD","FEEDBACK_NEXT_PULSE"),
               "edge semantics/identity")
        t=(edge["from"],edge["to"],edge["type"])
        demand(t not in seen,"duplicate edge")
        seen.add(t)
        if edge["type"]=="FEEDFORWARD":
            demand(nodes[edge["from"]]["rank"] < nodes[edge["to"]]["rank"],
                   "forward edge violates stage order")
            forward.append(edge)
        else:
            demand(edge["from"] in ("TELEMETRY","G3C") and
                   edge["to"] in ("HUB_REPAIR","CODEX_REPAIR","CENSUS"),
                   "feedback must cross into NEXT pulse")
            feedback.append(edge)
    demand(len(feedback)>=2,"missing feedback control")
    indeg={n:0 for n in nodes}; adj={n:[] for n in nodes}
    for e in forward:
        adj[e["from"]].append(e["to"])
        indeg[e["to"]]+=1
    queue=deque(sorted(n for n,k in indeg.items() if k==0))
    order=[]
    while queue:
        n=queue.popleft()
        order.append(n)
        for nxt in sorted(adj[n]):
            indeg[nxt]-=1
            if indeg[nxt]==0: queue.append(nxt)
    demand(len(order)==len(nodes),"cycle in within-pulse DAG")
    sipoc=d.get("sipoc")
    demand(isinstance(sipoc,list) and len(sipoc)==6 and
           {x.get("id") for x in sipoc} == {
             "OWNER_PROTECTION","SOURCE_REPAIR","PROOF_CUSTODY",
             "FEDERATION","ANALYTICS","RELEASE"}, "SIPOC population")
    for row in sipoc:
        demand(all(isinstance(row.get(x),str) and row[x] for x in (
            "supplier","input","process","output","customer","authority")),
            "SIPOC missing owner/contract")
    telemetry=d.get("telemetry_contract")
    demand(isinstance(telemetry,dict) and all(isinstance(telemetry.get(k),list)
           and telemetry[k] for k in ("identities","quality_states","measures","unsupported")),
           "telemetry contract missing")
    demand(set(("repository","source_sha","run_id","attempt","job_id",
                "artifact_sha256"))<=set(telemetry["identities"]),"incomplete native identity")
    controls=d.get("spine_rules") or {}
    demand(controls.get("no_cycle_within_pulse") is True and
           controls.get("feedback_only_next_pulse") is True and
           set(controls.get("merge_requires",[]))==REQUIRED_GATE and
           controls.get("publication_is_not_engineering_acceptance") is True,
           "admission gate weakened")
    named=d.get("named_counts") or {}
    demand(named.get("repositories_sampled")==6 and
           named.get("qualified_owner_controls")==0 and
           named.get("governed_issue_closures")==0 and
           named.get("source_repairs_verified_as_governed")==0,
           "false governed credit")
    return {"schema":"missioncontrol.spine.w4.qa_receipt.v1",
            "source_sha":source["sha"],"node_count":len(nodes),
            "edge_count":len(forward)+len(feedback),
            "forward_edge_count":len(forward),"next_pulse_feedback_count":len(feedback),
            "sipoc_processes":len(sipoc),"topological_order":order,
            "gate":"HOLD","native_verification":"NOT_EXECUTED_BY_THIS_PROJECTION",
            "owner_controls_qualified":0,"governed_issue_closures":0,
            "consumer_acceptance":"WITHHELD","authority_transfer":False}


def mermaid(d):
    lines=["flowchart LR"]
    for n in d["nodes"]:
        label=n["label"].replace('"',"'")
        lines.append(f'  {n["id"]}["{label}"]')
    for e in d["edges"]:
        if e["type"]=="FEEDFORWARD":
            lines.append(f'  {e["from"]} --> {e["to"]}')
        else:
            lines.append(f'  {e["from"]} -. "N+1 only" .-> {e["to"]}')
    lines.append("  %% Dotted arrows are NEXT-PULSE transitions; never in current-pulse DAG.")
    return "\n".join(lines)+"\n"


def svg(d):
    nodes=d["nodes"]; node_by_id={n["id"]:n for n in nodes}
    def xy(n):
        return 24+int(n["rank"])*212, 52+int(n["lane"])*104
    edges=[]
    for e in d["edges"]:
        if e["type"]!="FEEDFORWARD":continue
        a,b=node_by_id[e["from"]],node_by_id[e["to"]]
        x,y=xy(a);xx,yy=xy(b)
        edges.append(f'<path d="M{x+174},{y+27} L{xx-7},{yy+27}" fill="none" stroke="#8a9aae" stroke-width="1.5" marker-end="url(#arr)"/>')
    blocks=[]
    for n in nodes:
        x,y=xy(n)
        fill="#f0e3cf" if n["kind"] in ("CONTROL","GATE","ADMISSION") else (
             "#daebe9" if n["kind"] in ("EVIDENCE","OBSERVATION","CONSUMER") else "#e8eaf3")
        blocks.append(f'<g><rect x="{x}" y="{y}" width="174" height="54" rx="8" fill="{fill}" stroke="#40546c"/>'
                      f'<text x="{x+8}" y="{y+17}" font-size="11" font-weight="600">{html.escape(n["label"])}</text>'
                      f'<text x="{x+8}" y="{y+34}" font-size="10">{html.escape(n["state"])}</text></g>')
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1530 730" role="img" '
            'aria-label="W4 governance source-to-admission-to-telemetry DAG; feedback in next pulse only">'
            '<defs><marker id="arr" markerWidth="7" markerHeight="7" refX="5" refY="3" orient="auto">'
            '<path d="M0,0L6,3L0,6" fill="none" stroke="#8a9aae"/></marker></defs>'
            '<text x="24" y="22" font-size="17" font-weight="700" fill="#172338">W4 architecture: authority / evidence / admission / telemetry</text>'
            + "".join(edges)+"".join(blocks)+"</svg>\n")


def sipoc_md(d):
    headers=("Supplier","Inputs","Process","Outputs","Customer","Authority")
    rows=["# W4 separate SIPOC — source and process ownership","",
          "Projection only: owner rulesets, CODEX MYCELIUM, and Mission Control remain canonical.","",
          "| "+" | ".join(headers)+" |","| "+" | ".join("---" for _ in headers)+" |"]
    for x in d["sipoc"]:
        rows.append("| "+" | ".join(str(x[k]).replace("|","/") for k in (
            "supplier","input","process","output","customer","authority"))+" |")
    return "\n".join(rows)+"\n"


def html_view(d, receipt, graph_svg):
    rows="".join("<tr>"+"".join(f"<td>{html.escape(str(n[k]))}</td>"
        for k in ("id","label","owner","state","kind"))+"</tr>" for n in d["nodes"])
    ts="".join(f"<li>{html.escape(x)}</li>" for x in d["telemetry_contract"]["measures"])
    controls="".join(f"<li>{html.escape(x)}</li>" for x in d["spine_rules"]["merge_requires"])
    source=html.escape(receipt["source_sha"])
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CODE PURPLE W4 — SPINE architecture and SIPOC</title>
<style>body{{margin:0;background:#f7f8fb;color:#172338;font:15px/1.5 system-ui,sans-serif}}main{{max-width:1100px;padding:24px;margin:auto}}.panel{{background:white;border:1px solid #d6dce6;border-radius:12px;margin:16px 0;padding:18px}}.diagram{{overflow-x:auto}}.diagram svg{{display:block;max-width:none;width:1500px;height:auto}}table{{border-collapse:collapse;width:100%}}th,td{{text-align:left;vertical-align:top;border-bottom:1px solid #e0e4ed;padding:7px;font-size:13px}}code{{overflow-wrap:anywhere}}</style>
</head><body><main><h1>W4 · Governance SPINE and dependency control</h1>
<p>This is an architectural review view, <strong>not</strong> CODEX ADR-0002 SPINE-core and not a second engineering or merge authority.</p>
<section class="panel"><h2>Admission remains HOLD</h2><p>Snapshots are not live. No native CI, independent approval, RED canary, owner ruleset installation or root closure is attested here.</p>
<p>Source default SHA: <code>{source}</code></p></section>
<section class="panel diagram"><h2>Within-pulse DAG (feedforward only)</h2>{graph_svg}
<p>Dotted feedback edges appear in the downloadable Mermaid model and mean N+1 only. They are excluded from within-pulse acyclicity and from admission shortcuts.</p></section>
<section class="panel"><h2>Source-controlled node identities</h2><div style="overflow-x:auto"><table><thead><tr><th>ID</th><th>Purpose</th><th>Owner</th><th>Snapshot state</th><th>Class</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<section class="panel"><h2>Non-compensating merge gates</h2><ul>{controls}</ul><p>Measured coverage, graph completeness or consumer tests cannot bypass governance and source-owner approvals.</p></section>
<section class="panel"><h2>Telemetry is separate from authority</h2><ul>{ts}</ul><p>Missing independent trials, fleet capacity and PCA/BT stability remain UNKNOWN rather than zero.</p></section>
<section class="panel"><h2>SIPOC</h2><p>See <code>spine-sipoc.md</code> for the six independently owned process chains. The JSON contract is a review-only projection of existing repo contracts.</p></section>
</main></body></html>'''


def build(d, out:Path):
    receipt=validate(d)
    raw=json.dumps(receipt,indent=2,sort_keys=True)+"\n"
    artifacts={
        "spine-control.json":raw.encode(),
        "spine-control.svg":svg(d).encode(),
        "spine-control.mmd":mermaid(d).encode(),
        "spine-sipoc.md":sipoc_md(d).encode()
    }
    artifacts["spine-control.html"]=html_view(d,receipt,artifacts["spine-control.svg"].decode()).encode()
    out.mkdir(parents=True,exist_ok=True)
    for name,content in artifacts.items():(out/name).write_bytes(content)
    manifest={"schema":"missioncontrol.spine.w4.artifact_manifest.v1",
              "source_sha":receipt["source_sha"],"gate":"HOLD",
              "artifacts_sha256":{k:hashlib.sha256(v).hexdigest() for k,v in sorted(artifacts.items())}}
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
    return manifest


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--contract",type=Path,default=Path(__file__).with_name("control_view.json"))
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    result=build(json.loads(a.contract.read_text(encoding="utf-8")),a.out)
    print("SPINE_W4=SOURCE_PROJECTION_ONLY; ARTIFACTS=%d; ADMISSION=HOLD"%
          len(result["artifacts_sha256"]))
