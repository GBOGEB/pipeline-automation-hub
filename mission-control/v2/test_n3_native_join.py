"""Positive and adversarial source identity, job/attempt and timestamp tests."""
import copy
import sys
import unittest
import json
import io
import runpy
import tempfile
from contextlib import redirect_stdout
from unittest import mock
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from n3_native_join import project


def fixture():
    sha = 'a' * 40
    return {'schema': 'missioncontrol.native_ci_observations.v1',
            'repository': 'GBOGEB/pipeline-automation-hub', 'source_sha': sha,
            'observed_at': '2026-10-17T12:00:00Z',
            'runs': [
                {'run_id': 1001, 'run_attempt': 2, 'head_sha': sha,
                 'status': 'completed', 'conclusion': 'failure',
                 'created_at': '2026-10-17T10:00:00Z', 'run_started_at': '2026-10-17T10:10:00Z',
                 'job_total': 2, 'jobs': [
                     {'job_id': 1201, 'run_id': 1001, 'run_attempt': 2,
                      'head_sha': sha, 'status': 'completed', 'conclusion': 'failure',
                      'failed_steps': [{'step_number': 3, 'step_name': 'pytest'}]},
                 ]},
                {'run_id': 1002, 'run_attempt': 1, 'head_sha': sha, 'status': 'queued',
                 'conclusion': None, 'created_at': '2026-10-17T11:50:00Z',
                 'run_started_at': None, 'job_total': 0, 'jobs': []}]}


