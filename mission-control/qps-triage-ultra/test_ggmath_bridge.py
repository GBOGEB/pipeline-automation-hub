"""Unit and negative controls for the QPS TRIAGE / gg_MATH bridge.

Covers: digest-mismatch fail-closed fetch and import, no authority promotion,
Bradley-Terry never fed PCA-generated wins, reverse trials only when
independently observed, flow KPI identities, deterministic Plotly JSON and the
disabled-by-default JADE hook.

Kernel-executing tests fetch the pinned provider by exact SHA.  Offline they are
skipped unless GGMATH_REQUIRE_PROVIDER=1 (set in CI), where a failed fetch fails.
"""
import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ggmath_bridge as gb  # noqa: E402
import ggmath_flow_kpi as fk  # noqa: E402
import ggmath_jade_hook as jh  # noqa: E402
import ggmath_plotly as gp  # noqa: E402

BINDING = json.loads((HERE / "ggmath_provider_binding_v1.json").read_text(encoding="utf-8"))
RECEIPT_BYTES = (HERE / "ggmath_bridge_receipt.json").read_bytes()
RECEIPT = json.loads(RECEIPT_BYTES)
FIGURES_PATH = HERE / "site" / "_data" / "ggmath_bridge_figures.json"
TELEMETRY = json.loads((HERE / "w3_fleet_telemetry.json").read_text(encoding="utf-8"))
OBSERVATIONS = json.loads((HERE / "w3_bt_observations.json").read_text(encoding="utf-8"))
LEDGER = json.loads((HERE / "analytics" / "EXPEDITION_FLEET_ITERATION_LEDGER_v1.json").read_text(encoding="utf-8"))
TASK_KERNELS = {
    "kernels/bt_uncertainty.py", "kernels/pca_uncertainty.py", "kernels/pca_alignment.py",
    "kernels/rmt_calibration.py", "kernels/convergence_control.py", "kernels/temporal_subspace_trace.py",
    "kernels/temporal_pca_receipt.py", "kernels/visual_engine_bridge.py", "kernels/uncertainty.py",
    "kernels/stats_core.py",
}


def synthetic_binding(files: dict) -> dict:
    """Committed binding with its bound files replaced by in-test kernels."""
    b = copy.deepcopy(BINDING)
    b["provider_sha"] = "0" * 40
    b["bridged_kernels"] = [{"path": p, "sha256": gb.sha256_bytes(data), "role": "BRIDGED"} for p, data in files.items()]
    b["provider_data"] = []
    return b


class Binding(unittest.TestCase):
    def test_committed_binding_is_exact_and_complete(self):
        b = gb.validate_binding(copy.deepcopy(BINDING))
        self.assertRegex(b["provider_sha"], r"^[0-9a-f]{40}$")
        bound = {e["path"] for e in b["bridged_kernels"]}
        self.assertTrue(TASK_KERNELS <= bound, TASK_KERNELS - bound)
        self.assertFalse(b["authority_transfer"])
        for name, spec in b["outputs"].items():
            self.assertIn(spec["threshold_kind"], gb.THRESHOLD_KINDS, name)

    def test_binding_rejects_promotion_and_inexact_identity(self):
        cases = {
            "authority": lambda b: b.update(authority_transfer=True),
            "short sha": lambda b: b.update(provider_sha="e857f44"),
            "bad digest": lambda b: b["bridged_kernels"][0].update(sha256="abc"),
            "pca as bt": lambda b: b["boundaries"].update(pca_outputs_are_bt_evidence=True),
            "swapped reverse": lambda b: b["boundaries"].update(reverse_trials_from_swapped_labels=True),
            "threshold kind": lambda b: b["outputs"]["pca_pa95"].update(threshold_kind="VIBES"),
            "path escape": lambda b: b["bridged_kernels"][0].update(path="../x.py"),
        }
        for label, fn in cases.items():
            with self.subTest(label=label):
                b = copy.deepcopy(BINDING)
                fn(b)
                with self.assertRaises(gb.BridgeHold) as ctx:
                    gb.validate_binding(b)
                self.assertEqual(ctx.exception.status, "DEFER_BINDING_INVALID")


