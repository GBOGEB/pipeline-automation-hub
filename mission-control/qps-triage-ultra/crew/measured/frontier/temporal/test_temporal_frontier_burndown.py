import unittest

from temporal_frontier_burndown import build_burndown


class TemporalFrontierBurndownTests(unittest.TestCase):
    def config(self):
        return {
            "control_policy_gate": {
                "min_independent_windows": 6,
                "min_distinct_source_shas": 3,
                "min_temporal_span_seconds": 86400,
                "min_directional_windows": 5,
                "min_direction_consistency": 0.8,
                "min_pooled_winner_strength": 0.7,
                "latest_two_directional_windows_must_agree": True,
                "min_hosted_runner_classes": 3,
                "requires_baseline_and_held_lanes": True,
            }
        }

    def control(self, dominant, counts, consistency, strength, latest, *, windows=19):
        return {
            "independent_windows": windows,
            "distinct_source_shas": 11,
            "temporal_span_seconds": 389315.0,
            "directional_windows": sum(counts.values()),
            "direction_consistency": consistency,
            "pooled_winner_strength": strength,
            "latest_two_directional_windows_agree": latest,
            "hosted_runner_classes": ["linux", "macos", "windows"],
            "lanes": ["baseline", "held"],
            "dominant_direction": dominant,
            "direction_counts": counts,
        }

    def receipt(self):
        return {
            "mission_id": "MC-CREW-FRONTIER-004",
            "authority_transfer": False,
            "competency_promotions": 0,
            "scheduled_control_frontier": {"independent_windows": 19},
            "policies": {
                "cache_artifact_reuse": {
                    "policy_status": "CONTROL_POLICY",
                    "control_frontier": self.control(
                        "ALLOC_SINGLE_CELL", {"ALLOC_SINGLE_CELL": 19}, 1.0, 0.99, True
                    ),
                },
                "short_compute": {
                    "policy_status": "CONTROL_POLICY",
                    "control_frontier": self.control(
                        "ALLOC_SINGLE_CELL",
                        {"ALLOC_SINGLE_CELL": 15, "ALLOC_PAIRED_CELL": 1},
                        0.9375,
                        0.7008,
                        True,
                    ),
                },
                "validation_bundle": {
                    "policy_status": "CONTROL_POLICY",
                    "control_frontier": self.control(
                        "ALLOC_PAIRED_CELL", {"ALLOC_PAIRED_CELL": 19}, 1.0, 0.994, True
                    ),
                },
                "human_dependency_wait_proxy": {
                    "policy_status": "LEARNING_DIRECTION_UNSTABLE",
                    "control_frontier": self.control(
                        "ALLOC_SINGLE_CELL",
                        {"ALLOC_SINGLE_CELL": 11, "ALLOC_PAIRED_CELL": 4},
                        11 / 15,
                        0.6212672162393283,
                        False,
                    ),
                },
                "long_compute_contended": {
                    "policy_status": "LEARNING_DIRECTION_UNSTABLE",
                    "control_frontier": self.control(
                        "ALLOC_PAIRED_CELL",
                        {"ALLOC_PAIRED_CELL": 9, "ALLOC_SINGLE_CELL": 5},
                        9 / 14,
                        0.5987602959653776,
                        False,
                    ),
                },
            },
            "temporal_surveillance": {
                "horizons": {
                    "H2_72H": {"target_span_seconds": 259200, "mature": True},
                    "H3_7D": {"target_span_seconds": 604800, "mature": False},
                },
                "classes": {
                    "human_dependency_wait_proxy": {
                        "direction_flip_count": 7,
                        "indeterminate_window_fraction": 4 / 19,
                        "early_direction": "ALLOC_SINGLE_CELL",
                        "late_direction": "ALLOC_SINGLE_CELL",
                        "early_vs_late_direction_agreement": True,
                        "jackknife": {
                            "min_pooled_winner_strength": 0.600553303416023,
                            "direction_preservation_fraction": 1.0,
                        },
                    },
                    "long_compute_contended": {
                        "direction_flip_count": 3,
                        "indeterminate_window_fraction": 5 / 19,
                        "early_direction": "ALLOC_PAIRED_CELL",
                        "late_direction": "ALLOC_SINGLE_CELL",
                        "early_vs_late_direction_agreement": False,
                        "jackknife": {
                            "min_pooled_winner_strength": 0.5803153551429414,
                            "direction_preservation_fraction": 1.0,
                        },
                    },
                },
            },
        }

    def test_current_frontier_is_ranked_and_bounded(self):
        result = build_burndown(self.receipt(), self.config())
        self.assertEqual(
            result["control_classes"],
            ["cache_artifact_reuse", "short_compute", "validation_bundle"],
        )
        self.assertFalse(result["full_control_policy"])
        self.assertEqual(result["control_class_count"], 3)
        self.assertEqual(len(result["active_frontier"]), 2)

        long_row = result["active_frontier"][0]
        human_row = result["active_frontier"][1]
        self.assertEqual(long_row["task_class"], "long_compute_contended")
        self.assertEqual(long_row["regime_classification"], "REGIME_REVERSAL_OBSERVED")
        self.assertEqual(long_row["first_red_gate"], "direction_consistency")
        self.assertEqual(long_row["min_consecutive_clean_dominant_windows_to_consistency"], 11)

        self.assertEqual(human_row["task_class"], "human_dependency_wait_proxy")
        self.assertEqual(human_row["regime_classification"], "WEAK_OR_NOISY_DIRECTION")
        self.assertEqual(human_row["first_red_gate"], "direction_consistency")
        self.assertEqual(human_row["min_consecutive_clean_dominant_windows_to_consistency"], 5)
        self.assertEqual(
            human_row["claim_boundary"],
            "CONTROLLED_WAIT_PROXY_ONLY_NOT_REAL_HUMAN_INTERVENTION_EVIDENCE",
        )

    def test_global_clock_gate_failure_precedes_class_specific_red(self):
        receipt = self.receipt()
        receipt["policies"]["long_compute_contended"]["control_frontier"]["independent_windows"] = 5
        result = build_burndown(receipt, self.config())
        row = next(x for x in result["active_frontier"] if x["task_class"] == "long_compute_contended")
        self.assertEqual(row["first_red_gate"], "independent_windows")

    def test_authority_transfer_fails_closed(self):
        receipt = self.receipt()
        receipt["authority_transfer"] = True
        with self.assertRaises(ValueError):
            build_burndown(receipt, self.config())


if __name__ == "__main__":
    unittest.main()
