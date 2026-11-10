#!/usr/bin/env python3
"""Render-check Mermaid diagrams from Markdown or .mmd files in a browser (stdlib only, Python 3.8+).

Usage:
  python build_mermaid_check.py                         # WDDD_WEEK_CODES.md, with %W -> %V comparison (default)
  python build_mermaid_check.py docs README.md flow.mmd # any mix of files and folders
  python build_mermaid_check.py docs --serve            # build, serve on 127.0.0.1 and open the browser
  python build_mermaid_check.py docs -o out.html --mermaid 11.4.1 --strict

It writes one HTML page that renders every diagram with one pinned Mermaid version. For each diagram it shows
"rendered" or the parse error, and the axis labels of a Gantt chart. `window.__results` holds the same outcome
for scripts. Before the browser step it lints in Python: a Gantt `axisFormat` with %W is flagged, because %W is
the Monday-based week of the calendar year, not the ISO week (use %V).

Markdown parsing follows CommonMark fences: ``` or ~~~ with info string `mermaid`; a fence closes on the same
character repeated at least as often; other fenced blocks are skipped whole, so a ```mermaid example inside a
````markdown block is not taken as a diagram. A .mmd or .mermaid file is one diagram.
"""
from __future__ import annotations

import argparse
import functools
import http.server
import json
import os
import re
import socket
import sys
import tempfile
import webbrowser
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Sequence

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
DEFAULT_INPUT = REPO_ROOT / "mission-control" / "jade_temple" / "devops" / "WDDD_WEEK_CODES.md"
DEFAULT_OUT = Path(tempfile.gettempdir()) / "mermaid_check" / "mermaid_check.html"
DEFAULT_MERMAID = "11.4.1"
DEFAULT_PORT = 8796
MD_SUFFIXES = {".md", ".markdown"}
MMD_SUFFIXES = {".mmd", ".mermaid"}
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".tox", ".mypy_cache", ".pytest_cache"}