class DigestFailClosed(unittest.TestCase):
    GOOD = b"VALUE = 41\n"

    def setUp(self):
        gb.unload_kernels()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "provider" / "kernels").mkdir(parents=True)
        (self.root / "provider" / "kernels" / "answer.py").write_bytes(self.GOOD)
        self.binding = synthetic_binding({"kernels/answer.py": self.GOOD})

    def tearDown(self):
        gb.unload_kernels()
        self.tmp.cleanup()

    def test_verified_fetch_then_import(self):
        root = gb.fetch_provider(self.binding, cache=self.root / "cache", provider_root=self.root / "provider")
        pk = gb.ProviderKernels(self.binding, root)
        self.assertEqual(pk.module("answer").VALUE, 41)

    def test_tampered_provider_source_is_never_cached(self):
        (self.root / "provider" / "kernels" / "answer.py").write_bytes(b"VALUE = 42\n")
        with self.assertRaises(gb.BridgeHold) as ctx:
            gb.fetch_provider(self.binding, cache=self.root / "cache", provider_root=self.root / "provider")
        self.assertEqual(ctx.exception.status, "DEFER_PROVIDER_DIGEST_MISMATCH")
        self.assertFalse((self.root / "cache" / ("0" * 40) / "kernels" / "answer.py").exists())

    def test_tampered_network_bytes_fail_closed(self):
        with self.assertRaises(gb.BridgeHold) as ctx:
            gb.fetch_provider(self.binding, cache=self.root / "cache", fetcher=lambda url: b"VALUE = 0\n")
        self.assertEqual(ctx.exception.status, "DEFER_PROVIDER_DIGEST_MISMATCH")

    def test_tampered_cache_fails_at_import_verification(self):
        root = gb.fetch_provider(self.binding, cache=self.root / "cache", provider_root=self.root / "provider")
        (root / "kernels" / "answer.py").write_bytes(b"VALUE = 666\n")
        with self.assertRaises(gb.BridgeHold) as ctx:
            gb.ProviderKernels(self.binding, root)
        self.assertEqual(ctx.exception.status, "DEFER_PROVIDER_DIGEST_MISMATCH")

    def test_missing_file_and_unbound_import_defer(self):
        with self.assertRaises(gb.BridgeHold) as ctx:
            gb.verify_provider(self.binding, self.root / "nowhere")
        self.assertEqual(ctx.exception.status, "DEFER_PROVIDER_FILE_MISSING")
        sneaky = b"import kernels.unbound\n"
        (self.root / "provider" / "kernels" / "sneaky.py").write_bytes(sneaky)
        binding = synthetic_binding({"kernels/sneaky.py": sneaky})
        root = gb.fetch_provider(binding, cache=self.root / "cache2", provider_root=self.root / "provider")
        with self.assertRaises(gb.BridgeHold) as ctx:
            gb.ProviderKernels(binding, root).module("sneaky")
        self.assertEqual(ctx.exception.status, "DEFER_UNBOUND_PROVIDER_MODULE")

    def test_foreign_kernels_package_is_a_collision(self):
        with mock.patch.dict(sys.modules, {"kernels": type(sys)("kernels")}):
            root = gb.fetch_provider(self.binding, cache=self.root / "cache", provider_root=self.root / "provider")
            with self.assertRaises(gb.BridgeHold) as ctx:
                gb.ProviderKernels(self.binding, root)
            self.assertEqual(ctx.exception.status, "DEFER_KERNEL_NAMESPACE_COLLISION")


