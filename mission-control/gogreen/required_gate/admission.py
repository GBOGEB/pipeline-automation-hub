#!/usr/bin/env python3
"""GOGREEN admission ledger: the trust -> authority step between red-trace and the gate.

    telemetry  red_trace.json (master lane) + red_trace_pr.json (merged-PR lane)
    trust      per-workflow health: current state, green streak since the last red,
               freshness, nondeterminism (same-head disagreement / rerun rescue), 📌 pins
    authority  ADMISSION.json (committed): EVERY workflow file gets a disposition
               ENFORCED / OBSERVED / EXCLUDED with reason codes; omission is not a state
    gate       gate.py reads ADMISSION.json from the base branch and enforces ENFORCED

Ratchet: a workflow the previous ledger (or, before one exists, the N+8 bootstrap)
ENFORCES is never auto-demoted. If its evidence turns bad it stays ENFORCED and is listed
as a demotion candidate: weakening a gate is the owner's decision, not the agent's.

Runtime debt: every `uses:` reference is resolved to its `runs.using` (node20 / node24 /
composite / docker). The resolution map is part of the ledger, so CI regeneration is
offline; `--resolve-runtimes` refreshes it with `git fetch --depth 1` of the action repo.

Read-only. Writes only the ledger file it is pointed at.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gate as g  # noqa: E402

MIN_STREAK = 2      # consecutive green heads since the last red, on the freshest lane
FRESH_DAYS = 14     # a gate nobody exercised for two weeks is observed, not enforced
INFO = re.compile(r"^\s*#\s*gogreen-admission:\s*(observe|exclude)\b", re.M)
USES = re.compile(r"""^\s*(?:-\s*)?uses:\s*['"]?([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)((?:/[A-Za-z0-9_.-]+)*)@([A-Za-z0-9_./-]+)""", re.M)
LANES = ("master", "pr")


def uses(text: str) -> list:
    return sorted({f"{repo}{sub}@{ref}" for repo, sub, ref in USES.findall(text)})


def resolve_runtime(ref: str, timeout=90) -> str:
    """`runs.using` of owner/repo[/sub]@ref via a blobless depth-1 git fetch (no API scope needed)."""
    m = re.fullmatch(r"([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)((?:/[A-Za-z0-9_.-]+)*)@([A-Za-z0-9_./-]+)", ref)
    if not m or ".." in ref:
        return "UNRESOLVED"
    repo, sub, rev = m.group(1), m.group(2).lstrip("/"), m.group(3)
    with tempfile.TemporaryDirectory() as d:
        run = lambda *a: subprocess.run(["git", "-C", d, *a], capture_output=True, text=True, timeout=timeout)
        run("init", "-q")
        if run("fetch", "-q", "--depth", "1", "--filter=blob:none", f"https://github.com/{repo}", rev).returncode:
            return "UNRESOLVED"
        for name in ("action.yml", "action.yaml"):
            shown = run("show", f"FETCH_HEAD:{sub + '/' if sub else ''}{name}")
            if shown.returncode == 0:
                try:
                    using = ((yaml.safe_load(shown.stdout) or {}).get("runs") or {}).get("using")
                except yaml.YAMLError:
                    return "UNRESOLVED"
                return str(using).strip("'\"") if using else "UNRESOLVED"
    return "UNRESOLVED"


def lane_view(w: dict | None, lane: str) -> dict | None:
    if not w:
        return None
    v = {"class": w.get("class"), "current": w.get("current"), "green_streak": w.get("green_streak", 0),
         "latest_age_days": w.get("latest_age_days"), "latest_sha": (w.get("latest") or {}).get("sha"),
         "nondeterministic": bool((w.get("nondeterminism") or {}).get("nondeterministic")),
         "same_head_disagreements": (w.get("nondeterminism") or {}).get("same_head_disagreements", 0),
         "rerun_rescues": (w.get("nondeterminism") or {}).get("rerun_rescues", 0)}
    if lane == "pr":
        v["merged_red_prs"] = len(w.get("merged_red_prs", []))
        v["latest_pr"] = w.get("latest_pr")
    return v


def scope(t: dict, rel: str, text: str) -> tuple[str | None, list]:
    """(EXCLUDED reason or None, informational flags) from the workflow's own definition."""
    if rel == g.SELF:
        return "SELF", []
    if t.get("parse_error"):
        return "UNPARSEABLE", []
    if not t.get("pull_request"):
        return ("PULL_REQUEST_TARGET_ONLY" if t.get("pull_request_target") else "NO_PULL_REQUEST_TRIGGER"), []
    why = g.fires_for_base(t, "master")
    if why:
        return ("TYPES_SKIP_HEADS" if "types" in why else "NOT_FOR_MASTER"), []
    m = INFO.search(text)
    if m:
        return ("DECLARED_EXCLUDE" if m.group(1) == "exclude" else None), (["DECLARED_INFORMATIONAL"] if m.group(1) == "observe" else [])
    return None, []


def judge(views: dict, pinned: list, flags: list) -> list:
    """Reason codes that keep a workflow OBSERVED; [] means the evidence supports ENFORCED."""
    present = {k: v for k, v in views.items() if v and v.get("current")}
    if flags:
        return list(flags)
    if not present:
        return ["NO_TERMINAL_EVIDENCE"]
    out = []
    for lane, v in sorted(present.items()):
        if v["current"] == "RED":
            out.append(f"RED_NOW_{lane.upper()}")
        if v["nondeterministic"]:
            out.append(f"NONDETERMINISTIC_{lane.upper()}")
    freshest = min(present.values(), key=lambda v: v["latest_age_days"] if v["latest_age_days"] is not None else 1e9)
    if freshest["latest_age_days"] is None or freshest["latest_age_days"] > FRESH_DAYS:
        out.append("NOT_EXERCISED_RECENTLY")
    # Stability is the longest current green streak on any lane: a short lane window (e.g. a
    # recent PR-lane sample) must not hide a long master streak and raise a false demotion.
    if freshest["current"] == "GREEN" and max(v["green_streak"] for v in present.values()) < MIN_STREAK:
        out.append("GREEN_STREAK_SHORT")
    if pinned:
        out.append("PINNED_EVIDENCE")
    return out


def build(root: Path, master: dict | None, pr: dict | None, previous: dict | None, runtimes: dict) -> dict:
    root = Path(root)
    by = {lane: {w["path"]: w for w in (rep or {}).get("workflows", [])} for lane, rep in (("master", master), ("pr", pr))}
    incumbents = ({e["path"] for e in previous["entries"] if e["disposition"] == g.ENFORCED}
                  if previous else set(g.GUARDED))
    wdir = root / ".github" / "workflows"
    files = sorted(str(f.relative_to(root)) for f in list(wdir.glob("*.yml")) + list(wdir.glob("*.yaml")))
    entries = []
    for rel in files:
        text = (root / rel).read_text(encoding="utf-8")
        t = g.triggers(root / rel)
        excluded, flags = scope(t, rel, text)
        views = {lane: lane_view(by[lane].get(rel), lane) for lane in LANES}
        pinned = sorted({p for lane in LANES for p in (by[lane].get(rel) or {}).get("pinned_historical_ids", [])})
        refs = uses(text)
        e = {"path": rel, "name": t.get("name"), "incumbent": rel in incumbents,
             "trigger": {"pull_request": bool(t.get("pull_request")),
                         "filter": ("PATHS" if t.get("paths") else "PATHS_IGNORE" if t.get("paths_ignore") else "ALL"),
                         "branches": t.get("branches"), "types": t.get("types")},
             "evidence": {lane: v for lane, v in views.items() if v},
             "uses": refs, "node20_uses": [r for r in refs if runtimes.get(r) == "node20"]}
        if excluded:
            e.update(disposition=g.EXCLUDED, reasons=[excluded] + (["INCUMBENT_LOST_SCOPE"] if rel in incumbents else []))
        else:
            hold = judge(views, pinned, flags)
            if not hold:
                e.update(disposition=g.ENFORCED, reasons=["EVIDENCE_HEALTHY"])
            elif rel in incumbents:
                e.update(disposition=g.ENFORCED, reasons=["INCUMBENT_RATCHET"], demotion_candidate=hold)
            else:
                e.update(disposition=g.OBSERVED, reasons=hold)
        entries.append(e)
    counts = {}
    for e in entries:
        counts[e["disposition"]] = counts.get(e["disposition"], 0) + 1
    pr_scope = [e for e in entries if e["trigger"]["pull_request"]]
    src = lambda rep: None if not rep else {
        "schema": rep.get("schema"), "digest_sha256": rep.get("digest_sha256"),
        "observed_at_utc": rep.get("observed_at_utc"),
        "window": rep.get("window")}
    doc = {"schema": g.ADMISSION_SCHEMA,
           "generated_from": {"master_lane": src(master), "pr_lane": src(pr),
                              "previous_ledger_sha256": previous.get("ledger_sha256") if previous else None},
           "rules": {"MIN_STREAK": MIN_STREAK, "FRESH_DAYS": FRESH_DAYS,
                     "ratchet": "an ENFORCED entry is never auto-demoted; bad evidence -> demotion_candidate (OWNER)",
                     "policy_read_from": "base branch (gate.py --policy base)"},
           "counts": counts,
           "coverage": {"workflow_files": len(entries), "dispositioned": len(entries),
                        "pull_request_scoped": len(pr_scope),
                        "enforced_of_pr_scoped": counts.get(g.ENFORCED, 0),
                        "with_evidence": {lane: sum(lane in e["evidence"] for e in entries) for lane in LANES},
                        "with_any_evidence": sum(bool(e["evidence"]) for e in entries)},
           "runtime_debt": {"node20_workflows": sum(bool(e["node20_uses"]) for e in entries),
                            "node20_refs": sorted({r for e in entries for r in e["node20_uses"]}),
                            "unresolved_refs": sorted({r for e in entries for r in e["uses"]
                                                       if runtimes.get(r, "UNRESOLVED") == "UNRESOLVED"})},
           "runtimes": dict(sorted(runtimes.items())),
           "entries": entries,
           "authority": {"merge_authorized": False, "branch_protection_changed": False,
                         "proposed_by": "AGENT", "owner_review": "required before merge"}}
    doc["ledger_sha256"] = hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest()
    return doc


def diff(old: dict | None, new: dict) -> dict:
    o = {e["path"]: e["disposition"] for e in (old or {}).get("entries", [])}
    n = {e["path"]: e for e in new["entries"]}
    return {"promoted": sorted(p for p, e in n.items() if e["disposition"] == g.ENFORCED and o.get(p) != g.ENFORCED),
            "demotion_candidates": sorted(p for p, e in n.items() if e.get("demotion_candidate")),
            "new_files": sorted(set(n) - set(o)), "removed_files": sorted(set(o) - set(n))}


def markdown(doc: dict, d: dict | None = None) -> str:
    c, cov, rd = doc["counts"], doc["coverage"], doc["runtime_debt"]
    lines = ["### GOGREEN admission ledger (trust → authority)",
             f"{cov['workflow_files']} workflow files, **all dispositioned**: "
             f"ENFORCED {c.get('ENFORCED', 0)} · OBSERVED {c.get('OBSERVED', 0)} · EXCLUDED {c.get('EXCLUDED', 0)}. "
             f"Evidence: master lane {cov['with_evidence']['master']}, merged-PR lane {cov['with_evidence']['pr']}, "
             f"either {cov['with_any_evidence']}.",
             f"Runtime debt: {rd['node20_workflows']} workflow(s) use a Node 20 action "
             f"({', '.join(rd['node20_refs']) or 'none'}).", ""]
    reasons = {}
    for e in doc["entries"]:
        for r in e["reasons"] + e.get("demotion_candidate", []):
            reasons[(e["disposition"], r)] = reasons.get((e["disposition"], r), 0) + 1
    lines += ["| Disposition | Reason | Workflows |", "|---|---|---:|"]
    lines += [f"| {k[0]} | {k[1]} | {v} |" for k, v in sorted(reasons.items())]
    if d:
        lines += ["", f"Drift vs committed ledger: promoted {len(d['promoted'])}, demotion candidates "
                      f"{len(d['demotion_candidates'])}, new files {len(d['new_files'])}, removed {len(d['removed_files'])}."]
        for k in ("promoted", "demotion_candidates", "new_files", "removed_files"):
            if d[k]:
                lines.append(f"- {k}: " + ", ".join(p.split('/')[-1] for p in d[k][:20]))
    lines += ["", "_Proposal by an agent from read-only telemetry. ENFORCED takes effect only once this ledger is "
              "merged to the base branch by the owner; demotion is always an owner decision._"]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--master-trace", type=Path)
    ap.add_argument("--pr-trace", type=Path)
    ap.add_argument("--ledger", type=Path, default=None, help="committed ledger (previous state + runtime map)")
    ap.add_argument("--out", type=Path, help="write the proposed ledger here")
    ap.add_argument("--summary", type=Path, help="write a markdown summary here")
    ap.add_argument("--resolve-runtimes", action="store_true", help="git-fetch action.yml for unknown refs")
    a = ap.parse_args(argv)
    ledger = a.ledger or (a.root / g.ADMISSION)
    previous = json.loads(ledger.read_text()) if ledger.exists() else None
    load = lambda p: json.loads(p.read_text()) if p else None
    runtimes = dict((previous or {}).get("runtimes", {}))
    if a.resolve_runtimes:
        wdir = a.root / ".github" / "workflows"
        for ref in sorted({r for f in list(wdir.glob("*.yml")) + list(wdir.glob("*.yaml")) for r in uses(f.read_text())}):
            if runtimes.get(ref, "UNRESOLVED") == "UNRESOLVED":
                runtimes[ref] = resolve_runtime(ref)
    doc = build(a.root, load(a.master_trace), load(a.pr_trace), previous, runtimes)
    d = diff(previous, doc)
    if a.out:
        a.out.write_text(json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    md = markdown(doc, d if previous else None)
    if a.summary:
        a.summary.write_text(md)
    print(json.dumps({"counts": doc["counts"], "coverage": doc["coverage"],
                      "node20_workflows": doc["runtime_debt"]["node20_workflows"], "drift": {k: len(v) for k, v in d.items()}},
                     sort_keys=True))
    return doc


if __name__ == "__main__":
    main()
