"""Offline controls for the GOGREEN required-gate aggregator (v2: ledger-driven)."""
import base64
import contextlib
import hashlib
import io
import itertools
import json
import os
import sys
import tempfile
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest import mock

import yaml

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
        (w / name).write_text(text, encoding="utf-8", newline="\n")
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
            p.write_text("on: [push, pull_request]\n", encoding="utf-8", newline="\n")
            t = g.triggers(p)
            self.assertTrue(t["pull_request"])
            self.assertIsNone(t["paths"])
            p.write_text("on:\n  pull_request:\n    branches: [master]\n    paths: ['a/**']\n    types: [labeled]\n", encoding="utf-8", newline="\n")
            t = g.triggers(p)
            self.assertEqual((t["branches"], t["paths"], t["types"]), (["master"], ["a/**"], ["labeled"]))
            self.assertIn("types", g.fires_for_base(t, "master"))
            p.write_text("on:\n  pull_request_target: {}\n", encoding="utf-8", newline="\n")
            t = g.triggers(p)
            self.assertEqual((t["pull_request"], t["pull_request_target"]), (False, True))
            p.write_text("on: [unclosed\n", encoding="utf-8", newline="\n")
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
            p.write_text("on:\n  push: {}\n", encoding="utf-8", newline="\n")
            with self.assertRaises(ValueError):
                g.path_filters(p)
            p.write_text("on:\n  pull_request:\n    paths-ignore: ['x']\n", encoding="utf-8", newline="\n")
            self.assertIsNone(g.path_filters(p), "paths-ignore is supported since v2")

    def test_committed_ledger_is_complete_and_legal(self):
        doc = json.loads((ROOT / g.ADMISSION).read_text(encoding="utf-8"))
        pol = g.policy_from_doc(doc, "head")
        files = sorted(f.relative_to(ROOT).as_posix() for f in (ROOT / ".github/workflows").glob("*.y*ml"))
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


def run(rid, status, conclusion, attempt=1, created="2026-10-25T00:00:00Z", started=None):
    r = {"id": rid, "status": status, "conclusion": conclusion, "run_attempt": attempt, "created_at": created,
         "html_url": f"https://github.com/{REPO}/actions/runs/{rid}"}
    if started:
        r["run_started_at"] = started
    return r


class LatestByStartTime(unittest.TestCase):
    """#886 (2): the latest run is the one that STARTED last, not the highest attempt."""

    def test_newer_run_beats_older_run_on_higher_attempt(self):
        old = run(1, "completed", "failure", attempt=2, created="2026-10-25T00:00:00Z", started="2026-10-25T01:00:00Z")
        new = run(2, "completed", "success", attempt=1, created="2026-10-25T02:00:00Z", started="2026-10-25T02:00:00Z")
        for runs in ([old, new], [new, old]):
            self.assertEqual(g.latest_run(runs)["id"], 2)
            self.assertEqual(g.verdict(runs), g.PASS)

    def test_rerun_keeps_created_at_but_wins_by_start_time(self):
        rerun = run(1, "completed", "success", attempt=2, created="2026-10-25T00:00:00Z", started="2026-10-25T03:00:00Z")
        newer = run(2, "completed", "failure", attempt=1, created="2026-10-25T02:00:00Z", started="2026-10-25T02:00:00Z")
        self.assertEqual(g.verdict([newer, rerun]), g.PASS)
        self.assertEqual(g.latest_run([newer, rerun])["id"], 1)

    def test_falls_back_to_created_at_then_attempt_then_id(self):
        a = run(1, "completed", "failure", created="2026-10-25T00:00:00Z")
        b = run(2, "completed", "success", created="2026-10-25T01:00:00Z")
        self.assertEqual(g.latest_run([b, a])["id"], 2)
        c = run(3, "completed", "failure", attempt=1, created="2026-10-25T05:00:00Z")
        d = run(3, "completed", "success", attempt=2, created="2026-10-25T05:00:00Z")
        self.assertEqual(g.latest_run([d, c])["run_attempt"], 2)
        e, f = run(4, "completed", "failure"), run(5, "completed", "success")
        self.assertEqual(g.latest_run([f, e])["id"], 5)
        self.assertIsNone(g.latest_run([]))


