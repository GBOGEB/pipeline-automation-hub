#!/usr/bin/env python3
"""C1-C14 alkane DAG: naming checks, Kahn waves, lane and matrix rules.

Read-only. data/C1_C14_ALKANE_DAG.json names 14 workflow nodes after the alkane
series (C1_methane .. C14_tetradecane). Waves come from the JADE Kahn owner
devops/lifecycle.topo_layers and the critical path from tools/cicd_dag.critical_path;
neither is re-implemented here (AGENTS.md L4).

  python mission-control/jade_temple/tools/alkane_dag.py [--dag PATH]
Exit 0 = clean, 1 = naming or lane violations, 2 = cycle or unknown dependency.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / "data" / "C1_C14_ALKANE_DAG.json"
SCHEMA = "jade.temple.alkane-dag.v1"
ALKANES = ("methane", "ethane", "propane", "butane", "pentane", "hexane", "heptane",
           "octane", "nonane", "decane", "undecane", "dodecane", "tridecane", "tetradecane")
KEY = re.compile(r"C([1-9]\d?)_([a-z]+)")
LANE = re.compile(r"LANE-[0-9A-Z]+|MATRIX-\d\d")


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


L = _load("jade_alkane_lifecycle", "devops/lifecycle.py")
CD = _load("jade_alkane_cicd_dag", "tools/cicd_dag.py")


def formula(n: int) -> str:
    return f"C{n if n > 1 else ''}H{2 * n + 2}"


def carbon_of(key: str) -> int:
    """Carbon number from the node key, for ordering; malformed keys sort last."""
    m = KEY.fullmatch(key)
    return int(m[1]) if m else len(ALKANES) + 1


def load(path: Path = DATA) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise ValueError(f"{path.name}: schema {doc.get('schema')!r} != {SCHEMA}")
    return doc


def check_names(nodes: dict) -> list[str]:
    errs, seen = [], {}
    for key, node in nodes.items():
        m = KEY.fullmatch(key)
        if not m:
            errs.append(f"{key}: key must be C<n>_<alkane>")
            continue
        n, name = int(m[1]), m[2]
        want = ALKANES[n - 1] if n <= len(ALKANES) else None
        if name != want:
            errs.append(f"{key}: C{n} is {want or 'outside C1-C14'}")
        if node.get("carbon") != n:
            errs.append(f"{key}: carbon {node.get('carbon')!r} != {n}")
        if node.get("formula") != formula(n):
            errs.append(f"{key}: formula {node.get('formula')} != {formula(n)}")
        seen.setdefault(n, []).append(key)
    for n in range(1, len(ALKANES) + 1):
        if len(seen.get(n, [])) != 1:
            errs.append(f"C{n}: {len(seen.get(n, []))} nodes, want 1")
    return errs


def waves(prereqs: dict[str, list[str]]) -> dict[str, int]:
    """1-based Kahn wave per node; ValueError on a cycle or an unknown node."""
    edges = [(d, k, "FEEDFORWARD") for k, ds in prereqs.items() for d in ds]
    return {k: w for w, layer in enumerate(L.topo_layers(list(prereqs), edges), 1) for k in layer}


def ancestors(prereqs: dict[str, list[str]]) -> dict[str, set[str]]:
    memo: dict[str, set[str]] = {}

    def up(k: str) -> set[str]:
        if k not in memo:
            memo[k] = set()
            for d in prereqs[k]:
                memo[k] |= {d} | up(d)
        return memo[k]

    return {k: up(k) for k in prereqs}


def check_lanes(nodes: dict, wave: dict[str, int], prereqs: dict[str, list[str]]) -> list[str]:
    errs, lanes = [], {}
    for k, n in nodes.items():
        if not LANE.fullmatch(str(n.get("lane"))):
            errs.append(f"{k}: lane {n.get('lane')!r} is not LANE-<id> or MATRIX-<nn>")
        lanes.setdefault(str(n.get("lane")), []).append(k)
    anc = ancestors(prereqs)
    for lane, members in sorted(lanes.items()):
        members.sort(key=lambda k: (wave[k], carbon_of(k), k))
        if lane.startswith("MATRIX-"):
            # A matrix is one wave of peers that consume the same upstream outputs.
            if len(members) < 2:
                errs.append(f"{lane}: only {members[0]}; a matrix needs >= 2 peers")
            if len({wave[k] for k in members}) > 1:
                errs.append(f"{lane}: {', '.join(members)} sit in waves "
                            f"{sorted({wave[k] for k in members})}; a matrix runs in one wave")
            if len({tuple(sorted(prereqs[k])) for k in members}) > 1:
                errs.append(f"{lane}: members consume different inputs")
        else:
            # A lane is one worktree: each node must depend on the one before it.
            for a, b in zip(members, members[1:]):
                if a not in anc[b]:
                    errs.append(f"{lane}: {b} does not depend on {a}; parallel work forced serial")
    return errs


def evaluate(nodes: dict) -> dict:
    """Violations, waves and critical path; `fatal` names a cycle or dangling edge."""
    out = {"errors": check_names(nodes), "fatal": None, "wave": {}, "critical": []}
    prereqs = {k: list(n.get("depends_on") or []) for k, n in nodes.items()}
    try:
        out["wave"] = waves(prereqs)
    except ValueError as exc:
        out["fatal"] = str(exc)
        return out
    out["errors"] += check_lanes(nodes, out["wave"], prereqs)
    out["critical"] = CD.critical_path(prereqs) if prereqs else []
    return out


def report(nodes: dict) -> int:
    r = evaluate(nodes)
    wave = r["wave"]
    for w in range(1, max(wave.values(), default=0) + 1):
        row = sorted((k for k in wave if wave[k] == w), key=lambda k: (carbon_of(k), k))
        print(f"W{w}  " + "  ".join(f"{k}[{nodes[k].get('lane')}]" for k in row))
    if r["critical"]:
        print(f"critical path ({len(r['critical'])}): " + " -> ".join(r["critical"]))
    mapped = sum(bool(n.get("task")) for n in nodes.values())
    print(f"task mapping: {mapped}/{len(nodes)} nodes name a real task")
    for e in r["errors"]:
        print(f"FAIL {e}")
    if r["fatal"]:
        print(f"FATAL {r['fatal']}")
        return 2
    print("PASS" if not r["errors"] else f"{len(r['errors'])} violation(s)")
    return 1 if r["errors"] else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dag", type=Path, default=DATA, help="alkane DAG json (default: committed)")
    a = ap.parse_args(argv)
    return report(load(a.dag)["nodes"])


if __name__ == "__main__":
    sys.exit(main())
