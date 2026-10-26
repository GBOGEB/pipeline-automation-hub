"""#529 G05 controls: latest-valid evidence binding, evidence DAG/scheduler, pin census (offline)."""
import io
import json
import sys
import tempfile
import unittest
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import evidence_binding as eb  # noqa: E402

ROOT = HERE.parents[1]
REPO = "GBOGEB/pipeline-automation-hub"
NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
GATE = "f" * 40


def sha(n):
    return f"{n:040x}"


def run(i, head, event="push", day=19, conclusion="success"):
    return {"id": i, "head_sha": head, "event": event, "status": "completed", "conclusion": conclusion,
            "created_at": f"2026-10-{day:02d}T05:00:00Z"}


def art(i, head, expired=False, digest="sha256:" + "a" * 64, prefix="p-"):
    return {"id": i, "name": prefix + head, "expired": expired, "digest": digest, "expires_at": "2026-11-18T00:00:00Z"}


class Fake:
    def __init__(self, runs, arts, ancestors):
        self.runs, self.arts, self.anc = runs, arts, ancestors

    def opener(self, req, timeout):
        u = req.full_url
        if "/runs?" in u:
            body = {"workflow_runs": self.runs}
        elif "/artifacts" in u:
            rid = int(u.split("/runs/")[1].split("/")[0])
            body = {"artifacts": self.arts.get(rid, [])}
        elif "/compare/" in u:
            a = u.split("/compare/")[1].split("...")[0]
            body = {"status": "ahead" if a in self.anc else "diverged"}
        else:
            raise AssertionError(u)
        return io.BytesIO(json.dumps(body).encode())

    def reader(self):
        return eb.Reader(REPO, token="", opener=self.opener)


class Resolve(unittest.TestCase):
    def test_picks_newest_valid_and_reports_rejections(self):
        a, b, c, d, e = sha(1), sha(2), sha(3), sha(4), sha(5)
        f = Fake([run(5, e, event="pull_request", day=20), run(4, d, day=20), run(3, c, day=19), run(2, b, day=18), run(1, a, day=10)],
                 {4: [art(40, d, expired=True)], 3: [art(30, c)], 2: [art(20, b)]}, ancestors={c, b, a, d})
        binding, r, ar, _ = eb.resolve(f.reader(), "w.yml", "p-", GATE, now=NOW)
        self.assertEqual((binding["run_id"], binding["artifact_id"]), (3, 30))
        self.assertFalse(binding["pinned_ids_used"])
        reasons = {x["run_id"]: x["reason"] for x in binding["rejected_newer_candidates"]}
        self.assertEqual(reasons[5], "event pull_request")
        self.assertIn("expired", reasons[4])

    def test_non_ancestor_rejected(self):
        a = sha(1)
        f = Fake([run(1, a)], {1: [art(10, a)]}, ancestors=set())
        with self.assertRaisesRegex(eb.EvidenceError, "NO_VALID_EVIDENCE"):
            eb.resolve(f.reader(), "w.yml", "p-", GATE, now=NOW)

    def test_too_old_rejected_fail_closed(self):
        a = sha(1)
        f = Fake([run(1, a, day=1)], {1: [art(10, a)]}, ancestors={a})
        with self.assertRaises(eb.EvidenceError):
            eb.resolve(f.reader(), "w.yml", "p-", GATE, now=NOW, max_age_days=14)

    def test_artifact_name_must_bind_run_head(self):
        a = sha(1)
        f = Fake([run(1, a)], {1: [dict(art(10, a), name="p-" + sha(9))]}, ancestors={a})
        with self.assertRaises(eb.EvidenceError):
            eb.resolve(f.reader(), "w.yml", "p-", GATE, now=NOW)

    def test_undigested_artifact_rejected(self):
        a = sha(1)
        f = Fake([run(1, a)], {1: [art(10, a, digest=None)]}, ancestors={a})
        with self.assertRaises(eb.EvidenceError):
            eb.resolve(f.reader(), "w.yml", "p-", GATE, now=NOW)

    def test_gate_sha_and_producer_validated(self):
        f = Fake([], {}, set())
        with self.assertRaises(eb.EvidenceError):
            eb.resolve(f.reader(), "w.yml", "p-", "abc", now=NOW)
        with self.assertRaises(eb.EvidenceError):
            eb.resolve(f.reader(), "../x", "p-", GATE, now=NOW)

    def test_cli_writes_fail_receipt_and_exit_1(self):
        with tempfile.TemporaryDirectory() as t:
            orig = eb.Reader
            fake = Fake([], {}, set()).reader()
            eb.Reader = lambda repo: fake
            try:
                rc = eb.main(["resolve", "--repo", REPO, "--producer", "w.yml", "--artifact-prefix", "p-",
                              "--source-sha", GATE, "--binding-out", f"{t}/b.json"])
            finally:
                eb.Reader = orig
            self.assertEqual(rc, 1)
            b = json.loads(Path(t, "b.json").read_text())
            self.assertEqual(b["result"], "FAIL")
            self.assertFalse(b["merge_authorized"])


