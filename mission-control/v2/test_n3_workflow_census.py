"""G3A N+11: negative cases for source-bound, censored CI telemetry."""
import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
import contextlib
import io
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import n3_workflow_census as census


def observation():
    sha = 'a'*40
    return {'schema':'missioncontrol.github_workflow_census.v1','repository':'GBOGEB/pipeline-automation-hub',
            'source_sha':sha,'retrieval_scope':'FIRST_PAGE_PR_HEAD',
            'artifact_check_run_ids':[101],
            'workflow_runs':[
                {'run_id':101,'head_sha':sha,'name':'N3 Evidence Metrics','run_attempt':1,
                 'status':'queued','conclusion':None,'created_at':'2026-10-17T12:00:00Z',
                 'started_at':None,'completed_at':None,'reported_job_total':None,
                 'artifact_count':0,'jobs':[{'job_id':501,'run_id':101,'run_attempt':1,'head_sha':sha,'status':'queued','conclusion':None}]},
                {'run_id':102,'head_sha':sha,'name':'V2 Contract','run_attempt':None,
                 'status':'completed','conclusion':'success','created_at':'2026-10-17T11:00:00Z',
                 'started_at':'2026-10-17T11:05:00Z','completed_at':'2026-10-17T11:06:00Z',
                 'reported_job_total':1,'artifact_count':None,
                 'jobs':[{'job_id':502,'run_id':102,'run_attempt':1,'head_sha':sha,'status':'completed','conclusion':'success'}]},
            ]}


