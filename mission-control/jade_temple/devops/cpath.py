#!/usr/bin/env python3
"""Critical path with float, criticality and unlock leverage over any work DAG.

Kahn's algorithm gives a valid order; two dynamic-programming passes over that
order give the Critical Path Method (CPM) numbers:

  forward:  ES(v) = max EF(u) over predecessors u, EF(v) = ES(v) + d(v)
  backward: LF(v) = min LS(w) over successors w (makespan for sinks), LS(v) = LF(v) - d(v)
  total float TF = LS - ES; free float FF = min ES(successor) - EF(v)

TF = 0 is the critical path. Done work has duration 0, so the result is the
critical path of the REMAINING work. Unknown durations are not zero: callers
pass a default (unit) and use ``criticality`` to see how fragile the answer is.

This module adds float, weighted durations, criticality and unlock leverage. It
does not replace the existing owners, it imports them:

  * layering            lifecycle.topo_layers            (Kahn waves, cycle naming)
  * deadlock condensing issue_rank/issue_math.strongly_connected
  * transitive relief   issue_rank.unblock_pressure
  * hop-count C-path    cicd_dag.critical_path stays the gate-page owner; with unit
                        durations ``cpm`` reproduces its length (tested).

Edge convention everywhere here: (before, after), i.e. blocker -> waiter.
Pure functions, no I/O; the pilot and CLI live in cpath_pilot.py.
"""
from __future__ import annotations

import heapq
import importlib.util
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
MC = HERE.parents[1]  # mission-control/


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


lifecycle = _load("jade_devops_lifecycle", HERE / "lifecycle.py")
issue_math = _load("issue_math", MC / "issue_rank" / "issue_math.py")

EPS = 1e-9


# ---------------------------------------------------------------- structure

def condense(nodes: list[str], edges: list[tuple[str, str]]) -> dict:
    """Collapse deadlock cycles (SCCs) into single nodes so Kahn can order the rest.

    Returns ``{"comp_of": node->cid, "members": cid->[nodes], "edges": [(cid, cid)],
    "cycles": [[nodes]]}``. A cycle's members all get the cycle's CPM numbers; the
    cycle itself is reported, never silently ordered.
    """
    nodes = sorted(set(nodes))
    known = set(nodes)
    succ = defaultdict(list)
    for a, b in edges:
        if a not in known or b not in known:
            raise ValueError(f"unknown edge endpoint {a}->{b}")
        if a != b:
            succ[a].append(b)
    comps = issue_math.strongly_connected(nodes, succ)
    comp_of = {}
    members = {}
    for c in comps:
        cid = c[0] if len(c) == 1 else "SCC(" + "+".join(sorted(c)) + ")"
        members[cid] = sorted(c)
        for n in c:
            comp_of[n] = cid
    cedges = sorted({(comp_of[a], comp_of[b]) for a, b in edges
                     if a != b and comp_of[a] != comp_of[b]})
    return {"comp_of": comp_of, "members": members, "edges": cedges,
            "cycles": [members[c] for c in members if len(members[c]) > 1]}


def kahn_order(nodes: list[str], edges: list[tuple[str, str]]) -> list[list[str]]:
    """Kahn waves via the canonical owner (lifecycle.topo_layers)."""
    return lifecycle.topo_layers(sorted(nodes), [(a, b, "FEEDFORWARD") for a, b in edges])


# ---------------------------------------------------------------- CPM

