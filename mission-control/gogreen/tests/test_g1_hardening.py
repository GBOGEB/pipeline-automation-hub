"""Extra G1 evidence/security negative controls (no remote mutations)."""
import io
import json
import hashlib
import unittest
import zipfile
from test_native_zip import fixture, binding, rewrite, V

class G1MoreNegativeControls(unittest.TestCase):
    def test_reject_nonmapping_and_untrusted_identity_types(self):
        raw=fixture()
        bad=[None,[],{},dict(binding(raw),run_attempt=True),dict(binding(raw),job_id=0),
             dict(binding(raw),artifact_id=-1),dict(binding(raw),repository='github.com/owner/repo'),
             dict(binding(raw),source_sha='ab'),dict(binding(raw),archive_sha256='a'*63)]
        for item in bad:
            with self.subTest(item=item),self.assertRaises(ValueError): V.verify(raw,item)

    def test_reject_wrong_attempt_and_repository(self):
        raw=fixture()
        for field,value in [('run_attempt',2),('repository','GBOGEB/ABACUS')]:
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'execution provenance'):
                V.verify(raw,dict(binding(raw),**{field:value}))

    def test_reject_missing_required_zip_member(self):
        raw=fixture();out=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(raw)) as src,zipfile.ZipFile(out,'w') as dst:
            for n in src.namelist():
                if n!='manifest.json':dst.writestr(n,src.read(n))
        edited=out.getvalue()
        with self.assertRaisesRegex(ValueError,'member census'):V.verify(edited,binding(edited))

    def test_reject_zip_path_traversal(self):
        raw=fixture();out=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(raw)) as src,zipfile.ZipFile(out,'w') as dst:
            for n in src.namelist():dst.writestr(n,src.read(n))
            dst.writestr('../injection.py',b'bad')
        edited=out.getvalue()
        with self.assertRaisesRegex(ValueError,'unsafe ZIP member'):V.verify(edited,binding(edited))

    def test_reject_zip_symlink_member(self):
        raw=fixture();out=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(raw)) as src,zipfile.ZipFile(out,'w') as dst:
            for n in src.namelist():dst.writestr(n,src.read(n))
            link=zipfile.ZipInfo('danger-link');link.create_system=3;link.external_attr=0o120777 << 16
            dst.writestr(link,b'../../home')
        edited=out.getvalue()
        with self.assertRaisesRegex(ValueError,'unsafe ZIP member'):V.verify(edited,binding(edited))

    def test_reject_zip_bomb_budget(self):
        raw=fixture();out=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(raw)) as src,zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as dst:
            for n in src.namelist():dst.writestr(n,src.read(n))
            dst.writestr('bomb',b'X'*(V.MAX_MEMBER_BYTES+1))
        edited=out.getvalue()
        with self.assertRaisesRegex(ValueError,'unsafe ZIP member'):V.verify(edited,binding(edited))

    def test_reject_manifest_schema_or_digest_census(self):
        raw=fixture()
        with zipfile.ZipFile(io.BytesIO(raw)) as src:original=json.loads(src.read('manifest.json'))
        for patch in ({'schema':'gogreen.manifest.v999'},{'sha256':{}},{'authority_transfer':True}):
            edited=rewrite(raw,{'manifest.json':json.dumps(dict(original,**patch)).encode()})
            with self.subTest(patch=patch),self.assertRaises(ValueError):V.verify(edited,binding(edited))

    def test_reject_producer_evidence_self_authorization(self):
        raw=fixture()
        with zipfile.ZipFile(io.BytesIO(raw)) as src:
            ev=json.loads(src.read('evidence.json'));m=json.loads(src.read('manifest.json'))
            p=json.loads(src.read('execution_provenance.json'))
        ev['merge_authorized']=True;changed=json.dumps(ev).encode()
        m['sha256']['evidence.json']=hashlib.sha256(changed).hexdigest()
        new_m=json.dumps(m).encode();p['manifest_file_sha256']=hashlib.sha256(new_m).hexdigest()
        edited=rewrite(raw,{'evidence.json':changed,'manifest.json':new_m,
                            'execution_provenance.json':json.dumps(p).encode()})
        with self.assertRaisesRegex(ValueError,'forbidden authority'):V.verify(edited,binding(edited))

    def test_reject_empty_invalid_zip(self):
        with self.assertRaises(zipfile.BadZipFile):V.verify(b'not zip',binding(b'not zip'))

    def test_reject_too_many_members(self):
        raw=fixture();out=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(raw)) as src,zipfile.ZipFile(out,'w') as dst:
            for n in src.namelist():dst.writestr(n,src.read(n))
            for i in range(50):dst.writestr(f'junk-{i}',b'')
        edited=out.getvalue()
        with self.assertRaisesRegex(ValueError,'member census'):V.verify(edited,binding(edited))
