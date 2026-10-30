"""JADE FOCUS5 Actions usage + performance metrics: projection over cached runs and jobs (offline)."""
import importlib.util
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


M = load("actions_metrics")
REPO = "GBOGEB/pipeline-automation-hub"
SHA = "a" * 40


def run(i, path=".github/workflows/gate.yml", name="Gate", conclusion="success", event="pull_request",
        created="2026-10-05T10:00:00Z", started="2026-10-05T10:00:30Z", updated="2026-10-05T10:02:30Z"):
    return {"id": i, "name": name, "path": path, "event": event, "status": "completed", "conclusion": conclusion,
            "created_at": created, "run_started_at": started, "updated_at": updated, "run_attempt": 1,
            "head_branch": "x"}


def job(run_id, name="j", conclusion="success", created="2026-10-05T10:00:00Z",
        started="2026-10-05T10:01:00Z", completed="2026-10-05T10:01:30Z", labels=("ubuntu-latest",)):
    return {"id": run_id * 10, "run_id": run_id, "run_attempt": 1, "name": name, "status": "completed",
            "conclusion": conclusion, "created_at": created, "started_at": started, "completed_at": completed,
            "labels": list(labels), "runner_group_name": "GitHub Actions"}


class Project(unittest.TestCase):
    def cache(self, runs, jobs):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        d = Path(tmp.name) / REPO.replace("/", "__")
        (d / "runs").mkdir(parents=True)
        (d / "jobs").mkdir()
        (d / "runs" / "2026-10-05.json").write_text(json.dumps(runs), encoding="utf-8", newline="\n")
        for rid, js in jobs.items():
            (d / "jobs" / f"{rid}-1.json").write_text(json.dumps(js), encoding="utf-8", newline="\n")
        return Path(tmp.name)

    def doc(self, runs, jobs, census=None):
        heads = {REPO: {"branch": "master", "head_sha": SHA, "visibility": "public",
                        "oids": {".github/workflows/gate.yml": "b" * 40}}}
        return M.project(self.cache(runs, jobs), [REPO], date(2026, 10, 5), date(2026, 10, 5), heads, census,
                         "2026-10-26T00:00:00Z")

    def test_billable_minutes_round_each_job_up(self):
        doc = self.doc([run(1)], {1: [job(1, "a"), job(1, "b", completed="2026-10-05T10:02:01Z")]})
        t = doc["repos"][0]["totals"]
        self.assertEqual(t["job_runs"], 2)
        self.assertEqual(t["total_minutes"], 1 + 2)  # 30s -> 1, 61s -> 2
        self.assertEqual(t["avg_job_run_s"], 45.5)
        self.assertEqual(t["avg_job_queue_s"], 60.0)
        self.assertEqual(t["runner_type"], "hosted")
        self.assertEqual(t["runtime_os"], "linux")

    def test_failure_rates_and_failed_minutes(self):
        runs = [run(1, conclusion="failure"), run(2)]
        jobs = {1: [job(1, "a", "failure"), job(1, "b")], 2: [job(2, "a"), job(2, "b")]}
        t = self.doc(runs, jobs)["repos"][0]["totals"]
        self.assertEqual(t["job_failure_rate"], 25.0)
        self.assertEqual(t["has_job_failures_pct"], 50.0)
        self.assertEqual(t["run_failure_rate"], 50.0)
        self.assertEqual(t["failed_job_minutes"], 1)

    def test_skipped_jobs_cost_nothing(self):
        t = self.doc([run(1)], {1: [job(1, "a"), job(1, "s", "skipped", started=None, completed=None)]}
                     )["repos"][0]["totals"]
        self.assertEqual((t["job_runs"], t["jobs_skipped"], t["total_minutes"]), (1, 1, 1))

    def test_partial_job_coverage_is_reported_not_assumed(self):
        t = self.doc([run(1), run(2), run(3), run(4)], {1: [job(1)]})["repos"][0]["totals"]
        self.assertEqual(t["workflow_runs"], 4)
        self.assertEqual(t["job_coverage"], 0.25)
        self.assertEqual(t["total_minutes"], 1)
        self.assertEqual(t["est_total_minutes"], 4)

    def test_no_jobs_read_means_unknown_not_zero(self):
        t = self.doc([run(1)], {})["repos"][0]["totals"]
        self.assertEqual(t["job_coverage"], 0.0)
        self.assertIsNone(t["avg_job_run_s"])
        self.assertIsNone(t["job_failure_rate"])
        self.assertIsNone(t["est_total_minutes"])

    def test_workflow_rows_bind_blob_oid_class_and_band(self):
        runs = [run(1), run(2, path="dynamic/github-code-scanning/codeql", name="CodeQL")]
        doc = self.doc(runs, {1: [job(1)], 2: [job(2, completed="2026-10-05T10:20:00Z")]})
        rows = {w["workflow"]: w for w in doc["repos"][0]["workflows"]}
        self.assertEqual(rows["Gate"]["blob_oid"], "b" * 40)
        self.assertIsNone(rows["CodeQL"]["blob_oid"])
        self.assertEqual((rows["Gate"]["class"], rows["CodeQL"]["class"]), ("GATE", "SECURITY"))
        self.assertEqual(rows["Gate"]["band"], "B1_SHORT_10s-1m")
        self.assertEqual(rows["CodeQL"]["band"], "B4_VERY_LONG_>15m")
        self.assertEqual(doc["repos"][0]["workflows"][0]["workflow"], "CodeQL")  # sorted by minutes

    def test_census_sha_binding(self):
        same = self.doc([run(1)], {1: [job(1)]}, {"repos": [{"repo": REPO, "head_sha": SHA}]})
        other = self.doc([run(1)], {1: [job(1)]}, {"repos": [{"repo": REPO, "head_sha": "c" * 40}]})
        none = self.doc([run(1)], {1: [job(1)]})
        self.assertTrue(same["repos"][0]["same_pulse"])
        self.assertFalse(other["repos"][0]["same_pulse"])
        self.assertIsNone(none["repos"][0]["same_pulse"])

    def test_fleet_total_and_groupings(self):
        runs = [run(1), run(2, event="schedule", path=".github/workflows/w3-recon.yml", name="W3 recon")]
        doc = self.doc(runs, {1: [job(1)], 2: [job(2)]})
        self.assertEqual(doc["fleet"]["totals"]["job_runs"], 2)
        self.assertEqual(set(doc["fleet"]["by_class"]), {"GATE", "CENSUS_TELEMETRY"})
        self.assertEqual(doc["fleet"]["by_event"]["schedule"]["workflow_runs"], 1)
        self.assertEqual(doc["repos"][0]["weekly"], {"2026-W41": {"runs": 2, "failed_runs": 0, "minutes": 2,
                                                                   "job_runs": 2}})

    def test_stratified_sample_covers_every_week_and_workflow_first(self):
        runs = [run(i, path=f".github/workflows/{p}.yml", created=f"2026-10-{d:02d}T0{i % 9}:00:00Z")
                for i, (p, d) in enumerate([("a", 5), ("a", 5), ("a", 6), ("b", 5), ("a", 20)], start=1)]
        # strata: W43/a [5], W41/b [4], W41/a [3, 2, 1]; one per stratum per round
        self.assertEqual([r["id"] for r in M.stratified(runs)], [5, 4, 3, 2, 1])

    def test_repo_estimate_scales_each_workflow_by_its_own_coverage(self):
        b = ".github/workflows/b.yml"
        runs = [run(1), run(2), run(3), run(4), run(5, path=b, name="B")]
        doc = self.doc(runs, {1: [job(1)], 5: [job(5, conclusion="failure")]})
        t = doc["repos"][0]["totals"]
        self.assertEqual(t["est_total_minutes"], 4 + 1)  # gate: 1 / 0.25, B: 1 / 1.0
        self.assertEqual((t["est_job_runs"], t["est_failed_job_minutes"], t["est_job_failure_rate"]), (5, 1, 20.0))
        self.assertEqual(t["est_unsampled_runs"], 0)
        self.assertEqual(doc["fleet"]["totals"]["est_total_minutes"], 5)

    def test_rerun_rate(self):
        r2 = dict(run(2), run_attempt=2)
        t = self.doc([run(1), r2], {1: [job(1)]})["repos"][0]["totals"]
        self.assertEqual(t["rerun_rate"], 50.0)

    def test_self_hosted_runner(self):
        self.assertEqual(M.runner_of({"labels": ["self-hosted", "Linux", "X64"], "runner_group_name": "Default"}),
                         ("self-hosted", "linux"))
        self.assertEqual(M.runner_of({"labels": ["windows-latest"], "runner_group_name": "GitHub Actions"}),
                         ("hosted", "windows"))



