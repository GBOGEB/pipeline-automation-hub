"""Adversarial and positive native GREEN temporal proof contracts."""
from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[2]
spec = importlib.util.spec_from_file_location("runner_telemetry", BASE / "runner_telemetry.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
INPUT = BASE / "samples/native_success_20261017.json"
REGISTRY = ROOT / "mission-control/grand-missions/GM_DMAIC_EVOLUTION_T7_T14_T21_v1.json"
SHA = "a" * 40


class NativeGreenProof(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads(INPUT.read_text(encoding="utf-8"))
        self.registry = json.loads(REGISTRY.read_text(encoding="utf-8"))

    def invalid(self):
        with self.assertRaises((ValueError, AssertionError, KeyError, TypeError)):
            m.validate(self.raw, self.registry)

    def test_native_sample_21_and_24_and_10(self):
        heads, rows, ids, jobs = m.validate(self.raw, self.registry)
        self.assertEqual((len(heads), len(rows), len(ids), len(jobs)), (21, 24, 24, 9))

    def test_canonical_cohorts_seven_each(self):
        names = m.registry_names(self.registry)
        self.assertEqual([n[1] for n in names].count("TOP21_EXTENSION"), 7)
        self.assertEqual(len({n[0] for n in names}), 21)

    def test_source_reach_never_workflow_admission(self):
        a = m.metrics(self.raw, self.registry)
        self.assertEqual(a["top21_head_discovered"], 21)
        self.assertIsNone(a["effective_merge_admission"])
        self.assertEqual(a["current_head_protection_observed"], 1)

    def test_observed_runner_denominators(self):
        a = m.metrics(self.raw, self.registry)
        self.assertEqual(a["observed_successful_run_ids"], 24)
        self.assertEqual(a["current_head_successful_run_observations"], 4)
        self.assertEqual(a["sampled_terminal_native_jobs"], 10)
        self.assertEqual(a["measured_successful_native_jobs"], 9)
        self.assertEqual(a["skipped_native_jobs_excluded"], 1)
        self.assertEqual(a["sampled_runner_seconds_total"], 235)
        self.assertAlmostEqual(a["sampled_runner_minutes_not_billed"], 3.9167, places=4)

    def test_running_ordinal_gap_not_false_failure(self):
        a = m.metrics(self.raw, self.registry)
        by = {w["name"]: w for w in a["workflow_families"]}
        self.assertEqual(by["QPS TRIAGE Debug DAG Pilot"]["unobserved_run_number_gaps"], 0)
        self.assertEqual(by["Zero-Test Gate Guard"]["unobserved_run_number_gaps"], 10)
        self.assertEqual(by["M02B Math Bunker Smoke"]["unobserved_run_number_gaps"], 5)
        self.assertEqual(by["QPS Perpetual Debug Control"]["unobserved_run_number_gaps"], 0)
        self.assertIsNone(by["Zero-Test Gate Guard"]["population_success_rate"])

    def test_observation_span_maturity_not_reliability(self):
        a = m.metrics(self.raw, self.registry)
        by = {w["name"]: w for w in a["workflow_families"]}
        self.assertGreater(by["QPS TRIAGE Debug DAG Pilot"]["observed_maturity_span_hours"], 24)
        self.assertIsNone(by["QPS TRIAGE Debug DAG Pilot"]["independent_trial_count"])
        self.assertIsNone(a["statistical_independent_trials"])

    def test_parallel_runner_overlap_real(self):
        a = m.metrics(self.raw, self.registry)
        code = next(x for x in a["runner_by_repository"] if x["repository"] == "GBOGEB/CODEX")
        self.assertEqual(code["per_run"][0]["max_observed_parallel_jobs"], 3)
        self.assertEqual(code["sampled_runner_seconds"], 163)

    def test_qps_skipped_job_not_counted(self):
        a = m.metrics(self.raw, self.registry)
        self.assertEqual(a["skipped_native_jobs_excluded"], 1)
        self.assertEqual(len([j for j in self.raw["native_jobs"] if j["runner_id"] is None]), 1)

    def test_workflow_ability_has_owner_and_output(self):
        dag = m.dag(self.raw, m.metrics(self.raw, self.registry))
        self.assertEqual(dag["admission"], "HOLD")
        self.assertEqual(len([n for n in dag["nodes"] if n["id"].startswith("CAP_")]), 8)
        self.assertTrue(all(n["input"] and n["output"] for n in dag["nodes"] if n["id"].startswith("CAP_")))
        self.assertTrue(any(e["binding"] == "DECLARED" for e in dag["edges"]))
        self.assertFalse(dag["dispatch_authorized"])

    def test_sipoc_graph_has_no_cycle(self):
        graph = m.dag(self.raw, m.metrics(self.raw, self.registry))
        ancestors = {}
        for edge in graph["edges"]:
            ancestors.setdefault(edge["target"], []).append(edge["source"])
        visiting, done = set(), set()
        def walk(i):
            if i in visiting:
                raise AssertionError("cycle")
            if i in done:
                return
            visiting.add(i)
            for pred in ancestors.get(i, []):
                walk(pred)
            visiting.remove(i)
            done.add(i)
        for n in graph["nodes"]:
            walk(n["id"])

    def test_produce_hash_manifest_and_html(self):
        with tempfile.TemporaryDirectory() as path:
            r = m.build(self.raw, self.registry, SHA, Path(path))
            for name, expected in r["manifest"]["files"].items():
                self.assertEqual(m.digest((Path(path) / name).read_bytes()), expected)
            page = (Path(path) / "index.html").read_text(encoding="utf-8")
            self.assertIn("GoGREEN / GREEN-to-GREENER", page)
            self.assertIn("Current-head matches", page)
            self.assertIn("HOLD", (Path(path) / "sipoc_dag.json").read_text(encoding="utf-8"))
            self.assertFalse(r["manifest"]["artifact_bytes_verified_external"])

    def test_html_injection_escaped(self):
        self.raw["capabilities"][0]["operation"] = "<script>alert(1)</script>"
        page = m.render_html(m.metrics(self.raw, self.registry),
                             m.dag(self.raw, m.metrics(self.raw, self.registry)), self.raw)
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)

    def test_refuses_fake_closure(self):
        self.raw["root_closure_credit"] = 1
        self.invalid()

    def test_refuses_security_waiver(self):
        self.raw["security_waiver"] = True
        self.invalid()

    def test_refuses_merge_permission(self):
        self.raw["merge_authorized"] = True
        self.invalid()

    def test_refuses_authority_transfer(self):
        self.raw["authority_transfer"] = True
        self.invalid()

    def test_refuses_shrunk_roster(self):
        self.raw["repo_heads"].pop()
        self.invalid()

    def test_refuses_reordered_top21(self):
        a = self.raw["repo_heads"]
        a[0], a[1] = a[1], a[0]
        self.invalid()

    def test_refuses_forged_cohort(self):
        self.raw["repo_heads"][20]["cohort"] = "TOP7"
        self.invalid()

    def test_refuses_duplicate_canonical(self):
        self.registry["cohorts"]["top21_extension"][0] = self.registry["cohorts"]["top7"][0]
        self.invalid()

    def test_refuses_declared_success_for_head_discovery(self):
        self.raw["repo_heads"][0]["ci_at_current_head"] = "GREEN"
        self.invalid()

    def test_refuses_invalid_repository_head_sha(self):
        self.raw["repo_heads"][0]["head_sha"] = "f" * 39
        self.invalid()

    def test_refuses_fake_run_sha(self):
        self.raw["workflow_samples"][0]["run_observations"][0]["source_sha"] = "not-sha"
        self.invalid()

    def test_refuses_queued_run_in_green_sample(self):
        self.raw["workflow_samples"][0]["run_observations"][0]["status"] = "queued"
        self.invalid()

    def test_refuses_red_run_in_green_sample(self):
        self.raw["workflow_samples"][0]["run_observations"][0]["conclusion"] = "failure"
        self.invalid()

    def test_refuses_misleading_completeness(self):
        self.raw["workflow_samples"][0]["sample_only"] = False
        self.invalid()

    def test_refuses_double_credit_run_id(self):
        self.raw["workflow_samples"][1]["run_observations"][0]["run_id"] = (
            self.raw["workflow_samples"][0]["run_observations"][0]["run_id"])
        self.invalid()

    def test_refuses_duplicate_run_number(self):
        self.raw["workflow_samples"][0]["run_observations"][1]["run_number"] = 280
        self.invalid()

    def test_refuses_boolean_run_attempt(self):
        self.raw["workflow_samples"][0]["run_observations"][0]["attempt"] = True
        self.invalid()

    def test_refuses_missing_run_attempt(self):
        self.raw["workflow_samples"][0]["run_observations"][0].pop("attempt")
        self.invalid()

    def test_refuses_run_outside_window(self):
        self.raw["workflow_samples"][0]["run_observations"][0]["created_at"] = "2026-10-15T23:59:59Z"
        self.invalid()

    def test_refuses_local_without_timezone(self):
        self.raw["workflow_samples"][0]["run_observations"][0]["created_at"] = "2026-10-16T12:00:00"
        self.invalid()

    def test_refuses_reversed_ordinal_timeline(self):
        self.raw["workflow_samples"][0]["run_observations"][0]["created_at"] = "2026-10-17T18:10:00Z"
        self.invalid()

    def test_refuses_wrong_capability_owner(self):
        self.raw["capabilities"][0]["owner_repo"] = "GBOGEB/CODEX"
        self.invalid()

    def test_refuses_promoted_capability_evidence(self):
        self.raw["capabilities"][0]["evidence_level"] = "PRODUCTION_APPROVED"
        self.invalid()

    def test_refuses_duplicate_capability_id(self):
        self.raw["capabilities"][1]["id"] = self.raw["capabilities"][0]["id"]
        self.invalid()

    def test_refuses_job_run_id_not_observed(self):
        self.raw["native_jobs"][0]["run_id"] = 1
        self.invalid()

    def test_refuses_job_head_mismatch(self):
        self.raw["native_jobs"][0]["source_sha"] = "f" * 40
        self.invalid()

    def test_refuses_job_attempt_mismatch(self):
        self.raw["native_jobs"][0]["attempt"] = 2
        self.invalid()

    def test_refuses_duplicate_native_job_id(self):
        self.raw["native_jobs"][1]["job_id"] = self.raw["native_jobs"][0]["job_id"]
        self.invalid()

    def test_refuses_failed_job_as_green(self):
        self.raw["native_jobs"][0]["conclusion"] = "failure"
        self.invalid()

    def test_refuses_success_without_runner(self):
        self.raw["native_jobs"][0]["runner_id"] = None
        self.invalid()

    def test_refuses_negative_duration(self):
        self.raw["native_jobs"][0]["completed_at"] = "2026-10-17T09:45:00Z"
        self.invalid()

    def test_refuses_skipped_job_with_runner(self):
        self.raw["native_jobs"][5]["runner_id"] = 10
        self.invalid()

    def test_refuses_skipped_job_success_credit(self):
        self.raw["native_jobs"][5]["steps_success_eligible"] = True
        self.invalid()

    def test_refuses_red_root_forgery(self):
        self.raw["red_controls"][0]["root_confirmed"] = True
        self.invalid()

    def test_refuses_red_association_reused_success_id(self):
        self.raw["red_controls"][0]["run_id"] = 39021623362
        self.invalid()

    def test_refuses_registered_root_population_drift(self):
        self.raw["canonical_roster_path"] = "new-register.json"
        self.invalid()

    def test_refuses_bad_producer_sha(self):
        with tempfile.TemporaryDirectory() as path:
            with self.assertRaises(ValueError):
                m.build(self.raw, self.registry, "bad", Path(path))

    def test_fail_closed_on_wrong_schema(self):
        self.raw["schema"] = "new"
        self.invalid()

    def test_contract_rejects_nonnumeric_runner_ids(self):
        self.raw["native_jobs"][0]["runner_id"] = "123"
        self.invalid()


    def test_invalid_utc_date_reaches_datetime_exception_path(self):
        with self.assertRaisesRegex(ValueError, "malformed source timestamp"):
            m.timestamp("2026-02-30T10:00:00Z")

    def test_actual_cli_main_branch_generates_digest_bound_outputs(self):
        import contextlib
        import io
        import runpy
        import sys
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as path:
            dst = Path(path) / "out"
            argv = ["runner_telemetry.py", "--input", str(INPUT),
                    "--registry", str(REGISTRY), "--out", str(dst),
                    "--source-sha", SHA]
            stdout = io.StringIO()
            with patch.object(sys, "argv", argv), contextlib.redirect_stdout(stdout):
                runpy.run_path(str(BASE / "runner_telemetry.py"), run_name="__main__")
            self.assertEqual(json.loads(stdout.getvalue())["selected_green_runs"], 24)
            self.assertEqual(json.loads((dst / "metrics.json").read_text(encoding="utf-8"))
                             ["top21_head_discovered"], 21)
            manifest = json.loads((dst / "manifest.json").read_text(encoding="utf-8"))
            for name, checksum in manifest["files"].items():
                self.assertEqual(checksum, m.digest((dst / name).read_bytes()))


if __name__ == "__main__":
    unittest.main()
