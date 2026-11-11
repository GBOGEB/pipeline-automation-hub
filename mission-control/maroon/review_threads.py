#!/usr/bin/env python3
"""CODE MAROON review-thread source: active pull requests and historical review debt.

A merged PR can carry open review threads from Copilot, Codex, a security bot or a person. Nothing
re-reads them after the merge, so they become silent debt. This module reads the most recent closed
PRs of named repositories, newest first, and hands every review thread to the MAROON receipt as a
manifestation of the `review_threads` source:

- an unresolved thread is `outstanding`, a resolved one `closed`;
- its root is a theme (path aliasing, digest pins, ...) in one repository, so one root is one
  follow-up PR, even when Copilot and Codex flag the same defect twice;
- its severity is the reviewer's own (Codex P badge, Copilot's High/Medium/Low), mapped onto
  `maroon.RANK`.

Thread resolution comes from GraphQL in Actions, through `first_pass_closure_gate.resolved_thread_roots`
(imported, not copied: AGENTS.md L4). Claude Code sessions cannot reach GraphQL and pass
`--threads ccr` to use the session's REST route instead.

The raw file holds review text and paths: private only. `maroon.public_projection` keeps counts.
It closes no thread and has no merge authority.

    python review_threads.py fetch --repos GBOGEB/CODEX,GBOGEB/ABACUS --limit 30 --out <private dir>
    python maroon.py build --raw <dir>/raw.json --review <dir>/raw_review.json --out <dir>
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA = "code_maroon.review_raw.v1"

_spec = importlib.util.spec_from_file_location("first_pass_closure_gate", HERE.parents[1] / "scripts" / "first_pass_closure_gate.py")
FPC = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(FPC)

REVIEWERS = [
    # reviewer family -> logins; anything else ending in [bot] is "other-bot", the rest "human"
    ("copilot", re.compile(r"^(Copilot|copilot-pull-request-reviewer\[bot\])$")),
    ("codex", re.compile(r"^" + re.escape(FPC.DEFAULT_CODEX_LOGIN) + r"(\[bot\])?$")),
    ("codeql", re.compile(r"^github-advanced-security(?:\[bot\])?$")),
    ("semgrep", re.compile(r"semgrep", re.I)),
    ("sonar", re.compile(r"sonar", re.I)),
    ("other-bot", re.compile(r"\[bot\]$")),
]
# Theme = root subject. A triage heuristic over the finding's first line, in order; a deep read may
# re-theme a manifestation. Keep the list short: each theme is meant to be one follow-up PR per repo.
THEMES = [
    ("path-alias", r"alias|overwrit|same file|hard ?link|symlink|refers to (either|an) input"),
    ("private-leak", r"worktree|\bcheckout\b|git ancestor|leak|expos|private|reviewer text|publish"),
    ("provenance-pin", r"sha-?256|digest|\bhash\b|\bpin(ned)?\b|provenance|checksum"),
    ("fail-open", r"\bassert|python -O|silent|ignored|fail[- ]open|passes even|still pass|swallow|exit 0|reports success"),
    ("atomic-write", r"before (saving|writing|any)|temporary|atomic|partial|left (behind|on disk)|promot"),
    ("ooxml-integrity", r"ooxml|content.?type|\.rels\b|relationship|pptx|docx|xlsx|section ?lst|shape id|layout"),
    ("input-validation", r"schema|validat|malformed|missing (key|field)|type check|\benum\b"),
    ("ci-repro", r"workflow|\bci\b|runner|lockfile|\bnpm\b|\bpip\b|reproduc|deterministic"),
    ("security", r"secur|inject|\bsql\b|xss|csrf|ssrf|secret|credential|traversal|privilege|cve-\d|ghsa-|sanitiz|deserializ|shell=True"),
]
# CodeQL's PR comments project code-scanning alerts that the `code_scanning` source already reads, with
# their real state, from the alert API. Counting the threads too would count those findings twice.
DEFERRED_FAMILIES = {"codeql"}
SEVERITY = {"P0": "critical", "P1": "high", "P2": "medium", "P3": "low",
            "high": "high", "medium": "medium", "low": "low"}
COPILOT_SEVERITY_RE = re.compile(r'alt="(High|Medium|Low) severity".*?discussion_r(\d+)')


def reviewer_family(login: str | None) -> str:
    for name, pattern in REVIEWERS:
        if pattern.search(login or ""):
            return name
    return "human"


def finding_title(body: str) -> str:
    """The finding's first line without badges, HTML or bold markers."""
    text = re.sub(r"<[^>]+>|!\[[^\]]*\]\([^)]*\)|\*\*", "", body or "").strip()
    return text.splitlines()[0].strip()[:160] if text else ""


