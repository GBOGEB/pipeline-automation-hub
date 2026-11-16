#!/usr/bin/env python3
"""C-PATH pilot: critical path, unlock leverage, back-pressure and attack-vector scaling.

Three graph sources, one method (cpath.py):

  gates   H01..H12 release-gate DAG (ROLLING5_POLICY) with each FOCUS5 repo's statuses
          from a FOCUS5 point-release pulse; PASS = done, FAIL/UNKNOWN = open (fail closed).
  issues  live open issues + PRs of the JADE top-5 read over REST into issue_rank's own
          snapshot format, so the canonical ``build_graph`` / ``dep_edges`` parse the
          dependencies (DEPENDS_ON, checklist CHILD, PARENT, "blocked by", "closes").
  scale   layered random DAGs (1e3..1e5 nodes) for runtime and policy behaviour at size.

Outputs one JSON (``jade.cpath.pilot.v1``). Private repositories are aggregated: counts
only, no item ids or titles (same rule as issue_rank.redact).

REST limits: issue comments and timeline cross-references are not read (cost); edges
come from bodies and PR closing references. Unresolved references stay unknown-open.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cpath  # noqa: E402

JADE = HERE.parent
QPS = HERE.parents[1] / "qps-triage-ultra"
OWNER = "GBOGEB"
JADE5 = ("ABACUS", "CODEX", "pipeline-automation-hub", "cryoplant-project", "gg_MATH")
SCHEMA = "jade.cpath.pilot.v1"
WORKERS = (1, 2, 4, 8, 16)


def _issue_rank():
    d = str(HERE.parents[1] / "issue_rank")
    sys.path.insert(0, d)
    try:
        return cpath._load("issue_rank_for_cpath", Path(d) / "issue_rank.py")
    finally:
        sys.path.remove(d)


# ---------------------------------------------------------------- gates

def gate_pilot(pulse_path: Path) -> dict:
    prereqs = json.loads((JADE / "data" / "ROLLING5_POLICY.json").read_text(encoding="utf-8"))["gate_prerequisites"]
    pulse = json.loads(pulse_path.read_text(encoding="utf-8"))
    nodes = sorted(prereqs)
    edges = [(p, g) for g, ps in prereqs.items() for p in ps]
    full = cpath.cpm(nodes, edges)
    out = {"source": pulse_path.relative_to(HERE.parents[2]).as_posix(), "nodes": len(nodes), "edges": len(edges),
           "full_critical_path": full["critical_path"], "full_critical_set": full["critical_set"],
           "full_makespan": full["makespan"], "repos": []}
    for row in pulse["rows"]:
        st = {x["id"]: x["status"] for x in row["gates"]}
        done = {g for g, s in st.items() if s == "PASS"}
        r = cpath.cpm(nodes, edges, done=done)
        u = cpath.unlock(nodes, edges, done=done)
        crit = cpath.criticality(nodes, edges, done=done, samples=300)
        lever = sorted(((len(u["releases"][n]), u["relief"][n], n) for n in u["ready_now"]), reverse=True)
        out["repos"].append({
            "repo": row["repo"], "source_sha": row.get("source_sha"), "done": sorted(done),
            "open_by_status": {s: sorted(g for g, v in st.items() if v == s) for s in ("FAIL", "UNKNOWN")},
            "remaining_makespan": r["makespan"], "critical_path": r["critical_path"],
            "critical_set": r["critical_set"], "ready_now": u["ready_now"],
            "next_unlock": [{"gate": n, "releases": u["releases"][n], "relief": rel}
                            for _, rel, n in lever],
            "float": {n: v["total_float"] for n, v in r["nodes"].items() if not v["done"]},
            "criticality_index": {k: v for k, v in crit["index"].items() if v > 0},
            "makespan_p50_p90": [round(crit["makespan"]["p50"], 2), round(crit["makespan"]["p90"], 2)]})
    return out


# ---------------------------------------------------------------- issues over REST

def _gh1(path: str):
    for attempt in range(3):
        p = subprocess.run(["gh", "api", path], capture_output=True, text=True)
        if p.returncode == 0:
            return json.loads(p.stdout)
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"gh api {path} failed: {p.stderr[:200]}")  # never treat failure as empty


def _gh(path: str) -> list | dict:
    """GET with explicit page numbers (Link-header pagination uses numeric-id URLs some proxies refuse)."""
    if "per_page=" not in path:
        return _gh1(path)
    out, page = [], 1
    while True:
        chunk = _gh1(f"{path}&page={page}")
        out += chunk
        if len(chunk) < 100 or page >= 50:
            return out
        page += 1


def _iso(s):
    return s[:19] + "Z" if s else None


def rest_snapshot(repos=JADE5, owner=OWNER) -> dict:
    """Open issues and PRs in issue_rank's snapshot shape (REST, bodies only)."""
    at = datetime.now(timezone.utc).replace(microsecond=0)
    snap = {"schema": "jade.issue-rank.snapshot.rest-subset", "owner": owner,
            "fetched_at": at.strftime("%Y-%m-%dT%H:%M:%SZ"), "window": {"days": 14, "since": None},
            "repos": {}, "refs": {}, "limits": ["no_comments", "no_timeline_refs", "rest_only"]}
    for name in repos:
        meta = _gh(f"repos/{owner}/{name}")
        full = meta["full_name"]
        head = _gh(f"repos/{full}/commits/{meta['default_branch']}")["sha"]
        items = _gh(f"repos/{full}/issues?state=open&per_page=100")
        prs = {p["number"]: p for p in _gh(f"repos/{full}/pulls?state=open&per_page=100")}
        issues, plist = [], []
        for it in items:
            base = {"repo": full, "number": it["number"], "title": it["title"], "url": it["html_url"],
                    "created_at": _iso(it["created_at"]), "updated_at": _iso(it["updated_at"]),
                    "author": (it.get("user") or {}).get("login"),
                    "labels": [x["name"] for x in it.get("labels") or []], "body": it.get("body") or ""}
            if "pull_request" in it:
                p = prs.get(it["number"], {})
                plist.append({**base, "type": "PullRequest", "draft": p.get("draft"), "review_decision": None,
                              "approvals": None, "base": (p.get("base") or {}).get("ref"),
                              "head": (p.get("head") or {}).get("ref"), "head_sha": (p.get("head") or {}).get("sha"),
                              "checks": None, "closes": []})
            else:
                issues.append({**base, "type": "Issue", "closed_at": None, "state": "OPEN", "state_reason": None,
                               "assignees": [x["login"] for x in it.get("assignees") or []],
                               "milestone": (it.get("milestone") or {}).get("title"),
                               "comments_count": it.get("comments", 0), "comments": [], "refs_in": [],
                               "relations": {}, "sub_issues_summary": None, "relation_limits_reached": []})
        snap["repos"][full] = {"private": meta["private"], "default_branch": meta["default_branch"],
                               "head_sha": head, "issues": issues, "prs": plist, "closed": []}
    return snap


