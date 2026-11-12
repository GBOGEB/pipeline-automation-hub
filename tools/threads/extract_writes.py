"""Recover files that Claude Code sessions wrote, from the raw JSONL transcripts.

Use it after a session's notes folder or scratch files are gone: every Write call's full
content is still in ``~/.claude/projects/*/<cliSessionId>.jsonl``.

    python tools/threads/extract_writes.py list <jsonl>...
    python tools/threads/extract_writes.py dump <outdir> <substr> <jsonl>...

``list`` prints every Write / Edit / MultiEdit with its timestamp and ``file_path``.
``dump`` rebuilds each path whose ``file_path`` contains ``substr``: the last Write, then
every later Edit replayed on top of it. It writes ``MANIFEST.json`` with a status per path:

- ``complete``: the last Write plus all later Edits applied cleanly.
- ``partial``: an Edit did not apply, or the path has Edits but no Write (an Edit holds
  only a fragment). A partial file is written as ``<name>.partial``; an Edit-only path
  gets ``<name>.edits.json`` with the fragments and no rebuilt file.

Lessons kept from the workstation version (hub#1191):

- Read the JSONL with ``errors="replace"`` and skip lines that do not parse; live sessions
  append partial lines.
- Write output with ``newline=""`` so CRLF content round-trips unchanged.
- Each path dumps into its own subfolder, so two files with one basename never overwrite
  each other.
- Never dump into a git work tree: transcripts can hold private content. Use a scratch
  folder.

Limits: files written through Bash heredocs (``cat > f <<EOF``) are not Write calls and
are not seen; search the Bash ``command`` inputs for those. Stdlib only, offline.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

TOOLS = ("Write", "Edit", "MultiEdit")


def iter_calls(paths):
    """Yield ``{ts, tool, file_path, input, src}`` for each Write/Edit/MultiEdit, in order."""
    for p in paths:
        with open(p, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue  # partial line from a live session, or corrupt
                msg = rec.get("message") if isinstance(rec, dict) else None
                content = msg.get("content") if isinstance(msg, dict) else None
                if not isinstance(content, list):
                    continue
                for part in content:
                    if not isinstance(part, dict) or part.get("type") != "tool_use":
                        continue
                    inp = part.get("input")
                    if part.get("name") not in TOOLS or not isinstance(inp, dict):
                        continue
                    fp = inp.get("file_path")
                    if isinstance(fp, str) and fp:
                        yield {"ts": rec.get("timestamp", ""), "tool": part["name"],
                               "file_path": fp, "input": inp, "src": str(p)}


def _edits(call):
    inp = call["input"]
    if call["tool"] == "MultiEdit":
        return [e for e in inp.get("edits") or [] if isinstance(e, dict)]
    return [inp]


def _apply(text, edit):
    old, new = edit.get("old_string"), edit.get("new_string")
    if not isinstance(old, str) or not isinstance(new, str) or not old or old not in text:
        return None
    return text.replace(old, new) if edit.get("replace_all") else text.replace(old, new, 1)


def rebuild(calls):
    """Rebuild one path from its calls (in order). Returns ``(text_or_None, status, info)``."""
    last_write = max((i for i, c in enumerate(calls) if c["tool"] == "Write"), default=None)
    if last_write is None:
        frags = [e for c in calls for e in _edits(c)]
        return None, "partial", {"reason": "edits without a Write", "edits": len(frags)}
    text = calls[last_write]["input"].get("content")
    if not isinstance(text, str):
        return None, "partial", {"reason": "Write without string content", "edits": 0}
    applied = failed = 0
    for c in calls[last_write + 1:]:
        for e in _edits(c):
            out = _apply(text, e)
            if out is None:
                failed += 1
            else:
                text, applied = out, applied + 1
    status = "complete" if failed == 0 else "partial"
    info = {"edits_applied": applied, "edits_failed": failed}
    if failed:
        info["reason"] = "an Edit after the last Write did not apply"
    return text, status, info


def in_git_tree(path: Path) -> bool:
    """True when ``path`` (existing or not) lies inside a git work tree."""
    p = path.resolve()
    for d in (p, *p.parents):
        if (d / ".git").exists():
            return True
    return False


def _slot(file_path: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(file_path.replace("\\", "/")).parent.name)[:40]
    return f"{hashlib.sha1(file_path.encode('utf-8')).hexdigest()[:8]}_{stem or 'root'}"


def dump(outdir: Path, substr: str, jsonl):
    if in_git_tree(outdir):
        raise SystemExit(f"refusing to dump into a git work tree: {outdir} (use a scratch folder)")
    by_path: dict[str, list] = {}
    for c in iter_calls(jsonl):
        if substr in c["file_path"]:
            by_path.setdefault(c["file_path"], []).append(c)
    outdir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for fp, calls in by_path.items():
        name = Path(fp.replace("\\", "/")).name or "file"
        folder = outdir / _slot(fp)
        folder.mkdir(parents=True, exist_ok=True)
        text, status, info = rebuild(calls)
        if text is not None:
            target = folder / (name if status == "complete" else name + ".partial")
            with open(target, "w", encoding="utf-8", newline="") as fh:
                fh.write(text)
        else:
            target = folder / (name + ".edits.json")
            frags = [{"ts": c["ts"], **{k: e.get(k) for k in ("old_string", "new_string", "replace_all")}}
                     for c in calls for e in _edits(c)]
            with open(target, "w", encoding="utf-8", newline="") as fh:
                json.dump(frags, fh, indent=2, ensure_ascii=False)
        manifest.append({"file_path": fp, "status": status, "output": str(target.relative_to(outdir)),
                         "calls": len(calls), "last_ts": calls[-1]["ts"], **info})
    with open(outdir / "MANIFEST.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
    return manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list", help="list Write/Edit calls")
    ls.add_argument("jsonl", nargs="+")
    dp = sub.add_parser("dump", help="rebuild matching files into OUTDIR")
    dp.add_argument("outdir")
    dp.add_argument("substr")
    dp.add_argument("jsonl", nargs="+")
    a = ap.parse_args(argv)
    if a.cmd == "list":
        for c in iter_calls(a.jsonl):
            print(f"{c['ts']}\t{c['tool']}\t{c['file_path']}")
        return 0
    m = dump(Path(a.outdir), a.substr, a.jsonl)
    for row in m:
        print(f"{row['status']}\t{row['output']}\t{row['file_path']}")
    return 0 if all(r["status"] == "complete" for r in m) else 2


if __name__ == "__main__":
    sys.exit(main())
