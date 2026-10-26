"""Static fail-closed HTML/manifest tests (browser fetch still requires runtime QA)."""
import json
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/'federation-atlas'
HTML=ROOT/'G3P_LIVE_LEDGER.html'
MANIFEST=ROOT/'G3P_LIVE_SOURCES_v1.json'

class G3PLiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html=HTML.read_text(encoding='utf-8')
        cls.m=json.loads(MANIFEST.read_text(encoding='utf-8'))
    def test_manifest_authority(self):
        self.assertIs(self.m['authority_transfer'],False)
        self.assertEqual(self.m['merge_admission'],'HOLD')
    def test_manifest_order_and_waves(self):
        self.assertEqual([(w['start'],w['end']) for w in self.m['waves']],[(1,3),(4,6),(7,9),(10,12)])
    def test_real_source_refs(self):
        self.assertEqual(len(set((w['ref'],w['path']) for w in self.m['waves'])),4)
        self.assertTrue(all(w['path'].startswith('mission-control/federation-atlas/') for w in self.m['waves']))
    def test_manual_and_cyclic_refresh(self):
        for term in ('addEventListener("click",refresh)','setInterval','visibilitychange','cache:"no-store"','Date.now()'):
            self.assertIn(term,self.html)
    def test_data_not_authority(self):
        for term in ('"HOLD"','authority_transfer===false','security_waiver===false','merge_admission==="HOLD"'):
            self.assertIn(term,self.html)
    def test_manifest_dynamic_growth(self):
        for term in ('G3P_LIVE_SOURCES_v1.json','manifest.waves.map','sources=next','w.end===w.start+2'):
            self.assertIn(term,self.html)
    def test_svg_and_accessibility(self):
        for term in ('role="img"','aria-label','addEventListener("keydown"','stroke-dasharray','id="growth"'):
            self.assertIn(term,self.html)
    def test_no_remote_mutation(self):
        self.assertNotIn('method:"POST"',self.html)
        self.assertNotIn('method:"PUT"',self.html)
        self.assertNotIn('Authorization:',self.html)
    def test_no_script_dependency(self):
        self.assertEqual(self.html.count('<script>'),1)
        self.assertEqual(self.html.count('</script>'),1)
    def test_status_unknown_not_zero(self):
        self.assertIn('UNKNOWN',self.html)
        self.assertIn('PARTIAL_UNKNOWN',self.html)

if __name__=='__main__':unittest.main()
