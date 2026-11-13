#!/usr/bin/env python3
"""CODE MAROON REX: run known fixes against a local diff before it reaches GitHub.

`hints.py` tells a worker which review findings recur once they are on GitHub. REX moves that
knowledge left: a small catalog (`data/REX_KNOWN_FIXES_v1.json`) maps each recurring finding to a
local detector and one agreed fix, and `scan` runs the catalog over the lines a branch adds.

    python rex.py fetch --repos GBOGEB/pipeline-automation-hub,GBOGEB/ABACUS --out <dir>   # read-only
    python rex.py mine --comments <dir>/review_comments.jsonl [--write-evidence]          # coverage + candidates
    python rex.py scan [--base origin/master] [--fix] [--strict] [--json]                  # before push
    python rex.py install-hook [--force]                                                   # advisory pre-push hook

`mine` counts how many review comments each entry would have caught and lists the recurring
findings the catalog does not cover yet (finding identity from `hints.finding_key`), so the
dictionary grows from data. `scan` is advisory unless `--strict` (or `REX_STRICT=1` in the hook):
it attacks known defects early, it does not claim the diff is clean. Every result is
`PREPUSH_HINT_NOT_REVIEW_PROOF`.
"""
from __future__ import annotations

import argparse
import ast
import collections
import fnmatch
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CATALOG = HERE / "data" / "REX_KNOWN_FIXES_v1.json"
SCHEMA = "code_maroon.rex_known_fixes.v1"
SCAN_SCHEMA = "code_maroon.rex_scan.v1"
MINE_SCHEMA = "code_maroon.rex_mine.v1"
AUTHORITY = "PREPUSH_HINT_NOT_REVIEW_PROOF"
HOOK_MARK = "# code-maroon-rex pre-push hook"

_spec = importlib.util.spec_from_file_location("maroon_rex_hints", HERE / "hints.py")
HINTS = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(HINTS)

_BADGE = re.compile(r"!\[[^\]]*\]\([^)]*\)|<[^>]+>|\*\*")


def load_catalog(path: Path = CATALOG) -> dict:
    cat = json.loads(path.read_text(encoding="utf-8"))
    if cat.get("schema") != SCHEMA:
        raise SystemExit(f"rex: {path} is not {SCHEMA}")
    ids = [e["rex_id"] for e in cat["entries"]]
    if len(ids) != len(set(ids)):
        raise SystemExit("rex: duplicate rex_id in catalog")
    return cat


def first_line(body: str) -> str:
    """The finding's title. A scanner header with no rule (`## Bandit / `) is joined to the next line."""
    lines = [s.strip().lstrip("#").strip() for s in _BADGE.sub("", body or "").splitlines()]
    lines = [s for s in lines if s]
    for i, s in enumerate(lines):
        if s.endswith("/") and i + 1 < len(lines):
            return f"{s} {lines[i + 1]}"
        if len(s) > 10:
            return s
    return ""


def match_entry(cat: dict, text: str) -> str | None:
    low = text.lower()
    for e in cat["entries"]:
        if any(m.lower() in low for m in e.get("review_match", [])):
            return e["rex_id"]
    return None


# ---------------------------------------------------------------- mine


def mine(cat: dict, comments: list[dict], min_prs: int = 3, top: int = 25) -> dict:
    """Coverage of the catalog over review comments, plus recurring findings it does not cover."""
    rows = [c for c in comments if not c.get("reply")]
    hit = collections.Counter()
    hit_prs = collections.defaultdict(set)
    miss = collections.Counter()
    miss_prs = collections.defaultdict(set)
    example = {}
    for c in rows:
        t = first_line(c.get("body", ""))
        pr = (c.get("repo"), str(c.get("pr")))
        rid = match_entry(cat, t)
        if rid:
            hit[rid] += 1
            hit_prs[rid].add(pr)
            continue
        k = HINTS.finding_key(c.get("repo") or "", t)
        miss[k] += 1
        miss_prs[k].add(pr)
        example.setdefault(k, {"title": t[:160], "reviewer": c.get("user"), "repo": c.get("repo")})
    candidates = sorted((k for k in miss if len(miss_prs[k]) >= min_prs), key=lambda k: (-len(miss_prs[k]), -miss[k], k))
    covered = sum(hit.values())
    return {
        "schema": MINE_SCHEMA, "authority": AUTHORITY,
        "comments": len(rows), "covered": covered,
        "coverage": round(covered / len(rows), 4) if rows else None,
        "by_reviewer": dict(collections.Counter(c.get("user") for c in rows).most_common()),
        "entries": {e["rex_id"]: {"comments": hit[e["rex_id"]], "prs": len(hit_prs[e["rex_id"]])} for e in cat["entries"]},
        "candidates": [dict(example[k], key=k, comments=miss[k], prs=len(miss_prs[k])) for k in candidates[:top]],
    }


