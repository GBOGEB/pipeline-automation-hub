#!/usr/bin/env python3
"""CODE MAROON open-PR source: every review thread on every OPEN pull request, with what it needs to act.

`review_threads.py` reads closed PRs (post-merge debt). This module reads the PRs that are still open,
because their unresolved threads are what blocks a merge today. For each open PR it records one pulse
(AGENTS.md L6): the PR head SHA, merge state, changed files and commits, and per thread:

- resolution and outdated state, and the GraphQL thread id needed to resolve it;
- the last comment (login and body), so an evidence reply already posted is recognised;
- whether the thread's path is still changed by the PR at its head;
- whether its anchor line and any ```suggestion``` block are present in the file at the head.

Thread records extend `review_threads.threads_of` (imported, AGENTS.md L4), so theme, severity and
reviewer family are the same as for closed-PR threads. Raw output holds review text and paths: private.
It writes nothing to GitHub.

    python open_threads.py fetch --owner GBOGEB --out <private dir>                 # every repo with open PRs
    python open_threads.py fetch --repos GBOGEB/ABACUS,GBOGEB/CODEX --out <dir>
"""
from __future__ import annotations

import argparse
import concurrent.futures
import importlib.util
import json
import re
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA = "code_maroon.open_raw.v1"
_SPEC = importlib.util.spec_from_file_location("maroon_review_threads", HERE / "review_threads.py")
RT = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(RT)

SUGGESTION_RE = re.compile(r"```suggestion[^\n]*\n(.*?)```", re.S)
MAX_FILE_BYTES = 400_000  # anchor checks read the file at head; skip anything larger
TRANSIENT_RE = re.compile(r"connect|timed? ?out|EOF|reset by peer|HTTP 50[234]|Bad Gateway|Service Unavailable|"
                          r"secondary rate limit", re.I)
WORKERS = 4  # PRs read in parallel; GitHub's secondary rate limit punishes more


def retrying(gh, attempts: int = 4, pause: float = 2.0, sleep=time.sleep):
    """`gh` that retries transient network and 5xx failures with exponential backoff. Other errors return."""
    def call(args):
        for attempt in range(attempts):
            code, out, err = gh(args)
            if code == 0 or not TRANSIENT_RE.search(err or "") or attempt == attempts - 1:
                return code, out, err
            sleep(pause * 2 ** attempt)
        return code, out, err
    return call
THREADS_QUERY = """
query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes { id isResolved isOutdated comments(first: 1) { nodes { databaseId } } }
      }
    }
  }
}"""


def thread_index_graphql(gh, repo: str, number: int) -> dict[int, dict]:
    """Root comment id -> {thread_id, resolved, outdated}, through GraphQL (any `gh` login)."""
    owner, name = repo.split("/", 1)
    out, cursor = {}, None
    for _ in range(20):
        args = ["api", "graphql", "-f", f"query={THREADS_QUERY}", "-f", f"owner={owner}", "-f", f"name={name}",
                "-F", f"number={number}"] + (["-f", f"cursor={cursor}"] if cursor else [])
        code, stdout, err = gh(args)
        if code:
            raise RuntimeError(f"review threads {repo}#{number}: {err.strip()[:200]}")
        data = (((json.loads(stdout).get("data") or {}).get("repository") or {}).get("pullRequest") or {})
        page = data.get("reviewThreads") or {}
        for node in page.get("nodes") or []:
            first = ((node.get("comments") or {}).get("nodes") or [{}])[0].get("databaseId")
            if first:
                out[int(first)] = {"thread_id": node["id"], "resolved": bool(node.get("isResolved")),
                                   "outdated": bool(node.get("isOutdated"))}
        info = page.get("pageInfo") or {}
        if not info.get("hasNextPage"):
            return out
        cursor = info.get("endCursor")
    raise RuntimeError(f"review threads {repo}#{number}: more than 2000 threads")