def seq_reader(files, listings, calls=None, posts=None):
    """Fake API whose head-SHA run listing changes per poll (last listing repeats)."""
    polls = iter(listings)
    last = {}

    def opener(req, timeout):
        u = req.full_url
        if calls is not None:
            calls.append(u)
        if req.get_method() == "POST":
            if posts is None:
                raise AssertionError("unexpected POST " + u)
            posts.append(u)
            return io.BytesIO(b"")
        if "/pulls/" in u:
            body = [{"filename": f} for f in files] if "page=1" in u else []
        elif "/actions/runs?head_sha=" in u:
            last["v"] = next(polls, last.get("v", {}))
            rs = [dict(r, path=".github/workflows/" + name) for name, lst in last["v"].items() for r in lst]
            body = {"total_count": len(rs), "workflow_runs": rs}
        else:
            raise AssertionError("unexpected GET " + u)
        return io.BytesIO(json.dumps(body).encode())
    return g.Reader(REPO, token="", opener=opener)


class RereadEveryPoll(unittest.TestCase):
    WF = {"a.yml": "name: A\non:\n  pull_request:\n    paths: ['a/**']\n",
          "b.yml": "name: B\non:\n  pull_request:\n    paths: ['b/**']\n"}

    def policy(self):
        return g.policy_from_doc({"schema": g.ADMISSION_SCHEMA, "entries": [
            {"path": ".github/workflows/a.yml", "disposition": g.ENFORCED},
            {"path": ".github/workflows/b.yml", "disposition": g.ENFORCED}]}, "t")

    def test_gate_rerun_during_the_wait_is_seen(self):
        t0, t1 = "2026-10-25T00:00:00Z", "2026-10-25T00:10:00Z"
        listings = [
            {"a.yml": [run(1, "completed", "failure", created=t0, started=t0)], "b.yml": [run(2, "in_progress", None)]},
            {"a.yml": [run(1, "queued", None, attempt=2, created=t0, started=t1)], "b.yml": [run(2, "completed", "success")]},
            {"a.yml": [run(1, "completed", "success", attempt=2, created=t0, started=t1)],
             "b.yml": [run(2, "completed", "success")]},
        ]
        calls = []
        with tempfile.TemporaryDirectory() as d:
            root = mini_repo(d, self.WF)
            rep = g.evaluate(seq_reader(["a/x", "b/y"], listings, calls), root, 1, SHA, 3600,
                             sleep=lambda s: None, policy=self.policy(), base_ref="master")
        self.assertEqual(rep["verdict"], g.PASS)
        self.assertEqual(sum("/actions/runs?head_sha=" in u for u in calls), 3)
        a = [x for x in rep["gates"] if x["workflow"].endswith("a.yml")][0]
        self.assertEqual((a["run"]["id"], a["run"]["attempt"], a["run"]["conclusion"]), (1, 2, "success"))

    def test_failed_gate_still_fails_when_not_rerun(self):
        listings = [{"a.yml": [run(1, "completed", "failure")], "b.yml": [run(2, "in_progress", None)]},
                    {"a.yml": [run(1, "completed", "failure")], "b.yml": [run(2, "completed", "success")]}]
        with tempfile.TemporaryDirectory() as d:
            root = mini_repo(d, self.WF)
            rep = g.evaluate(seq_reader(["a/x", "b/y"], listings), root, 1, SHA, 3600,
                             sleep=lambda s: None, policy=self.policy(), base_ref="master")
        self.assertEqual(rep["verdict"], g.FAIL)


