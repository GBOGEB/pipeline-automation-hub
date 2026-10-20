#!/usr/bin/env python3
"""Assemble the JADE N+8 federation red-trace snapshot from gogreen.red_trace.v1 reports.

Input : one red_trace.json per core repository (produced by
        mission-control/gogreen/red_trace/red_trace.py, read-only Actions metadata).
Output: data/RED_TRACE_FEDERATION_N8.json, a compact, source-bound, deterministic projection
        consumed by site/build_redtrace.py (HTML + slides) and the PDF renderer.
No authority, no root confirmation, no admission is derived here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "RED_TRACE_FEDERATION_N8.json"
CORE = ["pipeline-automation-hub", "ABACUS", "CODEX", "cryoplant-project", "gg_MATH"]
ROLE = {
    "pipeline-automation-hub": "Mission Control hub · pipeline origin (Master_Input document pipeline → MC/JADE/GOGREEN)",
    "ABACUS": "System Under Test · 12-cluster DMAIC engine · EVERRED ledger owner (local working tree: Master_Input)",
    "CODEX": "Federation governance & orchestration hub (Mycelium, MissionControl receipts)",
    "cryoplant-project": "QPS engineering SSOT · QPS TRIAGE owner (private)",
    "gg_MATH": "Mathematics provider (PCA/BT/Monte Carlo kernels, Plotly artifacts)",
}


def _short(t):
    if not t:
        return None
    keep = ("last_green_sha", "first_red_sha", "first_red_run", "first_red_at", "recovery_sha", "recovery_run",
            "recovered_at", "red_hours", "red_streak_runs", "suspect_commit_count", "red_before_window")
    out = {k: t[k] for k in keep if k in t}
    out["failing"] = [f"{f['job']}: {', '.join(f['steps'])}" for f in t.get("failing", [])][:3]
    return out


def project(rep: dict) -> dict:
    wfs = []
    for w in rep["workflows"]:
        if w["class"] == "STABLE_GREEN":
            continue
        t = w.get("break") or (w.get("red_episodes") or [None])[-1] or (
            dict(w["first_red"], first_red_sha=w["first_red"]["sha"], first_red_run=w["first_red"]["run_id"],
                 first_red_at=w["first_red"]["at"]) if "first_red" in w else None)
        wfs.append({"name": w["name"], "path": w["path"], "class": w["class"], "current": w.get("current"),
                    "stale": bool(w.get("stale")), "age_days": w.get("latest_age_days"),
                    "pinned": bool(w.get("pinned_historical_ids")), "flips": len(w.get("flips", [])),
                    "history_truncated": bool(w.get("history_truncated")), "window": _short(t)})
    order = {"GREEN_TO_RED": 0, "EVERRED": 1, "FLAKY": 2, "RED_TO_GREEN": 3, "UNKNOWN_NO_TERMINAL": 4}
    wfs.sort(key=lambda x: (x["current"] != "RED", order.get(x["class"], 9), x["name"]))
    return {"repository": rep["repository"], "branch": rep["branch"], "observed_at_utc": rep["observed_at_utc"],
            "source_digest": rep["digest_sha256"], "workflows_traced": len(rep["workflows"]),
            "runs": rep["window"]["runs"], "truncated_workflows": rep["window"].get("truncated_workflows", 0),
            "counts": rep["counts"], "currently_red": len(rep["currently_red"]),
            "currently_red_stale": len(rep["currently_red_stale"]),
            "shared_break_roots": rep["shared_break_roots"][:8], "non_green": wfs}


def assemble(reports: dict) -> dict:
    repos = []
    for name in CORE:
        rep = reports[name]
        if rep.get("schema") != "gogreen.red_trace.v1" or rep.get("authority", {}).get("merge_authorized") is not False:
            raise ValueError(f"{name}: invalid or authority-bearing red-trace report")
        p = project(rep)
        p["short"] = name
        p["role"] = ROLE[name]
        repos.append(p)
    tot = {"workflows": sum(r["workflows_traced"] for r in repos), "runs": sum(r["runs"] for r in repos),
           "red": sum(r["currently_red"] for r in repos), "red_stale": sum(r["currently_red_stale"] for r in repos)}
    classes = {}
    for r in repos:
        for k, v in r["counts"].items():
            classes[k] = classes.get(k, 0) + v
    tot["classes"] = classes
    tot["red_fresh"] = tot["red"] - tot["red_stale"]
    tot["pinned_red"] = sum(1 for r in repos for w in r["non_green"] if w["pinned"] and w["current"] == "RED")
    data = {"schema": "jade.temple.redtrace_federation.v1", "iteration": "N+8",
            "observed_at_utc": max(r["observed_at_utc"] for r in repos), "repositories": repos, "totals": tot,
            "authority": {"merge_authorized": False, "root_closure_credit": None, "admission": "HOLD"}}
    data["digest_sha256"] = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    return data


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--reports", type=Path, required=True, help="dir with <repo>/red_trace.json")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    reports = {n: json.loads((a.reports / n / "red_trace.json").read_text()) for n in CORE}
    data = assemble(reports)
    a.out.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "totals": data["totals"]}, sort_keys=True))


if __name__ == "__main__":
    main()
