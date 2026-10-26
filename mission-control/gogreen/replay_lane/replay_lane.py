#!/usr/bin/env python3
"""GOGREEN bounded auto-replay lane (#529 G04, owner-approved actions:write).

Input: red_trace.json (gogreen.red_trace.v1) for the default branch, produced earlier in the
same job. Selects workflows that are RED at last observation AND stale, then dispatches them on
master so the ledger reflects current HEAD instead of a weeks-old verdict.

Every candidate must pass ALL gates, else it is skipped with a typed reason:
  stale red          current == RED and latest observation older than policy.stale_days
  dispatchable       workflow_dispatch trigger with no required inputs
  read-only          no `write` permission outside policy.allowed_permission_writes
                     (workflow- AND job-level; `write-all` / missing permissions = refused)
  not denied         not in policy.deny (superseded gates, the lane itself, publishers)
  not pinned         no dead/pinned historical evidence (📌): a replay cannot fix those
  rate               no workflow_dispatch run of it in the last N hours, none queued/running
  back-pressure      repo queued runs <= policy.max_repo_queued_runs (else the lane skips)
  budget             at most policy.max_dispatches_per_run dispatches, oldest red first
The only write call is POST .../actions/workflows/<file>/dispatches {"ref": branch}.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
POLICY = HERE / "REPLAY_POLICY.json"
FILE_RX = re.compile(r"\.github/workflows/[\w.-]+\.ya?ml\Z")


class Api:
    def __init__(self, repo, token=None, opener=None):
        if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo or ""):
            raise ValueError("invalid owner/repo")
        self.repo, self.token = repo, token if token is not None else os.environ.get("GITHUB_TOKEN", "")
        self.opener = opener or urllib.request.urlopen
        self.posts = []

    def _req(self, path, body=None):
        h = {"Accept": "application/vnd.github+json", "User-Agent": "gogreen-replay-lane/1"}
        if self.token:
            h["Authorization"] = "Bearer " + self.token
        data = None
        if body is not None:
            h["Content-Type"] = "application/json"
            data = json.dumps(body).encode()
        req = urllib.request.Request("https://api.github.com" + path, headers=h, data=data,
                                     method="POST" if body is not None else "GET")
        with self.opener(req, timeout=20) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}

    def get(self, path):
        if not path.startswith(f"/repos/{self.repo}/") or ".." in path.split("?")[0].split("/"):
            raise ValueError("unapproved read path")
        return self._req(path)

    def dispatch(self, wf_file, ref):
        name = Path(wf_file).name
        if not re.fullmatch(r"[\w.-]+\.ya?ml", name):
            raise ValueError("bad workflow file")
        path = f"/repos/{self.repo}/actions/workflows/{name}/dispatches"  # the ONLY write endpoint
        self.posts.append(path)
        return self._req(path, {"ref": ref})


def workflow_facts(root: Path, rel: str) -> dict:
    p = root / rel
    if not FILE_RX.fullmatch(rel) or not p.is_file():
        return {"exists": False}
    d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    on = d.get(True, d.get("on"))
    disp = None
    if isinstance(on, dict) and "workflow_dispatch" in on:
        disp = on.get("workflow_dispatch") or {}
    elif on == "workflow_dispatch" or (isinstance(on, list) and "workflow_dispatch" in on):
        disp = {}
    required = sorted(k for k, v in ((disp or {}).get("inputs") or {}).items()
                      if isinstance(v, dict) and v.get("required") and "default" not in v)

    def writes(perm):
        if perm is None:
            return ["<unspecified: default token permissions>"]
        if isinstance(perm, str):
            return [] if perm == "read-all" else [perm]
        return sorted(k for k, v in perm.items() if v == "write")
    w = set(writes(d.get("permissions")))
    for job in (d.get("jobs") or {}).values():
        if isinstance(job, dict) and "permissions" in job:
            w |= set(writes(job["permissions"])) - {"<unspecified: default token permissions>"}
    return {"exists": True, "dispatchable": disp is not None, "required_inputs": required, "writes": sorted(w)}


def plan(trace: dict, root: Path, policy: dict, api: Api, now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    stale_cut = timedelta(days=policy["stale_days"])
    rate_cut = timedelta(hours=policy["min_hours_between_replays_per_workflow"])
    allowed = set(policy["allowed_permission_writes"])
    rows = []
    for w in trace.get("workflows", []):
        if w.get("current") != "RED":
            continue
        latest = w.get("latest") or {}
        at = datetime.fromisoformat(latest["at"].replace("Z", "+00:00")) if latest.get("at") else None
        row = {"workflow": w["name"], "path": w["path"], "class": w["class"], "latest_at": latest.get("at"),
               "age_days": round((now - at).total_seconds() / 86400, 1) if at else None}
        f = workflow_facts(root, w["path"])
        reason = None
        if at is None or now - at <= stale_cut:
            reason = "fresh red: needs repair, not replay"
        elif w["path"] in policy["deny"]:
            reason = "denied: " + policy["deny"][w["path"]]
        elif not f.get("exists"):
            reason = "workflow file absent at this checkout"
        elif not f["dispatchable"]:
            reason = "no workflow_dispatch trigger"
        elif f["required_inputs"]:
            reason = "required dispatch inputs " + ",".join(f["required_inputs"])
        elif set(f["writes"]) - allowed:
            reason = "not read-only: writes " + ",".join(sorted(set(f["writes"]) - allowed))
        elif w.get("pinned_historical_ids"):
            reason = "pinned historical evidence: replay cannot fix (see G05)"
        row["facts"] = f
        row["skip"] = reason
        rows.append(row)
    cands = sorted((r for r in rows if not r["skip"]), key=lambda r: r["latest_at"])
    queued = api.get(f"/repos/{api.repo}/actions/runs?status=queued&per_page=1").get("total_count", 0)
    rep = {"schema": "gogreen.replay_lane.receipt.v1", "observed_at_utc": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
           "trace_digest": trace.get("digest_sha256"), "repo_queued_runs": queued, "policy": {k: policy[k] for k in (
               "stale_days", "max_dispatches_per_run", "min_hours_between_replays_per_workflow", "max_repo_queued_runs")},
           "rows": rows, "dispatch": [], "merge_authorized": False}
    if queued > policy["max_repo_queued_runs"]:
        rep["lane"] = "SKIPPED_BACKPRESSURE"
        for r in cands:
            r["skip"] = f"back-pressure: {queued} queued > {policy['max_repo_queued_runs']}"
        return rep
    budget = policy["max_dispatches_per_run"]
    for r in cands:
        name = Path(r["path"]).name
        recent = api.get(f"/repos/{api.repo}/actions/workflows/{name}/runs?event=workflow_dispatch&per_page=1").get("workflow_runs", [])
        if recent:
            last = datetime.fromisoformat(recent[0]["created_at"].replace("Z", "+00:00"))
            if now - last < rate_cut:
                r["skip"] = f"rate: replayed {round((now - last).total_seconds() / 3600, 1)} h ago"
                continue
        busy = sum(api.get(f"/repos/{api.repo}/actions/workflows/{name}/runs?status={s}&per_page=1").get("total_count", 0)
                   for s in ("queued", "in_progress"))
        if busy:
            r["skip"] = "already queued/in progress"
            continue
        if budget <= 0:
            r["skip"] = "budget exhausted this run"
            continue
        budget -= 1
        rep["dispatch"].append(r["path"])
    rep["lane"] = "PLANNED"
    return rep


def markdown(rep):
    lines = ["### GOGREEN replay lane", "",
             f"Lane: **{rep['lane']}** · repo queued {rep['repo_queued_runs']} · "
             f"dispatch {len(rep['dispatch'])}/{rep['policy']['max_dispatches_per_run']}", "",
             "| Workflow | Class | Red age (d) | Decision |", "|---|---|---:|---|"]
    for r in rep["rows"]:
        d = "DISPATCHED" if r["path"] in rep.get("dispatched", []) else (
            "PLANNED" if r["path"] in rep["dispatch"] else "skip: " + (r["skip"] or ""))
        lines.append(f"| {r['workflow']} | {r['class']} | {r['age_days']} | {d} |")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    ap.add_argument("--trace", type=Path, required=True)
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--policy", type=Path, default=POLICY)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--summary", type=Path)
    a = ap.parse_args(argv)
    policy = json.loads(a.policy.read_text(encoding="utf-8"))
    trace = json.loads(a.trace.read_text(encoding="utf-8"))
    if trace.get("schema") != "gogreen.red_trace.v1" or trace.get("branch") != policy["branch"]:
        raise SystemExit("REPLAY_LANE_REFUSED: trace is not a default-branch gogreen.red_trace.v1 report")
    api = Api(a.repo)
    rep = plan(trace, a.root, policy, api)
    rep["dry_run"] = bool(a.dry_run)
    rep["dispatched"] = []
    if not a.dry_run:
        for path in rep["dispatch"]:
            api.dispatch(path, policy["branch"])
            rep["dispatched"].append(path)
    a.out.write_text(json.dumps(rep, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    if a.summary:
        a.summary.write_text(markdown(rep), encoding="utf-8", newline="\n")
    print(json.dumps({"lane": rep["lane"], "candidates": sum(1 for r in rep["rows"] if not r["skip"]),
                      "planned": len(rep["dispatch"]), "dispatched": len(rep["dispatched"]), "dry_run": rep["dry_run"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
