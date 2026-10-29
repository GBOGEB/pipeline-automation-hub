#!/usr/bin/env python3
"""Read-only CI spine: bind existing workflow/DAG/metrics owners without copying their logic.

This is an index/contract adapter, NOT a new scheduler, CI metric owner, release
gate or certification. GitHub runtime/queue/recovery data belongs to the owners
named in AGENTS.md; this script reports source topology only.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "jade.devops.ci-spine.bindings.v1"
REPORT_SCHEMA = "jade.devops.ci-spine.index.v1"
PHASES = ("SOURCE", "TEST", "EVIDENCE", "GOVERN", "OPERATE")
SHA40 = re.compile(r"^[0-9a-f]{40}$")
DEFAULT_CONTRACT = "governance/ci_spine/CI_SPINE_BINDINGS_V1.json"


def _load(module: str, path: Path):
    spec = importlib.util.spec_from_file_location(module, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("canonical source unavailable: " + str(path))
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def _owners():
    root = REPO_ROOT / "mission-control/jade_temple/devops"
    return (_load("ci_spine_workflows", root / "workflows.py"),
            _load("ci_spine_actions_metrics", root / "actions_metrics.py"))


def _safe(root: Path, name: object, prefix: str = "") -> Path | None:
    """Reject escapes, Windows paths, noncanonical aliases and symlink escapes."""
    if not isinstance(name, str) or not name or "\\" in name or "\x00" in name:
        return None
    p = PurePosixPath(name)
    if p.is_absolute() or str(p) != name or any(x in (".", "..") for x in p.parts):
        return None
    if prefix and not name.startswith(prefix):
        return None
    result = (root / name).resolve()
    return result if result.is_relative_to(root.resolve()) else None


def _head(root: Path) -> str | None:
    try:
        p = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=root,
                           capture_output=True, text=True, timeout=8, check=False)
        return p.stdout.strip() if p.returncode == 0 and SHA40.fullmatch(p.stdout.strip()) else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def build(root: Path, contract: dict, expected_sha: str = "", owners=None) -> dict:
    """Index ALL workflows, fail closed only for the declared authoritative anchors."""
    root = root.resolve()
    workflows, actions = owners or _owners()
    errors, advisories, rows, by_path = [], [], [], {}
    if not isinstance(contract, dict) or contract.get("schema") != SCHEMA:
        errors.append("invalid binding schema")
        contract = {}
    if contract.get("coverage_scope") != "anchors_only":
        errors.append("scope must remain anchors_only (unmapped != passing)")
    actual_sha = _head(root)
    if expected_sha:
        if not SHA40.fullmatch(expected_sha):
            errors.append("expected head is not a 40-hex commit")
        elif actual_sha != expected_sha:
            errors.append("exact-head mismatch or unavailable checkout")

    wf_dir = root / ".github/workflows"
    files = sorted([*wf_dir.glob("*.yml"), *wf_dir.glob("*.yaml")]) if wf_dir.is_dir() else []
    if not files:
        errors.append("no workflow inventory")
    for f in files:
        path = f.relative_to(root).as_posix()
        try:
            raw = f.read_text(encoding="utf-8")
            parsed = workflows.parse(raw, path=path, repo="GBOGEB/pipeline-automation-hub")
            malformed = parsed.get("parse_error")
            dag = parsed.get("dag") or {}
            name = parsed.get("name", f.name)
            row = {
                "oid": parsed.get("oid"), "path": path, "name": name,
                "source_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                "class": actions.wf_class(name, path),
                "triggers": parsed.get("triggers", []),
                "schedules": parsed.get("schedules", []),
                "reusable": parsed.get("reusable", False),
                "paths_filtered": parsed.get("paths_filtered", False),
                "permissions": parsed.get("permissions", "UNKNOWN"),
                "jobs": [{"id": j["id"], "oid": j["oid"], "needs": j.get("needs", []),
                          "layer": j.get("layer"), "def_sha256": j.get("def_sha256")}
                         for j in parsed.get("jobs", [])],
                "dag_layers": dag.get("layers", []),
                "dag_edges": dag.get("edges", []),
                "parse_error": malformed,
                "dag_cycle": dag.get("cycle", False),
                "dangling_needs": dag.get("dangling", []),
            }
        except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
            row = {"path": path, "parse_error": "READ_OR_SHAPE: " + type(exc).__name__}
        by_path[path] = row
        rows.append(row)
        if row.get("parse_error") or row.get("dag_cycle") or row.get("dangling_needs"):
            advisories.append(path + ": workflow structure requires review")

    bindings = contract.get("anchors", [])
    if not isinstance(bindings, list) or not bindings:
        errors.append("missing anchor bindings")
        bindings = []
    seen_ids, seen_paths, anchors = set(), set(), []
    for item in bindings:
        if not isinstance(item, dict):
            errors.append("anchor is not an object")
            continue
        ident, path, phase = item.get("id"), item.get("path"), item.get("phase")
        if not isinstance(ident, str) or not re.fullmatch(r"CI-[A-Z0-9-]+", ident):
            errors.append("invalid anchor id: " + repr(ident))
            continue
        if ident in seen_ids:
            errors.append("duplicate anchor id " + ident)
        seen_ids.add(ident)
        valid_path = _safe(root, path, ".github/workflows/")
        if valid_path is None or not str(path).endswith((".yml", ".yaml")):
            errors.append(ident + ": unsafe workflow binding path")
            continue
        if path in seen_paths:
            errors.append("duplicate workflow authority " + path)
        seen_paths.add(path)
        if phase not in PHASES:
            errors.append(ident + ": unknown phase")
        bound = by_path.get(path)
        if bound is None:
            errors.append(ident + ": missing canonical workflow " + path)
        elif bound.get("parse_error") or bound.get("dag_cycle") or bound.get("dangling_needs"):
            errors.append(ident + ": malformed canonical workflow DAG")
        anchors.append({"id": ident, "phase": phase, "path": path,
                        "purpose": item.get("purpose", ""), "workflow_oid": (bound or {}).get("oid"),
                        "static_binding": "PASS" if bound and not (bound.get("parse_error") or
                            bound.get("dag_cycle") or bound.get("dangling_needs")) else "FAIL"})

    declared_owners = contract.get("metric_owner_bindings", {})
    if not isinstance(declared_owners, dict) or not declared_owners:
        errors.append("missing metric owner pointers")
        declared_owners = {}
    agents = root / "AGENTS.md"
    agents_text = agents.read_text(encoding="utf-8") if agents.is_file() else ""
    for metric, path in declared_owners.items():
        file = _safe(root, path)
        if not isinstance(metric, str) or not metric or file is None or not file.is_file():
            errors.append("invalid metric owner pointer " + str(metric))
        elif path not in agents_text:
            errors.append("metric owner not declared in AGENTS.md: " + str(metric))

    edges = contract.get("conceptual_edges", [])
    if not isinstance(edges, list):
        errors.append("conceptual_edges must be a list")
        edges = []
    phase_of = {x["id"]: x["phase"] for x in anchors}
    for edge in edges:
        if not isinstance(edge, list) or len(edge) != 2 or any(e not in phase_of for e in edge):
            errors.append("dangling conceptual edge: " + repr(edge))
        elif phase_of[edge[0]] not in PHASES or phase_of[edge[1]] not in PHASES or (
            PHASES.index(phase_of[edge[0]]) >= PHASES.index(phase_of[edge[1]])
        ):
            errors.append("nonprogressive conceptual edge: " + repr(edge))
    counts = Counter(row.get("class", "UNKNOWN") for row in rows)
    return {
        "schema": REPORT_SCHEMA, "verdict": "CI_SPINE_CONTRACT_FIRST_RED" if errors else "PASS_STATIC_BINDINGS_ONLY",
        "source": {"checkout_sha": actual_sha, "expected_sha": expected_sha or None,
                   "scope": "local_workflow_tree", "live_run_census": "NOT_FETCHED"},
        "assurance": {"badge": "WORKFLOW_STATUS_ONLY", "release": "NOT_ASSESSED",
                      "independent_certification": "NOT_ASSESSED", "merge_admission": "HOLD"},
        "counts": {"workflow_files": len(rows), "anchor_bindings": len(anchors),
                   "unbound_workflows": len(rows) - len(set(a["path"] for a in anchors if a["path"] in by_path)),
                   "structural_advisories": len(advisories), "by_existing_actions_class": dict(sorted(counts.items()))},
        "metric_owner_bindings": declared_owners, "anchors": anchors,
        "conceptual_edges_not_execution_dependencies": edges,
        "workflows": rows, "advisories": advisories, "errors": errors,
        "runtime_owner": "mission-control/jade_temple/devops/actions_metrics.py",
        "root_recovery_owner": "mission-control/gogreen/scale_dock.py",
        "dag_owner": "mission-control/jade_temple/tools/cicd_dag.py",
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--root", type=Path, default=REPO_ROOT)
    p.add_argument("--contract", default=DEFAULT_CONTRACT)
    p.add_argument("--source-sha", default="", help="expected exact 40-hex checkout head")
    p.add_argument("--out", type=Path, help="optional JSON receipt, preferably outside tracked tree")
    p.add_argument("--check", action="store_true", help="exit nonzero on binding or source errors")
    args = p.parse_args(argv)
    path = _safe(args.root.resolve(), args.contract)
    if path is None or not path.is_file():
        print(json.dumps({"verdict": "CI_SPINE_CONTRACT_FIRST_RED", "errors": ["missing or unsafe contract"]}))
        return 1
    try:
        contract = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        print(json.dumps({"verdict": "CI_SPINE_CONTRACT_FIRST_RED", "errors": [type(exc).__name__]}))
        return 1
    report = build(args.root, contract, args.source_sha)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: report[k] for k in ("schema", "verdict", "source", "counts", "errors")},
                     indent=2, sort_keys=True))
    return int(args.check and bool(report["errors"]))


if __name__ == "__main__":
    sys.exit(main())
