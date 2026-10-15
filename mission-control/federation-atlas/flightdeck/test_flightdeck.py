"""W1/W2 positive, negative and deterministic controls; no GitHub mutation."""
import copy,hashlib,json,os,sys,tempfile,unittest,io
from unittest import mock
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import flightdeck as f
FLEET=HERE/'fleet_g1.json'
if not FLEET.is_file():
    FLEET=HERE.parents[1]/'gogreen'/'samples'/'fleet_g1.json'  # Exact GitHub checkout
SNAP=HERE/'head_snapshot.json'
CONTRACT=HERE/'flightdeck_contract.json'

class FlightDeckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fleet=f.read(FLEET);cls.snap=f.read(SNAP);cls.contract=f.read(CONTRACT)
        cls.digest=f.ssot_digest([FLEET,SNAP,CONTRACT])
    def runvalid(self,fleet=None,snap=None,contract=None):
        return f.validate(fleet or self.fleet,snap or self.snap,contract or self.contract)
    def test_fixed_six_repo_catalog(self):self.assertTrue(self.runvalid())
    def test_semantic_hash_repeatable(self):self.assertEqual(self.digest,f.ssot_digest([FLEET,SNAP,CONTRACT]))
    def test_42_uniquely_typed_cells(self):
        d=f.build_census(self.fleet,self.snap,self.contract,self.digest)
        self.assertEqual(len({c['id'] for c in d['cells']}),42)
    def test_36_missing_not_failed(self):
        d=f.build_census(self.fleet,self.snap,self.contract,self.digest)
        self.assertEqual(sum(x['status']=='UNKNOWN_NOT_OBSERVED' for x in d['cells']),36)
        self.assertTrue(all(x['root_id'] is None for x in d['cells']))
    def test_original_metadata_not_byte_proof(self):
        d=f.build_census(self.fleet,self.snap,self.contract,self.digest)
        self.assertEqual(sum(x['bytes_independently_verified'] for x in d['cells']),0)
    def test_pr_anchor_excluded_from_main(self):
        d=f.build_census(self.fleet,self.snap,self.contract,self.digest)
        self.assertEqual(len(d['anchors']),5)
        self.assertFalse(any('ABACUS' in x['repository'] for x in d['anchors']))
    def test_snapshot_stale_counts(self):
        d=f.build_census(self.fleet,self.snap,self.contract,self.digest)
        self.assertEqual((d['metrics']['main_anchor_matches'],d['metrics']['stale_main_anchors']),(2,3))
    def test_html_has_42_reviewable_details(self):
        d=f.build_census(self.fleet,self.snap,self.contract,self.digest)
        markup=f.site_html(d)
        self.assertEqual(markup.count('data-status="'),42)
        self.assertEqual(markup.count('<details>'),42)
        self.assertIn('Export selected rows + notes',markup)
    def test_output_svg_has_pipeline_steps(self):
        d=f.build_census(self.fleet,self.snap,self.contract,self.digest)
        svg=f.flow_svg(d)
        self.assertEqual(svg.count('<a href="#step-'),8)
        self.assertIn('<desc id="fdesc">',svg)
    def test_duplicate_repo_rejected(self):
        d=copy.deepcopy(self.fleet);d['repositories'][0]['repository']=d['repositories'][1]['repository']
        with self.assertRaises(ValueError):f.validate(d,self.snap,self.contract)
    def test_duplicate_family_rejected(self):
        d=copy.deepcopy(self.fleet);d['repositories'][0]['target_families'][0]='coverage'
        with self.assertRaises(ValueError):f.validate(d,self.snap,self.contract)
    def test_wrong_denominator_rejected(self):
        d=copy.deepcopy(self.fleet);d['repositories'][0]['target_families'].pop()
        with self.assertRaises(ValueError):f.validate(d,self.snap,self.contract)
    def test_forged_byte_proof_rejected(self):
        d=copy.deepcopy(self.fleet);d['observations'][0]['artifact']['bytes_verified']=True
        with self.assertRaises(ValueError):f.validate(d,self.snap,self.contract)
    def test_observed_sha_mismatch_rejected(self):
        d=copy.deepcopy(self.fleet);d['observations'][0]['source_sha']='f'*40
        with self.assertRaises(ValueError):f.validate(d,self.snap,self.contract)
    def test_observed_non_success_rejected(self):
        d=copy.deepcopy(self.fleet);d['observations'][0]['job_conclusion']='failure'
        with self.assertRaises(ValueError):f.validate(d,self.snap,self.contract)
    def test_broken_main_snapshot_rejected(self):
        d=copy.deepcopy(self.snap);d['branches'].pop('GBOGEB/CODEX')
        with self.assertRaises(ValueError):f.validate(self.fleet,d,self.contract)
    def test_absent_timestamp_rejected(self):
        d=copy.deepcopy(self.snap);d['observed_at_utc']=''
        with self.assertRaises(ValueError):f.validate(self.fleet,d,self.contract)
    def test_forged_corporate_authorization_rejected(self):
        d=copy.deepcopy(self.contract);d['presentation']['corporate_approval']='CERTIFIED'
        with self.assertRaises(ValueError):f.validate(self.fleet,self.snap,d)
    def test_missing_pipeline_node_rejected(self):
        d=copy.deepcopy(self.contract);d['pipeline'].pop()
        with self.assertRaises(ValueError):f.validate(self.fleet,self.snap,d)
    def test_cross_repo_status_does_not_authorize_merge(self):
        d=f.build_census(self.fleet,self.snap,self.contract,self.digest)
        self.assertFalse(d['merge_authorized']);self.assertFalse(d['engineering_accepted'])
    def test_boolean_git_ref_rejected(self):
        with self.assertRaises(ValueError):f.build_census(self.fleet,self.snap,self.contract,self.digest,'BAD_SHA')
    def test_missing_source_preflight_fails(self):
        self.assertEqual(f.main(['preflight','--fleet','/no/such/fleet','--snapshot',str(SNAP),'--contract',str(CONTRACT)]),2)
    def test_complete_build_and_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            argv=['build','--fleet',str(FLEET),'--snapshot',str(SNAP),'--contract',str(CONTRACT),'--out',tmp]
            self.assertEqual(f.main(argv),0)
            self.assertEqual(f.verify(tmp)['validated_files'],6)
    def test_build_byte_reproducibility(self):
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
            src=dict(fleet=str(FLEET),snapshot=str(SNAP),contract=str(CONTRACT),out=a,exact_git_sha=None)
            f.build(type('X',(),src)());src['out']=b;f.build(type('X',(),src)())
            for n in ['index.html','census.json','flightdeck.svg','GUIDE.md','bd_leaves.json','anchors.json','manifest.json']:
                self.assertEqual((Path(a)/n).read_bytes(),(Path(b)/n).read_bytes())
    def test_tampered_archive_refuses_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            opt=type('X',(),dict(fleet=str(FLEET),snapshot=str(SNAP),contract=str(CONTRACT),out=tmp,exact_git_sha=None))()
            f.build(opt)
            with (Path(tmp)/'index.html').open('ab') as out:out.write(b'TAMPER')
            with self.assertRaises(ValueError):f.verify(tmp)
    def test_unsafe_unknown_per_repo_not_status_green(self):
        d=f.build_census(self.fleet,self.snap,self.contract,self.digest)
        for c in d['cells']:
            if c['status']=='UNKNOWN_NOT_OBSERVED':
                self.assertIsNone(c['run_id']);self.assertIsNone(c['job_id']);self.assertEqual(c['bd_disposition'],'SCOUT_REQUIRED')
    def test_bd_links_trace_to_existing_register(self):
        d=f.build_census(self.fleet,self.snap,self.contract,self.digest)
        self.assertEqual({c['bd_authority'] for c in d['cells']},{'https://github.com/GBOGEB/pipeline-automation-hub/issues/529'})
    def test_guide_tracks_source_identity(self):
        d=f.build_census(self.fleet,self.snap,self.contract,self.digest)
        self.assertIn(self.digest,f.operator_guide(d))
    def test_unsupported_input_schema_rejected(self):
        d=copy.deepcopy(self.fleet);d['schema']='fake'
        with self.assertRaises(ValueError):f.validate(d,self.snap,self.contract)

    def test_negative_control_matrix(self):
        mutations=[
            ("snapshot_schema", "snap", lambda d: d.update(schema="bad")),
            ("contract_authority", "contract", lambda d: d.update(authority="AUTHORIZE_MERGE")),
            ("repo_count", "fleet", lambda d: d["repositories"].pop()),
            ("taxonomy_drift", "contract", lambda d: d["families"].pop("security")),
            ("bad_source_sha", "fleet", lambda d: d["repositories"][0].update(head_sha="bad")),
            ("wrong_ref_kind", "fleet", lambda d: d["repositories"][0].update(ref_kind="HEAD")),
            ("duplicate_observation", "fleet", lambda d: d["observations"].append(copy.deepcopy(d["observations"][0]))),
            ("wrong_run_type", "fleet", lambda d: d["observations"][0].update(run_id=True)),
            ("too_few_observations", "fleet", lambda d: d["observations"].pop()),
            ("bad_protected", "snap", lambda d: d["branches"]["GBOGEB/CODEX"].update(protected="yes")),
            ("wrong_branch", "snap", lambda d: d["branches"]["GBOGEB/CODEX"].update(branch="develop")),
            ("absent_controls", "contract", lambda d: d["controls"].pop()),
            ("wrong_document_number", "contract", lambda d: d["presentation"].update(corporate_document_number="SCKCEN-FAKE-1")),
        ]
        for name,kind,mutate in mutations:
            with self.subTest(case=name):
                fs=copy.deepcopy(self.fleet);hs=copy.deepcopy(self.snap);cs=copy.deepcopy(self.contract)
                target={"fleet":fs,"snap":hs,"contract":cs}[kind]
                mutate(target)
                with self.assertRaises(ValueError):f.validate(fs,hs,cs)

    def test_verify_rejects_source_manifest_identity_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.make_build(tmp)
            manifest=f.read(Path(tmp)/'manifest.json')
            manifest['source_semantic_sha256']='f'*64
            f.write_json(Path(tmp)/'manifest.json',manifest)
            with self.assertRaisesRegex(ValueError,'source identity'):f.verify(tmp)

    def test_verify_rejects_duplicate_leaf_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.make_build(tmp)
            c=f.read(Path(tmp)/'census.json')
            c['cells'][1]['id']=c['cells'][0]['id']
            f.write_json(Path(tmp)/'census.json',c)
            with self.assertRaisesRegex(ValueError,'cardinality'):f.verify(tmp)

    def test_verify_rejects_false_missing_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.make_build(tmp)
            c=f.read(Path(tmp)/'census.json');c['metrics']['unobserved_cells']=0
            f.write_json(Path(tmp)/'census.json',c)
            with self.assertRaisesRegex(ValueError,'Missing evidence count'):f.verify(tmp)

    def test_verify_rejects_false_main_freshness(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.make_build(tmp)
            c=f.read(Path(tmp)/'census.json');c['metrics']['stale_main_anchors']=0
            f.write_json(Path(tmp)/'census.json',c)
            with self.assertRaisesRegex(ValueError,'Historical anchor'):f.verify(tmp)

    def test_verify_rejects_html_missing_counter(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.make_build(tmp)
            html=Path(tmp)/'index.html';html.write_text('blank',encoding='utf-8')
            f.seal(tmp)
            with self.assertRaisesRegex(ValueError,'HTML observation'):f.verify(tmp)

    def test_build_rejects_missing_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=type('A',(),dict(fleet='/notfound',snapshot=str(SNAP),contract=str(CONTRACT),out=tmp,exact_git_sha=None))()
            with self.assertRaisesRegex(ValueError,'missing'):f.build(args)

    def test_seal_rejects_missing_census(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'Missing census'):f.seal(tmp)

    def test_cli_preflight_pass(self):
        self.assertEqual(f.main(['preflight','--fleet',str(FLEET),'--snapshot',str(SNAP),'--contract',str(CONTRACT)]),0)

    def test_cli_verify_and_seal_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.make_build(tmp)
            self.assertEqual(f.main(['seal','--out',tmp]),0)
            self.assertEqual(f.main(['verify','--out',tmp]),0)

    def test_refresh_readonly_captures_all_five_main_heads(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'snapshot.json';path.write_text(SNAP.read_text(encoding='utf-8'))
            class FakeResponse:
                def __enter__(self):return self
                def __exit__(self,*a):return False
                def read(self,*a):return b'{}'
            fake=lambda *a,**kw:FakeResponse()
            with mock.patch.object(f.urllib.request,'urlopen',side_effect=fake) as fetch, mock.patch.object(f.json,'load',return_value={'commit':{'sha':'a'*40},'protected':True}):
                result=f.refresh_heads(type('A',(),dict(fleet=str(FLEET),snapshot=str(path)))())
            self.assertEqual(result['branches'],6)
            self.assertEqual(fetch.call_count,5)
            self.assertEqual(f.read(path)['branches']['GBOGEB/CODEX']['sha'],'a'*40)

    def test_refresh_rejects_invalid_remote_head(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'snapshot.json';path.write_text(SNAP.read_text())
            class FakeResponse:
                def __enter__(self):return self
                def __exit__(self,*a):return False
            with mock.patch.object(f.urllib.request,'urlopen',return_value=FakeResponse()),mock.patch.object(f.json,'load',return_value={'commit':{'sha':'malformed'},'protected':False}):
                with self.assertRaisesRegex(ValueError,'Invalid live GitHub'):f.refresh_heads(type('A',(),dict(fleet=str(FLEET),snapshot=str(path)))())

    def test_scout_regression_can_add_seventh_observation_in_same_42_cell_cohort(self):
        future=copy.deepcopy(self.fleet)
        original=future['repositories'][0]
        future['observations'].append({'repository':original['repository'],'source_sha':original['head_sha'],'family':'security','run_id':987654321,'job_id':99887766,'run_url':'https://github.com/GBOGEB/ABACUS/actions/runs/987654321','workflow_conclusion':'success','job_conclusion':'success','evidence_class':'GITHUB_NATIVE_METADATA'})
        d=f.build_census(future,self.snap,self.contract,self.digest)
        self.assertEqual((d['metrics']['observed_cells'],d['metrics']['unobserved_cells']),(7,35))
        self.assertIn('Explore 35 missing leaves',f.site_html(d))

    def make_build(self,out):
        opt=type('X',(),dict(fleet=str(FLEET),snapshot=str(SNAP),contract=str(CONTRACT),out=out,exact_git_sha=None))()
        return f.build(opt)


if __name__=='__main__':unittest.main()