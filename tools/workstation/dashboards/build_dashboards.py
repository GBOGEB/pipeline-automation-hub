"""Build the PC dashboard launcher: one page that finds every HTML page in every local clone.

Usage:  python build_dashboards.py [--offline] [--config PATH] [--out PATH]

Reads dashboards.json (default: next to this file), scans the configured folders for git
clones, lists their HTML pages (tracked, or untracked but not ignored), and writes index.html
(default: next to this file). With network access it asks `gh` for each repo's GitHub Pages
site and caches the answer in pages_cache.json next to the page; --offline uses the cache only.
Progress goes to build.log next to the page.
"""
from __future__ import annotations

import argparse
import glob
import html
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "template.html"
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # no console flashes under pythonw
LOG: Path | None = None


def log(msg: str) -> None:
    if LOG is None:
        return
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(stamp + " " + msg + "\n")


def git(repo: Path, *args: str, timeout: int = 60) -> str:
    try:
        r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout,
                           stdin=subprocess.DEVNULL, creationflags=NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return r.stdout if r.returncode == 0 else ""


def slug(remote: str) -> str:
    """https://github.com/GBOGEB/ABACUS.git -> GBOGEB/ABACUS"""
    m = re.search(r"github\.com[:/]+([^/]+)/([^/]+?)(?:\.git)?/?$", remote.strip())
    return f"{m.group(1)}/{m.group(2)}" if m else ""


def expand_root(path: str) -> list[Path]:
    """'~' and glob patterns (such as '~/OneDrive - *') to existing folders."""
    return [Path(p) for p in sorted(glob.glob(os.path.expanduser(path))) if os.path.isdir(p)]


def find_clones(cfg: dict) -> list[Path]:
    skip = set(cfg["skip_dirs"])
    found: set[Path] = set()
    for root in cfg["scan_roots"]:
        for base in expand_root(root["path"]):
            stack = [(base, 0)]
            while stack:
                d, depth = stack.pop()
                try:
                    entries = list(os.scandir(d))
                except OSError:
                    continue
                if any(e.name == ".git" for e in entries):
                    found.add(d.resolve())
                    continue  # do not descend into a clone
                if depth >= root["depth"]:
                    continue
                for e in entries:
                    if e.is_dir(follow_symlinks=False) and e.name not in skip and not e.name.startswith("."):
                        stack.append((Path(e.path), depth + 1))
    if cfg.get("include_claude_worktrees"):
        for repo in list(found):
            for line in git(repo, "worktree", "list", "--porcelain").splitlines():
                if line.startswith("worktree "):
                    p = Path(line[9:])
                    if p.is_dir():
                        found.add(p.resolve())
    return sorted(found, key=lambda p: str(p).lower())


def page_title(path: Path) -> str:
    try:
        with open(path, "rb") as f:
            head = f.read(8192).decode("utf-8", "replace")
    except OSError:
        return ""
    m = TITLE_RE.search(head)
    return html.unescape(re.sub(r"\s+", " ", m.group(1))).strip() if m else ""


def scan_repo(repo: Path, cfg: dict, entry_re: re.Pattern) -> dict:
    remote = git(repo, "remote", "get-url", "origin").strip()
    files = git(repo, "ls-files", "--cached", "--others", "--exclude-standard", "--",
                "*.html", "*.htm", timeout=120).splitlines()
    skip = [s.lower() for s in cfg["skip_html_patterns"]]
    pages = []
    for rel in sorted(set(files)):
        low = "/" + rel.lower()
        if any(s in low for s in skip):
            continue
        p = repo / rel
        try:
            mtime = p.stat().st_mtime
        except OSError:
            continue  # tracked but deleted in the working tree
        pages.append({
            "rel": rel,
            "title": page_title(p),
            "uri": p.as_uri(),
            "mtime": int(mtime),
            "entry": bool(entry_re.search(rel.lower())),
        })
    log_line = git(repo, "log", "-1", "--format=%cs|%h").strip().split("|")
    return {
        "path": str(repo),
        "uri": repo.as_uri(),
        "slug": slug(remote),
        "remote": remote,
        "branch": git(repo, "branch", "--show-current").strip() or "(detached)",
        "last_commit": log_line[0] if log_line and log_line[0] else "",
        "head": log_line[1] if len(log_line) > 1 else "",
        "pages": pages,
    }


