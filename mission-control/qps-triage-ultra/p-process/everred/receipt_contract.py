#!/usr/bin/env python3
"""EVERRED companion: exact-head, fail-closed root occurrence and regression receipts.

This never creates canonical root IDs, changes EVERRED ownership, or grants admission.
Use normalized provider *observations*, not text reconstructed from chat reports.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

SCHEMA = "everred.root-receipt/v1"
SHA = re.compile(r"^[0-9a-f]{40}$")
SAFE_URL = re.compile(r"^https://github\.com/GBOGEB/[A-Za-z0-9_.-]+/(?:actions/runs/\d+|pull/\d+|commit/[0-9a-f]{40})(?:/.*)?$")
CONCLUSIONS = {"failure", "success", "neutral", "skipped", "cancelled", "action_required", "queued"}
NONEXEC = {"neutral", "skipped", "cancelled", "action_required", "queued"}


def canonical(obj):
    return json.dumps(obj, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def norm(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("IDENTITY_FIELD_MISSING")
    return " ".join(value.split()).casefold()


def fingerprint(e):
    # Explicit predicate and configuration scope prevent two distinct failures
    # in one workflow step being silently coalesced into a false common root.
    fields = ("repo", "workflow", "job", "step", "failure_predicate", "config_scope")
    return hashlib.sha256(canonical({k: norm(e.get(k)) for k in fields}).encode()).hexdigest()


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("TIMESTAMP_MISSING")
    try:
        when = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as ex:
        raise ValueError("TIMESTAMP_INVALID") from ex
    if when.tzinfo is None:
        raise ValueError("TIMESTAMP_NOT_ZONED")
    return when


def match_root(event, catalog):
    """Existing EVERRED match rules only. Ambiguous and absent rules stay candidates."""
    hits = []
    for root in catalog.get("roots", []):
        for rule in root.get("match", []):
            if "probe" in rule or (rule.get("repo") and rule["repo"] != event["repo"]):
                continue
            if all(norm(rule[k]) in norm(event[k]) for k in ("workflow", "job", "step") if rule.get(k)):
                if any(rule.get(k) for k in ("workflow", "job", "step")):
                    hits.append(root["id"])
                    break
    hits = sorted(set(hits))
    return hits[0] if len(hits) == 1 else None, "MATCHED_CANDIDATE" if len(hits) == 1 else ("AMBIGUOUS" if hits else "UNMATCHED")


def valid_proof(proof, head):
    """Provider-readback-shaped evidence; no third-party claim can be promoted."""
    if not isinstance(proof, dict) or proof.get("head_sha") != head:
        return False
    if proof.get("source_grade") != "PROVIDER_READBACK" or proof.get("conclusion") != "success":
        return False
    if not isinstance(proof.get("executed_steps"), int) or isinstance(proof["executed_steps"], bool) or proof["executed_steps"] < 1:
        return False
    if not SAFE_URL.fullmatch(proof.get("url") or ""):
        return False
    return True


def regression_verified(event, head):
    p = event.get("regression") or {}
    if event.get("conclusion") != "success" or event.get("source_grade") != "PROVIDER_READBACK":
        return False
    neg, pos = p.get("negative"), p.get("positive")
    if not (valid_proof(neg, head) and valid_proof(pos, head)):
        return False
    if neg["url"] == pos["url"]:  # independent executed tests, not one reused receipt
        return False
    reviewer = p.get("independent_review") or {}
    return (reviewer.get("state") == "APPROVED" and reviewer.get("head_sha") == head
            and reviewer.get("source_grade") == "PROVIDER_READBACK"
            and reviewer.get("reviewer") and reviewer.get("reviewer") != p.get("author")
            and SAFE_URL.fullmatch(reviewer.get("url") or "") is not None)


def kahn(nodes, edges):
    graph = {n: set() for n in nodes}
    degree = {n: 0 for n in nodes}
    if len(graph) != len(nodes):
        raise ValueError("DUPLICATE_DAG_NODE")
    for left, right in edges:
        if left not in graph or right not in graph:
            raise ValueError("DAG_UNKNOWN_NODE")
        if right not in graph[left]:
            graph[left].add(right)
            degree[right] += 1
    layers = []
    frontier = sorted(n for n, d in degree.items() if d == 0)
    while frontier:
        layers.append(frontier)
        next_ready = []
        for n in frontier:
            for m in sorted(graph[n]):
                degree[m] -= 1
                if degree[m] == 0:
                    next_ready.append(m)
        frontier = sorted(next_ready)
    if sum(map(len, layers)) != len(nodes):
        raise ValueError("DAG_CYCLE")
    return layers


def check_disjoint(lanes):
    owners = {}
    for lane, paths in lanes.items():
        for path in paths:
            if path in owners and owners[path] != lane:
                raise ValueError("WRITE_COLLISION: " + path)
            owners[path] = lane
    return True


def build(events, catalog, heads):
    """Events and catalog are immutable inputs; output deterministic, not a closure claim."""
    if not isinstance(events, list) or not isinstance(heads, dict) or not isinstance(catalog, dict):
        raise ValueError("INPUT_SCHEMA")
    seen = {}
    groups = defaultdict(list)
    for e in events:
        if not isinstance(e, dict) or not SHA.fullmatch(e.get("sha") or ""):
            raise ValueError("EVENT_SHA")
        if e.get("conclusion") not in CONCLUSIONS:
            raise ValueError("CONCLUSION_UNKNOWN")
        if type(e.get("run_id")) is not int or e["run_id"] < 1 or type(e.get("run_attempt")) is not int or e["run_attempt"] < 1:
            raise ValueError("RUN_IDENTITY")
        if type(e.get("job_id")) is not int or e["job_id"] < 1 or type(e.get("step_number")) is not int or e["step_number"] < 0:
            raise ValueError("JOB_STEP_IDENTITY")
        stamp = timestamp(e.get("observed_at"))
        steps = e.get("executed_steps")
        if steps is not None and (type(steps) is not int or steps < 0):
            raise ValueError("EXECUTION_COUNT")
        if e["conclusion"] == "success" and (steps is None or steps == 0):
            raise ValueError("ZERO_STEP_SUCCESS")
        if e["conclusion"] in ("queued", "action_required") and steps not in (0, None):
            raise ValueError("UNEXECUTED_WITH_STEPS")
        fp = fingerprint(e)
        target = e.get("target_ref")
        if not isinstance(target, str) or not target.strip():
            raise ValueError("TARGET_REF_MISSING")
        ref = f'{e["repo"]}@{target}'
        identity = (e["repo"], e["run_id"], e["run_attempt"], e["job_id"], e["step_number"])
        record = {"fingerprint": fp, "repo": e["repo"], "head_sha": e["sha"], "target": ref,
                  "run_id": e["run_id"], "attempt": e["run_attempt"], "job_id": e["job_id"],
                  "step_number": e["step_number"], "conclusion": e["conclusion"],
                  "executed_steps": steps, "observed_at": stamp.isoformat(),
                  "url": e.get("url") if SAFE_URL.fullmatch(e.get("url") or "") else None,
                  "source_grade": e.get("source_grade", "UNKNOWN")}
        if identity in seen:
            if seen[identity] != record:
                raise ValueError("MUTATED_DELIVERY_IDENTITY")
            continue
        seen[identity] = dict(record)  # frozen delivery identity before badge enrichment
        root_id, mapping = match_root(e, catalog)
        record["canonical_root_id"] = root_id
        record["root_mapping"] = mapping
        h = heads.get(ref)
        if h is not None and (not isinstance(h, str) or not SHA.fullmatch(h)):
            raise ValueError("CURRENT_HEAD_INVALID")
        if h is None:
            badge = "HEAD_UNKNOWN"
        elif h != e["sha"]:
            badge = "STALE_HEAD"
        elif e["conclusion"] in NONEXEC or steps in (None, 0):
            badge = "UNEXECUTED"
        elif e["conclusion"] == "failure":
            badge = "ROOT_RED"
        elif regression_verified(e, h):
            badge = "REGRESSION_VERIFIED"
        else:
            badge = "PROOF_INCOMPLETE"
        record["badge"] = badge
        record["admission"] = "ADMISSION_HOLD"  # root proof is never complete PR admission
        groups[fp].append(record)
    rows = []
    occurrences = []
    for fp, rs in sorted(groups.items()):
        rs.sort(key=lambda r: (r["observed_at"], r["run_id"], r["attempt"], r["job_id"], r["step_number"]))
        occurrences.extend(rs)
        state = [r["conclusion"] for r in rs]
        rows.append({"fingerprint": fp, "canonical_root_id": rs[0]["canonical_root_id"],
                     "root_mapping": rs[0]["root_mapping"], "occurrence_count": len(rs),
                     "distinct_heads": len({r["head_sha"] for r in rs}),
                     "regression_after_success": any(a == "success" and b == "failure" for a, b in zip(state, state[1:])),
                     "latest_badge": rs[-1]["badge"], "root_closed": False})
    dag_nodes = ["normalize", "negative", "badge", "integrate", "native", "independent", "admission"]
    dag_edges = [("normalize", "integrate"), ("negative", "integrate"), ("badge", "integrate"),
                 ("integrate", "native"), ("native", "independent"), ("independent", "admission")]
    result = {"schema": SCHEMA, "unique_semantic_candidates": len(rows), "occurrences": occurrences,
              "roots": rows, "counts": {"raw": len(events), "unique": len(occurrences),
              "duplicate_deliveries": len(events)-len(occurrences), "canonically_matched_candidates": sum(r["canonical_root_id"] is not None for r in rows),
              "verified_closed": 0}, "dag_layers": kahn(dag_nodes, dag_edges),
              "disposition": "MERGE_ADMISSION_HOLD", "source_grade": "INPUT_OBSERVATIONS_NOT_INDEPENDENTLY_AUTHENTICATED"}
    result["sha256"] = hashlib.sha256(canonical(result).encode()).hexdigest()
    return result


def render_html(report):
    rows = []
    for r in report["roots"]:
        tag = html.escape(r["latest_badge"])
        rows.append(f'<tr><td><code>{html.escape(r["fingerprint"][:16])}</code></td><td>{html.escape(r["canonical_root_id"] or "CANDIDATE")}</td><td>{r["occurrence_count"]}</td><td><span class="badge">{tag}</span></td><td>ADMISSION HOLD</td></tr>')
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>EVERRED semantic receipts</title><style>body{font:15px Aptos,Arial,sans-serif;background:#faf7fc;color:#321838;max-width:1050px;margin:2rem auto;padding:1rem}'
            'h1{color:#60246e}table{width:100%;border-collapse:collapse}td,th{padding:12px;border-bottom:1px solid #d9c4db;text-align:left}'
            'th{background:#f2e0ef}.badge{padding:4px 8px;border-radius:8px;background:#f8e5ed;color:#7e1e42;font-weight:bold}'
            'code{font-family:Consolas,monospace}</style><h1>EVERRED semantic occurrence receipt</h1>'
            '<p>Source-bound candidate mapping. No automatic semantic closure, engineering approval, or merge admission.</p>'
            '<table><thead><tr><th>Fingerprint</th><th>Existing root / candidate</th><th>Occurrences</th><th>Proof badge</th><th>Admission</th></tr></thead><tbody>'
            + ''.join(rows) + '</tbody></table></html>')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--events", required=True, type=Path)
    ap.add_argument("--catalog", required=True, type=Path)
    ap.add_argument("--heads", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args(argv)
    # Catalog is either a JSON object of existing EVERRED roots, or roots.yaml.
    if a.catalog.suffix in (".yaml", ".yml"):
        import yaml  # Existing EVERRED dependency; testable JSON mode requires stdlib only.
        catalog = yaml.safe_load(a.catalog.read_text(encoding="utf-8"))
    else:
        catalog = json.loads(a.catalog.read_text(encoding="utf-8"))
    result = build(json.loads(a.events.read_text(encoding="utf-8")), catalog,
                   json.loads(a.heads.read_text(encoding="utf-8")))
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "root_receipt.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (a.out / "root_receipt.html").write_text(render_html(result), encoding="utf-8", newline="\n")
    print("CANDIDATES", result["counts"]["canonically_matched_candidates"],
          "ROOTS", len(result["roots"]), "OCCURRENCES", result["counts"]["unique"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
