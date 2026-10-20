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


if __name__ == "__main__":
    unittest.main()