def theme_of(title: str) -> str:
    for name, pattern in THEMES:
        if re.search(pattern, title, re.I):
            return name
    return "other"


def copilot_severities(reviews: list[dict]) -> dict[int, str]:
    """Copilot's review overview lists each finding's severity next to a link to its thread."""
    found = {}
    for review in reviews:
        for level, cid in COPILOT_SEVERITY_RE.findall(review.get("body") or ""):
            found[int(cid)] = level.lower()
    return found


def severity_of(body: str, copilot: dict[int, str], comment_id: int) -> str:
    badge = FPC.PRIORITY_BADGE_RE.search(body or "")
    level = badge.group(1) if badge else copilot.get(comment_id)
    return SEVERITY.get(level or "", "note")


def pr_state(pr: dict) -> str:
    """Explicit state wins; a historical closed timestamp supports legacy raw inputs."""
    state = pr.get("state")
    if state in {"open", "closed"}:
        return state
    return "closed" if pr.get("closed_at") or pr.get("merged_at") else "unknown"


def is_negative_canary(title, body):
    """Protect deliberate probes; an ordinary 'unless green' gate is not a canary."""
    text = "\n".join([title or "", body or ""])
    text = re.sub(r"(?i)do\s+not\s+merge\s+(?:unless|until)\s+green", "conditional green gate", text)
    return bool(re.search(
        r"(?i)(?:\bdo\s+not\s+merge\b|\b(?:red|negative)\s*[-_ ]?canary\b|"
        r"\bnon[- ]?mergeable\b|\btestflight\b|\boracle\s+probe\b|\bprobe.{0,30}close after reading)", text))