class NoPromotion(unittest.TestCase):
    def test_nested_promotions_are_rejected(self):
        for bad in ({"authority_transfer": True}, {"a": [{"engineering_acceptance": True}]},
                    {"merge_admission": "MERGE"}, {"formal_credit_delta": 1},
                    {"x": {"six_sigma_achievement_proven": True}}):
            with self.subTest(bad=bad):
                with self.assertRaises(gb.BridgeHold) as ctx:
                    gb.assert_no_promotion(bad)
                self.assertEqual(ctx.exception.status, "DEFER_AUTHORITY_PROMOTION_REJECTED")
        gb.assert_no_promotion({"authority_transfer": False, "merge_admission": "HOLD", "qps_acceptance": None})

    def test_committed_receipt_and_figures_never_promote(self):
        gb.assert_no_promotion(RECEIPT)
        self.assertFalse(RECEIPT["authority_transfer"])
        for name, env in RECEIPT["measured"].items():
            with self.subTest(adapter=name):
                self.assertFalse(env["authority_transfer"])
                self.assertTrue(env["status"].startswith(("PASS", "DEFER", "RESEARCH_TODO")))
        self.assertFalse(json.loads(FIGURES_PATH.read_text(encoding="utf-8"))["authority_transfer"])


class BTAdmission(unittest.TestCase):
    SOURCES = BINDING["boundaries"]["bt_admissible_outcome_sources"]

    def record(self, **kw):
        base = {"winner": "A", "loser": "B", "outcome_source": "OBSERVED_PAIRWISE_OUTCOME", "evidence_class": "MEASURED"}
        base.update(kw)
        return base

    def test_pca_generated_wins_are_rejected(self):
        cases = {
            "pca score order": self.record(outcome_source="PCA_SCORE_ORDER"),
            "pc score payload": self.record(pc_score=1.7),
            "loadings payload": self.record(loadings=[[0.1]]),
            "derived from pca": self.record(derived_from="pca_retention"),
            "pca envelope": {**RECEIPT["measured"]["pca_retention_w3_fleet"], "winner": "A", "loser": "B"},
            "bt_admissible false": self.record(bt_admissible=False),
            "rmt": self.record(derived_from="rmt_calibration"),
        }
        for label, rec in cases.items():
            with self.subTest(label=label):
                with self.assertRaises(gb.BridgeHold) as ctx:
                    gb.admit_bt_records([rec], self.SOURCES)
                self.assertEqual(ctx.exception.status, "DEFER_PCA_DERIVED_WIN_REJECTED")

    def test_unobserved_or_unmeasured_outcomes_are_rejected(self):
        for rec, status in ((self.record(outcome_source="EXPERT_SEED"), "DEFER_BT_OUTCOME_SOURCE_NOT_OBSERVED"),
                            (self.record(evidence_class="SEEDED"), "DEFER_BT_NON_MEASURED_EVIDENCE")):
            with self.subTest(status=status):
                with self.assertRaises(gb.BridgeHold) as ctx:
                    gb.admit_bt_records([rec], self.SOURCES)
                self.assertEqual(ctx.exception.status, status)

    def test_w3_pairs_reuse_the_w3_15_gate(self):
        self.assertEqual(len(gb.w3_pairs_for_bt(copy.deepcopy(OBSERVATIONS))), 2)
        bad = copy.deepcopy(OBSERVATIONS)
        bad["current_frontier"]["pairs"][0]["control_repeat_outcome"] = "FAIL"
        with self.assertRaises(gb.BridgeHold) as ctx:
            gb.w3_pairs_for_bt(bad)
        self.assertEqual(ctx.exception.status, "DEFER_PAIR_EVIDENCE_VALIDATION_FAILED")


