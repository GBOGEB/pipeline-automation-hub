import json
import unittest
from pathlib import Path
from metric_atlas.census import request, rollup
from metric_atlas.census_dashboard import cohort, render

ROOT = Path(__file__).resolve().parents[1]
H = {"ABACUS":"a"*40,"CODEX":"b"*40,"QPS_ENGINEERING":None}


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.manifest = request('N2', H)
        self.rollup = rollup(self.manifest, [])
        self.ledger = json.loads((ROOT/'data/observations.json').read_text())

    def test_private_lane_visible(self):
        output = render(self.manifest,self.rollup,self.ledger)
        self.assertIn('HOLD_SOURCE_HEAD_UNKNOWN',output)
        self.assertIn('3',output)

    def test_separate_absolute_and_relative_scales(self):
        output=render(self.manifest,self.rollup,self.ledger)
        self.assertIn("plot('stock')",output)
        self.assertIn("plot('delta')",output)
        self.assertIn("plot('relative')",output)
        self.assertIn('Method Atlas',output)

    def test_third_cohort_source_bound_and_normalized(self):
        series = cohort(self.ledger, "MC:QPS_CENSUS_CONTROLLER")
        self.assertEqual(series["baseline"], 39)
        self.assertEqual(series["latest"], 48)
        self.assertEqual(series["delta"], 9)
        self.assertAlmostEqual(series["index"], 123.077, places=3)
        output = render(self.manifest, self.rollup, self.ledger)
        self.assertIn("QPS census controller", output)

    def test_census_native_growth_does_not_credit_receiver(self):
        output = render(self.manifest, self.rollup, self.ledger)
        self.assertIn("Measured test/coverage uplift", output)
        self.assertEqual(self.rollup["observed_repos"], 0)
        self.assertEqual(self.rollup["native_job_receipts"], 0)

    def test_no_fake_executed_tests(self):
        output=render(self.manifest,self.rollup,self.ledger)
        self.assertIn('not new N1 receiver test executions',output)
        self.assertIn('Current mode: plan and dry-run only',output)

    def test_wave_mismatch_fail_closed(self):
        self.rollup['wave']='other'
        with self.assertRaises(ValueError):
            render(self.manifest,self.rollup,self.ledger)


if __name__ == '__main__': unittest.main()
