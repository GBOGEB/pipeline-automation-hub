#!/usr/bin/env python3
"""Issue burndown ranking: three views over live GitHub issues and PRs.

1. Bottom-up (oldest first) with the golden thread: each open item's position
   on the lifecycle thread (defined, verifiable, owned, started, unblocked,
   PR green, reviewed, DoD met, DoV met; ``rolling5.golden_thread``) and its
   lineage back to the oldest referenced ancestor.
2. Top-down (newest first), the mycelium view: what each new item attaches to
   (hyphae), how far it reaches in two hops, and whether it is rooted.
3. Nodes / edges / graph: typed reference graph (API relations OBSERVED, body
   text DECLARED), pressure rank, PageRank, betweenness, components, unblock
   pressure, dependency deadlocks and blocker chains.

Method v2 (METHOD.md): an item's urgency comes from priority, nearness, PR
state, age and idle time, with unknown parts imputed at the scope mean, never
zero. Pressure is a PageRank whose walk restarts in proportion to urgency and
follows waiter -> blocker, so an item ranks by its own urgency plus the
urgency of everything waiting on it (score = own + inherited, exactly). A
Monte Carlo over weights and damping gives each rank a 90% interval.

Per item it reads the DoV / DoD / steps checklists from the issue body and
reports how far the item is from closure (4/7 ticked, blocker chain 2, thread
5/9, first break REVIEWED). Rollups are per repository, FOCUS4 (the four
federated repos), JADE (the TOP21 roster) and USER (every fetched repository
of the owner), each with flow (arrivals, closures, exact Poisson intervals,
ETA) over the window.

The ranking is ADVISORY. It grants no closure, merge or dispatch authority, and
a ticked checklist is not a verified DoD. Private repository text never leaves
the local output directory; ``--redact-private`` projects private items to
pseudonyms through ``jade_temple/tools/private_boundary.py``.

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
import random
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

import title_taxonomy as tt
import taxonomy_pulse as tp

SCHEMA = "jade.issue-rank.v2"
SNAPSHOT_SCHEMA = "jade.issue-rank.snapshot.v2"
LEDGER_SCHEMA = "jade.issue-rank.ledger.v1"
METHOD_VERSION = "issue-rank-method/2.0"
OWNER = "GBOGEB"
FOCUS_REPOS = ("cryoplant-project", "ABACUS", "CODEX", "pipeline-automation-hub")
HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE / "out"
MC = HERE.parent
JADE_ROSTER = MC / "jade_temple" / "data" / "TOP21_PORTFOLIO.json"


def _load(name: str, path: Path):
    """Import an owner module by path (hyphenated directories, AGENTS.md)."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


IM = _load("issue_rank_math", HERE / "issue_math.py")


def _rolling5():
    """``golden_thread()`` owner (AGENTS.md: rolling5 owns the golden thread)."""
    return _load("jade_rolling5", MC / "jade_temple" / "tools" / "rolling5.py")


def _boundary():
    """Aggregate-only projection owner for private repositories."""
    return _load("jade_private_boundary", MC / "jade_temple" / "tools" / "private_boundary.py")


def jade_roster(path: Path = JADE_ROSTER) -> list[str]:
    """TOP21 repositories from the JADE roster; the four focus repos if it is missing."""
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))["repositories"]
        return sorted(r["repo"] for r in rows)
    except (OSError, KeyError, ValueError, TypeError):
        return sorted(f"{OWNER}/{r}" for r in FOCUS_REPOS)

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
    if owner != OWNER:
        raise ValueError(f"triway parses GBOGEB references only, not {owner!r}")
    return [{"repo": r["repo"], "number": r["number"], "kind": KIND.get(r["kind"], "MENTION"),
             "ticked": r.get("ticked")}
            for r in triway.references(text or "", home, pr=pr)]

# ---------------------------------------------------------------- fetch

# GitHub's own dependency relations (blockedBy / blocking / parent / sub-issues /
# closing PRs) are OBSERVED edges; references parsed from text are DECLARED.
_REL = "number state createdAt repository{nameWithOwner}"
# The GraphQL query requests bounded nested connections without cursors.
# An exactly-saturated connection is UNKNOWN, even if no extra row exists.
_RELATION_PAGE_CAPS = {"subIssues": 30, "blockedBy": 20, "blocking": 20,
                       "closedByPullRequestsReferences": 10}
_ISSUE_NODE = """nodes{number title url createdAt updatedAt closedAt state stateReason body author{login}
labels(first:20){nodes{name}} assignees(first:10){nodes{login}} milestone{title}
comments(last:5){totalCount nodes{body createdAt}}
subIssuesSummary{total completed}
parent{%(r)s} subIssues(first:30){nodes{%(r)s}}
blockedBy(first:20){nodes{%(r)s}} blocking(first:20){nodes{%(r)s}}
closedByPullRequestsReferences(first:10,includeClosedPrs:true){nodes{%(r)s}}
timelineItems(first:50,itemTypes:[CROSS_REFERENCED_EVENT,CONNECTED_EVENT]){nodes{__typename
... on CrossReferencedEvent{willCloseTarget source{__typename
 ... on Issue{number state createdAt repository{nameWithOwner}}
 ... on PullRequest{number state isDraft createdAt repository{nameWithOwner}}}}
... on ConnectedEvent{subject{__typename
 ... on Issue{number state createdAt repository{nameWithOwner}}
 ... on PullRequest{number state isDraft createdAt repository{nameWithOwner}}}}}}}""" % {"r": _REL}

ISSUES_Q = ("""query($owner:String!,$name:String!,$cursor:String){rateLimit{cost remaining}
repository(owner:$owner,name:$name){
issues(states:OPEN,first:30,after:$cursor,orderBy:{field:CREATED_AT,direction:ASC}){
pageInfo{hasNextPage endCursor}
""" + _ISSUE_NODE + "}}}")

# Closed in the window: flow (throughput) and closures that left predicates open.
CLOSED_Q = ("""query($owner:String!,$name:String!,$cursor:String,$since:DateTime){rateLimit{cost remaining}
repository(owner:$owner,name:$name){
issues(states:CLOSED,first:30,after:$cursor,filterBy:{since:$since},orderBy:{field:UPDATED_AT,direction:DESC}){
pageInfo{hasNextPage endCursor}
""" + _ISSUE_NODE + "}}}")