class ReaderNegativeControls(unittest.TestCase):
    """Previously shallow API and saturation paths, exercised without network."""

    def test_reject_unsafe_routes_before_network(self):
        rd = M.Reader("test")
        for route in ("https://evil.invalid/repos", "relative", "/repos/x/../secrets",
                      "/repos/x\\evil"):
            with self.subTest(route=route), self.assertRaisesRegex(ValueError, "noncanonical API path"):
                rd.get(route)
        self.assertEqual(rd.calls, 0)

    def test_auth_403_fails_immediately_without_retry(self):
        from unittest.mock import patch
        from urllib.error import HTTPError
        err = HTTPError("https://api.github.com/x", 403, "forbidden", {}, None)
        rd = M.Reader()
        with patch.object(M.urllib.request, "urlopen", side_effect=err) as req, \
             patch.object(M.time, "sleep") as sleeping:
            with self.assertRaises(HTTPError):
                rd.get("/repos/a/b")
            self.assertEqual((req.call_count, rd.calls, sleeping.call_count), (1, 1, 0))

    def test_transient_503_retries_bounded_exactly_four(self):
        from unittest.mock import patch
        from urllib.error import HTTPError
        rd = M.Reader()
        err = HTTPError("https://api.github.com/x", 503, "unavailable", {}, None)
        with patch.object(M.urllib.request, "urlopen", side_effect=err) as req, \
             patch.object(M.time, "sleep") as sleeping:
            with self.assertRaises(HTTPError):
                rd.get("/repos/a/b")
            self.assertEqual((req.call_count, rd.calls), (4, 4))
            self.assertEqual([c.args[0] for c in sleeping.call_args_list], [3, 6, 12])

    def test_reader_page_limit_exposes_unread_remainder(self):
        class Pages(M.Reader):
            def get(self, route):
                return {"workflow_runs": [{"id": n} for n in range(100)],
                        "total_count": 1001}
        rows, total = Pages().pages("/repos/x/y/actions/runs", "workflow_runs")
        self.assertEqual((len(rows), total), (1000, 1001))

    def test_oversized_day_fans_out_hours_and_deduplicates(self):
        class Hourly:
            def __init__(self):
                self.calls = []
            def pages(self, route, key):
                self.calls.append(route)
                if ".." not in route:
                    return [run(1)], 1001
                return ([run(1), run(2)], 2) if "T00:" in route else ([run(2)], 1)
        rd = Hourly()
        rows = M.fetch_runs_day(rd, REPO, date(2026, 10, 26))
        self.assertEqual({r["id"] for r in rows}, {1, 2})
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rd.calls), 25)

    def test_hourly_incomplete_total_fails_closed_not_a_fake_success(self):
        class Incomplete:
            def pages(self, route, key):
                # This was previously misreported by the successful 24-hour
                # fixture. An hour with one row but total_count=2 is incomplete.
                if ".." not in route:
                    return [run(1)], 1001
                return [run(1)], 2
        with self.assertRaisesRegex(ValueError, "exceeds the search cap"):
            M.fetch_runs_day(Incomplete(), REPO, date(2026, 10, 26))

    def test_hourly_search_cap_fails_closed(self):
        class Saturated:
            def pages(self, route, key):
                return [run(1)], 1001
        with self.assertRaisesRegex(ValueError, "exceeds the search cap"):
            M.fetch_runs_day(Saturated(), REPO, date(2026, 10, 26))

    def test_empty_or_negative_durations_are_unknown_not_zero(self):
        self.assertIsNone(M.seconds(None, "2026-10-26T00:00:00Z"))
        self.assertIsNone(M.seconds("2026-10-26T02:00:00Z", "2026-10-26T01:00:00Z"))
        self.assertIsNone(M.band(None))



