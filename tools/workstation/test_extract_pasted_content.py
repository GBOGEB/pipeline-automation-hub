"""Tests for extract_pasted_content.py. Run: python -m pytest -q tools/workstation/test_extract_pasted_content.py"""
import hashlib
import json

import extract_pasted_content as epc


def _write(tmp_path, records):
    p = tmp_path / "s.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return p


def _user(text, as_list=False):
    content = [{"type": "text", "text": text}] if as_list else text
    return {"type": "user", "message": {"content": content}}


def test_extracts_blocks_byte_exact_with_sums_and_duplicates(tmp_path):
    b1 = "## B1\n```mermaid\ngantt\n```\n  trailing spaces  "
    b2 = "B2 body\nline two"
    turn1 = f'A:\nnotes\n<pasted_content id="x">\n{b1}\n</pasted_content id="x">\nB2:\n<pasted_content id="x">\n{b2}\n</pasted_content id="x">'
    turn2 = f'<pasted_content id="y">\n{b2}\n</pasted_content id="y">'
    jsonl = _write(tmp_path, [_user(turn1), {"type": "assistant", "message": {"content": "hi"}}, _user(turn2, as_list=True), _user("no paste")])
    out = tmp_path / "out"
    written = epc.extract(jsonl, out)
    assert [n for _, n in written] == ["paste_01_01.md", "paste_01_02.md", "paste_02_01.md"]
    assert (out / "paste_01_01.md").read_bytes() == (b1 + "\n").encode()
    assert hashlib.sha256((out / "paste_02_01.md").read_bytes()).hexdigest() in (out / "SHA256SUMS").read_text()
    assert (out / "DUPLICATES.txt").read_text() == "paste_02_01.md is byte-identical to paste_01_02.md\n"


def test_no_blocks_exits_1(tmp_path):
    jsonl = _write(tmp_path, [_user("nothing pasted")])
    assert epc.main([str(jsonl), str(tmp_path / "o")]) == 1
    assert epc.main([]) == 2
