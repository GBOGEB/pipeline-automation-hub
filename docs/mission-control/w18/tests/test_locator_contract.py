"""Cross-view location and recursive BD contracts, without network or mutation."""
from pathlib import Path
import hashlib
import json
import unittest
import sys

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
import render

class LocatorContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=(BASE/'snapshot.json').read_bytes()
        cls.master=json.loads(cls.raw)
        cls.index=json.loads((BASE/'locator_index.json').read_text(encoding='utf-8'))
        cls.runtime=(BASE/'runtime.js').read_text(encoding='utf-8')

    def test_frozen_master_identity_is_unmodified(self):
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(),
          '8da98db2b6ff4550b40f923d72429366dfe32cb4ac2bad1ff9fc7edcf1e8dcee')
        self.assertEqual(self.master['slug'],'cp-w18-fleet-dov-20261017')
        self.assertEqual(self.master['census']['latest_observed_open'],142)
        self.assertEqual(self.master['controls']['merge_admission'],'HOLD')

    def test_index_has_exact_same_master_digest(self):
        self.assertEqual(self.index['master_sha256'],hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(self.index['count'],len(self.index['locations']))
        self.assertGreaterEqual(self.index['count'],38)
        self.assertFalse(self.index['controls']['auto_comment_post'])
        self.assertEqual(self.index['controls']['merge_admission'],'HOLD')

    def test_unique_stable_deep_links_and_distinct_bd_leaves(self):
        ids=[x['location_id'] for x in self.index['locations']]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertIn('CP-W18/overview/panel-evidence-and-classification',ids)
        self.assertIn('CP-W18/bd/bd-register',ids)
        self.assertIn('CP-W18/overview/figure-two-point-issue-count',ids)
        for item in self.master['bd_queue']:
            self.assertIn('CP-W18/bd/'+item['id'],ids)
        for item in self.index['locations']:
            self.assertTrue(item['route'].startswith('docs/mission-control/w18/'))
            self.assertIn('#',item['route'])
            self.assertIn('github.com/GBOGEB/',item['canonical_issue'])

    def test_local_bd_action_replaces_external_only_footer(self):
        self.assertIn('Open global BD register — 8 actionable leaves',self.runtime)
        self.assertIn('cards.html#bd-register',self.runtime)
        self.assertIn("location.hash='bd@bd-register'",self.runtime)
        self.assertIn('Fleet controller #153',self.runtime)
        self.assertIn('Root owner #85',self.runtime)
        self.assertIn('Local queue #358',self.runtime)

    def test_recursive_w17_w18_status_kept_independent(self):
        m=self.master
        self.assertEqual(m['ci']['w16_historical_workflow_rollup']['success'],24)
        self.assertEqual(m['ci']['w16_historical_workflow_rollup']['failure'],3)
        self.assertEqual(m['ci']['w16_historical_workflow_rollup']['queued'],10)
        self.assertEqual((m['coverage']['four_module']['covered'],m['coverage']['four_module']['eligible']),(231,444))
        self.assertEqual(m['coverage']['phase8_same_blob']['new_covered'],33)
        self.assertFalse(m['coverage']['historical_n14']['comparable_with_w16'])
        self.assertIn('153 first census → 143 intermediate → 142 latest',self.runtime)
        self.assertIn('N+1 security/TOML/Python',self.runtime)
        self.assertIn('B9/coverage and queue-timing',self.runtime)

    def test_comment_composer_has_no_post_api(self):
        self.assertIn('Draft only — nothing is posted automatically',self.runtime)
        self.assertIn('Copy GitHub comment',(BASE/'index.html').read_text(encoding='utf-8'))
        self.assertIn('CP-W18/',self.runtime)
        self.assertIn('MASTER_SHA',self.runtime)
        self.assertIn("window.open(url,'_blank','noopener,noreferrer')",self.runtime)
        self.assertNotIn('api.github.com/repos/GBOGEB/',self.runtime)
        self.assertNotIn('fetch(',self.runtime)

    def test_generated_documents_have_toolbar_dialog_and_lineage(self):
        for name in ('index.html','cards.html','deck.html'):
            s=(BASE/name).read_text(encoding='utf-8')
            self.assertIn('id="devops-toggle"',s)
            self.assertIn('id="devops-dialog"',s)
            self.assertIn('id="devops-copy-comment"',s)
            self.assertIn('id="devops-copy-location"',s)
            self.assertIn('id="source-master"',s)
        self.assertIn('Recursive TODO',(BASE/'index.html').read_text(encoding='utf-8'))
        self.assertIn('RECURSIVE_W17_W18_FOCUS', (BASE/'RECURSIVE_W17_W18_FOCUS.md').name)

    def test_generated_locator_index_rebuild_is_byte_for_byte(self):
        m,b=render.load_contract()
        self.assertEqual(render.locator_index(m,b),(BASE/'locator_index.json').read_bytes())
        man=json.loads((BASE/'manifest.json').read_text(encoding='utf-8'))
        for path,value in man['generated_sha256'].items():
            self.assertEqual(value,hashlib.sha256((BASE/path).read_bytes()).hexdigest())

if __name__=='__main__':
    unittest.main()