def cpm(nodes: list[str], edges: list[tuple[str, str]], duration: dict | None = None,
        done=frozenset(), default: float = 1.0) -> dict:
    """CPM over the remaining work. ``done`` nodes take zero time.

    Returns per-node ``es, ef, ls, lf, total_float, free_float, critical, wave`` and
    ``makespan``, ``critical_path`` (one zero-float chain, first to last),
    ``critical_set`` (every zero-float open node) and ``cycles`` (deadlocks condensed).
    """
    duration = duration or {}
    done = set(done)
    g = condense(nodes, edges)
    cids = sorted(g["members"])

    def d(n):
        return 0.0 if n in done else float(duration.get(n, default))

    cdur = {c: sum(d(n) for n in g["members"][c]) for c in cids}
    waves = kahn_order(cids, g["edges"])
    order = [c for w in waves for c in w]
    wave_of = {c: i for i, w in enumerate(waves) for c in w}
    pred, succ = defaultdict(list), defaultdict(list)
    for a, b in g["edges"]:
        pred[b].append(a)
        succ[a].append(b)

    es, ef = {}, {}
    for c in order:
        es[c] = max((ef[p] for p in pred[c]), default=0.0)
        ef[c] = es[c] + cdur[c]
    makespan = max(ef.values(), default=0.0)
    ls, lf = {}, {}
    for c in reversed(order):
        lf[c] = min((ls[s] for s in succ[c]), default=makespan)
        ls[c] = lf[c] - cdur[c]

    per = {}
    for c in order:
        tf = ls[c] - es[c]
        ff = min((es[s] for s in succ[c]), default=makespan) - ef[c]
        crit = abs(tf) < EPS and cdur[c] > 0
        for n in g["members"][c]:
            per[n] = {"es": es[c], "ef": ef[c], "ls": ls[c], "lf": lf[c],
                      "total_float": round(tf, 9), "free_float": round(ff, 9),
                      "critical": crit, "wave": wave_of[c], "component": c,
                      "done": n in done}

    # One zero-float chain: start at a critical source, follow critical successors whose ES == EF.
    path = []
    starts = [c for c in order if not pred[c] and abs(ls[c] - es[c]) < EPS and cdur[c] > 0]
    if not starts:  # all remaining critical work sits behind done prerequisites
        starts = [c for c in order if abs(ls[c] - es[c]) < EPS and cdur[c] > 0
                  and all(cdur[p] == 0 for p in pred[c])]
    c = min(starts, key=lambda x: (es[x], x)) if starts else None
    while c is not None:
        path.append(c)
        nxt = [s for s in sorted(succ[c]) if abs(ls[s] - es[s]) < EPS and abs(es[s] - ef[c]) < EPS]
        c = nxt[0] if nxt else None
    return {"makespan": makespan, "nodes": per, "critical_path": path,
            "critical_set": sorted(n for n, v in per.items() if v["critical"]),
            "cycles": g["cycles"], "waves": len(waves)}


# ---------------------------------------------------------------- uncertainty

def criticality(nodes: list[str], edges: list[tuple[str, str]], spread: dict | None = None,
                done=frozenset(), default=(0.5, 1.0, 3.0), samples: int = 400, seed: int = 7) -> dict:
    """Monte Carlo criticality index: share of samples in which a node has zero float.

    ``spread[n] = (low, mode, high)`` triangular durations; ``default`` for the rest
    (right-skewed: work runs late more often than early). Also returns the makespan
    P10/P50/P90. A node with index near 1 is critical whatever the estimates;
    near 0.5 means the path choice depends on the estimates.
    """
    spread = spread or {}
    rng = random.Random(seed)
    hits = defaultdict(int)
    spans = []
    open_nodes = [n for n in nodes if n not in done]
    for _ in range(samples):
        dur = {n: rng.triangular(*(lambda t: (t[0], t[2], t[1]))(spread.get(n, default)))
               for n in open_nodes}
        r = cpm(nodes, edges, dur, done=done)
        spans.append(r["makespan"])
        for n in r["critical_set"]:
            hits[n] += 1
    spans.sort()

    def q(p):
        return spans[min(len(spans) - 1, int(p * len(spans)))] if spans else 0.0
    return {"index": {n: round(hits[n] / samples, 4) for n in sorted(open_nodes)},
            "makespan": {"p10": q(0.10), "p50": q(0.50), "p90": q(0.90)}, "samples": samples}


