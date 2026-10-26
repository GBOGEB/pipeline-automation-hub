"""Safety controls for the GOGREEN bounded replay lane (offline, fake API, temp workflows)."""
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import replay_lane as rl  # noqa: E402

REPO = "GBOGEB/pipeline-automation-hub"
NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
POLICY = json.loads((HERE / "REPLAY_POLICY.json").read_text(encoding="utf-8"))

RO = "permissions:\n  contents: read\n  actions: read\n"
WF = {
    "ok1.yml": "on:\n  workflow_dispatch:\n" + RO + "jobs: {a: {runs-on: x}}\n",
    "ok2.yml": "on:\n  workflow_dispatch:\n" + RO + "jobs: {a: {runs-on: x}}\n",
    "ok3.yml": "on:\n  workflow_dispatch:\n" + RO + "jobs: {a: {runs-on: x}}\n",
    "ok4.yml": "on:\n  workflow_dispatch:\n" + RO + "jobs: {a: {runs-on: x}}\n",
    "nodisp.yml": "on:\n  push: {}\n" + RO + "jobs: {}\n",
    "req.yml": "on:\n  workflow_dispatch:\n    inputs:\n      x: {required: true}\n" + RO + "jobs: {}\n",
    "write.yml": "on:\n  workflow_dispatch:\npermissions:\n  contents: write\njobs: {}\n",
    "jobwrite.yml": "on:\n  workflow_dispatch:\n" + RO + "jobs:\n  a:\n    permissions:\n      pull-requests: write\n",
    "noperm.yml": "on:\n  workflow_dispatch:\njobs: {}\n",
    "writeall.yml": "on:\n  workflow_dispatch:\npermissions: write-all\njobs: {}\n",
    "pinned.yml": "on:\n  workflow_dispatch:\n" + RO + "jobs: {}\n",
    "recent.yml": "on:\n  workflow_dispatch:\n" + RO + "jobs: {}\n",
    "busy.yml": "on:\n  workflow_dispatch:\n" + RO + "jobs: {}\n",
}


def wf(name, day=10, current="RED", **kw):
    return dict({"name": name, "path": f".github/workflows/{name}", "class": "GREEN_TO_RED", "current": current,
                 "latest": {"at": f"2026-10-{day:02d}T00:00:00Z", "sha": "a" * 40}}, **kw)


def trace(workflows):
    return {"schema": "gogreen.red_trace.v1", "branch": "master", "digest_sha256": "d" * 64, "workflows": workflows}


class Fake:
    def __init__(self, queued=0, recent=None, busy=None):
        self.queued, self.recent, self.busy = queued, recent or {}, busy or {}
        self.writes = []

    def opener(self, req, timeout):
        u = req.full_url
        if req.get_method() == "POST":
            self.writes.append((u, json.loads(req.data)))
            return io.BytesIO(b"")
        if "/actions/runs?status=queued" in u:
            body = {"total_count": self.queued}
        elif "event=workflow_dispatch" in u:
            name = u.split("/workflows/")[1].split("/")[0]
            body = {"workflow_runs": [{"created_at": self.recent[name]}] if name in self.recent else []}
        elif "status=queued" in u or "status=in_progress" in u:
            name = u.split("/workflows/")[1].split("/")[0]
            body = {"total_count": self.busy.get(name, 0) if "queued" in u else 0}
        else:
            raise AssertionError(u)
        return io.BytesIO(json.dumps(body).encode())

    def api(self):
        return rl.Api(REPO, token="", opener=self.opener)


