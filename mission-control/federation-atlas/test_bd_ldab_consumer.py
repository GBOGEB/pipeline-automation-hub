"""Negative, provenance, determinism and GUI-XSS controls for BD-LDAB consumer."""
import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

FILE=Path(__file__).with_name('bd_ldab_consumer.py')
SPEC=importlib.util.spec_from_file_location('bd_ldab_consumer',FILE)
M=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
SHA='a'*40
OLD='b'*40
DIGEST='f'*64
URL='https://github.com/GBOGEB/ABACUS/actions/runs/999'


def fixture():
    a=dict(repository='GBOGEB/ABACUS',source_sha=SHA,run_id=999,job_id=5,
           evidence_url=URL,source='bandit_disjoint')
    d=dict(repository='GBOGEB/CODEX',source_sha='c'*40,run_id=888,job_id=1,
           evidence_url='https://github.com/GBOGEB/CODEX/actions/runs/888',
           source='debug_receipt',proof_level='REPORTED_UNVERIFIED',
           session_id='reported-not-authenticated',real_probe_steps=10)
    return {'schema':'bd.ldab.joined.census.v1',
            'scope':{'repository':'GBOGEB/ABACUS','head_sha':SHA,
                     'scan_configuration':'full-default-v1'},
            'metrics':{'full_bandit_unique':1,'ci_observations':0,
                       'debug_receipts':1,'debug_reported_sessions':1,
                       'comparable_delta':None,'changed_line_coverage':None,
                       'active_workers':None},
            'roots':[{'root_id':'BD-root001','category':'BANDIT',
                      'disposition':'OPEN_UNREVIEWED','source_path':'scripts/a.py',
                      'owner_lane':'B3-subprocess','observations':[a]}],
            'unlinked_debug_receipts':[d],
            'merge_admission':'HOLD','authority_transfer':False,
            'security_waiver':False,'formal_credit_delta':0,
            'engineering_credit_delta':0}


def read(data):
    return M.consume(data,expected_sha=SHA,input_sha256=DIGEST)


class ConsumerTests(unittest.TestCase):
    def test_known_good(self):
        out=read(fixture())
        self.assertEqual(out['metrics']['roots_observed'],1)
        self.assertEqual(out['metrics']['unlinked_debug'],1)
        self.assertIsNone(out['metrics']['formal_root_closures'])
        self.assertEqual(out['debugger_dag'][0],'RECEIPT_REPORTED')
        self.assertFalse(out['dispatch_authorized'])
        self.assertEqual(out['merge_admission'],'HOLD')

    def test_ci_manifestation_can_bind_existing_root_without_new_root(self):
        x=fixture(); ci=copy.deepcopy(x['roots'][0]['observations'][0]);ci.update(source='ci_failure',job_id=7)
        x['roots'][0]['observations'].append(ci);x['metrics']['ci_observations']=1
        out=read(x)
        self.assertEqual(out['metrics']['roots_observed'],1)
        self.assertEqual(out['metrics']['ci_manifestations'],1)

    def test_comparable_fingerprint_delta_not_formal_closure(self):
        x=fixture();x['metrics']['comparable_delta']=dict(status='FINGERPRINT_DELTA_ONLY_REVIEW_REQUIRED',
             after_sha=SHA,before_sha=OLD,scan_configuration='full-default-v1',
             before_unique=2,after_unique=1,new=0,resolved=1)
        self.assertEqual(read(x)['metrics']['comparable_fingerprint_delta']['resolved'],1)
        self.assertIsNone(read(x)['metrics']['formal_root_closures'])

    def test_adversarial_inputs_fail_closed(self):
        mutations=[
            lambda x:x.update(merge_admission='PASS'),
            lambda x:x.update(authority_transfer=True),
            lambda x:x.update(security_waiver=True),
            lambda x:x.update(formal_credit_delta=1),
            lambda x:x.update(engineering_credit_delta=1),
            lambda x:x['scope'].update(head_sha=OLD),
            lambda x:x['scope'].update(scan_configuration=''),
            lambda x:x['metrics'].update(full_bandit_unique=0),
            lambda x:x['metrics'].update(ci_observations=1),
            lambda x:x['metrics'].update(debug_receipts=0),
            lambda x:x['metrics'].update(debug_reported_sessions=0),
            lambda x:x['metrics'].update(changed_line_coverage=0),
            lambda x:x['metrics'].update(active_workers=0),
            lambda x:x['roots'][0].update(disposition='CLOSED_VERIFIED'),
            lambda x:x['roots'][0]['observations'][0].update(source_sha= 'short'),
            lambda x:x['roots'][0]['observations'][0].update(evidence_url='https://notgithub.org/foo'),
            lambda x:x['roots'][0]['observations'][0].update(run_id=True),
            lambda x:x['unlinked_debug_receipts'][0].update(proof_level='NATIVE_VERIFIED'),
            lambda x:x['unlinked_debug_receipts'][0].update(real_probe_steps=-1),
        ]
        for fn in mutations:
            x=fixture(); fn(x)
            with self.subTest(fn=fn):
                with self.assertRaises(ValueError):read(x)

    def test_duplicate_root_and_evidence_fails(self):
        x=fixture();x['roots'].append(copy.deepcopy(x['roots'][0]));x['metrics']['full_bandit_unique']=2
        with self.assertRaises(ValueError):read(x)
        x=fixture();x['roots'][0]['observations'].append(copy.deepcopy(x['roots'][0]['observations'][0]))
        with self.assertRaises(ValueError):read(x)

    def test_xss_escaped_and_filter_exists(self):
        x=fixture();x['roots'][0]['source_path']='"><script>alert(1)</script>'
        page=M.render(read(x))
        self.assertNotIn('<script>alert(1)</script>',page)
        self.assertIn('&lt;script&gt;',page)
        self.assertIn('function filterRows()',page)
        self.assertIn('aria-live',page)

    def test_deterministic_and_cli_output(self):
        x=fixture()
        with tempfile.TemporaryDirectory() as folder:
            src=Path(folder)/'joined.json';dest=Path(folder)/'out'
            src.write_text(json.dumps(x))
            M.main(['--joined',str(src),'--expected-sha',SHA,'--out',str(dest)])
            first=(dest/'bd-ldab-consumer.json').read_bytes()
            M.main(['--joined',str(src),'--expected-sha',SHA,'--out',str(dest)])
            self.assertEqual(first,(dest/'bd-ldab-consumer.json').read_bytes())
            self.assertEqual(json.loads(first)['input_sha256'],hashlib.sha256(src.read_bytes()).hexdigest())
            with self.assertRaises(ValueError):
                M.main(['--joined',str(src),'--expected-sha',OLD,'--out',str(dest)])

    def test_invalid_empty_and_schema(self):
        x=fixture();x['roots']=[];x['metrics']['full_bandit_unique']=0
        self.assertEqual(read(x)['metrics']['roots_observed'],0)
        x['schema']='unknown'
        with self.assertRaises(ValueError):read(x)

if __name__=='__main__':unittest.main()
