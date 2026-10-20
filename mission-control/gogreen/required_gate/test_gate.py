"""Offline controls for the GOGREEN required-gate aggregator (v2: ledger-driven)."""
import base64
import io
import itertools
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gate as g  # noqa: E402

ROOT = HERE.parents[2]
SHA = "a" * 40
BASE = "b" * 40
REPO = "GBOGEB/pipeline-automation-hub"


def mini_repo(d, workflows):
    w = Path(d) / ".github" / "workflows"
    w.mkdir(parents=True)
    for name, text in workflows.items():
        (w / name).write_text(text)
    return Path(d)


class Globs(unittest.TestCase):
    def test_github_glob_semantics(self):
        r = g.glob_to_regex("mission-control/federation-atlas/**")
        self.assertTrue(r.match("mission-control/federation-atlas/a/b.py"))
        self.assertFalse(r.match("mission-control/federation-atlasX/a.py"))
        star = g.glob_to_regex("docs/*.md")
        self.assertTrue(star.match("docs/a.md"))
        self.assertFalse(star.match("docs/x/a.md"))
        self.assertTrue(g.glob_to_regex("**/*.yml").match("a/b/c.yml"))
        self.assertTrue(g.glob_to_regex("**/*.yml").match("c.yml"))
        self.assertTrue(g.glob_to_regex(".github/workflows/x.yml").match(".github/workflows/x.yml"))
        self.assertFalse(g.glob_to_regex(".github/workflows/x.yml").match(".github/workflowsXx.yml"))

    def test_negation(self):
        self.assertEqual(g.applies(["a/x.py", "a/skip.md"], ["a/**", "!a/*.md"]), ["a/x.py"])

    def test_negation_is_ordered_like_github(self):
        # a later positive pattern re-includes a path an earlier negative excluded
        self.assertEqual(g.applies(["a/keep.md"], ["a/**", "!a/*.md", "a/keep.md"]), ["a/keep.md"])
        self.assertEqual(g.applies(["a/x.md"], ["!a/*.md", "a/**"]), ["a/x.md"])

    def test_no_filter_always_applies(self):
        self.assertEqual(g.applies(["anything"], None), ["anything"])

    def test_paths_ignore(self):
        self.assertEqual(g.applies(["docs/a.md"], None, ["docs/**"]), [])
        self.assertEqual(g.applies(["docs/a.md", "src/x.py"], None, ["docs/**"]), ["src/x.py"])


