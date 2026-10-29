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

Each gate's verdict comes from its LATEST run on the head (by start time, so a re-run beats
an older run), and the deciding run is linked in the error line and the job summary; the
full JSON report goes only to --out.

The aggregator makes read-only GETs. `recheck` (driven by gogreen-required-gate-recheck.yml
on `workflow_run: completed` of the enforced gates) makes the one write: it re-runs the latest
FAILED aggregator run on the same head SHA, so a re-run gate turns this check green on its
own. `recheck-names` prints/writes the workflow names that trigger it (kept in sync by a test).
Requiring THIS single check is the owner's branch-protection decision.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import zipfile
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

GUARDED = (".github/workflows/code-purple-method-atlas.yml", ".github/workflows/live-lossless-qa.yml")
SELF = ".github/workflows/gogreen-required-gate.yml"
RECHECK = ".github/workflows/gogreen-required-gate-recheck.yml"
RECHECK_BEGIN, RECHECK_END = "# BEGIN recheck-names", "# END recheck-names"
RECHECK_MAX_ATTEMPT = 10  # never re-run an aggregator run that already has this many attempts
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
    import yaml  # lazy: `recheck` runs on the bare runner python without third-party installs
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


def run_order(r: dict) -> tuple:
    """Latest = started last. A re-run keeps its run id and created_at but gets a new
    run_started_at, so it beats an older run; created_at, attempt and id only break ties."""
    created = r.get("created_at") or ""
    return (r.get("run_started_at") or created, created, r.get("run_attempt") or 0, r.get("id") or 0)


def latest_run(runs: list) -> dict | None:
    return max(runs, key=run_order) if runs else None


def verdict(runs: list) -> str:
    """runs = this workflow's pull_request runs on the exact head SHA (any attempts)."""
    latest = latest_run(runs)
    if latest is None or latest.get("status") != "completed":
        return WAIT
    return PASS if latest.get("conclusion") == "success" else FAIL


def run_ref(run: dict | None, repo: str) -> dict | None:
    """The deciding run, small enough for an error line: id, attempt, outcome and a link
    to that exact attempt."""
    if not run:
        return None
    rid, attempt = run.get("id"), run.get("run_attempt")
    url = run.get("html_url") or (f"https://github.com/{repo}/actions/runs/{rid}" if rid else None)
    if url and attempt:
        url = f"{url}/attempts/{int(attempt)}"
    return {"id": rid, "attempt": attempt, "status": run.get("status"), "conclusion": run.get("conclusion"),
            "started_at": run.get("run_started_at") or run.get("created_at"), "url": url}


class Reader:
    def __init__(self, repo, token=None, opener=None):
        self.repo, self.token = repo, token if token is not None else os.environ.get("GITHUB_TOKEN", "")
        self.opener = opener or urllib.request.urlopen
        self.requests = 0

    def _headers(self):
        h = {"Accept": "application/vnd.github+json", "User-Agent": "gogreen-required-gate/2"}
        if self.token:
            h["Authorization"] = "Bearer " + self.token
        return h

    def get(self, path):
        if not path.startswith(f"/repos/{self.repo}/") or ".." in path.split("?")[0].split("/"):
            raise ValueError("unapproved read path")
        self.requests += 1
        with self.opener(urllib.request.Request("https://api.github.com" + path, headers=self._headers()),
                         timeout=20) as r:
            return json.load(r)

    def rerun(self, run_id) -> None:
        """The only write: re-run one workflow run (recheck). No other POST path exists."""
        path = f"/repos/{self.repo}/actions/runs/{int(run_id)}/rerun"
        self.requests += 1
        req = urllib.request.Request("https://api.github.com" + path, data=b"{}", method="POST",
                                     headers=dict(self._headers(), **{"Content-Type": "application/json"}))
        with self.opener(req, timeout=20) as r:
            r.read()


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
        return policy_from_doc(json.loads((Path(root) / ADMISSION).read_text(encoding="utf-8")), "head:" + ADMISSION)
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
    universe = sorted(f.relative_to(root).as_posix() for f in list(wdir.glob("*.yml")) + list(wdir.glob("*.yaml")))
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
    # Every applicable enforced gate is re-read on every poll, not only the pending ones: a
    # gate that failed and is re-run while we wait goes back to WAITING and its new run decides.
    applicable = [g for g in report["gates"] if g["state"] == WAIT]
    watched = [g for g in report["observed"] if g["state"] == WAIT]
    start, by = clock(), {}
    while True:
        by = head_runs_by_workflow(reader, sha)
        for g in applicable:
            runs = by.get(g["workflow"], [])
            g["state"], g["run"] = verdict(runs), run_ref(latest_run(runs), reader.repo)
        if not any(g["state"] == WAIT for g in applicable) or clock() - start >= deadline_s:
            break
        sleep(poll_s)
    for g in applicable:
        if g["state"] == WAIT:
            g["state"] = FAIL
            g["reason"] = "no terminal run on exact head before deadline"
    for g in watched:  # snapshot only: observed gates never extend the wait or block
        runs = by.get(g["workflow"], [])
        g["state"], g["run"] = verdict(runs), run_ref(latest_run(runs), reader.repo)
    report["coverage"] = {
        "workflows_in_head": len(universe),
        "enforced": len(report["gates"]), "enforced_applicable": sum(bool(g["matched_files"]) for g in report["gates"]),
        "observed": len(report["observed"]), "observed_applicable": len(watched),
        "excluded": len(report["excluded"]), "unlisted": sum(bool(g.get("unlisted")) for g in report["observed"])}
    report["verdict"] = FAIL if any(g["state"] == FAIL for g in report["gates"]) else PASS
    return report