def resolve_stubs(snap: dict, ir, cap: int = 600) -> dict:
    """State of referenced items outside the open set (REST, one call each, capped)."""
    g = ir.build_graph(snap)
    deps = ir.dep_edges(g["edges"])
    want = sorted({k for pair in deps for k in pair if g["nodes"][k].get("stub")})[:cap]
    allowed = set(snap["repos"])

    def one(k):
        repo, num = k.rsplit("#", 1)
        if repo not in allowed:
            return k, "OUT_OF_SCOPE"
        p = subprocess.run(["gh", "api", f"repos/{repo}/issues/{num}"], capture_output=True, text=True)
        if p.returncode != 0:
            return k, None if "Not Found" in p.stdout + p.stderr else "UNKNOWN"
        d = json.loads(p.stdout)
        return k, {"type": "PullRequest" if "pull_request" in d else "Issue", "state": d["state"].upper(),
                   "created_at": _iso(d["created_at"]), "draft": d.get("draft")}
    with concurrent.futures.ThreadPoolExecutor(8) as ex:
        for k, v in ex.map(one, want):
            if isinstance(v, dict) or v is None:
                snap["refs"][k] = v
    return {"stubs_seen": len(want), "resolved": sum(isinstance(snap["refs"].get(k), dict) for k in want),
            "missing": sum(snap["refs"].get(k, 0) is None for k in want)}