class Triggers(unittest.TestCase):
    def test_trigger_shapes(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "w.yml"
            p.write_text("on: [push, pull_request]\n")
            t = g.triggers(p)
            self.assertTrue(t["pull_request"])
            self.assertIsNone(t["paths"])
            p.write_text("on:\n  pull_request:\n    branches: [master]\n    paths: ['a/**']\n    types: [labeled]\n")
            t = g.triggers(p)
            self.assertEqual((t["branches"], t["paths"], t["types"]), (["master"], ["a/**"], ["labeled"]))
            self.assertIn("types", g.fires_for_base(t, "master"))
            p.write_text("on:\n  pull_request_target: {}\n")
            t = g.triggers(p)
            self.assertEqual((t["pull_request"], t["pull_request_target"]), (False, True))
            p.write_text("on: [unclosed\n")
            self.assertIn("parse_error", g.triggers(p))

    def test_base_branch_filter(self):
        t = {"pull_request": True, "branches": ["master"], "types": None}
        self.assertIsNone(g.fires_for_base(t, "master"))
        self.assertIn("branches", g.fires_for_base(t, "release/x"))
        t = {"pull_request": True, "branches_ignore": ["release/**"]}
        self.assertIn("ignore", g.fires_for_base(t, "release/a/b"))
        self.assertIsNone(g.fires_for_base({"pull_request": True}, "anything"))


class RealWorkflows(unittest.TestCase):
    def test_guarded_workflows_parse_from_repo(self):
        for wf in g.GUARDED:
            with self.subTest(wf=wf):
                f = g.path_filters(ROOT / wf)
                self.assertTrue(f, "guarded workflow must declare pull_request.paths")
                self.assertIn(wf, f, "workflow should trigger on its own edits")

    def test_unrelated_change_not_applicable_related_applies(self):
        atlas = g.path_filters(ROOT / g.GUARDED[0])
        self.assertEqual(g.applies(["README.md"], atlas), [])
        self.assertTrue(g.applies(["mission-control/federation-atlas/build_atlas.py"], atlas))

    def test_rejects_non_pull_request_workflows(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "w.yml"
            p.write_text("on:\n  push: {}\n")
            with self.assertRaises(ValueError):
                g.path_filters(p)
            p.write_text("on:\n  pull_request:\n    paths-ignore: ['x']\n")
            self.assertIsNone(g.path_filters(p), "paths-ignore is supported since v2")

    def test_committed_ledger_is_complete_and_legal(self):
        doc = json.loads((ROOT / g.ADMISSION).read_text())
        pol = g.policy_from_doc(doc, "head")
        files = sorted(str(f.relative_to(ROOT)) for f in (ROOT / ".github/workflows").glob("*.y*ml"))
        missing = [f for f in files if f not in pol["entries"]]
        self.assertLessEqual(len(missing), max(10, len(files) // 10),
                             f"ledger badly out of date; regenerate with admission.py ({missing[:5]})")
        for wf in g.GUARDED:  # ratchet: the N+8 incumbents stay enforced
            self.assertEqual(pol["entries"][wf], g.ENFORCED)
        self.assertNotEqual(pol["entries"].get(g.SELF), g.ENFORCED)
        self.assertFalse(doc["authority"]["merge_authorized"])


class Verdicts(unittest.TestCase):
    def r(self, status, conclusion, attempt=1, rid=1):
        return {"status": status, "conclusion": conclusion, "run_attempt": attempt, "id": rid,
                "created_at": "2026-10-19T00:00:00Z"}

    def test_states(self):
        self.assertEqual(g.verdict([]), g.WAIT)
        self.assertEqual(g.verdict([self.r("in_progress", None)]), g.WAIT)
        self.assertEqual(g.verdict([self.r("completed", "success")]), g.PASS)
        for bad in ("failure", "cancelled", "timed_out", "skipped"):
            self.assertEqual(g.verdict([self.r("completed", bad)]), g.FAIL)

    def test_latest_attempt_wins(self):
        runs = [self.r("completed", "failure", 1), self.r("completed", "success", 2)]
        self.assertEqual(g.verdict(runs), g.PASS)
        self.assertEqual(g.verdict(list(reversed(runs))), g.PASS)


def reader(files, runs_by_wf, calls=None, contents=None):
    """Fake API: PR files, one head-SHA run listing for all workflows, base contents."""
    def opener(req, timeout):
        u = req.full_url
        if calls is not None:
            calls.append(u)
        if "/pulls/" in u:
            body = [{"filename": f} for f in files] if "page=1" in u else []
        elif "/actions/runs?head_sha=" in u:
            runs = [dict(r, path=".github/workflows/" + name) for name, rs in runs_by_wf.items() for r in rs]
            body = {"total_count": len(runs), "workflow_runs": runs}
        elif "/contents/" in u:
            if contents is None:
                raise urllib.error.HTTPError(u, 404, "Not Found", {}, None)
            body = {"content": base64.b64encode(json.dumps(contents).encode()).decode()}
        else:
            raise AssertionError("unexpected GET " + u)
        return io.BytesIO(json.dumps(body).encode())
    return g.Reader(REPO, token="", opener=opener)


DONE = lambda c: [{"status": "completed", "conclusion": c, "id": 1}]


class Evaluate(unittest.TestCase):
    def test_not_applicable_passes_without_waiting(self):
        rep = g.evaluate(reader(["README.md"], {}), ROOT, 1, SHA, deadline_s=0, sleep=lambda s: None,
                         base_ref="master")
        self.assertEqual(rep["verdict"], g.PASS)
        self.assertTrue(all(x["state"] == g.NA for x in rep["gates"]))

    def test_applicable_red_fails(self):
        rep = g.evaluate(reader(["mission-control/federation-atlas/x.py"],
                                {"code-purple-method-atlas.yml": DONE("failure")}), ROOT, 1, SHA, 0,
                         sleep=lambda s: None)
        self.assertEqual(rep["verdict"], g.FAIL)

    def test_applicable_green_passes(self):
        rep = g.evaluate(reader(["mission-control/federation-atlas/x.py"],
                                {"code-purple-method-atlas.yml": DONE("success")}), ROOT, 1, SHA, 0,
                         sleep=lambda s: None)
        self.assertEqual(rep["verdict"], g.PASS)
        self.assertFalse(rep["merge_authorized"])

    def test_missing_run_fails_closed_at_deadline(self):
        t = itertools.chain([0, 0], itertools.repeat(999))
        rep = g.evaluate(reader(["mission-control/federation-atlas/x.py"], {}), ROOT, 1, SHA, 10,
                         clock=lambda: next(t), sleep=lambda s: None)
        self.assertEqual(rep["verdict"], g.FAIL)
        self.assertIn("deadline", [x for x in rep["gates"] if x["state"] == g.FAIL][0]["reason"])

    def test_both_gates_apply_to_shared_workflow_file(self):
        both = ".github/workflows/code-purple-method-atlas.yml"
        rep = g.evaluate(reader([both], {}), ROOT, 1, SHA, 0, sleep=lambda s: None)
        self.assertTrue(set(g.GUARDED) <= {x["workflow"] for x in rep["gates"] if x["matched_files"]})

    def test_one_listing_per_poll_regardless_of_gate_count(self):
        calls = []
        rep = g.evaluate(reader([".github/workflows/code-purple-method-atlas.yml",
                                 "mission-control/federation-atlas/x.py"],
                                {"code-purple-method-atlas.yml": DONE("success"),
                                 "live-lossless-qa.yml": DONE("success")}, calls), ROOT, 1, SHA, 0,
                         sleep=lambda s: None)
        self.assertEqual(rep["verdict"], g.PASS)
        self.assertEqual(sum("/actions/runs?head_sha=" in u for u in calls), 1)


class Policy(unittest.TestCase):
    WF = {"a.yml": "name: A\non:\n  pull_request:\n    paths: ['a/**']\n",
          "b.yml": "name: B\non:\n  pull_request:\n    paths: ['b/**']\n",
          "c.yml": "name: C\non:\n  pull_request:\n    branches: [release]\n",
          "gogreen-required-gate.yml": "name: G\non:\n  pull_request: {}\n"}

    def ledger(self, **disp):
        return {"schema": g.ADMISSION_SCHEMA,
                "entries": [{"path": f".github/workflows/{k}.yml", "disposition": v, "reasons": ["T"]}
                            for k, v in disp.items()] +
                           [{"path": g.SELF, "disposition": g.ENFORCED, "reasons": ["MISCONFIGURED"]}]}

    def test_observed_red_never_blocks_but_enforced_does(self):
        with tempfile.TemporaryDirectory() as d:
            root = mini_repo(d, self.WF)
            pol = g.policy_from_doc(self.ledger(a=g.ENFORCED, b=g.OBSERVED), "t")
            rep = g.evaluate(reader(["a/x", "b/y"], {"a.yml": DONE("success"), "b.yml": DONE("failure")}),
                             root, 1, SHA, 0, sleep=lambda s: None, policy=pol, base_ref="master")
            self.assertEqual(rep["verdict"], g.PASS)
            self.assertEqual([x["state"] for x in rep["observed"] if x["workflow"].endswith("b.yml")], [g.FAIL])
            rep = g.evaluate(reader(["a/x"], {"a.yml": DONE("failure")}), root, 1, SHA, 0,
                             sleep=lambda s: None, policy=pol, base_ref="master")
            self.assertEqual(rep["verdict"], g.FAIL)

    def test_self_never_waited_on_even_if_ledger_says_enforced(self):
        with tempfile.TemporaryDirectory() as d:
            root = mini_repo(d, self.WF)
            pol = g.policy_from_doc(self.ledger(a=g.ENFORCED), "t")
            rep = g.evaluate(reader(["x"], {}), root, 1, SHA, 0, sleep=lambda s: None, policy=pol, base_ref="master")
            self.assertIn(g.SELF, [x["workflow"] for x in rep["excluded"]])
            self.assertNotIn(g.SELF, [x["workflow"] for x in rep["gates"]])

    def test_unlisted_reported_never_omitted(self):
        with tempfile.TemporaryDirectory() as d:
            root = mini_repo(d, self.WF)
            pol = g.policy_from_doc(self.ledger(a=g.ENFORCED), "t")
            rep = g.evaluate(reader(["b/y"], {}), root, 1, SHA, 0, sleep=lambda s: None, policy=pol, base_ref="master")
            b = [x for x in rep["observed"] if x["workflow"].endswith("b.yml")][0]
            self.assertTrue(b["unlisted"])
            self.assertEqual(rep["coverage"]["unlisted"], 2)  # b and c
            self.assertEqual(rep["verdict"], g.PASS)

    def test_branch_filter_makes_enforced_not_applicable(self):
        with tempfile.TemporaryDirectory() as d:
            root = mini_repo(d, self.WF)
            pol = g.policy_from_doc(self.ledger(c=g.ENFORCED), "t")
            rep = g.evaluate(reader(["anything"], {}), root, 1, SHA, 0, sleep=lambda s: None, policy=pol,
                             base_ref="master")
            c = [x for x in rep["gates"] if x["workflow"].endswith("c.yml")][0]
            self.assertEqual(c["state"], g.NA)
            self.assertIn("branches", c["reason"])

    def test_policy_read_from_base_and_bootstrap_fallback(self):
        doc = self.ledger(a=g.ENFORCED)
        pol = g.load_policy(reader([], {}, contents=doc), BASE, ROOT, "base")
        self.assertTrue(pol["source"].startswith(f"base@{BASE}"))
        self.assertEqual(pol["entries"][".github/workflows/a.yml"], g.ENFORCED)
        boot = g.load_policy(reader([], {}), BASE, ROOT, "base")
        self.assertTrue(boot["source"].startswith("bootstrap"))
        self.assertEqual(set(p for p, v in boot["entries"].items() if v == g.ENFORCED), set(g.GUARDED))
        with self.assertRaises(ValueError):
            g.load_policy(reader([], {}), "short", ROOT, "base")

    def test_illegal_ledger_rejected(self):
        with self.assertRaises(ValueError):
            g.policy_from_doc({"schema": "other", "entries": []}, "t")
        with self.assertRaises(ValueError):
            g.policy_from_doc({"schema": g.ADMISSION_SCHEMA, "entries": [{"path": "x", "disposition": "MAYBE"}]}, "t")


if __name__ == "__main__":
    unittest.main()
