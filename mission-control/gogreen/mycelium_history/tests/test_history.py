"""Mycelium history W6: adversarial source, denominator, lineage, UI tests."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import collect
import history

A, B, C = "a"*40, "b"*40, "c"*40


def run(id, sha, conclusion, when, *, attempt=1):
    return {
        "id": id, "attempt": attempt, "workflow_id": 371030423,
        "name": "MissionControl Mycelium CI",
        "status": "completed" if conclusion is not None else "queued",
        "conclusion": conclusion, "head_sha": sha, "event": "pull_request",
        "head_branch": "test", "created_at": when, "updated_at": when,
        "run_started_at": when, "url": f"https://github.com/GBOGEB/CODEX/actions/runs/{id}",
        "previous_attempts_collected": attempt == 1,
    }


def job(id=901, run_id=101, status="failure"):
    steps = [
        {"number": 1, "name": "Checkout", "status": "completed",
         "conclusion": "success"},
        {"number": 2, "name": "Preflight generated-value parity",
         "status": "completed", "conclusion": status},
        {"number": 3, "name": "Run MissionControl tests",
         "status": "completed", "conclusion": "skipped" if status == "failure" else "success"},
    ]
    return {
        "id": id, "run_id": run_id, "attempt": 1,
        "name": "validate", "status": "completed", "conclusion": status,
        "steps": steps,
        "first_failed_step": steps[1]["name"] if status == "failure" else None,
        "downstream_skipped_steps": [steps[2]["name"]] if status == "failure" else [],
        "log_bytes_sha256": "d"*64 if status == "failure" else None,
        "log_first_error": "generated executable inventory drift" if status == "failure" else None,
        "log_read_status": "READ_BOUNDED" if status == "failure" else "NOT_REQUESTED",
    }


def fixture():
    runs = [
        run(101, A, "failure", "2026-10-18T13:40:00Z"),
        run(102, B, "success", "2026-10-18T15:10:00Z"),
        run(103, C, "failure", "2026-10-18T15:30:00Z"),
    ]
    detail = {"101": {
        "run_id": 101, "attempt": 1, "api_job_total": 1,
        "jobs": [job()], "jobs_complete": True,
    }, "103": {
        "run_id": 103, "attempt": 1, "api_job_total": 1,
        "jobs": [job(902, 103)], "jobs_complete": True,
    }}
    return {
        "schema": collect.SCHEMA, "repository": collect.REPO,
        "workflow_file": collect.WORKFLOW,
        "capture_at": "2026-10-18T16:00:00Z",
        "source_main_before": B, "source_main_after": B,
        "source_main_stable_during_scan": True,
        "api_total_count": 3, "observed_run_count": 3,
        "page_count": 1, "run_inventory_complete": True,
        "pagination_nonatomic_or_capped": False, "duplicated_ids": [],
        "workflow_id": 371030423, "runs": runs,
        "selected_job_details": detail, "selected_job_run_count": 2,
        "job_detail_policy": "PRIORITIZED_FAILING_PLUS_RECENT_NOT_RANDOM",
        "job_detail_error_count": 0, "job_detail_errors": [],
        "failure_log_reads": 2, "log_read_attempts": 2,
        "unreadable_log_attempts": 0, "older_attempts_collected": True,
        "merged_pr_sample": [{
            "number": 1095, "title": "fix(mycelium W5): recensus 521 executable assets",
            "head_sha": A, "merge_sha": B,
            "base": "main", "merged_at": "2026-10-18T14:20:00Z",
            "url": "https://github.com/GBOGEB/CODEX/pull/1095",
        }],
        "merged_pr_sample_is_complete": False,
        "merge_admission": "HOLD", "authority_transfer": False,
        "security_waiver": False, "qps_acceptance": "WITHHELD",
        "root_closure_credit": 0, "worker_hours": None,
        "runner_capacity_slots": None, "fixture_only": True,
    }


class SemanticTests(unittest.TestCase):
    def test_icon_first_verb_and_parenthesized_scope(self):
        result = history.norm_title("fix(mycelium W5): recensus 521")
        self.assertEqual((result["kind"], result["family"], result["wave"]),
                         ("REPAIR", "MYCELIUM", "W5"))
        self.assertEqual(result["scope"], "mycelium W5")

    def test_feature_ci_docs_test_categories(self):
        for token, expect in (("feat", "FEATURE"), ("ci", "CI"),
                              ("docs", "DOCS"), ("test", "TEST"),
                              ("refactor", "REFACTOR"), ("revert", "REVERT")):
            with self.subTest(token=token):
                self.assertEqual(history.norm_title(token + "(mycelium): item")["kind"], expect)

    def test_series_code_purple_everred_gogreen(self):
        for scope, expect in (("code purple", "CODE_PURPLE"),
                              ("everred", "EVERRED"), ("gogreen", "GOGREEN"),
                              ("spine", "SPINE"), ("qps", "QPS")):
            with self.subTest(scope=scope):
                self.assertEqual(history.norm_title("fix(" + scope + "): item")["family"], expect)

    def test_unknown_title_never_claims_kind(self):
        self.assertEqual(history.norm_title("misc unicode system")["kind"], "OTHER")

    def test_merge_title_has_merge_glyph(self):
        self.assertEqual(history.norm_title("Merge pull request #1095 from example")["kind"], "MERGE")

    def test_html_labels_are_escaped(self):
        d = fixture()
        d["merged_pr_sample"][0]["title"] = 'fix(mycelium): <script>alert(1)</script>'
        html = history.html_page(history.summarize(d),
                                 history.lineage_dag(history.summarize(d)))
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_pr_with_red_before_and_main_green_after(self):
        r = history.summarize(fixture())
        p = r["merged_with_red"]["prs"][0]
        self.assertEqual((p["red_before_merge"], p["successful_post_merge"]), (1, 1))
        self.assertIsNone(p["independent_approval"])
        self.assertEqual(p["governed_admission"], "UNKNOWN_NOT_CREDITED")

    def test_native_job_completion_before_merge_separate_from_proxy(self):
        d = fixture()
        d["selected_job_details"]["101"]["jobs"][0]["completed_at"] = (
            "2026-10-18T13:42:00Z")
        out = history.summarize(d)["merged_with_red"]["prs"][0]
        self.assertEqual(out["native_failed_jobs_completed_before_merge"], 1)
        self.assertEqual(out["native_failed_jobs_completed_after_merge"], 0)
        self.assertEqual(out["native_jobs_with_completion_timestamps"], 1)
        self.assertEqual(out["run_timing_basis"],
                         "RUN_UPDATED_AT_PROXY_NOT_CHECK_COMPLETION")
        self.assertFalse(out["native_job_timing_complete_for_all_runs"])

    def test_native_job_after_merge_can_contradict_run_updated_proxy(self):
        d = fixture()
        d["selected_job_details"]["101"]["jobs"][0]["completed_at"] = (
            "2026-10-18T14:23:00Z")
        out = history.summarize(d)["merged_with_red"]["prs"][0]
        self.assertEqual(out["red_before_merge"], 1)
        self.assertEqual(out["native_failed_jobs_completed_before_merge"], 0)
        self.assertEqual(out["native_failed_jobs_completed_after_merge"], 1)
        self.assertEqual(out["governed_admission"], "UNKNOWN_NOT_CREDITED")

    def test_untrusted_job_completion_timestamp_rejected(self):
        d = fixture()
        d["selected_job_details"]["101"]["jobs"][0]["completed_at"] = "soon"
        with self.assertRaisesRegex(ValueError, "UTC timestamp"):
            history.summarize(d)

    def test_symbol_parser_ci_scope_has_distinct_icon(self):
        value = history.norm_title("fix(ci W5): register W4 handover")
        self.assertEqual(value["kind"], "REPAIR")
        self.assertEqual(value["family"], "CI")
        self.assertEqual(value["wave"], "W5")

    def test_fingerprint_repeat_is_not_root_closure(self):
        r = history.summarize(fixture())
        self.assertEqual(r["first_red"]["sampled_occurrences"], 2)
        self.assertEqual(r["first_red"]["sampled_distinct_fingerprints"], 1)
        self.assertEqual(r["first_red"]["accepted_root_closures"], 0)
        self.assertEqual(r["first_red"]["downstream_skipped_step_occurrences"], 2)

    def test_first_red_signature_step_only_is_different(self):
        a = job()
        b = copy.deepcopy(a)
        b["log_first_error"] = None
        self.assertNotEqual(history.fingerprint(a)["id"], history.fingerprint(b)["id"])

    def test_first_red_signature_normalizes_random_sha(self):
        a, b = job(), job()
        a["log_first_error"] = A + " expired"
        b["log_first_error"] = B + " expired"
        self.assertEqual(history.fingerprint(a)["id"], history.fingerprint(b)["id"])

    def test_integer_daily_bins_not_fractional_issues(self):
        result = history.summarize(fixture())
        self.assertEqual(sum(x["observed"] for x in result["daily_bins"]), 3)
        self.assertTrue(all(type(x["red"]) is int for x in result["daily_bins"]))
        self.assertIn("dtick", json.dumps(history.plotly_payload(result)))

    def test_no_fake_matched_coverage_or_worker_capacity(self):
        r = history.summarize(fixture())
        self.assertIsNone(r["statistics"]["matched_statement_coverage"])
        self.assertIsNone(r["statistics"]["worker_hours"])
        self.assertIn("NOT_QUALIFIED", r["statistics"]["PCA"])
        self.assertFalse(r["authority"]["merge_authorized"])


class RejectionTests(unittest.TestCase):
    def bad(self, modify, text):
        d = fixture()
        modify(d)
        with self.assertRaisesRegex(ValueError, text):
            history.validate(d)

    def test_forged_merge_authority_rejected(self):
        self.bad(lambda d:d.update(merge_admission="PASS"), "false-governed")

    def test_forged_security_waiver_rejected(self):
        self.bad(lambda d:d.update(security_waiver=True), "false-governed")

    def test_forged_qps_approval_rejected(self):
        self.bad(lambda d:d.update(qps_acceptance="ACCEPT"), "false-governed")

    def test_forged_root_closure_rejected(self):
        self.bad(lambda d:d.update(root_closure_credit=1), "false-governed")

    def test_zero_worker_hours_not_unknown(self):
        self.bad(lambda d:d.update(worker_hours=0), "capacity")

    def test_fabricated_660_denominator_completion_rejected(self):
        self.bad(lambda d:d.update(api_total_count=660), "fabricated full-history")

    def test_duplicate_run_id_rejected(self):
        self.bad(lambda d:d["runs"].append(d["runs"][0]), "run denominator")

    def test_invalid_sha_rejected(self):
        self.bad(lambda d:d["runs"][0].update(head_sha="HEAD"), "run head")

    def test_nonterminal_fake_success_rejected(self):
        self.bad(lambda d:d["runs"][0].update(status="queued"), "terminal mismatch")

    def test_running_without_conclusion_accepts_zero_credit(self):
        d = fixture()
        d["runs"][0].update(status="queued", conclusion=None)
        del d["selected_job_details"]["101"]
        d["selected_job_run_count"] = 1
        history.validate(d)
        self.assertEqual(history.summarize(d)["run_population"]["nonterminal"], 1)

    def test_attempt_identity_mismatch_rejected(self):
        self.bad(lambda d:d["selected_job_details"]["101"].update(attempt=2), "job/run binding")

    def test_run_previous_attempts_flag_forged_rejected(self):
        self.bad(lambda d:d["runs"][0].update(attempt=2), "rerun history")

    def test_duplicate_job_rejected(self):
        self.bad(lambda d:d["selected_job_details"]["101"]["jobs"].append(
            copy.deepcopy(d["selected_job_details"]["101"]["jobs"][0])), "claimed complete")

    def test_first_red_forgery_rejected(self):
        self.bad(lambda d:d["selected_job_details"]["101"]["jobs"][0].update(
            first_failed_step="nonsense"), "first-red first step")

    def test_missing_bounded_log_hash_rejected(self):
        self.bad(lambda d:d["selected_job_details"]["101"]["jobs"][0].update(
            log_bytes_sha256=None), "forged log")

    def test_pr_sample_cannot_claim_fleet_completeness(self):
        self.bad(lambda d:d.update(merged_pr_sample_is_complete=True), "sample cannot")

    def test_bad_pr_merge_sha_rejected(self):
        self.bad(lambda d:d["merged_pr_sample"][0].update(merge_sha="HEAD"), "merge SHA")

    def test_bad_capture_timestamp_rejected(self):
        self.bad(lambda d:d.update(capture_at="sometime"), "UTC timestamp")

    def test_untrusted_source_repo_rejected(self):
        self.bad(lambda d:d.update(repository="GBOGEB/mystery"), "source identity")


class CollectorTests(unittest.TestCase):
    def raw(self, id=101, conclusion="failure", sha=A):
        x = run(id, sha, conclusion, "2026-10-18T13:40:00Z")
        x["run_attempt"] = x["attempt"]  # REST input, not normalized fixture
        return x

    def test_normalize_run_preserves_exact_attempt(self):
        result = collect.normalize_run(self.raw(), 371030423)
        self.assertEqual(result["attempt"], 1)
        self.assertEqual(result["head_sha"], A)

    def test_normalize_wrong_workflow_rejected(self):
        with self.assertRaisesRegex(ValueError, "wrong workflow"):
            collect.normalize_run(self.raw(), 55)

    def test_normalize_run_conclusion_mismatch_rejected(self):
        x = self.raw()
        x["status"] = "queued"
        with self.assertRaisesRegex(ValueError, "run is not terminal"):
            collect.normalize_run(x)

    def test_pages_two_pages_of_101(self):
        rows = [self.raw(i, "success") for i in range(1001, 1102)]
        def getter(path):
            page = 1 if path.endswith("&page=1") else 2
            return {"total_count": 101, "workflow_runs":
                    rows[:100] if page == 1 else rows[100:]}
        result = collect.read_run_pages(getter)
        self.assertEqual((result["observed_run_count"], result["page_count"]), (101, 2))
        self.assertTrue(result["run_inventory_complete"])

    def test_pages_capture_non_atomic_denominator(self):
        rows = [self.raw(i, "success") for i in range(2001, 2102)]
        def getter(path):
            page = 1 if path.endswith("&page=1") else 2
            return {"total_count": 101 if page == 1 else 102,
                    "workflow_runs": rows[:100] if page == 1 else rows[100:]}
        self.assertFalse(collect.read_run_pages(getter)["run_inventory_complete"])

    def test_pages_max_run_cap_never_passes_as_complete(self):
        rows = [self.raw(i, "success") for i in range(3001, 3101)]
        result = collect.read_run_pages(
            lambda path: {"total_count": 660, "workflow_runs": rows}, max_runs=100)
        self.assertFalse(result["run_inventory_complete"])
        self.assertEqual(result["eligible_api_reported"] if
                         "eligible_api_reported" in result else result["api_total_count"], 660)

    def test_pages_duplicate_run_marks_partial(self):
        rows = [self.raw(i, "success") for i in range(4001, 4101)]
        def getter(path):
            return {"total_count": 101, "workflow_runs":
                    rows if path.endswith("&page=1") else [rows[-1]]}
        result = collect.read_run_pages(getter)
        self.assertEqual(len(result["duplicated_ids"]), 1)
        self.assertFalse(result["run_inventory_complete"])

    def test_job_detail_includes_skip_chain(self):
        raw = {"id": 901, "name": "validate", "status": "completed",
               "conclusion": "failure", "steps": job()["steps"]}
        result = collect.normalize_job(raw, 101, 1)
        self.assertEqual(result["first_failed_step"], "Preflight generated-value parity")
        self.assertEqual(result["downstream_skipped_steps"], ["Run MissionControl tests"])

    def test_job_duplicate_id_rejected(self):
        raw = {"id":901, "name":"validate", "steps":[]}
        def fetch(_):
            return {"total_count":2, "jobs":[raw,raw]}
        with self.assertRaisesRegex(ValueError, "duplicate job"):
            collect.read_jobs(fetch, run(101,A,"failure","2026-10-18T13:40:00Z"))

    def test_job_detail_zero_jobs_is_complete(self):
        d = collect.read_jobs(lambda _:{"total_count":0,"jobs":[]},
                              run(101,A,"failure","2026-10-18T13:40:00Z"))
        self.assertEqual(d["api_job_total"], 0)
        self.assertTrue(d["jobs_complete"])

    def test_balanced_160_run_quota_reports_100_red_60_green(self):
        vals = [run(i, A, "failure", "2026-10-18T15:00:00Z")
                for i in range(2000, 2120)]
        vals += [run(i, B, "success", "2026-10-18T15:10:00Z")
                 for i in range(3000, 3080)]
        selected = collect.select_for_jobs(vals, 160)
        self.assertEqual(len(selected), 160)
        self.assertEqual(sum(r["conclusion"] == "failure" for r in selected), 100)
        self.assertEqual(sum(r["conclusion"] == "success" for r in selected), 60)

    def test_short_green_stratum_lends_selection_to_red(self):
        vals = [run(i, A, "failure", "2026-10-18T15:00:00Z")
                for i in range(4000, 4020)]
        vals += [run(5000, B, "success", "2026-10-18T15:00:00Z")]
        selected = collect.select_for_jobs(vals, 10)
        self.assertEqual(len(selected), 10)
        self.assertEqual(sum(r["conclusion"] == "success" for r in selected), 1)

    def test_days_with_zero_runs_are_kept_explicit(self):
        vals = [run(8001, A, "success", "2026-10-01T12:00:00Z"),
                run(8002, A, "failure", "2026-10-03T12:00:00Z")]
        out = history.bins(vals)
        self.assertEqual([x["date"] for x in out],
                         ["2026-10-01", "2026-10-02", "2026-10-03"])
        self.assertEqual([x["observed"] for x in out], [1, 0, 1])

    def test_failure_priority_before_selected_success(self):
        vals = [run(i, A, "success", "2026-10-18T15:00:00Z")
                for i in range(10,15)]
        vals.append(run(1, A, "failure", "2026-10-17T10:00:00Z"))
        selected = collect.select_for_jobs(vals, 2)
        self.assertEqual(selected[0]["id"], 1)

    def test_log_extract_only_runtime_annotation(self):
        line = b'echo "fake ##[error]example"\n2026-10-18 ##[error]inventory drift\n'
        self.assertEqual(collect.parse_error(line), "GENERATED_EXECUTABLE_INVENTORY_DRIFT")

    def test_secret_line_reduces_to_hash_not_raw_secret(self):
        secret = "ghs_" + "Z" * 48
        observed = collect.parse_error(("##[error]" + secret + " rejected").encode())
        self.assertTrue(observed.startswith("UNCLASSIFIED_ERROR_"))
        self.assertNotIn(secret, observed)

    def test_no_error_log_is_unknown(self):
        self.assertIsNone(collect.parse_error(b"tests passed and logs empty"))

    def test_merged_pr_list_is_sampled(self):
        def fetch(path):
            return [{"number":1, "head":{"sha":A},
                     "merged_at":"2026-10-18T14:00:00Z",
                     "merge_commit_sha":B, "base":{"ref":"main"}, "title":"fix(c): a"}]
        r = collect.merged_pr_sample(fetch)
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["head_sha"], A)

    def test_unsafe_external_api_url_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsafe"):
            collect.request_json("/repos/GBOGEB/CODEX//actions/runs")


class PresentationTests(unittest.TestCase):
    def test_empty_run_list_has_no_invented_day_bars(self):
        self.assertEqual(history.bins([]), [])

    def test_partial_run_snapshot_stays_partial(self):
        d = fixture()
        d["api_total_count"] = 4
        d["run_inventory_complete"] = False
        d["pagination_nonatomic_or_capped"] = True
        history.validate(d)
        self.assertFalse(history.summarize(d)["run_population"]["complete"])

    def test_incomplete_job_page_cannot_claim_complete(self):
        d = fixture()
        d["selected_job_details"]["101"]["jobs_complete"] = False
        history.validate(d)
        self.assertEqual(history.summarize(d)["job_detail"]["observed_run_records"], 2)

    def test_successful_selected_job_exercises_skip_firstred_path(self):
        d = fixture()
        d["selected_job_details"]["102"] = {
            "run_id": 102, "attempt": 1, "api_job_total": 1,
            "jobs_complete": True, "jobs": [job(903, 102, "success")],
        }
        d["selected_job_run_count"] = 3
        r = history.summarize(d)
        self.assertEqual(r["job_detail"]["sampled_successful_runs"], 1)
        self.assertEqual(r["first_red"]["sampled_occurrences"], 2)

    def test_missing_merge_sha_stays_unknown_without_inferred_main(self):
        d = fixture()
        d["merged_pr_sample"][0]["merge_sha"] = None
        r = history.summarize(d)
        self.assertEqual(r["merged_with_red"]["prs"][0]["observed_runs_on_head_or_merge_sha"], 1)
        self.assertEqual(r["merged_with_red"]["prs"][0]["successful_post_merge"], 0)

    def test_dag_edges_tagged_by_evidence(self):
        graph = history.lineage_dag(history.summarize(fixture()))
        self.assertEqual(len(graph["nodes"]), 8)
        self.assertIn("NEXT_PULSE_ONLY", {e["evidence"] for e in graph["edges"]})
        self.assertFalse(graph["authority_transfer"])

    def test_html_and_svg_contain_native_categories(self):
        report = history.summarize(fixture())
        page = history.html_page(report, history.lineage_dag(report))
        self.assertIn("CODE PURPLE", page)
        self.assertIn("MYCELIUM", page)
        self.assertIn("Merged PRs with RED", page)
        self.assertIn('viewBox="0 0 980 310"', history.mini_chart(report))

    def test_juxtaposed_run_counts_not_coverage(self):
        payload = history.plotly_payload(history.summarize(fixture()))
        self.assertEqual(payload["layout"]["yaxis"]["dtick"], 1)
        self.assertIn("not roots", payload["layout"]["yaxis"]["title"])

    def test_html_no_external_script_or_browser_network(self):
        report = history.summarize(fixture())
        page = history.html_page(report, history.lineage_dag(report))
        self.assertNotIn("<script", page)
        self.assertNotIn("cdn.plot.ly", page)

    def test_deterministic_preview_replay_and_manifest(self):
        with tempfile.TemporaryDirectory() as x, tempfile.TemporaryDirectory() as y:
            a, b = Path(x), Path(y)
            source = fixture()
            report = history.build(source, C, a)
            history.build(source, C, b)
            history.build(source, C, a, check=True)
            manifest = json.loads((a / "manifest.json").read_text())
            for name, digest in manifest["file_sha256"].items():
                self.assertEqual(hashlib.sha256((a/name).read_bytes()).hexdigest(),
                                 digest)
                self.assertEqual((a/name).read_bytes(), (b/name).read_bytes())
            self.assertFalse(manifest["public_pages_deployed"])
            self.assertEqual(report["authority"]["admission"], "HOLD")

    def test_archive_candidate_byte_drift_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            out = Path(root)
            history.build(fixture(), C, out)
            (out/"index.html").write_text("drift", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "determinism drift"):
                history.build(fixture(), C, out, check=True)

    def test_unexpected_artifact_member_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            out = Path(root)
            history.build(fixture(), C, out)
            (out/"shadow.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "unexpected or missing"):
                history.build(fixture(), C, out, check=True)

    def test_no_short_head_sha_in_preview_identity(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, "source SHA"):
                history.build(fixture(), C[:10], Path(root))

    def test_repeated_rerun_is_not_independent(self):
        d = fixture()
        d["runs"][0]["attempt"] = 2
        d["runs"][0]["previous_attempts_collected"] = False
        d["selected_job_details"]["101"]["attempt"] = 2
        d["selected_job_details"]["101"]["jobs"][0]["attempt"] = 2
        r = history.summarize(d)
        self.assertEqual(r["attempts"]["rerun_latest_attempts"], 1)
        self.assertEqual(r["attempts"]["independence"], "NOT_PROVEN")


if __name__ == "__main__":
    unittest.main()
