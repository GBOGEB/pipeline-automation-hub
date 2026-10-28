#!/usr/bin/env python3
"""Advisory CI bundle census: reuse JADE workflow parser without new gate authority."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import workflows

ROOT = Path(__file__).resolve().parents[3]
CATALOG = Path(__file__).with_name("CI_BUNDLE_CATALOG_V1.json")


def inventory(root: Path, catalog: dict, source_sha: str) -> dict:
    if len(source_sha) != 40 or any(c not in "0123456789abcdef" for c in source_sha):
        raise ValueError("source SHA must be exactly 40 lowercase hex characters")
    bundles = catalog["bundles"]
    if len({b["id"] for b in bundles}) != len(bundles):
        raise ValueError("duplicate bundle IDs")
    ids = {b["id"] for b in bundles}
    if any(set(b["planning_dependencies"]) - ids for b in bundles):
        raise ValueError("dangling bundle dependency")
    graph = [{"id": b["id"], "needs": b["planning_dependencies"], "lane": b["lane"], "phase": b["phase"]} for b in bundles]
    if workflows.job_dag([{"id": b["id"], "needs": b["planning_dependencies"]} for b in bundles])["cycle"]:
        raise ValueError("bundle DAG cycle")
    rows = []
    for path in sorted((root / ".github/workflows").glob("*.y*ml")):
        rel = path.relative_to(root).as_posix()
        body = path.read_text(encoding="utf-8")
        parsed = workflows.parse(body, path=rel, blob_oid=None, repo="pipeline-automation-hub")
        rec = workflows.analyse(parsed)
        name = rec.get("name", path.name)
        text = (name + " " + rel).lower()
        sig = set()
        for job in rec.get("jobs", []):
            sig.update(job.get("signals", []))
        candidates = sorted(b["id"] for b in bundles
                            if any(s in sig for s in b["signal_hints"])
                            or any(s in text for s in b["name_hints"]))
        dag = rec.get("dag", {})
        rows.append({
            "path": rel, "name": name, "content_sha256": hashlib.sha256(body.encode()).hexdigest(),
            "triggers": rec.get("triggers", []), "job_count": len(rec.get("jobs", [])),
            "jobs": [{"id": j["id"], "needs": j.get("needs", []), "definition_sha256": j.get("def_sha256")}
                     for j in rec.get("jobs", [])],
            "bundle_candidates": candidates, "classification_authority": "HEURISTIC_ONLY",
            "parse_error": rec.get("parse_error"), "dag_cycle": bool(dag.get("cycle")),
            "dangling_dependencies": dag.get("dangling", []),
            "diagnostics": (["UNCLASSIFIED"] if not candidates else [])
        })
    return {
        "schema": "jade.devops.ci_bundle_inventory.v1", "source_sha": source_sha,
        "catalog_schema": catalog["schema"], "authority": "ADVISORY_ONLY",
        "merge_authorized": False, "workflow_count": len(rows),
        "parse_errors": sum(bool(r["parse_error"]) for r in rows),
        "dag_anomalies": sum(bool(r["dag_cycle"] or r["dangling_dependencies"]) for r in rows),
        "unclassified": sum(not r["bundle_candidates"] for r in rows),
        "planning_dag": graph, "workflows": rows
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--source-sha", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    report = inventory(args.root, json.loads(CATALOG.read_text(encoding="utf-8")), args.source_sha)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: report[k] for k in ("schema", "source_sha", "workflow_count", "parse_errors", "dag_anomalies", "unclassified", "authority")}, sort_keys=True))
    return 1 if report["parse_errors"] or report["dag_anomalies"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