def run_link(ref: dict | None) -> str:
    """Markdown link to the deciding run attempt, or an em dash when there is none."""
    if not ref or not ref.get("url"):
        return "—"
    label = f"run {ref['id']}" + (f" attempt {ref['attempt']}" if ref.get("attempt") else "")
    return f"[{label}]({ref['url']})"


def fail_line(g: dict) -> str:
    """One `::error` annotation per failing enforced gate: name, why, and the link."""
    ref = g.get("run") or {}
    why = g.get("reason") or ref.get("conclusion") or ""
    tail = " — ".join(x for x in (why, ref.get("url") or "") if x)
    return f"::error title=GOGREEN enforced gate {g['state']}::{g.get('name') or g['workflow']}" + (
        f" — {tail}" if tail else "")


def summary_markdown(rep: dict) -> str:
    c = rep["coverage"]
    lines = [f"### GOGREEN required gate: **{rep['verdict']}**",
             f"Policy: `{rep['policy_source']}` · {rep['changed_files']} changed file(s) · "
             f"{c['workflows_in_head']} workflows: {c['enforced']} enforced ({c['enforced_applicable']} applicable), "
             f"{c['observed']} observed ({c['observed_applicable']} applicable, {c['unlisted']} unlisted), "
             f"{c['excluded']} excluded.", "", "| Disposition | Workflow | State | Matched | Deciding run |",
             "|---|---|---|---:|---|"]
    for g in rep["gates"] + rep["observed"]:
        if g["matched_files"] or g["disposition"] == ENFORCED:
            lines.append(f"| {g['disposition']}{' (unlisted)' if g.get('unlisted') else ''} | "
                         f"{g.get('name') or g['workflow']} | {g['state']} | {len(g['matched_files'])} | "
                         f"{run_link(g.get('run'))} |")
    lines += ["", "_Only ENFORCED rows decide the verdict. `merge_authorized=false`: a PASS is one observation, "
              "not an admission._"]
    return "\n".join(lines) + "\n"


def recheck_names(root: Path, policy: dict) -> list:
    """Workflow names (what `workflow_run.workflows` matches) of the ENFORCED gates that can
    run on a PR. GitHub names an unnamed workflow by its file path."""
    names = set()
    for rel in sorted(p for p, d in policy["entries"].items() if d == ENFORCED and p not in (SELF, RECHECK)):
        f = Path(root) / rel
        if f.is_file():
            t = triggers(f)
            if t.get("pull_request"):
                names.add(str(t.get("name") or rel))
    return sorted(names)


def declared_recheck_names(text: str) -> list:
    """The generated list between the markers of the recheck workflow (one quoted name per line)."""
    lines = text.splitlines()
    try:
        a = next(i for i, x in enumerate(lines) if x.strip() == RECHECK_BEGIN)
        b = next(i for i, x in enumerate(lines) if x.strip() == RECHECK_END and i > a)
    except StopIteration:
        raise ValueError(f"{RECHECK}: missing {RECHECK_BEGIN!r} / {RECHECK_END!r} markers") from None
    out = []
    for x in lines[a + 1:b]:
        s = x.strip()
        if not s.startswith("- "):
            raise ValueError(f"{RECHECK}: unexpected line inside the generated block: {s[:80]!r}")
        out.append(json.loads(s[2:]))
    return out


