#!/usr/bin/env python3
"""N+10 noncompensating root-predicate successor audit (public Hub only).

A closed issue is not a closed root when required acceptance predicates lack
an owner-accepted proof or an exact registered successor. MENTION is never
proof of succession. Cycles or multiple owners remain HOLD.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

INPUT="jade.root-successor-input.v1"
SCHEMA="jade.root-successor-audit.v1"
REPO="GBOGEB/pipeline-automation-hub"
KEY=re.compile(r"^GBOGEB/pipeline-automation-hub#[1-9][0-9]*$")
PRED=re.compile(r"^[A-Za-z0-9_.:-]{2,96}$")
SHA=re.compile(r"^[0-9a-f]{40}$",re.I)
STATES={"OPEN","CLOSED"}


def audit(data:dict) -> dict:
    if not isinstance(data,dict) or data.get("schema")!=INPUT:
        raise ValueError("INPUT_SCHEMA_MISMATCH")
    if data.get("repo")!=REPO or not SHA.fullmatch(str(data.get("source_head") or "")):
        raise ValueError("PUBLIC_SOURCE_HEAD_MISSING")
    rows=data.get("items")
    edges=data.get("edges")
    if not isinstance(rows,list) or not isinstance(edges,list):
        raise ValueError("GRAPH_NOT_LIST")
    items={}
    for item in rows:
        if not isinstance(item,dict):
            raise ValueError("ITEM_NOT_OBJECT")
        k=item.get("key")
        if not isinstance(k,str) or not KEY.fullmatch(k) or k in items:
            raise ValueError("DUPLICATE_OR_BAD_ITEM")
        if item.get("state") not in STATES:
            raise ValueError("ITEM_STATE_UNKNOWN")
        obligations={}
        ps=item.get("predicates")
        if not isinstance(ps,list):
            raise ValueError("PREDICATES_NOT_LIST")
        for predicate in ps:
            if not isinstance(predicate,dict):
                raise ValueError("PREDICATE_NOT_OBJECT")
            pid=predicate.get("id")
            if not isinstance(pid,str) or not PRED.fullmatch(pid) or pid in obligations:
                raise ValueError("DUPLICATE_OR_BAD_PREDICATE")
            accepted=predicate.get("owner_accepted")
            if type(accepted) is not bool:
                raise ValueError("OWNER_ACCEPTANCE_UNKNOWN")
            evid=predicate.get("evidence_sha")
            if accepted and (not isinstance(evid,str) or not SHA.fullmatch(evid)):
                raise ValueError("ACCEPTANCE_WITHOUT_SOURCE_PROOF")
            obligations[pid]=accepted
        items[k]={"state":item["state"],"predicates":obligations}
    links=defaultdict(set)
    for edge in edges:
        if not isinstance(edge,dict):
            raise ValueError("EDGE_NOT_OBJECT")
        src,dst=edge.get("from"),edge.get("to")
        if src not in items or dst not in items:
            raise ValueError("EDGE_NOT_BOUND_TO_SOURCE_ITEMS")
        if src==dst:
            raise ValueError("SELF_SUCCESSOR_CYCLE")
        if edge.get("relation")=="SUCCESSOR_OF":
            links[src].add(dst)
        elif edge.get("relation") not in ("MENTION","PARENT","RELATED"):
            raise ValueError("EDGE_RELATION_UNKNOWN")
    # Detect multi-hop cycles BEFORE issuing any successor credit.
    visited=set()
    active=set()
    def visit(key):
        if key in active:
            raise ValueError("SUCCESSOR_GRAPH_CYCLE")
        if key in visited:
            return
        active.add(key)
        for nxt in links[key]:
            visit(nxt)
        active.remove(key)
        visited.add(key)
    for key in items:
        visit(key)
    def holders(start,predicate):
        terminals=set()
        stack=list(links[start])
        seen=set()
        while stack:
            k=stack.pop()
            if k in seen: continue
            seen.add(k)
            node=items[k]
            if node["state"]=="OPEN" and predicate in node["predicates"]:
                terminals.add(k)
            # Continue beyond open nodes to catch ambiguous multi-owner handoffs.
            stack.extend(links[k])
        return terminals
    gaps=[]
    migrations=[]
    for root,node in sorted(items.items()):
        if node["state"]!="CLOSED":
            continue
        for pid,accepted in sorted(node["predicates"].items()):
            if accepted:
                continue
            candidates=sorted(holders(root,pid))
            status=("ORPHANED_ROOT_RESIDUAL" if not candidates else
                    "AMBIGUOUS_SUCCESSOR" if len(candidates)>1 else
                    "OPEN_SUCCESSOR_CANDIDATE_NOT_ACCEPTED")
            migrations.append({"closed_root":root,"predicate_id":pid,
                               "candidate_open_successors":candidates,"status":status,
                               "formal_closure_credit":0})
            if status!="OPEN_SUCCESSOR_CANDIDATE_NOT_ACCEPTED":
                gaps.append({"root":root,"predicate_id":pid,"reason":status})
    out={
        "schema":SCHEMA,"repo":REPO,"source_head":data["source_head"],
        "closed_items":sum(i["state"]=="CLOSED" for i in items.values()),
        "open_items":sum(i["state"]=="OPEN" for i in items.values()),
        "residual_predicates":len(migrations),
        "orphaned_or_ambiguous":len(gaps),
        "candidate_migrations":migrations,"root_gaps":gaps,
        "successor_proof_grade":"DECLARED_GRAPH_NOT_OWNER_SIGNED",
        "root_closure_credit":0,"merge_admission":"HOLD","formal_credit_delta":0,
        "authority_transfer":False}
    out["receipt_sha256"]=hashlib.sha256(json.dumps(
        out,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return out


def main(argv=None):
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--in",dest="source",type=Path,required=True)
    a.add_argument("--out",type=Path,required=True)
    opts=a.parse_args(argv)
    r=audit(json.loads(opts.source.read_text(encoding="utf-8")))
    opts.out.parent.mkdir(parents=True,exist_ok=True)
    opts.out.write_text(json.dumps(r,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("SUCCESSOR_ROOTS",r["closed_items"],"RESIDUAL",r["residual_predicates"],"HOLD")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