class Dag(unittest.TestCase):
    def test_repo_dag_passes(self):
        rep = eb.dag_check(ROOT)
        self.assertTrue(rep["ok"], rep["problems"])
        self.assertEqual(len([r for r in rep["rows"] if "consumer" in r]), 3)

    def test_cron_period(self):
        self.assertEqual(eb.cron_period_days("17 5 * * 1"), 7)
        self.assertEqual(eb.cron_period_days("0 */3 * * *"), 1)
        self.assertEqual(eb.cron_period_days("0 0 * * 1,4"), 4)
        self.assertEqual(eb.cron_period_days("0 0 1 * *"), 31)

    def _tree(self, t, consumer_text, producer_cron):
        root = Path(t)
        wf = root / ".github/workflows"
        wf.mkdir(parents=True)
        (wf / "p.yml").write_text("on:\n  workflow_dispatch:\n" + (f"  schedule:\n    - cron: '{producer_cron}'\n" if producer_cron else ""))
        (wf / "c.yml").write_text(consumer_text)
        dag = {"retention_days": 30, "producers": [{"workflow": "p.yml"}],
               "edges": [{"producer": "p.yml", "consumer": "c.yml", "artifact_prefix": "p-"}]}
        (root / "dag.json").write_text(json.dumps(dag))
        return root

    def test_pinned_consumer_and_unscheduled_producer_flagged(self):
        with tempfile.TemporaryDirectory() as t:
            root = self._tree(t, "run: curl $api/actions/runs/35171901674\n", None)
            rep = eb.dag_check(root, root / "dag.json")
            self.assertFalse(rep["ok"])
            text = " ".join(rep["problems"])
            self.assertIn("still pins", text)
            self.assertIn("does not resolve", text)
            self.assertIn("schedule gap None", text)

    def test_monthly_schedule_insufficient_margin(self):
        with tempfile.TemporaryDirectory() as t:
            root = self._tree(t, "evidence_binding.py resolve --producer p.yml --artifact-prefix p-\n", "0 0 1 * *")
            rep = eb.dag_check(root, root / "dag.json")
            self.assertFalse(rep["ok"])
            self.assertIn("<2x margin", rep["problems"][0])


class Census(unittest.TestCase):
    def test_live_vs_record_and_probe_states(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / ".github/workflows").mkdir(parents=True)
            (root / ".github/workflows/g.yml").write_text("curl $api/actions/artifacts/111111111\nassert run['id']==222222222\n")
            (root / "lineage.json").write_text('{"run_id": 333333333}')

            def opener(req, timeout):
                u = req.full_url
                if u.endswith("/actions/artifacts/111111111"):
                    return io.BytesIO(json.dumps({"expired": False, "expires_at": "2026-10-25T00:00:00Z"}).encode())
                if "/actions/runs/222222222" in u:
                    raise urllib.error.HTTPError(u, 404, "nf", None, None)
                if "/actions/artifacts/222222222" in u:
                    raise urllib.error.HTTPError(u, 404, "nf", None, None)
                raise AssertionError(u)
            rep = eb.census(root, REPO, eb.Reader(REPO, token="", opener=opener))
            state = {(r["kind"], r["id"]): r.get("state") for r in rep["rows"]}
            self.assertEqual(state[("artifact", "111111111")], "TIME_BOMB")
            self.assertEqual(state[("id", "222222222")], "DEAD")
            self.assertIsNone(state[("run", "333333333")])  # historical record: never probed
            self.assertEqual((rep["live_gate_pins"], rep["historical_record_pins"]), (2, 1))


class RepoState(unittest.TestCase):
    def test_gm_v_gates_carry_no_pins(self):
        for wf in ("gm-v-governor-readiness.yml", "gm-v-3pstar-mip-control.yml", "gogreen-federation.yml"):
            text = (ROOT / ".github/workflows" / wf).read_text()
            self.assertEqual(eb.find_pins(text), [], wf)

    def test_vendored_g1_archive_matches_pinned_digest(self):
        import hashlib
        fx = ROOT / "mission-control/gogreen/g5/fixtures"
        prov = json.loads((fx / "g1_producer_run38726158685.provenance.json").read_text())
        data = (fx / "g1_producer_run38726158685.zip").read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), prov["sha256"])
        self.assertEqual(len(data), prov["bytes"])
        self.assertIn(prov["sha256"], (ROOT / ".github/workflows/gogreen-federation.yml").read_text())


if __name__ == "__main__":
    unittest.main()