class DecidingRunLink(unittest.TestCase):
    """#886 (1): link the deciding run; the full JSON goes to --out only."""

    def test_run_ref_links_the_exact_attempt(self):
        ref = g.run_ref(run(77, "completed", "failure", attempt=3), REPO)
        self.assertEqual(ref["url"], f"https://github.com/{REPO}/actions/runs/77/attempts/3")
        bare = g.run_ref({"id": 5, "status": "completed", "conclusion": "success"}, REPO)
        self.assertEqual(bare["url"], f"https://github.com/{REPO}/actions/runs/5")
        self.assertIsNone(g.run_ref(None, REPO))
        self.assertEqual(g.run_link(None), "—")
        self.assertEqual(g.run_link(ref), f"[run 77 attempt 3]({ref['url']})")

    def test_fail_line_names_conclusion_and_link(self):
        gate = {"workflow": ".github/workflows/a.yml", "name": "A", "state": g.FAIL,
                "run": g.run_ref(run(9, "completed", "timed_out"), REPO)}
        line = g.fail_line(gate)
        self.assertTrue(line.startswith("::error title=GOGREEN enforced gate FAIL::A — timed_out — https://"))
        self.assertIn("/actions/runs/9/attempts/1", line)
        self.assertEqual(g.fail_line({"workflow": "w", "state": g.FAIL, "reason": "no terminal run"}),
                         "::error title=GOGREEN enforced gate FAIL::w — no terminal run")

    def test_main_prints_links_not_json_and_writes_full_report(self):
        wf = {"a.yml": "name: A\non:\n  pull_request:\n    paths: ['a/**']\n"}
        ledger = {"schema": g.ADMISSION_SCHEMA, "entries": [{"path": ".github/workflows/a.yml",
                                                             "disposition": g.ENFORCED}]}
        fake = seq_reader(["a/x"], [{"a.yml": [run(42, "completed", "failure")]}])
        with tempfile.TemporaryDirectory() as d:
            root = mini_repo(d, wf)
            (root / g.ADMISSION).parent.mkdir(parents=True)
            (root / g.ADMISSION).write_text(json.dumps(ledger), encoding="utf-8", newline="\n")
            out, summ = root / "rep.json", root / "summary.md"
            buf = io.StringIO()
            with mock.patch("urllib.request.urlopen", fake.opener), \
                    mock.patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summ), "GITHUB_TOKEN": ""}), \
                    contextlib.redirect_stdout(buf):
                rc = g.main(["--repo", REPO, "--pr", "1", "--sha", SHA, "--root", str(root),
                             "--policy", "head", "--deadline-min", "0", "--out", str(out)])
            text, report, summary = buf.getvalue(), json.loads(out.read_text(encoding="utf-8")), summ.read_text("utf-8")
        link = f"https://github.com/{REPO}/actions/runs/42/attempts/1"
        self.assertEqual(rc, 1)
        self.assertNotIn('"schema"', text)
        self.assertLess(len(text.splitlines()), 10)
        self.assertIn(f"::error title=GOGREEN enforced gate FAIL::A — failure — {link}", text)
        self.assertEqual(report["gates"][0]["run"]["url"], link)
        self.assertIn(f"[run 42 attempt 1]({link})", summary)


def agg_reader(agg_runs, calls=None, posts=None):
    """Fake API for `recheck`: the aggregator workflow's runs on one head, plus POST capture."""
    def opener(req, timeout):
        u = req.full_url
        if calls is not None:
            calls.append((req.get_method(), u))
        if req.get_method() == "POST":
            posts.append(u)
            return io.BytesIO(b"")
        if "/actions/workflows/gogreen-required-gate.yml/runs?head_sha=" + SHA in u:
            return io.BytesIO(json.dumps({"total_count": len(agg_runs), "workflow_runs": agg_runs}).encode())
        raise AssertionError("unexpected GET " + u)
    return g.Reader(REPO, token="", opener=opener)


class Recheck(unittest.TestCase):
    """#886 (3): a gate turning green re-runs the latest FAILED aggregator run on that head."""

    def test_reruns_latest_failed_aggregator_run(self):
        posts = []
        t0, t1 = "2026-10-25T00:00:00Z", "2026-10-25T01:00:00Z"
        runs = [run(10, "completed", "success", created=t0, started=t0), run(11, "completed", "failure", created=t1, started=t1)]
        out = g.recheck(agg_reader(runs, posts=posts), SHA)
        self.assertEqual(out["action"], "rerun")
        self.assertEqual(posts, [f"https://api.github.com/repos/{REPO}/actions/runs/11/rerun"])
        self.assertEqual(out["aggregator_run"]["id"], 11)

    def test_nothing_to_do(self):
        t0, t1 = "2026-10-25T00:00:00Z", "2026-10-25T01:00:00Z"
        cases = {
            "no aggregator run": [],
            "still in progress": [run(1, "in_progress", None)],
            "concluded success": [run(1, "completed", "failure", created=t0, started=t0),
                                  run(2, "completed", "success", created=t1, started=t1)],
            "concluded cancelled": [run(1, "completed", "cancelled")],
            "cap": [run(1, "completed", "failure", attempt=g.RECHECK_MAX_ATTEMPT)],
        }
        for why, runs in cases.items():
            with self.subTest(why):
                posts = []
                out = g.recheck(agg_reader(runs, posts=posts), SHA)
                self.assertEqual((out["action"], posts), ("none", []))
                self.assertTrue(out["reason"])

    def test_red_trigger_makes_no_call_at_all(self):
        calls = []
        out = g.recheck(agg_reader([run(1, "completed", "failure")], calls=calls, posts=[]), SHA, "failure")
        self.assertEqual((out["action"], calls), ("none", []))

    def test_dry_run_and_sha_validation(self):
        posts = []
        out = g.recheck(agg_reader([run(1, "completed", "failure")], posts=posts), SHA, dry_run=True)
        self.assertEqual((out["action"], posts), ("dry-run", []))
        for bad in ("", "abc", SHA + "&event=push", "A" * 40):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                g.recheck(agg_reader([]), bad)

    def test_cli_prints_one_line(self):
        posts = []
        fake = agg_reader([run(5, "completed", "failure")], posts=posts)
        buf = io.StringIO()
        with mock.patch("urllib.request.urlopen", fake.opener), mock.patch.dict(os.environ, {"GITHUB_TOKEN": ""}), \
                contextlib.redirect_stdout(buf):
            os.environ.pop("GITHUB_STEP_SUMMARY", None)  # restored by patch.dict
            rc = g.main(["recheck", "--repo", REPO, "--sha", SHA])
        self.assertEqual(rc, 0)
        self.assertEqual(len(posts), 1)
        self.assertTrue(buf.getvalue().startswith("recheck rerun: "))



