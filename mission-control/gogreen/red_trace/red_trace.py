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


def collect(reader: Reader, branch: str, per_workflow: int) -> dict:
    """Per-workflow history (the global run listing is capped at 1000 by the API, which
    starves rarely-run workflows). Truncation is recorded per workflow from total_count."""
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
    return {"runs": runs, "truncated": bool(truncated), "truncated_workflows": truncated}


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
    wfs = []
    for path, seq in sorted(flows.items()):
        c = classify(seq)
        c.update(path=path, name=seq[-1]["name"],
                 history_truncated=path in collected.get("truncated_workflows", {}))
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
    report["digest_sha256"] = hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest()
    return report


ORDER = ["GREEN_TO_RED", "EVERRED", "FLAKY", "RED_TO_GREEN", "STABLE_GREEN", "UNKNOWN_NO_TERMINAL"]


def markdown(rep: dict, limit_green=False) -> str:
    w = rep["window"]
    lines = [f"### GOGREEN red-trace · `{rep['repository']}@{rep['branch']}`",
             f"Window: {w['runs']} runs since {w['oldest_run_at']}" + (f" · history truncated for {w.get('truncated_workflows', 0)} workflow(s) (EVERRED there = never green *in window*)" if w["truncated"] else ""),
             "", "| Class | Count |", "|---|---:|"]
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
            lines.append(f"| {cls} | {x['name']}{' ⁺' if x.get('history_truncated') else ''} | {now} | {win} | {t.get('suspect_commit_count', '')} | {step} |")
    lines += ["", "_Read-only metadata trace. Suspects = commits between last green and first red head "
              "(meaningless when 📌: a pinned run/artifact can expire with zero code change). "
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
    a = ap.parse_args(argv)
    if not a.repo:
        raise SystemExit("--repo required")
    reader = Reader(a.repo)
    if a.runs_json:
        runs = json.loads(a.runs_json.read_text())
        collected = {"runs": runs, "truncated": False}
    else:
        collected = collect(reader, a.branch, a.per_workflow)
    rep = build(a.repo, a.branch, collected, outcomes(collected["runs"]),
                None if (a.no_enrich or a.runs_json) else reader, root=a.root)
    rep["requests"] = reader.requests
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "red_trace.json").write_text(json.dumps(rep, indent=2, sort_keys=True) + "\n")
    (a.out / "red_trace.md").write_text(markdown(rep))
    print(json.dumps({"status": "PASS", "counts": rep["counts"], "runs": rep["window"]["runs"],
                      "truncated": rep["window"]["truncated"], "requests": rep["requests"]}, sort_keys=True))
    return rep


if __name__ == "__main__":
    main()
