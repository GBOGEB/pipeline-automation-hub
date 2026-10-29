#!/usr/bin/env python3
"""Dependency-free graph and rank statistics for issue_rank.

Pure functions over plain dicts and lists: strongly connected components
(dependency deadlocks), blocker chains on the condensation DAG, exact Poisson
intervals for flow rates, and rank statistics for the Monte Carlo stability
check. None of them reads GitHub or the clock. PageRank, betweenness and
components stay in issue_rank.py (their owner, AGENTS.md).

gg_MATH (GBOGEB/gg_MATH) owns the federation's statistical kernels; it has no
SCC, chain or Poisson interval today. These are upstream candidates (README
roadmap) and stay here, next to their only consumer, until gg_MATH binds them.
"""
from __future__ import annotations

import math
from collections import defaultdict, deque


# ---------------------------------------------------------------- structure


def strongly_connected(nodes, succ):
    """Tarjan's SCCs (iterative). Returns every component, each sorted, in discovery order."""
    member = set(nodes)
    index, low, on, stack, out = {}, {}, set(), [], []
    counter = 0
    for root in nodes:
        if root in index:
            continue
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on.add(root)
        work = [(root, iter(sorted(w for w in succ.get(root, ()) if w in member)))]
        while work:
            v, it = work[-1]
            pushed = False
            for w in it:
                if w not in index:
                    index[w] = low[w] = counter
                    counter += 1
                    stack.append(w)
                    on.add(w)
                    work.append((w, iter(sorted(x for x in succ.get(w, ()) if x in member))))
                    pushed = True
                    break
                if w in on:
                    low[v] = min(low[v], index[w])
            if pushed:
                continue
            work.pop()
            if work:
                u = work[-1][0]
                low[u] = min(low[u], low[v])
            if low[v] == index[v]:
                comp = []
                while True:
                    w = stack.pop()
                    on.discard(w)
                    comp.append(w)
                    if w == v:
                        break
                out.append(sorted(comp))
    return out


def blocker_chains(nodes, succ):
    """Longest chains of ``succ`` (waiter -> blocker) through each node, cycles condensed.

    ``below[k]``: open items that must close, one after another, before k can
    close (the longest blocker chain under k; a cycle of size s counts s - 1 for
    its own members). ``above[k]``: the longest chain of waiters on top of k.
    ``critical``: the nodes of one longest chain overall, top waiter first.
    """
    nodes = sorted(nodes)
    comps = strongly_connected(nodes, succ)
    cid = {k: i for i, c in enumerate(comps) for k in c}
    size = [len(c) for c in comps]
    down, up = defaultdict(set), defaultdict(set)
    for k in nodes:
        for w in succ.get(k, ()):
            if w in cid and cid[w] != cid[k]:
                down[cid[k]].add(cid[w])
                up[cid[w]].add(cid[k])
    indeg = {c: len(up[c]) for c in range(len(comps))}
    order, q = [], deque(sorted(c for c, n in indeg.items() if n == 0))
    while q:
        c = q.popleft()
        order.append(c)
        for x in sorted(down[c]):
            indeg[x] -= 1
            if indeg[x] == 0:
                q.append(x)
    below_c, nxt = [0] * len(comps), [None] * len(comps)
    for c in reversed(order):
        best, arg = 0, None
        for x in sorted(down[c]):
            v = size[x] + below_c[x]
            if v > best:
                best, arg = v, x
        below_c[c], nxt[c] = best, arg
    above_c = [0] * len(comps)
    for c in order:
        for x in down[c]:
            above_c[x] = max(above_c[x], above_c[c] + size[c])
    below = {k: below_c[cid[k]] + size[cid[k]] - 1 for k in nodes}
    above = {k: above_c[cid[k]] for k in nodes}
    critical = []
    if order:
        start = max(order, key=lambda c: (below_c[c] + size[c] + above_c[c] if not up[c] else -1, -c))
        c = start
        while c is not None:
            critical += comps[c]
            c = nxt[c]
    return {"below": below, "above": above, "critical": critical,
            "cycles": [c for c in comps if len(c) > 1]}

# ---------------------------------------------------------------- statistics


def _poisson_cdf(k, lam):
    """P(X <= k) for X ~ Poisson(lam), summed in log space (no underflow for large lam)."""
    if k < 0:
        return 0.0
    if lam <= 0:
        return 1.0
    logs = [-lam + i * math.log(lam) - math.lgamma(i + 1) for i in range(k + 1)]
    top = max(logs)
    return min(1.0, math.exp(top) * sum(math.exp(x - top) for x in logs))


def poisson_interval(k, level=0.90):
    """Exact (Garwood) two-sided interval for a Poisson mean after observing ``k`` events."""
    if type(k) is not int or k < 0 or not 0 < level < 1:
        raise ValueError("poisson_interval needs an integer k >= 0 and 0 < level < 1")
    a = (1 - level) / 2

    def solve(f, lo, hi):  # f increasing in lam on [lo, hi]
        for _ in range(200):
            mid = (lo + hi) / 2
            if f(mid) < 0:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    span = k + 20 * math.sqrt(k + 1) + 20
    lower = 0.0 if k == 0 else solve(lambda lam: (1 - _poisson_cdf(k - 1, lam)) - a, 0.0, float(k))
    upper = solve(lambda lam: a - _poisson_cdf(k, lam), float(k), span)
    return lower, upper


def quantile(values, q):
    """Linear-interpolated quantile (type 7); ``None`` for an empty list."""
    xs = sorted(values)
    if not xs:
        return None
    pos = (len(xs) - 1) * q
    i = int(math.floor(pos))
    j = min(i + 1, len(xs) - 1)
    return xs[i] + (xs[j] - xs[i]) * (pos - i)


def average_ranks(values):
    """1-based ranks; tied values share their average rank."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for x in order[i:j + 1]:
            ranks[x] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def spearman(a, b):
    """Spearman's rho with average ranks; ``None`` when either side is constant or n < 2."""
    if len(a) != len(b) or len(a) < 2:
        return None
    ra, rb = average_ranks(a), average_ranks(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra)
    vb = sum((y - mb) ** 2 for y in rb)
    return cov / math.sqrt(va * vb) if va > 0 and vb > 0 else None


def kendall_tau_b(a, b):
    """Kendall's tau-b (tie-corrected), O(n^2); ``None`` when undefined."""
    n = len(a)
    if n != len(b) or n < 2:
        return None
    conc = disc = ties_a = ties_b = 0
    for i in range(n):
        for j in range(i + 1, n):
            da, db = a[i] - a[j], b[i] - b[j]
            if da == 0 and db == 0:
                continue
            if da == 0:
                ties_a += 1
            elif db == 0:
                ties_b += 1
            elif (da > 0) == (db > 0):
                conc += 1
            else:
                disc += 1
    denom = math.sqrt((conc + disc + ties_a) * (conc + disc + ties_b))
    return (conc - disc) / denom if denom else None


def dirichlet(rng, alphas):
    """One Dirichlet draw from ``random.Random`` (normalised gamma variates)."""
    g = [rng.gammavariate(a, 1.0) for a in alphas]
    s = sum(g)
    return [x / s for x in g] if s > 0 else [1.0 / len(g)] * len(g)
