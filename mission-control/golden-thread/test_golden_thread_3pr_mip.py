#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import unittest

import yaml

HERE = pathlib.Path(__file__).resolve().parent


class GoldenThread3PRMIPTests(unittest.TestCase):
    def _load(self, name):
        return yaml.safe_load((HERE / name).read_text(encoding="utf-8"))

    def test_three_pulse_refresh_preserves_authority_boundaries(self):
        receipt = self._load("GOLDEN_THREAD_3PR_MIP_M_20260917_v1.yaml")
        pulses = receipt["three_pulse_refresh"]

        self.assertEqual(list(pulses), ["P1_H1_QPS", "P2_H2_KEB", "P3_H3_DOW"])
        self.assertFalse(receipt["authority_transfer"])
        self.assertEqual(receipt["formal_credit_delta"], 0)
        self.assertEqual(receipt["engineering_credit_delta"], 0)
        self.assertEqual(pulses["P1_H1_QPS"]["first_red"], "GT_BDQ_0_EXACT_HEAD_HOSTED_REPLAY_PROOF")
        self.assertFalse(pulses["P1_H1_QPS"]["qps_gt_bdq_credit_from_missioncontrol"])
        self.assertFalse(pulses["P2_H2_KEB"]["new_semantic_framework_required"])
        self.assertTrue(pulses["P3_H3_DOW"]["measured_result"]["hosted_execution"])
        self.assertEqual(pulses["P3_H3_DOW"]["measured_result"]["quality_gate"], "PASS")

    def test_mip_modernizes_only_measured_stale_frontier_gap(self):
        receipt = self._load("GOLDEN_THREAD_3PR_MIP_M_20260917_v1.yaml")
        mip = receipt["mip_m"]
        self.assertTrue(mip["justified_by_observed_gap"])
        self.assertTrue(mip["modernization"]["base_bdq_preserved"])
        self.assertEqual(mip["modernization"]["strategy"], "APPEND_ONLY_CURRENT_OVERLAY")
        self.assertIn("QPS_GT_BDQ_0_advance", mip["forbidden"])
        self.assertEqual(receipt["next_first_red"], "GT-BD-003_REAL_CHILD_GATE_RESET_RECEIPT")

    def test_current_frontier_orders_closed_items_after_active_first_red(self):
        frontier = self._load("GOLDEN_THREAD_FRONTIER_CURRENT_v1.yaml")
        self.assertFalse(frontier["authority_transfer"])
        self.assertEqual(frontier["qps_boundary"]["current_first_red"], "GT_BDQ_0_EXACT_HEAD_HOSTED_REPLAY_PROOF")
        self.assertFalse(frontier["qps_boundary"]["compensation_allowed"])
        self.assertEqual(frontier["frontier"]["GT-BD-006"]["state"], "DONE")
        self.assertEqual(frontier["frontier"]["GT-BD-002"]["state"], "DONE")
        self.assertEqual(frontier["frontier"]["GT-BD-003"]["state"], "ACTIVE")
        self.assertEqual(frontier["priority_order"][0], "GT-BD-003")
        self.assertEqual(frontier["frontier"]["GT-BD-003"]["recommended_method"], "3PC")
        self.assertFalse(frontier["frontier"]["GT-BD-002"]["qps_credit"])
        self.assertFalse(frontier["frontier"]["GT-BD-011"]["fleet_wide_completion"])


if __name__ == "__main__":
    unittest.main()
