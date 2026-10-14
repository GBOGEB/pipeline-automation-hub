"""MissionControl P4 math-wormhole routing negative controls."""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
from unittest import TestCase

MODULE = Path(__file__).resolve().parents[1] / "qps_math_wormhole_plan.py"
spec = importlib.util.spec_from_file_location("qps_math_wormhole_plan", MODULE)
assert spec and spec.loader
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
SHA = "a" * 40
DIGEST = "b" * 64


class WormholePlannerTests(TestCase):
    def test_plan_is_deterministic_and_explicitly_nonexecuting(self):
        a = m.plan(provider_sha=SHA, artifact_sha256=DIGEST)
        self.assertEqual(a, m.plan(provider_sha=SHA, artifact_sha256=DIGEST))
        m.verify(a)
        self.assertEqual("PLAN_ONLY_NO_DISPATCH", a["mode"])
        self.assertEqual("DEFER", a["qps_child_disposition"])
        self.assertEqual(0, a["measurements"]["workers_executed"])
        self.assertEqual(0, a["measurements"]["authenticated_stage_receipts"])

    def test_canonical_route_and_topological_edges(self):
        p = m.plan(provider_sha=SHA, artifact_sha256=DIGEST)
        self.assertEqual(
            ["GBOGEB/gg_MATH", "GBOGEB/CODEX", "GBOGEB/ABACUS",
             "GBOGEB/cryoplant-project", "GBOGEB/pipeline-automation-hub"],
            [step["repo"] for step in p["steps"]],
        )
        m.validate_dag(p["steps"])
        self.assertEqual("P1:SOURCE_BOUND_NATIVE_PROVIDER_PROOF",
                         p["measurements"]["first_red"])

    def test_reject_missing_or_invalid_provider_sha(self):
        for bad in ("", "UNKNOWN", "g"*40, "a"*39):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    m.plan(provider_sha=bad, artifact_sha256=DIGEST)

    def test_reject_missing_or_invalid_digest(self):
        for bad in ("", "sha256:pending", "b"*63):
            with self.assertRaises(ValueError):
                m.plan(provider_sha=SHA, artifact_sha256=bad)

    def test_cycle_or_out_of_order_dependency_rejected(self):
        p = m.plan(provider_sha=SHA, artifact_sha256=DIGEST)
        p["steps"][0]["needs"] = ["P4_RETURN"]
        with self.assertRaisesRegex(ValueError, "non-topological"):
            m.validate_dag(p["steps"])

    def test_duplicate_stage_rejected(self):
        p = m.plan(provider_sha=SHA, artifact_sha256=DIGEST)
        p["steps"][1]["id"] = "P1"
        with self.assertRaisesRegex(ValueError, "duplicate"):
            m.validate_dag(p["steps"])

    def test_route_authority_mutation_rejected(self):
        p = m.plan(provider_sha=SHA, artifact_sha256=DIGEST)
        p["authority_transfer"] = True
        with self.assertRaises(ValueError):
            m.verify(p)

    def test_fabricated_worker_proof_rejected(self):
        p = m.plan(provider_sha=SHA, artifact_sha256=DIGEST)
        p["steps"][0]["run_id"] = 1234
        p["steps"][0]["worker_executed"] = True
        with self.assertRaises(ValueError):
            m.verify(p)

    def test_qps_acceptance_cannot_be_inferred_from_plan(self):
        p = m.plan(provider_sha=SHA, artifact_sha256=DIGEST)
        p["qps_child_disposition"] = "ACCEPT"
        with self.assertRaises(ValueError):
            m.verify(p)

    def test_no_provenance_credit_without_authenticated_hops(self):
        p = m.plan(provider_sha=SHA, artifact_sha256=DIGEST)
        self.assertEqual(5, p["measurements"]["deferred_stages"])
        self.assertEqual(0, p["measurements"]["qps_dispositions"])
        self.assertEqual(0, p["formal_credit_delta"])
