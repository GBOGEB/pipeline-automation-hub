"""Offline controls for GOGREEN red-trace (synthetic run histories, no network)."""
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import red_trace as t  # noqa: E402

REPO = "GBOGEB/pipeline-automation-hub"


def sha(n):
    return f"{n:040x}"


def run(path, n, conclusion, hour, attempt=1, rid=None, status="completed"):
    return {"path": path, "name": path.split("/")[-1], "head_sha": sha(n), "id": rid or 1000 + n * 10 + attempt,
            "run_attempt": attempt, "created_at": f"2026-10-18T{hour:02d}:00:00Z", "event": "push",
            "conclusion": conclusion, "status": status}


def classify_seq(*pairs, path="w.yml"):
    runs = [run(path, i + 1, c, i) for i, c in enumerate(pairs)]
    return t.classify(t.outcomes(runs)[path])


class Classification(unittest.TestCase):
    def test_everred(self):
        c = classify_seq("failure", "failure")
        self.assertEqual(c["class"], "EVERRED")
        self.assertEqual(c["first_red"]["sha"], sha(1))

    def test_stable_green(self):
        self.assertEqual(classify_seq("success", "success")["class"], "STABLE_GREEN")

    def test_green_to_red_break_window(self):
        c = classify_seq("success", "success", "failure", "failure")
        self.assertEqual(c["class"], "GREEN_TO_RED")
        b = c["break"]
        self.assertEqual((b["last_green_sha"], b["first_red_sha"], b["red_streak_runs"]), (sha(2), sha(3), 2))

    def test_red_to_green_episode_and_duration(self):
        c = classify_seq("success", "failure", "success")
        self.assertEqual(c["class"], "RED_TO_GREEN")
        e = c["red_episodes"][-1]
        self.assertEqual((e["last_green_sha"], e["first_red_sha"], e["recovery_sha"], e["red_hours"]),
                         (sha(1), sha(2), sha(3), 1.0))

    def test_window_opens_red(self):
        c = classify_seq("failure", "success")
        self.assertEqual(c["class"], "RED_TO_GREEN")
        e = c["red_episodes"][-1]
        self.assertTrue(e["red_before_window"])
        self.assertIsNone(e["last_green_sha"])
        self.assertEqual(e["recovery_sha"], sha(2))

    def test_flaky(self):
        self.assertEqual(classify_seq("success", "failure", "success", "failure")["class"], "FLAKY")

    def test_cancelled_and_in_progress_are_never_green_or_red(self):
        c = classify_seq("success", "cancelled", "skipped", None)
        self.assertEqual(c["class"], "STABLE_GREEN")
        self.assertEqual(c["non_terminal"], 3)
        self.assertEqual(classify_seq("cancelled")["class"], "UNKNOWN_NO_TERMINAL")

    def test_timed_out_and_startup_failure_count_red(self):
        self.assertEqual(classify_seq("success", "timed_out")["class"], "GREEN_TO_RED")
        self.assertEqual(classify_seq("startup_failure")["class"], "EVERRED")


class Outcomes(unittest.TestCase):
    def test_latest_attempt_per_head_wins(self):
        runs = [run("w.yml", 1, "failure", 1, attempt=1), run("w.yml", 1, "success", 1, attempt=2)]
        seq = t.outcomes(runs)["w.yml"]
        self.assertEqual(len(seq), 1)
        self.assertEqual(seq[0]["conclusion"], "success")

    def test_malformed_rows_ignored(self):
        bad = [{"path": "w.yml", "head_sha": "short"}, {"head_sha": sha(1)}]
        self.assertEqual(t.outcomes(bad), {})


