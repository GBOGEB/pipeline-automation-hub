#!/usr/bin/env python3
"""Build the workstation tool catalog: one self-contained page per TOOLS_CATALOG.json.

For every tool it shows the goal, when to use it and when not, what it writes, how to run it (PowerShell,
starting in the hub checkout), its artefacts and docs, and the code facts read from git at one commit:
blob OID, last commit touching the file, line count, a GitHub link pinned to that commit and the source
itself. With --online it adds the state of the listed PRs/issues and every OPEN PR that touches the file,
each with its checkout and in-situ fix command.

It owns no metric and no tool; it only describes them. Stdlib only. gh runs without GITHUB_TOKEN/GH_TOKEN.

    python tools/workstation/build_tool_catalog.py                 # offline, ~/DASHBOARDS/tools_catalog.html
    python tools/workstation/build_tool_catalog.py --online        # plus PR / issue state from gh
    python tools/workstation/build_tool_catalog.py --fragment --out x.html   # body only (for hosts that add <head>)
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA = "gbogeb.workstation-tool-catalog.v1"
SOURCE_LIMIT = 400_000  # characters of source embedded per tool


def git(root: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.stdout.strip() if r.returncode == 0 else ""


def gh_json(*args: str):
    env = {k: v for k, v in os.environ.items() if k not in ("GITHUB_TOKEN", "GH_TOKEN")}
    try:
        r = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0 or not r.stdout.strip():
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def load_catalog(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise ValueError(f"{path}: schema must be {SCHEMA}")
    ids = [t["id"] for t in doc["tools"]]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate tool ids")
    groups = {g["id"] for g in doc["groups"]}
    for t in doc["tools"]:
        missing = [k for k in ("id", "group", "name", "path", "goal", "when", "writes", "commands") if not t.get(k)]
        if missing:
            raise ValueError(f"{t.get('id')}: missing {missing}")
        if t["group"] not in groups:
            raise ValueError(f"{t['id']}: unknown group {t['group']}")
        if t.get("level") not in (None, "read", "write", "push"):
            raise ValueError(f"{t['id']}: level must be read, write or push")
        bad = [r for r in t.get("related", []) if r not in ids]
        if bad:
            raise ValueError(f"{t['id']}: unknown related ids {bad}")
    return doc


def write_level(writes: str) -> str:
    w = writes.lower()
    if w.startswith("read-only"):
        return "read"
    if "push" in w or "delete" in w or "resolve" in w or "pr body" in w:
        return "push"
    return "write"


def code_facts(root: Path, rel: str, head: str) -> dict:
    """Facts at HEAD from git (works in sparse checkouts); local edits are flagged, not shown."""
    blob = git(root, "rev-parse", f"HEAD:{rel}")
    if not blob:
        return {"present": False}
    log = git(root, "log", "-1", "--format=%H%x1f%cs%x1f%s", "HEAD", "--", rel).split("\x1f")
    source = git(root, "show", f"HEAD:{rel}")
    local = root / rel
    dirty = local.exists() and bool(git(root, "status", "--porcelain", "--", rel))
    return {
        "present": True, "blob": blob, "lines": source.count("\n") + (1 if source and not source.endswith("\n") else 0),
        "commit": log[0] if len(log) == 3 else head, "date": log[1] if len(log) == 3 else "",
        "subject": log[2] if len(log) == 3 else "", "source": source[:SOURCE_LIMIT],
        "truncated": len(source) > SOURCE_LIMIT, "dirty": dirty,
    }


def online_facts(repo: str, tools: list[dict]) -> dict:
    """{'open_by_path': {path: [pr...]}, 'refs': {('pr'|'issue', n): {...}}, 'ok': bool}."""
    out = {"open_by_path": {}, "refs": {}, "ok": False}
    prs = gh_json("pr", "list", "-R", repo, "--state", "open", "--limit", "200",
                  "--json", "number,title,headRefName,isDraft,url,files")
    if prs is None:
        return out
    out["ok"] = True
    paths = {t["path"] for t in tools}
    for pr in prs:
        for f in pr.get("files") or []:
            if f.get("path") in paths:
                out["open_by_path"].setdefault(f["path"], []).append(
                    {k: pr[k] for k in ("number", "title", "headRefName", "isDraft", "url")})
    for t in tools:
        for n in t.get("prs", []):
            v = gh_json("pr", "view", str(n), "-R", repo, "--json", "number,title,state,url,headRefName")
            if v:
                out["refs"][("pr", n)] = v
        for n in t.get("issues", []):
            v = gh_json("issue", "view", str(n), "-R", repo, "--json", "number,title,state,url")
            if v:
                out["refs"][("issue", n)] = v
    return out


def build(catalog: dict, root: Path, online: dict | None, now: str) -> dict:
    head = git(root, "rev-parse", "HEAD")
    tools = []
    for t in catalog["tools"]:
        facts = code_facts(root, t["path"], head)
        tools.append({**t, "level": t.get("level") or write_level(t["writes"]), "facts": facts,
                      "open_prs": (online or {}).get("open_by_path", {}).get(t["path"], []),
                      "refs": [((online or {}).get("refs", {}).get((kind, n)) or {"number": n, "state": "unknown"}) | {"kind": kind}
                               for kind, key in (("pr", "prs"), ("issue", "issues")) for n in t.get(key, [])]})
    return {"repo": catalog["repo"], "groups": catalog["groups"], "tools": tools, "head": head,
            "branch": git(root, "rev-parse", "--abbrev-ref", "HEAD"), "root": str(root), "built": now,
            "online": bool(online and online.get("ok"))}


# ------------------------------------------------------------------------------------------------ render

def e(s) -> str:
    return html.escape(str(s), quote=True)


CSS = """
/* Layout: sticky toolbar, then one band per group; tool cards in a single readable column with a
   facts rail on wide screens. Utility look: the subject is commands, SHAs and PR numbers. */
