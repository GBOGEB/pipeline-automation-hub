"""Method v2 contract tests: pressure walk, unknown-not-zero urgency, structure, flow, privacy.

Synthetic snapshots only (no network, no private data).
"""
from __future__ import annotations

import contextlib
import io
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import issue_rank as ir  # noqa: E402
from test_issue_rank import HUB, QPS, fixture, issue, pr, snapshot, FakeGh  # noqa: E402

IM = ir.IM


def k(n, repo=HUB):
    return f"{repo}#{n}"


def by_key(model):
    return {i["key"]: i for i in model["items"]}


class Math(unittest.TestCase):
    def test_scc_and_chains(self):
        succ = {"a": ["b"], "b": ["c"], "c": [], "x": ["y"], "y": ["x"]}
        comps = IM.strongly_connected(sorted(succ), succ)
        self.assertIn(["x", "y"], comps)
        ch = IM.blocker_chains(sorted(succ), succ)
        self.assertEqual((ch["below"]["a"], ch["below"]["b"], ch["below"]["c"]), (2, 1, 0))
        self.assertEqual((ch["above"]["a"], ch["above"]["c"]), (0, 2))
        self.assertEqual(ch["critical"], ["a", "b", "c"])
        self.assertEqual(ch["cycles"], [["x", "y"]])
        self.assertEqual(ch["below"]["x"], 1)  # its cycle partner must resolve first

    def test_poisson_interval_matches_garwood_table(self):
        lo, hi = IM.poisson_interval(0, 0.95)
        self.assertEqual(lo, 0.0)
        self.assertAlmostEqual(hi, 3.6889, places=3)
        lo, hi = IM.poisson_interval(10, 0.95)
        self.assertAlmostEqual(lo, 4.7954, places=3)
        self.assertAlmostEqual(hi, 18.3904, places=3)
        lo, hi = IM.poisson_interval(400, 0.90)  # large counts: no underflow
        self.assertLess(lo, 400)
        self.assertGreater(hi, 400)
        with self.assertRaises(ValueError):
            IM.poisson_interval(-1)

    def test_rank_statistics(self):
        self.assertAlmostEqual(IM.spearman([1, 2, 3, 4], [1, 2, 3, 4]), 1.0)
        self.assertAlmostEqual(IM.spearman([1, 2, 3, 4], [4, 3, 2, 1]), -1.0)
        self.assertIsNone(IM.spearman([1, 1, 1], [1, 2, 3]))
        self.assertAlmostEqual(IM.kendall_tau_b([1, 2, 3], [1, 2, 3]), 1.0)
        self.assertAlmostEqual(IM.kendall_tau_b([1, 2, 3], [3, 2, 1]), -1.0)
        self.assertAlmostEqual(IM.kendall_tau_b([1, 1, 2], [1, 2, 3]), 2 / (2 * 3) ** 0.5 * (2 / 2) ** 0.5 / 1, places=6)
        self.assertEqual(IM.quantile([1, 2, 3, 4], 0.5), 2.5)
        self.assertIsNone(IM.quantile([], 0.5))
        self.assertEqual(IM.average_ranks([10, 20, 20, 30]), [1, 2.5, 2.5, 4])
        draw = IM.dirichlet(random.Random(1), [1.0, 2.0, 3.0])
        self.assertAlmostEqual(sum(draw), 1.0)


class PressureWalk(unittest.TestCase):
    EDGES = [{"source": "waiter", "target": "blocker", "kind": "WAITS"},
             {"source": "other", "target": "blocker", "kind": "SOFT"}]

    def test_split_is_exact_and_mass_is_one(self):
        nodes = ["blocker", "other", "waiter"]
        r = ir.pagerank(nodes, self.EDGES, teleport={"waiter": 1.0, "other": 0.5, "blocker": 0.1},
                        weights={"WAITS": 1.0, "SOFT": 0.15}, split=True)
        self.assertAlmostEqual(sum(r["pi"].values()), 1.0, places=9)
        for n in nodes:
            self.assertAlmostEqual(r["pi"][n], r["own"][n] + r["inherited"][n], places=9)
        self.assertGreater(r["inherited"]["blocker"], 0)
        self.assertEqual(r["inherited"]["waiter"], 0)
        self.assertLess(r["residual"], 1e-9)

    def test_uniform_teleport_is_classical_pagerank(self):
        nodes = ["a", "b", "c"]
        e = [{"source": "a", "target": "b", "kind": "MENTION"}, {"source": "b", "target": "c", "kind": "MENTION"}]
        a = ir.pagerank(nodes, e)
        b = ir.pagerank(nodes, e, teleport={"a": 1, "b": 1, "c": 1})
        for n in nodes:
            self.assertAlmostEqual(a[n], b[n], places=9)