# ---------------------------------------------------------------- unlocking

def unlock(nodes: list[str], edges: list[tuple[str, str]], done=frozenset(), relief: bool = True) -> dict:
    """What closing each open node releases.

    ``ready_now``: open nodes whose prerequisites are all done (the frontier).
    ``releases[n]``: open nodes that become ready the moment n closes (n is their
    last open prerequisite). ``relief[n]``: open nodes that transitively wait on n,
    from the canonical ``issue_rank.unblock_pressure`` (one BFS per node, so
    quadratic on large graphs; ``relief=False`` skips it and returns ``{}``).
    """
    done = set(done)
    open_set = [n for n in nodes if n not in done]
    pred = defaultdict(set)
    for a, b in edges:
        pred[b].add(a)
    ready = sorted(n for n in open_set if not (pred[n] - done))
    releases = {n: [] for n in open_set}
    for w in open_set:
        left = pred[w] - done
        if len(left) == 1:  # w waits on exactly one open node: closing it releases w
            (n,) = left
            releases[n].append(w)
    for n in releases:
        releases[n].sort()
    rel_map = {}
    if relief:
        ir_dir = str(MC / "issue_rank")
        added = ir_dir not in sys.path
        if added:  # issue_rank imports its siblings (title_taxonomy, issue_math) by name
            sys.path.insert(0, ir_dir)
        try:
            ir = _load("issue_rank_for_cpath", MC / "issue_rank" / "issue_rank.py")
        finally:
            if added:
                sys.path.remove(ir_dir)
        inodes = {n: {"open": n not in done} for n in nodes}
        iedges = [{"source": b, "target": a, "kind": "DEPENDS_ON"} for a, b in edges]
        full = ir.unblock_pressure(inodes, iedges)
        rel_map = {n: full[n] for n in open_set}
    return {"ready_now": ready, "releases": releases, "relief": rel_map}


# ---------------------------------------------------------------- back-pressure

BP_SCHEMA = "jade.cpath.backpressure.v1"


def backpressure(queue: list[dict], pca: dict | None, bt: dict | None, crosswalk: dict | None = None,
                 base_wip: int = 6, min_bt_pairs: int = 5, min_pca_rows: int = 10,
                 max_boost: float = 0.5) -> dict:
    """Reverse pressure from the PCA/BT analytics onto the BD queue.

    * BT -> priority: each queue item's class maps (``crosswalk``) to a BT intervention
      type; its weight is 1 + max_boost * (normalised BT score - 0.5) * 2, bounded to
      [1 - max_boost, 1 + max_boost]. Classes without a mapping stay at 1.0.
    * PCA -> WIP cap: the queue-friction share (|queue_delay_s| loading x explained
      variance, summed over components) cuts the work-in-progress cap:
      wip = max(1, round(base_wip * (1 - friction))).

    Fail-neutral: if the evidence is too thin (fewer than ``min_bt_pairs`` measured
    pairs, BT not PASS, fewer than ``min_pca_rows`` PCA rows) or no crosswalk exists,
    that channel is HOLD and contributes nothing. Every HOLD names its reason, so the
    pressure is never fabricated from a 2-pair or 5-row sample.
    """
    reasons, weights = [], {}
    bt_ok = False
    frontier = (bt or {}).get("current_frontier") or {}
    pairs = frontier.get("pair_count") or 0
    status = (frontier.get("result") or {}).get("status")
    scores = (frontier.get("result") or {}).get("scores") or {}
    if status != "PASS_OBSERVED_BT":
        reasons.append(f"BT_HOLD: status {status!r}")
    elif pairs < min_bt_pairs:
        reasons.append(f"BT_HOLD: {pairs} measured pairs < {min_bt_pairs}")
    elif not crosswalk:
        reasons.append("BT_HOLD: no BD-class -> BT-intervention crosswalk supplied")
    else:
        bt_ok = True
        lo, hi = min(scores.values()), max(scores.values())
        span = (hi - lo) or 1.0
        for cls, iv in sorted(crosswalk.items()):
            if iv in scores:
                z = (scores[iv] - lo) / span
                weights[cls] = round(1 + max_boost * (z - 0.5) * 2, 4)

    pca_ok, friction = False, 0.0
    rows = (pca or {}).get("row_count") or 0
    if rows < min_pca_rows:
        reasons.append(f"PCA_HOLD: {rows} rows < {min_pca_rows}")
    else:
        pca_ok = True
        for comp in (pca or {}).get("components") or []:
            friction += abs(comp["loadings"].get("queue_delay_s", 0.0)) * comp["explained_variance_ratio"]
        friction = min(max(friction, 0.0), 0.9)
    wip = max(1, round(base_wip * (1 - friction))) if pca_ok else base_wip

    items = []
    for it in queue:
        w = weights.get(it.get("class"), 1.0) if bt_ok else 1.0
        items.append({**it, "bp_weight": w, "bp_priority": round(float(it.get("priority_score", 1.0)) * w, 6)})
    items.sort(key=lambda x: (-x["bp_priority"], str(x.get("id"))))
    return {"schema": BP_SCHEMA,
            "status": "APPLIED" if (bt_ok or pca_ok) else "NEUTRAL_HOLD",
            "channels": {"bt": "APPLIED" if bt_ok else "HOLD", "pca": "APPLIED" if pca_ok else "HOLD"},
            "evidence": {"bt_pairs": pairs, "bt_status": status, "pca_rows": rows,
                         "min_bt_pairs": min_bt_pairs, "min_pca_rows": min_pca_rows},
            "reasons": reasons, "class_weights": weights, "queue_friction": round(friction, 4),
            "wip_cap": wip, "base_wip": base_wip, "queue": items}


