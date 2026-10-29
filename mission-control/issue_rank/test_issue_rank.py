"""Contract tests for issue_rank on synthetic snapshots (no network, no private data)."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import issue_rank as ir  # noqa: E402

HUB, QPS = "GBOGEB/pipeline-automation-hub", "GBOGEB/cryoplant-project"


def issue(repo, n, body="", created="2026-10-01T00:00:00Z", updated=None, title=None, labels=()):
    return {"repo": repo, "number": n, "type": "Issue", "title": title or f"issue {n}",
            "url": f"https://github.com/{repo}/issues/{n}", "created_at": created,
            "updated_at": updated or created, "labels": list(labels), "assignees": [],
            "body": body, "comments": [], "refs_in": []}


def pr(repo, n, closes=(), checks="SUCCESS", draft=False, review=None, created="2026-10-20T00:00:00Z"):
    return {"repo": repo, "number": n, "type": "PullRequest", "title": f"pr {n}",
            "url": f"https://github.com/{repo}/pull/{n}", "created_at": created, "updated_at": created,
            "draft": draft, "review_decision": review, "labels": [], "checks": checks, "body": "",
            "closes": [{"repo": r, "number": x} for r, x in closes]}


def snapshot(hub_items=(), qps_items=(), refs=None):
    def split(items):
        return ([i for i in items if i["type"] == "Issue"], [i for i in items if i["type"] == "PullRequest"])
    hi, hp = split(hub_items)
    qi, qp = split(qps_items)
    return {"schema": ir.SNAPSHOT_SCHEMA, "owner": "GBOGEB", "fetched_at": "2026-10-26T00:00:00Z",
            "refs": refs or {},
            "repos": {HUB: {"private": False, "default_branch": "master", "head_sha": "a" * 40,
                            "issues": hi, "prs": hp},
                      QPS: {"private": True, "default_branch": "main", "head_sha": "b" * 40,
                            "issues": qi, "prs": qp}}}


class Checklist(unittest.TestCase):
    BODY = """## Purpose
