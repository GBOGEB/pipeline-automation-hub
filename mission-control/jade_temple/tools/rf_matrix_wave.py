#!/usr/bin/env python3
"""Read-only Mission Control RF wave matrix projection over canonical JADE owners.

Only lifecycle.rf_pulse_plan selects work; B00..B09 SIPOC and bundle DAG are
read from the committed CI Spine design. Metrics remain owned by actions_metrics.
No GitHub API, subprocess, credential, dispatch, merge or gate mutation exists.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BUNDLES = ROOT.parent.parent / "docs" / "ci-spine" / "LOGICAL_BUNDLE_DAG_v1.json"
CONTRACT = ROOT.parent.parent / "docs" / "ci-spine" / "RF_MATRIX_WAVE_v1.json"

def _lifecycle():
    spec = importlib.util.spec_from_file_location("jade_rf_lifecycle", ROOT / "devops" / "lifecycle.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

L = _lifecycle()
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SCHEMA = "jade.devops.rf-matrix.v1"
DAG_SCHEMA = "gbo.ci-spine.logical-bundle-dag.v1"
METRIC_OWNER = "mission-control/jade_temple/devops/actions_metrics.py"


def dag_index(doc: dict) -> tuple[dict, list[tuple]]:
    """Validate design-only B00..B09; no new workflow/metric authority."""
    if doc.get("schema") != DAG_SCHEMA or doc.get("record_type") != "design_only_not_live_workflow_or_authority":
        raise ValueError("not a design-only B00..B09 contract")
    nodes = doc.get("nodes")
    edges = doc.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("missing B00..B09 nodes or edges")
    mapping = {n["short_id"]: n for n in nodes if isinstance(n, dict) and "short_id" in n}
    if (len(mapping) != len(nodes) or set(mapping) != {f"B{i:02d}" for i in range(10)} or
            any(n.get("id") != f"ci-spine:bundle:{k}" for k, n in mapping.items())):
        raise ValueError("missing or duplicate bundle identity")
    for key, node in mapping.items():
        if (not isinstance(node.get("sipoc"), dict) or
                set(node["sipoc"]) != {"supplier", "input", "process", "output", "customer"} or
                any(not isinstance(v, list) or not v for v in node["sipoc"].values())):
            raise ValueError(f"{key}: SIPOC incomplete")
        if not node.get("devops_stage") or not node.get("example_workflow"):
            raise ValueError(f"{key}: missing stage/source anchor")
    links = []
    for edge in edges:
        if edge.get("kind") not in {"FEEDFORWARD", "FEEDBACK_NEXT_PULSE"}:
            raise ValueError("unknown edge type")
        a, b = edge.get("from"), edge.get("to")
        if a not in {n["id"] for n in nodes} or b not in {n["id"] for n in nodes}:
            raise ValueError("dangling bundle edge")
        links.append((a, b, edge["kind"]))
    L.topo_layers([n["id"] for n in nodes], links)
    feedback = [(a, b) for a, b, kind in links if kind == "FEEDBACK_NEXT_PULSE"]
    if feedback != [("ci-spine:bundle:B09", "ci-spine:bundle:B00")]:
        raise ValueError("temporal feedback must be B09 -> next-pulse B00 only")
    return mapping, links


def _reaches(start: str, finish: str, links: list[tuple]) -> bool:
    if start == finish:
        return True
    seen, pending = set(), [start]
    while pending:
        cur = pending.pop()
        if cur in seen:
            continue
        seen.add(cur)
        pending.extend(b for a, b, kind in links if a == cur and kind == "FEEDFORWARD")
        if finish in pending:
            return True
    return False


def validate_matrix(matrix: dict, dag: dict, source_sha: str) -> tuple[dict, list[dict]]:
    bundles, edges = dag_index(dag)
    if not isinstance(source_sha, str) or not HEX40.fullmatch(source_sha):
        raise ValueError("exact source_sha is mandatory")
    if matrix.get("schema") != SCHEMA or matrix.get("authority") != "ADVISORY_NON_DISPATCHING":
        raise ValueError("matrix is not an advisory RF contract")
    lanes = matrix.get("lanes")
    if not isinstance(lanes, list) or not 1 <= len(lanes) <= 32:
        raise ValueError("lane count must be in [1,32]")
    ids = [x.get("id") for x in lanes if isinstance(x, dict)]
    if len(ids) != len(lanes) or any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("missing or duplicate lane IDs")
    bundle_of = {x["id"]: x.get("bundle") for x in lanes}
    steps = []
    for lane in lanes:
        name, bundle = lane["id"], lane.get("bundle")
        if bundle not in bundles:
            raise ValueError(f"{name}: unknown B00..B09 bundle")
        if lane.get("devops_stage") != bundles[bundle]["devops_stage"]:
            raise ValueError(f"{name}: stage not bound to canonical bundle")
        if lane.get("phase") not in L.RF_PHASE_MATURITY or lane.get("crew") not in L.RF_CREW:
            raise ValueError(f"{name}: phase/crew is not canonical")
        if not isinstance(lane.get("t0_ref"), str) or not lane["t0_ref"].strip() or ".." in lane["t0_ref"]:
            raise ValueError(f"{name}: T0 receipt missing or unsafe")
        deps = lane.get("depends_on", [])
        if not isinstance(deps, list) or any(dep not in bundle_of for dep in deps):
            raise ValueError(f"{name}: unregistered dependency")
        for dep in deps:
            src, dst = f"ci-spine:bundle:{bundle_of[dep]}", f"ci-spine:bundle:{bundle}"
            if not _reaches(src, dst, edges):
                raise ValueError(f"{name}: dependency {dep} violates B00..B09 ancestry")
        if lane.get("state") == "DONE":
            receipt = lane.get("execution_receipt")
            if (not isinstance(receipt, dict) or receipt.get("head_sha") != source_sha or
                    not isinstance(receipt.get("run_id"), int) or isinstance(receipt.get("run_id"), bool) or
                    receipt["run_id"] <= 0 or not isinstance(receipt.get("attempt"), int) or
                    receipt["attempt"] < 1 or receipt.get("result") != "success" or
                    not isinstance(receipt.get("test_population"), int) or receipt["test_population"] < 1 or
                    not HEX64.fullmatch(str(receipt.get("digest", "")))):
                raise ValueError(f"{name}: DONE without a shaped exact-head execution receipt")
        steps.append({
            "id": name, "cluster": lane.get("cluster"), "phase": lane.get("phase"),
            "crew": lane.get("crew"), "state": lane.get("state"),
            "source_sha": source_sha, "t0_ref": lane["t0_ref"], "depends_on": deps,
            "write_pr": lane.get("write_pr", False),
            "touch_paths": lane.get("touch_paths", []),
        })
    goal = matrix.get("goal")
    if (not isinstance(goal, dict) or goal.get("metric_owner") != METRIC_OWNER or
            goal.get("comparison") not in ("at_most", "at_least") or
            not isinstance(goal.get("target"), (int, float)) or
            isinstance(goal["target"], bool) or not 0 <= goal["target"] <= 1 or
            not isinstance(goal.get("minimum_sample"), int) or goal["minimum_sample"] <= 0 or
            not goal.get("metric") or not goal.get("sample_method")):
        raise ValueError("goal lacks bounded, owner-bound measurement contract")
    return bundles, steps


def goal_readback(goal: dict, observation: dict | None, head_sha: str) -> dict:
    """Only compare an externally produced value to the goal; never invent rates."""
    out = {"metric": goal["metric"], "target": goal["target"], "status": "UNKNOWN",
           "action": "WAIT_FOR_MATCHED_T1", "admission": "HOLD"}
    if not isinstance(observation, dict):
        return out
    if (observation.get("metric") != goal["metric"] or observation.get("metric_owner") != METRIC_OWNER or
            observation.get("source_sha") != head_sha or
            observation.get("sample_method") != goal["sample_method"]):
        out["reason"] = "WRONG_SOURCE_OR_COHORT"
        return out
    n, value = observation.get("sample_n"), observation.get("value")
    if (not isinstance(n, int) or isinstance(n, bool) or n < goal["minimum_sample"] or
            not isinstance(value, (int, float)) or isinstance(value, bool) or
            not math.isfinite(value) or not 0 <= value <= 1 or
            not HEX64.fullmatch(str(observation.get("receipt_sha256", "")))):
        out["reason"] = "INSUFFICIENT_OR_MALFORMED_EVIDENCE"
        return out
    try:
        now = datetime.fromisoformat(observation["observed_at"].replace("Z", "+00:00"))
        before = datetime.fromisoformat(goal["t0"]["observed_at"].replace("Z", "+00:00"))
        if now <= before or now.tzinfo is None or before.tzinfo is None:
            raise ValueError("stale or naive timestamps")
    except (KeyError, TypeError, AttributeError, ValueError):
        out["reason"] = "STALE_OR_UNKNOWN_TIME"
        return out
    reached = value <= goal["target"] if goal["comparison"] == "at_most" else value >= goal["target"]
    out.update(status="TARGET_REACHED_UNVERIFIED" if reached else "TARGET_NOT_YET_REACHED",
               action="STOP_EXPERIMENT_FOR_INDEPENDENT_REVIEW" if reached else "CONTINUE_RF_WAVES",
               observed_value=value, sample_n=n,
               reason="receipt hash is shape-checked, not independently authenticated")
    return out


def project(matrix: dict, dag: dict, source_sha: str, observation: dict | None = None,
            max_parallel: int = 6, per_cluster: int = 2, open_stack: int = 0) -> dict:
    bundles, steps = validate_matrix(matrix, dag, source_sha)
    plan = L.rf_pulse_plan(steps, source_sha=source_sha, max_parallel=max_parallel,
                           per_cluster=per_cluster, open_stack=open_stack, max_stack=5)
    lane_by_id = {x["id"]: x for x in matrix["lanes"]}
    for category in ("on", "off", "held"):
        for item in plan[category]:
            lane = lane_by_id[item["id"]]
            bundle = bundles[lane["bundle"]]
            item["bundle"] = lane["bundle"]
            item["devops_stage"] = bundle["devops_stage"]
            item["sipoc"] = bundle["sipoc"]
    goal = goal_readback(matrix["goal"], observation, source_sha)
    return {"schema": "jade.devops.rf-matrix-projection.v1",
            "source_sha": source_sha, "basis": {
                "matrix": SCHEMA, "bundle_dag": DAG_SCHEMA,
                "scheduling_owner": "mission-control/jade_temple/devops/lifecycle.py",
                "metrics_owner": METRIC_OWNER,
                "merge_gate_owner": "mission-control/gogreen/required_gate/gate.py"},
            "matrix": plan, "goal": goal,
            "stop_rule": "STOP on evidence target or capacity/blocked; never auto-dispatch",
            "authority": {"merge_authorized": False, "dispatch_performed": False,
                          "admission": "HOLD", "feedback": "B09 -> B00 NEXT_PULSE_ONLY"}}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--matrix", type=Path, default=CONTRACT)
    p.add_argument("--bundles", type=Path, default=BUNDLES)
    p.add_argument("--source-sha", required=True)
    p.add_argument("--observation", type=Path)
    p.add_argument("--max-parallel", type=int, default=6)
    p.add_argument("--per-cluster", type=int, default=2)
    p.add_argument("--open-stack", type=int, default=0)
    p.add_argument("--out", type=Path)
    args = p.parse_args(argv)
    matrix = json.loads(args.matrix.read_text(encoding="utf-8"))
    dag = json.loads(args.bundles.read_text(encoding="utf-8"))
    observation = json.loads(args.observation.read_text(encoding="utf-8")) if args.observation else None
    report = project(matrix, dag, args.source_sha, observation,
                     args.max_parallel, args.per_cluster, args.open_stack)
    data = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(data, encoding="utf-8", newline="\n")
    else:
        print(data, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
