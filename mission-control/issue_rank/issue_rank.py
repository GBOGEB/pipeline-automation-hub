#!/usr/bin/env python3
"""Issue burndown ranking: three views over live GitHub issues and PRs.

1. Bottom-up (oldest first) with the golden thread: the lineage from each open
   item back to its oldest referenced ancestor, and how much newer work hangs
   off each root.
2. Top-down (newest first), the mycelium view: what each new item attaches to
   (hyphae) and how far it reaches in two hops.
3. Nodes / edges / graph: typed reference graph, PageRank, betweenness,
   components and unblock pressure (open items that transitively wait on a node).

Per item it reads the DoV / DoD / steps checklists from the issue body and
reports how far the item is from closure (for example 4/7 ticked, 2 blockers,
closing PR green). Rollups are per repository, JADE (the four federated repos)
and USER (every fetched repository of the owner).

The ranking is ADVISORY. It grants no closure, merge or dispatch authority, and
a ticked checklist is not a verified DoD. Private repository text never leaves
the local output directory; ``--redact-private`` strips titles and actions.

Subcommands: ``fetch`` (live, read-only GraphQL via ``gh``), ``rank`` (pure),
``run`` (fetch + rank + telemetry ledger append).
"""
from __future__ import annotations

import argparse
import hashlib
import html
import importlib.util
import json
import math
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

import title_taxonomy as tt
import taxonomy_pulse as tp

SCHEMA = "jade.issue-rank.v1"
SNAPSHOT_SCHEMA = "jade.issue-rank.snapshot.v1"
LEDGER_SCHEMA = "jade.issue-rank.ledger.v1"
OWNER = "GBOGEB"
JADE_REPOS = ("cryoplant-project", "ABACUS", "CODEX", "pipeline-automation-hub")
HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE / "out"

# ---------------------------------------------------------------- parsers (owned by triway)

# The checklist and reference parsers belong to the triway burndown (AGENTS.md L4).
# This module only maps their output onto the shapes the graph and lanes use.
TRIWAY_PATH = HERE.parent / "qps-triage-ultra" / "issue-expedition" / "triway_burndown.py"