class Report(unittest.TestCase):
    def setUp(self):
        runs = []
        for p in ("a.yml", "b.yml", "c.yml"):
            runs += [run(p, 1, "success", 1), run(p, 2, "failure", 2)]
        runs += [run("d.yml", 1, "success", 1), run("d.yml", 2, "success", 2)]
        self.rep = t.build(REPO, "master", {"runs": runs, "truncated": False}, t.outcomes(runs),
                           observed_at="2026-10-18T03:00:00Z")

    def test_shared_break_root_counted_once(self):
        fan = self.rep["shared_break_roots"]
        self.assertEqual(len(fan), 1)
        self.assertEqual((fan[0]["first_red_sha"], fan[0]["count"]), (sha(2), 3))

    def test_counts_current_red_and_authority(self):
        self.assertEqual(self.rep["counts"], {"GREEN_TO_RED": 3, "STABLE_GREEN": 1})
        self.assertEqual(self.rep["currently_red"], ["a.yml", "b.yml", "c.yml"])
        self.assertFalse(self.rep["authority"]["merge_authorized"])
        self.assertIsNone(self.rep["authority"]["root_closure_credit"])

    def test_staleness(self):
        rep = t.build(REPO, "master", {"runs": [run("x.yml", 1, "failure", 0)], "truncated": False},
                      t.outcomes([run("x.yml", 1, "failure", 0)]), observed_at="2026-10-25T00:00:00Z")
        w = rep["workflows"][0]
        self.assertTrue(w["stale"])
        self.assertEqual(rep["currently_red_stale"], ["x.yml"])

    def test_markdown_lists_reds_and_shared_root(self):
        md = t.markdown(self.rep, limit_green=True)
        self.assertIn("Shared break roots", md)
        self.assertIn(sha(2)[:8], md)
        self.assertNotIn("| STABLE_GREEN | d.yml", md)

    def test_deterministic_digest(self):
        runs = [run("a.yml", 1, "success", 1)]
        a = t.build(REPO, "master", {"runs": runs, "truncated": False}, t.outcomes(runs), observed_at="2026-10-18T03:00:00Z")
        b = t.build(REPO, "master", {"runs": runs, "truncated": False}, t.outcomes(runs), observed_at="2026-10-18T03:00:00Z")
        self.assertEqual(a["digest_sha256"], b["digest_sha256"])


