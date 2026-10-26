#!/usr/bin/env python3
"""Pre-flight overlap check: is this work already owned by master or by an open PR?

Run it BEFORE building a metric, page, gate or tool (AGENTS.md, Working rules L4):

    python scripts/preflight_overlap.py everred "p_decide" rolling5
    python scripts/preflight_overlap.py --path mission-control/gogreen/scale_dock.py
    python scripts/preflight_overlap.py scale_dock --path mission-control/jade_temple/tools

For every search term and path it lists
  (a) open PRs whose title, head branch or changed files match, and
  (b) what origin/master already has: matching file paths, def/class names and
      the number of files whose content mentions the term (git grep).
It ends with an "already owned by" summary per term/path.

Matching on titles, branches and paths is case-insensitive and ignores
punctuation, so "rolling-5" also finds rolling5.py. When both terms and --path
are given, the master search for the terms is narrowed to those paths (PR
matching is not narrowed). Read-only: it never pushes,
comments or edits. It always exits 0; a missing gh or git is reported, not fatal.
On a workstation with a stale GITHUB_TOKEN run it as
`unset GITHUB_TOKEN GH_TOKEN; python scripts/preflight_overlap.py ...`.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Callable, Sequence

Runner = Callable[[Sequence[str]], "tuple[int, str, str]"]
ERE_SPECIAL = re.compile(r"([.^$*+?()\[\]{}|\\])")


def run(cmd: Sequence[str]) -> tuple[int, str, str]:
    """Run a command; never raise. Returns (returncode, stdout, stderr)."""
    try:
        p = subprocess.run(list(cmd), capture_output=True, text=True, encoding="utf-8", errors="replace")
    except (OSError, ValueError) as exc:
        return 127, "", str(exc)
    return p.returncode, p.stdout or "", p.stderr or ""


def norm(s: str) -> str:
    """Lower-case and drop everything but letters and digits: 'Rolling-5' == 'rolling5'."""
    return re.sub(r"[^0-9a-z]", "", s.lower())


def ere_escape(term: str) -> str:
    return ERE_SPECIAL.sub(r"\\\1", term)


def term_hit(term: str, text: str) -> bool:
    n = norm(term)
    if not n:
        return term.lower() in text.lower()
    return n in norm(text)


def path_hit(prefix: str, path: str) -> bool:
    prefix = prefix.replace("\\", "/").strip("/")
    path = path.replace("\\", "/")
    return path == prefix or path.startswith(prefix + "/")


# --- (a) open PRs ---------------------------------------------------------

def open_prs(runner: Runner, repo: str | None, limit: int) -> tuple[list[dict], str | None]:
    cmd = ["gh", "pr", "list", "--state", "open", "--limit", str(limit),
           "--json", "number,title,headRefName,url,isDraft,author,files"]
    if repo:
        cmd += ["--repo", repo]
    rc, out, err = runner(cmd)
    if rc != 0:
        return [], f"gh pr list failed (rc={rc}): {err.strip() or out.strip()}"
    try:
        return json.loads(out or "[]"), None
    except json.JSONDecodeError as exc:
        return [], f"gh pr list returned non-JSON output: {exc}"


def pr_matches(pr: dict, terms: Sequence[str], paths: Sequence[str]) -> list[str]:
    """Return human-readable reasons this PR overlaps, empty if it does not."""
    files = [f.get("path", "") for f in pr.get("files") or []]
    why = []
    for t in terms:
        where = []
        if term_hit(t, pr.get("title", "")):
            where.append("title")
        if term_hit(t, pr.get("headRefName", "")):
            where.append("branch")
        hit_files = [f for f in files if term_hit(t, f)]
        if hit_files:
            where.append("files: " + ", ".join(hit_files[:5]) + (" ..." if len(hit_files) > 5 else ""))
        if where:
            why.append(f"'{t}' in " + "; ".join(where))
    for p in paths:
        hit_files = [f for f in files if path_hit(p, f)]
        if hit_files:
            why.append(f"touches {p}: " + ", ".join(hit_files[:5]) + (" ..." if len(hit_files) > 5 else ""))
    return why


# --- (b) origin/master ----------------------------------------------------

def master_files(runner: Runner, ref: str) -> tuple[list[str], str | None]:
    rc, out, err = runner(["git", "ls-tree", "-r", "--name-only", ref])
    if rc != 0:
        return [], f"git ls-tree {ref} failed (rc={rc}): {err.strip()}"
    return [line for line in out.splitlines() if line], None


def master_defs(runner: Runner, ref: str, term: str, limit_paths: Sequence[str]) -> list[str]:
    """def/class lines on `ref` whose name contains the term ('rolling-5' tries rolling_5 and rolling5)."""
    idents = sorted({re.sub(r"[^0-9A-Za-z_]", "_", term), re.sub(r"[^0-9A-Za-z_]", "", term)} - {""})
    if not idents:
        return []
    alt = "|".join(ere_escape(i) for i in idents)
    pattern = r"^[[:space:]]*(async[[:space:]]+)?(def|class)[[:space:]]+[A-Za-z0-9_]*(" + alt + ")"
    cmd = ["git", "grep", "-n", "-I", "-i", "-E", "-e", pattern, ref, "--", *(limit_paths or ["*.py"])]
    rc, out, _ = runner(cmd)
    if rc not in (0, 1):
        return []
    hits = []
    for line in out.splitlines():
        if line.startswith(ref + ":"):
            line = line[len(ref) + 1:]
        hits.append(line.strip())
    return hits


def master_content_files(runner: Runner, ref: str, term: str, limit_paths: Sequence[str]) -> list[str]:
    cmd = ["git", "grep", "-l", "-I", "-i", "-F", "-e", term, ref]
    if limit_paths:
        cmd += ["--", *limit_paths]
    rc, out, _ = runner(cmd)
    if rc not in (0, 1):
        return []
    return [line[len(ref) + 1:] if line.startswith(ref + ":") else line for line in out.splitlines() if line]


def last_touch(runner: Runner, ref: str, path: str) -> str | None:
    rc, out, _ = runner(["git", "log", "-1", "--format=%h %an %ad %s", "--date=short", ref, "--", path])
    return (out.strip() or None) if rc == 0 else None


# --- report ---------------------------------------------------------------

def _clip(items: list[str], n: int) -> list[str]:
    return items[:n] + ([f"... {len(items) - n} more"] if len(items) > n else [])


def analyse(terms: Sequence[str], paths: Sequence[str], *, runner: Runner = run, ref: str = "origin/master",
            repo: str | None = None, pr_limit: int = 100) -> dict:
    report: dict = {"ref": ref, "terms": list(terms), "paths": list(paths), "warnings": [],
                    "open_prs": [], "master": {"terms": {}, "paths": {}}}
    prs, warn = open_prs(runner, repo, pr_limit)
    if warn:
        report["warnings"].append(warn)
    for pr in prs:
        why = pr_matches(pr, terms, paths)
        if why:
            report["open_prs"].append({"number": pr.get("number"), "title": pr.get("title"),
                                       "branch": pr.get("headRefName"), "url": pr.get("url"),
                                       "draft": bool(pr.get("isDraft")),
                                       "author": (pr.get("author") or {}).get("login"), "why": why})
    files, warn = master_files(runner, ref)
    if warn:
        report["warnings"].append(warn)
    for t in terms:
        report["master"]["terms"][t] = {
            "paths": [f for f in files if term_hit(t, f) and (not paths or any(path_hit(p, f) for p in paths))],
            "defs": master_defs(runner, ref, t, paths),
            "content_files": master_content_files(runner, ref, t, paths),
        }
    for p in paths:
        hit = [f for f in files if path_hit(p, f)]
        report["master"]["paths"][p] = {"files": hit, "last_commit": last_touch(runner, ref, p) if hit else None}
    report["owners"] = owners(report)
    return report


def owners(report: dict) -> dict[str, list[str]]:
    """term/path -> who already owns it: 'PR #n (branch)' and/or 'master: <file or def>'."""
    out: dict[str, list[str]] = {}
    for key in [*report["terms"], *report["paths"]]:
        who = []
        for pr in report["open_prs"]:
            if any(w.startswith(f"'{key}' ") or w.startswith(f"touches {key}:") for w in pr["why"]):
                who.append(f"PR #{pr['number']} ({pr['branch']})")
        if key in report["master"]["terms"]:
            m = report["master"]["terms"][key]
            who += [f"master: {d}" for d in m["defs"][:3]]
            who += [f"master: {p}" for p in m["paths"][:3] if not any(d.startswith(p + ":") for d in m["defs"])]
        if key in report["master"]["paths"] and report["master"]["paths"][key]["files"]:
            m = report["master"]["paths"][key]
            who.append(f"master: {key} ({len(m['files'])} file(s); last: {m['last_commit']})")
        out[key] = who
    return out


def render(report: dict, max_items: int = 15) -> str:
    lines = [f"preflight_overlap against {report['ref']} + open PRs", ""]
    for w in report["warnings"]:
        lines.append(f"WARNING: {w}")
    if report["warnings"]:
        lines.append("")
    lines.append(f"(a) Open PRs that overlap: {len(report['open_prs'])}")
    for pr in report["open_prs"]:
        draft = " [draft]" if pr["draft"] else ""
        lines.append(f"  #{pr['number']}{draft} {pr['title']}  ({pr['branch']}, @{pr['author']})")
        lines += [f"      - {w}" for w in pr["why"]]
    lines += ["", f"(b) Already on {report['ref']}:"]
    for t, m in report["master"]["terms"].items():
        lines.append(f"  term '{t}': {len(m['paths'])} path(s), {len(m['defs'])} def/class, "
                     f"{len(m['content_files'])} file(s) mention it")
        lines += [f"      path  {p}" for p in _clip(m["paths"], max_items)]
        lines += [f"      def   {d}" for d in _clip(m["defs"], max_items)]
    for p, m in report["master"]["paths"].items():
        lines.append(f"  path '{p}': {len(m['files'])} file(s); last commit: {m['last_commit'] or '-'}")
        lines += [f"      {f}" for f in _clip(m["files"], max_items)]
    lines += ["", "Already owned by:"]
    for key, who in report["owners"].items():
        lines.append(f"  {key}: " + ("; ".join(who) if who else "nothing found (free to build; still push early)"))
    lines += ["", "Rule: import the owner's function or extend its PR; do not copy it (AGENTS.md L4)."]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None, runner: Runner = run) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("terms", nargs="*", help="search terms (metric, function, page or tool names)")
    ap.add_argument("--path", action="append", default=[], help="repo-relative path or directory (repeatable)")
    ap.add_argument("--ref", default="origin/master", help="ref to search (default origin/master)")
    ap.add_argument("--repo", help="OWNER/REPO for gh (default: the current checkout)")
    ap.add_argument("--pr-limit", type=int, default=100)
    ap.add_argument("--no-fetch", action="store_true", help="skip `git fetch origin` before searching")
    ap.add_argument("--json", action="store_true", help="print the full report as JSON")
    args = ap.parse_args(argv)
    if not args.terms and not args.path:
        ap.print_usage()
        print("give at least one search term or --path")
        return 0
    try:
        if not args.no_fetch and args.ref.startswith("origin/"):
            rc, _, err = runner(["git", "fetch", "-q", "origin"])
            if rc != 0:
                print(f"WARNING: git fetch origin failed; {args.ref} may be stale: {err.strip()}")
        report = analyse(args.terms, args.path, runner=runner, ref=args.ref, repo=args.repo,
                         pr_limit=args.pr_limit)
        print(json.dumps(report, indent=1) if args.json else render(report))
    except Exception as exc:  # advisory tool: never block a session
        print(f"WARNING: preflight_overlap could not finish: {exc!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