class Urgency(unittest.TestCase):
    def test_unknown_nearness_is_imputed_at_the_mean_never_zero(self):
        m = ir.rank(snapshot([issue(HUB, 1, ""), issue(HUB, 2, "- [ ] a\n- [ ] b"), issue(HUB, 3, "- [x] a")]),
                    draws=0)
        by = by_key(m)
        self.assertIsNone(by[k(1)]["urgency_parts"]["nearness"])
        self.assertIn("nearness", by[k(1)]["imputed"])
        self.assertLess(by[k(1)]["coverage"], by[k(2)]["coverage"])
        self.assertGreater(by[k(1)]["urgency"], by[k(2)]["urgency"])  # 0/2 ticked is not "unknown"
        self.assertIsNone(by[k(1)]["priority"])

    def test_overlay_priority_has_provenance(self):
        ov = {k(2): {"priority": "P0", "lane": "P0-A", "source": "D+14 audit"}}
        by = by_key(ir.rank(snapshot([issue(HUB, 1), issue(HUB, 2)]), overlay=ov, draws=0))
        self.assertEqual((by[k(2)]["priority"], by[k(2)]["priority_basis"]), (1.0, "OVERLAY"))
        self.assertEqual(by[k(2)]["overlay"]["lane"], "P0-A")
        self.assertEqual(by[k(2)]["rank_global"], 1)
        self.assertEqual(by[k(1)]["priority"], None)
        self.assertIn("priority", by[k(1)]["imputed"])
        self.assertGreater(by[k(2)]["urgency"], by[k(1)]["urgency"])  # neutral prior, not the mean of P0

    def test_load_overlay_validates_schema(self):
        with tempfile.TemporaryDirectory() as d:
            good, bad = Path(d) / "o.json", Path(d) / "b.json"
            good.write_text(json.dumps({"schema": ir.OVERLAY_SCHEMA, "source": "s",
                                        "entries": [{"key": k(1), "priority": "P1"}]}), encoding="utf-8")
            bad.write_text(json.dumps({"schema": "other"}), encoding="utf-8")
            self.assertEqual(ir.load_overlay([good])[k(1)], {"priority": "P1", "lane": None, "source": "s"})
            self.assertEqual(ir.load_overlay([Path(d) / "missing.json"]), {})
            with self.assertRaises(ValueError):
                ir.load_overlay([bad])


class Structure(unittest.TestCase):
    def test_pressure_flows_to_the_blocker_and_queue_skips_blocked(self):
        m = ir.rank(snapshot([issue(HUB, 1, "blocked by #2", labels=["P0"]), issue(HUB, 2), issue(HUB, 3)]),
                    draws=0)
        by = by_key(m)
        self.assertGreater(by[k(2)]["score_parts"]["inherited"], 0)
        self.assertGreater(by[k(2)]["score"], by[k(3)]["score"])
        self.assertEqual(by[k(1)]["lane"], "BLOCKED")
        self.assertNotIn(k(1), m["views"]["action_queue"])
        self.assertEqual(m["views"]["action_queue"][0], k(2))
        self.assertEqual(by[k(2)]["unblocks_now"], 1)

    def test_sole_blocker_only_counts_for_unblocks_now(self):
        by = by_key(ir.rank(snapshot([issue(HUB, 1, "blocked by #2 and blocked by #3"), issue(HUB, 2),
                                      issue(HUB, 3)]), draws=0))
        self.assertEqual((by[k(2)]["unblocks_now"], by[k(2)]["pressure"]), (0, 1))

    def test_duplicate_text_and_checkbox_declarations_are_one_blocker(self):
        m = ir.rank(snapshot([issue(HUB, 1, "- [ ] #2\nblocked by #2"), issue(HUB, 2)]), draws=0)
        by = by_key(m)
        self.assertEqual(by[k(1)]["open_blockers"], [k(2)])
        self.assertEqual(by[k(2)]["unblocks_now"], 1)
        self.assertNotIn(k(1), m["views"]["action_queue"])

    def test_deadlock_is_reported(self):
        m = ir.rank(snapshot([issue(HUB, 1, "depends on #2"), issue(HUB, 2, "depends on #1")]), draws=0)
        by = by_key(m)
        self.assertEqual({by[k(1)]["lane"], by[k(2)]["lane"]}, {"DEADLOCK"})
        self.assertEqual(m["graph"]["deadlocks"], [[k(1), k(2)]])
        self.assertEqual(m["rollups"]["USER"]["deadlocked"], 2)

    def test_chain_and_critical_path(self):
        m = ir.rank(snapshot([issue(HUB, 1, "depends on #2"), issue(HUB, 2, "depends on #3"), issue(HUB, 3)]),
                    draws=0)
        by = by_key(m)
        self.assertEqual(by[k(1)]["chain"]["below"], 2)
        self.assertEqual(m["graph"]["critical_chain"], [k(1), k(2), k(3)])

    def test_api_relations_are_observed_and_text_declared(self):
        it = issue(HUB, 1, "depends on #3")
        it["relations"] = {"parent": None, "sub_issues": [], "blocking": [], "closed_by": [],
                           "blocked_by": [{"repo": HUB, "number": 2, "state": "OPEN", "created_at": None}]}
        g = ir.build_graph(snapshot([it, issue(HUB, 2), issue(HUB, 3)]))
        binding = {(e["target"], e["kind"]): e["binding"] for e in g["edges"]}
        self.assertEqual(binding[(k(2), "DEPENDS_ON")], "OBSERVED")
        self.assertEqual(binding[(k(3), "DEPENDS_ON")], "DECLARED")

    def test_parked_intent_lane(self):
        m = ir.rank(snapshot([issue(HUB, 1, labels=["parked-intent", "P1"]), issue(HUB, 2, labels=["P1"])]), draws=0)
        by = by_key(m)
        self.assertEqual(by[k(1)]["lane"], "PARKED")
        self.assertFalse(by[k(1)]["actionable"])
        self.assertLess(by[k(1)]["urgency"], by[k(2)]["urgency"])