def write_evidence(path: Path, report: dict, source: str) -> None:
    cat = json.loads(path.read_text(encoding="utf-8"))
    for e in cat["entries"]:
        e["evidence"] = report["entries"].get(e["rex_id"], {"comments": 0, "prs": 0})
    cat["evidence_source"] = {"source": source, "comments": report["comments"], "coverage": report["coverage"]}
    path.write_text(json.dumps(cat, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


# ---------------------------------------------------------------- git


def tool(name: str) -> str:
    """Absolute path of a required executable (no partial-path process starts)."""
    path = shutil.which(name)
    if not path:
        raise SystemExit(f"rex: `{name}` is not on PATH")
    return path


def git(*args: str, cwd: Path | None = None) -> str:
    argv = [tool("git"), *args]
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, encoding="utf-8",  # noqa: S603 (resolved git, no shell)
                          errors="replace", check=True).stdout


HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def added_lines(diff: str) -> dict[str, dict[int, str]]:
    """path -> {new line number: text} for every added line of a unified diff (`-U0`)."""
    out: dict[str, dict[int, str]] = {}
    path, n = None, 0
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = None if line[4:] == "/dev/null" else line[4:].removeprefix("b/")
            if path:
                out.setdefault(path, {})
        elif line.startswith("@@"):
            m = HUNK.match(line)
            n = int(m.group(1)) if m else 0
        elif path and line.startswith("+") and not line.startswith("+++"):
            out[path][n] = line[1:]
            n += 1
    return out


def resolve_base(root: Path, base: str) -> str:
    """`base` if it names a commit; for the default `origin/HEAD` (absent in many clones) fall back to
    `origin/main`, then `origin/master`. Anything else unresolvable stops with a clear message."""
    candidates = [base] + (["origin/main", "origin/master"] if base == "origin/HEAD" else [])
    for ref in candidates:
        try:
            git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", cwd=root)
        except subprocess.CalledProcessError:
            continue
        return ref
    raise SystemExit(f"rex: base {' / '.join(candidates)} not found; pass --base <ref>")


def changed(root: Path, base: str) -> dict[str, dict[int, str]]:
    mb = git("merge-base", resolve_base(root, base), "HEAD", cwd=root).strip()
    committed = added_lines(git("diff", "-U0", "--no-color", "--diff-filter=AMR", mb, "HEAD", cwd=root))
    working = added_lines(git("diff", "-U0", "--no-color", "--diff-filter=AMR", "HEAD", cwd=root))
    for p, lines in working.items():
        committed.setdefault(p, {}).update(lines)
    return committed


def _match(path: str, globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, g) for g in globs)


# ---------------------------------------------------------------- detectors


def det_regex(e, files, root):
    d = e["detector"]
    rx = re.compile(d["pattern"])
    for path, lines in files.items():
        if _match(path, d.get("paths", ["*"])):
            for n, text in sorted(lines.items()):
                if rx.search(text):
                    yield path, n, text.strip()[:160]


def det_exec_bit(e, files, root):
    for path, lines in files.items():
        if path.endswith(".py") and 1 in lines and lines[1].startswith("#!"):
            mode = git("ls-files", "-s", "--", path, cwd=root).split(" ", 1)[0]
            if mode != "100755":
                yield path, 1, f"shebang with git mode {mode or 'untracked'}"


_IMP = re.compile(r"^import\s+([\w.]+)(?:\s+as\s+\w+)?\s*$")
_FROM = re.compile(r"^from\s+([\w.]+)\s+import\b")


def det_dual_import(e, files, root):
    for path, lines in files.items():
        p = root / path
        if not path.endswith(".py") or not p.is_file():
            continue
        imp, frm = {}, {}
        for i, text in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if (m := _IMP.match(text)):
                imp.setdefault(m.group(1), i)
            elif (m := _FROM.match(text)):
                frm.setdefault(m.group(1), i)
        for mod in sorted(set(imp) & set(frm)):
            if imp[mod] in lines or frm[mod] in lines:
                yield path, max(imp[mod], frm[mod]), f"`import {mod}` and `from {mod} import`"


def det_write_text_newline(e, files, root):
    """`Path.write_text(...)` calls on added lines that do not pass `newline=` (AST, not regex)."""
    for path, lines in files.items():
        p = root / path
        if not path.endswith(".py") or not p.is_file():
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "write_text"
                    and node.lineno in lines and not any(k.arg == "newline" for k in node.keywords)):
                yield path, node.lineno, lines[node.lineno].strip()[:160]


def det_workflow_permissions(e, files, root):
    for path in files:
        p = root / path
        if _match(path, [".github/workflows/*.yml", ".github/workflows/*.yaml"]) and p.is_file():
            if not re.search(r"(?m)^permissions:", p.read_text(encoding="utf-8", errors="replace")):
                yield path, 1, "no top-level permissions"


