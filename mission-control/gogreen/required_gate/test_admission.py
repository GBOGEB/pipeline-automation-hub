"""Offline controls for the admission ledger (trust -> authority) and the gate backtest."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import admission as a  # noqa: E402
import backtest as b  # noqa: E402
import gate as g  # noqa: E402

PR = "on:\n  pull_request:\n    paths: ['{p}/**']\njobs: {{}}\n"


def repo(d, extra=None):
    w = Path(d) / ".github" / "workflows"
    w.mkdir(parents=True)
    files = {
        "healthy.yml": ("name: H\non:\n  pull_request:\n    paths: ['h/**']\njobs:\n  a:\n"
                        "    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n"),
        "red.yml": "name: R\n" + PR.format(p="r"),
        "flaky.yml": "name: F\n" + PR.format(p="f"),
        "fresh.yml": "name: N\n" + PR.format(p="n"),
        "pushonly.yml": "name: P\non:\n  push: {}\n",
        "target.yml": "name: T\non:\n  pull_request_target: {}\n",
        "info.yml": "name: I\n# gogreen-admission: observe\n" + PR.format(p="i"),
        "release.yml": "name: Rel\non:\n  pull_request:\n    branches: [release]\n",
        "gogreen-required-gate.yml": "name: G\non:\n  pull_request: {}\n",
        "code-purple-method-atlas.yml": "name: Atlas\n" + PR.format(p="atlas"),
        "live-lossless-qa.yml": "name: LL\n" + PR.format(p="ll"),
    }
    files.update(extra or {})
    for k, v in files.items():
        (w / k).write_text(v)
    return Path(d)


def wf(path, cls, current, streak=3, age=0.5, nd=False, pins=(), **kw):
    return dict({"path": f".github/workflows/{path}", "class": cls, "current": current, "green_streak": streak,
                 "latest_age_days": age, "latest": {"sha": "c" * 40},
                 "nondeterminism": {"nondeterministic": nd, "same_head_disagreements": int(nd), "rerun_rescues": 0},
                 "pinned_historical_ids": list(pins)}, **kw)


MASTER = {"schema": "gogreen.red_trace.v1", "digest_sha256": "m", "observed_at_utc": "2026-10-20T00:00:00Z",
          "window": {}, "workflows": [
              wf("healthy.yml", "STABLE_GREEN", "GREEN"), wf("red.yml", "GREEN_TO_RED", "RED", streak=0),
              wf("flaky.yml", "FLAKY", "GREEN", nd=True), wf("info.yml", "STABLE_GREEN", "GREEN"),
              wf("code-purple-method-atlas.yml", "FLAKY", "GREEN", streak=9),
              wf("live-lossless-qa.yml", "RED_TO_GREEN", "GREEN", streak=1)]}
PRL = {"schema": "gogreen.red_trace.pr_lane.v1", "digest_sha256": "p", "observed_at_utc": "2026-10-20T00:00:00Z",
       "window": {}, "workflows": [wf("fresh.yml", "STABLE_GREEN", "GREEN", streak=4, merged_red_prs=[], latest_pr=9),
                                   wf("healthy.yml", "STABLE_GREEN", "GREEN", merged_red_prs=[], latest_pr=9)]}


class Ledger(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = repo(self.tmp.name)
        self.doc = a.build(self.root, MASTER, PRL, None, {"actions/checkout@v4": "node20"})
        self.e = {Path(x["path"]).name: x for x in self.doc["entries"]}

    def tearDown(self):
        self.tmp.cleanup()

    def test_every_file_dispositioned(self):
        self.assertEqual(len(self.doc["entries"]), 11)
        self.assertEqual(self.doc["coverage"]["dispositioned"], self.doc["coverage"]["workflow_files"])
        self.assertTrue(all(x["disposition"] in (g.ENFORCED, g.OBSERVED, g.EXCLUDED) and x["reasons"]
                            for x in self.doc["entries"]))

    def test_dispositions_follow_evidence(self):
        d = {k: (v["disposition"], v["reasons"]) for k, v in self.e.items()}
        self.assertEqual(d["healthy.yml"], (g.ENFORCED, ["EVIDENCE_HEALTHY"]))
        self.assertEqual(d["fresh.yml"], (g.ENFORCED, ["EVIDENCE_HEALTHY"]))          # PR-lane evidence only
        self.assertEqual(d["red.yml"], (g.OBSERVED, ["RED_NOW_MASTER"]))
        self.assertEqual(d["flaky.yml"], (g.OBSERVED, ["NONDETERMINISTIC_MASTER"]))
        self.assertEqual(d["info.yml"], (g.OBSERVED, ["DECLARED_INFORMATIONAL"]))
        self.assertEqual(d["pushonly.yml"], (g.EXCLUDED, ["NO_PULL_REQUEST_TRIGGER"]))
        self.assertEqual(d["target.yml"], (g.EXCLUDED, ["PULL_REQUEST_TARGET_ONLY"]))
        self.assertEqual(d["release.yml"], (g.EXCLUDED, ["NOT_FOR_MASTER"]))
        self.assertEqual(d["gogreen-required-gate.yml"], (g.EXCLUDED, ["SELF"]))

    def test_repair_oscillation_still_enforced(self):
        self.assertEqual(self.e["code-purple-method-atlas.yml"]["disposition"], g.ENFORCED)
        self.assertEqual(self.e["code-purple-method-atlas.yml"]["reasons"], ["EVIDENCE_HEALTHY"])

    def test_incumbent_ratchet_never_auto_demotes(self):
        ll = self.e["live-lossless-qa.yml"]  # bootstrap incumbent, streak 1 < MIN_STREAK
        self.assertEqual(ll["disposition"], g.ENFORCED)
        self.assertEqual(ll["reasons"], ["INCUMBENT_RATCHET"])
        self.assertEqual(ll["demotion_candidate"], ["GREEN_STREAK_SHORT"])
        # promoted entries become incumbents of the next generation
        nxt = a.build(self.root, {"workflows": [wf("healthy.yml", "GREEN_TO_RED", "RED", streak=0)]}, None,
                      self.doc, {})
        h = {Path(x["path"]).name: x for x in nxt["entries"]}["healthy.yml"]
        self.assertEqual((h["disposition"], h["demotion_candidate"]), (g.ENFORCED, ["RED_NOW_MASTER"]))
        self.assertIn(".github/workflows/healthy.yml", a.diff(self.doc, nxt)["demotion_candidates"])

    def test_stale_and_pinned_and_no_evidence_observed(self):
        doc = a.build(self.root, {"workflows": [wf("healthy.yml", "STABLE_GREEN", "GREEN", age=30),
                                                 wf("red.yml", "STABLE_GREEN", "GREEN", pins=["123456789"])]},
                      None, {"entries": []}, {})
        e = {Path(x["path"]).name: x for x in doc["entries"]}
        self.assertEqual(e["healthy.yml"]["reasons"], ["NOT_EXERCISED_RECENTLY"])
        self.assertEqual(e["red.yml"]["reasons"], ["PINNED_EVIDENCE"])
        self.assertEqual(e["fresh.yml"]["reasons"], ["NO_TERMINAL_EVIDENCE"])

    def test_runtime_debt_and_gate_compatibility(self):
        self.assertEqual(self.e["healthy.yml"]["node20_uses"], ["actions/checkout@v4"])
        self.assertEqual(self.doc["runtime_debt"]["node20_workflows"], 1)
        pol = g.policy_from_doc(self.doc, "t")  # the gate accepts what admission writes
        self.assertEqual(pol["entries"][".github/workflows/healthy.yml"], g.ENFORCED)
        self.assertFalse(self.doc["authority"]["merge_authorized"])
        self.assertIn("all dispositioned", a.markdown(self.doc, a.diff(None, self.doc)))

    def test_deterministic(self):
        again = a.build(self.root, MASTER, PRL, None, {"actions/checkout@v4": "node20"})
        self.assertEqual(again["ledger_sha256"], self.doc["ledger_sha256"])

    def test_uses_parser(self):
        text = ("steps:\n  - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683\n"
                "  - uses: 'github/codeql-action/init@v3'\n  - uses: ./local\n  - uses: docker://alpine:3\n")
        self.assertEqual(a.uses(text), ["actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683",
                                        "github/codeql-action/init@v3"])
        self.assertEqual(a.resolve_runtime("not a ref"), "UNRESOLVED")


class Backtest(unittest.TestCase):
    def test_replay_uses_gate_logic_and_policies(self):
        with tempfile.TemporaryDirectory() as d:
            root = repo(d)
            lane = {"repository": "x/y", "base": "master", "digest_sha256": "p",
                    "census": {"created_at": {".github/workflows/fresh.yml": "2026-10-19T05:00:00Z"}},
                    "merge_matrix": [
                        {"pr": 1, "merged_at": "2026-10-19T01:00:00Z",
                         "at_merge": {".github/workflows/code-purple-method-atlas.yml": "failure"}},
                        {"pr": 2, "merged_at": "2026-10-19T02:00:00Z",
                         "at_merge": {".github/workflows/healthy.yml": "pending_at_merge"}},
                        {"pr": 3, "merged_at": "2026-10-19T03:00:00Z", "at_merge": {}},
                        {"pr": 4, "merged_at": "2026-10-19T04:00:00Z",
                         "at_merge": {".github/workflows/healthy.yml": "success"}},
                        {"pr": 5, "merged_at": "2026-10-19T04:30:00Z", "at_merge": {}}]}
            files = {1: ["atlas/x.py"], 2: ["h/x"], 3: ["h/y", "README.md"], 4: ["h/z"], 5: ["n/x"]}
            ledger = a.build(root, MASTER, PRL, None, {})
            rep = b.run(root, lane, ledger, files, limit=10)
            boot, led = rep["policies"]["bootstrap_n8"], rep["policies"]["admission_ledger"]
            self.assertEqual(boot["summary"]["would_fail"], 1)               # only PR 1 (atlas red)
            self.assertEqual(boot["summary"]["would_have_caught_red"], 1)
            self.assertEqual(led["summary"]["would_fail"], 3)                # 1 red, 2 pending, 3 absent
            self.assertEqual(led["summary"]["by_reason"],
                             {"ABSENT_OR_FILTER_DRIFT": 1, "PENDING_AT_MERGE": 1, "RED_AT_MERGE": 1})
            # fresh.yml did not exist yet when PR 5 merged -> not applicable, not ABSENT
            self.assertNotIn(5, [r["pr"] for r in led["failing_prs"]])
            self.assertFalse(rep["authority"]["merge_authorized"])
            self.assertIn("would have answered", b.markdown(rep))
            # healthy.yml first ran on base after PR 3 merged -> not applicable, ABSENT disappears
            master = {"workflows": [{"path": ".github/workflows/healthy.yml", "first_observed_at": "2026-10-19T03:30:00Z",
                                     "history_truncated": False}]}
            rep2 = b.run(root, lane, ledger, files, limit=10, master=master)
            self.assertNotIn("ABSENT_OR_FILTER_DRIFT", rep2["policies"]["admission_ledger"]["summary"]["by_reason"])
            truncated = {"workflows": [dict(master["workflows"][0], history_truncated=True)]}
            rep3 = b.run(root, lane, ledger, files, limit=10, master=truncated)
            self.assertIn("ABSENT_OR_FILTER_DRIFT", rep3["policies"]["admission_ledger"]["summary"]["by_reason"])


if __name__ == "__main__":
    unittest.main()
