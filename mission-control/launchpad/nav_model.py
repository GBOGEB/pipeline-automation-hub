#!/usr/bin/env python3
"""Fail-closed, deterministic MissionControl graph/queue projection (no dispatch)."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

HERE=Path(__file__).resolve().parent
CONFIG=HERE/"MISSIONCONTROL_NAV_SOURCES_v1.json"
SHA=re.compile(r"[0-9a-f]{40}\Z")
KINDS={"CONTROL","PROCESS","REPOSITORY","GATEWAY","EVIDENCE","VIEW"}
RELATIONS={"DEPENDS_ON","DECLARED_ROUTE","EVIDENCE","ASSOCIATION","FEEDBACK"}
BINDINGS={"DECLARED","RECEIPT"}
DAG_TYPES={"DEPENDS_ON"}
MUTATION_FIELDS=("mutation_enabled","browser_apply_allowed","remote_dispatch_enabled","authority_transfer","security_waiver","qps_engineering_acceptance")

def require(ok,why):
    if not ok:raise ValueError("MC_NAV_HOLD:"+why)

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False)

def validate(d):
    require(d.get("schema")=="missioncontrol.launchpad.federated_architecture.v1","schema")
    p=d.get("policy",{});s=d.get("snapshot",{})
    require(p.get("read_only") is True and p.get("merge_admission")=="HOLD","admission")
    require(all(p.get(k) is False for k in MUTATION_FIELDS),"authority/mutation")
    require(p.get("enabled_mutation_transports")==[],"enabled transport")
    require(p.get("pages_publisher")=="mission-control/federation-atlas/pages_portal.py","publisher authority")
    require(p.get("code_purple_bd_registry")=="mission-control/federation-atlas/CODE_PURPLE_BD_QUEUE_v1.json","BD SSOT")
    require(s.get("kind")=="NONATOMIC_SOURCE_POINTER_READBACK" and s.get("hosted_url_verified") is False,"snapshot")
    require(s.get("live_runner_capacity") is None and s.get("accepted_n") is None,"unproved telemetry")
    require(SHA.fullmatch(s.get("basis_sha","")) is not None,"basis SHA")
    repos=d.get("repositories",[])
    ids=[r.get("id") for r in repos]
    require(len(repos)>=5 and len(set(ids))==len(ids) and "hub" in ids,"repo identities")
    for r in repos:
        require(r.get("name","").startswith("GBOGEB/") and SHA.fullmatch(r.get("sha","")) is not None,"repo SHA")
        require(r.get("public_class") in ("PUBLIC_METADATA","METADATA_ONLY_OWNER_PUBLICATION_REVIEW"),"publish scope")
        require(isinstance(r.get("role"),str) and bool(r["role"]),"repo role")
    for srow in d.get("source_inputs",[]):
        require(srow.get("repo") in [r["name"] for r in repos] and SHA.fullmatch(srow.get("blob_sha","")) is not None,"source blob")
        require(bool(srow.get("path")) and ".." not in srow["path"],"source path")
    nodes=d.get("nodes",[]); edges=d.get("edges",[])
    node_ids={n.get("id") for n in nodes}
    require(len(node_ids)==len(nodes) and len(nodes)>=10,"node inventory")
    for n in nodes:
        require(n.get("kind") in KINDS and type(n.get("column")) is int and type(n.get("row")) is int,"node kind/grid")
        require(n.get("id") and n.get("label"),"node label")
    adjacency={id:[] for id in node_ids}
    for e in edges:
        a,b=e.get("from"),e.get("to")
        require(a in node_ids and b in node_ids and a!=b,"dangling/self graph edge")
        require(e.get("relation") in RELATIONS and e.get("binding") in BINDINGS,"edge type")
        require(bool(e.get("basis")) and bool(e.get("detail")),"untraceable edge")
        if e["relation"]=="FEEDBACK":
            require(e.get("from")=="pages" and e.get("to")=="intake","feedback must be next pulse")
        if e["relation"] in DAG_TYPES:adjacency[a].append(b)
    require(any(e["binding"]=="RECEIPT" for e in edges),"no historical receipt anchors")
    require(any(e["relation"]=="FEEDBACK" for e in edges),"no recursive control edge")
    # A universal graph may have cycles. Only the executable dependency projection MUST be a DAG.
    indeg={id:0 for id in node_ids}
    for targets in adjacency.values():
        for target in targets:indeg[target]+=1
    ready=sorted(n for n,v in indeg.items() if v==0)
    ordered=[]
    while ready:
        current=ready.pop(0);ordered.append(current)
        for b in adjacency[current]:
            indeg[b]-=1
            if indeg[b]==0:ready.append(b);ready.sort()
    require(len(ordered)==len(nodes),"cyclic executable projection")
    levels=[h.get("level") for h in d.get("hierarchy",[])]
    require(levels==["Mission","Sprint","Wave","Pulse","Run"],"hierarchy")
    require({r.get("key") for r in d.get("sipoc",[])}=={"S","I","P","O","C"},"SIPOC")
    schedule=d.get("scheduler",{})
    require(schedule.get("model")=="READ_ONLY_PROPOSAL" and schedule.get("dispatch_authorized") is False and schedule.get("run_created_by_this_view") is False,"dispatch must be withheld")
    require(schedule.get("per_repo_source_repair_wip_limit")==1 and schedule.get("per_repo_prove_wip_limit")==1,"bounded path WIP")
    require(schedule.get("measured_concurrency") is None and schedule.get("worker_count_measured") is None,"no fake runner capacity")
    require(len({x.get("code") for x in d.get("queues",[])})==len(d.get("queues",[])),"queue duplicates")
    require({q.get("code") for q in d.get("queues",[])}=={"EXECUTE_NOW","PROVE","RETURN","CONTROL","READ","HOLD"},"queue coverage")
    for w in d.get("workers",[]):require(w.get("active_count") is None,"worker capacity invented")
    return ordered

def mermaid(d):
    validate(d)
    nmap={n["id"]:n for n in d["nodes"]}
    parts=["flowchart LR"]
    for n in d["nodes"]:
        label=n["label"].replace('"',"'").replace("<","").replace(">","")
        parts.append('    '+n["id"]+'["'+label+'"]')
    for e in d["edges"]:
        typ=e["relation"]
        arrow="-.->" if e["binding"]=="DECLARED" or typ in ("FEEDBACK","ASSOCIATION") else "-->"
        parts.append("    "+e["from"]+" "+arrow+" "+e["to"])
    return "\n".join(parts)+"\n"

def sipoc_md(d):
    validate(d)
    rows=["# MISSION CONTROL — federated SIPOC (read-only)", "",
          "Input authority: source-owned GitHub. No engineering, release or merge credit.", "",
          "| Stage | Evidence and process boundary | Canonical origin |",
          "|---|---|---|"]
    for x in d["sipoc"]:
        rows.append("| "+x["key"]+" · "+x["name"]+" | "+x["description"].replace("|","/")+" | `"+x["source"]+"` |")
    rows+=["","## Workflow hierarchy",""]
    rows += ["- "+str(x["depth"]+1)+". **"+x["level"]+"** — "+x["description"] for x in d["hierarchy"]]
    rows+=["","## Dispatch condition","","All displayed worker/dispatch routes are **DECLARED** scheduling proposals. The existing CODEX execution gateway is STAGE_ONLY; actual mutation is disabled. A display button is not an authenticated runner.",""]
    return "\n".join(rows)

def project(d):
    order=validate(d)
    return {"schema":"missioncontrol.launchpad.public_projection.v1",
            "input_sha256":hashlib.sha256((canonical(d)+"\n").encode()).hexdigest(),
            "source_snapshot":d["snapshot"],"policy":d["policy"],
            "repositories":d["repositories"],"nodes":d["nodes"],"edges":d["edges"],
            "sipoc":d["sipoc"],"hierarchy":d["hierarchy"],"queues":d["queues"],
            "workers":d["workers"],"scheduler":d["scheduler"],"links":d["links"],
            "counts":{"repositories":len(d["repositories"]),"nodes":len(d["nodes"]),"edges":len(d["edges"]),
                      "receipt_edges_historical":sum(e["binding"]=="RECEIPT" for e in d["edges"]),
                      "declared_edges":sum(e["binding"]=="DECLARED" for e in d["edges"]),
                      "execution_dependencies":sum(e["relation"]=="DEPENDS_ON" for e in d["edges"])},
            "executable_dag_topology":order,"native_run_qa":None,"visual_qa":None,
            "observed_dispatch_count":None,"admission":"HOLD"}

def generate(root=None,out=None):
    root=Path(root or HERE)
    d=json.loads((root/"MISSIONCONTROL_NAV_SOURCES_v1.json").read_text(encoding="utf-8"))
    result=project(d)
    out=Path(out or root/"build");out.mkdir(parents=True,exist_ok=True)
    (out/"snapshot.json").write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",encoding="utf-8",newline="\n")
    (out/"federation.mmd").write_text(mermaid(d),encoding="utf-8",newline="\n")
    (out/"SIPOC.md").write_text(sipoc_md(d),encoding="utf-8",newline="\n")
    return result

if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--out",required=True)
    args=ap.parse_args();r=generate(out=args.out)
    print("MISSIONCONTROL_NAV_MODEL=PASS",r["counts"],"admission=HOLD")
