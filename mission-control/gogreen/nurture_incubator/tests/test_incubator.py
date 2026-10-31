"""G12 adversarial evidence and recovery tests. No network or secrets."""
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
import incubator as mod

SHA = "a" * 40


def specimen():
    return json.loads(
        (HERE / "samples" / "w4_w5_native_pulse.json").read_text(encoding="utf-8")
    )


class NativeIncubatorTests(unittest.TestCase):
    def test_canonical_recovery_but_no_root_closure(self):
        report = mod.summarize(specimen())
        self.assertEqual(report["matched_workflow_family_count"], 2)
        self.assertEqual(report["matched_success_recoveries"], 1)
        self.assertEqual(report["matched_success_regressions"], 0)
        self.assertEqual(report["roots"]["new_accepted_root_closures"], 0)
        self.assertEqual(report["interpretation"],
                         "DESCRIPTIVE_TRANSITIONS_NOT_INDEPENDENT_TRIALS")

    def test_distinct_wave_denominators_not_poolable(self):
        report = mod.summarize(specimen())
        self.assertEqual([x["native_workflow_families"] for x in
                          report["snapshots"]], [2, 4])
        self.assertEqual([x["terminal_failure"] for x in
                          report["snapshots"]], [1, 0])
        self.assertIsNone(report["matched_workflow_rate_delta"])
        self.assertEqual(report["same_head_repeat_trials"], 0)

    def test_statement_denominator_changed_branch_stable(self):
        c = mod.summarize(specimen())["coverage_comparison"]
        self.assertFalse(c["statements"]["scope_matched"])
        self.assertIsNone(c["statements"]["delta_percentage_points"])
        self.assertEqual(c["statements"]["baseline"], [116, 126])
        self.assertEqual(c["statements"]["current"], [125, 135])
        self.assertTrue(c["branches"]["scope_matched"])
        self.assertEqual(c["branches"]["delta_percentage_points"], 0)

    def test_census_breadth_is_historical_not_new(self):
        c = mod.summarize(specimen())["census"]
        self.assertEqual((c["historical_observed"], c["historical_eligible"]),
                         (6, 42))
        self.assertIsNone(c["fresh_source_bound_breadth"])
        self.assertEqual(c["new_breadth_credit"], 0)

    def test_root_ids_vs_signatures_vs_occurrences_distinct(self):
        roots = mod.summarize(specimen())["roots"]
        self.assertEqual((roots["historical_distinct_root_count"],
                          roots["historical_distinct_fingerprints"],
                          roots["historical_occurrences"]), (15, 68, 375))
        self.assertEqual(roots["observed_red_fingerprint_displacement"], 1)
        self.assertEqual(roots["causal_root_disposition"], "UNKNOWN_NOT_CREDITED")

    def test_capacity_m2_m3_pca_bt_and_forecast_not_fabricated(self):
        r = mod.summarize(specimen())
        self.assertEqual(r["maturity"]["M1"], "PARTIAL_SOURCE_BOUND")
        self.assertTrue(all(x is None or "NOT_QUALIFIED" in x for x in
                            r["statistical_readiness"].values()))
        self.assertTrue(all("HOLD" in x for x in
                            (r["maturity"]["M2"], r["maturity"]["M3"])))
        self.assertIsNone(r["capacity"]["worker_hours"])
        self.assertIsNone(r["capacity"]["runner_slots"])
        self.assertIsNone(r["next_wave"]["forecast_failure_count"])
        self.assertFalse(r["public_pages_deployed"])

    def test_forged_authority_rejected(self):
        for key in ("authority_transfer", "dispatch_authorized",
                    "merge_authorized", "security_waiver"):
            with self.subTest(key=key):
                d = specimen()
                d[key] = True
                with self.assertRaisesRegex(ValueError, "forbidden"):
                    mod.summarize(d)

    def test_qps_acceptance_invented_rejected(self):
        d = specimen()
        d["qps_owner_acceptance"] = "ACCEPT"
        with self.assertRaisesRegex(ValueError, "false external authority"):
            mod.validate(d)

    def test_forged_member_zip_proof_rejected(self):
        d = specimen()
        d["waves"][1]["observations"][2]["artifact"]["verified_in_this_wave"] = True
        with self.assertRaisesRegex(ValueError, "byte custody"):
            mod.validate(d)

    def test_malformed_sha_rejected(self):
        d = specimen()
        d["waves"][0]["source_sha"] = "HEAD"
        with self.assertRaisesRegex(ValueError, "wave source SHA"):
            mod.validate(d)

    def test_duplicate_wave_source_rejected(self):
        d = specimen()
        d["waves"][1]["source_sha"] = d["waves"][0]["source_sha"]
        with self.assertRaisesRegex(ValueError, "wave source SHA"):
            mod.validate(d)

    def test_repeat_native_identity_rejected(self):
        d = specimen()
        one = copy.deepcopy(d["waves"][0]["observations"][0])
        one["workflow"] = "OTHER_WORKFLOW"
        d["waves"][1]["observations"].append(one)
        with self.assertRaisesRegex(ValueError, "duplicate native run"):
            mod.validate(d)

    def test_duplicate_workflow_family_rejected(self):
        d = specimen()
        one = copy.deepcopy(d["waves"][1]["observations"][0])
        one["run_id"] += 1
        one["job_id"] += 1
        d["waves"][1]["observations"].append(one)
        with self.assertRaisesRegex(ValueError, "duplicate workflow family"):
            mod.validate(d)

    def test_nonterminal_not_proof(self):
        d = specimen()
        d["waves"][1]["observations"][0]["conclusion"] = "queued"
        with self.assertRaisesRegex(ValueError, "nonterminal"):
            mod.validate(d)

    def test_test_denominator_cannot_shrink(self):
        d = specimen()
        d["waves"][1]["observations"][0]["tests"]["executed"] = 49
        with self.assertRaisesRegex(ValueError, "test denominator"):
            mod.validate(d)

    def test_false_green_tests_rejected(self):
        d = specimen()
        o = d["waves"][1]["observations"][0]
        o["tests"]["passed"] = 49
        o["tests"]["failed"] = 1
        with self.assertRaisesRegex(ValueError, "false-green"):
            mod.validate(d)

    def test_first_red_requires_failed_native_job(self):
        d = specimen()
        d["waves"][1]["observations"][0]["first_red_fingerprint"] = "fake first red"
        with self.assertRaisesRegex(ValueError, "first red"):
            mod.validate(d)

    def test_fresh_census_not_inferred(self):
        d = specimen()
        d["census"]["fresh_observed"] = 7
        with self.assertRaisesRegex(ValueError, "stale census"):
            mod.validate(d)

    def test_census_observed_cannot_exceed_eligible(self):
        d = specimen()
        d["census"]["observed"] = 43
        with self.assertRaisesRegex(ValueError, "stale census"):
            mod.validate(d)

    def test_causal_root_closure_needs_external_disposition(self):
        d = specimen()
        d["historical_root_ledger"]["accepted_closed_root_ids"] = ["ABACUS-RC-2026-0001"]
        with self.assertRaisesRegex(ValueError, "fabricated causal closure"):
            mod.validate(d)

    def test_root_fingerprint_occurrence_invariant(self):
        d = specimen()
        d["historical_root_ledger"]["occurrences"] = 50
        with self.assertRaisesRegex(ValueError, "fabricated causal closure"):
            mod.validate(d)

    def test_worker_hours_unknown_is_not_zero(self):
        d = specimen()
        d["worker_hours"] = 0
        with self.assertRaisesRegex(ValueError, "unknown capacity"):
            mod.validate(d)

    def test_branch_numerator_exceeds_denominator(self):
        d = specimen()
        d["coverage"][-1]["branches"]["covered"] = 25
        with self.assertRaisesRegex(ValueError, "numerator exceeds"):
            mod.validate(d)

    def test_scope_mismatch_withholds_comparable_uplift(self):
        d = specimen()
        d["coverage"][-1]["scope"] = "other_module"
        report = mod.summarize(d)
        self.assertFalse(report["coverage_comparison"]["branches"]["scope_matched"])
        self.assertIsNone(report["coverage_comparison"]["branches"]["delta_percentage_points"])

    def test_wave_ordinal_monotone(self):
        d = specimen()
        d["waves"][1]["ordinal"] = 0
        with self.assertRaisesRegex(ValueError, "nonmonotone"):
            mod.validate(d)

    def test_sipoc_dag_feedback_next_pulse(self):
        dag = mod.spine(mod.summarize(specimen()))
        self.assertEqual(len(dag["nodes"]), 6)
        self.assertEqual(len(dag["edges"]), 6)
        self.assertEqual(dag["edges"][-1]["type"],
                         "NEXT_PULSE_FEEDBACK_NOT_SAME_PULSE")
        self.assertFalse(dag["merge_authorized"])

    def test_offline_html_svg_mermaid_no_auto_deploy(self):
        report = mod.summarize(specimen())
        page = mod.render_html(report)
        self.assertIn("N-1", page)
        self.assertIn("No live API polling", page)
        self.assertNotIn("<script", page)
        dag = mod.spine(report)
        self.assertIn("svg", mod.render_svg(dag))
        self.assertIn("next pulse", mod.render_mermaid(dag))

    def test_preview_build_deterministic_manifest_and_check(self):
        with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
            a, b = Path(t1), Path(t2)
            data = specimen()
            _, manifest = mod.build(data, SHA, a)
            mod.build(data, SHA, b)
            self.assertEqual(sorted(x.name for x in a.iterdir()),
                             sorted(x.name for x in b.iterdir()))
            for name in manifest["file_sha256"]:
                raw = (a / name).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(),
                                 manifest["file_sha256"][name])
                self.assertEqual(raw, (b / name).read_bytes())
            mod.build(data, SHA, a, check=True)
            self.assertFalse(manifest["merge_authorized"])
            self.assertFalse(manifest["external_zip_member_bytes_verified"])

    def test_preview_byte_mutation_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            data = specimen()
            mod.build(data, SHA, p)
            (p / "index.html").write_text("corrupted", encoding="utf-8", newline="\n")
            with self.assertRaisesRegex(ValueError, "generated preview drift"):
                mod.build(data, SHA, p, check=True)

    def test_unknown_incubator_sha_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "exact-head identity"):
                mod.build(specimen(), "main", Path(tmp))


if __name__ == "__main__":
    unittest.main()


def test_zz_canary_g_pah():
    assert False, "red canary: proves CI collects this family"