class RecheckReceiptRelevance(unittest.TestCase):
    """P0 proof: a red aggregator receipt can distinguish related from unrelated green events.

    This is NOT live trigger deduplication. Current workflow_run events still create runs.
    """

    FAILING = ".github/workflows/failing.yml"
    OTHER = ".github/workflows/other.yml"

    def report(self, state=g.FAIL):
        return {"schema": "gogreen.required_gate.v2",
                "head_sha": SHA, "merge_authorized": False, "verdict": g.FAIL,
                "gates": [{"workflow": self.FAILING, "state": state},
                          {"workflow": self.OTHER, "state": g.FAIL}]}

    def choose(self, report=None, path=None):
        return g.receipt_recheck_relevance(
            self.report() if report is None else report,
            sha=SHA, workflow_path=path or self.FAILING)

    def test_failed_or_missing_required_gate_qualifies_for_recheck(self):
        for state in (g.FAIL, g.WAIT):
            with self.subTest(state=state):
                choice = self.choose(self.report(state))
                self.assertEqual(choice["decision"], g.RECHECK_ELIGIBLE)
                self.assertFalse(choice["merge_authorized"])
                self.assertEqual(choice["head_sha"], SHA)

    def test_already_passed_or_not_applicable_is_irrelevant_to_other_red(self):
        for state in (g.PASS, g.NA):
            with self.subTest(state=state):
                choice = self.choose(self.report(state))
                self.assertEqual(choice["decision"], g.RECHECK_ALREADY_SATISFIED)
                self.assertIn("did not contribute", choice["reason"])

    def test_bad_or_stale_receipt_is_unknown_not_a_permission_to_skip(self):
        cases = [
            {}, {"schema": "unexpected"}, self.report(),
            {**self.report(), "head_sha": BASE},
            {**self.report(), "merge_authorized": True},
            {**self.report(), "verdict": g.PASS},
            {**self.report(), "gates": []},
            {**self.report(), "gates": [*self.report()["gates"], self.report()["gates"][0]]},
            {**self.report(), "gates": [{"workflow": self.FAILING, "state": "UNDETERMINED"}]},
            {**self.report(), "gates": [1, 2, 3]},
        ]
        # The third case is changed below: a valid receipt is not UNKNOWN.
        cases.pop(2)
        for i, bad in enumerate(cases):
            with self.subTest(case=i):
                self.assertEqual(self.choose(bad)["decision"], g.RECHECK_UNKNOWN)
        self.assertEqual(self.choose(self.report(), path="../../gate.yml")["decision"], g.RECHECK_UNKNOWN)
        self.assertEqual(
            g.receipt_recheck_relevance(self.report(), sha=BASE, workflow_path=self.FAILING)["decision"],
            g.RECHECK_UNKNOWN)
        self.assertEqual(self.choose(self.report(), path=self.OTHER)["decision"], g.RECHECK_ELIGIBLE)

    def test_observed_gate_not_in_enforced_receipt_is_unknown(self):
        self.assertEqual(
            self.choose(self.report(), path=".github/workflows/observed.yml")["decision"],
            g.RECHECK_UNKNOWN)

    def test_offline_cli_requires_evidence_but_never_calls_github(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "required-gate.json"
            path.write_text(json.dumps(self.report(g.PASS)), encoding="utf-8", newline="\n")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = g.main(["recheck-receipt", "--report", str(path),
                             "--sha", SHA, "--workflow", self.FAILING])
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(out.getvalue())["decision"], g.RECHECK_ALREADY_SATISFIED)
            path.write_text('{"schema":"unexpected"}', encoding="utf-8", newline="\n")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = g.main(["recheck-receipt", "--report", str(path),
                             "--sha", SHA, "--workflow", self.FAILING])
            self.assertEqual(rc, 2)
            self.assertEqual(json.loads(out.getvalue())["decision"], g.RECHECK_UNKNOWN)