class Lane(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".github/workflows").mkdir(parents=True)
        for n, t in WF.items():
            (self.root / ".github/workflows" / n).write_text(t, encoding="utf-8", newline="\n")

    def tearDown(self):
        self.tmp.cleanup()

    def plan(self, workflows, fake=None, policy=POLICY):
        fake = fake or Fake()
        return rl.plan(trace(workflows), self.root, policy, fake.api(), now=NOW), fake

    def reasons(self, rep):
        return {Path(r["path"]).name: r["skip"] for r in rep["rows"]}

    def test_every_safety_gate(self):
        ws = [wf(n) for n in ("nodisp.yml", "req.yml", "write.yml", "jobwrite.yml", "noperm.yml", "writeall.yml")]
        ws += [wf("pinned.yml", pinned_historical_ids=["35171901674"]), wf("ok1.yml", day=19), wf("ok2.yml", current="GREEN"),
               wf("gm-iv-recon4-governor.yml")]
        rep, _ = self.plan(ws)
        r = self.reasons(rep)
        self.assertIn("no workflow_dispatch", r["nodisp.yml"])
        self.assertIn("required dispatch inputs x", r["req.yml"])
        self.assertIn("writes contents", r["write.yml"])
        self.assertIn("writes pull-requests", r["jobwrite.yml"])
        self.assertIn("default token permissions", r["noperm.yml"])
        self.assertIn("write-all", r["writeall.yml"])
        self.assertIn("pinned", r["pinned.yml"])
        self.assertIn("fresh red", r["ok1.yml"])
        self.assertNotIn("ok2.yml", r, "green workflows are never considered")
        self.assertIn("denied", r["gm-iv-recon4-governor.yml"])
        self.assertEqual(rep["dispatch"], [])

    def test_budget_oldest_first(self):
        ws = [wf("ok1.yml", day=12), wf("ok2.yml", day=5), wf("ok3.yml", day=9), wf("ok4.yml", day=1)]
        rep, _ = self.plan(ws)
        self.assertEqual([Path(p).name for p in rep["dispatch"]], ["ok4.yml", "ok2.yml", "ok3.yml"])
        self.assertIn("budget", self.reasons(rep)["ok1.yml"])

    def test_rate_limit_and_busy(self):
        fake = Fake(recent={"recent.yml": "2026-10-20T02:00:00Z"}, busy={"busy.yml": 1})
        rep, _ = self.plan([wf("recent.yml"), wf("busy.yml"), wf("ok1.yml")], fake)
        r = self.reasons(rep)
        self.assertIn("rate: replayed 10.0 h ago", r["recent.yml"])
        self.assertIn("already queued", r["busy.yml"])
        self.assertEqual([Path(p).name for p in rep["dispatch"]], ["ok1.yml"])

    def test_backpressure_skips_whole_lane(self):
        rep, _ = self.plan([wf("ok1.yml")], Fake(queued=41))
        self.assertEqual(rep["lane"], "SKIPPED_BACKPRESSURE")
        self.assertEqual(rep["dispatch"], [])
        self.assertIn("back-pressure", self.reasons(rep)["ok1.yml"])

    def test_main_dry_run_never_writes_and_live_writes_only_dispatch(self):
        t = self.root / "trace.json"
        t.write_text(json.dumps(trace([wf("ok1.yml"), wf("ok2.yml")])), encoding="utf-8", newline="\n")
        for dry in (True, False):
            fake = Fake()
            api = fake.api()
            orig = rl.Api
            rl.Api = lambda repo: api
            try:
                args = ["--repo", REPO, "--trace", str(t), "--root", str(self.root), "--out", str(self.root / "o.json")]
                rl.main(args + (["--dry-run"] if dry else []))
            finally:
                rl.Api = orig
            rep = json.loads((self.root / "o.json").read_text(encoding="utf-8"))
            if dry:
                self.assertEqual(fake.writes, [])
                self.assertEqual(rep["dispatched"], [])
            else:
                self.assertEqual(len(fake.writes), 2)
                for url, body in fake.writes:
                    self.assertRegex(url, r"/repos/GBOGEB/pipeline-automation-hub/actions/workflows/ok[12]\.yml/dispatches$")
                    self.assertEqual(body, {"ref": "master"})
            self.assertFalse(rep["merge_authorized"])

    def test_refuses_non_default_branch_trace(self):
        t = self.root / "trace.json"
        t.write_text(json.dumps(dict(trace([]), branch="feature")), encoding="utf-8", newline="\n")
        with self.assertRaises(SystemExit):
            rl.main(["--repo", REPO, "--trace", str(t), "--root", str(self.root), "--out", str(self.root / "o.json")])

    def test_dispatch_path_guard(self):
        with self.assertRaises(ValueError):
            Fake().api().dispatch(".github/workflows/../../x", "master")

    def test_no_cascade_dispatchers_refused(self):
        (self.root / ".github/workflows/disp.yml").write_text("on:\n  workflow_dispatch:\npermissions:\n  actions: write\n  contents: read\njobs: {}\n", encoding="utf-8", newline="\n")
        rep, _ = self.plan([wf("disp.yml")])
        self.assertIn("writes actions", self.reasons(rep)["disp.yml"])

    def test_repo_lane_workflow_is_refused_by_its_own_permissions(self):
        repo_root = HERE.parents[2]
        f = rl.workflow_facts(repo_root, ".github/workflows/gogreen-replay-lane.yml")
        self.assertTrue(set(f["writes"]) - set(POLICY["allowed_permission_writes"]))

    def test_repo_policy_denies_lane_itself_and_superseded_gate(self):
        self.assertIn(".github/workflows/gogreen-replay-lane.yml", POLICY["deny"])
        self.assertIn(".github/workflows/gm-iv-recon4-governor.yml", POLICY["deny"])
        self.assertLessEqual(POLICY["max_dispatches_per_run"], 3)


if __name__ == "__main__":
    unittest.main()
