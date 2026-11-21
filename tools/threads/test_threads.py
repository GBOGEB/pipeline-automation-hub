"""Offline tests for the thread tools: no gh, no network."""
from __future__ import annotations

import ast
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import _common as c  # noqa: E402
import check_presence  # noqa: E402
import parked_intents  # noqa: E402
import thread_wire  # noqa: E402
import wake_check  # noqa: E402

ITEM = {"id": "U99", "repo": "pipeline-automation-hub", "title": "t", "intent": "i", "done_when": "d",
        "sessions": [["Source", "local_abcdef12-0000-0000-0000-000000000000"]],
        "wake": {"paths": ["mission-control/x/"], "keywords": ["sigma"], "refs": ["#5", "CODEX#7"]}}


class ParkedMarker(unittest.TestCase):
    def test_body_round_trips_through_the_triway_owner(self):
        b = parked_intents.body(ITEM, "_pulse/x.md", "2026-11-10")
        meta = c.triway.parked_intent_meta(b)
        self.assertEqual(meta["id"], "U99")
        self.assertEqual(meta["wake"], ITEM["wake"])
        self.assertEqual(meta["sessions"], [ITEM["sessions"][0][1]])
        self.assertEqual(c.triway.parked_intent(b), {"marker": "parked-intent:v1", "valid": True, "id": "U99"})

    def test_malformed_marker(self):
        bad = "<!-- parked-intent:v1 {bad} -->"
        self.assertIsNone(c.triway.parked_intent_meta(bad))
        self.assertFalse(c.triway.parked_intent(bad)["valid"])
        self.assertIsNone(c.triway.parked_intent("no marker"))
        self.assertIsNone(c.triway.parked_intent_meta("<!-- parked-intent:v1 [1] -->"))

    def test_comment_dedup_does_not_confuse_prefix_ids(self):
        posted = ["**Parked intent U23**, update", "Parked intent U12b here"]
        self.assertTrue(parked_intents.already_commented(posted, "U23"))
        self.assertFalse(parked_intents.already_commented(posted, "U2"))
        self.assertTrue(parked_intents.already_commented(posted, "U12b"))
        self.assertFalse(parked_intents.already_commented(posted, "U12"))

    def test_gh_env_drops_tokens(self):
        import os
        os.environ["GH_TOKEN"] = "x"
        try:
            self.assertNotIn("GH_TOKEN", c.gh_env())
        finally:
            del os.environ["GH_TOKEN"]


class WakeMatch(unittest.TestCase):
    item = {**ITEM, "number": 1}
    since = "2026-11-09T00:00:00Z"

    def run_match(self, prs, updated=None, comments=0):
        return wake_check.match(self.item, {"pipeline-automation-hub": prs}, self.since,
                                updated=lambda r, n, s: (updated or {}).get((r, n)),
                                comments=lambda r, n, s: comments)

    def test_path_is_strong_keyword_is_weak(self):
        prs = [{"number": 2, "title": "Add sigma", "files": [{"path": "mission-control/x/a.py"}],
                "url": "u2", "updatedAt": "2026-11-09T10:00:00Z", "state": "OPEN"},
               {"number": 3, "title": "sigma table", "files": [], "url": "u3",
                "updatedAt": "2026-11-09T10:00:00Z", "state": "MERGED"}]
        hits = self.run_match(prs)
        self.assertEqual([h["strength"] for h in hits], ["strong", "weak"])
        self.assertIn("changes 1 file(s)", hits[0]["text"])

    def test_old_prs_and_the_issue_itself_are_ignored(self):
        prs = [{"number": 1, "title": "sigma", "files": [], "url": "u", "updatedAt": "2026-11-09T10:00:00Z", "state": "OPEN"},
               {"number": 4, "title": "sigma", "files": [], "url": "u", "updatedAt": "2026-11-01T00:00:00Z", "state": "OPEN"}]
        self.assertEqual(self.run_match(prs), [])

    def test_refs_and_comments(self):
        hits = self.run_match([], updated={("CODEX", 7): "https://x/7"}, comments=2)
        texts = [h["text"] for h in hits]
        self.assertIn("CODEX#7 was updated: https://x/7", texts)
        self.assertIn("2 new comment(s) on the parked issue itself", texts)

    def test_split_ref(self):
        self.assertEqual(wake_check.split_ref("#5", "hub"), ("hub", 5))
        self.assertEqual(wake_check.split_ref("CODEX#7", "hub"), ("CODEX", 7))
        self.assertEqual(wake_check.split_ref("1171", "hub"), ("hub", 1171))
        self.assertEqual(wake_check.split_ref(1135, "hub"), ("hub", 1135))
        for bad in ("CODEX 7", "", "#", True, None):
            with self.assertRaises(ValueError):
                wake_check.split_ref(bad, "hub")

    def test_bad_refs_are_skipped_not_fatal(self):
        good, bad = wake_check.parse_refs(["#5", 7, "nope", "CODEX#2"], "hub")
        self.assertEqual(good, {("hub", 5), ("hub", 7), ("CODEX", 2)})
        self.assertEqual(bad, ["nope"])

    def test_filer_refuses_unparseable_refs(self):
        spec = {"items": [{"id": "U1", "repo": "hub", "wake": {"refs": ["#1", "1171"]}},
                          {"id": "U2", "repo": "hub", "wake": {"refs": ["see 12"]}}]}
        self.assertEqual(parked_intents.bad_refs(spec), ["U2: 'see 12'"])

    def test_int_and_bare_refs_render_canonically(self):
        item = {"id": "U9", "repo": "hub", "title": "t", "intent": "i", "done_when": "d",
                "sessions": [["s", "local_x"]], "wake": {"refs": [1135, "1171", "#5", "CODEX#7", "hub#8"]}}
        text = parked_intents.body(item, "map.md", "2026-11-11")
        self.assertIn("- references: #1135, #1171, #5, CODEX#7, #8", text)
        self.assertIn('"refs":["#1135","#1171","#5","CODEX#7","#8"]', text)
        self.assertEqual(item["wake"]["refs"][0], 1135)

    def test_unread_repos_are_reported(self):
        lines = wake_check.report([self.item], [{**self.item, "hits": [], "strong": 0}], ["CODEX: boom"], "s", "n")
        self.assertIn("- CODEX: boom", lines)
        self.assertIn("No parked intent matched new activity.", lines)