:root {
  --bg: #f3f5f4; --panel: #ffffff; --ink: #18201d; --muted: #5b6763; --line: #d5dcd9;
  --accent: #0f6b5c; --accent-soft: #e0efeb; --code-bg: #eef2f0;
  --read: #2f6f3e; --read-bg: #e2f1e5; --write: #8a5a00; --write-bg: #fbefd5; --push: #a3352b; --push-bg: #f8e1de;
  --sans: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, "Cascadia Mono", Consolas, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #111614; --panel: #18201d; --ink: #e3ebe7; --muted: #9aa8a3; --line: #2c3833;
  --accent: #5cc5ae; --accent-soft: #17332c; --code-bg: #0d1210;
  --read: #8fd19e; --read-bg: #18301f; --write: #f0c060; --write-bg: #33270e; --push: #f19a90; --push-bg: #3a1c19;
  color-scheme: dark; } }
:root[data-theme="dark"] {
  --bg: #111614; --panel: #18201d; --ink: #e3ebe7; --muted: #9aa8a3; --line: #2c3833;
  --accent: #5cc5ae; --accent-soft: #17332c; --code-bg: #0d1210;
  --read: #8fd19e; --read-bg: #18301f; --write: #f0c060; --write-bg: #33270e; --push: #f19a90; --push-bg: #3a1c19;
  color-scheme: dark; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 15px/1.55 var(--sans); }