def unique_slugs(repos: list[dict], extra: list[str]) -> list[str]:
    """GitHub names are case-insensitive: one entry per repo, first spelling wins."""
    by_lower: dict[str, str] = {}
    for s in [r["slug"] for r in repos if r["slug"]] + list(extra):
        by_lower.setdefault(s.lower(), s)
    return sorted(by_lower.values(), key=str.lower)


def pages_sites(slugs: list[str], cache_path: Path, offline: bool) -> dict:
    cache = {}
    if cache_path.exists():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    if offline:
        return cache
    env = {k: v for k, v in os.environ.items() if k not in ("GITHUB_TOKEN", "GH_TOKEN")}
    for s in slugs:
        try:
            r = subprocess.run(["gh", "api", f"repos/{s}/pages", "--jq", ".html_url"],
                               capture_output=True, text=True, timeout=20, env=env,
                               stdin=subprocess.DEVNULL, creationflags=NO_WINDOW)
        except (OSError, subprocess.TimeoutExpired):
            continue  # keep the cached answer
        today = time.strftime("%Y-%m-%d")
        if r.returncode == 0 and r.stdout.strip():
            cache[s] = {"url": r.stdout.strip(), "checked": today}
        elif "404" in r.stdout + r.stderr:
            cache[s] = {"url": None, "checked": today}
    cache_path.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")
    return cache


def resolve_top(cfg: dict, repos: list[dict]) -> list[dict]:
    out = []
    for t in cfg["top"]:
        item = dict(t)
        if t.get("repo"):
            item["url"] = None
            # newest checkout of that repo that has the file
            for r in sorted(repos, key=lambda r: r["last_commit"], reverse=True):
                if r["slug"].lower() == t["repo"].lower() and (Path(r["path"]) / t["path"]).exists():
                    item["url"] = (Path(r["path"]) / t["path"]).as_uri()
                    item["where"] = r["path"]
                    break
            item["github"] = f"https://github.com/{t['repo']}/blob/HEAD/{t['path']}"
        out.append(item)
    return out


def build(config: Path, out: Path, offline: bool) -> dict:
    cfg = json.loads(config.read_text(encoding="utf-8"))
    entry_re = re.compile(cfg["entry_name_pattern"])
    t0 = time.time()
    log("start" + (" --offline" if offline else ""))
    clones = find_clones(cfg)
    log(f"found {len(clones)} clones")
    repos = []
    for c in clones:
        repos.append(scan_repo(c, cfg, entry_re))
        log(f"scanned {c} ({len(repos[-1]['pages'])} pages)")
    slugs = unique_slugs(repos, cfg.get("extra_repos_online", []))
    sites = pages_sites(slugs, out.parent / "pages_cache.json", offline)
    data = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "seconds": round(time.time() - t0, 1),
        "config_uri": config.resolve().as_uri(),
        "top": resolve_top(cfg, repos),
        "artifacts": cfg.get("artifacts", []),
        "sites": [dict(slug=s, **sites[s]) for s in slugs if s in sites],
        "repos": repos,
    }
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    out.write_text(TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload),
                   encoding="utf-8")
    return data


def main(argv: list[str] | None = None) -> int:
    global LOG
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--offline", action="store_true", help="use cached Pages sites, no gh calls")
    ap.add_argument("--config", type=Path, default=HERE / "dashboards.json")
    ap.add_argument("--out", type=Path, default=HERE / "index.html")
    args = ap.parse_args(argv)
    LOG = args.out.parent / "build.log"
    data = build(args.config, args.out, args.offline)
    n = sum(len(r["pages"]) for r in data["repos"])
    msg = f"{len(data['repos'])} clones, {n} HTML pages, {data['seconds']}s -> {args.out}"
    log("done: " + msg)
    if sys.stdout:  # None under pythonw
        print(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
