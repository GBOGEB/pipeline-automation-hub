#!/usr/bin/env python3
"""Read-only P-process -> CODEX MYCELIUM candidate projection.

Never emits mutation requests, merge-admission PASS or QPS engineering credit.
The external CODEX owner must accept any typed return independently.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

SHA = re.compile(r"[0-9a-f]{40}\Z")
REPOS = frozenset({"GBOGEB/ABACUS", "GBOGEB/CODEX", "GBOGEB/cryoplant-project",
                   "GBOGEB/gg_MATH", "GBOGEB/Q_engineering_tools", "GBOGEB/pipeline-automation-hub"})
MODES = frozenset({"CODE_PURPLE", "EVERRED"})
SOURCE = Path(__file__).resolve().parent / "site"


def project(state, census, everred, drift, *, source_sha, source_digests):
    if not isinstance(source_sha, str) or not SHA.fullmatch(source_sha):
        raise ValueError("exact producer head SHA required")
    if state.get("schema") != "p-process.state/1.0" or state.get("lifted") is not False:
        raise ValueError("unlifted P-process source expected; never infer incident lift")
    if everred.get("schema") != "everred.census/1.0" or not isinstance(everred.get("roots"), list):
        raise ValueError("missing EVERRED source contract")
    if census.get("lifted") is not False or not isinstance(census.get("lift"), list):
        raise ValueError("missing acute incident evidence")
    rs = state.get("repos")
    if not isinstance(rs, dict) or set(rs) != REPOS or set((drift.get("repos") or {})) != REPOS:
        raise ValueError("six-repo producer cohort incomplete")
    nodes = []
    edges = []
    for repo in sorted(REPOS):
        st = rs[repo]
        if st.get("mode") not in MODES or st.get("ruleset") not in {"RED", "GREEN", "UNKNOWN"}:
            raise ValueError("unknown repo mode/ruleset")
        if st["ruleset"] == "GREEN" and drift["repos"][repo].get("red") is not False:
            raise ValueError("false-green ruleset projection")
        nodes.append({"id":"repo:"+repo,"kind":"repository","owner":repo,
                      "mode":st["mode"],"ruleset":st["ruleset"],"evidence":"PRODUCER_SNAPSHOT"})
    ids=set()
    for r in everred["roots"]:
        rid=r.get("id")
        if not isinstance(rid,str) or rid in ids or not re.fullmatch(r"[A-Z]+-RC-\d{4}-\d{4}",rid):
            raise ValueError("missing/duplicate/invalid root identity")
        ids.add(rid)
        names = {"ABACUS":"ABACUS","CODEX":"CODEX","CRYO":"cryoplant-project",
                 "GGMATH":"gg_MATH","QET":"Q_engineering_tools","PAH":"pipeline-automation-hub"}
        prefix=rid.split("-")[0]
        if prefix not in names: raise ValueError("root with no named authority")
        repo="GBOGEB/"+names[prefix]
        nodes.append({"id":"root:"+rid,"kind":"issue","owner":repo,
                      "state":r.get("state","UNKNOWN"),"severity":r.get("severity","UNKNOWN"),
                      "evidence":"PRODUCER_SNAPSHOT"})
        edges.append({"from":"root:"+rid,"to":"repo:"+repo,"kind":"references",
                      "evidence":"DECLARED_SOURCE_LINK"})
    return {
        "schema":"mycelium.p_process.candidate/1.0",
        "authority_transfer":False,"formal_credit_delta":0,"engineering_credit_delta":0,
        "merge_admission":"HOLD","dispatch_authorized":False,"mutation_enabled":False,
        "consumer_acceptance":"WITHHELD","source":{"repository":"GBOGEB/pipeline-automation-hub",
        "commit_sha":source_sha,"data_digests_sha256":source_digests,
        "census_at":census.get("generated_at"),"everred_at":everred.get("generated_at")},
        "target":{"repository":"GBOGEB/CODEX","surface":"mission_control/mycelium",
                  "mechanism":"REFERENCE_CANDIDATE","owner_acceptance_required":True},
        "incident":{"id":state.get("incident"),"lifted":False,
                    "criteria_met":sum(x.get("ok") is True for x in census["lift"]),
                    "criteria_total":len(census["lift"])},
        "nodes":nodes,"edges":edges,
        "metric_scope":{"occurrences_total":everred.get("metrics",{}).get("occurrences_total"),
          "roots_independent":everred.get("metrics",{}).get("roots_independent"),
          "consumer_replay_coverage":everred.get("metrics",{}).get("consumer_replay_coverage")},
        "next_legal_transition":"CODEX_OWNER_REVIEW_TYPED_REFERENCE"}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--site",type=Path,default=SOURCE)
    ap.add_argument("--producer-sha",required=True)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    paths={"state":"data/p_state.json","census":"code-purple/kit/census.json",
           "everred":"everred/data/everred.json","drift":"rulesets/drift.json"}
    blobs={name:(args.site/path).read_bytes() for name,path in paths.items()}
    objects={name:json.loads(blob) for name,blob in blobs.items()}
    result=project(objects["state"],objects["census"],objects["everred"],objects["drift"],
                   source_sha=args.producer_sha,
                   source_digests={name:hashlib.sha256(blob).hexdigest() for name,blob in blobs.items()})
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("MYCELIUM=STAGED_READ_ONLY; NODES=%d; EDGES=%d"%(len(result["nodes"]),len(result["edges"])))

if __name__=="__main__": main()