_FENCE = re.compile(r"^(?P<indent> {0,3})(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
_VERSION = re.compile(r"^\d+\.\d+\.\d+$")
W_LINT = "axisFormat uses %W, the Monday-based week of the calendar year, not the ISO week; use %V"


@dataclass
class Diagram:
    source: str  # path as shown to the user
    line: int  # 1-based line of the opening fence (1 for a .mmd file)
    text: str
    dtype: str = ""
    lint: List[str] = field(default_factory=list)
    variant: str = ""

    @property
    def name(self) -> str:
        label = f"{self.source}:{self.line} ({self.dtype})"
        return f"{label} [{self.variant}]" if self.variant else label


def diagram_type(text: str) -> str:
    """First keyword after optional YAML front matter, %% comments and %%{init}%% directives."""
    lines = [s.strip() for s in text.splitlines()]
    start = 0
    if lines and lines[0] == "---":
        if "---" not in lines[1:]:
            return "unknown"
        start = lines.index("---", 1) + 1
    for s in lines[start:]:
        if s and not s.startswith("%%"):
            return s.split()[0].rstrip(":;")
    return "empty"


def lint(text: str, dtype: str) -> List[str]:
    warnings = []
    if dtype == "gantt":
        for n, raw in enumerate(text.splitlines(), 1):
            s = raw.strip()
            if s.startswith("axisFormat") and "%W" in s:
                warnings.append(f"diagram line {n}: {W_LINT}")
    return warnings


def _dedent(line: str, n: int) -> str:
    i = 0
    while i < n and i < len(line) and line[i] == " ":
        i += 1
    return line[i:]


def extract_markdown(text: str, source: str) -> List[Diagram]:
    lines = text.splitlines()
    found: List[Diagram] = []
    i = 0
    while i < len(lines):
        m = _FENCE.match(lines[i])
        if not m or (m["fence"][0] == "`" and "`" in m["info"]):
            i += 1
            continue
        fence, indent = m["fence"], len(m["indent"])
        info = m["info"].strip().split()
        is_mermaid = bool(info) and re.match(r"^mermaid(\{.*)?$", info[0], re.I) is not None
        close = re.compile(r"^ {0,3}" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}[ \t]*$")
        j, body = i + 1, []
        while j < len(lines) and not close.match(lines[j]):
            body.append(_dedent(lines[j], indent))
            j += 1
        if is_mermaid:
            d = Diagram(source=source, line=i + 1, text="\n".join(body) + "\n")
            if j >= len(lines):
                d.lint.append(f"fence opened at line {i + 1} is never closed; read to the end of the file")
            found.append(d)
        i = j + 1
    return found


def iter_files(paths: Iterable[Path]) -> Iterator[Path]:
    for p in paths:
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                rel_parts = f.relative_to(p).parts
                if f.is_file() and f.suffix.lower() in MD_SUFFIXES | MMD_SUFFIXES and not SKIP_DIRS.intersection(rel_parts):
                    yield f
        elif p.is_file():
            yield p
        else:
            raise FileNotFoundError(f"no such file or folder: {p}")


def display(p: Path) -> str:
    """Path relative to the current folder, climbing at most two levels; otherwise absolute."""
    try:
        rel = Path(os.path.relpath(p.resolve(), Path.cwd().resolve()))
    except ValueError:  # another drive
        return p.resolve().as_posix()
    return rel.as_posix() if rel.parts[:3].count("..") < 3 else p.resolve().as_posix()


def collect(paths: Sequence[Path]) -> List[Diagram]:
    diagrams: List[Diagram] = []
    for f in iter_files(paths):
        text = f.read_text(encoding="utf-8-sig", errors="replace")
        if f.suffix.lower() in MMD_SUFFIXES:
            found = [Diagram(source=display(f), line=1, text=text)]
        else:
            found = extract_markdown(text, display(f))
        for d in found:
            d.dtype = diagram_type(d.text)
            d.lint.extend(lint(d.text, d.dtype))
        diagrams.extend(found)
    return diagrams


def with_iso_week_variants(diagrams: List[Diagram]) -> List[Diagram]:
    """After each Gantt flagged for %W, add a copy whose axisFormat uses %V, so both axes can be compared."""
    out: List[Diagram] = []
    for d in diagrams:
        out.append(d)
        if any(W_LINT in w for w in d.lint):
            fixed = "\n".join(
                ln.replace("%W", "%V") if ln.strip().startswith("axisFormat") else ln for ln in d.text.splitlines()
            ) + "\n"
            out.append(replace(d, text=fixed, lint=[], variant="axisFormat %W -> %V"))
    return out


def _script_json(obj: object) -> str:
    """JSON that is safe inside <script>: no '<', '>' or '&' survives literally."""
    return json.dumps(obj).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Mermaid check</title>
<style>
body{font:14px/1.45 system-ui,sans-serif;margin:16px auto;padding:0 16px;max-width:1200px;background:#fff;color:#111}
/* A Gantt takes its width from the page while it renders and keeps 11px text, so on a full-HD screen it
   comes out very wide and sparse. Capping the page width gives the same proportions on any screen. */
h1{font-size:18px;margin:0 0 4px}h2{font-size:14px;margin:28px 0 4px;font-family:ui-monospace,Consolas,monospace}
.meta{color:#555;margin:0 0 12px}.ok{color:#0a7a2f}.err{color:#b00020;white-space:pre-wrap}.warn{color:#8a5a00}
.box{overflow-x:auto;border:1px solid #ddd;border-radius:6px;padding:8px;margin:4px 0;background:#fff}
body.darkbox .box{background:#0f172a;border-color:#334155}
button{font:inherit;padding:2px 10px;margin-left:8px;cursor:pointer}
</style>
<script src="https://cdn.jsdelivr.net/npm/mermaid@__VERSION__/dist/mermaid.min.js"></script></head><body>
<h1>Mermaid check</h1><p class="meta">Mermaid __VERSION__ &middot; __COUNT__ diagram(s) &middot; <span id="summary">rendering&hellip;</span>
<button id="bg" type="button" title="Some diagrams are themed for a dark page">Dark background</button></p>
<div id="out"></div>
<script>
const CASES = __CASES__;
mermaid.initialize({startOnLoad: false, securityLevel: 'strict'});
document.getElementById('bg').addEventListener('click', e => {
  const dark = document.body.classList.toggle('darkbox');
  e.target.textContent = dark ? 'Light background' : 'Dark background';
});
// Render ids must not collide with ids inside the diagrams (a Gantt task called m1 becomes id="m1"),
// or Mermaid measures and styles the wrong element. Hence a per-load random namespace.
const NS = 'mmdcheck-' + Math.random().toString(36).slice(2, 8) + '-';
(async () => {
  const out = document.getElementById('out'); const results = [];
  const add = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; e.textContent = text; out.appendChild(e); return e; };
  for (const [i, c] of CASES.entries()) {
    add('h2', '', c.name);
    for (const w of c.lint) add('p', 'warn', 'lint: ' + w);
    const box = add('div', 'box', '');
    try {
      const {svg} = await mermaid.render(NS + i, c.text);
      box.innerHTML = svg;
      const ticks = [...box.querySelectorAll('.tick text')].map(t => t.textContent.trim()).filter(Boolean);
      results.push({name: c.name, ok: true, lint: c.lint, ticks: ticks.slice(0, 16)});
      add('p', 'ok', 'rendered' + (ticks.length ? ' | axis: ' + ticks.join(', ') : ''));
    } catch (e) {
      box.remove();
      const msg = String((e && e.message) || e);
      results.push({name: c.name, ok: false, lint: c.lint, error: msg});
      add('p', 'err', 'ERROR: ' + msg);
    }
  }
  const bad = results.filter(r => !r.ok).length, warns = results.reduce((n, r) => n + r.lint.length, 0);
  document.getElementById('summary').textContent = `${results.length - bad} rendered, ${bad} with errors, ${warns} lint warning(s)`;
  window.__results = results;
})();
</script></body></html>
"""


def build_page(diagrams: Sequence[Diagram], version: str = DEFAULT_MERMAID) -> str:
    if not _VERSION.match(version):
        raise ValueError(f"Mermaid version must be exact, like 11.4.1: {version!r}")
    cases = [{"name": d.name, "text": d.text, "lint": d.lint} for d in diagrams]
    return (
        PAGE.replace("__VERSION__", version)
        .replace("__COUNT__", str(len(cases)))
        .replace("__CASES__", _script_json(cases))
    )


class _ExclusiveServer(http.server.ThreadingHTTPServer):
    """No SO_REUSEADDR: on Windows it lets a second server bind a port that is already in use, silently."""

    allow_reuse_address = False

    def server_bind(self) -> None:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def serve(page: Path, port: int, open_browser: bool) -> None:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(page.parent))
    for p in range(port, port + 10):
        try:
            httpd = _ExclusiveServer(("127.0.0.1", p), handler)
            break
        except OSError:
            continue
    else:
        raise SystemExit(f"no free port in {port}-{port + 9}")
    url = f"http://127.0.0.1:{p}/{page.name}"
    print(f"Serving {page.parent} at {url}  (Ctrl+C to stop)")
    if open_browser:
        webbrowser.open(url)
    with httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("stopped")


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Render-check Mermaid diagrams from Markdown or .mmd files in a browser.")
    ap.add_argument("paths", nargs="*", type=Path, help="Markdown or .mmd files and folders (default: mission-control/jade_temple/devops/WDDD_WEEK_CODES.md)")
    ap.add_argument("-o", "--out", type=Path, default=DEFAULT_OUT, help=f"page to write (default: {DEFAULT_OUT})")
    ap.add_argument("--mermaid", default=DEFAULT_MERMAID, help=f"exact Mermaid version from jsdelivr (default {DEFAULT_MERMAID})")
    ap.add_argument("--compare-iso-week", action="store_true", help="add a %%V copy after each Gantt that uses %%W (on by default with no paths)")
    ap.add_argument("--strict", action="store_true", help="exit 1 when any lint warning is found")
    ap.add_argument("--serve", nargs="?", const=DEFAULT_PORT, type=int, metavar="PORT", help=f"serve the page on 127.0.0.1 (default port {DEFAULT_PORT})")
    ap.add_argument("--no-open", action="store_true", help="with --serve, don't open the browser")
    args = ap.parse_args(argv)

    paths = args.paths or [DEFAULT_INPUT]
    try:
        diagrams = collect(paths)
    except FileNotFoundError as e:
        print(f"error: {e}. Give real file or folder paths.")
        return 2
    if not diagrams:
        print("no Mermaid diagrams found in: " + ", ".join(str(p) for p in paths))
        return 1
    if args.compare_iso_week or not args.paths:
        diagrams = with_iso_week_variants(diagrams)

    out: Path = args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_page(diagrams, args.mermaid), encoding="utf-8", newline="\n")

    warnings = 0
    for d in diagrams:
        print(f"{d.name}" + "".join(f"\n    lint: {w}" for w in d.lint))
        warnings += len(d.lint)
    print(f"{len(diagrams)} diagram(s), {warnings} lint warning(s) -> {out}")

    if args.serve is not None:
        serve(out, args.serve, open_browser=not args.no_open)
    return 1 if (args.strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
