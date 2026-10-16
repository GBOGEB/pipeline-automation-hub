"""Adversarial native acquisition checks; no network or synthetic admission."""
import copy
import unittest
from abacus_mip_collect import acquire

SHA='a'*40

def fake(replace=None):
    src={
        '/actions/runs?head_sha='+SHA+'&event=pull_request&per_page=100&page=1': {
            'total_count': 1,
            'workflow_runs':[{'id':123,'run_attempt':1,'head_sha':SHA,
                               'event':'pull_request'}]},
        '/actions/runs/123':{'id':123,'run_attempt':1,'head_sha':SHA,
                            'event':'pull_request','name':'CI','path':'.github/workflows/test.yml',
                            'html_url':'https://github.com/GBOGEB/ABACUS/actions/runs/123',
                            'created_at':'2026-10-16T10:00:00Z','status':'completed',
                            'conclusion':'failure'},
        '/actions/runs/123/attempts/1/jobs?per_page=100&page=1': {
            'total_count': 1, 'jobs':[{'id':456, 'run_id':123,
                       'run_attempt':1,'head_sha':SHA,'status':'completed',
                       'conclusion':'failure','name':'checks','created_at':None,
                       'started_at':'2026-10-16T10:01:00Z',
                       'completed_at':'2026-10-16T10:02:00Z',
                       'steps':[{'name':'pytest','number':1,'status':'completed',
                                 'conclusion':'failure'}]}]}}
    if replace:
        replace(src)
    def getter(repo,path):
        if repo!='GBOGEB/ABACUS':
            raise ValueError('wrong repo')
        return copy.deepcopy(src[path])
    return getter

class NativeTests(unittest.TestCase):
    def test_complete_exact_source_native_run(self):
        r=acquire(SHA,fake())
        self.assertEqual(r['run_attempts_observed'],1)
        self.assertEqual(len(r['jobs']),1)
        self.assertTrue(r['census_complete'])
        self.assertEqual(r['jobs'][0]['steps'][0]['number'],1)

    def test_missing_or_duplicate_run_fails(self):
        def change(src):
            key=next(iter(src))
            src[key]['total_count']=2
        with self.assertRaisesRegex(ValueError,'complete bounded'):
            acquire(SHA,fake(change))

    def test_job_sha_and_attempt_drift_rejected(self):
        for key,val in [('head_sha','b'*40),('run_attempt',2)]:
            def change(src):
                src['/actions/runs/123/attempts/1/jobs?per_page=100&page=1']['jobs'][0][key]=val
            with self.subTest(key=key), self.assertRaisesRegex(ValueError,'job/run/attempt'):
                acquire(SHA,fake(change))

    def test_no_job_page_premature_completion(self):
        def change(src):
            key='/actions/runs/123/attempts/1/jobs?per_page=100&page=1'
            src[key]['total_count']=2
            src[key]['jobs']=[]
        with self.assertRaisesRegex(ValueError,'short job page'):
            acquire(SHA,fake(change))

    def test_wrong_pr_event_and_missing_run_rejected(self):
        def change(src):
            src['/actions/runs/123']['event']='workflow_dispatch'
        with self.assertRaisesRegex(ValueError,'run drift'):
            acquire(SHA,fake(change))

if __name__=='__main__':
    unittest.main()