def render_recheck_names(text: str, names: list) -> str:
    """Rewrite only the generated block; every other byte of the workflow is kept."""
    lines = text.splitlines(keepends=True)
    a = next(i for i, x in enumerate(lines) if x.strip() == RECHECK_BEGIN)
    b = next(i for i, x in enumerate(lines) if x.strip() == RECHECK_END and i > a)
    indent = lines[a][:len(lines[a]) - len(lines[a].lstrip())]
    body = [f"{indent}- {json.dumps(n, ensure_ascii=False)}\n" for n in names]
    return "".join(lines[:a + 1] + body + lines[b:])



# A *receipt-derived proposal*, deliberately separate from live retry authority.
# The privileged workflow does not yet download or trust unverified PR-run artifacts.
RECHECK_ELIGIBLE = "RECHECK_ELIGIBLE"
RECHECK_ALREADY_SATISFIED = "ALREADY_SATISFIED"
RECHECK_UNKNOWN = "UNKNOWN"


def receipt_recheck_relevance(report: dict, *, sha: str, workflow_path: str) -> dict:
    """Classify whether a matching failed aggregator receipt implicates one workflow.

    This is advisory and has NO write path. A future consumer must independently bind
    artifact bytes to the exact aggregator run, attempt, repository, PR and head SHA,
    and validate its digest before it may use ALREADY_SATISFIED to suppress work.
    UNKNOWN deliberately cannot suppress a re-check.
    """
    out = {"schema": "gogreen.required_gate.receipt_relevance.v1",
           "head_sha": sha, "workflow": workflow_path,
           "decision": RECHECK_UNKNOWN, "merge_authorized": False}
    if not re.fullmatch(r"[0-9a-f]{40}", sha or ""):
        out["reason"] = "invalid exact head SHA"
        return out
    if not isinstance(report, dict) or report.get("schema") != "gogreen.required_gate.v2":
        out["reason"] = "missing or unrecognized aggregator report"
        return out
    if report.get("head_sha") != sha or report.get("merge_authorized") is not False:
        out["reason"] = "report source/authority binding mismatch"
        return out
    if report.get("verdict") != FAIL:
        out["reason"] = "report is not a failed aggregator observation"
        return out
    if not isinstance(workflow_path, str) or not re.fullmatch(
            r"\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml", workflow_path):
        out["reason"] = "invalid or ambiguous workflow path"
        return out
    gates = report.get("gates")
    if not isinstance(gates, list) or any(not isinstance(g, dict) for g in gates):
        out["reason"] = "missing or malformed enforced-gate population"
        return out
    matches = [g for g in gates if g.get("workflow") == workflow_path]
    if len(matches) != 1:
        out["reason"] = "enforced workflow absent or duplicated in receipt"
        return out
    state = matches[0].get("state")
    if state in (FAIL, WAIT):
        out["decision"] = RECHECK_ELIGIBLE
        out["reason"] = "the original failed report still requires this gate to be re-read"
    elif state in (PASS, NA):
        out["decision"] = RECHECK_ALREADY_SATISFIED
        out["reason"] = "this gate did not contribute to the original failed verdict"
    else:
        out["reason"] = "unknown prior enforced gate state"
    return out


def main_recheck_receipt(argv) -> int:
    """Offline, non-authoritative preflight for an already downloaded JSON receipt."""
    ap = argparse.ArgumentParser(prog="gate.py recheck-receipt")
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--sha", required=True)
    ap.add_argument("--workflow", required=True)
    a = ap.parse_args(argv)
    result = receipt_recheck_relevance(
        json.loads(a.report.read_text(encoding="utf-8")),
        sha=a.sha, workflow_path=a.workflow)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["decision"] != RECHECK_UNKNOWN else 2