def det_companion(e, files, root):
    d = e["detector"]
    if not (root / d["requires_file"]).is_file():
        return
    if "when_hints_regex" in d:
        rx = getattr(HINTS, d["when_hints_regex"])
        trig = sorted(p for p in files if rx.search(p))
    else:
        trig = sorted(p for p in files if _match(p, d["when"]))
    if trig and not any(_match(p, d["expect"]) for p in files):
        yield trig[0], 0, f"{len(trig)} trigger path(s) changed, none of {d['expect']} changed"


def ruff_findings(cat, files, root, target, fix=False):
    """{rex_id: [(path, line, text)]} from one ruff run over the changed Python files."""
    exe = shutil.which("ruff")
    py = sorted(p for p in files if p.endswith(".py") and (root / p).is_file())
    entries = [e for e in cat["entries"] if e["detector"]["kind"] == "ruff"]
    if not py or not entries:
        return {}, None
    if not exe:
        return {}, "ruff not on PATH: ruff-based entries skipped (pip install ruff)"
    code_of = {c: e["rex_id"] for e in entries for c in e["detector"]["codes"]}
    exclude = {e["rex_id"]: e["detector"].get("exclude", []) for e in entries}
    syntax_id = next((e["rex_id"] for e in entries if e["detector"].get("syntax")), None)
    base = [exe, "check", "--no-cache", "--isolated", "--preview", "--select", ",".join(sorted(c for c in code_of if c != "E999"))]
    if target:
        base += ["--target-version", target]
    if fix:
        auto = sorted(c for e in entries if e["mode"] == "autofix" for c in e["detector"]["codes"])
        fix_argv = [*base[:5], "--select", ",".join(auto), "--fix", *(["--target-version", target] if target else []), *py]
        subprocess.run(fix_argv, cwd=root, capture_output=True, check=False)  # noqa: S603 (resolved ruff path)
    run = subprocess.run([*base, "--output-format", "json", *py], cwd=root, capture_output=True,  # noqa: S603 (resolved ruff path)
                         text=True, encoding="utf-8", errors="replace", check=False)
    if run.returncode not in (0, 1):
        return {}, f"ruff exited {run.returncode}, ruff entries are unchecked: {(run.stderr or '').strip()[:200]}"
    out = collections.defaultdict(list)
    failed = [ln.strip() for ln in (run.stderr or "").splitlines() if "Failed to lint" in ln]
    for f in json.loads(run.stdout or "[]"):
        path = Path(f["filename"]).resolve().relative_to(root.resolve()).as_posix()
        line = f["location"]["row"]
        rid = code_of.get(f.get("code") or "") or (syntax_id if not f.get("code") or f.get("code") == "invalid-syntax" else None)
        if rid and not _match(path, exclude.get(rid, [])) and (line in files.get(path, {}) or rid == syntax_id):
            out[rid].append((path, line, f"{f.get('code') or 'syntax'}: {f['message'][:140]}"))
    return out, (f"ruff could not read {len(failed)} file(s), their ruff entries are unchecked: {failed[0]}" if failed else None)


DETECTORS = {"regex": det_regex, "exec_bit": det_exec_bit, "dual_import": det_dual_import,
             "workflow_permissions": det_workflow_permissions, "companion": det_companion,
             "write_text_newline": det_write_text_newline}


def target_version(root: Path) -> str | None:
    pv = root / ".python-version"
    if pv.is_file() and (m := re.match(r"\s*3\.(\d+)", pv.read_text(encoding="utf-8"))):
        return f"py3{m.group(1)}"
    return None


def scan(cat: dict, files: dict[str, dict[int, str]], root: Path, target: str | None = None, fix: bool = False) -> dict:
    findings = []
    ruff, note = ruff_findings(cat, files, root, target, fix=fix)
    for e in cat["entries"]:
        kind = e["detector"]["kind"]
        hits = ruff.get(e["rex_id"], []) if kind == "ruff" else list(DETECTORS[kind](e, files, root))
        for path, line, text in hits:
            findings.append({"rex_id": e["rex_id"], "path": path, "line": line, "text": text,
                             "known_fix": e["known_fix"], "mode": e["mode"]})
    findings.sort(key=lambda f: (f["rex_id"], f["path"], f["line"]))
    return {"schema": SCAN_SCHEMA, "authority": AUTHORITY, "files": len(files), "target": target,
            "findings": findings, "by_rex": dict(collections.Counter(f["rex_id"] for f in findings)),
            "notes": [note] if note else [], "self_review": cat.get("self_review", [])}