# ---------------------------------------------------------------- scheduling pilot

POLICIES = ("FIFO", "PRIORITY", "CPATH", "UNLOCK", "COMBO")


def simulate(nodes: list[str], edges: list[tuple[str, str]], duration: dict | None = None,
             workers: int = 4, policy: str = "COMBO", done=frozenset(), age: dict | None = None,
             priority: dict | None = None, wip_cap: int | None = None, default: float = 1.0,
             relief_limit: int = 5000) -> dict:
    """List-scheduling simulation of ``workers`` parallel agents clearing the DAG.

    Policies pick among ready nodes:
      FIFO     oldest first (``age``: larger = older)
      PRIORITY highest ``priority`` first
      CPATH    least total float first (critical path first)
      UNLOCK   most immediate releases, then most transitive relief
      COMBO    least float, then most releases, then priority (the multiplied vector)
    ``wip_cap`` (from back-pressure) limits concurrent work below ``workers``.
    Returns makespan, mean flow time (average completion time: lower = value earlier)
    and the time the first previously-blocked node became ready.
    """
    if policy not in POLICIES:
        raise ValueError(f"unknown policy {policy}")
    duration, age, priority = duration or {}, age or {}, priority or {}
    done = set(done)
    g = condense(nodes, edges)
    members, cedges = g["members"], g["edges"]
    cids = sorted(members)
    cdur = {c: sum(0.0 if n in done else float(duration.get(n, default)) for n in members[c]) for c in cids}
    work = [c for c in cids if cdur[c] > 0]
    pred, succ = defaultdict(set), defaultdict(set)
    for a, b in cedges:
        pred[b].add(a)
        succ[a].add(b)
    base = cpm(cids, cedges, cdur)
    tf = {c: base["nodes"][c]["total_float"] for c in cids}
    ul = unlock(cids, cedges, done={c for c in cids if cdur[c] == 0}, relief=len(cids) <= relief_limit)
    rel = {c: len(ul["releases"].get(c, [])) for c in cids}
    relief = ul["relief"]  # empty above relief_limit: UNLOCK then ranks on immediate releases only

    def key(c):
        a = -max((age.get(n, 0) for n in members[c]), default=0)
        p = -max((priority.get(n, 0) for n in members[c]), default=0)
        if policy == "FIFO":
            return (a, c)
        if policy == "PRIORITY":
            return (p, a, c)
        if policy == "CPATH":
            return (tf[c], p, c)
        if policy == "UNLOCK":
            return (-rel.get(c, 0), -relief.get(c, 0), p, c)
        return (tf[c], -rel.get(c, 0), -relief.get(c, 0), p, c)

    cap = min(workers, wip_cap) if wip_cap else workers
    finished = {c for c in cids if cdur[c] == 0}
    remaining = {c: len(pred[c] - finished) for c in cids}
    initially_blocked = {c for c in work if remaining[c] > 0}
    keys = {c: key(c) for c in work}  # static keys: float and releases come from the plan
    ready = [(keys[c], c) for c in work if remaining[c] == 0]
    heapq.heapify(ready)
    running = []  # heap of (finish_time, cid)
    t, completion, first_unlock = 0.0, {}, None
    while ready or running:
        while ready and len(running) < cap:
            _, c = heapq.heappop(ready)
            heapq.heappush(running, (t + cdur[c], c))
        t, c = heapq.heappop(running)
        completion[c] = t
        for s in sorted(succ[c]):
            remaining[s] -= 1
            if remaining[s] == 0 and cdur[s] > 0:
                heapq.heappush(ready, (keys[s], s))
                if s in initially_blocked and first_unlock is None:
                    first_unlock = t
    n_items = sum(len(members[c]) for c in work)
    flow_t = sum(completion[c] * len(members[c]) for c in work) / n_items if n_items else 0.0
    return {"policy": policy, "workers": workers, "wip_cap": cap, "makespan": round(t, 6),
            "mean_flow_time": round(flow_t, 6), "first_unlock": first_unlock,
            "lower_bound": round(max(base["makespan"], sum(cdur.values()) / cap if cap else 0), 6),
            "items": n_items}