def issue_pilot(snap: dict) -> tuple[dict, tuple]:
    ir = _issue_rank()
    g = ir.build_graph(snap)
    deps = ir.dep_edges(g["edges"])  # (waiter, blocker)
    nodes_all = g["nodes"]
    edges = sorted({(b, w) for w, b in deps})  # blocker -> waiter
    involved = sorted({k for e in edges for k in e})
    done = {k for k in involved if nodes_all[k].get("open") is False}
    open_items = [k for k, v in nodes_all.items() if v.get("open") and not v.get("stub")]
    universe = sorted(set(open_items) | set(involved))
    r = cpath.cpm(universe, edges, done=done)
    u = cpath.unlock(universe, edges, done=done)
    now = time.time()
    age = {k: now - (ir._ts(nodes_all[k].get("created_at")) or now) for k in universe}
    prio = {}
    for k in universe:
        p, _ = ir.priority_of(nodes_all[k])
        prio[k] = p or 0.0
    private = {full for full, rr in snap["repos"].items() if rr["private"]}

    def pub(k):
        return k.rsplit("#", 1)[0] not in private

    def show(keys):
        return [k if pub(k) else "PRIVATE" for k in keys]
    per_repo = []
    for full in snap["repos"]:
        mine = [k for k in universe if k.startswith(full + "#")]
        per_repo.append({"repo": full, "private": full in private,
                         "open_items": sum(1 for k in mine if k in open_items),
                         "in_dependency_graph": sum(1 for k in mine if k in involved),
                         "head_sha": snap["repos"][full]["head_sha"]})
    lever = sorted(((len(u["releases"][k]), u["relief"][k], k) for k in u["releases"]
                    if u["relief"][k] > 0), reverse=True)[:15]
    chain = r["critical_path"]
    out = {"items_open": len(open_items), "dependency_edges": len(edges),
           "items_in_graph": len(involved), "isolated_open": len(set(open_items) - set(involved)),
           "deadlocks": [show(c) for c in r["cycles"]], "waves": r["waves"],
           "remaining_makespan_unit": r["makespan"], "critical_path": show(chain),
           "critical_path_len": len(chain), "critical_set_size": len(r["critical_set"]),
           "balance_workers": round(len(open_items) / r["makespan"], 1) if r["makespan"] else None,
           "top_unlock": [{"item": k if pub(k) else "PRIVATE", "releases": n, "relief": rel}
                          for n, rel, k in lever],
           "per_repo": per_repo}
    return out, (universe, edges, done, age, prio)


# ---------------------------------------------------------------- attack vectors

def attack_vectors(universe, edges, done, age, prio, duration=None, workers=WORKERS) -> dict:
    out = {}
    for w in workers:
        res = {p: cpath.simulate(universe, edges, duration=duration, workers=w, policy=p, done=done,
                                 age=age, priority=prio) for p in cpath.POLICIES}
        out[str(w)] = {"results": {p: {k: r[k] for k in ("makespan", "mean_flow_time", "first_unlock")}
                                   for p, r in res.items()},
                       "lower_bound": res["FIFO"]["lower_bound"],
                       "synergy_flow": cpath.synergy(res, "mean_flow_time"),
                       "synergy_makespan": cpath.synergy(res, "makespan")}
    return out


def scale_pilot(sizes=(1000, 10000, 100000), workers=(4, 16, 64)) -> dict:
    import random
    out = {}
    for n in sizes:
        names, edges = cpath.random_dag(n, seed=n)
        rng = random.Random(n)
        dur = {k: min(20.0, rng.lognormvariate(0.0, 0.8)) for k in names}  # heavy-tailed effort
        t = time.monotonic()
        r = cpath.cpm(names, edges, dur)
        t_cpm = time.monotonic() - t
        row = {"edges": len(edges), "cpm_seconds": round(t_cpm, 3), "makespan": round(r["makespan"], 2),
               "critical_set": len(r["critical_set"]), "waves": r["waves"],
               "balance_workers": round(sum(dur.values()) / r["makespan"], 1), "policies": {}}
        if n <= 100000:
            order = names[:]
            rng.shuffle(order)  # filing age is not a topological order
            age = {k: n - i for i, k in enumerate(order)}
            prio = {k: rng.random() for k in names}
            for w in workers:
                t = time.monotonic()
                res = {p: cpath.simulate(names, edges, duration=dur, workers=w, policy=p, age=age, priority=prio)
                       for p in cpath.POLICIES}
                row["policies"][str(w)] = {
                    "seconds": round(time.monotonic() - t, 2),
                    "makespan": {p: round(x["makespan"], 2) for p, x in res.items()},
                    "mean_flow_time": {p: round(x["mean_flow_time"], 2) for p, x in res.items()},
                    "lower_bound": round(res["FIFO"]["lower_bound"], 2),
                    "synergy_flow": cpath.synergy(res, "mean_flow_time"),
                    "synergy_makespan": cpath.synergy(res, "makespan")}
        out[str(n)] = row
    return out