def threads_of(pr: dict, comments: list[dict], reviews: list[dict], resolved: set[int]) -> list[dict]:
    """One record per review thread: its first comment, replies counted, resolution from `resolved`."""
    copilot = copilot_severities(reviews)
    replies: dict[int, list[dict]] = {}
    for c in comments:
        if c.get("in_reply_to_id"):
            replies.setdefault(c["in_reply_to_id"], []).append(c)
    out = []
    for c in comments:
        if c.get("in_reply_to_id"):
            continue
        rs = replies.get(c["id"], [])
        title = finding_title(c.get("body"))
        context = [{"id": item["id"], "body": item.get("body") or "",
                    "author": (item.get("user") or {}).get("login"),
                    "created_at": item.get("created_at"), "updated_at": item.get("updated_at"),
                    "commit_id": item.get("commit_id") or item.get("original_commit_id")}
                   for item in sorted([c, *rs], key=lambda item: (item.get("created_at") or "", item["id"]))]
        metadata = getattr(resolved, "metadata", {}).get(c["id"], {})
        latest = context[-1]
        body = c.get("body") or ""
        out.append({
            "number": c["id"], "state": "resolved" if c["id"] in resolved else "open",
            "thread_id": metadata.get("id") or c.get("thread_id"),
            "is_outdated": metadata.get("isOutdated"), "pr_state": pr_state(pr),
            "pr_title": pr.get("title"), "pr_body": pr.get("body"),
            "negative_canary": is_negative_canary(pr.get("title"), pr.get("body")) if "title" in pr and "body" in pr else None,
            "pr": pr["number"], "pr_merged": bool(pr.get("merged_at")), "closed_at": pr.get("merged_at") or pr.get("closed_at"),
            "pr_head_ref": (pr.get("head") or {}).get("ref"),
            "pr_head_repo": ((pr.get("head") or {}).get("repo") or {}).get("full_name"),
            "pr_base_sha": (pr.get("base") or {}).get("sha"), "pr_base_ref": (pr.get("base") or {}).get("ref"),
            "pr_draft": pr.get("draft"),
            "reviewer": (c.get("user") or {}).get("login"), "reviewer_family": reviewer_family((c.get("user") or {}).get("login")),
            "severity": severity_of(c.get("body"), copilot, c["id"]), "title": title, "theme": theme_of(title),
            "body": body, "body_hash": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            "comments": context, "latest_comment_id": latest["id"],
            "latest_comment_updated_at": latest["updated_at"],
            "updated_at": max((item["updated_at"] or item["created_at"] or "" for item in context), default="") or None,
            "discussion_hash": hashlib.sha256(json.dumps(context, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
            "path": c.get("path"), "line": c.get("line") or c.get("original_line"), "url": c.get("html_url"),
            "commented_commit": c.get("original_commit_id"), "pr_head": (pr.get("head") or {}).get("sha"),
            "replies": len(rs), "human_replied": any(reviewer_family((r.get("user") or {}).get("login")) == "human" for r in rs),
            "anchor": (anchor_of(c.get("diff_hunk")) or {}).get("text"),
            "anchor_side": (anchor_of(c.get("diff_hunk")) or {}).get("side"),
        })
    return out


ANCHOR_SIDES = {"+": "added", "-": "deleted", " ": "context"}


def anchor_of(hunk: str | None) -> dict | None:
    """The line the comment targets: the last line of its diff hunk, as it read in the PR.

    Whatever its length or side, no other line is substituted. `side` tells a deep read what to look for:
    a deleted target being back on the default branch means something else than an added one still there.
    A short or blank target is weak evidence, and the consumer decides how much to trust it. Diff markers
    such as `\\ No newline at end of file` are not lines of the file and are skipped (#1129 review)."""
    lines = [line for line in (hunk or "").splitlines() if not line.startswith(("@@", "\\"))]
    if not lines or lines[-1][:1] not in ANCHOR_SIDES:
        return None
    text = lines[-1][1:].strip()
    return {"text": text, "side": ANCHOR_SIDES[lines[-1][:1]]} if text else None


def closed_at(pr: dict) -> str:
    return pr.get("merged_at") or pr.get("closed_at") or ""


PR_REF_RE = re.compile(r"(?<![\w/])#([1-9]\d*)\b")


def refs_of(body: str | None, number: int) -> list[int]:
    """Same-repository `#N` references in a PR body, any length, the PR itself excluded."""
    return sorted({int(n) for n in PR_REF_RE.findall(body or "") if int(n) != number})


def run_gh(args: list[str]) -> tuple[int, str, str]:
    try:
        p = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", timeout=60)
    except subprocess.TimeoutExpired:
        return 1, "", "GitHub read timed out"
    return p.returncode, p.stdout, p.stderr


def gh_json(gh, path: str, paginate: bool = False):
    args = ["api", path] + (["--paginate", "--slurp"] if paginate else [])
    code, out, err = gh(args)
    if code:
        raise RuntimeError(f"{path}: {err.strip()[:200]}")
    data = json.loads(out or "[]")
    if paginate:
        if not isinstance(data, list) or any(not isinstance(page, list) for page in data):
            raise RuntimeError(f"{path}: malformed paginated response")
        return [item for page in data for item in page]
    return data


class ResolvedThreads(set):
    """Set-compatible canonical resolution result with optional provider thread identities."""

    def __init__(self, values=(), metadata=None):
        super().__init__(values)
        self.metadata = metadata or {}


THREAD_METADATA_QUERY = """query($owner:String!,$name:String!,$number:Int!,$after:String){
  repository(owner:$owner,name:$name){pullRequest(number:$number){
    reviewThreads(first:100,after:$after){pageInfo{hasNextPage endCursor}
      nodes{id isResolved isOutdated comments(first:1){nodes{databaseId}}}}}}}"""


class GhGraphql:
    """`ApiClient.graphql` over `gh`, so `FPC.resolved_thread_roots` runs wherever `gh` is authenticated."""

    def __init__(self, gh=run_gh):
        self.gh = gh
        self.metadata = {}
        self.cursors = set()

    def graphql(self, query: str, variables: dict) -> dict:
        # Keep pagination and resolution semantics in their canonical owner. Enrich only the
        # selected fields; no second read or copied resolution implementation is necessary.
        canonical_threads = query == FPC.THREADS_QUERY
        if canonical_threads:
            query = THREAD_METADATA_QUERY
            cursor = variables.get("after")
            if cursor in self.cursors:
                raise FPC.GateError("REVIEW_THREADS_REPEATED_CURSOR")
            self.cursors.add(cursor)
        args = ["api", "graphql", "-f", f"query={query}"]
        for key, value in variables.items():
            if value is not None:
                args += ["-F" if isinstance(value, int) else "-f", f"{key}={value}"]
        code, out, err = self.gh(args)
        if code:
            raise FPC.GateError("REVIEW_THREADS_UNAVAILABLE: " + err.strip()[:200])
        result = json.loads(out)
        if result.get("errors"):
            raise FPC.GateError("REVIEW_THREADS_GRAPHQL_PARTIAL_ERROR")
        data = result.get("data")
        if canonical_threads:
            conn = (((data or {}).get("repository") or {}).get("pullRequest") or {}).get("reviewThreads")
            if not isinstance(conn, dict) or not isinstance(conn.get("nodes"), list):
                raise FPC.GateError("REVIEW_THREADS_UNAVAILABLE")
            page = conn.get("pageInfo") or {}
            if type(page.get("hasNextPage")) is not bool or (page["hasNextPage"] and not page.get("endCursor")):
                raise FPC.GateError("REVIEW_THREADS_INCOMPLETE_PAGE")
            for node in conn["nodes"]:
                if not isinstance(node, dict) or type(node.get("isResolved")) is not bool:
                    raise FPC.GateError("REVIEW_THREADS_MALFORMED_NODE")
                first = ((node.get("comments") or {}).get("nodes") or [{}])[0]
                if not isinstance(first.get("databaseId"), int):
                    raise FPC.GateError("REVIEW_THREADS_MISSING_COMMENT_ID")
                self.metadata[first["databaseId"]] = {k: node.get(k) for k in ("id", "isOutdated")}
        return data


def resolved_via_graphql(gh, repo: str, number: int) -> set[int]:
    client = GhGraphql(gh)
    values = FPC.resolved_thread_roots(client, repo, number)
    return ResolvedThreads(values, client.metadata)


def resolved_via_ccr(gh, repo: str, number: int) -> set[int]:
    """Claude Code sessions only: their REST route for review threads."""
    threads = gh_json(gh, f"repos/{repo}/pulls/{number}/ccr/review_threads")
    return ResolvedThreads(
        {t["comment_ids"][0] for t in threads if t.get("resolved") and t.get("comment_ids")},
        {t["comment_ids"][0]: {"id": t.get("id"), "isOutdated": t.get("outdated")}
         for t in threads if t.get("comment_ids")})


MAX_PAGES = 30


def recent_closed(gh, repo: str, limit: int, max_pages: int = MAX_PAGES) -> tuple[list[dict], bool]:
    """The `limit` most recently closed PRs, newest first by merge or close time, and whether that is proven.

    The API sorts closed PRs by update time, not closure time. A PR never closes after its last update,
    so once `limit` PRs closed at or after the oldest update time read so far, no later page can hold a
    newer closure and the window is proven. Running out of pages proves it too. Hitting `max_pages`
    first does not: the caller records that as a coverage gap.
    """
    seen: dict[int, dict] = {}
    for page in range(1, max_pages + 1):
        batch = gh_json(gh, f"repos/{repo}/pulls?state=closed&sort=updated&direction=desc&per_page=100&page={page}")
        if not isinstance(batch, list) or any(not isinstance(pr, dict) or type(pr.get("number")) is not int for pr in batch):
            raise RuntimeError("malformed closed PR page")
        for pr in batch:
            seen[pr["number"]] = pr
        newest = sorted(seen.values(), key=closed_at, reverse=True)
        if len(batch) < 100:
            return newest[:limit], True
        floor = batch[-1].get("updated_at") or ""
        if len(newest) >= limit and closed_at(newest[limit - 1]) >= floor:
            return newest[:limit], True
    return sorted(seen.values(), key=closed_at, reverse=True)[:limit], False


def open_prs(gh, repo: str, max_pages: int = MAX_PAGES) -> tuple[list[dict], bool]:
    """All open PRs, regardless of the historical window limit; a page ceiling is a coverage gap."""
    seen = {}
    for page in range(1, max_pages + 1):
        batch = gh_json(gh, f"repos/{repo}/pulls?state=open&sort=created&direction=asc&per_page=100&page={page}")
        if not isinstance(batch, list) or any(not isinstance(pr, dict) or type(pr.get("number")) is not int for pr in batch):
            raise RuntimeError("malformed open PR page")
        for pr in batch:
            if pr.get("state", "open") != "open":
                raise RuntimeError("open PR page contains a non-open PR")
            seen[pr["number"]] = dict(pr, state="open")
        if len(batch) < 100:
            return [seen[n] for n in sorted(seen)], True
    return [seen[n] for n in sorted(seen)], False


def fetch(repos: list[str], limit: int, gh=run_gh, resolved=resolved_via_graphql,
          *, state: str = "closed", max_pages: int = MAX_PAGES) -> dict:
    """Raw review threads per repository, in the shape `maroon.build` reads for a source."""
    if state not in {"open", "closed", "all"}:
        raise ValueError("state must be open, closed or all")
    if type(limit) is not int or limit < 1 or type(max_pages) is not int or max_pages < 1:
        raise ValueError("limit and max_pages must be positive integers")
    if not repos or len(repos) != len(set(repos)) or any(
            not isinstance(repo, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo)
            or any(part in {".", ".."} for part in repo.split("/")) for repo in repos):
        raise ValueError("repos must contain unique OWNER/REPO names")
    raw = {"schema": SCHEMA, "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "limit": limit, "state": state, "repos": {}}
    for repo in repos:
        try:
            head = gh_json(gh, f"repos/{repo}/commits/HEAD")["sha"]  # L6: one head per pulse, recorded with the data
            if not isinstance(head, str) or not re.fullmatch(r"[0-9a-f]{40}", head):
                raise RuntimeError("invalid repository head SHA")
            active, closed, active_proven, closed_proven = [], [], True, True
            if state in {"open", "all"}:
                active, active_proven = open_prs(gh, repo, max_pages)
            if state in {"closed", "all"}:
                closed, closed_proven = recent_closed(gh, repo, limit, max_pages)
            # A PR can transition while a census is in flight. Keep the later provider snapshot,
            # never two manifestations of the same thread; workers still recheck the exact head.
            by_number = {pr["number"]: pr for pr in active}
            for pr in closed:
                prior = by_number.get(pr["number"])
                if prior is None or (pr.get("updated_at") or "") >= (prior.get("updated_at") or ""):
                    by_number[pr["number"]] = dict(pr, state="closed")
            prs = list(by_number.values())
            proven = active_proven and closed_proven
            alerts, deferred, linked_alerts = [], 0, []
            failures = []
            read = set()
            for pr in prs:
                try:
                    comments = gh_json(gh, f"repos/{repo}/pulls/{pr['number']}/comments?per_page=100", paginate=True)
                    reviews = gh_json(gh, f"repos/{repo}/pulls/{pr['number']}/reviews?per_page=100", paginate=True)
                    threads = threads_of(pr, comments, reviews, resolved(gh, repo, pr["number"]) if comments else set())
                except (RuntimeError, FPC.GateError, ValueError, KeyError, TypeError) as error:
                    failures.append({"pr": pr["number"], "error": str(error)[:200]})
                    continue
                read.add(pr["number"])
                for thread in threads:
                    if thread["reviewer_family"] in DEFERRED_FAMILIES:
                        deferred += 1
                        # Scanner alert metrics keep their canonical owner, but resolving a review
                        # conversation is a separate obligation. Preserve its identity and context.
                        linked_alerts.append({**thread, "provider_alert_owner": "code_scanning",
                                              "scanner_alert_state": "UNKNOWN"})
                    else:
                        alerts.append(thread)
            window = [closed_at(closed[-1]), closed_at(closed[0])] if closed else None
            # Sample membership, so a later diff can tell a thread that aged out of the window from one
            # that was resolved.
            sample = [{"number": pr["number"], "state": pr_state(pr), "merged": bool(pr.get("merged_at")), "closed_at": closed_at(pr),
                       "merge_commit_sha": pr.get("merge_commit_sha"),
                       "head_sha": (pr.get("head") or {}).get("sha"), "head_ref": (pr.get("head") or {}).get("ref"),
                       "head_repo": ((pr.get("head") or {}).get("repo") or {}).get("full_name"),
                       "base_sha": (pr.get("base") or {}).get("sha"), "base_ref": (pr.get("base") or {}).get("ref"),
                       "draft": pr.get("draft"), "title": pr.get("title"), "body": pr.get("body"),
                       "negative_canary": is_negative_canary(pr.get("title"), pr.get("body")) if "title" in pr and "body" in pr else None,
                       "coverage": "ok" if pr["number"] in read else "not_readable",
                       "refs": refs_of(pr.get("body"), pr["number"])}
                      for pr in prs]
            coverage = "partial" if failures else ("ok" if proven else ("pagination_incomplete" if not active_proven else "window_unproven"))
            raw["repos"][repo] = {"coverage": coverage, "status": "OBSERVED" if coverage == "ok" else "UNKNOWN",
                                  "scope_state": state, "head_sha": head, "prs_read": len(read), "prs_enumerated": len(prs),
                                  "window": window, "prs": sample, "alerts": alerts,
                                  "linked_alerts": linked_alerts,
                                  "failures": failures,
                                  "threads_deferred_to_code_scanning": deferred}
        except (RuntimeError, FPC.GateError, ValueError, KeyError, TypeError) as error:
            raw["repos"][repo] = {"coverage": "not_readable", "status": "UNKNOWN", "scope_state": state,
                                  "error": str(error)[:200]}
    return raw


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="read all active PRs and/or a recent closed PR window")
    f.add_argument("--repos", required=True, help="comma-separated OWNER/REPO list")
    f.add_argument("--limit", type=int, default=30, help="closed PRs per repository, newest first")
    f.add_argument("--state", choices=("open", "closed", "all"), default="closed",
                   help="open reads every active PR; all adds the --limit recent closed PRs")
    f.add_argument("--threads", choices=("graphql", "ccr"), default="graphql")
    f.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)
    resolver = resolved_via_ccr if args.threads == "ccr" else resolved_via_graphql
    raw = fetch([r.strip() for r in args.repos.split(",") if r.strip()], args.limit, resolved=resolver, state=args.state)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "raw_review.json").write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8", newline="\n")
    gaps = [r for r, e in raw["repos"].items() if e["coverage"] != "ok"]
    print("MAROON_REVIEW_FETCH=UNKNOWN" if gaps else "MAROON_REVIEW_FETCH=PASS", "repos=%d" % len(raw["repos"]), "gaps=%d" % len(gaps),
          "threads=%d" % sum(len(e.get("alerts", [])) for e in raw["repos"].values()), "out=%s" % (args.out / "raw_review.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