class GoldenThread(unittest.TestCase):
    def test_lifecycle_positions_via_rolling5(self):
        done = issue(HUB, 1, "## DoD\n- [x] a\n- [x] b\n## DoV\n- [x] run")
        done["assignees"] = ["gbo"]
        by = by_key(ir.rank(snapshot([done, issue(HUB, 2, "")]), draws=0))
        t1, t2 = by[k(1)]["golden_thread"], by[k(2)]["golden_thread"]
        self.assertEqual((t1["track"], t1["position"], t1["of"], t1["first_break"]), ("OWNER", 7, 7, None))
        self.assertEqual((t2["position"], t2["first_break"]), (0, "DEFINED"))
        self.assertIn("DoD", t2["next_step"])

    def test_code_track_breaks_at_review(self):
        it = issue(HUB, 5, "## DoD\n- [x] a\n## DoV\n- [ ] run")
        it["assignees"] = ["gbo"]
        by = by_key(ir.rank(snapshot([it, pr(HUB, 9, closes=[(HUB, 5)], checks="SUCCESS")]), draws=0))
        t = by[k(5)]["golden_thread"]
        self.assertEqual((t["track"], t["first_break"]), ("CODE", "REVIEWED"))
        self.assertEqual(by[k(5)]["lane"], "REVIEW")
        self.assertEqual(by[k(9)]["golden_thread"]["track"], "PR")


class Flow(unittest.TestCase):
    def snap(self):
        s = snapshot([issue(HUB, i, created="2026-10-20T00:00:00Z") for i in range(1, 4)])
        s["window"] = {"days": 14, "since": "2026-10-12T00:00:00Z"}
        closed = []
        for n in range(10, 22):
            c = issue(HUB, n, created="2026-09-01T00:00:00Z")
            c.update(state="CLOSED", state_reason="COMPLETED", closed_at="2026-10-20T00:00:00Z")
            closed.append(c)
        leak = issue(HUB, 30, "- [x] a\n- [ ] b\n- [ ] c", created="2026-09-01T00:00:00Z")
        leak.update(state="CLOSED", state_reason="COMPLETED", closed_at="2026-10-21T00:00:00Z")
        carried = issue(HUB, 31, "- [ ] open item\n\nsuperseded by #1", created="2026-09-01T00:00:00Z")
        carried.update(state="CLOSED", state_reason="COMPLETED", closed_at="2026-10-21T00:00:00Z")
        s["repos"][HUB]["closed"] = closed + [leak, carried]
        return s

    def test_flow_rates_and_eta(self):
        f = ir.rank(self.snap(), draws=0)["rollups"][HUB]["flow"]
        self.assertEqual((f["wip_open_issues"], f["arrivals"]["events"], f["closures"]["events"]), (3, 3, 14))
        self.assertLessEqual(f["closures"]["lo"], f["closures"]["per_day"])
        self.assertGreaterEqual(f["closures"]["hi"], f["closures"]["per_day"])
        self.assertEqual(f["status"], "BURNING_DOWN")
        self.assertLessEqual(f["eta_days"]["lo"], f["eta_days"]["est"])
        self.assertEqual(f["closure_reasons"], {"COMPLETED": 14})

    def test_v1_snapshot_has_no_flow(self):
        self.assertIsNone(ir.rank(fixture(), draws=0)["rollups"]["USER"]["flow"])

    def test_predicate_leak_needs_no_open_successor(self):
        m = ir.rank(self.snap(), draws=0)
        self.assertEqual([x["key"] for x in m["predicate_leaks"]], [k(30)])
        self.assertEqual(m["rollups"]["USER"]["predicate_leaks"], 1)