Ship it.
## Definition of Done
- [x] tests green
- [ ] reviewed
## DoV
- [X] exact-head run
## Steps
1. [ ] write code
- [~] dropped item
- [ ] DoD: inline label wins
```
- [ ] inside code fence
```
"""

    def test_sections_and_counts(self):
        cl = ir.parse_checklist(self.BODY)
        self.assertEqual((cl["done"], cl["total"]), (2, 5))
        self.assertEqual(cl["sections"]["DOD"], {"done": 1, "total": 3, "untracked": 0})
        self.assertEqual(cl["sections"]["DOV"]["done"], 1)
        self.assertEqual(cl["sections"]["STEPS"]["total"], 1)
        self.assertEqual(cl["state"], "IN_PROGRESS")
        self.assertTrue(cl["dod_declared"] and cl["dov_declared"])
        self.assertEqual(cl["next_open"], "reviewed")
        self.assertEqual(ir.progress_text(cl), "2/5 (DOV 1/1, DOD 1/3, STEPS 0/1)")

    def test_states(self):
        self.assertEqual(ir.parse_checklist("")["state"], "NO_CHECKLIST")
        self.assertEqual(ir.parse_checklist("- [ ] a\n- [ ] b")["state"], "NOT_STARTED")
        self.assertEqual(ir.parse_checklist("- [x] a\n- [x] b")["state"], "ALL_TICKED")

    def test_plain_bullets_under_dod_are_untracked_never_done(self):
        cl = ir.parse_checklist("## Done when\n- CI green\n- owner signs\n## Notes\n- not a criterion")
        self.assertEqual(cl["state"], "UNTRACKED_CRITERIA")
        self.assertEqual((cl["done"], cl["total"], cl["untracked"]), (0, 0, 2))
        self.assertTrue(cl["dod_declared"])
        self.assertEqual(cl["next_open"], "CI green")
        self.assertEqual(ir.progress_text(cl), "2 criteria, none tickable")


class Refs(unittest.TestCase):
    def refs(self, text, home=HUB):
        return [(r["repo"], r["number"], r["kind"]) for r in ir.extract_refs(text, home)]

    def test_forms_and_foreign_owner(self):
        got = self.refs("see #5, GBOGEB/ABACUS#7, https://github.com/GBOGEB/CODEX/pull/9 and other/x#1")
        self.assertEqual(sorted(got), [("GBOGEB/ABACUS", 7, "MENTION"), ("GBOGEB/CODEX", 9, "MENTION"),
                                       (HUB, 5, "MENTION")])
        with self.assertRaises(ValueError):  # triway reads GBOGEB references only
            ir.extract_refs("#1", "other/x", owner="other")

    def test_typed_keywords(self):
        self.assertEqual(self.refs("Blocked by #3")[0][2], "DEPENDS_ON")
        self.assertEqual(self.refs("This blocks #4")[0][2], "BLOCKS")
        self.assertEqual(self.refs("Closes #5")[0][2], "MENTION")  # a closing claim needs a PR body
        self.assertEqual(ir.extract_refs("Closes #5", HUB, pr=True)[0]["kind"], "CLOSES")
        self.assertEqual(self.refs("Superseded by #8"), [(HUB, 8, "SUPERSEDED_BY")])
        self.assertEqual(self.refs("Parent: #6")[0][2], "PARENT")
        self.assertEqual(self.refs("Supersedes #7")[0][2], "SUPERSEDES")

    def test_keyword_binds_to_next_ref_only(self):
        self.assertEqual(self.refs("blocked by #3, see #4"), [(HUB, 3, "DEPENDS_ON"), (HUB, 4, "MENTION")])

    def test_negation_and_alias(self):
        self.assertEqual(self.refs("lane (not part of #1857 hotfix)")[0][2], "MENTION")
        self.assertEqual(self.refs("Related: QPS parent #1920", home="GBOGEB/ABACUS"),
                         [(QPS, 1920, "PARENT")])
        self.assertEqual(self.refs("ABACUS PR #2470")[0][:2], ("GBOGEB/ABACUS", 2470))

    def test_checklist_ref_is_child_with_tick(self):
        r = ir.extract_refs("- [x] #11 done\n- [ ] #12 open", HUB)
        self.assertEqual([(x["number"], x["kind"], x["ticked"]) for x in r], [(11, "CHILD", True), (12, "CHILD", False)])

    def test_dropped_checklist_ref_is_not_a_child(self):
        r = ir.extract_refs("- [~] #13 obsolete\n- [-] #14", HUB)
        self.assertEqual([(x["number"], x["kind"], x["ticked"]) for x in r], [(13, "MENTION", None), (14, "MENTION", None)])
        r = ir.extract_refs("- [~] depends on #15\n- [-] closes #16\n- [~] blocks #17", HUB)
        self.assertEqual([(x["number"], x["kind"]) for x in r], [(15, "MENTION"), (16, "MENTION"), (17, "MENTION")])
        r = ir.extract_refs("- [ ] ~~depends on #19~~\n- [~] superseded by #18", HUB)
        self.assertEqual([(x["number"], x["kind"]) for x in r], [(18, "MENTION"), (19, "MENTION")])
        self.assertEqual(ir.extract_refs("- [-] closes #16", HUB, pr=True)[0]["kind"], "MENTION")
        g = ir.build_graph(snapshot([issue(HUB, 1, "- [~] depends on #2"), issue(HUB, 2)]))
        self.assertEqual({e["kind"] for e in g["edges"]}, {"MENTION"})  # no blocker, no pressure

    def test_code_is_ignored(self):
        self.assertEqual(self.refs("`#99` and\n```\n#98\n```"), [])


class Graph(unittest.TestCase):
    def test_missing_refs_dropped_and_blocks_reversed(self):
        snap = snapshot([issue(HUB, 1, "blocks #2\nsee #77"), issue(HUB, 2)], refs={f"{HUB}#77": None})
        g = ir.build_graph(snap)
        self.assertNotIn(f"{HUB}#77", g["nodes"])
        self.assertEqual([(e["source"], e["target"], e["kind"]) for e in g["edges"]],
                         [(f"{HUB}#2", f"{HUB}#1", "DEPENDS_ON")])

    def test_superseded_by_is_stored_reversed(self):
        g = ir.build_graph(snapshot([issue(HUB, 1, "Superseded by #2"), issue(HUB, 2)]))
        self.assertEqual([(e["source"], e["target"], e["kind"]) for e in g["edges"]],
                         [(HUB + "#2", HUB + "#1", "SUPERSEDES")])

    def test_unblock_pressure_is_transitive_and_open_only(self):
        snap = snapshot([issue(HUB, 1), issue(HUB, 2, "depends on #1"), issue(HUB, 3, "depends on #2"),
                         issue(HUB, 4, "depends on #9")],
                        refs={f"{HUB}#9": {"type": "Issue", "state": "CLOSED", "created_at": None}})
        g = ir.build_graph(snap)
        p = ir.unblock_pressure(g["nodes"], g["edges"])
        self.assertEqual((p[f"{HUB}#1"], p[f"{HUB}#2"], p[f"{HUB}#3"]), (2, 1, 0))
        self.assertEqual(ir.open_blockers(g["nodes"], g["edges"]).get(f"{HUB}#4"), None)

    def test_unknown_blocker_state_fails_closed(self):
        g = ir.build_graph(snapshot([issue(HUB, 4, "depends on #9")]))
        self.assertEqual(ir.open_blockers(g["nodes"], g["edges"])[f"{HUB}#4"], [f"{HUB}#9"])

    def test_pagerank_and_betweenness(self):
        edges = [{"source": "a", "target": "b", "kind": "MENTION"}, {"source": "c", "target": "b", "kind": "MENTION"},
                 {"source": "b", "target": "d", "kind": "DEPENDS_ON"}]
        pr = ir.pagerank(["a", "b", "c", "d"], edges)
        self.assertAlmostEqual(sum(pr.values()), 1.0, places=9)
        self.assertGreater(pr["b"], pr["a"])
        bc = ir.betweenness(["a", "b", "c"], [{"source": "a", "target": "b", "kind": "X"},
                                              {"source": "b", "target": "c", "kind": "X"}])
        self.assertEqual((bc["a"], bc["b"], bc["c"]), (0.0, 1.0, 0.0))

    def test_golden_thread_and_mycelium(self):
        snap = snapshot([issue(HUB, 1, created="2026-09-01T00:00:00Z"),
                         issue(HUB, 2, "follow-up of #1", created="2026-09-10T00:00:00Z"),
                         issue(HUB, 3, "see #2 and #1", created="2026-10-01T00:00:00Z")])
        g = ir.build_graph(snap)
        t = ir.lineages(g["nodes"], g["edges"])
        self.assertEqual(t[f"{HUB}#3"], [f"{HUB}#1", f"{HUB}#3"])  # oldest older ref first
        self.assertEqual(t[f"{HUB}#2"], [f"{HUB}#1", f"{HUB}#2"])
        m = ir.mycelium(g["nodes"], g["edges"])
        self.assertEqual(m[f"{HUB}#3"]["hyphae"], [f"{HUB}#1", f"{HUB}#2"])
        self.assertEqual(m[f"{HUB}#1"]["reach1"], 2)


def fixture():
    return snapshot(
        [issue(HUB, 1, "## DoD\n- [x] a\n- [x] b", created="2026-09-01T00:00:00Z", labels=["P1"]),
         issue(HUB, 2, "## Steps\n- [x] a\n- [ ] b\n- [ ] c\n\nblocked by #3", created="2026-09-05T00:00:00Z"),
         issue(HUB, 3, "", created="2026-09-06T00:00:00Z"),
         issue(HUB, 4, "depends on #3", created="2026-09-07T00:00:00Z"),
         issue(HUB, 5, "## DoD\n- [x] a\n- [x] b\n- [x] c\n- [ ] d", created="2026-09-08T00:00:00Z"),
         pr(HUB, 10, closes=[(HUB, 5)], checks="FAILURE"),
         pr(HUB, 11, checks="SUCCESS", review="APPROVED")],
        [issue(QPS, 7, "## DoV\n- [ ] secret criterion", title="confidential bidder title")])


class Rank(unittest.TestCase):
    def setUp(self):
        self.m = ir.rank(fixture())
        self.by = {i["key"]: i for i in self.m["items"]}

    def test_lanes(self):
        lane = {k.split("/")[1]: v["lane"] for k, v in self.by.items()}
        self.assertEqual(lane["pipeline-automation-hub#1"], "CLOSE_CANDIDATE")
        self.assertEqual(lane["pipeline-automation-hub#2"], "BLOCKED")
        self.assertEqual(lane["pipeline-automation-hub#3"], "BOTTLENECK")
        self.assertEqual(lane["pipeline-automation-hub#5"], "FIX_RED")
        self.assertEqual(lane["pipeline-automation-hub#10"], "FIX_RED")
        self.assertEqual(lane["pipeline-automation-hub#11"], "MERGE_READY")
        self.assertEqual(lane["cryoplant-project#7"], "NOT_STARTED")

    def test_approved_pr_with_pending_checks_is_not_merge_ready(self):
        for checks in ("PENDING", "EXPECTED", None):
            with self.subTest(checks=checks):
                m = ir.rank(snapshot([pr(HUB, 20, checks=checks, review="APPROVED")]))
                self.assertEqual(m["items"][0]["lane"], "AWAIT_CHECKS")

    def test_scores_ranks_and_authority(self):
        self.assertEqual([i["rank_global"] for i in self.m["items"]], list(range(1, len(self.m["items"]) + 1)))
        self.assertEqual(self.by[f"{HUB}#3"]["pressure"], 2)
        self.assertEqual(self.by[f"{HUB}#1"]["urgency_parts"]["nearness"], 1.0)
        for i in self.m["items"]:  # score = own urgency + pressure inherited from waiters, exactly
            self.assertAlmostEqual(i["score"], i["score_parts"]["own"] + i["score_parts"]["inherited"], places=3)
        a = self.m["authority"]
        self.assertTrue(a["advisory_only"])
        self.assertFalse(a["closure_authorized"] or a["merge_authorized"] or a["dispatch_authorized"])

    def test_rollups(self):
        r = self.m["rollups"]
        self.assertEqual(set(r), {"USER", "JADE", "FOCUS4", HUB, QPS})
        self.assertEqual(r[HUB]["open_issues"], 5)
        self.assertEqual((r[HUB]["tasks_done"], r[HUB]["tasks_total"]), (6, 9))
        self.assertEqual(r["USER"]["open_issues"], 6)
        self.assertIn(f"{HUB}#3", r[HUB]["bottlenecks"])
        self.assertIn(f"{HUB}#1", r[HUB]["nearly_finished"])
        self.assertEqual(self.m["heads"][HUB]["head_sha"], "a" * 40)

    def test_views(self):
        v = self.m["views"]
        self.assertEqual(v["bottom_up"][0], f"{HUB}#1")
        self.assertEqual(v["top_down"][:2], [f"{HUB}#11", f"{HUB}#10"])  # same day: higher number newer
        self.assertEqual(sorted(v["graph"]), sorted(self.by))

    def test_redact_hides_private_text(self):
        red = ir.redact(self.m)
        self.assertFalse(any(i["repo"] == QPS for i in red["items"]))
        self.assertEqual(red["rollups"][QPS]["by_assignee"], [])
        self.assertIn(QPS, red["privacy_projection"]["validated_then_redacted_heads"])
        self.assertNotIn(f"{QPS}#7", json.dumps(red))
        self.assertIsNone(red["heads"][QPS]["head_sha"])
        self.assertNotIn("secret", json.dumps(red))
        self.assertNotIn("confidential", ir.render_html(red))

    def test_outputs_html_csv(self):
        page = ir.render_html(self.m, {"baseline": True})
        for s in ("Bottom-up", "Top-down", "PageRank", "Scopes", "advisory only"):
            self.assertIn(s, page)
        self.assertEqual(ir.to_csv(self.m).splitlines()[0].split(",")[:3], ["rank_global", "rank_repo", "key"])


class Telemetry(unittest.TestCase):
    def test_diff_reports_moves(self):
        before = ir.rank(fixture())
        snap = fixture()
        snap["repos"][HUB]["issues"][1]["body"] = "## Steps\n- [x] a\n- [x] b\n- [ ] c\n\nblocked by #3\nsee #4"
        snap["repos"][HUB]["issues"].append(issue(HUB, 6, created="2026-10-25T00:00:00Z"))
        d = ir.diff(before, ir.rank(snap))
        self.assertEqual(d["new_items"], [f"{HUB}#6"])
        self.assertIn([f"{HUB}#2", f"{HUB}#4", "MENTION"], d["new_links"])
        self.assertEqual(d["checklist_moves"], [{"key": f"{HUB}#2", "from": "1/3", "to": "2/3"}])
        self.assertTrue(ir.diff(None, before)["baseline"])

    def test_ledger_chain_and_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.jsonl"
            ir.append_ledger(path, {"x": 1})
            ir.append_ledger(path, {"x": 2})
            self.assertEqual(ir.verify_ledger(path), 2)
            path.write_text(path.read_text(encoding="utf-8").replace('"x": 2', '"x": 3'), encoding="utf-8")
            with self.assertRaises(ValueError):
                ir.verify_ledger(path)



    def test_taxonomy_pulse_output_is_hashed_by_existing_single_writer(self):
        current = ir.rank(fixture())
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            hashes = ir.write_outputs(out, current, {"baseline": True},
                                      parser_sha="c" * 40)
            self.assertIn("taxonomy_pulse.json", hashes)
            self.assertIn("taxonomy_pulse.csv", hashes)
            pulse = json.loads((out / "taxonomy_pulse.json").read_text(encoding="utf-8"))
            self.assertEqual(pulse["schema"], "jade.taxonomy-pulse.v1")
            self.assertEqual(pulse["parser_sha"], "c" * 40)
            self.assertEqual(pulse["population"]["total"], 7)
            self.assertNotIn(QPS, pulse["source_heads"])
            self.assertNotIn(QPS, pulse["rollups"])
            self.assertEqual(len(pulse["history_points"]), 1)
            self.assertEqual(pulse["history_points"][0]["wave"], "N0")
            self.assertIn("N0", (out / "taxonomy_pulse.csv").read_text())

    def test_two_pulses_share_existing_ledger_and_do_not_claim_closed(self):
        old = ir.rank(fixture())
        newer_snapshot = fixture()
        newer_snapshot["fetched_at"] = "2026-10-27T00:00:00Z"
        newer_snapshot["repos"][HUB]["issues"][0]["title"] = "fix(watch): census fails closed"
        now = ir.rank(newer_snapshot)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            hashes = ir.write_outputs(out, now, ir.diff(old, now),
                                      previous_model=old, parser_sha="c" * 40,
                                      previous_parser_sha="c" * 40)
            pulse = json.loads((out / "taxonomy_pulse.json").read_text())
            self.assertEqual([p["wave"] for p in pulse["history_points"]], ["N", "N+1"])
            self.assertTrue(pulse["delta"]["comparable"])
            self.assertTrue(pulse["delta"]["parser_identity_comparable"])
            self.assertIsNone(pulse["delta"]["verified_closed"])
            self.assertEqual(pulse["formal_credit_delta"], 0)
            csv_data = (out / "taxonomy_pulse.csv").read_text()
            self.assertIn(",N,", csv_data)
            self.assertIn(",N+1,", csv_data)
            ledger = out / "ledger.jsonl"
            row = ir.append_ledger(ledger, {"outputs": hashes})
            self.assertEqual(row["outputs"]["taxonomy_pulse.json"], hashes["taxonomy_pulse.json"])
            self.assertEqual(ir.verify_ledger(ledger), 1)


class FakeGh:
    """Serves canned GraphQL pages keyed by the query's root field."""

    def __init__(self):
        self.calls = 0

    def __call__(self, query, allow_not_found=False, **v):
        self.calls += 1
        if "defaultBranchRef" in query:
            return {"repository": {"nameWithOwner": f"GBOGEB/{v['name']}", "isPrivate": False,
                                   "defaultBranchRef": {"name": "main", "target": {"oid": "c" * 40}}}}
        if "issues(states:OPEN,first" in query:
            page = 1 if v.get("cursor") else 0
            node = {"number": 1 + page, "title": "t", "url": "u", "createdAt": "2026-10-01T00:00:00Z",
                    "updatedAt": "2026-10-02T00:00:00Z", "body": "see #50", "author": {"login": "x"},
                    "labels": {"nodes": []}, "assignees": {"nodes": []}, "milestone": None,
                    "comments": {"totalCount": 0, "nodes": []},
                    "timelineItems": {"nodes": [{"__typename": "CrossReferencedEvent", "willCloseTarget": True,
                                                 "source": {"__typename": "PullRequest", "number": 9,
                                                            "state": "OPEN", "isDraft": False,
                                                            "createdAt": "2026-10-03T00:00:00Z",
                                                            "repository": {"nameWithOwner": "GBOGEB/r"}}}]}}
            return {"repository": {"issues": {"pageInfo": {"hasNextPage": not page, "endCursor": "c1"},
                                              "nodes": [node]}}}
        if "issues(states:CLOSED,first" in query:
            return {"repository": {"issues": {"pageInfo": {"hasNextPage": False, "endCursor": None},
                                              "nodes": []}}}
        if "pullRequests(states:OPEN" in query:
            return {"repository": {"pullRequests": {"pageInfo": {"hasNextPage": False, "endCursor": None},
                                                    "nodes": []}}}
        assert allow_not_found  # stub resolution
        return {"r0": {"n50": None, "n9": {"__typename": "PullRequest", "state": "OPEN",
                                           "createdAt": "2026-10-03T00:00:00Z", "isDraft": False}}}