class Presence(unittest.TestCase):
    def test_tally_counts_the_newest_run_per_check(self):
        runs = {"a": [{"name": "test", "app": 15368, "c": "success"}, {"name": "test", "app": 15368, "c": "failure"},
                      {"name": "CodeQL", "app": 57789, "c": "neutral"}],
                "b": [{"name": "test", "app": 15368, "c": "failure"}]}
        prs = [{"headRefOid": "a"}, {"headRefOid": "b"}]
        t = check_presence.tally(prs, lambda sha: runs[sha])
        self.assertEqual(t["test\t15368"], {"present": 2, "success": 1, "app": 15368})
        self.assertEqual(t["CodeQL\t57789"]["present"], 1)
        self.assertEqual(check_presence.candidates({"prs": 2, "checks": t}), ["test\t15368"])
        self.assertEqual(check_presence.candidates({"prs": 0, "checks": {}}), [])


class Wire(unittest.TestCase):
    def test_map_from_fixture(self):
        sessions = [
            {"sessionId": "local_aaaaaaaa-1", "title": "Parent", "isArchived": False, "isRunning": False,
             "lastActivityAt": "2026-11-10T00:00:00Z"},
            {"sessionId": "local_bbbbbbbb-2", "title": "Child", "isArchived": True, "isRunning": False,
             "lastActivityAt": "2026-11-09T00:00:00Z", "startedBy": "local_aaaaaaaa-1", "prNumber": 9, "prState": "MERGED"},
            {"sessionId": "local_cccccccc-3", "title": "W123 alone", "isArchived": False, "isRunning": True,
             "lastActivityAt": "2026-11-08T00:00:00Z"}]
        wire = [{"id": "local_aaaaaaaa-1", "verdict": "RESUME", "repo": "CODEX", "intent": "x", "current": "y",
                 "next": "z", "todo": ["a"], "waiting_on_user": {"value": True, "what": "ok?"}}]
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "2026-11-10" / "wire"
            src.mkdir(parents=True)
            (src / "sessions.json").write_text(json.dumps(sessions), encoding="utf-8")
            (src / "wire_a.json").write_text(json.dumps(wire), encoding="utf-8")
            self.assertEqual(thread_wire.main([str(src)]), 0)
            md = (src.parent / "THREAD_MAP.md").read_text(encoding="utf-8")
        self.assertIn("# Thread wireframe, 2026-11-10", md)
        self.assertIn("3 threads: 2 live, 1 archived; 1 wireframed", md)
        self.assertIn("### RESUME · Parent", md)
        self.assertIn("**Waiting on you:** ok?", md)
        self.assertIn("  - [A] **-** Child `bbbbbbbb` · ? · #9 MERGED", md)
        self.assertIn("W123 alone", md)
        self.assertIn("· numbered", md)


class Hygiene(unittest.TestCase):
    def test_no_personal_paths_or_addresses_in_tools(self):
        import re
        for f in HERE.glob("*.py"):
            if f.name.startswith("test_"):
                continue
            text = f.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"[A-Za-z]:[\\/]+Users[\\/]", text), f.name)
            self.assertIsNone(re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text), f.name)

    def test_sources_parse_on_the_running_interpreter(self):
        for f in HERE.glob("*.py"):
            ast.parse(f.read_text(encoding="utf-8"), filename=str(f))


if __name__ == "__main__":
    unittest.main()
