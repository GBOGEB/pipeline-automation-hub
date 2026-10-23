#!/usr/bin/env python3
"""JADE CI/CD DAG + SIPOC: one process model, three scopes, three identity lenses.

Scopes: TOTAL (federation CI/CD process), REPO (each JADE focus repo) and
ORCHESTRATORS (hub, ABACUS, CODEX and the hub assets that federate them).
Lenses over the same nodes: FUNCTION (what the step means), SHA (exact commit
or sha256 snapshot it was observed on) and OID (git blob id of the python /
workflow / data object that produces it, plus the symbol inside it).

Read-only projection. Reuses tools/rolling5.py for the pulse ledger, gate DAG
and SOURCE_RED; never mutates GitHub; UNKNOWN is never PASS.

  python tools/cicd_dag.py --write     regenerate site/cicd_dag.{json,_crosswalk.csv} + diagrams
  python tools/cicd_dag.py --check     fail if committed outputs drift
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import math
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = "data/CICD_DAG_POLICY.json"
OUT_JSON = "site/cicd_dag.json"
OUT_CSV = "site/cicd_dag_crosswalk.csv"
MMD = "diagrams/CICD_DAG_{scope}_{lens}.mmd"
MMD_SCOPES = ("TOTAL", "ORCHESTRATORS")
LENSES = ("FUNCTION", "SHA", "OID")
SCHEMA = "jade.temple.cicd_dag.projection/1.0"
HUB_REPO = "GBOGEB/pipeline-automation-hub"
PASS, FAIL, UNKNOWN = "PASS", "FAIL", "UNKNOWN"
SHA40 = re.compile(r"[0-9a-f]{40}")
SHA64 = re.compile(r"[0-9a-f]{64}")
SIPOC_ORDER = "SIPOC"
KIND_MIN_LAYER = {"S": 0, "I": 1, "P": 2, "O": 3}
LAYERING_EDGES = {"FLOW", "PREREQ", "FEDERATION", "CONTAINS"}

_spec = importlib.util.spec_from_file_location(
    "jade_rolling5", Path(__file__).with_name("rolling5.py"))
r5 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(r5)


# --- Identity -------------------------------------------------------------

def git_blob_oid(data: bytes) -> str:
    """Git blob object id: sha1 of b'blob <len>\\0' + content.

    Text CRLF is folded to LF so a Windows autocrlf checkout yields the OID
    git stores; content with a NUL byte is treated as binary and kept as is.
    """
    if b"\0" not in data:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def bind_objects(hub: Path, objects: list[dict]) -> dict[str, dict]:
    """Bind every declared object to its blob OID; fail closed on drift."""
    out = {}
    for obj in objects:
        path = hub / obj["path"]
        if not path.is_file():
            raise ValueError(f"object {obj['id']} missing: {obj['path']}")
        data = path.read_bytes()
        symbol = obj.get("symbol")
        if symbol and not re.search(
                rb"^def " + re.escape(symbol.encode()) + rb"\(", data, re.M):
            raise ValueError(f"object {obj['id']} has no def {symbol}()")
        out[obj["id"]] = {**obj, "oid": git_blob_oid(data)}
    return out


def _binding(obj_id, path, symbol, oid, status, at=None, jade_oid=None) -> dict:
    return {"object": obj_id, "path": path, "symbol": symbol, "oid": oid,
            "status": status, "at": at, "jade_oid": jade_oid}


def oid_binding(obj: dict) -> dict:
    return _binding(obj["id"], obj["path"], obj.get("symbol"), obj["oid"], "BOUND")


def path_binding(hub: Path, repo: str, rel: str, census: dict | None = None) -> dict:
    """OID of a repo path: local checkout for the hub, census HEAD for the rest."""
    if repo != HUB_REPO:
        return (census_binding(census, repo, rel)
                or _binding(None, f"{repo}:{rel}", None, None, "EXTERNAL_UNOBSERVED"))
    p = hub / rel
    if not p.is_file():
        return _binding(None, rel, None, None, "NOT_IN_CHECKOUT")
    return _binding(None, rel, None, git_blob_oid(p.read_bytes()), "BOUND")


# --- DevOps census (peer N+9 input) ---------------------------------------

def load_census(root: Path, policy: dict) -> dict | None:
    """Load the pinned census and index every path to (blob, jade oid, kind).

    Fails closed when the census digest, the objects back-reference, the schema
    or the read-only authority flags drift from the policy pin.
    """
    cfg = policy.get("devops_census")
    if not cfg:
        return None
    raw_c, raw_o = (root / cfg["census"]).read_bytes(), (root / cfg["objects"]).read_bytes()
    census, objects = json.loads(raw_c), json.loads(raw_o)
    if census.get("schema") != cfg["schema"] or census.get("digest_sha256") != cfg["digest_sha256"]:
        raise ValueError("devops census digest/schema drift from policy pin")
    if objects.get("census_digest_sha256") != cfg["digest_sha256"]:
        raise ValueError("devops objects are not bound to the pinned census")
    auth = census.get("authority", {})
    if auth.get("authority_transfer") is not False or auth.get("merge_admission") != "HOLD":
        raise ValueError("devops census claims authority")
    cols = objects["columns"]
    index = {}
    for r in census["repos"]:
        name, paths = _short(r["repo"]), {}
        objs = objects["repos"].get(r["repo"], {})
        for rec in (dict(zip(cols["test_files"], x)) for x in objs.get("test_files", [])):
            paths[rec["path"]] = (rec["blob_oid"], f"jade:file:{name}:{rec['path']}", "test")
        for rec in (dict(zip(cols["py_modules"], x)) for x in objs.get("py_modules", [])):
            paths[rec["path"]] = (rec["blob_oid"], f"jade:py:{name}:{rec['dotted']}", "python")
        for items in r.get("evidence", {}).values():
            for ev in items:
                paths[ev["path"]] = (ev["blob_oid"], ev["oid"], ev["kind"])
        for root_red in (r.get("red_trace") or {}).get("first_red_roots", []):
            if root_red.get("blob_oid"):
                paths.setdefault(root_red["path"], (root_red["blob_oid"],
                                                    f"jade:wf:{name}:{root_red['path']}", "workflow"))
        names = {}
        for w in r.get("workflows", []):
            paths[w["path"]] = (w["blob_oid"], w["oid"], "workflow")
            names.setdefault(w["name"], w["path"])
        index[r["repo"]] = {"head": r.get("head_sha"), "paths": paths, "names": names}
    return {"census": census, "index": index,
            "repos": {r["repo"]: r for r in census["repos"]},
            "digests": {cfg["census"]: hashlib.sha256(raw_c).hexdigest(),
                        cfg["objects"]: hashlib.sha256(raw_o).hexdigest()}}


def census_binding(census: dict | None, repo: str, rel: str) -> dict | None:
    ent = (census or {}).get("index", {}).get(repo)
    hit = ent and ent["paths"].get(rel)
    if not hit or not hit[0]:
        return None
    return _binding(None, f"{repo}:{rel}", None, hit[0], "BOUND_AT_CENSUS_HEAD",
                    at=ent["head"], jade_oid=hit[1])


def census_workflow(census: dict | None, repo: str, name: str) -> dict | None:
    ent = (census or {}).get("index", {}).get(repo)
    path = ent and ent["names"].get(name)
    return census_binding(census, repo, path) if path else None


def stage_status(stage: dict) -> str:
    """State of the stage's next blocker, not a verdict on the attained level.

    A census level is attainment (highest fully passed tier); the colour follows
    the first probe above it, so an UNKNOWN blocker stays UNKNOWN. No blocker
    means L5: every probe passed.
    """
    if stage["probes"] and (stage["pass"] == stage["probes"] or stage.get("next_blocker") is None):
        return PASS
    blocker = (stage.get("next_blocker") or {}).get("state")
    return FAIL if blocker == FAIL else UNKNOWN


def add_lifecycle(g: "Graph", census: dict, stages: dict, *, fleet: bool,
                  feed_from: str, loop_target: str | None) -> None:
    """S0..S9 chain: FEEDFORWARD edges layer it, S9 -> S0 is TEMPORAL, and each
    stage crosswalks to the H gates it evidences (non-H gates stay text)."""
    life = census["census"]["lifecycle"]
    level_status = g.policy["lifecycle_level_status"]
    names = census["census"]["lifecycle"]["levels"]
    for st in life["stages"]:
        key, s = st["key"], stages[st["key"]]
        if fleet:
            lvl = s["median_level"]
            status = level_status[str(lvl)]
            detail = (f"median L{lvl} {names[str(lvl)]} · ≥L3 {s['repos_ge_L3']}/21 · "
                      f"completion {round(100 * s['mean_completion'])}% · {s['formalization']}")
            metrics = {k: s[k] for k in ("levels", "median_level", "mean_completion",
                                         "repos_ge_L3", "repos_ge_L4", "formalization")}
        else:
            status = stage_status(s)
            nb = s.get("next_blocker") or {}
            detail = (f"L{s['level']} {s['label']} · "
                      + (f"blocked by {nb.get('probe')} {nb.get('state')}" if nb else "all probes PASS")
                      + f" · {s['pass']}/{s['probes']} probes")
            metrics = dict(s)
        g.node(f"L.{key}", "P", "LIFECYCLE", f"{key} · {st['question'][:40]}" if fleet else key,
               status=status, phase="LIFECYCLE", producers=["LIFECYCLE"],
               oids=[_binding(None, c["path"], None, c["blob_oid"], "BOUND_AT_CENSUS_HEAD",
                              jade_oid=st["oid"]) for c in st.get("contract", []) if c.get("present")],
               detail=detail + f" · gates {', '.join(st['gates'])}", metrics=metrics)
        for gate in st["gates"]:
            if gate in g.nodes and gate.startswith("H"):
                g.edge(f"L.{key}", gate, "CROSSWALK", "stage evidences gate")
            elif gate == "P-loop" and loop_target:
                g.edge(f"L.{key}", loop_target, "CROSSWALK", "S9 control = P-loop")
    for a, b, kind in life["edges"]:
        g.edge(f"L.{a}", f"L.{b}", "TEMPORAL" if kind.startswith("FEEDBACK") else "FLOW",
               "next pulse" if kind.startswith("FEEDBACK") else "")
    g.edge(feed_from, f"L.{life['layers'][0][0]}")


def sha_ref(label: str, value: str | None) -> list[dict]:
    if value and (SHA40.fullmatch(value) or SHA64.fullmatch(value)):
        return [{"label": label, "value": value,
                 "kind": "commit" if len(value) == 40 else "sha256"}]
    return []


# --- Graph ----------------------------------------------------------------

KIND_COLOURS = ("P_PROCESS", "ISSUE_BD", "CROSSWALK")


def colour_of(flags: set[str], precedence: list[str], default: str) -> str:
    """Status colours win (CODE_PURPLE first); kind colours only colour status-free nodes."""
    for c in list(precedence) + list(KIND_COLOURS):
        if c in flags:
            return c
    return default


def layer_nodes(nodes: list[dict], edges: list[dict]) -> dict[str, int]:
    """Longest-path layering over layering edges, anchored by SIPOC kind.

    S starts at 0, I >= 1, P >= 2, O >= 3; C is pinned to the last column.
    CROSSWALK and TEMPORAL edges are drawn but never shape the layers.
    """
    ids = [n["id"] for n in nodes]
    kind = {n["id"]: n["kind"] for n in nodes}
    preds: dict[str, list[str]] = {i: [] for i in ids}
    succ: dict[str, list[str]] = {i: [] for i in ids}
    for e in edges:
        if e["type"] in LAYERING_EDGES:
            preds[e["to"]].append(e["from"])
            succ[e["from"]].append(e["to"])
    indeg = {i: len(preds[i]) for i in ids}
    ready = sorted(i for i in ids if not indeg[i])
    order = []
    while ready:
        cur = ready.pop(0)
        order.append(cur)
        for nxt in sorted(succ[cur]):
            indeg[nxt] -= 1
            if not indeg[nxt]:
                ready.append(nxt)
        ready.sort()
    if len(order) != len(ids):
        raise ValueError("cycle in layering edges: " +
                         ", ".join(sorted(set(ids) - set(order))))
    layer: dict[str, int] = {}
    for i in order:
        base = KIND_MIN_LAYER.get(kind[i], 0)
        layer[i] = max([base] + [layer[p] + 1 for p in preds[i]])
    last = max([v for i, v in layer.items() if kind[i] != "C"], default=0) + 1
    for i in ids:
        if kind[i] == "C":
            layer[i] = max(last, layer[i])
    return layer


def dag_stats(nodes: list[dict], edges: list[dict]) -> dict:
    layering = [e for e in edges if e["type"] in LAYERING_EDGES]
    has_in = {e["to"] for e in layering}
    has_out = {e["from"] for e in layering}
    layers = [n["layer"] for n in nodes]
    width = {}
    for v in layers:
        width[v] = width.get(v, 0) + 1
    return {
        "nodes": len(nodes),
        "edges": len(layering),
        "crosswalk_edges": sum(e["type"] == "CROSSWALK" for e in edges),
        "temporal_edges": sum(e["type"] == "TEMPORAL" for e in edges),
        "depth": max(layers) + 1 if layers else 0,
        "width_max": max(width.values()) if width else 0,
        "sources": sum(n["id"] not in has_in for n in nodes),
        "sinks": sum(n["id"] not in has_out for n in nodes),
        "by_sipoc": {k: sum(n["kind"] == k for n in nodes) for k in SIPOC_ORDER},
        "by_colour": dict(sorted(_count(n["colour"] for n in nodes).items())),
        "oid_coverage": _ratio(sum(any(b["oid"] for b in n["oids"]) for n in nodes),
                               len(nodes)),
        "sha_coverage": _ratio(sum(bool(n["shas"]) for n in nodes), len(nodes)),
    }


def critical_path(prereqs: dict[str, list[str]]) -> list[str]:
    """Longest prerequisite chain; ties resolve to the lowest gate id."""
    memo: dict[str, list[str]] = {}

    def chain(g: str) -> list[str]:
        if g not in memo:
            best: list[str] = []
            for need in sorted(prereqs[g]):
                c = chain(need)
                if len(c) > len(best):
                    best = c
            memo[g] = best + [g]
        return memo[g]

    paths = [chain(g) for g in sorted(prereqs)]
    return max(paths, key=len)  # max keeps the first (lowest id) on ties


def gate_frontier(status: dict[str, str], prereqs: dict[str, list[str]]) -> dict:
    ready, blocked = [], []
    for g in sorted(prereqs):
        if status.get(g) == PASS:
            continue
        if all(status.get(n) == PASS for n in prereqs[g]):
            ready.append(g)
        else:
            blocked.append(g)
    return {"ready_frontier": ready, "blocked_by_ancestor": blocked}


def _count(items) -> dict:
    out: dict = {}
    for i in items:
        out[i] = out.get(i, 0) + 1
    return out


def _ratio(n, d):
    return round(n / d, 4) if d else None


def _short(repo: str) -> str:
    return repo.split("/", 1)[-1]


class Graph:
    def __init__(self, scope: str, title: str, policy: dict, objects: dict,
                 census: dict | None = None):
        self.scope, self.title = scope, title
        self.policy, self.objects, self.census = policy, objects, census
        self.nodes: dict[str, dict] = {}
        self.edges: list[dict] = []

    def node(self, nid, kind, ntype, label, *, flags=(), default="NEUTRAL",
             status=None, phase=None, shas=(), producers=(), oids=(),
             detail="", metrics=None, url=None):
        bindings = list(oids)
        for key in producers:
            for oid_id in self.policy["node_producers"].get(key, [key]):
                if oid_id in self.objects:
                    b = oid_binding(self.objects[oid_id])
                    if b not in bindings:
                        bindings.append(b)
        for b in bindings:  # same blob in the census => same object: adopt its jade oid
            hit = census_binding(self.census, HUB_REPO, b["path"]) if b["status"] == "BOUND" else None
            if hit and hit["oid"] == b["oid"]:
                b["jade_oid"] = hit["jade_oid"]
        flags = set(flags) | ({status} if status else set())
        self.nodes[nid] = {
            "id": nid, "kind": kind, "type": ntype, "label": label,
            "status": status, "phase": phase,
            "colour": colour_of(flags, self.policy["colour_precedence"], default),
            "shas": list(shas), "oids": bindings, "detail": detail,
            "metrics": metrics or {}, "url": url,
        }

    def edge(self, src, dst, etype="FLOW", label="", state=None):
        self.edges.append({"from": src, "to": dst, "type": etype,
                           "label": label, "state": state})

    def finish(self, metrics: dict) -> dict:
        for e in self.edges:
            if e["from"] not in self.nodes or e["to"] not in self.nodes:
                raise ValueError(f"{self.scope}: dangling edge {e['from']} -> {e['to']}")
        nodes = sorted(self.nodes.values(), key=lambda n: n["id"])
        edges = sorted(self.edges, key=lambda e: (e["from"], e["to"], e["type"]))
        layers = layer_nodes(nodes, edges)
        for n in nodes:
            n["layer"] = layers[n["id"]]
        sipoc = {k: [n["id"] for n in nodes if n["kind"] == k] for k in SIPOC_ORDER}
        return {"scope": self.scope, "title": self.title, "nodes": nodes,
                "edges": edges, "sipoc": sipoc,
                "dag": dag_stats(nodes, edges), "metrics": metrics}


# --- Sources --------------------------------------------------------------

def load_sources(root: Path, policy: dict) -> dict:
    src = {}
    for key, rel in policy["sources"].items():
        raw = (root / rel).read_bytes()
        src[key] = raw
    spec = src["p_process_spec"].decode("utf-8")
    m = re.search(r"^\s*loop:\s*\[([^\]]*)\]", spec, re.M)
    loop = [s.strip() for s in m.group(1).split(",")] if m else None
    if loop != policy["p_process_loop"]:
        raise ValueError(f"p_process.yaml EVERRED loop drift: {loop}")
    rows = list(csv.DictReader(io.StringIO(src["bd_queue"].decode("utf-8"))))
    return {
        "red_trace": json.loads(src["red_trace"]),
        "bd_queue": rows,
        "head_crosswalk": json.loads(src["head_crosswalk"]),
        "cohort_crosswalk": json.loads(src["cohort_crosswalk"]),
        "p_state": json.loads(src["p_state"]),
        "everred": json.loads(src["everred_census"]),
        "digests": {rel: hashlib.sha256(src[k]).hexdigest()
                    for k, rel in policy["sources"].items()},
    }


def everred_metrics(red_trace: dict) -> dict:
    def block(counts, traced, non_green, shared):
        red_ages = [w["age_days"] for w in non_green if w["current"] == "RED"]
        churn = (counts.get("RED_TO_GREEN", 0) + counts.get("GREEN_TO_RED", 0)
                 + counts.get("EVERRED", 0))
        return {
            "workflows_traced": traced,
            "everred": counts.get("EVERRED", 0),
            "green_to_red": counts.get("GREEN_TO_RED", 0),
            "red_to_green": counts.get("RED_TO_GREEN", 0),
            "flaky": counts.get("FLAKY", 0),
            "everred_ratio": _ratio(counts.get("EVERRED", 0), traced),
            "recovery_rate": _ratio(counts.get("RED_TO_GREEN", 0), churn),
            "flake_rate": _ratio(counts.get("FLAKY", 0), traced),
            "red_now": len(red_ages),
            "red_now_median_age_days": (round(statistics.median(red_ages), 2)
                                        if red_ages else None),
            "shared_break_roots": shared,
        }

    per_repo, all_ng, total = {}, [], {}
    for r in red_trace["repositories"]:
        per_repo[r["repository"]] = block(
            r["counts"], r["workflows_traced"], r["non_green"],
            len(r["shared_break_roots"]))
        per_repo[r["repository"]]["red_stale"] = r["currently_red_stale"]
        all_ng.extend(r["non_green"])
        for k, v in r["counts"].items():
            total[k] = total.get(k, 0) + v
    t = red_trace["totals"]
    agg = block(total, t["workflows"], all_ng,
                sum(len(r["shared_break_roots"]) for r in red_trace["repositories"]))
    agg.update({"runs": t["runs"], "red_fresh": t["red_fresh"],
                "red_stale": t["red_stale"], "pinned_red": t["pinned_red"]})
    return {"total": agg, "per_repo": per_repo}


# --- TOTAL scope ----------------------------------------------------------

def build_total(ctx: dict) -> dict:
    pol, snap, src = ctx["policy"], ctx["snapshot"], ctx["sources"]
    g = Graph("TOTAL", "Federation CI/CD process (all focus repos + P-process)",
              pol, ctx["objects"], ctx["census"])
    rows, srd, pstate = snap["rows"], ctx["rolling5"]["source_red"], src["p_state"]
    pulse = ctx["rolling5"]["pulses"][-1]
    focus = {r["repo"] for r in rows}
    traced = {r["repository"]: r for r in src["red_trace"]["repositories"]}
    heads = {h["repo"]: h for h in src["head_crosswalk"]["repositories"]}
    ever_scope = set(src["everred"]["scope"])
    repos = sorted(focus | set(pol["orchestrators"]) | set(traced)
                   | {e["from"] for e in snap["edges"]} | {e["to"] for e in snap["edges"]})
    by_repo = {r["repo"]: r for r in rows}

    for repo in repos:
        row, mode = by_repo.get(repo), pstate["repos"].get(repo, {})
        flags = set()
        if mode.get("mode") == "CODE_PURPLE":
            flags.add("CODE_PURPLE")
        if traced.get(repo, {}).get("counts", {}).get("EVERRED"):
            flags.add("EVERRED")
        sha = (row or {}).get("source_sha") or heads.get(repo, {}).get("observed_sha")
        role = ((row or {}).get("role") or pol["orchestrators"].get(repo, {}).get("what")
                or traced.get(repo, {}).get("role", ""))
        g.node(f"S.{_short(repo)}", "S", "REPO", _short(repo), flags=flags,
               shas=sha_ref("default head", sha), producers=["REPO"],
               detail=f"{role} · P-mode {mode.get('mode', 'n/a')}",
               url=f"https://github.com/{repo}")

    cc = src["cohort_crosswalk"]
    g.node("X.COHORT", "I", "CROSSWALK", "Cohort crosswalk N11 ∩ GoGREEN",
           flags={"CROSSWALK"}, producers=["OBJ.COHORT_CROSSWALK"],
           detail=f"{cc['intersection_count']}/{cc['n11_count']} overlap; "
                  f"owner single cohort={cc['owner_approved_single_cohort']}",
           metrics={"n11": cc["n11_count"], "green": cc["green_count"],
                    "intersection": cc["intersection_count"]})
    compared = sum(h["changed"] is not None for h in heads.values())
    changed = sum(h["changed"] is True for h in heads.values())
    g.node("X.HEADS", "I", "CROSSWALK", "Head crosswalk prior → observed SHA",
           flags={"CROSSWALK"}, producers=["OBJ.HEAD_CROSSWALK"],
           detail=f"{compared}/{len(heads)} heads compared (null = no prior), {changed} moved",
           metrics={"heads": len(heads), "compared": compared, "changed": changed})
    observed = sum(bool(SHA40.fullmatch(r.get("source_sha") or "")) for r in rows)
    g.node("I.SOURCE_SHA", "I", "INPUT", "Exact source SHAs",
           status=PASS if observed == len(rows) else UNKNOWN,
           shas=sha_ref(f"pulse {pulse['id']} snapshot", pulse["snapshot_sha256"]),
           producers=["I.SOURCE_SHA"], detail=f"{observed}/{len(rows)} 40-hex heads")
    native = [o for r in rows for o in r.get("native_observations", [])]
    nconc = _count(o["conclusion"] for o in native)
    g.node("I.NATIVE_RUNS", "I", "INPUT", "Native Actions runs on exact SHA",
           status=FAIL if nconc.get("failure") else UNKNOWN if nconc.get("unknown") else PASS,
           producers=["I.NATIVE_RUNS"],
           detail=" · ".join(f"{k} {v}" for k, v in sorted(nconc.items())),
           metrics=nconc)
    ev = ctx["everred"]["total"]
    g.node("I.RED_TRACE", "I", "INPUT", "Red-trace N+8 workflow history",
           flags={"EVERRED"} if ev["everred"] else set(),
           shas=sha_ref("federation digest", src["red_trace"]["digest_sha256"]),
           producers=["I.RED_TRACE"],
           detail=f"{ev['runs']:,} runs · {ev['workflows_traced']} workflows · "
                  f"{ev['everred']} EVERRED · {ev['red_now']} red now",
           metrics=ev)
    shared = sorted((s for r in src["red_trace"]["repositories"]
                     for s in r["shared_break_roots"]),
                    key=lambda s: (-s["count"], s["first_red_sha"]))
    g.node("I.FIRST_RED", "I", "FIRST_RED", "First-red commits (shared break roots)",
           flags={"ROOT_RED"}, status=FAIL,
           shas=[x for s in shared for x in sha_ref(
               f"first red ×{s['count']}", s["first_red_sha"])],
           producers=["I.FIRST_RED"],
           detail=f"{len(shared)} commits each opened ≥2 workflow break windows",
           metrics={"shared_break_roots": len(shared),
                    "workflows_broken": sum(s["count"] for s in shared)})
    em = src["everred"]["metrics"]
    g.node("I.EVERRED_CENSUS", "I", "INPUT", "EVERRED census (PR + nightly)",
           flags={"EVERRED"}, producers=["I.EVERRED_CENSUS"],
           detail=f"{em['occurrences_total']} occurrences · {em['distinct_signatures']} "
                  f"signatures · {em['roots_independent']} roots",
           metrics={k: em[k] for k in ("occurrences_total", "distinct_signatures",
                                        "roots_independent", "unmatched_signatures")})

    for repo in repos:
        s = f"S.{_short(repo)}"
        if repo in focus:
            g.edge(s, "I.SOURCE_SHA")
            g.edge(s, "I.NATIVE_RUNS")
        if repo in traced:
            g.edge(s, "I.RED_TRACE")
        if repo in ever_scope:
            g.edge(s, "I.EVERRED_CENSUS")
    g.edge("X.COHORT", "X.HEADS", "CROSSWALK", "roster join")
    g.edge("X.HEADS", "I.SOURCE_SHA", "CROSSWALK", "prior → observed")
    g.edge("I.RED_TRACE", "I.FIRST_RED", "FLOW", "break windows")

    # Gate DAG aggregated over the focus window.
    prereqs = ctx["rolling5_policy"]["gate_prerequisites"]
    common = {a["gate"] for a in srd["ranked_gates"] if a["class"] == "COMMON_CAUSE"}
    common |= {srd["core_focus"]} if srd["core_focus"] else set()
    common_unknown = {u["gate"] for u in srd["common_unknown"]}
    statuses = {r["repo"]: {x["id"]: x["status"] for x in r["gates"]} for r in rows}
    frontier = {repo: gate_frontier(st, prereqs) for repo, st in statuses.items()}
    for req in snap["requisites"]:
        gid = req["id"]
        c = _count(statuses[r][gid] for r in statuses)
        flags = set()
        if c.get(FAIL):
            flags.add("ROOT_RED" if gid in common else FAIL)
        agg = (FAIL if c.get(FAIL) else UNKNOWN if c.get(UNKNOWN) else PASS)
        ready = sorted(_short(r) for r, f in frontier.items() if gid in f["ready_frontier"])
        note = " · common unknown" if gid in common_unknown else ""
        g.node(gid, "P", "GATE", f"{gid} {req['label']}", flags=flags, status=agg,
               phase=req["phase"],
               shas=sha_ref(f"pulse {pulse['id']} snapshot", pulse["snapshot_sha256"]),
               producers=(["ROOT_RED_GATE"] if gid in common else []) + ["GATE"],
               detail=f"PASS {c.get(PASS, 0)} · FAIL {c.get(FAIL, 0)} · UNKNOWN "
                      f"{c.get(UNKNOWN, 0)}{note}" + (f" · ready: {', '.join(ready)}" if ready else ""),
               metrics={"pass": c.get(PASS, 0), "fail": c.get(FAIL, 0),
                        "unknown": c.get(UNKNOWN, 0), "ready_frontier": ready})
    for gid, needs in sorted(prereqs.items()):
        for n in needs:
            g.edge(n, gid, "PREREQ")
    g.edge("I.SOURCE_SHA", "H01")
    g.edge("I.NATIVE_RUNS", "H05")
    g.edge("I.NATIVE_RUNS", "H06")
    g.edge("I.FIRST_RED", "H10", "FLOW", "first red / negative test")

    # P-process EVERRED loop with census readings per step.
    dims = em["dims"]
    p_detail = {
        "harvest": (f"{em['occurrences_total']} occurrences → {em['distinct_signatures']} signatures",
                    {"occurrences": em["occurrences_total"]}),
        "classify": (f"{em['unmatched_signatures']} signatures unmatched to a root",
                     {"unmatched": em["unmatched_signatures"]}),
        "root": (f"{em['roots_independent']} independent roots · amplification "
                 f"{em['failure_amplification']}", {"roots": em["roots_independent"]}),
        "repair_lane": (" · ".join(f"{k} {v}" for k, v in sorted(dims["repair"].items())),
                        dims["repair"]),
        "verify_progressive": (" · ".join(f"{k} {v}" for k, v in sorted(dims["integration"].items())),
                               dims["integration"]),
        "admit": (" · ".join(f"{k} {v}" for k, v in sorted(dims["admission"].items())),
                  dims["admission"]),
        "control": (f"control-plane red {em['control_plane_red']}/{em['control_plane_probed']} · "
                    + " · ".join(f"{k} {v}" for k, v in sorted(dims["control"].items())),
                    dims["control"]),
        "recurse": (f"closure {em['root_closure_rate']} · recurrence {em['recurrence_rate']} · "
                    f"replay {em['consumer_replay_coverage']}",
                    {"root_closure_rate": em["root_closure_rate"]}),
    }
    loop = pol["p_process_loop"]
    for step in loop:
        text, m = p_detail[step]
        red = step == "control" and em["control_plane_red"]
        g.node(f"P.{step}", "P", "P_STEP", f"P · {step}",
               flags={"P_PROCESS"} | ({"EVERRED"} if red else set()),
               default="P_PROCESS", producers=["P_STEP"], detail=text, metrics=m)
    for a, b in zip(loop, loop[1:]):
        g.edge(f"P.{a}", f"P.{b}")
    g.edge(f"P.{loop[-1]}", f"P.{loop[0]}", "TEMPORAL", "next pulse")
    cp = sorted(_short(r) for r, v in pstate["repos"].items() if v["mode"] == "CODE_PURPLE")
    g.node("P.CODE_PURPLE", "P", "P_MODE", "Code Purple (acute mode)",
           flags={"CODE_PURPLE"} if cp else set(), default="P_PROCESS",
           producers=["P_STEP", "OBJ.CP_INCIDENT", "OBJ.CP_READBACK"],
           detail=f"{pstate['incident']} · lifted={pstate['lifted']} · repos: {', '.join(cp) or 'none'}",
           metrics={"repos": cp, "lifted": pstate["lifted"]})
    g.edge("P.control", "P.CODE_PURPLE", "FLOW", "E1–E3 escalate")
    g.edge("P.CODE_PURPLE", "P.root", "TEMPORAL", "H1–H3 hand-off")
    for x in pol["crosswalk_edges"]:
        g.edge(x["from"], x["to"], "CROSSWALK", x["why"])

    # Outputs and customers.
    cands = [r for r in rows if SHA40.fullmatch(r.get("candidate_sha") or "")]
    g.node("O.CANDIDATES", "O", "OUTPUT", "Disjoint candidate branches",
           status=PASS if len(cands) == len(rows) else UNKNOWN,
           shas=[x for r in cands for x in sha_ref(r["candidate_branch"], r["candidate_sha"])],
           producers=["O.CANDIDATE"], detail=f"{len(cands)}/{len(rows)} with 40-hex candidate SHA")
    bd = src["bd_queue"]
    bd_status = _count(r["status"] for r in bd)
    open_bd = sum(not r["status"].startswith("DONE") for r in bd)
    issues = sum(r.get("open_github_issues") or 0 for r in rows)
    prs = sum(r.get("open_github_prs") or 0 for r in rows)
    g.node("O.BD", "O", "ISSUE_BD", "Issue / BD burn-down",
           flags={"ISSUE_BD"}, default="ISSUE_BD", producers=["BD"],
           detail=f"BD {open_bd}/{len(bd)} open · {issues} issues · {prs} PRs (focus repos)",
           metrics={"bd_total": len(bd), "bd_open": open_bd, "bd_by_status": bd_status,
                    "open_issues": issues, "open_prs": prs})
    site = ctx["site_digests"]
    g.node("O.SITE", "O", "OUTPUT", "Deterministic JADE site artifacts",
           shas=[x for rel, d in sorted(site.items()) for x in sha_ref(rel, d)],
           producers=["O.SITE"], detail="rolling-5, red-trace and this DAG; --check parity in QA")
    h12 = sum(statuses[r]["H12"] == PASS for r in statuses)
    g.node("O.RELEASE", "O", "OUTPUT", "Point release decision",
           status=PASS if h12 == len(rows) else UNKNOWN, producers=["O.RELEASE"],
           detail=f"H12 PASS {h12}/{len(rows)} · NIRVANA {ctx['rolling5']['metrics']['nirvana_count']} · admission HOLD")
    g.node("C.OWNER", "C", "CUSTOMER", "Repository owner (GBOGEB)", producers=["C.OWNER"],
           detail="signs H03/H09/H12; only actor who may break glass")
    g.node("C.PAGES", "C", "CUSTOMER", "Single Pages publisher", producers=["C.PAGES"],
           detail="hash-checked JADE child; no second publisher")
    g.node("C.FEDERATION", "C", "CUSTOMER", "Federation consumers (CODEX / ABACUS)",
           detail="typed reference-only receipts")
    g.edge("H10", "O.CANDIDATES")
    g.edge("H11", "O.SITE")
    g.edge("H12", "O.RELEASE")
    g.edge("P.admit", "O.RELEASE", "FLOW", "admit")
    g.edge("P.root", "O.BD", "FLOW", "one root, one lane, one owner")
    g.edge("O.CANDIDATES", "C.OWNER")
    g.edge("O.BD", "C.OWNER")
    g.edge("O.RELEASE", "C.OWNER")
    g.edge("O.SITE", "C.PAGES")
    g.edge("O.SITE", "C.FEDERATION")

    census = ctx["census"]
    if census:
        c = census["census"]
        t = c["fleet"]["totals"]
        g.node("I.DEVOPS_CENSUS", "I", "INPUT", "DevOps lifecycle census N+9",
               flags={"CROSSWALK"}, producers=["CENSUS"],
               shas=sha_ref("census digest", c["digest_sha256"]),
               detail=f"{c['fleet']['reachable']}/{c['fleet']['repos']} repos · {t['wf_workflows']} workflows · "
                      f"{t['jobs']} jobs · observed {c['observed_at_utc']}",
               metrics={"repos": c["fleet"]["repos"], "workflows": t["wf_workflows"], "jobs": t["jobs"]})
        for repo in repos:
            if repo in census["repos"]:
                g.edge(f"S.{_short(repo)}", "I.DEVOPS_CENSUS")
        add_lifecycle(g, census, c["fleet"]["stages"], fleet=True,
                      feed_from="I.DEVOPS_CENSUS", loop_target="P.root")

    # Metrics.
    flat = [s for st in statuses.values() for s in st.values()]
    c = _count(flat)
    phases = {}
    for ph in pol["dmaic_order"]:
        ids = [q["id"] for q in snap["requisites"] if q["phase"] == ph]
        vals = [statuses[r][i] for r in statuses for i in ids]
        phases[ph] = {"gates": ids, "pass": vals.count(PASS), "total": len(vals),
                      "yield": _ratio(vals.count(PASS), len(vals))}
    rty = math.prod(p["yield"] or 0 for p in phases.values())
    path = critical_path(prereqs)
    depth = {}
    for repo, st in statuses.items():
        d = 0
        for gid in path:
            if st.get(gid) != PASS:
                break
            d += 1
        depth[_short(repo)] = d
    metrics = {
        "gates": {
            "pass": c.get(PASS, 0), "fail": c.get(FAIL, 0), "unknown": c.get(UNKNOWN, 0),
            "total": len(flat),
            "verified_completion_pct": round(100 * c.get(PASS, 0) / len(flat), 2),
            "measurement_debt_pct": round(100 * c.get(UNKNOWN, 0) / len(flat), 2),
            "ready_frontier": sorted(f"{_short(r)}:{x}" for r, f in frontier.items()
                                     for x in f["ready_frontier"]),
            "blocked_by_ancestor": sum(len(f["blocked_by_ancestor"]) for f in frontier.values()),
            "phase_yield": phases,
            "rolled_throughput_yield": round(rty, 6),
            "critical_path": {"gates": path, "length": len(path), "pass_depth": depth,
                              "mean_pass_depth": round(statistics.mean(depth.values()), 2)},
        },
        "source_red": {
            "core_focus": srd["core_focus"],
            "common_cause": sorted(common - {None}),
            "common_unknown": sorted(common_unknown),
            "top_instances": [f"{_short(i['repo'])}:{i['gate']}:{i['unlock_score']}"
                              for i in srd["instances"][:5]],
        },
        "everred": ev,
        "p_process": {
            "modes": _count(v["mode"] for v in pstate["repos"].values()),
            "code_purple_repos": cp, "lifted": pstate["lifted"],
            "ruleset_red": sum(v["ruleset"] == "RED" for v in pstate["repos"].values()),
            "open_roots": sum(v["open_roots"] for v in pstate["repos"].values()),
            "root_closure_rate": em["root_closure_rate"],
            "failure_amplification": em["failure_amplification"],
            "recurrence_rate": em["recurrence_rate"],
            "consumer_replay_coverage": em["consumer_replay_coverage"],
            "control_plane_red": f"{em['control_plane_red']}/{em['control_plane_probed']}",
        },
        "issue_bd": {"bd_total": len(bd), "bd_open": open_bd, "by_status": bd_status,
                     "open_issues_focus": issues, "open_prs_focus": prs},
        "crosswalk": {"heads": len(heads), "heads_compared": compared, "heads_changed": changed,
                      "cohort_intersection": cc["intersection_count"],
                      "n11": cc["n11_count"], "green": cc["green_count"]},
    }
    if census:
        metrics["devops"] = devops_fleet_metrics(census, rows)
    return g.finish(metrics)


def devops_fleet_metrics(census: dict, rows: list[dict]) -> dict:
    c = census["census"]
    t, st = c["fleet"]["totals"], c["fleet"]["stages"]
    focus = {r["repo"]: r.get("source_sha") for r in rows}
    drift = sorted(_short(r) for r, sha in focus.items()
                   if census["repos"].get(r, {}).get("head_sha") not in (None, sha))
    return {
        "observed_at_utc": c["observed_at_utc"], "digest_sha256": c["digest_sha256"],
        "repos": c["fleet"]["repos"], "reachable": c["fleet"]["reachable"],
        "workflows": t["wf_workflows"], "jobs": t["jobs"],
        "deploy_contract_core": f"{t['wf_deploy_contract_core']}/{t['wf_deploy']}",
        "deploy_env": t["wf_deploy_env"], "deploy_verified": t["wf_deploy_verified"],
        "untested_module_pct": round(100 * t["tests_py_untested"] / t["tests_py_modules"], 2),
        "py_untested": f"{t['tests_py_untested']}/{t['tests_py_modules']}",
        "unguarded_test_job_pct": round(100 * t["wf_unguarded_test_jobs"] / t["wf_tests_ci"], 2),
        "actions_pinned_pct": round(100 * t["wf_actions_pinned"] / t["wf_actions_total"], 2),
        "test_cases": t["tests_cases"], "test_files": t["tests_files"],
        "zero_case_files": t["tests_zero_case_files"],
        "lifecycle_median_level": {k: v["median_level"] for k, v in st.items()},
        "repos_ge_L3": {k: v["repos_ge_L3"] for k, v in st.items()},
        "census_sha_drift": drift,
        "outcomes_since_baseline": c["fleet"]["outcomes_since_baseline"],
    }


# --- REPO scope -----------------------------------------------------------

def build_repo(ctx: dict, row: dict) -> dict:
    pol, snap, src = ctx["policy"], ctx["snapshot"], ctx["sources"]
    repo, short = row["repo"], _short(row["repo"])
    g = Graph(f"REPO:{short}", f"{short} · CI/CD DAG and SIPOC", pol, ctx["objects"], ctx["census"])
    pstate = src["p_state"]["repos"].get(repo, {})
    traced = {r["repository"]: r for r in src["red_trace"]["repositories"]}.get(repo)
    heads = {h["repo"]: h for h in src["head_crosswalk"]["repositories"]}
    r5row = next(r for r in ctx["rolling5"]["repos"] if r["repo"] == repo)
    reds = {i["gate"]: i for i in ctx["rolling5"]["source_red"]["instances"] if i["repo"] == repo}
    # Root red here = a common-cause gate, or this repo's red that unlocks the most.
    top = max(sorted(reds.values(), key=lambda i: i["gate"]),
              key=lambda i: i["unlock_score"], default=None)  # ties: lowest gate id
    root_red = set(reds) & ctx["common_cause"] | ({top["gate"]} if top else set())
    prereqs = ctx["rolling5_policy"]["gate_prerequisites"]
    status = {x["id"]: x["status"] for x in row["gates"]}
    front = gate_frontier(status, prereqs)
    sha = row.get("source_sha")

    self_flags = {"CODE_PURPLE"} if pstate.get("mode") == "CODE_PURPLE" else set()
    if traced and traced["counts"].get("EVERRED"):
        self_flags.add("EVERRED")
    g.node("S.self", "S", "REPO", short, flags=self_flags, shas=sha_ref("default head", sha),
           producers=["REPO"], detail=f"{row['role']} · owner lane: {row['owner_lane']}",
           url=f"https://github.com/{repo}")
    inbound = [e for e in snap["edges"] if e["to"] == repo]
    outbound = [e for e in snap["edges"] if e["from"] == repo]
    for e in inbound:
        g.node(f"S.{_short(e['from'])}", "S", "REPO", _short(e["from"]),
               detail=f"{e['type']} · {e['state']} · guard: {e['guard']}",
               url=f"https://github.com/{e['from']}")
    h = heads.get(repo)
    g.node("I.SOURCE_SHA", "I", "INPUT", "Exact default-branch SHA",
           status=PASS if SHA40.fullmatch(sha or "") else UNKNOWN,
           flags={"CROSSWALK"} if h else set(),
           shas=sha_ref("source", sha) + (sha_ref("prior (crosswalk)", h["prior_sha"]) if h else []),
           producers=["I.SOURCE_SHA"],
           detail=(f"crosswalk changed={h['changed']}" if h else "not in head crosswalk"))
    g.edge("S.self", "I.SOURCE_SHA")
    for e in inbound:
        g.edge(f"S.{_short(e['from'])}", "I.SOURCE_SHA", "FEDERATION", e["type"], e["state"])
    for i, rel in enumerate(row.get("input_paths", []), 1):
        b = path_binding(ctx["hub"], repo, rel, ctx["census"])
        g.node(f"I.PATH{i}", "I", "INPUT_PATH", rel, flags={"CROSSWALK"},
               status=None, oids=[b], detail=f"object {b['status']}")
        g.edge("S.self", f"I.PATH{i}")
        g.edge(f"I.PATH{i}", "H02", "FLOW", "root source / entrypoint")
    for i, o in enumerate(row.get("native_observations", []), 1):
        st = {"success": PASS, "failure": FAIL}.get(o["conclusion"], UNKNOWN)
        wf = (census_workflow(ctx["census"], repo, o["workflow_name"])
              if repo != HUB_REPO else None)
        g.node(f"I.RUN{i}", "I", "NATIVE_RUN", o["workflow_name"], status=st,
               shas=sha_ref("run head", o.get("source_sha")), producers=["I.NATIVE_RUNS"],
               oids=[wf] if wf else (),
               detail=f"run {o.get('run_id') or 'none'} · {o['conclusion']}"
                      + (" · no release credit" if o.get("release_credit") is False else ""),
               url=o.get("evidence_url"))
        g.edge("S.self", f"I.RUN{i}")
        g.edge(f"I.RUN{i}", "H05", "FLOW", "native B0")
    if traced:
        red = sorted((w for w in traced["non_green"] if w["current"] == "RED"),
                     key=lambda w: (w["class"] != "EVERRED", -w["age_days"], w["name"]))
        lim = pol["per_repo_first_red_limit"]
        for i, w in enumerate(red[:lim], 1):
            win = w.get("window") or {}
            g.node(f"I.RED{i}", "I", "FIRST_RED", w["name"], status=FAIL,
                   flags={"EVERRED" if w["class"] == "EVERRED" else "ROOT_RED"},
                   shas=sha_ref("first red", win.get("first_red_sha"))
                   + sha_ref("last green", win.get("last_green_sha")),
                   producers=["I.FIRST_RED"],
                   oids=[path_binding(ctx["hub"], repo, w["path"], ctx["census"])],
                   detail=f"{w['class']} · {w['age_days']} d · "
                          + ("; ".join(win.get("failing", [])) or "step unknown"),
                   url=(f"https://github.com/{repo}/actions/runs/{win['first_red_run']}"
                        if win.get("first_red_run") else None))
            g.edge("S.self", f"I.RED{i}")
            g.edge(f"I.RED{i}", "H05", "FLOW", "red run")
        if len(red) > lim:
            g.node("I.RED_MORE", "I", "FIRST_RED", f"+{len(red) - lim} more red workflows",
                   flags={"ROOT_RED"}, producers=["I.RED_TRACE"],
                   detail="see red-trace ledger")
            g.edge("S.self", "I.RED_MORE")
    else:
        g.node("I.RED_GAP", "I", "FIRST_RED", "Not traced in red-trace N+8", status=UNKNOWN,
               producers=["I.RED_TRACE"], detail="no workflow history: first red is UNKNOWN")
        g.edge("S.self", "I.RED_GAP")

    labels = {q["id"]: q for q in snap["requisites"]}
    for gid in sorted(prereqs):
        st = status.get(gid, UNKNOWN)
        inst = reds.get(gid)
        flags = {"ROOT_RED"} if gid in root_red else set()
        tag = ("ready" if gid in front["ready_frontier"]
               else "blocked" if gid in front["blocked_by_ancestor"] else "done")
        gate = next(x for x in row["gates"] if x["id"] == gid)
        g.node(gid, "P", "GATE", f"{gid} {labels[gid]['label']}", flags=flags, status=st,
               phase=labels[gid]["phase"], shas=sha_ref("source", sha),
               producers=(["ROOT_RED_GATE"] if gid in root_red else []) + ["GATE"],
               detail=f"{st} · {tag}" + (f" · unlocks {inst['unlock_score']}" if inst else "")
                      + (f" · {gate.get('reason')}" if gate.get("reason") else ""),
               metrics={"frontier": tag, "unlock_score": inst["unlock_score"] if inst else 0},
               url=gate.get("evidence"))
    for gid, needs in sorted(prereqs.items()):
        for n in needs:
            g.edge(n, gid, "PREREQ")
    g.edge("I.SOURCE_SHA", "H01")

    cand = row.get("candidate_sha")
    g.node("O.CANDIDATE", "O", "OUTPUT", row.get("candidate_branch") or "no candidate branch",
           status=PASS if SHA40.fullmatch(cand or "") else UNKNOWN,
           shas=sha_ref("candidate", cand), producers=["O.CANDIDATE"],
           detail=row.get("owner_action", ""))
    g.node("O.BD", "O", "ISSUE_BD", "Blockers / issues / PRs", flags={"ISSUE_BD"},
           default="ISSUE_BD", producers=["BD"],
           detail=f"{len(row['blockers'])} blockers · {row.get('open_github_issues')} issues · "
                  f"{row.get('open_github_prs')} PRs · {pstate.get('open_roots', 0)} EVERRED roots",
           metrics={"blockers": row["blockers"], "open_issues": row.get("open_github_issues"),
                    "open_prs": row.get("open_github_prs")})
    g.node("O.RELEASE", "O", "OUTPUT", "Owner point release", status=status.get("H12", UNKNOWN),
           producers=["O.RELEASE"], detail=f"release {row.get('release')} · admission HOLD")
    g.node("C.OWNER", "C", "CUSTOMER", row["owner_lane"], producers=["C.OWNER"])
    g.edge("H10", "O.CANDIDATE")
    g.edge("H12", "O.RELEASE")
    g.edge("H08", "O.BD", "FLOW", "protection / canary blockers")
    g.edge("O.CANDIDATE", "C.OWNER")
    g.edge("O.BD", "C.OWNER")
    g.edge("O.RELEASE", "C.OWNER")
    for e in outbound:
        nid = f"C.{_short(e['to'])}"
        if nid not in g.nodes:
            g.node(nid, "C", "REPO", _short(e["to"]),
                   detail=f"{e['type']} · {e['state']} · guard: {e['guard']}",
                   url=f"https://github.com/{e['to']}")
        g.edge("H11", nid, "FEDERATION", e["type"], e["state"])

    census = ctx["census"]
    crow = (census or {}).get("repos", {}).get(repo)
    if crow:
        add_repo_census(g, census, crow, sha)

    ev = ctx["everred"]["per_repo"].get(repo)
    counts = _count(status.values())
    return g.finish({
        "devops": devops_repo_metrics(crow, sha) if crow else None,
        "gates": {"pass": counts.get(PASS, 0), "fail": counts.get(FAIL, 0),
                  "unknown": counts.get(UNKNOWN, 0), **front,
                  "source_red": sorted(reds), "root_red": sorted(root_red)},
        "golden_thread": {k: r5row["golden_thread"][k] for k in ("position", "of", "first_break")},
        "critical_path_pass_depth": ctx["pass_depth"][short],
        "everred": ev,
        "p_process": {k: pstate.get(k) for k in ("mode", "ruleset", "open_roots", "worst")}
        | {"ruleset_gaps": len(pstate.get("ruleset_gaps", []))},
        "issue_bd": {"blockers": len(row["blockers"]), "open_issues": row.get("open_github_issues"),
                     "open_prs": row.get("open_github_prs")},
    })


def add_repo_census(g: Graph, census: dict, crow: dict, focus_sha: str | None) -> None:
    """Census HEAD, test inventory, lifecycle chain and deploy contract for one repo."""
    head = crow.get("head_sha")
    same = head == focus_sha
    g.node("I.CENSUS_HEAD", "I", "CROSSWALK", "Census HEAD vs gate SHA", flags={"CROSSWALK"},
           producers=["CENSUS"], shas=sha_ref("census HEAD", head) + sha_ref("gate source", focus_sha),
           detail=("census HEAD = gate SHA" if same else
                   "census HEAD differs from gate SHA: census OIDs describe a different tree"),
           metrics={"sha_drift": not same})
    g.edge("S.self", "I.CENSUS_HEAD")
    t, z = crow["tests"], crow.get("zero_test") or {}
    top = [_binding(None, f"{crow['repo']}:{m['path']}", None, m["blob_oid"],
                    "BOUND_AT_CENSUS_HEAD", at=head, jade_oid=m["oid"])
           for m in z.get("untested_modules_top", [])[:5] if m.get("blob_oid")]
    g.node("I.TESTS", "I", "TEST_INVENTORY", "Test inventory (census)",
           status=(PASS if t["py_modules"] and not t["py_untested"] else
                   FAIL if t["py_untested"] else UNKNOWN),
           producers=["CENSUS"], oids=top,
           detail=f"{t['files']} files · {t['cases']} cases · untested modules "
                  f"{t['py_untested']}/{t['py_modules']} · zero-case files {t['zero_case_files']}",
           metrics={k: t[k] for k in ("files", "cases", "py_modules", "py_untested", "zero_case_files")})
    g.edge("S.self", "I.TESTS")
    add_lifecycle(g, census, crow["stages"], fleet=False, feed_from="I.CENSUS_HEAD", loop_target=None)
    g.edge("I.TESTS", "L.S3_TEST", "FLOW", "test inventory")
    deploys = [(w, j) for w in crow.get("workflows", []) for j in w["jobs"] if j.get("dp")]
    core = sum(all(v == PASS for v in j["dp"].values()) for _, j in deploys)
    g.node("O.DEPLOY", "O", "OUTPUT", "Deploy jobs vs DP1-DP10",
           status=(UNKNOWN if not deploys else PASS if core == len(deploys) else FAIL),
           producers=["CENSUS"],
           oids=[_binding(None, f"{crow['repo']}:{w['path']}", None, w["blob_oid"],
                          "BOUND_AT_CENSUS_HEAD", at=head, jade_oid=j["oid"]) for w, j in deploys[:5]],
           detail=(f"{len(deploys)} deploy jobs · core contract {core}/{len(deploys)}"
                   if deploys else "no deploy job found: deploy path UNKNOWN"),
           metrics={"deploy_jobs": len(deploys), "core_pass": core})
    g.edge("L.S6_DEPLOY", "O.DEPLOY")
    g.edge("O.DEPLOY", "C.OWNER")


def devops_repo_metrics(crow: dict, focus_sha: str | None) -> dict:
    wf, t = crow.get("workflow_facts") or {}, crow["tests"]
    delta = crow.get("delta") or {}
    return {
        "census_head": crow.get("head_sha"), "sha_drift": crow.get("head_sha") != focus_sha,
        "lane": crow.get("lane"),
        "levels": {k: v["level"] for k, v in crow["stages"].items()},
        "workflows": wf.get("workflows"), "tests_ci": wf.get("tests_ci"),
        "unguarded_test_jobs": wf.get("unguarded_test_jobs"),
        "deploy_jobs": wf.get("deploy"), "deploy_contract_core": wf.get("deploy_contract_core"),
        "actions_pinned": f"{wf.get('actions_pinned')}/{wf.get('actions_total')}",
        "py_untested": f"{t['py_untested']}/{t['py_modules']}", "test_cases": t["cases"],
        "ci_mttr_hours_median": (crow.get("red_trace") or {}).get("ci_mttr_hours_median"),
        "commits_since_baseline": delta.get("commits"),
        "outcomes_since_baseline": delta.get("outcomes"),
    }


# --- ORCHESTRATORS scope --------------------------------------------------

def build_orchestrators(ctx: dict) -> dict:
    pol, snap, src = ctx["policy"], ctx["snapshot"], ctx["sources"]
    g = Graph("ORCHESTRATORS", "Orchestrating and federating assets", pol, ctx["objects"],
              ctx["census"])
    traced = {r["repository"]: r for r in src["red_trace"]["repositories"]}
    pstate = src["p_state"]["repos"]
    weights = ctx["rolling5_policy"]["source_red"]["edge_weights"]
    edges = list(snap["edges"])
    repos = sorted({e["from"] for e in edges} | {e["to"] for e in edges} | set(pol["orchestrators"]))
    rid = {r: ("P." if r in pol["orchestrators"] else "S.") + _short(r) for r in repos}
    rid.update({a["id"]: a["id"] for a in pol["orchestrator_assets"]})
    rid.update({"C.PAGES": "C.PAGES", "C.OWNER": "C.OWNER"})
    all_edges = edges + pol["orchestrator_edges"]
    per = {}
    for repo in repos:
        inn = [e for e in all_edges if e["to"] == repo]
        out = [e for e in all_edges if e["from"] == repo]
        st = pstate.get(repo, {})
        ev = ctx["everred"]["per_repo"].get(repo) or {}
        per[repo] = {
            "role": pol["orchestrators"].get(repo, {}).get("role", "SATELLITE"),
            "in_degree": len(inn), "out_degree": len(out),
            "authority_bound_in": sum(e.get("state") == "AUTHORITY_BOUND" for e in inn),
            "observation_in": sum(e.get("state") == "OBSERVATION_ONLY" for e in inn),
            "weighted_in": sum(weights.get(e.get("state"), 0) for e in inn),
            "weighted_out": sum(weights.get(e.get("state"), 0) for e in out),
            "mode": st.get("mode"), "ruleset": st.get("ruleset"),
            "open_roots": st.get("open_roots"), "worst_root": st.get("worst"),
            "red_now": ev.get("red_now"), "everred": ev.get("everred"),
            "workflows_traced": ev.get("workflows_traced"),
        }
        crow = (ctx["census"] or {}).get("repos", {}).get(repo)
        if crow:
            levels = [v["level"] for v in crow["stages"].values()]
            per[repo].update({"census_head": crow.get("head_sha"),
                              "lifecycle_median_level": statistics.median(levels),
                              "lifecycle_min_level": min(levels)})
        flags = set()
        if st.get("mode") == "CODE_PURPLE":
            flags.add("CODE_PURPLE")
        if ev.get("everred"):
            flags.add("EVERRED")
        what = pol["orchestrators"].get(repo, {}).get("what") or traced.get(repo, {}).get("role", "")
        m = per[repo]
        g.node(rid[repo], "P" if repo in pol["orchestrators"] else "S", "REPO", _short(repo),
               flags=flags, producers=["REPO"],
               shas=sha_ref("default head", ctx["heads"].get(repo)),
               detail=f"{m['role']} · in {m['in_degree']} (w{m['weighted_in']}) · out {m['out_degree']} · "
                      f"mode {m['mode'] or 'n/a'} · red now {m['red_now'] if m['red_now'] is not None else 'n/a'}"
                      + (f" · {what}" if what else ""),
               metrics=m, url=f"https://github.com/{repo}")
    for a in pol["orchestrator_assets"]:
        objs = [ctx["objects"][o] for o in a["objects"]]
        g.node(a["id"], a["kind"], "ASSET", a["label"], flags={a["colour"]},
               default=a["colour"], oids=[oid_binding(o) for o in objs],
               detail=" · ".join(Path(o["path"]).name + (f"::{o['symbol']}" if o.get("symbol") else "")
                                 for o in objs))
    g.node("C.PAGES", "C", "CUSTOMER", "Single Pages publisher", producers=["C.PAGES"])
    g.node("C.OWNER", "C", "CUSTOMER", "Repository owner (GBOGEB)", producers=["C.OWNER"])
    for e in edges:
        g.edge(rid[e["from"]], rid[e["to"]], "FEDERATION", e["type"], e["state"])
    for e in pol["orchestrator_edges"]:
        g.edge(rid[e["from"]], rid[e["to"]], e["type"], e.get("label", ""), e.get("state"))
    hub_in = per[HUB_REPO]["in_degree"]
    return g.finish({
        "repos": per,
        "hub_fan_in_share": _ratio(hub_in, len(edges)),
        "authority_bound_edges": sum(e["state"] == "AUTHORITY_BOUND" for e in edges),
        "causal_root_proof_edges": sum(bool(e.get("causal_root_proof")) for e in edges),
        "assets": len(pol["orchestrator_assets"]),
        "objects_bound": sum(len(a["objects"]) for a in pol["orchestrator_assets"]),
    })


# --- Projection -----------------------------------------------------------

def project(root: Path = ROOT) -> dict:
    hub = root.parents[1]
    policy = json.loads((root / POLICY).read_text(encoding="utf-8"))
    r5_policy = json.loads((root / r5.POLICY).read_text(encoding="utf-8"))
    pairs = r5.verified_pulses(root, json.loads((root / r5.LEDGER).read_text(encoding="utf-8")))
    snapshot = pairs[-1][1]
    rolling = r5.project(root)
    sources = load_sources(root, policy)
    objects = bind_objects(hub, policy["objects"])
    census = load_census(root, policy)
    srd = rolling["source_red"]
    common = {a["gate"] for a in srd["ranked_gates"] if a["class"] == "COMMON_CAUSE"}
    path = critical_path(r5_policy["gate_prerequisites"])
    pass_depth = {}
    for r in snapshot["rows"]:
        st = {x["id"]: x["status"] for x in r["gates"]}
        d = 0
        for gid in path:
            if st.get(gid) != PASS:
                break
            d += 1
        pass_depth[_short(r["repo"])] = d
    heads = {h["repo"]: h["observed_sha"] for h in sources["head_crosswalk"]["repositories"]}
    heads.update({r["repo"]: r["source_sha"] for r in snapshot["rows"]})
    site_digests = {rel: hashlib.sha256((root / rel).read_bytes()).hexdigest()
                    for rel in ("site/rolling5.json", "site/redtrace-manifest.json")}
    ctx = {"policy": policy, "rolling5_policy": r5_policy, "snapshot": snapshot,
           "rolling5": rolling, "sources": sources, "objects": objects, "hub": hub,
           "everred": everred_metrics(sources["red_trace"]), "common_cause": common,
           "pass_depth": pass_depth, "heads": heads, "site_digests": site_digests,
           "census": census}
    total = build_total(ctx)
    repos = [build_repo(ctx, r) for r in sorted(snapshot["rows"], key=lambda r: r["rank"])]
    orch = build_orchestrators(ctx)
    inputs = {POLICY: hashlib.sha256((root / POLICY).read_bytes()).hexdigest(),
              r5.POLICY: hashlib.sha256((root / r5.POLICY).read_bytes()).hexdigest(),
              r5.LEDGER: hashlib.sha256((root / r5.LEDGER).read_bytes()).hexdigest()}
    inputs.update(sources["digests"])
    if census:
        inputs.update(census["digests"])
    inputs.update(site_digests)
    return {
        "schema": SCHEMA,
        "authority": policy["authority"],
        "authority_transfer": False,
        "merge_admission": "HOLD",
        "release_credit": False,
        "latest_pulse": rolling["latest_pulse"],
        "inputs": dict(sorted(inputs.items())),
        "lenses": list(LENSES),
        "colour_classes": policy["colour_classes"],
        "metric_definitions": policy["metric_definitions"],
        "sipoc_definitions": policy["sipoc"],
        "objects": [{k: o.get(k) for k in ("id", "path", "symbol", "kind", "function", "oid")}
                    for o in objects.values()],
        "lifecycle": lifecycle_matrix(census, snapshot),
        "scopes": [total] + repos + [orch],
    }


def lifecycle_matrix(census: dict | None, snapshot: dict) -> dict | None:
    """21-repo x S0..S9 level matrix for the heatmap, plus census-vs-gate SHA drift."""
    if not census:
        return None
    c = census["census"]
    focus = {r["repo"]: r.get("source_sha") for r in snapshot["rows"]}
    keys = [s["key"] for s in c["lifecycle"]["stages"]]
    rows = []
    for r in c["repos"]:
        rows.append({
            "rank": r["rank"], "repo": r["repo"], "lane": r["lane"],
            "head_sha": r.get("head_sha"), "focus_sha": focus.get(r["repo"]),
            "sha_drift": (r["repo"] in focus and focus[r["repo"]] != r.get("head_sha")),
            "levels": {k: r["stages"][k]["level"] for k in keys},
            "status": {k: stage_status(r["stages"][k]) for k in keys},
            "next_blocker": {k: (r["stages"][k].get("next_blocker") or {}).get("probe") for k in keys},
        })
    return {"schema": c["schema"], "digest_sha256": c["digest_sha256"],
            "observed_at_utc": c["observed_at_utc"], "stages": keys,
            "level_names": c["lifecycle"]["levels"], "repos": rows,
            "fleet": {k: {x: c["fleet"]["stages"][k][x] for x in ("median_level", "mean_completion", "repos_ge_L3")}
                      for k in keys}}


# --- Rendering ------------------------------------------------------------

def lens_text(node: dict, lens: str) -> str:
    if lens == "SHA":
        s = node["shas"][0] if node["shas"] else None
        return f"{s['value'][:10]} {s['label']}" if s else "no SHA bound"
    if lens == "OID":
        b = next((b for b in node["oids"] if b["oid"]), None)
        if not b:
            return node["oids"][0]["status"] if node["oids"] else "no object bound"
        name = Path(b["path"]).name + (f"::{b['symbol']}" if b.get("symbol") else "")
        return f"{b['oid'][:10]} {name}" + (f" @{b['at'][:7]}" if b.get("at") else "")
    return node["status"] or node["colour"]


def mermaid(scope: dict, lens: str) -> str:
    ids = {n["id"]: f"n{i}" for i, n in enumerate(scope["nodes"])}

    def q(s):
        return str(s).replace('"', "'").replace("<", "‹").replace(">", "›")

    out = [f"%% {scope['title']} · lens {lens} · generated by tools/cicd_dag.py (do not hand edit)",
           "flowchart LR"]
    for k in SIPOC_ORDER:
        members = [n for n in scope["nodes"] if n["kind"] == k]
        if not members:
            continue
        out.append(f'  subgraph {k}["{k} · {q(SIPOC_NAMES[k])}"]')
        for n in members:
            out.append(f'    {ids[n["id"]]}["{q(n["label"][:48])}<br/><small>{q(lens_text(n, lens))}</small>"]:::{n["colour"].lower()}')
        out.append("  end")
    arrows = {"CROSSWALK": "-.->", "TEMPORAL": "-.->", "PREREQ": "-->"}
    for e in scope["edges"]:
        a = arrows.get(e["type"], "==>" if e["type"] == "FEDERATION" else "-->")
        lbl = e["label"] or ("next pulse" if e["type"] == "TEMPORAL" else "")
        lbl = f"|{q(lbl[:32])}|" if lbl else ""
        out.append(f"  {ids[e['from']]} {a}{lbl} {ids[e['to']]}")
    for name, fill in MERMAID_COLOURS.items():
        out.append(f"  classDef {name.lower()} {fill}")
    return "\n".join(out) + "\n"


SIPOC_NAMES = {"S": "Suppliers", "I": "Inputs", "P": "Process", "O": "Outputs", "C": "Customers"}
MERMAID_COLOURS = {
    "CODE_PURPLE": "fill:#2c1f47,stroke:#b48cff,color:#eadcff",
    "ROOT_RED": "fill:#4a1d17,stroke:#ff8a6b,color:#ffd9cf",
    "EVERRED": "fill:#3a1b1b,stroke:#ff6b6b,color:#ffd6d6",
    "FAIL": "fill:#3a1b1b,stroke:#ff9999,color:#ffd6d6",
    "UNKNOWN": "fill:#3a2f1c,stroke:#ffcc83,color:#ffe9c6",
    "PASS": "fill:#123d2c,stroke:#7be0ad,color:#dbffec",
    "P_PROCESS": "fill:#16284a,stroke:#7fb2ff,color:#dce9ff",
    "ISSUE_BD": "fill:#3a2f1c,stroke:#e6b35c,color:#ffe9c6",
    "CROSSWALK": "fill:#0f3340,stroke:#6fd6e8,color:#d6f6fb",
    "NEUTRAL": "fill:#183a30,stroke:#85ad9d,color:#eefaf2",
}


def crosswalk_csv(model: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["scope", "node_id", "sipoc", "type", "label", "status", "colour_class",
                "dmaic_phase", "layer", "sha_bindings", "oid_bindings", "jade_oids", "detail"])
    for s in model["scopes"]:
        for n in s["nodes"]:
            w.writerow([s["scope"], n["id"], n["kind"], n["type"], n["label"], n["status"] or "",
                        n["colour"], n["phase"] or "", n["layer"],
                        "|".join(f"{b['label']}={b['value']}" for b in n["shas"]),
                        "|".join(f"{b['oid'] or b['status']}:{b['path']}"
                                 + (f"::{b['symbol']}" if b.get("symbol") else "")
                                 + (f"@{b['at']}" if b.get("at") else "")
                                 for b in n["oids"]),
                        "|".join(b["jade_oid"] for b in n["oids"] if b.get("jade_oid")),
                        n["detail"]])
    return buf.getvalue()


def render(model: dict) -> dict[str, bytes]:
    files = {
        OUT_JSON: (json.dumps(model, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"),
        OUT_CSV: crosswalk_csv(model).encode("utf-8"),
    }
    by_scope = {s["scope"]: s for s in model["scopes"]}
    for scope in MMD_SCOPES:
        for lens in LENSES:
            files[MMD.format(scope=scope, lens=lens)] = mermaid(by_scope[scope], lens).encode("utf-8")
    return files


def main(argv=None, root: Path = ROOT) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    files = render(project(root))
    if args.check:
        drift = [rel for rel, data in files.items()
                 if not (root / rel).exists() or (root / rel).read_bytes() != data]
        if drift:
            print("CICD_DAG_FIRST_RED: regenerate " + ", ".join(drift))
            return 1
        print("CICD_DAG_PARITY_OK")
        return 0
    for rel, data in files.items():
        (root / rel).write_bytes(data)
    print("CICD_DAG_WROTE " + " ".join(files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
