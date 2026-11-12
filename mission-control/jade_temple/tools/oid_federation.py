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
New here: transitive reduction (muda prune) and the wishbone convergence check.
DSM, CPM slack and makespan are owned by gg_MATH kernels/dsm_makespan.py
(GBOGEB/gg_MATH#128); gg_math_kernel() loads it from a checkout of the pinned
commit (GG_MATH_ROOT) and reports UNKNOWN, with no numbers, when that is absent.

MIP means Modernize / Innovate / Perpetuate (LEVEL1.md). Perpetuate is the control
step that links MIP to DMAIC Control: immutable, idempotent, recursive lineage kept
active by MYCELIUM and the Golden Thread. The handover used "MIP" for makespan
optimisation; here that step is called SCHEDULE (an Innovate item). wishbone() proves
it idempotent, and check() binds every Modernize / Innovate / Perpetuate owner to its
blob OID.

  python mission-control/jade_temple/tools/oid_federation.py [--json]
Exit 0 = clean, 1 = crosswalk violations, 2 = DAG cycle or wishbone did not converge.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
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
MIP_STEPS = ("modernize", "innovate", "perpetuate")
PERPETUATE_PROPERTIES = ("immutable", "idempotent", "recursive_lineage", "mycelium_golden_thread")

# DSM / CPM / makespan owner (decision 2026-11-12): gg_MATH kernels/dsm_makespan.py, merged in
# GBOGEB/gg_MATH#128. Loaded from a checkout of exactly this commit (GG_MATH_ROOT); anything else
# is reported as UNKNOWN, never as a pass and never as numbers.
GG_MATH_REPO = "GBOGEB/gg_MATH"
GG_MATH_PIN = "0d7725b1942d16dbed73ddc33604ef0bc1649cce"
GG_MATH_SCHEMA = "gg-math-dsm-makespan/v1"
GG_MATH_WORKERS = (1, 2, 4)


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


def schedule(prereqs: dict[str, list[str]]) -> dict:
    """Kahn waves and the unit critical path, both from their hub owners.

    Weighted makespan, CPM slack and the N2 DSM belong to gg_MATH
    kernels/dsm_makespan.py (owner decision 2026-11-12, GBOGEB/gg_MATH#128)."""
    wave = AD.waves(prereqs)  # ValueError on a cycle or an unknown node
    layers = [sorted((k for k in wave if wave[k] == w), key=lambda k: (AD.carbon_of(k), k))
              for w in range(1, max(wave.values(), default=0) + 1)]
    return {"waves": layers, "wave_count": len(layers),
            "width": max((len(x) for x in layers), default=0),
            "critical": CD.critical_path(prereqs) if prereqs else []}


def wishbone(prereqs: dict[str, list[str]]) -> dict:
    """Track A: DMAIC (prune) then MIP (schedule); Track B: MIP then DMAIC; C merges.

    Transitive reduction keeps reachability, so A and B must agree on waves and the
    critical path, and pruning the pruned DAG must drop nothing (Perpetuate:
    idempotent). Any disagreement is a bug, and `converged` is False."""
    reduced, dropped = transitive_reduction(prereqs)
    a = schedule(reduced)
    b = schedule(prereqs)
    _, b_dropped = transitive_reduction(prereqs)
    again, re_dropped = transitive_reduction(reduced)
    idempotent = not re_dropped and again == reduced
    converged = (a["waves"] == b["waves"] and a["critical"] == b["critical"]
                 and dropped == b_dropped and idempotent)
    edges = sum(len(v) for v in prereqs.values())
    return {
        "track_a": {"order": ["DMAIC", "SCHEDULE"], "pruned": dropped, **a},
        "track_b": {"order": ["SCHEDULE", "DMAIC"], "pruned": b_dropped, **b},
        "track_c": {"converged": converged, "idempotent": idempotent, "edges_before": edges,
                    "edges_after": edges - len(dropped), "dag": reduced,
                    "wave_count": a["wave_count"], "waves": a["waves"]},
    }


# ---------------------------------------------------------------- gg_MATH owner (pinned)

def _git_head(root: Path) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def _import_kernel(root: Path):
    """Import kernels.dsm_makespan from `root` without leaking its `kernels` package."""
    def ours(k: str) -> bool:
        return k == "kernels" or k.startswith("kernels.")

    saved = {k: sys.modules.pop(k) for k in list(sys.modules) if ours(k)}
    sys.path.insert(0, str(root))
    try:
        return importlib.import_module("kernels.dsm_makespan")
    finally:
        sys.path.remove(str(root))
        for k in [k for k in sys.modules if ours(k)]:
            sys.modules.pop(k)
        sys.modules.update(saved)


def gg_math_kernel(prereqs: dict[str, list[str]], root: str | Path | None = None,
                   durations: dict[str, float] | None = None, head=_git_head) -> dict:
    """DSM / CPM / makespan from the pinned gg_MATH owner, or an explicit coverage gap.

    status OK: the checkout is exactly GG_MATH_PIN and `result` is its evaluate() output.
    status UNKNOWN: no checkout, wrong commit, missing kernel or wrong schema; no numbers.
    status FAIL: the owner ran, but its unit-weight critical path disagrees with the hub's
    wave count (both must count the same longest chain)."""
    out = {"status": "UNKNOWN", "repo": GG_MATH_REPO, "pin": GG_MATH_PIN, "reason": None,
           "result": None}
    root = root or os.environ.get("GG_MATH_ROOT")
    if not root:
        out["reason"] = "GG_MATH_ROOT not set: no gg_MATH checkout"
        return out
    root = Path(root)
    if not (root / "kernels" / "dsm_makespan.py").is_file():
        out["reason"] = f"{root}: kernels/dsm_makespan.py not found"
        return out
    got = head(root)
    if got != GG_MATH_PIN:
        out["reason"] = f"gg_MATH checkout at {got or 'unknown commit'}, pin is {GG_MATH_PIN}"
        return out
    dm = _import_kernel(root)
    if getattr(dm, "SCHEMA", None) != GG_MATH_SCHEMA:
        out["reason"] = f"schema {getattr(dm, 'SCHEMA', None)!r} != {GG_MATH_SCHEMA}"
        return out
    lanes = [{"id": k, "cost": float((durations or {}).get(k, 1.0)), "deps": list(v)}
             for k, v in prereqs.items()]
    result = dm.evaluate(lanes, workers=list(GG_MATH_WORKERS))
    out.update(status="OK", result=result)
    if durations is None:
        waves = schedule(prereqs)["wave_count"]
        length = result["critical_path"]["length"]
        if length != waves:
            out.update(status="FAIL", reason=f"gg_MATH unit critical path {length:g} != hub waves {waves}")
    return out


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
    mip = doc.get("mip") or {}
    for step in sorted(set(MIP_STEPS) ^ set(mip)):
        errs.append(f"mip.{step}: {'missing' if step in MIP_STEPS else 'not a MIP step'}")
    for step in MIP_STEPS:
        owners = (mip.get(step) or {}).get("owners") or []
        if not owners:
            errs.append(f"mip.{step}: names no owner")
        for rel in owners:
            o = oid(rel)
            if o is None:
                errs.append(f"mip.{step}: owner {rel} does not exist at HEAD")
            else:
                bound[rel] = o
    props = (mip.get("perpetuate") or {}).get("properties") or {}
    for p in PERPETUATE_PROPERTIES:
        if not props.get(p):
            errs.append(f"mip.perpetuate: property {p} is not bound to a control")
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

def build(doc: dict, nodes: dict) -> dict:
    prereqs = {k: list(n.get("depends_on") or []) for k, n in nodes.items()}
    errs, bound = check(doc, nodes)
    return {"schema": "jade.temple.oid-federation.v1", "errors": errs, "owners": bound,
            "wishbone": wishbone(prereqs), "gg_math_kernel": gg_math_kernel(prereqs)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--crosswalk", type=Path, default=DATA)
    ap.add_argument("--dag", type=Path, default=AD.DATA)
    ap.add_argument("--json", action="store_true", help="print the full result as json")
    a = ap.parse_args(argv)
    doc, nodes = load(a.crosswalk), AD.load(a.dag)["nodes"]
    try:
        r = build(doc, nodes)
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
              f"{c['wave_count']} waves, converged={c['converged']}, "
              f"idempotent={c['idempotent']}")
        g = r["gg_math_kernel"]
        if g["status"] == "OK":
            cp = g["result"]["critical_path"]
            print(f"gg_math_kernel: OK @ {GG_MATH_PIN[:12]} critical path {cp['length']:g}, "
                  f"work {cp['total_work']:g}")
        else:
            print(f"gg_math_kernel: {g['status']} ({g['reason']})")
        for e in r["errors"]:
            print(f"FAIL {e}")
    if not r["wishbone"]["track_c"]["converged"]:
        return 2
    if r["gg_math_kernel"]["status"] == "FAIL":
        return 1
    return 1 if r["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