def synergy(results: dict[str, dict], metric: str = "mean_flow_time", baseline: str = "FIFO") -> dict:
    """Do the attack vectors add or multiply?

    gain(p) = 1 - metric(p)/metric(baseline). With independent single-vector gains
    g1, g2 the additive prediction is g1 + g2 and the multiplicative one
    1 - (1-g1)(1-g2). ``interaction`` = observed COMBO gain minus the multiplicative
    prediction: > 0 synergy (more than multiplying), < 0 overlap (the vectors pull
    the same items forward).
    """
    b = results[baseline][metric]
    gain = {p: (1 - r[metric] / b) if b else 0.0 for p, r in results.items()}
    g1, g2 = gain.get("CPATH", 0.0), gain.get("UNLOCK", 0.0)
    mult = 1 - (1 - g1) * (1 - g2)
    obs = gain.get("COMBO", 0.0)
    return {"metric": metric, "gain": {p: round(v, 4) for p, v in gain.items()},
            "additive_prediction": round(g1 + g2, 4), "multiplicative_prediction": round(mult, 4),
            "observed_combo": round(obs, 4), "interaction": round(obs - mult, 4),
            "verdict": ("SYNERGY" if obs - mult > 0.01 else "OVERLAP" if obs - mult < -0.01 else "MULTIPLICATIVE")}


def random_dag(n: int, avg_deg: float = 2.0, width: int | None = None, seed: int = 1):
    """Layered random DAG for scale tests: edges only go to later ids within a window."""
    rng = random.Random(seed)
    width = width or max(4, int(math.sqrt(n)))
    names = [f"N{i:06d}" for i in range(n)]
    edges = set()
    for i in range(1, n):
        for _ in range(rng.randint(0, int(2 * avg_deg))):
            j = rng.randint(max(0, i - width), i - 1)
            edges.add((names[j], names[i]))
    return names, sorted(edges)
