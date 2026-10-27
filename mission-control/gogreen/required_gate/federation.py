#!/usr/bin/env python3
"""GOGREEN federation spine (N+11): the hub's control spine replayed over every core repo.

No new measurement: for each repository it composes, unchanged,
    red_trace (master + merged-PR lanes) -> admission.build() -> backtest.run() -> depth.build()
and rolls the results into one federation view with explicit denominators.

Per repo the ledger is a PROPOSAL (`proposed_admission`): only the hub has a required gate
today, so nothing here is enforced anywhere. A repo whose telemetry could not be read is
listed DEFERRED with the reason (e.g. private repo, no cross-repo credential), never dropped
and never counted green.

Input: --spec JSON list of {"repo", "branch", "root", "trace_dir"} (trace_dir holds the
red_trace.json / red_trace_pr.json produced by red_trace.py for that repo; null = DEFERRED).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import admission as adm  # noqa: E402
import backtest as bt  # noqa: E402
import depth as dp  # noqa: E402
import gate as g  # noqa: E402

SCHEMA = "gogreen.federation_spine.v1"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8")) if p and Path(p).exists() else None


def repo_row(spec: dict, files_by_pr: dict | None, limit: int, audit_fn=dp.load_audit) -> dict:
    row = {"repo": spec["repo"], "branch": spec.get("branch", "main")}
    tdir = spec.get("trace_dir")
    master = load(Path(tdir) / "red_trace.json") if tdir else None
    pr = load(Path(tdir) / "red_trace_pr.json") if tdir else None
    root = Path(spec["root"]).resolve() if spec.get("root") else None  # one spelling per file in every census
    if root is None or not (root / ".github" / "workflows").is_dir():
        row.update(state="DEFERRED", reason=spec.get("deferred_reason") or "no checkout")
        return row
    previous = load(spec.get("ledger")) or {"entries": []}  # the hub passes its committed ledger (ratchet)
    ledger = adm.build(root, master, pr, previous, previous.get("runtimes", {}))
    census = dp.build(root, ledger, audit_fn(root))
    t = census["totals"]
    row.update(state="OBSERVED" if master else "STATIC_ONLY",
               reason=None if master else (spec.get("deferred_reason") or "no Actions telemetry"),
               head_sha=spec.get("head_sha"),
               proposed_admission={"counts": ledger["counts"], "coverage": ledger["coverage"],
                                   "ledger_sha256": ledger["ledger_sha256"]},
               breadth=t["breadth"], depth=t["depth"], penetration=t["penetration"], tested=t["tested"],
               zero=t["zero"], depth_digest_sha256=census["digest_sha256"])
    if master:
        row["master_lane"] = {"counts": master["counts"], "census": {k: v for k, v in (master.get("census") or {}).items()
                                                                    if k != "unobserved"},
                              "currently_red": len(master.get("currently_red", [])),
                              "currently_red_stale": len(master.get("currently_red_stale", [])),
                              "shared_break_roots": len(master.get("shared_break_roots", [])),
                              "digest_sha256": master.get("digest_sha256")}
    if pr:
        row["pr_lane"] = {"counts": pr["counts"], "window": pr["window"], "merge_timing": pr.get("merge_timing"),
                          "merged_with_red": len(pr["merged_with_red"]),
                          "merged_with_pending": len(pr["merged_with_pending"]),
                          "digest_sha256": pr.get("digest_sha256")}
        if files_by_pr is not None:
            rep = bt.run(root, pr, ledger, files_by_pr, limit, master)
            p = rep["policies"]["admission_ledger"]
            row["backtest"] = {"enforced": p["enforced"], **{k: v for k, v in p["summary"].items() if k != "by_workflow"}}
    return row


def rollup(rows: list) -> dict:
    obs = [r for r in rows if r["state"] != "DEFERRED"]
    s = lambda f: sum(f(r) for r in obs)
    tot = {
        "repositories": len(rows), "observed": sum(r["state"] == "OBSERVED" for r in rows),
        "static_only": sum(r["state"] == "STATIC_ONLY" for r in rows),
        "deferred": sum(r["state"] == "DEFERRED" for r in rows),
        "workflows": s(lambda r: r["breadth"]["workflows"]),
        "workflows_with_evidence": s(lambda r: r["proposed_admission"]["coverage"]["with_any_evidence"]),
        "proposed_enforced": s(lambda r: r["proposed_admission"]["counts"].get("ENFORCED", 0)),
        "unique_tests": s(lambda r: r["depth"]["unique_tests"]),
        "test_executions_per_pass": s(lambda r: r["depth"]["tests_total"]),
        "zero_tests_workflows": s(lambda r: r["zero"].get("ZERO_TESTS", 0)),
        "tracked_files": s(lambda r: r["penetration"]["tracked_files"]),
        "targeted_files": s(lambda r: r["penetration"]["targeted_files"]),
        "code_files": s(lambda r: r["penetration"]["code_files"]),
        "zero_targeted_code": s(lambda r: r["penetration"]["zero_targeted_code"]),
        "dead_filters": s(lambda r: r["penetration"]["dead_filters"]),
        "modules": s(lambda r: r["tested"]["modules"]), "modules_tested": s(lambda r: r["tested"]["tested"]),
        "zero_tested_modules": s(lambda r: r["tested"]["zero_tested"]),
        "currently_red": s(lambda r: (r.get("master_lane") or {}).get("currently_red", 0)),
        "merged_prs_traced": s(lambda r: (r.get("pr_lane") or {}).get("window", {}).get("merged_prs", 0)),
        "merged_with_red": s(lambda r: (r.get("pr_lane") or {}).get("merged_with_red", 0)),
        "merged_with_pending": s(lambda r: (r.get("pr_lane") or {}).get("merged_with_pending", 0)),
        "backtest_would_have_caught_red": s(lambda r: (r.get("backtest") or {}).get("would_have_caught_red", 0)),
    }
    pct = lambda a, b: round(100 * a / b, 1) if b else None
    tot.update(evidence_pct=pct(tot["workflows_with_evidence"], tot["workflows"]),
               targeted_pct=pct(tot["targeted_files"], tot["tracked_files"]),
               tested_pct=pct(tot["modules_tested"], tot["modules"]),
               test_fanout=round(tot["test_executions_per_pass"] / tot["unique_tests"], 1) if tot["unique_tests"] else None)
    return tot


def markdown(doc: dict) -> str:
    t = doc["totals"]
    lines = ["### GOGREEN federation spine",
             f"{t['repositories']} repositories: {t['observed']} observed, {t['static_only']} static only, {t['deferred']} deferred. "
             f"{t['workflows']} workflows, {t['workflows_with_evidence']} with red/green evidence ({t['evidence_pct']}%); "
             f"{t['proposed_enforced']} would be ENFORCED under the hub's admission rules (proposal only).", "",
             "| Repo | State | Workflows | Evidence | Proposed enforced | Red now | Merged red / pending (PRs) | "
             "Unique tests | Fan-out | ZERO_TESTS wf | Targeted % | ZERO_TARGETED code | Tested % | ZERO_TESTED |",
             "|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in doc["repositories"]:
        if r["state"] == "DEFERRED":
            lines.append(f"| {r['repo']} | DEFERRED: {r['reason']} |" + " — |" * 12)
            continue
        pa, pl, d = r["proposed_admission"], r.get("pr_lane") or {}, r["depth"]
        fan = round(d["tests_total"] / d["unique_tests"], 1) if d["unique_tests"] else "—"
        lines.append(
            f"| {r['repo']} | {r['state']} | {r['breadth']['workflows']} | {pa['coverage']['with_any_evidence']} | "
            f"{pa['counts'].get('ENFORCED', 0)} | {(r.get('master_lane') or {}).get('currently_red', '—')} | "
            f"{pl.get('merged_with_red', '—')} / {pl.get('merged_with_pending', '—')} of {pl.get('window', {}).get('merged_prs', '—')} | "
            f"{d['unique_tests']} | {fan}× | {r['zero'].get('ZERO_TESTS', 0)} | {r['penetration']['targeted_pct']} | "
            f"{r['penetration']['zero_targeted_code']}/{r['penetration']['code_files']} | {r['tested']['tested_pct']} | "
            f"{r['tested']['zero_tested']} |")
    lines += ["", f"**Federation:** {t['unique_tests']} unique tests run {t['test_executions_per_pass']} times per full CI pass "
                  f"({t['test_fanout']}×); targeted penetration {t['targeted_pct']}%; tested modules {t['tested_pct']}%; "
                  f"{t['merged_with_red']} of {t['merged_prs_traced']} traced merges went in with a red check, "
                  f"{t['merged_with_pending']} with a check still running.",
              "", "_Read-only. Per-repo ledgers are proposals: only the hub has a required gate. DEFERRED is not green._"]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", type=Path, required=True)
    ap.add_argument("--backtest-limit", type=int, default=30, help="merged PRs per repo replayed (1 files read each)")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    specs = json.loads(a.spec.read_text(encoding="utf-8"))
    rows = []
    for spec in specs:
        files = None
        pr = load(Path(spec["trace_dir"]) / "red_trace_pr.json") if spec.get("trace_dir") else None
        if pr and a.backtest_limit > 0 and os.environ.get("GITHUB_TOKEN") is not None:
            reader = g.Reader(spec["repo"])
            recent = sorted(pr["merge_matrix"], key=lambda m: (m["merged_at"], m["pr"]))[-a.backtest_limit:]
            files = {}
            for m in recent:
                try:
                    files[m["pr"]] = g.changed_files(reader, m["pr"])
                except Exception as e:  # one unreadable PR must not hide the rest
                    print(f"::warning title=federation backtest::{spec['repo']}#{m['pr']}: {type(e).__name__}")
        rows.append(repo_row(spec, files, a.backtest_limit))
    doc = {"schema": SCHEMA, "repositories": rows, "totals": rollup(rows),
           "authority": {"merge_authorized": False, "enforced_anywhere_but_hub": False, "actor": "AGENT"}}
    doc["digest_sha256"] = hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest()
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "federation.json").write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (a.out / "federation.md").write_text(markdown(doc), encoding="utf-8", newline="\n")
    print(json.dumps(doc["totals"], sort_keys=True))
    return doc


if __name__ == "__main__":
    main()
