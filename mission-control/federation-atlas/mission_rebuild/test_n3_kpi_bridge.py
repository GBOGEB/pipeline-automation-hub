"""N3 source-bound current-control and historical native KPI regression contracts."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import n3_kpi_bridge as n3


def native_two_jobs():
    def job(job_id, start, end, conclusion, runner, failure):
        return {"id": job_id, "run_id": n3.RUN, "run_attempt": 1,
                "head_sha": n3.PRODUCER_SHA, "status": "completed",
                "conclusion": conclusion, "created_at": "2026-10-17T20:27:40Z",
                "started_at": start, "completed_at": end,
                "runner_id": runner, "labels": ["ubuntu-24.04"],
                "steps": [{"name": "Set up job", "number": 1,
                           "status": "completed", "conclusion": "success"},
                          {"name": "Refresh read-only census" if failure else "Negative contracts",
                           "number": 2, "status": "completed",
                           "conclusion": "failure" if failure else "success"}]}
    return {"total_count": 2,
            "jobs": [job(117496047462, "2026-10-17T20:29:50Z",
                         "2026-10-17T20:30:03Z", "failure", 1000655304, True),
                     job(117496047699, "2026-10-17T20:29:54Z",
                         "2026-10-17T20:30:01Z", "success", 1000655309, False)]}


class N3KPIContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.taxonomy = json.loads(n3.TAXONOMY.read_text(encoding="utf-8"))
        cls.rules = json.loads(n3.RULESET.read_text(encoding="utf-8"))

    def calculate(self, payload=None):
        return n3.classify(native_two_jobs() if payload is None else payload,
                           self.taxonomy, "c"*40,
                           "SYNTHETIC_TEST_FIXTURE_NOT_NATIVE")

    def test_bounded_native_two_job_measures(self):
        d = self.calculate()
        self.assertEqual([x["queue_seconds"] for x in d["jobs"]], [130, 134])
        self.assertEqual([x["runner_seconds"] for x in d["jobs"]], [13, 7])
        self.assertEqual(d["kpis"][0]["current_value"], 134)
        self.assertEqual(d["kpis"][0]["denominator"], 2)
        self.assertEqual(d["runner_occupied_seconds_observed"], 20)
        self.assertEqual(d["kpis"][0]["evidence_state"], "OBSERVED_HISTORICAL")

    def test_fleet_capability_unbound_and_no_authority(self):
        d = self.calculate()
        self.assertEqual(len(d["kpis"]), 6)
        self.assertTrue(all(m["current_value"] is None for m in d["kpis"][1:]))
        self.assertIsNone(d["fleet_runner_capacity"])
        self.assertIsNone(d["fleet_worker_hours"])
        self.assertEqual(d["authority"]["merge_admission"], "HOLD")
        self.assertEqual(d["statistical_control"]["m3"], "HOLD")
        self.assertEqual(d["statistical_control"]["bt"], "NOT_QUALIFIED")

    def test_manifestations_are_not_accepted_roots(self):
        d = self.calculate()
        self.assertEqual(len(d["manifestations"]), 1)
        self.assertIsNone(d["manifestations"][0]["root_id"])
        self.assertFalse(d["manifestations"][0]["accepted_root_closure"])
        self.assertIsNone(d["population"]["distinct_accepted_roots"])

    def test_owner_ruleset_has_required_status_and_independent_review(self):
        gate = n3.ruleset_gate(self.rules)
        self.assertIsNone(gate["owner_installed"])
        self.assertIsNone(gate["negative_red_canary"])
        bad = copy.deepcopy(self.rules)
        bad["conditions"]["ref_name"]["include"] = []
        with self.assertRaisesRegex(ValueError, "default branch"):
            n3.ruleset_gate(bad)
        bad = copy.deepcopy(self.rules)
        bad["rules"][3]["parameters"]["required_approving_review_count"] = 0
        with self.assertRaisesRegex(ValueError, "independent reviewer"):
            n3.ruleset_gate(bad)

    def test_wrong_head_and_attempt_fails_closed(self):
        for key, forged in (("head_sha", "d"*40), ("run_attempt", 2),
                            ("run_id", n3.RUN + 1)):
            data = native_two_jobs()
            data["jobs"][0][key] = forged
            with self.assertRaisesRegex(ValueError, "pinned run"):
                self.calculate(data)

    def test_empty_partial_or_duplicate_job_population(self):
        for data in ({"total_count": 0, "jobs": []},
                     {"total_count": 4, "jobs": native_two_jobs()["jobs"]},
                     {"total_count": 2, "jobs": [native_two_jobs()["jobs"][0]]*2}):
            with self.assertRaises(ValueError):
                self.calculate(data)

    def test_queued_or_forged_runner_denied(self):
        for key, value in (("status", "queued"), ("runner_id", 0),
                           ("labels", ["ubuntu-latest"])):
            data = native_two_jobs()
            data["jobs"][0][key] = value
            with self.assertRaises(ValueError):
                self.calculate(data)

    def test_nonmonotone_time_and_zero_steps_denied(self):
        data = native_two_jobs()
        data["jobs"][0]["completed_at"] = "2026-10-17T20:27:41Z"
        with self.assertRaisesRegex(ValueError, "time monotonicity"):
            self.calculate(data)
        data = native_two_jobs()
        data["jobs"][0]["steps"] = []
        with self.assertRaisesRegex(ValueError, "nonzero native"):
            self.calculate(data)

    def test_unknown_is_not_zero(self):
        d = n3.classify(None, self.taxonomy, "c"*40, "UNKNOWN_NO_NATIVE_SOURCE")
        self.assertEqual(d["population"]["jobs"], 0)
        self.assertTrue(all(k["current_value"] is None for k in d["kpis"]))
        self.assertIsNone(d["runner_occupied_seconds_observed"])

    def test_offline_plotly_html_and_member_hash_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, manifest = n3.build(tmp, "c"*40, native_two_jobs())
            page = (Path(tmp) / "n3-metrics.html").read_text(encoding="utf-8")
            self.assertIn("Mission Control N3", page)
            self.assertIn('id="detailToggle"', page)
            self.assertIn("Plotly.newPlot", page)
            self.assertIn('id="n3-queue_seconds"', page)
            self.assertIn('id="n3-runner_seconds"', page)
            self.assertLess(page.index("<script>"), page.index('id="n3-queue_seconds"'),
                            "Plotly library must load before chart newPlot scripts")
            self.assertIn("UNKNOWN", page)
            self.assertIn('Plotly.Plots.resize(el)', page,
                          "Charts must fit sibling grid cells after DOM load")
            self.assertEqual(report["population"]["jobs"], 2)
            self.assertEqual(set(manifest["member_sha256"]),
                             {"n3-metrics.json", "n3-metrics.html"})
            for name, digest in manifest["member_sha256"].items():
                self.assertEqual(hashlib.sha256((Path(tmp) / name).read_bytes()).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
