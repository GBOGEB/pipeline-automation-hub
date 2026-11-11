#!/usr/bin/env python3
"""OID federation crosswalk and wishbone schedule kernel for the C2-OH handover.

Read-only. Two jobs:

1. check(): the eight handover folders in data/OID_FEDERATION_C2OH_CROSSWALK.json
   each point to an existing hub owner (bound to its git blob OID at HEAD), an open PR,
   or a parked item. Unsupported handover claims stay listed with evidence null.
2. wishbone(): Track A (DMAIC then SCHEDULE: prune, then schedule), Track B
   (SCHEDULE then DMAIC) and Track C (converged) over the C1-C14 alkane DAG.

Waves come from devops/lifecycle.topo_layers through alkane_dag.waves, and the unit
critical path from tools/cicd_dag.critical_path; neither is re-implemented (AGENTS.md L4).
New here: transitive reduction (muda prune), CPM slack and makespan with optional
durations, and the N2 dependency structure matrix (DSM).

"MIP" in the handover means scheduling; in the hub MIP is Modernize/Innovate/Prune.
This module calls the handover's step SCHEDULE.

  python mission-control/jade_temple/tools/oid_federation.py [--durations PATH] [--json]
Exit 0 = clean, 1 = crosswalk violations, 2 = DAG cycle or wishbone did not converge.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HUB = ROOT.parents[1]
DATA = ROOT / "data" / "OID_FEDERATION_C2OH_CROSSWALK.json"
SCHEMA = "jade.temple.oid-federation-crosswalk.v1"
FOLDERS = ("00_CONTROL", "01_DROPBOX_IN", "02_HANDOVER_LEDGER", "03_REPOS_MIRROR",
           "04_SLICES_OUT", "TRACK_A_DMAIC_THEN_MIP", "TRACK_B_MIP_THEN_DMAIC",
           "TRACK_C_CONVERGED")
STATUSES = ("owned", "open_pr", "parked")


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


AD = _load("oidfed_alkane_dag", "tools/alkane_dag.py")
CD = AD.CD


# ---------------------------------------------------------------- math kernel

def transitive_reduction(prereqs: dict[str, list[str]]) -> tuple[dict[str, list[str]], list[tuple[str, str]]]:
    """Drop edge d->k when d is already an ancestor of another prerequisite of k.

    Reachability is unchanged, so every schedule built on the result is the same;
    the dropped edges are redundant gates (muda). Returns (reduced, dropped)."""
    anc = AD.ancestors(prereqs)
    reduced, dropped = {}, []
    for k in sorted(prereqs):
        keep = []
        for d in sorted(set(prereqs[k])):
            if any(d in anc[p] for p in prereqs[k] if p != d):
                dropped.append((d, k))
            else:
                keep.append(d)
        reduced[k] = keep
    return reduced, dropped


def cpm(prereqs: dict[str, list[str]], durations: dict[str, float] | None = None) -> dict:
    """Critical path method: earliest/latest start, slack and makespan.

    Without durations every node weighs 1, so the makespan counts waves."""
    wave = AD.waves(prereqs)  # ValueError on a cycle or an unknown node
    order = sorted(prereqs, key=lambda k: (wave[k], k))
    unit = durations is None
    missing = [] if unit else sorted(set(prereqs) - set(durations))
    if missing:
        raise ValueError(f"durations missing for {', '.join(missing)}")
    dur = {k: 1.0 if unit else float(durations[k]) for k in prereqs}
    es: dict[str, float] = {}
    for k in order:
        es[k] = max((es[d] + dur[d] for d in prereqs[k]), default=0.0)
    makespan = max((es[k] + dur[k] for k in order), default=0.0)
    succ: dict[str, list[str]] = {k: [] for k in prereqs}
    for k, ds in prereqs.items():
        for d in ds:
            succ[d].append(k)
    ls: dict[str, float] = {}
    for k in reversed(order):
        ls[k] = min((ls[s] for s in succ[k]), default=makespan) - dur[k]
    slack = {k: round(ls[k] - es[k], 9) for k in order}
    return {"unit": "waves" if unit else "seconds", "makespan": makespan,
            "earliest_start": es, "latest_start": ls, "slack": slack,
            "zero_slack": [k for k in order if slack[k] == 0]}


def schedule(prereqs: dict[str, list[str]], durations: dict[str, float] | None = None) -> dict:
    wave = AD.waves(prereqs)
    layers = [sorted((k for k in wave if wave[k] == w), key=lambda k: (AD.carbon_of(k), k))
              for w in range(1, max(wave.values(), default=0) + 1)]
    c = cpm(prereqs, durations)
    return {"waves": layers, "width": max((len(x) for x in layers), default=0),
            "critical": CD.critical_path(prereqs) if prereqs else [],
            "makespan": c["makespan"], "unit": c["unit"], "zero_slack": c["zero_slack"],
            "slack": c["slack"]}


def wishbone(prereqs: dict[str, list[str]], durations: dict[str, float] | None = None) -> dict:
    """Track A prunes then schedules; Track B schedules then prunes; C is the merge.

    Transitive reduction keeps reachability, so A and B must agree on waves and
    makespan. A disagreement is a bug, and `converged` is False."""
    reduced, dropped = transitive_reduction(prereqs)
    a = schedule(reduced, durations)
    b = schedule(prereqs, durations)
    _, b_dropped = transitive_reduction(prereqs)
    converged = a["waves"] == b["waves"] and a["makespan"] == b["makespan"] and dropped == b_dropped
    edges = sum(len(v) for v in prereqs.values())
    return {
        "track_a": {"order": ["DMAIC", "SCHEDULE"], "pruned": dropped, **a},
        "track_b": {"order": ["SCHEDULE", "DMAIC"], "pruned": b_dropped, **b},
        "track_c": {"converged": converged, "edges_before": edges,
                    "edges_after": edges - len(dropped), "dag": reduced,
                    "makespan": a["makespan"], "unit": a["unit"], "waves": a["waves"]},
    }


def dsm(prereqs: dict[str, list[str]]) -> dict:
    """N2 dependency structure matrix in wave order; m[i][j] = 1 when row i needs column j.

    In wave order every mark sits below the diagonal; `above` counts feedback marks."""
    wave = AD.waves(prereqs)
    order = sorted(prereqs, key=lambda k: (wave[k], AD.carbon_of(k), k))
    idx = {k: i for i, k in enumerate(order)}
    m = [[0] * len(order) for _ in order]
    for k, ds in prereqs.items():
        for d in ds:
            m[idx[k]][idx[d]] = 1
    above = sum(m[i][j] for i in range(len(order)) for j in range(i + 1, len(order)))
    return {"order": order, "matrix": m, "above": above}


# ---------------------------------------------------------------- crosswalk

def blob_oid(rel: str, hub: Path = HUB) -> str | None:
    """Git blob OID of a hub path at HEAD; falls back to hashing the working file."""
    try:
        out = subprocess.run(["git", "-C", str(hub), "rev-parse", f"HEAD:{rel}"],
                             capture_output=True, text=True, timeout=30)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    path = hub / rel
    return CD.git_blob_oid(path.read_bytes()) if path.is_file() else None


def load(path: Path = DATA) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise ValueError(f"{path.name}: schema {doc.get('schema')!r} != {SCHEMA}")
    return doc


def check(doc: dict, alkane_nodes: dict, oid=blob_oid) -> tuple[list[str], dict[str, str]]:
    """Fail-closed crosswalk check. Returns (errors, {owner path: blob OID})."""
    errs, bound = [], {}
    folders = doc.get("folders") or {}
    for name in sorted(set(FOLDERS) ^ set(folders)):
        errs.append(f"{name}: {'missing' if name in FOLDERS else 'not a handover folder'}")
    for name, f in sorted(folders.items()):
        st = f.get("status")
        if st not in STATUSES:
            errs.append(f"{name}: status {st!r} not in {STATUSES}")
        if st == "owned":
            if not f.get("owners"):
                errs.append(f"{name}: owned but names no owner")
            for rel in f.get("owners") or []:
                o = oid(rel)
                if o is None:
                    errs.append(f"{name}: owner {rel} does not exist at HEAD")
                else:
                    bound[rel] = o
        if st == "open_pr" and not isinstance(f.get("pr"), int):
            errs.append(f"{name}: open_pr needs a PR number")
    anchor = (doc.get("anchor") or {}).get("node")
    if anchor not in alkane_nodes:
        errs.append(f"anchor {anchor!r} is not an alkane DAG node")
    for p in doc.get("parked") or []:
        if not p.get("reason"):
            errs.append(f"parked {p.get('item')!r}: needs a reason")
    for c in doc.get("unverified_claims") or []:
        if c.get("evidence") is not None and not str(c["evidence"]).startswith("http"):
            errs.append(f"claim {c.get('claim')!r}: evidence must be null or a link")
    return errs, bound


# ---------------------------------------------------------------- CLI

def build(doc: dict, nodes: dict, durations: dict | None) -> dict:
    prereqs = {k: list(n.get("depends_on") or []) for k, n in nodes.items()}
    errs, bound = check(doc, nodes)
    return {"schema": "jade.temple.oid-federation.v1", "errors": errs, "owners": bound,
            "wishbone": wishbone(prereqs, durations), "dsm": dsm(prereqs)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--crosswalk", type=Path, default=DATA)
    ap.add_argument("--dag", type=Path, default=AD.DATA)
    ap.add_argument("--durations", type=Path, help="json {node: seconds}; default unit weights")
    ap.add_argument("--json", action="store_true", help="print the full result as json")
    a = ap.parse_args(argv)
    doc, nodes = load(a.crosswalk), AD.load(a.dag)["nodes"]
    durations = json.loads(a.durations.read_text(encoding="utf-8")) if a.durations else None
    try:
        r = build(doc, nodes, durations)
    except ValueError as exc:
        print(f"FATAL {exc}")
        return 2
    if a.json:
        print(json.dumps(r, indent=1, default=list))
    else:
        w = r["wishbone"]
        c = w["track_c"]
        print(f"owners bound: {len(r['owners'])}")
        print(f"track A pruned {len(w['track_a']['pruned'])} redundant edge(s): "
              + ", ".join(f"{d}->{k}" for d, k in w["track_a"]["pruned"]))
        print(f"track C: {c['edges_before']} -> {c['edges_after']} edges, "
              f"makespan {c['makespan']:g} {c['unit']}, converged={c['converged']}")
        print(f"DSM {len(r['dsm']['order'])}x{len(r['dsm']['order'])}, feedback marks {r['dsm']['above']}")
        for e in r["errors"]:
            print(f"FAIL {e}")
    if not r["wishbone"]["track_c"]["converged"]:
        return 2
    return 1 if r["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
