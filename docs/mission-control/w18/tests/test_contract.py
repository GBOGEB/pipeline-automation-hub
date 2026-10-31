"""W18 communication master/source-bound negative and positive controls.

Run: python -m unittest discover -s tests -v from the W18 directory.
No network, no private source, no GitHub write operations.
"""
import copy
import hashlib
import json
import re
import unittest
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0,str(BASE))
import render

class ContractTests(unittest.TestCase):
    def setUp(self):
        self.raw=(BASE/'snapshot.json').read_bytes()
        self.d=json.loads(self.raw)

    def test_master_contract_passes(self):
        x,raw=render.load_contract()
        self.assertEqual(x['slug'],'cp-w18-fleet-dov-20261017')
        self.assertEqual(raw,self.raw)

    def test_count_and_ages_exact(self):
        self.assertEqual(sum(x['open'] for x in self.d['census']['repos']),142)
        self.assertEqual(sum(x['open'] for x in self.d['census']['age_utc_date_windows']),142)
        self.assertEqual(153-142,11)
        self.assertEqual(sum(x['count'] for x in self.d['census']['verified_closure_categories']),11)

    def test_closure_classes_cannot_count_as_root_repairs(self):
        self.assertEqual(self.d['controls']['formal_root_closure_credit_this_wave'],0)
        for x in self.d['census']['verified_closure_categories']:
            self.assertEqual(x['engineering_root_credit'],0)
        self.assertEqual(self.d['controls']['merge_admission'],'HOLD')

    def test_b0_not_b9_or_four_module_other_epoch(self):
        self.assertEqual(self.d['coverage']['historical_n14']['comparable_with_w16'],False)
        self.assertIsNone(self.d['coverage']['b9_diff_coverage_current'])
        self.assertEqual(self.d['coverage']['four_module'],{'covered':231,'eligible':444,'uncovered':213})
        self.assertEqual(self.d['coverage']['phase8_same_blob']['new_covered'],33)

    def test_unknown_metrics_must_stay_null(self):
        self.assertIsNone(self.d['controls']['original_conversation_prompt_count'])
        self.assertIsNone(self.d['ci']['queue_p95_seconds'])
        self.assertIsNone(self.d['statistics']['dopportunity_total_for_six_sigma'])
        self.assertEqual(len([x for x in self.d['metrics'] if x['value'] is None]),3)

    def test_unqualified_statistics_not_promoted(self):
        for key in ['pca_qualified','bt_qualified','six_sigma_qualified']:
            self.assertIs(self.d['controls'][key],False)
        self.assertIsNone(self.d['statistics']['causal_closure_fraction'])
        self.assertEqual(self.d['statistics']['bt_pairs'],0)

    def test_dod_dov_and_root_ids_unique(self):
        for k in ['session_dod','global_dov','bd_queue','metrics']:
            ids=[x['id'] for x in self.d[k]]
            self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(sum(x['state']=='PASS' for x in self.d['global_dov']),2)
        self.assertEqual(len(self.d['global_dov']),8)

    def test_links_bound_to_gbogeb_github(self):
        urls=[]
        for x in self.d['metrics']:urls.append(x['source'])
        for x in self.d['bd_queue']:urls.append(x['source'])
        for x in self.d['global_dov']:urls.append(x['evidence'])
        for x in self.d['session_dod']:urls.append(x['evidence'])
        for url in urls:
            self.assertTrue(re.fullmatch(r'https://github\.com/GBOGEB/[A-Za-z0-9_./#?=\-]+',url),url)

    def test_three_html_modes_one_snapshot_sha(self):
        sha=hashlib.sha256(self.raw).hexdigest()
        for name,mode in [('index.html','dashboard'),('cards.html','cards'),('deck.html','deck')]:
            text=(BASE/name).read_text()
            self.assertIn(f'content="{sha}"',text)
            self.assertIn('data-mode="'+mode+'"',text)
            self.assertIn('id="source-master"',text)
            self.assertIn('231',text)
            self.assertIn('142',text)
            self.assertIn('HOLD',text)

    def test_manifest_checksums_reproduce(self):
        m=json.loads((BASE/'manifest.json').read_text())
        self.assertEqual(m['master_sha256'],hashlib.sha256(self.raw).hexdigest())
        for name,d in m['generated_sha256'].items():
            self.assertEqual(hashlib.sha256((BASE/name).read_bytes()).hexdigest(),d)

    def test_fail_closed_on_wrong_denominator(self):
        d=copy.deepcopy(self.d);d['coverage']['four_module']['eligible']=446
        saved=render.SNAPSHOT
        import tempfile
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'wrong.json';p.write_text(json.dumps(d))
            render.SNAPSHOT=p
            try:
                with self.assertRaisesRegex(ValueError,'source epoch coverage arithmetic'):
                    render.load_contract()
            finally:render.SNAPSHOT=saved

    def test_fail_closed_on_unattributed_close_cardinality(self):
        d=copy.deepcopy(self.d);d['census']['net_change']=-14
        saved=render.SNAPSHOT
        import tempfile
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'wrong.json';p.write_text(json.dumps(d))
            render.SNAPSHOT=p
            try:
                with self.assertRaisesRegex(ValueError,'non-reproducible issue delta'):
                    render.load_contract()
            finally:render.SNAPSHOT=saved

    def test_render_reproducible_byte_for_byte(self):
        d,raw=render.load_contract()
        for mode,name in [('dashboard','index.html'),('cards','cards.html'),('deck','deck.html')]:
            self.assertEqual(render.html_page(d,raw,mode),(BASE/name).read_bytes())
        self.assertEqual(render.metric_csv(d),(BASE/'metrics.csv').read_bytes())

if __name__=='__main__':unittest.main()


def test_zz_canary_g_pah():
    assert False, "red canary: proves CI collects this family"
