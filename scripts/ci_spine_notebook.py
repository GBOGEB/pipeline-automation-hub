#!/usr/bin/env python3
"""Read-only CI Spine notebook adapter: source JSON -> deterministic offline HTML.

Jacquard-inspired navigation, not the Jacquard implementation. Reuses the merged
CI Spine B00-B09 conceptual DAG and GitHub run timing snapshots; does not own
test results, CI metrics, scheduler, provenance authority, or PDF geometry.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
GRAPH = "docs/ci-spine/LOGICAL_BUNDLE_DAG_v1.json"
RUNS = "docs/ci-spine/RUN_TIMING_SAMPLES_20261028.json"
TEMPLATE = "docs/ci-spine/notebook.template.html"
OUTPUT = "docs/ci-spine/notebook.html"
SCHEMA = "ci-spine.provenance-notebook.readonly.v1"
GRAPH_SCHEMA = "gbo.ci-spine.logical-bundle-dag.v1"
RUNS_SCHEMA = "gbo.ci-spine.run-timing-sample.v1"
REPO = "GBOGEB/pipeline-automation-hub"
# A Git commit which contains the original frozen input files. Not 'current master'.
INPUT_REF = "83a4afecdad5ed41677591922c8f239316a8f638"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
WORKFLOW_PATH = re.compile(r"^\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml$")
PLACEHOLDER = "__CI_SPINE_NOTEBOOK_PAYLOAD__"


def require(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError("CI_SPINE_NOTEBOOK_FIRST_RED:" + code)


def load_sources(root: Path) -> tuple[dict, dict, str, str]:
    g = (root / GRAPH).read_bytes()
    r = (root / RUNS).read_bytes()
    graph, runs = json.loads(g), json.loads(r)
    return graph, runs, hashlib.sha256(g).hexdigest(), hashlib.sha256(r).hexdigest()


def dag_levels(nodes: list[dict], edges: list[dict]) -> dict[str, int]:
    ids = [n["id"] for n in nodes]
    require(len(ids) == len(set(ids)), "DUPLICATE_NODE_ID")
    levels = {x: 0 for x in ids}
    adj = {x: [] for x in ids}
    degree = {x: 0 for x in ids}
    for e in edges:
        require(isinstance(e, dict) and e.get("from") in degree and
                e.get("to") in degree, "DANGLING_EDGE")
        if e.get("kind") == "FEEDBACK_NEXT_PULSE":
            continue
        require(e.get("kind") == "FEEDFORWARD", "UNRECOGNIZED_EDGE_KIND")
        a, b = e["from"], e["to"]
        require(a != b, "SELF_EDGE")
        adj[a].append(b)
        degree[b] += 1
    frontier = sorted(x for x in ids if degree[x] == 0)
    visited = 0
    while frontier:
        n = frontier.pop(0)
        visited += 1
        for child in adj[n]:
            levels[child] = max(levels[child], levels[n] + 1)
            degree[child] -= 1
            if degree[child] == 0:
                frontier.append(child)
                frontier.sort()
    require(visited == len(ids), "WITHIN_PULSE_CYCLE")
    return levels


def safe_lines(text: str, short_id: str) -> int:
    target = '"short_id": "' + short_id + '"'
    positions = [i for i, line in enumerate(text.splitlines(), 1) if target in line]
    require(len(positions) == 1, "SOURCE_ANCHOR_NOT_UNIQUE:" + short_id)
    return positions[0]


def project(graph: dict, runs: dict, *, graph_digest: str,
            runs_digest: str, graph_text: str, source_ref: str = INPUT_REF) -> dict:
    require(HEX40.fullmatch(source_ref) is not None, "INVALID_SOURCE_REF")
    require(graph.get("schema") == GRAPH_SCHEMA, "DAG_SCHEMA")
    require(graph.get("record_type") == "design_only_not_live_workflow_or_authority",
            "DAG_AUTHORITY_BOUNDARY")
    require(runs.get("schema") == RUNS_SCHEMA, "RUNS_SCHEMA")
    require(runs.get("repository") == REPO, "RUNS_REPOSITORY")
    require(HEX40.fullmatch(str(graph.get("source", {}).get("master_sha", ""))) is not None,
            "SOURCE_HEAD")
    require(re.fullmatch("[0-9a-f]{64}", graph_digest) is not None and
            re.fullmatch("[0-9a-f]{64}", runs_digest) is not None,
            "DIGESTS")
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    require(isinstance(nodes, list) and isinstance(edges, list), "DAG_SHAPE")
    require(len(nodes) == 10 and len(edges) == 17, "FROZEN_SCOPE_DRIFT")
    require(set(n.get("short_id") for n in nodes) == {"B%02d" % i for i in range(10)},
            "BUNDLE_POPULATION")
    require(all(n.get("source_class") == "PROPOSED_DESIGN" for n in nodes),
            "ILLEGAL_AUTHORITY_PROMOTION")
    require(all(n.get("id") == "ci-spine:bundle:" + n["short_id"] for n in nodes),
            "NODE_ID_BINDING")
    require(all(WORKFLOW_PATH.fullmatch(str(n.get("example_workflow", "")))
                for n in nodes), "UNSAFE_WORKFLOW_LINK")
    for n in nodes:
        s = n.get("sipoc", {})
        require(all(isinstance(s.get(k), list) and all(isinstance(v, str) for v in s[k])
                    for k in ("supplier", "input", "process", "output", "customer")),
                "MALFORMED_SIPOC")
    next_pulse = [e for e in edges if e.get("kind") == "FEEDBACK_NEXT_PULSE"]
    require(len(next_pulse) == 1 and next_pulse[0]["from"].endswith(":B09") and
            next_pulse[0]["to"].endswith(":B00"), "TEMPORAL_FEEDBACK")
    levels = dag_levels(nodes, edges)
    require(runs.get("sample_count") == len(runs.get("runs", [])), "RUN_POPULATION")
    require(0 < len(runs["runs"]) <= 100, "RUN_SAMPLE_BOUNDS")
    timing_rows = []
    for r in runs["runs"]:
        require(isinstance(r.get("run_id"), int) and r["run_id"] > 0, "RUN_ID")
        require(HEX40.fullmatch(str(r.get("source_sha", ""))) is not None, "RUN_SOURCE_SHA")
        require(isinstance(r.get("jobs"), list), "RUN_JOBS")
        for j in r["jobs"]:
            q, t = j.get("queue_seconds"), j.get("execution_seconds")
            require(q is None or (type(q) is int and q >= 0), "QUEUE_CLOCK")
            require(t is None or (type(t) is int and t >= 0), "EXECUTION_CLOCK")
            timing_rows.append({
                "run_id": r["run_id"], "name": r["name"], "event": r["event"],
                "source_sha": r["source_sha"], "run_attempt": r["attempt"],
                "job": j["name"], "queue_seconds": q, "execution_seconds": t,
                "conclusion": j.get("conclusion"),
                "url": "https://github.com/" + REPO + "/actions/runs/" + str(r["run_id"]),
            })
    base = "https://github.com/" + REPO + "/blob/" + source_ref + "/"
    annotated = []
    for n in nodes:
        row = dict(n)
        row["layer"] = levels[n["id"]]
        row["source_pointer"] = {
            "kind": "json-pointer", "file": GRAPH,
            "pointer": "/nodes/" + str(nodes.index(n)),
            "line": safe_lines(graph_text, n["short_id"]),
            "href": base + GRAPH + "#L" + str(safe_lines(graph_text, n["short_id"])),
            "stable_view_anchor": "#bundle=" + n["short_id"],
            "mapping_accuracy": "EXACT_FILE_AND_JSON_MEMBER_NOT_PDF_COORDINATES",
        }
        row["workflow_href"] = base + n["example_workflow"]
        annotated.append(row)
    return {
        "schema": SCHEMA,
        "assurance": {"source_class": "FROZEN_SOURCE_SUPPORTED_NAVIGATION",
                      "not_live": True, "merge_admission": "HOLD",
                      "release_approval": "NOT_EVALUATED",
                      "pdf_location_mapping": "UNAVAILABLE",
                      "run_dispatch": False, "authority_transfer": False},
        "sources": {"repo": REPO, "graph_sha256": graph_digest,
                    "timing_sha256": runs_digest, "graph_source_sha": graph["source"]["master_sha"],
                    "frozen_ref_for_source_links": source_ref,
                    "timing_window": runs["observed_window"]},
        "nodes": annotated, "edges": edges, "timings": timing_rows,
        "crosslinks": [
            {"title": "CI Spine source index", "href": "../../governance/ci_spine/README.md"},
            {"title": "Canonical JADE DAG / SIPOC", "href": "../../mission-control/jade_temple/site/cicd_dag.html"},
            {"title": "Plotly Mission Control generator", "href": "../../mission-control/federation-atlas/mission_rebuild/w2_plotly.py"},
            {"title": "Interactive Mission Control W18", "href": "../mission-control/w18/index.html"},
        ],
        "source_urls": {"graph": base + GRAPH, "timing": base + RUNS,
                        "pr989": "https://github.com/" + REPO + "/pull/989",
                        "pr992": "https://github.com/" + REPO + "/pull/992"},
    }


def render(template: str, projection: dict) -> str:
    require(template.count(PLACEHOLDER) == 1, "TEMPLATE_SLOT")
    # Escaped JSON data only, never executable source. Rendering code uses textContent.
    raw = json.dumps(projection, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    raw = raw.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return template.replace(PLACEHOLDER, raw).replace("\r\n", "\n")


def build(root: Path) -> str:
    graph, runs, gd, rd = load_sources(root)
    template = (root / TEMPLATE).read_text(encoding="utf-8")
    graph_text = (root / GRAPH).read_text(encoding="utf-8")
    return render(template, project(graph, runs, graph_digest=gd, runs_digest=rd,
                                    graph_text=graph_text))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--root", type=Path, default=ROOT)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    a = p.parse_args(argv)
    rendered = build(a.root)
    target = a.root / OUTPUT
    if a.check:
        # Structural HTML parity and *semantic* JSON parity; JSON member order is
        # not a source identity or approval signal. Reject unescaped script data.
        if not target.is_file():
            print("CI_SPINE_NOTEBOOK_MISSING", file=sys.stderr)
            return 1
        template = (a.root / TEMPLATE).read_text(encoding="utf-8")
        prefix, suffix = template.split(PLACEHOLDER)
        actual = target.read_text(encoding="utf-8")
        if not actual.startswith(prefix) or not actual.endswith(suffix):
            print("CI_SPINE_NOTEBOOK_TEMPLATE_DRIFT", file=sys.stderr)
            return 1
        payload = actual[len(prefix):len(actual) - len(suffix)]
        if "<" in payload or "&" in payload:
            print("CI_SPINE_NOTEBOOK_UNSAFE_PAYLOAD", file=sys.stderr)
            return 1
        try:
            actual_doc = json.loads(payload)
            expected_doc = json.loads(rendered[len(prefix):len(rendered) - len(suffix)])
        except json.JSONDecodeError:
            print("CI_SPINE_NOTEBOOK_INVALID_JSON", file=sys.stderr)
            return 1
        if actual_doc != expected_doc:
            print("CI_SPINE_NOTEBOOK_SOURCE_DRIFT", file=sys.stderr)
            return 1
        print("CI_SPINE_NOTEBOOK_PARITY_PASS")
        return 0
    target.write_text(rendered, encoding="utf-8", newline="\n")
    print("CI_SPINE_NOTEBOOK_WROTE:" + target.as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main())
