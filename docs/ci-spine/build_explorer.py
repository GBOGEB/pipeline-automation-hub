#!/usr/bin/env python3
"""Deterministic, stdlib-only offline CI-spine viewer from PR #992 frozen receipts.

The canonical metric owners remain JADE workflow/DAG/actions_metrics modules.
This generator is a read-only presentation adapter; it executes no GitHub or shell jobs.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "explorer_template.html"
OUTPUT = HERE / "explorer.html"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SENTINEL = "__SPINE_JSON__"


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError("CI_SPINE_EXPLORER_FIRST_RED:" + code)


def load_sources(here: Path = HERE):
    names = ("WORKFLOW_INDEX_20261028.json", "TEST_FILE_INDEX_20261028.json",
             "LOGICAL_BUNDLE_DAG_v1.json", "RUN_TIMING_SAMPLES_20261028.json",
             "WORKSTREAM_STATUS_v1.json")
    return tuple(json.loads((here / name).read_text("utf-8")) for name in names)


def project(workflows: dict, tests: dict, dag: dict, timings: dict, status: dict) -> dict:
    require(workflows.get("schema") == "gbo.ci-spine.workflow-index.advisory.v1", "WF_SCHEMA")
    require(tests.get("schema") == "gbo.ci-spine.test-file-index.advisory.v1", "TEST_SCHEMA")
    require(dag.get("schema") == "gbo.ci-spine.logical-bundle-dag.v1", "DAG_SCHEMA")
    require(timings.get("schema") == "gbo.ci-spine.run-timing-sample.v1", "RUN_SCHEMA")
    require(status.get("schema") == "gbo.ci-spine.workstream-status.advisory.v1", "PLAN_SCHEMA")
    sha = workflows["source"]["head_sha"]
    require(bool(SHA40.fullmatch(sha)), "SNAPSHOT_SHA40")
    require(tests["source"]["head_sha"] == sha
            and dag["source"]["master_sha"] == sha
            and status["source"]["catalog_snapshot_head"] == sha, "SINGLE_SNAPSHOT_SOURCE")
    require(status["source"]["main_head_after_989"] != sha, "FROZEN_DISTINGUISHED_FROM_MAIN")
    w = workflows["workflows"]
    t = tests["files"]
    require(len(w) == workflows["counts"]["workflow_files"] == 182, "WORKFLOW_POPULATION")
    require(len(t) == tests["counts"]["test_named_files"] == 307, "TEST_SOURCE_POPULATION")
    require(len({x["path"] for x in w}) == len(w)
            and len({x["path"] for x in t}) == len(t), "UNIQUE_SOURCE_PATHS")
    require(len({x["blob_oid"] for x in w}) >= 1
            and all(SHA40.fullmatch(x["blob_oid"]) for x in w + t), "SOURCE_BLOB_SHAPES")
    require(all(x["alias_approved"] is False for x in w), "PROPOSED_ALIAS_ONLY")
    require(all(x["admission_snapshot"] in ("ENFORCED","OBSERVED","EXCLUDED","UNLISTED") for x in w),
            "ADMISSION_CLASS")
    require(workflows["counts"]["unlisted"] ==
            [".github/workflows/n6-crew-slow-burn.yml"], "UNKNOWN_NOT_AUTO_ENFORCED")
    nodes, edges = dag["nodes"], dag["edges"]
    ids = {x["id"] for x in nodes}
    require(len(nodes) == len(ids) == 10, "NODE_UNIQUENESS")
    require(len(edges) == 17 and all(x["from"] in ids and x["to"] in ids for x in edges),
            "EDGE_SET")
    require(sum(x["kind"] == "FEEDBACK_NEXT_PULSE" for x in edges) == 1
            and sum(x["kind"] == "FEEDFORWARD" for x in edges) == 16, "TEMPORAL_BOUNDARY")
    graph = {i: [] for i in ids}
    for edge in edges:
        if edge["kind"] == "FEEDFORWARD":
            graph[edge["from"]].append(edge["to"])
    visiting, visited = set(), set()

    def visit(node):
        require(node not in visiting, "DAG_CYCLE")
        if node in visited:
            return
        visiting.add(node)
        for other in graph[node]:
            visit(other)
        visiting.remove(node)
        visited.add(node)

    for node in ids:
        visit(node)
    require(all(x["source_class"] == "PROPOSED_DESIGN" for x in nodes), "AUTHORITY_BOUNDARY")
    runs = timings["runs"]
    require(timings["sample_count"] == len(runs) == 8
            and len({x["run_id"] for x in runs}) == len(runs), "SAMPLED_RUNS")
    require(all(SHA40.fullmatch(x["source_sha"])
                and isinstance(x["run_id"], int) and x["run_id"] > 0
                and x["attempt"] >= 1 for x in runs), "RUN_IDENTITY")
    require(all(isinstance(j.get("execution_seconds"), (int,float))
                and j["execution_seconds"] >= 0
                and (j["queue_seconds"] is None or j["queue_seconds"] >= 0)
                for x in runs for j in x["jobs"] if j["started_at"] and j["completed_at"]),
            "NONNEGATIVE_JOB_CLOCK")
    items = status["items"]
    require(len(items) >= 8 and len({x["id"] for x in items}) == len(items),
            "UNIQUE_WORKSTREAMS")
    require(all(x["stage"] != "PASS" for x in items if x["id"] != "JQ-00"),
            "NO_FALSE_GREEN_WORKSTREAM")
    return {
        "schema": "gbo.ci-spine.explorer-projection.readonly.v1",
        "source": {
            "repository": workflows["source"]["repository"],
            "snapshot_head": sha,
            "observed_window": timings["observed_window"],
            "main_head_at_readback": status["source"]["main_head_after_989"],
            "authority": "ADVISORY_FROZEN_NOT_CURRENT_CI",
        },
        "counts": {
            "test_named_files": len(t),
            "admission_ledger_entries": workflows["counts"]["admission_ledger_entries"],
        },
        "nodes": nodes,
        "edges": edges,
        "workflows": [
            {k: x[k] for k in ("path","blob_oid","group","legacy_name",
                               "proposed_alias","admission_snapshot","alias_approved")}
            for x in w
        ],
        "runs": runs,
        "workstreams": items,
    }


def compact_json(value: dict) -> str:
    """Safe text in a script[type=application/json], never executable source code."""
    return (json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
            .replace("<", r"\u003c").replace(">", r"\u003e").replace("&", r"\u0026"))


def render(here: Path = HERE) -> bytes:
    data = project(*load_sources(here))
    template = (here / "explorer_template.html").read_text("utf-8")
    require(template.count(SENTINEL) == 1, "SINGLE_DATA_SENTINEL")
    require("<script src=" not in template
            and "connect-src 'none'" in template, "OFFLINE_NO_REMOTE_JS")
    return template.replace(SENTINEL, compact_json(data)).encode("utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    m = parser.add_mutually_exclusive_group(required=True)
    m.add_argument("--write", action="store_true")
    m.add_argument("--check", action="store_true")
    a = parser.parse_args(argv)
    output = render()
    digest = hashlib.sha256(output).hexdigest()
    if a.check:
        require(OUTPUT.exists() and OUTPUT.read_bytes() == output,
                "STALE_OR_NONDETERMINISTIC_HTML")
        print(json.dumps({"verdict": "PASS", "sha256": digest, "bytes": len(output),
                          "source_kind": "FROZEN_ADVISORY", "network_calls": 0}, sort_keys=True))
    else:
        OUTPUT.write_bytes(output)
        print(json.dumps({"generated": str(OUTPUT), "sha256": digest,
                          "bytes": len(output), "merge_authorized": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
