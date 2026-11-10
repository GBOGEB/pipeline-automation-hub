#!/usr/bin/env python3
"""Resolve review threads whose evidence reply shows the fix is on the default branch.

    python resolve_answered.py --repos GBOGEB/cryoplant-project,GBOGEB/CODEX [--limit 60] [--apply]

Dry run by default. A thread on a merged PR qualifies only when its last comment is from the login running
this tool (the programme's evidence replies) and that reply:

* says the fix is already on main (``Already fixed on main``, ``Superseded on main``, ``Kept as is``, ...), or
* names a fix PR in the same repository that has merged (``Fixed in #N``, ``Fixed by merged #N``,
  ``the fix is in #N``), or
* names a commit on the thread's own PR, which has merged (``Fixed in <sha>``, ``Addressed on head <sha>``).

Everything else stays open: a fix PR that has not merged, a finding confirmed open, a re-theme, and any
reply this tool does not recognise. Resolution goes through the ``ccr`` route that Claude Code sessions
have; GitHub helpers come from ``review_threads.py`` (AGENTS.md L4).
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location("maroon_review_threads", HERE / "review_threads.py")
RT = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(RT)

ON_MAIN = re.compile(r"^(?:Already fixed on main|Already addressed on main|Superseded on main|Kept as is|"
                     r"Already fixed)", re.I)
FIX_PR = re.compile(r"(?:fixed|corrected) in #(\d+)|the fix is in #(\d+)|fixed by merged #(\d+)", re.I)
FIX_SHA = re.compile(r"^(?:Fixed in|Addressed on head) ([0-9a-f]{7,40})\b")
# Evidence replies may open with an HTML marker and a bold title before the verdict.
PREAMBLE = re.compile(r"^(?:\s*<!--.*?-->\s*)*(?:\*\*[^*]*\*\*\s*)?", re.S)
WAIT, SKIP = "WAIT", "SKIP"


def verdict_of(body: str, pr_merged) -> str:
    """What a reply proves: on-main, merged #N, fixed on this PR, WAIT (fix PR open) or SKIP (not evidence)."""
    text = PREAMBLE.sub("", body or "").strip()
    if ON_MAIN.match(text):
        return "on-main"
    match = FIX_PR.search(text)
    if match:
        number = int(next(g for g in match.groups() if g))
        return f"merged #{number}" if pr_merged(number) else f"{WAIT} #{number} unmerged"
    if FIX_SHA.match(text):
        return "fixed on this merged PR"
    return f"{SKIP} unrecognised reply"


def answered(gh, repo: str, limit: int, me: str):
    """(pr, root comment id, verdict) for every unresolved thread on a recent merged PR whose last word is ours."""
    cache: dict[int, bool] = {}

    def pr_merged(number: int) -> bool:
        if number not in cache:
            cache[number] = bool(RT.gh_json(gh, f"repos/{repo}/pulls/{number}").get("merged_at"))
        return cache[number]

    prs, _proven = RT.recent_closed(gh, repo, limit)
    for pr in prs:
        if not pr.get("merged_at"):
            continue
        try:
            threads = RT.gh_json(gh, f"repos/{repo}/pulls/{pr['number']}/ccr/review_threads") or []
        except RuntimeError as exc:  # one unreadable PR is a reported gap, not the end of the sweep
            yield pr["number"], None, f"{SKIP} GAP threads unreadable: {str(exc)[:80]}"
            continue
        for thread in threads:
            ids = thread.get("comment_ids") or []
            if thread.get("resolved") or len(ids) < 2:
                continue
            last = RT.gh_json(gh, f"repos/{repo}/pulls/comments/{ids[-1]}")
            if (last.get("user") or {}).get("login") != me:
                continue
            yield pr["number"], ids[0], verdict_of(last.get("body", ""), pr_merged)


def main(argv=None, gh=RT.run_gh) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repos", required=True, help="comma-separated owner/name list")
    parser.add_argument("--limit", type=int, default=60, help="most recently closed PRs read per repository")
    parser.add_argument("--apply", action="store_true", help="resolve; without it, only report")
    args = parser.parse_args(argv)
    me = RT.gh_json(gh, "user")["login"]
    resolved = considered = 0
    for repo in [r.strip() for r in args.repos.split(",") if r.strip()]:
        for number, root, verdict in answered(gh, repo, args.limit, me):
            considered += 1
            act = root is not None and not verdict.startswith((WAIT, SKIP))
            if act and args.apply:
                code, _out, err = gh(["api", "-X", "POST", f"repos/{repo}/pulls/{number}/ccr/comments/{root}/resolve"])
                if code:
                    raise RuntimeError(f"resolve {repo}#{number} {root}: {err.strip()[:200]}")
            resolved += act
            print(f"{repo}\t#{number}\t{root}\t{verdict}")
    print(f"{'resolved' if args.apply else 'would resolve'} {resolved} of {considered} answered threads",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
