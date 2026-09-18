import unittest

from temporal_regression_diagnostics import diagnose


class TemporalRegressionDiagnosticTests(unittest.TestCase):
    def fixture(self):
        def edge(cell_id, habitat, lane, winner, a, b):
            return {
                "cell_id": cell_id,
                "habitat": habitat,
                "lane": lane,
                "winner": winner,
                "relative_gap": abs(a-b)/max(a,b),
                "seconds_a": a,
                "seconds_b": b,
                "comparable": True,
            }
        return {
            "source_sha": "f226e6e61bc84482d4856f056b292ca9322e22f8",
            "run_id": "35350275999",
            "bt_conditional_by_task_class": {
                "short_compute": {
                    "observed_pairs": 6,
                    "nodes": [
                        {"strategy": "ALLOC_PAIRED_CELL", "normalized_strength": 0.5},
                        {"strategy": "ALLOC_SINGLE_CELL", "normalized_strength": 0.5},
                    ],
                    "edges": [
                        edge("linux-baseline","linux","baseline","ALLOC_SINGLE_CELL",0.012736,0.013129),
                        edge("linux-held","linux","held","ALLOC_PAIRED_CELL",0.012638,0.011866),
                        edge("macos-baseline","macos","baseline","ALLOC_SINGLE_CELL",0.013138,0.026826),
                        edge("macos-held","macos","held","ALLOC_SINGLE_CELL",0.007196,0.007730),
                        edge("windows-baseline","windows","baseline","ALLOC_PAIRED_CELL",0.017633,0.015839),
                        edge("windows-held","windows","held","ALLOC_PAIRED_CELL",0.018731,0.017294),
                    ],
                }
            },
        }

    def test_current_short_regression_decomposition(self):
        result = diagnose(self.fixture(), "short_compute", 0.7008026572612402, 114)
        self.assertEqual(result["global_counts"], {"ALLOC_SINGLE_CELL": 3, "ALLOC_PAIRED_CELL": 3})
        self.assertEqual(result["global_direction"], "INDETERMINATE")
        self.assertEqual(result["global_single_normalized_strength"], 0.5)
        self.assertEqual(result["by_habitat"]["linux"]["direction"], "INDETERMINATE")
        self.assertEqual(result["by_habitat"]["macos"]["direction"], "ALLOC_SINGLE_CELL")
        self.assertEqual(result["by_habitat"]["windows"]["direction"], "ALLOC_PAIRED_CELL")
        self.assertEqual(result["by_lane"]["baseline"]["direction"], "ALLOC_SINGLE_CELL")
        self.assertEqual(result["by_lane"]["held"]["direction"], "ALLOC_PAIRED_CELL")
        self.assertEqual(result["regime"], "HABITAT_AND_LANE_HETEROGENEITY_OBSERVED")
        self.assertAlmostEqual(
            result["weighted_history_identity"]["recomputed_pooled_single_strength"],
            0.6907625243981782,
            places=15,
        )
        self.assertFalse(result["authority_transfer"])
        self.assertEqual(result["competency_promotions"], 0)


if __name__ == "__main__":
    unittest.main()