class NativeJoinTests(unittest.TestCase):
    def setUp(self):
        self.s = fixture()

    def bad(self, mutate, message=None):
        mutate(self.s)
        with self.assertRaisesRegex(ValueError, message or '.*'):
            project(self.s)

    def test_metrics_and_declared_vs_observed(self):
        p = project(self.s)
        self.assertEqual((p['observed_runs'], p['observed_jobs'], p['declared_job_total']), (2, 1, 2))
        self.assertEqual((p['unobserved_job_slots'], p['observed_failed_steps']), (1, 1))
        self.assertEqual(p['queued_runs'], 1)
        self.assertEqual(len(p['first_red_symptoms']), 1)
        self.assertIsNone(p['first_red_symptoms'][0]['causal_root'])
        self.assertFalse(p['native_exact_head_authenticated'])
        self.assertEqual(p['merge_admission'], 'HOLD')

    def test_determinism_without_mutation(self):
        s = copy.deepcopy(self.s)
        self.assertEqual(project(self.s), project(self.s))
        self.assertEqual(self.s, s)

    def test_empty_run_list(self):
        self.s['runs'] = []
        self.assertEqual(project(self.s)['observed_runs'], 0)

    def test_calendar_invalid_timestamp_is_not_silently_accepted(self):
        self.bad(lambda x: x.__setitem__('observed_at', '2026-02-30T12:00:00Z'), 'invalid timestamp')

    def test_cli_report_output_and_stdout_are_consistent(self):
        import n3_native_join
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'native.json'
            target=Path(tmp)/'reports'/'metric.json'
            source.write_text(json.dumps(self.s))
            with mock.patch.object(sys, 'argv', ['n3_native_join',str(source),'--out',str(target)]):
                with redirect_stdout(io.StringIO()) as capture:
                    n3_native_join.main()
            self.assertEqual(json.loads(capture.getvalue()),json.loads(target.read_text()))
            self.assertEqual(json.loads(target.read_text())['merge_admission'],'HOLD')
            with mock.patch.object(sys, 'argv', ['n3_native_join',str(source)]):
                with redirect_stdout(io.StringIO()) as capture:
                    n3_native_join.main()
            self.assertEqual(json.loads(capture.getvalue())['observed_runs'],2)

    def test_direct_module_cli_main_proves_entrypoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'snapshot.json'
            source.write_text(json.dumps(self.s))
            with mock.patch.object(sys,'argv',['n3_native_join',str(source)]):
                with redirect_stdout(io.StringIO()) as capture:
                    runpy.run_path(str(HERE/'n3_native_join.py'),run_name='__main__')
            self.assertEqual(json.loads(capture.getvalue())['observed_runs'],2)

    def test_bad_source_sha(self):
        self.bad(lambda x: x.__setitem__('source_sha', 'main'), 'unbound native source')

    def test_wrong_repo(self):
        self.bad(lambda x: x.__setitem__('repository', 'other/repo'), 'unbound native source')


    def second_attempt(self, *, queued=False, duplicate_job=False):
        rerun = copy.deepcopy(self.s['runs'][0])
        rerun['run_attempt'] = 3
        rerun['run_started_at'] = '2026-10-17T11:20:00Z'
        if queued:
            rerun.update(status='queued', conclusion=None, run_started_at=None,
                         job_total=0, jobs=[])
        else:
            rerun['conclusion'] = 'success'
            rerun['jobs'][0].update(job_id=1201 if duplicate_job else 1202,
                                    run_attempt=3, conclusion='success',
                                    failed_steps=[])
        self.s['runs'].append(rerun)

    def test_two_attempts_one_run_no_double_counting(self):
        self.second_attempt()
        p = project(self.s)
        self.assertEqual(p['observed_runs'], 2)
        self.assertEqual(p['distinct_run_attempts'], 3)
        self.assertEqual(p['completed_runs'], 1)
        self.assertEqual(p['completed_attempts'], 2)
        self.assertEqual(p['run_attempt_aliases'], 1)
        self.assertEqual(p['run_ids_with_multiple_observed_attempts'], 1)
        self.assertIsNone(p['attempt_history_complete'])
        self.assertEqual(p['observed_jobs'], 2)
        self.assertEqual(p['declared_job_total'], 4)
        self.assertEqual(p['observed_failed_steps'], 1)
        self.assertEqual(len(p['first_red_symptoms']), 1)
        self.assertEqual(p['first_red_symptoms'][0]['run_attempt'], 2)
        self.assertEqual(p['causal_roots_confirmed'], 0)
        self.assertFalse(p['native_exact_head_authenticated'])

    def test_queued_rerun_does_not_claim_root_recovery(self):
        self.second_attempt(queued=True)
        p = project(self.s)
        self.assertEqual(p['observed_runs'], 2)
        self.assertEqual(p['distinct_run_attempts'], 3)
        self.assertEqual(p['queued_runs'], 2)
        self.assertEqual(p['queued_attempts'], 2)
        self.assertEqual(p['run_attempt_aliases'], 1)
        self.assertIsNone(p['independent_run_trials'])
        self.assertEqual(p['merge_admission'], 'HOLD')

    def test_duplicate_run_attempt_fails_closed(self):
        self.second_attempt()
        self.s['runs'].append(copy.deepcopy(self.s['runs'][-1]))
        with self.assertRaisesRegex(ValueError, 'duplicate run identity'):
            project(self.s)

    def test_reusing_job_id_on_distinct_attempt_is_rejected(self):
        self.second_attempt(duplicate_job=True)
        with self.assertRaisesRegex(ValueError, 'duplicate/invalid native job ID'):
            project(self.s)

    def test_reverse_input_order_does_not_change_attempt_population(self):
        self.second_attempt()
        first = project(self.s)
        self.s['runs'].reverse()
        second = project(self.s)
        for key in ('observed_runs', 'distinct_run_attempts', 'completed_attempts',
                    'run_attempt_aliases', 'run_ids_with_multiple_observed_attempts'):
            self.assertEqual(first[key], second[key])

    def test_original_attempt_2_does_not_imply_attempt_1_observed(self):
        p = project(self.s)
        self.assertEqual(p['observed_runs'], p['distinct_run_attempts'])
        self.assertIsNone(p['attempt_history_complete'])

    def test_cross_attempt_job_binding_can_not_be_spoofed(self):
        self.second_attempt()
        self.s['runs'][-1]['jobs'][0]['run_attempt'] = 2
        with self.assertRaisesRegex(ValueError, 'run-attempt conflict'):
            project(self.s)

    def test_duplicate_run_id(self):
        self.bad(lambda x: x['runs'].append(copy.deepcopy(x['runs'][0])), 'duplicate run identity')

    def test_boolean_attempt_rejected(self):
        self.bad(lambda x: x['runs'][0].__setitem__('run_attempt', True), 'run identity')

    def test_run_head_drift(self):
        self.bad(lambda x: x['runs'][0].__setitem__('head_sha', 'b'*40), 'head SHA drift')

    def test_job_wrong_attempt(self):
        self.bad(lambda x: x['runs'][0]['jobs'][0].__setitem__('run_attempt', 1), 'run-attempt conflict')

    def test_completed_without_conclusion(self):
        self.bad(lambda x: x['runs'][0].__setitem__('conclusion', None), 'contradiction')

    def test_queued_with_conclusion(self):
        self.bad(lambda x: x['runs'][1].__setitem__('conclusion', 'success'), 'contradiction')

    def test_queued_with_start(self):
        self.bad(lambda x: x['runs'][1].__setitem__('run_started_at', '2026-10-17T11:59:00Z'), 'queued run')

    def test_naive_timestamp_rejected(self):
        self.bad(lambda x: x.__setitem__('observed_at', '2026-10-17T12:00:00'), 'timezone')

    def test_run_time_order_rejected(self):
        self.bad(lambda x: x['runs'][0].__setitem__('run_started_at', '2026-10-17T09:00:00Z'), 'time order')

    def test_unobserved_slots_not_zeroed(self):
        self.bad(lambda x: x['runs'][0].__setitem__('job_total', 0), 'denominator')

    def test_duplicate_job_id(self):
        def mutate(x):
            x['runs'][0]['jobs'].append(copy.deepcopy(x['runs'][0]['jobs'][0]))
        self.bad(mutate, 'duplicate/invalid native job ID')

    def test_duplicate_failed_step(self):
        def mutate(x):
            x['runs'][0]['jobs'][0]['failed_steps'].append({'step_number': 3, 'step_name':'repeat'})
        self.bad(mutate, 'duplicate failed steps')

    def test_step_on_success_is_invalid(self):
        self.bad(lambda x: x['runs'][0]['jobs'][0].__setitem__('conclusion', 'success'), 'failed steps')

    def test_job_identity_wrong_run(self):
        self.bad(lambda x: x['runs'][0]['jobs'][0].__setitem__('run_id', 444), 'identity/head')


if __name__ == '__main__':
    unittest.main()
