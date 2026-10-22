#!/usr/bin/env python3
"""Bind gates to the LATEST VALID producer run, never a pinned run/artifact id (#529 G05).

A gate that asserts on a hard-coded historical run or artifact id turns red with zero
code change once GitHub's artifact retention purges it (GM-V Governor Readiness and
GM-V 3PSTAR MIP Control, red since 2026-10-17). This module replaces such pins with a
deterministic resolution rule, and checks that the rule stays satisfiable:

  resolve    latest producer run on the default branch that is
               * event in {push, schedule, workflow_dispatch}  (merged code only)
               * status completed, conclusion success
               * head_sha is an ANCESTOR of (or equal to) the gate's own source SHA
               * has a non-expired artifact named <prefix><head_sha> with a sha256 digest
               * created within --max-age-days (default 30 = retention)
             writes the same run / artifact JSON files the pinned steps produced, plus a
             binding receipt. No valid run -> exit 1 (fail closed), never a silent pass.
  dag-check  EVIDENCE_BINDING_DAG_v1.json against the workflows: every consumer gate
             calls this resolver and pins no run/artifact id; every producer has a
             schedule whose period leaves >= 2x margin inside retention.
  census     every hard-coded run/artifact id in a checkout, classified LIVE_GATE
             (a workflow asserts on it) vs HISTORICAL_RECORD (committed lineage),
             optionally with API existence/expiry (--api).
GET only. No dispatch, no merge, no authority transfer.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DAG = Path(__file__).resolve().parent / "EVIDENCE_BINDING_DAG_v1.json"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
EVENTS = ("push", "schedule", "workflow_dispatch")
PIN_PATTERNS = [
    ("run", re.compile(r"actions/runs/(\d{8,})")),
    ("artifact", re.compile(r"actions/artifacts/(\d{8,})")),
    ("id", re.compile(r"\[?['\"]id['\"]\]?\s*==\s*(\d{9,})")),  # run OR artifact: probed
    ("run", re.compile(r"['\"]?(?:postmerge_)?run_id['\"]?\s*[:=]\s*['\"]?(\d{9,})")),
    ("artifact", re.compile(r"['\"]?(?:postmerge_)?artifact_id['\"]?\s*[:=]\s*['\"]?(\d{9,})")),
]


class EvidenceError(RuntimeError):
    pass


class Reader:
    def __init__(self, repo, token=None, opener=None):
        if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo or ""):
            raise ValueError("invalid owner/repo")
        self.repo, self.token = repo, token if token is not None else os.environ.get("GITHUB_TOKEN", os.environ.get("GH_TOKEN", ""))
        self.opener = opener or urllib.request.urlopen

    def get(self, path):
        if not path.startswith(f"/repos/{self.repo}/") or ".." in path.split("?")[0].split("/"):
            raise ValueError("unapproved read path")
        h = {"Accept": "application/vnd.github+json", "User-Agent": "gm-evidence-binding/1"}
        if self.token:
            h["Authorization"] = "Bearer " + self.token
        with self.opener(urllib.request.Request("https://api.github.com" + path, headers=h), timeout=20) as r:
            return json.load(r)


def _age_days(ts, now):
    t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return (now - t).total_seconds() / 86400


def is_ancestor(reader, ancestor, descendant):
    if ancestor == descendant:
        return True
    cmp = reader.get(f"/repos/{reader.repo}/compare/{ancestor}...{descendant}")
    return cmp.get("status") in ("ahead", "identical")


def resolve(reader, producer, prefix, source_sha, branch="master", max_age_days=30, now=None, scan=50):
    if not SHA40.fullmatch(source_sha or ""):
        raise EvidenceError("invalid gate source SHA")
    if not re.fullmatch(r"[\w.-]+\.ya?ml", producer):
        raise EvidenceError("producer must be a workflow file name")
    now = now or datetime.now(timezone.utc)
    runs = reader.get(f"/repos/{reader.repo}/actions/workflows/{producer}/runs"
                      f"?branch={branch}&status=success&per_page={int(scan)}").get("workflow_runs", [])
    rejected = []
    for run in sorted(runs, key=lambda r: (r.get("created_at") or "", r.get("id") or 0), reverse=True):
        why = None
        if run.get("event") not in EVENTS:
            why = "event " + str(run.get("event"))
        elif run.get("status") != "completed" or run.get("conclusion") != "success":
            why = "not success"
        elif _age_days(run["created_at"], now) > max_age_days:
            why = "older than retention window"
        elif not is_ancestor(reader, run["head_sha"], source_sha):
            why = "head not an ancestor of gate source"
        if why:
            rejected.append({"run_id": run.get("id"), "reason": why})
            continue
        arts = reader.get(f"/repos/{reader.repo}/actions/runs/{run['id']}/artifacts?per_page=100").get("artifacts", [])
        want = prefix + run["head_sha"]
        art = next((a for a in arts if a.get("name") == want), None)
        if art is None or art.get("expired") is not False or not str(art.get("digest", "")).startswith("sha256:"):
            rejected.append({"run_id": run["id"], "reason": "artifact missing/expired/undigested"})
            continue
        return {"schema": "gm.evidence_binding.v1", "rule": "LATEST_VALID_RUN", "producer": producer,
                "branch": branch, "gate_source_sha": source_sha, "run_id": run["id"], "run_event": run["event"],
                "head_sha": run["head_sha"], "run_created_at": run["created_at"],
                "artifact_id": art["id"], "artifact_name": art["name"], "artifact_digest": art["digest"],
                "artifact_expires_at": art.get("expires_at"),
                "age_days": round(_age_days(run["created_at"], now), 2), "max_age_days": max_age_days,
                "rejected_newer_candidates": rejected, "pinned_ids_used": False,
                "merge_authorized": False}, run, art, arts
    raise EvidenceError(f"NO_VALID_EVIDENCE: {producer} has no successful {branch} run within "
                        f"{max_age_days} d with a live '{prefix}<sha>' artifact ancestor to {source_sha[:8]} "
                        f"(rejected {len(rejected)})")


# ------------------------------------------------------------------ DAG / scheduler checks
CRON_DAYS = {"weekly": 7, "daily": 1}


def cron_period_days(expr):
    """Upper bound on the gap between firings of a 5-field cron expression (days)."""
    f = expr.split()
    if len(f) != 5:
        raise ValueError("bad cron")
    _, _, dom, _, dow = f
    if dom == "*" and dow == "*":
        return 1
    if dom == "*" and dow != "*":
        days = set()
        for part in dow.split(","):
            if "-" in part:
                a, b = (int(x) for x in part.split("-"))
                days |= set(range(a, b + 1))
            else:
                days.add(int(part) % 7)
        if not days:
            return 7
        s = sorted(days)
        gaps = [(s[(i + 1) % len(s)] - s[i]) % 7 or 7 for i in range(len(s))]
        return max(gaps)
    return 31  # day-of-month schedules: monthly-scale


def workflow_schedules(path):
    import yaml
    d = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    on = d.get(True, d.get("on")) or {}
    return [s["cron"] for s in (on.get("schedule") or []) if isinstance(s, dict) and "cron" in s]


def find_pins(text):
    out = []
    for kind, rx in PIN_PATTERNS:
        for m in rx.finditer(text):
            out.append((kind, m.group(1)))
    return sorted(set(out))


def dag_check(root=ROOT, dag_path=DAG):
    dag = json.loads(Path(dag_path).read_text(encoding="utf-8"))
    wf = Path(root) / ".github" / "workflows"
    problems, rows = [], []
    retention = dag["retention_days"]
    for p in dag["producers"]:
        crons = workflow_schedules(wf / p["workflow"])
        period = min((cron_period_days(c) for c in crons), default=None)
        ok = period is not None and period * 2 <= retention
        rows.append({"producer": p["workflow"], "crons": crons, "max_gap_days": period, "ok": ok})
        if not ok:
            problems.append(f"producer {p['workflow']}: schedule gap {period} d leaves <2x margin in {retention} d retention")
    for e in dag["edges"]:
        text = (wf / e["consumer"]).read_text(encoding="utf-8")
        pins = find_pins(text)
        calls = "evidence_binding.py resolve" in text and e["producer"] in text and e["artifact_prefix"] in text
        rows.append({"consumer": e["consumer"], "producer": e["producer"], "resolver": calls, "pins": pins})
        if pins:
            problems.append(f"consumer {e['consumer']} still pins {pins}")
        if not calls:
            problems.append(f"consumer {e['consumer']} does not resolve {e['producer']} via evidence_binding.py")
    return {"schema": "gm.evidence_binding.dag_check.v1", "ok": not problems, "problems": problems, "rows": rows}


# ------------------------------------------------------------------ census
SCAN_SUFFIX = {".yml", ".yaml", ".py", ".json", ".sh", ".ps1"}
SKIP_DIRS = {".git", "node_modules", "__pycache__"}


def _probe(reader, kind, ident, now):
    def run():
        r = reader.get(f"/repos/{reader.repo}/actions/runs/{ident}")
        n = reader.get(f"/repos/{reader.repo}/actions/runs/{ident}/artifacts").get("total_count")
        return {"resolved_kind": "run", "exists": True, "created_at": r.get("created_at"), "artifacts_remaining": n,
                "dead": n == 0}

    def art():
        a = reader.get(f"/repos/{reader.repo}/actions/artifacts/{ident}")
        left = None
        if a.get("expires_at"):
            left = round((datetime.fromisoformat(a["expires_at"].replace("Z", "+00:00")) - now).total_seconds() / 86400, 1)
        return {"resolved_kind": "artifact", "exists": True, "expired": a.get("expired"), "expires_at": a.get("expires_at"),
                "days_left": left, "dead": a.get("expired") is True}

    order = {"run": [run], "artifact": [art], "id": [run, art]}[kind]
    last = None
    for f in order:
        try:
            return f()
        except urllib.error.HTTPError as e:
            last = e.code
    return {"resolved_kind": kind, "exists": False, "http_status": last, "dead": True}


def census(root, repo_name, reader=None, max_files=60000, warn_days=14):
    root = Path(root)
    found = {}
    n = 0
    for p in root.rglob("*"):
        if n >= max_files:
            break
        if not p.is_file() or p.suffix not in SCAN_SUFFIX or any(s in p.parts for s in SKIP_DIRS):
            continue
        n += 1
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = p.relative_to(root).as_posix()
        live = rel.startswith(".github/workflows/")
        for kind, ident in find_pins(text):
            row = found.setdefault((kind, ident), {"kind": kind, "id": ident, "live_gates": [], "records": []})
            (row["live_gates"] if live else row["records"]).append(rel)
    rows = sorted(found.values(), key=lambda r: (-len(r["live_gates"]), r["kind"], r["id"]))
    now = datetime.now(timezone.utc)
    if reader is not None:
        for r in rows:
            if r["live_gates"]:
                r["api"] = _probe(reader, r["kind"], r["id"], now)
                dl = r["api"].get("days_left")
                r["state"] = ("DEAD" if r["api"]["dead"] else
                              "TIME_BOMB" if dl is not None and dl <= warn_days else "LIVE")
    live = [r for r in rows if r["live_gates"]]
    return {"schema": "gm.evidence_binding.pin_census.v1", "repository": repo_name, "files_scanned": n,
            "pins_total": len(rows), "live_gate_pins": len(live),
            "historical_record_pins": len(rows) - len(live),
            "live_gate_pins_dead": sum(1 for r in live if r.get("state") == "DEAD"),
            "live_gate_pins_time_bomb": sum(1 for r in live if r.get("state") == "TIME_BOMB"),
            "warn_days": warn_days,
            "rows": rows}


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("resolve")
    r.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    r.add_argument("--producer", required=True)
    r.add_argument("--artifact-prefix", required=True)
    r.add_argument("--source-sha", required=True)
    r.add_argument("--branch", default="master")
    r.add_argument("--max-age-days", type=float, default=30)
    r.add_argument("--run-out", type=Path)
    r.add_argument("--artifact-out", type=Path)
    r.add_argument("--artifacts-list-out", type=Path)
    r.add_argument("--binding-out", type=Path, required=True)
    d = sub.add_parser("dag-check")
    d.add_argument("--root", type=Path, default=ROOT)
    d.add_argument("--out", type=Path)
    c = sub.add_parser("census")
    c.add_argument("--root", type=Path, default=ROOT)
    c.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "GBOGEB/pipeline-automation-hub"))
    c.add_argument("--api", action="store_true")
    c.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    if a.cmd == "resolve":
        try:
            binding, run, art, arts = resolve(Reader(a.repo), a.producer, a.artifact_prefix, a.source_sha,
                                              a.branch, a.max_age_days)
        except EvidenceError as e:
            print(f"::error title=evidence binding::{e}")
            a.binding_out.write_text(json.dumps({"schema": "gm.evidence_binding.v1", "result": "FAIL",
                                                 "reason": str(e), "merge_authorized": False}, indent=2) + "\n")
            return 1
        for path, obj in ((a.run_out, run), (a.artifact_out, art), (a.artifacts_list_out, {"total_count": len(arts), "artifacts": arts})):
            if path:
                path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
        binding["result"] = "PASS"
        a.binding_out.write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
        print(f"PASS_LATEST_VALID_EVIDENCE {a.producer} run={binding['run_id']} head={binding['head_sha'][:8]} "
              f"artifact={binding['artifact_id']} age={binding['age_days']}d expires={binding['artifact_expires_at']}")
        return 0
    if a.cmd == "dag-check":
        rep = dag_check(a.root)
        if a.out:
            a.out.write_text(json.dumps(rep, indent=2) + "\n")
        print(json.dumps({"ok": rep["ok"], "problems": rep["problems"]}))
        return 0 if rep["ok"] else 1
    rep = census(a.root, a.repo, Reader(a.repo) if a.api else None)
    a.out.write_text(json.dumps(rep, indent=2) + "\n")
    print(json.dumps({k: rep[k] for k in ("repository", "files_scanned", "pins_total", "live_gate_pins",
                                          "historical_record_pins", "live_gate_pins_dead",
                                          "live_gate_pins_time_bomb")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
