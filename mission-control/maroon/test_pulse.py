"""pulse.py and open_threads.py: verdicts, finding identity, recurrence, DAG waves, ledger and act. Fake gh only."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PU = _load("maroon_pulse", "pulse.py")
OT = PU.OT
ME = "owner"
HEAD_A, HEAD_B, HEAD_C = "a" * 40, "b" * 40, "c" * 40
RULE = "## Semgrep Finding: yaml.github-actions.security.github-actions-mutable-action-tag"


def thread(number, title, path="src/app.py", **kw):
    base = {"number": number, "state": "open", "title": title, "theme": PU.RT.theme_of(title), "severity": "medium",
            "path": path, "line": 3, "url": f"https://x/{number}", "reviewer": "copilot-pull-request-reviewer[bot]",
            "reviewer_family": "copilot", "replies": 0, "last_login": "copilot-pull-request-reviewer[bot]",
            "last_body": title, "last_id": number, "thread_id": f"T{number}", "outdated": False,
            "path_in_pr": True, "anchor_at_head": None, "suggestion_applied": None}
    base.update(kw)
    return base


def pr(number, head, threads, ref=None, **kw):
    base = {"number": number, "title": f"PR {number}", "author": ME, "draft": False, "head_ref": ref or f"feat/{number}",
            "head_sha": head, "head_repo": "o/r", "base_ref": "main", "mergeable_state": "blocked", "labels": [],
            "files": ["src/app.py", ".github/workflows/ci.yml"], "commits": [head], "threads": threads}
    base.update(kw)
    return base


def raw_of(*prs, at="2026-11-11T08:00:00+00:00"):
    return {"schema": OT.SCHEMA, "fetched_at": at, "owner": "o",
            "repos": {"o/r": {"coverage": "ok", "base_head_sha": "f" * 40, "prs": list(prs), "gaps": []}}}


def never_merged(repo, number):
    return number == 9


class Identity(unittest.TestCase):
    def test_rule_id_is_the_identity_and_prose_code_is_not_a_rule(self):
        self.assertEqual(PU.rule_of(RULE), "yaml.github-actions.security.github-actions-mutable-action-tag")
        self.assertEqual(PU.rule_of("Bandit B602: subprocess with shell"), "B602")
        self.assertIsNone(PU.rule_of("Use os.path.join here"))
        self.assertIsNone(PU.rule_of("Pin the SHA256 digest"))
        a = PU.finding_key("o/r", "security", RULE + " in ci.yml")
        b = PU.finding_key("o/r", "security", RULE + " somewhere else entirely")
        self.assertEqual(a, b)
        self.assertNotEqual(a, PU.finding_key("o/r", "security", "## Semgrep Finding: python.lang.security.audit.x-y"))

    def test_near_duplicates_merge_but_two_rules_never_do(self):
        items = [{"key": k, "repo": "o/r", "theme": "fail-open", "title": t, "words": PU.words(t)} for k, t in (
            ("k1", "Silent failure: exit 0 swallows the error"), ("k2", "exit 0 swallows the error silently: failure"),
            ("k3", RULE), ("k4", "## Semgrep Finding: python.lang.security.audit.other-rule"))]
        canon = PU.clusters_of(items)
        self.assertEqual(canon["k1"], canon["k2"])
        self.assertNotEqual(canon["k3"], canon["k4"])


class Verdicts(unittest.TestCase):
    def v(self, t, p=None, finding=None):
        p = p or pr(1, HEAD_A, [t])
        return PU.verdict_of(t, p, ME, finding, lambda n: n == 9)[0]

    def test_evidence_first(self):
        self.assertEqual(self.v(thread(1, "x", replies=1, last_login=ME, last_body="Fixed by merged #9.")), "ANSWERED")
        self.assertEqual(self.v(thread(1, "x", replies=1, last_login=ME, last_body="Fixed in #10.")), "WAIT")
        self.assertEqual(self.v(thread(1, "x", replies=1, last_login=ME, last_body=f"Fixed in {HEAD_A}.")), "ANSWERED")
        self.assertEqual(self.v(thread(1, "x", replies=1, last_login=ME, last_body=f"Fixed in {'9' * 40}.")), "NEEDS_FIX")
        kept = thread(1, "x", replies=1, last_login=ME, last_body="Kept as is: the alias is intended.")
        self.assertEqual(PU.verdict_of(kept, pr(1, HEAD_A, []), ME, None, lambda n: False), ("ANSWERED", "kept as is"))
        self.assertEqual(self.v(thread(1, "x", replies=1, last_login="alice")), "HUMAN_PENDING")

    def test_false_positive_and_history_signals(self):
        self.assertEqual(self.v(thread(1, "x", suggestion_applied=True)), "SUGGESTION_APPLIED")
        self.assertEqual(self.v(thread(1, "x", path_in_pr=False)), "OUT_OF_SCOPE")
        self.assertEqual(self.v(thread(1, "x"), finding={"kept": 2}), "FP_HISTORY")
        self.assertEqual(self.v(thread(1, "x"), finding={"kept": 0, "fixed": 1, "evidence": ["e"]}), "SEEN_FIXED")
        self.assertEqual(self.v(thread(1, "Stale numbers", path="mission-control/x/data/out.json")), "GENERATED")
        self.assertEqual(self.v(thread(1, "x", outdated=True, anchor_at_head=False)), "LIKELY_ADDRESSED")
        self.assertEqual(self.v(thread(1, "x", outdated=True, anchor_at_head=None)), "NEEDS_FIX")


class Plan(unittest.TestCase):
    def plan(self, raw, ledger=None):
        ledger = ledger or PU.new_ledger("o")
        items = PU.triage(raw, ledger, ME, never_merged)
        PU.record_findings(ledger, raw, items)
        plan = PU.build_plan(raw, ledger, items, ME)
        PU.augment(ledger, raw, items, plan)
        return plan, ledger

    def test_repeat_on_two_prs_is_one_cluster_worker_and_waves_are_disjoint(self):
        raw = raw_of(pr(1, HEAD_A, [thread(11, RULE, ".github/workflows/ci.yml"), thread(12, "Guard the None path")]),
                     pr(2, HEAD_B, [thread(21, RULE, ".github/workflows/ci.yml"),
                                    thread(22, "x", suggestion_applied=True)]))
        plan, _ = self.plan(raw)
        kinds = sorted(n["kind"] for n in plan["nodes"].values())
        self.assertEqual(kinds, ["close", "close", "cluster", "fix", "resolve"])
        cluster = next(n for n in plan["nodes"].values() if n["kind"] == "cluster")
        self.assertEqual(sorted(t["thread"] for t in cluster["threads"]), [11, 21])
        self.assertLess(cluster["wave"], plan["nodes"]["fix:o/r#1"]["wave"])  # same branch: cluster first
        self.assertEqual(plan["nodes"]["resolve:o/r#2"]["wave"], 0)  # evidence in hand: first wave
        for wave in plan["waves"]:
            writes = [w for nid in wave for w in plan["nodes"][nid]["writes"]]
            self.assertEqual(len(writes), len(set(writes)))
        self.assertEqual(set(cluster["sipoc"]), {"supplier", "input", "process", "output", "customer"})

    def test_bot_and_fork_branches_get_no_writer(self):
        raw = raw_of(pr(1, HEAD_A, [thread(11, "Guard it")], ref="dependabot/pip/x"),
                     pr(2, HEAD_B, [thread(21, "Guard it")], head_repo="fork/r"))
        plan, _ = self.plan(raw)
        self.assertFalse([n for n in plan["nodes"].values() if n["writes"]])

    def test_systemic_finding_gets_a_fold_back_node_on_first_sight(self):
        raw = raw_of(*(pr(n, h, [thread(n * 10, RULE, ".github/workflows/ci.yml")])
                       for n, h in ((1, HEAD_A), (2, HEAD_B), (3, HEAD_C))))
        plan, ledger = self.plan(raw)
        fold = [n for n in plan["nodes"].values() if n["kind"] == "fold"]
        self.assertEqual(len(fold), 1)
        self.assertEqual(fold[0]["recurrence"], "SYSTEMIC")
        self.assertIn(fold[0]["id"], plan["ready"] if "ready" in plan else PU.ready_nodes(plan, ledger))

    def test_ledger_recurrence_is_idempotent_and_counts_pulses(self):
        raw = raw_of(pr(1, HEAD_A, [thread(11, "Guard the None path")]))
        _, ledger = self.plan(raw)
        self.plan(raw, ledger)  # the same pulse planned twice
        f = next(iter(ledger["findings"].values()))
        self.assertEqual((f["pulses_seen"], f["occurrences"], f["verdicts"]), (1, 1, {"NEEDS_FIX": 1}))
        self.assertEqual(f["recurrence"], "ONCE")
        self.plan(raw_of(pr(1, HEAD_A, [thread(11, "Guard the None path")]), at="2026-11-11T16:00:00+00:00"), ledger)
        self.assertEqual((f["pulses_seen"], f["recurrence"], f["frequency"]), (2, "REPEAT", 0.5))

    def test_queue_states_stale_dispatch_and_blocked(self):
        raw = raw_of(pr(1, HEAD_A, [thread(11, "Guard the None path")]))
        _, ledger = self.plan(raw)
        q = ledger["queue"]["fix:o/r#1"]
        q.update(state="DISPATCHED", at="2026-11-09T00:00:00+00:00")
        self.plan(raw, ledger)
        self.assertEqual(q["state"], "QUEUED")
        q.update(state="FAILED", attempts=3)
        self.plan(raw, ledger)
        self.assertEqual(q["state"], "BLOCKED")
        later = raw_of(pr(1, HEAD_A, []), at="2026-11-11T16:00:00+00:00")
        q.update(state="QUEUED")
        self.plan(later, ledger)
        self.assertEqual(q["state"], "OBSERVED_CLOSED")

    def test_seed_gives_history(self):
        ledger = PU.new_ledger("o")
        PU.seed(ledger, {"fetched_at": "2026-11-01T00:00:00+00:00", "repos": {"o/r": {"alerts": [
            dict(thread(5, "Guard the None path"), state="resolved", pr=4, pr_merged=True, closed_at="2026-11-01")]}}})
        plan, _ = self.plan(raw_of(pr(1, HEAD_A, [thread(11, "Guard the None path")])), ledger)
        self.assertEqual(plan["verdicts"], {"SEEN_FIXED": 1})

    def test_public_counts_hold_no_text(self):
        plan, ledger = self.plan(raw_of(pr(1, HEAD_A, [thread(11, "Secret path src/app.py leaks")])))
        blob = json.dumps(PU.public_counts(plan, ledger))
        self.assertNotIn("src/app.py", blob)
        self.assertNotIn("leaks", blob)


class FakeGh:
    def __init__(self, head=HEAD_A, resolved=()):
        self.head, self.resolved, self.writes = head, set(resolved), []

    def __call__(self, args):
        if args[:3] == ["api", "-X", "POST"] or (args[:2] == ["api", "graphql"] and "mutation" in args[3]):
            self.writes.append(args)
            return 0, "{}", ""
        if args[:2] == ["api", "graphql"]:
            nodes = [{"id": f"T{n}", "isResolved": n in self.resolved, "isOutdated": False,
                      "comments": {"nodes": [{"databaseId": n}]}} for n in (11, 12)]
            return 0, json.dumps({"data": {"repository": {"pullRequest": {"reviewThreads": {
                "pageInfo": {"hasNextPage": False}, "nodes": nodes}}}}}), ""
        if args[1] == "repos/o/r/pulls/1":
            return 0, json.dumps({"state": "open", "head": {"sha": self.head}}), ""
        return 1, "", "unexpected " + " ".join(args)


class Act(unittest.TestCase):
    def setUp(self):
        raw = raw_of(pr(1, HEAD_A, [thread(11, "x", suggestion_applied=True), thread(12, "Guard the None path")]))
        self.ledger = PU.new_ledger("o")
        items = PU.triage(raw, self.ledger, ME, never_merged)
        PU.record_findings(self.ledger, raw, items)
        self.plan = PU.build_plan(raw, self.ledger, items, ME)
        PU.augment(self.ledger, raw, items, self.plan)

    def test_dry_run_writes_nothing(self):
        gh = FakeGh()
        out = PU.act(self.plan, self.ledger, gh)
        self.assertEqual(gh.writes, [])
        self.assertIn({"node": "resolve:o/r#1", "pr": "o/r#1", "thread": 11, "verdict": "SUGGESTION_APPLIED",
                       "outcome": "WOULD_REPLY_AND_RESOLVE"}, out)
        self.assertIn("WAIT_WORKERS", {r["outcome"] for r in out})  # close waits for fix:o/r#1

    def test_apply_replies_then_resolves_only_evidence_threads(self):
        gh = FakeGh()
        out = PU.act(self.plan, self.ledger, gh, apply=True)
        self.assertEqual(len(gh.writes), 2)
        self.assertIn("comments/11/replies", gh.writes[0][3])
        self.assertIn("Fixed in " + HEAD_A, gh.writes[0][-1])
        self.assertIn("id=T11", gh.writes[1][-1])
        self.assertEqual(self.ledger["queue"]["resolve:o/r#1"]["state"], "DONE")
        self.assertTrue(any(r["outcome"] == "REPLIED_AND_RESOLVED" for r in out))

    def test_moved_head_or_resolved_thread_or_budget_skips(self):
        self.assertEqual({r["outcome"] for r in PU.act(self.plan, self.ledger, FakeGh(head=HEAD_B), apply=True)
                          if "thread" in r}, {"SKIP_HEAD_MOVED"})
        self.assertEqual({r["outcome"] for r in PU.act(self.plan, self.ledger, FakeGh(resolved={11}), apply=True)
                          if "thread" in r}, {"SKIP_ALREADY_RESOLVED"})
        gh = FakeGh()
        self.assertEqual({r["outcome"] for r in PU.act(self.plan, self.ledger, gh, apply=True, max_actions=0)
                          if "thread" in r}, {"SKIP_BUDGET"})
        self.assertEqual(gh.writes, [])


class Scanner(unittest.TestCase):
    def test_head_evidence(self):
        t = {"anchor": "value = compute(alpha, beta)"}
        body = "Use a guard.\n```suggestion\nif value is None:\n    return\n```"
        text = "def f():\n    value = compute(alpha, beta)\n    if value is None:\n        return\n"
        self.assertEqual(OT.head_evidence(t, body, text),
                         {"file_at_head": True, "anchor_at_head": True, "suggestion_applied": True})
        self.assertEqual(OT.head_evidence({"anchor": "}"}, "", "x")["anchor_at_head"], None)  # short anchor proves nothing
        self.assertEqual(OT.head_evidence(t, body, None)["file_at_head"], False)

    def test_retry_on_transient_only(self):
        calls, sleeps = [], []

        def flaky(args):
            calls.append(args)
            return (1, "", "dial tcp: connectex: A connection attempt failed") if len(calls) < 3 else (0, "{}", "")
        self.assertEqual(OT.retrying(flaky, sleep=sleeps.append)(["api", "x"])[0], 0)
        self.assertEqual(sleeps, [2.0, 4.0])
        calls.clear()
        hard = OT.retrying(lambda a: (calls.append(a), (1, "", "HTTP 404: Not Found"))[1], sleep=sleeps.append)
        self.assertEqual(hard(["api", "y"])[0], 1)
        self.assertEqual(len(calls), 1)

    def test_cli_plan_and_done_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "raw_open.json").write_text(json.dumps(raw_of(pr(1, HEAD_A, [thread(11, "Guard the None path")]))),
                                               encoding="utf-8")
            gh = lambda args: (0, json.dumps({"merged_at": None}), "")
            self.assertEqual(PU.main(["plan", "--raw", str(tmp / "raw_open.json"), "--ledger", str(tmp / "l.json"),
                                      "--me", ME, "--out", str(tmp / "out")], gh=gh), 0)
            self.assertTrue((tmp / "out" / "briefs" / "fix_o_r_1.md").exists())
            self.assertIn("MAROON_WORKER=DONE", (tmp / "out" / "briefs" / "fix_o_r_1.md").read_text(encoding="utf-8"))
            self.assertEqual(PU.main(["done", "--ledger", str(tmp / "l.json"), "--node", "fix:o/r#1", "--status", "DONE"],
                                     gh=gh), 0)
            self.assertEqual(json.loads((tmp / "l.json").read_text(encoding="utf-8"))["queue"]["fix:o/r#1"]["state"], "DONE")


if __name__ == "__main__":
    unittest.main()