class RecheckWorkflow(unittest.TestCase):
    WF = ROOT / g.RECHECK

    def test_trigger_names_in_sync_with_enforced_ledger(self):
        pol = g.policy_from_doc(json.loads((ROOT / g.ADMISSION).read_text(encoding="utf-8")), "head")
        want = g.recheck_names(ROOT, pol)
        text = self.WF.read_text(encoding="utf-8")
        self.assertEqual(g.declared_recheck_names(text), want,
                         "out of sync: python mission-control/gogreen/required_gate/gate.py recheck-names --write")
        self.assertEqual(yaml.safe_load(text)[True]["workflow_run"]["workflows"], want)
        self.assertGreaterEqual(len(want), len(g.GUARDED))
        self_name = g.triggers(ROOT / g.SELF)["name"]
        self.assertNotIn(self_name, want, "the aggregator must never trigger its own re-check")

    def test_render_rewrites_only_the_block(self):
        text = "a: 1\n    # BEGIN recheck-names\n    - \"old\"\n    # END recheck-names\nb: 2\n"
        new = g.render_recheck_names(text, ["X (y)", "Z/W"])
        self.assertEqual(new, "a: 1\n    # BEGIN recheck-names\n    - \"X (y)\"\n    - \"Z/W\"\n"
                              "    # END recheck-names\nb: 2\n")
        self.assertEqual(g.declared_recheck_names(new), ["X (y)", "Z/W"])
        with self.assertRaises(ValueError):
            g.declared_recheck_names("no markers\n")

    def test_privileged_job_shape(self):
        text = self.WF.read_text(encoding="utf-8")
        doc = yaml.safe_load(text)
        self.assertEqual(set(doc[True]), {"workflow_run"})
        self.assertEqual(doc[True]["workflow_run"]["types"], ["completed"])
        self.assertEqual(doc["permissions"], {"contents": "read"})
        self.assertNotIn("needs.", text)
        (job,) = doc["jobs"].values()
        self.assertEqual(job["permissions"], {"contents": "read", "actions": "write"})
        self.assertIn("workflow_run.event == 'pull_request'", job["if"])
        self.assertIn("workflow_run.conclusion == 'success'", job["if"])
        steps = job["steps"]
        self.assertRegex(steps[0]["uses"], r"^actions/checkout@[0-9a-f]{40}$")
        self.assertEqual(steps[0]["with"]["ref"], "${{ github.sha }}")
        self.assertIs(steps[0]["with"]["persist-credentials"], False)
        self.assertIn('"$actual" != "$EXPECTED_SHA"', steps[1]["run"])
        self.assertEqual(steps[1]["env"]["EXPECTED_SHA"], "${{ github.sha }}")
        for s in steps:
            if "run" in s:  # event values reach shell only through env
                self.assertNotIn("${{", s["run"])
            if "uses" in s:
                self.assertRegex(s["uses"], r"@[0-9a-f]{40}$")


if __name__ == "__main__":
    unittest.main()



class RecheckStormControl(unittest.TestCase):
    def test_concurrency_cancels_overlaps_but_does_not_prevent_workflow_run_events(self):
        """Cancellation reduces overlapping jobs but NOT the number of triggered workflow runs."""
        workflow = yaml.safe_load((ROOT / g.RECHECK).read_text(encoding="utf-8"))
        concurrency = workflow["concurrency"]
        self.assertIn("github.event.workflow_run.head_sha", concurrency["group"])
        self.assertIs(concurrency["cancel-in-progress"], True)
        job = workflow["jobs"]["recheck"]
        self.assertEqual(job["permissions"]["actions"], "write")
        self.assertEqual(workflow["permissions"]["contents"], "read")
        self.assertIn("github.event.workflow_run.event == 'pull_request'", job["if"])
        self.assertIn("github.event.workflow_run.conclusion == 'success'", job["if"])
        self.assertIn("--sha", job["steps"][-1]["run"])
        self.assertIn("--conclusion", job["steps"][-1]["run"])
        self.assertNotIn("continue-on-error", job)
