#!/usr/bin/env python3
"""GOGREEN required-gate aggregator: one always-reporting check for path-filtered gates.

Problem: CODE PURPLE Method Atlas and Live Lossless QA only run on PRs touching their
`paths`. Marking them required on master would leave every other PR waiting forever
for a check that never reports. This gate runs on every PR and:

  * reads each guarded workflow's own pull_request.paths from the PR-head checkout
    (single source of truth; no duplicated path lists),
  * NOT_APPLICABLE  if no changed file matches -> pass,
  * otherwise waits for that workflow's run on the exact PR head SHA and passes only
    on `success`; failure/cancelled/timed_out/absent-after-deadline -> fail closed.

Read-only GETs. Requiring THIS single check is the owner's branch-protection decision.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

import yaml

GUARDED = (".github/workflows/code-purple-method-atlas.yml", ".github/workflows/live-lossless-qa.yml")
PASS, FAIL, NA, WAIT = "PASS", "FAIL", "NOT_APPLICABLE", "WAITING"


def glob_to_regex(pattern: str) -> re.Pattern:
    """GitHub Actions path-filter glob: ** spans '/', * and ? do not."""
    out, i = "", 0
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"; i += 3; continue
        if pattern.startswith("**", i):
            out += ".*"; i += 2; continue
        out += {"*": "[^/]*", "?": "[^/]"}.get(c, re.escape(c)); i += 1
    return re.compile(out + r"\Z")


def path_filters(workflow_file: Path) -> list | None:
    """pull_request.paths of a workflow; None = no paths filter (runs on every PR)."""
    data = yaml.safe_load(workflow_file.read_text(encoding="utf-8"))
    on = data.get(True, data.get("on"))
    pr = on.get("pull_request") if isinstance(on, dict) else None
    if pr is None:
        raise ValueError(f"{workflow_file}: no pull_request trigger; cannot be gated per PR")
    paths = (pr or {}).get("paths")
    if (pr or {}).get("paths-ignore"):
        raise ValueError(f"{workflow_file}: paths-ignore not supported by this gate")
    return list(paths) if paths else None


def applies(changed: list, filters: list | None) -> list:
    if filters is None:
        return list(changed) or ["<no paths filter>"]
    pos = [glob_to_regex(p) for p in filters if not p.startswith("!")]
    neg = [glob_to_regex(p[1:]) for p in filters if p.startswith("!")]
    return [f for f in changed if any(r.match(f) for r in pos) and not any(r.match(f) for r in neg)]


def verdict(runs: list) -> str:
    """runs = this workflow's pull_request runs on the exact head SHA (any attempts)."""
    if not runs:
        return WAIT
    latest = max(runs, key=lambda r: (r.get("run_attempt") or 0, r.get("created_at") or "", r.get("id") or 0))
    if latest.get("status") != "completed":
        return WAIT
    return PASS if latest.get("conclusion") == "success" else FAIL


class Reader:
    def __init__(self, repo, token=None, opener=None):
        self.repo, self.token = repo, token if token is not None else os.environ.get("GITHUB_TOKEN", "")
        self.opener = opener or urllib.request.urlopen

    def get(self, path):
        if not path.startswith(f"/repos/{self.repo}/") or ".." in path.split("?")[0].split("/"):
            raise ValueError("unapproved read path")
        h = {"Accept": "application/vnd.github+json", "User-Agent": "gogreen-required-gate/1"}
        if self.token:
            h["Authorization"] = "Bearer " + self.token
        with self.opener(urllib.request.Request("https://api.github.com" + path, headers=h), timeout=20) as r:
            return json.load(r)


def changed_files(reader, pr):
    files, page = [], 1
    while True:
        batch = reader.get(f"/repos/{reader.repo}/pulls/{int(pr)}/files?per_page=100&page={page}")
        files += [f["filename"] for f in batch] + [f["previous_filename"] for f in batch if f.get("previous_filename")]
        if len(batch) < 100 or page >= 30:
            return files
        page += 1


def head_runs(reader, workflow_file, sha):
    name = Path(workflow_file).name
    data = reader.get(f"/repos/{reader.repo}/actions/workflows/{name}/runs?head_sha={sha}&event=pull_request&per_page=20")
    return data.get("workflow_runs", [])


def evaluate(reader, root, pr, sha, deadline_s, poll_s=30, clock=time.monotonic, sleep=time.sleep):
    changed = changed_files(reader, pr)
    report = {"schema": "gogreen.required_gate.v1", "pr": pr, "head_sha": sha,
              "changed_files": len(changed), "gates": [], "merge_authorized": False}
    pending = {}
    for wf in GUARDED:
        hits = applies(changed, path_filters(Path(root) / wf))
        g = {"workflow": wf, "matched_files": hits[:20], "state": NA if not hits else WAIT}
        report["gates"].append(g)
        if hits:
            pending[wf] = g
    start = clock()
    while pending:
        for wf, g in list(pending.items()):
            g["state"] = verdict(head_runs(reader, wf, sha))
            if g["state"] != WAIT:
                pending.pop(wf)
        if not pending or clock() - start >= deadline_s:
            break
        sleep(poll_s)
    for g in pending.values():
        g["state"] = FAIL
        g["reason"] = "no terminal run on exact head before deadline"
    report["verdict"] = FAIL if any(g["state"] == FAIL for g in report["gates"]) else PASS
    return report


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    ap.add_argument("--pr", type=int, required=True)
    ap.add_argument("--sha", required=True)
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--deadline-min", type=float, default=75)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    if not re.fullmatch(r"[0-9a-f]{40}", a.sha):
        raise SystemExit("invalid head SHA")
    rep = evaluate(Reader(a.repo), a.root, a.pr, a.sha, a.deadline_min * 60)
    text = json.dumps(rep, indent=2, sort_keys=True)
    if a.out:
        a.out.write_text(text + "\n")
    print(text)
    for g in rep["gates"]:
        print(f"{g['workflow']}: {g['state']}" + (f" ({len(g['matched_files'])} matched)" if g["matched_files"] else ""))
    return 0 if rep["verdict"] == PASS else 1


if __name__ == "__main__":
    sys.exit(main())