class FlowKPI(unittest.TestCase):
    def test_committed_gm_i_a_fast_lane_queue_dominates(self):
        kpi = RECEIPT["measured"]["flow_kpi_gm_i_a"]
        self.assertEqual(kpi["status"], "PASS_FLOW_KPI")
        self.assertAlmostEqual(kpi["lanes"]["fast"]["flow_efficiency"], 7 / 519, places=9)
        self.assertAlmostEqual(kpi["lanes"]["fast"]["queue_execute_ratio"], 512 / 7, places=6)
        self.assertEqual(kpi["fleet"]["dominant_component"], "QUEUE_ADMISSION")
        little = kpi["littles_law_consistency"]["GM-I-A-MCLOCK-P001"]
        self.assertEqual(little["status"], "PASS_LITTLES_LAW_CONSISTENT")
        self.assertFalse(little["steady_state_claimed"])
        self.assertEqual(kpi["threshold_kind"]["littles_law_consistency"], "EXACT_IDENTITY")

    def test_fleet_ledger_excludes_unexecuted_iterations(self):
        kpi = fk.flow_kpi(fk.jobs_from_fleet_ledger(LEDGER), source="analytics/EXPEDITION_FLEET_ITERATION_LEDGER_v1.json",
                          source_sha=None,
                          excluded=fk.excluded_from_fleet_ledger(LEDGER))
        self.assertEqual(kpi["status"], "PASS_FLOW_KPI")
        self.assertEqual(len(kpi["jobs"]), 5)
        self.assertEqual({e["result"] for e in kpi["excluded"]}, {"QUEUED", "STATIC_REPAIR_MERGED"})
        self.assertEqual(gb.jsonable(kpi), RECEIPT["measured"]["flow_kpi_fleet_ledger"])

    def jobs(self):
        return fk.jobs_from_fleet_ledger(LEDGER)

    def test_inconsistent_or_missing_measurements_defer(self):
        drift = self.jobs()
        drift[0]["queue_seconds"] += 30  # feature no longer matches timestamps
        self.assertEqual(fk.flow_kpi(drift, source="t", source_sha=None)["status"], "DEFER_FLOW_KPI_INCONSISTENT")
        missing = self.jobs()
        missing[0]["execute_seconds"] = None
        missing[0]["completed"] = None
        self.assertTrue(fk.flow_kpi(missing, source="t", source_sha=None)["status"].startswith("DEFER"))
        order = self.jobs()
        order[0]["completed"] = "2000-01-01T00:00:00Z"
        self.assertEqual(fk.flow_kpi(order, source="t", source_sha=None)["status"], "DEFER_TIMESTAMP_ORDER_INVALID")
        nan = self.jobs()
        nan[0]["queue_seconds"] = float("nan")
        self.assertEqual(fk.flow_kpi(nan, source="t", source_sha=None)["status"],
                         "DEFER_MISSING_MEASUREMENT_NO_IMPUTATION")

    def test_occupancy_sweep_matches_littles_identity(self):
        kpis = [fk._job_kpi(j) for j in self.jobs()]
        little = fk.littles_law(kpis)
        self.assertLess(little["relative_residual"], 1e-12)
        self.assertEqual(fk.littles_law(kpis[:1])["status"], "DEFER_INSUFFICIENT_JOBS")


class DeterministicPlotly(unittest.TestCase):
    def test_figure_json_is_byte_stable_and_committed(self):
        a = gp.dumps(gp.build_figures(json.loads(RECEIPT_BYTES), RECEIPT_BYTES))
        b = gp.dumps(gp.build_figures(json.loads(RECEIPT_BYTES), RECEIPT_BYTES))
        self.assertEqual(a, b)
        self.assertEqual(a, FIGURES_PATH.read_text(encoding="utf-8"))
        self.assertEqual(json.loads(a)["receipt_sha256"], gb.sha256_text(HERE / "ggmath_bridge_receipt.json"))

    def test_required_figures_and_labels(self):
        doc = json.loads(FIGURES_PATH.read_text(encoding="utf-8"))
        ids = {f["id"] for f in doc["figures"]}
        self.assertTrue({"scree_w3_fleet", "bt_strength_w3_current_frontier", "bt_rank_frequency_w3_current_frontier",
                         "principal_angles_reference", "grassmann_history_reference",
                         "convergence_velocity_reference", "flow_gm_i_a"} <= ids)
        for f in doc["figures"]:
            with self.subTest(figure=f["id"]):
                self.assertIn(f["status"].split("_")[0], ("PASS", "DEFER"))
                title = f["figure"]["layout"]["title"]["text"]
                self.assertTrue(f["status"] in title or f["evidence_class"] in title)
                if f["id"].endswith("_reference"):
                    self.assertEqual(f["evidence_class"], "SYNTHETIC_REFERENCE")
                    self.assertIn("SYNTHETIC_REFERENCE", title)
        scree = next(f for f in doc["figures"] if f["id"] == "scree_w3_fleet")
        names = [t["name"] for t in scree["figure"]["data"]]
        self.assertIn("MP upper edge (asymptotic)", names)
        self.assertIn("PA95 null threshold", names)

    def test_canonical_rounding_and_tolerant_compare(self):
        self.assertEqual(gp.canon({"x": [1 / 3, float("inf"), -0.0]}), {"x": [0.333333, None, 0.0]})
        doc = json.loads(FIGURES_PATH.read_text(encoding="utf-8"))
        self.assertEqual(gp.compare_figure_docs(doc, copy.deepcopy(doc)), [])
        moved = copy.deepcopy(doc)
        moved["figures"][0]["status"] = "PASS_SOMETHING_ELSE"
        self.assertTrue(gp.compare_figure_docs(doc, moved))

    def test_plotly_accepts_every_figure(self):
        try:
            import plotly  # noqa: F401
        except ImportError:
            self.skipTest("plotly not installed")
        doc = json.loads(FIGURES_PATH.read_text(encoding="utf-8"))
        self.assertEqual(gp.validate_with_plotly(doc), len(doc["figures"]))

    def test_site_surface_is_offline(self):
        page = (HERE / "site" / "ggmath-bridge.md").read_text(encoding="utf-8")
        loader = (HERE / "site" / "assets" / "js" / "ggmath-bridge.js").read_text(encoding="utf-8")
        for text in (page, loader):
            self.assertNotRegex(text, r"https?://")
        self.assertIn("data-ggmath-provider-sha", page)


