"""CODE-HEALTH frontier: source census, Golden Thread and fail-closed tests."""

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from central import code_health as health  # noqa: E402


class CodeHealthControlTests(unittest.TestCase):
    def setUp(self):
        self.source = health.read_json(health.REGISTRY)

    def test_six_repo_census_is_scope_matched(self):
        result = health.validate(self.source)
        self.assertEqual(result["repositories"], 6)
        self.assertEqual(result["open_issues"], 143)
        self.assertEqual(result["closed_issues"], 412)
        self.assertEqual(result["open_prs"], 68)
        self.assertEqual(result["closed_prs"], 5126)
        self.assertEqual(result["canonical_root_closures"], None)
        self.assertEqual(result["admission"], "HOLD")

    def test_existing_canonical_lane_population_not_replaced(self):
        metrics = health.validate(self.source)
        self.assertEqual((metrics["lane_count"], metrics["stage_count"]), (10, 39))
        self.assertEqual((metrics["graph_nodes"], metrics["graph_edges"]), (26, 29))
        self.assertEqual(metrics["work_items"], 15)

    def test_triad_is_preserved_and_future_actual_is_missing(self):
        self.assertEqual([c["id"] for c in self.source["cycles"]],
                         ["N-1", "N", "N+1"])
        self.assertEqual(self.source["cycles"][0]["metrics"]["abacus_issues_open"], 47)
        self.assertEqual(self.source["cycles"][1]["metrics"]["abacus_issues_open"], 48)
        for forecast in self.source["forecasts"]:
            self.assertIsNone(forecast["actual_next"])
            self.assertIsNone(health.forecast_score(forecast))
            self.assertFalse(forecast["credit_to_engineering_roots"])

    def test_source_does_not_fabricate_crew_launch_from_dab_jobs(self):
        result = health.validate(self.source)
        self.assertIsNone(result["verified_crew_launches"])
        self.assertEqual(self.source["crew"]["dab_proposal_jobs_passed_historical"], 8)
        self.assertIsNone(self.source["crew"]["authenticated_launch_count"])
        self.assertIsNone(self.source["crew"]["accepted_rex_count"])

    def test_no_authority_transfer_or_unauthorized_repo_rename(self):
        authority = self.source["authority"]
        self.assertEqual(authority["alias_candidate"], "gg_mCC")
        self.assertFalse(authority["rename_authorized"])
        self.assertFalse(authority["mutation_enabled"])
        self.assertFalse(authority["merge_authorized"])
        self.assertFalse(authority["authority_transfer"])

    def test_missing_runner_inventory_means_no_remote_launch(self):
        result = health.route_work(self.source["work"],
                                   self.source["runner_capacity"])
        self.assertEqual(len(result), 15)
        self.assertFalse(any(x["automatically_launched"] for x in result))
        self.assertEqual(next(x["route"] for x in result if x["id"] == "W01"),
                         "BLOCKED_P0")
        self.assertEqual(next(x["route"] for x in result if x["id"] == "W06"),
                         "WAIT_OWNER")
        self.assertIn(next(x["route"] for x in result if x["id"] == "W03"),
                      {"WAIT_CAPACITY", "WAIT_INPUT"})

    def test_repairs_with_same_config_and_population_are_comparable(self):
        before = {
            "repo": "ABACUS", "scope": "module", "config_id": "branch",
            "eligible_lines": 100, "covered_lines": 41,
            "eligible_branches": 50, "covered_branches": 18,
        }
        after = dict(before, covered_lines=51, covered_branches=23)
        r = health.matching_coverage(before, after)
        self.assertEqual(r["status"], "COMPARABLE")
        self.assertEqual(r["numerator_delta"], 15)
        self.assertEqual(r["eligible"], 150)
        self.assertAlmostEqual(r["delta_pp"], 10.0)

    def test_coverage_must_not_compare_changed_denominators(self):
        b = {
            "repo": "ABACUS", "scope": "small", "config_id": "branch",
            "eligible_lines": 100, "covered_lines": 50,
            "eligible_branches": 10, "covered_branches": 5,
        }
        a = dict(b, eligible_lines=101, covered_lines=90)
        self.assertEqual(health.matching_coverage(b, a)["status"],
                         "INCOMPARABLE")
        self.assertIsNone(health.matching_coverage(b, a)["delta_pp"])

    def test_branch_coverage_forgery_is_rejected(self):
        b = {
            "repo": "ABACUS", "scope": "same", "config_id": "branch",
            "eligible_lines": 100, "covered_lines": 80,
            "eligible_branches": 10, "covered_branches": 9,
        }
        a = dict(b, covered_branches=11)
        with self.assertRaisesRegex(ValueError, "numerator"):
            health.matching_coverage(b, a)

    def test_missing_clocks_never_become_zero_queue_time(self):
        self.assertIsNone(health.duration_seconds(None, None))
        self.assertIsNone(health.duration_seconds(
            "2026-10-16T08:00:00", "2026-10-16T08:01:00"))
        self.assertIsNone(health.duration_seconds(
            "2026-10-16T08:03:00Z", "2026-10-16T08:01:00Z"))
        self.assertIsNone(health.native_p95([]))
        self.assertEqual(health.duration_seconds(
            "2026-10-16T08:00:00Z", "2026-10-16T08:02:30Z"), 150)

    def test_nearest_rank_p95_uses_only_observed_samples(self):
        self.assertEqual(health.native_p95([0, 1, 2, 3, 4, 5]), 5)
        with self.assertRaisesRegex(ValueError, "invalid native latency"):
            health.native_p95([-1, 2])
        with self.assertRaisesRegex(ValueError, "invalid native latency"):
            health.native_p95([float("nan")])

    def test_root_numbers_are_not_derived_from_issue_counts(self):
        bad = copy.deepcopy(self.source)
        bad["census"]["repositories"][0]["root_closed"] = 37
        with self.assertRaisesRegex(ValueError, "BD roots"):
            health.validate(bad)

    def test_unknown_runner_slots_cannot_be_set_to_zero(self):
        bad = copy.deepcopy(self.source)
        bad["runner_capacity"]["native_available_slots"] = 0
        with self.assertRaisesRegex(ValueError, "unmeasured runner"):
            health.validate(bad)

    def test_out_of_scope_repo_is_rejected(self):
        bad = copy.deepcopy(self.source)
        bad["census"]["repositories"][0]["id"] = "BAD/OTHER"
        with self.assertRaisesRegex(ValueError, "foreign repository"):
            health.validate(bad)

    def test_issue_population_must_reconcile(self):
        bad = copy.deepcopy(self.source)
        bad["census"]["repositories"][0]["issue_register"]["open"] = 10
        with self.assertRaisesRegex(ValueError, "totals mismatch"):
            health.validate(bad)

    def test_dangling_and_duplicate_graph_edges_rejected(self):
        bad = copy.deepcopy(self.source)
        bad["graph"]["edges"][0]["to"] = "DOES_NOT_EXIST"
        with self.assertRaisesRegex(ValueError, "dangling"):
            health.validate(bad)
        bad = copy.deepcopy(self.source)
        bad["graph"]["edges"][1]["id"] = bad["graph"]["edges"][0]["id"]
        with self.assertRaisesRegex(ValueError, "duplicate graph edge"):
            health.validate(bad)

    def test_historical_execution_edge_requires_evidence_link(self):
        bad = copy.deepcopy(self.source)
        seen = [e for e in bad["graph"]["edges"]
                if e["binding"] == "OBSERVED_HISTORICAL"]
        self.assertEqual(len(seen), 2)
        seen[0]["evidence"] = None
        with self.assertRaisesRegex(ValueError, "bound edge needs"):
            health.validate(bad)

    def test_future_cannot_claim_actual_before_future_pulse(self):
        bad = copy.deepcopy(self.source)
        bad["forecasts"][0]["actual_next"] = 143
        with self.assertRaisesRegex(ValueError, "not an observed"):
            health.validate(bad)

    def test_rename_or_merge_promotion_is_rejected(self):
        for key in ("rename_authorized", "merge_authorized",
                    "authority_transfer", "mutation_enabled"):
            bad = copy.deepcopy(self.source)
            bad["authority"][key] = True
            with self.subTest(key=key), self.assertRaisesRegex(
                ValueError, "non-authorized transition"
            ):
                health.validate(bad)

    def test_mermaid_sources_real_queue_and_owner_links(self):
        mmd = health.mermaid(self.source)
        self.assertIn("W07 --> W08", mmd)
        self.assertIn("W11 --> W12", mmd)
        self.assertIn("GATE", mmd)
        self.assertIn("UNKNOWN or FAIL", mmd)

    def test_html_escapes_untrusted_text(self):
        x = copy.deepcopy(self.source)
        x["work"][0]["owner"] = "<script>alert(123)</script>"
        rendered = health.render(
            x, health.validate(self.source),
            health.route_work(self.source["work"],
                              self.source["runner_capacity"]),
            checkout_sha=self.source["authority"]["source_sha"],
        )
        self.assertNotIn("<script>alert(123)</script>", rendered)
        self.assertIn("&lt;script&gt;alert(123)&lt;/script&gt;", rendered)

    def test_all_defined_graph_atoms_are_rendered(self):
        svg = health.graph_svg(self.source)
        self.assertEqual(svg.count("<rect"), 26)
        self.assertEqual(svg.count("<path"), 30)  # 29 edges + 1 marker
        self.assertIn("aria-label", svg)

    def test_builder_emits_source_bound_html_dag_and_checksums(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sha = "a" * 40
            result = health.build(health.REGISTRY, root, checkout_sha=sha)
            self.assertEqual(result["checkout_sha"], sha)
            self.assertIsNone(result["crew_auth_launches"])
            self.assertEqual(result["admission"], "HOLD")
            manifest = json.loads(
                (root / "code-health-manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["checkout_sha"], sha)
            self.assertEqual(manifest["source_sha256"],
                             hashlib.sha256(health.REGISTRY.read_bytes()).hexdigest())
            for name, digest in manifest["files_sha256"].items():
                self.assertEqual(hashlib.sha256((root / name).read_bytes()).hexdigest(),
                                 digest)
            page = (root / "code-health.html").read_text(encoding="utf-8")
            self.assertIn("N−1 / N / N+1", page)
            self.assertIn("census", page.lower())
            self.assertIn("143", page)
            self.assertIn("Crew launches", page)
            self.assertNotIn("__SOURCE_CHECKOUT_SHA__", page)

    def test_postulated_forecast_can_only_be_scored_after_actual(self):
        observed = dict(self.source["forecasts"][0], actual_next=140)
        self.assertEqual(health.forecast_score(observed), 3)
        self.assertIsNone(health.forecast_score(self.source["forecasts"][0]))

    def test_local_path_is_proposed_not_claimed_accessed(self):
        local = next(p for p in self.source["pillars"] if p["id"] == "L")
        self.assertEqual(local["root_path_windows"], "C:\\repos")
        self.assertFalse(local["machine_accessed"])
        self.assertIsNone(local["runtime_receipts"])


if __name__ == "__main__":
    unittest.main()