# ---------------------------------------------------------------- back-pressure

def backpressure_pilot() -> dict:
    pca = json.loads((QPS / "w3_measured_analytics_receipt.json").read_text(encoding="utf-8"))
    bt = json.loads((QPS / "w3_observed_bt_receipt.json").read_text(encoding="utf-8"))
    bd = json.loads((HERE.parents[1] / "v2/handoff/closeout/w11-gmic-r2-p0008/BD_B01_B46_READONLY.json").read_text(encoding="utf-8"))
    rank = {"P0": 2.0, "P1": 1.0}
    queue = [{"id": i["id"], "class": i["state"], "priority_score": rank.get(i["priority"], 0.5)}
             for i in bd["items"] if i["state"] != "DONE"]
    as_is = cpath.backpressure(queue, pca, bt)
    # What the same mechanism would do once evidence clears the gates (labelled counterfactual,
    # never written back): thresholds lowered to the evidence that exists today.
    cw = {"REVIEW_WAIT": "SEMANTIC_BOUNDARY_GUARD_REPAIR", "ACTIONABLE": "STATISTICAL_TOLERANCE_REPAIR",
          "OWNER_HOLD": "UNREPAIRED_BASELINE", "DEPENDENCY_HOLD": "UNREPAIRED_BASELINE"}
    cf = cpath.backpressure(queue, pca, bt, crosswalk=cw, min_bt_pairs=2, min_pca_rows=3)
    return {"bd_source": "BD_B01_B46_READONLY.json", "open_bd_items": len(queue),
            "as_is": {k: as_is[k] for k in ("status", "channels", "evidence", "reasons", "wip_cap")},
            "counterfactual_low_thresholds": {
                "label": "COUNTERFACTUAL_NOT_ADMITTED: thresholds lowered to the 2-pair / 5-row evidence and an "
                         "illustrative crosswalk; shows mechanism only",
                **{k: cf[k] for k in ("status", "channels", "class_weights", "queue_friction", "wip_cap")},
                "top5": [q["id"] for q in cf["queue"][:5]]}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pulse", type=Path, default=JADE / "data" / "FOCUS5_POINT_RELEASE_P0005.json")
    ap.add_argument("--no-issues", action="store_true", help="skip the live REST issue graph")
    ap.add_argument("--snapshot", type=Path, help="reuse a saved REST snapshot instead of fetching")
    ap.add_argument("--save-snapshot", type=Path)
    ap.add_argument("--sizes", default="1000,10000,100000")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    t0 = time.monotonic()
    report = {"schema": SCHEMA, "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "method": "Kahn order (lifecycle.topo_layers) + CPM forward/backward passes; SCC deadlocks condensed",
              "duration_model": "unit (unknown-not-zero); criticality uses triangular(0.5, 1, 3)",
              "gates": gate_pilot(a.pulse), "backpressure": backpressure_pilot()}
    if not a.no_issues:
        if a.snapshot:
            snap = json.loads(a.snapshot.read_text(encoding="utf-8"))
        else:
            snap = rest_snapshot()
            report["stub_resolution"] = resolve_stubs(snap, _issue_rank())
            if a.save_snapshot:
                a.save_snapshot.write_text(json.dumps(snap), encoding="utf-8", newline="\n")
        issues, (universe, edges, done, age, prio) = issue_pilot(snap)
        report["issues"] = issues
        report["issues"]["fetched_at"] = snap["fetched_at"]
        report["issues"]["limits"] = snap.get("limits")
        report["attack_vectors_issues"] = attack_vectors(universe, edges, done, age, prio)
    report["scale"] = scale_pilot(tuple(int(x) for x in a.sizes.split(",")))
    report["wall_seconds"] = round(time.monotonic() - t0, 1)
    pb = cpath._load("private_boundary", JADE / "tools" / "private_boundary.py")
    report = pb.project(report)  # aggregate-only for private repos; output is a fixed point
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=1, sort_keys=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: report[k] for k in ("schema", "wall_seconds")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
