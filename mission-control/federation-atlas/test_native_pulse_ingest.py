import copy
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import native_pulse_ingest as n

SHA = 'a'*40
CONF = 'b'*64
REPO = 'GBOGEB/pipeline-automation-hub'

def fixture():
    run={'id':17,'repository':{'full_name':REPO},'head_sha':SHA,'run_attempt':2,
         'status':'completed','conclusion':'success'}
    jobs={'jobs':[{'id':81,'run_id':17,'run_attempt':2,
                   'status':'completed','conclusion':'success'}]}
    artifacts={'artifacts':[{'id':19,'name':'pulse-measurement','expired':False,
                             'workflow_run':{'id':17,'head_sha':SHA}}]}
    inside={'schema':n.INNER, 'repository':REPO, 'head_sha':SHA, 'run_id':17,
            'run_attempt':2, 'job_id':81, 'config_sha256':CONF,
            'selection':'unit:fixed', 'tool':{'name':'coverage.py','version':'7.13.3'},
            'tests':{'passed':3,'failed':0,'skipped':1},
            'source_scope':[{'path':'scripts/mod.py','sha256':'c'*64}],
            'line':{'covered':4,'eligible':5},'branch':{'covered':3,'eligible':4}}
    return run,jobs,artifacts,inside

def zip_receipt(obj):
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w') as z:
        z.writestr('pulse_measurement.json',json.dumps(obj))
    return data.getvalue()

class TestIntake(unittest.TestCase):
    def data(self):
        a,b,c,d=fixture()
        return a,b,c,d,zip_receipt(d)
    def verified(self,**changes):
        a,b,c,d,z=self.data()
        return n.validate(REPO,17,a,b,c,artifact_name='pulse-measurement',archive=z,**changes)
    def test_exact_verified(self):
        obj=self.verified(expected_sha=SHA)
        self.assertEqual(obj['measurement']['line']['pct'],80.)
        self.assertEqual(obj['measurement']['branch']['pct'],75.)
        self.assertFalse(obj['merge_admitted'])
        self.assertEqual(obj['metadata_origin'], 'CALLER_SUPPLIED_OFFLINE')
        self.assertEqual(obj['measurement_authority'], 'PRODUCER_REPORTED_NOT_INDEPENDENTLY_RECOMPUTED')
        self.assertEqual(obj['qps_owner_decision'],'DEFER')
    def test_metadata_never_coverage(self):
        a,b,c,_,_=self.data()
        obj=n.validate(REPO,17,a,b,c,artifact_name='pulse-measurement')
        self.assertIsNone(obj['measurement'])
        self.assertEqual(obj['evidence_depth'],'RUN_METADATA_ONLY')
    def test_run_sha_mismatch(self):
        with self.assertRaisesRegex(ValueError,'expected SHA'):
            self.verified(expected_sha='d'*40)
    def test_wrong_repo(self):
        a,b,c,_,_=self.data()
        a['repository']['full_name']='GBOGEB/ABACUS'
        with self.assertRaisesRegex(ValueError,'repository mismatch'):
            n.validate(REPO,17,a,b,c)
    def test_wrong_attempt(self):
        a,b,c,d,_=self.data();d['run_attempt']=1
        with self.assertRaisesRegex(ValueError,'inner provenance'):
            n.validate(REPO,17,a,b,c,artifact_name='pulse-measurement',archive=zip_receipt(d))
    def test_false_coverage(self):
        a,b,c,d,_=self.data();d['line']['covered']=6
        with self.assertRaisesRegex(ValueError,'metric invalid'):
            n.validate(REPO,17,a,b,c,artifact_name='pulse-measurement',archive=zip_receipt(d))
    def test_red_not_credited(self):
        a,b,c,d,z=self.data();a['conclusion']='failure'
        with self.assertRaisesRegex(ValueError,'coverage credit'):
            n.validate(REPO,17,a,b,c,artifact_name='pulse-measurement',archive=z)
    def test_failed_job(self):
        a,b,c,d,z=self.data();b['jobs'][0]['conclusion']='failure'
        with self.assertRaisesRegex(ValueError,'not successful'):
            n.validate(REPO,17,a,b,c,artifact_name='pulse-measurement',archive=z)
    def test_missing_internal_receipt(self):
        a,b,c,d,z=self.data();empty=io.BytesIO()
        with zipfile.ZipFile(empty,'w') as f:f.writestr('other.txt','data')
        with self.assertRaisesRegex(ValueError,'receipt missing'):
            n.validate(REPO,17,a,b,c,artifact_name='pulse-measurement',archive=empty.getvalue())
    def test_unsafe_member(self):
        a,b,c,d,z=self.data();bad=io.BytesIO()
        with zipfile.ZipFile(bad,'w') as f:
            f.writestr('pulse_measurement.json',json.dumps(d));f.writestr('../escape','boom')
        with self.assertRaisesRegex(ValueError,'unsafe ZIP'):
            n.validate(REPO,17,a,b,c,artifact_name='pulse-measurement',archive=bad.getvalue())
    def test_artifact_source_mismatch(self):
        a,b,c,d,z=self.data();c['artifacts'][0]['workflow_run']['head_sha']='d'*40
        with self.assertRaisesRegex(ValueError,'artifact run/source'):
            n.validate(REPO,17,a,b,c,artifact_name='pulse-measurement',archive=z)
    def test_idempotent_and_tamper_proof(self):
        e=self.verified()
        with tempfile.TemporaryDirectory() as d:
            first=n.write_event(e,d)
            second=n.write_event(e,d)
            self.assertEqual(first,second)
            data=json.loads((Path(d)/'native_pulse_ledger.json').read_text())
            self.assertEqual(len(data['events']),1)
            self.assertTrue((Path(d)/'native_pulse_index.html').exists())
            first.write_text('{"bad":true}')
            with self.assertRaises((ValueError,KeyError)):
                n.write_event(e,d)
    def test_api_outside_cohort_blocked(self):
        with self.assertRaisesRegex(ValueError,'disallowed API'):
            n.get('/users/me',None)
    def test_nonterminal_status_no_success(self):
        a,b,c,_,_=self.data();a['status']='queued';a['conclusion']=None
        obj=n.validate(REPO,17,a,b,c)
        self.assertIsNone(obj['measurement'])
    def test_duplicate_jobs(self):
        a,b,c,_,_=self.data();b['jobs'].append(b['jobs'][0])
        with self.assertRaisesRegex(ValueError,'job identity'):
            n.validate(REPO,17,a,b,c)

if __name__=='__main__': unittest.main()