def thread_index_ccr(gh, repo: str, number: int) -> dict[int, dict]:
    """Claude Code cloud sessions only: their REST route. It has no thread id or outdated flag."""
    threads = RT.gh_json(gh, f"repos/{repo}/pulls/{number}/ccr/review_threads") or []
    return {t["comment_ids"][0]: {"thread_id": None, "resolved": bool(t.get("resolved")),
                                  "outdated": bool(t.get("outdated"))}
            for t in threads if t.get("comment_ids")}


def file_at(gh, repo: str, path: str, sha: str, cache: dict) -> str | None:
    """File text at a commit, or None when it is absent, binary or too large. Cached per (path, sha)."""
    key = (path, sha)
    if key not in cache:
        code, out, _ = gh(["api", "-H", "Accept: application/vnd.github.raw",
                           f"repos/{repo}/contents/{urllib.parse.quote(path, safe='/')}?ref={sha}"])
        cache[key] = out if (code == 0 and len(out) <= MAX_FILE_BYTES and "\x00" not in out) else None
    return cache[key]


def squash(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def head_evidence(thread: dict, root_body: str, text: str | None) -> dict:
    """What the file at the PR head says about a thread: anchor still there, suggestion applied."""
    if text is None:
        return {"file_at_head": False, "anchor_at_head": None, "suggestion_applied": None}
    flat = squash(text)
    anchor = thread.get("anchor")
    suggestions = [squash(s) for s in SUGGESTION_RE.findall(root_body or "") if squash(s)]
    return {"file_at_head": True,
            # a short anchor (`}` or `return x`) is weak evidence either way: record None, not a verdict
            "anchor_at_head": (squash(anchor) in flat) if anchor and len(anchor.strip()) >= 12 else None,
            "suggestion_applied": all(s in flat for s in suggestions) if suggestions else None}


def open_prs(gh, owner: str | None, repos: list[str] | None) -> dict[str, list[int]]:
    """Open PR numbers per repository: the named repositories, or every repository of the owner with one."""
    if repos:
        return {r: sorted(p["number"] for p in RT.gh_json(gh, f"repos/{r}/pulls?state=open&per_page=100", paginate=True))
                for r in repos}
    code, out, err = gh(["search", "prs", "--owner", owner, "--state", "open", "--limit", "1000",
                         "--json", "repository,number"])
    if code:
        raise RuntimeError("gh search prs failed: " + err.strip()[:200])
    found: dict[str, list[int]] = {}
    for item in json.loads(out or "[]"):
        found.setdefault(item["repository"]["nameWithOwner"], []).append(item["number"])
    return {r: sorted(ns) for r, ns in sorted(found.items())}


def read_pr(gh, repo: str, number: int, index_of, file_cache: dict) -> dict:
    pr = RT.gh_json(gh, f"repos/{repo}/pulls/{number}")
    head = pr["head"]["sha"]
    comments = RT.gh_json(gh, f"repos/{repo}/pulls/{number}/comments?per_page=100", paginate=True)
    reviews = RT.gh_json(gh, f"repos/{repo}/pulls/{number}/reviews?per_page=100", paginate=True)
    files = [f["filename"] for f in RT.gh_json(gh, f"repos/{repo}/pulls/{number}/files?per_page=100", paginate=True)]
    commits = [c["sha"] for c in RT.gh_json(gh, f"repos/{repo}/pulls/{number}/commits?per_page=100", paginate=True)]
    index = index_of(gh, repo, number) if comments else {}
    resolved = {cid for cid, t in index.items() if t["resolved"]}
    by_id = {c["id"]: c for c in comments}
    replies: dict[int, list[dict]] = {}
    for c in comments:
        if c.get("in_reply_to_id"):
            replies.setdefault(c["in_reply_to_id"], []).append(c)
    threads = []
    for t in RT.threads_of(pr, comments, reviews, resolved):
        root = by_id[t["number"]]
        last = sorted(replies.get(t["number"], []), key=lambda c: (c.get("created_at") or "", c["id"]))
        last = last[-1] if last else root
        meta = index.get(t["number"], {})
        t.update({
            "thread_id": meta.get("thread_id"), "outdated": meta.get("outdated", root.get("position") is None),
            "last_login": (last.get("user") or {}).get("login"), "last_body": (last.get("body") or "")[:2000],
            "last_id": last["id"], "body": (root.get("body") or "")[:4000],
            "path_in_pr": t.get("path") in files,
        })
        if t["state"] == "open" and t.get("path"):
            t.update(head_evidence(t, root.get("body"), file_at(gh, repo, t["path"], head, file_cache)))
        threads.append(t)
    return {"number": number, "title": pr.get("title"), "author": (pr.get("user") or {}).get("login"),
            "draft": bool(pr.get("draft")), "head_ref": pr["head"]["ref"], "head_sha": head,
            "head_repo": ((pr["head"].get("repo") or {}).get("full_name")), "base_ref": pr["base"]["ref"],
            "mergeable_state": pr.get("mergeable_state"), "labels": [l["name"] for l in pr.get("labels") or []],
            "updated_at": pr.get("updated_at"), "body_refs": RT.refs_of(pr.get("body"), number),
            "files": files, "commits": commits, "threads": threads}


def fetch(owner: str | None = None, repos: list[str] | None = None, gh=RT.run_gh, index_of=thread_index_graphql) -> dict:
    gh = retrying(gh)
    raw = {"schema": SCHEMA, "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "owner": owner or (repos[0].split("/")[0] if repos else None), "repos": {}}
    for repo, numbers in open_prs(gh, owner, repos).items():
        entry = {"coverage": "ok", "prs": [], "gaps": []}
        try:
            entry["base_head_sha"] = RT.gh_json(gh, f"repos/{repo}/commits/HEAD")["sha"]  # L6
        except RuntimeError as error:
            raw["repos"][repo] = {"coverage": "not_readable", "error": str(error)[:200], "prs": []}
            continue
        cache: dict = {}

        def one(number, repo=repo, cache=cache):
            try:
                return read_pr(gh, repo, number, index_of, cache), None
            except (RuntimeError, KeyError, ValueError) as error:  # one unreadable PR is a gap, not the end
                return None, {"pr": number, "error": str(error)[:200]}
        with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
            for pr, gap in pool.map(one, numbers):  # map keeps PR order: the raw file is deterministic
                if pr:
                    entry["prs"].append(pr)
                else:
                    entry["gaps"].append(gap)
        if entry["gaps"]:
            entry["coverage"] = "partial"
        raw["repos"][repo] = entry
    return raw


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="read every open PR's review threads")
    who = f.add_mutually_exclusive_group(required=True)
    who.add_argument("--owner")
    who.add_argument("--repos", help="comma-separated OWNER/REPO list")
    f.add_argument("--threads", choices=("graphql", "ccr"), default="graphql")
    f.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)
    repos = [r.strip() for r in args.repos.split(",") if r.strip()] if args.repos else None
    raw = fetch(args.owner, repos, index_of=thread_index_ccr if args.threads == "ccr" else thread_index_graphql)
    args.out.mkdir(parents=True, exist_ok=True)
    target = args.out / "raw_open.json"
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8", newline="\n")
    tmp.replace(target)
    prs = sum(len(e["prs"]) for e in raw["repos"].values())
    threads = sum(len(p["threads"]) for e in raw["repos"].values() for p in e["prs"])
    gaps = sum(len(e.get("gaps", [])) + (e["coverage"] == "not_readable") for e in raw["repos"].values())
    print("MAROON_OPEN_FETCH=PASS", f"repos={len(raw['repos'])}", f"prs={prs}", f"threads={threads}",
          f"gaps={gaps}", f"out={target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
