"""W380: bounded P1 fan-in trains; read-only, deterministic, never autonomous dispatch.

Composes canonical W378 P1 two-wave plans (two reader slots) into a finite
four-wave exercise. No independent census, PR/issue status or scheduler exists.
"""
from __future__ import annotations
import argparse
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
from metric_atlas import topic_exchange, topic_wave, topic_wave_scale

SCHEMA = "qps.topic-train.plan.v1"
RECEIPT = "qps.topic-train.receipt.v1"
MODES = ("READ_ONLY_SOURCE_DECLARED", "SYNTHETIC_REPEAT_TEST_ONLY")


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def synthetic_twin(six):
    """Test-only second partition: NEW TOPIC ALIASES, SAME HISTORICAL SOURCE BYTES.

    Never imply six new source-verified topics or a second actual repository scan.
    """
    second = copy.deepcopy(six)
    for pulse in second["waves"]:
        pulse["cohort"] = "W380-" + pulse["cohort"]
        for row in pulse["packets"]:
            p = row["packet"]
            row["packet"] = topic_exchange.create_packet(
                topic="w380." + p["topic"], producer_repo=p["producer_repo"],
                producer_head=p["producer_head"], scope_sha256=p["scope_sha256"],
                source_sha256=p["source_sha256"], receipt_sha256=p["receipt_sha256"],
                recipients=p["recipients"], sequence=p["sequence"],
                observed_at=p["observed_at"], expires_at=p["expires_at"],
                prior_packet_sha256=p["prior_packet_sha256"],
                evidence_class=p["evidence_class"])
    # The old PR and issue IDs are not new independent outcomes.
    second["bd_targets"] = []
    return {"schema":SCHEMA, "mode":"SYNTHETIC_REPEAT_TEST_ONLY",
            "max_parallel_readers":2, "goal_unique_topic_ids":12,
            "partitions":[copy.deepcopy(six), second],
            "native_runners_launched":0, "source_writers":0,
            "authority_transfer":False, "merge_admission":"HOLD"}


def plan(doc):
    require(type(doc) is dict and set(doc) == {
        "schema", "mode", "max_parallel_readers", "goal_unique_topic_ids",
        "partitions", "native_runners_launched", "source_writers",
        "authority_transfer", "merge_admission"}, "INVALID_TRAIN_FIELDS")
    require(doc["schema"] == SCHEMA and doc["mode"] in MODES, "INVALID_TRAIN_MODE")
    require(doc["authority_transfer"] is False and doc["merge_admission"] == "HOLD",
            "AUTHORITY_ESCALATION")
    require(type(doc["native_runners_launched"]) is int and doc["native_runners_launched"] == 0
            and type(doc["source_writers"]) is int and doc["source_writers"] == 0,
            "UNPROVEN_PHYSICAL_EXECUTION")
    require(type(doc["max_parallel_readers"]) is int and doc["max_parallel_readers"] == 2,
            "UNPROVEN_READER_CAPACITY")
    require(type(doc["goal_unique_topic_ids"]) is int and
            6 <= doc["goal_unique_topic_ids"] <= 24, "UNBOUNDED_GOAL")
    partitions = doc["partitions"]
    require(type(partitions) is list and 1 <= len(partitions) <= 4,
            "UNBOUNDED_PARTITION_COUNT")
    outputs, topics, target_ids = [], set(), set()
    pinned_graph = None
    previous = None
    clock_waves = 0
    source_fingerprints = set()
    for index,part in enumerate(partitions,1):
        require(type(part) is dict and part.get("max_parallel_readers") ==
                doc["max_parallel_readers"], "INCONSISTENT_READER_CAP")
        p1 = topic_wave_scale.plan(part)  # canonical W378 P1 verifier
        require(p1["planned_topic_count"] == 6 and p1["wave_count"] == 2,
                "P1_CONTRACT_DRIFT")
        if pinned_graph is None:
            pinned_graph = p1["source_graph_sha256"]
        require(p1["source_graph_sha256"] == pinned_graph, "CROSS_PARTITION_GRAPH_DRIFT")
        group_topics = set()
        for wave in part["waves"]:
            for row in wave["packets"]:
                pkt = topic_exchange.verify_packet(row["packet"])
                key = pkt["topic"]
                require(key not in topics and key not in group_topics,
                        "CROSS_PARTITION_TOPIC_COLLISION")
                group_topics.add(key)
                source_fingerprints.add((pkt["producer_repo"], pkt["producer_head"],
                    pkt["scope_sha256"], pkt["source_sha256"]))
        for target in part["bd_targets"]:
            key = (target["kind"],target["repo"],target["number"])
            require(key not in target_ids,"CROSS_PARTITION_TARGET_COLLISION")
            target_ids.add(key)
        topics.update(group_topics)
        clock_waves += 2
        receipt = {"partition":index, "state":"DECLARED_PLAN_NOT_DISPATCHED",
                   "parent_sha256":previous, "p1_plan_sha256":p1["plan_sha256"],
                   "topic_ids":sorted(group_topics), "wave_receipts":[
                       w["receipt_sha256"] for w in p1["waves"]],
                   "source_graph_sha256":pinned_graph,
                   "pause_state":"RECONCILE_OFFLINE_NO_ELAPSED_TIME_CLAIM",
                   "source_writers":0, "actual_reader_jobs":None}
        receipt["receipt_sha256"] = topic_wave.digest(receipt)
        previous = receipt["receipt_sha256"]
        outputs.append(receipt)
    met = len(topics) >= doc["goal_unique_topic_ids"]
    nodes = ["START"]
    edges = []
    prior = "START"
    for i in range(1,len(outputs)+1):
        a,b,pause = ("B%d_W1"%i, "B%d_W2"%i, "B%d_RECONCILE"%i)
        nodes.extend((a,b,pause))
        edges.extend(((prior,a,"DEPENDS"),(a,b,"DEPENDS"),(b,pause,"BARRIER")))
        prior=pause
    nodes.append("ADMISSION_HOLD")
    edges.append((prior,"ADMISSION_HOLD","GATE"))
    edges.append(("ADMISSION_HOLD","START","NEXT_PULSE"))
    sipoc = [{
        "partition":r["partition"],
        "S":sorted(set(row["packet"]["producer_repo"] for w in part["waves"]
                       for row in w["packets"])),
        "I":{"source":"W377 immutable packet metadata","topics":len(r["topic_ids"]),
             "p1_plan_sha256":r["p1_plan_sha256"]},
        "P":"Reuse topic_wave_scale.plan; two 3-topic wave barriers, <=2 reader slots",
        "O":{"receipt_sha256":r["receipt_sha256"],"authority":"DECLARED_ONLY"},
        "C":"Existing declared subscriber, engineering and governance owners"
    } for r,part in zip(outputs,partitions)]
    r={"schema":RECEIPT,"source_plan_sha256":topic_wave.digest(doc),
       "cohort":"DECLARED_TOPICS_NOT_ACTUAL_SOURCE_COVERAGE",
       "mode":doc["mode"],"topics_unique_declared":len(topics),
       "topic_evaluations":sum(len(o["topic_ids"]) for o in outputs),
       "distinct_source_fingerprints":len(source_fingerprints),
       "goal_unique_topic_ids":doc["goal_unique_topic_ids"],
       "declared_goal_reached":met,"real_goal_verified":False,
       "stop_reason":"MISSING_NATIVE_QUEUE_AND_CONTROLLER_ACK" if met
            else "DECLARED_PLAN_EXHAUSTED",
       "partitions":outputs,"within_pulse_waves":clock_waves,
       "max_parallel_readers_declared":doc["max_parallel_readers"],
       "wave_barriers":len(outputs), "pinned_graph_sha256":pinned_graph,
       "dag":{"nodes":nodes,"edges":[{"from":a,"to":b,"kind":k}
                                     for a,b,k in edges],
              "same_pulse_acyclic":True,"temporal_feedback_edges":1},
       "sipoc":sipoc,
       "metrics":{"actual_reader_jobs":None,"actual_queue_p95_seconds":None,
                  "actual_runner_minutes":None,"verified_external_acks":None,
                  "saved_scan_minutes":None,"accepted_root_closures":None,
                  "native_runners_launched":0,"source_writers":0,
                  "new_cron_jobs_created":0,"formal_credit_delta":0},
       "scale_admission":"HOLD","merge_admission":"HOLD","authority_transfer":False}
    r["receipt_sha256"]=topic_wave.digest(r)
    return r


