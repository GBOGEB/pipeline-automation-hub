#!/usr/bin/env python3
"""Extract every <pasted_content> block from a Claude Code session transcript, byte-exact (stdlib only).

Handovers pasted into a chat from other tools live only in that session's JSONL transcript
(`~/.claude/projects/<project>/<cliSessionId>.jsonl`). Deleting the session loses them. This writes each block
to `<out>/paste_<turn>_<n>.md`, a `SHA256SUMS` file and a `DUPLICATES.txt` report of identical blocks.
On 2026-11-08, that report showed a "lossless" handover (B3) to be byte-identical to an earlier paste (B2),
so it had dropped a third paste (B1) entirely.

Usage:
  python extract_pasted_content.py <session.jsonl> <out_dir>
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Iterator, List, Tuple

_BLOCK = re.compile(r"<pasted_content[^>]*>\n?(.*?)\n?</pasted_content[^>]*>", re.S)


def _text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def iter_blocks(jsonl: Path) -> Iterator[Tuple[int, int, str]]:
    """(user_turn, block_index, text) for every pasted block, in transcript order. Turns count from 1."""
    turn = 0
    for line in jsonl.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("type") != "user":
            continue
        text = _text(rec.get("message", {}).get("content"))
        blocks = _BLOCK.findall(text)
        if not blocks:
            continue
        turn += 1
        for n, b in enumerate(blocks, 1):
            yield turn, n, b


def extract(jsonl: Path, out: Path) -> List[Tuple[str, str]]:
    out.mkdir(parents=True, exist_ok=True)
    written: List[Tuple[str, str]] = []
    for turn, n, body in iter_blocks(jsonl):
        name = f"paste_{turn:02d}_{n:02d}.md"
        data = (body + "\n").encode("utf-8")
        (out / name).write_bytes(data)
        written.append((hashlib.sha256(data).hexdigest(), name))
    (out / "SHA256SUMS").write_text("".join(f"{h}  {n}\n" for h, n in written), encoding="utf-8", newline="\n")
    seen: dict = {}
    dups = []
    for h, n in written:
        if h in seen:
            dups.append(f"{n} is byte-identical to {seen[h]}")
        else:
            seen[h] = n
    (out / "DUPLICATES.txt").write_text("\n".join(dups) + ("\n" if dups else ""), encoding="utf-8", newline="\n")
    return written


def main(argv: List[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    written = extract(Path(argv[0]), Path(argv[1]))
    for h, n in written:
        print(f"{h[:12]}  {n}")
    dup_text = (Path(argv[1]) / "DUPLICATES.txt").read_text(encoding="utf-8").strip()
    print(f"{len(written)} block(s) written to {argv[1]}" + (f"\n{dup_text}" if dup_text else ""))
    return 0 if written else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
