"""GOGREEN G4 rollup negative and scaling contract tests."""
from __future__ import annotations
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pulse_rollup as m


class PulseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        samples = ROOT / 'samples'
        cls.g0 = json.loads((samples / 'fleet_g0.json').read_text())
        cls.g1 = json.loads((samples / 'fleet_g1.json').read_text())

    def test_fixed_catalog_and_growth(self):
        report = m.rollup(self.g0, self.g1, workers=2, packet_budget=12)
        self.assertEqual([(r['observed_cells'], r['target_cells']) for r in report['waves']], [(1,42),(6,42)])
        self.assertEqual(report['waves'][1]['native_status_only'], 5)
        self.assertEqual(report['waves'][1]['verified_archive_bytes'], 0)
        self.assertIsNone(report['measurement_boundaries']['independent_trial_count'])
        self.assertFalse(report['merge_authorized'])

    def test_source_catalog_drift_rejected(self):
        g1 = copy.deepcopy(self.g1)
        g1['repositories'][0]['head_sha'] = '0' * 40
        with self.assertRaises(ValueError): m.rollup(self.g0, g1)

    def test_baseline_deletion_rejected(self):
        g1 = copy.deepcopy(self.g1)
        g1['observations'] = g1['observations'][1:]
        with self.assertRaises(ValueError): m.rollup(self.g0, g1)

    def test_baseline_rewrite_rejected(self):
        g1 = copy.deepcopy(self.g1)
        g1['observations'][0]['job_id'] += 100
        with self.assertRaises(ValueError): m.rollup(self.g0, g1)

    def test_invalid_sha_rejected(self):
        with self.assertRaises(ValueError): m.rollup(self.g0, self.g1, source_sha='short')

    def test_no_self_asserted_bytes(self):
        g1 = copy.deepcopy(self.g1)
        g1['observations'][0]['artifact']['bytes_verified'] = True
        with self.assertRaises(ValueError): m.rollup(self.g0, g1)

    def test_capped_disjoint_plan(self):
        out = m.rollup(self.g0, self.g1, workers=2, per_repo=1, packet_budget=12)['scale_plan']
        self.assertEqual(out['packets_planned'], 6)
        self.assertEqual(len({p['repository'] for p in out['packets']}), 6)
        self.assertTrue(all(p['dispatch_authorized'] is False and p['mutation_paths'] == [] for p in out['packets']))

    def test_low_cap_and_negative_budget(self):
        plan = m.rollup(self.g0, self.g1, workers=1, packet_budget=3)['scale_plan']
        self.assertEqual(plan['packets_planned'], 3)
        for bad in (0, -1, 65, True):
            with self.assertRaises(ValueError): m.bounded_schedule(self.g1['repositories'], m._extract(self.g1)[0], workers=bad)

    def test_output_deterministic(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            report = m.rollup(self.g0, self.g1)
            a = m.emit(report, p)
            b = m.emit(report, p)
            self.assertEqual(a, b)
            self.assertEqual(len(a),64)
            self.assertIn('G1', (p / 'pulse_rollup.md').read_text())

    def test_counterfactual_denominator_change_rejected(self):
        from unittest.mock import patch
        real = m._extract(self.g0)[0]
        bad = copy.deepcopy(real)
        bad['breadth']['catalog_repo_family_cells'] += 1
        with patch.object(m, '_extract', side_effect=[(real, {}), (bad, {})]):
            with self.assertRaisesRegex(ValueError, 'denominator drift'):
                m.rollup(self.g0, self.g1)

    def test_counterfactual_observed_regression_rejected(self):
        from unittest.mock import patch
        real = m._extract(self.g0)[0]
        bad = copy.deepcopy(real)
        bad['breadth']['observed_cells'] = 0
        with patch.object(m, '_extract', side_effect=[(real, {}), (bad, {})]):
            with self.assertRaisesRegex(ValueError, 'observation regression'):
                m.rollup(self.g0, self.g1)

    def test_native_entrypoint_generates_receipts(self):
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            cmd = [sys.executable, str(ROOT / 'pulse_rollup.py'),
                   '--g0', str(ROOT / 'samples' / 'fleet_g0.json'),
                   '--g1', str(ROOT / 'samples' / 'fleet_g1.json'),
                   '--source-sha', 'a' * 40, '--out', str(out)]
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  check=True, timeout=10)
            self.assertEqual(json.loads(proc.stdout)['scale_plan_count'], 6)
            self.assertEqual(json.loads((out / 'pulse_rollup.json').read_text())['source_git_sha'], 'a' * 40)

    def test_python_main_guard_executes(self):
        import contextlib
        import io
        import runpy
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            args = [str(ROOT / 'pulse_rollup.py'),
                    '--g0', str(ROOT / 'samples' / 'fleet_g0.json'),
                    '--g1', str(ROOT / 'samples' / 'fleet_g1.json'),
                    '--out', temp]
            with patch.object(sys, 'argv', args), contextlib.redirect_stdout(io.StringIO()):
                runpy.run_path(str(ROOT / 'pulse_rollup.py'), run_name='__main__')
            self.assertTrue((Path(temp) / 'pulse_rollup.sha256').exists())

    def test_no_authority_transfer(self):
        report = m.rollup(self.g0, self.g1)
        self.assertEqual(report['qps_disposition'],'DEFER')
        self.assertFalse(report['authority_transfer'])
        self.assertIsNone(report['scale_plan']['real_worker_capacity'])


if __name__ == '__main__':
    unittest.main()