class JadeHook(unittest.TestCase):
    HOOK = json.loads((HERE / "ggmath_jade_hook_v1.json").read_text(encoding="utf-8"))

    def test_disabled_by_default(self):
        self.assertIs(self.HOOK["enabled"], False)
        with self.assertRaises(jh.HookHold) as ctx:
            jh.jade_annotation(RECEIPT, copy.deepcopy(self.HOOK))
        self.assertEqual(ctx.exception.status, "DEFER_JADE_HOOK_DISABLED")

    def test_enabled_hook_waits_for_engine_then_stays_read_only(self):
        hook = dict(copy.deepcopy(self.HOOK), enabled=True)
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(jh.HookHold) as ctx:
                jh.jade_annotation(RECEIPT, hook, Path(d))
            self.assertEqual(ctx.exception.status, "DEFER_JADE_TARGET_NOT_ON_MASTER")
            for rel in hook["activation"]["requires_on_master"]:
                (Path(d) / rel).parent.mkdir(parents=True, exist_ok=True)
                (Path(d) / rel).write_text("{}", encoding="utf-8")
            doc = jh.jade_annotation(RECEIPT, hook, Path(d))
        self.assertEqual(doc["schema"], jh.ANNOTATION_SCHEMA)
        self.assertFalse(doc["authority_transfer"] or doc["release_credit"] or doc["changes_jade_gates"])
        self.assertIn("GBOGEB/CoolProp", doc["per_repo_queue_pressure"])

    def test_hook_cannot_grant_credit(self):
        for key in ("release_credit", "may_change_jade_gates", "pca_outputs_are_bt_evidence"):
            with self.subTest(key=key):
                hook = copy.deepcopy(self.HOOK)
                hook["contract"][key] = True
                with self.assertRaises(jh.HookHold) as ctx:
                    jh.validate_hook(hook)
                self.assertEqual(ctx.exception.status, "DEFER_AUTHORITY_PROMOTION_REJECTED")


