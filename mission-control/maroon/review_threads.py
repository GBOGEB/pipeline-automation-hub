#!/usr/bin/env python3
"""CODE MAROON review-thread source: review findings left unresolved on closed pull requests.

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
    ("codeql", re.compile(r"^github-advanced-security\[bot\]$")),
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
        out.append({
            "number": c["id"], "state": "resolved" if c["id"] in resolved else "open",
            "pr": pr["number"], "pr_merged": bool(pr.get("merged_at")), "closed_at": pr.get("merged_at") or pr.get("closed_at"),
            "reviewer": (c.get("user") or {}).get("login"), "reviewer_family": reviewer_family((c.get("user") or {}).get("login")),
            "severity": severity_of(c.get("body"), copilot, c["id"]), "title": title, "theme": theme_of(title),
            "path": c.get("path"), "line": c.get("line") or c.get("original_line"), "url": c.get("html_url"),
            "commented_commit": c.get("original_commit_id"), "pr_head": (pr.get("head") or {}).get("sha"),
            "replies": len(rs), "human_replied": any(reviewer_family((r.get("user") or {}).get("login")) == "human" for r in rs),
        })
    return out


def run_gh(args: list[str]) -> tuple[int, str, str]:
    p = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout, p.stderr


def gh_json(gh, path: str, paginate: bool = False):
    args = ["api", path] + (["--paginate", "--slurp"] if paginate else [])
    code, out, err = gh(args)
    if code:
        raise RuntimeError(f"{path}: {err.strip()[:200]}")
    data = json.loads(out or "[]")
    if paginate:
        return [item for page in data for item in (page if isinstance(page, list) else [page])]
    return data


class GhGraphql:
    """`ApiClient.graphql` over `gh`, so `FPC.resolved_thread_roots` runs wherever `gh` is authenticated."""

    def __init__(self, gh=run_gh):
        self.gh = gh

    def graphql(self, query: str, variables: dict) -> dict:
        args = ["api", "graphql", "-f", f"query={query}"]
        for key, value in variables.items():
            if value is not None:
                args += ["-F" if isinstance(value, int) else "-f", f"{key}={value}"]
        code, out, err = self.gh(args)
        if code:
            raise FPC.GateError("REVIEW_THREADS_UNAVAILABLE: " + err.strip()[:200])
        return json.loads(out).get("data")


def resolved_via_graphql(gh, repo: str, number: int) -> set[int]:
    return FPC.resolved_thread_roots(GhGraphql(gh), repo, number)


def resolved_via_ccr(gh, repo: str, number: int) -> set[int]:
    """Claude Code sessions only: their REST route for review threads."""
    threads = gh_json(gh, f"repos/{repo}/pulls/{number}/ccr/review_threads")
    return {t["comment_ids"][0] for t in threads if t.get("resolved") and t.get("comment_ids")}


def recent_closed(gh, repo: str, limit: int) -> list[dict]:
    """The `limit` most recently closed PRs, newest first by merge or close time."""
    prs, page = [], 1
    while len(prs) < limit * 2 and page <= 10:
        batch = gh_json(gh, f"repos/{repo}/pulls?state=closed&sort=updated&direction=desc&per_page=100&page={page}")
        if not batch:
            break
        prs += batch
        page += 1
    prs.sort(key=lambda p: p.get("merged_at") or p.get("closed_at") or "", reverse=True)
    return prs[:limit]


def fetch(repos: list[str], limit: int, gh=run_gh, resolved=resolved_via_graphql) -> dict:
    """Raw review threads per repository, in the shape `maroon.build` reads for a source."""
    raw = {"schema": SCHEMA, "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "limit": limit, "repos": {}}
    for repo in repos:
        try:
            head = gh_json(gh, f"repos/{repo}/commits/HEAD")["sha"]  # L6: one head per pulse, recorded with the data
            alerts, prs, deferred = [], recent_closed(gh, repo, limit), 0
            for pr in prs:
                comments = gh_json(gh, f"repos/{repo}/pulls/{pr['number']}/comments?per_page=100", paginate=True)
                reviews = gh_json(gh, f"repos/{repo}/pulls/{pr['number']}/reviews?per_page=100", paginate=True)
                for thread in threads_of(pr, comments, reviews, resolved(gh, repo, pr["number"]) if comments else set()):
                    if thread["reviewer_family"] in DEFERRED_FAMILIES:
                        deferred += 1
                    else:
                        alerts.append(thread)
            window = [prs[-1].get("merged_at") or prs[-1].get("closed_at"), prs[0].get("merged_at") or prs[0].get("closed_at")] if prs else None
            raw["repos"][repo] = {"coverage": "ok", "head_sha": head, "prs_read": len(prs), "window": window, "alerts": alerts,
                                  "threads_deferred_to_code_scanning": deferred}
        except (RuntimeError, FPC.GateError) as error:
            raw["repos"][repo] = {"coverage": "not_readable", "error": str(error)[:200]}
    return raw


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="read review threads of the most recent closed PRs")
    f.add_argument("--repos", required=True, help="comma-separated OWNER/REPO list")
    f.add_argument("--limit", type=int, default=30, help="closed PRs per repository, newest first")
    f.add_argument("--threads", choices=("graphql", "ccr"), default="graphql")
    f.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)
    resolver = resolved_via_ccr if args.threads == "ccr" else resolved_via_graphql
    raw = fetch([r.strip() for r in args.repos.split(",") if r.strip()], args.limit, resolved=resolver)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "raw_review.json").write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8", newline="\n")
    gaps = [r for r, e in raw["repos"].items() if e["coverage"] != "ok"]
    print("MAROON_REVIEW_FETCH=PASS", "repos=%d" % len(raw["repos"]), "gaps=%d" % len(gaps),
          "threads=%d" % sum(len(e.get("alerts", [])) for e in raw["repos"].values()), "out=%s" % (args.out / "raw_review.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
