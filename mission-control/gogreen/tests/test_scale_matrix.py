"""G2 local bounded scaling and queue telemetry controls."""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('scale_matrix',ROOT/'scale_matrix.py')
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
from synthetic_probe import percentile_ns

class ScalingControls(unittest.TestCase):
    def test_matrix_profiles_bounds_and_admission(self):
        x=mod.matrix()
        self.assertEqual(4,x['profile_count'])
        self.assertEqual(280,x['total_task_observations'])
        self.assertIsNone(x['real_child_capacity'])
        self.assertIsNone(x['independent_native_runs'])
        self.assertEqual('NOT_ESTABLISHED',x['statistical_stability'])
        self.assertFalse(x['merge_authorized'])
        self.assertEqual('DEFER',x['child_acceptance'])
        for row in x['profiles']:
            for c in row['probe']['iterations']:
                self.assertLessEqual(c['max_queue'],row['probe']['bounds']['queue_depth'])
                self.assertLessEqual(c['peak_in_flight'],row['probe']['bounds']['workers'])
                self.assertGreater(c['elapsed_ns'],0)
                self.assertGreaterEqual(c['queue_wait_p95_ns'],c['queue_wait_p50_ns'])
        self.assertEqual(2,x['profiles'][-1]['fault_count'])

    def test_reject_unbounded_matrix(self):
        with self.assertRaisesRegex(ValueError,'profile count'):mod.matrix(mod.PROFILES*2)

    def test_reject_duplicated_profile(self):
        with self.assertRaisesRegex(ValueError,'profile identity'):mod.matrix([mod.PROFILES[0],mod.PROFILES[0]])

    def test_reject_profile_extending_queue_or_workers(self):
        for profile in [('too-many-workers',10,3,5,1,None),('too-deep',10,9,1,1,None),
                        ('too-many-tasks',65,8,2,1,None)]:
            with self.subTest(profile=profile[0]),self.assertRaises(ValueError):
                mod.matrix([profile])

    def test_nearest_rank_percentile_and_empty(self):
        self.assertIsNone(percentile_ns([],95))
        self.assertEqual(1,percentile_ns([2,1],50))
        self.assertEqual(2,percentile_ns([2,1],95))