class MonteCarlo(unittest.TestCase):
    def test_reproducible_and_bounded(self):
        a = ir.rank(fixture(), draws=30, seed=7)
        b = ir.rank(fixture(), draws=30, seed=7)
        self.assertEqual(ir.canonical(a), ir.canonical(b))
        n = len(a["items"])
        for i in a["items"]:
            ri = i["rank_interval"]
            self.assertTrue(1 <= ri["p05"] <= ri["p50"] <= ri["p95"] <= n)
            self.assertTrue(0 <= ri["p_top"] <= 1)
        mc = a["method"]["monte_carlo"]
        self.assertEqual((mc["draws"], mc["seed"]), (30, 7))
        self.assertTrue(-1 <= mc["spearman_median"] <= 1)

    def test_zero_draws_disable_intervals(self):
        m = ir.rank(fixture(), draws=0)
        self.assertIsNone(m["items"][0]["rank_interval"])
        self.assertEqual(m["method"]["monte_carlo"]["draws"], 0)


class SourceCompleteness(unittest.TestCase):
    def test_nested_graphql_relation_limit_is_marked_incomplete(self):
        raw = FakeGh()(ir.ISSUES_Q, owner="GBOGEB", name="r")["repository"]["issues"]["nodes"][0]
        raw["subIssues"] = {"nodes": [
            {"number": i + 100, "state": "OPEN", "createdAt": None,
             "repository": {"nameWithOwner": HUB}} for i in range(30)]}
        observed = ir._issue(raw, HUB)
        self.assertEqual(observed["relation_limits_reached"], ["subIssues"])

    def test_capped_source_withholds_close_candidate_and_telemetry(self):
        s = fixture()
        s["repos"][HUB]["issues"][0]["relation_limits_reached"] = ["subIssues"]
        model = ir.rank(s, draws=0)
        item = by_key(model)[k(1)]
        self.assertEqual(item["lane"], "SOURCE_INCOMPLETE")
        self.assertFalse(item["actionable"])
        self.assertFalse(model["authority"]["source_relations_complete"])
        self.assertEqual(model["authority"]["nested_relation_capped_items"], 1)
        receipt = ir.telemetry(model, s, {"baseline": True})
        self.assertFalse(receipt["method"]["relations_complete"])


class Privacy(unittest.TestCase):
    def test_redacted_model_and_delta_are_boundary_fixed_points(self):
        before = ir.rank(fixture(), draws=0)
        after_snap = fixture()
        after_snap["repos"][QPS]["issues"].append(issue(QPS, 8, "blocked by #7", title="another secret"))
        after = ir.rank(after_snap, draws=0)
        model, delta = ir.redact(after, ir.diff(before, after))
        text = json.dumps([model, delta])
        for leaked in (f"{QPS}#7", f"{QPS}#8", "secret", "confidential", "b" * 40):
            self.assertNotIn(leaked, text)
        boundary = ir._boundary().Boundary([QPS])
        self.assertEqual(boundary.project({"model": model, "delta": delta}), {"model": model, "delta": delta})
        self.assertEqual(delta["new_items"], [])
        self.assertEqual(delta["private_item_movement"], "UNKNOWN_AGGREGATE_ONLY")


    def test_public_rollup_does_not_export_private_assignee_fingerprint(self):
        snap = fixture()
        snap["repos"][QPS]["issues"][0]["assignees"] = ["PRIVATE_ASSIGNEE_CANARY"]
        snap["repos"][HUB]["issues"][0]["assignees"] = ["public-reviewer"]
        model = ir.redact(ir.rank(snap, draws=0))
        text = json.dumps(model)
        self.assertNotIn("PRIVATE_ASSIGNEE_CANARY", text)
        self.assertIn("public-reviewer", text)
        self.assertEqual(model["rollups"][QPS]["by_assignee"], [])
        self.assertTrue(all(r["assignee"] != "PRIVATE_ASSIGNEE_CANARY"
                            for r in model["rollups"]["USER"]["by_assignee"]))

    def test_explicit_p4_remains_lowest_priority_not_unknown(self):
        ranked = ir.rank(snapshot([issue(HUB, 1, labels=["P4"])]), draws=0)
        low = by_key(ranked)[k(1)]
        self.assertEqual((low["priority"], low["priority_basis"]), (0.0, "LABEL_OR_TITLE"))
        self.assertNotIn("priority", low["imputed"])