class Fetch(unittest.TestCase):
    def test_fetch_pages_and_resolves(self):
        snap = ir.fetch(FakeGh(), ["r"])
        r = snap["repos"]["GBOGEB/r"]
        self.assertEqual([i["number"] for i in r["issues"]], [1, 2])
        self.assertEqual(r["head_sha"], "c" * 40)
        self.assertIsNone(snap["refs"]["GBOGEB/r#50"])
        m = ir.rank(snap)
        self.assertEqual(m["items"][0]["linked_prs"][0]["pr"], "GBOGEB/r#9")
        self.assertNotIn("GBOGEB/r#50", {e["target"] for e in m["edges"]})

    def test_redacted_run_persists_no_raw_snapshot(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(ir, "Gh", FakeGh), \
                contextlib.redirect_stdout(io.StringIO()):
            out = Path(d) / "focus"
            out.mkdir()
            (out / "snapshot.json").write_text("{\"stale\": \"raw private body\"}", encoding="utf-8")
            self.assertEqual(ir.main(["run", "--repos", "r", "--out", d, "--redact-private", "--draws", "5"]), 0)
            self.assertFalse((out / "snapshot.json").exists())
            self.assertTrue((out / "issue_rank.json").exists())
            self.assertEqual(ir.verify_ledger(out / "ledger.jsonl"), 1)
            # A plain run persists its snapshot. Own scope directory: a second pulse in the
            # same directory within the same second fails the taxonomy series' strict order.
            ir.main(["run", "--scope", "user", "--repos", "r", "--out", d, "--draws", "5"])
            self.assertTrue((Path(d) / "user" / "snapshot.json").exists())


if __name__ == "__main__":
    unittest.main()
