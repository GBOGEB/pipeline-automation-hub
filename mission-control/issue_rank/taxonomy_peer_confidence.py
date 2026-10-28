#!/usr/bin/env python3
"""N+9 source-pinned peer/cohort analytics over canonical taxonomy facets.

One unique issue/PR per primary peer group. Topic memberships overlap and
are never a substitute for item denominators. Public projection strips
private rows before statistics and source signatures are formed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import taxonomy_pulse as pulse

SCHEMA="jade.taxonomy-peer-confidence.v1"


def wilson(good,denominator,z=1.96):
    if denominator==0: return None
    p=good/denominator
    q=1+z*z/denominator
    spread=z*math.sqrt(p*(1-p)/denominator+z*z/(4*denominator**2))/q
    mid=(p+z*z/(2*denominator))/q
    return [round(max(0,mid-spread),6),round(min(1,mid+spread),6)]


def _report_visible(projection:dict) -> dict:
    rows=projection["items"]
    by_repo=defaultdict(list)
    for row in rows:
        by_repo[row["repo"]].append(row)
    repos=sorted(projection["heads"])
    peers=Counter()
    kinds=Counter()
    topics=Counter()
    samples={}
    for item in rows:
        facet=pulse.facets(item)
        peer=facet["action"]+"/"+facet["scope"]
        peers[peer]+=1
        kinds[item["type"]]+=1
        for topic in set(item["topic_families"]):
            topics[topic]+=1
    n=len(rows)
    if sum(peers.values())!=n or sum(kinds.values())!=n:
        raise ValueError("NONADDITIVE_PRIMARY_PEERS")
    for key,count in sorted(peers.items()):
        samples[key]={"count":count,"denominator":n,
                      "fraction":round(count/n,6) if n else None,
                      "wilson95":wilson(count,n)}
    return {"items":n,"issues":kinds["Issue"],"prs":kinds["PullRequest"],
            "reconciled_peer_sum":sum(peers.values()),
            "peers":samples,
            "topic_memberships_nonadditive":dict(sorted(topics.items())),
            "repositories":{repo:len(by_repo[repo]) for repo in repos},
            "private_excluded":projection["excluded_private_count"]}


def analyze(current:dict,previous:dict|None=None,*,public=True) -> dict:
    # Never expose a previously-private source because a subsequent model
    # labels the same repository public. Require independent owner review.
    if previous is not None:
        old_sources=previous.get("heads",{})
        new_sources=current.get("heads",{})
        if isinstance(old_sources,dict) and isinstance(new_sources,dict):
            for repo in old_sources.keys() & new_sources.keys():
                if bool(old_sources[repo].get("private")) != bool(new_sources[repo].get("private")):
                    raise ValueError("SOURCE_VISIBILITY_CHANGED_REQUIRES_OWNER_REVIEW")
    c=pulse.visible(current,public=public)
    now=_report_visible(c)
    earlier=pulse.visible(previous,public=public) if previous is not None else None
    matched=False
    delta={}
    if earlier is not None:
        if pulse._timestamp(earlier["fetched_at"]) >= pulse._timestamp(c["fetched_at"]):
            raise ValueError("REVERSED_PULSE")
        # Compare the full source-repository population *before* public
        # redaction. Otherwise a missing private repository is silently
        # hidden, yielding a false matched cohort despite source drift.
        current_sources=current["heads"]
        previous_sources=previous["heads"]
        matched=(set(current_sources)==set(previous_sources) and
                 all(bool(current_sources[k].get("private")) ==
                     bool(previous_sources[k].get("private"))
                     for k in current_sources) and
                 set(c["heads"])==set(earlier["heads"]))
        if matched:
            old=_report_visible(earlier)
            for key in sorted(set(now["peers"])|set(old["peers"])):
                curr=now["peers"].get(key,{"count":0})["count"]
                prev=old["peers"].get(key,{"count":0})["count"]
                delta[key]={"current":curr,"previous":prev,
                            "open_population_delta":curr-prev,
                            "verified_root_closure":None}
    result={
        "schema":SCHEMA,"taxonomy_schema":pulse.tax.SCHEMA,
        "source_grade":"NON_ATOMIC_GITHUB_OPEN_ITEMS_HEADS",
        "observed_at":c["fetched_at"],"source_heads":c["heads"],
        "visibility":"PUBLIC_PROJECTION" if public else "OWNER_PRIVATE_ONLY",
        "current":now,
        "previous_population_comparable":matched if earlier is not None else None,
        "population_comparison":("SOURCE_AND_VISIBLE_MATCHED" if matched else
            "WITHHELD_SOURCE_OR_PRIVACY_SCOPE_DRIFT" if earlier is not None else "BASELINE_ONLY"),
        "peer_delta":delta,
        "delta_is_causal":False,
        "count_of_absent_open_items_is_not_closure":True,
        "merge_admission":"HOLD","root_burndown_credit":0,
        "formal_credit_delta":0,"authority_transfer":False}
    result["receipt_sha256"]=hashlib.sha256(json.dumps(
        result,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    return result


def main(argv=None):
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--current",type=Path,required=True)
    a.add_argument("--previous",type=Path)
    a.add_argument("--out",type=Path,required=True)
    a.add_argument("--private-local",action="store_true")
    opts=a.parse_args(argv)
    current=json.loads(opts.current.read_text(encoding="utf-8"))
    previous=json.loads(opts.previous.read_text(encoding="utf-8")) if opts.previous else None
    r=analyze(current,previous,public=not opts.private_local)
    opts.out.parent.mkdir(parents=True,exist_ok=True)
    opts.out.write_text(json.dumps(r,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print("PEER_COHORTS",r["current"]["items"],"cohorts",len(r["current"]["peers"]))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
