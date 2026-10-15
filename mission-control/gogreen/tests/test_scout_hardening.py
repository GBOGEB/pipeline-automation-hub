"""Additional passive scout first-red and schema boundary controls."""
import unittest
from test_collect_readonly import mod, fixture

class MoreCollectorBoundaries(unittest.TestCase):
    def test_path_gate_rejects_nonrepo_and_traversal(self):
        for path in ('/users/owner','/repos/x/../secret','/repos/x//secret'):
            with self.subTest(path=path),self.assertRaisesRegex(ValueError,'outside'):
                mod.get_json(path,'')

    def test_unknown_job_fetch_and_invalid_job_identity(self):
        data=fixture();sha=data['repositories'][0]['head_sha']
        def fetch(path):
            if '/actions/runs?' in path:
                if '/ABACUS/' in path:
                    return {'total_count':1,'workflow_runs':[{'head_sha':sha,'id':567,
                        'run_attempt':1,'run_number':2,'status':'completed','conclusion':'success','name':'Bandit'}]}
                return {'total_count':0,'workflow_runs':[]}
            return {'jobs':[{'id':False,'status':'completed','conclusion':'success'}]}
        _,meta=mod.scan(data,fetch)
        self.assertEqual('INVALID_JOB_ID',meta['collection_errors'][0]['kind'])

    def test_terminal_failed_job_does_not_get_green_credit(self):
        data=fixture();sha=data['repositories'][0]['head_sha']
        def fetch(path):
            if '/actions/runs?' in path:
                return {'total_count':1,'workflow_runs':[{'head_sha':sha,'id':567,'run_attempt':1,
                    'run_number':2,'status':'completed','conclusion':'success','name':'Bandit'}]}
            return {'jobs':[{'id':999,'status':'completed','conclusion':'failure'}]}
        new,meta=mod.scan(data,fetch)
        self.assertEqual(1,len(meta['unattributed_non_green']))
        self.assertEqual(1,len(new['observations']))
        self.assertFalse(meta['complete_fleet_census'])

    def test_invalid_run_id_is_observation_error(self):
        data=fixture()
        def fetch(path):
            sha=next(r['head_sha'] for r in data['repositories'] if r['repository'] in path)
            return {'total_count':1,'workflow_runs':[{'head_sha':sha,'id':True,
                'run_attempt':1,'status':'completed','conclusion':'success'}]}
        _,meta=mod.scan(data,fetch)
        self.assertEqual(6,len(meta['collection_errors']))
        self.assertTrue(all(x['kind']=='INVALID_RUN_IDENTITY' for x in meta['collection_errors']))

    def test_job_fetch_exception_yields_unavailable(self):
        data=fixture()
        def fetch(path):
            if '/actions/runs?' in path:
                sha=next(r['head_sha'] for r in data['repositories'] if r['repository'] in path)
                return {'total_count':1,'workflow_runs':[{'head_sha':sha,'id':567,'run_attempt':1,
                    'run_number':2,'status':'completed','conclusion':'success','name':'Bandit'}]}
            raise ValueError('jobs inaccessible')
        _,meta=mod.scan(data,fetch)
        self.assertEqual(6,len(meta['collection_errors']))
        self.assertTrue(all(e['kind']=='JOB_FETCH_UNAVAILABLE' for e in meta['collection_errors']))

    def test_bad_job_budget_rejected(self):
        for n in (0,9,True):
            with self.subTest(n=n),self.assertRaises(ValueError):mod.scan(fixture(),lambda path:{},max_jobs=n)
