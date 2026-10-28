#!/usr/bin/env python3
"""Observe one JADE focus-five pulse: H01-H12 for the current rolling-5 window.

Read-only. For every repo in the current window (site/rolling5.json) it reads
the default-branch head SHA once (AGENTS.md L6) and evaluates each gate on that
exact SHA only, writing a snapshot in the FOCUS5 shape that rolling5.py pins:

  H01  PASS when the head SHA is read back.
  H02  PASS when a root README exists at that SHA.
  H04/H05/H06  the workflows declared for the gate in
       data/FOCUS5_GATE_EVIDENCE_REGISTRY.json (else the workflow that evidenced it
       in the previous pulse) are looked up on the new head: every one success ->
       PASS, any failure -> FAIL, otherwise (not run, cancelled, skipped) ->
       UNKNOWN. A gate with neither stays UNKNOWN.
  H08  FAIL when the default branch is unprotected; protected with a pull
       request rule -> UNKNOWN until a rejected RED canary is evidenced.
  H03 H07 H09 H10 H11 H12  owner or independent evidence -> UNKNOWN here; the
       observation (security runs, tags) is recorded, never promoted.

UNKNOWN is never PASS, and the snapshot grants no release credit.

  python tools/focus5_pulse.py --out data/FOCUS5_POINT_RELEASE_P0002.json --date 2026-10-25
  python tools/rolling5.py --append-pulse data/FOCUS5_POINT_RELEASE_P0002.json --pulse-id P0002
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_pb = importlib.util.spec_from_file_location("jade_private_boundary", ROOT / "tools" / "private_boundary.py")
PB = importlib.util.module_from_spec(_pb)
_pb.loader.exec_module(PB)
WINDOW = "site/rolling5.json"
LEDGER = "data/ROLLING5_PULSES.json"
REGISTRY = "data/FOCUS5_GATE_EVIDENCE_REGISTRY.json"
RUN_GATES = ("H04", "H05", "H06")
SECURITY_RX = re.compile(r"codeql|osv|bandit|security|scorecard|dependency.review|secret", re.I)
RUN_URL = re.compile(r"/actions/runs/(\d+)")


def gh(path: str) -> object:
    out = subprocess.run(["gh", "api", path], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def previous_snapshot(root: Path) -> dict:
    ledger = json.loads((root / LEDGER).read_text(encoding="utf-8"))
    return json.loads((root / ledger["pulses"][-1]["snapshot"]).read_text(encoding="utf-8"))


def evidence_workflows(prev_row: dict | None, repo: str, lookup=gh) -> dict[str, str]:
    """Gate -> workflow path that evidenced it in the previous pulse (from its run URL)."""
    out: dict[str, str] = {}
    for g in (prev_row or {}).get("gates", []):
        m = RUN_URL.search(str(g.get("evidence") or ""))
        if g["id"] in RUN_GATES and m:
            out[g["id"]] = lookup(f"repos/{repo}/actions/runs/{m.group(1)}")["path"]
    return out


def validate_registry(reg: dict) -> dict[str, dict[str, list[str]]]:
    """Repo -> gate -> declared workflow paths. Raises ValueError on a malformed registry."""
    if reg.get("schema") != "jade.focus5.gate_evidence_registry.v1":
        raise ValueError("unknown registry schema")
    out: dict[str, dict[str, list[str]]] = {}
    for repo, gates in reg["repos"].items():
        if repo.count("/") != 1:
            raise ValueError(f"{repo}: expected owner/name")
        for gid, entries in gates.items():
            if gid not in RUN_GATES:
                raise ValueError(f"{repo} {gid}: only {', '.join(RUN_GATES)} may be declared")
            paths = [e["workflow"] for e in entries]
            if not paths or len(set(paths)) != len(paths):
                raise ValueError(f"{repo} {gid}: empty or duplicate workflows")
            for e in entries:
                if not e["workflow"].startswith(".github/workflows/") or not e["workflow"].endswith((".yml", ".yaml")):
                    raise ValueError(f"{repo} {gid}: {e['workflow']} is not a workflow file")
                if not str(e.get("proves") or "").strip():
                    raise ValueError(f"{repo} {gid}: {e['workflow']} does not state what it proves")
            out.setdefault(repo, {})[gid] = paths
    return out


def load_registry(root: Path) -> dict[str, dict[str, list[str]]]:
    path = root / REGISTRY
    return validate_registry(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else {}


NOT_STARTED = "not_started"


def mark_unstarted_failures(repo: str, latest: dict[str, dict], paths, lookup=gh) -> None:
    """A failed run whose jobs never ran a step (no runner: billing, spending limit,
    runner outage) proves nothing about the code: its conclusion becomes not_started,
    which classifies as UNKNOWN, never FAIL or PASS."""
    for path in paths:
        run = latest.get(path)
        if run and run["conclusion"] == "failure":
            jobs = lookup(f"repos/{repo}/actions/runs/{run['id']}/jobs?per_page=100")["jobs"]
            if not any(j.get("steps") for j in jobs):
                latest[path] = dict(run, conclusion=NOT_STARTED)


def classify_run(conclusion: str | None) -> str:
    return {"success": "PASS", "failure": "FAIL"}.get(conclusion or "", "UNKNOWN")


def classify_gate(paths: list[str], latest: dict[str, dict]) -> tuple[str, str | None, str]:
    """All declared workflows must succeed on this SHA; any failure fails the gate."""
    runs = {p: latest.get(p) for p in paths}
    failed = [p for p, r in runs.items() if r and classify_run(r["conclusion"]) == "FAIL"]
    if failed:
        r = runs[failed[0]]
        return "FAIL", r["html_url"], f"{r['name']} failure on this exact SHA ({', '.join(failed)})"
    missing = [p for p, r in runs.items() if not r or classify_run(r["conclusion"]) != "PASS"]
    if missing:
        detail = ", ".join(f"{p}={runs[p]['conclusion']}" if runs[p] else f"{p} not completed" for p in missing)
        return "UNKNOWN", None, f"Declared evidence incomplete on this exact SHA: {detail}"
    first = runs[paths[0]]
    names = ", ".join(runs[p]["name"] for p in paths)
    return "PASS", first["html_url"], f"{names} success on this exact SHA"


def observe_repo(repo: str, prev_row: dict | None, lookup=gh, declared: dict[str, list[str]] | None = None) -> dict:
    meta = lookup(f"repos/{repo}")
    branch = meta["default_branch"]
    sha = lookup(f"repos/{repo}/commits/{branch}")["sha"]  # read once, used for every gate
    base = f"https://github.com/{repo}"
    gates: dict[str, dict] = {}

    def gate(gid: str, status: str, evidence: str | None, reason: str) -> None:
        gates[gid] = {"id": gid, "status": status, "evidence": evidence, "reason": reason}

    gate("H01", "PASS", f"{base}/commit/{sha}", "Default branch exact SHA read back in this pulse")
    root_files = {e["name"].lower() for e in lookup(f"repos/{repo}/contents?ref={sha}") if e.get("type") == "file"}
    readme = sorted(n for n in root_files if n.startswith("readme"))
    gate("H02", "PASS" if readme else "UNKNOWN", f"{base}/tree/{sha}" if readme else None,
         "Root README present at this SHA" if readme else "No root README at this SHA")
    gate("H03", "UNKNOWN", None, "Owner acceptance of release applicability not evidenced in this pulse")

    runs = lookup(f"repos/{repo}/actions/runs?head_sha={sha}&per_page=100")["workflow_runs"]
    latest: dict[str, dict] = {}
    for run in sorted(runs, key=lambda r: r["created_at"]):
        if run["status"] == "completed":
            latest[run["path"]] = run
    declared = declared or {}
    wf = evidence_workflows(prev_row, repo, lookup) if set(RUN_GATES) - set(declared) else {}
    evidence_paths = {p for ps in declared.values() for p in ps} | set(wf.values())
    mark_unstarted_failures(repo, latest, sorted(evidence_paths), lookup)
    for gid in RUN_GATES:
        if gid in declared:
            status, url, why = classify_gate(declared[gid], latest)
            gate(gid, status, url, why + " (declared in gate evidence registry)")
            continue
        path = wf.get(gid)
        run = latest.get(path) if path else None
        if run:
            gate(gid, classify_run(run["conclusion"]), run["html_url"],
                 f"{run['name']} {run['conclusion']} on this exact SHA (same workflow as previous pulse)")
        elif path:
            gate(gid, "UNKNOWN", None, f"{path} has not completed on this exact SHA")
        else:
            gate(gid, "UNKNOWN", None, "No workflow evidence for this gate in the previous pulse")

    security = sorted(f"{p}={r['conclusion']}" for p, r in latest.items() if SECURITY_RX.search(p + r["name"]))
    gate("H07", "UNKNOWN", None, "Not independently accepted; observed security runs on this SHA: "
         + (", ".join(security) if security else "none"))

    protected = lookup(f"repos/{repo}/branches/{branch}")["protected"]
    rules = sorted({r["type"] for r in lookup(f"repos/{repo}/rules/branches/{branch}")})
    if not protected and not rules:
        gate("H08", "FAIL", f"{base}/settings/branches", "Default branch unprotected (no protection, no ruleset)")
    elif "pull_request" in rules:
        gate("H08", "UNKNOWN", f"{base}/settings/rules",
             "Pull request rule active (" + ", ".join(rules) + "); rejected RED canary not evidenced in this pulse")
    else:
        gate("H08", "UNKNOWN", f"{base}/settings/branches",
             "Protected without a pull request rule (" + (", ".join(rules) or "classic protection") + ")")
    for gid, text in (("H09", "Eligible independent human approval not evidenced in this pulse"),
                      ("H10", "Matched coverage and negative tests not evidenced in this pulse"),
                      ("H11", "Source-bound artifact QA and hashes not evidenced in this pulse")):
        gate(gid, "UNKNOWN", None, text)
    tags = lookup(f"repos/{repo}/tags?per_page=100")
    on_head = sorted(t["name"] for t in tags if t["commit"]["sha"] == sha)
    gate("H12", "UNKNOWN", None, "Owner release tag, assets and rollback not signed in this pulse; tags on this SHA: "
         + (", ".join(on_head) if on_head else "none"))

    ordered = [gates[f"H{i:02d}"] for i in range(1, 13)]
    counts = {s: sum(1 for g in ordered if g["status"] == s) for s in ("PASS", "FAIL", "UNKNOWN")}
    row = dict(prev_row or {})
    # Owner-authored text from the previous pulse is not re-observed: blockers are
    # re-derived from this pulse's FAIL gates, and a candidate branch is kept only if
    # it still exists at the same SHA.
    row["blockers"] = [f"{g['id']}: {g['reason']}" for g in gates.values() if g["status"] == "FAIL"]
    cand = row.get("candidate_branch")
    if cand:
        try:
            still = lookup(f"repos/{repo}/branches/{cand}")["commit"]["sha"] == row.get("candidate_sha")
        except subprocess.CalledProcessError:
            still = False
        if not still:
            row["candidate_branch"] = row["candidate_sha"] = None
    row["owner_action"] = None  # owner text is not re-observed by this tool
    row.update({
        "repo": repo, "name": repo.split("/", 1)[1], "default_branch": branch, "source_sha": sha,
        "gate_denominator": 12, "verified_complete": counts["PASS"], "verified_failed": counts["FAIL"],
        "unqualified": counts["UNKNOWN"], "percent": round(100 * counts["PASS"] / 12, 2), "gates": ordered,
        "release": "HOLD", "native_observations": [
            {"source_sha": sha, "run_id": r["id"], "workflow_name": r["name"], "conclusion": r["conclusion"],
             "evidence_url": r["html_url"]} for r in sorted(latest.values(), key=lambda r: r["path"])],
    })
    row["head_readback"] = None  # set by build_snapshot for the whole pulse
    return row


def build_snapshot(prev: dict, repos: list[str], date: str, lookup=gh,
                   registry: dict[str, dict[str, list[str]]] | None = None) -> dict:
    prev_rows = {r["repo"]: r for r in prev["rows"]}
    registry = registry or {}
    rows = [observe_repo(repo, prev_rows.get(repo), lookup, registry.get(repo)) for repo in repos]
    for row in rows:
        row["head_readback"] = f"{date} one pulse"
    passed = sum(r["verified_complete"] for r in rows)
    failed = sum(r["verified_failed"] for r in rows)
    total = 12 * len(rows)
    snap = {k: v for k, v in prev.items() if k not in ("rows", "metrics", "source")}
    snap["source"] = dict(prev["source"], observed_date=date, readback="ONE_PULSE_GITHUB_API",
                          release_authority_transfer=False)
    snap["metrics"] = dict(prev["metrics"], required_gate_total=total, passed=passed, failed=failed,
                           unknown=total - passed - failed, verified_completion_pct=round(100 * passed / total, 2),
                           globally_admitted_point_release=None)
    snap["rows"] = rows
    return PB.project(snap)  # private repos: counts and statuses only


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--date", required=True, help="observation date (YYYY-MM-DD)")
    args = ap.parse_args(argv)
    window = json.loads((ROOT / WINDOW).read_text(encoding="utf-8"))["window"]["current"]
    snap = build_snapshot(previous_snapshot(ROOT), window, args.date, registry=load_registry(ROOT))
    out = ROOT / args.out
    out.write_text(json.dumps(snap, indent=2) + "\n", encoding="utf-8", newline="\n")
    m = snap["metrics"]
    print(f"FOCUS5 pulse {args.date}: {m['passed']} PASS / {m['failed']} FAIL / {m['unknown']} UNKNOWN of {m['required_gate_total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
