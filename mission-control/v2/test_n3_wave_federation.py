"""No false continuity or unmeasured effect/authority in G3P graph/SIPOC."""
import copy
import json
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

HERE=Path(__file__).parent
sys.path.insert(0,str(HERE))
import n3_wave_federation as fed

ROOT=HERE.parent/'federation-atlas'
FILES=[ROOT/'CBD_GOLDEN_GRAPH_N3_20261017.json',ROOT/'CBD_GOLDEN_GRAPH_N6_20261017.json']


class Tags(HTMLParser):
    def __init__(self):super().__init__();self.tags=[]
    def handle_starttag(self,tag,attrs):self.tags.append((tag,dict(attrs)))


class WaveFederationTests(unittest.TestCase):
    def setUp(self):self.ledgers=[json.loads(p.read_text()) for p in FILES]
    def graph(self):return fed.compile_waves(self.ledgers)

    def test_structural_counts_and_gap(self):
        p=self.graph();m=p['metrics']
        self.assertEqual((m['waves'],m['pulses'],m['edge_count']),(2,6,5))
        self.assertEqual(m['intervening_unproven_source_boundaries'],1)
        self.assertEqual(sum(e['evidence']=='DECLARED_GAP' for e in p['edges']),1)

    def test_no_causal_or_admission_promotion(self):
        p=self.graph()
        self.assertFalse(any(e['causal_confirmed'] or e['source_ancestry_proven'] for e in p['edges']))
        self.assertEqual(p['merge_admission'],'HOLD')
        self.assertIsNone(p['metrics']['matched_coverage_delta'])
        self.assertEqual(p['metrics']['authenticated_native_pulse_receipts'],0)

    def test_sipoc_five_components(self):
        x=self.graph()['sipoc']
        for key in ('supplier','inputs','process','outputs','customer'):
            self.assertTrue(x[key])
        self.assertIn('UNKNOWN',x['feeder_health'])

    def test_determinism_and_no_mutation(self):
        orig=copy.deepcopy(self.ledgers)
        self.assertEqual(self.graph(),self.graph())
        self.assertEqual(self.ledgers,orig)

    def test_bad_mission_rejected(self):
        self.ledgers[1]['mission']['id']='BAD-MISSION'
        with self.assertRaisesRegex(ValueError,'qualified pulse identity mismatch|foreign mission'):self.graph()

    def test_skipped_wave_ordinal_rejected(self):
        self.ledgers[1]['start_ordinal']=7
        with self.assertRaises(ValueError):self.graph()

    def test_duplicate_wave_rejected(self):
        self.ledgers[1]=copy.deepcopy(self.ledgers[0])
        with self.assertRaisesRegex(ValueError,'duplicate wave'):self.graph()

    def test_no_partial_wave_masquerade(self):
        self.ledgers[1]['receipts'].pop()
        with self.assertRaisesRegex(ValueError,'partial or blocked wave'):self.graph()

    def test_mermaid_uses_dashed_gap(self):
        m=fed.mermaid(self.graph())
        self.assertEqual(m.count('-.->'),1)
        self.assertEqual(m.count('-->'),4)

    def test_svg_shapes_and_accessibility(self):
        h=fed.html_report(self.graph());p=Tags();p.feed(h)
        self.assertEqual(sum(t=='circle' for t,_ in p.tags),6)
        self.assertIn('aria-label="Six directed',h)
        self.assertIn('stroke-dasharray',h)
        self.assertEqual(h.count('<script>'), 1)
        self.assertNotIn('<script src=', h)
        self.assertIn('id="reload"', h)
        self.assertIn('id="ordinal"', h)

    def test_cross_wave_equal_sha_remains_unverified(self):
        # The sha record may be equal without an authenticated Git ancestry proof.
        last=self.ledgers[0]['receipts'][-1]['output_source_sha']
        self.ledgers[1]['mission']['start_sha']=last
        self.ledgers[1]['receipts'][0]['input_source_sha']=last
        from n3_continuation import digest
        for i in range(1, len(self.ledgers[1]['receipts'])):
            self.ledgers[1]['receipts'][i]['prev_receipt_digest']=digest(self.ledgers[1]['receipts'][i-1])
        p=self.graph()
        e=[e for e in p['edges'] if e['relationship']=='inter_wave_source_lineage'][0]
        self.assertEqual(e['evidence'],'LEDGER_HEAD_EQUALITY')
        self.assertFalse(e['source_ancestry_proven'])

    def test_renderer_refuses_unsafe_authority(self):
        p=self.graph();p['merge_admission']='PASS'
        with self.assertRaises(ValueError):fed.html_report(p)

    def test_cli_outputs_reproducible_and_readonly(self):
        with tempfile.TemporaryDirectory() as t:
            out=Path(t)/'artifacts'
            with patch.object(sys,'argv',['n3_wave_federation.py','--ledgers',*(str(p) for p in FILES),'--out-dir',str(out)]):
                fed.main()
            j=json.loads((out/'g3p-lineage.json').read_text())
            self.assertEqual(j['metrics']['pulses'],6)
            self.assertIn('-.->',(out/'g3p-lineage.mmd').read_text())
            self.assertIn('UNKNOWN',(out/'g3p-lineage.html').read_text())


if __name__=='__main__':unittest.main()
