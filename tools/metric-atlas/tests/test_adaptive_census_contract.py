"""Portable owner-repo regression contract for adaptive read-only census adapter."""
from __future__ import annotations
import asyncio
import copy
import json
import tempfile
import unittest
from pathlib import Path
from metric_atlas import adaptive_census as m


def report(num=12):
    files={}
    for i in range(num):
        ex=[[i*10+1,i*10+2]] if i%3 else []
        mi=[[i*10+1,i*10+3],[i*10+2,i*10+4]] if i%2 else []
        files[f'domain/module_{i:03d}.py']={
           'summary':{'num_branches':len(ex)+len(mi),'covered_branches':len(ex),
                 'num_statements':5,'covered_lines':4},
           'executed_branches':ex,'missing_branches':mi}
    return {'files':files}

class ContractTests(unittest.TestCase):
    def setUp(self):
        self.source=m.adapt_coverage_json(report(),repository='GBOGEB/ABACUS',exact_head='a'*40)
        self.plan=m.plan(self.source,caps=(2,4,8))
        self.parts=asyncio.run(m.emit_partials(self.source,self.plan))

    def test_disjoint_three_pulses(self):
        self.assertEqual([v['incremental_modules'] for v in self.plan['slices']],[2,2,4])
        self.assertEqual(len({x['path'] for s in self.plan['slices'] for x in s['selected']}),8)

    def test_local_no_native_claims(self):
        self.assertEqual(self.plan['source_evidence_class'],'LOCAL_COVERAGE_DECLARED_HEAD_NOT_NATIVE')
        self.assertEqual(self.plan['native_ci_jobs_dispatched'],0)
        self.assertEqual(self.plan['merge_admission'],'HOLD')

    def test_partial_immutable_chain(self):
        for i in range(1,3):self.assertEqual(self.parts[i]['parent_receipt_sha256'],self.parts[i-1]['receipt_sha256'])
        self.assertEqual(self.parts,asyncio.run(m.emit_partials(self.source,self.plan)))

    def test_rollup_conservation(self):
        d=m.rollup(self.source,self.plan,self.parts)
        self.assertEqual(d['audit']['sample_modules'],8)
        self.assertEqual(d['audit']['true_denominator_growth_on_frozen_head'],0)
        self.assertIsNone(d['audit']['new_native_test_count'])
        self.assertIsNone(d['audit']['new_confirmed_red_count'])

    def test_breadth_does_not_enable_workers(self):
        d=m.rollup(self.source,self.plan,self.parts)
        self.assertEqual(d['audit']['native_test_workers_launched'],0)
        self.assertEqual(d['audit']['source_writers_launched'],0)
        self.assertEqual(d['decision'],'LOCAL_DISCOVERY_COMPLETE_EXTERNAL_GATES_HOLD')

    def test_exact_duplicate_idempotent(self):
        d1=m.rollup(self.source,self.plan,self.parts)
        d2=m.rollup(self.source,self.plan,self.parts+[copy.deepcopy(self.parts[0])])
        self.assertEqual(d1,d2)

    def test_tampered_coverage_and_new_digest_rejected(self):
        q=copy.deepcopy(self.parts[0]);q['scope_rows'][0]['covered_arcs']+=1
        q['receipt_sha256']=m.digest({k:v for k,v in q.items() if k!='receipt_sha256'})
        with self.assertRaises(m.CensusError):m.verify_partial(self.source,self.plan,q)

    def test_false_first_red_rejected(self):
        q=copy.deepcopy(self.parts[0]);q['new_confirmed_reds']=12
        q['receipt_sha256']=m.digest({k:v for k,v in q.items() if k!='receipt_sha256'})
        with self.assertRaises(m.CensusError):m.verify_partial(self.source,self.plan,q)

    def test_fake_lldb_rejected(self):
        q=copy.deepcopy(self.parts[0]);q['scope_rows'][0]['ldab_execution']='PASSED'
        q['receipt_sha256']=m.digest({k:v for k,v in q.items() if k!='receipt_sha256'})
        with self.assertRaises(m.CensusError):m.verify_partial(self.source,self.plan,q)

    def test_stale_source_head_rejected(self):
        d=copy.deepcopy(self.source);d['exact_head']='b'*40
        with self.assertRaises(m.CensusError):m.verify_manifest(d,self.plan)

    def test_hard_caps_and_concurrency(self):
        for caps in ((2,4,9),(8,4,10),(2,6,10)):
            with self.subTest(caps=caps),self.assertRaises(m.CensusError):m.plan(self.source,caps=caps)
        with self.assertRaises(m.CensusError):m.plan(self.source,caps=(2,4,8),max_readers=5)

    def test_security_does_not_transfer(self):
        p=copy.deepcopy(self.plan);p['security_waiver']=True
        p['manifest_sha256']=m.digest({k:v for k,v in p.items() if k!='manifest_sha256'})
        with self.assertRaises(m.CensusError):m.verify_manifest(self.source,p)

    def test_readonly_emit_path_diff(self):
        d=m.rollup(self.source,self.plan,self.parts)
        with tempfile.TemporaryDirectory() as t:
            m.emit_files(t,self.source,self.plan,self.parts,d)
            self.assertEqual(len((Path(t)/'census_events.ndjson').read_text().splitlines()),3)
            self.assertEqual(len((Path(t)/'census_module_diff.ndjson').read_text().splitlines()),8)

    def test_other_repo_allowlist(self):
        for repo in ('GBOGEB/CODEX','GBOGEB/cryoplant-project'):
            d=m.adapt_coverage_json(report(),repository=repo,exact_head='c'*40)
            self.assertEqual(m.plan(d,caps=(2,4,8))['repository'],repo)
        with self.assertRaises(m.CensusError):m.adapt_coverage_json(report(),repository='random/org',exact_head='a'*40)

if __name__=='__main__':unittest.main()