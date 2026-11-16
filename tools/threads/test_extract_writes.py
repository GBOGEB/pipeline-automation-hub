"""Offline tests for extract_writes.py over a synthetic transcript: no gh, no network."""
from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import extract_writes as xw  # noqa: E402


def _call(ts, name, inp):
    return {"timestamp": ts, "type": "assistant",
            "message": {"role": "assistant", "content": [
                {"type": "text", "text": "x"},
                {"type": "tool_use", "id": uuid.uuid4().hex, "name": name, "input": inp}]}}


A = "C:\\work\\a\\notes.md"
B = "/home/u/b/notes.md"
C = "/tmp/only_edited.py"
LINES = [
    json.dumps(_call("2026-11-01T10:00:00Z", "Write", {"file_path": A, "content": "one\r\ntwo\r\n"})),
    json.dumps({"type": "user", "message": {"role": "user", "content": "plain string content"}}),
    json.dumps(_call("2026-11-01T10:01:00Z", "Edit",
                     {"file_path": A, "old_string": "two", "new_string": "TWO"})),
    json.dumps(_call("2026-11-01T10:02:00Z", "Write", {"file_path": B, "content": "b first\n"})),
    json.dumps(_call("2026-11-01T10:03:00Z", "Write", {"file_path": B, "content": "b last\n"})),
    json.dumps(_call("2026-11-01T10:04:00Z", "Edit",
                     {"file_path": C, "old_string": "x = 1", "new_string": "x = 2"})),
    json.dumps(_call("2026-11-01T10:05:00Z", "Bash", {"command": "cat > f <<EOF"})),
    '{"timestamp": "2026-11-01T10:06:00Z", "message": {"content": [{"type": "tool_use", "name": "Wri',
]


class ExtractWrites(unittest.TestCase):
    def setUp(self):
        # Not TemporaryDirectory: owner-only temp folders break git and cleanup (AGENTS.md).
        self.tmp = Path(tempfile.gettempdir()) / f"xw_test_{uuid.uuid4().hex[:8]}"
        os.makedirs(self.tmp)
        self.jsonl = self.tmp / "s.jsonl"
        with open(self.jsonl, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(LINES))  # last line truncated, no trailing newline
        with open(self.jsonl, "ab") as fh:
            fh.write(b"\n\xff\xfe not utf-8\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_list_skips_truncated_and_undecodable_lines(self):
        calls = list(xw.iter_calls([self.jsonl]))
        self.assertEqual([(c["tool"], c["file_path"]) for c in calls],
                         [("Write", A), ("Edit", A), ("Write", B), ("Write", B), ("Edit", C)])
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(xw.main(["list", str(self.jsonl)]), 0)
        self.assertIn(f"2026-11-01T10:01:00Z\tEdit\t{A}", buf.getvalue())

    def test_dump_replays_edits_keeps_crlf_and_marks_edit_only_partial(self):
        out = self.tmp / "out"
        m = {r["file_path"]: r for r in xw.dump(out, "", [self.jsonl])}
        self.assertEqual(m[A]["status"], "complete")
        self.assertEqual(m[A]["edits_applied"], 1)
        with open(out / m[A]["output"], "rb") as fh:
            self.assertEqual(fh.read(), b"one\r\nTWO\r\n")
        self.assertEqual((out / m[B]["output"]).read_text(encoding="utf-8"), "b last\n")
        self.assertNotEqual(Path(m[A]["output"]).parent, Path(m[B]["output"]).parent)
        self.assertEqual(m[C]["status"], "partial")
        self.assertTrue(m[C]["output"].endswith("only_edited.py.edits.json"))
        frags = json.loads((out / m[C]["output"]).read_text(encoding="utf-8"))
        self.assertEqual(frags[0]["new_string"], "x = 2")
        self.assertEqual(len(json.loads((out / "MANIFEST.json").read_text(encoding="utf-8"))), 3)

    def test_failed_edit_marks_partial(self):
        text, status, info = xw.rebuild([
            {"tool": "Write", "input": {"content": "abc"}},
            {"tool": "MultiEdit", "input": {"edits": [{"old_string": "b", "new_string": "B"},
                                                      {"old_string": "zzz", "new_string": "y"}]}}])
        self.assertEqual((text, status, info["edits_failed"]), ("aBc", "partial", 1))

    def test_substr_filters_and_exit_code(self):
        out = self.tmp / "out2"
        with redirect_stdout(io.StringIO()):
            self.assertEqual(xw.main(["dump", str(out), "only_edited", str(self.jsonl)]), 2)
            self.assertEqual(xw.main(["dump", str(self.tmp / "out3"), "/b/", str(self.jsonl)]), 0)
        self.assertEqual(len(json.loads((out / "MANIFEST.json").read_text(encoding="utf-8"))), 1)

    def test_refuses_output_inside_a_git_tree(self):
        os.makedirs(self.tmp / "repo" / ".git")
        with self.assertRaises(SystemExit):
            xw.dump(self.tmp / "repo" / "rescue", "", [self.jsonl])
        self.assertFalse((self.tmp / "repo" / "rescue").exists())

    def test_errored_calls_are_dropped(self):
        j = self.tmp / "err.jsonl"
        w_ok = _call("2026-11-01T10:00:00Z", "Write", {"file_path": A, "content": "good"})
        w_bad = _call("2026-11-01T10:01:00Z", "Write", {"file_path": A, "content": "never"})
        e_bad = _call("2026-11-01T10:02:00Z", "Edit", {"file_path": A, "old_string": "good", "new_string": "bad"})
        res = lambda c: {"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": c["message"]["content"][1]["id"],
             "is_error": True, "content": "denied"}]}}
        with open(j, "w", encoding="utf-8") as fh:
            fh.write(chr(10).join(json.dumps(r) for r in (w_ok, w_bad, res(w_bad), e_bad, res(e_bad))))
        calls = list(xw.iter_calls([j]))
        self.assertEqual(len(calls), 1)
        self.assertEqual(xw.rebuild(calls)[:2], ("good", "complete"))

    def test_calls_merge_chronologically_across_files(self):
        old, new = self.tmp / "old.jsonl", self.tmp / "new.jsonl"
        old.write_text(json.dumps(_call("2026-11-01T09:00:00Z", "Write", {"file_path": A, "content": "stale"})),
                       encoding="utf-8")
        new.write_text(json.dumps(_call("2026-11-02T09:00:00Z", "Write", {"file_path": A, "content": "fresh"})),
                       encoding="utf-8")
        for order in ([old, new], [new, old]):
            self.assertEqual(xw.rebuild(list(xw.iter_calls(order)))[0], "fresh")


if __name__ == "__main__":
    unittest.main()
