import copy
import json
import tempfile
import unittest
from pathlib import Path
from metric_atlas.analytics import validate, analyze, history_stats, matched_comparison, LedgerError, simulate
from metric_atlas.cli import verify_zip
from metric_atlas.render import render_html

ROOT=Path(__file__).resolve().parents[1]
LEDGER=json.loads((ROOT/'data/observations.json').read_text())


class MetricAtlasTests(unittest.TestCase):
    def test_seed_valid(self):
        self.assertTrue(validate(LEDGER))

    def test_native_zip_crc_sha_and_member_bytes(self):
        a=LEDGER['native_archive']
        z=verify_zip(ROOT/'evidence'/a['filename'],a['sha256'])
        self.assertEqual(z['integrity'],'PASS')
        self.assertTrue(z['expected_sha_matches'])
        members={v['name']:v['uncompressed_bytes'] for v in z['members']}
        self.assertEqual(members['lane-process.html'],38236)
        self.assertEqual(members['lane-process.mmd'],4403)
        self.assertEqual(members['lane-process.json'],16695)

    def test_local_66_never_merged_into_8394(self):
        a=analyze(LEDGER)
        self.assertEqual(a['histories']['MC:4-PY-MODULES::branch_coverage']['latest'],52/66)
        self.assertIsNone(a['histories']['ABACUS:PY312_BROAD::branch_coverage']['latest'])

    def test_mismatched_coverage_no_fake_uplift(self):
        a=[r for r in LEDGER['measurements'] if r['scope_id']=='ABACUS:PY312_BROAD' and r['metric']=='statement_coverage']
        c=matched_comparison(a[0],a[1])
        self.assertEqual(c['status'],'UNMATCHED_POPULATION')
        self.assertIsNone(c['delta'])

    def test_negative_numerator_denominator(self):
        bad=copy.deepcopy(LEDGER)
        bad['measurements'][0]['numerator']=67
        with self.assertRaises(LedgerError): validate(bad)

    def test_duplicate_evidence_rejected(self):
        bad=copy.deepcopy(LEDGER)
        bad['measurements'].append(copy.deepcopy(bad['measurements'][0]))
        with self.assertRaises(LedgerError): validate(bad)

    def test_n20_not_fabricated(self):
        a=analyze(LEDGER)
        for h in a['histories'].values():
            self.assertIsNone(h['rolling_n20'])

    def test_series_unequal_denominator(self):
        arr=[r for r in LEDGER['measurements'] if r['metric']=='bd_completion_fraction']
        self.assertEqual(len(arr),4)
        self.assertAlmostEqual(arr[-2]['numerator']/arr[-2]['denominator'],4/9)
        self.assertAlmostEqual(arr[-1]['numerator']/arr[-1]['denominator'],4/18)
        self.assertEqual(arr[-2]['numerator'],arr[-1]['numerator'])

    def test_method_atlas_growth_leads_test_growth(self):
        a=analyze(LEDGER)
        s=a['rankings']['relative_test_growth']
        self.assertEqual(s[0]['scope_id'],'MC:METHOD_ATLAS')
        self.assertAlmostEqual(s[0]['growth_pct'],100*(74/53-1))

    def test_temporal_slope_acceleration(self):
        rows=[{'step':0,'value':1},{'step':1,'value':3},{'step':2,'value':6}]
        h=history_stats(rows)
        self.assertEqual(h['slope_per_pulse'],3)
        self.assertEqual(h['acceleration_per_pulse2'],1)

    def test_simulations_cannot_claim_native(self):
        a=analyze(LEDGER)
        h=a['histories']['MC:METHOD_ATLAS::tests_passed']
        s=simulate(h,3)
        self.assertEqual(s['state'],'SIMULATED_UNCERTIFIED')
        self.assertEqual([x['value'] for x in s['scenario']],[95,116,137])

    def test_html_offline_and_embedded(self):
        html=render_html(LEDGER)
        self.assertIn('CODE PURPLE / GoGREEN',html)
        self.assertIn('lane-process.html',html)
        self.assertNotIn('https://cdn.',html)
        self.assertIn('normalized',html)

    def test_zero_baseline_no_divide_by_zero(self):
        h=history_stats([{'step':0,'value':0},{'step':1,'value':2}])
        self.assertIsNone(h['pct_change'])
        self.assertIsNone(h['normalized_timeline'][0]['index'])

    def test_no_observation_yield_winner(self):
        a=analyze(LEDGER)
        self.assertIsNone(a['interpretation']['yield_winner'])
        self.assertIsNone(a['interpretation']['stability_winner'])


if __name__=='__main__': unittest.main()
