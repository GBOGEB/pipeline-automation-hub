#!/usr/bin/env python3
"""G4 W32 canonical-census consumer: disjoint pull plan and empty push contract.

Works *inside* the existing GOGREEN G4 workflow (#531 owner). No new
scheduler, publisher, GitHub mutation, authenticated consumer, runner launch,
artifact byte verification or cross-repo coverage credit is created here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

HEX40 = re.compile(r"[a-f0-9]{40}\Z")
PULSE_SCHEMA = "gogreen.pulse-rollup.v1"
PLAN_SCHEMA = "gogreen.g4.w32.disjoint-pull-plan.v1"
PUSH_SCHEMA = "gogreen.g4.w32.empty-push-contract.v1"
MANIFEST_SCHEMA = "gogreen.g4.w32.packet-manifest.v1"
OWNER = "GBOGEB/pipeline-automation-hub"
BASELINE_CELLS = 42


def fail(flag, reason):
    if flag:
        raise ValueError(reason)


def serialize(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def make_plan(report, *, exact_head, new_lane_cap=1, packet_cap=6):
    fail(type(report) is not dict or report.get("schema") != PULSE_SCHEMA,
         "BAD_CANONICAL_PULSE")
    fail(not isinstance(exact_head,str) or not HEX40.fullmatch(exact_head)
         or report.get("source_git_sha") != exact_head, "UNPINNED_PRODUCER_HEAD")
    fail(report.get("merge_authorized") is not False
         or report.get("security_waiver") is not False
         or report.get("authority_transfer") is not False
         or report.get("qps_disposition") != "DEFER", "AUTHORITY_PROMOTION")
    fail(type(new_lane_cap) is not int or new_lane_cap != 1,
         "UNMEASURED_CAPACITY_EXPANSION")
    fail(type(packet_cap) is not int or packet_cap < 1 or packet_cap > 6,
         "UNBOUNDED_PACKET_CAP")
    waves = report.get("waves", [])
    fail(type(waves) is not list or len(waves) != 2 or waves[0].get("wave") != "G0"
         or waves[1].get("wave") != "G1", "HISTORICAL_WAVE_DRIFT")
    last = waves[-1]
    fail(last.get("target_cells") != BASELINE_CELLS
         or last.get("observed_cells") != 6
         or last.get("unobserved_cells") != 36, "CANONICAL_42_CELL_BREADTH_DRIFT")
    sp=report.get("scale_plan",{})
    fail(sp.get("contract") != "PLAN_ONLY"
         or sp.get("dispatch_authorized") is not False
         or sp.get("authority_transfer") is not False
         or sp.get("real_worker_capacity") is not None
         or sp.get("workers_max_parallel") not in (1,2),
         "NONCANONICAL_DISPATCH_OR_CAPACITY")
    raw=sp.get("packets")
    fail(type(raw) is not list or not raw, "EMPTY_SOURCE_PACKETS")
    seen=set()
    candidates=[]
    for i,packet in enumerate(raw[:packet_cap],1):
        repo, family, source = packet.get("repository"), packet.get("family"), packet.get("source_sha")
        fail(not isinstance(repo,str) or not repo.startswith("GBOGEB/")
             or not isinstance(family,str) or not family
             or not isinstance(source,str) or not HEX40.fullmatch(source)
             or packet.get("dispatch_authorized") is not False
             or packet.get("mutation_paths") != []
             or packet.get("mode") != "READ_ONLY_SCOUT", "UNSAFE_SOURCE_PACKET")
        # A unique repository is a real scheduling constraint. Repeated
        # families on the same repo do not create independent workers.
        fail(repo in seen,"NONDISJOINT_REPOSITORY_PACKET")
        seen.add(repo)
        identity = {"repo":repo,"family":family,"head":source}
        candidates.append({
            "packet_id":"G4-W32-%02d" % i,
            "identity_sha256":sha(serialize(identity)),
            "repo":repo,"family":family,"source_sha":source,
            "run_id":None,"run_attempt":None,"job_id":None,
            "artifact_id":None,"zip_bytes":None,"member_bytes":None,
            "member_sha256":None,"statement_covered":None,
            "statement_total":None,"branch_covered":None,"branch_total":None,
            "observed_at":None,"worker_hours":None,
            "status":"CANDIDATE_NOT_DISPATCHED",
            "native_evidence_class":None,"owner_acceptance":None,
            "dispatch_authorized":False,"authority_transfer":False
        })
    return {
        "schema":PLAN_SCHEMA,
        "producer_repo":OWNER,"producer_head":exact_head,
        "canonical_six_repo_producer_pr":531,
        "source_pulse_sha256":sha(serialize(report)),
        "frozen_historical_breadth":{"observed":6,"eligible":42,"unobserved":36},
        "source_plan_max_parallel":sp["workers_max_parallel"],
        "conservative_new_lane_cap":new_lane_cap,
        "actual_worker_capacity":None,"worker_hours":None,
        "status":"PULL_PLAN_ONLY_NOT_EXECUTED",
        "packet_count":len(candidates),
        "packets":candidates,
        "native_successes_created":0,
        "cross_repo_coverage_gain":None,
        "merge_admission":"HOLD","security_waiver":False,
        "qps_engineering_acceptance":None,
        "authority_transfer":False
    }


def empty_push(plan):
    fail(plan.get("schema") != PLAN_SCHEMA
         or plan.get("status") != "PULL_PLAN_ONLY_NOT_EXECUTED"
         or plan.get("native_successes_created") != 0, "FALSE_PUSH_PRECONDITION")
    return {
        "schema":PUSH_SCHEMA,
        "pull_plan_sha256":sha(serialize(plan)),
        "canonical_receiver":"MC_G4_531_EXISTING_PRODUCER",
        "emissions":[],
        "packets_executed":0,
        "native_receipts_accepted":None,
        "unknown_tail":plan["frozen_historical_breadth"]["unobserved"],
        "status":"EMPTY_NOT_EXECUTED",
        "future_required_identity":["repo","source_sha","run_id","run_attempt",
                                    "job_id","artifact_id","member_sha256",
                                    "scope_hash","numerators","denominators"],
        "member_bytes_validated":None,
        "cross_repo_coverage_gain":None,
        "worker_hours":None,
        "merge_admission":"HOLD",
        "authority_transfer":False
    }


def emit(report, out, *, exact_head, new_lane_cap=1, packet_cap=6):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    plan=make_plan(report,exact_head=exact_head,new_lane_cap=new_lane_cap,packet_cap=packet_cap)
    push=empty_push(plan)
    files={"pull-plan.json":serialize(plan),"empty-push.json":serialize(push)}
    for name,data in files.items():
        (out/name).write_bytes(data)
    manifest={"schema":MANIFEST_SCHEMA,"producer_head":exact_head,
              "source_pulse_sha256":plan["source_pulse_sha256"],
              "publisher":"EXISTING_GOGREEN_G4_ARTIFACT_ONLY",
              "zip_verifier_role":"MC_530_NOT_REPLACED",
              "six_repo_producer_role":"MC_531_NOT_REPLACED",
              "lane_viewer_role":"MC_533_NOT_REPLACED",
              "files_sha256":{name:sha(data) for name,data in files.items()},
              "merge_admission":"HOLD","security_waiver":False,
              "authority_transfer":False,"worker_dispatch":False}
    (out/"manifest.json").write_bytes(serialize(manifest))
    verify(out,exact_head=exact_head)
    return manifest


def verify(out, *, exact_head):
    out=Path(out)
    m=json.loads((out/"manifest.json").read_bytes())
    fail(m.get("schema")!=MANIFEST_SCHEMA
         or m.get("producer_head")!=exact_head
         or m.get("merge_admission")!="HOLD"
         or m.get("worker_dispatch") is not False
         or m.get("security_waiver") is not False
         or m.get("authority_transfer") is not False
         or set(m.get("files_sha256",{})) != {"pull-plan.json","empty-push.json"},
         "INVALID_PACKET_MANIFEST")
    for name,digest in m["files_sha256"].items():
        fail(sha((out/name).read_bytes()) != digest, "PACKET_MEMBER_SHA256_MISMATCH")
    p=json.loads((out/"pull-plan.json").read_bytes())
    x=json.loads((out/"empty-push.json").read_bytes())
    fail(p.get("producer_head")!=exact_head or p.get("packet_count")!=len(p.get("packets",[]))
         or p.get("native_successes_created")!=0 or p.get("status")!="PULL_PLAN_ONLY_NOT_EXECUTED"
         or p.get("actual_worker_capacity") is not None
         or p.get("cross_repo_coverage_gain") is not None,
         "FALSE_PLAN_PROMOTION")
    fail(x.get("pull_plan_sha256")!=sha((out/"pull-plan.json").read_bytes())
         or x.get("emissions")!=[] or x.get("packets_executed")!=0
         or x.get("status")!="EMPTY_NOT_EXECUTED"
         or x.get("native_receipts_accepted") is not None,
         "FABRICATED_PUSH_EMISSION")
    return m


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--rollup",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--head",required=True)
    p.add_argument("--verify-only",action="store_true")
    args=p.parse_args()
    if args.verify_only:
        m=verify(args.out,exact_head=args.head)
    else:
        m=emit(json.loads(args.rollup.read_text(encoding="utf-8")),args.out,
               exact_head=args.head)
    print(json.dumps({"status":"PULL_PLAN_ONLY","producer_head":args.head,
                      "sha256":m["files_sha256"]},sort_keys=True))


if __name__=="__main__":
    main()