class PinnedKernels(unittest.TestCase):
    """Executes the real pinned gg_MATH kernels (network or GGMATH_PROVIDER_ROOT)."""

    @classmethod
    def setUpClass(cls):
        gb.unload_kernels()
        try:
            cls.pk = gb.load_kernels(copy.deepcopy(BINDING))
        except gb.BridgeHold as hold:
            if os.environ.get("GGMATH_REQUIRE_PROVIDER") == "1" or hold.status != "DEFER_PROVIDER_FETCH_FAILED":
                raise
            raise unittest.SkipTest(f"pinned provider unavailable offline: {hold.status}")

    @classmethod
    def tearDownClass(cls):
        gb.unload_kernels()

    def test_modules_execute_from_pinned_bytes(self):
        mod = self.pk.module("bt_uncertainty")
        self.assertEqual(mod.__ggmath_sha__, BINDING["provider_sha"])
        self.assertTrue(mod.__spec__.origin.startswith("gg_MATH@"))

    def test_kernel_promotion_is_caught(self):
        bt = self.pk.module("bt_uncertainty")
        real = bt.finite_mle_guard
        with mock.patch.object(bt, "finite_mle_guard", lambda *a, **k: {**real(*a, **k), "authority_transfer": True}):
            with self.assertRaises(gb.BridgeHold) as ctx:
                gb.bt_strength(self.pk, gb.w3_pairs_for_bt(copy.deepcopy(OBSERVATIONS)), resamples=100)
        self.assertEqual(ctx.exception.status, "DEFER_AUTHORITY_PROMOTION_REJECTED")

    def test_bt_never_receives_pca_wins_end_to_end(self):
        fields = TELEMETRY["comparability_contract"]["required_common_numeric_fields"][:2]
        pca = self.pk.module("pca_reference").pca_reference([[r[f] for f in fields] for r in TELEMETRY["rows"]],
                                                             scale=True, components=1)
        order = sorted(range(len(pca["scores"])), key=lambda i: -pca["scores"][i][0])
        pca_wins = [{"winner": TELEMETRY["rows"][a]["mission_id"], "loser": TELEMETRY["rows"][b]["mission_id"],
                     "outcome_source": "OBSERVED_PAIRWISE_OUTCOME", "evidence_class": "MEASURED",
                     "derived_from": "pca_reference.scores"} for a, b in zip(order, order[1:])]
        with self.assertRaises(gb.BridgeHold) as ctx:
            gb.bt_strength(self.pk, pca_wins, resamples=100)
        self.assertEqual(ctx.exception.status, "DEFER_PCA_DERIVED_WIN_REJECTED")
        env = gb.pca_retention(self.pk, [[r[f] for f in fields] for r in TELEMETRY["rows"]], fields,
                               evidence_class="MEASURED")
        self.assertIs(env["bt_admissible"], False)
        with self.assertRaises(gb.BridgeHold):
            gb.bt_strength(self.pk, [dict(env, winner="a", loser="b")], resamples=100)

    def test_bt_classical_only_when_strongly_connected(self):
        env = gb.bt_strength(self.pk, gb.w3_pairs_for_bt(copy.deepcopy(OBSERVATIONS)), resamples=100)
        self.assertEqual(env["status"], "DEFER_NO_FINITE_MLE")
        self.assertFalse(env["result"]["reported_fit_is_classical_mle"])
        self.assertEqual(env["result"]["reported_fit"]["fit_kind"], "L2_PENALIZED_BT")
        cyc = [{"winner": w, "loser": l, "outcome_source": "OBSERVED_PAIRWISE_OUTCOME", "evidence_class": "MEASURED"}
               for w, l in (("a", "b"), ("b", "c"), ("c", "a"), ("a", "c"), ("a", "b"))]
        env = gb.bt_strength(self.pk, cyc, resamples=100)
        self.assertEqual(env["status"], "PASS_CLASSICAL_BT_MLE")
        self.assertEqual(env["threshold_kind"]["bt_log_strength_intervals"], "DISTRIBUTION_DERIVED")

    def trials(self):
        def t(tid, oid, pair, order, first, second, winner, **kw):
            return {"trial_id": tid, "observation_id": oid, "pair_id": pair, "order": order, "first": first,
                    "second": second, "winner": winner, "outcome_source": "OBSERVED_PAIRWISE_OUTCOME",
                    "evidence_class": "MEASURED", "observed_independently": order == "REVERSE", **kw}
        return [t("t1", "run-1", "AB", "FORWARD", "A", "B", "A"), t("t2", "run-2", "AB", "REVERSE", "B", "A", "A"),
                t("t3", "run-3", "AB", "FORWARD", "A", "B", "A"), t("t4", "run-4", "AB", "REVERSE", "B", "A", "B"),
                t("t5", "run-5", "BC", "FORWARD", "B", "C", "B"), t("t6", "run-6", "BC", "REVERSE", "C", "B", "B")]

    def test_order_effect_uses_independent_reverse_trials_only(self):
        env = gb.bt_order_effect(self.pk, self.trials())
        self.assertTrue(env["status"].startswith("PASS_ORDER_EFFECT"))
        self.assertEqual(env["result"]["pairs_with_forward_and_reverse"], 2)
        self.assertEqual(env["threshold_kind"]["bt_order_effect"], "DISTRIBUTION_DERIVED")
        cases = {
            "DEFER_REVERSE_TRIAL_NOT_INDEPENDENT": lambda ts: ts[1].update(observation_id="run-1"),
            "DEFER_SWAPPED_LABEL_REVERSE_REJECTED": lambda ts: ts[1].update(label_swapped=True),
            "DEFER_ORDER_ORIENTATION_MISMATCH": lambda ts: ts[1].update(first="A", second="B"),
        }
        for status, fn in cases.items():
            with self.subTest(status=status):
                ts = self.trials()
                fn(ts)
                with self.assertRaises(gb.BridgeHold) as ctx:
                    gb.bt_order_effect(self.pk, ts)
                self.assertEqual(ctx.exception.status, status)
        unflagged = self.trials()
        unflagged[1]["observed_independently"] = False
        with self.assertRaises(gb.BridgeHold) as ctx:
            gb.bt_order_effect(self.pk, unflagged)
        self.assertEqual(ctx.exception.status, "DEFER_REVERSE_TRIAL_NOT_INDEPENDENT")
        forward_only = [t for t in self.trials() if t["order"] == "FORWARD"]
        self.assertEqual(gb.bt_order_effect(self.pk, forward_only)["status"], "DEFER_NO_INDEPENDENT_REVERSE_TRIALS")

    def test_temporal_trace_matches_analytic_geodesic(self):
        env = gb.temporal_trace(self.pk, gb._synthetic_trace_states(self.pk), evidence_class="SYNTHETIC_REFERENCE")
        steps = [a["grassmann_geodesic_distance"] for a in env["result"]["trace"]["adjacent"]]
        for got, want in zip(steps, (0.10, 0.15, 0.05, 0.15)):
            self.assertAlmostEqual(got, want, places=9)
        self.assertEqual(len(env["result"]["multiclock_steps"]), 4)
        bad = gb.temporal_trace(self.pk, [dict(s, t="2026-10-01T00:00:00") for s in gb._synthetic_trace_states(self.pk)],
                                evidence_class="SYNTHETIC_REFERENCE")
        self.assertEqual(bad["status"], "DEFER_TEMPORAL_INPUT_REJECTED")

    def test_convergence_and_pca_defers(self):
        env = gb.convergence(self.pk, gb._synthetic_convergence_payload())
        self.assertEqual(env["result"]["receipt"]["classification"], "PLATEAU_DESCRIPTIVE_NOT_PROVEN_STABLE")
        promoted = dict(gb._synthetic_convergence_payload(), authority_transfer=True)
        self.assertEqual(gb.convergence(self.pk, promoted)["status"], "DEFER_CONVERGENCE_INPUT_REJECTED")
        tiny = gb.pca_retention(self.pk, [[1.0, 2.0], [2.0, 1.0]], ["a", "b"], evidence_class="MEASURED")
        self.assertEqual(tiny["status"], "DEFER_INSUFFICIENT_OBSERVATIONS")
        with self.assertRaises(gb.BridgeHold) as ctx:
            gb.pca_retention(self.pk, [[1.0, 2.0]] * 5, ["a", "b"], evidence_class="SEEDED")
        self.assertEqual(ctx.exception.status, "DEFER_NON_MEASURED_PCA_INPUT")

    def test_fresh_receipt_matches_committed_figures(self):
        fresh = json.dumps(gb.build_receipt(self.pk), indent=2, sort_keys=True).encode("utf-8")
        figures = json.loads(gp.dumps(gp.build_figures(json.loads(fresh), fresh)))
        self.assertEqual(gp.compare_figure_docs(json.loads(FIGURES_PATH.read_text(encoding="utf-8")), figures), [])


if __name__ == "__main__":
    unittest.main()
