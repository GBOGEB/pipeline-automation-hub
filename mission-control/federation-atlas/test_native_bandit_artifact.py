"""Native archive custody / hard negative regressions; synthetic inputs never claim auth."""
import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

FILE=Path(__file__).with_name('native_bandit_artifact.py')
SPEC=importlib.util.spec_from_file_location('native_bandit_artifact',FILE)
M=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(M)
SHA='a'*40
FP='b'*64
RUN=4321
JOB=555

def rows():
    item=dict(fingerprint=FP,path='src/module.py',line=17,rule='B603')
    return {'schema':'bandit.disjoint.census.v1','exact_sha':SHA,
            'authority_transfer':False,'total_unique':1,'lanes':{
             name:{'items':[item] if name=='B3-subprocess' else [],
                   'findings':1 if name=='B3-subprocess' else 0,
                   'files':1 if name=='B3-subprocess' else 0} for name in M.LANES}}

def zipbuild(path, data=None, full=None, *, extra=None, stale_manifest=False):
    data=rows() if data is None else data
    full={'results':[{'test_id':'B603'}]} if full is None else full
    content={'disjoint.json':json.dumps(data).encode(),'full.json':json.dumps(full).encode()}
    if extra:content.update(extra)
    manifest='\n'.join(hashlib.sha256(v).hexdigest()+'  bandit-evidence/'+k for k,v in content.items())+'\n'
    if stale_manifest:manifest='0'*64+'  bandit-evidence/disjoint.json\n'
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name,blob in content.items():z.writestr(name,blob)
        z.writestr('SHA256SUMS',manifest)
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def openarchive(path,digest):
    return M.inspect_archive(path,archive_digest=digest,expected_sha=SHA,run_id=RUN,job_id=JOB)

class BanditArtifactTests(unittest.TestCase):
    def test_authenticated_shaped_source_and_uncertainty(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'x.zip';d=zipbuild(p)
            a=openarchive(p,d)
            self.assertEqual(a['native_fingerprints'],1)
            self.assertEqual(a['unique_source_files'],1)
            self.assertEqual(a['lanes']['B3-subprocess']['findings'],1)
            self.assertEqual(a['rules'],{'B603':1})
            for k in ('native_joined_receipt','causal_roots_confirmed','root_closures','independent_trials','scan_configuration_equivalence'):
                self.assertIsNone(a[k])
            self.assertEqual(a['merge_admission'],'HOLD')
            self.assertFalse(a['dispatch_authorized'])
            rendered=M.render(a)
            self.assertIn('filterRows()',rendered)
            self.assertIn("' of 1 native fingerprint records'",rendered)
    def test_bad_external_digest_and_head_and_job_refused(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'x.zip';d=zipbuild(p)
            for args in ({'archive_digest':'0'*64},{'expected_sha':'c'*40},{'job_id':0},{'run_id':True}):
                v=dict(archive_digest=d,expected_sha=SHA,job_id=JOB,run_id=RUN);v.update(args)
                with self.subTest(args=args),self.assertRaises(ValueError):
                    M.inspect_archive(p,**v)
    def test_nested_manifest_crc_and_unsupported_source_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'x.zip';d=zipbuild(p,stale_manifest=True)
            with self.assertRaisesRegex(ValueError,'missing required member hashes'):openarchive(p,d)
            r=rows();r['exact_sha']='d'*40;d=zipbuild(p,data=r)
            with self.assertRaisesRegex(ValueError,'SHA'):openarchive(p,d)
            r=rows();r['authority_transfer']=True;d=zipbuild(p,data=r)
            with self.assertRaises(ValueError):openarchive(p,d)
    def test_mismatched_total_and_full_population_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'x.zip';r=rows();r['total_unique']=2;d=zipbuild(p,data=r)
            with self.assertRaisesRegex(ValueError,'total'):openarchive(p,d)
            d=zipbuild(p,full={'results':[]})
            with self.assertRaisesRegex(ValueError,'full scan'):openarchive(p,d)
    def test_duplicate_fingerprint_and_owner_collision_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'x.zip';r=rows();a=copy.deepcopy(r['lanes']['B3-subprocess']['items'][0])
            r['lanes']['B4-files-secrets']['items']=[a]
            r['lanes']['B4-files-secrets'].update(findings=1,files=1)
            r['total_unique']=2
            d=zipbuild(p,data=r,full={'results':[{},{}]})
            with self.assertRaisesRegex(ValueError,'duplicate fingerprint'):openarchive(p,d)
            r['lanes']['B4-files-secrets']['items'][0]['fingerprint']='e'*64
            d=zipbuild(p,data=r,full={'results':[{},{}]})
            with self.assertRaisesRegex(ValueError,'multiple disjoint'):openarchive(p,d)
    def test_malformed_paths_counts_and_rule_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'x.zip'
            for field,value in [('path','../outside'),('line',True),('rule','BLAH'),('fingerprint','short')]:
                r=rows();r['lanes']['B3-subprocess']['items'][0][field]=value
                d=zipbuild(p,data=r)
                with self.subTest(field=field),self.assertRaises(ValueError):openarchive(p,d)
            r=rows();r['lanes']['B3-subprocess']['files']=2;d=zipbuild(p,data=r)
            with self.assertRaisesRegex(ValueError,'denominator'):openarchive(p,d)
    def test_unsafe_zip_entry_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'x.zip';d=zipbuild(p,extra={'../escape.txt':b'not allowed'})
            with self.assertRaisesRegex(ValueError,'unsafe zip'):openarchive(p,d)
            d=zipbuild(p,extra={'C:drive.txt':b'drive'})
            with self.assertRaisesRegex(ValueError,'unsafe zip'):openarchive(p,d)
    def test_html_xss_and_deterministic_render(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'x.zip';r=rows()
            r['lanes']['B3-subprocess']['items'][0]['path']='src/<script>alert(1)</script>.py'
            d=zipbuild(p,data=r);a=openarchive(p,d)
            html=M.render(a)
            self.assertNotIn('<script>alert(1)</script>',html)
            self.assertIn('&lt;script&gt;',html)
            self.assertEqual(M.render(a),html)

if __name__=='__main__':unittest.main()