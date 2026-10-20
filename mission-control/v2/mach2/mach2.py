#!/usr/bin/env python3
"""Mission Control MACH-II: additive Mycelium graph, cyclic MIP & DMAIC, statistics.

Reference/learning cycles are first-class. Execution is ONLY the acyclic
SIPOC_DEPENDENCY subset. Nothing returned here launches workers or promotes
engineering/domain/governance authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
FULL = "code-purple.mycelium.graph.v2"
KINDS = {
    "SIPOC_DEPENDENCY", "OWNED_BY", "FEDERATION_BRIDGE", "REFERENCE", "PROOF",
    "SUPPLIES", "TEMPORAL_SUCCESSOR", "REVERSE_PRESSURE", "PROPOSED_CONSUMER",
}
LAYERS = {"SIPOC", "FEDERATION", "GOLDEN_THREAD", "BD", "TEMPORAL", "CONTROL", "ATOMS"}
BINDINGS = {"DECLARED", "HISTORICAL", "OBSERVED", "RECEIPT_BOUND", "ACCEPTED"}
DMAIC = {"DEFINE", "MEASURE", "ANALYSE", "IMPROVE", "CONTROL", "RECENSUS", "REX", "REPLAN", "BLOCKED", "WAIT_OWNER", "WAIT_RUNNER"}
TASKS = ("SOURCE_READBACK", "OWNER_CLASSIFICATION", "BOUNDED_CHANGE", "NATIVE_PROOF", "REX_RETURN")
ID = ("GM-I", "GM-II", "GM-III", "GM-IV", "GM-V")


def need(ok: bool, msg: str) -> None:
    if not ok:
        raise ValueError("MACHII_FAIL_CLOSED: " + msg)


def blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def load_manifest() -> tuple[dict, dict]:
    m = json.loads((HERE / "MACHII_MISSION_MANIFEST.json").read_text(encoding="utf-8"))
    r = BASE / m["source"]["gm_registry"]
    raw = r.read_bytes()
    need(blob_sha(raw) == m["source"]["gm_registry_blob_sha"], "canonical GM source drift")
    return m, json.loads(raw)


def validate_missions(m: dict, reg: dict) -> None:
    need(m["schema"] == "missioncontrol.gm.mach_ii.extension.v1", "manifest schema")
    need(m.get("authority_transfer") is False and m.get("dispatch_authorized") is False, "authority escalation")
    need(m.get("admission") == "HOLD" and m.get("new_grand_mission_number") is False, "governance")
    rows = m["missions"]
    need([x["id"] for x in rows] == list(ID), "GM I-V must not be renumbered")
    old = reg["grand_missions"]
    need([x["id"] for x in old] == list(ID), "canonical mission identities")
    need([x["frontier_count"] for x in old] == [1, 2, 4, 8, 16], "original 1/2/4/8/16 invariant")
    need(all(x["frontiers"] == y["frontier_count"] and x["source_disposition"] == y["state"]
             for x,y in zip(rows, old)), "MACH-II cannot rewrite source disposition")
    need(old[3]["state"] == "ACTIVE_8_OF_8" and len(old[3]["children"]) == 0, "GM-IV child authority")
    need(old[4]["state"] == "HELD" and len(old[4]["children"]) == 0, "GM-V control")
    for x in rows:
        mip = x["mip"]
        need(all(isinstance(mip.get(k),str) and len(mip[k])>12
                 for k in ("modernise","innovate","perpetuate")), "MIP incomplete " + x["id"])
        need(len(x["must_prove"])>=3 and x.get("forbidden"), "DoV boundary " + x["id"])


def schedule_sipoc(nodes: list[dict], edges: list[dict]) -> list[list[str]]:
    active = {n["id"] for n in nodes if n["kind"] == "SIPOC_INSTANCE"}
    degrees = {x: 0 for x in active}
    adj = defaultdict(set)
    for e in edges:
        if e["kind"] != "SIPOC_DEPENDENCY":
            continue
        src, dst = e["from"], e["to"]
        need(src in active and dst in active, "SIPOC edge not between executable nodes")
        if dst not in adj[src]:
            adj[src].add(dst)
            degrees[dst]+=1
    stages=[]
    remaining=set(active)
    while remaining:
        ready=sorted(n for n in remaining if degrees[n]==0)
        need(bool(ready), "cycle in executable SIPOC DAG")
        stages.append(ready)
        for n in ready:
            remaining.remove(n)
            for child in adj[n]:
                degrees[child]-=1
    return stages


def validate_mycelium(g: dict) -> dict:
    need(g.get("schema")==FULL, "Mycelium graph schema")
    need(g.get("authority_transfer") is False and g.get("dispatch_authorized") is False, "graph authority")
    nodes, edges = g.get("nodes"),g.get("edges")
    need(isinstance(nodes,list) and isinstance(edges,list), "graph arrays")
    ids=[n.get("id") for n in nodes]
    need(all(isinstance(i,str) and i for i in ids) and len(set(ids))==len(ids), "duplicate node")
    ni={n["id"]:n for n in nodes}
    for n in nodes:
        need(n.get("layer") in LAYERS and n.get("evidence") in BINDINGS, "node layer/evidence")
        need(isinstance(n.get("source"),str) and n["source"] and isinstance(n.get("owner"),str) and n["owner"], "owner/source")
    keys=set()
    for e in edges:
        need(e.get("from") in ni and e.get("to") in ni and e["from"]!=e["to"], "dangling/self edge")
        need(e.get("kind") in KINDS and e.get("layer") in LAYERS and e.get("binding") in BINDINGS, "untyped edge")
        need(isinstance(e.get("source_ref"),str) and e["source_ref"], "edge provenance")
        key=(e["from"],e["to"],e["kind"],e["layer"])
        need(key not in keys,"duplicate typed edge")
        keys.add(key)
        if e["binding"] in ("RECEIPT_BOUND","ACCEPTED"):
            need(e.get("proof_ref"),"unproven receipt edge")
        if e["binding"]=="ACCEPTED":
            need(e.get("owner_acceptance") is True and e.get("reviewer"),"forged owner acceptance")
    need(all(not n["id"].startswith("sipoc:GM-V:") for n in nodes), "HELD GM-V executable node")
    ordered=schedule_sipoc(nodes,edges)
    return {"nodes":len(nodes),"edges":len(edges),"waves":ordered,
            "edge_classes":dict(Counter(e["kind"] for e in edges)),
            "binding_classes":dict(Counter(e["binding"] for e in edges)),
            "reference_feedback_cycles_allowed":True,
            "executable_sipoc_acyclic":True,
            "dispatches_verified":None}


def build_graph(manifest: dict, canonical: dict) -> dict:
    validate_missions(manifest,canonical)
    source=manifest["source"]
    path="mission-control/v2/mach2/MACHII_MISSION_MANIFEST.json"
    nodes, edges=[],[]
    def node(id, title, kind, layer="FEDERATION", **extra):
        nodes.append({"id":id,"title":title,"kind":kind,"layer":layer,
                      "owner":"GBOGEB/pipeline-automation-hub","source":path,
                      "evidence":"DECLARED",**extra})
    def edge(a,b,kind,layer="FEDERATION"):
        edges.append({"from":a,"to":b,"kind":kind,"layer":layer,
                      "binding":"DECLARED","source_ref":path})
    node("mc:control","Mission Control v2","CONTROL","CONTROL")
    node("mycelium:bridge","CODEX Mycelium crosswalk","BRIDGE","FEDERATION",
         source_sha=source["mycelium"]["sha"])
    node("math:provider","gg_MATH MIP and statistics provider","METHOD_PROVIDER","FEDERATION",
         source_sha=source["gg_math"]["sha"])
    node("qps:owner","QPS HEPAK domain owner","ENGINEERING_OWNER","FEDERATION",
         source_sha=source["qps"]["sha"])
    edge("mc:control","mycelium:bridge","FEDERATION_BRIDGE")
    edge("mc:control","math:provider","PROPOSED_CONSUMER")
    edge("mc:control","qps:owner","REFERENCE")
    for mission in manifest["missions"]:
        mid=mission["id"]
        node("mission:"+mid,mid+" · "+mission["mach2_moniker"],"GRAND_MISSION","CONTROL",
             state=mission["source_disposition"],frontiers=mission["frontiers"])
        edge("mc:control","mission:"+mid,"OWNED_BY","CONTROL")
        for name in ("modernise","innovate","perpetuate"):
            ident="mip:"+mid+":"+name
            node(ident,name.upper()+" · "+mid,"MIP_AXIS","CONTROL",description=mission["mip"][name])
            edge("mission:"+mid,ident,"SUPPLIES","CONTROL")
            # Learning can return from ANY facet into its parent: reference graph is cyclic.
            edge(ident,"mission:"+mid,"REVERSE_PRESSURE","GOLDEN_THREAD")
        edge("mission:"+mid,"mycelium:bridge","FEDERATION_BRIDGE")
        edge("mission:"+mid,"math:provider","PROPOSED_CONSUMER")
        if mid=="GM-I":
            edge("mission:"+mid,"qps:owner","PROPOSED_CONSUMER")
        if mid=="GM-V":
            continue  # HELD is visible but never allocated an executable plan node.
        for task in TASKS:
            ident="sipoc:"+mid+":"+task
            node(ident,mid+" "+task,"SIPOC_INSTANCE","SIPOC",proposal_only=True)
            edge("mission:"+mid,ident,"REFERENCE","SIPOC")
        for a,b in zip(TASKS,TASKS[1:]):
            edge("sipoc:"+mid+":"+a,"sipoc:"+mid+":"+b,"SIPOC_DEPENDENCY","SIPOC")
        edge("sipoc:"+mid+":REX_RETURN","sipoc:"+mid+":SOURCE_READBACK","REVERSE_PRESSURE","GOLDEN_THREAD")
    graph={"schema":FULL,"authority_transfer":False,"dispatch_authorized":False,
           "source_repo":"GBOGEB/pipeline-automation-hub",
           "source_manifest_blob":blob_sha(Path(__file__).with_name("MACHII_MISSION_MANIFEST.json").read_bytes()),
           "status":"READ_ONLY_SOURCE_BOUND_TYPED_GRAPH_NO_OWNER_ACCEPTANCE",
           "historical_gm_unchanged":True,"nodes":nodes,"edges":edges}
    graph["projection_receipt"]=validate_mycelium(graph)
    return graph


def wilson(successes: int, n: int, z: float=1.959963984540054) -> dict | None:
    """Two-sided fixed-horizon Wilson 95%, conditional on independent Bernoulli."""
    if type(successes)!=int or type(n)!=int or n<=0 or not 0<=successes<=n:
        return None
    p=successes/n
    den=1+z*z/n
    centre=(p+z*z/(2*n))/den
    half=z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/den
    return {"lower":max(0.,centre-half),"upper":min(1.,centre+half),
            "estimator":"WILSON_95_FIXED_HORIZON_IID_ONLY"}


def defects_rate(defects: int | None, opportunities: int | None,
                 independent: bool=False, stable_control: bool=False) -> dict:
    """Six-sigma evidence condition is NOT formal acceptance."""
    if type(defects)!=int or type(opportunities)!=int or opportunities<=0 or not 0<=defects<=opportunities:
        return {"state":"UNKNOWN_DENOMINATOR","dpmo":None,"upper95_dpmo":None,"sigma_claim":None}
    result={"state":"DESCRIPTIVE_ONLY","n":opportunities,"defects":defects,
            "dpmo":1e6*defects/opportunities,"independent_opportunities_proven":independent,
            "stable_control_proven":stable_control,
            "uncertainty":wilson(defects,opportunities) if independent else None,
            "upper95_dpmo":None,"sigma_claim":None}
    if independent and defects==0:
        result["upper95_dpmo"]=1e6*(-math.expm1(math.log(0.05)/opportunities))
    if independent and stable_control and result["upper95_dpmo"] is not None and result["upper95_dpmo"]<=3.4:
        result["state"]="SIX_SIGMA_STATISTICAL_UPPER_BOUND_CANDIDATE_NOT_CERTIFIED"
    return result


def trend(rows: list[dict], *, metric: str="residual_roots") -> dict:
    """Snapshots MUST have identical registered scope, opportunity population and ordered pulses.
    No independent variance inference from sequential snapshots.
    """
    if not rows:
        return {"state":"UNKNOWN_NOT_MEASURED","delta":None}
    if any(x.get("pending") or x.get("blocked") for x in rows):
        return {"state":"CENSORED_OR_BLOCKED","delta":None}
    if any(metric not in x or not isinstance(x[metric],(int,float)) for x in rows):
        return {"state":"UNKNOWN_NO_MEASUREMENT","delta":None}
    population={(x.get("cohort_id"),x.get("denominator")) for x in rows}
    if len(population)!=1 or next(iter(population))[1] in (None,0):
        return {"state":"INCOMPARABLE_DENOMINATORS","delta":None}
    if len(set(x.get("pulse") for x in rows))!=len(rows):
        return {"state":"DUPLICATE_PULSE_ID","delta":None}
    d=rows[-1][metric]-rows[0][metric]
    if len(rows)<5:
        return {"state":"UNDERPOWERED_TREND_LT5","delta":d,"independent_stability_proven":False}
    deltas=[b[metric]-a[metric] for a,b in zip(rows,rows[1:])]
    med=sorted(deltas)[len(deltas)//2]
    mad=sorted(abs(x-med) for x in deltas)[len(deltas)//2]
    last=deltas[-1]
    state=("CONVERGING_DESCRIPTIVE" if med<0
           else "DIVERGING_DESCRIPTIVE" if med>0
           else "STAGNATION_OR_FLOOR_UNDETERMINED")
    if len(rows)<20:
        state+="_LT20"
    return {"state":state,"delta":d,"last_step":last,"median_step":med,
            "mad_step":mad,"matched_windows":len(rows),"independent_stability_proven":False}


def run_event(clock: list[dict], e: dict) -> list[dict]:
    """Irregular events + backward movement permitted; monotone event order, append-only."""
    need(e.get("action") in DMAIC, "unknown DMAIC/MIP action")
    need(isinstance(e.get("mission_id"),str) and e["mission_id"] in ID, "unknown mission")
    need(isinstance(e.get("source_sha"),str) and len(e["source_sha"])==40
         and all(c in "0123456789abcdef" for c in e["source_sha"]), "unbound event source")
    need(type(e.get("sequence_e")) is int and e["sequence_e"]>=0, "invalid event clock")
    if clock:
        need(e["sequence_e"]>clock[-1]["sequence_e"], "nonmonotone event clock")
    need("observed_at" in e and "known_at" in e and e["observed_at"] and e["known_at"],
         "missing two-clock provenance")
    need(e.get("accepted_semantic_delta") in (False,None), "forged semantic generation")
    return [*clock,dict(e,accepted_semantic_delta=False)]


def build() -> dict:
    manifest, canonical=load_manifest()
    graph=build_graph(manifest,canonical)
    return {"schema":"missioncontrol.mach_ii.projection.v1",
            "mission_states":[{"id":x["id"],"state":x["source_disposition"],
                               "frontiers":x["frontiers"],"mach2":x["mach2_moniker"],
                               "MIP":x["mip"],"required_DoV":x["must_prove"]} for x in manifest["missions"]],
            "source_sha":manifest["source"]["baseline_sha"],
            "mycelium_graph":graph,
            "SIPOC":{"supplier":"Source owners + exact GitHub refs",
                     "input":"Git blob + native run/job/attempt + REX + licence boundaries",
                     "process":"Irregular DMAIC/MIP evidence cycle; bounded executable DAG",
                     "output":"Source-bound DoD/DoV, recensus, REX and BD decision",
                     "customer":"Governor, CODEX/KEB, DOW and QPS domain authority"},
            "stats":{"six_sigma_reference_dpmo":3.4,
                     "zero_defect_trials_needed_95_upper":math.ceil(math.log(.05)/math.log1p(-3.4e-6)),
                     "independent_case_status":"NOT_MEASURED",
                     "PCA_BT_status":"REQUIRES_COMPARABLE_REPLICATES_AND_CONNECTED_GRAPH",
                     "GM_V_launch":"HELD"},
            "MIP_universal":True,"Golden_Thread":{"event_sequence_e":None,
                      "semantic_generation_k":None,"source_receipts_accepted":False},
            "authority_transfer":False,"dispatch_authorized":False,"admission":"HOLD",
            "counts":{"GM":5,"MIP_axes":15,"executable_GM":4,
                      "SIPOC_steps":4*len(TASKS),"scheduled_workers_verified":None}}


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path)
    args=p.parse_args()
    out=build()
    payload=json.dumps(out,indent=2,sort_keys=True)+"\n"
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(payload,encoding="utf-8")
    print(json.dumps({"schema":out["schema"],"GM":out["counts"]["GM"],
                      "node_count":out["mycelium_graph"]["projection_receipt"]["nodes"],
                      "edge_count":out["mycelium_graph"]["projection_receipt"]["edges"],
                      "sipoc_waves":len(out["mycelium_graph"]["projection_receipt"]["waves"]),
                      "sigma_zero_defect_n_required":out["stats"]["zero_defect_trials_needed_95_upper"],
                      "admission":out["admission"]}))


if __name__=="__main__":
    main()