PRS_Q = """query($owner:String!,$name:String!,$cursor:String){rateLimit{cost remaining}
repository(owner:$owner,name:$name){
pullRequests(states:OPEN,first:40,after:$cursor,orderBy:{field:CREATED_AT,direction:ASC}){
pageInfo{hasNextPage endCursor}
nodes{number title url createdAt updatedAt isDraft reviewDecision body author{login}
baseRefName headRefName labels(first:20){nodes{name}}
reviews(states:APPROVED){totalCount}
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
        self.cost, self.remaining = 0, None  # GraphQL rate-limit points, from rateLimit{}

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
        rl = data["data"].pop("rateLimit", None) or {}
        self.cost += rl.get("cost") or 0
        if rl.get("remaining") is not None:
            self.remaining = rl["remaining"] if self.remaining is None else min(self.remaining, rl["remaining"])
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
    def rel(n):
        return {"repo": n["repository"]["nameWithOwner"], "number": n["number"],
                "state": n.get("state"), "created_at": n.get("createdAt")}

    def rels(field):
        return [rel(n) for n in ((node.get(field) or {}).get("nodes") or [])]

    summary = node.get("subIssuesSummary") or {}
    capped = sorted(field for field, cap in _RELATION_PAGE_CAPS.items()
                    if len((node.get(field) or {}).get("nodes") or []) >= cap)
    return {"repo": repo, "number": node["number"], "type": "Issue", "title": node["title"],
            "url": node["url"], "created_at": node["createdAt"], "updated_at": node["updatedAt"],
            "closed_at": node.get("closedAt"), "state": node.get("state") or "OPEN",
            "state_reason": node.get("stateReason"),
            "author": (node.get("author") or {}).get("login"),
            "labels": [x["name"] for x in node["labels"]["nodes"]],
            "assignees": [x["login"] for x in node["assignees"]["nodes"]],
            "milestone": (node.get("milestone") or {}).get("title"),
            "body": node.get("body") or "", "comments_count": node["comments"]["totalCount"],
            "comments": [c["body"] for c in node["comments"]["nodes"]], "refs_in": refs_in,
            "relations": {"parent": rel(node["parent"]) if node.get("parent") else None,
                          "sub_issues": rels("subIssues"), "blocked_by": rels("blockedBy"),
                          "blocking": rels("blocking"), "closed_by": rels("closedByPullRequestsReferences")},
            "sub_issues_summary": {"total": summary.get("total"), "completed": summary.get("completed")}
            if summary else None,
            "relation_limits_reached": capped}


def _pr(node: dict, repo: str) -> dict:
    commit = (node["commits"]["nodes"] or [{}])[0].get("commit") or {}
    return {"repo": repo, "number": node["number"], "type": "PullRequest", "title": node["title"],
            "url": node["url"], "created_at": node["createdAt"], "updated_at": node["updatedAt"],
            "author": (node.get("author") or {}).get("login"), "draft": node["isDraft"],
            "review_decision": node.get("reviewDecision"),
            "approvals": (node.get("reviews") or {}).get("totalCount"),
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


def fetch(gh, repos: list[str], owner: str = OWNER, window_days: int = 14, now: datetime | None = None) -> dict:
    """One snapshot: open issues and PRs, issues closed in the window, and each
    repo's default-branch head SHA (read once: one pulse per snapshot)."""
    if type(window_days) is not int or window_days <= 0:
        raise ValueError("INVALID_FLOW_WINDOW: window_days must be a positive integer")
    t0 = time.monotonic()
    at = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    since = (at - timedelta(days=window_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = {"schema": SNAPSHOT_SCHEMA, "owner": owner, "fetched_at": at.strftime("%Y-%m-%dT%H:%M:%SZ"),
           "window": {"days": window_days, "since": since}, "repos": {}}
    for name in repos:
        r0 = time.monotonic()
        meta = gh(REPO_Q, owner=owner, name=name)["repository"]
        full = meta["nameWithOwner"]
        ref = meta.get("defaultBranchRef") or {}
        issues = _paged(gh, ISSUES_Q, ("repository", "issues"), owner=owner, name=name)
        prs = _paged(gh, PRS_Q, ("repository", "pullRequests"), owner=owner, name=name)
        closed = _paged(gh, CLOSED_Q, ("repository", "issues"), owner=owner, name=name, since=since)
        out["repos"][full] = {
            "private": meta["isPrivate"], "default_branch": ref.get("name"),
            "head_sha": (ref.get("target") or {}).get("oid"),
            "issues": [_issue(n, full) for n in issues], "prs": [_pr(n, full) for n in prs],
            # filterBy.since is "updated since"; keep only closures inside the window.
            "closed": [_issue(n, full) for n in closed if (n.get("closedAt") or "") >= since],
            "fetch_seconds": round(time.monotonic() - r0, 2)}
    out["refs"] = resolve_refs(gh, out)
    out["telemetry"] = {"api_calls": getattr(gh, "calls", None), "api_retries": getattr(gh, "retries", None),
                        "graphql_cost": getattr(gh, "cost", None), "rate_remaining": getattr(gh, "remaining", None),
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
        for it in r.get("closed") or []:  # closed in the window: flow and predicate leaks
            nodes[key(full, it["number"])] = {**it, "open": False, "closed": True, "private": r["private"]}
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

    def add(src, dst, kind, binding="DECLARED", **kw):
        """DECLARED: parsed from text. OBSERVED: a GitHub relation or timeline event (wins)."""
        if src is None or dst is None or src == dst:
            return
        e = edges.setdefault((src, dst, kind), {"source": src, "target": dst, "kind": kind,
                                                "binding": binding})
        if binding == "OBSERVED":
            e["binding"] = "OBSERVED"
        e.update({k: v for k, v in kw.items() if v is not None})

    for k, it in list(nodes.items()):
        if it.get("stub"):
            continue
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
            add(k, stub(c["repo"], c["number"], type="Issue"), "CLOSES", "OBSERVED")
        for ref in it.get("refs_in") or []:
            s = stub(ref["repo"], ref["number"], type=ref["type"], state=ref["state"],
                     created_at=ref.get("created_at"))
            add(s, k, "CLOSES" if ref["will_close"] and ref["type"] == "PullRequest" else "XREF", "OBSERVED")
        rel = it.get("relations") or {}

        def node_of(r, typ="Issue"):
            return stub(r["repo"], r["number"], type=typ, state=r.get("state"), created_at=r.get("created_at"))
        if rel.get("parent"):
            add(k, node_of(rel["parent"]), "PARENT", "OBSERVED")
        for r in rel.get("sub_issues") or []:
            add(node_of(r), k, "PARENT", "OBSERVED")
        for r in rel.get("blocked_by") or []:
            add(k, node_of(r), "DEPENDS_ON", "OBSERVED")
        for r in rel.get("blocking") or []:
            add(node_of(r), k, "DEPENDS_ON", "OBSERVED")
        for r in rel.get("closed_by") or []:
            add(node_of(r, "PullRequest"), k, "CLOSES", "OBSERVED")
    return {"nodes": nodes, "edges": list(edges.values())}


def dep_edges(edges: list[dict]) -> list[tuple[str, str]]:
    """(waiter, blocker) pairs: waiter cannot close before blocker."""
    out = []
    for e in edges:
        if e["kind"] in ("DEPENDS_ON", "CHILD"):
            out.append((e["source"], e["target"]))
        elif e["kind"] == "PARENT":  # child -> parent: the parent waits on the child
            out.append((e["target"], e["source"]))
    # A duplicated declaration is still one blocker relationship.
    return sorted(set(out))


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
             max_iter: int = 200, teleport: dict[str, float] | None = None,
             weights: dict[str, float] | None = None, split: bool = False):
    """Weighted PageRank; a reference passes importance to what it references.

    ``teleport`` personalises the restart (and dangling) distribution; uniform
    when omitted, which is the classical PageRank. ``weights`` overrides the
    per-kind edge weights. With ``split`` it returns the fixed point's exact
    decomposition ``pi = own + inherited``:

        own_i       = (1 - d + d * dangling) * t_i          restart mass held by i
        inherited_i = d * sum_j pi_j * w_ji / out_j          mass pushed onto i by its in-links

    plus the iteration count and the final L1 residual.
    """
    n = len(nodes)
    if not n:
        return {"pi": {}, "own": {}, "inherited": {}, "iterations": 0, "residual": 0.0} if split else {}
    member = set(nodes)
    wmap = weights if weights is not None else EDGE_WEIGHT
    out_w = defaultdict(float)
    links = defaultdict(list)
    for e in edges:
        w = wmap.get(e["kind"], 0.3)
        if w > 0 and e["source"] in member and e["target"] in member and e["source"] != e["target"]:
            links[e["source"]].append((e["target"], w))
            out_w[e["source"]] += w
    raw = {k: max(0.0, (teleport or {}).get(k, 0.0)) for k in nodes} if teleport is not None else {}
    total = sum(raw.values())
    t = {k: raw[k] / total for k in nodes} if total > 0 else {k: 1.0 / n for k in nodes}

    def step(pr):
        dangling = sum(pr[k] for k in nodes if not out_w[k])
        own = {k: (1 - d + d * dangling) * t[k] for k in nodes}
        inh = dict.fromkeys(nodes, 0.0)
        for s, lst in links.items():
            for x, w in lst:
                inh[x] += d * pr[s] * w / out_w[s]
        return own, inh

    pr, delta, it = dict(t), math.inf, 0
    while it < max_iter and delta >= tol:
        it += 1
        own, inh = step(pr)
        nxt = {k: own[k] + inh[k] for k in nodes}
        delta = sum(abs(nxt[k] - pr[k]) for k in nodes)
        pr = nxt
    if not split:
        return pr
    own, inh = step(pr)
    return {"pi": pr, "own": own, "inherited": inh, "iterations": it, "residual": delta}


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


def lineages(nodes: dict, edges: list[dict]) -> dict[str, list[str]]:
    """Lineage from each open item back to its oldest referenced ancestor.

    Provenance, not the golden thread: the golden thread is the lifecycle gate
    chain owned by ``rolling5.golden_thread`` (see ``lifecycle_thread``).

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

PRIORITY = (("P0", 1.0), ("P1", 0.66), ("P2", 0.33), ("P3", 0.1), ("P4", 0.0))
# Urgency: what an item asks for on its own. An unknown part is imputed at the
# scope mean, never 0; ``coverage`` is the share of weight actually observed.
WEIGHTS = {"priority": 0.35, "nearness": 0.20, "pr_ready": 0.15, "age": 0.15, "idle": 0.15}
# Priority is missing not at random: owners label the urgent few, so the mean of
# the known labels would promote every unlabelled item. It takes a declared
# neutral prior (P2) instead; the other parts take the scope mean.
PRIOR = {"priority": 0.33}
# Pressure walk: waiter -> what it waits on (weight 1), mention direction for
# soft references (SOFT). Both, and the weights, are perturbed in the Monte Carlo.
DAMPING, SOFT, PARKED_FACTOR, URGENCY_FLOOR = 0.85, 0.15, 0.1, 0.01
MC_DRAWS, MC_SEED, MC_KAPPA, TOP_K = 200, 20261026, 20.0, 10
MC_DAMPING, MC_SOFT = (0.75, 0.92), (0.05, 0.30)
PARKED_LABELS = {"parked-intent", "parked"}
PARKED_MARK = re.compile(r"<!--\s*parked-intent:v1\b")
NEARLY = 0.7
# The lifecycle golden thread per track, scored by rolling5.golden_thread.
THREAD = {
    "CODE": ("DEFINED", "VERIFIABLE", "OWNED", "STARTED", "UNBLOCKED", "PR_GREEN", "REVIEWED",
             "DOD_MET", "DOV_MET"),
    "OWNER": ("DEFINED", "VERIFIABLE", "OWNED", "STARTED", "UNBLOCKED", "DOD_MET", "DOV_MET"),
    "PR": ("LINKED", "READY", "PR_GREEN", "REVIEWED"),
}
NEXT_STEP = {
    "DEFINED": "write the DoD as - [ ] items (define done)",
    "VERIFIABLE": "add a DoV: which evidence proves it (run, SHA, owner record)",
    "OWNED": "assign an owner",
    "STARTED": "start: tick the first item or open the PR",
    "UNBLOCKED": "unblock: close or re-plan the open blockers",
    "PR_GREEN": "make the linked PR green on its exact head",
    "REVIEWED": "get an independent approving review",
    "DOD_MET": "finish the open DoD items",
    "DOV_MET": "run and record the DoV evidence",
    "LINKED": "link the issue this PR closes (Closes #N)",
    "READY": "finish the draft and mark it ready",
}


def priority_of(node: dict, overlay: dict | None = None) -> tuple[float | None, str | None]:
    """(value, basis): an owner overlay first, then P0..P3 in labels or title. Unknown is None."""
    o = (overlay or {}).get(key(node["repo"], node["number"])) or {}
    if o.get("priority") in dict(PRIORITY):
        return dict(PRIORITY)[o["priority"]], "OVERLAY"
    text = " ".join(node.get("labels") or []) + " " + (node.get("title") or "")
    for tag, value in PRIORITY:
        if re.search(rf"(?<![A-Za-z0-9]){tag}(?![0-9])", text, re.I):
            return value, "LABEL_OR_TITLE"
    if re.search(r"critical|urgent|blocker", text, re.I):
        return 0.66, "KEYWORD"
    return None, None


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
            seen[e["source"]] = {"pr": e["source"], "open": p.get("open"), "state": p.get("state"),
                                 "draft": p.get("draft"), "checks": p.get("checks"),
                                 "review": p.get("review_decision"), "approvals": p.get("approvals")}
    return [seen[x] for x in sorted(seen)]


def _approved(p: dict) -> bool:
    """Aggregate review denial outranks a historical per-review approval count."""
    decision = p.get("review_decision")
    if decision is None:
        decision = p.get("review")
    if decision is not None:
        return decision == "APPROVED"
    return (p.get("approvals") or 0) > 0


def classify(item: dict) -> tuple[str, str]:
    """(lane, next action) for one open item."""
    cl, prs = item["checklist"], item["linked_prs"]
    live = [p for p in prs if p["open"]]
    green = [p for p in live if p["checks"] == "SUCCESS" and not p["draft"]]
    red = [p for p in live if p["checks"] in ("FAILURE", "ERROR")]
    if item["type"] == "PullRequest":
        if item.get("checks") in ("FAILURE", "ERROR"):
            return "FIX_RED", "make the PR head green (first red job), then request review"
        if item.get("draft"):
            return "IN_FLIGHT", "finish draft, mark ready when DoD of the issue it closes is met"
        if not _approved(item):
            return "REVIEW", "needs an independent approving review before merge"
        if item.get("checks") != "SUCCESS":
            return "AWAIT_CHECKS", "approved; wait for every required check to pass before merge"
        return "MERGE_READY", "approved and green: merge under the ruleset"
    if item.get("parked"):
        return "PARKED", "parked intent: leave it until a wake trigger fires"
    if item.get("deadlock"):
        return "DEADLOCK", f"dependency cycle with {', '.join(item['deadlock'][:3])}: drop or re-plan one edge"
    if item["open_blockers"] and cl["state"] != "ALL_TICKED":
        return "BLOCKED", (f"unblock first: {', '.join(item['open_blockers'][:3])}"
                           f" (blocker chain {item['chain']['below']})")
    if cl["state"] == "ALL_TICKED":
        return "CLOSE_CANDIDATE", "verify DoD evidence and close (ticks are not proof)"
    if red:
        return "FIX_RED", f"linked PR red: {red[0]['pr']}"
    if green:
        ok = [p for p in green if _approved(p)]
        if ok:
            return "MERGE_READY", f"linked PR green and approved: merge {ok[0]['pr']}, then verify the DoD"
        return "REVIEW", f"linked PR green: independent approval on {green[0]['pr']} before merge"
    if item["pressure"] >= 2 or item.get("unblocks_now", 0) >= 2:
        return "BOTTLENECK", (f"de-bottleneck: closing this frees {item.get('unblocks_now', 0)} now and "
                              f"relieves {item['pressure']} open items")
    if cl["ratio"] is not None and (cl["ratio"] >= NEARLY or cl["total"] >= 3 and cl["total"] - cl["done"] == 1):
        return "NEARLY_DONE", f"next: {cl['next_open']}"
    if cl["state"] == "UNTRACKED_CRITERIA":
        return "TRACK_DOD", f"turn the {cl['untracked']} declared criteria into - [ ] items and tick what is met"
    if cl["state"] == "NO_CHECKLIST":
        return "DEFINE_DOD", "write DoD / DoV checklist so progress is measurable"
    if cl["state"] == "NOT_STARTED":
        return "NOT_STARTED", f"start: {cl['next_open']}"
    return "IN_PROGRESS", f"next: {cl['next_open']}"


def lifecycle_gates(item: dict) -> tuple[str, dict[str, str]]:
    """(track, gate -> PASS / FAIL / UNKNOWN) for the lifecycle golden thread."""
    P, F, U = "PASS", "FAIL", "UNKNOWN"
    if item["type"] == "PullRequest":
        checks = item.get("checks")
        return "PR", {"LINKED": P if item.get("closes") else F, "READY": F if item.get("draft") else P,
                      "PR_GREEN": P if checks == "SUCCESS" else F if checks in ("FAILURE", "ERROR") else U,
                      "REVIEWED": P if _approved(item) else F}
    cl, prs = item["checklist"], item["linked_prs"]
    live = [p for p in prs if p["open"]]
    merged = [p for p in prs if p.get("state") == "MERGED"]
    states = {p["checks"] for p in live}
    green = P if merged or "SUCCESS" in states else F if states & {"FAILURE", "ERROR"} else U
    if any(_approved(p) for p in live):
        reviewed = P
    elif live:
        reviewed = F
    else:  # merged stubs carry no review record: unknown, never assumed
        reviewed = U
    sec = cl["sections"]

    def met(part):
        if part["total"]:
            return P if part["done"] == part["total"] else F
        return U
    dod = met(sec["DOD"]) if sec["DOD"]["total"] else (met(cl) if cl["total"] else U)
    sub = item.get("sub_issues_summary") or {}
    gates = {"DEFINED": P if cl["dod_declared"] or cl["total"] else F,
             "VERIFIABLE": P if cl["dov_declared"] else F,
             "OWNED": P if item.get("assignees") else F,
             "STARTED": P if cl["done"] or prs or (sub.get("completed") or 0) else F,
             "UNBLOCKED": F if item["open_blockers"] else P,
             "PR_GREEN": green, "REVIEWED": reviewed, "DOD_MET": dod, "DOV_MET": met(sec["DOV"])}
    return ("CODE" if prs else "OWNER"), gates


def lifecycle_thread(item: dict, golden_thread) -> dict:
    """Position on the golden thread via the owner's ``golden_thread(row, mapping)``."""
    track, gates = lifecycle_gates(item)
    t = golden_thread({"gates": gates}, {step: [step] for step in THREAD[track]})
    return {"track": track, **t, "next_step": NEXT_STEP.get(t["first_break"])}


def urgency_parts(items: list[dict]) -> dict[str, dict]:
    """Per item, each urgency feature in [0, 1], or None when it is not observed."""
    pct_age = _pct({i["key"]: i["age_days"] for i in items})
    pct_idle = _pct({i["key"]: i["idle_days"] for i in items})
    out = {}
    for i in items:
        cl = i["checklist"]
        checks = [p["checks"] for p in i["linked_prs"] if p["open"]]
        if i["type"] == "PullRequest":
            checks.append(i.get("checks"))
        states = {c for c in checks if c}
        merged = any(p.get("state") == "MERGED" for p in i["linked_prs"])
        pr_ready = (1.0 if merged or "SUCCESS" in states else 0.5 if states else 0.25 if checks else None)
        out[i["key"]] = {"priority": i["priority"],
                         "nearness": 1.0 if cl["state"] == "ALL_TICKED" else cl["ratio"],
                         "pr_ready": pr_ready, "age": pct_age[i["key"]], "idle": pct_idle[i["key"]]}
    return out


def urgency(parts: dict[str, dict], weights: dict[str, float], parked=frozenset()) -> tuple[dict, dict, dict]:
    """(u, coverage, imputed) per item. An unknown part takes PRIOR when declared,
    else the scope mean of that part; a part with neither drops out and the
    weights renormalise. Never zero."""
    means = {}
    for f in weights:
        known = [p[f] for p in parts.values() if p[f] is not None]
        means[f] = PRIOR.get(f, sum(known) / len(known) if known else None)
    live = [f for f in weights if means[f] is not None and weights[f] > 0]
    total = sum(weights[f] for f in live) or 1.0
    u, cov, imp = {}, {}, {}
    for k, p in parts.items():
        u[k] = sum(weights[f] * (p[f] if p[f] is not None else means[f]) for f in live) / total
        cov[k] = round(sum(weights[f] for f in live if p[f] is not None) / total, 4)
        imp[k] = [f for f in live if p[f] is None]
        if k in parked:
            u[k] *= PARKED_FACTOR
        u[k] = max(u[k], URGENCY_FLOOR)
    return u, cov, imp


def wait_edges(edges: list[dict]) -> list[dict]:
    """Edges of the pressure walk: waiter -> what it waits on (WAITS), mention -> mentioned (SOFT)."""
    out = [{"source": w, "target": b, "kind": "WAITS"} for w, b in dep_edges(edges)]
    for e in edges:
        if e["kind"] == "CLOSES":  # the issue waits on the PR that closes it
            out.append({"source": e["target"], "target": e["source"], "kind": "WAITS"})
        elif e["kind"] in ("MENTION", "XREF", "SUPERSEDES", "DUPLICATE_OF"):
            out.append({"source": e["source"], "target": e["target"], "kind": "SOFT"})
    return out


def monte_carlo(walk: list[str], wedges: list[dict], parts: dict, keys: list[str], parked,
                draws: int = MC_DRAWS, seed: int = MC_SEED) -> tuple[dict, dict]:
    """Rank stability under perturbed urgency weights (Dirichlet, concentration
    MC_KAPPA around WEIGHTS), damping and soft-edge weight. Seeded: reproducible."""
    if draws <= 0 or not keys:
        return {}, {"draws": 0, "seed": seed}
    rng = random.Random(seed)
    names = list(WEIGHTS)
    alphas = [MC_KAPPA * WEIGHTS[f] for f in names]
    u0, _, _ = urgency(parts, WEIGHTS, parked)
    base = pagerank(walk, wedges, DAMPING, teleport=u0, weights={"WAITS": 1.0, "SOFT": SOFT})
    base_rank = {k: i + 1 for i, k in enumerate(sorted(keys, key=lambda k: (-base[k], k)))}
    ranks, top, rhos = {k: [] for k in keys}, Counter(), []
    for _ in range(draws):
        w = dict(zip(names, IM.dirichlet(rng, alphas)))
        d, s = rng.uniform(*MC_DAMPING), rng.uniform(*MC_SOFT)
        u, _, _ = urgency(parts, w, parked)
        pi = pagerank(walk, wedges, d, tol=1e-9, teleport=u, weights={"WAITS": 1.0, "SOFT": s})
        order = sorted(keys, key=lambda k: (-pi[k], k))
        for r, k in enumerate(order, 1):
            ranks[k].append(r)
        top.update(order[:TOP_K])
        rhos.append(IM.spearman([base_rank[k] for k in keys], [ranks[k][-1] for k in keys]))
    per = {k: {"p05": round(IM.quantile(ranks[k], 0.05), 1), "p50": round(IM.quantile(ranks[k], 0.5), 1),
               "p95": round(IM.quantile(ranks[k], 0.95), 1), "p_top": round(top[k] / draws, 3)} for k in keys}
    rhos = [r for r in rhos if r is not None]
    return per, {"draws": draws, "seed": seed, "kappa": MC_KAPPA, "damping": list(MC_DAMPING),
                 "soft": list(MC_SOFT), "top_k": TOP_K,
                 "spearman_median": round(IM.quantile(rhos, 0.5), 4) if rhos else None,
                 "spearman_p05": round(IM.quantile(rhos, 0.05), 4) if rhos else None}


def flow(snap: dict, repos: set[str], level: float = 0.90) -> dict | None:
    """Arrivals and closures of issues in the window, exact Poisson intervals per
    day, Little's law time in system and an ETA when the burn is significantly
    positive. None when the snapshot has no window (v1 snapshots)."""
    win = snap.get("window") or {}
    days, since = win.get("days"), win.get("since")
    if not win:
        return None
    if type(days) is not int or days <= 0 or not isinstance(since, str) or not since:
        raise ValueError("INVALID_FLOW_WINDOW: positive integer days and since timestamp required")
    wip = arrivals = closed = 0
    reasons = Counter()
    for repo in sorted(repos):
        r = snap["repos"].get(repo)
        if not r:
            continue
        wip += len(r["issues"])
        arrivals += sum(1 for i in r["issues"] if (i.get("created_at") or "") >= since)
        for i in r.get("closed") or []:
            closed += 1
            arrivals += (i.get("created_at") or "") >= since
            reasons[i.get("state_reason") or "UNKNOWN"] += 1

    def rate(k):
        lo, hi = IM.poisson_interval(k, level)
        return {"events": k, "per_day": round(k / days, 4), "lo": round(lo / days, 4), "hi": round(hi / days, 4)}
    a, c = rate(arrivals), rate(closed)
    z = 1.6448536269514722 if level == 0.90 else 1.959963984540054
    net = (closed - arrivals) / days
    se = math.sqrt(closed + arrivals) / days
    net_lo, net_hi = net - z * se, net + z * se
    out = {"window_days": days, "since": since, "level": level, "wip_open_issues": wip,
           "arrivals": a, "closures": c, "closure_reasons": dict(sorted(reasons.items())),
           "net_burn_per_day": {"est": round(net, 4), "lo": round(net_lo, 4), "hi": round(net_hi, 4),
                                "method": "normal approximation to a Poisson difference"},
           "littles_law_days": None, "eta_days": None, "status": "NOT_CONVERGING"}
    if c["per_day"] > 0:
        out["littles_law_days"] = {"est": round(wip / c["per_day"], 1),
                                   "lo": round(wip / c["hi"], 1) if c["hi"] else None,
                                   "hi": round(wip / c["lo"], 1) if c["lo"] else None}
    if net_lo > 0:
        out["eta_days"] = {"est": round(wip / net, 1), "lo": round(wip / net_hi, 1), "hi": round(wip / net_lo, 1)}
        out["status"] = "BURNING_DOWN"
    elif net_hi < 0:
        out["status"] = "GROWING"
    return out


def predicate_leaks(nodes: dict, edges: list[dict]) -> list[dict]:
    """Issues closed in the window as completed with open checklist items and no
    open successor (supersession) or open parent to carry them: work that may
    have vanished from the burndown (the D+14 E-07 closure pattern)."""
    near = defaultdict(set)
    for e in edges:
        if e["kind"] in ("SUPERSEDES", "DUPLICATE_OF"):
            near[e["source"]].add(e["target"])
            near[e["target"]].add(e["source"])
        elif e["kind"] == "PARENT":
            near[e["source"]].add(e["target"])
    out = []
    for k, n in sorted(nodes.items()):
        if not n.get("closed") or n.get("type") != "Issue" or n.get("state_reason") not in (None, "COMPLETED"):
            continue
        cl = parse_checklist(n.get("body"))
        if not cl["total"] or cl["done"] == cl["total"]:
            continue
        if any(nodes[x].get("open") for x in near[k] if x in nodes):
            continue
        out.append({"key": k, "repo": n["repo"], "open_items": cl["total"] - cl["done"],
                    "progress": f"{cl['done']}/{cl['total']}", "closed_at": n.get("closed_at")})
    return out


def is_parked(node: dict) -> bool:
    return bool(PARKED_LABELS & {x.lower() for x in node.get("labels") or []}) or bool(
        PARKED_MARK.search(node.get("body") or ""))


def rank(snap: dict, now: float | None = None, overlay: dict | None = None,
         draws: int = MC_DRAWS, seed: int = MC_SEED) -> dict:
    g = build_graph(snap)
    nodes, edges = g["nodes"], g["edges"]
    names = sorted(nodes)
    capped_nodes = [k for k, v in nodes.items() if v.get("relation_limits_reached")]
    now = now if now is not None else _ts(snap["fetched_at"])
    pr = pagerank(names, edges)
    bc = betweenness(names, edges)
    comp = components(names, edges)
    comp_size = Counter(comp.values())
    pressure = unblock_pressure(nodes, edges)
    blockers = open_blockers(nodes, edges)
    lineage = lineages(nodes, edges)
    myc = mycelium(nodes, edges)
    deg_in, deg_out = Counter(e["target"] for e in edges), Counter(e["source"] for e in edges)
    open_keys = [k for k in names if nodes[k].get("open") and not nodes[k].get("stub")]

    # Waiting structure among open (or unknown-state) items: deadlocks, chains, sole blockers.
    walk = [k for k in names if nodes[k].get("open") is not False]
    walk_set = set(walk)
    succ = {k: [b for b in blockers.get(k, []) if b in walk_set] for k in walk}
    chains = IM.blocker_chains(walk, succ)
    cycle_of = {k: c for c in chains["cycles"] for k in c}
    unblocks_now = Counter(bs[0] for w, bs in blockers.items() if len(bs) == 1 and w in walk_set)

    items = []
    for k in open_keys:
        n = nodes[k]
        cl = parse_checklist(n.get("body"))
        children = [e for e in edges if e["source"] == k and e["kind"] == "CHILD"]
        drift = [e["target"] for e in children
                 if e.get("ticked") is False and nodes[e["target"]].get("open") is False]
        prio, basis = priority_of(n, overlay)
        items.append({
            "key": k, "repo": n["repo"], "number": n["number"], "type": n["type"],
            "title": n.get("title"), "url": n.get("url"), "private": n.get("private"),
            "title_taxonomy": tt.parse_title(n.get("title"), n["type"], n.get("labels")),
            "created_at": n.get("created_at"), "updated_at": n.get("updated_at"),
            "age_days": round((now - _ts(n["created_at"])) / 86400, 1),
            "idle_days": round((now - _ts(n["updated_at"])) / 86400, 1),
            "labels": n.get("labels"), "assignees": n.get("assignees"),
            "draft": n.get("draft"), "checks": n.get("checks"), "review_decision": n.get("review_decision"),
            "approvals": n.get("approvals"),
            "closes": [key(c["repo"], c["number"]) for c in n.get("closes") or []],
            "checklist": {x: cl[x] for x in cl if x not in ("items", "untracked_items")},
            "progress": progress_text(cl),
            "sub_issues_summary": n.get("sub_issues_summary"),
            "linked_prs": linked_prs(k, nodes, edges), "open_blockers": sorted(blockers.get(k, [])),
            "ticked_but_child_open": [e["target"] for e in children
                                      if e.get("ticked") and nodes[e["target"]].get("open")],
            "unticked_but_child_closed": drift,
            "pressure": pressure[k], "unblocks_now": unblocks_now[k],
            "chain": {"below": chains["below"].get(k, 0), "above": chains["above"].get(k, 0),
                      "critical": k in chains["critical"]},
            "deadlock": [x for x in cycle_of.get(k, []) if x != k],
            "parked": is_parked(n),
            "pagerank": pr[k], "betweenness": bc[k],
            "degree_in": deg_in[k], "degree_out": deg_out[k],
            "component": comp[k], "component_size": comp_size[comp[k]],
            "lineage": lineage.get(k, [k]), "mycelium": myc.get(k),
            "priority": prio, "priority_basis": basis,
            "overlay": (overlay or {}).get(k),
        })
    associated = tt.associated_families(items, edges, max_hops=2)
    for item in items:
        item["title_taxonomy"]["related_families"] = associated[item["key"]]

    # Urgency (own) and pressure (own + inherited from waiters) in one walk.
    parts = urgency_parts(items)
    parked = frozenset(i["key"] for i in items if i["parked"])
    u, cov, imp = urgency(parts, WEIGHTS, parked)
    wedges = wait_edges(edges)
    walk_w = {"WAITS": 1.0, "SOFT": SOFT}
    walked = pagerank(walk, wedges, DAMPING, teleport=u, weights=walk_w, split=True)
    keys = [i["key"] for i in items]
    top_pi = max([walked["pi"][k] for k in keys] + [1e-300])
    mc, mc_summary = monte_carlo(walk, wedges, parts, keys, parked, draws, seed)
    rolling = _rolling5()
    for i in items:
        k = i["key"]
        pi, own, inh = walked["pi"][k], walked["own"][k], walked["inherited"][k]
        i["urgency"] = round(u[k], 4)
        i["urgency_parts"] = {f: (round(v, 4) if v is not None else None) for f, v in parts[k].items()}
        i["coverage"], i["imputed"] = cov[k], imp[k]
        i["score"] = round(pi / top_pi, 4)
        i["score_parts"] = {"own": round(own / top_pi, 4), "inherited": round(inh / top_pi, 4)}
        i["inherited_share"] = round(inh / pi, 4) if pi else None
        i["rank_interval"] = mc.get(k)
        i["golden_thread"] = lifecycle_thread(i, rolling.golden_thread)
        i["lane"], i["action"] = classify(i)
        if nodes[k].get("relation_limits_reached"):
            i["lane"] = "SOURCE_INCOMPLETE"
            i["action"] = "paginate capped GitHub dependency connections before closure or ranking"
        i["actionable"] = i["lane"] not in ("BLOCKED", "DEADLOCK", "PARKED", "SOURCE_INCOMPLETE")
    items.sort(key=lambda i: (-i["score"], i["key"]))
    for r, i in enumerate(items, 1):
        i["rank_global"] = r
    for repo in {i["repo"] for i in items}:
        for r, i in enumerate((x for x in items if x["repo"] == repo), 1):
            i["rank_repo"] = r

    fetched = sorted(snap["repos"])
    owner = snap["owner"]
    focus = {f"{owner}/{r}" for r in FOCUS_REPOS}
    jade = set(jade_roster())
    leaks = predicate_leaks(nodes, edges)
    pi_total = sum(walked["pi"][k] for k in keys) or 1.0
    external = sorted(((k, walked["pi"][k]) for k in walk if nodes[k].get("stub")), key=lambda x: (-x[1], x[0]))
    model = {
        "schema": SCHEMA, "owner": owner, "fetched_at": snap["fetched_at"], "window": snap.get("window"),
        "authority": {"advisory_only": True, "closure_authorized": False, "merge_authorized": False,
                      "dispatch_authorized": False, "ticks_are_not_verified_dod": True,
                      "source_relations_complete": not capped_nodes,
                      "nested_relation_capped_items": len(capped_nodes)},
        "method": {"version": METHOD_VERSION, "ordering": "NON_BT_REVERSE_PRESSURE_PAGERANK",
                   "bradley_terry": "WITHHELD_NO_OBSERVED_PAIRWISE_OUTCOMES",
                   "urgency_weights": WEIGHTS, "damping": DAMPING, "soft_weight": SOFT,
                   "parked_factor": PARKED_FACTOR, "unknown_part": "SCOPE_MEAN_NEVER_ZERO", "priors": PRIOR,
                   "walk": {"iterations": walked["iterations"], "residual": walked["residual"]},
                   "monte_carlo": mc_summary},
        "weights": WEIGHTS,
        "heads": {r: {"default_branch": v.get("default_branch"), "head_sha": v.get("head_sha"),
                      "private": v.get("private")} for r, v in snap["repos"].items()},
        "graph": {**graph_stats(nodes, edges, comp), "deadlocks": chains["cycles"],
                  "critical_chain": [k for k in chains["critical"] if k in walk_set],
                  "edges_by_binding": dict(sorted(Counter(e.get("binding", "DECLARED") for e in edges).items()))},
        "external_pressure": [{"key": k, "share": round(v / pi_total, 4)} for k, v in external[:15]],
        "predicate_leaks": leaks,
        "closed_in_window": [{"key": k, "repo": n["repo"], "state_reason": n.get("state_reason"),
                              "closed_at": n.get("closed_at")}
                             for k, n in sorted(nodes.items()) if n.get("closed")],
        "rollups": {},
        "items": items,
        "edges": edges,
        "views": {},
    }
    scopes = [("USER", set(fetched), set(fetched)), ("JADE", jade, jade), ("FOCUS4", focus, focus)]
    scopes += [(r, {r}, {r}) for r in fetched]
    for name, repos, need in scopes:
        sel = [i for i in items if i["repo"] in repos]
        if not sel and name in ("JADE", "FOCUS4") and not (need & set(fetched)):
            continue
        roll = rollup(sel, nodes, edges)
        roll["complete"] = need <= set(fetched)
        roll["missing_repos"] = sorted(need - set(fetched)) if name in ("JADE", "FOCUS4") else []
        roll["flow"] = flow(snap, repos & set(fetched))
        roll["predicate_leaks"] = sum(1 for x in leaks if x["repo"] in repos)
        roll["pressure_share"] = round(sum(walked["pi"][i["key"]] for i in sel) / pi_total, 4)
        model["rollups"][name] = roll
    model["views"] = views(items, lineage, nodes)
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
        # v2: actionable queue, robust top, lifecycle thread funnel, owners, structure debt
        "actionable": sum(1 for i in items if i.get("actionable")),
        "parked": sum(1 for i in items if i.get("parked")),
        "deadlocked": sum(1 for i in items if i.get("deadlock")),
        "measurable": _ratio(sum(1 for i in issues if i["checklist"]["total"] or i["checklist"]["untracked"]),
                             len(issues)),
        "mean_coverage": _ratio(sum(i.get("coverage") or 0 for i in items), len(items)),
        "action_queue": [i["key"] for i in items if i.get("actionable")][:10],
        "robust_top": [i["key"] for i in items if (i.get("rank_interval") or {}).get("p_top", 0) >= 0.8],
        "thread_funnel": dict(sorted(Counter((i.get("golden_thread") or {}).get("first_break") or "CLOSABLE"
                                             for i in issues).items())),
        "by_assignee": _by_assignee(items),
        "title_taxonomy": tt.summary(items),
    }


def _by_assignee(items: list[dict]) -> list[dict]:
    """Open items, summed score and nearly-done items per assignee (unassigned last)."""
    acc = defaultdict(lambda: {"open": 0, "score": 0.0, "nearly_done": 0})
    for i in items:
        for who in i.get("assignees") or ["(unassigned)"]:
            a = acc[who]
            a["open"] += 1
            a["score"] += i.get("score") or 0.0
            a["nearly_done"] += i["lane"] in ("CLOSE_CANDIDATE", "NEARLY_DONE", "MERGE_READY")
    rows = [{"assignee": k, **v, "score": round(v["score"], 4)} for k, v in acc.items()]
    return sorted(rows, key=lambda r: (r["assignee"] == "(unassigned)", -r["score"], r["assignee"]))[:10]


def views(items: list[dict], threads: dict, nodes: dict) -> dict:
    """The three reading orders, the action queue, and how far the orders agree."""
    roots = defaultdict(list)
    for k, chain in threads.items():
        roots[chain[0]].append(k)
    bottom_up = sorted(items, key=lambda i: _age_key(nodes[i["key"]]))
    top_down = sorted(items, key=lambda i: _age_key(nodes[i["key"]]), reverse=True)
    graph = sorted(items, key=lambda i: (-i["pagerank"], i["key"]))
    pos = {name: {i["key"]: r for r, i in enumerate(order)} for name, order in
           (("bottom_up", bottom_up), ("pressure", items), ("graph", graph))}
    keys = [i["key"] for i in items]

    def tau(a, b):
        t = IM.kendall_tau_b([pos[a][k] for k in keys], [pos[b][k] for k in keys])
        return round(t, 4) if t is not None else None

    def overlap(a, b, n=TOP_K):
        sa = {k for k, r in pos[a].items() if r < n}
        sb = {k for k, r in pos[b].items() if r < n}
        return round(len(sa & sb) / len(sa | sb), 4) if sa | sb else None
    return {
        "bottom_up": [i["key"] for i in bottom_up],
        "action_queue": [i["key"] for i in items if i.get("actionable")],
        "agreement": {"kendall_tau_b": {"bottom_up~pressure": tau("bottom_up", "pressure"),
                                        "graph~pressure": tau("graph", "pressure"),
                                        "bottom_up~graph": tau("bottom_up", "graph")},
                      "top10_jaccard": {"bottom_up~pressure": overlap("bottom_up", "pressure"),
                                        "graph~pressure": overlap("graph", "pressure")},
                      "note": "top-down is bottom-up reversed: tau(top_down, x) = -tau(bottom_up, x)"},
        "lineage_roots": sorted(({"root": r, "open_root": bool(nodes[r].get("open")),
                                 "descendants": len(v), "longest": max(len(threads[x]) for x in v)}
                                for r, v in roots.items() if len(v) > 1 or r not in v),
                               key=lambda x: (-x["descendants"], x["root"]))[:25],
        "top_down": [i["key"] for i in top_down],
        "graph": [i["key"] for i in graph],
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
    # Progress (ticks) and scope (items added) are separate: 2/5 -> 3/6 is one
    # tick and one unit of scope growth, not zero movement.
    ticked = scope = 0
    for k in sorted(set(p_items) & set(c_items)):
        a, b = p_items[k]["checklist"], c_items[k]["checklist"]
        ticked += b["done"] - a["done"]
        scope += b["total"] - a["total"]
    known = set(p_items) | {x for e in p_edges for x in e[:2]}
    new = sorted(set(c_items) - set(p_items))
    rooted = [k for k in new if any(k in e[:2] and (set(e[:2]) - {k}) & known for e in c_edges)]
    gone = sorted(set(p_items) - set(c_items))
    reason = {x["key"]: x.get("state_reason") for x in cur.get("closed_in_window") or []}
    thread_moves = Counter()
    for k in sorted(set(p_items) & set(c_items)):
        a = (p_items[k].get("golden_thread") or {}).get("position")
        b = (c_items[k].get("golden_thread") or {}).get("position")
        if isinstance(a, int) and isinstance(b, int) and a != b:
            thread_moves["advanced" if b > a else "regressed"] += 1
    return {"baseline": False, "since": prev["fetched_at"],
            "new_items": new, "new_items_rooted": rooted,
            "new_items_unrooted": [k for k in new if k not in rooted],
            "gone_items": gone,
            "gone_closed_completed": [k for k in gone if reason.get(k) == "COMPLETED"],
            "gone_closed_not_planned": [k for k in gone if reason.get(k) == "NOT_PLANNED"],
            "new_links": [list(e) for e in new_edges],
            "removed_links": [list(e) for e in sorted(p_edges - c_edges)],
            "new_pr_dependencies": [list(e) for e in new_edges if e[2] == "CLOSES"],
            "checklist_moves": ticks, "lane_moves": lane_moves,
            "tasks_ticked_net": ticked, "scope_added_net": scope,
            "thread_moves": dict(sorted(thread_moves.items())),
            "taxonomy_moves": taxonomy_moves}


def telemetry(model: dict, snap: dict, delta: dict) -> dict:
    roll = model["rollups"]
    return {"fetched_at": model["fetched_at"], "fetch": snap.get("telemetry"),
            "heads": {r: h["head_sha"] for r, h in model["heads"].items()},
            "graph": {k: v for k, v in model["graph"].items() if k not in ("deadlocks", "critical_chain")},
            "method": {"version": model["method"]["version"], "walk": model["method"]["walk"],
                       "monte_carlo": model["method"]["monte_carlo"],
                       "relations_complete": model["authority"]["source_relations_complete"],
                       "relation_capped_items": model["authority"]["nested_relation_capped_items"]},
            "predicate_leaks": len(model.get("predicate_leaks") or []),
            "scopes": {s: {k: v for k, v in r.items() if k not in ("top", "bottlenecks", "nearly_finished",
                                                                    "action_queue", "robust_top", "by_assignee")}
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


PRIVATE_KEY = re.compile(r"(GBOGEB/[A-Za-z0-9_.-]+)#(\d+)")


def redact(model: dict, delta: dict | None = None, private_repos=None):
    """Project private-repository items to pseudonyms, then through private_boundary.

    Every private key (``owner/repo#N``), wherever it appears (items, edges,
    views, rollups, lineages, the delta), becomes ``owner/repo#PRIVATE-007``,
    numbered in rank order so the pseudonym carries no issue number. Titles,
    URLs, numbers, labels, assignees, overlay notes and free-text actions of
    private items are dropped, and private head SHAs are removed. The result is
    then projected by ``jade_temple/tools/private_boundary.py`` (the owner of the
    aggregate-only rule) and must be a fixed point of it. Pseudonyms are stable
    within one pulse only, so private deltas are counts, not identities.
    """
    priv = set(private_repos or ()) | {r for r, h in model["heads"].items() if h.get("private")}
    pb = _boundary()
    try:
        priv |= set(pb.private_repos())
    except (OSError, ValueError, KeyError):
        pass
    alias: dict[str, str] = {}

    def name(k: str) -> str:
        if k not in alias:
            alias[k] = f"{k.split('#', 1)[0]}#PRIVATE-{len(alias) + 1:03d}"
        return alias[k]
    for i in model["items"]:
        if i["repo"] in priv:
            name(i["key"])

    def walk(o):
        if isinstance(o, dict):
            return {walk(k) if isinstance(k, str) else k: walk(v) for k, v in o.items()}
        if isinstance(o, list):
            return [walk(v) for v in o]
        if isinstance(o, str):
            return PRIVATE_KEY.sub(lambda m: name(m.group(0)) if m.group(1) in priv else m.group(0), o)
        return o
    out = walk(json.loads(json.dumps({"model": model, "delta": delta})))
    m = out["model"]
    private_refs = {i["key"] for i in m["items"] if i["repo"] in priv}
    for i in m["items"]:
        if i["repo"] not in priv and "title_taxonomy" in i:  # no family candidate sourced from a private item
            i["title_taxonomy"]["related_families"] = [
                r for r in i["title_taxonomy"].get("related_families", []) if r["source_item"] not in private_refs]
        if i["repo"] in priv:
            i["title_taxonomy"] = {"schema": tt.SCHEMA, "family": "REDACTED_PRIVATE",
                                   "path": "REDACTED_PRIVATE", "programmes": [], "codes": [],
                                   "topic_families": [], "technical_clusters": [],
                                   "classification": "UNCLASSIFIED", "lint": [], "related_families": []}
            i.update(title=None, url=None, number=None, labels=[], assignees=[], overlay=None)
            i["checklist"]["next_open"] = None
            if i["action"].startswith(("next:", "start:")):
                i["action"] = i["action"].split(":")[0] + ": <private>"
    # Prove private HEAD validity before removing identifiers from public output.
    # The projection mark is not a replacement for the original source receipt.
    redacted_heads = []
    for r, h in m["heads"].items():
        if r in priv:
            original = model["heads"][r].get("head_sha")
            if not isinstance(original, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", original):
                raise ValueError("INVALID_SOURCE_HEAD_BEFORE_REDACTION:" + r)
            h["head_sha"] = None
            redacted_heads.append(r)
    m["privacy_projection"] = {"validated_then_redacted_heads": sorted(redacted_heads)}
    jade, focus = set(jade_roster()), {f"{m['owner']}/{r}" for r in FOCUS_REPOS}
    for scope, roll in m["rollups"].items():
        members = (set(m["heads"]) if scope == "USER" else jade if scope == "JADE"
                   else focus if scope == "FOCUS4" else {scope})
        visible = [i for i in m["items"] if i["repo"] in members and i["repo"] not in priv]
        roll["title_taxonomy"] = tt.summary(visible)
        # A named private assignee is a row-level fingerprint, not an aggregate.
        roll["by_assignee"] = _by_assignee(visible)
        roll["title_taxonomy"]["private_items_excluded"] = sum(
            1 for i in m["items"] if i["repo"] in members and i["repo"] in priv)
    # Export only aggregate private counts. Individual pseudonyms still expose
    # timestamps, rank intervals and graph fingerprints across repeated pulses.
    # Strip private rows and cross-references *before* the boundary fixed point.
    def private_key(value):
        return (isinstance(value, str) and "#" in value
                and value.split("#", 1)[0] in priv)

    def private_row(value):
        return (isinstance(value, dict) and
                (value.get("repo") in priv or
                 any(private_key(value.get(k)) for k in ("key", "source", "target", "pr", "root"))))

    def export_public(value):
        if isinstance(value, dict):
            return {k: export_public(v) for k, v in value.items()
                    if not private_key(k)}
        if isinstance(value, list):
            return [export_public(v) for v in value
                    if not private_key(v) and not private_row(v)]
        if isinstance(value, str) and any(r + "#PRIVATE-" in value for r in priv):
            return "<private aggregate>"
        return value

    # Freeze public-only lineage while private pseudonyms are still visible to
    # the detector. export_public() strips those hops, so scanning afterwards
    # would silently join public nodes across a private intermediary.
    safe_public_threads = {}
    for item in m["items"]:
        if item["repo"] in priv:
            continue
        item_key = item["key"]
        source_path = item.get("lineage") or [item_key]
        last_private = max(
            (n for n, node in enumerate(source_path) if private_key(node)),
            default=-1,
        )
        safe_path = [node for node in source_path[last_private + 1:]
                     if not private_key(node)]
        safe_public_threads[item_key] = (
            safe_path if safe_path and safe_path[-1] == item_key else [item_key]
        )

    out = export_public(out)
    # Preserve public closed/stub ancestors only when the full source path
    # contains no intervening private node. No graph bridge through secrecy.
    public_model = out["model"]
    public_items = {i["key"]: i for i in public_model["items"]}
    public_threads = {key: safe_public_threads.get(key, [key])
                      for key in public_items}
    public_roots = defaultdict(list)
    for item_key, thread in public_threads.items():
        public_roots[thread[0]].append((item_key, len(thread)))
    for item_key, item in public_items.items():
        item["lineage"] = public_threads[item_key]
    public_model["views"]["lineage_roots"] = sorted(
        ({"root": root, "open_root": root in public_items,
          "descendants": len(children),
          "longest": max(length for _, length in children)}
         for root, children in public_roots.items()
         if len(children) > 1 or root not in {key_ for key_, _ in children}),
        key=lambda x: (-x["descendants"], x["root"]))[:25]
    public_model["privacy_projection"]["public_lineage_recomputed"] = True
    if out.get("delta") is not None:
        out["delta"]["private_item_movement"] = "UNKNOWN_AGGREGATE_ONLY"
    boundary = pb.Boundary(sorted(priv))
    out = boundary.project(out)
    if boundary.project(out) != out:
        raise ValueError("redacted model is not a fixed point of private_boundary")
    return out["model"] if delta is None else (out["model"], out["delta"])


CSV_COLS = ("rank_global", "rank_repo", "key", "type", "lane", "score", "rank_p05", "rank_p95", "p_top",
            "urgency", "coverage", "inherited_share", "progress", "thread", "first_break", "pressure",
            "unblocks_now", "chain_below", "open_blockers", "linked_prs", "age_days", "idle_days", "action", "title",
            "family", "prefix_path", "prefix_codes", "topic_families", "technical_clusters",
            "related_family_candidates")


def _csv_value(i: dict, c: str):
    ri, gt = i.get("rank_interval") or {}, i.get("golden_thread") or {}
    tax = i.get("title_taxonomy") or {}
    if c == "family":
        return tax.get("family", "")
    if c == "prefix_path":
        return tax.get("path", "")
    if c == "prefix_codes":
        return ";".join(tax.get("codes", []))
    if c in ("topic_families", "technical_clusters"):
        return ";".join(tax.get(c, []))
    if c == "related_family_candidates":
        return ";".join(r["family"] for r in tax.get("related_families", []))
    if c == "open_blockers":
        return " ".join(i[c])
    if c == "linked_prs":
        return " ".join(p["pr"] for p in i[c])
    if c in ("rank_p05", "rank_p95", "p_top"):
        return ri.get({"rank_p05": "p05", "rank_p95": "p95", "p_top": "p_top"}[c])
    if c == "thread":
        return f"{gt.get('position')}/{gt.get('of')}" if gt else None
    if c == "first_break":
        return gt.get("first_break")
    if c == "chain_below":
        return (i.get("chain") or {}).get("below")
    return i.get(c)


def to_csv(model: dict) -> str:
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(CSV_COLS)
    for i in model["items"]:
        w.writerow([_csv_value(i, c) for c in CSV_COLS])
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

    def interval(i):
        ri = i.get("rank_interval")
        return "" if not ri else "%g-%g" % (ri["p05"], ri["p95"])

    def thread(i):
        gt = i.get("golden_thread")
        if not gt:
            return ""
        brk = gt["first_break"] or "closable"
        return "%d/%d %s" % (gt["position"], gt["of"], esc(brk))

    def row(i):
        return (f'<tr><td class="num">{i["rank_global"]}</td><td>{link(i["key"])}</td>'
                f'<td><span class="lane l-{i["lane"]}">{i["lane"]}</span></td>'
                f'<td class="num">{i["score"]:.3f}</td><td class="num">{interval(i)}</td>'
                f'<td>{bar(i)}</td><td>{thread(i)}</td><td class="num">{i["pressure"]}</td>'
                f'<td>{" ".join(link(b) for b in i["open_blockers"][:4])}</td>'
                f'<td class="num">{i["age_days"]:.0f}</td><td>{esc(i["action"])}</td>'
                f'<td>{esc((i.get("title_taxonomy") or {}).get("path", "UNKNOWN"))}</td>'
                f'<td>{esc(i.get("title") or "")}</td></tr>')

    head = ('<tr><th>#</th><th>item</th><th>lane</th><th>score</th><th>rank 90%</th>'
            '<th>progress (DoD/DoV/steps)</th><th>golden thread</th>'
            '<th>pressure</th><th>open blockers</th><th>age d</th><th>next action</th>'
            '<th>family / prefix path</th><th>title</th></tr>')

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
        for g in model["views"]["lineage_roots"])
    nearly = model["rollups"]["USER"]["nearly_finished"]
    # Built outside the page template: no nested f-strings (Python 3.11 tokenizer).
    heads = " ".join("%s@%s" % (esc(r.split("/")[1]), (h["head_sha"] or "?")[:12])
                     for r, h in model["heads"].items())
    kinds = ", ".join("%s %d" % kv for kv in model["graph"]["edges_by_kind"].items())
    formula = " + ".join("%s·%s" % (v, k) for k, v in model["weights"].items())
    mc = model["method"]["monte_carlo"]
    agree = model["views"]["agreement"]["kendall_tau_b"]
    agree_html = " · ".join("%s %s" % (esc(k), "n/a" if v is None else "%.2f" % v) for k, v in agree.items())

    def flow_row(name, r):
        f = r.get("flow")
        if not f:
            return ""
        eta = f["eta_days"]
        eta_txt = "%s d (%s-%s)" % (eta["est"], eta["lo"], eta["hi"]) if eta else f["status"]
        return (f'<tr><td>{esc(name)}</td><td class="num">{f["wip_open_issues"]}</td>'
                f'<td class="num">{f["arrivals"]["per_day"]} ({f["arrivals"]["lo"]}-{f["arrivals"]["hi"]})</td>'
                f'<td class="num">{f["closures"]["per_day"]} ({f["closures"]["lo"]}-{f["closures"]["hi"]})</td>'
                f'<td class="num">{f["net_burn_per_day"]["est"]}</td><td>{esc(eta_txt)}</td>'
                f'<td class="num">{r.get("predicate_leaks", 0)}</td>'
                f'<td>{esc(" ".join("%s:%d" % kv for kv in r.get("thread_funnel", {}).items()))}</td></tr>')
    flows = "".join(flow_row(s, r) for s, r in model["rollups"].items())
    leaks = "".join(f'<tr><td>{link(x["key"])}</td><td class="num">{esc(x["progress"])}</td>'
                    f'<td>{esc(x.get("closed_at") or "")}</td></tr>' for x in model.get("predicate_leaks", []))
    dead = "; ".join(", ".join(link(k) for k in c) for c in model["graph"].get("deadlocks", [])) or "none"
    crit = " &rarr; ".join(link(k) for k in model["graph"].get("critical_chain", [])) or "none"
    parked = [i["key"] for i in model["items"] if i.get("parked")]
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
.l-BLOCKED,.l-FIX_RED,.l-DEADLOCK{color:var(--bad)}.l-PARKED{color:var(--muted)}.l-BOTTLENECK,.l-DEFINE_DOD{color:var(--warn)}
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
<h2>Action queue (actionable only, pressure order)</h2>
<p class="muted">Pressure = PageRank on waiter &rarr; blocker, restarting in proportion to urgency = {formula}
(unknown parts at the scope mean, never 0). Score = own + inherited urgency. Rank 90% interval from
{mc["draws"]} Monte Carlo draws (Spearman median {mc.get("spearman_median")}). View agreement (Kendall tau-b): {agree_html}.</p>
<div class="wrap">{table(model["views"]["action_queue"], 30)}</div>
<h2>Flow and burndown (window)</h2><div class="wrap"><table><tr><th>scope</th><th>open issues</th>
<th>arrivals/d (90%)</th><th>closures/d (90%)</th><th>net/d</th><th>ETA</th><th>predicate leaks</th><th>golden-thread first break</th></tr>{flows}</table></div>
<h2>Structure: deadlocks, critical chain, leaks, parked</h2>
<p>Dependency cycles: {dead}</p><p>Longest blocker chain: {crit}</p>
<div class="wrap"><table><tr><th>closed with open items, no successor</th><th>ticked</th><th>closed at</th></tr>{leaks}</table></div>
<p class="muted">Parked intents ({len(parked)}): {" ".join(link(k) for k in parked)}</p>
<h2>Title family census · disjoint counts per repository and total</h2>
<div class="wrap"><table><tr><th>scope</th><th>family</th><th>issues</th><th>PRs</th><th>total</th></tr>{taxonomy_rows}</table></div>
<h2>Nested clusters · USER leaf paths (non-additive ancestry)</h2>
<div class="wrap"><table><tr><th>prefix path</th><th>issues</th><th>PRs</th><th>total</th></tr>{cluster_rows}</table></div>
<h2>Topic families · overlapping title / label associations</h2>
<div class="wrap"><table><tr><th>scope</th><th>topic</th><th>issues</th><th>PRs</th><th>matches</th></tr>{topic_rows}</table></div>
<h2>Technical clusters · overlapping title / label associations</h2>
<div class="wrap"><table><tr><th>scope</th><th>cluster</th><th>issues</th><th>PRs</th><th>matches</th></tr>{technical_rows}</table></div>
<h2>All items (pressure order)</h2>
<div class="wrap">{table([i["key"] for i in model["items"]], 60)}</div>
<h2>Nearly finished / close candidates</h2><div class="wrap">{table(nearly, 30)}</div>
<h2>Bottlenecks (unblock pressure)</h2><div class="wrap">{table(model["rollups"]["USER"]["bottlenecks"], 20)}</div>
<h2>1 · Bottom-up: oldest first + golden thread</h2>
<p class="muted">Golden thread = lifecycle gates (rolling5.golden_thread); lineage roots below are provenance.</p>
<div class="wrap"><table><tr><th>lineage root</th><th>state</th><th>open descendants</th><th>longest chain</th></tr>{roots}</table></div>
<div class="wrap">{table(model["views"]["bottom_up"], 30)}</div>
<h2>2 · Top-down: newest first (mycelium)</h2><div class="wrap">{table(model["views"]["top_down"], 30)}</div>
<h2>3 · Graph: PageRank order</h2><div class="wrap">{table(model["views"]["graph"], 30)}</div>
</body></html>
"""


def _fmt_pct(x):
    return "n/a" if x is None else f"{100 * x:.0f}%"


def write_outputs(out: Path, model: dict, delta: dict, *,
                  previous_model: dict | None = None, parser_sha: str | None = None,
                  previous_parser_sha: str | None = None, pulse_model: dict | None = None) -> dict[str, str]:
    """Write taxonomy pulse through the existing single-writer output manifest.

    ``pulse_model`` is the unredacted model: taxonomy_pulse validates source
    identities and heads first, then drops private material itself (public=True).
    """
    out.mkdir(parents=True, exist_ok=True)
    pulse = tp.build(pulse_model or model, previous_model, public=True, parser_sha=parser_sha,
                     previous_parser_sha=previous_parser_sha)
    files = {"issue_rank.json": canonical(model), "issue_rank.csv": to_csv(model).encode("utf-8"),
             "issue_rank.html": render_html(model, delta).encode("utf-8"), "delta.json": canonical(delta),
             "taxonomy_pulse.json": tp.canonical(pulse) + b"\n",
             "taxonomy_pulse.csv": tp.csv_view(pulse).encode("utf-8")}
    for name, data in files.items():
        (out / name).write_bytes(data)
    return {name: sha256(data) for name, data in files.items()}

# ---------------------------------------------------------------- CLI

OVERLAY_SCHEMA = "jade.issue-rank.overlay.v1"


def load_overlay(paths=None) -> dict:
    """key -> {priority, lane, source}. Owner-declared priority with provenance
    (DECLARED, not observed); later files win. Defaults: the committed public
    overlay.json, then the gitignored out/overlay_private.json."""
    paths = paths if paths is not None else [HERE / "overlay.json", DEFAULT_OUT / "overlay_private.json"]
    out = {}
    for path in paths:
        if not Path(path).exists():
            continue
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        if doc.get("schema") != OVERLAY_SCHEMA:
            raise ValueError(f"{path}: not an {OVERLAY_SCHEMA} document")
        for e in doc.get("entries") or []:
            out[e["key"]] = {"priority": e.get("priority"), "lane": e.get("lane"),
                             "source": e.get("source") or doc.get("source")}
    return out


def _repos(args, gh) -> list[str]:
    if args.repos:
        return args.repos
    if args.scope == "user":
        return sorted(set(list_repos(gh, args.owner)) | {r.split("/", 1)[1] for r in jade_roster()})
    if args.scope == "jade":
        return [r.split("/", 1)[1] for r in jade_roster()]
    return list(FOCUS_REPOS)


def _positive_window_days(raw: str) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("window-days must be a positive integer") from exc
    if value <= 0:
        raise argparse.ArgumentTypeError("window-days must be a positive integer")
    return value


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("fetch", "run"):
        p = sub.add_parser(name)
        p.add_argument("--owner", default=OWNER)
        p.add_argument("--scope", choices=("focus", "jade", "user"), default="focus",
                       help="focus: the four federated repos; jade: TOP21 roster; user: every repo with open items")
        p.add_argument("--window-days", type=_positive_window_days, default=14)
        p.add_argument("--repos", nargs="*")
        p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    r = sub.add_parser("rank")
    r.add_argument("--snapshot", type=Path, required=True)
    r.add_argument("--prev", type=Path, help="previous issue_rank.json, for the delta")
    r.add_argument("--out", type=Path, default=DEFAULT_OUT)
    for p in (sub.choices["run"], r):
        p.add_argument("--parser-sha", help="exact parser source SHA for taxonomy attribution")
        p.add_argument("--previous-parser-sha", help="previous parser source SHA")
        p.add_argument("--redact-private", action="store_true")
        p.add_argument("--draws", type=int, default=MC_DRAWS, help="Monte Carlo draws (0 disables)")
        p.add_argument("--overlay", type=Path, action="append", default=None,
                       help="owner priority overlay JSON (repeatable); default overlay.json and out/overlay_private.json")
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
        snap = fetch(gh, _repos(args, gh), args.owner, window_days=args.window_days)
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
    model = rank(snap, overlay=load_overlay(args.overlay), draws=args.draws)
    full = model  # validate source heads before public projection in taxonomy_pulse
    def comparable_public(m):
        if m is None:
            return None
        private = {r for r, h in m["heads"].items() if h.get("private")}
        is_private = lambda k: isinstance(k, str) and k.split("#", 1)[0] in private
        return {**m,
                "items": [i for i in m["items"] if i["repo"] not in private],
                "edges": [e for e in m["edges"] if not is_private(e["source"])
                          and not is_private(e["target"])]}
    redacted_prev = bool(prev and any(
        h.get("private") and not h.get("head_sha") for h in prev.get("heads", {}).values()))
    if args.redact_private or redacted_prev:
        # A public comparison cannot match pulse-local pseudonyms to raw private
        # identities. Withhold private movement rather than fabricate new/gone.
        delta = diff(comparable_public(prev), comparable_public(model))
        delta["private_item_movement"] = "UNKNOWN_AGGREGATE_ONLY"
    else:
        delta = diff(prev, model)
    if args.redact_private:
        private_refs = {i["key"] for i in model["items"] if i.get("private")}
        if isinstance(delta.get("taxonomy_moves"), list):
            delta["taxonomy_moves"] = [d for d in delta["taxonomy_moves"]
                                       if d["key"] not in private_refs]
        model, delta = redact(model, delta)
    # A repeated source observation at the exact same instant is not N+1.
    # No source-validated taxonomy history is inferred from a redacted old head.
    # A prior pulse projected by the canonical private boundary still supplies
    # valid public taxonomy history and a source-validated redaction marker;
    # unknown private movement remains withheld in delta, never reidentified.
    pulse_previous = prev
    if prev is not None:
        old_time = datetime.fromisoformat(prev["fetched_at"].replace("Z", "+00:00"))
        new_time = datetime.fromisoformat(model["fetched_at"].replace("Z", "+00:00"))
        if old_time == new_time:
            pulse_previous = None
        elif old_time > new_time:
            raise ValueError("PULSE_TIMESTAMP_REVERSED")
    digests = write_outputs(
        out, model, delta, previous_model=pulse_previous, pulse_model=full,
        parser_sha=args.parser_sha, previous_parser_sha=args.previous_parser_sha)
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