class RedactedPulse(unittest.TestCase):
    def test_redacted_run_with_private_repo_writes_taxonomy_pulse_without_leaks(self):
        with tempfile.TemporaryDirectory() as d:
            snap = Path(d) / "snap.json"
            snap.write_bytes(ir.canonical(fixture()))
            out = Path(d) / "pub"
            args = ["rank", "--snapshot", str(snap), "--out", str(out), "--redact-private", "--draws", "3"]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ir.main(args), 0)
                self.assertEqual(ir.main(args + ["--prev", str(out / "issue_rank.json")]), 0)  # redacted prev
            text = "".join(p.read_text(encoding="utf-8") for p in sorted(out.iterdir()))
            self.assertTrue((out / "taxonomy_pulse.json").exists())
            for leaked in (f"{QPS}#7", "secret", "confidential", "b" * 40):
                self.assertNotIn(leaked, text)


    def test_two_different_redacted_pulses_do_not_invent_private_new_gone(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "public"
            for day in (26, 28):
                snap = fixture()
                snap["fetched_at"] = f"2026-10-{day}T00:00:00Z"
                source = Path(d) / f"source-{day}.json"
                source.write_bytes(ir.canonical(snap))
                args = ["rank", "--snapshot", str(source), "--out", str(out),
                        "--redact-private", "--draws", "0"]
                if day == 28:
                    args += ["--prev", str(out / "issue_rank.json")]
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(ir.main(args), 0)
            delta = json.loads((out / "delta.json").read_text(encoding="utf-8"))
            self.assertEqual(delta["new_items"], [])
            self.assertEqual(delta["gone_items"], [])
            self.assertEqual(delta["private_item_movement"], "UNKNOWN_AGGREGATE_ONLY")

class Delta(unittest.TestCase):
    def test_progress_scope_and_rooting(self):
        before = ir.rank(fixture(), draws=0)
        snap = fixture()
        snap["repos"][HUB]["issues"][1]["body"] = "## Steps\n- [x] a\n- [x] b\n- [ ] c\n- [ ] d\n\nblocked by #3"
        snap["repos"][HUB]["issues"].append(issue(HUB, 6, "see #3", created="2026-10-25T00:00:00Z"))
        snap["repos"][HUB]["issues"].append(issue(HUB, 7, "", created="2026-10-25T00:00:00Z"))
        d = ir.diff(before, ir.rank(snap, draws=0))
        self.assertEqual((d["tasks_ticked_net"], d["scope_added_net"]), (1, 1))
        self.assertEqual((d["new_items_rooted"], d["new_items_unrooted"]), ([k(6)], [k(7)]))


class Outputs(unittest.TestCase):
    def test_views_agreement_csv_html(self):
        m = ir.rank(fixture(), draws=10)
        ag = m["views"]["agreement"]["kendall_tau_b"]
        self.assertTrue(all(v is None or -1 <= v <= 1 for v in ag.values()))
        head = ir.to_csv(m).splitlines()[0].split(",")
        for col in ("rank_p05", "rank_p95", "p_top", "coverage", "thread", "first_break", "unblocks_now"):
            self.assertIn(col, head)
        page = ir.render_html(m, {"baseline": True})
        for s in ("Action queue", "Flow and burndown", "Dependency cycles", "Golden thread = lifecycle gates"):
            self.assertIn(s, page)
        self.assertEqual(m["method"]["ordering"], "NON_BT_REVERSE_PRESSURE_PAGERANK")
        self.assertEqual(m["schema"], "jade.issue-rank.v2")

    def test_jade_roster_and_fallback(self):
        self.assertIn("GBOGEB/ABACUS", ir.jade_roster())
        self.assertEqual(len(ir.jade_roster(Path("does-not-exist.json"))), 4)


if __name__ == "__main__":
    unittest.main()