def recheck(reader, sha: str, conclusion: str = "success", dry_run: bool = False) -> dict:
    """Re-run the latest FAILED aggregator run on `sha` after an enforced gate succeeded there.
    Nothing happens when the gate did not succeed, the aggregator never ran on this head, is
    still running (it re-reads every poll), already passed, or hit RECHECK_MAX_ATTEMPT."""
    if not re.fullmatch(r"[0-9a-f]{40}", sha or ""):
        raise ValueError("invalid head SHA")
    out = {"schema": "gogreen.required_gate.recheck.v1", "head_sha": sha, "action": "none",
           "trigger_conclusion": conclusion, "aggregator_run": None}
    if conclusion != "success":
        out["reason"] = f"triggering gate concluded {conclusion}; a re-run aggregator would stay red"
        return out
    wf = SELF.rsplit("/", 1)[1]
    data = reader.get(f"/repos/{reader.repo}/actions/workflows/{wf}/runs"
                      f"?head_sha={sha}&event=pull_request&per_page=100")
    run = latest_run(data.get("workflow_runs") or [])
    out["aggregator_run"] = run_ref(run, reader.repo)
    if run is None:
        out["reason"] = "no aggregator run on this head"
    elif run.get("status") != "completed":
        out["reason"] = "latest aggregator run is still in progress; it re-reads every poll"
    elif run.get("conclusion") != "failure":
        out["reason"] = f"latest aggregator run concluded {run.get('conclusion')}; nothing to re-run"
    elif (run.get("run_attempt") or 1) >= RECHECK_MAX_ATTEMPT:
        out["reason"] = f"latest aggregator run is at attempt {run.get('run_attempt')} (cap {RECHECK_MAX_ATTEMPT})"
    else:
        if not dry_run:
            reader.rerun(run["id"])
        out["action"] = "dry-run" if dry_run else "rerun"
        out["reason"] = "latest aggregator run failed; re-run so it re-reads the gates on this head"
    return out


def main_recheck(argv) -> int:
    ap = argparse.ArgumentParser(prog="gate.py recheck")
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    ap.add_argument("--sha", required=True, help="head SHA of the gate run that completed")
    ap.add_argument("--conclusion", default="success", help="conclusion of the gate run that completed")
    ap.add_argument("--dry-run", action="store_true", help="decide, but do not re-run")
    a = ap.parse_args(argv)
    if not a.repo:
        raise SystemExit("--repo or GITHUB_REPOSITORY is required")
    reader = Reader(a.repo)
    out = recheck(reader, a.sha, a.conclusion, a.dry_run)
    ref = out["aggregator_run"]
    line = f"recheck {out['action']}: {out['reason']}" + (f" ({ref['url']})" if ref and ref.get("url") else "")
    print(line)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8", newline="\n") as fh:
            fh.write(f"### GOGREEN required gate re-check: **{out['action']}**\n"
                     f"Head `{a.sha}` · {out['reason']} · aggregator {run_link(ref)}\n")
    return 0


def main_recheck_names(argv) -> int:
    ap = argparse.ArgumentParser(prog="gate.py recheck-names")
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--policy", choices=("head", "bootstrap"), default="head")
    ap.add_argument("--write", action="store_true", help=f"rewrite the generated block in {RECHECK}")
    ap.add_argument("--check", action="store_true", help=f"exit 1 when {RECHECK} is out of sync")
    a = ap.parse_args(argv)
    names = recheck_names(a.root, load_policy(None, None, a.root, a.policy))
    wf = a.root / RECHECK
    if a.write:
        text = wf.read_text(encoding="utf-8")
        wf.write_text(render_recheck_names(text, names), encoding="utf-8", newline="\n")
    if a.check and declared_recheck_names(wf.read_text(encoding="utf-8")) != names:
        print(f"{RECHECK} is out of sync; run: python mission-control/gogreen/required_gate/gate.py "
              "recheck-names --write",
              file=sys.stderr)
        return 1
    print("\n".join(names))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["recheck"]:
        return main_recheck(argv[1:])
    if argv[:1] == ["recheck-names"]:
        return main_recheck_names(argv[1:])
    if argv[:1] == ["recheck-receipt"]:
        return main_recheck_receipt(argv[1:])
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
    if a.out:  # the full report lives in --out (uploaded as an artifact), not in the log
        a.out.write_text(text + "\n", encoding="utf-8", newline="\n")
        print(f"full report: {a.out}")
    else:
        print(text)
    for g in rep["gates"]:
        url = (g.get("run") or {}).get("url")
        print(f"{g['workflow']}: {g['state']}" + (f" ({len(g['matched_files'])} matched)" if g["matched_files"] else "")
              + (f" {url}" if url else ""))
        if g["state"] == FAIL:
            print(fail_line(g))
    for g in rep["observed"]:
        if g["state"] == FAIL and g["matched_files"]:
            url = (g.get("run") or {}).get("url")
            print(f"::warning title=GOGREEN observed (not blocking) {g['state']}::{g.get('name') or g['workflow']}"
                  + (f" — {url}" if url else ""))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8", newline="\n") as fh:
            fh.write(summary_markdown(rep))
    return 0 if rep["verdict"] == PASS else 1


if __name__ == "__main__":
    sys.exit(main())
