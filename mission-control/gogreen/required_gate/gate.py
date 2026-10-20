#!/usr/bin/env python3
"""GOGREEN required gate: one always-reporting check for the path-filtered PR gates.

Problem: most PR gates here only run on PRs touching their `paths`. Marking one required
on master would leave every other PR waiting forever for a check that never reports. This
gate runs on every PR and, for each workflow the admission ledger ENFORCES:

  * reads that workflow's own pull_request trigger (paths / paths-ignore / branches /
    types) from the PR-head checkout: single source of truth, no copied path lists;
  * NOT_APPLICABLE if the trigger would not fire for this PR -> pass;
  * otherwise waits for its run on the exact PR head SHA and passes only on `success`;
    failure / cancelled / timed_out / absent-after-deadline -> fail closed.

Control spine (N+9): telemetry (red_trace, both lanes) -> trust (admission.py) ->
authority (ADMISSION.json, read from the BASE branch, so a PR cannot demote the gates that
judge it) -> gate (this file). OBSERVED workflows are reported and annotated, never
blocking; EXCLUDED ones are listed with their reason; a workflow missing from the ledger is
reported as UNLISTED (observed), never silently omitted. Until ADMISSION.json exists on the
base branch the bootstrap policy is the two N+8 incumbents.

Read-only GETs. Requiring THIS single check is the owner's branch-protection decision.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import yaml

GUARDED = (".github/workflows/code-purple-method-atlas.yml", ".github/workflows/live-lossless-qa.yml")
SELF = ".github/workflows/gogreen-required-gate.yml"
ADMISSION = "mission-control/gogreen/required_gate/ADMISSION.json"
ADMISSION_SCHEMA = "gogreen.required_gate.admission.v1"
PASS, FAIL, NA, WAIT = "PASS", "FAIL", "NOT_APPLICABLE", "WAITING"
ENFORCED, OBSERVED, EXCLUDED = "ENFORCED", "OBSERVED", "EXCLUDED"
DEFAULT_TYPES = {"opened", "synchronize", "reopened"}


def glob_to_regex(pattern: str) -> re.Pattern:
    """GitHub Actions filter glob: ** spans '/', * and ? do not."""
    out, i = "", 0
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"; i += 3; continue
        if pattern.startswith("**", i):
            out += ".*"; i += 2; continue
        out += {"*": "[^/]*", "?": "[^/]"}.get(c, re.escape(c)); i += 1
    return re.compile(out + r"\Z")


def ordered_match(value: str, patterns: list) -> bool:
    """GitHub filter semantics: patterns are evaluated in order; a later `!pattern` match
    excludes, a later positive match re-includes."""
    included = False
    for p in patterns:
        neg = p.startswith("!")
        if glob_to_regex(p[1:] if neg else p).match(value):
            included = not neg
    return included


def triggers(workflow_file: Path) -> dict:
    """Pull-request trigger semantics of one workflow, read from its own YAML."""
    try:
        data = yaml.safe_load(Path(workflow_file).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        return {"pull_request": False, "pull_request_target": False, "parse_error": str(e)[:200]}
    if not isinstance(data, dict):
        return {"pull_request": False, "pull_request_target": False, "parse_error": "workflow is not a mapping"}
    on = data.get(True, data.get("on"))
    if isinstance(on, str):
        on = {on: None}
    elif isinstance(on, list):
        on = {k: None for k in on}
    elif not isinstance(on, dict):
        on = {}
    cfg = on.get("pull_request") or {}
    cfg = cfg if isinstance(cfg, dict) else {}
    lst = lambda k: [str(x) for x in cfg[k]] if isinstance(cfg.get(k), list) and cfg.get(k) else None
    return {"name": data.get("name"), "pull_request": "pull_request" in on,
            "pull_request_target": "pull_request_target" in on,
            "paths": lst("paths"), "paths_ignore": lst("paths-ignore"),
            "branches": lst("branches"), "branches_ignore": lst("branches-ignore"), "types": lst("types")}


def path_filters(workflow_file: Path) -> list | None:
    """pull_request.paths of a workflow; None = no paths filter (runs on every PR)."""
    t = triggers(workflow_file)
    if t.get("parse_error") or not t["pull_request"]:
        raise ValueError(f"{workflow_file}: no pull_request trigger; cannot be gated per PR")
    return t["paths"]


def applies(changed: list, filters: list | None, ignore: list | None = None) -> list:
    """Changed files that make the workflow fire. paths: any file matching (ordered `!`);
    paths-ignore: fires unless every changed file is ignored; neither: always fires."""
    if filters is None and ignore:
        return [f for f in changed if not ordered_match(f, ignore)]
    if filters is None:
        return list(changed) or ["<no paths filter>"]
    return [f for f in changed if ordered_match(f, filters)]


def fires_for_base(t: dict, base_ref: str | None) -> str | None:
    """Reason the trigger cannot fire for a PR into base_ref (None = it can)."""
    if t.get("parse_error"):
        return "workflow YAML does not parse"
    if not t.get("pull_request"):
        return "no pull_request trigger"
    if t.get("types") and not ({"opened", "synchronize"} <= set(t["types"])):
        return f"pull_request types {t['types']} do not cover every new head"
    if base_ref is not None:
        if t.get("branches") and not ordered_match(base_ref, t["branches"]):
            return f"base {base_ref} not in branches filter"
        if t.get("branches_ignore") and ordered_match(base_ref, t["branches_ignore"]):
            return f"base {base_ref} in branches-ignore"
    return None


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
        self.requests = 0

    def get(self, path):
        if not path.startswith(f"/repos/{self.repo}/") or ".." in path.split("?")[0].split("/"):
            raise ValueError("unapproved read path")
        h = {"Accept": "application/vnd.github+json", "User-Agent": "gogreen-required-gate/2"}
        if self.token:
            h["Authorization"] = "Bearer " + self.token
        self.requests += 1
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


def head_runs_by_workflow(reader, sha) -> dict:
    """All pull_request runs on the exact head, grouped by workflow path: ONE paginated
    listing per poll, however many gates are watched (N+8 made one call per gate)."""
    runs, page = [], 1
    while True:
        data = reader.get(f"/repos/{reader.repo}/actions/runs?head_sha={sha}&event=pull_request&per_page=100&page={page}")
        batch = data.get("workflow_runs") or []
        runs += batch
        total = data.get("total_count")
        if len(batch) < 100 or (isinstance(total, int) and len(runs) >= total) or page >= 10:
            break
        page += 1
    by = {}
    for r in runs:
        if r.get("path"):
            by.setdefault(r["path"].split("@")[0], []).append(r)
    return by


def bootstrap_policy() -> dict:
    return {"source": "bootstrap:n8-incumbents", "entries": {wf: ENFORCED for wf in GUARDED}, "reasons": {}}


def policy_from_doc(doc: dict, source: str) -> dict:
    if not isinstance(doc, dict) or doc.get("schema") != ADMISSION_SCHEMA or not isinstance(doc.get("entries"), list):
        raise ValueError(f"{source}: not a {ADMISSION_SCHEMA} ledger")
    entries, reasons = {}, {}
    for e in doc["entries"]:
        if e.get("disposition") not in (ENFORCED, OBSERVED, EXCLUDED) or not e.get("path"):
            raise ValueError(f"{source}: illegal entry {e!r:.120}")
        entries[e["path"]] = e["disposition"]
        reasons[e["path"]] = e.get("reasons", [])
    return {"source": source, "entries": entries, "reasons": reasons}


def load_policy(reader, base_sha: str | None, root: Path, mode: str) -> dict:
    """base: ADMISSION.json as committed on the base SHA (a PR cannot weaken the gates that
    judge it); head: from the checkout (offline/testing); bootstrap: the N+8 incumbents.
    A base without the ledger yet falls back to bootstrap, which is reported."""
    if mode == "bootstrap":
        return bootstrap_policy()
    if mode == "head":
        return policy_from_doc(json.loads((Path(root) / ADMISSION).read_text()), "head:" + ADMISSION)
    if not base_sha or not re.fullmatch(r"[0-9a-f]{40}", base_sha):
        raise ValueError("base policy needs the exact base SHA")
    try:
        data = reader.get(f"/repos/{reader.repo}/contents/{ADMISSION}?ref={base_sha}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            p = bootstrap_policy()
            p["source"] += f" (no ledger at base {base_sha[:12]})"
            return p
        raise
    raw = base64.b64decode(data.get("content") or "")
    return policy_from_doc(json.loads(raw), f"base@{base_sha}:{ADMISSION}")


def evaluate(reader, root, pr, sha, deadline_s, poll_s=30, clock=time.monotonic, sleep=time.sleep,
             policy=None, base_ref=None):
    policy = policy or bootstrap_policy()
    changed = changed_files(reader, pr)
    report = {"schema": "gogreen.required_gate.v2", "pr": pr, "head_sha": sha, "base_ref": base_ref,
              "policy_source": policy["source"], "changed_files": len(changed),
              "gates": [], "observed": [], "excluded": [], "merge_authorized": False}
    wdir = Path(root) / ".github" / "workflows"
    universe = sorted(str(f.relative_to(root)) for f in list(wdir.glob("*.yml")) + list(wdir.glob("*.yaml")))
    for rel in universe:
        disp = policy["entries"].get(rel)
        if rel == SELF:  # deadlock invariant: the gate never waits for itself, whatever the ledger says
            report["excluded"].append({"workflow": rel, "reasons": ["SELF"]})
            continue
        if disp == EXCLUDED:
            report["excluded"].append({"workflow": rel, "reasons": policy["reasons"].get(rel, [])})
            continue
        t = triggers(Path(root) / rel)
        g = {"workflow": rel, "name": t.get("name"), "disposition": disp or OBSERVED, "matched_files": []}
        if disp is None:
            g["unlisted"] = True
        why = fires_for_base(t, base_ref)
        if why:
            g.update(state=NA, reason=why)
        else:
            g["matched_files"] = applies(changed, t["paths"], t["paths_ignore"])[:20]
            g["state"] = WAIT if g["matched_files"] else NA
        (report["gates"] if disp == ENFORCED else report["observed"]).append(g)
    for wf in sorted(p for p, d in policy["entries"].items() if d == ENFORCED and p not in universe):
        report["gates"].append({"workflow": wf, "disposition": ENFORCED, "matched_files": [], "state": NA,
                                "reason": "workflow file absent in PR head"})
    pending = {g["workflow"]: g for g in report["gates"] if g["state"] == WAIT}
    watched = [g for g in report["observed"] if g["state"] == WAIT]
    start, by = clock(), {}
    while True:
        by = head_runs_by_workflow(reader, sha)
        for wf, g in list(pending.items()):
            g["state"] = verdict(by.get(wf, []))
            if g["state"] != WAIT:
                pending.pop(wf)
        if not pending or clock() - start >= deadline_s:
            break
        sleep(poll_s)
    for g in pending.values():
        g["state"] = FAIL
        g["reason"] = "no terminal run on exact head before deadline"
    for g in watched:  # snapshot only: observed gates never extend the wait or block
        g["state"] = verdict(by.get(g["workflow"], []))
    report["coverage"] = {
        "workflows_in_head": len(universe),
        "enforced": len(report["gates"]), "enforced_applicable": sum(bool(g["matched_files"]) for g in report["gates"]),
        "observed": len(report["observed"]), "observed_applicable": len(watched),
        "excluded": len(report["excluded"]), "unlisted": sum(bool(g.get("unlisted")) for g in report["observed"])}
    report["verdict"] = FAIL if any(g["state"] == FAIL for g in report["gates"]) else PASS
    return report


def summary_markdown(rep: dict) -> str:
    c = rep["coverage"]
    lines = [f"### GOGREEN required gate: **{rep['verdict']}**",
             f"Policy: `{rep['policy_source']}` · {rep['changed_files']} changed file(s) · "
             f"{c['workflows_in_head']} workflows: {c['enforced']} enforced ({c['enforced_applicable']} applicable), "
             f"{c['observed']} observed ({c['observed_applicable']} applicable, {c['unlisted']} unlisted), "
             f"{c['excluded']} excluded.", "", "| Disposition | Workflow | State | Matched |", "|---|---|---|---:|"]
    for g in rep["gates"] + rep["observed"]:
        if g["matched_files"] or g["disposition"] == ENFORCED:
            lines.append(f"| {g['disposition']}{' (unlisted)' if g.get('unlisted') else ''} | "
                         f"{g.get('name') or g['workflow']} | {g['state']} | {len(g['matched_files'])} |")
    lines += ["", "_Only ENFORCED rows decide the verdict. `merge_authorized=false`: a PASS is one observation, "
              "not an admission._"]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    ap.add_argument("--pr", type=int, required=True)
    ap.add_argument("--sha", required=True)
    ap.add_argument("--base-ref")
    ap.add_argument("--base-sha")
    ap.add_argument("--policy", choices=("base", "head", "bootstrap"), default=None,
                    help="default: base when --base-sha is given, else bootstrap")
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--deadline-min", type=float, default=75)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    if not re.fullmatch(r"[0-9a-f]{40}", a.sha):
        raise SystemExit("invalid head SHA")
    reader = Reader(a.repo)
    policy = load_policy(reader, a.base_sha, a.root, a.policy or ("base" if a.base_sha else "bootstrap"))
    rep = evaluate(reader, a.root, a.pr, a.sha, a.deadline_min * 60, policy=policy, base_ref=a.base_ref)
    rep["requests"] = reader.requests
    text = json.dumps(rep, indent=2, sort_keys=True)
    if a.out:
        a.out.write_text(text + "\n")
    print(text)
    for g in rep["gates"]:
        print(f"{g['workflow']}: {g['state']}" + (f" ({len(g['matched_files'])} matched)" if g["matched_files"] else ""))
        if g["state"] == FAIL:
            print(f"::error title=GOGREEN enforced gate {g['state']}::{g.get('name') or g['workflow']}"
                  f"{' — ' + g['reason'] if g.get('reason') else ''}")
    for g in rep["observed"]:
        if g["state"] == FAIL and g["matched_files"]:
            print(f"::warning title=GOGREEN observed (not blocking) {g['state']}::{g.get('name') or g['workflow']}")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write(summary_markdown(rep))
    return 0 if rep["verdict"] == PASS else 1


if __name__ == "__main__":
    sys.exit(main())
