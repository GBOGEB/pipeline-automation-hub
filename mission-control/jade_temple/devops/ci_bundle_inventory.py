#!/usr/bin/env python3
"""Advisory CI bundle census over immutable Git objects, not a working tree."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import workflows

ROOT = Path(__file__).resolve().parents[3]
CATALOG = Path(__file__).with_name("CI_BUNDLE_CATALOG_V1.json")


def _git(root: Path, *args: str) -> bytes:
    """Read Git objects only. Unavailable or incomplete objects are errors, never zero."""
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError(f"GIT_SOURCE_UNAVAILABLE: {args[0]}") from exc


def _workflow_blobs(root: Path, source_sha: str):
    """Yield path, OID and text read from source_sha, ignoring dirty worktree data."""
    root = root.resolve()
    top = Path(_git(root, "rev-parse", "--show-toplevel").decode("utf-8").strip()).resolve()
    if top != root:
        raise ValueError("ROOT_MUST_BE_REPOSITORY_TOPLEVEL")
    # ls-tree accepts any tree-ish; only a commit OID binds the report to a repository head.
    if _git(root, "cat-file", "-t", source_sha).strip() != b"commit":
        raise ValueError("SOURCE_SHA_MUST_NAME_A_COMMIT")
    tree =_git(root, "ls-tree", "-rz", source_sha, "--", ".github/workflows")
    rows = []
    for item in tree.split(b"\0"):
        if not item:
            continue
        header, sep, rawpath = item.partition(b"\t")
        if not sep:
            raise ValueError("MALFORMED_GIT_TREE_ENTRY")
        mode, kind, rawoid = header.decode("ascii").split()
        path = rawpath.decode("utf-8")
        if not path.endswith((".yml", ".yaml")):
            continue
        if kind != "blob" or len(rawoid) != 40:
            raise ValueError("UNEXPECTED_GIT_WORKFLOW_OBJECT")
        rows.append((path, rawoid))
    if not rows:
        raise ValueError("EMPTY_WORKFLOW_SOURCE_POPULATION")
    for path, oid in sorted(rows):
        try:
            content = _git(root, "show", f"{source_sha}:{path}").decode("utf-8")
        except UnicodeError as exc:
            raise ValueError(f"WORKFLOW_NOT_UTF8: {path}") from exc
        yield path, oid, content


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
    for rel, oid, body in _workflow_blobs(root, source_sha):
        parsed = workflows.parse(body, path=rel, blob_oid=oid, repo="pipeline-automation-hub")
        rec = workflows.analyse(parsed)
        name = rec.get("name", rel.rsplit("/", 1)[-1])
        text = (name + " " + rel).lower()
        sig = set()
        for job in rec.get("jobs", []):
            sig.update(job.get("signals", []))
        candidates = sorted(b["id"] for b in bundles
                            if any(s in sig for s in b["signal_hints"])
                            or any(s in text for s in b["name_hints"]))
        dag = rec.get("dag", {})
        jobs = [{"id": j["id"], "needs": j.get("needs", []),
                 "definition_sha256": j.get("def_sha256"), "parse_error": j.get("parse_error")}
                for j in rec.get("jobs", [])]
        job_errors = [f"{j['id']}: {j['parse_error']}" for j in jobs if j["parse_error"]]
        rows.append({
            "path": rel, "name": name, "git_blob_oid": oid,
            "content_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            "triggers": rec.get("triggers", []), "job_count": len(jobs),
            "jobs": jobs, "job_parse_errors": job_errors,
            "bundle_candidates": candidates, "classification_authority": "HEURISTIC_ONLY",
            "parse_error": rec.get("parse_error"), "dag_cycle": bool(dag.get("cycle")),
            "dangling_dependencies": dag.get("dangling", []),
            "diagnostics": (["UNCLASSIFIED"] if not candidates else [])
                           + (["JOB_PARSE_ERROR"] if job_errors else [])
        })
    return {
        "schema": "jade.devops.ci_bundle_inventory.v1", "source_sha": source_sha,
        "source_binding": "IMMUTABLE_GIT_OBJECT_AT_SHA",
        "catalog_schema": catalog["schema"], "authority": "ADVISORY_ONLY",
        "merge_authorized": False, "workflow_count": len(rows),
        "parse_errors": sum(bool(r["parse_error"]) or bool(r["job_parse_errors"]) for r in rows),
        "job_parse_errors": sum(len(r["job_parse_errors"]) for r in rows),
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
    print(json.dumps({k: report[k] for k in ("schema", "source_sha", "source_binding", "workflow_count", "parse_errors", "job_parse_errors", "dag_anomalies", "unclassified", "authority")}, sort_keys=True))
    return 1 if report["parse_errors"] or report["dag_anomalies"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