class Pins(unittest.TestCase):
    def test_detects_pinned_run_and_artifact(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "w.yml"
            f.write_text("curl $api/actions/runs/35171901674\n a=next(x for x in arts if x['id']==10476967287)\n")
            self.assertEqual(t.pins(f), ["10476967287", "35171901674"])
            f.write_text("run: echo ok\n")
            self.assertEqual(t.pins(f), [])
            self.assertEqual(t.pins(Path(d) / "missing.yml"), [])


class ReaderGuard(unittest.TestCase):
    def fake(self, payload):
        return lambda req, timeout: io.BytesIO(json.dumps(payload).encode())

    def test_get_only_within_repo(self):
        r = t.Reader(REPO, token="x", opener=self.fake({"ok": 1}))
        self.assertEqual(r.get(f"/repos/{REPO}/compare/{sha(1)}...{sha(2)}"), {"ok": 1})
        for bad in ("/repos/OTHER/x/actions/runs", f"/repos/{REPO}/../../user", f"/repos/{REPO}/a#b"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                r.get(bad)
        with self.assertRaises(ValueError):
            t.Reader("no-slash")

    def test_collect_records_per_workflow_truncation(self):
        pages = {"workflows": {"workflows": [{"id": 7, "path": "w.yml"}]},
                 "runs": {"total_count": 250, "workflow_runs": [run("w.yml", i + 1, "success", 0) for i in range(100)]}}
        r = t.Reader(REPO, token="", opener=lambda req, timeout: io.BytesIO(json.dumps(
            pages["runs"] if "/workflows/7/runs" in req.full_url else pages["workflows"]).encode()))
        got = t.collect(r, "master", per_workflow=100)
        self.assertTrue(got["truncated"])
        self.assertEqual(got["truncated_workflows"]["w.yml"], {"fetched": 100, "total": 250})

    def test_collect_paginates_workflow_listing(self):
        wfs=[{"id":i,"path":f"w{i}.yml"} for i in range(1,151)]
        def opener(req, timeout):
            u=req.full_url
            if "/actions/workflows?" in u:
                page=int(u.split("page=")[-1]); body={"total_count":150,"workflows":wfs[(page-1)*100:page*100]}
            else:
                body={"total_count":0,"workflow_runs":[]}
            return io.BytesIO(json.dumps(body).encode())
        r=t.Reader(REPO, token="", opener=opener)
        t.collect(r,"master",per_workflow=10)
        self.assertEqual(r.requests, 2+150)

    def test_incomplete_workflow_census_fails_closed(self):
        def opener(req, timeout):
            if "/actions/workflows?" in req.full_url:
                return io.BytesIO(json.dumps({"total_count":5,"workflows":[{"id":1,"path":"a.yml"}]}).encode())
            return io.BytesIO(json.dumps({"workflow_runs":[]}).encode())
        with self.assertRaisesRegex(ValueError,"incomplete"):
            t.collect(t.Reader(REPO, token="", opener=opener),"master",per_workflow=10)

    def test_token_not_in_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "runs.json"
            src.write_text(json.dumps([run("a.yml", 1, "success", 1)]))
            import os
            old = os.environ.get("GITHUB_TOKEN")
            os.environ["GITHUB_TOKEN"] = "ghs_SECRETVALUE"
            try:
                t.main(["--repo", REPO, "--runs-json", str(src), "--out", d, "--root", d])
            finally:
                os.environ.pop("GITHUB_TOKEN") if old is None else os.environ.__setitem__("GITHUB_TOKEN", old)
            for f in ("red_trace.json", "red_trace.md"):
                self.assertNotIn("SECRETVALUE", (Path(d) / f).read_text())


class Nondeterminism(unittest.TestCase):
    def test_same_head_disagreement_and_rerun_rescue(self):
        runs = [run("w.yml", 1, "failure", 1, rid=1), run("w.yml", 1, "success", 2, rid=2),
                run("v.yml", 2, "success", 1, attempt=2), run("u.yml", 3, "success", 1)]
        nd = t.nondeterminism(runs)
        self.assertEqual(nd["w.yml"]["same_head_disagreements"], 1)
        self.assertEqual(nd["w.yml"]["disagreeing_shas"], [sha(1)])
        self.assertEqual(nd["v.yml"]["rerun_rescues"], 1)
        self.assertTrue(nd["v.yml"]["nondeterministic"])
        self.assertFalse(nd["u.yml"]["nondeterministic"])

    def test_repair_oscillation_is_not_nondeterminism(self):
        # FLAKY by flips (code changed between heads) but each head is consistent
        runs = [run("w.yml", i + 1, c, i) for i, c in enumerate(("success", "failure", "success", "failure", "success"))]
        rep = t.build(REPO, "master", {"runs": runs, "truncated": False}, t.outcomes(runs),
                      observed_at="2026-10-18T06:00:00Z")
        w = rep["workflows"][0]
        self.assertEqual(w["class"], "FLAKY")
        self.assertFalse(w["nondeterminism"]["nondeterministic"])
        self.assertEqual(w["green_streak"], 1)

    def test_green_streak(self):
        self.assertEqual(classify_seq("failure", "success", "success")["green_streak"], 2)
        self.assertEqual(classify_seq("success", "failure")["green_streak"], 0)
        self.assertEqual(classify_seq("success", "cancelled", "success")["green_streak"], 2)


class Census(unittest.TestCase):
    def test_unobserved_workflows_are_explicit(self):
        runs = [run(".github/workflows/a.yml", 1, "success", 1)]
        meta = {".github/workflows/a.yml": {}, ".github/workflows/b.yml": {}, "dynamic/codeql": {}}
        rep = t.build(REPO, "master", {"runs": runs, "truncated": False, "workflows_meta": meta}, t.outcomes(runs),
                      observed_at="2026-10-18T03:00:00Z")
        self.assertEqual(rep["census"], {"workflows_total": 2, "observed": 1,
                                         "unobserved": [".github/workflows/b.yml"]})
        self.assertIn("Coverage: 1/2", t.markdown(rep))


def prun(path, head, conclusion, created, updated, attempt=1, rid=None, status="completed", started=None):
    return {"path": path, "name": path, "head_sha": head, "id": rid or hash((path, head, created)) % 10**8,
            "run_attempt": attempt, "created_at": created, "updated_at": updated, "status": status,
            "run_started_at": started or created, "conclusion": conclusion, "event": "pull_request"}


class PRLane(unittest.TestCase):
    M = "2026-10-19T10:00:00Z"

    def test_at_merge_chronology(self):
        h = sha(9)
        runs = [prun("a.yml", h, "success", "2026-10-19T09:00:00Z", "2026-10-19T09:10:00Z"),
                prun("b.yml", h, "failure", "2026-10-19T09:00:00Z", "2026-10-19T09:10:00Z"),
                prun("c.yml", h, "success", "2026-10-19T09:59:00Z", "2026-10-19T10:30:00Z"),   # finished after merge
                prun("d.yml", h, "success", "2026-10-19T10:01:00Z", "2026-10-19T10:05:00Z"),   # created after merge
                prun("e.yml", h, "success", "2026-10-19T09:00:00Z", "2026-10-19T11:00:00Z", attempt=2,
                     started="2026-10-19T10:50:00Z")]                                            # rerun after merge
        am = t.at_merge(runs, self.M)
        self.assertEqual({k: v["conclusion"] for k, v in am.items()},
                         {"a.yml": "success", "b.yml": "failure", "c.yml": t.PENDING_AT_MERGE,
                          "e.yml": t.RERUN_AFTER_MERGE})

    def lane(self):
        prs = []
        for i, (ca, cb) in enumerate((("success", "success"), ("success", "failure"), ("success", "success"))):
            h = sha(100 + i)
            m = f"2026-10-19T1{i}:00:00Z"
            prs.append({"number": 10 + i, "head_sha": h, "merged_at": m, "title": f"pr{i}",
                        "runs": [prun("a.yml", h, ca, f"2026-10-19T0{i}:00:00Z", f"2026-10-19T0{i}:30:00Z"),
                                 prun("b.yml", h, cb, f"2026-10-19T0{i}:00:00Z", f"2026-10-19T0{i}:30:00Z")]})
        return t.build_pr_lane(REPO, "master", {"prs": prs, "workflows_meta": {
            "a.yml": {}, "b.yml": {}, ".github/workflows/x.yml": {}}}, observed_at="2026-10-19T13:00:00Z")

    def test_pr_lane_reuses_classify_over_merged_heads(self):
        rep = self.lane()
        w = {x["path"]: x for x in rep["workflows"]}
        self.assertEqual(w["a.yml"]["class"], "STABLE_GREEN")
        self.assertEqual(w["b.yml"]["class"], "RED_TO_GREEN")
        self.assertEqual(w["b.yml"]["merged_red_prs"], [11])
        self.assertEqual(w["b.yml"]["latest_pr"], 12)
        self.assertEqual(rep["merged_with_red"], [{"pr": 11, "workflows": ["b.yml"]}])
        self.assertEqual(rep["schema"], t.PR_SCHEMA)
        self.assertFalse(rep["authority"]["merge_authorized"])
        self.assertEqual(rep["merge_matrix"][0]["merge_after_s"], 36000)
        self.assertIn("Merged with a red check at merge time: 1", t.markdown_pr_lane(rep))

    def test_merged_prs_skips_unmerged_and_validates_base(self):
        h = sha(5)
        body = [{"number": 1, "merged_at": None, "head": {"sha": h}},
                {"number": 2, "merged_at": "2026-10-19T01:00:00Z", "head": {"sha": h}, "title": "x"},
                {"number": 3, "merged_at": "2026-10-19T02:00:00Z", "head": {"sha": "short"}}]
        r = t.Reader(REPO, token="", opener=lambda req, timeout: io.BytesIO(json.dumps(body).encode()))
        self.assertEqual([p["number"] for p in t.merged_prs(r, "master", 10)], [2])
        for bad in ("", "a&b", "../x"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                t.merged_prs(r, bad, 1)

    def test_one_listing_per_merged_head(self):
        h1, h2 = sha(7), sha(8)
        def opener(req, timeout):
            u = req.full_url
            if "/pulls?" in u:
                body = [{"number": 1, "merged_at": "2026-10-19T01:00:00Z", "head": {"sha": h1}},
                        {"number": 2, "merged_at": "2026-10-19T02:00:00Z", "head": {"sha": h2}}]
            else:
                body = {"total_count": 1, "workflow_runs": [prun("a.yml", h1, "success", "2026-10-19T00:00:00Z",
                                                                  "2026-10-19T00:10:00Z")]}
            return io.BytesIO(json.dumps(body).encode())
        r = t.Reader(REPO, token="", opener=opener)
        got = t.collect_pr_lane(r, "master", 5, workflows_meta={"a.yml": {}})
        self.assertEqual(r.requests, 1 + 2)
        self.assertEqual(len(got["prs"]), 2)
        with self.assertRaises(ValueError):
            t.head_runs(r, "not-a-sha")


if __name__ == "__main__":
    unittest.main()
