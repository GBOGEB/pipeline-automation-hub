import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime

here = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('bd_queue_wave', here.parent/'bd_queue_wave.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
H = 'a' * 40
J = 'b' * 40


def pr(n=1, sha=H, repo='GBOGEB/ABACUS'):
    return {'repo':repo, 'number':n, 'head_sha':sha, 'base':'main', 'draft':False}


def raw_pr(n=1, sha=H):
    return {'number':n, 'head':{'sha':sha}, 'base':{'ref':'main'}, 'state':'open', 'draft':False}


def run(n=1, name='CI Workflow Governance', sha=H, result='failure', attempt=1, wid=1):
    return {'id':n,'name':name,'workflow_id':wid,'head_sha':sha,'event':'pull_request',
            'status':'completed' if result is not None else 'in_progress', 'conclusion':result,
            'run_attempt':attempt, 'created_at':'2026-10-17T08:00:00Z',
            'run_started_at':'2026-10-17T08:00:15Z'}


class Fake:
    def __init__(self, prs=None, issues=None, runs=None):
        self.prs = prs or {}
        self.issues = issues or {}
        self.runs = runs or {}

    def paginate(self, route, key=None):
        if '/pulls?' in route:
            return self.prs.get(route.split('/repos/')[1].split('/pulls?')[0], [])
        if '/search/issues?' in route:
            from urllib.parse import unquote
            q = unquote(route.split('?q=')[1]); repo = q.split('repo:')[1].split()[0]
            return self.issues.get(repo, [])
        raise AssertionError(route)

    def get(self, route):
        sha = route.split('head_sha=')[1].split('&')[0]
        if sha not in self.runs:
            return {'total_count':0,'workflow_runs':[]}
        return self.runs[sha]


class Tests(unittest.TestCase):
    def test_schema(self): self.assertEqual('codepurple.bd-queue-wave.v1', mod.SCHEMA)
    def test_repos_not_modifiable(self): self.assertEqual(4, len(mod.REPOS))
    def test_families(self):
        self.assertEqual('CONFIDENTIALITY',mod.family('a10-guard'))
        self.assertEqual('GOVERNANCE',mod.family('CI Workflow Governance'))
        self.assertEqual('SECURITY',mod.family('Bandit Disjoint Census'))
        self.assertEqual('PYTHON_MATRIX',mod.family('CI - ABACUS Matrix'))
        self.assertEqual('FORMAT',mod.family('Validate Docs'))
        self.assertEqual('INTEGRATED_SUITE',mod.family('CI/CD Test Suite'))
        self.assertEqual('OTHER',mod.family('Unexpected'))
    def test_missing_family(self): self.assertEqual('OTHER',mod.family(None))
    def test_queue_seconds(self): self.assertEqual(15,mod.queue_seconds(run()))
    def test_queue_missing(self):
        a=run(); a.pop('run_started_at'); self.assertIsNone(mod.queue_seconds(a))
    def test_queue_negative(self):
        a=run(); a['run_started_at']='2026-10-17T07:59:59Z'; self.assertIsNone(mod.queue_seconds(a))
    def test_queue_excessive(self):
        a=run(); a['run_started_at']='2026-12-17T08:00:00Z'; self.assertIsNone(mod.queue_seconds(a))
    def test_queue_invalid(self):
        a=run(); a['created_at']='garbled'; self.assertIsNone(mod.queue_seconds(a))
    def test_nearest_rank(self):
        self.assertEqual(3,mod.percentile([1,2,3,4,5],.5)); self.assertEqual(5,mod.percentile([1,2,3,4,5],.95))
        self.assertIsNone(mod.percentile([],.5))
    def test_percentile_ignores_nan(self): self.assertEqual(2,mod.percentile([float('nan'),-1,2], .95))
    def test_validate_prs(self):
        self.assertEqual([1,2],[x['number'] for x in mod.validate_prs([raw_pr(2),raw_pr(1)], 'GBOGEB/ABACUS')])
    def test_duplicate_pr(self):
        with self.assertRaisesRegex(ValueError,'duplicate'):
            mod.validate_prs([raw_pr(),raw_pr()], 'GBOGEB/ABACUS')
    def test_bad_pr_sha(self):
        with self.assertRaisesRegex(ValueError,'SHA'):
            mod.validate_prs([raw_pr(1,'bogus')], 'GBOGEB/ABACUS')
    def test_closed_pr(self):
        r=raw_pr();r['state']='closed'
        with self.assertRaisesRegex(ValueError,'non-open'):mod.validate_prs([r], 'GBOGEB/ABACUS')
    def test_invalid_pr_object(self):
        with self.assertRaises(ValueError):mod.validate_prs([None], 'GBOGEB/ABACUS')
    def test_rerun_latest(self):
        p=pr(); r=mod.summarize_runs(p,{'total_count':2,'workflow_runs':[run(1,attempt=1),run(2,result='success',attempt=2)]})
        self.assertEqual('NO_OBSERVED_RED',r['status']); self.assertEqual(1,r['run_cohort_count']); self.assertEqual(1,r['retry_attempt_excess_proxy'])
    def test_duplicate_run_same_attempt(self):
        p=pr(); r=mod.summarize_runs(p,{'total_count':2,'workflow_runs':[run(1),run(9,result='success')]})
        self.assertEqual('NO_OBSERVED_RED',r['status'])
    def test_mixed_workflows(self):
        a=run(2,name='CI/CD Test Suite',wid=2,result='success')
        r=mod.summarize_runs(pr(),{'total_count':2,'workflow_runs':[run(),a]})
        self.assertEqual((1,1),(r['green_workflows'],r['red_workflows']))
        self.assertEqual('GOVERNANCE',r['manifestations'][0]['family'])
        self.assertFalse(r['manifestations'][0]['causal_root_verified'])
    def test_head_rejection(self):
        with self.assertRaisesRegex(ValueError,'head'):mod.summarize_runs(pr(),{'total_count':1,'workflow_runs':[run(sha=J)]})
    def test_event_rejection(self):
        a=run();a['event']='push'
        with self.assertRaisesRegex(ValueError,'non-PR'):mod.summarize_runs(pr(),{'total_count':1,'workflow_runs':[a]})
    def test_partial_page_rejected(self):
        with self.assertRaisesRegex(ValueError,'partial'):mod.summarize_runs(pr(),{'total_count':101,'workflow_runs':[run()]})
    def test_missing_total_rejected(self):
        with self.assertRaises(ValueError):mod.summarize_runs(pr(),{'workflow_runs':[run()]})
    def test_null_run_pending(self):
        r=mod.summarize_runs(pr(),{'total_count':1,'workflow_runs':[run(result=None)]})
        self.assertEqual('UNKNOWN',r['status'])
    def test_empty_runs_unknown(self):
        self.assertEqual('UNKNOWN',mod.summarize_runs(pr(),{'total_count':0,'workflow_runs':[]})['status'])
    def test_invalid_run_id(self):
        a=run();a['id']='1'
        with self.assertRaises(ValueError):mod.summarize_runs(pr(),{'total_count':1,'workflow_runs':[a]})
    def test_invalid_attempt(self):
        a=run();a['run_attempt']=0
        with self.assertRaises(ValueError):mod.summarize_runs(pr(),{'total_count':1,'workflow_runs':[a]})
    def test_issue_page(self):
        r=mod.summarize_issue_page([{'number':2,'state':'open'},{'number':1,'state':'open'}],'GBOGEB/ABACUS',2)
        self.assertEqual([1,2],r['issue_ids'])
    def test_issue_duplicate(self):
        with self.assertRaises(ValueError):mod.summarize_issue_page([{'number':1,'state':'open'}]*2,'x',2)
    def test_issue_pr_rejection(self):
        with self.assertRaises(ValueError):mod.summarize_issue_page([{'number':1,'state':'open','pull_request':{}}],'x',1)
    def test_issue_partial(self):
        with self.assertRaises(ValueError):mod.summarize_issue_page([{'number':1,'state':'open'}],'x',2)
    def test_aggregation(self):
        a=mod.summarize_runs(pr(),{'total_count':1,'workflow_runs':[run()]})
        summary,manifest=mod.aggregate([a],[{'repository':'GBOGEB/ABACUS','open_issues':2,'issue_ids':[1,2]}])
        self.assertEqual((1,2,3,1),(summary['open_prs'],summary['open_issues'],summary['open_items'],summary['manifestations']))
        self.assertEqual(1,summary['family_groups'][0]['affected_prs'])
        self.assertIsNone(summary['independent_root_count'])
        self.assertIsNone(summary['matched_coverage_numerator'])
    def test_aggregate_duplicate(self):
        with self.assertRaisesRegex(ValueError,'duplicate PR'):mod.aggregate([pr(),pr()],[])
    def test_real_output_files_and_replay(self):
        rows=[mod.summarize_runs(pr(),{'total_count':1,'workflow_runs':[run()]})]
        summary,m=mod.aggregate(rows,[])
        with tempfile.TemporaryDirectory() as d:
            x=mod.write_outputs(d,summary,rows,m)
            self.assertEqual(6,len(x['files']))
            a={k:Path(d,k).read_bytes() for k in x['files']}
            mod.write_outputs(d,summary,rows,m)
            self.assertEqual(a,{k:Path(d,k).read_bytes() for k in x['files']})
            self.assertEqual(1,len(json.loads(Path(d,'bd_manifestations.json').read_text())))
            self.assertTrue(Path(d,'bd_pr_queue.csv').read_text().startswith('repository,pr,'))
    def test_public_only_explicit_three_sources(self):
        self.assertEqual(mod.REPOS[:-1], mod.PUBLIC_REPOS)
        self.assertNotIn(mod.PRIVATE_OWNER_REPO, mod.PUBLIC_REPOS)

    def test_public_census_does_not_probe_private(self):
        class OwnerSafe(Fake):
            def paginate(self, route, key=None):
                if 'cryoplant-project' in route:
                    raise AssertionError("private QPS API was queried")
                return super().paginate(route, key)
        fake = OwnerSafe(
            prs={'GBOGEB/ABACUS': [raw_pr()]},
            issues={'GBOGEB/ABACUS': [{'number': 9, 'state': 'open'}]},
            runs={H: {'total_count': 1, 'workflow_runs': [run()]}}
        )
        summary, prs, reds = mod.scan_public(fake, max_parallel=2)
        self.assertEqual(mod.PUBLIC_SCOPE, summary['scope'])
        self.assertEqual(3, len(summary['issues']))
        self.assertEqual(1, summary['open_issues'])
        self.assertEqual(1, summary['open_prs'])
        self.assertEqual(1, len(reds))
        self.assertEqual([mod.PRIVATE_OWNER_REPO],
                         summary['unobserved_private_repositories'])
        self.assertIsNone(summary['private_qps_open_issues'])
        self.assertIsNone(summary['private_qps_root_closures'])
        self.assertFalse(summary['full_four_repo_census'])
        self.assertEqual('HOLD', summary['federation_admission'])
        self.assertTrue(summary['public_is_not_global_denominator'])

    def test_public_census_denominator_does_not_include_qps(self):
        fake = Fake(issues={
            'GBOGEB/ABACUS': [{'number': 1, 'state': 'open'}],
            'GBOGEB/CODEX': [{'number': 2, 'state': 'open'}],
            'GBOGEB/pipeline-automation-hub': [{'number': 3, 'state': 'open'}],
            'GBOGEB/cryoplant-project': [{'number': n, 'state': 'open'} for n in range(10, 25)]
        })
        summary, rows, red = mod.scan_public(fake)
        self.assertEqual((3, 0, 3), (summary['open_issues'], len(rows), summary['open_items']))
        self.assertEqual([], red)
        self.assertEqual('HOLD_OWNER_PRIVATE_RECEIPT_REQUIRED', summary['private_receipt_status'])

    def test_public_census_fails_if_a_public_source_is_denied(self):
        class Denied(Fake):
            def paginate(self, route, key=None):
                if '/repos/GBOGEB/CODEX/pulls?' in route:
                    raise OSError('public source denied')
                return super().paginate(route, key)
        with self.assertRaisesRegex(OSError, 'denied'):
            mod.scan_public(Denied())

    def test_public_snapshot_receipt_is_explicit_partial(self):
        summary, rows, manifest = mod.scan_public(Fake())
        with tempfile.TemporaryDirectory() as root:
            mod.write_outputs(root, summary, rows, manifest)
            parsed = json.loads(Path(root, 'bd_summary.json').read_text())
            receipt = json.loads(Path(root, 'bd_files_sha256.json').read_text())
            self.assertEqual('LIVE_PUBLIC_THREE_REPO_PARTIAL_QPS_UNKNOWN', parsed['scope'])
            self.assertTrue(receipt['source_is_live_api'])
            self.assertFalse(receipt['complete_federation_observed'])
            self.assertIsNone(parsed['private_qps_open_prs'])

    def test_public_cli_dry_fixture(self):
        snapshot, prs, manifestations = mod.scan_public(Fake())
        with tempfile.TemporaryDirectory() as root:
            with patch.object(mod, 'scan_public',
                              return_value=(snapshot, prs, manifestations)):
                with patch('sys.argv', ['bd_queue_wave.py', '--public-only', '--out', root]):
                    self.assertEqual(0, mod.main())
            self.assertEqual('HOLD', json.loads(Path(root, 'bd_summary.json').read_text())['federation_admission'])

    def test_scan_fully_mocked(self):
        fake=Fake(prs={'GBOGEB/ABACUS':[raw_pr()]},issues={'GBOGEB/ABACUS':[{'number':15,'state':'open'}]},runs={H:{'total_count':1,'workflow_runs':[run()]}})
        summary,rows,manifest=mod.scan(fake,repos=['GBOGEB/ABACUS'],max_parallel=2)
        self.assertEqual(2,summary['open_items']);self.assertEqual(1,len(manifest));self.assertEqual(0,summary['prs_unknown'])
    def test_scan_records_bad_run_as_unknown(self):
        fake=Fake(prs={'GBOGEB/ABACUS':[raw_pr()]},runs={H:{'total_count':1,'workflow_runs':[run(sha=J)]}})
        summary,rows,manifest=mod.scan(fake,repos=['GBOGEB/ABACUS'])
        self.assertEqual(1,summary['prs_unknown']);self.assertEqual(1,len(summary['errors']));self.assertEqual(0,len(manifest))
    def test_scan_unknown_repo_denied(self):
        with self.assertRaises(ValueError):mod.scan(Fake(),repos=['other/owner'])
    def test_scan_bad_capacity(self):
        with self.assertRaises(ValueError):mod.scan(Fake(),repos=['GBOGEB/ABACUS'],max_parallel=0)
    def test_paginate(self):
        class Stub(mod.GitHubReader):
            def __init__(self): pass
            def get(self,route):return [{'number':1}]
        self.assertEqual(1,len(Stub().paginate('/anything')))
    def test_bad_api_path(self):
        with self.assertRaises(ValueError):mod.GitHubReader().get('/../sensitive')
    def test_json_stability(self):
        self.assertEqual(mod.stable({'z':1,'a':2}),mod.stable({'a':2,'z':1}))

if __name__=='__main__':unittest.main()

class EdgeCoverageTests(unittest.TestCase):
    def test_nonlatest_same_workflow_does_not_count(self):
        a = mod.summarize_runs(pr(),{'total_count':2,'workflow_runs':[run(3,attempt=3,result='success'),run(2,attempt=2)]})
        self.assertEqual(0,a['red_workflows']); self.assertEqual(1,a['run_cohort_count'])
    def test_cancelled_and_unknown_conclusions(self):
        x=run(1,result='cancelled');y=run(2,wid=2,result='skipped')
        z=mod.summarize_runs(pr(),{'total_count':2,'workflow_runs':[x,y]})
        self.assertEqual(1,z['cancelled_workflows']);self.assertEqual(1,z['unknown_workflows']);self.assertEqual('UNKNOWN',z['status'])
    def test_no_queue_timestamp_excludes_sample(self):
        x=run();x['run_started_at']='invalid'
        self.assertEqual([],mod.summarize_runs(pr(),{'total_count':1,'workflow_runs':[x]})['queue_latency_samples_seconds'])
    def test_github_get_with_mock_transport(self):
        class API:
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self):return b'{}'
        with patch.object(mod.urllib.request,'urlopen',return_value=API()) as mocked:
            self.assertEqual({},mod.GitHubReader('token','https://api.github.com').get('/repos/owner/repo'))
            self.assertIn('Authorization',mocked.call_args.args[0].headers)
    def test_pagination_total_count_mismatch_fails(self):
        class Bad(mod.GitHubReader):
            def __init__(self):pass
            def get(self,path):return {'items':[{'number':1}], 'total_count':3}
        with self.assertRaisesRegex(ValueError,'incomplete total_count'):Bad().paginate('/search/issues?q=x',key='items')
    def test_pagination_two_pages(self):
        class Pages(mod.GitHubReader):
            def __init__(self):self.n=0
            def get(self,path):
                self.n+=1
                return [{'number':i} for i in range(100)] if self.n==1 else [{'number':101}]
        self.assertEqual(101,len(Pages().paginate('/repos/example/pulls')))
    def test_pagination_overlimit(self):
        class Endless(mod.GitHubReader):
            def __init__(self):pass
            def get(self,path):return [{'number':i} for i in range(100)]
        with self.assertRaisesRegex(ValueError,'capacity exceeded'):Endless().paginate('/repos/example/pulls')
    def test_pagination_invalid_items(self):
        class Invalid(mod.GitHubReader):
            def __init__(self):pass
            def get(self,path):return {'items':'not_list'}
        with self.assertRaisesRegex(ValueError,'invalid paged'):Invalid().paginate('/search/issues?q=x',key='items')
    def test_main_executes_fixture_and_writes_real_files(self):
        sample=mod.summarize_runs(pr(), {'total_count':1,'workflow_runs':[run()]})
        summary,manifest=mod.aggregate([sample],[])
        with tempfile.TemporaryDirectory() as td:
            with patch.object(mod, 'scan',return_value=(summary,[sample],manifest)):
                with patch('sys.argv',['bd_queue_wave.py','--out',td]):
                    self.assertEqual(0,mod.main())
            self.assertTrue((Path(td)/'BD_REPORT.md').is_file())
