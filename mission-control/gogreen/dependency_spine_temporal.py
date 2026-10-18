#!/usr/bin/env python3
"""Mission Control read-only N-1/N/N+1 Dependency SPINE continuity projection.

Not the authoritative Golden Thread, not a worker scheduler and not a BD ledger.
Native peer artifact admission remains separately source/owner verified.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

SCHEMA="missioncontrol.dependency_spine.temporal.v1"
SHA=re.compile(r"^[0-9a-f]{40}$")
FLEET=("GBOGEB/ABACUS","GBOGEB/CODEX","GBOGEB/pipeline-automation-hub",
       "GBOGEB/cryoplant-project","GBOGEB/gg_MATH")
PEERS=tuple(x for x in FLEET if x!="GBOGEB/cryoplant-project")

def canonical(value:dict)->bytes:
    return (json.dumps(value,sort_keys=True,indent=2,ensure_ascii=True)+"\n").encode()

def digest(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

def git_head(root:Path)->str:
    p=subprocess.run(["git","rev-parse","--verify","HEAD"],cwd=root,capture_output=True,text=True,check=False)
    return p.stdout.strip() if p.returncode==0 else ""

def check_owner(root:Path):
    a=root/"mission-control"/"gogreen"/"sipoc_instances.py"
    b=root/"mission-control"/"golden-thread"/"golden_thread.py"
    if not a.is_file() or not b.is_file():
        raise ValueError("CANONICAL_OWNER_PLANNER_MISSING")

def validate_peer(receipt:dict,manifest:dict,repo:str,expected_sha:str) -> dict:
    if repo not in PEERS or not SHA.fullmatch(expected_sha):
        raise ValueError("PEER_PIN_INVALID")
    if receipt.get("schema")!="qps.dependency_spine.peer_census.v1":
        raise ValueError("PEER_SCHEMA")
    if (receipt.get("repo")!=repo or receipt.get("head_sha")!=expected_sha or
        receipt.get("exact_head_verified") is not True):
        raise ValueError("PEER_IDENTITY_DRIFT")
    if manifest.get("schema")!="qps.dependency_spine.peer_sha256.v1":
        raise ValueError("MANIFEST_SCHEMA")
    if manifest.get("repo")!=repo or manifest.get("head_sha")!=expected_sha:
        raise ValueError("MANIFEST_IDENTITY")
    if manifest.get("files")!={"PEER_CENSUS.json":digest(canonical(receipt))}:
        raise ValueError("PEER_DIGEST")
    guards=receipt.get("governance",{})
    if (guards.get("authority_transfer") is not False or guards.get("remote_dispatch_authorized") is not False
        or guards.get("mutation_enabled") is not False or guards.get("formal_credit_delta")!=0
        or guards.get("merge_admission")!="HOLD"):
        raise ValueError("PEER_AUTHORITY_ESCALATION")
    if receipt.get("runtime_proof")!="NATIVE_SCAN_JOB_ONLY_NOT_DEPENDABOT_UPGRADE_PROOF":
        raise ValueError("PEER_FALSE_RUNTIME")
    return {"repo":repo,"head_sha":expected_sha,"workflow_count":receipt["workflow_count"],
            "action_reference_count":receipt["action_reference_count"],
            "dependabot_present":receipt["dependabot_present"],
            "receipt_sha256":digest(canonical(receipt)),
            "origin":"LOCAL_BYTE_VERIFIED_PEER_STAGING_NO_AUTHENTICATED_RUN_PROOF"}

def collect(peer_dirs:dict[str,Path], expected:dict[str,str]) -> dict:
    if set(peer_dirs)-set(PEERS) or set(expected)-set(peer_dirs):
        raise ValueError("UNAUTHORIZED_PEER_SCOPE")
    records={}
    for repo in PEERS:
        if repo not in peer_dirs:
            records[repo]={"repo":repo,"status":"NOT_STAGED","head_sha":None}
            continue
        path=peer_dirs[repo]
        try:
            a=json.loads((path/"PEER_CENSUS.json").read_text(encoding="utf-8"))
            b=json.loads((path/"PEER_SHA256.json").read_text(encoding="utf-8"))
        except (OSError,ValueError) as e:
            raise ValueError("PEER_STAGE_MISSING_OR_INVALID:"+repo) from e
        records[repo]={"status":"LOCALLY_VERIFIED_UNAUTHENTICATED",
                       **validate_peer(a,b,repo,expected[repo])}
    return records

def build(owner_sha:str, records:dict, *, previous:dict|None=None) -> dict:
    if not SHA.fullmatch(owner_sha) or set(records)!=set(PEERS):
        raise ValueError("OWNER_HEAD_OR_ROSTER_INVALID")
    staged=[x for x in records.values() if x["status"]=="LOCALLY_VERIFIED_UNAUTHENTICATED"]
    counts={"declared_repos":5,"peer_declared":4,"locally_staged_peers":len(staged),
            "peer_missing":4-len(staged),
            "native_cross_repo_hops_accepted":0,
            "native_peer_authenticated_count":0,
            "reference_upgrade_coverage_pct":None,
            "qps_engineering_coverage_pct":None,
            "statement_branch_coverage_pct":None}
    previous_stage=None
    if previous is not None:
        if (previous.get("schema")!=SCHEMA or previous.get("authority_transfer") is not False
            or previous.get("formal_credit_delta")!=0):
            raise ValueError("HISTORICAL_SOURCE_NOT_ACCEPTED")
        previous_stage=previous.get("metrics",{}).get("locally_staged_peers")
        if not isinstance(previous_stage,int) or previous_stage<0 or previous_stage>4:
            raise ValueError("HISTORICAL_METRIC_INVALID")
    result={
      "schema":SCHEMA,"producer_repo":"GBOGEB/pipeline-automation-hub","producer_head_sha":owner_sha,
      "canonical_owner_paths":["mission-control/gogreen/sipoc_instances.py",
                               "mission-control/golden-thread/golden_thread.py"],
      "historical_n_minus_1":previous_stage,
      "current_n":len(staged),
      "next_n_plus_1_target":4,
      "comparison_same_scope":previous_stage is not None,
      "improvement_delta":len(staged)-previous_stage if previous_stage is not None else None,
      "metrics":counts,
      "peers":records,
      "sipoc": [
          {"supplier":"Peer owner CI","input":"exact head + peer manifest",
           "process":"validate staged bytes and source identity",
           "output":"local staging disposition","customer":"CODEX MYCELIUM"},
          {"supplier":"CODEX / ABACUS owners","input":"independent authenticated consumer receipts",
           "process":"owner-gated KEB→DOW routing","output":"withheld until exact producer/consumer proof",
           "customer":"QPS child gate"},
          {"supplier":"QPS child owner","input":"governed acceptance receipt",
           "process":"ACCEPT/REJECT/DEFER independently","output":"next pulse observation",
           "customer":"Mission Control observer"},
      ],
      "feedback":"N_PLUS_1_ONLY_NOT_SAME_PULSE_EDGE",
      "authority_transfer":False,"formal_credit_delta":0,"mutation_enabled":False,
      "dispatch_authorized":False,"merge_admission":"HOLD","qps_disposition":"DEFER",
      "observation_state":"STAGE_ONLY_UNAUTHENTICATED" if staged else "DEFER_NO_PEER_ARTIFACTS",
    }
    result["semantic_sha256"]=digest(canonical(result))
    return result

def verify(value:dict):
    bare={k:v for k,v in value.items() if k!="semantic_sha256"}
    if value.get("semantic_sha256")!=digest(canonical(bare)):
        raise ValueError("OBSERVATION_HASH_DRIFT")
    if (value.get("schema")!=SCHEMA or value.get("authority_transfer") is not False
        or value.get("formal_credit_delta")!=0 or value.get("mutation_enabled") is not False
        or value.get("dispatch_authorized") is not False or value.get("merge_admission")!="HOLD"
        or value.get("qps_disposition")!="DEFER"
        or value.get("metrics",{}).get("native_cross_repo_hops_accepted")!=0):
        raise ValueError("MISSIONCONTROL_FALSE_ACCEPT")
    if value.get("feedback")!="N_PLUS_1_ONLY_NOT_SAME_PULSE_EDGE":
        raise ValueError("INVALID_FEEDBACK_EDGE")

def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--expected-head",required=True)
    p.add_argument("--root",type=Path,default=Path("."))
    p.add_argument("--peer",action="append",default=[],help="owner/repo=local artifact directory")
    p.add_argument("--pin",action="append",default=[],help="owner/repo=40-character source commit SHA")
    p.add_argument("--previous",type=Path)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    if git_head(a.root)!=a.expected_head:
        raise SystemExit("EXACT_HUB_SOURCE_HEAD_MISMATCH")
    check_owner(a.root)
    def mapping(items):
        result={}
        for value in items:
            name,sep,text=value.partition("=")
            if not sep or not name or not text or name in result:
                raise ValueError("INVALID_MAPPING")
            result[name]=text
        return result
    peer_dirs={k:Path(v) for k,v in mapping(a.peer).items()}
    pins=mapping(a.pin)
    previous=json.loads(a.previous.read_text(encoding="utf-8")) if a.previous else None
    result=build(a.expected_head,collect(peer_dirs,pins),previous=previous)
    verify(result)
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/"MC_DEPENDENCY_SPINE_TEMPORAL.json").write_bytes(canonical(result))
    print(json.dumps({"observed_staged":result["current_n"],"required_peers":4,
                      "status":result["observation_state"],"admission":"HOLD"},sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