class RecheckPressureRF(unittest.TestCase):
    """Canonical measurement owner: no synthetic passing rates for incomplete samples."""

    @staticmethod
    def synthetic():
        return [run(i, name="GOGREEN Required Gate Re-check" if i <= 363 else "Other QA",
                    event="workflow_run" if i <= 363 else "pull_request",
                    conclusion="cancelled" if i <= 278 else "success")
                for i in range(1, 1001)]

    def pressure(self, rows=None, **kw):
        return M.recheck_pressure(rows if rows is not None else self.synthetic(),
                                  REPO, SHA, "2026-10-28T16:00:00Z", **kw)

    def test_source_bound_363_over_1000_is_not_job_cost(self):
        report = self.pressure()
        self.assertEqual((report["sample_n"], report["recheck_records"],
                          report["recheck_cancelled"], report["value"]), (1000, 363, 278, 0.363))
        self.assertEqual(report["coverage"], "COMPLETE")
        self.assertFalse(report["merge_authorized"])

    def test_missing_population_is_unknown_not_zero_share(self):
        report = self.pressure(self.synthetic()[:12])
        self.assertEqual((report["sample_n"], report["coverage"]), (12, "PARTIAL_UNKNOWN"))
        self.assertIsNone(report["value"])

    def test_empty_population_remains_null(self):
        report = self.pressure([])
        self.assertEqual((report["sample_n"], report["coverage"], report["value"]),
                         (0, "PARTIAL_UNKNOWN", None))

    def test_more_than_1000_records_uses_fixed_recent_cohort(self):
        rows = self.synthetic()
        rows.append(run(1001, name="Other QA", event="push", created="2026-10-28T15:00:00Z"))
        report = self.pressure(rows)
        self.assertEqual((report["sample_n"], report["expected_n"]), (1000, 1000))
        self.assertEqual(report["recheck_records"], 362)

    def test_recheck_name_without_workflow_run_event_is_not_a_recheck(self):
        rows = self.synthetic()
        rows[0]["event"] = "push"
        report = self.pressure(rows)
        self.assertEqual(report["recheck_records"], 362)

    def test_duplicate_ids_are_rejected_not_double_counted(self):
        rows = self.synthetic()
        rows.append(rows[0])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.pressure(rows)

    def test_untrusted_head_and_denominator_are_refused(self):
        with self.assertRaisesRegex(ValueError, "source_sha"):
            M.recheck_pressure(self.synthetic(), REPO, "bad", "2026-10-28T16:00:00Z")
        with self.assertRaisesRegex(ValueError, "denominator"):
            self.pressure(sample_size=999)

    def test_future_run_is_not_in_historical_snapshot(self):
        rows = self.synthetic()
        rows[0]["created_at"] = "2026-10-28T17:00:00Z"
        with self.assertRaisesRegex(ValueError, "after observation"):
            self.pressure(rows)

    def test_bad_timestamp_and_boolean_run_id_refused(self):
        rows = self.synthetic()
        rows[0]["created_at"] = "not-a-date"
        with self.assertRaises(ValueError):
            self.pressure(rows)
        rows = self.synthetic()
        rows[0]["id"] = True
        with self.assertRaises(ValueError):
            self.pressure(rows)

    def test_replay_order_cannot_change_immutable_receipt(self):
        one = self.pressure()
        two = self.pressure(list(reversed(self.synthetic())))
        self.assertEqual(one, two)
        self.assertRegex(one["receipt_sha256"], r"^[0-9a-f]{64}$")

    def test_goal_contract_matches_rf_matrix_without_duplicate_metric(self):
        doc = self.pressure()
        self.assertEqual(doc["metric"], "recheck_workflow_record_share")
        self.assertEqual(doc["sample_method"], "last_1000_repo_workflow_runs")
        self.assertEqual(doc["metric_owner"], "mission-control/jade_temple/devops/actions_metrics.py")
        self.assertEqual(doc["source_binding"], "collector_repo_head_not_all_historical_run_heads")

    def test_cli_pressure_does_not_probe_network_or_require_token(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            cache = base / REPO.replace("/", "__") / "runs"
            cache.mkdir(parents=True)
            (cache / "2026-10-05.json").write_text(json.dumps([run(1)]), encoding="utf-8", newline="\n")
            out = base / "pressure.json"
            with mock.patch.object(M, "token", side_effect=AssertionError("no CLI token expected")):
                self.assertEqual(M.main(["pressure", "--cache", str(base),
                    "--since", "2026-10-05", "--until", "2026-10-05",
                    "--repo", REPO, "--source-sha", SHA, "--out", str(out)]), 0)
            report = json.loads(out.read_text(encoding="utf-8"))
            self.assertIsNone(report["value"])
            self.assertEqual(report["sample_n"], 1)
    def test_queued_and_in_progress_runs_are_not_in_cohort(self):
        rows = self.synthetic()
        rows.append(dict(run(2001, name="GOGREEN Required Gate Re-check", event="workflow_run",
                             conclusion=None, created="2026-10-28T15:00:00Z"), status="in_progress"))
        rows.append(dict(run(2002, name="Other QA", conclusion=None,
                             created="2026-10-28T15:01:00Z"), status="queued"))
        report = self.pressure(rows)
        self.assertEqual((report["sample_n"], report["recheck_records"], report["value"]),
                         (1000, 363, 0.363))
        self.assertEqual(report["excluded_incomplete_runs"], 2)
        self.assertNotIn("in_progress", report["recheck_outcomes"])

    def test_missing_source_day_keeps_full_cohort_unknown(self):
        report = self.pressure(missing_days=["2026-10-27"])
        self.assertEqual((report["sample_n"], report["coverage"]), (1000, "PARTIAL_UNKNOWN"))
        self.assertIsNone(report["value"])
        self.assertEqual(report["missing_source_days"], ["2026-10-27"])

    def test_receipt_binds_cohort_identity_not_only_aggregates(self):
        one = self.pressure()
        rows = self.synthetic()
        # Same boundaries and same outcome totals, different run identities.
        for rec in rows[1:-1]:
            rec["id"] += 5000
        two = self.pressure(rows)
        for key in ("sample_n", "recheck_records", "recheck_cancelled", "cohort_earliest",
                    "cohort_latest", "value"):
            self.assertEqual(one[key], two[key])
        self.assertNotEqual(one["cohort_sha256"], two["cohort_sha256"])
        self.assertNotEqual(one["receipt_sha256"], two["receipt_sha256"])

    def test_cli_pressure_flags_missing_cache_day(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            cache = base / REPO.replace("/", "__") / "runs"
            cache.mkdir(parents=True)
            (cache / "2026-10-05.json").write_text(json.dumps([run(1)]), encoding="utf-8", newline="\n")
            out = base / "pressure.json"
            self.assertEqual(M.main(["pressure", "--cache", str(base),
                "--since", "2026-10-04", "--until", "2026-10-05",
                "--repo", REPO, "--source-sha", SHA, "--out", str(out)]), 0)
            report = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(report["missing_source_days"], ["2026-10-04"])
            self.assertEqual(report["coverage"], "PARTIAL_UNKNOWN")


    def test_old_full_size_window_must_not_claim_current_t1(self):
        """Codex P1: 1000 older valid records cannot be the current observation."""
        result = M.recheck_pressure(self.synthetic(), REPO, SHA,
                                    "2026-10-30T08:00:00Z",
                                    window_end_date=date(2026, 10, 28))
        self.assertEqual((result["sample_n"], result["recheck_records"]), (1000, 363))
        self.assertEqual(result["coverage"], "PARTIAL_UNKNOWN")
        self.assertIsNone(result["value"])
        self.assertTrue(result["window_end_before_observation"])
        self.assertFalse(result["merge_authorized"])

    def test_matching_utc_day_allows_completeness_only_with_full_cohort(self):
        result = M.recheck_pressure(self.synthetic(), REPO, SHA,
                                    "2026-10-30T08:00:00Z",
                                    window_end_date=date(2026, 10, 30))
        self.assertEqual((result["sample_n"], result["value"], result["coverage"]),
                         (1000, 0.363, "COMPLETE"))
        self.assertFalse(result["window_end_before_observation"])
        self.assertEqual(result["window_end_date"], "2026-10-30")

    def test_cli_old_full_size_cache_stays_unknown(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            cache = base / REPO.replace("/", "__") / "runs"
            cache.mkdir(parents=True)
            (cache / "2026-10-28.json").write_text(
                json.dumps(self.synthetic()), encoding="utf-8", newline="\\n")
            out = base / "pressure.json"
            with mock.patch.object(M, "token", side_effect=AssertionError("no token for projection")):
                self.assertEqual(M.main(["pressure", "--cache", str(base),
                    "--since", "2026-10-28", "--until", "2026-10-28",
                    "--repo", REPO, "--source-sha", SHA, "--out", str(out)]), 0)
            report = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(report["sample_n"], 1000)
            self.assertTrue(report["window_end_before_observation"])
            self.assertIsNone(report["value"])


if __name__ == "__main__":
    unittest.main()
