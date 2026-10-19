#!/usr/bin/env python3
"""Read-only CODE PURPLE Mission Control operator graph.

Inputs are existing canonical registries and a historical SIPOC planning sample.
No dispatch, new owner SSOT, API mutation, or release/engineering credit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ATLAS = HERE.parent
SHA40 = re.compile(r"[a-f0-9]{40}\Z")
REPOS = (
    ("ABACUS / DOW", "GBOGEB/ABACUS", "Process, CI, source-owned repairs"),
    ("CODEX / KEB", "GBOGEB/CODEX", "Semantic control and KEB contracts"),
    ("QPS Cryoplant", "GBOGEB/cryoplant-project", "Owner engineering DoV"),
    ("Mission Control", "GBOGEB/pipeline-automation-hub", "Federation orchestration/observation"),
    ("gg_MATH", "GBOGEB/gg_MATH", "PCA, BT and method provider"),
)
FILES = ("index.html", "graph.json", "graph.mmd")


def require(value, message):
    if not value:
        raise ValueError("MC_REBUILD_FAIL_CLOSED: " + message)


def read(path):
    raw = Path(path).read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def node_id(prefix, name):
    return prefix + "_" + re.sub(r"[^A-Za-z0-9_]", "_", name)


def project(lanes, beam_graph, plan, source_sha, source_digests):
    require(isinstance(source_sha, str) and SHA40.fullmatch(source_sha), "exact checkout SHA")
    require(lanes.get("schema") == "missioncontrol.federation_atlas.process_lanes.v1"
            and lanes.get("observer_authority") == "READ_ONLY", "Method Atlas authority")
    require(beam_graph.get("schema") == "missioncontrol.code_purple.beams_dag.v1"
            and beam_graph.get("authority_transfer") is False
            and beam_graph.get("formal_credit_delta") == 0
            and beam_graph.get("engineering_credit_delta") == 0, "beam authority")
    require([s.get("key") for s in lanes.get("sipoc", [])] == list("SIPOC"), "SIPOC source")
    require(plan.get("schema") == "missioncontrol.sipoc-process-instances.v1"
            and plan.get("dispatch_authorized") is False
            and plan.get("authority_transfer") is False, "historical planner control")
    repo_nodes, nodes, edges, seen = [], [], [], set()
    def add(n):
        require(n["id"] not in seen, "duplicate atom " + n["id"])
        seen.add(n["id"])
        nodes.append(n)
    for label, full, role in REPOS:
        n = {"id": node_id("REPO", full.rsplit("/", 1)[-1]), "kind": "REPO",
             "label": label, "repo": full, "role": role,
             "url": "https://github.com/" + full}
        add(n)
        repo_nodes.append(n)
    previous = None
    process_count, lane_names = 0, set()
    for lane in lanes.get("lanes", []):
        name = lane.get("id")
        require(isinstance(name, str) and name not in lane_names, "duplicate lane")
        lane_names.add(name)
        rows = lane.get("stages", [])
        require(isinstance(rows, list) and len(rows) > 0, "empty lane")
        prior_stage = None
        for stage in rows:
            require(isinstance(stage, list) and len(stage) == 6
                    and all(isinstance(x, str) and x for x in stage), "stage atom")
            n = {"id": node_id("STAGE", name + "_" + stage[0]), "kind": "STAGE",
                 "label": stage[1], "stage": stage[0], "lane": name,
                 "input": stage[2], "output": stage[3], "metric": stage[4],
                 "failure": stage[5]}
            add(n)
            process_count += 1
            if prior_stage:
                edges.append({"source": prior_stage, "target": n["id"],
                              "kind": "PROCESS", "temporal": "SAME_PULSE"})
            prior_stage = n["id"]
        first = node_id("STAGE", name + "_" + rows[0][0])
        if previous:
            edges.append({"source": previous, "target": first,
                          "kind": "PROCESS", "temporal": "SAME_PULSE"})
        previous = prior_stage
    require(len(lane_names) == 10 and process_count == 39, "canonical process population drift")
    beams = set()
    for b in beam_graph.get("beams", []):
        bid = b.get("id")
        require(isinstance(bid, str) and bid not in beams, "duplicate beam")
        beams.add(bid)
        add({"id": node_id("BEAM", bid), "kind": "BEAM", "label": b["title"],
             "beam": bid, "lane": b["lane"], "entry": b["entry"],
             "exit": b["exit"], "trigger": b["trigger"]})
    for e in beam_graph.get("edges", []):
        require(e.get("from") in beams and e.get("to") in beams
                and e.get("type") in {"FEEDFORWARD", "FEEDBACK"}, "beam dependency")
        edges.append({"source": node_id("BEAM", e["from"]),
                      "target": node_id("BEAM", e["to"]),
                      "kind": e["type"],
                      "temporal": "NEXT_PULSE" if e["type"] == "FEEDBACK" else "SAME_PULSE",
                      "carries": e.get("carries", "")})
    # A same-pulse graph must be acyclic; feedback is a next-pulse link only.
    adj = {node_id("BEAM", b): [] for b in beams}
    for e in edges:
        if e["kind"] == "FEEDFORWARD":
            adj[e["source"]].append(e["target"])
    active, done = set(), set()
    def visit(v):
        require(v not in active, "same-pulse beam cycle")
        if v in done:
            return
        active.add(v)
        for w in adj[v]:
            visit(w)
        active.remove(v)
        done.add(v)
    for v in adj:
        visit(v)
    cap, per_repo = plan.get("max_parallel"), plan.get("max_parallel_per_repo")
    require(type(cap) is int and 1 <= cap <= 6
            and type(per_repo) is int and 1 <= per_repo <= cap, "sample planner capacity")
    workers = []
    ids = set()
    for w in plan.get("instances", []):
        require(w.get("id") not in ids and w.get("state") in ("READY", "BLOCKED", "PROOF_PENDING")
                and w.get("repo") and w.get("stage_ref"), "historical worker row")
        ids.add(w["id"])
        workers.append({"id": w["id"], "repo": w["repo"], "stage": w["stage_ref"],
                        "status": w["state"], "mode": w.get("mode"),
                        "depends_on": w.get("depends_on", []),
                        "lease_paths": w.get("mutation_paths", []),
                        "source_sha": w.get("source_sha"),
                        "owner_issue": w.get("owner_issue"),
                        "blockers": w.get("blockers", [])})
    require(all(set(w["depends_on"]).issubset(ids) for w in workers),
            "unbound worker prerequisites")
    return {
        "schema": "missioncontrol.makeover.projection.v1",
        "source_sha": source_sha,
        "source_digests_sha256": source_digests,
        "provenance": "CANONICAL_METHOD_AND_BEAM_REGISTRIES_PLUS_HISTORICAL_WORKER_SAMPLE",
        "repos": repo_nodes, "nodes": nodes, "edges": edges, "sipoc": lanes["sipoc"],
        "scheduler": {
            "source": "mission-control/gogreen/sipoc_instances.py",
            "dispatch_authorized": False,
            "historical_sample_max_parallel": cap,
            "historical_sample_per_repo": per_repo,
            "actual_worker_capacity": None,
            "worker_hours": None,
            "workers": workers},
        "population": {
            "repositories": len(repo_nodes), "lanes": len(lane_names),
            "process_atoms": process_count, "beams": len(beams),
            "nodes": len(nodes), "edges": len(edges),
            "next_pulse_feedback_edges": sum(e["temporal"] == "NEXT_PULSE" for e in edges)},
        "gate": {"merge_admission": "HOLD", "security_waiver": False,
                 "authority_transfer": False, "qps_acceptance": None,
                 "native_cross_repo_proof": None,
                 "cross_repo_coverage_delta": None,
                 "accepted_root_closures": None,
                 "m1": "STRUCTURAL_MODEL_ONLY", "m2": "HOLD", "m3": "HOLD",
                 "pca": None, "bt": None}
    }


def mermaid(model):
    lines = ["flowchart LR", "  %% Canonical beams; dashed FEEDBACK reaches the next pulse only."]
    for n in model["nodes"]:
        if n["kind"] == "BEAM":
            label = (n["beam"] + " - " + n["label"]).replace('"', "'")
            lines.append('  ' + n["id"] + '["' + label + '"]')
    for e in model["edges"]:
        if e["kind"] == "FEEDFORWARD":
            lines.append("  " + e["source"] + " --> " + e["target"])
        elif e["kind"] == "FEEDBACK":
            lines.append('  ' + e["source"] + ' -. "N+1" .-> ' + e["target"])
    lines.append("  %% Refer to graph.json for 39 process atoms and five repositories.")
    return "\n".join(lines) + "\n"


def build(atlas, output, source_sha, worker_sample):
    atlas, output = Path(atlas), Path(output)
    files = {"lanes": atlas / "PROCESS_LANES_v1.json",
             "beams": atlas / "CODE_PURPLE_BEAMS_DAG_v1.json",
             "workers": Path(worker_sample)}
    data, digests = {}, {}
    for k, path in files.items():
        data[k], digests[k] = read(path)
    model = project(data["lanes"], data["beams"], data["workers"], source_sha, digests)
    output.mkdir(parents=True, exist_ok=True)
    (output / "graph.json").write_text(json.dumps(model, sort_keys=True, indent=2,
                                    ensure_ascii=False) + "\n", encoding="utf-8")
    (output / "graph.mmd").write_text(mermaid(model), encoding="utf-8")
    template = (HERE / "template.html").read_text(encoding="utf-8")
    require(template.count("__GRAPH_DATA__") == 1, "HTML model slot")
    embedded = json.dumps(model, ensure_ascii=False).replace("<", "\\u003c").replace("&", "\\u0026")
    (output / "index.html").write_text(template.replace("__GRAPH_DATA__", embedded), encoding="utf-8")
    manifest = {
        "schema": "missioncontrol.makeover.manifest.v1",
        "source_sha": source_sha,
        "input_sha256": digests,
        "published_by": "EXISTING_METHOD_ATLAS_PAGES_ONLY",
        "merge_admission": "HOLD", "security_waiver": False,
        "authority_transfer": False,
        "files_sha256": {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                         for name in FILES}}
    (output / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--atlas", default=str(ATLAS))
    p.add_argument("--out", required=True)
    p.add_argument("--source-sha", required=True)
    p.add_argument("--workers", default=str(ATLAS.parent / "gogreen/samples/sipoc_instance_wave_20261016.json"))
    a = p.parse_args()
    print(json.dumps(build(a.atlas, a.out, a.source_sha, a.workers), sort_keys=True))
