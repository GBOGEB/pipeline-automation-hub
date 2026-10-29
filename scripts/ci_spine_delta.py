#!/usr/bin/env python3
"""Deterministic, read-only two-pulse CI source delta from canonical index v1.

No GitHub reads or inferred runtime rates. Counts describe source topology only.
UNKNOWN and missing evidence never become PASS, GREEN, or merge authority.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCHEMA_IN = "jade.devops.ci-spine.index.v1"
SCHEMA_OUT = "jade.devops.ci-spine.source-delta.v1"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")


def _normalize(doc, label, errors):
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA_IN:
        errors.append(label + ": invalid index schema")
        return None, {}, {}
    source = doc.get("source")
    if not isinstance(source, dict):
        errors.append(label + ": malformed source object")
        source = {}
    assurance = doc.get("assurance")
    if not isinstance(assurance, dict):
        errors.append(label + ": malformed assurance object")
        assurance = {}
    head = source.get("checkout_sha")
    if not isinstance(head, str) or not SHA40.fullmatch(head):
        errors.append(label + ": no canonical 40-hex head")
    if source.get("expected_sha") not in (None, head):
        errors.append(label + ": expected head differs")
    if not isinstance(doc.get("errors"), list):
        errors.append(label + ": malformed errors list")
    if doc.get("verdict") != "PASS_STATIC_BINDINGS_ONLY" or doc.get("errors"):
        errors.append(label + ": index not statically qualified")
    if assurance.get("merge_admission") != "HOLD":
        errors.append(label + ": merge-admission status invalid")
    records = doc.get("workflows")
    if not isinstance(records, list):
        errors.append(label + ": no workflow inventory")
        records = []
    by_path = {}
    for wf in records:
        if not isinstance(wf, dict):
            errors.append(label + ": malformed workflow row")
            continue
        path, digest = wf.get("path"), wf.get("source_sha256")
        if not isinstance(path, str) or not path.startswith(".github/workflows/") or \
                not isinstance(digest, str) or not SHA64.fullmatch(digest):
            errors.append(label + ": malformed workflow identity/digest")
            continue
        jobs = wf.get("jobs")
        if not isinstance(jobs, list):
            errors.append(label + ": malformed jobs inventory " + path)
        else:
            ids = [job.get("id") for job in jobs if isinstance(job, dict)]
            if (len(ids) != len(jobs) or any(not isinstance(i, str) for i in ids)
                    or len(ids) != len(set(ids))):
                errors.append(label + ": malformed or duplicate job identities " + path)
        if path in by_path:
            errors.append(label + ": duplicate workflow " + path)
        by_path[path] = wf
    anchors = doc.get("anchors")
    if not isinstance(anchors, list):
        errors.append(label + ": missing anchors")
        anchors = []
    bound = {}
    for a in anchors:
        if not isinstance(a, dict) or not isinstance(a.get("id"), str) or not isinstance(a.get("path"), str):
            errors.append(label + ": malformed anchor")
            continue
        if a["id"] in bound:
            errors.append(label + ": duplicate anchor " + a["id"])
        bound[a["id"]] = {"path": a["path"], "phase": a.get("phase"),
                           "workflow_oid": a.get("workflow_oid"), "static_binding": a.get("static_binding")}
        if a.get("static_binding") != "PASS":
            errors.append(label + ": unqualified anchor " + a["id"])
    return head, by_path, bound


def _job_map(wf):
    jobs = wf.get("jobs")
    if not isinstance(jobs, list):
        return {}  # _normalize reports a first-red; _fields also marks malformed.
    return {x.get("id"): {"needs": x.get("needs"), "def_sha256": x.get("def_sha256"),
                          "layer": x.get("layer")}
            for x in jobs if isinstance(x, dict) and isinstance(x.get("id"), str)}


def _fields(a, b):
    """Semantic changes in emitted index rows; never equate structural RED with text-only drift."""
    out = []
    if not isinstance(a.get("jobs"), list) or not isinstance(b.get("jobs"), list):
        out.append("malformed_job_inventory")
    for key in ("name", "class", "triggers", "schedules", "permissions",
                "reusable", "paths_filtered", "dag_edges", "dag_layers",
                "parse_error", "dag_cycle", "dangling_needs"):
        if a.get(key) != b.get(key):
            out.append(key)
    if _job_map(a) != _job_map(b):
        out.append("job_definitions_or_needs")
    if a.get("jobs") != b.get("jobs") and "job_definitions_or_needs" not in out:
        out.append("job_structure_or_errors")
    # Other emitted fields (e.g. workflow OID) also carry source meaning.
    if a.get("oid") != b.get("oid"):
        out.append("workflow_oid")
    if a.get("source_sha256") != b.get("source_sha256") and not out:
        out.append("source_only_no_observed_semantic_delta")
    return out


def _structural_fault(row):
    """Unbound workflows may be advisory in the index, but cannot be hidden in a delta."""
    if not isinstance(row, dict):
        return True
    if row.get("parse_error") or row.get("dag_cycle") or row.get("dangling_needs"):
        return True
    jobs = row.get("jobs")
    return not isinstance(jobs, list) or any(
        not isinstance(job, dict) or job.get("parse_error") for job in jobs
    )


def compare(old, new):
    errors = []
    before, old_map, old_anchors = _normalize(old, "before", errors)
    after, new_map, new_anchors = _normalize(new, "after", errors)
    if before and before == after and old != new:
        errors.append("same source SHA but different source index")
    if not isinstance(old, dict) or not isinstance(new, dict):
        errors.append("unreadable input pair")
    paths = sorted(set(old_map) | set(new_map))
    rows = []
    for path in paths:
        a, b = old_map.get(path), new_map.get(path)
        if a is None:
            status, changed = "ADDED", ["entire_workflow"]
        elif b is None:
            status, changed = "REMOVED_REQUIRES_CUSTODY_PROOF", ["entire_workflow"]
        elif a["source_sha256"] == b["source_sha256"]:
            status, changed = "SAME_SOURCE", []
            # Compare the entire emitted row. Parser/classifier drift can change
            # projection without changing workflow bytes (e.g. reusable, layers).
            if a != b:
                errors.append(path + ": identical source digest has inconsistent parser projection")
        else:
            status, changed = "MODIFIED", _fields(a, b)
        if status != "SAME_SOURCE":
            rows.append({"path": path, "change": status, "changed_fields": changed,
                         "previous_source_sha256": a.get("source_sha256") if a else None,
                         "current_source_sha256": b.get("source_sha256") if b else None,
                         "safety_attention": (
                             status == "REMOVED_REQUIRES_CUSTODY_PROOF"
                             or _structural_fault(b) or _structural_fault(a)
                             or any(x in changed for x in ("permissions", "triggers", "schedules",
                               "dag_edges", "dag_layers", "job_definitions_or_needs",
                               "job_structure_or_errors", "malformed_job_inventory",
                               "parse_error", "dag_cycle",
                               "dangling_needs", "workflow_oid"))),
                         "merge_admission": "HOLD"})
    ar = []
    for ident in sorted(set(old_anchors) | set(new_anchors)):
        x, y = old_anchors.get(ident), new_anchors.get(ident)
        if x != y:
            ar.append({"id": ident, "before": x, "after": y, "status": "AUTHORITY_REVIEW_REQUIRED"})
    if errors:
        verdict = "CI_SPINE_DELTA_FIRST_RED"
    else:
        verdict = "DIFFERENCE_REVIEW_REQUIRED" if rows or ar else "NO_OBSERVED_SOURCE_DELTA"
    return {
        "schema": SCHEMA_OUT, "verdict": verdict,
        "source": {"previous_sha": before, "current_sha": after, "clock": "SOURCE_COMMITS_NOT_RUNTIME"},
        "counts": {
            "previous_workflows": len(old_map), "current_workflows": len(new_map),
            "added": sum(x["change"] == "ADDED" for x in rows),
            "removed": sum(x["change"] == "REMOVED_REQUIRES_CUSTODY_PROOF" for x in rows),
            "modified": sum(x["change"] == "MODIFIED" for x in rows),
            "unchanged": len(paths) - len(rows),
            "authority_binding_changes": len(ar),
            "safety_attention": sum(x["safety_attention"] for x in rows),
        },
        "workflow_changes": rows, "authority_changes": ar, "errors": errors,
        "limits": {
            "run_metrics": "NOT_MEASURED", "job_queue_seconds": "NOT_MEASURED",
            "runtime_seconds": "NOT_MEASURED", "source_sha_order_is_not_wall_clock_order": True,
            "historical_lineage": "NOT_REVALIDATED", "pr_merge_status": "NOT_EVALUATED",
            "merge_admission": "HOLD", "branch_delete_authorized": False,
        }
    }


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--before", type=Path, required=True)
    a.add_argument("--after", type=Path, required=True)
    a.add_argument("--out", type=Path)
    a.add_argument("--check", action="store_true", help="fail closed on invalid schema or projection conflict")
    args = a.parse_args(argv)
    try:
        result = compare(json.loads(args.before.read_text(encoding="utf-8")),
                         json.loads(args.after.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        result = {"schema": SCHEMA_OUT, "verdict": "CI_SPINE_DELTA_FIRST_RED",
                  "errors": [type(exc).__name__], "workflow_changes": [],
                  "limits": {"merge_admission": "HOLD"}}
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                            encoding="utf-8", newline="\n")
    print(json.dumps(result, sort_keys=True, indent=2))
    return int(args.check and result["verdict"] == "CI_SPINE_DELTA_FIRST_RED")


if __name__ == "__main__":
    sys.exit(main())
