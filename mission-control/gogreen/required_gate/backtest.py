#!/usr/bin/env python3
"""Backtest the required gate against merged history (recursive use of the gate's own logic).

For each recently merged PR, replay what GOGREEN required gate WOULD have answered at merge
time, under two policies: the N+8 bootstrap (2 incumbents) and the proposed admission
ledger. Inputs are the merged-PR lane of red_trace (result of every workflow on the merged
head at merge time) and each PR's changed files. Applicability uses gate.fires_for_base()
and gate.applies() unchanged, so this measures the code that will actually run.

A FAIL here is an observation that a merge happened while an applicable gate was not
green at that moment; it is not a root, a fault attribution or a claim the gate was
required then. Caveats, printed with every report:
  * trigger filters are read from today's workflow files (historical filter drift is
    possible); a workflow is skipped for PRs merged before it existed;
  * ABSENT = no run on the merged head before merge: a trigger miss OR filter drift.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gate as g  # noqa: E402

RED = {"failure", "timed_out", "startup_failure"}


def reason(conclusion) -> str | None:
    if conclusion == "success":
        return None
    if conclusion is None:
        return "ABSENT_OR_FILTER_DRIFT"
    if conclusion in RED:
        return "RED_AT_MERGE"
    if conclusion == "pending_at_merge":
        return "PENDING_AT_MERGE"
    return f"{str(conclusion).upper()}_AT_MERGE"


def replay(root: Path, matrix_row: dict, files: list, enforced: list, created_at: dict, base: str) -> dict:
    out = {"pr": matrix_row["pr"], "merged_at": matrix_row["merged_at"], "applicable": [], "failing": []}
    for wf in enforced:
        if wf == g.SELF or not (Path(root) / wf).exists():
            continue
        t = g.triggers(Path(root) / wf)
        if g.fires_for_base(t, base):
            continue
        made = created_at.get(wf)
        if made and made > matrix_row["merged_at"]:
            continue
        if not g.applies(files, t["paths"], t["paths_ignore"]):
            continue
        out["applicable"].append(wf)
        why = reason(matrix_row["at_merge"].get(wf))
        if why:
            out["failing"].append({"workflow": wf, "reason": why})
    out["verdict"] = g.FAIL if out["failing"] else g.PASS
    return out


def summarize(rows: list) -> dict:
    by_reason, by_wf = {}, {}
    for r in rows:
        for f in r["failing"]:
            by_reason[f["reason"]] = by_reason.get(f["reason"], 0) + 1
            by_wf[f["workflow"]] = by_wf.get(f["workflow"], 0) + 1
    return {"evaluated": len(rows), "would_pass": sum(r["verdict"] == g.PASS for r in rows),
            "would_fail": sum(r["verdict"] == g.FAIL for r in rows),
            "prs_with_applicable_gate": sum(bool(r["applicable"]) for r in rows),
            "applicable_checks": sum(len(r["applicable"]) for r in rows),
            "would_have_caught_red": sum(any(f["reason"] == "RED_AT_MERGE" for f in r["failing"]) for r in rows),
            "by_reason": dict(sorted(by_reason.items())),
            "by_workflow": dict(sorted(by_wf.items(), key=lambda kv: (-kv[1], kv[0])))}


def landed_on_base(master: dict | None) -> dict:
    """{workflow: first run on the base branch} when the master lane saw its whole history
    (not truncated): a workflow that first ran on base after a PR merged was not there yet."""
    out = {}
    for w in (master or {}).get("workflows", []):
        if w.get("first_observed_at") and not w.get("history_truncated"):
            out[w["path"]] = w["first_observed_at"]
    return out


def run(root, pr_lane: dict, ledger: dict | None, files_by_pr: dict, limit: int, master: dict | None = None) -> dict:
    base = pr_lane.get("base", "master")
    created = dict((pr_lane.get("census") or {}).get("created_at", {}))
    for wf, at in landed_on_base(master).items():  # the later of API created_at and first base run
        if not created.get(wf) or at > created[wf]:
            created[wf] = at
    matrix = sorted(pr_lane["merge_matrix"], key=lambda m: (m["merged_at"], m["pr"]))[-limit:]
    matrix = [m for m in matrix if m["pr"] in files_by_pr]
    policies = {"bootstrap_n8": sorted(g.GUARDED)}
    if ledger:
        policies["admission_ledger"] = sorted(e["path"] for e in ledger["entries"] if e["disposition"] == g.ENFORCED)
    out = {"schema": "gogreen.required_gate.backtest.v1", "repository": pr_lane.get("repository"), "base": base,
           "pr_lane_digest": pr_lane.get("digest_sha256"),
           "ledger_sha256": (ledger or {}).get("ledger_sha256"),
           "window": {"merged_prs": len(matrix), "from": matrix[0]["merged_at"] if matrix else None,
                      "to": matrix[-1]["merged_at"] if matrix else None},
           "policies": {}, "caveats": [
               "trigger filters read from today's workflow files; historical filter drift possible",
               "a workflow counts only for PRs merged after it was created and (with --master-trace) first ran on base",
               "ABSENT_OR_FILTER_DRIFT = no run on the merged head before merge (trigger miss or drift)",
               "an observation about merge-time state, not a root, attribution or required-check claim"],
           "authority": {"merge_authorized": False, "branch_protection_changed": False}}
    for name, enforced in policies.items():
        rows = [replay(root, m, files_by_pr[m["pr"]], enforced, created, base) for m in matrix]
        out["policies"][name] = {"enforced": len(enforced), "summary": summarize(rows),
                                 "failing_prs": [r for r in rows if r["failing"]]}
    return out


def markdown(rep: dict) -> str:
    w = rep["window"]
    lines = [f"### GOGREEN required-gate backtest · {w['merged_prs']} merged PRs ({w['from']} → {w['to']})",
             "What the gate would have answered at merge time, per policy.", "",
             "| Policy | Enforced | PRs with an applicable gate | Checks evaluated | Would FAIL | of which red at merge |",
             "|---|---:|---:|---:|---:|---:|"]
    for name, p in rep["policies"].items():
        s = p["summary"]
        lines.append(f"| {name} | {p['enforced']} | {s['prs_with_applicable_gate']} | {s['applicable_checks']} | "
                     f"{s['would_fail']} | {s['would_have_caught_red']} |")
    for name, p in rep["policies"].items():
        if p["summary"]["by_reason"]:
            lines += ["", f"**{name}** reasons: " + ", ".join(f"{k} {v}" for k, v in p["summary"]["by_reason"].items())]
            top = list(p["summary"]["by_workflow"].items())[:8]
            lines.append("Most frequent: " + ", ".join(f"{k.split('/')[-1]} ({v})" for k, v in top))
    lines += ["", "_Caveats: " + "; ".join(rep["caveats"]) + "._"]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--pr-trace", type=Path, required=True)
    ap.add_argument("--ledger", type=Path)
    ap.add_argument("--master-trace", type=Path, help="red_trace.json: skip workflows not yet on base at merge")
    ap.add_argument("--limit", type=int, default=40, help="most recent merged PRs to replay (1 files read each)")
    ap.add_argument("--files-json", type=Path, help="offline: {pr: [files]} instead of the API")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    lane = json.loads(a.pr_trace.read_text())
    ledger = json.loads(a.ledger.read_text()) if a.ledger and a.ledger.exists() else None
    recent = sorted(lane["merge_matrix"], key=lambda m: (m["merged_at"], m["pr"]))[-a.limit:]
    if a.files_json:
        files = {int(k): v for k, v in json.loads(a.files_json.read_text()).items()}
    else:
        reader = g.Reader(a.repo)
        files = {m["pr"]: g.changed_files(reader, m["pr"]) for m in recent}
    master = json.loads(a.master_trace.read_text()) if a.master_trace else None
    rep = run(a.root, lane, ledger, files, a.limit, master)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "backtest.json").write_text(json.dumps(rep, indent=1, sort_keys=True) + "\n")
    (a.out / "backtest.md").write_text(markdown(rep))
    print(json.dumps({k: v["summary"] | {"enforced": v["enforced"]} for k, v in rep["policies"].items()},
                     sort_keys=True))
    return rep


if __name__ == "__main__":
    main()