body::before { content: ""; position: fixed; inset: 0 0 auto; height: env(safe-area-inset-top, 0px); z-index: 10; background: var(--panel); }
a { color: var(--accent); }
a:focus-visible, button:focus-visible, input:focus-visible, summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.wrap { max-width: 1120px; margin: 0 auto; padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
header.top { background: var(--panel); border-bottom: 1px solid var(--line); }
header.top .wrap { padding-block: 22px 16px; display: grid; gap: 6px; }
h1 { font-size: 1.6rem; line-height: 1.2; margin: 0; letter-spacing: -0.01em; text-wrap: balance; }
.pulse { font: 13px/1.5 var(--mono); color: var(--muted); display: flex; flex-wrap: wrap; gap: 4px 16px; }
.pulse b { color: var(--ink); font-weight: 500; }
.bar { position: sticky; top: env(safe-area-inset-top, 0px); z-index: 5; background: var(--panel); border-bottom: 1px solid var(--line); }
.bar .wrap { padding-block: 10px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.bar input { flex: 1 1 220px; min-width: 0; font: inherit; padding: 7px 10px; border: 1px solid var(--line); border-radius: 6px; background: var(--bg); color: var(--ink); }
.chip { font: 12px/1 var(--sans); padding: 7px 10px; border-radius: 999px; border: 1px solid var(--line); background: var(--panel); color: var(--ink); cursor: pointer; }
.chip[aria-pressed="true"] { background: var(--accent); border-color: var(--accent); color: var(--panel); }
main .wrap { padding-block: 18px 48px; display: grid; gap: 30px; }
section.group { display: grid; gap: 14px; }
section.group > h2 { font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); margin: 0; }
article.tool { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; display: grid; grid-template-columns: minmax(0, 1fr) 300px; }
@media (max-width: 860px) { article.tool { grid-template-columns: minmax(0, 1fr); } .rail { border-left: 0 !important; border-top: 1px solid var(--line); } }
.main, .rail { padding: 16px 18px; min-width: 0; display: grid; gap: 12px; align-content: start; }
.rail { border-left: 1px solid var(--line); font-size: 13px; }
.head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 10px; }
.head h3 { margin: 0; font: 600 1.05rem/1.3 var(--mono); }
.path { font: 12px/1.4 var(--mono); color: var(--muted); overflow-wrap: anywhere; }
.lvl { font: 600 11px/1 var(--sans); letter-spacing: 0.06em; text-transform: uppercase; padding: 4px 7px; border-radius: 4px; }
.lvl.read { color: var(--read); background: var(--read-bg); } .lvl.write { color: var(--write); background: var(--write-bg); } .lvl.push { color: var(--push); background: var(--push-bg); }
.goal { margin: 0; max-width: 68ch; }
.pair { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px 18px; }
.lbl { font: 600 11px/1.3 var(--sans); text-transform: uppercase; letter-spacing: 0.07em; color: var(--muted); margin: 0 0 3px; }
.pair p, .rail p { margin: 0; }
.cmds { position: relative; background: var(--code-bg); border-radius: 6px; border: 1px solid var(--line); }
.cmds pre { margin: 0; padding: 10px 12px; overflow-x: auto; font: 12.5px/1.6 var(--mono); }
.copy { position: absolute; top: 6px; right: 6px; font: 12px var(--sans); padding: 4px 8px; border-radius: 4px; border: 1px solid var(--line); background: var(--panel); color: var(--ink); cursor: pointer; }
ul.plain { margin: 0; padding-left: 18px; }
.kv { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 3px 10px; font-variant-numeric: tabular-nums; }
.kv dt { color: var(--muted); } .kv dd { margin: 0; font-family: var(--mono); overflow-wrap: anywhere; }
.pr { display: grid; gap: 3px; padding: 7px 0; border-top: 1px dashed var(--line); }
.pr code { font: 11.5px/1.5 var(--mono); background: var(--code-bg); padding: 2px 5px; border-radius: 3px; overflow-wrap: anywhere; }
.state { font: 600 10.5px/1 var(--sans); text-transform: uppercase; letter-spacing: 0.05em; padding: 3px 5px; border-radius: 3px; background: var(--accent-soft); color: var(--accent); }
.warn { color: var(--push); }
details.src summary { cursor: pointer; color: var(--accent); font-size: 13px; }
details.src pre { max-height: 520px; overflow: auto; margin: 8px 0 0; padding: 10px 12px; background: var(--code-bg); border: 1px solid var(--line); border-radius: 6px; font: 12px/1.5 var(--mono); }
.rel a { font-family: var(--mono); font-size: 12.5px; }
footer { color: var(--muted); font-size: 13px; }
.empty { color: var(--muted); }
@media (prefers-reduced-motion: no-preference) { article.tool { transition: border-color .15s; } article.tool:target { border-color: var(--accent); } }
"""

JS = """
(function () {
  const q = document.getElementById('q');
  const chips = Array.from(document.querySelectorAll('.chip[data-level]'));
  const tools = Array.from(document.querySelectorAll('article.tool'));
  let level = 'all';
  function apply() {
    const term = (q.value || '').toLowerCase().trim();
    tools.forEach(function (t) {
      const okText = !term || t.dataset.text.indexOf(term) !== -1;
      const okLvl = level === 'all' || t.dataset.level === level;
      t.hidden = !(okText && okLvl);
    });
    document.querySelectorAll('section.group').forEach(function (g) {
      g.hidden = !g.querySelector('article.tool:not([hidden])');
    });
  }
  q.addEventListener('input', apply);
  chips.forEach(function (c) {
    c.addEventListener('click', function () {
      level = c.dataset.level;
      chips.forEach(function (x) { x.setAttribute('aria-pressed', String(x === c)); });
      apply();
    });
  });
  document.addEventListener('keydown', function (ev) {
    if (ev.key === '/' && document.activeElement !== q) { ev.preventDefault(); q.focus(); }
    if (ev.key === 'Escape') { q.value = ''; apply(); }
  });
  document.querySelectorAll('.copy').forEach(function (b) {
    b.addEventListener('click', function () {
      const pre = b.parentElement.querySelector('pre');
      const text = pre.innerText;
      function done(msg) { b.textContent = msg; setTimeout(function () { b.textContent = 'Copy'; }, 1400); }
      function select() { const r = document.createRange(); r.selectNodeContents(pre); const s = getSelection(); s.removeAllRanges(); s.addRange(r); done('Selected'); }
      if (navigator.clipboard && navigator.clipboard.writeText) { navigator.clipboard.writeText(text).then(function () { done('Copied'); }, select); }
      else { select(); }
    });
  });
})();
"""


def render_tool(t: dict, ctx: dict) -> str:
    repo, root = ctx["repo"], ctx["root"]
    f = t["facts"]
    cmds = "\n".join(c.replace("{hub}", root) for c in t["commands"])
    text = " ".join([t["id"], t["name"], t["path"], t["goal"], t["when"], t.get("not_for", ""), t["writes"]]).lower()
    blob_url = f"https://github.com/{repo}/blob/{f['commit']}/{t['path']}" if f.get("present") else ""
    parts = [f'<article class="tool" id="{e(t["id"])}" data-level="{e(t["level"])}" data-text="{e(text)}">',
             '<div class="main">',
             '<div class="head">', f'<h3>{e(t["name"])}</h3>',
             f'<span class="lvl {e(t["level"])}">{ {"read": "read-only", "write": "writes local", "push": "writes GitHub"}[t["level"]] }</span>',
             '</div>', f'<div class="path">{e(t["path"])}</div>',
             f'<p class="goal">{e(t["goal"])}</p>',
             '<div class="pair">',
             f'<div><p class="lbl">Use when</p><p>{e(t["when"])}</p></div>',
             f'<div><p class="lbl">Not for</p><p>{e(t.get("not_for") or "No known misuse.")}</p></div>',
             f'<div><p class="lbl">Writes</p><p>{e(t["writes"])}</p></div>',
             '</div>',
             '<div><p class="lbl">Run (PowerShell 7)</p>',
             f'<div class="cmds"><button class="copy" type="button">Copy</button><pre>{e(cmds)}</pre></div></div>']
    if t.get("artefacts"):
        parts.append('<div><p class="lbl">Artefacts</p><ul class="plain">'
                     + "".join(f"<li><code>{e(a)}</code></li>" for a in t["artefacts"]) + "</ul></div>")
    if f.get("present"):
        note = " (truncated)" if f["truncated"] else ""
        parts.append(f'<details class="src"><summary>Source at {e(f["commit"][:12])}, {f["lines"]} lines{note}</summary>'
                     f'<pre>{e(f["source"])}</pre></details>')
    parts.append("</div>")

    # rail: code facts, mods, docs, related
    rail = ['<div class="rail">', '<div><p class="lbl">Code</p>']
    if f.get("present"):
        commit_url = f"https://github.com/{repo}/commit/{f['commit']}"
        rail.append('<dl class="kv">'
                    f'<dt>blob</dt><dd>{e(f["blob"][:12])}</dd>'
                    f'<dt>commit</dt><dd><a href="{e(commit_url)}">{e(f["commit"][:12])}</a> {e(f["date"])}</dd>'
                    f'<dt>subject</dt><dd style="font-family:var(--sans)">{e(f["subject"])}</dd>'
                    f'<dt>lines</dt><dd>{f["lines"]}</dd></dl>'
                    f'<p><a href="{e(blob_url)}">Open on GitHub at this commit</a></p>')
        if f["dirty"]:
            rail.append('<p class="warn">Local changes in this checkout are not shown.</p>')
    else:
        rail.append('<p class="warn">Not in this checkout at HEAD. It may live only in an open PR (see Changes).</p>')
    rail.append("</div>")

    rail.append('<div><p class="lbl">Changes (PRs and issues)</p>')
    rows = []
    for r in t["refs"]:
        url = r.get("url") or f"https://github.com/{repo}/{'pull' if r['kind'] == 'pr' else 'issues'}/{r['number']}"
        rows.append(f'<div class="pr"><div><a href="{e(url)}">{e(repo)}#{r["number"]}</a> '
                    f'<span class="state">{e(r.get("state", "unknown"))}</span></div>'
                    f'<div>{e(r.get("title", "state not read (offline)"))}</div>'
                    + (f'<code>gh pr checkout {r["number"]} -R {e(repo)}</code>' if r["kind"] == "pr" else "") + "</div>")
    for p in t["open_prs"]:
        if any(r["kind"] == "pr" and r["number"] == p["number"] for r in t["refs"]):
            continue
        fix = (f'pwsh -NoProfile -File tools/workstation/Invoke-PrFixInSitu.ps1 -Repo {repo} -Pr {p["number"]}')
        rows.append(f'<div class="pr"><div><a href="{e(p["url"])}">{e(repo)}#{p["number"]}</a> '
                    f'<span class="state">{"draft" if p["isDraft"] else "open"}</span> touches this file</div>'
                    f'<div>{e(p["title"])}</div><code>gh pr checkout {p["number"]} -R {e(repo)}</code><code>{e(fix)}</code></div>')
    if rows:
        rail.extend(rows)
    else:
        rail.append(f'<p class="empty">{"No open PR touches this file." if ctx["online"] else "Build with --online to list open PRs touching this file."}</p>')
    rail.append("</div>")

    links = [(d, f"https://github.com/{repo}/blob/{ctx['head']}/{d}") for d in t.get("docs", [])]
    if t.get("ci"):
        links.append((t["ci"], f"https://github.com/{repo}/blob/{ctx['head']}/{t['ci']}"))
    if links:
        rail.append('<div><p class="lbl">Docs and CI</p><ul class="plain">'
                    + "".join(f'<li><a href="{e(u)}">{e(d)}</a></li>' for d, u in links) + "</ul></div>")
    if t.get("related"):
        rail.append('<div class="rel"><p class="lbl">Related</p>'
                    + " ".join(f'<a href="#{e(r)}">{e(ctx["names"][r])}</a>' for r in t["related"]) + "</div>")
    rail.append("</div>")
    return "\n".join(parts + rail + ["</article>"])


def render(model: dict, fragment: bool = False) -> str:
    ctx = {"repo": model["repo"], "root": model["root"], "head": model["head"], "online": model["online"],
           "names": {t["id"]: t["name"] for t in model["tools"]}}
    missing = sum(1 for t in model["tools"] if not t["facts"].get("present"))
    open_prs = len({p["number"] for t in model["tools"] for p in t["open_prs"]})
    counts = {lvl: sum(1 for t in model["tools"] if t["level"] == lvl) for lvl in ("read", "write", "push")}
    head_url = f"https://github.com/{model['repo']}/commit/{model['head']}"
    body = [
        '<header class="top"><div class="wrap">',
        "<h1>Workstation Tool Catalog</h1>",
        '<div class="pulse">'
        f'<span>repo <b>{e(model["repo"])}</b></span>'
        f'<span>snapshot <b><a href="{e(head_url)}">{e(model["head"][:12])}</a></b> ({e(model["branch"])})</span>'
        f'<span>built <b>{e(model["built"])}</b></span>'
        f'<span><b>{len(model["tools"])}</b> tools · <b>{counts["read"]}</b> read-only · <b>{counts["write"]}</b> write local · <b>{counts["push"]}</b> write GitHub</span>'
        + (f'<span><b>{open_prs}</b> open PRs touch these tools</span>' if model["online"] else "<span>offline build: PR state not read</span>")
        + (f'<span class="warn"><b>{missing}</b> not in this checkout</span>' if missing else "")
        + "</div></div></header>",
        '<div class="bar"><div class="wrap">',
        '<input id="q" type="search" placeholder="Filter tools (press /)" aria-label="Filter tools">',
        '<button class="chip" type="button" data-level="all" aria-pressed="true">All</button>',
        '<button class="chip" type="button" data-level="read" aria-pressed="false">Read-only</button>',
        '<button class="chip" type="button" data-level="write" aria-pressed="false">Writes local</button>',
        '<button class="chip" type="button" data-level="push" aria-pressed="false">Writes GitHub</button>',
        "</div></div>",
        '<main><div class="wrap">',
    ]
    for g in model["groups"]:
        tools = [t for t in model["tools"] if t["group"] == g["id"]]
        if not tools:
            continue
        body.append(f'<section class="group" id="g-{e(g["id"])}"><h2>{e(g["title"])}</h2>')
        body.extend(render_tool(t, ctx) for t in tools)
        body.append("</section>")
    body.append('<footer>Generated by tools/workstation/build_tool_catalog.py from TOOLS_CATALOG.json. '
                'Edit the JSON and rebuild; code facts come from git at the snapshot commit.</footer>')
    body.append("</div></main>")
    head = ('<title>Workstation Tool Catalog</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n'
            '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600'
            '&family=IBM+Plex+Sans:wght@400;500;600&display=swap">\n'
            f"<style>{CSS}</style>")
    page = head + "\n" + "\n".join(body) + f"\n<script>{JS}</script>\n"
    if fragment:
        return page
    return ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            + head + "\n</head>\n<body>\n" + "\n".join(body) + f"\n<script>{JS}</script>\n</body>\n</html>\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--catalog", type=Path, default=HERE / "TOOLS_CATALOG.json")
    ap.add_argument("--root", type=Path, default=None, help="hub checkout (default: the repo holding this script)")
    ap.add_argument("--out", type=Path, default=Path.home() / "DASHBOARDS" / "tools_catalog.html")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--online", action="store_true", help="read PR / issue state with gh")
    mode.add_argument("--offline", action="store_true", help="no gh calls (default)")
    ap.add_argument("--fragment", action="store_true", help="omit <html>/<head>/<body> (for hosts that add them)")
    ap.add_argument("--json", type=Path, default=None, help="also write the built model (without sources) here")
    args = ap.parse_args(argv)
    root = (args.root or Path(git(HERE, "rev-parse", "--show-toplevel") or HERE)).resolve()
    catalog = load_catalog(args.catalog)
    online = online_facts(catalog["repo"], catalog["tools"]) if args.online else None
    if args.online and not online["ok"]:
        print("WARN: gh could not list PRs; PR state is UNKNOWN in this build", file=sys.stderr)
    now = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %z")
    model = build(catalog, root, online, now)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(model, fragment=args.fragment), encoding="utf-8", newline="\n")
    if args.json:
        slim = {**model, "tools": [{**t, "facts": {k: v for k, v in t["facts"].items() if k != "source"}} for t in model["tools"]]}
        args.json.write_text(json.dumps(slim, indent=1, default=list), encoding="utf-8", newline="\n")
    print(f"wrote {args.out} ({len(model['tools'])} tools, snapshot {model['head'][:12]}, online={model['online']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
