#!/usr/bin/env python3
"""GOGREEN red-trace: per-workflow state transitions on one branch, from Actions history.

Read-only. For every workflow observed on the branch it answers:
  * class: EVERRED (never green in window), GREEN_TO_RED (red now, was green),
    RED_TO_GREEN (green now, was red in window), STABLE_GREEN, FLAKY (>=3 flips)
  * the exact break window: last green head SHA -> first red head SHA, with the
    commits in between (the suspect set), and the failing job/step at first red
  * the recovery commit and red-streak length (runs and wall time)

Evidence rules (fail closed, never infer):
  * one outcome per (workflow, head_sha): the highest run_attempt of the latest run
  * only terminal success/failure/timed_out count; cancelled/skipped/in-progress are
    reported but never treated as green or red
  * a window shorter than the requested history is flagged TRUNCATED; EVERRED inside a
    truncated window means "never green in window", not "never green ever"
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "gogreen.red_trace.v1"
GREEN = {"success"}
RED = {"failure", "timed_out", "startup_failure"}
API = "https://api.github.com"


class Reader:
    """GET-only GitHub client; the token is never written to outputs."""

    def __init__(self, repo: str, token: str | None = None, opener=None):
        if repo.count("/") != 1 or any(c in repo for c in "?#%\\ \n"):
            raise ValueError("invalid owner/repo")
        self.repo, self.token = repo, token if token is not None else os.environ.get("GITHUB_TOKEN", "")
        self.opener = opener or urllib.request.urlopen
        self.requests = 0

    def get(self, path: str):
        segs = path.split("?")[0].split("/")
        if not path.startswith("/repos/" + self.repo + "/") or ".." in segs or any(c in path for c in "\\\n\r#"):
            raise ValueError("unapproved read path")
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "gogreen-red-trace/1"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        self.requests += 1
        with self.opener(urllib.request.Request(API + path, headers=headers), timeout=20) as r:
            return json.load(r)


def list_workflows(reader: Reader) -> list:
    """Complete workflow census (fails closed when the listing is short of total_count)."""
    wfs, wpage = [], 1
    while True:  # repos here carry 150-250 workflows; one page silently dropped >half of them
        data = reader.get(f"/repos/{reader.repo}/actions/workflows?per_page=100&page={wpage}")
        batch = data.get("workflows")
        if not isinstance(batch, list):
            raise ValueError("workflows missing")
        wfs += batch
        total = data.get("total_count")
        if len(batch) < 100 or (isinstance(total, int) and len(wfs) >= total) or wpage >= 20:
            break
        wpage += 1
    if isinstance(data.get("total_count"), int) and len(wfs) < data["total_count"]:
        raise ValueError(f"workflow census incomplete: {len(wfs)}/{data['total_count']}")
    return wfs


def collect(reader: Reader, branch: str, per_workflow: int) -> dict:
    """Per-workflow history (the global run listing is capped at 1000 by the API, which
    starves rarely-run workflows). Truncation is recorded per workflow from total_count."""
    wfs = list_workflows(reader)
    runs, truncated = [], {}
    for wf in wfs:
        got, page, total = [], 1, None
        while len(got) < per_workflow:
            data = reader.get(f"/repos/{reader.repo}/actions/workflows/{int(wf['id'])}/runs"
                              f"?branch={branch}&per_page=100&page={page}")
            batch = data.get("workflow_runs")
            if not isinstance(batch, list):
                raise ValueError("workflow_runs missing")
            total = data.get("total_count", total)
            got += batch
            if len(batch) < 100:
                break
            page += 1
        got = got[:per_workflow]
        if got and isinstance(total, int) and total > len(got):
            truncated[wf.get("path")] = {"fetched": len(got), "total": total}
        runs += got
    return {"runs": runs, "truncated": bool(truncated), "truncated_workflows": truncated,
            "workflows_meta": workflow_meta(wfs)}


def workflow_meta(wfs: list) -> dict:
    """{path: {id, name, state, created_at}} for the full census (the coverage denominator)."""
    return {w["path"]: {"id": w.get("id"), "name": w.get("name"), "state": w.get("state"),
                        "created_at": w.get("created_at")}
            for w in wfs if isinstance(w, dict) and w.get("path")}


def nondeterminism(runs: list) -> dict:
    """Per workflow: evidence that the SAME code gave different terminal results.

    `outcomes()` keeps one result per head, so a red that a rerun turned green is invisible
    to `classify()`. That is what separates a nondeterministic gate from one that flipped
    because the code changed (repair oscillation). Two signals, both read-only:
      * same_head_disagreements: distinct runs on one head SHA with both a GREEN and a RED
        terminal conclusion (e.g. push + schedule + dispatch on the same master head);
      * rerun_rescues: runs whose latest attempt (>1) is green, i.e. a rerun was needed.
    """
    heads, rescues = {}, {}
    for r in runs:
        path, sha = r.get("path"), r.get("head_sha")
        if not path or not isinstance(sha, str) or len(sha) != 40:
            continue
        s = state(r.get("conclusion"))
        if s:
            heads.setdefault((path, sha), set()).add(s)
        if s == "GREEN" and (r.get("run_attempt") or 1) > 1:
            rescues[path] = rescues.get(path, 0) + 1
    out = {}
    for (path, sha), states in heads.items():
        o = out.setdefault(path, {"same_head_disagreements": 0, "disagreeing_shas": [], "rerun_rescues": 0})
        if len(states) > 1:
            o["same_head_disagreements"] += 1
            o["disagreeing_shas"] = sorted(o["disagreeing_shas"] + [sha])[:5]
    for path, n in rescues.items():
        out.setdefault(path, {"same_head_disagreements": 0, "disagreeing_shas": [], "rerun_rescues": 0})
        out[path]["rerun_rescues"] = n
    for o in out.values():
        o["nondeterministic"] = bool(o["same_head_disagreements"] or o["rerun_rescues"])
    return out


def outcomes(runs: list) -> dict:
    """{workflow_path: [ {sha, conclusion, ...} oldest->newest ]}, one per head SHA."""
    by = {}
    for r in runs:
        path, sha = r.get("path"), r.get("head_sha")
        if not path or not isinstance(sha, str) or len(sha) != 40:
            continue
        key = (path, sha)
        cur = by.get(key)
        rank = (r.get("created_at") or "", r.get("run_attempt") or 0)
        if cur is None or rank > cur["_rank"]:
            by[key] = {"_rank": rank, "path": path, "name": r.get("name"), "sha": sha,
                       "at": r.get("created_at"), "run_id": r.get("id"),
                       "attempt": r.get("run_attempt"), "event": r.get("event"),
                       "conclusion": r.get("conclusion") or r.get("status")}
    flows = {}
    for v in by.values():
        v.pop("_rank")
        flows.setdefault(v["path"], []).append(v)
    for seq in flows.values():
        seq.sort(key=lambda x: (x["at"] or "", x["run_id"] or 0))
    return flows


def state(c):
    return "GREEN" if c in GREEN else "RED" if c in RED else None


def classify(seq: list) -> dict:
    terminal = [x for x in seq if state(x["conclusion"])]
    flips, prev = [], None
    for x in terminal:
        s = state(x["conclusion"])
        if prev and s != prev["s"]:
            flips.append({"from": prev["s"], "to": s, "before_sha": prev["x"]["sha"],
                          "after_sha": x["sha"], "after_run_id": x["run_id"], "at": x["at"]})
        prev = {"s": s, "x": x}
    out = {"observations": len(seq), "terminal": len(terminal),
           "non_terminal": len(seq) - len(terminal), "flips": flips}
    if not terminal:
        out["class"] = "UNKNOWN_NO_TERMINAL"
        return out
    greens = [x for x in terminal if state(x["conclusion"]) == "GREEN"]
    current = state(terminal[-1]["conclusion"])
    out["current"] = current
    out["latest"] = {k: terminal[-1][k] for k in ("sha", "run_id", "at", "conclusion")}
    streak = 0
    for x in reversed(terminal):  # consecutive heads green since the last red (stability after repair)
        if state(x["conclusion"]) != "GREEN":
            break
        streak += 1
    out["green_streak"] = streak
    if not greens:
        out["class"] = "EVERRED"
        out["first_red"] = {k: terminal[0][k] for k in ("sha", "run_id", "at")}
    elif len(flips) >= 3:
        out["class"] = "FLAKY"
    elif current == "RED":
        out["class"] = "GREEN_TO_RED"
    elif any(f["to"] == "GREEN" for f in flips):
        out["class"] = "RED_TO_GREEN"
    else:
        out["class"] = "STABLE_GREEN"
    if current == "RED" and greens:
        last_green = greens[-1]
        first_red = next(x for x in terminal if x["at"] > last_green["at"] and state(x["conclusion"]) == "RED")
        streak = [x for x in terminal if x["at"] >= first_red["at"]]
        out["break"] = {"last_green_sha": last_green["sha"], "last_green_run": last_green["run_id"],
                        "first_red_sha": first_red["sha"], "first_red_run": first_red["run_id"],
                        "first_red_at": first_red["at"], "red_streak_runs": len(streak)}
    # most recent completed red episode (for RED_TO_GREEN / FLAKY history)
    episodes, open_ep = [], None
    if state(terminal[0]["conclusion"]) == "RED" and flips:
        open_ep = {"last_green_sha": None, "first_red_sha": terminal[0]["sha"],
                   "first_red_run": terminal[0]["run_id"], "first_red_at": terminal[0]["at"],
                   "red_before_window": True}
    for f in flips:
        if f["to"] == "RED":
            open_ep = {"last_green_sha": f["before_sha"], "first_red_sha": f["after_sha"],
                       "first_red_run": f["after_run_id"], "first_red_at": f["at"]}
        elif open_ep:
            open_ep.update(recovery_sha=f["after_sha"], recovery_run=f["after_run_id"], recovered_at=f["at"],
                           red_hours=round(hours(open_ep["first_red_at"], f["at"]), 2))
            episodes.append(open_ep)
            open_ep = None
    out["red_episodes"] = episodes
    return out


def hours(a, b):
    p = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))
    return (p(b) - p(a)).total_seconds() / 3600


def enrich(reader: Reader, wf: dict, max_suspects=30) -> None:
    """Suspect commits and first failing step for each break/episode (bounded GETs)."""
    if "first_red" in wf:
        wf["first_red"]["first_red_run"] = wf["first_red"]["run_id"]
    targets = ([wf["break"]] if "break" in wf else []) + wf.get("red_episodes", [])[-1:] + \
              ([wf["first_red"]] if "first_red" in wf else [])
    for t in targets:
        if t.get("last_green_sha"):
            cmp = reader.get(f"/repos/{reader.repo}/compare/{t['last_green_sha']}...{t['first_red_sha']}")
            commits = cmp.get("commits") or []
            t["suspect_commit_count"] = cmp.get("total_commits", len(commits))
            t["suspects"] = [{"sha": c["sha"], "title": (c["commit"]["message"].splitlines() or [""])[0][:120]}
                             for c in commits[-max_suspects:]]
        jobs = reader.get(f"/repos/{reader.repo}/actions/runs/{t['first_red_run']}/jobs?per_page=50").get("jobs", [])
        t["failing"] = [{"job": j.get("name"),
                         "steps": [s.get("name") for s in j.get("steps", []) if s.get("conclusion") == "failure"]}
                        for j in jobs if j.get("conclusion") == "failure"]


STALE_DAYS = 3


def pins(workflow_file: Path) -> list:
    """Hard-coded historical run/artifact IDs a workflow asserts on (time-bomb dependencies:
    artifacts expire by retention, so such a gate can turn red with zero code change)."""
    import re
    try:
        text = workflow_file.read_text(encoding="utf-8")
    except OSError:
        return []
    found = re.findall(r"actions/runs/(\d{8,})", text) + re.findall(r"\[?'id'\]?\s*==\s*(\d{8,})", text)
    return sorted(set(found))


def build(repo, branch, collected, flows, enriched_reader=None, observed_at=None, root=None):
    observed_at = observed_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    nd = nondeterminism(collected["runs"])
    wfs = []
    for path, seq in sorted(flows.items()):
        c = classify(seq)
        c.update(path=path, name=seq[-1]["name"], first_observed_at=seq[0]["at"],
                 history_truncated=path in collected.get("truncated_workflows", {}),
                 nondeterminism=nd.get(path, {"same_head_disagreements": 0, "disagreeing_shas": [],
                                              "rerun_rescues": 0, "nondeterministic": False}))
        if c.get("latest"):
            c["latest_age_days"] = round(hours(c["latest"]["at"], observed_at) / 24, 1)
            c["stale"] = c["latest_age_days"] > STALE_DAYS
        if root is not None:
            c["pinned_historical_ids"] = pins(Path(root) / path)
        if enriched_reader and c.get("class") in ("GREEN_TO_RED", "EVERRED", "RED_TO_GREEN", "FLAKY"):
            enrich(enriched_reader, c)
        wfs.append(c)
    # Fan-out: several workflows whose break (or latest episode) starts at the same head SHA
    # share one candidate root; count it once, not once per workflow.
    shared = {}
    for w in wfs:
        t = w.get("break") or (w.get("red_episodes") or [None])[-1]
        if t and t.get("last_green_sha"):
            shared.setdefault(t["first_red_sha"], []).append(w["name"])
    fanout = [{"first_red_sha": k, "workflows": sorted(v), "count": len(v)}
              for k, v in sorted(shared.items(), key=lambda kv: (-len(kv[1]), kv[0])) if len(v) > 1]
    counts = {}
    for w in wfs:
        counts[w["class"]] = counts.get(w["class"], 0) + 1
    report = {"schema": SCHEMA, "repository": repo, "branch": branch,
              "observed_at_utc": observed_at,
              "window": {"runs": len(collected["runs"]), "truncated": collected["truncated"],
                         "truncated_workflows": len(collected.get("truncated_workflows", {})),
                         "oldest_run_at": min((r.get("created_at") for r in collected["runs"]), default=None)},
              "counts": counts, "shared_break_roots": fanout,
              "currently_red": sorted(w["name"] for w in wfs if w.get("current") == "RED"),
              "currently_red_stale": sorted(w["name"] for w in wfs if w.get("current") == "RED" and w.get("stale")),
              "workflows": wfs,
              "authority": {"merge_authorized": False, "root_closure_credit": None, "security_waiver": False}}
    meta = {k: v for k, v in (collected.get("workflows_meta") or {}).items() if k.startswith(".github/workflows/")}
    if meta:  # explicit denominator: a workflow absent from this lane is unobserved, not green
        seen = set(flows)
        report["census"] = {"workflows_total": len(meta), "observed": len(seen & set(meta)),
                            "unobserved": sorted(set(meta) - seen)}
    report["digest_sha256"] = hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest()
    return report


# ---------------------------------------------------------------------------------------
# Merged-PR lane. The master lane only sees workflows that run on master; a gate that is
# pull_request-only (about half of this fleet) is invisible to it. The same classify() is
# replayed over a second ordered sequence: the result each workflow showed on the final
# head of every merged PR, AT merge time (merged_outcome_census chronology: a check that
# completed after merging was not a premerge observation).
# ---------------------------------------------------------------------------------------
PR_SCHEMA = "gogreen.red_trace.pr_lane.v1"
PENDING_AT_MERGE = "pending_at_merge"
RERUN_AFTER_MERGE = "rerun_after_merge"


def merged_prs(reader: Reader, base: str, limit: int) -> list:
    if not base or any(c in base for c in "?&#%\\ \n") or ".." in base:
        raise ValueError("invalid base branch")
    prs, page = [], 1
    while page <= 10:
        batch = reader.get(f"/repos/{reader.repo}/pulls?state=closed&base={base}"
                           f"&sort=updated&direction=desc&per_page=100&page={page}")
        if not isinstance(batch, list):
            raise ValueError("pulls missing")
        for p in batch:
            head = (p.get("head") or {}).get("sha")
            if p.get("merged_at") and isinstance(head, str) and len(head) == 40:
                prs.append({"number": int(p["number"]), "head_sha": head, "merged_at": p["merged_at"],
                            "title": (p.get("title") or "")[:120]})
        if len(batch) < 100 or len(prs) >= 3 * limit:
            break
        page += 1
    prs.sort(key=lambda p: (p["merged_at"], p["number"]), reverse=True)
    return prs[:limit]


def head_runs(reader: Reader, sha: str) -> list:
    """Every pull_request run on one head SHA, all workflows, in one paginated listing."""
    if not isinstance(sha, str) or len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        raise ValueError("invalid head SHA")
    runs, page = [], 1
    while True:
        data = reader.get(f"/repos/{reader.repo}/actions/runs?head_sha={sha}&event=pull_request"
                          f"&per_page=100&page={page}")
        batch = data.get("workflow_runs")
        if not isinstance(batch, list):
            raise ValueError("workflow_runs missing")
        runs += batch
        total = data.get("total_count")
        if len(batch) < 100 or (isinstance(total, int) and len(runs) >= total) or page >= 10:
            return runs
        page += 1


def collect_pr_lane(reader: Reader, base: str, limit: int, workflows_meta: dict | None = None) -> dict:
    prs = merged_prs(reader, base, limit)
    for p in prs:
        p["runs"] = head_runs(reader, p["head_sha"])
    return {"prs": prs, "workflows_meta": workflows_meta or workflow_meta(list_workflows(reader))}


def at_merge(runs: list, merged_at: str) -> dict:
    """{workflow path: result on the merged head at merge time}. Only runs created before
    the merge count; a run that was still going (or was re-run) after the merge is
    PENDING_AT_MERGE, never green or red."""
    best = {}
    for r in runs:
        path = r.get("path")
        if not path or not r.get("created_at") or r["created_at"] > merged_at:
            continue
        rank = (r["created_at"], r.get("run_attempt") or 0, r.get("id") or 0)
        if path not in best or rank > best[path][0]:
            best[path] = (rank, r)
    out = {}
    for path, (_, r) in best.items():
        done = r.get("status") == "completed" and (r.get("updated_at") or "9") <= merged_at
        if done:
            c = r.get("conclusion")
        elif (r.get("run_attempt") or 1) > 1 and (r.get("run_started_at") or "") > merged_at:
            c = RERUN_AFTER_MERGE  # the attempt seen at merge was overwritten by a later rerun
        else:
            c = PENDING_AT_MERGE
        out[path] = {"conclusion": c, "run_id": r.get("id"), "attempt": r.get("run_attempt"), "name": r.get("name")}
    return out


def build_pr_lane(repo, base, collected, observed_at=None):
    observed_at = observed_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    prs = sorted(collected["prs"], key=lambda p: (p["merged_at"], p["number"]))
    flows, matrix, premerge = {}, [], []
    for p in prs:
        am = at_merge(p.get("runs", []), p["merged_at"])
        pre = [r for r in p.get("runs", []) if (r.get("created_at") or "9") <= p["merged_at"]]
        premerge += pre
        started = min((r["created_at"] for r in pre), default=None)
        matrix.append({"pr": p["number"], "head_sha": p["head_sha"], "merged_at": p["merged_at"],
                       "title": p.get("title", ""), "at_merge": {k: v["conclusion"] for k, v in sorted(am.items())},
                       "checks_started_at": started,
                       "merge_after_s": round(hours(started, p["merged_at"]) * 3600) if started else None})
        for path, v in am.items():
            flows.setdefault(path, []).append({"path": path, "name": v["name"], "sha": p["head_sha"],
                                               "at": p["merged_at"], "run_id": v["run_id"], "attempt": v["attempt"],
                                               "event": "pull_request", "conclusion": v["conclusion"],
                                               "pr": p["number"]})
    nd = nondeterminism(premerge)
    wfs = []
    for path, seq in sorted(flows.items()):
        c = classify(seq)
        c.update(path=path, name=seq[-1]["name"], lane="merged_pr_heads",
                 merged_red_prs=[x["pr"] for x in seq if state(x["conclusion"]) == "RED"],
                 pending_at_merge_prs=[x["pr"] for x in seq if x["conclusion"] in (PENDING_AT_MERGE, RERUN_AFTER_MERGE)],
                 nondeterminism=nd.get(path, {"same_head_disagreements": 0, "disagreeing_shas": [],
                                              "rerun_rescues": 0, "nondeterministic": False}))
        if c.get("latest"):
            c["latest_pr"] = next(x["pr"] for x in reversed(seq) if x["sha"] == c["latest"]["sha"])
            c["latest_age_days"] = round(hours(c["latest"]["at"], observed_at) / 24, 1)
            c["stale"] = c["latest_age_days"] > STALE_DAYS
        wfs.append(c)
    counts = {}
    for w in wfs:
        counts[w["class"]] = counts.get(w["class"], 0) + 1
    red = [{"pr": m["pr"], "workflows": sorted(k for k, v in m["at_merge"].items() if state(v) == "RED")}
           for m in matrix]
    pend = [{"pr": m["pr"], "workflows": sorted(k for k, v in m["at_merge"].items()
                                                if v in (PENDING_AT_MERGE, RERUN_AFTER_MERGE))}
            for m in matrix]
    lat = sorted(m["merge_after_s"] for m in matrix if m["merge_after_s"] is not None)
    report = {"schema": PR_SCHEMA, "repository": repo, "base": base, "observed_at_utc": observed_at,
              "window": {"merged_prs": len(prs), "oldest_merged_at": prs[0]["merged_at"] if prs else None,
                         "newest_merged_at": prs[-1]["merged_at"] if prs else None,
                         "runs_premerge": len(premerge)},
              "merge_timing": {"prs_with_checks": len(lat), "prs_without_premerge_checks": len(matrix) - len(lat),
                               "median_s_first_check_to_merge": lat[len(lat) // 2] if lat else None,
                               "merged_within_120s_of_first_check": sum(x <= 120 for x in lat)},
              "counts": counts,
              "merged_with_red": [x for x in red if x["workflows"]],
              "merged_with_pending": [x for x in pend if x["workflows"]],
              "workflows": wfs, "merge_matrix": matrix,
              "authority": {"merge_authorized": False, "root_closure_credit": None, "security_waiver": False}}
    meta = collected.get("workflows_meta")
    meta = {k: v for k, v in (meta or {}).items() if k.startswith(".github/workflows/")}
    if meta:
        report["census"] = {"workflows_total": len(meta), "observed": len(set(flows) & set(meta)),
                            "unobserved": sorted(set(meta) - set(flows)),
                            "created_at": {k: v.get("created_at") for k, v in sorted(meta.items())}}
    report["digest_sha256"] = hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest()
    return report


def markdown_pr_lane(rep: dict) -> str:
    w = rep["window"]
    lines = [f"### GOGREEN red-trace · merged-PR lane · `{rep['repository']}` → `{rep['base']}`",
             f"{w['merged_prs']} merged PRs ({w['oldest_merged_at']} → {w['newest_merged_at']}), "
             f"{w['runs_premerge']} premerge runs. Each cell = the result a workflow showed on the merged head "
             f"**at merge time**."]
    if rep.get("census"):
        c = rep["census"]
        lines.append(f"Coverage: {c['observed']}/{c['workflows_total']} workflows observed in this lane.")
    lines += ["", "| Class | Count |", "|---|---:|"]
    lines += [f"| {k} | {rep['counts'].get(k, 0)} |" for k in ORDER if rep["counts"].get(k)]
    mt = rep.get("merge_timing") or {}
    lines += ["", f"**Merged with a red check at merge time: {len(rep['merged_with_red'])} PR(s)** · "
              f"merged while a check was still pending: {len(rep['merged_with_pending'])} PR(s) · "
              f"merged ≤ 120 s after its first check started: {mt.get('merged_within_120s_of_first_check', '—')} "
              f"(median {mt.get('median_s_first_check_to_merge', '—')} s)", ""]
    for x in rep["merged_with_red"][-15:]:
        lines.append(f"- #{x['pr']}: " + ", ".join(p.split('/')[-1] for p in x["workflows"]))
    lines += ["", "| Class | Workflow | Now | Green streak | Merged red | Same-head disagreement / rerun rescue |",
              "|---|---|---|---:|---:|---|"]
    for cls in ORDER:
        if cls == "STABLE_GREEN":
            continue
        for x in [x for x in rep["workflows"] if x["class"] == cls]:
            nd = x["nondeterminism"]
            lines.append(f"| {cls} | {x['name']} | {x.get('current', '—')} (#{x.get('latest_pr', '—')}) | "
                         f"{x.get('green_streak', 0)} | {len(x['merged_red_prs'])} | "
                         f"{nd['same_head_disagreements']} / {nd['rerun_rescues']} |")
    lines += ["", "_Read-only. A red at merge is an observation about that head, not a root or a fault "
              "attribution; whether the check was required at the time is not read here._"]
    return "\n".join(lines) + "\n"


ORDER = ["GREEN_TO_RED", "EVERRED", "FLAKY", "RED_TO_GREEN", "STABLE_GREEN", "UNKNOWN_NO_TERMINAL"]


def markdown(rep: dict, limit_green=False) -> str:
    w = rep["window"]
    lines = [f"### GOGREEN red-trace · `{rep['repository']}@{rep['branch']}`",
             f"Window: {w['runs']} runs since {w['oldest_run_at']}" + (f" · history truncated for {w.get('truncated_workflows', 0)} workflow(s) (EVERRED there = never green *in window*)" if w["truncated"] else ""),
             "", "| Class | Count |", "|---|---:|"]
    if rep.get("census"):
        c = rep["census"]
        lines.insert(2, f"Coverage: {c['observed']}/{c['workflows_total']} workflows ran on `{rep['branch']}` in window; "
                        f"the other {len(c['unobserved'])} are unobserved here (see the merged-PR lane), not green.")
    lines += [f"| {k} | {rep['counts'].get(k, 0)} |" for k in ORDER if rep["counts"].get(k)]
    if rep.get("shared_break_roots"):
        lines += ["", "**Shared break roots** (one head SHA turned several workflows red; treat as one candidate root):", ""]
        lines += [f"- `{r['first_red_sha'][:8]}` → {r['count']} workflows: {', '.join(r['workflows'])}" for r in rep["shared_break_roots"]]
    lines += ["", f"**Red at last observation on `{rep['branch']}`: {len(rep.get('currently_red', []))}** "
              f"(stale > {STALE_DAYS} d, needs a replay before it says anything about current HEAD: "
              f"{len(rep.get('currently_red_stale', []))})"]
    lines += ["", "| Class | Workflow | Now | Break / episode window | Suspects | First failing step |", "|---|---|---|---|---:|---|"]
    for cls in ORDER:
        if cls == "STABLE_GREEN" and limit_green:
            continue
        for x in [x for x in rep["workflows"] if x["class"] == cls]:
            t = x.get("break") or (x.get("red_episodes") or [None])[-1] or (dict(x["first_red"], first_red_sha=x["first_red"]["sha"]) if "first_red" in x else {})
            win = ""
            if t.get("last_green_sha"):
                win = f"`{t['last_green_sha'][:8]}` → `{t['first_red_sha'][:8]}`"
                if t.get("recovery_sha"):
                    win += f" → ✓`{t['recovery_sha'][:8]}` ({t['red_hours']} h)"
                elif t.get("red_streak_runs"):
                    win += f" ({t['red_streak_runs']} red)"
            elif t.get("red_before_window") and t.get("recovery_sha"):
                win = f"red at window start (`{t['first_red_sha'][:8]}`) → ✓`{t['recovery_sha'][:8]}`"
            elif t.get("first_red_sha"):
                win = f"never green in window; first `{t['first_red_sha'][:8]}`"
            step = "; ".join(f"{f['job']}: {', '.join(f['steps'])}" for f in t.get("failing", []))[:160]
            now = x.get("current", "—") + (f" · stale {x['latest_age_days']} d" if x.get("stale") else "")
            if x.get("pinned_historical_ids") and x.get("current") == "RED":
                now += " · 📌 pinned run/artifact"
            if (x.get("nondeterminism") or {}).get("nondeterministic"):
                now += " · ↻ same-head disagreement/rerun"
            lines.append(f"| {cls} | {x['name']}{' ⁺' if x.get('history_truncated') else ''} | {now} | {win} | {t.get('suspect_commit_count', '')} | {step} |")
    lines += ["", "_Read-only metadata trace. Suspects = commits between last green and first red head "
              "(meaningless when 📌: a pinned run/artifact can expire with zero code change). "
              "↻ = the same head gave both green and red, or needed a rerun (nondeterminism, not a code change). "
              "⁺ = older history not fetched. Not a causal attribution or root-closure credit._"]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    ap.add_argument("--branch", default="master")
    ap.add_argument("--per-workflow", type=int, default=200)
    ap.add_argument("--runs-json", type=Path, help="offline: recorded runs list instead of API")
    ap.add_argument("--no-enrich", action="store_true")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--root", type=Path, default=Path("."), help="checkout root, for pinned-ID scan")
    ap.add_argument("--pr-lane", type=int, default=0, metavar="N",
                    help="also trace the last N merged PR heads into --branch (0 = off)")
    a = ap.parse_args(argv)
    if not a.repo:
        raise SystemExit("--repo required")
    reader = Reader(a.repo)
    if a.runs_json:
        runs = json.loads(a.runs_json.read_text(encoding="utf-8"))
        collected = {"runs": runs, "truncated": False}
    else:
        collected = collect(reader, a.branch, a.per_workflow)
    rep = build(a.repo, a.branch, collected, outcomes(collected["runs"]),
                None if (a.no_enrich or a.runs_json) else reader, root=a.root)
    rep["requests"] = reader.requests
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "red_trace.json").write_text(json.dumps(rep, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (a.out / "red_trace.md").write_text(markdown(rep), encoding="utf-8", newline="\n")
    summary = {"status": "PASS", "counts": rep["counts"], "runs": rep["window"]["runs"],
               "truncated": rep["window"]["truncated"], "requests": rep["requests"]}
    if a.pr_lane > 0 and not a.runs_json:
        before = reader.requests
        pr = build_pr_lane(a.repo, a.branch, collect_pr_lane(reader, a.branch, a.pr_lane,
                                                              collected.get("workflows_meta")))
        pr["requests"] = reader.requests - before
        (a.out / "red_trace_pr.json").write_text(json.dumps(pr, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        (a.out / "red_trace_pr.md").write_text(markdown_pr_lane(pr), encoding="utf-8", newline="\n")
        summary["pr_lane"] = {"merged_prs": pr["window"]["merged_prs"], "counts": pr["counts"],
                              "merged_with_red": len(pr["merged_with_red"]), "requests": pr["requests"]}
    print(json.dumps(summary, sort_keys=True))
    return rep


if __name__ == "__main__":
    main()