def render(report: dict, cat: dict) -> str:
    title = {e["rex_id"]: e["title"] for e in cat["entries"]}
    out = [f"REX scan: {report['files']} changed file(s), {len(report['findings'])} known-fix hit(s)  [{AUTHORITY}]"]
    last = None
    for f in report["findings"]:
        if f["rex_id"] != last:
            out += ["", f"{f['rex_id']}  {title[f['rex_id']]}  ({f['mode']})", f"  fix: {f['known_fix']}"]
            last = f["rex_id"]
        out.append(f"  {f['path']}:{f['line']}  {f['text']}")
    out += [f"note: {n}" for n in report["notes"]]
    if report["self_review"]:
        out += ["", "Self-review before push (the recurring Codex P1 questions):"] + [f"  [ ] {q}" for q in report["self_review"]]
    return "\n".join(out)


# ---------------------------------------------------------------- fetch / hook


def fetch(repos: list[str], limit: int) -> list[dict]:
    rows = []
    q = ('.[] | {pr:(.pull_request_url|split("/")|last), path, user:.user.login, created:.created_at,'
         ' body:(.body[0:600]), reply:(.in_reply_to_id!=null)}')
    for repo in repos:
        argv = [tool("gh"), "api", f"repos/{repo}/pulls/comments?per_page=100&sort=created&direction=desc", "--paginate", "-q", q]
        run = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", check=True)  # noqa: S603 (resolved gh, no shell)
        for line in run.stdout.splitlines()[:limit]:
            rows.append(dict(json.loads(line), repo=repo))
    return rows


def install_hook(root: Path, force: bool) -> Path:
    hooks = Path(git("rev-parse", "--git-common-dir", cwd=root).strip())
    hooks = (hooks if hooks.is_absolute() else root / hooks) / "hooks"
    hook = hooks / "pre-push"
    if hook.exists() and HOOK_MARK not in hook.read_text(encoding="utf-8", errors="replace") and not force:
        raise SystemExit(f"rex: {hook} exists and is not ours; pass --force to replace it")
    hooks.mkdir(parents=True, exist_ok=True)
    me = Path(__file__).resolve().as_posix()
    hook.write_text(f"#!/bin/sh\n{HOOK_MARK}\n# Advisory unless REX_STRICT=1. Skip once with: git push --no-verify\n"
                    f"python \"{me}\" scan --base origin/HEAD ${{REX_STRICT:+--strict}}\n", encoding="utf-8", newline="\n")
    hook.chmod(0o755)
    return hook


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--repos", required=True)
    f.add_argument("--limit", type=int, default=4000)
    f.add_argument("--out", required=True)
    m = sub.add_parser("mine")
    m.add_argument("--comments", nargs="+", required=True)
    m.add_argument("--min-prs", type=int, default=3)
    m.add_argument("--out")
    m.add_argument("--write-evidence", action="store_true")
    s = sub.add_parser("scan")
    s.add_argument("--base", default="origin/HEAD")
    s.add_argument("--repo", default=".")
    s.add_argument("--target-version")
    s.add_argument("--fix", action="store_true", help="apply ruff fixes for autofix entries to changed files")
    s.add_argument("--strict", action="store_true")
    s.add_argument("--json", action="store_true")
    h = sub.add_parser("install-hook")
    h.add_argument("--repo", default=".")
    h.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cat = load_catalog()

    if a.cmd == "fetch":
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        rows = fetch([r.strip() for r in a.repos.split(",") if r.strip()], a.limit)
        (out / "review_comments.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                                                   encoding="utf-8", newline="\n")
        print(f"rex: {len(rows)} review comments -> {out / 'review_comments.jsonl'} (private: keep out of the repo)")
        return 0
    if a.cmd == "mine":
        rows = [json.loads(line) for p in a.comments for line in Path(p).read_text(encoding="utf-8").splitlines() if line.strip()]
        rep = mine(cat, rows, a.min_prs)
        if a.out:
            Path(a.out).write_text(json.dumps(rep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        if a.write_evidence:
            write_evidence(CATALOG, rep, source=f"{rep['comments']} top-level review comments")
        print(f"rex: {rep['covered']}/{rep['comments']} review comments covered ({rep['coverage']:.1%}); "
              f"{len(rep['candidates'])} uncatalogued finding(s) on >= {a.min_prs} PRs")
        for c in rep["candidates"][:10]:
            print(f"  {c['prs']:3d} PRs {c['comments']:4d}x  {c['title'][:110]}")
        return 0
    root = Path(git("rev-parse", "--show-toplevel", cwd=Path(a.repo)).strip())
    if a.cmd == "install-hook":
        print(f"rex: advisory pre-push hook written to {install_hook(root, a.force)}")
        return 0
    rep = scan(cat, changed(root, a.base), root, a.target_version or target_version(root), fix=a.fix)
    print(json.dumps(rep, indent=2) if a.json else render(rep, cat))
    return 1 if a.strict and rep["findings"] else 0


if __name__ == "__main__":
    sys.exit(main())
