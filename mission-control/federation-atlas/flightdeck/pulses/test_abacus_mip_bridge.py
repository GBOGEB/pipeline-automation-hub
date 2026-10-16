"""Positive and adversarial controls for source-bound supporting projection."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from abacus_mip_bridge import OUTCOMES, main, project

SHA = 'a'*40
DIGEST = 'b'*64
SEMANTIC = dict(workflow_path='.github/workflows/ci.yml', job_name='pytest',
                step_name='Test', step_number=4)
FP = hashlib.sha256(json.dumps(SEMANTIC, sort_keys=True,
                               separators=(',', ':')).encode()).hexdigest()


def fixture():
    event = dict(SEMANTIC, fingerprint=FP, run_id=100, run_attempt=1, job_id=200)
    signature = dict(SEMANTIC, fingerprint=FP, manifestations=1)
    outcomes = {key: 0 for key in OUTCOMES}
    outcomes['success'], outcomes['failure'] = 16, 4
    outcomes['cancelled'] = 1
    return {
        'schema': 'abacus.mip.ci-wave-telemetry.v2',
        'repository': 'GBOGEB/ABACUS', 'source_sha': SHA,
        'authority_transfer': False, 'merge_authorized': False,
        'security_waiver': False, 'distinct_bd_roots_closed': None,
        'first_red_causal_roots_verified': None,
        'rex_receipts_accepted': None,
        'independent_gates': {'admission': 'HOLD', 'merge_authorized': False},
        'workflow_records_observed': 21,
        'workflow_terminal_by_outcome': outcomes,
        'workflow_nonterminal': 0, 'workflow_unclassified': 0,
        'jobs_observed': 23, 'queue_samples': 22,
        'queue_source_counts': {'job_created_at': 22,
                                'workflow_run_created_at_fallback': 0},
        'queue_seconds_p95': 42.0,
        'first_red_manifestations': [event],
        'first_red_signatures': [signature],
        'first_red_unique_signatures': 1,
        'first_red_repeated_signatures': 0,
        'red_jobs_without_attributed_first_step': 3,
    }


def read(doc):
    return project(doc, SHA, input_sha256=DIGEST)


class ConsumerTests(unittest.TestCase):
    def test_readonly_stats_denominator_and_nonpromoted_math(self):
        result = read(fixture())
        self.assertEqual(result['metrics']['workflow_records'], 21)
        self.assertEqual(result['metrics']['workflow_success'], 16)
        self.assertEqual(result['metrics']['success_share_of_observed_pct'], 76.19)
        self.assertEqual(result['metrics']['queue_native_timestamp_share_pct'], 100)
        self.assertTrue(result['metrics']['queue_p95_cross_wave_eligible'])
        self.assertEqual(result['first_red_signatures_readonly'][0]['manifestations'], 1)
        for stat in ('pca','bradley_terry','anova','manova'):
            self.assertEqual(result['statistics'][stat]['status'], 'HOLD')
        self.assertEqual(result['statistics']['intervals_90_95_99'],
                         {'90': None, '95': None, '99': None})
        self.assertIsNone(result['root_closures_verified'])
        self.assertEqual(result['merge_admission'], 'HOLD')

    def test_mixed_clocks_retained_but_not_qualified(self):
        d = fixture()
        d['queue_source_counts'] = {'job_created_at': 20,
                                    'workflow_run_created_at_fallback': 2}
        out = read(d)['metrics']
        self.assertFalse(out['queue_p95_cross_wave_eligible'])
        self.assertEqual(out['queue_native_timestamp_share_pct'], 90.909)

    def test_unresolved_workflow_keeps_interval_unestimated(self):
        d = fixture()
        d['workflow_terminal_by_outcome']['success'] -= 1
        d['workflow_nonterminal'] = 1
        out = read(d)
        self.assertFalse(out['metrics']['queue_p95_cross_wave_eligible'])
        self.assertIsNone(out['statistics']['intervals_90_95_99']['95'])

    def test_fail_closed_bad_identity_and_promotions(self):
        mutations = [
            lambda d: d.update(source_sha='c'*40),
            lambda d: d.update(merge_authorized=True),
            lambda d: d.update(distinct_bd_roots_closed=0),
            lambda d: d['independent_gates'].update(admission='PASS'),
            lambda d: d['workflow_terminal_by_outcome'].update(success=17),
            lambda d: d['queue_source_counts'].update(job_created_at=21),
            lambda d: d['queue_source_counts'].update(job_created_at=True),
            lambda d: d['first_red_manifestations'][0].update(step_name='different'),
            lambda d: d['first_red_signatures'][0].update(manifestations=2),
            lambda d: d.update(first_red_signatures=[]),
            lambda d: d.update(red_jobs_without_attributed_first_step=23),
        ]
        for mutate in mutations:
            d = fixture(); mutate(d)
            with self.subTest(mutate=mutate):
                with self.assertRaises(ValueError):
                    read(d)

    def test_duplicate_step_and_native_job_identity_rejected(self):
        d = fixture()
        d['first_red_manifestations'].append(copy.deepcopy(
            d['first_red_manifestations'][0]))
        with self.assertRaisesRegex(ValueError, 'repeated native job'):
            read(d)

    def test_deterministic_cli_replay_and_alias_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); src=root/'source.json'; out=root/'out.json'
            src.write_text(json.dumps(fixture()))
            main(['--projection',str(src),'--source-sha',SHA,'--output',str(out)])
            first = out.read_bytes()
            main(['--projection',str(src),'--source-sha',SHA,'--output',str(out)])
            self.assertEqual(first,out.read_bytes())
            with self.assertRaisesRegex(ValueError, 'input output alias'):
                main(['--projection',str(src),'--source-sha',SHA,'--output',str(src)])


if __name__ == '__main__':
    unittest.main()