def mermaid(report):
    names=set(report["dag"]["nodes"])
    require("START" in names and "ADMISSION_HOLD" in names, "MISSING_DAG_ENDS")
    lines=["flowchart LR","%% read-only wave train, next pulse feedback excluded from DAG"]
    for name in report["dag"]["nodes"]:
        lines.append("  "+name+"[\""+name.replace("_"," ")+"\"]")
    for edge in report["dag"]["edges"]:
        symbol="-.->" if edge["kind"] == "NEXT_PULSE" else "-->"
        lines.append("  "+edge["from"]+" "+symbol+" "+edge["to"])
    return "\n".join(lines)+"\n"


def emit(doc,out):
    report=plan(doc)
    folder=Path(out);folder.mkdir(parents=True,exist_ok=True)
    outputs={"train-receipt.json":json.dumps(report,indent=2,sort_keys=True)+"\n",
             "wave-dag.mmd":mermaid(report),
             "sipoc.json":json.dumps(report["sipoc"],indent=2,sort_keys=True)+"\n"}
    manifest={"schema":"qps.topic-train.manifest.v1",
              "source_plan_sha256":report["source_plan_sha256"],
              "files_sha256":{},
              "authority_transfer":False,"merge_admission":"HOLD"}
    for name,data in outputs.items():
        binary=data.encode("utf-8")
        (folder/name).write_bytes(binary)
        manifest["files_sha256"][name]=hashlib.sha256(binary).hexdigest()
    (folder/"manifest.json").write_text(
        json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8",newline="\n")
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    x=p.add_mutually_exclusive_group(required=True)
    x.add_argument("--input",type=Path)
    x.add_argument("--demo-seed-p1",type=Path)
    p.add_argument("--out",required=True,type=Path)
    args=p.parse_args(argv)
    seed=json.loads((args.input or args.demo_seed_p1).read_text(encoding="utf-8"))
    if args.demo_seed_p1:
        seed=synthetic_twin(seed)
    r=emit(seed,args.out)
    print(json.dumps({"declared_topic_ids":r["topics_unique_declared"],
         "real_goal_verified":r["real_goal_verified"],
         "stop_reason":r["stop_reason"],
         "merge_admission":r["merge_admission"]},sort_keys=True))


if __name__=="__main__":
    main()