class WorkflowCensusTests(unittest.TestCase):
    def setUp(self):self.obj=observation()
    def bad(self,edit,needle):
        edit(self.obj)
        with self.assertRaisesRegex(ValueError,needle):census.project(self.obj)

    def test_mixed_queued_and_completed_not_full_pass(self):
        got=census.project(self.obj)['metrics']
        self.assertEqual(got['workflow_runs_observed'],2)
        self.assertEqual(got['terminal_workflows']['numerator'],1)
        self.assertEqual(got['queued_or_pending_workflows']['numerator'],1)
        self.assertEqual(got['known_run_attempts']['numerator'],1)
        self.assertEqual(got['queue_latency_p95_ms'],300000)
        self.assertEqual(got['run_duration_p95_ms'],60000)
        self.assertEqual(got['known_job_attempt_bindings'],{'numerator':1,'denominator':2,'pct':50.0})
        self.assertEqual(census.project(self.obj)['workflows'][0]['job_attempts'][0]['run_attempt'],1)
        self.assertIsNone(got['reported_total_jobs_for_known_runs'])
        self.assertEqual(got['runs_with_unknown_job_denominator'],1)

    def test_unknown_latency_and_success_denominator(self):
        self.obj['workflow_runs']=self.obj['workflow_runs'][:1]
        r=census.project(self.obj)['metrics']
        self.assertIsNone(r['queue_latency_p95_ms'])
        self.assertIsNone(r['successful_terminal_workflows']['pct'])
        self.assertEqual(r['queue_latency_sample_count'],0)

    def test_unknown_job_observation_is_not_zero(self):
        self.obj['workflow_runs'][0]['jobs']=None
        result=census.project(self.obj)
        self.assertIsNone(result['workflows'][0]['observed_jobs'])

    def test_duplicate_run_id(self):
        self.bad(lambda x:x['workflow_runs'][1].__setitem__('run_id',101),'duplicate workflow')

    def test_duplicate_job_id(self):
        self.bad(lambda x:x['workflow_runs'][1]['jobs'][0].__setitem__('job_id',501),'duplicate/invalid job')

    def test_job_attempt_must_match_enclosing_run(self):
        self.bad(lambda x:x['workflow_runs'][0]['jobs'][0].__setitem__('run_attempt',2),'job run-attempt mismatch')

    def test_job_attempt_binding_is_unknown_when_either_attempt_is_missing(self):
        self.obj['workflow_runs'][0]['jobs'][0]['run_attempt']=None
        result=census.project(self.obj)
        self.assertEqual(result['workflows'][0]['job_attempts'][0],
                         {'job_id':501,'run_attempt':None,'attempt_binding':'UNKNOWN'})
        self.obj['workflow_runs'][0]['jobs'][0]['run_attempt']=1
        result=census.project(self.obj)
        self.assertEqual(result['workflows'][1]['job_attempts'][0],
                         {'job_id':502,'run_attempt':1,'attempt_binding':'UNKNOWN'})

    def test_wrong_sha(self):
        self.bad(lambda x:x['workflow_runs'][1].__setitem__('head_sha','b'*40),'exact-head')

    def test_bad_repo(self):
        self.bad(lambda x:x.__setitem__('repository','other/repo'),'source repository')

    def test_bad_run_attempt_bool(self):
        self.bad(lambda x:x['workflow_runs'][0].__setitem__('run_attempt',True),'run attempt')

    def test_queued_with_success(self):
        self.bad(lambda x:x['workflow_runs'][0].__setitem__('conclusion','success'),'inconsistent terminal')

    def test_queued_with_unknown_conclusion(self):
        self.bad(lambda x:x['workflow_runs'][0].__setitem__('conclusion','unknown'),'inconsistent terminal')

    def test_job_with_unknown_conclusion(self):
        self.bad(lambda x:x['workflow_runs'][0]['jobs'][0].__setitem__('conclusion','unknown'),'inconsistent terminal')

    def test_terminal_without_conclusion(self):
        self.bad(lambda x:x['workflow_runs'][1].__setitem__('conclusion',None),'inconsistent terminal')

    def test_run_startup_failure_counts_as_failed_terminal(self):
        run = self.obj['workflow_runs'][0]
        run.update(status='completed', conclusion='startup_failure',
                   completed_at='2026-10-17T12:01:00Z', reported_job_total=0, jobs=[])
        metrics = census.project(self.obj)['metrics']
        self.assertEqual(metrics['terminal_workflows']['numerator'], 2)
        self.assertEqual(metrics['failed_terminal_workflows']['numerator'], 1)

    def test_job_startup_failure_is_not_a_supported_conclusion(self):
        job = self.obj['workflow_runs'][0]['jobs'][0]
        job.update(status='completed', conclusion='startup_failure')
        self.bad(lambda x: None, 'inconsistent terminal')

    def test_queued_with_started_at(self):
        self.bad(lambda x:x['workflow_runs'][0].__setitem__('started_at','2026-10-17T12:01:00Z'),'queued run falsely')

    def test_time_order(self):
        self.bad(lambda x:x['workflow_runs'][1].__setitem__('started_at','2026-10-17T10:00:00Z'),'start precedes')

    def test_invalid_date(self):
        self.bad(lambda x:x['workflow_runs'][1].__setitem__('created_at','bad timestamp'),'invalid time value')

    def test_naive_date(self):
        self.bad(lambda x:x['workflow_runs'][1].__setitem__('created_at','2026-10-17T11:00:00'),'timezone required')

    def test_unknown_artifact_cannot_report_zero(self):
        self.bad(lambda x:x['workflow_runs'][1].__setitem__('artifact_count',0),'uncorroborated artifact')

    def test_checked_artifact_must_supply_count(self):
        self.bad(lambda x:x['workflow_runs'][0].__setitem__('artifact_count',None),'checked artifact count')

    def test_checked_artifact_not_in_readback(self):
        self.bad(lambda x:x['artifact_check_run_ids'].append(999),'artifact check does not belong')

    def test_bad_job_total(self):
        self.bad(lambda x:x['workflow_runs'][1].__setitem__('reported_job_total',0),'invalid declared job total')

    def test_subtotal_determinism_and_source_immutable(self):
        before=copy.deepcopy(self.obj)
        self.assertEqual(census.project(self.obj),census.project(self.obj))
        self.assertEqual(before,self.obj)

    def test_cli_projection_artifact(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'source.json';q=Path(d)/'telemetry.json'
            p.write_text(json.dumps(self.obj))
            with patch.object(sys,'argv',['n3_workflow_census.py',str(p),'--out',str(q)]):
                with contextlib.redirect_stdout(io.StringIO()):census.main()
            self.assertEqual(json.loads(q.read_text())['metrics']['observed_jobs'],2)


if __name__=='__main__':unittest.main()
