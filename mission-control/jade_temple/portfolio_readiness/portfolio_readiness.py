#!/usr/bin/env python3
"""Offline portfolio facade over canonical JADE, issue-rank and RF owners.

This consumer neither fetches source evidence nor grants execution/closure credit.
Its only writes are deterministic review artifacts in an explicitly chosen folder.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
JADE = HERE.parent
REPO = JADE.parent.parent
SCHEMA = "jade.portfolio-readiness.v1"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
REPO_NAME = re.compile(r"^GBOGEB/[A-Za-z0-9_.-]+$")
OWNERS = {
    "gate12": "mission-control/jade_temple/tools/build_gate12_dov.py",
    "rolling5": "mission-control/jade_temple/tools/rolling5.py",
    "lifecycle": "mission-control/jade_temple/devops/lifecycle.py",
    "issue_rank": "mission-control/issue_rank/issue_rank.py",
    "private_boundary": "mission-control/jade_temple/tools/private_boundary.py",
    "statistics": "mission-control/federation-atlas/flightdeck/pulses/mip_statistical_qualification.py",
    "provider": "mission-control/federation-atlas/flightdeck/pulses/mip_provider_execution.py",
}


def owner(name: str):
    path = REPO / OWNERS[name]
    if name == "issue_rank":
        for sibling in ("title_taxonomy", "taxonomy_pulse"):
            cached = sys.modules.get(sibling)
            if cached is not None:
                need(Path(getattr(cached, "__file__", "")).resolve() == path.parent / (sibling + ".py"),
                     "foreign cached issue owner module: " + sibling)
    spec = importlib.util.spec_from_file_location("portfolio_owner_" + name, path)
    module = importlib.util.module_from_spec(spec)
    # issue_rank's sibling imports remain owned by issue_rank. Do not copy them.
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def need(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError("PORTFOLIO_INPUT: " + message)


def scalar_text(value, label: str, *, nullable: bool = True):
    need((value is None and nullable) or isinstance(value, str), label + " must be text")
    return value


def timestamp(value: str) -> datetime:
    need(isinstance(value, str), "timestamp must be a string")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    need(dt.tzinfo is not None, "timestamp must include timezone")
    return dt.astimezone(timezone.utc)


def canonical(value) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, indent=2,
                       allow_nan=False) + "\n").encode("ascii")


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def safe_url(value) -> str | None:
    if not isinstance(value, str) or any(ord(c) < 32 for c in value):
        return None
    try:
        url = urlsplit(value)
        if (url.scheme == "https" and url.hostname in {"github.com", "api.github.com"}
                and not url.username and not url.password and url.port in (None, 443)):
            return value
    except ValueError:
        pass
    return None


def source_hashes(jade: Path) -> dict:
    gate, rolling = owner("gate12"), owner("rolling5")
    files = {"mission-control/jade_temple/" + p for p in gate.FILES.values()}
    policy = rolling.load(jade, rolling.POLICY)
    ledger = rolling.load(jade, rolling.LEDGER)
    files.update("mission-control/jade_temple/" + p for p in
                 [rolling.POLICY, rolling.LEDGER, policy["roster_source"]])
    files.update("mission-control/jade_temple/" + p["snapshot"] for p in ledger["pulses"])
    files.update(OWNERS.values())
    files.update("mission-control/jade_temple/portfolio_readiness/" + p
                 for p in ("portfolio_readiness.py", "dashboard.py"))
    result = {}
    for rel in sorted(files):
        path = jade / rel.removeprefix("mission-control/jade_temple/") if rel.startswith(
            "mission-control/jade_temple/") else REPO / rel
        raw = path.read_bytes()
        result[rel] = {"sha256": hashlib.sha256(raw).hexdigest(),
                       "git_blob_oid": gate.blob_oid(raw)}
    return result


def baseline_binding(source_sha: str, hashes: dict) -> dict:
    """Read local Git objects only; a shaped SHA is never source authentication."""
    paths = sorted(p for p in hashes if "/portfolio_readiness/" not in p)
    try:
        proc = subprocess.run(["git", "-C", str(REPO), "ls-tree", "-r", "-z", source_sha, "--", *paths],
                              capture_output=True, timeout=15, check=False,
                              env={**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0"})
    except (OSError, subprocess.TimeoutExpired):
        return {"status": "UNRESOLVED_BASELINE", "canonical_inputs_match": None, "mismatches": []}
    if proc.returncode:
        return {"status": "UNRESOLVED_BASELINE", "canonical_inputs_match": None, "mismatches": []}
    found = {}
    for row in proc.stdout.decode("utf-8").split("\0"):
        if row:
            meta, path = row.split("\t", 1)
            found[path] = meta.split()[2]
    mismatches = [p for p in paths if found.get(p) != hashes[p]["git_blob_oid"]]
    return {"status": "BASELINE_INPUTS_MATCH" if not mismatches else "BASELINE_INPUT_DRIFT",
            "canonical_inputs_match": not mismatches, "mismatches": mismatches,
            "scope": "canonical owner code and recorded inputs; consumer working bytes hashed separately",
            "native_authentication": False}


def release_metadata(value):
    if value is None or isinstance(value, str):
        return value
    need(isinstance(value, dict), "release metadata must be an object, string or null")
    return {"tag_name": scalar_text(value.get("tag_name"), "release tag"),
            "html_url": safe_url(value.get("html_url")),
            "published_at": scalar_text(value.get("published_at"), "release timestamp")}


def observations(doc: dict | None, as_of: datetime, private: set[str]) -> dict:
    if doc is None:
        return {"status": "NOT_SUPPLIED", "captured_at": None, "repos": [], "frontier": [],
                "full_census": False, "source_digest": None}
    need(isinstance(doc, dict) and doc.get("schema") == "jade.portfolio-observation.v1", "observation schema")
    captured = timestamp(doc.get("captured_at"))
    need(captured <= as_of, "observation is after as-of")
    rows = doc.get("repos")
    need(isinstance(rows, list), "observation repos must be a list")
    names = [r.get("repo") for r in rows if isinstance(r, dict)]
    need(len(names) == len(rows) and len(set(names)) == len(names), "duplicate repository")
    result = []
    for row in rows:
        name = row["repo"]
        need(bool(REPO_NAME.fullmatch(str(name))), "repository identity")
        need(type(row.get("private", False)) is bool, "private flag must be boolean")
        is_private = name in private or row.get("private") is True
        if is_private:
            private.add(name)
            result.append({"repo": name, "private": True, "head_sha": None,
                           "current_qualification": "UNKNOWN_PRIVATE_OWNER"})
            continue
        sha = row.get("head_sha")
        need(sha is None or bool(HEX40.fullmatch(str(sha))), "malformed observed head")
        observed = timestamp(row.get("observed_at", doc["captured_at"]))
        need(observed <= captured, "repository observed after capture boundary")
        counts = row.get("check_counts")
        if counts is not None:
            need(isinstance(counts, dict) and all(
                k in {"success", "failure", "skipped", "cancelled", "neutral", "pending", "action_required", "other"}
                and type(v) is int and v >= 0 for k, v in counts.items()), "invalid native-unit check counts")
        # Explicit allowlist: raw bodies, comments and arbitrary extra keys never escape.
        result.append({"repo": name, "private": False, "head_sha": sha,
                       "default_branch": scalar_text(row.get("default_branch"), "default branch"),
                       "observed_at": observed.isoformat(), "check_counts": counts,
                       "check_population": scalar_text(row.get("check_population", "UNKNOWN"), "check population"),
                       "check_collection_complete": row.get("check_collection_complete") is True,
                       "latest_release": release_metadata(row.get("latest_release")),
                       "current_qualification": "NOT_REQUALIFIED",
                       "source_urls": [u for x in row.get("source_urls", []) if (u := safe_url(x))]})
    frontier = []
    for row in doc.get("frontier", []):
        need(isinstance(row, dict) and row.get("repository") in names, "frontier repository not observed")
        if row["repository"] in private:
            continue
        sha = row.get("head_sha")
        need(sha is None or bool(HEX40.fullmatch(str(sha))), "frontier head")
        frontier.append({k: scalar_text(row.get(k), "frontier " + k)
                         for k in ("id", "repository", "head_sha", "state", "status", "blocker")}
                        | {"url": safe_url(row.get("url")),
                           "source_urls": [u for x in row.get("source_urls", []) if (u := safe_url(x))]})
    return {"status": "BOUNDED_OBSERVATION", "captured_at": captured.isoformat(),
            "age_hours": round((as_of - captured).total_seconds() / 3600, 3),
            "freshness": "STALE" if (as_of - captured).total_seconds() > 86400 else "WITHIN_24H",
            "repos": result, "frontier": frontier, "full_census": False,
            "source_digest": digest(doc)}


def issue_view(snapshot: dict | None, as_of: datetime, private: set[str] | None = None) -> dict:
    if snapshot is None:
        return {"status": "NOT_SUPPLIED", "public_open_items": None, "model": None}
    ir = owner("issue_rank")
    need(isinstance(snapshot, dict) and snapshot.get("schema") == ir.SNAPSHOT_SCHEMA, "canonical issue snapshot required")
    need(timestamp(snapshot["fetched_at"]) <= as_of, "issue snapshot is after as-of")
    # Full source-owner model and redaction, including taxonomy, pressure and golden thread.
    model = ir.rank(snapshot, now=as_of.timestamp())
    model = ir.redact(model, private_repos=private)
    return {"status": "SOURCE_OWNER_PROJECTION", "public_open_items": len(model["items"]),
            "scope": snapshot.get("collection_scope", "UNDECLARED"),
            "full_population_qualified": False,
            "source_digest": digest(snapshot), "model": model}


def proposal(doc: dict | None, source_sha: str, private: set[str]) -> dict:
    if doc is None:
        return {"status": "NOT_SUPPLIED", "tasks": [], "clusters": [], "waves": [], "matrix": None}
    need(isinstance(doc, dict) and doc.get("schema") == "jade.portfolio-plan.v1", "plan schema")
    topic = scalar_text(doc.get("topic", "Portfolio source convergence"), "plan topic", nullable=False)
    tasks, clusters = copy.deepcopy(doc.get("tasks")), copy.deepcopy(doc.get("clusters"))
    need(isinstance(tasks, list) and isinstance(clusters, list), "plan lists required")
    task_fields = {"id", "cluster", "phase", "crew", "state", "source_sha", "t0_ref",
                   "depends_on", "touch_paths", "write_pr", "title", "intent", "dov", "dod",
                   "target_repo", "target_head_sha"}
    cluster_fields = {"id", "title", "domain", "epic", "issue_refs"}
    need(all(isinstance(t, dict) for t in tasks) and all(isinstance(c, dict) for c in clusters),
         "task and cluster objects required")
    tasks = [{k: v for k, v in t.items() if k in task_fields} for t in tasks]
    clusters = [{k: v for k, v in c.items() if k in cluster_fields} for c in clusters]
    cluster_ids = [c.get("id") for c in clusters if isinstance(c, dict)]
    need(len(cluster_ids) == len(clusters) and len(set(cluster_ids)) == len(clusters)
         and all(isinstance(x, str) and x for x in cluster_ids), "unique cluster identities")
    for task in tasks:
        need(isinstance(task, dict) and task.get("cluster") in cluster_ids, "unknown task cluster")
        need(task.get("state") in {"READY", "HOLD", "FAILED"},
             "proposal cannot claim DONE or RUNNING; use the native execution owner")
        need(all(isinstance(task.get(k), str) and task[k].strip() for k in ("title", "intent", "target_repo")),
             "task title, intent and target repository required")
        need(bool(REPO_NAME.fullmatch(task["target_repo"])), "invalid target repo")
        target_sha = task.get("target_head_sha")
        need(target_sha is None or (isinstance(target_sha, str) and bool(HEX40.fullmatch(target_sha))),
             "target head must be an exact SHA or null")
        need(all(isinstance(task.get(k), list) and task[k] and
                 all(isinstance(x, str) and x.strip() for x in task[k]) for k in ("dov", "dod")),
             "every task requires explicit DOV and DOD")
        need(safe_url(task.get("t0_ref")) is not None, "task T0 must be a source URL")
        # Repository-qualified locks avoid false collisions for two repos' README.md.
        task["repository"] = task["target_repo"]
    lifecycle = owner("lifecycle")
    steps = [{**t, "touch_paths": [t["target_repo"] + "/" + p for p in t.get("touch_paths", [])]}
             for t in tasks]
    cap = doc.get("max_parallel", 2)
    need(type(cap) is int and 1 <= cap <= 2, "pilot cap is two until scale owner qualifies it")
    matrix = lifecycle.rf_pulse_plan(steps, source_sha=source_sha, max_parallel=cap,
                                    per_cluster=doc.get("per_cluster", 1),
                                    open_stack=doc.get("open_stack", 0), max_stack=5)
    edges = [(dep, t["id"], "FEEDFORWARD") for t in tasks for dep in t.get("depends_on", [])]
    waves = lifecycle.topo_layers([t["id"] for t in tasks], edges)
    private_ids = {t["id"] for t in tasks if t["target_repo"] in private}
    for category in ("on", "off", "held"):
        for row in matrix[category]:
            if row["id"] in private_ids and "t0_ref" in row:
                row["t0_ref"] = None
    for task in tasks:
        if task["target_repo"] in private:
            for field in ("target_head_sha", "t0_ref", "source_sha"):
                task[field] = None
            task.update(title="Private owner action", intent="Owner-held source required",
                        dov=["Private owner verifies the source"], dod=["Private owner accepts the result"],
                        touch_paths=[])
    for cluster in clusters:
        for field in ("title", "domain", "epic"):
            scalar_text(cluster.get(field), "cluster " + field)
        need(isinstance(cluster.get("issue_refs", []), list), "cluster references must be a list")
        need(all(isinstance(x, str) and re.fullmatch(r"GBOGEB/[A-Za-z0-9_.-]+#[1-9][0-9]*", x)
                 for x in cluster.get("issue_refs", [])), "cluster issue reference identity")
        cluster["issue_refs"] = [x for x in cluster.get("issue_refs", [])
                                 if isinstance(x, str) and x.split("#", 1)[0] not in private]
    return {"status": "PROPOSAL_ONLY", "topic": topic, "tasks": tasks, "clusters": clusters,
            "waves": waves, "edges": edges, "matrix": matrix,
            "cluster_counts_additive": False,
            "note": "Clusters may overlap; membership counts are not a fleet denominator.",
            "source_digest": digest(doc)}


def history_view(jade: Path, as_of: datetime) -> list[dict]:
    rolling = owner("rolling5")
    pairs = rolling.verified_pulses(jade, rolling.load(jade, rolling.LEDGER))
    history = []
    for pulse, snapshot in pairs:
        day = datetime.fromisoformat(pulse["observed_date"]).date()
        need(day <= as_of.date(), "historical ledger contains a future pulse")
        rows = rolling.rows_of(snapshot)
        history.append({"id": pulse["id"], "observed_date": pulse["observed_date"],
                        "snapshot_sha256": pulse["snapshot_sha256"],
                        "snapshot": pulse["snapshot"], "metrics": snapshot["metrics"],
                        "cohort": sorted(rows), "age_days": (as_of.date() - day).days,
                        "current_native_qualification": False})
    return history


def semantic_state(model: dict) -> dict:
    """Ignore rendering time; material notifications need a change in evidence/state."""
    issues = model["issues"].get("model")
    issue_state = None if issues is None else {
        "heads": issues["heads"], "edges": issues["edges"],
        "items": [{k: i.get(k) for k in ("key", "title", "updated_at", "draft", "checks",
                                          "review_decision", "approvals", "checklist", "open_blockers")}
                  for i in sorted(issues["items"], key=lambda x: x["key"])],
        "closed_in_window": issues.get("closed_in_window")}
    return {"planning_source_sha": model["planning_source_sha"], "source_hashes": model["source_hashes"],
            "history": [(p["id"], p["snapshot_sha256"]) for p in model["history"]],
            "repos": [{k: sorted(v) if k == "source_urls" else v for k, v in r.items() if k != "observed_at"}
                      for r in sorted(model["observation"]["repos"], key=lambda x: x["repo"])],
            "observation_freshness": model["observation"].get("freshness"),
            "frontier": [{k: sorted(v) if k == "source_urls" else v for k, v in r.items()}
                         for r in sorted(model["observation"]["frontier"], key=lambda x: (x.get("repository") or "", x.get("id") or ""))],
            "issues": issue_state,
            "plan": {k: model["plan"].get(k) for k in ("topic", "tasks", "clusters", "waves", "matrix")}}


def view_cohort(model: dict) -> dict:
    """Display comparability is separate from native CONTROL qualification."""
    issue_model = model["issues"].get("model")
    return {"schema": model["schema"], "planning_source_sha": model["planning_source_sha"],
            "history_cohort": model["history"][-1]["cohort"],
            "history_denominator": model["rolling5_historical"]["metrics"]["gate_denominator"],
            "repos": sorted((r["repo"], r.get("check_population"),
                             sum(r["check_counts"].values()) if r.get("check_counts") is not None else None)
                            for r in model["observation"]["repos"]),
            "issue_scope": model["issues"].get("scope"),
            "issue_repos": sorted(issue_model["heads"]) if issue_model else None}


def project(*, as_of: str, source_sha: str, jade: Path = JADE,
            observation: dict | None = None, issue_snapshot: dict | None = None,
            plan: dict | None = None, previous: dict | None = None) -> dict:
    at = timestamp(as_of)
    need(bool(HEX40.fullmatch(source_sha)), "exact planning baseline SHA required")
    pb = owner("private_boundary")
    private = set(pb.private_repos())
    observed = observations(observation, at, private)
    if issue_snapshot is not None:
        for row in observed["repos"]:
            issue_head = issue_snapshot.get("repos", {}).get(row["repo"], {}).get("head_sha")
            if not row.get("private") and row.get("head_sha") and issue_head:
                need(row["head_sha"] == issue_head, "MIXED_PULSE: issue and observation heads differ")
    gate, rolling = owner("gate12").project(jade), owner("rolling5").project(jade)
    history = history_view(jade, at)
    latest = {r["repo"]: r for r in rolling["repos"]}
    current = {r["repo"]: r for r in observed["repos"]}
    comparisons = []
    for name in sorted(set(latest) | set(current)):
        past, now = latest.get(name, {}), current.get(name, {})
        old_sha, new_sha = past.get("source_sha"), now.get("head_sha")
        qualified = bool(isinstance(old_sha, str) and HEX40.fullmatch(old_sha)
                         and isinstance(new_sha, str) and HEX40.fullmatch(new_sha))
        status = ("SOURCE_MATCH_ONLY" if old_sha == new_sha else "SOURCE_CHANGED") if qualified else "UNKNOWN"
        comparisons.append({"repository": name, "historical_sha": old_sha if name not in private else None,
                            "observed_sha": new_sha, "source_comparison": status,
                            "current_gate_pass": None,
                            "reason": "Current native H01-H12 recertification is not supplied by source identity."})
    hashes = source_hashes(jade)
    out = {
        "schema": SCHEMA, "as_of": at.isoformat(), "planning_source_sha": source_sha,
        "authority": {"merge_admission": "HOLD", "owner_release": "WITHHELD", "formal_credit_delta": 0,
                      "dispatch_performed": False, "authority_transfer": False,
                      "live_weighted_closure_rate": None, "current_point_release_readiness": None},
        "source_hashes": hashes, "source_binding": baseline_binding(source_sha, hashes), "owners": OWNERS,
        "gate12_frozen": gate, "rolling5_historical": rolling, "history": history,
        "observation": observed, "source_comparisons": comparisons,
        "issues": issue_view(issue_snapshot, at, private), "plan": proposal(plan, source_sha, private),
        "statistics": {"provider": "GBOGEB/gg_MATH", "pca": "WITHHELD_NO_QUALIFIED_TEMPORAL_MATRIX",
                       "bradley_terry": "WITHHELD_NO_OBSERVED_PAIRWISE_OUTCOMES",
                       "reverse_pressure": "NON_BT_REVERSE_PRESSURE_PAGERANK",
                       "qualification_owner": OWNERS["statistics"], "execution_owner": OWNERS["provider"],
                       "authority_transfer": False},
        "watch": {"state": "DEVELOPMENT_PREVIEW", "enabled": False, "timezone": "Europe/Brussels",
                  "backend": "EXISTING_AUTOMATION_OWNERS", "cron_install_performed": False,
                  "owners": {"cluster_delta": "MIP Perpetual Closure", "queue": "N6 Queue Drain Watch",
                             "calibration": "MIP Weekly KPI Calibration", "bridge": "GM-I-C Contract and PR Gate Watch"},
                  "notify_on": ["changed_source_head", "changed_first_red", "changed_review_or_admission",
                                "newly_qualified_closure", "stale_source_transition"],
                  "new_schedule_required": False},
    }
    out = pb.Boundary(private).project(out)
    fingerprint = digest(semantic_state(out))
    if previous is not None:
        need(previous.get("schema") == SCHEMA, "previous snapshot schema")
        need(timestamp(previous["as_of"]) <= at, "previous snapshot is newer than current")
        comparable = view_cohort(previous) == view_cohort(out)
        old = digest(semantic_state(previous))
        out["delta"] = {"basis_comparable": comparable, "material_change": old != fingerprint,
                        "notification": "MATERIAL_CHANGE" if old != fingerprint else "NO_UPDATE",
                        "previous_as_of": previous["as_of"], "fingerprint": fingerprint,
                        "comparability_scope": "VIEW_SCHEMA_AND_COHORT_ONLY",
                        "native_control_comparable": None}
    else:
        out["delta"] = {"basis_comparable": None, "material_change": None,
                        "notification": "BASELINE_ONLY", "previous_as_of": None, "fingerprint": fingerprint,
                        "comparability_scope": "VIEW_SCHEMA_AND_COHORT_ONLY",
                        "native_control_comparable": None}
    return out


def artifacts(model: dict) -> dict[str, bytes]:
    spec = importlib.util.spec_from_file_location("portfolio_dashboard", HERE / "dashboard.py")
    dashboard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dashboard)
    queue = io.StringIO()
    columns = ["id", "cluster", "target_repo", "state", "title", "intent", "dov", "dod", "depends_on", "t0_ref"]
    writer = csv.DictWriter(queue, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for task in model["plan"]["tasks"]:
        row = {k: " | ".join(task[k]) if isinstance(task.get(k), list) else task.get(k, "") for k in columns}
        # Spreadsheet formula injection protection for the review CSV.
        writer.writerow({k: "'" + v if isinstance(v, str) and v[:1] in "=+-@\t\r" and v else v for k, v in row.items()})
    ids = {t["id"]: "n" + str(i) for i, t in enumerate(model["plan"]["tasks"])}
    dag = ["flowchart TD"]
    for task in model["plan"]["tasks"]:
        label = re.sub(r'[^A-Za-z0-9 .:_/-]', " ", task["id"] + ": " + task["title"])
        dag.append(f'  {ids[task["id"]]}["{label}"]')
    for a, b, _ in model["plan"].get("edges", []):
        dag.append(f"  {ids[a]} --> {ids[b]}")
    return {"portfolio_readiness.json": canonical(model), "index.html": dashboard.render(model).encode("utf-8"),
            "action_queue.csv": queue.getvalue().encode("utf-8"),
            "execution_dag.mmd": ("\n".join(dag) + "\n").encode("utf-8"),
            "watch_request.json": canonical(model["watch"] | {"delta": model["delta"]})}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--as-of", required=True)
    p.add_argument("--source-sha", required=True, help="Exact planning baseline, never a floating ref")
    p.add_argument("--observation", type=Path)
    p.add_argument("--issue-snapshot", type=Path)
    p.add_argument("--plan", type=Path, default=HERE / "plan.json")
    p.add_argument("--previous", type=Path)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    def read(path):
        return json.loads(path.read_text(encoding="utf-8")) if path else None
    model = project(as_of=args.as_of, source_sha=args.source_sha, observation=read(args.observation),
                    issue_snapshot=read(args.issue_snapshot), plan=read(args.plan), previous=read(args.previous))
    outputs = artifacts(model)
    args.out.mkdir(parents=True, exist_ok=True)
    for name, raw in outputs.items():
        (args.out / name).write_bytes(raw)
    receipt = {"schema": "jade.portfolio-artifacts.v1", "as_of": model["as_of"],
               "files": {name: hashlib.sha256(raw).hexdigest() for name, raw in outputs.items()},
               "authority": model["authority"]}
    (args.out / "manifest.json").write_bytes(canonical(receipt))
    print(json.dumps({"status": "REVIEW_ARTIFACTS_WRITTEN", "notification": model["delta"]["notification"],
                      "file_count": len(outputs) + 1, "merge_admission": "HOLD"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
