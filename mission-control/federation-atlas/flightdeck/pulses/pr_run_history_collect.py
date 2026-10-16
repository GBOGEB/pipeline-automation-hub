#!/usr/bin/env python3
"""Read-only bounded GitHub temporal recensus: never mutate PRs or authority."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, parse, request

SHA=re.compile(r"^[0-9a-f]{40}$")
REPO=re.compile(r"^GBOGEB/[A-Za-z0-9_.-]+$")
PRREF=re.compile(r"^(GBOGEB/[A-Za-z0-9_.-]+)#([1-9][0-9]*)$")
LIMIT_PAGES=3
LIMIT_NODES=12

def require(ok,reason):
    if not ok: raise ValueError(reason)

def read_api(repo,path,token=None):
    """GET only, no redirects to unknown hosts, token scoped to same repository."""
    require(REPO.fullmatch(repo) and path.startswith("/") and
            ".." not in path and "://" not in path,"unsafe GitHub API locator")
    uri="https://api.github.com/repos/"+repo+path
    head={"Accept":"application/vnd.github+json",
          "X-GitHub-Api-Version":"2022-11-28",
          "User-Agent":"CODE-PURPLE-readonly-PR-recensus"}
    if token and os.environ.get("GITHUB_REPOSITORY")==repo:
        head["Authorization"]="Bearer "+token
    req=request.Request(uri,headers=head,method="GET")
    try:
        with request.urlopen(req,timeout=12) as res:
            require(res.geturl().startswith("https://api.github.com/"),
                    "API redirect outside GitHub refused")
            raw=res.read(3_000_001)
        require(len(raw)<=3_000_000,"GitHub response too large")
        return json.loads(raw)
    except (error.HTTPError,error.URLError,TimeoutError,UnicodeError,json.JSONDecodeError) as exc:
        raise ValueError("GitHub READ unavailable: "+type(exc).__name__) from exc

def _timestamp(s):
    if s is None: return None
    require(isinstance(s,str) and s.endswith("Z"),"invalid UTC instant")
    datetime.fromisoformat(s.replace("Z","+00:00"))
    return s

def ancestry_nodes(source):
    """Traverse only verified source-specified edges, never discovered conjecture."""
    roots=[(p["repository"],p["pr"],0) for p in source["prs"]]
    adjacency={}
    for e in source["edges"]:
        m=PRREF.fullmatch(e["from"])
        child=PRREF.fullmatch(e["to"])
        if m and child:
            adjacency.setdefault((m[1],int(m[2])),[]).append((child[1],int(child[2])))
    out=[]; seen=set(); queue=list(roots)
    maxdepth=source["recursive_contract"]["max_depth"]
    while queue and len(out)<LIMIT_NODES:
        repo,pr,depth=queue.pop(0)
        if (repo,pr) in seen: continue
        seen.add((repo,pr));out.append((repo,pr,depth))
        if depth<maxdepth:
            for child in sorted(adjacency.get((repo,pr),[])):
                if child not in seen:queue.append((child[0],child[1],depth+1))
    return out

def get_runs(repo,sha,getter,max_pages=LIMIT_PAGES):
    """Enumerate up to three pages, preserving incomplete pagination explicitly."""
    require(isinstance(sha,str) and SHA.fullmatch(sha),"invalid run query SHA")
    rows=[]; listed=None; pages=0
    for page in range(1,max_pages+1):
        suffix="/actions/runs?"+parse.urlencode({"head_sha":sha,"per_page":100,"page":page})
        payload=getter(repo,suffix)
        require(isinstance(payload,dict) and
                type(payload.get("total_count")) is int and
                payload["total_count"]>=0 and
                isinstance(payload.get("workflow_runs"),list),"bad workflow page")
        listed=payload["total_count"]
        page_runs=payload["workflow_runs"]
        pages+=1
        for r in page_runs:
            ident=r.get("id")
            require(type(ident) is int and ident>0 and
                    type(r.get("run_attempt")) is int and r["run_attempt"]>0 and
                    isinstance(r.get("head_sha"),str) and SHA.fullmatch(r["head_sha"]),
                    "invalid workflow/run/attempt identity")
            row={
                "run_id":ident,"run_attempt":r["run_attempt"],
                "workflow":r.get("name"),"event":r.get("event"),
                "created_at":_timestamp(r.get("created_at")),
                "started_at":_timestamp(r.get("run_started_at")),
                "updated_at":_timestamp(r.get("updated_at")),
                "head_sha":r["head_sha"],"status":r.get("status"),
                "conclusion":r.get("conclusion"),
                "sha_alignment":"MATCH" if r["head_sha"]==sha else "MISMATCH",
                "url":f"https://github.com/{repo}/actions/runs/{ident}"
            }
            rows.append(row)
        if len(rows)>=listed or not page_runs:break
    ids=[(x["run_id"],x["run_attempt"]) for x in rows]
    require(len(ids)==len(set(ids)),"duplicate run/attempt")
    return {
        "requested_sha":sha,"reported_count":listed,
        "retrieved_count":len(rows),"pages_retrieved":pages,
        "census_complete":len(rows)==listed,
        "grade":"SOURCE_SHA_ASSOCIATED_RUNS_NOT_EXECUTION_SHA",
        "runs":sorted(rows,key=lambda x:(x["created_at"] or "",x["run_id"],x["run_attempt"]))
    }

def recensus(source,getter,clock,enabled):
    from importlib import util
    # Local validation of the source controls, not a new SSOT.
    here=Path(__file__).resolve().parent
    spec=util.spec_from_file_location("pr_merge_temporal_viewer",here/"pr_merge_temporal_viewer.py")
    viewer=util.module_from_spec(spec);spec.loader.exec_module(viewer)
    viewer.validate(source)
    obs={"schema":"code-purple.pr-history.native-refresh.v1",
         "observed_at_utc":_timestamp(clock()),
         "mode":"LIVE_READONLY" if enabled else "NOT_REQUESTED",
         "source_pulse":source["pulse"],
         "source_semantic_sha256":hashlib.sha256(
             json.dumps(source,sort_keys=True,separators=(",",":")).encode()).hexdigest(),
         "authority_transfer":False,"security_waiver":False,"merge_admission":"HOLD",
         "accepted_rex":None,"accepted_root_closures":None,"rows":[]}
    if not enabled:
        obs["qualification"]="NOT_REQUESTED_NOT_ZERO"
        return obs
    seed={(p["repository"],p["pr"]):p for p in source["prs"]}
    for repo,pr,depth in ancestry_nodes(source):
        item={"repository":repo,"pr":pr,"depth":depth,"state":"UNKNOWN",
              "source_alignment":"UNKNOWN","run_phases":[],
              "error":None}
        try:
            data=getter(repo,f"/pulls/{pr}")
            require(isinstance(data,dict),"bad PR response")
            head=data.get("head",{}).get("sha")
            merge=data.get("merge_commit_sha")
            base=data.get("base",{}).get("ref")
            merged_at=_timestamp(data.get("merged_at"))
            require(isinstance(head,str) and SHA.fullmatch(head),
                    "PR head unknown")
            pinned=seed.get((repo,pr))
            if pinned and (head!=pinned["head_sha"] or
                merge!=pinned["merge_commit_sha"] or
                base!=pinned["base_branch"] or
                merged_at!=pinned["merged_at_utc"]):
                item["state"]="SOURCE_DRIFT_HOLD"
                item["error"]="Historical PR identity changed; no current-head promotion"
                obs["rows"].append(item)
                continue
            item["state"]="MERGED" if merged_at else "OPEN_OR_NOT_MERGED"
            item["source_alignment"]="PIN_MATCH" if pinned else "RECURSIVE_PARENT_OBSERVATION_ONLY"
            item["merged_at_utc"]=merged_at
            item["head_sha"]=head
            item["merge_commit_sha"]=merge if isinstance(merge,str) and SHA.fullmatch(merge) else None
            for kind,sha in (("PR_HEAD",head),("MERGE",item["merge_commit_sha"] if merged_at else None)):
                if not sha:continue
                try:
                    phase=get_runs(repo,sha,getter)
                    phase["kind"]=kind
                    item["run_phases"].append(phase)
                except ValueError as exc:
                    item["run_phases"].append({"kind":kind,"requested_sha":sha,
                        "reported_count":None,"retrieved_count":None,
                        "census_complete":None,"status":"UNKNOWN","error":str(exc)})
        except ValueError as exc:
            item["state"]="UNKNOWN";item["error"]=str(exc)
        obs["rows"].append(item)
    obs["qualification"]="READ_ONLY_INCOMPLETE_OR_PENDING_OWNER_REVIEW"
    return obs

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--live",action="store_true",help="Opt-in GitHub REST read-only recensus")
    args=p.parse_args()
    data=json.loads(args.source.read_text())
    now=lambda:datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
    token=os.environ.get("GITHUB_TOKEN")
    receipt=recensus(data,lambda repo,path:read_api(repo,path,token),now,args.live)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"mode":receipt["mode"],"rows":len(receipt["rows"]),
                      "qualification":receipt["qualification"],
                      "merge_admission":"HOLD"},sort_keys=True))

if __name__=="__main__":main()