def _load_triway():
    spec = importlib.util.spec_from_file_location("triway_burndown", TRIWAY_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


triway = _load_triway()
SECTION = {"DoV": "DOV", "DoD": "DOD", "STEPS": "STEPS", "OTHER": "OTHER"}


def parse_checklist(body: str | None) -> dict:
    """``triway.checklist()`` as counts per section (DOV / DOD / STEPS / OTHER).

    Withdrawn items (``[~]``, ``[-]``, struck through) are not counted. Declared
    criteria without a checkbox are ``untracked``, never done. ``next_open`` is
    the first open item, taking sections in the order DOD, DOV, STEPS, OTHER.
    """
    tw = triway.checklist(body or "")
    sections, items, untracked = {}, [], []
    for name in ("DoV", "DoD", "STEPS", "OTHER"):
        sec, kind = tw[name], SECTION[name]
        prog = sec["progress"] or {"checked": 0, "total": 0}
        sections[kind] = {"done": prog["checked"], "total": prog["total"], "untracked": sec["untracked"]}
        items += [{"kind": kind, "done": x["checked_in_issue"], "text": x["text"][:200]}
                  for x in sec["items"] if not x.get("withdrawn")]
        untracked += [{"kind": kind, "text": x["text"][:200]} for x in sec["declared"]]
    done = sum(x["done"] for x in sections.values())
    total = sum(x["total"] for x in sections.values())
    n_untracked = sum(x["untracked"] for x in sections.values())
    if total == 0:
        state = "UNTRACKED_CRITERIA" if n_untracked else "NO_CHECKLIST"
    elif done == 0:
        state = "NOT_STARTED"
    elif done == total:
        state = "ALL_TICKED"
    else:
        state = "IN_PROGRESS"
    order = {"DOD": 0, "DOV": 1, "STEPS": 2, "OTHER": 3}
    nxt = (min((i for i in items if not i["done"]), key=lambda i: order[i["kind"]], default=None)
           or (untracked[0] if untracked else None))

    def declared(name):
        sec = tw[name]
        return bool(sec["heading_seen"] or sec["items"] or sec["declared"])
    return {"done": done, "total": total, "ratio": round(done / total, 4) if total else None,
            "untracked": n_untracked, "state": state, "sections": sections,
            "dod_declared": declared("DoD"), "dov_declared": declared("DoV"),
            "next_open": nxt["text"] if nxt else None, "items": items, "untracked_items": untracked}


def progress_text(cl: dict) -> str:
    if not cl["total"]:
        return f"{cl['untracked']} criteria, none tickable" if cl["untracked"] else "no checklist"
    parts = [f"{k} {s['done']}/{s['total']}" for k, s in cl["sections"].items() if s["total"]]
    tail = f" +{cl['untracked']} untracked" if cl["untracked"] else ""
    return f"{cl['done']}/{cl['total']} ({', '.join(parts)}){tail}"


# triway reference kinds -> graph edge kinds. SUPERSEDED_BY is stored reversed, as
# SUPERSEDES from the successor, the way BLOCKS is stored as DEPENDS_ON.
KIND = {"DECLARED_BLOCKER_CANDIDATE": "DEPENDS_ON", "DECLARED_BLOCKS_CANDIDATE": "BLOCKS",
        "DECLARED_PARENT_CANDIDATE": "PARENT", "DECLARED_CHILD_CANDIDATE": "CHILD",
        "DECLARED_PREDECESSOR": "SUPERSEDES", "DECLARED_SUCCESSOR": "SUPERSEDED_BY",
        "DECLARED_DUPLICATE_OF": "DUPLICATE_OF", "TEXT_ASSOCIATION": "MENTION",
        "PR_CLOSURE_CLAIM": "CLOSES", "PR_ASSOCIATION": "MENTION"}
# Weight of each edge type in the PageRank walk; the dependency family also
# drives unblock pressure.
EDGE_WEIGHT = {"CHILD": 1.0, "DEPENDS_ON": 1.0, "BLOCKS": 1.0, "CLOSES": 1.0, "PARENT": 0.6,
               "SUPERSEDES": 0.5, "DUPLICATE_OF": 0.5, "MENTION": 0.3, "XREF": 0.3}


def key(repo: str, number: int) -> str:
    return f"{repo}#{number}"


def extract_refs(text: str | None, home: str, owner: str = OWNER, pr: bool = False) -> list[dict]:
    """``triway.references()`` with graph edge kinds.

    ``home`` is ``owner/repo``; bare ``#N`` resolves there. ``pr`` selects the PR
    reading (closing claims become CLOSES). triway reads GBOGEB references only,
    so another owner fails closed.
    """
    out, seen = [], set()
    in_code = False
    for line in (text or "").splitlines():
        if line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        line = re.sub(r"`[^`]*`", "", line)
        check = CHECK.match(line)
        last = 0
        for m in REF.finditer(line):
            if m.group("un"):
                repo, n = f"{m.group('uo')}/{m.group('ur')}", int(m.group("un"))
            elif m.group("n"):
                repo, n = f"{m.group('o')}/{m.group('r')}", int(m.group("n"))
            elif m.group("an"):
                alias = re.sub(r"\s+", " ", m.group("al").lower())
                repo, n = f"{owner}/{ALIASES[alias]}", int(m.group("an"))
            else:
                repo, n = home, int(m.group("b"))
            if repo.split("/")[0].lower() != owner.lower():
                continue
            # The typing window ends at the '#', so "QPS parent #1920" sees "parent";
            # a keyword binds to the next reference only.
            end = m.start("an") - 1 if m.group("an") else m.start()
            before = line[max(last, end - 48):end]
            last = m.end()
            kind = "MENTION"
            for name, rx in TYPED:
                hit = rx.search(before)
                if hit:
                    kind = "MENTION" if NEGATED.search(before[:hit.start()]) else name
                    break
            # Only live [ ] / [x] items make a CHILD. A dropped [~] / [-] item is withdrawn:
            # every reference in it stays a mention, whatever keyword precedes it.
            live = check is not None and check.group(1) not in "~-"
            if check is not None and not live:
                kind = "MENTION"
            elif live and kind == "MENTION":
                kind = "CHILD"
            k = (repo, n, kind)
            if k not in seen:
                seen.add(k)
                out.append({"repo": repo, "number": n, "kind": kind,
                            "ticked": (check.group(1) in "xX") if live else None})
    return out

# ---------------------------------------------------------------- fetch

ISSUES_Q = """query($owner:String!,$name:String!,$cursor:String){repository(owner:$owner,name:$name){
issues(states:OPEN,first:40,after:$cursor,orderBy:{field:CREATED_AT,direction:ASC}){
pageInfo{hasNextPage endCursor}
nodes{number title url createdAt updatedAt body author{login}
labels(first:20){nodes{name}} assignees(first:10){nodes{login}} milestone{title}
comments(last:5){totalCount nodes{body createdAt}}
timelineItems(first:60,itemTypes:[CROSS_REFERENCED_EVENT,CONNECTED_EVENT]){nodes{__typename
... on CrossReferencedEvent{willCloseTarget source{__typename
 ... on Issue{number state createdAt repository{nameWithOwner}}
 ... on PullRequest{number state isDraft createdAt repository{nameWithOwner}}}}
... on ConnectedEvent{subject{__typename
 ... on Issue{number state createdAt repository{nameWithOwner}}
 ... on PullRequest{number state isDraft createdAt repository{nameWithOwner}}}}}}}}}}"""

PRS_Q = """query($owner:String!,$name:String!,$cursor:String){repository(owner:$owner,name:$name){
pullRequests(states:OPEN,first:40,after:$cursor,orderBy:{field:CREATED_AT,direction:ASC}){
pageInfo{hasNextPage endCursor}
nodes{number title url createdAt updatedAt isDraft reviewDecision body author{login}
baseRefName headRefName labels(first:20){nodes{name}}
closingIssuesReferences(first:20){nodes{number repository{nameWithOwner}}}
commits(last:1){nodes{commit{oid statusCheckRollup{state}}}}}}}}"""

REPO_Q = """query($owner:String!,$name:String!){repository(owner:$owner,name:$name){
nameWithOwner isPrivate defaultBranchRef{name target{oid}}}}"""

LIST_Q = """query($owner:String!,$cursor:String){repositoryOwner(login:$owner){
repositories(first:100,after:$cursor,ownerAffiliations:OWNER,isArchived:false){
pageInfo{hasNextPage endCursor}
nodes{name hasIssuesEnabled issues(states:OPEN){totalCount} pullRequests(states:OPEN){totalCount}}}}}"""


class Gh:
    """Read-only ``gh api graphql`` runner; counts calls and seconds for telemetry."""

    def __init__(self, exe: str = "gh", attempts: int = 4):
        self.exe, self.attempts = exe, attempts
        self.calls, self.retries, self.seconds = 0, 0, 0.0

    def __call__(self, query: str, allow_not_found: bool = False, **variables) -> dict:
        args = [self.exe, "api", "graphql", "-f", f"query={query}"]
        for k, v in variables.items():
            if v is not None:
                args += ["-F" if isinstance(v, int) else "-f", f"{k}={v}"]
        for attempt in range(self.attempts):
            t0 = time.monotonic()
            res = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
            self.seconds += time.monotonic() - t0
            self.calls += 1
            try:
                data = json.loads(res.stdout)
                break
            except json.JSONDecodeError:  # transport failure: no JSON body
                if attempt + 1 == self.attempts:
                    raise RuntimeError(f"gh api graphql failed: {res.stderr.strip()[:400]}") from None
                self.retries += 1
                time.sleep(2 ** attempt * 3)
        errors = data.get("errors") or []
        if allow_not_found:
            errors = [e for e in errors if e.get("type") != "NOT_FOUND"]
        if errors or (res.returncode and not allow_not_found) or data.get("data") is None:
            raise RuntimeError(f"GraphQL errors: {json.dumps(errors)[:400]} {res.stderr.strip()[:200]}")
        return data["data"]


def _paged(gh, query: str, path: tuple[str, ...], **variables) -> list[dict]:
    nodes, cursor = [], None
    while True:
        data = gh(query, cursor=cursor, **variables)
        for p in path:
            data = data[p]
        nodes += data["nodes"]
        if not data["pageInfo"]["hasNextPage"]:
            return nodes
        cursor = data["pageInfo"]["endCursor"]


def list_repos(gh, owner: str = OWNER) -> list[str]:
    rows = _paged(gh, LIST_Q, ("repositoryOwner", "repositories"), owner=owner)
    return sorted(r["name"] for r in rows if r["hasIssuesEnabled"]
                  and (r["issues"]["totalCount"] or r["pullRequests"]["totalCount"]))


def _issue(node: dict, repo: str) -> dict:
    refs_in = []
    for ev in node["timelineItems"]["nodes"]:
        src = ev.get("source") or ev.get("subject")
        if not src or "number" not in src:
            continue
        refs_in.append({"repo": src["repository"]["nameWithOwner"], "number": src["number"],
                        "type": src["__typename"], "state": src["state"],
                        "created_at": src.get("createdAt"), "draft": src.get("isDraft"),
                        "will_close": bool(ev.get("willCloseTarget")) or ev["__typename"] == "ConnectedEvent"})
    return {"repo": repo, "number": node["number"], "type": "Issue", "title": node["title"],
            "url": node["url"], "created_at": node["createdAt"], "updated_at": node["updatedAt"],
            "author": (node.get("author") or {}).get("login"),
            "labels": [x["name"] for x in node["labels"]["nodes"]],
            "assignees": [x["login"] for x in node["assignees"]["nodes"]],
            "milestone": (node.get("milestone") or {}).get("title"),
            "body": node.get("body") or "", "comments_count": node["comments"]["totalCount"],
            "comments": [c["body"] for c in node["comments"]["nodes"]], "refs_in": refs_in}


def _pr(node: dict, repo: str) -> dict:
    commit = (node["commits"]["nodes"] or [{}])[0].get("commit") or {}
    return {"repo": repo, "number": node["number"], "type": "PullRequest", "title": node["title"],
            "url": node["url"], "created_at": node["createdAt"], "updated_at": node["updatedAt"],
            "author": (node.get("author") or {}).get("login"), "draft": node["isDraft"],
            "review_decision": node.get("reviewDecision"),
            "labels": [x["name"] for x in node["labels"]["nodes"]],
            "base": node["baseRefName"], "head": node["headRefName"], "head_sha": commit.get("oid"),
            "checks": (commit.get("statusCheckRollup") or {}).get("state"),
            "body": node.get("body") or "",
            "closes": [{"repo": x["repository"]["nameWithOwner"], "number": x["number"]}
                       for x in node["closingIssuesReferences"]["nodes"]]}


def resolve_refs(gh, snap: dict, batch: int = 80) -> dict[str, dict | None]:
    """State and creation time of every referenced item outside the snapshot.

    ``None`` marks a reference that does not exist (for example ``#1`` used as
    list numbering); build_graph drops those edges.
    """
    stubs = sorted((n["repo"], n["number"]) for n in build_graph(snap)["nodes"].values() if n.get("stub"))
    found: dict[str, dict | None] = {}
    for i in range(0, len(stubs), batch):
        chunk = stubs[i:i + batch]
        by_repo = defaultdict(list)
        for repo, n in chunk:
            by_repo[repo].append(n)
        parts = []
        for j, (repo, nums) in enumerate(sorted(by_repo.items())):
            owner, name = repo.split("/", 1)
            inner = " ".join(f"n{n}:issueOrPullRequest(number:{n}){{__typename "
                             f"...on Issue{{state createdAt}} ...on PullRequest{{state createdAt isDraft}}}}"
                             for n in nums)
            parts.append(f'r{j}:repository(owner:{json.dumps(owner)},name:{json.dumps(name)}){{{inner}}}')
        data = gh("query{" + " ".join(parts) + "}", allow_not_found=True)
        for j, (repo, nums) in enumerate(sorted(by_repo.items())):
            r = data.get(f"r{j}") or {}
            for n in nums:
                v = r.get(f"n{n}")
                found[key(repo, n)] = None if not v else {
                    "type": v["__typename"], "state": v["state"], "created_at": v["createdAt"],
                    "draft": v.get("isDraft")}
    return found


def fetch(gh, repos: list[str], owner: str = OWNER) -> dict:
    """One snapshot: open issues and PRs plus each repo's default-branch head SHA."""
    t0 = time.monotonic()
    out = {"schema": SNAPSHOT_SCHEMA, "owner": owner,
           "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "repos": {}}
    for name in repos:
        r0 = time.monotonic()
        meta = gh(REPO_Q, owner=owner, name=name)["repository"]
        full = meta["nameWithOwner"]
        ref = meta.get("defaultBranchRef") or {}
        issues = _paged(gh, ISSUES_Q, ("repository", "issues"), owner=owner, name=name)
        prs = _paged(gh, PRS_Q, ("repository", "pullRequests"), owner=owner, name=name)
        out["repos"][full] = {
            "private": meta["isPrivate"], "default_branch": ref.get("name"),
            "head_sha": (ref.get("target") or {}).get("oid"),
            "issues": [_issue(n, full) for n in issues], "prs": [_pr(n, full) for n in prs],
            "fetch_seconds": round(time.monotonic() - r0, 2)}
    out["refs"] = resolve_refs(gh, out)
    out["telemetry"] = {"api_calls": getattr(gh, "calls", None), "api_retries": getattr(gh, "retries", None),
                        "refs_resolved": len(out["refs"]),
                        "refs_missing": sum(1 for v in out["refs"].values() if v is None),
                        "api_seconds": round(getattr(gh, "seconds", 0.0), 2),
                        "wall_seconds": round(time.monotonic() - t0, 2)}
    return out

# ---------------------------------------------------------------- graph


def _ts(s: str | None) -> float | None:
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()


def build_graph(snap: dict) -> dict:
    """Nodes (open items + referenced stubs) and typed, deduplicated edges."""
    nodes: dict[str, dict] = {}
    for full, r in snap["repos"].items():
        for it in r["issues"] + r["prs"]:
            nodes[key(full, it["number"])] = {**it, "open": True, "private": r["private"]}
    edges: dict[tuple[str, str, str], dict] = {}
    resolved = snap.get("refs") or {}

    def stub(repo, number, **kw):
        k = key(repo, number)
        if k in resolved:
            if resolved[k] is None:  # reference to nothing: drop the edge
                return None
            kw = {**resolved[k], **{x: v for x, v in kw.items() if v is not None}}
        if k not in nodes:
            private = snap["repos"].get(repo, {}).get("private")
            nodes[k] = {"repo": repo, "number": number, "type": kw.get("type", "Unknown"),
                        "open": kw.get("state") == "OPEN" if kw.get("state") else None,
                        "state": kw.get("state"), "created_at": kw.get("created_at"),
                        "draft": kw.get("draft"), "private": private, "stub": True}
        return k

    def add(src, dst, kind, **kw):
        if src is None or dst is None or src == dst:
            return
        e = edges.setdefault((src, dst, kind), {"source": src, "target": dst, "kind": kind})
        e.update({k: v for k, v in kw.items() if v is not None})

    for k, it in list(nodes.items()):
        texts = [it.get("body")] + list(it.get("comments") or [])
        for i, text in enumerate(texts):
            for ref in extract_refs(text, it["repo"], snap["owner"], pr=it["type"] == "PullRequest"):
                t = stub(ref["repo"], ref["number"])
                kind = ref["kind"]
                if i and kind == "CHILD":  # comment checklists are status notes, not the plan
                    kind = "MENTION"
                if it["type"] == "PullRequest" and kind == "CLOSES":
                    add(k, t, "CLOSES")
                elif kind == "BLOCKS":  # this blocks ref -> ref depends on this
                    add(t, k, "DEPENDS_ON", origin=k)
                elif kind == "SUPERSEDED_BY":  # ref replaces this -> ref supersedes this
                    add(t, k, "SUPERSEDES", origin=k)
                else:
                    add(k, t, kind, ticked=ref["ticked"] if kind == "CHILD" else None)
        for c in it.get("closes") or []:
            add(k, stub(c["repo"], c["number"], type="Issue"), "CLOSES")
        for ref in it.get("refs_in") or []:
            s = stub(ref["repo"], ref["number"], type=ref["type"], state=ref["state"],
                     created_at=ref.get("created_at"))
            add(s, k, "CLOSES" if ref["will_close"] and ref["type"] == "PullRequest" else "XREF")
    return {"nodes": nodes, "edges": list(edges.values())}


def dep_edges(edges: list[dict]) -> list[tuple[str, str]]:
    """(waiter, blocker) pairs: waiter cannot close before blocker."""
    out = []
    for e in edges:
        if e["kind"] in ("DEPENDS_ON", "CHILD"):
            out.append((e["source"], e["target"]))
        elif e["kind"] == "PARENT":  # child -> parent: the parent waits on the child
            out.append((e["target"], e["source"]))
    return out


def unblock_pressure(nodes: dict, edges: list[dict]) -> dict[str, int]:
    """Open items that transitively wait on each node (closing it relieves them)."""
    waiters = defaultdict(set)
    for w, b in dep_edges(edges):
        waiters[b].add(w)
    out = {}
    for k in nodes:
        seen, q = set(), deque([k])
        while q:
            for w in waiters[q.popleft()]:
                if w not in seen and w != k:
                    seen.add(w)
                    q.append(w)
        out[k] = sum(1 for w in seen if nodes[w].get("open"))
    return out


def open_blockers(nodes: dict, edges: list[dict]) -> dict[str, list[str]]:
    out = defaultdict(list)
    for w, b in dep_edges(edges):
        if nodes[b].get("open") is not False:  # unknown state counts as open: fail closed
            out[w].append(b)
    return out


def pagerank(nodes: list[str], edges: list[dict], d: float = 0.85, tol: float = 1e-10,
             max_iter: int = 200) -> dict[str, float]:
    """Weighted PageRank; a reference passes importance to what it references."""
    n = len(nodes)
    if not n:
        return {}
    out_w = defaultdict(float)
    links = defaultdict(list)
    for e in edges:
        w = EDGE_WEIGHT.get(e["kind"], 0.3)
        links[e["source"]].append((e["target"], w))
        out_w[e["source"]] += w
    pr = {k: 1.0 / n for k in nodes}
    for _ in range(max_iter):
        dangling = sum(pr[k] for k in nodes if not out_w[k])
        nxt = {k: (1 - d) / n + d * dangling / n for k in nodes}
        for s, lst in links.items():
            for t, w in lst:
                nxt[t] += d * pr[s] * w / out_w[s]
        delta = sum(abs(nxt[k] - pr[k]) for k in nodes)
        pr = nxt
        if delta < tol:
            break
    return pr


def betweenness(nodes: list[str], edges: list[dict]) -> dict[str, float]:
    """Brandes betweenness on the undirected, unweighted reference graph (normalized)."""
    adj = defaultdict(set)
    for e in edges:
        adj[e["source"]].add(e["target"])
        adj[e["target"]].add(e["source"])
    bc = dict.fromkeys(nodes, 0.0)
    for s in nodes:
        stack, pred = [], defaultdict(list)
        sigma, dist = defaultdict(float), {s: 0}
        sigma[s] = 1.0
        q = deque([s])
        while q:
            v = q.popleft()
            stack.append(v)
            for w in adj[v]:
                if w not in dist:
                    dist[w] = dist[v] + 1
                    q.append(w)
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]
                    pred[w].append(v)
        delta = defaultdict(float)
        while stack:
            w = stack.pop()
            for v in pred[w]:
                delta[v] += sigma[v] / sigma[w] * (1 + delta[w])
            if w != s:
                bc[w] += delta[w]
    n = len(nodes)
    scale = 1.0 / ((n - 1) * (n - 2)) if n > 2 else 1.0
    return {k: v * scale for k, v in bc.items()}  # undirected: each pair counted twice


def components(nodes: list[str], edges: list[dict]) -> dict[str, int]:
    adj = defaultdict(set)
    for e in edges:
        adj[e["source"]].add(e["target"])
        adj[e["target"]].add(e["source"])
    comp, cid = {}, 0
    for s in nodes:
        if s in comp:
            continue
        q = deque([s])
        comp[s] = cid
        while q:
            for w in adj[q.popleft()]:
                if w not in comp:
                    comp[w] = cid
                    q.append(w)
        cid += 1
    return comp


def _age_key(node: dict) -> tuple:
    """Older first: creation time when known, else issue number within a repo."""
    ts = _ts(node.get("created_at"))
    return (ts if ts is not None else math.inf, node["number"])


def golden_threads(nodes: dict, edges: list[dict]) -> dict[str, list[str]]:
    """Lineage from each open item back to its oldest referenced ancestor.

    At each step follow the outgoing reference to the oldest strictly older item;
    stop at a node with none. The chain is ordered root first.
    """
    out_refs = defaultdict(set)
    for e in edges:
        out_refs[e["source"]].add(e["target"])
    threads = {}
    for k, node in nodes.items():
        if not node.get("open") or node.get("stub"):
            continue
        chain, cur, seen = [k], k, {k}
        while True:
            older = [t for t in out_refs[cur] if t not in seen and _comparable_older(nodes[t], nodes[cur])]
            if not older:
                break
            cur = min(older, key=lambda t: _age_key(nodes[t]))
            seen.add(cur)
            chain.append(cur)
        threads[k] = list(reversed(chain))
    return threads


def _comparable_older(a: dict, b: dict) -> bool:
    ta, tb = _ts(a.get("created_at")), _ts(b.get("created_at"))
    if ta is not None and tb is not None:
        return ta < tb
    return a["repo"] == b["repo"] and a["number"] < b["number"]


def mycelium(nodes: dict, edges: list[dict]) -> dict[str, dict]:
    """Hyphae (links to older items) and 1-/2-hop reach for each open item."""
    adj = defaultdict(set)
    for e in edges:
        adj[e["source"]].add(e["target"])
        adj[e["target"]].add(e["source"])
    out = {}
    for k, node in nodes.items():
        if not node.get("open") or node.get("stub"):
            continue
        r1 = adj[k]
        r2 = set().union(*(adj[x] for x in r1)) - r1 - {k} if r1 else set()
        out[k] = {"hyphae": sorted(t for t in r1 if _comparable_older(nodes[t], node)),
                  "reach1": len(r1), "reach2": len(r2)}
    return out

# ---------------------------------------------------------------- ranking

PRIORITY = (("P0", 1.0), ("P1", 0.66), ("P2", 0.33), ("P3", 0.1))
WEIGHTS = {"pressure": 0.25, "nearness": 0.20, "priority": 0.15, "centrality": 0.15,
           "bridge": 0.10, "pr_ready": 0.10, "age": 0.05}


def priority_of(node: dict) -> float:
    text = " ".join(node.get("labels") or []) + " " + (node.get("title") or "")
    for tag, value in PRIORITY:
        if re.search(rf"(?<![A-Za-z0-9]){tag}(?![0-9])", text, re.I):
            return value
    if re.search(r"critical|urgent|blocker", text, re.I):
        return 0.66
    return 0.0


def _pct(values: dict[str, float]) -> dict[str, float]:
    """Percentile rank in [0, 1]; ties share the lower rank; all-zero stays zero."""
    keys = sorted(values, key=values.get)
    n = len(keys)
    out, i = {}, 0
    while i < n:
        j = i
        while j + 1 < n and values[keys[j + 1]] == values[keys[i]]:
            j += 1
        p = 0.0 if values[keys[i]] == 0 else (i / (n - 1) if n > 1 else 1.0)
        for x in keys[i:j + 1]:
            out[x] = p
        i = j + 1
    return out


def linked_prs(k: str, nodes: dict, edges: list[dict]) -> list[dict]:
    seen = {}
    for e in edges:
        if e["kind"] == "CLOSES" and e["target"] == k and nodes[e["source"]].get("type") == "PullRequest":
            p = nodes[e["source"]]
            seen[e["source"]] = {"pr": e["source"], "open": p.get("open"), "draft": p.get("draft"),
                                 "checks": p.get("checks"), "review": p.get("review_decision")}
    return list(seen.values())


def classify(item: dict) -> tuple[str, str]:
    """(lane, next action) for one open item."""
    cl, prs = item["checklist"], item["linked_prs"]
    green = [p for p in prs if p["open"] and p["checks"] == "SUCCESS" and not p["draft"]]
    red = [p for p in prs if p["open"] and p["checks"] in ("FAILURE", "ERROR")]
    if item["type"] == "PullRequest":
        if item.get("checks") in ("FAILURE", "ERROR"):
            return "FIX_RED", "make the PR head green (first red job), then request review"
        if item.get("draft"):
            return "IN_FLIGHT", "finish draft, mark ready when DoD of the issue it closes is met"
        if item.get("review_decision") != "APPROVED":
            return "REVIEW", "needs an independent approving review before merge"
        if item.get("checks") != "SUCCESS":
            return "AWAIT_CHECKS", "approved; wait for every required check to pass before merge"
        return "MERGE_READY", "approved and green: merge under the ruleset"
    if item["open_blockers"] and cl["state"] != "ALL_TICKED":
        return "BLOCKED", f"unblock first: {', '.join(item['open_blockers'][:3])}"
    if cl["state"] == "ALL_TICKED" or green:
        return "CLOSE_CANDIDATE", "verify DoD evidence and close (ticks are not proof)"
    if red:
        return "FIX_RED", f"linked PR red: {red[0]['pr']}"
    if item["pressure"] >= 2:
        return "BOTTLENECK", f"de-bottleneck: {item['pressure']} open items wait on this"
    if cl["ratio"] is not None and cl["ratio"] >= 0.7:
        return "NEARLY_DONE", f"next: {cl['next_open']}"
    if cl["state"] == "UNTRACKED_CRITERIA":
        return "TRACK_DOD", f"turn the {cl['untracked']} declared criteria into - [ ] items and tick what is met"
    if cl["state"] == "NO_CHECKLIST":
        return "DEFINE_DOD", "write DoD / DoV checklist so progress is measurable"
    if cl["state"] == "NOT_STARTED":
        return "NOT_STARTED", f"start: {cl['next_open']}"
    return "IN_PROGRESS", f"next: {cl['next_open']}"


def rank(snap: dict, now: float | None = None) -> dict:
    g = build_graph(snap)
    nodes, edges = g["nodes"], g["edges"]
    names = sorted(nodes)
    now = now if now is not None else _ts(snap["fetched_at"])
    pr = pagerank(names, edges)
    bc = betweenness(names, edges)
    comp = components(names, edges)
    comp_size = Counter(comp.values())
    pressure = unblock_pressure(nodes, edges)
    blockers = open_blockers(nodes, edges)
    threads = golden_threads(nodes, edges)
    myc = mycelium(nodes, edges)
    deg_in, deg_out = Counter(e["target"] for e in edges), Counter(e["source"] for e in edges)
    open_keys = [k for k in names if nodes[k].get("open") and not nodes[k].get("stub")]

    items = []
    for k in open_keys:
        n = nodes[k]
        cl = parse_checklist(n.get("body"))
        children = [e for e in edges if e["source"] == k and e["kind"] == "CHILD"]
        drift = [e["target"] for e in children
                 if e.get("ticked") is False and nodes[e["target"]].get("open") is False]
        items.append({
            "key": k, "repo": n["repo"], "number": n["number"], "type": n["type"],
            "title": n.get("title"), "url": n.get("url"), "private": n.get("private"),
            "title_taxonomy": tt.parse_title(n.get("title"), n["type"], n.get("labels")),
            "created_at": n.get("created_at"), "updated_at": n.get("updated_at"),
            "age_days": round((now - _ts(n["created_at"])) / 86400, 1),
            "idle_days": round((now - _ts(n["updated_at"])) / 86400, 1),
            "labels": n.get("labels"), "assignees": n.get("assignees"),
            "draft": n.get("draft"), "checks": n.get("checks"), "review_decision": n.get("review_decision"),
            "checklist": {x: cl[x] for x in cl if x not in ("items", "untracked_items")},
            "progress": progress_text(cl),
            "linked_prs": linked_prs(k, nodes, edges), "open_blockers": sorted(blockers.get(k, [])),
            "ticked_but_child_open": [e["target"] for e in children
                                      if e.get("ticked") and nodes[e["target"]].get("open")],
            "unticked_but_child_closed": drift,
            "pressure": pressure[k], "pagerank": pr[k], "betweenness": bc[k],
            "degree_in": deg_in[k], "degree_out": deg_out[k],
            "component": comp[k], "component_size": comp_size[comp[k]],
            "golden_thread": threads.get(k, [k]), "mycelium": myc.get(k),
            "priority": priority_of(n),
        })
    associated = tt.associated_families(items, edges, max_hops=2)
    for item in items:
        item["title_taxonomy"]["related_families"] = associated[item["key"]]
    pct_pr = _pct({i["key"]: i["pagerank"] for i in items})
    pct_bc = _pct({i["key"]: i["betweenness"] for i in items})
    pct_age = _pct({i["key"]: i["age_days"] for i in items})
    max_p = max([i["pressure"] for i in items] + [1])
    for i in items:
        cl = i["checklist"]
        checks = [p["checks"] for p in i["linked_prs"] if p["open"]]
        if i["type"] == "PullRequest":
            checks.append(i["checks"])
        green, red = "SUCCESS" in checks, bool({"FAILURE", "ERROR"} & set(checks))
        parts = {
            "pressure": math.log1p(i["pressure"]) / math.log1p(max_p),
            "nearness": 1.0 if cl["state"] == "ALL_TICKED" else (cl["ratio"] or 0.0),
            "priority": i["priority"],
            "centrality": pct_pr[i["key"]], "bridge": pct_bc[i["key"]],
            "pr_ready": 1.0 if green else 0.5 if red else 0.0,
            "age": pct_age[i["key"]],
        }
        i["score_parts"] = {k: round(v, 4) for k, v in parts.items()}
        i["score"] = round(sum(WEIGHTS[k] * v for k, v in parts.items()), 4)
        i["lane"], i["action"] = classify(i)
    items.sort(key=lambda i: (-i["score"], i["key"]))
    for r, i in enumerate(items, 1):
        i["rank_global"] = r
    for repo in {i["repo"] for i in items}:
        for r, i in enumerate((x for x in items if x["repo"] == repo), 1):
            i["rank_repo"] = r

    jade = {f"{snap['owner']}/{r}" for r in JADE_REPOS}
    model = {
        "schema": SCHEMA, "owner": snap["owner"], "fetched_at": snap["fetched_at"],
        "authority": {"advisory_only": True, "closure_authorized": False, "merge_authorized": False,
                      "dispatch_authorized": False, "ticks_are_not_verified_dod": True},
        "weights": WEIGHTS,
        "heads": {r: {"default_branch": v.get("default_branch"), "head_sha": v.get("head_sha"),
                      "private": v.get("private")} for r, v in snap["repos"].items()},
        "graph": graph_stats(nodes, edges, comp),
        "rollups": {"USER": rollup(items, nodes, edges)},
        "items": items,
        "edges": edges,
        "views": {},
    }
    in_jade = [i for i in items if i["repo"] in jade]
    if in_jade:
        model["rollups"]["JADE"] = rollup(in_jade, nodes, edges)
    for repo in sorted(snap["repos"]):
        model["rollups"][repo] = rollup([i for i in items if i["repo"] == repo], nodes, edges)
    model["views"] = views(items, threads, nodes)
    return model


def graph_stats(nodes: dict, edges: list[dict], comp: dict) -> dict:
    open_n = sum(1 for n in nodes.values() if n.get("open") and not n.get("stub"))
    sizes = Counter(comp.values())
    n = len(nodes)
    return {"nodes": n, "open_items": open_n, "stub_nodes": n - open_n, "edges": len(edges),
            "edges_by_kind": dict(sorted(Counter(e["kind"] for e in edges).items())),
            "dependency_edges": len(dep_edges(edges)),
            "components": len(sizes), "largest_component": max(sizes.values()) if sizes else 0,
            "isolated_open_items": sum(1 for k, v in comp.items() if sizes[v] == 1 and nodes[k].get("open")),
            "density": round(len(edges) / (n * (n - 1)), 6) if n > 1 else 0.0}


def rollup(items: list[dict], nodes: dict, edges: list[dict]) -> dict:
    issues = [i for i in items if i["type"] == "Issue"]
    prs = [i for i in items if i["type"] == "PullRequest"]
    with_cl = [i for i in issues if i["checklist"]["total"]]
    lanes = Counter(i["lane"] for i in items)
    return {
        "open_issues": len(issues), "open_prs": len(prs),
        "checklist_coverage": _ratio(len(with_cl), len(issues)),
        "dod_declared": _ratio(sum(1 for i in issues if i["checklist"]["dod_declared"]), len(issues)),
        "dov_declared": _ratio(sum(1 for i in issues if i["checklist"]["dov_declared"]), len(issues)),
        "tasks_done": sum(i["checklist"]["done"] for i in issues),
        "tasks_total": sum(i["checklist"]["total"] for i in issues),
        "criteria_untracked": sum(i["checklist"]["untracked"] for i in issues),
        "states": dict(sorted(Counter(i["checklist"]["state"] for i in issues).items())),
        "lanes": dict(sorted(lanes.items())),
        "prs_red": sum(1 for p in prs if p.get("checks") in ("FAILURE", "ERROR")),
        "prs_unreviewed": sum(1 for p in prs if p.get("review_decision") != "APPROVED"),
        "median_age_days": _median([i["age_days"] for i in issues]),
        "stale_21d": sum(1 for i in issues if i["idle_days"] > 21),
        "checklist_drift": sum(1 for i in issues if i["ticked_but_child_open"] or i["unticked_but_child_closed"]),
        "top": [i["key"] for i in items[:10]],
        "bottlenecks": [i["key"] for i in sorted(items, key=lambda i: -i["pressure"]) if i["pressure"] >= 2][:10],
        "nearly_finished": [i["key"] for i in items if i["lane"] in ("CLOSE_CANDIDATE", "NEARLY_DONE", "MERGE_READY")][:15],
        "title_taxonomy": tt.summary(items),
    }


def views(items: list[dict], threads: dict, nodes: dict) -> dict:
    roots = defaultdict(list)
    for k, chain in threads.items():
        roots[chain[0]].append(k)
    bottom_up = sorted(items, key=lambda i: _age_key(nodes[i["key"]]))
    top_down = sorted(items, key=lambda i: _age_key(nodes[i["key"]]), reverse=True)
    return {
        "bottom_up": [i["key"] for i in bottom_up],
        "golden_roots": sorted(({"root": r, "open_root": bool(nodes[r].get("open")),
                                 "descendants": len(v), "longest": max(len(threads[x]) for x in v)}
                                for r, v in roots.items() if len(v) > 1 or r not in v),
                               key=lambda x: (-x["descendants"], x["root"]))[:25],
        "top_down": [i["key"] for i in top_down],
        "graph": [i["key"] for i in sorted(items, key=lambda i: (-i["pagerank"], i["key"]))],
    }


def _ratio(a, b):
    return round(a / b, 4) if b else None


def _median(xs):
    xs = sorted(xs)
    if not xs:
        return None
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 else round((xs[m - 1] + xs[m]) / 2, 1)

# ---------------------------------------------------------------- telemetry


def canonical(obj) -> bytes:
    return (json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def diff(prev: dict | None, cur: dict) -> dict:
    """What moved between two rank models: items, links, PR dependencies, ticks."""
    if not prev:
        return {"baseline": True}
    p_items = {i["key"]: i for i in prev["items"]}
    c_items = {i["key"]: i for i in cur["items"]}
    ek = lambda e: (e["source"], e["target"], e["kind"])  # noqa: E731
    p_edges, c_edges = {ek(e) for e in prev["edges"]}, {ek(e) for e in cur["edges"]}
    ticks = []
    for k in sorted(set(p_items) & set(c_items)):
        a, b = p_items[k]["checklist"], c_items[k]["checklist"]
        if (a["done"], a["total"]) != (b["done"], b["total"]):
            ticks.append({"key": k, "from": f"{a['done']}/{a['total']}", "to": f"{b['done']}/{b['total']}"})
    lane_moves = [{"key": k, "from": p_items[k]["lane"], "to": c_items[k]["lane"]}
                  for k in sorted(set(p_items) & set(c_items)) if p_items[k]["lane"] != c_items[k]["lane"]]
    taxonomy_moves = [{"key": k, "from": p_items[k].get("title_taxonomy", {}).get("path"),
                       "to": c_items[k].get("title_taxonomy", {}).get("path")}
                      for k in sorted(set(p_items) & set(c_items))
                      if p_items[k].get("title_taxonomy", {}).get("path") !=
                      c_items[k].get("title_taxonomy", {}).get("path")]
    new_edges = sorted(c_edges - p_edges)
    return {"baseline": False, "since": prev["fetched_at"],
            "new_items": sorted(set(c_items) - set(p_items)),
            "gone_items": sorted(set(p_items) - set(c_items)),
            "new_links": [list(e) for e in new_edges],
            "removed_links": [list(e) for e in sorted(p_edges - c_edges)],
            "new_pr_dependencies": [list(e) for e in new_edges if e[2] == "CLOSES"],
            "checklist_moves": ticks, "lane_moves": lane_moves,
            "taxonomy_moves": taxonomy_moves}


def telemetry(model: dict, snap: dict, delta: dict) -> dict:
    roll = model["rollups"]
    return {"fetched_at": model["fetched_at"], "fetch": snap.get("telemetry"),
            "heads": {r: h["head_sha"] for r, h in model["heads"].items()},
            "graph": model["graph"],
            "scopes": {s: {k: v for k, v in r.items() if k not in ("top", "bottlenecks", "nearly_finished")}
                       for s, r in roll.items()},
            "delta": {k: (len(v) if isinstance(v, list) else v) for k, v in delta.items()}}


def append_ledger(path: Path, record: dict) -> dict:
    """sha256-chained JSONL append; each row binds the previous row's digest."""
    prev = None
    if path.exists():
        lines = [x for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
        if lines:
            prev = json.loads(lines[-1])
    row = {"schema": LEDGER_SCHEMA, "seq": (prev["seq"] + 1) if prev else 0,
           "prev_sha256": prev["row_sha256"] if prev else None, **record}
    row["row_sha256"] = sha256(canonical(row))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    return row


def verify_ledger(path: Path) -> int:
    prev = None
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    for i, row in enumerate(rows):
        body = {k: v for k, v in row.items() if k != "row_sha256"}
        if row["seq"] != i or row["prev_sha256"] != prev or sha256(canonical(body)) != row["row_sha256"]:
            raise ValueError(f"ledger broken at seq {i}")
        prev = row["row_sha256"]
    return len(rows)

# ---------------------------------------------------------------- outputs


def redact(model: dict) -> dict:
    """Drop titles, URLs and free text of private-repository items."""
    out = json.loads(json.dumps(model))
    private_refs = {i["key"] for i in out["items"] if i.get("private")}
    for i in out["items"]:
        if not i.get("private") and "title_taxonomy" in i:
            i["title_taxonomy"]["related_families"] = [r for r in i["title_taxonomy"].get("related_families", [])
                                                         if r["source_item"] not in private_refs]
        if i.get("private"):
            i["title_taxonomy"] = {"schema": tt.SCHEMA, "family": "REDACTED_PRIVATE",
                                   "path": "REDACTED_PRIVATE", "programmes": [], "codes": [],
                                   "topic_families": [], "technical_clusters": [],
                                   "classification": "UNCLASSIFIED", "lint": [],
                                   "related_families": []}
            for f in ("title", "url"):
                i[f] = None
            i["checklist"]["next_open"] = None
            if i["action"].startswith(("next:", "start:")):
                i["action"] = i["action"].split(":")[0] + ": <private>"
    jade_repos = {f"{out['owner']}/{r}" for r in JADE_REPOS}
    for scope, r in out["rollups"].items():
        visible = [i for i in out["items"] if not i.get("private") and
                   (scope == "USER" or scope == "JADE" and i["repo"] in jade_repos
                    or i["repo"] == scope)]
        r["title_taxonomy"] = tt.summary(visible)
        r["title_taxonomy"]["private_items_excluded"] = sum(
            i.get("private", False) and
            (scope == "USER" or scope == "JADE" and i["repo"] in jade_repos
             or i["repo"] == scope) for i in out["items"])
    return out


CSV_COLS = ("rank_global", "rank_repo", "key", "type", "lane", "score", "progress", "pressure",
            "open_blockers", "linked_prs", "age_days", "idle_days", "action", "title",
            "family", "prefix_path", "prefix_codes", "topic_families", "technical_clusters",
            "related_family_candidates")


def to_csv(model: dict) -> str:
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(CSV_COLS)
    for i in model["items"]:
        title_tax = i.get("title_taxonomy") or {}
        def cell(name):
            if name == "open_blockers":
                return " ".join(i[name])
            if name == "linked_prs":
                return " ".join(p["pr"] for p in i[name])
            if name == "family":
                return title_tax.get("family", "")
            if name == "prefix_path":
                return title_tax.get("path", "")
            if name == "prefix_codes":
                return ";".join(title_tax.get("codes", []))
            if name in ("topic_families", "technical_clusters"):
                return ";".join(title_tax.get(name, []))
            if name == "related_family_candidates":
                return ";".join(r["family"] for r in title_tax.get("related_families", []))
            return i.get(name)
        w.writerow([cell(col) for col in CSV_COLS])
    return buf.getvalue()


def render_html(model: dict, delta: dict | None = None) -> str:
    """Standalone page: scope rollups, the three views and per-item progress bars."""
    items = {i["key"]: i for i in model["items"]}
    esc = html.escape

    def link(k):
        i = items.get(k)
        label = esc(k.split("/", 1)[1])
        return f'<a href="{esc(i["url"])}">{label}</a>' if i and i.get("url") else label

    def bar(i):
        cl = i["checklist"]
        if not cl["total"]:
            return '<span class="muted">no checklist</span>'
        pct = round(100 * cl["done"] / cl["total"])
        return (f'<span class="bar"><span style="width:{pct}%"></span></span> '
                f'<span class="num">{esc(i["progress"])}</span>')

    def row(i):
        return (f'<tr><td class="num">{i["rank_global"]}</td><td>{link(i["key"])}</td>'
                f'<td><span class="lane l-{i["lane"]}">{i["lane"]}</span></td>'
                f'<td class="num">{i["score"]:.3f}</td><td>{bar(i)}</td><td class="num">{i["pressure"]}</td>'
                f'<td>{" ".join(link(b) for b in i["open_blockers"][:4])}</td>'
                f'<td class="num">{i["age_days"]:.0f}</td><td>{esc(i["action"])}</td>'
                f'<td>{esc((i.get("title_taxonomy") or {}).get("path", "UNKNOWN"))}</td>'
                f'<td>{esc(i.get("title") or "")}</td></tr>')

    head = ('<tr><th>#</th><th>item</th><th>lane</th><th>score</th><th>progress (DoD/DoV/steps)</th>'
            '<th>pressure</th><th>open blockers</th><th>age d</th><th>next action</th><th>family / prefix path</th><th>title</th></tr>')

    def table(keys, limit=40):
        return f'<table>{head}{"".join(row(items[k]) for k in keys[:limit])}</table>'

    scopes = "".join(
        f'<tr><td>{esc(s)}</td><td class="num">{r["open_issues"]}</td><td class="num">{r["open_prs"]}</td>'
        f'<td class="num">{r["tasks_done"]}/{r["tasks_total"]}</td>'
        f'<td class="num">{_fmt_pct(r["checklist_coverage"])}</td><td class="num">{_fmt_pct(r["dod_declared"])}</td>'
        f'<td class="num">{_fmt_pct(r["dov_declared"])}</td><td class="num">{r["prs_red"]}</td>'
        f'<td class="num">{r["prs_unreviewed"]}</td><td class="num">{r["stale_21d"]}</td>'
        f'<td>{esc(" ".join("%s:%d" % kv for kv in r["lanes"].items()))}</td></tr>'
        for s, r in model["rollups"].items())
    taxonomy_rows = "".join(
        f'<tr><td>{esc(scope)}</td><td>{esc(fam)}</td><td class="num">{count["Issue"]}</td>'
        f'<td class="num">{count["PullRequest"]}</td><td class="num">{count["total"]}</td></tr>'
        for scope, roll in model["rollups"].items()
        for fam, count in roll["title_taxonomy"]["family"].items())
    leaf_clusters = sorted(model["rollups"]["USER"]["title_taxonomy"]["leaf_clusters"].items(),
                           key=lambda kv: (-kv[1]["total"], kv[0]))[:60]
    cluster_rows = "".join(
        f'<tr><td>{esc(path)}</td><td class="num">{count["Issue"]}</td>'
        f'<td class="num">{count["PullRequest"]}</td><td class="num">{count["total"]}</td></tr>'
        for path, count in leaf_clusters)
    technical_rows = "".join(
        f'<tr><td>{esc(scope)}</td><td>{esc(name)}</td><td class="num">{value["Issue"]}</td>'
        f'<td class="num">{value["PullRequest"]}</td><td class="num">{value["total"]}</td></tr>'
        for scope, roll in model["rollups"].items()
        for name, value in roll["title_taxonomy"]["technical_clusters_nonexclusive"].items())
    topic_rows = "".join(
        f'<tr><td>{esc(scope)}</td><td>{esc(name)}</td><td class="num">{value["Issue"]}</td>'
        f'<td class="num">{value["PullRequest"]}</td><td class="num">{value["total"]}</td></tr>'
        for scope, roll in model["rollups"].items()
        for name, value in roll["title_taxonomy"]["topic_families_nonexclusive"].items())
    roots = "".join(
        f'<tr><td>{link(g["root"])}</td><td>{"open" if g["open_root"] else "closed/stub"}</td>'
        f'<td class="num">{g["descendants"]}</td><td class="num">{g["longest"]}</td></tr>'
        for g in model["views"]["golden_roots"])
    nearly = model["rollups"]["USER"]["nearly_finished"]
    # Built outside the page template: no nested f-strings (Python 3.11 tokenizer).
    heads = " ".join("%s@%s" % (esc(r.split("/")[1]), (h["head_sha"] or "?")[:12])
                     for r, h in model["heads"].items())
    kinds = ", ".join("%s %d" % kv for kv in model["graph"]["edges_by_kind"].items())
    formula = " + ".join("%s·%s" % (v, k) for k, v in model["weights"].items())
    gs = model["graph"]
    d = delta or {}
    delta_html = ("baseline (first pulse)" if d.get("baseline") else
                  " · ".join(f"{esc(k)} {len(v)}" for k, v in d.items() if isinstance(v, list)))
    css = """
:root{--bg:#fbfaf7;--fg:#1d1d1b;--muted:#6b6a65;--line:#e4e1d8;--accent:#2f6f4f;--warn:#a5531b;--bad:#a12a2a}
@media (prefers-color-scheme:dark){:root{--bg:#161614;--fg:#ecebe6;--muted:#9a988f;--line:#33322d;--accent:#7fc29b;--warn:#e0a060;--bad:#e07a7a}}
body{background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif;margin:0 auto;max-width:1400px;padding:16px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:28px 0 8px;border-bottom:1px solid var(--line);padding-bottom:4px}
.muted{color:var(--muted)}table{border-collapse:collapse;width:100%;font-size:13px}
.wrap{overflow-x:auto}th,td{border-bottom:1px solid var(--line);padding:4px 6px;text-align:left;vertical-align:top}
th{font-weight:600;color:var(--muted)}.num{font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}
a{color:var(--accent)}.bar{display:inline-block;width:70px;height:8px;background:var(--line);border-radius:4px;vertical-align:middle}
.bar span{display:block;height:100%;background:var(--accent);border-radius:4px}
.lane{font-size:11px;padding:1px 6px;border-radius:8px;border:1px solid var(--line);white-space:nowrap}
.l-BLOCKED,.l-FIX_RED{color:var(--bad)}.l-BOTTLENECK,.l-DEFINE_DOD{color:var(--warn)}
.l-CLOSE_CANDIDATE,.l-NEARLY_DONE,.l-MERGE_READY{color:var(--accent)}"""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Issue Burndown Ranking</title>
<style>{css}</style></head><body>
<h1>Issue burndown ranking</h1>
<p class="muted">Snapshot {esc(model["fetched_at"])} · advisory only: no closure, merge or dispatch authority ·
ticked boxes are not verified DoD · heads: {heads}</p>
<p class="muted">Graph: {gs["nodes"]} nodes ({gs["open_items"]} open, {gs["stub_nodes"]} referenced) · {gs["edges"]} edges
({kinds}) · {gs["components"]} components, largest {gs["largest_component"]},
{gs["isolated_open_items"]} isolated open items · delta: {delta_html}</p>
<h2>Scopes</h2><div class="wrap"><table><tr><th>scope</th><th>issues</th><th>PRs</th><th>tasks ticked</th>
<th>checklist</th><th>DoD</th><th>DoV</th><th>red PRs</th><th>unapproved PRs</th><th>idle &gt;21d</th><th>lanes</th></tr>{scopes}</table></div>
<h2>Title family census · disjoint counts per repository and total</h2>
<div class="wrap"><table><tr><th>scope</th><th>family</th><th>issues</th><th>PRs</th><th>total</th></tr>{taxonomy_rows}</table></div>
<h2>Nested clusters · USER leaf paths (non-additive ancestry)</h2>
<div class="wrap"><table><tr><th>prefix path</th><th>issues</th><th>PRs</th><th>total</th></tr>{cluster_rows}</table></div>
<h2>Topic families · overlapping title / label associations</h2>
<div class="wrap"><table><tr><th>scope</th><th>topic</th><th>issues</th><th>PRs</th><th>matches</th></tr>{topic_rows}</table></div>
<h2>Technical clusters · overlapping title / label associations</h2>
<div class="wrap"><table><tr><th>scope</th><th>cluster</th><th>issues</th><th>PRs</th><th>matches</th></tr>{technical_rows}</table></div>
<h2>Ranked (composite)</h2><p class="muted">score = {formula}</p>
<div class="wrap">{table([i["key"] for i in model["items"]], 60)}</div>
<h2>Nearly finished / close candidates</h2><div class="wrap">{table(nearly, 30)}</div>
<h2>Bottlenecks (unblock pressure)</h2><div class="wrap">{table(model["rollups"]["USER"]["bottlenecks"], 20)}</div>
<h2>1 · Bottom-up: oldest first + golden thread</h2>
<div class="wrap"><table><tr><th>golden root</th><th>state</th><th>open descendants</th><th>longest chain</th></tr>{roots}</table></div>
<div class="wrap">{table(model["views"]["bottom_up"], 30)}</div>
<h2>2 · Top-down: newest first (mycelium)</h2><div class="wrap">{table(model["views"]["top_down"], 30)}</div>
<h2>3 · Graph: PageRank order</h2><div class="wrap">{table(model["views"]["graph"], 30)}</div>
</body></html>
"""


def _fmt_pct(x):
    return "n/a" if x is None else f"{100 * x:.0f}%"


def write_outputs(out: Path, model: dict, delta: dict, *,
                  previous_model: dict | None = None, parser_sha: str | None = None,
                  previous_parser_sha: str | None = None) -> dict[str, str]:
    """Write taxonomy pulse through the existing single-writer output manifest."""
    out.mkdir(parents=True, exist_ok=True)
    pulse = tp.build(model, previous_model, public=True, parser_sha=parser_sha,
                     previous_parser_sha=previous_parser_sha)
    files = {"issue_rank.json": canonical(model), "issue_rank.csv": to_csv(model).encode("utf-8"),
             "issue_rank.html": render_html(model, delta).encode("utf-8"), "delta.json": canonical(delta),
             "taxonomy_pulse.json": tp.canonical(pulse) + b"\n",
             "taxonomy_pulse.csv": tp.csv_view(pulse).encode("utf-8")}
    for name, data in files.items():
        (out / name).write_bytes(data)
    return {name: sha256(data) for name, data in files.items()}

# ---------------------------------------------------------------- CLI


def _repos(args, gh) -> list[str]:
    if args.repos:
        return args.repos
    return list_repos(gh, args.owner) if args.scope == "user" else list(JADE_REPOS)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("fetch", "run"):
        p = sub.add_parser(name)
        p.add_argument("--owner", default=OWNER)
        p.add_argument("--scope", choices=("jade", "user"), default="jade")
        p.add_argument("--repos", nargs="*")
        p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    r = sub.add_parser("rank")
    r.add_argument("--snapshot", type=Path, required=True)
    r.add_argument("--prev", type=Path, help="previous issue_rank.json, for the delta")
    r.add_argument("--out", type=Path, default=DEFAULT_OUT)
    for p in (sub.choices["run"], r):
        p.add_argument("--redact-private", action="store_true")
        p.add_argument("--parser-sha", help="exact checked-out taxonomy producer 40-hex SHA")
        p.add_argument("--previous-parser-sha", help="previous checked-out taxonomy producer SHA")
    v = sub.add_parser("verify-ledger")
    v.add_argument("--ledger", type=Path, default=DEFAULT_OUT / "jade" / "ledger.jsonl")
    args = ap.parse_args(argv)

    if args.cmd == "verify-ledger":
        print(f"ledger ok: {verify_ledger(args.ledger)} rows")
        return 0
    if args.cmd == "rank":
        snap = json.loads(args.snapshot.read_text(encoding="utf-8"))
        prev = json.loads(args.prev.read_text(encoding="utf-8")) if args.prev else None
        out = args.out
    else:
        gh = Gh()
        snap = fetch(gh, _repos(args, gh), args.owner)
        out = args.out / args.scope  # one pulse directory per scope
        out.mkdir(parents=True, exist_ok=True)
        if getattr(args, "redact_private", False):
            # The snapshot holds raw private bodies and comments; a redacted run keeps
            # only its digest (in the ledger) and removes any earlier raw copy.
            (out / "snapshot.json").unlink(missing_ok=True)
            print(f"snapshot not persisted (--redact-private) {snap['telemetry']}")
        else:
            (out / "snapshot.json").write_bytes(canonical(snap))
            print(f"snapshot {out / 'snapshot.json'} {snap['telemetry']}")
        if args.cmd == "fetch":
            return 0
        last = out / "issue_rank.json"
        prev = json.loads(last.read_text(encoding="utf-8")) if last.exists() else None
    model = rank(snap)
    delta = diff(prev, model)
    if args.redact_private:
        private_refs = {i["key"] for i in model["items"] if i.get("private")}
        if isinstance(delta.get("taxonomy_moves"), list):
            delta["taxonomy_moves"] = [d for d in delta["taxonomy_moves"]
                                       if d["key"] not in private_refs]
        model = redact(model)
    digests = write_outputs(out, model, delta, previous_model=prev,
                            parser_sha=args.parser_sha,
                            previous_parser_sha=args.previous_parser_sha)
    if args.cmd == "run":
        row = append_ledger(out / "ledger.jsonl", {
            "snapshot_sha256": sha256(canonical(snap)), "outputs": digests,
            "telemetry": telemetry(model, snap, delta)})
        print(f"ledger seq {row['seq']} {row['row_sha256'][:12]}")
    u = model["rollups"]["USER"]
    print(f"{u['open_issues']} issues, {u['open_prs']} PRs, tasks {u['tasks_done']}/{u['tasks_total']}, "
          f"lanes {u['lanes']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
